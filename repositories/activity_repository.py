"""
ActivityRepository - Data access layer for Activity model
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from utils.datetime_utils import utc_now
from sqlalchemy import desc, func
from repositories.base_repository import BaseRepository, PaginatedResult
from crm_database import Activity


class ActivityRepository(BaseRepository):
    """Repository for Activity data access"""
    
    def __init__(self, session):
        """Initialize repository with database session"""
        super().__init__(session, Activity)
    
    def find_by_conversation_id(self, conversation_id: int) -> List:
        """
        Find all activities for a conversation.
        
        Args:
            conversation_id: ID of the conversation
            
        Returns:
            List of Activity objects ordered by created_at desc
        """
        return self.session.query(self.model_class)\
            .filter_by(conversation_id=conversation_id)\
            .order_by(desc(self.model_class.created_at))\
            .all()
    
    def find_by_contact_id(self, contact_id: int, limit: int = 50) -> List:
        """
        Find activities for a contact.
        
        Args:
            contact_id: ID of the contact
            limit: Maximum number of results
            
        Returns:
            List of Activity objects ordered by created_at desc
        """
        return self.session.query(self.model_class)\
            .filter_by(contact_id=contact_id)\
            .order_by(desc(self.model_class.created_at))\
            .limit(limit)\
            .all()
    
    def find_recent_activities(self, limit: int = 100) -> List:
        """
        Find the most recent activities.
        
        Args:
            limit: Maximum number of results
            
        Returns:
            List of most recent Activity objects
        """
        return self.session.query(self.model_class)\
            .order_by(desc(self.model_class.created_at))\
            .limit(limit)\
            .all()
    
    def find_by_type(self, activity_type: str) -> List:
        """
        Find all activities of a specific type.
        
        Args:
            activity_type: Type of activity (sms, call, voicemail, etc.)
            
        Returns:
            List of Activity objects of the specified type
        """
        return self.session.query(self.model_class)\
            .filter_by(activity_type=activity_type)\
            .all()
    
    def find_by_openphone_id(self, openphone_id: str) -> Optional:
        """
        Find activity by OpenPhone ID.
        
        Args:
            openphone_id: OpenPhone activity ID
            
        Returns:
            Activity object or None if not found
        """
        return self.session.query(self.model_class)\
            .filter_by(openphone_id=openphone_id)\
            .first()
    
    def find_by_campaign_id(self, campaign_id: int) -> List:
        """
        Find activities by campaign ID.
        
        Args:
            campaign_id: Campaign ID to search for
            
        Returns:
            List of activities
        """
        try:
            return self.session.query(self.model_class).filter_by(campaign_id=campaign_id).all()
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error finding activities by campaign ID: {e}")
            return []
    
    def get_activities_page(self, page: int = 1, per_page: int = 50, 
                           filters: Optional[dict] = None) -> PaginatedResult:
        """
        Get paginated activities with optional filters.
        
        Args:
            page: Page number (1-indexed)
            per_page: Items per page
            filters: Optional filter criteria
            
        Returns:
            PaginatedResult with activities
        """
        query = self.session.query(self.model_class)
        
        if filters:
            for key, value in filters.items():
                if hasattr(self.model_class, key):
                    query = query.filter_by(**{key: value})
        
        total = query.count()
        items = query.order_by(desc(self.model_class.created_at))\
            .limit(per_page)\
            .offset((page - 1) * per_page)\
            .all()
        
        return PaginatedResult(
            items=items,
            total=total,
            page=page,
            per_page=per_page
        )
    
    def count_by_type(self, activity_type: str) -> int:
        """
        Count activities of a specific type.
        
        Args:
            activity_type: Type of activity
            
        Returns:
            Count of activities
        """
        return self.session.query(self.model_class)\
            .filter_by(activity_type=activity_type)\
            .count()
    
    def update_activity_summary(self, activity_id: int, summary: str):
        """
        Update the summary field of an activity.
        
        Args:
            activity_id: ID of the activity
            summary: New summary text
            
        Returns:
            Updated Activity object
        """
        activity = self.session.get(self.model_class, activity_id)
        if activity:
            activity.summary = summary
            self.session.commit()
        return activity
    
    def find_unprocessed_activities(self, limit: int = 100) -> List:
        """
        Find activities that haven't been processed yet.
        
        Args:
            limit: Maximum number of results
            
        Returns:
            List of unprocessed Activity objects
        """
        return self.session.query(self.model_class)\
            .filter_by(processed=False)\
            .limit(limit)\
            .all()
    
    def mark_as_processed(self, activity_id: int) -> bool:
        """
        Mark an activity as processed.
        
        Args:
            activity_id: ID of the activity
            
        Returns:
            True if successful, False otherwise
        """
        activity = self.session.get(self.model_class, activity_id)
        if activity:
            activity.processed = True
            self.session.commit()
            return True
        return False
    
    def search(self, query: str) -> List:
        """
        Search activities by content or summary.
        
        Args:
            query: Search query string
            
        Returns:
            List of matching Activity objects
        """
        from sqlalchemy import or_
        
        if not query:
            return []
        
        search_filter = or_(
            self.model_class.content.ilike(f'%{query}%'),
            self.model_class.summary.ilike(f'%{query}%')
        )
        
        return self.session.query(self.model_class)\
            .filter(search_filter)\
            .order_by(desc(self.model_class.created_at))\
            .limit(100)\
            .all()
    
    # Dashboard-specific methods
    
    def get_message_volume_data(self, days: int = 7) -> List[Dict[str, Any]]:
        """
        Get message volume data for the last N days.
        
        Args:
            days: Number of days to look back
            
        Returns:
            List of dictionaries with date and count for each day
        """
        from datetime import datetime, timedelta
        
        message_volume_data = []
        for i in range(days):
            day = utc_now().date() - timedelta(days=days-1-i)
            count = self.session.query(self.model_class).filter(
                self.model_class.activity_type == 'message',
                func.date(self.model_class.created_at) == day
            ).count()
            message_volume_data.append({'date': day, 'count': count})
            
        return message_volume_data
    
    def get_messages_sent_today_count(self) -> int:
        """
        Get count of outgoing messages sent today.
        
        Returns:
            Number of outgoing messages sent today
        """
        from datetime import datetime, time
        
        # Get start and end of today in UTC
        today_start = datetime.combine(utc_now().date(), time.min)
        today_end = datetime.combine(utc_now().date(), time.max)
        
        return self.session.query(self.model_class).filter(
            self.model_class.activity_type == 'message',
            self.model_class.direction == 'outgoing',
            self.model_class.created_at >= today_start,
            self.model_class.created_at <= today_end
        ).count()
    
    def calculate_overall_response_rate(self) -> float:
        """
        Calculate overall response rate (incoming vs outgoing messages).
        
        Returns:
            Response rate as percentage (0-100)
        """
        total_outgoing = self.session.query(self.model_class).filter(
            self.model_class.activity_type == 'message',
            self.model_class.direction == 'outgoing'
        ).count()
        
        if total_outgoing == 0:
            return 0
        
        total_incoming = self.session.query(self.model_class).filter(
            self.model_class.activity_type == 'message',
            self.model_class.direction == 'incoming'
        ).count()
        
        return round((total_incoming / total_outgoing) * 100, 1)
    
    def get_distinct_contacts_with_recent_activity(self, days: int = 7) -> int:
        """
        Get count of distinct contacts with activity in the last N days.
        
        Args:
            days: Number of days to look back
            
        Returns:
            Number of distinct contacts with recent activity
        """
        from datetime import datetime, timedelta
        
        cutoff_date = utc_now() - timedelta(days=days)
        return self.session.query(self.model_class.contact_id).filter(
            self.model_class.created_at >= cutoff_date,
            self.model_class.contact_id.isnot(None)
        ).distinct().count()
    
    # SMS Metrics Enhancement Methods
    
    def update_activity_status_with_metadata(self, activity_id: int, status: str, metadata: dict):
        """
        Update activity status and merge metadata for SMS metrics tracking.
        
        Args:
            activity_id: ID of the activity to update
            status: New status to set
            metadata: Metadata to merge with existing metadata
            
        Returns:
            Updated Activity object or None if not found
        """
        activity = self.get_by_id(activity_id)
        if not activity:
            return None
        
        # Update status
        activity.status = status
        activity.updated_at = utc_now()
        
        # Merge metadata
        if activity.activity_metadata:
            activity.activity_metadata.update(metadata)
        else:
            activity.activity_metadata = metadata
        
        self.session.flush()
        return activity
    
    def find_messages_by_date_range_and_direction(self, since_date: datetime, direction: str) -> List:
        """
        Find message activities by date range and direction.
        
        Args:
            since_date: Start date for filtering
            direction: Message direction ('outgoing' or 'incoming')
            
        Returns:
            List of matching Activity objects
        """
        return self.session.query(self.model_class).filter(
            self.model_class.activity_type == 'message',
            self.model_class.direction == direction,
            self.model_class.created_at >= since_date
        ).all()
    
    def find_messages_by_contact_with_order(self, contact_id: int, order: str = 'created_at_desc', limit: int = 10) -> List:
        """
        Find messages for a contact with specific ordering.
        
        Args:
            contact_id: Contact ID to filter by
            order: Ordering option ('created_at_desc' or 'created_at_asc')
            limit: Maximum number of results
            
        Returns:
            List of ordered Activity objects
        """
        query = self.session.query(self.model_class).filter(
            self.model_class.contact_id == contact_id,
            self.model_class.activity_type == 'message'
        )
        
        if order == 'created_at_desc':
            query = query.order_by(desc(self.model_class.created_at))
        else:
            query = query.order_by(self.model_class.created_at)
            
        return query.limit(limit).all()
    
    def get_message_status_counts_by_categories(self, status_categories: dict, since_date: datetime, direction: str = None) -> dict:
        """
        Get message counts grouped by status categories.
        
        Args:
            status_categories: Dict mapping category names to list of statuses
            since_date: Start date for filtering
            direction: Optional direction filter
            
        Returns:
            Dict with category names and their counts
        """
        # Build base query
        query = self.session.query(self.model_class).filter(
            self.model_class.activity_type == 'message',
            self.model_class.created_at >= since_date
        )
        
        if direction:
            query = query.filter(self.model_class.direction == direction)
        
        # Get all messages
        messages = query.all()
        
        # Count by categories
        counts = {category: 0 for category in status_categories.keys()}
        
        for message in messages:
            for category, statuses in status_categories.items():
                if message.status in statuses:
                    counts[category] += 1
                    break
        
        return counts
    
    def find_activities_with_bounce_metadata(self, since_date: datetime) -> List:
        """
        Find activities that have bounce metadata.
        
        Args:
            since_date: Start date for filtering
            
        Returns:
            List of Activity objects with bounce metadata
        """
        return self.session.query(self.model_class).filter(
            self.model_class.created_at >= since_date,
            self.model_class.activity_metadata.contains('bounce_type')
        ).all()
    
    def get_daily_message_stats(self, days: int = 7) -> List[dict]:
        """
        Get daily message statistics for the last N days.
        
        Args:
            days: Number of days to analyze
            
        Returns:
            List of daily statistics dictionaries
        """
        stats = []
        
        for i in range(days):
            day = utc_now().date() - timedelta(days=days-1-i)
            
            # Count messages for this day
            day_messages = self.session.query(self.model_class).filter(
                self.model_class.activity_type == 'message',
                func.date(self.model_class.created_at) == day
            ).all()
            
            sent = sum(1 for m in day_messages if m.direction == 'outgoing')
            bounced = sum(1 for m in day_messages if m.status in ['failed', 'undelivered', 'rejected', 'blocked'])
            bounce_rate = (bounced / sent * 100) if sent > 0 else 0
            
            stats.append({
                'date': day,
                'sent': sent,
                'bounced': bounced,
                'bounce_rate': bounce_rate
            })
        
        return stats
    
    def update_activity_metadata(self, activity_id: int, metadata: dict, merge: bool = True):
        """
        Update activity metadata.
        
        Args:
            activity_id: ID of the activity to update
            metadata: Metadata to set/merge
            merge: Whether to merge with existing metadata
            
        Returns:
            Updated Activity object or None if not found
        """
        activity = self.get_by_id(activity_id)
        if not activity:
            return None
        
        if merge and activity.activity_metadata:
            activity.activity_metadata.update(metadata)
        else:
            activity.activity_metadata = metadata
        
        activity.updated_at = utc_now()
        self.session.flush()
        return activity
    
    def find_failed_messages_with_details(self, since_date: datetime, bounce_types: List[str] = None) -> List:
        """
        Find failed messages with bounce details.
        
        Args:
            since_date: Start date for filtering
            bounce_types: Optional list of bounce types to filter by
            
        Returns:
            List of failed Activity objects
        """
        query = self.session.query(self.model_class).filter(
            self.model_class.activity_type == 'message',
            self.model_class.status.in_(['failed', 'undelivered', 'rejected', 'blocked']),
            self.model_class.created_at >= since_date
        )
        
        messages = query.all()
        
        if bounce_types:
            # Filter by bounce types in metadata
            filtered = []
            for msg in messages:
                if msg.activity_metadata and msg.activity_metadata.get('bounce_type') in bounce_types:
                    filtered.append(msg)
            return filtered
        
        return messages
    
    def get_contact_message_summary(self, contact_id: int) -> dict:
        """
        Get comprehensive message summary for a contact.
        
        Args:
            contact_id: Contact ID to analyze
            
        Returns:
            Dictionary with message statistics and recent messages
        """
        messages = self.session.query(self.model_class).filter(
            self.model_class.contact_id == contact_id,
            self.model_class.activity_type == 'message'
        ).order_by(desc(self.model_class.created_at)).all()
        
        summary = {
            'total_messages': len(messages),
            'sent_count': sum(1 for m in messages if m.direction == 'outgoing'),
            'received_count': sum(1 for m in messages if m.direction == 'incoming'),
            'delivered_count': sum(1 for m in messages if m.status == 'delivered'),
            'bounced_count': sum(1 for m in messages if m.status in ['failed', 'undelivered', 'rejected', 'blocked']),
            'recent_messages': [
                {
                    'id': m.id,
                    'direction': m.direction,
                    'status': m.status,
                    'body': m.body[:100] if m.body else None,
                    'created_at': m.created_at.isoformat() if m.created_at else None
                }
                for m in messages[:10]
            ]
        }
        
        return summary
    
    def bulk_update_activities_status(self, activity_ids: List[int], status: str, metadata: dict = None) -> int:
        """
        Bulk update activity statuses.
        
        Args:
            activity_ids: List of activity IDs to update
            status: New status to set
            metadata: Optional metadata to set
            
        Returns:
            Number of activities updated
        """
        if not activity_ids:
            return 0
        
        # Update each activity individually to properly handle metadata merging
        count = 0
        for activity_id in activity_ids:
            activity = self.get_by_id(activity_id)
            if activity:
                activity.status = status
                activity.updated_at = utc_now()
                
                if metadata:
                    if activity.activity_metadata:
                        activity.activity_metadata.update(metadata)
                    else:
                        activity.activity_metadata = metadata
                
                count += 1
        
        self.session.flush()
        return count
    
    def find_latest_by_type(self, activity_type: str) -> Optional:
        """
        Find the latest activity of a specific type.
        
        Args:
            activity_type: Type of activity (sms, call, voicemail, etc.)
            
        Returns:
            Latest Activity object of the specified type or None
        """
        return self.session.query(self.model_class)\
            .filter_by(activity_type=activity_type)\
            .order_by(desc(self.model_class.created_at))\
            .first()
    
    def find_recent_by_type_with_contact(self, activity_type: str, limit: int = 10) -> List:
        """
        Find recent activities of a specific type with contact information.
        
        Args:
            activity_type: Type of activity to filter by
            limit: Maximum number of results to return (default: 10)
            
        Returns:
            List of Activity objects with contact relationships loaded
        """
        return self.session.query(self.model_class)\
            .filter_by(activity_type=activity_type)\
            .order_by(desc(self.model_class.created_at))\
            .limit(limit)\
            .all()