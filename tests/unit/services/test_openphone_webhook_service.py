"""
Comprehensive Unit Tests for OpenPhoneWebhookServiceRefactored

Tests all webhook event types, repository interactions, error handling,
and edge cases following TDD principles with proper dependency injection.
"""

import pytest
import json
from unittest.mock import Mock, patch, MagicMock, call, ANY
from datetime import datetime
from services.openphone_webhook_service_refactored import OpenPhoneWebhookServiceRefactored
from services.common.result import Result
from crm_database import Contact, Conversation, Activity, WebhookEvent
# Comment out factory imports until factory_boy is installed
# from tests.fixtures.factories.webhook_event_factory import WebhookEventFactory
# from tests.fixtures.factories.contact_factory import ContactFactory
# from tests.fixtures.factories.conversation_factory import ConversationFactory
# from tests.fixtures.factories.activity_factory import ActivityFactory


def create_webhook_service_with_mocks():
    """Helper function to create service with mocked dependencies"""
    mock_activity_repo = Mock()
    mock_conversation_repo = Mock()
    mock_webhook_repo = Mock()
    mock_contact_repo = Mock()  # Add missing contact repository
    mock_appointment_repo = Mock()  # Add missing appointment repository
    mock_contact_service = Mock()
    mock_sms_metrics_service = Mock()
    
    # Mock the create method to return a webhook event
    mock_webhook_event = Mock()
    mock_webhook_event.id = 123
    mock_webhook_repo.create.return_value = mock_webhook_event
    
    service = OpenPhoneWebhookServiceRefactored(
        activity_repository=mock_activity_repo,
        conversation_repository=mock_conversation_repo,
        webhook_event_repository=mock_webhook_repo,
        contact_service=mock_contact_service,
        sms_metrics_service=mock_sms_metrics_service
    )
    
    # Attach mocks to service for test access
    service._mock_activity_repo = mock_activity_repo
    service._mock_conversation_repo = mock_conversation_repo
    service._mock_webhook_repo = mock_webhook_repo
    service._mock_contact_repo = mock_contact_repo
    service._mock_appointment_repo = mock_appointment_repo
    service._mock_contact_service = mock_contact_service
    service._mock_sms_metrics_service = mock_sms_metrics_service
    
    return service


class TestOpenPhoneWebhookServiceRefactoredInitialization:
    """Test service initialization and dependency injection"""
    
    def test_service_instantiation(self):
        """Test that service can be instantiated with dependencies"""
        service = create_webhook_service_with_mocks()
        
        # Verify dependencies are set up
        assert service.contact_service is not None
        assert service.sms_metrics_service is not None
        assert hasattr(service, 'contact_service')
        assert hasattr(service, 'sms_metrics_service')
    
    def test_service_has_required_methods(self):
        """Test that service has all required public methods"""
        service = create_webhook_service_with_mocks()
        
        # Verify public interface
        assert hasattr(service, 'process_webhook')
        assert callable(service.process_webhook)
        
        # Verify private methods exist
        assert hasattr(service, '_handle_message_webhook')
        assert hasattr(service, '_handle_call_webhook')
        assert hasattr(service, '_handle_call_recording_webhook')
        assert hasattr(service, '_handle_call_summary_webhook')
        assert hasattr(service, '_handle_call_transcript_webhook')


class TestWebhookEventLogging:
    """Test webhook event logging functionality"""
    
    def test_webhook_event_logging_success(self):
        """Test successful webhook event logging"""
        service = create_webhook_service_with_mocks()
        webhook_data = {'type': 'message.received', 'data': {}}  # WebhookEventFactory.build().payload
        
        result = service._log_webhook_event(webhook_data)
        
        # Verify result is successful
        assert result.is_success
        
        # Verify repository was called with correct data
        service._mock_webhook_repo.create.assert_called_once()
        call_args = service._mock_webhook_repo.create.call_args[1]
        assert call_args['event_type'] == 'message.received'
        assert call_args['payload'] == webhook_data
        assert call_args['processed'] == False
    
    @patch('services.openphone_webhook_service_refactored.logger')
    def test_webhook_event_logging_database_error(self, mock_logger):
        """Test webhook event logging handles database errors gracefully"""
        service = create_webhook_service_with_mocks()
        webhook_data = {'type': 'test.event'}
        
        # Simulate repository error
        service._mock_webhook_repo.create.side_effect = Exception("Database error")
        
        # Should return failure result
        result = service._log_webhook_event(webhook_data)
        
        assert result.is_failure
        assert 'Failed to log webhook event' in result.error
        
        # Verify error was logged
        mock_logger.error.assert_called_once()
    
    def test_webhook_event_logging_with_missing_type(self):
        """Test webhook event logging with missing event type"""
        service = create_webhook_service_with_mocks()
        webhook_data = {}  # Missing 'type' field
        
        result = service._log_webhook_event(webhook_data)
        
        # Verify result is successful
        assert result.is_success
        
        # Verify repository was called with 'unknown' type
        service._mock_webhook_repo.create.assert_called_once()
        call_args = service._mock_webhook_repo.create.call_args[1]
        assert call_args['event_type'] == 'unknown'


