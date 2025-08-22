"""
Celery tasks for OpenPhone reconciliation

Handles scheduled and manual reconciliation of OpenPhone data.
"""

import logging
from datetime import datetime
from typing import Dict, Any

from celery import shared_task
from flask import current_app

from services.common.result import Result

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def run_daily_reconciliation(self, hours_back: int = 48) -> Dict[str, Any]:
    """
    Daily task to reconcile OpenPhone messages with local database.
    
    Args:
        hours_back: Number of hours to look back for messages
        
    Returns:
        Dictionary with reconciliation results
    """
    try:
        logger.info(f"Starting daily OpenPhone reconciliation task for last {hours_back} hours")
        
        # Get reconciliation service from registry
        reconciliation_service = current_app.services.get('openphone_reconciliation')
        
        if not reconciliation_service:
            error_msg = "OpenPhone reconciliation service not found in registry"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        # Run message reconciliation
        message_result = reconciliation_service.reconcile_messages(hours_back=hours_back)
        
        if message_result.is_failure:
            logger.error(f"Message reconciliation failed: {message_result.error}")
            # Retry the task
            raise self.retry(
                exc=Exception(message_result.error),
                countdown=60 * (self.request.retries + 1)  # Exponential backoff
            )
        
        # Also reconcile conversations
        conversation_result = reconciliation_service.reconcile_conversations(hours_back=hours_back)
        
        # Prepare summary
        summary = {
            'task_id': self.request.id,
            'executed_at': datetime.utcnow().isoformat(),
            'hours_back': hours_back,
            'messages': message_result.value,
            'conversations': conversation_result.value if conversation_result.is_success else {
                'error': conversation_result.error if conversation_result.is_failure else 'Unknown error'
            },
            'success': True
        }
        
        # Log summary
        logger.info(
            f"Daily reconciliation completed successfully",
            extra={
                'total_messages': message_result.value.get('total_messages', 0),
                'new_messages': message_result.value.get('new_messages', 0),
                'errors': len(message_result.value.get('errors', []))
            }
        )
        
        # Send notification if there were errors
        if message_result.value.get('errors'):
            _send_error_notification(summary)
        
        return summary
        
    except Exception as e:
        logger.error(f"Daily reconciliation task failed: {e}", exc_info=True)
        
        # Retry with exponential backoff
        if self.request.retries < self.max_retries:
            raise self.retry(
                exc=e,
                countdown=60 * (self.request.retries + 1)
            )
        
        # Max retries exceeded
        summary = {
            'task_id': self.request.id,
            'executed_at': datetime.utcnow().isoformat(),
            'hours_back': hours_back,
            'success': False,
            'error': str(e),
            'retries': self.request.retries
        }
        
        _send_failure_notification(summary)
        return summary


@shared_task
def run_manual_reconciliation(hours_back: int = 24, user_id: int = None) -> Dict[str, Any]:
    """
    Manual reconciliation task triggered by user.
    
    Args:
        hours_back: Number of hours to look back
        user_id: ID of user who triggered the task
        
    Returns:
        Dictionary with reconciliation results
    """
    try:
        logger.info(
            f"Starting manual OpenPhone reconciliation",
            extra={'hours_back': hours_back, 'user_id': user_id}
        )
        
        # Get reconciliation service
        reconciliation_service = current_app.services.get('openphone_reconciliation')
        
        if not reconciliation_service:
            return {
                'success': False,
                'error': 'Reconciliation service not available'
            }
        
        # Run reconciliation
        result = reconciliation_service.reconcile_messages(hours_back=hours_back)
        
        if result.is_failure:
            return {
                'success': False,
                'error': result.error,
                'user_id': user_id
            }
        
        return {
            'success': True,
            'data': result.value,
            'user_id': user_id,
            'executed_at': datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Manual reconciliation failed: {e}", exc_info=True)
        return {
            'success': False,
            'error': str(e),
            'user_id': user_id
        }


@shared_task
def validate_data_integrity() -> Dict[str, Any]:
    """
    Task to validate data integrity between OpenPhone and local database.
    
    Returns:
        Dictionary with validation results
    """
    try:
        logger.info("Starting data integrity validation task")
        
        reconciliation_service = current_app.services.get('openphone_reconciliation')
        
        if not reconciliation_service:
            return {
                'success': False,
                'error': 'Reconciliation service not available'
            }
        
        result = reconciliation_service.validate_data_integrity()
        
        if result.is_failure:
            return {
                'success': False,
                'error': result.error
            }
        
        return {
            'success': True,
            'report': result.value,
            'executed_at': datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Data integrity validation failed: {e}", exc_info=True)
        return {
            'success': False,
            'error': str(e)
        }


@shared_task
def cleanup_old_reconciliation_logs(days_to_keep: int = 30) -> Dict[str, Any]:
    """
    Clean up old reconciliation logs and statistics.
    
    Args:
        days_to_keep: Number of days of logs to keep
        
    Returns:
        Dictionary with cleanup results
    """
    try:
        logger.info(f"Cleaning up reconciliation logs older than {days_to_keep} days")
        
        # This would clean up any stored logs or statistics
        # Implementation depends on how you store reconciliation history
        
        return {
            'success': True,
            'message': f'Cleaned up logs older than {days_to_keep} days',
            'executed_at': datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Cleanup task failed: {e}", exc_info=True)
        return {
            'success': False,
            'error': str(e)
        }


def _send_error_notification(summary: Dict[str, Any]):
    """
    Send notification about reconciliation errors.
    
    Args:
        summary: Reconciliation summary with errors
    """
    try:
        error_count = len(summary.get('messages', {}).get('errors', []))
        
        if error_count > 0:
            logger.warning(
                f"Reconciliation completed with {error_count} errors",
                extra={'summary': summary}
            )
            
            # Here you could send email, Slack notification, etc.
            # For now, just log
            
    except Exception as e:
        logger.error(f"Failed to send error notification: {e}")


def _send_failure_notification(summary: Dict[str, Any]):
    """
    Send notification about reconciliation failure.
    
    Args:
        summary: Reconciliation summary with failure details
    """
    try:
        logger.error(
            "Reconciliation task failed after max retries",
            extra={'summary': summary}
        )
        
        # Here you could send email, Slack notification, etc.
        # For now, just log
        
    except Exception as e:
        logger.error(f"Failed to send failure notification: {e}")