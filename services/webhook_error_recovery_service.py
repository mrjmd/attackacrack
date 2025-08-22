"""
WebhookErrorRecoveryService - Business logic for webhook error recovery and retry management (P1-15 to P1-17)

Handles the complete webhook error recovery workflow:
- Queuing failed webhooks for retry
- Processing retry attempts with exponential backoff
- Managing retry exhaustion
- Manual replay functionality
- Failure statistics and monitoring

Uses repository pattern for data access and Result pattern for error handling.
"""

import logging
from typing import Dict, Any, List, Optional, TYPE_CHECKING
from datetime import datetime, timedelta
from decimal import Decimal

from services.common.result import Result
from repositories.failed_webhook_queue_repository import FailedWebhookQueueRepository
from repositories.webhook_event_repository import WebhookEventRepository

if TYPE_CHECKING:
    from crm_database import FailedWebhookQueue

logger = logging.getLogger(__name__)


class WebhookErrorRecoveryService:
    """Service for webhook error recovery and retry management"""
    
    def __init__(self, 
                 failed_webhook_repository: FailedWebhookQueueRepository,
                 webhook_service,  # OpenPhoneWebhookServiceRefactored - avoid circular import
                 webhook_event_repository: WebhookEventRepository):
        """
        Initialize with injected dependencies.
        
        Args:
            failed_webhook_repository: Repository for FailedWebhookQueue data access
            webhook_service: Service for processing webhooks
            webhook_event_repository: Repository for WebhookEvent data access
        """
        self.failed_webhook_repository = failed_webhook_repository
        self.webhook_service = webhook_service
        self.webhook_event_repository = webhook_event_repository
    
    def queue_failed_webhook(self, webhook_data: Dict[str, Any], error_message: str, 
                           retry_config: Optional[Dict[str, Any]] = None) -> Result:
        """
        Queue a failed webhook for retry with exponential backoff.
        
        Args:
            webhook_data: Original webhook payload data
            error_message: Description of the error that occurred
            retry_config: Optional custom retry configuration
            
        Returns:
            Result with FailedWebhookQueue object or error
        """
        try:
            # Set default retry configuration
            default_config = {
                'max_retries': 5,
                'backoff_multiplier': Decimal('2.0'),
                'base_delay_seconds': 60
            }
            
            if retry_config:
                default_config.update(retry_config)
            
            # Calculate initial retry time (1 minute from now)
            next_retry_at = datetime.utcnow() + timedelta(seconds=default_config['base_delay_seconds'])
            
            # Create failed webhook queue entry
            failed_webhook_data = {
                'event_id': webhook_data.get('event_id', webhook_data.get('id', 'unknown')),
                'event_type': webhook_data.get('event_type', webhook_data.get('type', 'unknown')),
                'original_payload': webhook_data,
                'error_message': error_message,
                'retry_count': 0,
                'max_retries': default_config['max_retries'],
                'backoff_multiplier': default_config['backoff_multiplier'],
                'base_delay_seconds': default_config['base_delay_seconds'],
                'next_retry_at': next_retry_at,
                'resolved': False,
                'created_at': datetime.utcnow()
            }
            
            # Check if this webhook is already queued
            existing = self.failed_webhook_repository.find_by_event_id(
                failed_webhook_data['event_id']
            )
            
            if existing and not existing.resolved:
                logger.warning(f"Webhook {failed_webhook_data['event_id']} already queued for retry")
                return Result.success(existing)
            
            failed_webhook = self.failed_webhook_repository.create(failed_webhook_data)
            
            logger.info(f"Queued webhook {failed_webhook.event_id} for retry. Next attempt at {next_retry_at}")
            return Result.success(failed_webhook)
            
        except Exception as e:
            logger.error(f"Failed to queue webhook for retry: {e}")
            return Result.failure(f"Failed to queue webhook for retry: {str(e)}")
    
    def process_retry(self, failed_webhook: 'FailedWebhookQueue') -> Result:
        """
        Process a retry attempt for a failed webhook.
        
        Args:
            failed_webhook: FailedWebhookQueue object to retry
            
        Returns:
            Result indicating success or failure of retry
        """
        try:
            # Check if retry is exhausted
            if failed_webhook.is_retry_exhausted():
                error_msg = f"Webhook {failed_webhook.event_id} has exhausted all retry attempts ({failed_webhook.retry_count}/{failed_webhook.max_retries})"
                logger.warning(error_msg)
                return Result.failure(error_msg)
            
            # Check if it's time to retry
            if not failed_webhook.can_retry_now():
                error_msg = f"Webhook {failed_webhook.event_id} is not ready for retry yet"
                logger.debug(error_msg)
                return Result.failure(error_msg)
            
            logger.info(f"Attempting retry {failed_webhook.retry_count + 1}/{failed_webhook.max_retries} for webhook {failed_webhook.event_id}")
            
            # Attempt to process the webhook
            retry_result = self.webhook_service.process_webhook(failed_webhook.original_payload)
            
            if retry_result.is_success:
                # Success! Mark as resolved
                resolution_note = f"Successfully processed on retry attempt {failed_webhook.retry_count + 1}"
                self.failed_webhook_repository.mark_as_resolved(failed_webhook.id, resolution_note)
                
                logger.info(f"Webhook {failed_webhook.event_id} successfully processed on retry")
                return Result.success({
                    'processed': True,
                    'retry_count': failed_webhook.retry_count + 1,
                    'resolution_note': resolution_note
                })
            else:
                # Still failing - increment retry count
                self.failed_webhook_repository.increment_retry_count(
                    failed_webhook.id, 
                    base_delay_seconds=failed_webhook.base_delay_seconds
                )
                
                logger.warning(f"Webhook {failed_webhook.event_id} retry failed: {retry_result.error}")
                return Result.failure(f"Retry failed: {retry_result.error}")
                
        except Exception as e:
            # Unexpected error during retry - increment retry count
            logger.error(f"Unexpected error during webhook retry {failed_webhook.event_id}: {e}")
            
            try:
                self.failed_webhook_repository.increment_retry_count(
                    failed_webhook.id,
                    base_delay_seconds=failed_webhook.base_delay_seconds
                )
            except Exception as retry_error:
                logger.error(f"Failed to increment retry count: {retry_error}")
            
            return Result.failure(f"Unexpected error during retry: {str(e)}")
    
    def get_pending_retries(self, limit: int = 50) -> Result:
        """
        Get webhooks that are pending retry.
        
        Args:
            limit: Maximum number of results
            
        Returns:
            Result with list of pending FailedWebhookQueue objects
        """
        try:
            pending_retries = self.failed_webhook_repository.find_pending_retries(limit=limit)
            return Result.success(pending_retries)
            
        except Exception as e:
            logger.error(f"Failed to get pending retries: {e}")
            return Result.failure(f"Failed to get pending retries: {str(e)}")
    
    def manual_replay_webhook(self, failed_webhook_id: int) -> Result:
        """
        Manually replay a failed webhook (admin interface).
        
        Args:
            failed_webhook_id: ID of the failed webhook to replay
            
        Returns:
            Result indicating success or failure of manual replay
        """
        try:
            # Get the failed webhook
            failed_webhook = self.failed_webhook_repository.get_by_id(failed_webhook_id)
            if not failed_webhook:
                return Result.failure(f"Failed webhook {failed_webhook_id} not found")
            
            if failed_webhook.resolved:
                return Result.failure(f"Webhook {failed_webhook.event_id} is already resolved")
            
            logger.info(f"Manual replay requested for webhook {failed_webhook.event_id}")
            
            # Attempt to process the webhook
            replay_result = self.webhook_service.process_webhook(failed_webhook.original_payload)
            
            if replay_result.is_success:
                # Success! Mark as resolved
                resolution_note = f"Successfully processed via manual replay"
                self.failed_webhook_repository.mark_as_resolved(failed_webhook.id, resolution_note)
                
                logger.info(f"Manual replay successful for webhook {failed_webhook.event_id}")
                return Result.success({
                    'processed': True,
                    'event_id': failed_webhook.event_id,
                    'message': f"Webhook {failed_webhook.event_id} successfully replayed"
                })
            else:
                logger.warning(f"Manual replay failed for webhook {failed_webhook.event_id}: {replay_result.error}")
                return Result.failure(f"Manual replay failed: {replay_result.error}")
                
        except Exception as e:
            logger.error(f"Error during manual webhook replay {failed_webhook_id}: {e}")
            return Result.failure(f"Error during manual replay: {str(e)}")
    
    def get_failure_statistics(self, hours_back: int = 24) -> Result:
        """
        Get failure statistics for monitoring and alerting.
        
        Args:
            hours_back: Calculate statistics for this many hours back
            
        Returns:
            Result with failure statistics dictionary
        """
        try:
            stats = self.failed_webhook_repository.get_failure_statistics(hours_back=hours_back)
            return Result.success(stats)
            
        except Exception as e:
            logger.error(f"Failed to get failure statistics: {e}")
            return Result.failure(f"Failed to get failure statistics: {str(e)}")
    
    def get_retry_queue_status(self) -> Result:
        """
        Get current status of the retry queue.
        
        Returns:
            Result with queue status information
        """
        try:
            status = self.failed_webhook_repository.get_retry_queue_status()
            return Result.success(status)
            
        except Exception as e:
            logger.error(f"Failed to get retry queue status: {e}")
            return Result.failure(f"Failed to get retry queue status: {str(e)}")
    
    def cleanup_old_failed_webhooks(self, days_old: int = 30) -> Result:
        """
        Clean up old resolved or exhausted failed webhooks.
        
        Args:
            days_old: Delete webhooks older than this many days
            
        Returns:
            Result with number of deleted records
        """
        try:
            deleted_count = self.failed_webhook_repository.cleanup_old_failed_webhooks(days_old)
            
            logger.info(f"Cleaned up {deleted_count} old failed webhooks (older than {days_old} days)")
            return Result.success({
                'deleted_count': deleted_count,
                'days_old': days_old
            })
            
        except Exception as e:
            logger.error(f"Failed to cleanup old failed webhooks: {e}")
            return Result.failure(f"Failed to cleanup old failed webhooks: {str(e)}")
    
    def should_send_failure_alert(self, stats: Dict[str, Any]) -> bool:
        """
        Determine if failure alert should be sent based on statistics.
        
        Args:
            stats: Failure statistics dictionary
            
        Returns:
            True if alert should be sent
        """
        # Alert thresholds
        HIGH_FAILURE_RATE_THRESHOLD = 0.20  # 20%
        HIGH_EXHAUSTED_COUNT_THRESHOLD = 10
        
        failure_rate = stats.get('failure_rate_24h', 0)
        exhausted_retries = stats.get('exhausted_retries', 0)
        
        # Send alert if failure rate is high OR too many webhooks exhausted retries
        return (failure_rate >= HIGH_FAILURE_RATE_THRESHOLD or 
                exhausted_retries >= HIGH_EXHAUSTED_COUNT_THRESHOLD)
    
    def generate_failure_alert_message(self, stats: Dict[str, Any]) -> str:
        """
        Generate alert message for webhook failures.
        
        Args:
            stats: Failure statistics dictionary
            
        Returns:
            Formatted alert message
        """
        failure_rate = stats.get('failure_rate_24h', 0) * 100  # Convert to percentage
        total_failed = stats.get('total_failed', 0)
        exhausted_retries = stats.get('exhausted_retries', 0)
        pending_retries = stats.get('pending_retries', 0)
        
        message = f"🚨 Webhook Failure Alert\\n\\n"
        message += f"Webhook failure rate: {failure_rate:.1f}%\\n"
        message += f"Total failed webhooks (24h): {total_failed}\\n"
        message += f"Pending retries: {pending_retries}\\n"
        message += f"Exhausted retries: {exhausted_retries}\\n\\n"
        
        if exhausted_retries > 0:
            message += f"⚠️ {exhausted_retries} webhooks have exhausted all retry attempts and need manual attention.\\n\\n"
        
        message += f"Check the admin dashboard for details and manual replay options."
        
        return message