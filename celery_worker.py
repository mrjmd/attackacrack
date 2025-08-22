# celery_worker.py
import os
from app import create_app
from celery_config import create_celery_app

# Create Celery instance with shared configuration
celery = create_celery_app(__name__)

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
    'process-campaign-queue': {
        'task': 'tasks.campaign_tasks.process_campaign_queue',
        # Executes every 60 seconds to process pending campaign sends
        'schedule': 60.0,
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
