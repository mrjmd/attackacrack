import os
from dotenv import load_dotenv

# Find the absolute path of the root directory
basedir = os.path.abspath(os.path.dirname(__file__))

# Load the .env file from the root directory
load_dotenv(os.path.join(basedir, '.env'))

class Config:
    """
    Base configuration class. Contains default configuration settings
    and settings applicable to all environments.
    """
    # Flask settings
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'you-will-never-guess'
    FLASK_ENV = os.environ.get('FLASK_ENV')

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
