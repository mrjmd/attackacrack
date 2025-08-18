"""
Shared Celery configuration for both Flask app and Celery workers
"""
import os
import ssl
from celery import Celery

def create_celery_app(app_name=__name__):
    """Create a Celery app with proper SSL Redis configuration"""
    broker_url = os.environ.get('CELERY_BROKER_URL') or os.environ.get('REDIS_URL') or 'redis://redis:6379/0'
    result_backend_url = os.environ.get('CELERY_RESULT_BACKEND') or broker_url
    
    # Helper function to add SSL params to URL if needed
    def add_ssl_params(url):
        if not url.startswith('rediss://'):
            return url
        from urllib.parse import urlparse, parse_qs
        parsed = urlparse(url)
        query_params = parse_qs(parsed.query)
        if 'ssl_cert_reqs' not in query_params:
            separator = '&' if parsed.query else '?'
            return url + f"{separator}ssl_cert_reqs=CERT_NONE"
        return url
    
    # Check if either URL uses SSL
    broker_uses_ssl = broker_url.startswith('rediss://')
    backend_uses_ssl = result_backend_url.startswith('rediss://')
    
    # Process URLs for SSL if needed
    processed_broker_url = add_ssl_params(broker_url)
    processed_backend_url = add_ssl_params(result_backend_url)
    
    # Create Celery instance with appropriate configuration
    if broker_uses_ssl or backend_uses_ssl:
        # SSL configuration
        celery = Celery(
            app_name,
            broker=processed_broker_url,
            backend=processed_backend_url,
            broker_use_ssl={
                'ssl_cert_reqs': ssl.CERT_NONE,
                'ssl_ca_certs': None,
                'ssl_certfile': None,
                'ssl_keyfile': None,
            } if broker_uses_ssl else None,
            redis_backend_use_ssl={
                'ssl_cert_reqs': ssl.CERT_NONE,
                'ssl_ca_certs': None,
                'ssl_certfile': None,
                'ssl_keyfile': None,
            } if backend_uses_ssl else None,
            broker_connection_retry_on_startup=True,
            broker_connection_retry=True,
            broker_connection_max_retries=3,
            broker_transport_options={
                'socket_connect_timeout': 30,
                'socket_timeout': 30,
            }
        )
    else:
        # Non-SSL Redis
        celery = Celery(
            app_name,
            broker=broker_url,
            backend=result_backend_url
        )
    
    # Debug logging
    print(f"Broker URL: {broker_url}")
    print(f"Result Backend URL: {result_backend_url}")
    print(f"Broker uses SSL: {broker_uses_ssl}")
    print(f"Backend uses SSL: {backend_uses_ssl}")
    
    return celery