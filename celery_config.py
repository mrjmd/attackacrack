"""
Shared Celery configuration for both Flask app and Celery workers
"""
import os
import ssl
from celery import Celery

def create_celery_app(app_name=__name__):
    """Create a Celery app with proper SSL Redis configuration"""
    redis_url = os.environ.get('REDIS_URL') or os.environ.get('CELERY_BROKER_URL') or 'redis://redis:6379/0'
    
    # For Celery with SSL Redis, we need to configure it differently
    if redis_url.startswith('rediss://'):
        # Parse the URL to separate it into components
        from urllib.parse import urlparse, parse_qs
        parsed = urlparse(redis_url)
        
        # Check if ssl_cert_reqs is already in the URL
        query_params = parse_qs(parsed.query)
        
        # Build the Redis URL with proper SSL parameters
        if 'ssl_cert_reqs' not in query_params:
            # Add SSL parameters to the URL
            separator = '&' if parsed.query else '?'
            ssl_params = f"{separator}ssl_cert_reqs=CERT_NONE"
            celery_broker_url = redis_url + ssl_params
            celery_result_backend = redis_url + ssl_params
        else:
            celery_broker_url = redis_url
            celery_result_backend = redis_url
        
        # Create Celery instance with SSL configuration
        celery = Celery(
            app_name,
            broker=celery_broker_url,
            backend=celery_result_backend,
            broker_use_ssl={
                'ssl_cert_reqs': ssl.CERT_NONE,
                'ssl_ca_certs': None,
                'ssl_certfile': None,
                'ssl_keyfile': None,
            },
            redis_backend_use_ssl={
                'ssl_cert_reqs': ssl.CERT_NONE,
                'ssl_ca_certs': None,
                'ssl_certfile': None,
                'ssl_keyfile': None,
            }
        )
    else:
        # Non-SSL Redis
        celery = Celery(
            app_name,
            broker=redis_url,
            backend=redis_url
        )
    
    # Debug logging
    print(f"Redis URL: {redis_url}")
    print(f"Using SSL: {redis_url.startswith('rediss://')}")
    
    return celery