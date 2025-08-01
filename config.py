import os
import secrets
from dotenv import load_dotenv
from typing import Optional

# Find the absolute path of the root directory
basedir = os.path.abspath(os.path.dirname(__file__))

# Load the .env file from the root directory
load_dotenv(os.path.join(basedir, '.env'))

class ConfigurationError(Exception):
    """Raised when required configuration is missing or invalid"""
    pass

class Config:
    """
    Base configuration class. Contains default configuration settings
    and settings applicable to all environments.
    """
    # Flask settings - SECURITY FIX: Generate secure random key if not provided
    SECRET_KEY = os.environ.get('SECRET_KEY') or secrets.token_hex(32)
    FLASK_ENV = os.environ.get('FLASK_ENV')
    
    @classmethod
    def validate_required_config(cls) -> None:
        """Validate that all required configuration is present"""
        # Skip validation in testing environment
        if os.environ.get('FLASK_ENV') == 'testing':
            return
            
        # In production, we use DATABASE_URL instead of individual DB vars
        if os.environ.get('DATABASE_URL') or os.environ.get('POSTGRES_URI'):
            required_vars = ['OPENPHONE_API_KEY']
        else:
            required_vars = [
                'OPENPHONE_API_KEY',
                'DB_USER', 
                'DB_PASSWORD',
                'DB_NAME'
            ]
        
        missing_vars = []
        for var in required_vars:
            if not os.environ.get(var):
                missing_vars.append(var)
        
        if missing_vars:
            raise ConfigurationError(
                f"Missing required environment variables: {', '.join(missing_vars)}"
            )
    
    @staticmethod
    def get_required_env(key: str) -> str:
        """Get required environment variable or raise error"""
        value = os.environ.get(key)
        if not value:
            raise ConfigurationError(f"Required environment variable {key} is not set")
        return value

    # Database settings
    SQLALCHEMY_DATABASE_URI = os.environ.get('POSTGRES_URI') or \
        'sqlite:///' + os.path.join(basedir, 'crm.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # OpenPhone API
    OPENPHONE_API_KEY = os.environ.get('OPENPHONE_API_KEY')
    OPENPHONE_PHONE_NUMBER = os.environ.get('OPENPHONE_PHONE_NUMBER')
    OPENPHONE_PHONE_NUMBER_ID = os.environ.get('OPENPHONE_PHONE_NUMBER_ID')
    OPENPHONE_WEBHOOK_SIGNING_KEY = os.environ.get('OPENPHONE_WEBHOOK_SIGNING_KEY')

    # Google OAuth
    GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID')
    GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET')
    GOOGLE_PROJECT_ID = os.environ.get('GOOGLE_PROJECT_ID')

    # Gemini API
    GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')

    # --- FIXED: Celery Configuration (Using standard uppercase prefixes) ---
    # Flask will load these, and Celery will automatically map them to its lowercase settings.
    # We also use 'redis' as the hostname, which is the service name in docker-compose.
    CELERY_BROKER_URL = os.environ.get('REDIS_URL') or 'redis://redis:6379/0'
    CELERY_RESULT_BACKEND = os.environ.get('REDIS_URL') or 'redis://redis:6379/0'
    
    # Mail settings
    MAIL_SERVER = os.environ.get('MAIL_SERVER')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'true').lower() == 'true'
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', 'noreply@attackacrack.com')
    
    # Security settings
    SESSION_COOKIE_SECURE = False  # Will be overridden in production
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    PERMANENT_SESSION_LIFETIME = 86400  # 24 hours
    
    # Application settings
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file upload
    JSON_SORT_KEYS = False
    
    @classmethod
    def init_app(cls, app):
        """Initialize application with this config"""
        pass


