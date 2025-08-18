"""
Refactored MessageService following Phase 2 patterns:
- Dependency injection instead of direct instantiation
- Repository pattern for data access  
- Result pattern for consistent error handling
- No direct database queries
"""

from typing import List, Optional, Dict, Any
from datetime import datetime

from services.common.result import Result
from crm_database import Conversation, Activity


class MessageServiceRefactored:
    """
    Refactored message service that uses repositories and dependency injection.
    
    This service handles conversation and activity management without direct
    database access, following clean architecture principles.
    """
    
    def __init__(self, 
                 conversation_repository,
                 activity_repository,
                 contact_service,
                 property_service,
                 openphone_service,
                 ai_service):
        """
        Initialize service with injected dependencies.
        
        Args:
            conversation_repository: Repository for conversation data access
            activity_repository: Repository for activity data access
            contact_service: Service for contact operations
            property_service: Service for property operations
            openphone_service: Service for OpenPhone API operations
            ai_service: Service for AI operations
        """
        self.conversation_repository = conversation_repository
        self.activity_repository = activity_repository
        self.contact_service = contact_service
        self.property_service = property_service
        self.openphone_service = openphone_service
        self.ai_service = ai_service
    
    def get_or_create_conversation(self, 
                                   contact_id: int, 
                                   openphone_convo_id: Optional[str] = None, 
                                   participants: Optional[List[str]] = None) -> Result[Conversation]:
        """
        Get existing conversation or create a new one.
        
        Args:
            contact_id: ID of the contact
            openphone_convo_id: Optional OpenPhone conversation ID
            participants: Optional list of participant phone numbers
            
        Returns:
            Result containing the conversation or error details
        """
        try:
            # Validate required parameters
            if not contact_id:
                return Result.failure(
                    "Contact ID is required",
                    code="VALIDATION_ERROR"
                )
            
            # Try to find by OpenPhone ID first if provided
            if openphone_convo_id:
                conversation = self.conversation_repository.find_by_openphone_id(openphone_convo_id)
                if conversation:
                    return Result.success(conversation)
            
            # Try to find by contact ID
            conversations = self.conversation_repository.find_by_contact_id(contact_id)
            if conversations:
                conversation = conversations[0]  # Get the first/primary conversation
                
                # Update with OpenPhone ID if provided and not set
                if openphone_convo_id and not conversation.openphone_id:
                    conversation.openphone_id = openphone_convo_id
                    updated_conversation = self.conversation_repository.update(conversation)
                    return Result.success(updated_conversation)
                
                return Result.success(conversation)
            
            # Create new conversation
            conversation_data = {
                'contact_id': contact_id,
                'openphone_id': openphone_convo_id,
                'participants': ','.join(participants) if participants else '',
                'last_activity_at': datetime.utcnow()
            }
            
            new_conversation = self.conversation_repository.create(conversation_data)
            return Result.success(new_conversation)
            
        except Exception as e:
            return Result.failure(
                f"Failed to get or create conversation: {str(e)}",
                code="REPOSITORY_ERROR"
            )
    
    def get_activities_for_contact(self, contact_id: int) -> Result[List[Activity]]:
        """
        Get all activities for a contact, sorted chronologically.
        
        Args:
            contact_id: ID of the contact
            
        Returns:
            Result containing list of activities or error details
        """
        try:
            # Validate required parameters
            if not contact_id:
                return Result.failure(
                    "Contact ID is required",
                    code="VALIDATION_ERROR"
                )
            
            # Get activities from repository
            activities = self.activity_repository.find_by_contact_id(contact_id)
            
            return Result.success(activities)
            
        except Exception as e:
            return Result.failure(
                f"Failed to get activities for contact: {str(e)}",
                code="REPOSITORY_ERROR"
            )
    
    def get_latest_conversations_from_db(self, limit: int = 10) -> Result[List[Conversation]]:
        """
        Get the most recent conversations from the database.
        
        Efficiently loads related contact and activities data to prevent N+1 queries.
        
        Args:
            limit: Maximum number of conversations to return (default: 10)
            
        Returns:
            Result containing list of conversations with metadata about eager loading
        """
        try:
            # Validate limit parameter
            if limit <= 0:
                return Result.failure(
                    "Limit must be positive",
                    code="VALIDATION_ERROR"
                )
            
            if limit > 1000:  # Reasonable upper bound
                return Result.failure(
                    "Limit cannot exceed 1000",
                    code="VALIDATION_ERROR"
                )
            
            # Get conversations from repository
            conversations = self.conversation_repository.find_recent_conversations(limit=limit)
            
            # Include metadata about optimization
            metadata = {
                "eager_loaded": True,
                "relations": ["contact", "activities"],
                "limit_applied": limit,
                "total_returned": len(conversations)
            }
            
            return Result.success(conversations, metadata=metadata)
            
        except Exception as e:
            return Result.failure(
                f"Failed to get latest conversations: {str(e)}",
                code="REPOSITORY_ERROR"
            )

# Alias for compatibility
MessageService = MessageServiceRefactored