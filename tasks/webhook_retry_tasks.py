"""
Celery tasks for webhook error recovery and automatic retry processing (P1-14 to P1-17)

Tasks:
- process_webhook_retries: Periodic task to process pending retries
- retry_failed_webhook: Individual webhook retry task
- cleanup_old_failed_webhooks: Maintenance task for old records
- webhook_failure_alerts: Monitoring and alerting task

All tasks use the service registry pattern and proper error handling.
"""

import logging
from datetime import datetime
from celery.exceptions import Retry

from celery_worker import celery
from app import create_app
from logging_config import get_logger

logger = get_logger(__name__)


@celery.task(bind=True, max_retries=3, default_retry_delay=60)
def process_webhook_retries(self, limit: int = 50):
    """
    Process pending webhook retries using exponential backoff.
    
    This task runs periodically to find failed webhooks that are ready
    for retry and attempts to process them.
    
    Args:
        limit: Maximum number of retries to process in one batch
        
    Returns:
        Dict with processing results
    """
    app = create_app()
    
    with app.app_context():
        try:
            # Get error recovery service from registry
            error_recovery_service = app.services.get('webhook_error_recovery')
            if not error_recovery_service:
                raise ValueError("Webhook error recovery service not registered")
            
            # Get pending retries
            pending_result = error_recovery_service.get_pending_retries(limit=limit)
            if pending_result.is_failure:
                logger.error(f"Failed to get pending retries: {pending_result.error}")
                raise Exception(pending_result.error)
            
            pending_retries = pending_result.data
            
            if not pending_retries:
                logger.info("No pending retries found")
                return {'status': 'success', 'message': 'No pending retries found', 'processed': 0}
            
            logger.info(f"Processing {len(pending_retries)} pending webhook retries")
            
            # Process each retry
            processed_count = 0
            failed_count = 0
            
            for failed_webhook in pending_retries:
                try:
                    retry_result = error_recovery_service.process_retry(failed_webhook)
                    
                    if retry_result.is_success:
                        processed_count += 1
                        logger.debug(f"Successfully retried webhook {failed_webhook.event_id}")
                    else:
                        failed_count += 1
                        logger.warning(f"Retry failed for webhook {failed_webhook.event_id}: {retry_result.error}")
                        
                except Exception as e:
                    failed_count += 1
                    logger.error(f"Error processing retry for webhook {failed_webhook.event_id}: {e}")
            
            message = f"Processed: {processed_count}, Failed: {failed_count} webhook retries"
            logger.info(message)
            
            return {
                'status': 'success',
                'message': message,
                'processed': processed_count,
                'failed': failed_count,
                'total_pending': len(pending_retries)
            }
            
        except Exception as e:
            logger.error(f"Error in process_webhook_retries task: {e}")
            
            # Retry the task with exponential backoff
            if self.request.retries < self.max_retries:
                logger.info(f"Retrying process_webhook_retries task (attempt {self.request.retries + 1}/{self.max_retries})")
                raise self.retry(exc=e, countdown=2 ** self.request.retries * 60)
            else:
                # Max retries exceeded
                error_msg = f"process_webhook_retries task failed after {self.max_retries} retries: {e}"
                logger.error(error_msg)
                return {'status': 'error', 'message': error_msg}


@celery.task(bind=True, autoretry_for=(Exception,), max_retries=3, retry_backoff=True, retry_jitter=True)
def retry_failed_webhook(self, failed_webhook_id: int):
    """
    Retry a specific failed webhook (can be called manually or automatically).
    
    Args:
        failed_webhook_id: ID of the FailedWebhookQueue record to retry
        
    Returns:
        Dict with retry results
    """
    app = create_app()
    
    with app.app_context():
        try:
            # Get error recovery service from registry
            error_recovery_service = app.services.get('webhook_error_recovery')
            if not error_recovery_service:
                raise ValueError("Webhook error recovery service not registered")
            
            # Attempt manual replay
            replay_result = error_recovery_service.manual_replay_webhook(failed_webhook_id)
            
            if replay_result.is_success:
                message = f"Successfully replayed webhook: {replay_result.data.get('event_id', failed_webhook_id)}"
                logger.info(message)
                return {
                    'status': 'success',
                    'message': message,
                    'event_id': replay_result.data.get('event_id'),
                    'failed_webhook_id': failed_webhook_id
                }
            else:
                error_msg = f"Failed to replay webhook {failed_webhook_id}: {replay_result.error}"
                logger.error(error_msg)
                
                # Check if this is a permanent failure (webhook not found, already resolved)
                if "not found" in replay_result.error.lower() or "already resolved" in replay_result.error.lower():
                    # Don't retry permanent failures
                    return {'status': 'error', 'message': error_msg, 'permanent_failure': True}
                
                # Retry transient failures
                raise Exception(replay_result.error)
                
        except Exception as e:
            logger.error(f"Error in retry_failed_webhook task for ID {failed_webhook_id}: {e}")
            
            # Let Celery handle the retry with autoretry_for
            raise


