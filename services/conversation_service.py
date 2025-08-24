"""
ConversationService - Handles conversation listing, filtering, and management
"""
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from utils.datetime_utils import utc_now
# Model imports removed - using repositories only
from repositories.conversation_repository import ConversationRepository
from repositories.campaign_repository import CampaignRepository


class ConversationService:
    """Service for managing conversations and message threads"""
    
    def __init__(self, conversation_repository: ConversationRepository, campaign_repository: CampaignRepository):
        """
        Initialize ConversationService with repository dependencies.
        
        Args:
            conversation_repository: Repository for conversation data access
            campaign_repository: Repository for campaign data access
        """
        self.conversation_repository = conversation_repository
        self.campaign_repository = campaign_repository
    
    def get_conversations_page(
        self,
        search_query: str = '',
        filter_type: str = 'all',
        date_filter: str = 'all',
        page: int = 1,
        per_page: int = 20
    ) -> Dict[str, Any]:
        """
        Get a paginated page of conversations with filters
        
        Args:
            search_query: Search text for name, phone, email, or message content
            filter_type: Filter type (all, unread, has_attachments, office_numbers)
            date_filter: Date filter (all, today, week, month)
            page: Page number (1-indexed)
            per_page: Number of items per page
            
        Returns:
            Dictionary containing conversations and pagination info
        """
        # Use repository to get filtered conversations
        repo_result = self.conversation_repository.find_conversations_with_filters(
            search_query=search_query,
            filter_type=filter_type,
            date_filter=date_filter,
            page=page,
            per_page=per_page
        )
        
        conversations = repo_result['conversations']
        total_count = repo_result['total_count']
        
        # Enhance conversations with metadata
        enhanced_conversations = self._enhance_conversations(conversations)
        
        # Calculate pagination info
        total_pages = (total_count + per_page - 1) // per_page
        
        return {
            'conversations': enhanced_conversations,
            'total_count': total_count,
            'page': page,
            'per_page': per_page,
            'total_pages': total_pages,
            'has_prev': page > 1,
            'has_next': page < total_pages
        }
    
    # Removed _apply_search_filter, _apply_type_filter, _apply_date_filter - moved to repository
    
    def _enhance_conversations(self, conversations: List[Dict]) -> List[Dict[str, Any]]:
        """
        Enhance conversations with additional metadata
        
        Args:
            conversations: List of Conversation objects
            
        Returns:
            List of enhanced conversation dictionaries
        """
        # Get all contact IDs for batch flag lookup
        contact_ids = [conv.contact_id for conv in conversations]
        
        # Use repository for batch office flag lookup
        office_flags = self.conversation_repository.get_office_flags_batch(contact_ids)
        
        # Enhance each conversation
        enhanced = []
        for conv in conversations:
            # Process pre-loaded activities
            activities = conv.activities  # Already loaded via selectinload
            
            # Get latest activity
            latest_activity = max(activities, key=lambda a: a.created_at) if activities else None
            
            # Check for unread status - simplified logic
            incoming_activities = [a for a in activities if a.direction == 'incoming']
            outgoing_activities = [a for a in activities if a.direction == 'outgoing']
            
            is_unread = False
            if incoming_activities and outgoing_activities:
                latest_incoming = max(incoming_activities, key=lambda a: a.created_at)
                latest_outgoing = max(outgoing_activities, key=lambda a: a.created_at)
                is_unread = latest_incoming.created_at > latest_outgoing.created_at
            elif incoming_activities and not outgoing_activities:
                is_unread = True
            
            # Check for real attachments (not empty arrays)
            has_attachments = False
            for activity in activities:
                if activity.media_urls:
                    try:
                        # Check if it's a non-empty array
                        import json
                        if isinstance(activity.media_urls, str):
                            urls = json.loads(activity.media_urls)
                        else:
                            urls = activity.media_urls
                        if urls and len(urls) > 0:
                            has_attachments = True
                            break
                    except:
                        pass
            
            # Check for AI content
            has_ai_summary = any(a.ai_summary for a in activities)
            
            # Check if office number
            is_office_number = conv.contact_id in office_flags
            
            # Message count
            message_count = len(activities)
            
            enhanced.append({
                'conversation': conv,
                'latest_activity': latest_activity,
                'is_unread': is_unread,
                'has_attachments': has_attachments,
                'has_ai_summary': has_ai_summary,
                'is_office_number': is_office_number,
                'message_count': message_count
            })
        
        return enhanced
    
    def get_available_campaigns(self):
        """Get campaigns available for bulk actions"""
        return self.campaign_repository.find_by_statuses(['draft', 'running'])
    
    def mark_conversations_read(self, conversation_ids: List[int]) -> Tuple[bool, str]:
        """Mark conversations as read by updating last activity"""
        if not conversation_ids:
            return False, "No conversations selected"
        
        success = self.conversation_repository.bulk_update_last_activity(
            conversation_ids, utc_now()
        )
        
        if success:
            return True, f'Marked {len(conversation_ids)} conversations as read'
        else:
            return False, 'Error marking conversations'
    
    def get_contact_ids_from_conversations(self, conversation_ids: List[int]) -> List[int]:
        """Get unique contact IDs from conversation IDs"""
        conversations = self.conversation_repository.find_conversations_by_ids_with_contact_info(conversation_ids)
        return list(set(conv.contact_id for conv in conversations if conv.contact_id))
    
    def export_conversations_with_contacts(self, conversation_ids: List[int]) -> str:
        """Export conversations with contact info to CSV"""
        import csv
        import io
        
        # Use repository methods for data access
        conversations = self.conversation_repository.find_conversations_by_ids_with_contact_info(conversation_ids)
        activity_counts = self.conversation_repository.get_activity_counts_for_conversations(conversation_ids)
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write headers
        writer.writerow(['Contact Name', 'Phone', 'Email', 'Last Activity', 'Message Count'])
        
        # Write data
        for conv in conversations:
            message_count = activity_counts.get(conv.id, 0)
            writer.writerow([
                f"{conv.contact.first_name} {conv.contact.last_name}" if conv.contact else "",
                conv.contact.phone if conv.contact else "",
                conv.contact.email if conv.contact else "",
                conv.last_activity_at.strftime('%Y-%m-%d %H:%M:%S') if conv.last_activity_at else '',
                message_count
            ])
        
        output.seek(0)
        return output.getvalue()
    
    def bulk_action(self, action: str, conversation_ids: List[int], **kwargs) -> Tuple[bool, str]:
        """
        Perform bulk action on conversations
        
        Args:
            action: Action to perform (mark_read, add_to_campaign, flag_office, export)
            conversation_ids: List of conversation IDs
            **kwargs: Additional parameters for specific actions
            
        Returns:
            Tuple of (success, message)
        """
        if not conversation_ids:
            return False, "No conversations selected"
        
        try:
            if action == 'mark_read':
                return self.mark_conversations_read(conversation_ids)
            elif action == 'export':
                csv_data = self.export_conversations_with_contacts(conversation_ids)
                return True, csv_data
            else:
                return False, f"Unknown action: {action}"
                
        except Exception as e:
            return False, f"Error performing bulk action: {str(e)}"