class TestTokenValidationWebhooks:
    """Test token validation webhook handling"""
    
    def test_handle_token_validation_success(self):
        """Test successful token validation webhook"""
        service = create_webhook_service_with_mocks()
        webhook_data = {
            'type': 'token.validated',
            'data': {'valid': True}
        }
        
        result = service._handle_token_validation(webhook_data)
        
        assert result.is_success
        assert result.data['status'] == 'success'
        assert result.data['message'] == 'Token validated'
    
    @patch('services.openphone_webhook_service_refactored.logger')
    def test_token_validation_logs_info(self, mock_logger):
        """Test that token validation logs info message"""
        service = create_webhook_service_with_mocks()
        webhook_data = {'type': 'token.validated'}
        
        service._handle_token_validation(webhook_data)
        
        mock_logger.info.assert_called_with("Token validation webhook received")


class TestMessageWebhooks:
    """Test message webhook handling with repository pattern"""
    
    def setup_method(self):
        """Set up mocks for each test"""
        self.mock_contact_service = Mock()
        self.mock_metrics_service = Mock()
        self.mock_contact = Mock()
        self.mock_contact.id = 123
        self.mock_conversation = Mock()
        self.mock_conversation.id = 456
        
    def test_message_received_creates_new_activity(self):
        """Test that message.received creates new activity when none exists"""
        service = create_webhook_service_with_mocks()
        
        # Mock no existing activity in repository
        service._mock_activity_repo.find_by_openphone_id.return_value = None
        
        # Mock successful contact creation
        mock_contact = Mock()
        mock_contact.id = 123
        service._mock_contact_service.get_contact_by_phone.return_value = Result.failure('not found')
        service._mock_contact_service.add_contact.return_value = Result.success(mock_contact)
        
        # Mock conversation creation
        mock_conversation = Mock()
        mock_conversation.id = 456
        service._mock_conversation_repo.find_or_create_for_contact.return_value = mock_conversation
        
        # Mock activity creation
        mock_new_activity = Mock()
        mock_new_activity.id = 789
        service._mock_activity_repo.create.return_value = mock_new_activity
        
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
                    'media': [],
                    'status': 'received',
                    'createdAt': '2025-07-30T10:00:00.000Z'
                }
            }
        }
        
        result = service._handle_message_webhook(webhook_data)
        
        # Verify result
        assert result.is_success
        assert result.data['status'] == 'created'
        assert result.data['activity_id'] == 789
        assert result.data['media_count'] == 0
        
        # Verify repository calls
        service._mock_activity_repo.find_by_openphone_id.assert_called_once_with('msg_123')
        service._mock_contact_service.add_contact.assert_called_once()
        service._mock_conversation_repo.find_or_create_for_contact.assert_called_once_with(
            contact_id=123, openphone_id='conv_456'
        )
        service._mock_activity_repo.create.assert_called_once()
    
    def test_message_delivered_updates_existing_activity(self):
        """Test that message.delivered updates existing activity status"""
        service = create_webhook_service_with_mocks()
        
        # Mock existing activity
        mock_existing_activity = Mock()
        mock_existing_activity.id = 789
        mock_existing_activity.status = 'sent'
        mock_existing_activity.direction = 'outgoing'
        service._mock_activity_repo.find_by_openphone_id.return_value = mock_existing_activity
        service._mock_activity_repo.update.return_value = mock_existing_activity
        
        webhook_data = {
            'type': 'message.delivered',
            'data': {
                'object': {
                    'id': 'msg_123',
                    'status': 'delivered'
                }
            }
        }
        
        result = service._handle_message_webhook(webhook_data)
        
        # Verify result
        assert result.is_success
        assert result.data['status'] == 'updated'
        assert result.data['activity_id'] == 789
        
        # Verify repository calls
        service._mock_activity_repo.find_by_openphone_id.assert_called_once_with('msg_123')
        service._mock_activity_repo.update.assert_called_once_with(
            789, status='delivered', updated_at=ANY  # Allow any datetime
        )
        
        # Verify metrics were tracked
        service._mock_sms_metrics_service.track_message_status.assert_called_once_with(789, 'delivered')
    
    def test_message_failed_tracks_error_metrics(self):
        """Test that failed message status tracks error metrics"""
        service = create_webhook_service_with_mocks()
        
        # Mock existing activity
        mock_existing_activity = Mock()
        mock_existing_activity.id = 789
        mock_existing_activity.direction = 'outgoing'
        service._mock_activity_repo.find_by_openphone_id.return_value = mock_existing_activity
        service._mock_activity_repo.update.return_value = mock_existing_activity
        
        webhook_data = {
            'type': 'message.failed',
            'data': {
                'object': {
                    'id': 'msg_123',
                    'status': 'failed',
                    'errorMessage': 'Invalid phone number'
                }
            }
        }
        
        result = service._handle_message_webhook(webhook_data)
        
        # Verify result is successful
        assert result.is_success
        assert result.data['status'] == 'updated'
        
        # Verify error metrics were tracked
        service._mock_sms_metrics_service.track_message_status.assert_called_once_with(
            789, 'failed', 'Invalid phone number'
        )
    
    def test_message_webhook_missing_data_object(self):
        """Test message webhook handling with missing data object"""
        service = create_webhook_service_with_mocks()
        
        webhook_data = {
            'type': 'message.received',
            'data': {}  # Missing 'object' key
        }
        
        result = service._handle_message_webhook(webhook_data)
        
        assert result.is_failure
        assert 'No message data provided' in result.error
    
    def test_message_with_media_attachments(self):
        """Test message webhook with media attachments"""
        service = create_webhook_service_with_mocks()
        
        # Mock no existing activity
        service._mock_activity_repo.find_by_openphone_id.return_value = None
        
        # Mock successful contact creation
        mock_contact = Mock()
        mock_contact.id = 123
        service._mock_contact_service.get_contact_by_phone.return_value = Result.failure('not found')
        service._mock_contact_service.add_contact.return_value = Result.success(mock_contact)
        
        # Mock conversation creation
        mock_conversation = Mock()
        mock_conversation.id = 456
        service._mock_conversation_repo.find_or_create_for_contact.return_value = mock_conversation
        
        # Mock activity creation
        mock_new_activity = Mock()
        mock_new_activity.id = 789
        service._mock_activity_repo.create.return_value = mock_new_activity
        
        webhook_data = {
            'type': 'message.received',
            'data': {
                'object': {
                    'id': 'msg_123',
                    'direction': 'incoming',
                    'from': '+1234567890',
                    'to': ['+0987654321'],
                    'text': 'Check out these photos',
                    'media': [
                        {'url': 'https://example.com/photo1.jpg', 'type': 'image/jpeg'},
                        {'url': 'https://example.com/photo2.jpg', 'type': 'image/jpeg'}
                    ],
                    'status': 'received'
                }
            }
        }
        
        result = service._handle_message_webhook(webhook_data)
        
        assert result.is_success
        assert result.data['status'] == 'created'
        assert result.data['media_count'] == 2


