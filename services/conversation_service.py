"""
ConversationService - Handles conversation listing, filtering, and management
"""
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from sqlalchemy import or_, func, and_, exists, select
from sqlalchemy.orm import joinedload, selectinload
from extensions import db
from crm_database import Conversation, Contact, Activity, ContactFlag, Campaign


class ConversationService:
    """Service for managing conversations and message threads"""
    
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
        # Start with base query - only conversations with activities
        query = db.session.query(Conversation).options(
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
            # This avoids the aggregate function error
            subquery = select(Activity.conversation_id).where(
                Activity.direction == 'incoming'
            ).group_by(Activity.conversation_id).subquery()
            
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
            office_contact_ids = db.session.query(ContactFlag.contact_id).filter(
                ContactFlag.flag_type == 'office_number'
            ).subquery()
            query = query.filter(Contact.id.in_(office_contact_ids))
        
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
    
    def _enhance_conversations(self, conversations: List[Conversation]) -> List[Dict[str, Any]]:
        """
        Enhance conversations with additional metadata
        
        Args:
            conversations: List of Conversation objects
            
        Returns:
            List of enhanced conversation dictionaries
        """
        # Get all contact IDs for batch flag lookup
        contact_ids = [conv.contact_id for conv in conversations]
        
        # Batch query for office flags
        office_flags = set()
        if contact_ids:
            office_flag_results = db.session.query(ContactFlag.contact_id).filter(
                ContactFlag.contact_id.in_(contact_ids),
                ContactFlag.flag_type == 'office_number'
            ).all()
            office_flags = {flag.contact_id for flag in office_flag_results}
        
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
    
    def get_available_campaigns(self) -> List[Campaign]:
        """Get campaigns available for bulk actions"""
        return Campaign.query.filter(
            Campaign.status.in_(['draft', 'running'])
        ).all()
    
    def mark_conversations_read(self, conversation_ids: List[int]) -> Tuple[bool, str]:
        """Mark conversations as read by updating last activity"""
        if not conversation_ids:
            return False, "No conversations selected"
        
        try:
            for conv_id in conversation_ids:
                conv = Conversation.query.get(conv_id)
                if conv:
                    conv.last_activity_at = datetime.utcnow()
            db.session.commit()
            return True, f'Marked {len(conversation_ids)} conversations as read'
        except Exception as e:
            db.session.rollback()
            return False, f'Error marking conversations: {str(e)}'
    
    def get_contact_ids_from_conversations(self, conversation_ids: List[int]) -> List[int]:
        """Get unique contact IDs from conversation IDs"""
        conversations = Conversation.query.filter(
            Conversation.id.in_(conversation_ids)
        ).all()
        return list(set(conv.contact_id for conv in conversations if conv.contact_id))
    
    def export_conversations_with_contacts(self, conversation_ids: List[int]) -> str:
        """Export conversations with contact info to CSV"""
        import csv
        import io
        
        conversations = Conversation.query.filter(
            Conversation.id.in_(conversation_ids)
        ).options(joinedload(Conversation.contact)).all()
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write headers
        writer.writerow(['Contact Name', 'Phone', 'Email', 'Last Activity', 'Message Count'])
        
        # Write data
        for conv in conversations:
            message_count = Activity.query.filter_by(conversation_id=conv.id).count()
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
            db.session.rollback()
            return False, f"Error performing bulk action: {str(e)}"