@celery.task(bind=True)
def cleanup_old_failed_webhooks(self, days_old: int = 30):
    """
    Clean up old resolved or exhausted failed webhooks.
    
    Args:
        days_old: Delete webhooks older than this many days (default: 30)
        
    Returns:
        Dict with cleanup results
    """
    app = create_app()
    
    with app.app_context():
        try:
            # Get failed webhook repository from registry
            failed_webhook_repository = app.services.get('failed_webhook_queue_repository')
            if not failed_webhook_repository:
                raise ValueError("Failed webhook queue repository not registered")
            
            # Perform cleanup
            deleted_count = failed_webhook_repository.cleanup_old_failed_webhooks(days_old)
            
            message = f"Cleaned up {deleted_count} old failed webhooks (older than {days_old} days)"
            logger.info(message)
            
            return {
                'status': 'success',
                'message': message,
                'deleted_count': deleted_count,
                'days_old': days_old
            }
            
        except Exception as e:
            error_msg = f"Error in cleanup_old_failed_webhooks task: {e}"
            logger.error(error_msg)
            return {'status': 'error', 'message': error_msg}


@celery.task(bind=True)
def webhook_failure_alerts(self):
    """
    Check webhook failure statistics and send alerts if thresholds are exceeded.
    
    This task should run periodically to monitor webhook health and alert
    administrators when failure rates are too high.
    
    Returns:
        Dict with alert results
    """
    app = create_app()
    
    with app.app_context():
        try:
            # Get error recovery service from registry
            error_recovery_service = app.services.get('webhook_error_recovery')
            if not error_recovery_service:
                raise ValueError("Webhook error recovery service not registered")
            
            # Get failure statistics
            stats_result = error_recovery_service.get_failure_statistics(hours_back=24)
            if stats_result.is_failure:
                logger.error(f"Failed to get failure statistics: {stats_result.error}")
                raise Exception(stats_result.error)
            
            stats = stats_result.data
            logger.debug(f"Webhook failure statistics: {stats}")
            
            # Check if alert should be sent
            if error_recovery_service.should_send_failure_alert(stats):
                # Get notification service
                notification_service = app.services.get('notification')
                if not notification_service:
                    logger.warning("Notification service not available for webhook failure alerts")
                    return {
                        'status': 'warning',
                        'message': 'Alert needed but notification service not available',
                        'stats': stats
                    }
                
                # Generate and send alert
                alert_message = error_recovery_service.generate_failure_alert_message(stats)
                
                try:
                    notification_service.send_admin_alert(
                        alert_message,
                        subject="Webhook Failure Alert",
                        priority="high"
                    )
                    
                    logger.warning(f"Webhook failure alert sent: {stats}")
                    return {
                        'status': 'success',
                        'message': 'Alert sent due to high failure rate',
                        'stats': stats,
                        'alert_sent': True
                    }
                    
                except Exception as alert_error:
                    logger.error(f"Failed to send webhook failure alert: {alert_error}")
                    return {
                        'status': 'error',
                        'message': f'Failed to send alert: {alert_error}',
                        'stats': stats
                    }
            else:
                # No alert needed
                logger.debug("Webhook failure rates within acceptable limits")
                return {
                    'status': 'success',
                    'message': 'No alerts needed - failure rates acceptable',
                    'stats': stats,
                    'alert_sent': False
                }
                
        except Exception as e:
            error_msg = f"Error in webhook_failure_alerts task: {e}"
            logger.error(error_msg)
            return {'status': 'error', 'message': error_msg}


# Task for manual triggering of retry processing (useful for debugging)
@celery.task
def trigger_retry_processing(limit: int = 10):
    """
    Manually trigger retry processing (useful for testing/debugging).
    
    Args:
        limit: Maximum number of retries to process
        
    Returns:
        Task result from process_webhook_retries
    """
    logger.info(f"Manually triggering webhook retry processing (limit: {limit})")
    return process_webhook_retries.delay(limit=limit)


# Task for getting current retry queue status
@celery.task
def get_retry_queue_status():
    """
    Get current status of the webhook retry queue.
    
    Returns:
        Dict with queue status information
    """
    app = create_app()
    
    with app.app_context():
        try:
            error_recovery_service = app.services.get('webhook_error_recovery')
            if not error_recovery_service:
                return {'status': 'error', 'message': 'Error recovery service not registered'}
            
            status_result = error_recovery_service.get_retry_queue_status()
            
            if status_result.is_success:
                return {
                    'status': 'success',
                    'queue_status': status_result.data
                }
            else:
                return {
                    'status': 'error',
                    'message': status_result.error
                }
                
        except Exception as e:
            return {
                'status': 'error',
                'message': f'Error getting queue status: {str(e)}'
            }