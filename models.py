from extensions import db
from flask_login import UserMixin
from datetime import datetime

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    password_hash = db.Column(db.String(128), nullable=False)
    username = db.Column(db.String(150), unique=True, nullable=False)
    is_profile_setup = db.Column(db.Boolean, default=False)
    profile = db.relationship('Profile', backref='user', uselist=False, cascade="all, delete-orphan")
    skills = db.relationship('Skill', backref='user', lazy=True, cascade="all, delete-orphan")
    applications = db.relationship('Application', backref='user', lazy=True, cascade="all, delete-orphan")
    learning_paths = db.relationship('LearningPath', backref='user', lazy=True, cascade="all, delete-orphan")
    interview_sessions = db.relationship('InterviewSession', backref='user', lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f'<User {self.username}>'

class Profile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(150), nullable=False)
    college = db.Column(db.String(200), nullable=False)
    branch = db.Column(db.String(150), nullable=False)
    year_of_study = db.Column(db.String(50), nullable=False)
    target_role = db.Column(db.String(150), nullable=False)
    github_link = db.Column(db.String(250), nullable=True)
    linkedin_link = db.Column(db.String(250), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

class Skill(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    def __repr__(self):
        return f'<Skill {self.name}>'

class Application(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    company_name = db.Column(db.String(150), nullable=False)
    role = db.Column(db.String(150), nullable=False)
    status = db.Column(db.String(50), nullable=False, default='Applied')
    deadline = db.Column(db.DateTime, nullable=True)
    rejection_reason = db.Column(db.String(250), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Application {self.company_name} - {self.role}>'

class LearningPath(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    company = db.Column(db.String(150), nullable=False)
    role = db.Column(db.String(150), nullable=False)
    match_score = db.Column(db.Integer, default=0)
    missing_skills = db.Column(db.Text, nullable=True) # JSON stored as string
    learning_steps = db.Column(db.Text, nullable=True) # JSON stored as string
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    step_completions = db.relationship('LearningStepCompletion', backref='learning_path', lazy=True, cascade='all, delete-orphan')

    def __repr__(self):
        return f'<LearningPath {self.company} - {self.role}>'

class LearningStepCompletion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    learning_path_id = db.Column(db.Integer, db.ForeignKey('learning_path.id'), nullable=False)
    step_id = db.Column(db.Integer, nullable=False)
    is_completed = db.Column(db.Boolean, default=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    def __repr__(self):
        return f'<LearningStepCompletion path={self.learning_path_id} step={self.step_id} status={self.is_completed}>'

class InterviewSession(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    target_role = db.Column(db.String(150), nullable=False)
    questions = db.Column(db.Text, nullable=False) # JSON stored as string
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<InterviewSession {self.target_role}>'
