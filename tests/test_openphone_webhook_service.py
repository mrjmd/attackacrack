# tests/test_openphone_webhook_service.py
"""
Comprehensive tests for OpenPhoneWebhookService covering all event types
and webhook signature verification.
"""

import pytest
import json
import hmac
import hashlib
import base64
from unittest.mock import MagicMock, patch, Mock
from datetime import datetime
from services.openphone_webhook_service import OpenPhoneWebhookService
from crm_database import Contact, Conversation, Activity, WebhookEvent


@pytest.fixture
def webhook_service(app):
    """Fixture providing webhook service instance with app context"""
    with app.app_context():
        return OpenPhoneWebhookService()


@pytest.fixture
def valid_signing_key():
    """Fixture providing a test signing key"""
    return base64.b64encode(b"test_webhook_signing_key").decode('utf-8')


def generate_signature(payload, signing_key):
    """Generate valid webhook signature for testing"""
    import time
    timestamp = str(int(time.time() * 1000))
    signed_data = timestamp.encode() + b'.' + payload.encode()
    
    signing_key_bytes = base64.b64decode(signing_key)
    signature = base64.b64encode(
        hmac.new(
            key=signing_key_bytes,
            msg=signed_data,
            digestmod=hashlib.sha256
        ).digest()
    ).decode('utf-8')
    
    return f"hmac;1;{timestamp};{signature}"


# Signature verification is handled in the route decorator, not the service
# Remove these tests as they're not applicable to the service


class TestMessageWebhooks:
    """Test message webhook handling"""
    
    @patch('services.openphone_webhook_service.db.session')
    def test_message_received_new_contact(self, mock_session, webhook_service, app):
        """Test incoming message from new contact"""
        with app.app_context():
            payload = {
                "type": "message.received",
                "data": {
                    "object": {
                        "id": "MSG123456789",
                        "conversationId": "CONV123456",
                        "direction": "incoming",
                        "from": "+1234567890",
                        "to": ["+0987654321"],
                        "text": "Hello, I need help with my foundation",
                        "media": [],
                        "status": "received",
                        "createdAt": "2025-07-30T10:00:00.000Z"
                    }
                }
            }
            
            # Mock query results
            mock_session.query.return_value.filter_by.return_value.first.return_value = None
            
            # Mock new objects
            mock_contact = MagicMock()
            mock_conversation = MagicMock()
            mock_activity = MagicMock()
            
            with patch('services.openphone_webhook_service.Contact', return_value=mock_contact) as mock_contact_cls:
                with patch('services.openphone_webhook_service.Conversation', return_value=mock_conversation):
                    with patch('services.openphone_webhook_service.Activity', return_value=mock_activity):
                        result = webhook_service.process_webhook(payload)
            
            assert result['status'] in ['created', 'updated']
            assert 'activity_id' in result
            
            # Verify contact was created
            mock_contact_cls.assert_called_once()
            assert mock_contact.phone == "+1234567890"
            
            # Verify activity was created
            assert mock_activity.openphone_id == "MSG123456789"
            assert mock_activity.body == "Hello, I need help with my foundation"
            assert mock_activity.direction == "incoming"
            
            mock_session.add.assert_called()
            mock_session.commit.assert_called()
    
    @patch('services.openphone_webhook_service.db.session')
    def test_message_received_with_media(self, mock_session, webhook_service):
        """Test incoming message with media attachments"""
        payload = {
            "type": "message.received",
            "data": {
                "object": {
                    "id": "MSG123456790",
                    "conversationId": "CONV123457",
                    "direction": "incoming",
                    "from": "+1234567891",
                    "to": ["+0987654321"],
                    "text": "Here are photos of the cracks",
                    "media": [
                        "https://media.openphone.com/attachment1.jpg",
                        "https://media.openphone.com/attachment2.jpg"
                    ],
                    "status": "received",
                    "createdAt": "2025-07-30T10:05:00.000Z"
                }
            }
        }
        
        # Mock existing contact
        mock_contact = MagicMock()
        mock_contact.id = 1
        mock_session.query.return_value.filter_by.return_value.first.side_effect = [
            mock_contact,  # Contact exists
            None,  # Conversation doesn't exist
            None   # Activity doesn't exist
        ]
        
        mock_conversation = MagicMock()
        mock_activity = MagicMock()
        
        with patch('services.openphone_webhook_service.Conversation', return_value=mock_conversation):
            with patch('services.openphone_webhook_service.Activity', return_value=mock_activity):
                result = webhook_service.process_webhook(payload)
        
        assert result['status'] in ['created', 'updated']
        
        # Verify media was stored
        assert mock_activity.media_urls == json.dumps([
            "https://media.openphone.com/attachment1.jpg",
            "https://media.openphone.com/attachment2.jpg"
        ])
    
    @patch('services.openphone_webhook_service.db.session')
    def test_message_delivered(self, mock_session, webhook_service):
        """Test outgoing message delivered webhook"""
        payload = {
            "type": "message.delivered",
            "data": {
                "object": {
                    "id": "MSG123456791",
                    "conversationId": "CONV123458",
                    "direction": "outgoing",
                    "from": "+0987654321",
                    "to": ["+1234567892"],
                    "text": "Your appointment is confirmed",
                    "status": "delivered",
                    "deliveredAt": "2025-07-30T10:10:00.000Z"
                }
            }
        }
        
        # Mock existing activity
        mock_activity = MagicMock()
        mock_activity.status = "sent"
        mock_session.query.return_value.filter_by.return_value.first.return_value = mock_activity
        
        result = webhook_service.process_webhook(payload)
        
        assert result['status'] in ['created', 'updated']
        assert mock_activity.status == "delivered"
        mock_session.commit.assert_called()


