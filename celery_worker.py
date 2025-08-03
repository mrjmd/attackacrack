# celery_worker.py
import os
from celery import Celery
from app import create_app

# --- FIXED: Configure Celery directly from environment variables ---
# This ensures the Celery CLI can start reliably without depending on the
# full Flask app context being available at import time.
redis_url = os.environ.get('REDIS_URL') or 'redis://redis:6379/0'

# For Celery with SSL Redis, we need to configure it differently
import ssl
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
        __name__,
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
        __name__,
        broker=redis_url,
        backend=redis_url
    )

# Debug logging
print(f"Redis URL: {redis_url}")
print(f"Using SSL: {redis_url.startswith('rediss://')}")

# Create the Flask app instance. This is still needed to provide context for tasks when they run.
flask_app = create_app()

# Set the custom Task class to ensure tasks run within the Flask app context.
class ContextTask(celery.Task):
    def __call__(self, *args, **kwargs):
        with flask_app.app_context():
            return self.run(*args, **kwargs)

celery.Task = ContextTask

# --- Celery Beat Schedule ---
# This is where we define the periodic tasks that Celery should run.
celery.conf.beat_schedule = {
    'run-daily-tasks': {
        'task': 'services.scheduler_service.run_daily_tasks',
        # Executes every 24 hours. For a specific time, like 8 AM, use crontab.
        # from celery.schedules import crontab
        # 'schedule': crontab(hour=8, minute=0),
        'schedule': 3600.0 * 24,
    },
}
celery.conf.timezone = 'UTC'

# Import tasks to ensure they're registered with Celery
# This must be done after the Flask app is created
try:
    with flask_app.app_context():
        import services.scheduler_service
        import tasks.campaign_tasks
        import tasks.sync_tasks
        print("Successfully imported tasks")
        print(f"Registered tasks: {list(celery.tasks.keys())}")
except Exception as e:
    print(f"Error importing tasks: {e}")
    import traceback
    traceback.print_exc()
