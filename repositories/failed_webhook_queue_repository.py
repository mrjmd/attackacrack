"""
FailedWebhookQueueRepository - Data access layer for failed webhook retry management (P1-16)

Handles database operations for the webhook error recovery system:
- Queuing failed webhooks for retry
- Finding pending retries
- Managing retry counts and timing
- Cleanup operations
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from utils.datetime_utils import utc_now
from decimal import Decimal
from sqlalchemy import desc, and_, or_, func

from repositories.base_repository import BaseRepository
from crm_database import FailedWebhookQueue


class FailedWebhookQueueRepository(BaseRepository):
    """Repository for FailedWebhookQueue data access and retry management"""
    
    def __init__(self, session):
        """Initialize repository with database session"""
        super().__init__(session, FailedWebhookQueue)
    
    def find_pending_retries(self, limit: int = 50) -> List[FailedWebhookQueue]:
        """
        Find failed webhooks that are ready for retry.
        
        Args:
            limit: Maximum number of results to return
            
        Returns:
            List of FailedWebhookQueue objects ready for retry
        """
        now = utc_now()
        
        return self.session.query(self.model_class)\
            .filter(self.model_class.resolved == False)\
            .filter(self.model_class.retry_count < self.model_class.max_retries)\
            .filter(or_(
                self.model_class.next_retry_at.is_(None),
                self.model_class.next_retry_at <= now
            ))\
            .order_by(self.model_class.created_at)\
            .limit(limit)\
            .all()
    
    def increment_retry_count(self, failed_webhook_id: int, base_delay_seconds: int = 60) -> Optional[FailedWebhookQueue]:
        """
        Increment retry count and calculate next retry time.
        
        Args:
            failed_webhook_id: ID of the failed webhook
            base_delay_seconds: Base delay for exponential backoff calculation
            
        Returns:
            Updated FailedWebhookQueue object or None if not found
        """
        webhook = self.session.get(self.model_class, failed_webhook_id)
        if not webhook:
            return None
            
        # Increment retry count
        webhook.retry_count += 1
        webhook.last_retry_at = utc_now()
        
        # Calculate next retry time using exponential backoff
        if webhook.retry_count < webhook.max_retries:
            delay_seconds = base_delay_seconds * (Decimal(str(webhook.backoff_multiplier)) ** webhook.retry_count)
            webhook.next_retry_at = utc_now() + timedelta(seconds=int(delay_seconds))
        else:
            # No more retries - set next_retry_at to None
            webhook.next_retry_at = None
            
        webhook.updated_at = utc_now()
        self.session.commit()
        return webhook
    
    def mark_as_resolved(self, failed_webhook_id: int, resolution_note: str = None) -> Optional[FailedWebhookQueue]:
        """
        Mark failed webhook as resolved.
        
        Args:
            failed_webhook_id: ID of the failed webhook
            resolution_note: Optional note about the resolution
            
        Returns:
            Updated FailedWebhookQueue object or None if not found
        """
        webhook = self.session.get(self.model_class, failed_webhook_id)
        if not webhook:
            return None
            
        webhook.resolved = True
        webhook.resolved_at = utc_now()
        webhook.resolution_note = resolution_note
        webhook.updated_at = utc_now()
        
        self.session.commit()
        return webhook
    
    def find_exhausted_retries(self) -> List[FailedWebhookQueue]:
        """
        Find webhooks that have exhausted all retry attempts.
        
        Returns:
            List of FailedWebhookQueue objects with exhausted retries
        """
        return self.session.query(self.model_class)\
            .filter(self.model_class.resolved == False)\
            .filter(self.model_class.retry_count >= self.model_class.max_retries)\
            .all()
    
    def find_by_event_id(self, event_id: str) -> Optional[FailedWebhookQueue]:
        """
        Find failed webhook by event ID.
        
        Args:
            event_id: OpenPhone event ID
            
        Returns:
            FailedWebhookQueue object or None if not found
        """
        return self.session.query(self.model_class)\
            .filter_by(event_id=event_id)\
            .first()
    
    def cleanup_old_failed_webhooks(self, days_old: int = 30) -> int:
        """
        Clean up old resolved or exhausted failed webhooks.
        
        Args:
            days_old: Delete webhooks older than this many days
            
        Returns:
            Number of deleted records
        """
        cutoff_date = utc_now() - timedelta(days=days_old)
        
        # Delete resolved webhooks or webhooks that have exhausted retries
        deleted_count = self.session.query(self.model_class)\
            .filter(self.model_class.created_at < cutoff_date)\
            .filter(or_(
                self.model_class.resolved == True,
                self.model_class.retry_count >= self.model_class.max_retries
            ))\
            .delete()
            
        self.session.commit()
        return deleted_count
    
    def get_failure_statistics(self, hours_back: int = 24) -> Dict[str, Any]:
        """
        Get failure statistics for monitoring and alerting.
        
        Args:
            hours_back: Calculate statistics for this many hours back
            
        Returns:
            Dictionary with failure statistics
        """
        cutoff_time = utc_now() - timedelta(hours=hours_back)
        
        # Total failed webhooks in time period
        total_failed = self.session.query(func.count(self.model_class.id))\
            .filter(self.model_class.created_at >= cutoff_time)\
            .scalar()
        
        # Pending retries
        pending_retries = self.session.query(func.count(self.model_class.id))\
            .filter(self.model_class.created_at >= cutoff_time)\
            .filter(self.model_class.resolved == False)\
            .filter(self.model_class.retry_count < self.model_class.max_retries)\
            .scalar()
        
        # Exhausted retries
        exhausted_retries = self.session.query(func.count(self.model_class.id))\
            .filter(self.model_class.created_at >= cutoff_time)\
            .filter(self.model_class.resolved == False)\
            .filter(self.model_class.retry_count >= self.model_class.max_retries)\
            .scalar()
        
        # Resolved
        resolved = self.session.query(func.count(self.model_class.id))\
            .filter(self.model_class.created_at >= cutoff_time)\
            .filter(self.model_class.resolved == True)\
            .scalar()
        
        # Calculate failure rate (need total webhook events for comparison)
        # For now, just return the counts
        failure_rate = 0.0
        if total_failed > 0:
            # This would need integration with WebhookEvent table for accurate rate
            # For now, estimate based on resolution rate
            failure_rate = (total_failed - resolved) / max(total_failed, 1)
        
        return {
            'total_failed': total_failed,
            'pending_retries': pending_retries,
            'exhausted_retries': exhausted_retries,
            'resolved': resolved,
            'failure_rate_24h': round(failure_rate, 3),
            'calculated_at': utc_now().isoformat()
        }
    
    def find_by_event_type(self, event_type: str, resolved: bool = None) -> List[FailedWebhookQueue]:
        """
        Find failed webhooks by event type.
        
        Args:
            event_type: Type of webhook event
            resolved: Filter by resolution status (None for all)
            
        Returns:
            List of FailedWebhookQueue objects
        """
        query = self.session.query(self.model_class)\
            .filter_by(event_type=event_type)
            
        if resolved is not None:
            query = query.filter_by(resolved=resolved)
            
        return query.order_by(desc(self.model_class.created_at)).all()
    
    def get_retry_queue_status(self) -> Dict[str, Any]:
        """
        Get overall status of the retry queue for monitoring.
        
        Returns:
            Dictionary with queue status information
        """
        now = utc_now()
        
        # Count by status
        total_unresolved = self.session.query(func.count(self.model_class.id))\
            .filter_by(resolved=False)\
            .scalar()
            
        ready_for_retry = self.session.query(func.count(self.model_class.id))\
            .filter(self.model_class.resolved == False)\
            .filter(self.model_class.retry_count < self.model_class.max_retries)\
            .filter(or_(
                self.model_class.next_retry_at.is_(None),
                self.model_class.next_retry_at <= now
            ))\
            .scalar()
            
        waiting_for_retry = self.session.query(func.count(self.model_class.id))\
            .filter(self.model_class.resolved == False)\
            .filter(self.model_class.retry_count < self.model_class.max_retries)\
            .filter(self.model_class.next_retry_at > now)\
            .scalar()
            
        # Next retry time
        next_retry = self.session.query(func.min(self.model_class.next_retry_at))\
            .filter(self.model_class.resolved == False)\
            .filter(self.model_class.next_retry_at > now)\
            .scalar()
        
        return {
            'total_unresolved': total_unresolved,
            'ready_for_retry': ready_for_retry,
            'waiting_for_retry': waiting_for_retry,
            'next_retry_at': next_retry.isoformat() if next_retry else None,
            'status_checked_at': now.isoformat()
        }
    
    def search(self, query: str, fields: Optional[List[str]] = None) -> List[FailedWebhookQueue]:
        """
        Search failed webhooks by event ID or event type.
        
        Args:
            query: Search query string
            fields: Fields to search in (ignored for failed webhooks)
            
        Returns:
            List of matching FailedWebhookQueue objects
        """
        if not query:
            return []
        
        search_filter = or_(
            self.model_class.event_id.ilike(f'%{query}%'),
            self.model_class.event_type.ilike(f'%{query}%'),
            self.model_class.error_message.ilike(f'%{query}%')
        )
        
        return self.session.query(self.model_class)\
            .filter(search_filter)\
            .order_by(desc(self.model_class.created_at))\
            .limit(100)\
            .all()