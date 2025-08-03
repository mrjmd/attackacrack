"""
Utility functions for getting Celery instance with proper SSL configuration
"""

_celery_instance = None

def get_celery():
    """Get the Celery instance with proper SSL configuration for production"""
    global _celery_instance
    
    if _celery_instance is None:
        try:
            # First try to import the existing celery instance
            from celery_worker import celery
            _celery_instance = celery
        except ImportError:
            # If that fails, create a new one with proper config
            from celery_config import create_celery_app
            _celery_instance = create_celery_app('attackacrack')
    
    return _celery_instance