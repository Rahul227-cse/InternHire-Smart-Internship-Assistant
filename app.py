from flask import Flask
from flask_wtf.csrf import CSRFProtect
from extensions import db, bcrypt, login_manager
import os

app = Flask(__name__)
csrf = CSRFProtect(app)
# Configurations
app.config['SECRET_KEY'] = 'a_very_secret_key_for_internhire'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///internhire.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
bcrypt.init_app(app)
login_manager.init_app(app)
login_manager.login_view = 'auth.login'
login_manager.login_message_category = 'info'

from models import User

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

from auth import auth as auth_bp
from routes import routes as routes_bp

app.register_blueprint(auth_bp)
app.register_blueprint(routes_bp)

with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True)
