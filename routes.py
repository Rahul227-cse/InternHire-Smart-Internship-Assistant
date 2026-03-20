from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from extensions import db
from models import Skill, Application, LearningPath, LearningStepCompletion
from forms import SkillForm, ApplicationForm
import os
import json
from ai_helper import analyze_job, get_recommendations, generate_interview_prep, chat_with_assistant, search_jobs_live

routes = Blueprint('routes', __name__)

@routes.app_template_filter('from_json')
def from_json_filter(value):
    import json
    if not value:
        return []
    try:
        return json.loads(value)
    except Exception:
        return []

@routes.route('/')
def index():
    if current_user.is_authenticated:
        if current_user.is_profile_setup:
            return redirect(url_for('routes.dashboard'))
        return redirect(url_for('auth.profile_setup'))
    return render_template('index.html')

@routes.route('/dashboard')
@login_required
def dashboard():
    apps = Application.query.filter_by(user_id=current_user.id).all()
    stats = {
        'total_apps': len(apps),
        'applied': len([a for a in apps if a.status == 'Applied']),
        'interviews': len([a for a in apps if a.status == 'Interview Scheduled']),
        'rejections': len([a for a in apps if a.status == 'Rejected']),
        'offers': len([a for a in apps if a.status == 'Offer Received'])
    }
    recent_apps = Application.query.filter_by(user_id=current_user.id).order_by(Application.created_at.desc()).limit(5).all()
    
    
    user_skills = [s.name for s in Skill.query.filter_by(user_id=current_user.id).all()]
    from utils import get_recommendations
    recommendations = get_recommendations(user_skills)[:2] # Top 2 for dashboard
    
    return render_template('dashboard.html', title='Dashboard', stats=stats, recent_apps=recent_apps, recommendations=recommendations)

@routes.route('/profile', methods=['GET'])
@login_required
def profile():
    return render_template('profile.html', title='Profile')

