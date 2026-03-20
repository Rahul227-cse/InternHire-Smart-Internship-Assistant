import os
import json
from groq import Groq
from openai import OpenAI

groq_client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
openrouter_client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.environ.get("OPENROUTER_API_KEY", ""),
)

def _chat(messages, temperature=0.7, max_tokens=1024):
    # Try Groq first
    try:
        response = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"[AI] Groq failed: {e} — trying OpenRouter...")

    # Fallback to OpenRouter
    try:
        response = openrouter_client.chat.completions.create(
            model="openrouter/auto",
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"[AI] OpenRouter also failed: {e}")
        raise Exception("All AI providers failed. Please try again later.")

def _parse_json_response(response_text, default_fallback):
    text = response_text.strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()
    
    try:
        return json.loads(text)
    except Exception as e:
        print(f"JSON parsing error: {e}")
        return default_fallback

def analyze_job(job_description, user_skills):
    prompt = f"""
    Analyze the following job description against the user's skills.
    Job Description: {job_description}
    User Skills: {', '.join(user_skills) if isinstance(user_skills, list) else user_skills}
    
    Return ONLY a valid JSON object with exactly these keys:
    - "match_percentage": integer (0-100)
    - "matched_skills": list of strings
    - "missing_skills": list of strings
    - "role_summary": string (brief summary of the role)
    - "recommendation": string (actionable advice for the user based on missing skills)
    Do not use markdown formatting like ```json.
    """
    
    fallback = {
        "match_percentage": 0,
        "matched_skills": [],
        "missing_skills": [],
        "role_summary": "Failed to analyze role.",
        "recommendation": "Please try again later."
    }
    
    try:
        response_text = _chat([{"role": "user", "content": prompt}], temperature=0.7)
        return _parse_json_response(response_text, fallback)
    except Exception as e:
        print(f"AI Error in analyze_job: {e}")
        return fallback

def get_recommendations(user_skills, interests, applied_roles):
    prompt = f"""
    Provide career recommendations based on the user's profile.
    User Skills: {', '.join(user_skills) if isinstance(user_skills, list) else user_skills}
    Interests: { interests }
    Previously Applied Roles: {', '.join(applied_roles) if isinstance(applied_roles, list) else applied_roles}
    
    Return ONLY a valid JSON object with exactly these keys:
    - "recommendations": list of exactly 5 objects, each with: "role" (string), "company_type" (string), "why_fit" (string), "skills_to_highlight" (list of strings), "where_to_find" (string - platforms or types of websites to find these jobs)
    - "top_advice": string (overall career advice)
    Do not use markdown formatting like ```json.
    """
    
    fallback = {
        "recommendations": [],
        "top_advice": "Unable to generate recommendations right now."
    }
    
    try:
        response_text = _chat([{"role": "user", "content": prompt}], temperature=0.7)
        return _parse_json_response(response_text, fallback)
    except Exception as e:
        print(f"AI Error in get_recommendations: {e}")
        return fallback

def generate_interview_prep(role, user_skills):
    prompt = f"""
    Generate an interview preparation guide for the specified role.
    Target Role: {role}
    User Skills: {', '.join(user_skills) if isinstance(user_skills, list) else user_skills}
    
    Return ONLY a valid JSON object with exactly these keys:
    - "role": string (the target role)
    - "questions": list of exactly 8 objects, each with: "question" (string), "type" (string e.g. Behavioral, Technical), "sample_answer" (string), "tip" (string)
    - "quick_tips": list of exactly 3 strings (general interview advice)
    Do not use markdown formatting like ```json.
    """
    
    fallback = {
        "role": role,
        "questions": [],
        "quick_tips": ["Be yourself.", "Research the company.", "Prepare questions to ask."]
    }
    
    try:
        response_text = _chat([{"role": "user", "content": prompt}], temperature=0.7)
        return _parse_json_response(response_text, fallback)
    except Exception as e:
        print(f"AI Error in generate_interview_prep: {e}")
        return fallback