class DevelopmentConfig(Config):
    """Development environment configuration"""
    DEBUG = True
    TESTING = False
    
    # Development-specific database URI
    SQLALCHEMY_DATABASE_URI = os.environ.get('DEV_DATABASE_URL') or \
        Config.SQLALCHEMY_DATABASE_URI
    
    # Development mail settings - use console backend
    MAIL_SUPPRESS_SEND = True
    
    @classmethod
    def init_app(cls, app):
        """Development-specific initialization"""
        Config.init_app(app)
        
        # Log to stdout in development
        import logging
        from logging import StreamHandler
        stream_handler = StreamHandler()
        stream_handler.setLevel(logging.DEBUG)
        app.logger.addHandler(stream_handler)


class TestingConfig(Config):
    """Testing environment configuration"""
    TESTING = True
    DEBUG = True
    
    # Use in-memory SQLite for tests
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    
    # Disable CSRF for testing
    WTF_CSRF_ENABLED = False
    
    # Use test Redis database
    CELERY_BROKER_URL = 'redis://localhost:6379/1'
    CELERY_RESULT_BACKEND = 'redis://localhost:6379/1'
    
    @classmethod
    def init_app(cls, app):
        """Testing-specific initialization"""
        Config.init_app(app)
        
        # Disable foreign keys for SQLite in tests to avoid cascading issues
        # This matches the behavior of many ORMs where foreign keys are not enforced
        # during testing to allow for more flexible test data setup
        from sqlalchemy import event
        from sqlalchemy.engine import Engine
        
        @event.listens_for(Engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            if 'sqlite' in str(dbapi_connection):
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA foreign_keys=OFF")
                cursor.close()


class ProductionConfig(Config):
    """Production environment configuration"""
    DEBUG = False
    TESTING = False
    
    # Production database
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', '')
    
    # Security settings for production
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_NAME = 'attackacrack_session'
    
    # Production Redis - will be validated in init_app
    CELERY_BROKER_URL = os.environ.get('REDIS_URL', '')
    CELERY_RESULT_BACKEND = os.environ.get('REDIS_URL', '')
    
    # If using rediss:// (SSL), append required parameters
    if CELERY_BROKER_URL.startswith('rediss://'):
        # Append SSL parameters if not already present
        if 'ssl_cert_reqs' not in CELERY_BROKER_URL:
            # Use CERT_NONE for managed Redis/Valkey services
            separator = '&' if '?' in CELERY_BROKER_URL else '?'
            ssl_params = f"{separator}ssl_cert_reqs=CERT_NONE"
            CELERY_BROKER_URL += ssl_params
            CELERY_RESULT_BACKEND += ssl_params
    
    @classmethod
    def init_app(cls, app):
        """Production-specific initialization"""
        Config.init_app(app)
        
        # Validate required environment variables
        if not cls.SQLALCHEMY_DATABASE_URI:
            cls.SQLALCHEMY_DATABASE_URI = cls.get_required_env('POSTGRES_URI')
        if not cls.CELERY_BROKER_URL:
            cls.CELERY_BROKER_URL = cls.get_required_env('REDIS_URL')
            cls.CELERY_RESULT_BACKEND = cls.CELERY_BROKER_URL
            
            # Handle rediss:// URLs
            if cls.CELERY_BROKER_URL.startswith('rediss://'):
                if 'ssl_cert_reqs' not in cls.CELERY_BROKER_URL:
                    separator = '&' if '?' in cls.CELERY_BROKER_URL else '?'
                    ssl_params = f"{separator}ssl_cert_reqs=CERT_NONE"
                    cls.CELERY_BROKER_URL += ssl_params
                    cls.CELERY_RESULT_BACKEND += ssl_params
        
        # Validate all required config
        cls.validate_required_config()
        
        # Log to syslog in production
        import logging
        from logging.handlers import SysLogHandler
        syslog_handler = SysLogHandler()
        syslog_handler.setLevel(logging.WARNING)
        app.logger.addHandler(syslog_handler)


# Configuration dictionary
config = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}


def get_config(config_name: Optional[str] = None) -> type[Config]:
    """Get configuration class based on environment"""
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')
    
    return config.get(config_name, DevelopmentConfig)
