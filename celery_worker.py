# celery_worker.py
import os
from celery import Celery
from app import create_app

# --- FIXED: Configure Celery directly from environment variables ---
# This ensures the Celery CLI can start reliably without depending on the
# full Flask app context being available at import time.
celery_broker_url = os.environ.get('REDIS_URL') or 'redis://redis:6379/0'
celery_result_backend = os.environ.get('REDIS_URL') or 'redis://redis:6379/0'

celery = Celery(
    __name__,
    broker=celery_broker_url,
    backend=celery_result_backend
)

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
