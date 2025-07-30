"""
OpenPhone Webhook Service

Comprehensive service for handling all OpenPhone webhook event types:
- Messages (incoming/outgoing)
- Calls (incoming/outgoing)
- Call summaries
- Call transcripts

Based on: https://support.openphone.com/hc/en-us/articles/4690754298903-How-to-use-webhooks
"""

import logging
from datetime import datetime
from typing import Dict, Any, Optional

from extensions import db
from crm_database import Activity, Contact, Conversation, WebhookEvent
from services.contact_service import ContactService

logger = logging.getLogger(__name__)

class OpenPhoneWebhookService:
    """Handles all OpenPhone webhook events"""
    
    def __init__(self):
        self.contact_service = ContactService()
        
    def process_webhook(self, webhook_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main webhook processor that routes to specific handlers
        """
        try:
            # Log the webhook event
            self._log_webhook_event(webhook_data)
            
            # Get event type from top level
            event_type = webhook_data.get('type', '')
            event_data = webhook_data
            
            # Route to specific handlers
            if event_type == 'token.validated':
                return self._handle_token_validation(event_data)
            
            elif event_type.startswith('message.'):
                return self._handle_message_webhook(event_data)
                
            elif event_type == 'call.recording.completed':
                return self._handle_call_recording_webhook(event_data)
                
            elif event_type == 'call.summary.completed':
                return self._handle_call_summary_webhook(event_data)
                
            elif event_type == 'call.transcript.completed':
                return self._handle_call_transcript_webhook(event_data)
                
            elif event_type.startswith('call.'):
                return self._handle_call_webhook(event_data)
                
            else:
                logger.warning(f"Unknown webhook type: {event_type}")
                return {'status': 'ignored', 'reason': f'Unknown event type: {event_type}'}
                
        except Exception as e:
            logger.error(f"Error processing webhook: {e}", exc_info=True)
            return {'status': 'error', 'message': str(e)}
    
    def _log_webhook_event(self, webhook_data: Dict[str, Any]):
        """Log webhook event to database"""
        try:
            webhook_event = WebhookEvent(
                event_type=webhook_data.get('type', 'unknown'),
                payload=webhook_data,
                processed=False,
                created_at=datetime.utcnow()
            )
            db.session.add(webhook_event)
            db.session.commit()
        except Exception as e:
            logger.error(f"Failed to log webhook event: {e}")
    
    def _handle_token_validation(self, webhook_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle token validation webhook"""
        logger.info("Token validation webhook received")
        return {'status': 'success', 'message': 'Token validated'}
    
    def _handle_message_webhook(self, webhook_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle message webhooks:
        - message.received (incoming message with media support!)
        - message.delivered (delivery confirmation)
        """
        event_type = webhook_data.get('type')
        message_data = webhook_data.get('data', {}).get('object', {})
        
        if not message_data:
            return {'status': 'error', 'message': 'No message data provided'}
        
        logger.info(f"Processing {event_type} webhook")
        
        # Extract message details
        openphone_id = message_data.get('id')
        direction = message_data.get('direction', 'unknown')
        from_number = message_data.get('from')
        to_number = message_data.get('to')
        body = message_data.get('text', message_data.get('body', ''))
        conversation_id = message_data.get('conversationId')
        status = message_data.get('status', 'unknown')
        created_at = self._parse_timestamp(message_data.get('createdAt'))
        
        # EXCITING: Extract media URLs!
        media_data = message_data.get('media', [])
        # Store media as list of dicts with url and type
        media_urls = [{'url': item.get('url'), 'type': item.get('type')} 
                     for item in media_data 
                     if isinstance(item, dict) and 'url' in item]
        
        # Determine contact based on direction
        if direction == 'incoming':
            contact_phone = from_number
            db_direction = 'incoming'
        else:
            contact_phone = to_number  
            db_direction = 'outgoing'
        
        # Get or create contact
        contact = self._get_or_create_contact(contact_phone)
        
        # Get or create conversation
        conversation = self._get_or_create_conversation(contact.id, conversation_id)
        
        # Check if activity already exists
        existing_activity = Activity.query.filter_by(openphone_id=openphone_id).first()
        if existing_activity:
            logger.info(f"Activity {openphone_id} already exists, updating status")
            existing_activity.status = status
            db.session.commit()
            return {'status': 'updated', 'activity_id': existing_activity.id}
        
        # Create new activity
        new_activity = Activity(
            conversation_id=conversation.id,
            contact_id=contact.id,
            openphone_id=openphone_id,
            activity_type='message',
            body=body,
            direction=db_direction,
            status=status,
            media_urls=media_urls,  # Store media URLs!
            created_at=created_at or datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        db.session.add(new_activity)
        
        # Update conversation last activity
        conversation.last_activity_at = created_at or datetime.utcnow()
        
        db.session.commit()
        
        # Log if media was included
        if media_urls:
            logger.info(f"Message {openphone_id} includes {len(media_urls)} media attachments")
        
        return {'status': 'created', 'activity_id': new_activity.id, 'media_count': len(media_urls)}
    
    def _handle_call_webhook(self, webhook_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle call webhooks:
        - call.completed (all call completion states)
        """
        event_type = webhook_data.get('type')
        call_data = webhook_data.get('data', {}).get('object', {})
        
        if not call_data:
            return {'status': 'error', 'message': 'No call data provided'}
        
        logger.info(f"Processing {event_type} webhook")
        
        # Extract call details
        openphone_id = call_data.get('id')
        direction = call_data.get('direction', 'unknown')
        status = call_data.get('status', 'unknown')
        duration = call_data.get('duration', call_data.get('durationSeconds', 0))
        
        # Get participants
        participants = call_data.get('participants', [])
        if not participants:
            return {'status': 'error', 'message': 'No participants in call data'}
        
        # Determine contact phone (participant who is not our number)
        our_number = self._get_our_phone_number()
        contact_phone = None
        for participant in participants:
            if participant != our_number:
                contact_phone = participant
                break
        
        if not contact_phone:
            logger.warning(f"Could not determine contact phone from participants: {participants}")
            return {'status': 'error', 'message': 'Could not determine contact phone'}
        
        # Get or create contact
        contact = self._get_or_create_contact(contact_phone)
        
        # Get or create conversation
        conversation = self._get_or_create_conversation(contact.id)
        
        # Check if call activity already exists
        existing_activity = Activity.query.filter_by(openphone_id=openphone_id).first()
        if existing_activity:
            logger.info(f"Call {openphone_id} already exists, updating")
            existing_activity.status = status
            existing_activity.duration_seconds = duration
            db.session.commit()
            return {'status': 'updated', 'activity_id': existing_activity.id}
        
        # Create new call activity
        new_activity = Activity(
            conversation_id=conversation.id,
            contact_id=contact.id,
            openphone_id=openphone_id,
            activity_type='call',
            direction=direction,
            status=status,
            duration_seconds=duration,
            answered_at=self._parse_timestamp(call_data.get('answeredAt')),
            completed_at=self._parse_timestamp(call_data.get('completedAt')),
            created_at=self._parse_timestamp(call_data.get('createdAt')) or datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        db.session.add(new_activity)
        
        # Update conversation
        conversation.last_activity_at = new_activity.created_at
        
        db.session.commit()
        
        # Try to fetch call recording if call is completed
        if status == 'completed':
            self._fetch_call_recording_async(new_activity.id, openphone_id)
        
        return {'status': 'created', 'activity_id': new_activity.id}
    
    def _handle_call_summary_webhook(self, webhook_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle call summary webhooks (AI-generated summaries)"""
        event_type = webhook_data.get('type')
        summary_data = webhook_data.get('data', {}).get('object', {})
        
        logger.info(f"Processing {event_type} webhook")
        
        call_id = summary_data.get('callId')
        summary_text = summary_data.get('summary')
        
        if not call_id or not summary_text:
            return {'status': 'error', 'message': 'Missing call ID or summary'}
        
        # Find the call activity
        call_activity = Activity.query.filter_by(
            openphone_id=call_id,
            activity_type='call'
        ).first()
        
        if not call_activity:
            logger.warning(f"Call activity not found for call ID: {call_id}")
            return {'status': 'error', 'message': 'Call activity not found'}
        
        # Update with AI summary
        call_activity.ai_summary = summary_text
        call_activity.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        return {'status': 'updated', 'activity_id': call_activity.id}
    
    def _handle_call_transcript_webhook(self, webhook_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle call transcript webhooks (AI-generated transcripts)"""
        event_type = webhook_data.get('type')
        transcript_data = webhook_data.get('data', {}).get('object', {})
        
        logger.info(f"Processing {event_type} webhook")
        
        call_id = transcript_data.get('callId')
        transcript = transcript_data.get('transcript')
        
        if not call_id or not transcript:
            return {'status': 'error', 'message': 'Missing call ID or transcript'}
        
        # Find the call activity
        call_activity = Activity.query.filter_by(
            openphone_id=call_id,
            activity_type='call'
        ).first()
        
        if not call_activity:
            logger.warning(f"Call activity not found for call ID: {call_id}")
            return {'status': 'error', 'message': 'Call activity not found'}
        
        # Update with AI transcript
        call_activity.ai_transcript = transcript
        call_activity.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        return {'status': 'updated', 'activity_id': call_activity.id}
    
    def _handle_call_recording_webhook(self, webhook_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle call recording completed webhook"""
        event_type = webhook_data.get('type')
        recording_data = webhook_data.get('data', {}).get('object', {})
        
        logger.info(f"Processing {event_type} webhook")
        
        recording_id = recording_data.get('id')
        call_id = recording_data.get('callId')
        recording_url = recording_data.get('url')
        
        if not call_id or not recording_url:
            return {'status': 'error', 'message': 'Missing call ID or recording URL'}
        
        # Find the call activity
        call_activity = Activity.query.filter_by(
            openphone_id=call_id,
            activity_type='call'
        ).first()
        
        if not call_activity:
            logger.warning(f"Call activity not found for call ID: {call_id}")
            return {'status': 'error', 'message': 'Call activity not found'}
        
        # Update with recording URL
        call_activity.recording_url = recording_url
        call_activity.updated_at = datetime.utcnow()
        
        # Store recording metadata if available
        if recording_data.get('duration'):
            call_activity.duration_seconds = recording_data['duration']
        
        db.session.commit()
        
        logger.info(f"Call recording updated for call {call_id}")
        
        return {'status': 'updated', 'activity_id': call_activity.id, 'recording_id': recording_id}
    
    def _get_or_create_contact(self, phone_number: str) -> Contact:
        """Get or create a contact by phone number"""
        contact = self.contact_service.get_contact_by_phone(phone_number)
        if not contact:
            contact = self.contact_service.add_contact(
                first_name=phone_number,
                last_name="(from OpenPhone)",
                phone=phone_number
            )
        return contact
    
    def _get_or_create_conversation(self, contact_id: int, openphone_conversation_id: str = None) -> Conversation:
        """Get or create a conversation"""
        # Try to find by OpenPhone conversation ID first
        if openphone_conversation_id:
            conversation = Conversation.query.filter_by(
                openphone_id=openphone_conversation_id
            ).first()
            if conversation:
                return conversation
        
        # Try to find by contact ID
        conversation = Conversation.query.filter_by(contact_id=contact_id).first()
        if conversation:
            # Update with OpenPhone ID if provided
            if openphone_conversation_id and not conversation.openphone_id:
                conversation.openphone_id = openphone_conversation_id
                db.session.commit()
            return conversation
        
        # Create new conversation
        new_conversation = Conversation(
            contact_id=contact_id,
            openphone_id=openphone_conversation_id,
            last_activity_at=datetime.utcnow()
        )
        db.session.add(new_conversation)
        db.session.commit()
        
        return new_conversation
    
    def _parse_timestamp(self, timestamp_str: str) -> Optional[datetime]:
        """Parse OpenPhone timestamp format"""
        if not timestamp_str:
            return None
        
        try:
            # OpenPhone uses ISO format: "2025-07-29T14:41:30.000Z"
            return datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        except Exception as e:
            logger.error(f"Failed to parse timestamp {timestamp_str}: {e}")
            return None
    
    def _get_our_phone_number(self) -> str:
        """Get our OpenPhone number from config"""
        from flask import current_app
        return current_app.config.get('OPENPHONE_PHONE_NUMBER', '')
    
    def _fetch_call_recording_async(self, activity_id: int, call_id: str):
        """Fetch call recording asynchronously (placeholder for Celery task)"""
        # TODO: Implement as Celery task
        logger.info(f"Should fetch recording for call {call_id} (activity {activity_id})")
        pass