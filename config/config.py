"""
Configuration settings for Email Management Tool

IMPORTANT: This replaces hardcoded secrets in simple_app.py
Supports dev/staging/prod environments with proper validation.

Usage:
    from config import get_config
    config = get_config()
    app.config.from_object(config)
"""
import os
import secrets
from datetime import timedelta
from pathlib import Path

# Try to load .env file if python-dotenv is available
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv is optional


class Config:
    """Base configuration - NEVER use directly in production"""

    # Project paths
    PROJECT_ROOT = Path(__file__).parent.parent

    # Flask Core Settings
    SECRET_KEY = os.environ.get('FLASK_SECRET_KEY') or os.environ.get('SECRET_KEY')
    DEBUG = False
    TESTING = False

    # Database Settings (SQLite-based, no SQLAlchemy required)
    DB_PATH = os.environ.get('DB_PATH', 'email_manager.db')

    # SMTP Proxy Settings
    SMTP_PROXY_HOST = os.environ.get('SMTP_PROXY_HOST', '127.0.0.1')
    SMTP_PROXY_PORT = int(os.environ.get('SMTP_PROXY_PORT', 8587))
    SMTP_PROXY_MAX_SIZE = int(os.environ.get('SMTP_PROXY_MAX_SIZE', 10485760))  # 10MB
    
    # SMTP Relay Settings (for sending approved emails)
    SMTP_RELAY_HOST = os.environ.get('SMTP_RELAY_HOST', 'smtp.gmail.com')
    SMTP_RELAY_PORT = int(os.environ.get('SMTP_RELAY_PORT', 587))
    SMTP_RELAY_USE_TLS = os.environ.get('SMTP_RELAY_USE_TLS', 'True') == 'True'
    SMTP_RELAY_USERNAME = os.environ.get('SMTP_RELAY_USERNAME', '')
    SMTP_RELAY_PASSWORD = os.environ.get('SMTP_RELAY_PASSWORD', '')
    
    # Web Interface
    WEB_HOST = os.environ.get('WEB_HOST', '127.0.0.1')
    WEB_PORT = int(os.environ.get('WEB_PORT', 5000))
    
    # Security
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY') or SECRET_KEY
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=1)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)
    JWT_ALGORITHM = 'HS256'
    
    # Session
    SESSION_TYPE = 'filesystem'
    PERMANENT_SESSION_LIFETIME = timedelta(hours=24)
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    
    # Rate Limiting
    RATELIMIT_STORAGE_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379')
    RATELIMIT_DEFAULT = "100 per hour"
    
    # Celery Configuration
    CELERY_BROKER_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
    CELERY_RESULT_BACKEND = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
    CELERY_TASK_SERIALIZER = 'json'
    CELERY_ACCEPT_CONTENT = ['json']
    CELERY_RESULT_SERIALIZER = 'json'
    CELERY_TIMEZONE = 'UTC'
    CELERY_ENABLE_UTC = True
    
    # Logging
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
    LOG_FILE = 'logs/email_moderation.log'
    LOG_MAX_BYTES = 10485760  # 10MB
    LOG_BACKUP_COUNT = 10
    
    # Email Processing
    MAX_EMAIL_SIZE = 10485760  # 10MB
    ATTACHMENT_ALLOWED_EXTENSIONS = {'.pdf', '.doc', '.docx', '.xls', '.xlsx', '.txt', '.png', '.jpg', '.jpeg'}
    ATTACHMENTS_UI_ENABLED = os.environ.get('ATTACHMENTS_UI_ENABLED', 'false').lower() == 'true'
    ATTACHMENTS_EDIT_ENABLED = os.environ.get('ATTACHMENTS_EDIT_ENABLED', 'false').lower() == 'true'
    ATTACHMENTS_RELEASE_ENABLED = os.environ.get('ATTACHMENTS_RELEASE_ENABLED', 'false').lower() == 'true'
    ATTACHMENT_MAX_BYTES = int(os.environ.get('ATTACHMENT_MAX_BYTES', 25 * 1024 * 1024))
    ATTACHMENTS_MAX_COUNT = int(os.environ.get('ATTACHMENTS_MAX_COUNT', 25))
    ATTACHMENT_ALLOWED_MIME = os.environ.get(
        'ATTACHMENT_ALLOWED_MIME',
        'application/pdf,image/png,image/jpeg,text/plain'
    )
    ATTACHMENT_CLAMAV_ENABLED = os.environ.get('ATTACHMENT_CLAMAV_ENABLED', 'false').lower() == 'true'
    ATTACHMENTS_ROOT_DIR = os.environ.get('ATTACHMENTS_ROOT_DIR', 'attachments')
    ATTACHMENTS_STAGED_ROOT_DIR = os.environ.get('ATTACHMENTS_STAGED_ROOT_DIR', 'attachments_staged')
    
    # Pagination
    ITEMS_PER_PAGE = 20
    
    # SSE (Server-Sent Events)
    SSE_REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/1')
    

class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    TESTING = False
    

class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    TESTING = False
    
    # Enforce HTTPS in production
    SESSION_COOKIE_SECURE = True
    
    # Stricter rate limiting in production
    RATELIMIT_DEFAULT = "50 per hour"
    

class TestingConfig(Config):
    """Testing configuration"""
    DEBUG = True
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False
    

# Configuration dictionary
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}


def get_config(env: str = None) -> type[Config]:
    """
    Get configuration class based on environment.

    Args:
        env: Environment name ('development', 'production', 'testing').
             If None, reads from FLASK_ENV or defaults to 'development'.

    Returns:
        Configuration class (DevelopmentConfig, ProductionConfig, or TestingConfig)
    """
    if env is None:
        env = os.environ.get('FLASK_ENV', 'development').lower()

    return config.get(env, config['default'])
