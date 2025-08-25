"""
EngagementEventRepository - Data access layer for EngagementEvent entities
Handles all database operations for engagement event tracking and analytics
"""

from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
from decimal import Decimal
from sqlalchemy import func, and_, or_, desc, asc, String
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from repositories.base_repository import BaseRepository, PaginationParams, PaginatedResult, SortOrder
from crm_database import EngagementEvent, Contact, Campaign
from utils.datetime_utils import utc_now, ensure_utc
import logging

logger = logging.getLogger(__name__)

# Valid event types and channels
VALID_EVENT_TYPES = {
    'delivered', 'opened', 'clicked', 'responded', 
    'converted', 'opted_out', 'bounced'
}
VALID_CHANNELS = {'sms', 'email', 'call'}


class EngagementEventRepository(BaseRepository[EngagementEvent]):
    """Repository for EngagementEvent data access"""
    
    def __init__(self, session: Session):
        """Initialize repository with database session"""
        super().__init__(session, EngagementEvent)
    
    def create(self, **kwargs) -> EngagementEvent:
        """
        Create a new engagement event with validation.
        
        Args:
            **kwargs: Event attributes including:
                - contact_id: Required contact ID
                - campaign_id: Required campaign ID
                - event_type: Required event type (must be valid)
                - event_timestamp: Required timestamp
                - channel: Required channel (must be valid)
                - message_id: Optional message identifier
                - parent_event_id: Optional parent event for chains
                - Additional event-specific fields
        
        Returns:
            Created EngagementEvent instance
        
        Raises:
            ValueError: If event_type or channel is invalid
            SQLAlchemyError: If database operation fails
        """
        # Validate event type
        event_type = kwargs.get('event_type')
        if event_type and event_type not in VALID_EVENT_TYPES:
            raise ValueError(f"Invalid event type: {event_type}. Must be one of {VALID_EVENT_TYPES}")
        
        # Validate channel
        channel = kwargs.get('channel')
        if channel and channel not in VALID_CHANNELS:
            raise ValueError(f"Invalid channel: {channel}. Must be one of {VALID_CHANNELS}")
        
        # Ensure timestamp is UTC
        if 'event_timestamp' in kwargs:
            kwargs['event_timestamp'] = ensure_utc(kwargs['event_timestamp'])
        
        try:
            return super().create(**kwargs)
        except IntegrityError as e:
            logger.error(f"Integrity error creating engagement event: {e}")
            self.session.rollback()
            raise
    
    def bulk_create(self, events_data: List[Dict[str, Any]]) -> List[EngagementEvent]:
        """
        Bulk create multiple engagement events efficiently.
        
        Args:
            events_data: List of event data dictionaries
        
        Returns:
            List of created EngagementEvent instances
        
        Raises:
            ValueError: If any event has invalid type or channel
            SQLAlchemyError: If database operation fails
        """
        # Validate all events first
        for event_data in events_data:
            event_type = event_data.get('event_type')
            if event_type and event_type not in VALID_EVENT_TYPES:
                raise ValueError(f"Invalid event type: {event_type}")
            
            channel = event_data.get('channel')
            if channel and channel not in VALID_CHANNELS:
                raise ValueError(f"Invalid channel: {channel}")
            
            # Ensure timestamp is UTC
            if 'event_timestamp' in event_data:
                event_data['event_timestamp'] = ensure_utc(event_data['event_timestamp'])
        
        try:
            return super().create_many(events_data)
        except SQLAlchemyError as e:
            logger.error(f"Error bulk creating engagement events: {e}")
            self.session.rollback()
            raise
    
    def get_events_for_contact(self, contact_id: int, 
                               limit: Optional[int] = None) -> List[EngagementEvent]:
        """
        Get all engagement events for a specific contact.
        
        Args:
            contact_id: Contact ID
            limit: Optional limit on number of events
        
        Returns:
            List of EngagementEvent instances ordered by timestamp desc
        """
        try:
            query = self.session.query(EngagementEvent).filter(
                EngagementEvent.contact_id == contact_id
            ).order_by(desc(EngagementEvent.event_timestamp))
            
            if limit:
                query = query.limit(limit)
            
            return query.all()
        except SQLAlchemyError as e:
            logger.error(f"Error getting events for contact {contact_id}: {e}")
            return []
    
    def get_events_for_campaign(self, campaign_id: int,
                                limit: Optional[int] = None) -> List[EngagementEvent]:
        """
        Get all engagement events for a specific campaign.
        
        Args:
            campaign_id: Campaign ID
            limit: Optional limit on number of events
        
        Returns:
            List of EngagementEvent instances ordered by timestamp desc
        """
        try:
            query = self.session.query(EngagementEvent).filter(
                EngagementEvent.campaign_id == campaign_id
            ).order_by(desc(EngagementEvent.event_timestamp))
            
            if limit:
                query = query.limit(limit)
            
            return query.all()
        except SQLAlchemyError as e:
            logger.error(f"Error getting events for campaign {campaign_id}: {e}")
            return []
    
    def get_events_by_date_range(self, start_date: datetime, end_date: datetime,
                                 contact_id: Optional[int] = None,
                                 campaign_id: Optional[int] = None) -> List[EngagementEvent]:
        """
        Get events within a specific date range.
        
        Args:
            start_date: Start of date range (inclusive)
            end_date: End of date range (inclusive)
            contact_id: Optional filter by contact
            campaign_id: Optional filter by campaign
        
        Returns:
            List of EngagementEvent instances
        """
        try:
            start_date = ensure_utc(start_date)
            end_date = ensure_utc(end_date)
            
            query = self.session.query(EngagementEvent).filter(
                and_(
                    EngagementEvent.event_timestamp >= start_date,
                    EngagementEvent.event_timestamp <= end_date
                )
            )
            
            if contact_id:
                query = query.filter(EngagementEvent.contact_id == contact_id)
            
            if campaign_id:
                query = query.filter(EngagementEvent.campaign_id == campaign_id)
            
            return query.order_by(desc(EngagementEvent.event_timestamp)).all()
        except SQLAlchemyError as e:
            logger.error(f"Error getting events by date range: {e}")
            return []
    
    def get_events_by_type(self, event_type: str,
                           contact_id: Optional[int] = None,
                           campaign_id: Optional[int] = None) -> List[EngagementEvent]:
        """
        Get all events of a specific type.
        
        Args:
            event_type: Type of event to filter by
            contact_id: Optional filter by contact
            campaign_id: Optional filter by campaign
        
        Returns:
            List of EngagementEvent instances
        """
        try:
            query = self.session.query(EngagementEvent).filter(
                EngagementEvent.event_type == event_type
            )
            
            if contact_id:
                query = query.filter(EngagementEvent.contact_id == contact_id)
            
            if campaign_id:
                query = query.filter(EngagementEvent.campaign_id == campaign_id)
            
            return query.order_by(desc(EngagementEvent.event_timestamp)).all()
        except SQLAlchemyError as e:
            logger.error(f"Error getting events by type {event_type}: {e}")
            return []
    
    def aggregate_events_by_type(self, contact_id: Optional[int] = None,
                                 campaign_id: Optional[int] = None) -> Dict[str, int]:
        """
        Get count of events grouped by type.
        
        Args:
            contact_id: Optional filter by contact
            campaign_id: Optional filter by campaign
        
        Returns:
            Dictionary mapping event type to count
        """
        try:
            query = self.session.query(
                EngagementEvent.event_type,
                func.count(EngagementEvent.id).label('count')
            )
            
            if contact_id:
                query = query.filter(EngagementEvent.contact_id == contact_id)
            
            if campaign_id:
                query = query.filter(EngagementEvent.campaign_id == campaign_id)
            
            results = query.group_by(EngagementEvent.event_type).all()
            
            # Convert to dictionary and ensure all event types are present
            aggregation = {event_type: 0 for event_type in VALID_EVENT_TYPES}
            for event_type, count in results:
                aggregation[event_type] = count
            
            return aggregation
        except SQLAlchemyError as e:
            logger.error(f"Error aggregating events by type: {e}")
            return {event_type: 0 for event_type in VALID_EVENT_TYPES}
    
    def get_recent_events_for_scoring(self, days_back: int = 30) -> List[EngagementEvent]:
        """
        Get recent events for engagement scoring calculations.
        
        Args:
            days_back: Number of days to look back (default: 30)
        
        Returns:
            List of recent EngagementEvent instances
        """
        try:
            cutoff_date = utc_now() - timedelta(days=days_back)
            
            return self.session.query(EngagementEvent).filter(
                EngagementEvent.event_timestamp >= cutoff_date
            ).order_by(desc(EngagementEvent.event_timestamp)).all()
        except SQLAlchemyError as e:
            logger.error(f"Error getting recent events for scoring: {e}")
            return []
    
    def get_conversion_events_with_value(self, min_value: Optional[Decimal] = None) -> List[EngagementEvent]:
        """
        Get conversion events that have monetary value.
        
        Args:
            min_value: Optional minimum conversion value filter
        
        Returns:
            List of conversion EngagementEvent instances with value
        """
        try:
            query = self.session.query(EngagementEvent).filter(
                and_(
                    EngagementEvent.event_type == 'converted',
                    EngagementEvent.conversion_value.isnot(None)
                )
            )
            
            if min_value is not None:
                query = query.filter(EngagementEvent.conversion_value >= min_value)
            
            return query.order_by(desc(EngagementEvent.conversion_value)).all()
        except SQLAlchemyError as e:
            logger.error(f"Error getting conversion events with value: {e}")
            return []
    
    def get_engagement_funnel_data(self, campaign_id: int) -> Dict[str, int]:
        """
        Get engagement funnel data for analytics.
        
        Args:
            campaign_id: Campaign ID to analyze
        
        Returns:
            Dictionary with counts for each funnel stage
        """
        try:
            # Define funnel stages in order
            funnel_stages = ['delivered', 'opened', 'clicked', 'responded', 'converted']
            
            # Get counts for each stage
            funnel_data = {}
            for stage in funnel_stages:
                count = self.session.query(func.count(EngagementEvent.id)).filter(
                    and_(
                        EngagementEvent.campaign_id == campaign_id,
                        EngagementEvent.event_type == stage
                    )
                ).scalar()
                funnel_data[stage] = count or 0
            
            return funnel_data
        except SQLAlchemyError as e:
            logger.error(f"Error getting engagement funnel data: {e}")
            return {stage: 0 for stage in ['delivered', 'opened', 'clicked', 'responded', 'converted']}
    
    def search(self, query: str, fields: Optional[List[str]] = None) -> List[EngagementEvent]:
        """
        Search engagement events by text query.
        
        Args:
            query: Search query string
            fields: Fields to search in (default: event_metadata)
        
        Returns:
            List of matching EngagementEvent instances
        """
        if not query:
            return []
        
        try:
            search_fields = fields or ['event_metadata']
            conditions = []
            
            for field in search_fields:
                if field == 'event_metadata' and hasattr(EngagementEvent, 'event_metadata'):
                    # Search in JSON field (PostgreSQL specific)
                    conditions.append(
                        func.cast(EngagementEvent.event_metadata, String).ilike(f'%{query}%')
                    )
                elif hasattr(EngagementEvent, field):
                    attr = getattr(EngagementEvent, field)
                    if hasattr(attr, 'ilike'):
                        conditions.append(attr.ilike(f'%{query}%'))
            
            if not conditions:
                return []
            
            return self.session.query(EngagementEvent).filter(
                or_(*conditions)
            ).order_by(desc(EngagementEvent.event_timestamp)).all()
        except Exception as e:
            logger.error(f"Error searching engagement events: {e}")
            return []
    
    def get_paginated(self, pagination: PaginationParams,
                     filters: Optional[Dict[str, Any]] = None,
                     order_by: Optional[str] = None,
                     order: SortOrder = SortOrder.DESC) -> PaginatedResult[EngagementEvent]:
        """
        Get paginated engagement events.
        
        Args:
            pagination: Pagination parameters
            filters: Optional filters to apply
            order_by: Field to order by (default: event_timestamp)
            order: Sort order
        
        Returns:
            PaginatedResult with events and metadata
        """
        # Default ordering by event_timestamp
        if not order_by:
            order_by = 'event_timestamp'
        
        return super().get_paginated(pagination, filters, order_by, order)
    
    def delete_events_older_than(self, cutoff_date: datetime) -> int:
        """
        Delete events older than a specified date for data retention.
        
        Args:
            cutoff_date: Date before which events should be deleted
        
        Returns:
            Number of deleted events
        """
        try:
            cutoff_date = ensure_utc(cutoff_date)
            
            # Get events to delete
            events_to_delete = self.session.query(EngagementEvent).filter(
                EngagementEvent.event_timestamp < cutoff_date
            ).all()
            
            count = len(events_to_delete)
            
            # Delete events
            for event in events_to_delete:
                self.session.delete(event)
            
            self.session.flush()
            logger.info(f"Deleted {count} engagement events older than {cutoff_date}")
            
            return count
        except SQLAlchemyError as e:
            logger.error(f"Error deleting old engagement events: {e}")
            self.session.rollback()
            return 0
