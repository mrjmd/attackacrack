"""
Celery tasks for webhook health monitoring
Handles periodic health checks and alerting
"""

from datetime import datetime
from utils.datetime_utils import utc_now
from celery_worker import celery
from app import create_app
from logging_config import get_logger

logger = get_logger(__name__)


@celery.task(bind=True)
def run_webhook_health_check(self):
    """
    Run OpenPhone webhook health check
    Sends test message and verifies webhook receipt
    """
    # Create Flask app context for service registry access
    app = create_app()
    
    with app.app_context():
        try:
            # Get health check service from registry
            health_check_service = app.services.get('webhook_health_check')
            if not health_check_service:
                raise ValueError("Webhook health check service not registered")
            
            # Run health check
            result = health_check_service.run_health_check()
            
            # Log results
            logger.info(
                "Webhook health check completed",
                status=result.status.value,
                response_time=result.response_time,
                error=result.error_message
            )
            
            return {
                'success': result.status.value in ['success', 'sent'],
                'status': result.status.value,
                'response_time': result.response_time,
                'message_id': result.message_id,
                'error': result.error_message,
                'timestamp': utc_now().isoformat()
            }
            
        except Exception as e:
            logger.error("Webhook health check task failed", error=str(e))
            
            # Don't retry for configuration errors
            if "not registered" in str(e) or "not configured" in str(e):
                raise
            
            # Retry up to 3 times with exponential backoff
            self.retry(countdown=60 * (2 ** self.request.retries), max_retries=3)
            
            return {
                'success': False,
                'error': str(e),
                'timestamp': utc_now().isoformat()
            }


@celery.task
def get_webhook_health_status(hours: int = 24):
    """
    Get webhook health check status summary
    
    Args:
        hours: Number of hours to look back (default 24)
    
    Returns:
        Dictionary with health check statistics
    """
    # Create Flask app context for service registry access
    app = create_app()
    
    with app.app_context():
        try:
            # Get health check service from registry
            health_check_service = app.services.get('webhook_health_check')
            if not health_check_service:
                raise ValueError("Webhook health check service not registered")
            
            # Get status summary
            status = health_check_service.get_health_check_status(hours=hours)
            
            logger.info(
                "Retrieved webhook health status",
                total_checks=status['total_checks'],
                success_rate=status['success_rate']
            )
            
            return {
                'success': True,
                'data': status,
                'timestamp': utc_now().isoformat()
            }
            
        except Exception as e:
            logger.error("Failed to get webhook health status", error=str(e))
            return {
                'success': False,
                'error': str(e),
                'timestamp': utc_now().isoformat()
            }


@celery.task
def cleanup_old_health_checks(days: int = 30):
    """
    Clean up old health check records
    
    Args:
        days: Number of days to keep (default 30)
    
    Returns:
        Dictionary with cleanup results
    """
    # Create Flask app context for service registry access
    app = create_app()
    
    with app.app_context():
        try:
            from datetime import timedelta
            from crm_database import WebhookEvent
            from extensions import db
            
            # Calculate cutoff date
            cutoff_date = utc_now() - timedelta(days=days)
            
            # Delete old health check events
            deleted_count = WebhookEvent.query.filter(
                WebhookEvent.event_type.like('health_check.%'),
                WebhookEvent.created_at < cutoff_date
            ).delete()
            
            db.session.commit()
            
            logger.info(
                "Cleaned up old health check records",
                deleted_count=deleted_count,
                days_retained=days
            )
            
            return {
                'success': True,
                'deleted_count': deleted_count,
                'cutoff_date': cutoff_date.isoformat(),
                'timestamp': utc_now().isoformat()
            }
            
        except Exception as e:
            logger.error("Failed to cleanup old health checks", error=str(e))
            db.session.rollback()
            return {
                'success': False,
                'error': str(e),
                'timestamp': utc_now().isoformat()
            }