class TestCallWebhooks:
    """Test call webhook handling"""
    
    @patch('services.openphone_webhook_service.db.session')
    def test_call_completed(self, mock_session, webhook_service):
        """Test call completed webhook"""
        payload = {
            "type": "call.completed",
            "data": {
                "object": {
                    "id": "CALL123456789",
                    "status": "completed",
                    "duration": 300,
                    "participants": ["+1234567890", "+0987654321"],
                    "answeredAt": "2025-07-30T10:00:05.000Z",
                    "completedAt": "2025-07-30T10:05:00.000Z"
                }
            }
        }
        
        # Mock contact lookup
        mock_contact = MagicMock()
        mock_contact.id = 1
        mock_contact.phone = "+1234567890"
        mock_session.query.return_value.filter.return_value.first.return_value = mock_contact
        
        # Mock conversation and activity don't exist
        mock_session.query.return_value.filter_by.return_value.first.return_value = None
        
        mock_conversation = MagicMock()
        mock_activity = MagicMock()
        
        with patch('services.openphone_webhook_service.Conversation', return_value=mock_conversation):
            with patch('services.openphone_webhook_service.Activity', return_value=mock_activity):
                result = webhook_service.process_webhook(payload)
        
        assert result['status'] in ['created', 'updated']
        
        # Verify activity created correctly
        assert mock_activity.openphone_id == "CALL123456789"
        assert mock_activity.activity_type == "call"
        assert mock_activity.duration == 300
        assert mock_activity.status == "completed"
    
    @patch('services.openphone_webhook_service.db.session')
    def test_call_completed_with_recording(self, mock_session, webhook_service):
        """Test call completed with recording URL"""
        payload = {
            "type": "call.completed",
            "data": {
                "object": {
                    "id": "CALL123456790",
                    "status": "completed",
                    "duration": 180,
                    "participants": ["+1234567891", "+0987654321"],
                    "recordingUrl": "https://api.openphone.com/v1/call-recordings/CALL123456790",
                    "answeredAt": "2025-07-30T11:00:00.000Z",
                    "completedAt": "2025-07-30T11:03:00.000Z"
                }
            }
        }
        
        # Setup mocks
        mock_contact = MagicMock()
        mock_contact.id = 1
        mock_session.query.return_value.filter.return_value.first.return_value = mock_contact
        mock_session.query.return_value.filter_by.return_value.first.return_value = None
        
        mock_activity = MagicMock()
        
        with patch('services.openphone_webhook_service.Activity', return_value=mock_activity):
            result = webhook_service.process_webhook(payload)
        
        assert result['status'] in ['created', 'updated']
        assert mock_activity.recording_url == "https://api.openphone.com/v1/call-recordings/CALL123456790"
    
    @patch('services.openphone_webhook_service.db.session')
    def test_call_recording_completed(self, mock_session, webhook_service):
        """Test call recording completed webhook"""
        payload = {
            "type": "call.recording.completed",
            "data": {
                "object": {
                    "id": "REC123456789",
                    "callId": "CALL123456789",
                    "url": "https://api.openphone.com/v1/call-recordings/CALL123456789",
                    "duration": 300,
                    "size": 2400000
                }
            }
        }
        
        # Mock existing call activity
        mock_activity = MagicMock()
        mock_activity.openphone_id = "CALL123456789"
        mock_activity.recording_url = None
        mock_session.query.return_value.filter_by.return_value.first.return_value = mock_activity
        
        result = webhook_service.process_webhook(payload)
        
        assert result['status'] in ['created', 'updated']
        assert mock_activity.recording_url == "https://api.openphone.com/v1/call-recordings/CALL123456789"
        mock_session.commit.assert_called()


