"""
OpenPhone Webhook Service - Refactored with Repository Pattern and Result Pattern

Comprehensive service for handling all OpenPhone webhook event types using:
- Repository pattern for all data access
- Result pattern for consistent error handling
- Proper dependency injection
- No direct database queries

Based on: https://support.openphone.com/hc/en-us/articles/4690754298903-How-to-use-webhooks
"""

import logging
from datetime import datetime
from utils.datetime_utils import utc_now
from typing import Dict, Any, Optional

from services.common.result import Result
# Model imports removed - using repositories only
from repositories.activity_repository import ActivityRepository
from repositories.conversation_repository import ConversationRepository
from repositories.webhook_event_repository import WebhookEventRepository
from services.contact_service_refactored import ContactService
from services.sms_metrics_service import SMSMetricsService
from services.opt_out_service import OptOutService

logger = logging.getLogger(__name__)


class OpenPhoneWebhookServiceRefactored:
    """Handles all OpenPhone webhook events using repository pattern and Result pattern"""
    
    def __init__(self, 
                 activity_repository: ActivityRepository,
                 conversation_repository: ConversationRepository,
                 webhook_event_repository: WebhookEventRepository,
                 contact_service: ContactService,
                 sms_metrics_service: SMSMetricsService,
                 opt_out_service: Optional['OptOutService'] = None):
        """
        Initialize with injected dependencies.
        
        Args:
            activity_repository: Repository for Activity data access
            conversation_repository: Repository for Conversation data access
            webhook_event_repository: Repository for WebhookEvent data access
            contact_service: Service for contact management (returns Result objects)
            sms_metrics_service: Service for SMS metrics tracking
            opt_out_service: Service for opt-out processing (optional)
        """
        self.activity_repository = activity_repository
        self.conversation_repository = conversation_repository
        self.webhook_event_repository = webhook_event_repository
        self.contact_service = contact_service
        self.sms_metrics_service = sms_metrics_service
        self.opt_out_service = opt_out_service
    
    def process_webhook(self, webhook_data: Dict[str, Any]) -> Result[Dict[str, Any]]:
        """
        Main webhook processor that routes to specific handlers using Result pattern.
        
        Args:
            webhook_data: Webhook payload from OpenPhone
            
        Returns:
            Result[Dict]: Success with processing result or failure with error
        """
        try:
            # Log the webhook event
            log_result = self._log_webhook_event(webhook_data)
            if log_result.is_failure:
                logger.warning(f"Failed to log webhook event: {log_result.error}")
                # Continue processing even if logging fails
            
            # Get event type from top level
            event_type = webhook_data.get('type', '')
            
            # Route to specific handlers
            if event_type == 'token.validated':
                return self._handle_token_validation(webhook_data)
            
            elif event_type.startswith('message.'):
                return self._handle_message_webhook(webhook_data)
                
            elif event_type == 'call.recording.completed':
                return self._handle_call_recording_webhook(webhook_data)
                
            elif event_type == 'call.summary.completed':
                return self._handle_call_summary_webhook(webhook_data)
                
            elif event_type == 'call.transcript.completed':
                return self._handle_call_transcript_webhook(webhook_data)
                
            elif event_type.startswith('call.'):
                return self._handle_call_webhook(webhook_data)
                
            else:
                logger.warning(f"Unknown webhook type: {event_type}")
                return Result.failure(
                    f'Unknown event type: {event_type}', 
                    code="UNKNOWN_EVENT_TYPE"
                )
                
        except Exception as e:
            logger.error(f"Error processing webhook: {e}", exc_info=True)
            return Result.failure(str(e), code="PROCESSING_ERROR")
    
    def _log_webhook_event(self, webhook_data: Dict[str, Any]) -> Result[Dict]:
        """
        Log webhook event to database using repository.
        
        Args:
            webhook_data: Webhook payload
            
        Returns:
            Result[Dict]: Success with event data or failure
        """
        try:
            event_data = {
                'event_type': webhook_data.get('type', 'unknown'),
                'payload': webhook_data,
                'processed': False,
                'created_at': utc_now()
            }
            
            webhook_event = self.webhook_event_repository.create(**event_data)
            logger.debug(f"Logged webhook event: {webhook_event.id}")
            
            return Result.success(webhook_event)
            
        except Exception as e:
            logger.error(f"Failed to log webhook event: {e}")
            return Result.failure(f"Failed to log webhook event: {str(e)}", code="WEBHOOK_LOG_ERROR")
    
    def _handle_token_validation(self, webhook_data: Dict[str, Any]) -> Result[Dict[str, Any]]:
        """
        Handle token validation webhook.
        
        Args:
            webhook_data: Token validation payload
            
        Returns:
            Result[Dict]: Success with validation result
        """
        logger.info("Token validation webhook received")
        return Result.success({
            'status': 'success', 
            'message': 'Token validated'
        })
    
    def _handle_message_webhook(self, webhook_data: Dict[str, Any]) -> Result[Dict[str, Any]]:
        """
        Handle message webhooks using repository pattern.
        
        Args:
            webhook_data: Message webhook payload
            
        Returns:
            Result[Dict]: Success with processing result or failure
        """
        try:
            event_type = webhook_data.get('type')
            message_data = webhook_data.get('data', {}).get('object', {})
            
            if not message_data:
                return Result.failure('No message data provided', code="INVALID_DATA")
            
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
            
            # Extract media URLs
            media_data = message_data.get('media', [])
            media_urls = [{'url': item.get('url'), 'type': item.get('type')} 
                         for item in media_data 
                         if isinstance(item, dict) and 'url' in item]
            
            # Check if activity already exists FIRST to short-circuit for updates
            existing_activity = self.activity_repository.find_by_openphone_id(openphone_id)
            if existing_activity:
                logger.info(f"Activity {openphone_id} already exists, updating status from {existing_activity.status} to {status}")
                old_status = existing_activity.status
                
                # Update activity using repository
                updated_activity = self.activity_repository.update(
                    existing_activity.id,
                    status=status,
                    updated_at=utc_now()
                )
                
                # Track metrics for outgoing messages
                if existing_activity.direction == 'outgoing':
                    # Track delivery status changes
                    if status in ['failed', 'undelivered', 'rejected', 'blocked']:
                        # Message bounced - track it
                        error_details = message_data.get('errorMessage', message_data.get('error', 'Unknown error'))
                        self.sms_metrics_service.track_message_status(
                            existing_activity.id, 
                            status,
                            error_details
                        )
                        logger.warning(f"Message {openphone_id} bounced: {error_details}")
                    elif status == 'delivered' and old_status != 'delivered':
                        # Message successfully delivered
                        self.sms_metrics_service.track_message_status(existing_activity.id, status)
                        logger.info(f"Message {openphone_id} successfully delivered")
                
                return Result.success({
                    'status': 'updated', 
                    'activity_id': existing_activity.id
                })
            
            # Activity doesn't exist - check if this is a status update for a message we don't have
            # For delivery status updates without message data, we should not create new activities
            if event_type in ['message.delivered', 'message.failed', 'message.undelivered'] and not (from_number or to_number):
                logger.warning(f"Received {event_type} webhook for message {openphone_id} but no existing activity found and no contact info available. This is likely a delivery status for a message sent before webhook setup.")
                return Result.success({
                    'status': 'skipped',
                    'reason': 'delivery_status_without_existing_activity',
                    'message_id': openphone_id
                })
            
            # Determine contact based on direction
            if direction == 'incoming':
                contact_phone = from_number
                db_direction = 'incoming'
            else:
                # 'to' is a list, get the first number
                contact_phone = to_number[0] if isinstance(to_number, list) and to_number else to_number
                db_direction = 'outgoing'
            
            # Validate that we have contact information
            if not contact_phone:
                logger.error(f"Cannot process message webhook {event_type} for {openphone_id}: no contact phone number available")
                return Result.failure('No contact phone number available in webhook data', code="MISSING_CONTACT_INFO")
            
            # Get or create contact using Result pattern
            contact_result = self._get_or_create_contact(contact_phone)
            if contact_result.is_failure:
                return Result.failure(contact_result.error, code="CONTACT_ERROR")
            
            contact = contact_result.data
            
            # Get or create conversation using repository
            conversation = self._get_or_create_conversation(contact.id, conversation_id)
            
            # Create new activity using repository
            activity_data = {
                'conversation_id': conversation.id,
                'contact_id': contact.id,
                'openphone_id': openphone_id,
                'activity_type': 'message',
                'body': body,
                'direction': db_direction,
                'status': status,
                'media_urls': media_urls,
                'created_at': created_at or utc_now(),
                'updated_at': utc_now()
            }
            
            new_activity = self.activity_repository.create(**activity_data)
            
            # Update conversation last activity using repository
            self.conversation_repository.update_last_activity(
                conversation.id, 
                created_at or utc_now()
            )
            
            # Track initial status for outgoing messages
            if db_direction == 'outgoing':
                if status in ['failed', 'undelivered', 'rejected', 'blocked']:
                    # Message bounced immediately
                    error_details = message_data.get('errorMessage', message_data.get('error', 'Unknown error'))
                    self.sms_metrics_service.track_message_status(
                        new_activity.id,
                        status,
                        error_details
                    )
                    logger.warning(f"New message {openphone_id} bounced: {error_details}")
                elif status == 'delivered':
                    # Message delivered immediately
                    self.sms_metrics_service.track_message_status(new_activity.id, status)
                    logger.info(f"New message {openphone_id} delivered")
            
            # Process opt-out/opt-in for incoming messages
            if db_direction == 'incoming' and self.opt_out_service and body:
                opt_result = self.opt_out_service.process_incoming_message(
                    contact=contact,
                    message_body=body,
                    webhook_data={'id': openphone_id, 'direction': 'incoming'}
                )
                if opt_result.is_success:
                    action = opt_result.data.get('action', 'none')
                    if action in ['opted_out', 'opted_in']:
                        logger.info(f"Processed {action} for contact {contact.id} from message {openphone_id}")
            
            # Log if media was included
            if media_urls:
                logger.info(f"Message {openphone_id} includes {len(media_urls)} media attachments")
            
            return Result.success({
                'status': 'created', 
                'activity_id': new_activity.id, 
                'media_count': len(media_urls),
                'opt_out_processed': db_direction == 'incoming' and self.opt_out_service is not None
            })
            
        except Exception as e:
            logger.error(f"Error handling message webhook: {e}", exc_info=True)
            return Result.failure(f"Error handling message webhook: {str(e)}", code="REPOSITORY_ERROR")
    
    def _handle_call_webhook(self, webhook_data: Dict[str, Any]) -> Result[Dict[str, Any]]:
        """
        Handle call webhooks using repository pattern.
        
        Args:
            webhook_data: Call webhook payload
            
        Returns:
            Result[Dict]: Success with processing result or failure
        """
        try:
            event_type = webhook_data.get('type')
            call_data = webhook_data.get('data', {}).get('object', {})
            
            if not call_data:
                return Result.failure('No call data provided', code="INVALID_DATA")
            
            logger.info(f"Processing {event_type} webhook")
            
            # Extract call details
            openphone_id = call_data.get('id')
            direction = call_data.get('direction', 'unknown')
            status = call_data.get('status', 'unknown')
            duration = call_data.get('duration', call_data.get('durationSeconds', 0))
            
            # Check if call activity already exists FIRST to short-circuit for updates  
            existing_activity = self.activity_repository.find_by_openphone_id(openphone_id)
            if existing_activity:
                logger.info(f"Call {openphone_id} already exists, updating")
                
                updated_activity = self.activity_repository.update(
                    existing_activity.id,
                    status=status,
                    duration_seconds=duration,
                    updated_at=utc_now()
                )
                
                return Result.success({
                    'status': 'updated', 
                    'activity_id': existing_activity.id
                })
            
            # Activity doesn't exist - check if this is a status update for a call we don't have
            # For call status updates without participant data, we should not create new activities
            participants = call_data.get('participants', [])
            if not participants:
                if event_type in ['call.completed', 'call.ended', 'call.failed']:
                    logger.warning(f"Received {event_type} webhook for call {openphone_id} but no existing activity found and no participant info available. This is likely a status update for a call made before webhook setup.")
                    return Result.success({
                        'status': 'skipped',
                        'reason': 'call_status_without_existing_activity',
                        'call_id': openphone_id
                    })
                else:
                    return Result.failure('No participants in call data', code="INVALID_DATA")
            
            # Determine contact phone (participant who is not our number)
            our_number = self._get_our_phone_number()
            contact_phone = None
            for participant in participants:
                if participant != our_number:
                    contact_phone = participant
                    break
            
            if not contact_phone:
                logger.warning(f"Could not determine contact phone from participants: {participants}")
                return Result.failure('Could not determine contact phone', code="INVALID_DATA")
            
            # Get or create contact using Result pattern
            contact_result = self._get_or_create_contact(contact_phone)
            if contact_result.is_failure:
                return Result.failure(contact_result.error, code="CONTACT_ERROR")
            
            contact = contact_result.data
            
            # Get or create conversation using repository
            conversation = self._get_or_create_conversation(contact.id)
            
            # Create new call activity using repository
            activity_data = {
                'conversation_id': conversation.id,
                'contact_id': contact.id,
                'openphone_id': openphone_id,
                'activity_type': 'call',
                'direction': direction,
                'status': status,
                'duration_seconds': duration,
                'answered_at': self._parse_timestamp(call_data.get('answeredAt')),
                'completed_at': self._parse_timestamp(call_data.get('completedAt')),
                'created_at': self._parse_timestamp(call_data.get('createdAt')) or utc_now(),
                'updated_at': utc_now()
            }
            
            new_activity = self.activity_repository.create(**activity_data)
            
            # Update conversation using repository
            self.conversation_repository.update_last_activity(
                conversation.id, 
                new_activity.created_at
            )
            
            # Try to fetch call recording if call is completed
            if status == 'completed':
                self._fetch_call_recording_async(new_activity.id, openphone_id)
            
            return Result.success({
                'status': 'created', 
                'activity_id': new_activity.id
            })
            
        except Exception as e:
            logger.error(f"Error handling call webhook: {e}", exc_info=True)
            return Result.failure(f"Error handling call webhook: {str(e)}", code="REPOSITORY_ERROR")
    
    def _handle_call_summary_webhook(self, webhook_data: Dict[str, Any]) -> Result[Dict[str, Any]]:
        """
        Handle call summary webhooks using repository pattern.
        
        Args:
            webhook_data: Call summary webhook payload
            
        Returns:
            Result[Dict]: Success with processing result or failure
        """
        try:
            event_type = webhook_data.get('type')
            summary_data = webhook_data.get('data', {}).get('object', {})
            
            logger.info(f"Processing {event_type} webhook")
            
            call_id = summary_data.get('callId')
            summary_text = summary_data.get('summary')
            
            if not call_id or not summary_text:
                return Result.failure('Missing call ID or summary', code="INVALID_DATA")
            
            # Find the call activity using repository
            call_activity = self.activity_repository.find_by_openphone_id(call_id)
            
            if not call_activity:
                logger.warning(f"Call activity not found for call ID: {call_id}. This is likely a summary for a call made before webhook setup.")
                return Result.success({
                    'status': 'skipped',
                    'reason': 'call_activity_not_found',
                    'call_id': call_id
                })
            
            # Update with AI summary using repository
            updated_activity = self.activity_repository.update(
                call_activity.id,
                ai_summary=summary_text,
                updated_at=utc_now()
            )
            
            return Result.success({
                'status': 'updated', 
                'activity_id': call_activity.id
            })
            
        except Exception as e:
            logger.error(f"Error handling call summary webhook: {e}", exc_info=True)
            return Result.failure(f"Error handling call summary webhook: {str(e)}", code="REPOSITORY_ERROR")
    
    def _handle_call_transcript_webhook(self, webhook_data: Dict[str, Any]) -> Result[Dict[str, Any]]:
        """
        Handle call transcript webhooks using repository pattern.
        
        Args:
            webhook_data: Call transcript webhook payload
            
        Returns:
            Result[Dict]: Success with processing result or failure
        """
        try:
            event_type = webhook_data.get('type')
            transcript_data = webhook_data.get('data', {}).get('object', {})
            
            logger.info(f"Processing {event_type} webhook")
            
            call_id = transcript_data.get('callId')
            transcript = transcript_data.get('transcript')
            
            if not call_id or not transcript:
                return Result.failure('Missing call ID or transcript', code="INVALID_DATA")
            
            # Find the call activity using repository
            call_activity = self.activity_repository.find_by_openphone_id(call_id)
            
            if not call_activity:
                logger.warning(f"Call activity not found for call ID: {call_id}. This is likely a transcript for a call made before webhook setup.")
                return Result.success({
                    'status': 'skipped',
                    'reason': 'call_activity_not_found',
                    'call_id': call_id
                })
            
            # Update with AI transcript using repository
            updated_activity = self.activity_repository.update(
                call_activity.id,
                ai_transcript=transcript,
                updated_at=utc_now()
            )
            
            return Result.success({
                'status': 'updated', 
                'activity_id': call_activity.id
            })
            
        except Exception as e:
            logger.error(f"Error handling call transcript webhook: {e}", exc_info=True)
            return Result.failure(f"Error handling call transcript webhook: {str(e)}", code="REPOSITORY_ERROR")
    
    def _handle_call_recording_webhook(self, webhook_data: Dict[str, Any]) -> Result[Dict[str, Any]]:
        """
        Handle call recording completed webhook using repository pattern.
        
        Args:
            webhook_data: Call recording webhook payload
            
        Returns:
            Result[Dict]: Success with processing result or failure
        """
        try:
            event_type = webhook_data.get('type')
            recording_data = webhook_data.get('data', {}).get('object', {})
            
            logger.info(f"Processing {event_type} webhook")
            
            recording_id = recording_data.get('id')
            call_id = recording_data.get('callId')
            recording_url = recording_data.get('url')
            
            if not call_id or not recording_url:
                return Result.failure('Missing call ID or recording URL', code="INVALID_DATA")
            
            # Find the call activity using repository
            call_activity = self.activity_repository.find_by_openphone_id(call_id)
            
            if not call_activity:
                logger.warning(f"Call activity not found for call ID: {call_id}. This is likely a recording for a call made before webhook setup.")
                return Result.success({
                    'status': 'skipped',
                    'reason': 'call_activity_not_found',
                    'call_id': call_id
                })
            
            # Update with recording URL using repository
            update_data = {
                'recording_url': recording_url,
                'updated_at': utc_now()
            }
            
            # Store recording metadata if available
            if recording_data.get('duration'):
                update_data['duration_seconds'] = recording_data['duration']
            
            updated_activity = self.activity_repository.update(call_activity.id, **update_data)
            
            logger.info(f"Call recording updated for call {call_id}")
            
            return Result.success({
                'status': 'updated', 
                'activity_id': call_activity.id, 
                'recording_id': recording_id
            })
            
        except Exception as e:
            logger.error(f"Error handling call recording webhook: {e}", exc_info=True)
            return Result.failure(f"Error handling call recording webhook: {str(e)}", code="REPOSITORY_ERROR")
    
    def _get_or_create_contact(self, phone_number: str) -> Result[Dict]:
        """
        Get or create a contact by phone number using ContactService Result pattern.
        
        Args:
            phone_number: Phone number to search/create
            
        Returns:
            Result[Dict]: Success with contact data or failure
        """
        # Try to get existing contact
        contact_result = self.contact_service.get_contact_by_phone(phone_number)
        if contact_result.is_success:
            return contact_result
        
        # Contact not found, try to create new one
        create_result = self.contact_service.add_contact(
            first_name=phone_number,
            last_name="(from OpenPhone)",
            phone=phone_number
        )
        
        if create_result.is_success:
            return create_result
        else:
            return Result.failure(create_result.error, code="CONTACT_ERROR")
    
    def _get_or_create_conversation(self, contact_id: int, openphone_conversation_id: str = None) -> Dict[str, Any]:
        """
        Get or create a conversation using repository pattern.
        
        Args:
            contact_id: Contact ID
            openphone_conversation_id: Optional OpenPhone conversation ID
            
        Returns:
            Conversation: Conversation object
        """
        return self.conversation_repository.find_or_create_for_contact(
            contact_id=contact_id,
            openphone_id=openphone_conversation_id
        )
    
    def _parse_timestamp(self, timestamp_str: str) -> Optional[datetime]:
        """
        Parse OpenPhone timestamp format.
        
        Args:
            timestamp_str: ISO timestamp string
            
        Returns:
            datetime object or None if parsing fails
        """
        if not timestamp_str:
            return None
        
        try:
            # OpenPhone uses ISO format: "2025-07-29T14:41:30.000Z"
            return datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        except Exception as e:
            logger.error(f"Failed to parse timestamp {timestamp_str}: {e}")
            return None
    
    def _get_our_phone_number(self) -> str:
        """
        Get our OpenPhone number from config.
        
        Returns:
            Our phone number string
        """
        from flask import current_app
        return current_app.config.get('OPENPHONE_PHONE_NUMBER', '')
    
    def _fetch_call_recording_async(self, activity_id: int, call_id: str):
        """
        Fetch call recording asynchronously (placeholder for Celery task).
        
        Args:
            activity_id: Activity ID
            call_id: OpenPhone call ID
        """
        # TODO: Implement as Celery task
        logger.info(f"Should fetch recording for call {call_id} (activity {activity_id})")
        pass