@routes.route('/edit_profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    from forms import EditProfileForm
    form = EditProfileForm()
    
    if form.validate_on_submit():
        profile = current_user.profile
        profile.full_name = form.full_name.data
        profile.college = form.college.data
        profile.branch = form.branch.data
        profile.year_of_study = form.year_of_study.data
        profile.target_role = form.target_role.data
        profile.github_link = form.github_link.data
        profile.linkedin_link = form.linkedin_link.data
        
        db.session.commit()
        flash('Your profile has been updated successfully!', 'success')
        return redirect(url_for('routes.profile'))
        
    elif request.method == 'GET':
        profile = current_user.profile
        form.full_name.data = profile.full_name
        form.college.data = profile.college
        form.branch.data = profile.branch
        form.year_of_study.data = profile.year_of_study
        form.target_role.data = profile.target_role
        form.github_link.data = profile.github_link
        form.linkedin_link.data = profile.linkedin_link
        
    return render_template('edit_profile.html', title='Edit Profile', form=form)

@routes.route('/skills', methods=['GET', 'POST'])
@login_required
def skills():
    form = SkillForm()
    if form.validate_on_submit():
        # Check if skill already exists for this user
        existing_skill = Skill.query.filter_by(name=form.name.data.strip(), user_id=current_user.id).first()
        if existing_skill:
            flash(f'Skill "{form.name.data}" is already added.', 'info')
        else:
            skill = Skill(name=form.name.data.strip(), user=current_user)
            db.session.add(skill)
            db.session.commit()
            flash(f'Skill "{form.name.data}" added successfully!', 'success')
        return redirect(url_for('routes.skills'))
    
    user_skills = Skill.query.filter_by(user_id=current_user.id).all()
    
    # Check if there are detected skills from a resumed upload
    detected_skills = request.args.get('detected_skills')
    if detected_skills:
        import json
        try:
            detected_skills = json.loads(detected_skills)
        except:
            detected_skills = []
    else:
        detected_skills = []
        
    return render_template('skills.html', title='Skills', form=form, skills=user_skills, detected_skills=detected_skills)

@routes.route('/upload_resume', methods=['POST'])
@login_required
def upload_resume():
    if 'resume' not in request.files:
        flash('No file part', 'danger')
        return redirect(url_for('routes.profile'))
        
    file = request.files['resume']
    if file.filename == '':
        flash('No selected file', 'danger')
        return redirect(url_for('routes.profile'))
        
    if file and file.filename.lower().endswith('.pdf'):
        from utils import extract_text_from_pdf, extract_skills_from_jd
        import json
        
        text = extract_text_from_pdf(file)
        if text:
            detected_skills = extract_skills_from_jd(text)
            
            # Filter out skills the user already has
            user_skills = [s.name.lower() for s in Skill.query.filter_by(user_id=current_user.id).all()]
            novel_skills = [s for s in detected_skills if s.lower() not in user_skills]
            
            if novel_skills:
                flash(f'Successfully parsed resume and found {len(novel_skills)} new skills!', 'success')
                # Redirect to skills page with detected skills to review
                return redirect(url_for('routes.skills', detected_skills=json.dumps(novel_skills)))
            else:
                flash('Resume parsed, but no new skills were found that you do not already have.', 'info')
        else:
            flash('Failed to extract text from the PDF. It might be scanned or image-based.', 'warning')
    else:
        flash('Invalid file format. Please upload a PDF.', 'danger')
        
    return redirect(url_for('routes.profile'))

@routes.route('/add_extracted_skills', methods=['POST'])
@login_required
def add_extracted_skills():
    import json
    skills_data = request.form.get('skills_to_add')
    if skills_data:
        try:
            skills_list = json.loads(skills_data)
            added_count = 0
            for skill_name in skills_list:
                 existing_skill = Skill.query.filter_by(name=skill_name.strip(), user_id=current_user.id).first()
                 if not existing_skill:
                     skill = Skill(name=skill_name.strip(), user=current_user)
                     db.session.add(skill)
                     added_count = added_count + 1
            if added_count > 0:
                db.session.commit()
                flash(f'Successfully added {added_count} skills to your profile!', 'success')
            else:
                flash('All selected skills were already in your profile.', 'info')
        except Exception as e:
            flash('Error processing skills data.', 'danger')
    return redirect(url_for('routes.skills'))

@routes.route('/skills/delete/<int:skill_id>', methods=['POST'])
@login_required
def delete_skill(skill_id):
    skill = Skill.query.get_or_404(skill_id)
    if skill.user_id != current_user.id:
        flash('Unauthorized action.', 'danger')
        return redirect(url_for('routes.skills'))
    
    db.session.delete(skill)
    db.session.commit()
    flash('Skill deleted successfully.', 'success')
    return redirect(url_for('routes.skills'))

@routes.route('/applications', methods=['GET', 'POST'])
@login_required
def applications():
    form = ApplicationForm()
    if form.validate_on_submit():
        app = Application(
            company_name=form.company_name.data,
            role=form.role.data,
            status=form.status.data,
            deadline=form.deadline.data,
            rejection_reason=form.rejection_reason.data if form.status.data == 'Rejected' else None,
            user=current_user
        )
        db.session.add(app)
        db.session.commit()
        flash('Application added successfully!', 'success')
        return redirect(url_for('routes.applications'))
    
    apps = Application.query.filter_by(user_id=current_user.id).order_by(Application.created_at.desc()).all()
    return render_template('applications.html', title='Applications', form=form, applications=apps)

@routes.route('/applications/delete/<int:app_id>', methods=['POST'])
@login_required
def delete_application(app_id):
    app = Application.query.get_or_404(app_id)
    if app.user_id != current_user.id:
        flash('Unauthorized action.', 'danger')
        return redirect(url_for('routes.applications'))
    
    db.session.delete(app)
    db.session.commit()
    flash('Application deleted successfully.', 'success')
    return redirect(url_for('routes.applications'))

@routes.route('/update_application_status', methods=['POST'])
@login_required
def update_application_status_kanban():
    from flask import jsonify
    data = request.get_json()
    if not data or 'application_id' not in data or 'status' not in data:
        return jsonify({'success': False, 'error': 'Invalid input'}), 400
        
    app = Application.query.get(data['application_id'])
    
    if not app or app.user_id != current_user.id:
        return jsonify({'success': False, 'error': 'Application not found'}), 404
        
    app.status = data['status']
    db.session.commit()
    return jsonify({'success': True})

@routes.route('/job_analyzer', methods=['GET', 'POST'])
@login_required
def job_analyzer():
    from utils import extract_text_from_pdf
    analysis = None
    error = None
    
    # Fetch user's applications for the dropdown
    user_apps = Application.query.filter_by(user_id=current_user.id).order_by(Application.created_at.desc()).all()
    selected_app = None

    if request.method == 'POST':
        jd_text = request.form.get('job_description', '')
        job_title = request.form.get('job_title', '')
        app_id = request.form.get('application_id')
        job_pdf = request.files.get('job_pdf')
        
        if app_id:
            selected_app = Application.query.get(app_id)
            if selected_app and selected_app.user_id != current_user.id:
                selected_app = None # Security check
            if selected_app:
                job_title = f"{selected_app.company_name} - {selected_app.role}"

        if job_pdf and job_pdf.filename.lower().endswith('.pdf'):
            extracted_text = extract_text_from_pdf(job_pdf)
            if extracted_text:
                jd_text = extracted_text
            else:
                flash('Could not extract text from the provided PDF. Please verify the document or paste the text directly.', 'warning')
                
        if jd_text:
            user_skill_objs = Skill.query.filter_by(user_id=current_user.id).all()
            user_skills_list = [s.name for s in user_skill_objs]
            
            try:
                analysis = analyze_job(jd_text, user_skills_list)
                analysis['internship_name'] = job_title if job_title else "General Analysis"
                
                # Format learning path dynamically based on missing skills
                missing_skills = analysis.get('missing_skills', [])
                formatted_learning_path = []
                for skill in missing_skills:
                    formatted_learning_path.append(f"Research and learn the fundamentals of {skill}")
                    formatted_learning_path.append(f"Build a small introductory project using {skill}")
                    
                match_score = analysis.get('match_percentage', 0)
                
                # Save the learning path to the database
                company_name = selected_app.company_name if selected_app else "General"
                role_name = selected_app.role if selected_app else job_title if job_title else "Analysis"
                
                new_path = LearningPath(
                    company=company_name,
                    role=role_name,
                    match_score=match_score,
                    missing_skills=json.dumps(missing_skills),
                    learning_steps=json.dumps(formatted_learning_path),
                    user=current_user
                )
                db.session.add(new_path)
                db.session.commit()
                
            except Exception as e:
                error = str(e)
            
    return render_template('job_analyzer.html', title='Job Analyzer', result=analysis, applications=user_apps, error=error)

@routes.route('/recommendations')
@login_required
def recommendations():
    user = current_user
    user_skills_objs = Skill.query.filter_by(user_id=user.id).all()
    user_skills = [s.name for s in user_skills_objs]
    
    profile = user.profile
    target_role = profile.target_role if profile and profile.target_role else 'Any Tech Role'
    year_of_study = profile.year_of_study if profile and profile.year_of_study else 'Unknown'
    branch = profile.branch if profile and profile.branch else 'Unknown'
    
    apps = Application.query.filter_by(user_id=user.id).all()
    past_roles = [app.role for app in apps]
    
    recs = []
    error = None
    if len(user_skills) >= 2:
        try:
            interests = f"Target Role: {target_role}, Branch: {branch}, Year: {year_of_study}"
            recs = get_recommendations(user_skills, interests, past_roles)
        except Exception as e:
            error = str(e)

    return render_template('recommendations.html', title='Recommendations', result=recs, error=error)

@routes.route('/learning-path')
@login_required
def learning_paths():
    import json
    paths = LearningPath.query.filter_by(user_id=current_user.id).order_by(LearningPath.created_at.desc()).all()
    
    # Deserialize JSON strings back into lists for the template
    parsed_paths = []
    for p in paths:
        try:
            missing = json.loads(p.missing_skills) if p.missing_skills else []
            steps = json.loads(p.learning_steps) if p.learning_steps else []
        except:
            missing = []
            steps = []
        
        # Build set of completed step indices for this path
        completed_indices = set(
            sc.step_id for sc in LearningStepCompletion.query.filter_by(
                learning_path_id=p.id, user_id=current_user.id, is_completed=True
            ).all()
        )

        # Calculate readiness score
        total_steps = len(steps)
        completed_count = len(completed_indices)
        learning_progress = (completed_count / total_steps * 100) if total_steps > 0 else 0
        match_score = p.match_score if p.match_score else 0
        readiness_score = int((match_score * 0.6) + (learning_progress * 0.4))

        # Check if missing skills are already in user's profile
        user_skills_set = set(s.name.lower() for s in current_user.skills)
        all_skills_added = all(s.lower() in user_skills_set for s in missing)

        parsed_paths.append({
            'id': p.id,
            'company': p.company,
            'role': p.role,
            'match_score': match_score,
            'readiness_score': readiness_score,
            'missing_skills': missing,
            'learning_steps': steps,
            'created_at': p.created_at,
            'completed_steps': completed_indices,
            'total_steps': total_steps,
            'completed_count': completed_count,
            'all_skills_added': all_skills_added
        })
        
    return render_template('learning_paths.html', title='Learning Path', learning_paths=parsed_paths)

@routes.route('/learning-path/delete/<int:path_id>', methods=['POST'])
@login_required
def delete_learning_path(path_id):
    path = LearningPath.query.get_or_404(path_id)
    if path.user_id != current_user.id:
        flash('Unauthorized action.', 'danger')
        return redirect(url_for('routes.learning_paths'))
    
    db.session.delete(path)  # cascade deletes step_completions automatically
    db.session.commit()
    flash('Learning path deleted successfully.', 'success')
    return redirect(url_for('routes.learning_paths'))

@routes.route('/toggle_step_completion', methods=['POST'])
@login_required
def toggle_step_completion():
    data = request.get_json()
    path_id = data.get('learning_path_id') or data.get('path_id')
    step_id = data.get('step_id')
    
    if path_id is None or step_id is None:
        return jsonify({'success': False, 'message': 'Invalid input'}), 400

    path_id = int(path_id)
    step_id = int(step_id)

    # Verify the path belongs to current user
    path = LearningPath.query.get(path_id)
    if not path or path.user_id != current_user.id:
        return jsonify({'success': False, 'message': 'Not found or unauthorized'}), 403

    existing = LearningStepCompletion.query.filter_by(
        learning_path_id=path_id,
        step_id=step_id,
        user_id=current_user.id
    ).first()

    if existing:
        existing.is_completed = not existing.is_completed
        completed = existing.is_completed
    else:
        new_completion = LearningStepCompletion(
            learning_path_id=path_id,
            step_id=step_id,
            is_completed=True,
            user_id=current_user.id
        )
        db.session.add(new_completion)
        completed = True

    db.session.commit()

    # Return updated counts
    completed_count = LearningStepCompletion.query.filter_by(
        learning_path_id=path_id, user_id=current_user.id, is_completed=True
    ).count()
    import json
    missing_skills = json.loads(path.missing_skills) if path.missing_skills else []
    total = len(json.loads(path.learning_steps)) if path.learning_steps else 0

    return jsonify({
        'success': True,
        'completed': completed,
        'completed_count': completed_count,
        'total': total,
        'missing_skills': missing_skills if completed_count == total else []
    })

@routes.route('/add_skills_from_path', methods=['POST'])
@login_required
def add_skills_from_path():
    data = request.get_json()
    path_id = data.get('path_id')
    
    if path_id is None:
        return jsonify({'success': False, 'message': 'Invalid input'}), 400
        
    path = LearningPath.query.get(path_id)
    if not path or path.user_id != current_user.id:
        return jsonify({'success': False, 'message': 'Path not found'}), 404
        
    import json
    missing_skills = json.loads(path.missing_skills) if path.missing_skills else []
    user_skills_objs = Skill.query.filter_by(user_id=current_user.id).all()
    user_skills_names = [s.name.lower() for s in user_skills_objs]
    
    added_count = 0
    for skill_name in missing_skills:
        if skill_name.lower() not in user_skills_names:
            new_skill = Skill(name=skill_name, user_id=current_user.id)
            db.session.add(new_skill)
            added_count += 1
            
    # Update match score to 100 since all skills are now present
    old_match_score = path.match_score
    path.match_score = 100
    db.session.commit()
    
    # Recalculate readiness
    # (100 * 0.6) + (100 * 0.4) = 100
    new_readiness = 100
    
    return jsonify({
        'success': True,
        'added_count': added_count,
        'old_match_score': old_match_score,
        'new_readiness': new_readiness
    })

@routes.route('/interview-prep', methods=['GET', 'POST'])
@login_required
def interview_prep():
    from models import InterviewSession
    if request.method == 'POST':
        role = request.form.get('target_role', 'Software Engineer')
        user_skills_objs = Skill.query.filter_by(user_id=current_user.id).all()
        user_skills = [s.name for s in user_skills_objs]
        try:
            result = generate_interview_prep(role, user_skills)
            if result and 'questions' in result:
                new_session = InterviewSession(
                    user_id=current_user.id,
                    target_role=role,
                    questions=json.dumps(result['questions'])
                )
                db.session.add(new_session)
                db.session.commit()
                flash('Questions generated successfully!', 'success')
            else:
                flash('Failed to generate questions.', 'danger')
        except Exception as e:
            flash(f'Error: {str(e)}', 'danger')
        return redirect(url_for('routes.interview_prep'))
        
    sessions = InterviewSession.query.filter_by(user_id=current_user.id).order_by(InterviewSession.created_at.desc()).all()
    return render_template('interview_prep.html', title='Interview Prep', sessions=sessions)

@routes.route('/interview-prep/delete/<int:session_id>', methods=['POST'])
@login_required
def delete_interview_session(session_id):
    from models import InterviewSession
    session_obj = InterviewSession.query.get_or_404(session_id)
    if session_obj.user_id == current_user.id:
        db.session.delete(session_obj)
        db.session.commit()
        flash('Session deleted.', 'success')
    else:
        flash('Unauthorized action.', 'danger')
    return redirect(url_for('routes.interview_prep'))

@routes.route('/interview-prep/more/<int:session_id>', methods=['POST'])
@login_required
def more_interview_questions(session_id):
    from models import InterviewSession
    session_obj = InterviewSession.query.get_or_404(session_id)
    if session_obj.user_id != current_user.id:
        flash('Unauthorized action.', 'danger')
        return redirect(url_for('routes.interview_prep'))
        
    user_skills_objs = Skill.query.filter_by(user_id=current_user.id).all()
    user_skills = [s.name for s in user_skills_objs]
    
    try:
        result = generate_interview_prep(session_obj.target_role, user_skills)
        if result and 'questions' in result:
            existing_questions = json.loads(session_obj.questions) if session_obj.questions else []
            existing_questions.extend(result['questions'])
            session_obj.questions = json.dumps(existing_questions)
            db.session.commit()
            flash('More questions added!', 'success')
        else:
            flash('Failed to generate more questions.', 'danger')
    except Exception as e:
        flash(f'Error: {str(e)}', 'danger')
        
    return redirect(url_for('routes.interview_prep'))

@routes.route("/chat", methods=["POST"])
@login_required
def chat_api():
    data = request.get_json()
    messages = data.get("messages", [])
    
    if messages:
        last_message = messages[-1].get("content", "").lower()
        job_search_triggers = ["find ", "search ", "looking for ", "jobs", "internships", "intern"]
        is_job_search = any(t in last_message for t in ["job", "internship", "intern", "role"]) and any(t in last_message for t in ["find", "search", "looking", "want"])
        if is_job_search:
            query = last_message
            for trigger in job_search_triggers:
                query = query.replace(trigger, "").strip()
            query = query.replace("for", "").strip()
            if not query or len(query) < 3:
                user_skills = [s.name for s in current_user.skills]
                query = user_skills[0] + " intern" if user_skills else "software intern"
            search_url = f"/job-search?q={query.replace(' ', '+')}"
            return jsonify({
                "reply": f"Opening job search for '{query}' now!",
                "status": "ok",
                "navigate": search_url
            })

    top_score = 0
    paths = LearningPath.query.filter_by(user_id=current_user.id).all()
    if paths:
        top_score = max((p.match_score for p in paths if p.match_score), default=0)
        
    user_context = {
        "name": current_user.username,
        "skills": [s.name for s in current_user.skills],
        "applications_count": len(current_user.applications),
        "applications": [
            {
                "role": a.role,
                "company": a.company if hasattr(a, 'company') else "Unknown",
                "status": a.status if hasattr(a, 'status') else "Unknown",
                "date_applied": str(a.date_applied) if hasattr(a, 'date_applied') else "Unknown"
            }
            for a in current_user.applications
        ],
        "top_match_score": 0
    }
    
    try:
        reply = chat_with_assistant(messages, user_context)
        return jsonify({"reply": reply, "status": "ok"})
    except Exception as e:
        print(f"Chat route error: {e}")
        return jsonify({"reply": "Sorry, I'm having trouble connecting right now. Please try again shortly.", "status": "error"})

@routes.route("/job-search")
@login_required
def job_search():
    query = request.args.get("q", "").strip()
    user_skills = [s.name for s in current_user.skills]
    default_query = user_skills[0] + " intern" if user_skills else "software intern"
    results = None
    google_url = None
    if query:
        results = search_jobs_live(query)
        if results and results.get("source") == "google":
            google_url = results.get("google_url")
    return render_template("job_search.html",
        title="Job Search",
        query=query,
        results=results,
        google_url=google_url,
        default_query=default_query,
        user_skills=user_skills
    )

@routes.route("/api/job-search")
@login_required
def api_job_search():
    query = request.args.get("q", "").strip()
    if not query:
        return jsonify({"error": "No query provided"})
    results = search_jobs_live(query)
    return jsonify(results)
