"""
ActivityRepository - Data access layer for Activity model
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy import desc, func
from repositories.base_repository import BaseRepository, PaginatedResult


class ActivityRepository(BaseRepository):
    """Repository for Activity data access"""
    
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
            .filter_by(type=activity_type)\
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
            .filter_by(type=activity_type)\
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
        activity = self.session.query(self.model_class).get(activity_id)
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
        activity = self.session.query(self.model_class).get(activity_id)
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
            day = datetime.utcnow().date() - timedelta(days=days-1-i)
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
        from datetime import datetime
        
        today = datetime.utcnow().date()
        return self.session.query(self.model_class).filter(
            self.model_class.activity_type == 'message',
            self.model_class.direction == 'outgoing',
            func.date(self.model_class.created_at) == today
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
        
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        return self.session.query(self.model_class.contact_id).filter(
            self.model_class.created_at >= cutoff_date,
            self.model_class.contact_id.isnot(None)
        ).distinct().count()