class TestCallWebhooks:
    """Test call webhook handling"""
    
    def setup_method(self):
        """Set up mocks for each test"""
        self.mock_contact = Mock()
        self.mock_contact.id = 123
        self.mock_conversation = Mock()
        self.mock_conversation.id = 456
    
    def test_call_completed_creates_new_activity(self):
        """Test that call.completed creates new call activity"""
        service = create_webhook_service_with_mocks()
        
        # Mock no existing activity
        service._mock_activity_repo.find_by_openphone_id.return_value = None
        
        # Mock successful contact creation
        mock_contact = Mock()
        mock_contact.id = 123
        service._mock_contact_service.get_contact_by_phone.return_value = Result.failure('not found')
        service._mock_contact_service.add_contact.return_value = Result.success(mock_contact)
        
        # Mock conversation creation
        mock_conversation = Mock()
        mock_conversation.id = 456
        service._mock_conversation_repo.find_or_create_for_contact.return_value = mock_conversation
        
        # Mock activity creation
        mock_new_activity = Mock()
        mock_new_activity.id = 789
        mock_new_activity.created_at = datetime.now()
        service._mock_activity_repo.create.return_value = mock_new_activity
        
        with patch.object(service, '_get_our_phone_number', return_value='+0987654321'), \
             patch.object(service, '_fetch_call_recording_async'):
            
            webhook_data = {
                'type': 'call.completed',
                'data': {
                    'object': {
                        'id': 'call_123',
                        'direction': 'incoming',
                        'status': 'completed',
                        'duration': 300,
                        'participants': ['+1234567890', '+0987654321'],
                        'answeredAt': '2025-07-30T10:00:05.000Z',
                        'completedAt': '2025-07-30T10:05:00.000Z'
                    }
                }
            }
            
            result = service._handle_call_webhook(webhook_data)
            
            assert result.is_success
            assert result.data['status'] == 'created'
            assert result.data['activity_id'] == 789
            
            # Verify repository calls
            service._mock_activity_repo.find_by_openphone_id.assert_called_once_with('call_123')
            service._mock_contact_service.add_contact.assert_called_once()
            service._mock_conversation_repo.find_or_create_for_contact.assert_called_once_with(contact_id=123, openphone_id=None)
            service._mock_activity_repo.create.assert_called_once()
            
            # Verify async recording fetch was triggered
            service._fetch_call_recording_async.assert_called_once()
    
    def test_call_completed_updates_existing_activity(self):
        """Test that call.completed updates existing call activity"""
        service = create_webhook_service_with_mocks()
        
        # Mock existing activity
        mock_existing_activity = Mock()
        mock_existing_activity.id = 789
        service._mock_activity_repo.find_by_openphone_id.return_value = mock_existing_activity
        service._mock_activity_repo.update.return_value = mock_existing_activity
        
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
        
        result = service._handle_call_webhook(webhook_data)
        
        assert result.is_success
        assert result.data['status'] == 'updated'
        assert result.data['activity_id'] == 789
        
        # Verify repository calls
        service._mock_activity_repo.find_by_openphone_id.assert_called_once_with('call_123')
        service._mock_activity_repo.update.assert_called_once_with(
            789, status='completed', duration_seconds=450, updated_at=ANY
        )
    
    def test_call_webhook_missing_participants(self):
        """Test call webhook handling with missing participants"""
        service = create_webhook_service_with_mocks()
        
        # Mock no existing activity
        service._mock_activity_repo.find_by_openphone_id.return_value = None
        
        webhook_data = {
            'type': 'call.completed',
            'data': {
                'object': {
                    'id': 'call_123',
                    'participants': []  # Empty participants list
                }
            }
        }
        
        result = service._handle_call_webhook(webhook_data)
        
        assert result.is_failure
        assert 'No participants in call data' in result.error
    
    def test_call_webhook_cannot_determine_contact_phone(self):
        """Test call webhook when contact phone cannot be determined"""
        service = create_webhook_service_with_mocks()
        
        # Mock no existing activity
        service._mock_activity_repo.find_by_openphone_id.return_value = None
        
        with patch.object(service, '_get_our_phone_number', return_value='+0987654321'):
            webhook_data = {
                'type': 'call.completed',
                'data': {
                    'object': {
                        'id': 'call_123',
                        'participants': ['+0987654321']  # Only our number
                    }
                }
            }
            
            result = service._handle_call_webhook(webhook_data)
            
            assert result.is_failure
            assert 'Could not determine contact phone' in result.error


