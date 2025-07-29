#!/usr/bin/env python3
"""
OpenPhone Webhook Sync Service
Handles real-time synchronization of OpenPhone data via webhooks
"""

import json
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Tuple
from flask import current_app

from extensions import db
from crm_database import (
    WebhookEvent, Activity, Conversation, Contact, MediaAttachment
)
from services.contact_service import ContactService
from services.ai_service import AIService

logger = logging.getLogger(__name__)

class WebhookSyncService:
    """Service for processing OpenPhone webhook events in real-time"""
    
    def __init__(self):
        self.contact_service = ContactService()
        self.ai_service = AIService()
    
    def process_webhook_event(self, webhook_payload: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Process incoming webhook event from OpenPhone
        
        Args:
            webhook_payload: Complete webhook payload from OpenPhone
            
        Returns:
            Tuple of (success: bool, message: str)
        """
        try:
            # Extract event metadata
            event_id = webhook_payload.get('id')
            event_type = webhook_payload.get('type')
            api_version = webhook_payload.get('apiVersion', 'v1')
            event_data = webhook_payload.get('data', {})
            
            if not event_id or not event_type:
                return False, "Invalid webhook payload: missing id or type"
            
            # Check if we've already processed this event
            existing_event = db.session.query(WebhookEvent).filter_by(
                event_id=event_id
            ).first()
            
            if existing_event and existing_event.processed:
                logger.info(f"Webhook event {event_id} already processed")
                return True, "Event already processed"
            
            # Store webhook event for reliability
            webhook_event = existing_event or WebhookEvent(
                event_id=event_id,
                event_type=event_type,
                api_version=api_version,
                payload=webhook_payload,
                processed=False
            )
            
            if not existing_event:
                db.session.add(webhook_event)
                db.session.flush()
            
            # Process based on event type
            success = False
            message = ""
            
            if event_type == 'message.created':
                success, message = self._process_message_created(event_data)
            elif event_type == 'call.completed':
                success, message = self._process_call_completed(event_data)
            elif event_type == 'call.recording.created':
                success, message = self._process_call_recording_created(event_data)
            elif event_type in ['contact.created', 'contact.updated']:
                success, message = self._process_contact_updated(event_data)
            else:
                logger.info(f"Unhandled webhook event type: {event_type}")
                success = True
                message = f"Event type {event_type} acknowledged but not processed"
            
            # Mark as processed if successful
            if success:
                webhook_event.processed = True
                webhook_event.processed_at = datetime.utcnow()
            else:
                webhook_event.error_message = message
            
            db.session.commit()
            
            logger.info(f"Webhook event {event_id} ({event_type}): {message}")
            return success, message
            
        except Exception as e:
            logger.error(f"Error processing webhook event: {e}")
            if 'webhook_event' in locals():
                webhook_event.error_message = str(e)
                db.session.commit()
            return False, f"Processing error: {str(e)}"
    
    def _process_message_created(self, event_data: Dict[str, Any]) -> Tuple[bool, str]:
        """Process new message webhook event"""
        try:
            message_data = event_data.get('object', {})
            message_id = message_data.get('id')
            
            if not message_id:
                return False, "Missing message ID in webhook data"
            
            # Check if message already exists
            existing_activity = db.session.query(Activity).filter_by(
                openphone_id=message_id
            ).first()
            
            if existing_activity:
                return True, "Message already exists in database"
            
            # Get or create conversation and contact
            conversation_id = message_data.get('conversationId')
            conversation = self._get_or_create_conversation_from_message(message_data)
            
            if not conversation:
                return False, "Could not create/find conversation for message"
            
            # Create activity record
            created_at = self._parse_webhook_datetime(message_data.get('createdAt'))
            
            new_activity = Activity(
                conversation_id=conversation.id,
                contact_id=conversation.contact_id,
                openphone_id=message_id,
                activity_type='message',
                direction=message_data.get('direction'),
                status=message_data.get('status', 'delivered'),
                
                # Participants
                from_number=message_data.get('from'),
                to_numbers=message_data.get('to', []),
                phone_number_id=message_data.get('phoneNumberId'),
                
                # Content
                body=message_data.get('text'),
                media_urls=message_data.get('media', []),
                
                # Timestamps
                created_at=created_at,
                updated_at=datetime.utcnow()
            )
            
            db.session.add(new_activity)
            db.session.flush()
            
            # Update conversation last activity
            conversation.last_activity_at = created_at
            conversation.last_activity_type = 'message'
            conversation.last_activity_id = message_id
            
            # Process media attachments if present
            media_count = 0
            for media_url in message_data.get('media', []):
                try:
                    # Note: In production, you might want to queue media downloads
                    # For now, we'll store the URL for later processing
                    media_attachment = MediaAttachment(
                        activity_id=new_activity.id,
                        source_url=media_url,
                        local_path=None,  # Download later
                        content_type=None  # Determine later
                    )
                    db.session.add(media_attachment)
                    media_count += 1
                except Exception as e:
                    logger.error(f"Error creating media attachment record: {e}")
            
            db.session.commit()
            
            message_text = f"Message imported successfully"
            if media_count > 0:
                message_text += f" with {media_count} media attachments"
            
            return True, message_text
            
        except Exception as e:
            logger.error(f"Error processing message webhook: {e}")
            return False, f"Message processing error: {str(e)}"
    
    def _process_call_completed(self, event_data: Dict[str, Any]) -> Tuple[bool, str]:
        """Process completed call webhook event"""
        try:
            call_data = event_data.get('object', {})
            call_id = call_data.get('id')
            
            if not call_id:
                return False, "Missing call ID in webhook data"
            
            # Check if call already exists
            existing_activity = db.session.query(Activity).filter_by(
                openphone_id=call_id
            ).first()
            
            if existing_activity:
                # Update existing call with completion data
                existing_activity.status = call_data.get('callStatus')
                existing_activity.duration_seconds = call_data.get('duration')
                existing_activity.completed_at = self._parse_webhook_datetime(call_data.get('completedAt'))
                existing_activity.recording_url = call_data.get('recordingUrl')
                existing_activity.voicemail_url = call_data.get('voicemailUrl')
                
                db.session.commit()
                return True, "Call updated with completion data"
            
            # Create new call activity
            conversation = self._get_or_create_conversation_from_call(call_data)
            
            if not conversation:
                return False, "Could not create/find conversation for call"
            
            created_at = self._parse_webhook_datetime(call_data.get('createdAt'))
            completed_at = self._parse_webhook_datetime(call_data.get('completedAt'))
            answered_at = self._parse_webhook_datetime(call_data.get('answeredAt'))
            
            new_activity = Activity(
                conversation_id=conversation.id,
                contact_id=conversation.contact_id,
                openphone_id=call_id,
                activity_type='call',
                direction=call_data.get('direction'),
                status=call_data.get('callStatus'),
                
                # Participants
                from_number=call_data.get('from'),
                to_numbers=call_data.get('to', []),
                phone_number_id=call_data.get('phoneNumberId'),
                
                # Call-specific fields
                duration_seconds=call_data.get('duration'),
                recording_url=call_data.get('recordingUrl'),
                voicemail_url=call_data.get('voicemailUrl'),
                answered_at=answered_at,
                answered_by=call_data.get('answeredBy'),
                completed_at=completed_at,
                initiated_by=call_data.get('initiatedBy'),
                
                # Timestamps
                created_at=created_at,
                updated_at=datetime.utcnow()
            )
            
            db.session.add(new_activity)
            db.session.flush()
            
            # Update conversation last activity
            conversation.last_activity_at = completed_at or created_at
            conversation.last_activity_type = 'call'
            conversation.last_activity_id = call_id
            
            db.session.commit()
            
            # Queue AI processing for completed calls with recordings
            if call_data.get('recordingUrl') and call_data.get('duration', 0) > 30:
                # Mark for AI processing (to be handled by background job)
                new_activity.ai_content_status = 'pending'
                db.session.commit()
            
            return True, f"Call imported successfully (duration: {call_data.get('duration', 0)}s)"
            
        except Exception as e:
            logger.error(f"Error processing call webhook: {e}")
            return False, f"Call processing error: {str(e)}"
    
    def _process_call_recording_created(self, event_data: Dict[str, Any]) -> Tuple[bool, str]:
        """Process call recording created webhook event"""
        try:
            recording_data = event_data.get('object', {})
            call_id = recording_data.get('callId')
            recording_url = recording_data.get('url')
            
            if not call_id or not recording_url:
                return False, "Missing call ID or recording URL in webhook data"
            
            # Find the call activity
            call_activity = db.session.query(Activity).filter_by(
                openphone_id=call_id,
                activity_type='call'
            ).first()
            
            if not call_activity:
                return False, f"Call activity not found for ID: {call_id}"
            
            # Update with recording URL
            call_activity.recording_url = recording_url
            call_activity.ai_content_status = 'pending'  # Mark for AI processing
            
            db.session.commit()
            
            return True, "Call recording URL updated successfully"
            
        except Exception as e:
            logger.error(f"Error processing call recording webhook: {e}")
            return False, f"Recording processing error: {str(e)}"
    
    def _process_contact_updated(self, event_data: Dict[str, Any]) -> Tuple[bool, str]:
        """Process contact created/updated webhook event"""
        try:
            contact_data = event_data.get('object', {})
            phone_number = contact_data.get('phoneNumber')
            
            if not phone_number:
                return True, "Contact webhook without phone number - skipped"
            
            # Find existing contact
            existing_contact = self.contact_service.get_contact_by_phone(phone_number)
            
            if existing_contact:
                # Update existing contact with new data
                if contact_data.get('firstName'):
                    existing_contact.first_name = contact_data['firstName']
                if contact_data.get('lastName'):
                    existing_contact.last_name = contact_data['lastName']
                if contact_data.get('email'):
                    existing_contact.email = contact_data['email']
                
                db.session.commit()
                return True, "Existing contact updated from webhook"
            else:
                # Create new contact
                first_name = contact_data.get('firstName', phone_number)
                last_name = contact_data.get('lastName', '(from webhook)')
                email = contact_data.get('email')
                
                new_contact = self.contact_service.add_contact(
                    first_name=first_name,
                    last_name=last_name,
                    phone=phone_number,
                    email=email
                )
                
                return True, "New contact created from webhook"
                
        except Exception as e:
            logger.error(f"Error processing contact webhook: {e}")
            return False, f"Contact processing error: {str(e)}"
    
    def _get_or_create_conversation_from_message(self, message_data: Dict[str, Any]) -> Optional[Conversation]:
        """Get or create conversation from message webhook data"""
        try:
            # Try to find existing conversation by OpenPhone conversation ID
            conversation_id = message_data.get('conversationId')
            if conversation_id:
                conversation = db.session.query(Conversation).filter_by(
                    openphone_id=conversation_id
                ).first()
                
                if conversation:
                    return conversation
            
            # Create new conversation based on participants
            participants = [message_data.get('from')] + message_data.get('to', [])
            user_phone = current_app.config.get('OPENPHONE_PHONE_NUMBER')
            other_participants = [p for p in participants if p != user_phone]
            
            if not other_participants:
                return None
            
            primary_participant = other_participants[0]
            
            # Get or create contact
            contact = self.contact_service.get_contact_by_phone(primary_participant)
            if not contact:
                contact = self.contact_service.add_contact(
                    first_name=primary_participant,
                    last_name="(from webhook)",
                    phone=primary_participant
                )
            
            # Create conversation
            new_conversation = Conversation(
                openphone_id=conversation_id,
                contact_id=contact.id,
                participants=','.join(participants),
                phone_number_id=message_data.get('phoneNumberId')
            )
            
            db.session.add(new_conversation)
            db.session.flush()
            
            return new_conversation
            
        except Exception as e:
            logger.error(f"Error creating conversation from message: {e}")
            return None
    
    def _get_or_create_conversation_from_call(self, call_data: Dict[str, Any]) -> Optional[Conversation]:
        """Get or create conversation from call webhook data"""
        try:
            # Similar logic to message conversation creation
            participants = [call_data.get('from')] + call_data.get('to', [])
            user_phone = current_app.config.get('OPENPHONE_PHONE_NUMBER')
            other_participants = [p for p in participants if p != user_phone]
            
            if not other_participants:
                return None
            
            primary_participant = other_participants[0]
            
            # Try to find existing conversation for this contact
            contact = self.contact_service.get_contact_by_phone(primary_participant)
            if not contact:
                contact = self.contact_service.add_contact(
                    first_name=primary_participant,
                    last_name="(from webhook)",
                    phone=primary_participant
                )
            
            # Look for existing conversation
            existing_conversation = db.session.query(Conversation).filter_by(
                contact_id=contact.id
            ).first()
            
            if existing_conversation:
                return existing_conversation
            
            # Create new conversation
            new_conversation = Conversation(
                contact_id=contact.id,
                participants=','.join(participants),
                phone_number_id=call_data.get('phoneNumberId')
            )
            
            db.session.add(new_conversation)
            db.session.flush()
            
            return new_conversation
            
        except Exception as e:
            logger.error(f"Error creating conversation from call: {e}")
            return None
    
    def _parse_webhook_datetime(self, datetime_str: Optional[str]) -> Optional[datetime]:
        """Parse OpenPhone webhook datetime string"""
        if not datetime_str:
            return None
        try:
            return datetime.fromisoformat(datetime_str.replace('Z', '')).replace(tzinfo=timezone.utc)
        except Exception:
            return None
    
    def cleanup_old_webhook_events(self, days_old: int = 30) -> int:
        """
        Clean up old processed webhook events
        
        Args:
            days_old: Delete events older than this many days
            
        Returns:
            Number of events deleted
        """
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days_old)
            
            old_events = db.session.query(WebhookEvent).filter(
                WebhookEvent.processed == True,
                WebhookEvent.created_at < cutoff_date
            ).all()
            
            count = len(old_events)
            for event in old_events:
                db.session.delete(event)
            
            db.session.commit()
            
            logger.info(f"Cleaned up {count} old webhook events")
            return count
            
        except Exception as e:
            logger.error(f"Error cleaning up webhook events: {e}")
            return 0
    
    def get_webhook_stats(self) -> Dict[str, Any]:
        """Get webhook processing statistics"""
        try:
            total_events = db.session.query(WebhookEvent).count()
            processed_events = db.session.query(WebhookEvent).filter_by(processed=True).count()
            failed_events = db.session.query(WebhookEvent).filter(
                WebhookEvent.processed == False,
                WebhookEvent.error_message.isnot(None)
            ).count()
            
            # Event type breakdown
            event_types = db.session.query(
                WebhookEvent.event_type,
                db.func.count(WebhookEvent.id)
            ).group_by(WebhookEvent.event_type).all()
            
            return {
                'total_events': total_events,
                'processed_events': processed_events,
                'failed_events': failed_events,
                'pending_events': total_events - processed_events,
                'event_types': dict(event_types)
            }
            
        except Exception as e:
            logger.error(f"Error getting webhook stats: {e}")
            return {'error': str(e)}