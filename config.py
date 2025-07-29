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
