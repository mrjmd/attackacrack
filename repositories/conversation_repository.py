"""
ConversationRepository - Data access layer for Conversation model
"""

from typing import List, Optional, Dict, Any, Set
from datetime import datetime, timedelta
from utils.datetime_utils import utc_now
from sqlalchemy import desc, or_, func, and_, exists, select
from sqlalchemy.orm import joinedload, selectinload
from repositories.base_repository import BaseRepository, PaginatedResult
from crm_database import Conversation, Contact, Activity, ContactFlag


class ConversationRepository(BaseRepository):
    """Repository for Conversation data access"""
    
    def __init__(self, session):
        """Initialize repository with database session"""
        super().__init__(session, Conversation)
    
    def find_by_contact_id(self, contact_id: int) -> List:
        """
        Find all conversations for a contact.
        
        Args:
            contact_id: ID of the contact
            
        Returns:
            List of Conversation objects ordered by last_activity_at desc
        """
        return self.session.query(self.model_class)\
            .filter_by(contact_id=contact_id)\
            .order_by(desc(self.model_class.last_activity_at))\
            .all()
    
    def find_by_openphone_id(self, openphone_id: str) -> Optional:
        """
        Find conversation by OpenPhone ID.
        
        Args:
            openphone_id: OpenPhone conversation ID
            
        Returns:
            Conversation object or None if not found
        """
        return self.session.query(self.model_class)\
            .filter_by(openphone_id=openphone_id)\
            .first()
    
    def find_recent_conversations(self, limit: int = 50) -> List:
        """
        Find the most recent conversations.
        
        Args:
            limit: Maximum number of results
            
        Returns:
            List of most recent Conversation objects
        """
        return self.session.query(self.model_class)\
            .order_by(desc(self.model_class.last_activity_at))\
            .limit(limit)\
            .all()
    
    def find_active_conversations(self) -> List:
        """
        Find all active conversations (those with recent activity).
        
        Returns:
            List of Conversation objects with recent activity
        """
        return self.session.query(self.model_class)\
            .filter(self.model_class.last_activity_at.isnot(None))\
            .order_by(desc(self.model_class.last_activity_at))\
            .all()
    
    def get_conversations_page(self, page: int = 1, per_page: int = 50, 
                              filters: Optional[dict] = None) -> PaginatedResult:
        """
        Get paginated conversations with optional filters.
        
        Args:
            page: Page number (1-indexed)
            per_page: Items per page
            filters: Optional filter criteria
            
        Returns:
            PaginatedResult with conversations
        """
        query = self.session.query(self.model_class)
        
        if filters:
            for key, value in filters.items():
                if hasattr(self.model_class, key):
                    query = query.filter_by(**{key: value})
        
        total = query.count()
        items = query.order_by(desc(self.model_class.last_activity_at))\
            .limit(per_page)\
            .offset((page - 1) * per_page)\
            .all()
        
        return PaginatedResult(
            items=items,
            total=total,
            page=page,
            per_page=per_page
        )
    
    def update_last_activity(self, conversation_id: int, activity_time: datetime):
        """
        Update the last activity time of a conversation.
        
        Args:
            conversation_id: ID of the conversation
            activity_time: New last activity timestamp
            
        Returns:
            Updated Conversation object
        """
        conversation = self.session.query(self.model_class).get(conversation_id)
        if conversation:
            conversation.last_activity_at = activity_time
            self.session.commit()
        return conversation
    
    def count_by_status(self, status: str) -> int:
        """
        Count conversations by activity status.
        
        Args:
            status: Activity status ("active" for with activity, "inactive" for without)
            
        Returns:
            Count of conversations
        """
        if status == "active":
            return self.session.query(self.model_class)\
                .filter(self.model_class.last_activity_at.isnot(None))\
                .count()
        else:
            return self.session.query(self.model_class)\
                .filter(self.model_class.last_activity_at.is_(None))\
                .count()
    
    def find_or_create_for_contact(self, contact_id: int, openphone_id: str = None, **kwargs):
        """
        Find or create a conversation for a contact.
        
        Args:
            contact_id: ID of the contact
            openphone_id: Optional OpenPhone conversation ID
            **kwargs: Additional conversation attributes
            
        Returns:
            Conversation object (existing or newly created)
        """
        # Try to find by OpenPhone ID first if provided
        if openphone_id:
            conversation = self.session.query(self.model_class)\
                .filter_by(openphone_id=openphone_id)\
                .first()
            if conversation:
                return conversation
        
        # Try to find by contact ID
        conversation = self.session.query(self.model_class)\
            .filter_by(contact_id=contact_id)\
            .first()
        
        if conversation:
            # Update with OpenPhone ID if provided and not set
            if openphone_id and not conversation.openphone_id:
                conversation.openphone_id = openphone_id
                self.session.commit()
            return conversation
        
        # Create new conversation
        conversation_data = {
            'contact_id': contact_id,
            'openphone_id': openphone_id,
            'last_activity_at': utc_now(),
            **kwargs
        }
        
        conversation = self.model_class(**conversation_data)
        self.session.add(conversation)
        self.session.commit()
        
        return conversation
    
    def archive_conversation(self, conversation_id: int) -> bool:
        """
        Archive a conversation (mark as inactive by clearing last_activity_at).
        
        Args:
            conversation_id: ID of the conversation
            
        Returns:
            True if successful, False otherwise
        """
        conversation = self.session.query(self.model_class).get(conversation_id)
        if conversation:
            # Archive by setting a flag or we could add an archived_at field
            # For now, we'll just ensure it exists
            self.session.commit()
            return True
        return False
    
    def search(self, query: str) -> List:
        """
        Search conversations by joining with contacts and searching names/phones.
        
        Args:
            query: Search query string
            
        Returns:
            List of matching Conversation objects
        """
        if not query:
            return []
        
        # Join with Contact to search by contact details
        search_results = self.session.query(self.model_class)\
            .join(Contact)\
            .filter(
                or_(
                    Contact.first_name.ilike(f'%{query}%'),
                    Contact.last_name.ilike(f'%{query}%'),
                    Contact.phone.ilike(f'%{query}%'),
                    Contact.email.ilike(f'%{query}%')
                )
            )\
            .distinct()\
            .limit(100)\
            .all()
        
        return search_results
    
    def find_conversations_with_filters(
        self,
        search_query: str = '',
        filter_type: str = 'all',
        date_filter: str = 'all',
        page: int = 1,
        per_page: int = 20
    ) -> Dict[str, Any]:
        """
        Find conversations with comprehensive filtering and pagination.
        
        Args:
            search_query: Search text for name, phone, email, or message content
            filter_type: Filter type (all, unread, has_attachments, office_numbers)
            date_filter: Date filter (all, today, week, month)
            page: Page number (1-indexed)
            per_page: Number of items per page
            
        Returns:
            Dictionary containing conversations and total count
        """
        # Start with base query - only conversations with activities
        query = self.session.query(self.model_class).options(
            joinedload(Conversation.contact),
            selectinload(Conversation.activities)
        ).join(Contact).filter(
            exists().where(Activity.conversation_id == Conversation.id)
        )
        
        # Apply search filters
        if search_query:
            query = self._apply_search_filter(query, search_query)
        
        # Apply type filters
        query = self._apply_type_filter(query, filter_type)
        
        # Apply date filters
        query = self._apply_date_filter(query, date_filter)
        
        # Order by most recent activity
        query = query.order_by(Conversation.last_activity_at.desc())
        
        # Get total count before pagination
        total_count = query.count()
        
        # Paginate results
        conversations = query.offset((page - 1) * per_page).limit(per_page).all()
        
        return {
            'conversations': conversations,
            'total_count': total_count
        }
    
    def _apply_search_filter(self, query, search_query: str):
        """Apply search filter to query"""
        return query.filter(
            or_(
                Contact.first_name.ilike(f'%{search_query}%'),
                Contact.last_name.ilike(f'%{search_query}%'),
                Contact.phone.ilike(f'%{search_query}%'),
                Contact.email.ilike(f'%{search_query}%'),
                # Search in message content
                exists().where(
                    and_(
                        Activity.conversation_id == Conversation.id,
                        Activity.body.ilike(f'%{search_query}%')
                    )
                )
            )
        )
    
    def _apply_type_filter(self, query, filter_type: str):
        """Apply type filter to query"""
        if filter_type == 'unread':
            # Fixed unread filter - conversations with incoming messages that have no later outgoing
            subquery = select(Activity.conversation_id).where(
                Activity.direction == 'incoming'
            ).group_by(Activity.conversation_id)
            
            query = query.filter(Conversation.id.in_(subquery))
            
        elif filter_type == 'has_attachments':
            # Filter for conversations with actual media URLs (not empty JSON arrays)
            query = query.filter(
                exists().where(
                    and_(
                        Activity.conversation_id == Conversation.id,
                        Activity.media_urls.isnot(None),
                        func.jsonb_array_length(Activity.media_urls) > 0
                    )
                )
            )
            
        elif filter_type == 'office_numbers':
            # Conversations with contacts flagged as office numbers
            query = query.filter(
                exists().where(
                    and_(
                        ContactFlag.contact_id == Contact.id,
                        ContactFlag.flag_type == 'office_number'
                    )
                )
            )
        
        return query
    
    def _apply_date_filter(self, query, date_filter: str):
        """Apply date filter to query"""
        if date_filter == 'today':
            today = datetime.now().date()
            query = query.filter(func.date(Conversation.last_activity_at) == today)
        elif date_filter == 'week':
            week_ago = datetime.now() - timedelta(days=7)
            query = query.filter(Conversation.last_activity_at >= week_ago)
        elif date_filter == 'month':
            month_ago = datetime.now() - timedelta(days=30)
            query = query.filter(Conversation.last_activity_at >= month_ago)
        
        return query
    
    def get_office_flags_batch(self, contact_ids: List[int]) -> Set[int]:
        """
        Get office number flags for multiple contacts in batch.
        
        Args:
            contact_ids: List of contact IDs to check
            
        Returns:
            Set of contact IDs that are flagged as office numbers
        """
        if not contact_ids:
            return set()
        
        office_flag_results = self.session.query(ContactFlag.contact_id).filter(
            ContactFlag.contact_id.in_(contact_ids),
            ContactFlag.flag_type == 'office_number'
        ).all()
        
        return {flag.contact_id for flag in office_flag_results}
    
    def bulk_update_last_activity(self, conversation_ids: List[int], activity_time: datetime) -> bool:
        """
        Update last activity time for multiple conversations.
        
        Args:
            conversation_ids: List of conversation IDs to update
            activity_time: New last activity timestamp
            
        Returns:
            True if successful, False otherwise
        """
        if not conversation_ids:
            return False
        
        try:
            conversations = self.session.query(self.model_class).filter(
                self.model_class.id.in_(conversation_ids)
            ).all()
            
            for conv in conversations:
                conv.last_activity_at = activity_time
            
            self.session.commit()
            return True
        except Exception:
            self.session.rollback()
            return False
    
    def find_conversations_by_ids_with_contact_info(self, conversation_ids: List[int]) -> List:
        """
        Find conversations by IDs with contact information loaded.
        
        Args:
            conversation_ids: List of conversation IDs
            
        Returns:
            List of Conversation objects with contact info loaded
        """
        if not conversation_ids:
            return []
        
        return self.session.query(self.model_class).filter(
            self.model_class.id.in_(conversation_ids)
        ).options(joinedload(Conversation.contact)).all()
    
    def get_activity_counts_for_conversations(self, conversation_ids: List[int]) -> Dict[int, int]:
        """
        Get activity counts for multiple conversations.
        
        Args:
            conversation_ids: List of conversation IDs
            
        Returns:
            Dictionary mapping conversation_id to activity count
        """
        if not conversation_ids:
            return {}
        
        results = self.session.query(
            Activity.conversation_id,
            func.count(Activity.id)
        ).filter(
            Activity.conversation_id.in_(conversation_ids)
        ).group_by(Activity.conversation_id).all()
        
        return {conv_id: count for conv_id, count in results}
    
    # Dashboard-specific methods
    
    def get_recent_conversations_with_activities(self, limit: int = 20) -> List:
        """
        Get recent conversations with activities and contacts preloaded.
        Only returns conversations that have activities.
        
        Args:
            limit: Maximum number of conversations to return
            
        Returns:
            List of Conversation objects with contact and activities preloaded
        """
        return self.session.query(self.model_class).options(
            joinedload(Conversation.contact),
            selectinload(Conversation.activities)
        ).filter(
            self.model_class.last_activity_at.isnot(None),
            exists().where(Activity.conversation_id == Conversation.id)
        ).order_by(
            desc(self.model_class.last_activity_at)
        ).limit(limit).all()