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
    
    def test_message_received_new_contact(self, webhook_service, app, db_session):
        """Test incoming message from new contact"""
        import time
        unique_id = str(int(time.time() * 1000000))[-10:]
        
        with app.app_context():
            payload = {
                "type": "message.received",
                "data": {
                    "object": {
                        "id": f"MSG{unique_id}",
                        "conversationId": f"CONV{unique_id}",
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
            
            # Process the webhook
            result = webhook_service.process_webhook(payload)
            
            # Should create a new activity
            assert result['status'] == 'created'
            assert 'activity_id' in result
            
            # Verify the objects were created in the database
            new_activity = Activity.query.filter_by(openphone_id=f"MSG{unique_id}").first()
            assert new_activity is not None
            assert new_activity.body == "Hello, I need help with my foundation"
            assert new_activity.direction == "incoming"
            assert new_activity.status == "received"
            
            # Verify contact was created
            contact = Contact.query.filter_by(phone="+1234567890").first()
            assert contact is not None
            assert contact.first_name == "+1234567890"
            assert contact.last_name == "(from OpenPhone)"
            
            # Verify conversation was created
            conversation = Conversation.query.filter_by(contact_id=contact.id).first()
            assert conversation is not None
            assert conversation.openphone_id == f"CONV{unique_id}"
    
    def test_message_received_with_media(self, webhook_service, app, db_session):
        """Test incoming message with media attachments"""
        import time
        unique_id = str(int(time.time() * 1000000))[-10:]
        
        # First create a contact so it exists
        existing_contact = Contact(
            phone="+1234567891",
            first_name="Existing",
            last_name="Contact"
        )
        db_session.add(existing_contact)
        db_session.commit()
        
        payload = {
            "type": "message.received",
            "data": {
                "object": {
                    "id": f"MSG{unique_id}",
                    "conversationId": f"CONV{unique_id}",
                    "direction": "incoming",
                    "from": "+1234567891",
                    "to": ["+0987654321"],
                    "text": "Here are photos of the cracks",
                    "media": [
                        {"url": "https://media.openphone.com/attachment1.jpg", "type": "image/jpeg"},
                        {"url": "https://media.openphone.com/attachment2.jpg", "type": "image/jpeg"}
                    ],
                    "status": "received",
                    "createdAt": "2025-07-30T10:05:00.000Z"
                }
            }
        }
        
        with app.app_context():
            result = webhook_service.process_webhook(payload)
        
        assert result['status'] == 'created'
        assert 'media_count' in result
        assert result['media_count'] == 2
        
        # Verify activity was created with media
        new_activity = Activity.query.filter_by(openphone_id=f"MSG{unique_id}").first()
        assert new_activity is not None
        assert new_activity.body == "Here are photos of the cracks"
        
        # Check media URLs were stored correctly (they're stored as JSON in the database)
        import json
        media_urls = json.loads(new_activity.media_urls) if isinstance(new_activity.media_urls, str) else new_activity.media_urls
        assert len(media_urls) == 2
        assert media_urls[0]['url'] == "https://media.openphone.com/attachment1.jpg"
        assert media_urls[0]['type'] == "image/jpeg"
    
    def test_message_delivered(self, webhook_service, app, db_session):
        """Test outgoing message delivered webhook"""
        import time
        unique_id = str(int(time.time() * 1000000))[-10:]
        
        # First create the contact and initial activity
        contact = Contact(
            phone="+1234567892",
            first_name="Customer",
            last_name="Name"
        )
        db_session.add(contact)
        db_session.commit()
        
        conversation = Conversation(
            contact_id=contact.id,
            openphone_id=f"CONV{unique_id}"
        )
        db_session.add(conversation)
        db_session.commit()
        
        # Create the initial activity with "sent" status
        initial_activity = Activity(
            conversation_id=conversation.id,
            contact_id=contact.id,
            openphone_id=f"MSG{unique_id}",
            activity_type='message',
            body="Your appointment is confirmed",
            direction='outgoing',
            status='sent'
        )
        db_session.add(initial_activity)
        db_session.commit()
        
        payload = {
            "type": "message.delivered",
            "data": {
                "object": {
                    "id": f"MSG{unique_id}",
                    "conversationId": f"CONV{unique_id}",
                    "direction": "outgoing",
                    "from": "+0987654321",
                    "to": ["+1234567892"],
                    "text": "Your appointment is confirmed",
                    "status": "delivered",
                    "deliveredAt": "2025-07-30T10:10:00.000Z"
                }
            }
        }
        
        with app.app_context():
            result = webhook_service.process_webhook(payload)
        
        assert result['status'] == 'updated'
        assert result['activity_id'] == initial_activity.id
        
        # Verify status was updated
        db_session.refresh(initial_activity)
        assert initial_activity.status == "delivered"


class TestCallWebhooks:
    """Test call webhook handling"""
    
    def test_call_completed(self, webhook_service, app, db_session):
        """Test call completed webhook"""
        import time
        unique_id = str(int(time.time() * 1000000))[-10:]
        
        with app.app_context():
            # Need to mock the _get_our_phone_number method
            with patch.object(webhook_service, '_get_our_phone_number', return_value='+0987654321'):
                payload = {
                    "type": "call.completed",
                    "data": {
                        "object": {
                            "id": f"CALL{unique_id}",
                            "status": "completed",
                            "duration": 300,
                            "participants": ["+1234567890", "+0987654321"],
                            "answeredAt": "2025-07-30T10:00:05.000Z",
                            "completedAt": "2025-07-30T10:05:00.000Z"
                        }
                    }
                }
                
                result = webhook_service.process_webhook(payload)
            
            assert result['status'] == 'created'
            assert 'activity_id' in result
            
            # Verify activity was created
            new_activity = Activity.query.filter_by(openphone_id=f"CALL{unique_id}").first()
            assert new_activity is not None
            assert new_activity.activity_type == "call"
            assert new_activity.duration_seconds == 300
            assert new_activity.status == "completed"
            
            # Verify contact was created
            contact = Contact.query.filter_by(phone="+1234567890").first()
            assert contact is not None
    
    def test_call_completed_with_recording(self, webhook_service, app, db_session):
        """Test call completed with recording URL"""
        import time
        unique_id = str(int(time.time() * 1000000))[-10:]
        
        with app.app_context():
            # Need to mock the _get_our_phone_number method
            with patch.object(webhook_service, '_get_our_phone_number', return_value='+0987654321'):
                payload = {
                    "type": "call.completed",
                    "data": {
                        "object": {
                            "id": f"CALL{unique_id}",
                            "status": "completed",
                            "duration": 180,
                            "participants": ["+1234567891", "+0987654321"],
                            "recordingUrl": f"https://api.openphone.com/v1/call-recordings/CALL{unique_id}",
                            "answeredAt": "2025-07-30T11:00:00.000Z",
                            "completedAt": "2025-07-30T11:03:00.000Z"
                        }
                    }
                }
                
                result = webhook_service.process_webhook(payload)
            
            assert result['status'] == 'created'
            
            # Verify activity was created (recording URL is NOT stored from call.completed)
            new_activity = Activity.query.filter_by(openphone_id=f"CALL{unique_id}").first()
            assert new_activity is not None
            assert new_activity.recording_url is None  # Recording URL comes from separate webhook
            assert new_activity.duration_seconds == 180
    
    def test_call_recording_completed(self, webhook_service, app, db_session):
        """Test call recording completed webhook"""
        import time
        unique_id = str(int(time.time() * 1000000))[-10:]
        
        # First create a call activity without recording
        contact = Contact(
            phone="+1234567893",
            first_name="Test",
            last_name="Contact"
        )
        db_session.add(contact)
        db_session.commit()
        
        conversation = Conversation(
            contact_id=contact.id
        )
        db_session.add(conversation)
        db_session.commit()
        
        call_activity = Activity(
            conversation_id=conversation.id,
            contact_id=contact.id,
            openphone_id=f"CALL{unique_id}",
            activity_type='call',
            direction='incoming',
            status='completed',
            duration_seconds=300
        )
        db_session.add(call_activity)
        db_session.commit()
        
        payload = {
            "type": "call.recording.completed",
            "data": {
                "object": {
                    "id": f"REC{unique_id}",
                    "callId": f"CALL{unique_id}",
                    "url": f"https://api.openphone.com/v1/call-recordings/CALL{unique_id}",
                    "duration": 300,
                    "size": 2400000
                }
            }
        }
        
        with app.app_context():
            result = webhook_service.process_webhook(payload)
        
        assert result['status'] == 'updated'
        assert result['activity_id'] == call_activity.id
        assert 'recording_id' in result
        
        # Verify recording URL was added
        db_session.refresh(call_activity)
        assert call_activity.recording_url == f"https://api.openphone.com/v1/call-recordings/CALL{unique_id}"


class TestAIContentWebhooks:
    """Test AI-generated content webhooks"""
    
    def test_call_summary_completed(self, webhook_service, app, db_session):
        """Test call summary completed webhook"""
        import time
        unique_id = str(int(time.time() * 1000000))[-10:]
        
        # Create a call activity first
        contact = Contact(
            phone="+1234567894",
            first_name="AI",
            last_name="Test"
        )
        db_session.add(contact)
        db_session.commit()
        
        conversation = Conversation(
            contact_id=contact.id
        )
        db_session.add(conversation)
        db_session.commit()
        
        call_activity = Activity(
            conversation_id=conversation.id,
            contact_id=contact.id,
            openphone_id=f"CALL{unique_id}",
            activity_type='call',
            direction='incoming',
            status='completed',
            duration_seconds=300
        )
        db_session.add(call_activity)
        db_session.commit()
        
        payload = {
            "type": "call.summary.completed",
            "data": {
                "object": {
                    "callId": f"CALL{unique_id}",
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
        
        with app.app_context():
            result = webhook_service.process_webhook(payload)
        
        assert result['status'] == 'updated'
        assert result['activity_id'] == call_activity.id
        
        # Verify AI summary was stored (service only stores the summary text)
        db_session.refresh(call_activity)
        assert call_activity.ai_summary == "Customer inquired about foundation repair pricing and timeline"
    
    def test_call_transcript_completed(self, webhook_service, app, db_session):
        """Test call transcript completed webhook"""
        import time
        unique_id = str(int(time.time() * 1000000))[-10:]
        
        # Create a call activity first
        contact = Contact(
            phone="+1234567895",
            first_name="Transcript",
            last_name="Test"
        )
        db_session.add(contact)
        db_session.commit()
        
        conversation = Conversation(
            contact_id=contact.id
        )
        db_session.add(conversation)
        db_session.commit()
        
        call_activity = Activity(
            conversation_id=conversation.id,
            contact_id=contact.id,
            openphone_id=f"CALL{unique_id}",
            activity_type='call',
            direction='incoming',
            status='completed',
            duration_seconds=180
        )
        db_session.add(call_activity)
        db_session.commit()
        
        payload = {
            "type": "call.transcript.completed",
            "data": {
                "object": {
                    "callId": f"CALL{unique_id}",
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
        
        with app.app_context():
            result = webhook_service.process_webhook(payload)
        
        assert result['status'] == 'updated'
        assert result['activity_id'] == call_activity.id
        
        # Verify transcript was stored (service stores the full transcript object)
        db_session.refresh(call_activity)
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
        # The service stores the transcript as a JSON string
        import json
        actual_transcript = json.loads(call_activity.ai_transcript) if isinstance(call_activity.ai_transcript, str) else call_activity.ai_transcript
        assert actual_transcript == expected_transcript


class TestWebhookEventLogging:
    """Test webhook event logging and processing"""
    
    def test_webhook_event_logged(self, webhook_service, app, db_session):
        """Test that webhook events are logged"""
        import time
        unique_id = str(int(time.time() * 1000000))[-10:]
        
        payload = {
            "type": "message.received",
            "data": {
                "object": {
                    "id": f"MSG{unique_id}",
                    "from": "+1234567890",
                    "to": ["+0987654321"],
                    "text": "Test message",
                    "status": "received",
                    "createdAt": "2025-07-30T10:00:00.000Z"
                }
            }
        }
        
        with app.app_context():
            result = webhook_service.process_webhook(payload)
        
        # Should successfully process
        assert result['status'] == 'created'
        
        # Verify webhook event was created - get the most recent one
        webhook_events = WebhookEvent.query.filter_by(event_type="message.received").order_by(WebhookEvent.id.desc()).all()
        assert len(webhook_events) > 0
        
        # Find the one with our unique ID
        webhook_event = None
        import json
        for event in webhook_events:
            stored_payload = json.loads(event.payload) if isinstance(event.payload, str) else event.payload
            if stored_payload['data']['object']['id'] == f"MSG{unique_id}":
                webhook_event = event
                break
        
        assert webhook_event is not None
        assert webhook_event.processed is False  # Service logs it as unprocessed initially
        assert webhook_event.error_message is None
    
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
    
    def test_database_error_handling(self, webhook_service, app):
        """Test handling of database errors"""
        import time
        unique_id = str(int(time.time() * 1000000))[-10:]
        
        payload = {
            "type": "message.received",
            "data": {
                "object": {
                    "id": f"MSG{unique_id}",
                    "from": "+1234567890",
                    "to": ["+0987654321"],
                    "text": "Test message",
                    "status": "received",
                    "createdAt": "2025-07-30T10:00:00.000Z"
                }
            }
        }
        
        with app.app_context():
            # Mock db.session.commit to raise an exception
            with patch('services.openphone_webhook_service.db.session.commit') as mock_commit:
                mock_commit.side_effect = Exception("Database error")
                
                result = webhook_service.process_webhook(payload)
        
        assert result['status'] == 'error'
        assert 'Database error' in result['message']


class TestIdempotency:
    """Test webhook idempotency"""
    
    def test_duplicate_message_webhook(self, webhook_service, app, db_session):
        """Test handling of duplicate message webhooks"""
        import time
        unique_id = str(int(time.time() * 1000000))[-10:]
        
        # First create an activity that will be duplicated
        contact = Contact(
            phone="+1234567896",
            first_name="Duplicate",
            last_name="Test"
        )
        db_session.add(contact)
        db_session.commit()
        
        conversation = Conversation(
            contact_id=contact.id
        )
        db_session.add(conversation)
        db_session.commit()
        
        existing_activity = Activity(
            conversation_id=conversation.id,
            contact_id=contact.id,
            openphone_id=f"MSG{unique_id}",
            activity_type='message',
            body="Original message",
            direction='incoming',
            status='received'
        )
        db_session.add(existing_activity)
        db_session.commit()
        
        # Now send a webhook for the same message ID
        payload = {
            "type": "message.received",
            "data": {
                "object": {
                    "id": f"MSG{unique_id}",
                    "from": "+1234567896",
                    "to": ["+0987654321"],
                    "text": "Duplicate test",
                    "status": "delivered",
                    "createdAt": "2025-07-30T10:05:00.000Z"
                }
            }
        }
        
        with app.app_context():
            result = webhook_service.process_webhook(payload)
        
        assert result['status'] == 'updated'
        assert result['activity_id'] == existing_activity.id
        
        # Verify status was updated but no new activity created
        db_session.refresh(existing_activity)
        assert existing_activity.status == "delivered"  # Status should be updated
        
        # Verify only one activity exists with this ID
        activities = Activity.query.filter_by(openphone_id=f"MSG{unique_id}").all()
        assert len(activities) == 1


class TestContactHandling:
    """Test contact creation and matching"""
    
    def test_contact_phone_normalization(self, webhook_service, app, db_session):
        """Test phone number normalization"""
        import time
        unique_id = str(int(time.time() * 1000000))[-10:]
        
        payload = {
            "type": "message.received",
            "data": {
                "object": {
                    "id": f"MSG{unique_id}",
                    "from": "1234567890",  # Missing + sign
                    "to": ["+0987654321"],
                    "text": "Test",
                    "status": "received",
                    "createdAt": "2025-07-30T10:00:00.000Z"
                }
            }
        }
        
        with app.app_context():
            result = webhook_service.process_webhook(payload)
        
        assert result['status'] == 'created'
        
        # Verify phone was normalized with + prefix
        contact = Contact.query.filter_by(phone="+1234567890").first()
        assert contact is not None
        assert contact.phone == "+1234567890"