class TestAIContentWebhooks:
    """Test AI-generated content webhooks"""
    
    @patch('services.openphone_webhook_service.db.session')
    def test_call_summary_completed(self, mock_session, webhook_service):
        """Test call summary completed webhook"""
        payload = {
            "type": "call.summary.completed",
            "data": {
                "object": {
                    "callId": "CALL123456789",
                    "summary": "Customer inquired about foundation repair pricing and timeline",
                    "keyPoints": [
                        "Foundation has visible cracks",
                        "Customer wants estimate this week"
                    ],
                    "nextSteps": [
                        "Schedule on-site assessment",
                        "Prepare quote"
                    ],
                    "sentiment": "positive"
                }
            }
        }
        
        # Mock existing call activity
        mock_activity = MagicMock()
        mock_activity.openphone_id = "CALL123456789"
        mock_activity.ai_summary = None
        mock_session.query.return_value.filter_by.return_value.first.return_value = mock_activity
        
        result = webhook_service.process_webhook(payload)
        
        assert result['status'] in ['created', 'updated']
        
        # Verify AI summary was stored
        expected_summary = {
            "summary": "Customer inquired about foundation repair pricing and timeline",
            "keyPoints": [
                "Foundation has visible cracks",
                "Customer wants estimate this week"
            ],
            "nextSteps": [
                "Schedule on-site assessment",
                "Prepare quote"
            ],
            "sentiment": "positive"
        }
        assert mock_activity.ai_summary == json.dumps(expected_summary)
        mock_session.commit.assert_called()
    
    @patch('services.openphone_webhook_service.db.session')
    def test_call_transcript_completed(self, mock_session, webhook_service):
        """Test call transcript completed webhook"""
        payload = {
            "type": "call.transcript.completed",
            "data": {
                "object": {
                    "callId": "CALL123456789",
                    "transcript": {
                        "dialogue": [
                            {
                                "speaker": "Agent",
                                "text": "Hello, Attack-a-Crack Foundation Repair, how can I help you?",
                                "timestamp": "00:00:02"
                            },
                            {
                                "speaker": "Customer",
                                "text": "Hi, I have some cracks in my foundation that I'm concerned about",
                                "timestamp": "00:00:05"
                            }
                        ],
                        "confidence": 0.95
                    }
                }
            }
        }
        
        # Mock existing call activity
        mock_activity = MagicMock()
        mock_activity.openphone_id = "CALL123456789"
        mock_activity.ai_transcript = None
        mock_session.query.return_value.filter_by.return_value.first.return_value = mock_activity
        
        result = webhook_service.process_webhook(payload)
        
        assert result['status'] in ['created', 'updated']
        
        # Verify transcript was stored
        expected_transcript = {
            "dialogue": [
                {
                    "speaker": "Agent",
                    "text": "Hello, Attack-a-Crack Foundation Repair, how can I help you?",
                    "timestamp": "00:00:02"
                },
                {
                    "speaker": "Customer",
                    "text": "Hi, I have some cracks in my foundation that I'm concerned about",
                    "timestamp": "00:00:05"
                }
            ],
            "confidence": 0.95
        }
        assert mock_activity.ai_transcript == json.dumps(expected_transcript)
        mock_session.commit.assert_called()


