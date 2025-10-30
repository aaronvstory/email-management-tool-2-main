"""
Email Management Tool - Flask Application Factory
"""
import os
import logging
import logging.handlers
from flask import Flask
from flask_login import LoginManager
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_cors import CORS
from config.config import config

# Initialize extensions
login_manager = LoginManager()
limiter = Limiter(key_func=get_remote_address)

def create_app(config_name=None):
    """Create Flask application with factory pattern"""
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')
    
    app = Flask(__name__, 
                template_folder='../templates',
                static_folder='../static')
    
    # Load configuration
    app.config.from_object(config[config_name])
    
    # Initialize extensions
    initialize_extensions(app)
    
    # Register blueprints
    register_blueprints(app)
    
    # Configure logging
    configure_logging(app)
    
    # Create database tables
    with app.app_context():
        from app.models.base import Database, Base
        from app.models import User, EmailMessage, ModerationRule, EmailAccount, AuditLog
        
        # Initialize database
        global db
        db = Database(app.config['SQLALCHEMY_DATABASE_URI'])
        app.db = db
        
        # Create tables if they don't exist
        Base.metadata.create_all(bind=db.engine)
        
        # Create default admin user if not exists
        create_default_admin(db)
    
    return app

def initialize_extensions(app):
    """Initialize Flask extensions"""
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'
    
    limiter.init_app(app)
    
    # Enable CORS for API endpoints
    CORS(app, resources={r"/api/*": {"origins": "*"}})
    
    @login_manager.user_loader
    def load_user(user_id):
        from app.models import User
        session = app.db.get_session()
        user = session.query(User).filter_by(id=user_id).first()
        session.close()
        return user

def register_blueprints(app):
    """Register Flask blueprints"""
    from app.web.dashboard import dashboard_bp
    from app.web.auth import auth_bp
    from app.web.email import email_bp
    from app.web.rules import rules_bp
    from app.web.settings import settings_bp
    from app.api import api_bp
    
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(email_bp, url_prefix='/emails')
    app.register_blueprint(rules_bp, url_prefix='/rules')
    app.register_blueprint(settings_bp, url_prefix='/settings')
    app.register_blueprint(api_bp, url_prefix='/api')

def configure_logging(app):
    """Configure application logging"""
    if not app.debug:
        if not os.path.exists('logs'):
            os.mkdir('logs')
        
        file_handler = logging.handlers.RotatingFileHandler(
            'logs/email_moderation.log',
            maxBytes=10240000,
            backupCount=10
        )
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        ))
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)
        
        app.logger.setLevel(logging.INFO)
        app.logger.info('Email Management Tool startup')

def create_default_admin(db):
    """Create default admin user if not exists"""
    from app.models import User, Role, RoleEnum
    
    session = db.get_session()
    
    # Check if admin role exists
    admin_role = session.query(Role).filter_by(name=RoleEnum.ADMIN.value).first()
    if not admin_role:
        admin_role = Role(name=RoleEnum.ADMIN.value, description='Administrator role')
        session.add(admin_role)
    
    # Check if admin user exists
    admin_user = session.query(User).filter_by(username='admin').first()
    if not admin_user:
        admin_user = User(
            username='admin',
            email='admin@example.com',
            first_name='System',
            last_name='Administrator'
        )
        admin_user.set_password('admin123')  # Change this in production!
        admin_user.roles.append(admin_role)
        session.add(admin_user)
    
    session.commit()
    session.close()