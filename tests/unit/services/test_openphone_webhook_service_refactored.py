"""
Comprehensive Unit Tests for Refactored OpenPhoneWebhookService
Tests TDD-compliant implementation with Result pattern and repository pattern
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
from typing import Dict, Any

from services.openphone_webhook_service_refactored import OpenPhoneWebhookServiceRefactored
from services.common.result import Result
from crm_database import Contact, Conversation, Activity, WebhookEvent


class TestOpenPhoneWebhookServiceRefactoredInitialization:
    """Test service initialization with dependency injection"""
    
    def test_service_exists_and_imports_successfully(self):
        """Test that service can be imported successfully"""
        # Service should now exist and import successfully
        from services.openphone_webhook_service_refactored import OpenPhoneWebhookServiceRefactored
        assert OpenPhoneWebhookServiceRefactored is not None
    
    def test_service_initialization_with_repositories(self):
        """Test service initialization with proper repositories"""
        # Mock all required repositories
        activity_repo = Mock()
        conversation_repo = Mock()
        webhook_repo = Mock()
        contact_service = Mock()
        metrics_service = Mock()
        
        # This should pass after implementation
        service = OpenPhoneWebhookServiceRefactored(
            activity_repository=activity_repo,
            conversation_repository=conversation_repo,
            webhook_event_repository=webhook_repo,
            contact_service=contact_service,
            sms_metrics_service=metrics_service
        )
        
        assert service.activity_repository == activity_repo
        assert service.conversation_repository == conversation_repo
        assert service.webhook_event_repository == webhook_repo
        assert service.contact_service == contact_service
        assert service.sms_metrics_service == metrics_service


class TestWebhookEventLoggingWithResult:
    """Test webhook event logging with Result pattern"""
    
    def test_log_webhook_event_success(self):
        """Test successful webhook event logging returns Result.success"""
        service = self._create_service()
        webhook_data = {'type': 'message.received', 'data': {}}
        
        # Mock successful creation
        mock_event = Mock()
        mock_event.id = 123
        service.webhook_event_repository.create.return_value = mock_event
        
        result = service._log_webhook_event(webhook_data)
        
        assert result.is_success
        assert result.data == mock_event
        service.webhook_event_repository.create.assert_called_once()
    
    def test_log_webhook_event_failure(self):
        """Test webhook event logging handles repository errors"""
        service = self._create_service()
        webhook_data = {'type': 'message.received', 'data': {}}
        
        # Mock repository error
        service.webhook_event_repository.create.side_effect = Exception("Database error")
        
        result = service._log_webhook_event(webhook_data)
        
        assert result.is_failure
        assert "Database error" in result.error
        assert result.error_code == "WEBHOOK_LOG_ERROR"
    
    def test_log_webhook_event_with_missing_type(self):
        """Test webhook event logging with missing event type"""
        service = self._create_service()
        webhook_data = {}  # Missing 'type' field
        
        mock_event = Mock()
        service.webhook_event_repository.create.return_value = mock_event
        
        result = service._log_webhook_event(webhook_data)
        
        assert result.is_success
        # Should use 'unknown' as default type
        call_args = service.webhook_event_repository.create.call_args[1]
        assert call_args['event_type'] == 'unknown'
    
    def _create_service(self):
        """Helper to create service with mocked dependencies"""
        # Create mocks with sensible defaults
        activity_repo = Mock()
        activity_repo.find_by_openphone_id.return_value = None  # Default: no existing activity
        
        conversation_repo = Mock()
        webhook_repo = Mock()
        contact_service = Mock()
        metrics_service = Mock()
        
        return OpenPhoneWebhookServiceRefactored(
            activity_repository=activity_repo,
            conversation_repository=conversation_repo,
            webhook_event_repository=webhook_repo,
            contact_service=contact_service,
            sms_metrics_service=metrics_service
        )


class TestTokenValidationWebhooks:
    """Test token validation webhook handling with Result pattern"""
    
    def test_handle_token_validation_returns_result_success(self):
        """Test token validation returns Result.success"""
        service = self._create_service()
        webhook_data = {'type': 'token.validated', 'data': {'valid': True}}
        
        result = service._handle_token_validation(webhook_data)
        
        assert result.is_success
        assert result.data['status'] == 'success'
        assert result.data['message'] == 'Token validated'
    
    def _create_service(self):
        # Create mocks with sensible defaults
        activity_repo = Mock()
        activity_repo.find_by_openphone_id.return_value = None  # Default: no existing activity
        
        conversation_repo = Mock()
        webhook_repo = Mock()
        contact_service = Mock()
        metrics_service = Mock()
        
        return OpenPhoneWebhookServiceRefactored(
            activity_repository=activity_repo,
            conversation_repository=conversation_repo,
            webhook_event_repository=webhook_repo,
            contact_service=contact_service,
            sms_metrics_service=metrics_service
        )


class TestMessageWebhooksWithRepositories:
    """Test message webhook handling using repository pattern"""
    
    def test_message_received_creates_new_activity_with_repositories(self):
        """Test message.received creates activity using repositories"""
        service = self._create_service()
        
        # Mock contact service Result
        mock_contact = Mock()
        mock_contact.id = 123
        service.contact_service.get_contact_by_phone.return_value = Result.success(mock_contact)
        
        # Mock conversation repository
        mock_conversation = Mock()
        mock_conversation.id = 456
        service.conversation_repository.find_or_create_for_contact.return_value = mock_conversation
        
        # Mock no existing activity
        service.activity_repository.find_by_openphone_id.return_value = None
        
        # Mock activity creation
        mock_activity = Mock()
        mock_activity.id = 789
        service.activity_repository.create.return_value = mock_activity
        
        webhook_data = {
            'type': 'message.received',
            'data': {
                'object': {
                    'id': 'msg_123',
                    'conversationId': 'conv_456',
                    'direction': 'incoming',
                    'from': '+1234567890',
                    'to': ['+0987654321'],
                    'text': 'Hello world',
                    'status': 'received',
                    'createdAt': '2025-07-30T10:00:00.000Z'
                }
            }
        }
        
        result = service._handle_message_webhook(webhook_data)
        
        # Verify Result pattern
        assert result.is_success
        assert result.data['status'] == 'created'
        assert result.data['activity_id'] == 789
        
        # Verify repository calls
        service.contact_service.get_contact_by_phone.assert_called_once_with('+1234567890')
        service.conversation_repository.find_or_create_for_contact.assert_called_once()
        service.activity_repository.find_by_openphone_id.assert_called_once_with('msg_123')
        service.activity_repository.create.assert_called_once()
    
    def test_message_delivered_updates_existing_activity_via_repository(self):
        """Test message.delivered updates activity via repository"""
        service = self._create_service()
        
        # Mock existing activity
        mock_activity = Mock()
        mock_activity.id = 789
        mock_activity.status = 'sent'
        mock_activity.direction = 'outgoing'
        service.activity_repository.find_by_openphone_id.return_value = mock_activity
        
        # Mock successful update
        service.activity_repository.update.return_value = mock_activity
        
        # Note: For update webhooks, we don't need to resolve contact since activity exists
        # The service short-circuits to update mode when activity is found
        webhook_data = {
            'type': 'message.delivered',
            'data': {
                'object': {
                    'id': 'msg_123',
                    'status': 'delivered',
                    'direction': 'outgoing',  # Add direction to skip contact resolution
                    'from': '+1234567890',
                    'to': ['+0987654321']
                }
            }
        }
        
        result = service._handle_message_webhook(webhook_data)
        
        assert result.is_success
        assert result.data['status'] == 'updated'
        assert result.data['activity_id'] == 789
        
        # Verify repository update call
        service.activity_repository.update.assert_called_once()
        service.sms_metrics_service.track_message_status.assert_called_once_with(789, 'delivered')
    
    def test_message_failed_tracks_error_metrics_via_repository(self):
        """Test failed message tracks error metrics using repository"""
        service = self._create_service()
        
        # Mock existing activity
        mock_activity = Mock()
        mock_activity.id = 789
        mock_activity.direction = 'outgoing'
        service.activity_repository.find_by_openphone_id.return_value = mock_activity
        service.activity_repository.update.return_value = mock_activity
        
        webhook_data = {
            'type': 'message.failed',
            'data': {
                'object': {
                    'id': 'msg_123',
                    'status': 'failed',
                    'errorMessage': 'Invalid phone number',
                    'direction': 'outgoing',  # Add direction to skip contact resolution
                    'from': '+1234567890',
                    'to': ['+0987654321']
                }
            }
        }
        
        result = service._handle_message_webhook(webhook_data)
        
        assert result.is_success
        
        # Verify error metrics tracking
        service.sms_metrics_service.track_message_status.assert_called_once_with(
            789, 'failed', 'Invalid phone number'
        )
    
    def test_message_webhook_handles_contact_service_failure(self):
        """Test message webhook handles ContactService Result.failure"""
        service = self._create_service()
        
        # Mock NO existing activity so contact resolution is attempted
        service.activity_repository.find_by_openphone_id.return_value = None
        
        # Mock contact service failure
        service.contact_service.get_contact_by_phone.return_value = Result.failure(
            "Contact not found", code="NOT_FOUND"
        )
        service.contact_service.add_contact.return_value = Result.failure(
            "Cannot create contact", code="CREATE_ERROR"
        )
        
        webhook_data = {
            'type': 'message.received',
            'data': {
                'object': {
                    'id': 'msg_123',
                    'direction': 'incoming',
                    'from': '+1234567890'
                }
            }
        }
        
        result = service._handle_message_webhook(webhook_data)
        
        assert result.is_failure
        assert "Cannot create contact" in result.error
        assert result.error_code == "CONTACT_ERROR"
    
    def test_message_webhook_missing_data_object(self):
        """Test message webhook with missing data returns Result.failure"""
        service = self._create_service()
        
        webhook_data = {
            'type': 'message.received',
            'data': {}  # Missing 'object' key
        }
        
        result = service._handle_message_webhook(webhook_data)
        
        assert result.is_failure
        assert 'No message data provided' in result.error
        assert result.error_code == "INVALID_DATA"
    
    def test_message_with_media_attachments_via_repository(self):
        """Test message with media attachments using repository"""
        service = self._create_service()
        
        # Setup mocks for successful flow
        mock_contact = Mock()
        mock_contact.id = 123
        service.contact_service.get_contact_by_phone.return_value = Result.success(mock_contact)
        
        mock_conversation = Mock()
        mock_conversation.id = 456
        service.conversation_repository.find_or_create_for_contact.return_value = mock_conversation
        
        service.activity_repository.find_by_openphone_id.return_value = None
        
        mock_activity = Mock()
        mock_activity.id = 789
        service.activity_repository.create.return_value = mock_activity
        
        webhook_data = {
            'type': 'message.received',
            'data': {
                'object': {
                    'id': 'msg_123',
                    'text': 'Check out these photos',
                    'media': [
                        {'url': 'https://example.com/photo1.jpg', 'type': 'image/jpeg'},
                        {'url': 'https://example.com/photo2.jpg', 'type': 'image/jpeg'}
                    ]
                }
            }
        }
        
        result = service._handle_message_webhook(webhook_data)
        
        assert result.is_success
        assert result.data['media_count'] == 2
        
        # Verify media URLs are passed to repository
        create_call_args = service.activity_repository.create.call_args[1]
        assert len(create_call_args['media_urls']) == 2
    
    def _create_service(self):
        # Create mocks with sensible defaults
        activity_repo = Mock()
        activity_repo.find_by_openphone_id.return_value = None  # Default: no existing activity
        
        conversation_repo = Mock()
        webhook_repo = Mock()
        contact_service = Mock()
        metrics_service = Mock()
        
        return OpenPhoneWebhookServiceRefactored(
            activity_repository=activity_repo,
            conversation_repository=conversation_repo,
            webhook_event_repository=webhook_repo,
            contact_service=contact_service,
            sms_metrics_service=metrics_service
        )


class TestCallWebhooksWithRepositories:
    """Test call webhook handling using repository pattern"""
    
    def test_call_completed_creates_new_activity_via_repository(self):
        """Test call.completed creates activity using repository"""
        service = self._create_service()
        
        # Mock contact resolution
        mock_contact = Mock()
        mock_contact.id = 123
        service.contact_service.get_contact_by_phone.return_value = Result.success(mock_contact)
        
        # Mock conversation
        mock_conversation = Mock()
        mock_conversation.id = 456
        service.conversation_repository.find_or_create_for_contact.return_value = mock_conversation
        
        # Mock no existing activity
        service.activity_repository.find_by_openphone_id.return_value = None
        
        # Mock activity creation
        mock_activity = Mock()
        mock_activity.id = 789
        service.activity_repository.create.return_value = mock_activity
        
        webhook_data = {
            'type': 'call.completed',
            'data': {
                'object': {
                    'id': 'call_123',
                    'direction': 'incoming',
                    'status': 'completed',
                    'duration': 300,
                    'participants': ['+1234567890', '+0987654321']
                }
            }
        }
        
        with patch.object(service, '_get_our_phone_number', return_value='+0987654321'):
            result = service._handle_call_webhook(webhook_data)
        
        assert result.is_success
        assert result.data['status'] == 'created'
        assert result.data['activity_id'] == 789
        
        # Verify repository calls
        service.contact_service.get_contact_by_phone.assert_called_once_with('+1234567890')
        service.activity_repository.create.assert_called_once()
    
    def test_call_completed_updates_existing_activity_via_repository(self):
        """Test call.completed updates existing activity via repository"""
        service = self._create_service()
        
        # Mock existing activity - for updates, we skip contact resolution
        mock_activity = Mock()
        mock_activity.id = 789
        service.activity_repository.find_by_openphone_id.return_value = mock_activity
        service.activity_repository.update.return_value = mock_activity
        
        webhook_data = {
            'type': 'call.completed',
            'data': {
                'object': {
                    'id': 'call_123',
                    'status': 'completed',
                    'duration': 450,
                    'participants': ['+1234567890', '+0987654321']
                }
            }
        }
        
        # When activity exists, the service short-circuits to update mode
        # and doesn't need to resolve contact or conversation
        result = service._handle_call_webhook(webhook_data)
        
        assert result.is_success
        assert result.data['status'] == 'updated'
        assert result.data['activity_id'] == 789
        
        # Verify repository update
        service.activity_repository.update.assert_called_once()
    
    def test_call_webhook_missing_participants_returns_failure(self):
        """Test call webhook with missing participants returns Result.failure"""
        service = self._create_service()
        
        # Mock NO existing activity so validation is attempted
        service.activity_repository.find_by_openphone_id.return_value = None
        
        webhook_data = {
            'type': 'call.completed',
            'data': {
                'object': {
                    'id': 'call_123',
                    'participants': []
                }
            }
        }
        
        result = service._handle_call_webhook(webhook_data)
        
        assert result.is_failure
        assert 'No participants in call data' in result.error
        assert result.error_code == "INVALID_DATA"
    
    def test_call_webhook_cannot_determine_contact_phone(self):
        """Test call webhook when contact phone cannot be determined"""
        service = self._create_service()
        
        # Mock NO existing activity so validation is attempted
        service.activity_repository.find_by_openphone_id.return_value = None
        
        webhook_data = {
            'type': 'call.completed',
            'data': {
                'object': {
                    'id': 'call_123',
                    'participants': ['+0987654321']  # Only our number
                }
            }
        }
        
        with patch.object(service, '_get_our_phone_number', return_value='+0987654321'):
            result = service._handle_call_webhook(webhook_data)
        
        assert result.is_failure
        assert 'Could not determine contact phone' in result.error
        assert result.error_code == "INVALID_DATA"
    
    def _create_service(self):
        # Create mocks with sensible defaults
        activity_repo = Mock()
        activity_repo.find_by_openphone_id.return_value = None  # Default: no existing activity
        
        conversation_repo = Mock()
        webhook_repo = Mock()
        contact_service = Mock()
        metrics_service = Mock()
        
        return OpenPhoneWebhookServiceRefactored(
            activity_repository=activity_repo,
            conversation_repository=conversation_repo,
            webhook_event_repository=webhook_repo,
            contact_service=contact_service,
            sms_metrics_service=metrics_service
        )


class TestAIContentWebhooksWithRepositories:
    """Test AI-generated content webhooks using repository pattern"""
    
    def test_call_summary_completed_updates_via_repository(self):
        """Test call.summary.completed updates activity via repository"""
        service = self._create_service()
        
        # Mock existing call activity
        mock_activity = Mock()
        mock_activity.id = 789
        service.activity_repository.find_by_openphone_id.return_value = mock_activity
        service.activity_repository.update.return_value = mock_activity
        
        webhook_data = {
            'type': 'call.summary.completed',
            'data': {
                'object': {
                    'callId': 'call_123',
                    'summary': 'Customer called about foundation repair pricing'
                }
            }
        }
        
        result = service._handle_call_summary_webhook(webhook_data)
        
        assert result.is_success
        assert result.data['status'] == 'updated'
        assert result.data['activity_id'] == 789
        
        # Verify repository update with AI summary
        service.activity_repository.update.assert_called_once()
        update_args = service.activity_repository.update.call_args[0]
        assert update_args[0] == 789  # activity_id
        update_kwargs = service.activity_repository.update.call_args[1]
        assert update_kwargs['ai_summary'] == 'Customer called about foundation repair pricing'
    
    def test_call_transcript_completed_updates_via_repository(self):
        """Test call.transcript.completed updates activity via repository"""
        service = self._create_service()
        
        # Mock existing call activity
        mock_activity = Mock()
        mock_activity.id = 789
        service.activity_repository.find_by_openphone_id.return_value = mock_activity
        service.activity_repository.update.return_value = mock_activity
        
        transcript_data = {
            'dialogue': [
                {'speaker': 'Agent', 'text': 'Hello, how can I help?'},
                {'speaker': 'Customer', 'text': 'I need foundation repair'}
            ],
            'confidence': 0.95
        }
        
        webhook_data = {
            'type': 'call.transcript.completed',
            'data': {
                'object': {
                    'callId': 'call_123',
                    'transcript': transcript_data
                }
            }
        }
        
        result = service._handle_call_transcript_webhook(webhook_data)
        
        assert result.is_success
        assert result.data['status'] == 'updated'
        assert result.data['activity_id'] == 789
        
        # Verify repository update with transcript
        service.activity_repository.update.assert_called_once()
        update_kwargs = service.activity_repository.update.call_args[1]
        assert update_kwargs['ai_transcript'] == transcript_data
    
    def test_call_recording_completed_updates_via_repository(self):
        """Test call.recording.completed updates activity via repository"""
        service = self._create_service()
        
        # Mock existing call activity
        mock_activity = Mock()
        mock_activity.id = 789
        service.activity_repository.find_by_openphone_id.return_value = mock_activity
        service.activity_repository.update.return_value = mock_activity
        
        webhook_data = {
            'type': 'call.recording.completed',
            'data': {
                'object': {
                    'id': 'rec_123',
                    'callId': 'call_123',
                    'url': 'https://recordings.openphone.com/call_123.mp3',
                    'duration': 300
                }
            }
        }
        
        result = service._handle_call_recording_webhook(webhook_data)
        
        assert result.is_success
        assert result.data['status'] == 'updated'
        assert result.data['activity_id'] == 789
        assert result.data['recording_id'] == 'rec_123'
        
        # Verify repository update with recording URL
        service.activity_repository.update.assert_called_once()
        update_kwargs = service.activity_repository.update.call_args[1]
        assert update_kwargs['recording_url'] == 'https://recordings.openphone.com/call_123.mp3'
    
    def test_ai_webhook_missing_required_data_returns_failure(self):
        """Test AI webhooks with missing data return Result.failure"""
        service = self._create_service()
        
        # Test missing summary
        webhook_data = {
            'type': 'call.summary.completed',
            'data': {
                'object': {
                    'callId': 'call_123'
                    # Missing 'summary'
                }
            }
        }
        
        result = service._handle_call_summary_webhook(webhook_data)
        
        assert result.is_failure
        assert 'Missing call ID or summary' in result.error
        assert result.error_code == "INVALID_DATA"
    
    def test_ai_webhook_call_not_found_returns_failure(self):
        """Test AI webhooks when call activity not found"""
        service = self._create_service()
        
        # Mock no existing call activity
        service.activity_repository.find_by_openphone_id.return_value = None
        
        webhook_data = {
            'type': 'call.summary.completed',
            'data': {
                'object': {
                    'callId': 'call_123',
                    'summary': 'Some summary'
                }
            }
        }
        
        result = service._handle_call_summary_webhook(webhook_data)
        
        assert result.is_failure
        assert 'Call activity not found' in result.error
        assert result.error_code == "NOT_FOUND"
    
    def _create_service(self):
        # Create mocks with sensible defaults
        activity_repo = Mock()
        activity_repo.find_by_openphone_id.return_value = None  # Default: no existing activity
        
        conversation_repo = Mock()
        webhook_repo = Mock()
        contact_service = Mock()
        metrics_service = Mock()
        
        return OpenPhoneWebhookServiceRefactored(
            activity_repository=activity_repo,
            conversation_repository=conversation_repo,
            webhook_event_repository=webhook_repo,
            contact_service=contact_service,
            sms_metrics_service=metrics_service
        )


class TestContactAndConversationManagementWithRepositories:
    """Test contact and conversation management using repositories and Result pattern"""
    
    def test_get_or_create_contact_existing_contact_success(self):
        """Test getting existing contact returns Result.success"""
        service = self._create_service()
        
        # Mock existing contact
        mock_contact = Mock()
        mock_contact.id = 123
        service.contact_service.get_contact_by_phone.return_value = Result.success(mock_contact)
        
        result = service._get_or_create_contact('+1234567890')
        
        assert result.is_success
        assert result.data == mock_contact
        service.contact_service.add_contact.assert_not_called()
    
    def test_get_or_create_contact_creates_new_contact(self):
        """Test creating new contact when none exists"""
        service = self._create_service()
        
        # Mock no existing contact
        service.contact_service.get_contact_by_phone.return_value = Result.failure(
            "Contact not found", code="NOT_FOUND"
        )
        
        # Mock successful contact creation
        mock_new_contact = Mock()
        mock_new_contact.id = 123
        service.contact_service.add_contact.return_value = Result.success(mock_new_contact)
        
        result = service._get_or_create_contact('+1234567890')
        
        assert result.is_success
        assert result.data == mock_new_contact
        service.contact_service.add_contact.assert_called_once_with(
            first_name='+1234567890',
            last_name='(from OpenPhone)',
            phone='+1234567890'
        )
    
    def test_get_or_create_contact_creation_fails(self):
        """Test handling contact creation failure"""
        service = self._create_service()
        
        # Mock no existing contact
        service.contact_service.get_contact_by_phone.return_value = Result.failure(
            "Contact not found", code="NOT_FOUND"
        )
        
        # Mock contact creation failure
        service.contact_service.add_contact.return_value = Result.failure(
            "Database error", code="CREATE_ERROR"
        )
        
        result = service._get_or_create_contact('+1234567890')
        
        assert result.is_failure
        assert "Database error" in result.error
        assert result.error_code == "CONTACT_ERROR"
    
    def test_get_or_create_conversation_uses_repository(self):
        """Test conversation creation using repository pattern"""
        service = self._create_service()
        
        # Mock conversation repository
        mock_conversation = Mock()
        mock_conversation.id = 456
        service.conversation_repository.find_or_create_for_contact.return_value = mock_conversation
        
        result = service._get_or_create_conversation(123, 'conv_456')
        
        assert result == mock_conversation
        service.conversation_repository.find_or_create_for_contact.assert_called_once_with(
            contact_id=123,
            openphone_id='conv_456'
        )
    
    def _create_service(self):
        # Create mocks with sensible defaults
        activity_repo = Mock()
        activity_repo.find_by_openphone_id.return_value = None  # Default: no existing activity
        
        conversation_repo = Mock()
        webhook_repo = Mock()
        contact_service = Mock()
        metrics_service = Mock()
        
        return OpenPhoneWebhookServiceRefactored(
            activity_repository=activity_repo,
            conversation_repository=conversation_repo,
            webhook_event_repository=webhook_repo,
            contact_service=contact_service,
            sms_metrics_service=metrics_service
        )


class TestMainWebhookProcessorWithResult:
    """Test main webhook processor with Result pattern"""
    
    def test_process_webhook_returns_result_success(self):
        """Test main processor returns Result.success for valid webhooks"""
        service = self._create_service()
        
        # Mock successful webhook logging
        mock_webhook_event = Mock()
        service.webhook_event_repository.create.return_value = mock_webhook_event
        
        # Mock successful token validation
        with patch.object(service, '_handle_token_validation') as mock_handler:
            mock_handler.return_value = Result.success({'status': 'success', 'message': 'Token validated'})
            
            webhook_data = {'type': 'token.validated', 'data': {}}
            result = service.process_webhook(webhook_data)
        
        assert result.is_success
        assert result.data['status'] == 'success'
    
    def test_process_webhook_returns_result_failure_for_unknown_type(self):
        """Test processor returns Result.failure for unknown webhook types"""
        service = self._create_service()
        
        # Mock successful webhook logging
        service.webhook_event_repository.create.return_value = Mock()
        
        webhook_data = {'type': 'unknown.event.type', 'data': {}}
        result = service.process_webhook(webhook_data)
        
        assert result.is_failure
        assert 'Unknown event type' in result.error
        assert result.error_code == "UNKNOWN_EVENT_TYPE"
    
    def test_process_webhook_handles_handler_exceptions(self):
        """Test processor handles handler exceptions gracefully"""
        service = self._create_service()
        
        # Mock successful webhook logging
        service.webhook_event_repository.create.return_value = Mock()
        
        # Mock handler that raises exception
        with patch.object(service, '_handle_token_validation') as mock_handler:
            mock_handler.side_effect = Exception("Handler error")
            
            webhook_data = {'type': 'token.validated', 'data': {}}
            result = service.process_webhook(webhook_data)
        
        assert result.is_failure
        assert "Handler error" in result.error
        assert result.error_code == "PROCESSING_ERROR"
    
    def test_process_webhook_routes_to_correct_handlers(self):
        """Test webhook routing to correct handlers with Result pattern"""
        service = self._create_service()
        
        # Mock successful webhook logging
        service.webhook_event_repository.create.return_value = Mock()
        
        test_cases = [
            ('token.validated', '_handle_token_validation'),
            ('message.received', '_handle_message_webhook'),
            ('message.delivered', '_handle_message_webhook'),
            ('call.completed', '_handle_call_webhook'),
            ('call.recording.completed', '_handle_call_recording_webhook'),
            ('call.summary.completed', '_handle_call_summary_webhook'),
            ('call.transcript.completed', '_handle_call_transcript_webhook'),
        ]
        
        for event_type, expected_handler in test_cases:
            with patch.object(service, expected_handler) as mock_handler:
                mock_handler.return_value = Result.success({'status': 'test'})
                
                webhook_data = {'type': event_type, 'data': {}}
                result = service.process_webhook(webhook_data)
                
                assert result.is_success
                assert result.data['status'] == 'test'
                mock_handler.assert_called_once_with(webhook_data)
    
    def _create_service(self):
        # Create mocks with sensible defaults
        activity_repo = Mock()
        activity_repo.find_by_openphone_id.return_value = None  # Default: no existing activity
        
        conversation_repo = Mock()
        webhook_repo = Mock()
        contact_service = Mock()
        metrics_service = Mock()
        
        return OpenPhoneWebhookServiceRefactored(
            activity_repository=activity_repo,
            conversation_repository=conversation_repo,
            webhook_event_repository=webhook_repo,
            contact_service=contact_service,
            sms_metrics_service=metrics_service
        )


class TestRepositoryErrorHandling:
    """Test error handling for repository operations"""
    
    def test_activity_repository_error_handling(self):
        """Test activity repository errors are properly handled"""
        service = self._create_service()
        
        # Mock repository error
        service.activity_repository.find_by_openphone_id.side_effect = Exception("Repository error")
        
        webhook_data = {
            'type': 'message.received',
            'data': {
                'object': {
                    'id': 'msg_123',
                    'direction': 'incoming',
                    'from': '+1234567890'
                }
            }
        }
        
        result = service._handle_message_webhook(webhook_data)
        
        assert result.is_failure
        assert "Repository error" in str(result.error)
        assert result.error_code == "REPOSITORY_ERROR"
    
    def test_conversation_repository_error_handling(self):
        """Test conversation repository errors are properly handled"""
        service = self._create_service()
        
        # Mock NO existing activity so contact/conversation resolution is attempted
        service.activity_repository.find_by_openphone_id.return_value = None
        
        # Mock successful contact resolution
        mock_contact = Mock()
        mock_contact.id = 123
        service.contact_service.get_contact_by_phone.return_value = Result.success(mock_contact)
        
        # Mock conversation repository error
        service.conversation_repository.find_or_create_for_contact.side_effect = Exception("Conversation error")
        
        webhook_data = {
            'type': 'message.received',
            'data': {
                'object': {
                    'id': 'msg_123',
                    'direction': 'incoming',
                    'from': '+1234567890'
                }
            }
        }
        
        result = service._handle_message_webhook(webhook_data)
        
        assert result.is_failure
        assert "Conversation error" in str(result.error)
        assert result.error_code == "REPOSITORY_ERROR"
    
    def _create_service(self):
        # Create mocks with sensible defaults
        activity_repo = Mock()
        activity_repo.find_by_openphone_id.return_value = None  # Default: no existing activity
        
        conversation_repo = Mock()
        webhook_repo = Mock()
        contact_service = Mock()
        metrics_service = Mock()
        
        return OpenPhoneWebhookServiceRefactored(
            activity_repository=activity_repo,
            conversation_repository=conversation_repo,
            webhook_event_repository=webhook_repo,
            contact_service=contact_service,
            sms_metrics_service=metrics_service
        )