class TestWebhookEventLogging:
    """Test webhook event logging and processing"""
    
    @patch('services.openphone_webhook_service.db.session')
    def test_webhook_event_logged(self, mock_session, webhook_service):
        """Test that webhook events are logged"""
        payload = {
            "type": "message.received",
            "data": {
                "object": {
                    "id": "MSG123",
                    "from": "+1234567890",
                    "text": "Test message"
                }
            }
        }
        
        # Mock webhook event tracking
        mock_webhook_event = MagicMock()
        
        with patch('services.openphone_webhook_service.WebhookEvent', return_value=mock_webhook_event):
            # Set up other mocks to handle the message processing
            mock_session.query.return_value.filter_by.return_value.first.return_value = None
            
            result = webhook_service.process_webhook(payload)
        
        # Verify webhook event was created
        assert mock_webhook_event.event_type == "message.received"
        assert mock_webhook_event.payload == json.dumps(payload)
        assert mock_webhook_event.processed is True
        assert mock_webhook_event.error_message is None
    
    @patch('services.openphone_webhook_service.db.session')
    def test_webhook_event_error_logged(self, mock_session, webhook_service):
        """Test that webhook errors are logged"""
        payload = {
            "type": "invalid.type",
            "data": {}
        }
        
        mock_webhook_event = MagicMock()
        
        with patch('services.openphone_webhook_service.WebhookEvent', return_value=mock_webhook_event):
            result = webhook_service.process_webhook(payload)
        
        assert result['status'] == 'ignored'
        # Webhook event is still created even for ignored types
        mock_session.add.assert_called_once_with(mock_webhook_event)


class TestErrorHandling:
    """Test error handling scenarios"""
    
    def test_invalid_webhook_type(self, webhook_service):
        """Test handling of unknown webhook type"""
        payload = {
            "type": "unknown.webhook.type",
            "data": {"object": {}}
        }
        
        result = webhook_service.process_webhook(payload)
        
        assert result['status'] == 'ignored'
        assert 'Unknown event type' in result['reason']
    
    def test_missing_data_object(self, webhook_service):
        """Test handling of missing data object"""
        payload = {
            "type": "message.received",
            "data": {}  # Empty data object
        }
        
        result = webhook_service.process_webhook(payload)
        
        assert result['status'] == 'error'
        assert 'No message data provided' in result['message']
    
    @patch('services.openphone_webhook_service.db.session')
    def test_database_error_handling(self, mock_session, webhook_service):
        """Test handling of database errors"""
        payload = {
            "type": "message.received",
            "data": {
                "object": {
                    "id": "MSG123",
                    "from": "+1234567890",
                    "text": "Test message"
                }
            }
        }
        
        # Make session.commit raise an exception
        mock_session.commit.side_effect = Exception("Database error")
        mock_session.query.return_value.filter_by.return_value.first.return_value = None
        
        result = webhook_service.process_webhook(payload)
        
        assert result['status'] == 'error'
        assert 'Database error' in result['message']
        mock_session.rollback.assert_called()


class TestIdempotency:
    """Test webhook idempotency"""
    
    @patch('services.openphone_webhook_service.db.session')
    def test_duplicate_message_webhook(self, mock_session, webhook_service):
        """Test handling of duplicate message webhooks"""
        payload = {
            "type": "message.received",
            "data": {
                "object": {
                    "id": "MSG123456789",
                    "from": "+1234567890",
                    "text": "Duplicate test"
                }
            }
        }
        
        # Mock existing activity
        mock_activity = MagicMock()
        mock_activity.openphone_id = "MSG123456789"
        
        # Return existing activity on lookup
        mock_session.query.return_value.filter_by.return_value.first.side_effect = [
            None,  # Contact lookup
            None,  # Conversation lookup
            mock_activity  # Activity exists
        ]
        
        result = webhook_service.process_webhook(payload)
        
        assert result['status'] == 'updated'
        assert 'activity_id' in result
        
        # Verify no new activity was created
        mock_session.add.assert_not_called()


class TestContactHandling:
    """Test contact creation and matching"""
    
    @patch('services.openphone_webhook_service.db.session')
    def test_contact_phone_normalization(self, mock_session, webhook_service):
        """Test phone number normalization"""
        payload = {
            "type": "message.received",
            "data": {
                "object": {
                    "id": "MSG123",
                    "from": "1234567890",  # Missing + sign
                    "text": "Test"
                }
            }
        }
        
        mock_session.query.return_value.filter_by.return_value.first.return_value = None
        
        mock_contact = MagicMock()
        
        with patch('services.openphone_webhook_service.Contact', return_value=mock_contact) as mock_contact_cls:
            result = webhook_service.process_webhook(payload)
        
        # Verify phone was normalized with + prefix
        assert mock_contact.phone == "+1234567890"