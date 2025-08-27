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
    
    # Gunicorn Configuration
    GUNICORN_TIMEOUT = int(os.environ.get('GUNICORN_TIMEOUT', '300'))  # 5 minutes default for CSV imports
    GUNICORN_WORKERS = int(os.environ.get('GUNICORN_WORKERS', '4'))  # Default 4 workers
    
    @classmethod
    def validate_required_config(cls) -> None:
        """Validate that all required configuration is present"""
        # Skip validation in testing environment or during migrations
        if os.environ.get('FLASK_ENV') == 'testing' or os.environ.get('SKIP_ENV_VALIDATION'):
            return
            
        # In production, we use DATABASE_URL instead of individual DB vars
        if os.environ.get('DATABASE_URL') or os.environ.get('POSTGRES_URI'):
            # Make API keys optional for initial deployment
            required_vars = []
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
    MAIL_PORT = int(os.environ.get('MAIL_PORT') or 587)  # Handle empty string
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
    
    # Bcrypt settings
    BCRYPT_LOG_ROUNDS = 12  # Production default
    
    # Session configuration - Use Redis for session storage to support multiple workers
    SESSION_TYPE = 'redis'
    SESSION_PERMANENT = False
    SESSION_KEY_PREFIX = 'attackacrack:'
    SESSION_COOKIE_NAME = 'attackacrack_session'
    SESSION_COOKIE_SECURE = True  # Always use secure cookies in production
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    # Redis URL will be set in init_app method
    
    @classmethod
    def init_app(cls, app):
        """Initialize application with this config"""
        # Set up Redis connection for Flask-Session
        import redis
        from flask_session import Session
        
        # Try multiple sources for Redis URL
        redis_url = (
            os.environ.get('REDIS_URL') or 
            os.environ.get('CELERY_BROKER_URL') or
            app.config.get('CELERY_BROKER_URL') or
            app.config.get('REDIS_URL') or
            'redis://localhost:6379/0'
        )
        
        # Log the Redis URL being used (without password)
        import logging
        logger = logging.getLogger(__name__)
        if 'rediss://' in redis_url:
            logger.info(f"Using Redis URL: rediss://[REDACTED]@{redis_url.split('@')[1] if '@' in redis_url else 'unknown'}")
        else:
            logger.info(f"Using Redis URL: {redis_url.split('@')[1] if '@' in redis_url else redis_url}")
        
        # Parse Redis URL and create connection
        try:
            if redis_url.startswith('rediss://'):
                # SSL connection for managed Redis/Valkey
                app.config['SESSION_REDIS'] = redis.from_url(
                    redis_url,
                    ssl_cert_reqs=None,  # Managed services don't need cert validation
                    decode_responses=False
                )
            else:
                # Regular Redis connection
                app.config['SESSION_REDIS'] = redis.from_url(redis_url, decode_responses=False)
            
            # Test the connection
            app.config['SESSION_REDIS'].ping()
            logger.info("Redis connection successful for Flask-Session")
        except Exception as e:
            logger.error(f"Failed to connect to Redis for sessions: {e}")
            # Fall back to filesystem sessions if Redis fails
            app.config['SESSION_TYPE'] = 'filesystem'
            logger.warning("Falling back to filesystem sessions")
        
        # Initialize Flask-Session
        Session(app)


class DevelopmentConfig(Config):
    """Development environment configuration"""
    DEBUG = True
    TESTING = False
    
    # Development-specific database URI
    SQLALCHEMY_DATABASE_URI = os.environ.get('DEV_DATABASE_URL') or \
        Config.SQLALCHEMY_DATABASE_URI
    
    # Development mail settings - use console backend
    MAIL_SUPPRESS_SEND = True
    
    # Allow non-secure cookies in development
    SESSION_COOKIE_SECURE = False
    
    # Faster bcrypt rounds for development
    BCRYPT_LOG_ROUNDS = 8
    
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
    
    # Disable login requirement for testing
    LOGIN_DISABLED = True
    
    # Use test Redis database
    CELERY_BROKER_URL = 'redis://localhost:6379/1'
    CELERY_RESULT_BACKEND = 'redis://localhost:6379/1'
    
    # Fast bcrypt rounds for testing
    BCRYPT_LOG_ROUNDS = 4
    
    @classmethod
    def init_app(cls, app):
        """Testing-specific initialization"""
        # Do NOT call Config.init_app for testing - it tries to connect to Redis
        # Instead, set up minimal session configuration for tests
        import logging
        logger = logging.getLogger(__name__)
        
        # Use cachelib sessions for testing to avoid Redis dependency and deprecation warnings
        app.config['SESSION_TYPE'] = 'cachelib'
        app.config['SESSION_PERMANENT'] = False
        app.config['SESSION_KEY_PREFIX'] = 'test_session:'
        
        # Initialize Flask-Session with CacheLib backend
        from flask_session import Session
        from cachelib import FileSystemCache
        import tempfile
        import os
        
        # Use a temporary directory for test sessions
        temp_dir = os.path.join(tempfile.gettempdir(), 'flask_test_sessions')
        os.makedirs(temp_dir, exist_ok=True)
        app.config['SESSION_CACHELIB'] = FileSystemCache(temp_dir, threshold=500, default_timeout=300)
        
        Session(app)
        logger.info("Testing mode: Using cachelib filesystem sessions")
        
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
    
    # Secure bcrypt rounds for production
    BCRYPT_LOG_ROUNDS = 14
    
    # Production Redis - set immediately for Flask-Session
    REDIS_URL = os.environ.get('REDIS_URL', '')
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
            # Make Redis optional for initial deployment
            redis_url = os.environ.get('REDIS_URL')
            if redis_url:
                cls.CELERY_BROKER_URL = redis_url
                cls.CELERY_RESULT_BACKEND = redis_url
            
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