def chat_with_assistant(messages, user_context):
    system_prompt = f"""
    You are InternHire's friendly AI assistant. InternHire is a smart internship tracker that helps students track applications, analyze skill gaps, generate learning roadmaps, and prepare for interviews.

    You help users with TWO things:
    1. PLATFORM HELP — answer questions about how to use InternHire:
       - Dashboard: shows application stats and overview
       - Applications: track internship applications with status (Applied/Interview/Offer/Rejected)
       - Skills: add and manage your skills
       - Job Analyzer: paste a job description to get AI skill match % and gap analysis
       - Learning Path: auto-generated roadmaps based on your job analyses
       - Recommendations: AI-suggested internships based on your skills
       - Job Search: search live internship listings, user can also say "find Python jobs" to go directly to /job-search?q=python+intern
       - Interview Prep: generate interview questions and answers for any role

    2. CAREER ADVICE — answer internship and career questions:
       - Skill recommendations, resume tips, interview prep, company suggestions
       - Personalized advice based on the user's actual profile

    Current user profile:
    - Name: {user_context.get('name', 'Unknown')}
    - Skills: {user_context.get('skills', [])}
    - Total applications submitted: {user_context.get('applications_count', 0)}
    - Application details: {user_context.get('applications', [])}
    - Best job match score so far: {user_context.get('top_match_score', 0)}%

    NAVIGATION: If the user asks to go to a page or open a feature, include a navigation tag at the very end of your reply in this exact format: [NAVIGATE:/route]. Use these routes:
    - Dashboard → [NAVIGATE:/dashboard]
    - Applications → [NAVIGATE:/applications]
    - Skills → [NAVIGATE:/skills]
    - Job Analyzer → [NAVIGATE:/job_analyzer]
    - Learning Path → [NAVIGATE:/learning-path]
    - Recommendations → [NAVIGATE:/recommendations]
    - Interview Prep → [NAVIGATE:/interview-prep]
    - Job Search → [NAVIGATE:/job-search]
    Only include the tag if the user explicitly asks to go somewhere or open a page.

    IMPORTANT BEHAVIOUR RULES:
    1. Be concise and friendly. Maximum 3 sentences for simple requests like navigation.
    2. If the user just asks to GO to a page (e.g. "take me to learning path", "open job analyzer", "go to dashboard"), respond with ONLY a short confirmation like "Sure, taking you there!" or "Opening that for you!" — nothing else. Do NOT explain what the page does, do NOT analyze their profile, do NOT list their skills. Just confirm and navigate.
    3. Only give detailed analysis, skill breakdowns, or profile information if the user EXPLICITLY asks for it. For example "what are my skills?" or "analyze my profile" or "what's my match score?"
    4. Use bullet points only when explaining multi-step processes, not for simple replies.
    5. Keep responses under 80 words for simple requests, up to 150 words only when detailed explanation is genuinely needed.
    6. Never show internal reasoning, never pre-emptively analyze unless asked.
    """
    
    full_messages = [{"role": "system", "content": system_prompt.strip()}] + messages
    
    try:
        return _chat(full_messages, temperature=0.7)
    except Exception as e:
        print(f"AI Error in chat_with_assistant: {e}")
        raise

from cachetools import TTLCache
import requests

job_cache = TTLCache(maxsize=100, ttl=86400)

def search_jobs_live(query: str, num_results: int = 8) -> dict:
    cache_key = query.lower().strip()
    if cache_key in job_cache:
        return {"jobs": job_cache[cache_key], "source": "cache"}

    rapidapi_key = os.environ.get("JSEARCH_API_KEY", "")

    # Try JSearch first
    try:
        r = requests.get(
            "https://jsearch.p.rapidapi.com/search",
            headers={
                "x-rapidapi-key": rapidapi_key,
                "x-rapidapi-host": "jsearch.p.rapidapi.com"
            },
            params={"query": query, "num_pages": "1"},
            timeout=10
        )
        if r.status_code == 200:
            data = r.json()
            jobs = []
            for job in data.get("data", [])[:num_results]:
                jobs.append({
                    "title": job.get("job_title", "Unknown"),
                    "company": job.get("employer_name", "Unknown"),
                    "location": f"{job.get('job_city', '')} {job.get('job_country', '')}".strip(),
                    "type": job.get("job_employment_type", ""),
                    "link": job.get("job_apply_link", "#"),
                    "posted": job.get("job_posted_at_datetime_utc", "")[:10] if job.get("job_posted_at_datetime_utc") else "N/A",
                    "description": job.get("job_description", "")[:200] + "..." if job.get("job_description") else ""
                })
            if jobs:
                job_cache[cache_key] = jobs
                return {"jobs": jobs, "source": "live"}
    except Exception:
        pass

    # Silent fallback to Google Jobs API
    try:
        r = requests.get(
            "https://google-jobs-api.p.rapidapi.com/google-jobs",
            headers={
                "x-rapidapi-key": rapidapi_key,
                "x-rapidapi-host": "google-jobs-api.p.rapidapi.com"
            },
            params={"include": query, "language": "English"},
            timeout=10
        )
        if r.status_code == 200:
            data = r.json()
            jobs = []
            for job in data.get("jobs", [])[:num_results]:
                jobs.append({
                    "title": job.get("title", "Unknown"),
                    "company": job.get("company", "Unknown"),
                    "location": job.get("location", ""),
                    "type": job.get("jobType", ""),
                    "link": job.get("link", "#"),
                    "posted": job.get("postedDate", "N/A") or "N/A",
                    "description": job.get("snippet", "")
                })
            if jobs:
                job_cache[cache_key] = jobs
                return {"jobs": jobs, "source": "live"}
    except Exception:
        pass

    # Final silent fallback — Google Jobs search URL
    google_url = f"https://www.google.com/search?q={query.replace(' ', '+')}&ibp=htl;jobs"
    return {"jobs": [], "source": "google", "google_url": google_url}