class TestCallRecordingWebhooks:
    """Test call recording webhook handling"""
    
    def test_call_recording_completed_updates_activity(self):
        """Test that call.recording.completed updates call activity"""
        service = create_webhook_service_with_mocks()
        
        # Mock existing call activity
        mock_call_activity = Mock()
        mock_call_activity.id = 789
        service._mock_activity_repo.find_by_openphone_id.return_value = mock_call_activity
        service._mock_activity_repo.update.return_value = mock_call_activity
        
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
        
        # Verify repository calls
        service._mock_activity_repo.find_by_openphone_id.assert_called_once_with('call_123')
        service._mock_activity_repo.update.assert_called_once_with(
            789, 
            recording_url='https://recordings.openphone.com/call_123.mp3',
            duration_seconds=300,
            updated_at=ANY
        )
    
    def test_call_recording_webhook_missing_call_id(self):
        """Test call recording webhook with missing call ID"""
        service = create_webhook_service_with_mocks()
        
        webhook_data = {
            'type': 'call.recording.completed',
            'data': {
                'object': {
                    'id': 'rec_123',
                    'url': 'https://recordings.openphone.com/recording.mp3'
                    # Missing 'callId'
                }
            }
        }
        
        result = service._handle_call_recording_webhook(webhook_data)
        
        assert result.is_failure
        assert 'Missing call ID or recording URL' in result.error
    
    @patch('services.openphone_webhook_service_refactored.logger')
    def test_call_recording_webhook_call_not_found(self, mock_logger):
        """Test call recording webhook when call activity not found"""
        service = create_webhook_service_with_mocks()
        
        # Mock no existing call activity
        service._mock_activity_repo.find_by_openphone_id.return_value = None
        
        webhook_data = {
            'type': 'call.recording.completed',
            'data': {
                'object': {
                    'callId': 'call_123',
                    'url': 'https://recordings.openphone.com/call_123.mp3'
                }
            }
        }
        
        result = service._handle_call_recording_webhook(webhook_data)
        
        # After webhook service improvement, missing calls return success with 'skipped' status
        assert result.is_success
        assert result.data['status'] == 'skipped'
        assert result.data['reason'] == 'call_activity_not_found'
        assert result.data['call_id'] == 'call_123'
        # Verify appropriate warning was logged
        mock_logger.warning.assert_called_with('Call activity not found for call ID: call_123. This is likely a recording for a call made before webhook setup.')


