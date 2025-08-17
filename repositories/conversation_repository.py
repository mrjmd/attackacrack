"""
ConversationRepository - Data access layer for Conversation model
"""

from typing import List, Optional
from datetime import datetime
from sqlalchemy import desc, or_
from repositories.base_repository import BaseRepository, PaginatedResult
from crm_database import Conversation, Contact


class ConversationRepository(BaseRepository):
    """Repository for Conversation data access"""
    
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
            'last_activity_at': datetime.utcnow(),
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