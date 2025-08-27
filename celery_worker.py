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
from celery.schedules import crontab

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
    'webhook-health-check': {
        'task': 'tasks.webhook_health_tasks.run_webhook_health_check',
        # Executes every hour to check webhook health
        'schedule': 3600.0,  # 1 hour
    },
    'cleanup-old-health-checks': {
        'task': 'tasks.webhook_health_tasks.cleanup_old_health_checks',
        # Executes daily to clean up old health check records
        'schedule': 3600.0 * 24,  # 24 hours
    },
    'openphone-reconciliation': {
        'task': 'tasks.reconciliation_tasks.run_daily_reconciliation',
        # Executes daily at 2 AM UTC to reconcile OpenPhone messages
        'schedule': crontab(hour=2, minute=0),
        'kwargs': {'hours_back': 48}  # Look back 48 hours to catch any delayed webhooks
    },
    'openphone-data-integrity': {
        'task': 'tasks.reconciliation_tasks.validate_data_integrity',
        # Executes weekly on Sunday at 3 AM UTC
        'schedule': crontab(hour=3, minute=0, day_of_week=0),
    },
    'webhook-retry-processing': {
        'task': 'tasks.webhook_retry_tasks.process_webhook_retries',
        # Executes every 5 minutes to process pending webhook retries
        'schedule': 300.0,  # 5 minutes
        'kwargs': {'limit': 50}
    },
    'webhook-failure-alerts': {
        'task': 'tasks.webhook_retry_tasks.webhook_failure_alerts',
        # Executes every hour to check for webhook failure alerts
        'schedule': 3600.0,  # 1 hour
    },
    'cleanup-old-failed-webhooks': {
        'task': 'tasks.webhook_retry_tasks.cleanup_old_failed_webhooks',
        # Executes weekly on Sunday at 4 AM UTC to clean up old failed webhooks
        'schedule': crontab(hour=4, minute=0, day_of_week=0),
        'kwargs': {'days_old': 30}
    },
    # Phase 3C: Campaign Scheduling Tasks
    'check-scheduled-campaigns': {
        'task': 'tasks.campaign_scheduling_tasks.check_scheduled_campaigns',
        # Executes every minute to check for campaigns ready to run
        'schedule': 60.0,  # 1 minute
    },
    'calculate-recurring-schedules': {
        'task': 'tasks.campaign_scheduling_tasks.calculate_recurring_schedules',
        # Executes every 15 minutes to update recurring campaign schedules
        'schedule': 900.0,  # 15 minutes
    },
    'cleanup-expired-campaigns': {
        'task': 'tasks.campaign_scheduling_tasks.cleanup_expired_campaigns',
        # Executes daily at 1 AM UTC to clean up expired recurring campaigns
        'schedule': crontab(hour=1, minute=0),
    },
    'send-schedule-notifications': {
        'task': 'tasks.campaign_scheduling_tasks.send_schedule_notifications',
        # Executes every 30 minutes to send upcoming campaign notifications
        'schedule': 1800.0,  # 30 minutes
    },
    'validate-scheduled-campaigns': {
        'task': 'tasks.campaign_scheduling_tasks.validate_scheduled_campaigns',
        # Executes every hour to validate scheduled campaigns
        'schedule': 3600.0,  # 1 hour
    },
    'archive-old-campaigns': {
        'task': 'tasks.campaign_scheduling_tasks.archive_old_campaigns',
        # Executes weekly on Sunday at 5 AM UTC to archive old campaigns
        'schedule': crontab(hour=5, minute=0, day_of_week=0),
        'kwargs': {'days_old': 90}
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
        import tasks.webhook_health_tasks
        import tasks.webhook_retry_tasks
        import tasks.reconciliation_tasks
        import tasks.campaign_scheduling_tasks
        import tasks.csv_import_tasks
        print("Successfully imported tasks")
        print(f"Registered tasks: {list(celery.tasks.keys())}")
except Exception as e:
    print(f"Error importing tasks: {e}")
    import traceback
    traceback.print_exc()