class TestAIContentWebhooks:
    """Test AI-generated content webhooks (summaries and transcripts)"""
    
    def test_call_summary_completed_updates_activity(self):
        """Test that call.summary.completed updates call activity"""
        service = create_webhook_service_with_mocks()
        
        # Mock existing call activity
        mock_call_activity = Mock()
        mock_call_activity.id = 789
        service._mock_activity_repo.find_by_openphone_id.return_value = mock_call_activity
        service._mock_activity_repo.update.return_value = mock_call_activity
        
        webhook_data = {
            'type': 'call.summary.completed',
            'data': {
                'object': {
                    'callId': 'call_123',
                    'summary': 'Customer called about foundation repair pricing',
                    'keyPoints': ['Foundation cracks visible', 'Needs estimate'],
                    'sentiment': 'positive'
                }
            }
        }
        
        result = service._handle_call_summary_webhook(webhook_data)
        
        assert result.is_success
        assert result.data['status'] == 'updated'
        assert result.data['activity_id'] == 789
        
        # Verify repository calls
        service._mock_activity_repo.find_by_openphone_id.assert_called_once_with('call_123')
        service._mock_activity_repo.update.assert_called_once_with(
            789,
            ai_summary='Customer called about foundation repair pricing',
            updated_at=ANY
        )
    
    def test_call_transcript_completed_updates_activity(self):
        """Test that call.transcript.completed updates call activity"""
        service = create_webhook_service_with_mocks()
        
        # Mock existing call activity
        mock_call_activity = Mock()
        mock_call_activity.id = 789
        service._mock_activity_repo.find_by_openphone_id.return_value = mock_call_activity
        service._mock_activity_repo.update.return_value = mock_call_activity
        
        transcript_data = {
            'dialogue': [
                {'speaker': 'Agent', 'text': 'Hello, how can I help?', 'timestamp': '00:00:02'},
                {'speaker': 'Customer', 'text': 'I need foundation repair', 'timestamp': '00:00:05'}
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
        
        # Verify repository calls
        service._mock_activity_repo.find_by_openphone_id.assert_called_once_with('call_123')
        service._mock_activity_repo.update.assert_called_once_with(
            789,
            ai_transcript=transcript_data,
            updated_at=ANY
        )
    
    def test_call_summary_webhook_missing_data(self):
        """Test call summary webhook with missing required data"""
        service = create_webhook_service_with_mocks()
        
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
    
    def test_call_transcript_webhook_missing_data(self):
        """Test call transcript webhook with missing required data"""
        service = create_webhook_service_with_mocks()
        
        webhook_data = {
            'type': 'call.transcript.completed',
            'data': {
                'object': {
                    'callId': 'call_123'
                    # Missing 'transcript'
                }
            }
        }
        
        result = service._handle_call_transcript_webhook(webhook_data)
        
        assert result.is_failure
        assert 'Missing call ID or transcript' in result.error


class TestContactAndConversationManagement:
    """Test contact and conversation creation/retrieval"""
    
    def test_get_or_create_contact_existing_contact(self):
        """Test getting existing contact by phone number"""
        service = create_webhook_service_with_mocks()
        
        # Mock existing contact
        mock_existing_contact = Mock()
        service._mock_contact_service.get_contact_by_phone.return_value = Result.success(mock_existing_contact)
        
        result = service._get_or_create_contact('+1234567890')
        
        assert result.is_success
        assert result.data == mock_existing_contact
        service._mock_contact_service.get_contact_by_phone.assert_called_once_with('+1234567890')
        service._mock_contact_service.add_contact.assert_not_called()
    
    def test_get_or_create_contact_new_contact(self):
        """Test creating new contact when none exists"""
        service = create_webhook_service_with_mocks()
        
        # Mock no existing contact
        service._mock_contact_service.get_contact_by_phone.return_value = Result.failure('Contact not found')
        
        # Mock new contact creation
        mock_new_contact = Mock()
        service._mock_contact_service.add_contact.return_value = Result.success(mock_new_contact)
        
        result = service._get_or_create_contact('+1234567890')
        
        assert result.is_success
        assert result.data == mock_new_contact
        service._mock_contact_service.add_contact.assert_called_once_with(
            first_name='+1234567890',
            last_name='(from OpenPhone)',
            phone='+1234567890'
        )
    
    def test_get_or_create_conversation_by_openphone_id(self):
        """Test getting conversation by OpenPhone ID"""
        service = create_webhook_service_with_mocks()
        
        # Mock existing conversation
        mock_existing_conversation = Mock()
        service._mock_conversation_repo.find_or_create_for_contact.return_value = mock_existing_conversation
        
        result = service._get_or_create_conversation(123, 'conv_456')
        
        assert result == mock_existing_conversation
        service._mock_conversation_repo.find_or_create_for_contact.assert_called_with(
            contact_id=123, openphone_id='conv_456'
        )
    
    def test_get_or_create_conversation_by_contact_id(self):
        """Test getting conversation by contact ID when OpenPhone ID not found"""
        service = create_webhook_service_with_mocks()
        
        # Mock conversation with no OpenPhone ID that gets updated
        mock_existing_conversation = Mock()
        mock_existing_conversation.openphone_id = None
        service._mock_conversation_repo.find_or_create_for_contact.return_value = mock_existing_conversation
        
        result = service._get_or_create_conversation(123, 'conv_456')
        
        assert result == mock_existing_conversation
        service._mock_conversation_repo.find_or_create_for_contact.assert_called_with(
            contact_id=123, openphone_id='conv_456'
        )
    
    def test_get_or_create_conversation_creates_new(self):
        """Test creating new conversation when none exists"""
        service = create_webhook_service_with_mocks()
        
        # Mock new conversation creation
        mock_new_conversation = Mock()
        service._mock_conversation_repo.find_or_create_for_contact.return_value = mock_new_conversation
        
        result = service._get_or_create_conversation(123, 'conv_456')
        
        assert result == mock_new_conversation
        service._mock_conversation_repo.find_or_create_for_contact.assert_called_with(
            contact_id=123, openphone_id='conv_456'
        )


class TestTimestampParsing:
    """Test timestamp parsing functionality"""
    
    def test_parse_timestamp_valid_iso_format(self):
        """Test parsing valid ISO timestamp"""
        service = create_webhook_service_with_mocks()
        
        timestamp_str = "2025-07-30T10:00:00.000Z"
        result = service._parse_timestamp(timestamp_str)
        
        assert result is not None
        assert isinstance(result, datetime)
        assert result.year == 2025
        assert result.month == 7
        assert result.day == 30
    
    def test_parse_timestamp_empty_string(self):
        """Test parsing empty timestamp string"""
        service = create_webhook_service_with_mocks()
        
        result = service._parse_timestamp("")
        assert result is None
        
        result = service._parse_timestamp(None)
        assert result is None
    
    @patch('services.openphone_webhook_service_refactored.logger')
    def test_parse_timestamp_invalid_format(self, mock_logger):
        """Test parsing invalid timestamp format"""
        service = create_webhook_service_with_mocks()
        
        result = service._parse_timestamp("invalid-timestamp")
        
        assert result is None
        mock_logger.error.assert_called_once()
    
    def test_parse_timestamp_various_formats(self):
        """Test parsing various valid timestamp formats"""
        service = create_webhook_service_with_mocks()
        
        # Test with milliseconds
        result1 = service._parse_timestamp("2025-07-30T10:00:00.123Z")
        assert result1 is not None
        
        # Test without milliseconds
        result2 = service._parse_timestamp("2025-07-30T10:00:00Z")
        assert result2 is not None


class TestPhoneNumberHandling:
    """Test phone number handling and configuration"""
    
    def test_get_our_phone_number_from_config(self):
        """Test getting our phone number from Flask config"""
        service = create_webhook_service_with_mocks()
        
        with patch('flask.current_app') as mock_app:
            # Ensure the mock returns a plain value, not a coroutine
            mock_config = Mock()
            mock_config.get = Mock(return_value='+14155551000')
            mock_app.config = mock_config
            
            result = service._get_our_phone_number()
            
            assert result == '+14155551000'
            mock_config.get.assert_called_once_with('OPENPHONE_PHONE_NUMBER', '')
    
    def test_get_our_phone_number_default_empty(self):
        """Test getting our phone number when config is empty"""
        service = create_webhook_service_with_mocks()
        
        with patch('flask.current_app') as mock_app:
            # Ensure the mock returns a plain value, not a coroutine
            mock_config = Mock()
            mock_config.get = Mock(return_value='')
            mock_app.config = mock_config
            
            result = service._get_our_phone_number()
            
            assert result == ''


class TestAsyncCallRecordingFetch:
    """Test async call recording fetch functionality"""
    
    @patch('services.openphone_webhook_service_refactored.logger')
    def test_fetch_call_recording_async_placeholder(self, mock_logger):
        """Test that async recording fetch logs intent (placeholder implementation)"""
        service = create_webhook_service_with_mocks()
        
        service._fetch_call_recording_async(123, 'call_456')
        
        mock_logger.info.assert_called_with(
            'Should fetch recording for call call_456 (activity 123)'
        )


class TestErrorHandlingAndEdgeCases:
    """Test comprehensive error handling and edge cases"""
    
    def test_process_webhook_unknown_event_type(self):
        """Test processing webhook with unknown event type"""
        service = create_webhook_service_with_mocks()
        
        webhook_data = {
            'type': 'unknown.event.type',
            'data': {}
        }
        
        result = service.process_webhook(webhook_data)
        
        assert result.is_failure
        assert 'Unknown event type: unknown.event.type' in result.error
    
    def test_process_webhook_missing_event_type(self):
        """Test processing webhook with missing event type"""
        service = create_webhook_service_with_mocks()
        
        webhook_data = {'data': {}}  # Missing 'type' field
        
        result = service.process_webhook(webhook_data)
        
        assert result.is_failure
        assert 'Unknown event type: ' in result.error
    
    @patch('services.openphone_webhook_service_refactored.logger')
    def test_process_webhook_exception_handling(self, mock_logger):
        """Test that webhook processing handles exceptions gracefully"""
        service = create_webhook_service_with_mocks()
        
        webhook_data = {'type': 'message.received'}
        
        # Mock _handle_message_webhook to raise exception
        with patch.object(service, '_handle_message_webhook', side_effect=Exception("Test error")):
            result = service.process_webhook(webhook_data)
        
        assert result.is_failure
        assert 'Test error' in result.error
        mock_logger.error.assert_called_once()
    
    def test_process_webhook_routes_to_correct_handlers(self):
        """Test that webhook routing works correctly for all event types"""
        service = create_webhook_service_with_mocks()
        
        test_cases = [
            ('token.validated', '_handle_token_validation'),
            ('message.received', '_handle_message_webhook'),
            ('message.delivered', '_handle_message_webhook'),
            ('message.failed', '_handle_message_webhook'),
            ('call.completed', '_handle_call_webhook'),
            ('call.missed', '_handle_call_webhook'),
            ('call.recording.completed', '_handle_call_recording_webhook'),
            ('call.summary.completed', '_handle_call_summary_webhook'),
            ('call.transcript.completed', '_handle_call_transcript_webhook'),
        ]
        
        for event_type, expected_handler in test_cases:
            webhook_data = {'type': event_type, 'data': {}}
            
            with patch.object(service, expected_handler, return_value=Result.success({'status': 'test'})):
                result = service.process_webhook(webhook_data)
                assert result.is_success
                assert result.data['status'] == 'test'
                getattr(service, expected_handler).assert_called_once_with(webhook_data)


class TestIdempotencyAndDuplicateHandling:
    """Test idempotency and duplicate event handling"""
    
    def test_duplicate_message_webhook_idempotency(self):
        """Test that duplicate message webhooks are handled idempotently"""
        service = create_webhook_service_with_mocks()
        
        # Mock existing activity
        mock_existing_activity = Mock()
        mock_existing_activity.id = 789
        mock_existing_activity.status = 'sent'
        mock_existing_activity.direction = 'outgoing'
        service._mock_activity_repo.find_by_openphone_id.return_value = mock_existing_activity
        service._mock_activity_repo.update.return_value = mock_existing_activity
        
        webhook_data = {
            'type': 'message.delivered',
            'data': {
                'object': {
                    'id': 'msg_123',  # Same ID as existing activity
                    'status': 'delivered'
                }
            }
        }
        
        # Process the same webhook twice
        result1 = service._handle_message_webhook(webhook_data)
        result2 = service._handle_message_webhook(webhook_data)
        
        # Both should return the same updated activity
        assert result1.is_success
        assert result2.is_success
        assert result1.data['status'] == 'updated'
        assert result2.data['status'] == 'updated'
        assert result1.data['activity_id'] == result2.data['activity_id'] == 789
    
    def test_duplicate_call_webhook_idempotency(self):
        """Test that duplicate call webhooks are handled idempotently"""
        service = create_webhook_service_with_mocks()
        
        # Mock existing call activity
        mock_existing_activity = Mock()
        mock_existing_activity.id = 789
        service._mock_activity_repo.find_by_openphone_id.return_value = mock_existing_activity
        service._mock_activity_repo.update.return_value = mock_existing_activity
        
        webhook_data = {
            'type': 'call.completed',
            'data': {
                'object': {
                    'id': 'call_123',
                    'status': 'completed',
                    'duration': 300
                }
            }
        }
        
        # Process the same webhook twice
        result1 = service._handle_call_webhook(webhook_data)
        result2 = service._handle_call_webhook(webhook_data)
        
        # Both should return the same updated activity
        assert result1.is_success
        assert result2.is_success
        assert result1.data['status'] == 'updated'
        assert result2.data['status'] == 'updated'
        assert result1.data['activity_id'] == result2.data['activity_id'] == 789


class TestWebhookIntegrationScenarios:
    """Test realistic webhook integration scenarios"""
    
    def test_complete_message_conversation_flow(self):
        """Test complete message conversation flow"""
        service = create_webhook_service_with_mocks()
        
        # Mock contact and conversation
        mock_contact = Mock()
        mock_contact.id = 123
        mock_conversation = Mock()
        mock_conversation.id = 456
        
        # Mock service dependencies
        service._mock_contact_service.get_contact_by_phone.return_value = Result.failure('not found')
        service._mock_contact_service.add_contact.return_value = Result.success(mock_contact)
        service._mock_conversation_repo.find_or_create_for_contact.return_value = mock_conversation
        
        # 1. Incoming message received - no existing activity
        service._mock_activity_repo.find_by_openphone_id.return_value = None
        mock_incoming_activity = Mock()
        mock_incoming_activity.id = 111
        service._mock_activity_repo.create.return_value = mock_incoming_activity
        
        incoming_webhook = {
            'type': 'message.received',
            'data': {
                'object': {
                    'id': 'msg_incoming_123',
                    'direction': 'incoming',
                    'from': '+1234567890',
                    'to': ['+0987654321'],
                    'text': 'I need foundation repair',
                    'status': 'received'
                }
            }
        }
        
        result1 = service._handle_message_webhook(incoming_webhook)
        assert result1.is_success
        assert result1.data['status'] == 'created'
        
        # 2. Outgoing message sent - no existing activity
        service._mock_activity_repo.find_by_openphone_id.return_value = None
        mock_outgoing_activity = Mock()
        mock_outgoing_activity.id = 222
        service._mock_activity_repo.create.return_value = mock_outgoing_activity
        
        outgoing_webhook = {
            'type': 'message.received',  # OpenPhone sends this for outgoing too
            'data': {
                'object': {
                    'id': 'msg_outgoing_124',
                    'direction': 'outgoing',
                    'from': '+0987654321',
                    'to': ['+1234567890'],
                    'text': 'Thanks! We can help with that.',
                    'status': 'sent'
                }
            }
        }
        
        result2 = service._handle_message_webhook(outgoing_webhook)
        assert result2.is_success
        assert result2.data['status'] == 'created'
        
        # 3. Delivery confirmation for outgoing message - existing activity
        mock_existing_outgoing = Mock()
        mock_existing_outgoing.id = 789
        mock_existing_outgoing.direction = 'outgoing'
        service._mock_activity_repo.find_by_openphone_id.return_value = mock_existing_outgoing
        service._mock_activity_repo.update.return_value = mock_existing_outgoing
        
        delivery_webhook = {
            'type': 'message.delivered',
            'data': {
                'object': {
                    'id': 'msg_outgoing_124',
                    'status': 'delivered'
                }
            }
        }
        
        result3 = service._handle_message_webhook(delivery_webhook)
        assert result3.is_success
        assert result3.data['status'] == 'updated'
        assert result3.data['activity_id'] == 789
    
    def test_factory_generated_webhook_data(self):
        """Test processing webhook data generated by WebhookEventFactory"""
        service = create_webhook_service_with_mocks()
        
        # Use factory to generate realistic webhook data
        webhook_event = {'type': 'message.received', 'data': {}}  # WebhookEventFactory.build(is_message_received=True)
        webhook_data = webhook_event  # .payload
        
        with patch.object(service, '_handle_message_webhook', return_value=Result.success({'status': 'created'})):
            result = service.process_webhook(webhook_data)
            
            assert result.is_success
            assert result.data['status'] == 'created'
            service._handle_message_webhook.assert_called_once_with(webhook_data)
    
    def test_webhook_sequence_with_factory_data(self):
        """Test processing a sequence of webhooks using factory data"""
        service = create_webhook_service_with_mocks()
        
        # Generate a conversation thread using factory (placeholder for now)
        conversation_id = 'conv_test_123'
        webhook_events = []  # WebhookEventFactory.create_message_thread(
        #     conversation_id=conversation_id,
        #     message_count=3
        # )
        
        # Mock three webhook events for testing
        webhook_events = [
            {'type': 'message.received', 'data': {'object': {'id': 'msg1'}}},
            {'type': 'message.received', 'data': {'object': {'id': 'msg2'}}},
            {'type': 'message.received', 'data': {'object': {'id': 'msg3'}}},
        ]
        
        results = []
        with patch.object(service, '_handle_message_webhook', return_value=Result.success({'status': 'processed'})):
            for webhook_event in webhook_events:
                result = service.process_webhook(webhook_event)
                results.append(result)
        
        # All webhooks should be processed
        assert len(results) == 3
        assert all(r.is_success and r.data['status'] == 'processed' for r in results)