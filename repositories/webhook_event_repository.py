"""
WebhookEventRepository - Data access layer for WebhookEvent model
"""

from typing import List, Optional
from datetime import datetime
from sqlalchemy import desc, or_, and_
from repositories.base_repository import BaseRepository, PaginatedResult


class WebhookEventRepository(BaseRepository):
    """Repository for WebhookEvent data access"""
    
    def find_by_event_id(self, event_id: str) -> Optional:
        """
        Find webhook event by event ID.
        
        Args:
            event_id: OpenPhone event ID
            
        Returns:
            WebhookEvent object or None if not found
        """
        return self.session.query(self.model_class)\
            .filter_by(event_id=event_id)\
            .first()
    
    def find_by_event_type(self, event_type: str) -> List:
        """
        Find webhook events by event type.
        
        Args:
            event_type: Type of webhook event
            
        Returns:
            List of WebhookEvent objects
        """
        return self.session.query(self.model_class)\
            .filter_by(event_type=event_type)\
            .all()
    
    def find_unprocessed_events(self, limit: int = 100) -> List:
        """
        Find unprocessed webhook events.
        
        Args:
            limit: Maximum number of results
            
        Returns:
            List of unprocessed WebhookEvent objects
        """
        return self.session.query(self.model_class)\
            .filter_by(processed=False)\
            .limit(limit)\
            .all()
    
    def find_failed_events(self) -> List:
        """
        Find webhook events that failed processing.
        
        Returns:
            List of failed WebhookEvent objects
        """
        return self.session.query(self.model_class)\
            .filter(self.model_class.error_message.isnot(None))\
            .all()
    
    def mark_as_processed(self, event_id: int):
        """
        Mark a webhook event as processed.
        
        Args:
            event_id: ID of the webhook event
            
        Returns:
            Updated WebhookEvent object
        """
        event = self.session.query(self.model_class).get(event_id)
        if event:
            event.processed = True
            event.processed_at = datetime.utcnow()
            self.session.commit()
        return event
    
    def mark_as_failed(self, event_id: int, error_message: str):
        """
        Mark a webhook event as failed.
        
        Args:
            event_id: ID of the webhook event
            error_message: Error description
            
        Returns:
            Updated WebhookEvent object
        """
        event = self.session.query(self.model_class).get(event_id)
        if event:
            event.error_message = error_message
            self.session.commit()
        return event
    
    def count_by_event_type(self, event_type: str) -> int:
        """
        Count webhook events by type.
        
        Args:
            event_type: Type of webhook event
            
        Returns:
            Count of events
        """
        return self.session.query(self.model_class)\
            .filter_by(event_type=event_type)\
            .count()
    
    def search(self, query: str) -> List:
        """
        Search webhook events by event type or event ID.
        
        Args:
            query: Search query string
            
        Returns:
            List of matching WebhookEvent objects
        """
        if not query:
            return []
        
        search_filter = or_(
            self.model_class.event_type.ilike(f'%{query}%'),
            self.model_class.event_id.ilike(f'%{query}%')
        )
        
        return self.session.query(self.model_class)\
            .filter(search_filter)\
            .limit(100)\
            .all()