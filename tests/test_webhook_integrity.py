"""
Webhook integrity test harness for OpenPhoneWebhookService.
Tests all supported webhook event types with comprehensive validation.
"""
import pytest
import json
import hmac
import hashlib
import base64
from datetime import datetime, UTC
from unittest.mock import Mock, patch, MagicMock

from services.openphone_webhook_service import OpenPhoneWebhookService
from crm_database import Contact, Activity, Conversation
from extensions import db


class TestWebhookIntegrity:
    """Comprehensive test harness for webhook handling."""
    
    @pytest.fixture
    def webhook_service(self):
        """Create webhook service instance."""
        return OpenPhoneWebhookService()
    
    @pytest.fixture
    def signing_key(self, app):
        """Set up webhook signing key."""
        key = "test_webhook_signing_key_123"
        app.config['OPENPHONE_WEBHOOK_SIGNING_KEY'] = key
        return key
    
    def generate_signature(self, payload: dict, signing_key: str) -> str:
        """Generate valid webhook signature."""
        payload_str = json.dumps(payload, separators=(',', ':'))
        signature = hmac.new(
            signing_key.encode('utf-8'),
            payload_str.encode('utf-8'),
            hashlib.sha256
        ).digest()
        return base64.b64encode(signature).decode('utf-8')
    
    def create_webhook_payload(self, event_type: str, data: dict) -> dict:
        """Create a properly formatted webhook payload."""
        return {
            "id": f"webhook_{event_type}_123",
            "object": "webhook",
            "createdAt": datetime.now(UTC).isoformat(),
            "type": event_type,
            "data": data
        }
    
    @pytest.fixture
    def sample_contact(self):
        """Create a sample contact for testing."""
        contact = Contact(
            openphone_contact_id="CN123456",
            first_name="Test",
            last_name="User",
            phone="+12345678900",
            email="test@example.com"
        )
        db.session.add(contact)
        db.session.commit()
        return contact
    
    def test_message_created_webhook(self, webhook_service, sample_contact):
        """Test message.created webhook handling."""
        payload = self.create_webhook_payload("message.created", {
            "object": "message",
            "id": "MSG123",
            "conversationId": "CONV123",
            "body": "Hello, this is a test message",
            "from": "+12345678900",
            "to": ["+19876543210"],
            "direction": "incoming",
            "createdAt": datetime.now(UTC).isoformat(),
            "userId": None,
            "media": []
        })
        
        result = webhook_service.handle_webhook(payload)
        
        assert result['success'] is True
        assert result['action'] == 'message_created'
        
        # Verify activity created
        activity = Activity.query.filter_by(
            openphone_activity_id="MSG123"
        ).first()
        assert activity is not None
        assert activity.type == 'sms'
        assert activity.direction == 'incoming'
        assert activity.body == "Hello, this is a test message"
        assert activity.contact_id == sample_contact.id
        
        # Verify conversation
        conversation = Conversation.query.filter_by(
            openphone_conversation_id="CONV123"
        ).first()
        assert conversation is not None
        assert conversation.contact_id == sample_contact.id
    
    def test_message_with_media_webhook(self, webhook_service, sample_contact):
        """Test message webhook with media attachments."""
        media_items = [
            {
                "type": "image",
                "url": "https://example.com/image1.jpg",
                "mimeType": "image/jpeg"
            },
            {
                "type": "video",
                "url": "https://example.com/video1.mp4",
                "mimeType": "video/mp4"
            }
        ]
        
        payload = self.create_webhook_payload("message.created", {
            "object": "message",
            "id": "MSG_MEDIA_123",
            "conversationId": "CONV123",
            "body": "Check out these files",
            "from": "+12345678900",
            "to": ["+19876543210"],
            "direction": "incoming",
            "createdAt": datetime.now(UTC).isoformat(),
            "media": media_items
        })
        
        result = webhook_service.handle_webhook(payload)
        
        assert result['success'] is True
        assert 'media_count' in result
        assert result['media_count'] == 2
        
        # Verify media URLs stored
        activity = Activity.query.filter_by(
            openphone_activity_id="MSG_MEDIA_123"
        ).first()
        assert activity.media_urls is not None
        assert len(activity.media_urls) == 2
        assert any("image1.jpg" in url for url in activity.media_urls)
        assert any("video1.mp4" in url for url in activity.media_urls)
    
    def test_message_updated_webhook(self, webhook_service, sample_contact):
        """Test message.updated webhook handling."""
        # First create a message
        original_payload = self.create_webhook_payload("message.created", {
            "object": "message",
            "id": "MSG_UPDATE_123",
            "conversationId": "CONV123",
            "body": "Original message",
            "from": "+12345678900",
            "to": ["+19876543210"],
            "direction": "incoming",
            "createdAt": datetime.now(UTC).isoformat()
        })
        webhook_service.handle_webhook(original_payload)
        
        # Now update it
        update_payload = self.create_webhook_payload("message.updated", {
            "object": "message",
            "id": "MSG_UPDATE_123",
            "conversationId": "CONV123",
            "body": "Updated message content",
            "from": "+12345678900",
            "to": ["+19876543210"],
            "direction": "incoming",
            "updatedAt": datetime.now(UTC).isoformat()
        })
        
        result = webhook_service.handle_webhook(update_payload)
        
        assert result['success'] is True
        assert result['action'] == 'message_updated'
        
        # Verify update
        activity = Activity.query.filter_by(
            openphone_activity_id="MSG_UPDATE_123"
        ).first()
        assert activity.body == "Updated message content"
    
    def test_call_completed_webhook(self, webhook_service, sample_contact):
        """Test call.completed webhook handling."""
        payload = self.create_webhook_payload("call.completed", {
            "object": "call",
            "id": "CALL123",
            "conversationId": "CONV_CALL_123",
            "from": "+12345678900",
            "to": "+19876543210",
            "direction": "incoming",
            "status": "completed",
            "duration": 180,  # 3 minutes
            "createdAt": datetime.now(UTC).isoformat(),
            "completedAt": datetime.now(UTC).isoformat(),
            "answeredAt": datetime.now(UTC).isoformat(),
            "recordingUrl": "https://example.com/recording.mp3",
            "recordingDurationMs": 180000,
            "summary": {
                "content": "Customer called about service inquiry",
                "highlights": ["Interested in quarterly service", "Lives in Oakland"],
                "nextSteps": ["Send quote", "Schedule follow-up"]
            },
            "transcript": {
                "dialogue": [
                    {
                        "speaker": "customer",
                        "text": "Hi, I need pest control service",
                        "timestamp": 0
                    },
                    {
                        "speaker": "agent", 
                        "text": "I can help you with that",
                        "timestamp": 5000
                    }
                ]
            }
        })
        
        result = webhook_service.handle_webhook(payload)
        
        assert result['success'] is True
        assert result['action'] == 'call_completed'
        
        # Verify call activity created
        activity = Activity.query.filter_by(
            openphone_activity_id="CALL123"
        ).first()
        assert activity is not None
        assert activity.type == 'call'
        assert activity.direction == 'incoming'
        assert activity.call_duration == 180
        assert activity.recording_url == "https://example.com/recording.mp3"
        
        # Verify AI content stored
        assert activity.ai_summary is not None
        assert activity.ai_summary['content'] == "Customer called about service inquiry"
        assert len(activity.ai_summary['highlights']) == 2
        assert len(activity.ai_summary['nextSteps']) == 2
        
        assert activity.ai_transcript is not None
        assert len(activity.ai_transcript['dialogue']) == 2
    
    def test_call_recording_completed_webhook(self, webhook_service):
        """Test call.recording.completed webhook handling."""
        # First create a call activity
        call_activity = Activity(
            openphone_activity_id="CALL_REC_123",
            type="call",
            direction="outgoing",
            from_number="+19876543210",
            to_number="+12345678900",
            created_at=datetime.now(UTC)
        )
        db.session.add(call_activity)
        db.session.commit()
        
        payload = self.create_webhook_payload("call.recording.completed", {
            "object": "recording",
            "callId": "CALL_REC_123",
            "url": "https://recordings.openphone.com/call123.mp3",
            "durationMs": 240000,  # 4 minutes
            "createdAt": datetime.now(UTC).isoformat()
        })
        
        result = webhook_service.handle_webhook(payload)
        
        assert result['success'] is True
        assert result['action'] == 'recording_completed'
        
        # Verify recording URL updated
        activity = Activity.query.filter_by(
            openphone_activity_id="CALL_REC_123"
        ).first()
        assert activity.recording_url == "https://recordings.openphone.com/call123.mp3"
        assert activity.recording_duration_ms == 240000
    
    def test_contact_created_webhook(self, webhook_service):
        """Test contact.created webhook handling."""
        payload = self.create_webhook_payload("contact.created", {
            "object": "contact",
            "id": "CN_NEW_123",
            "name": "John Doe",
            "firstName": "John",
            "lastName": "Doe", 
            "phoneNumbers": [
                {
                    "id": "PN123",
                    "number": "+13335557777",
                    "type": "mobile"
                }
            ],
            "emails": ["john.doe@example.com"],
            "customFields": [
                {
                    "id": "CF123",
                    "name": "Company",
                    "value": "Acme Corp"
                }
            ],
            "createdAt": datetime.now(UTC).isoformat()
        })
        
        result = webhook_service.handle_webhook(payload)
        
        assert result['success'] is True
        assert result['action'] == 'contact_created'
        
        # Verify contact created
        contact = Contact.query.filter_by(
            openphone_contact_id="CN_NEW_123"
        ).first()
        assert contact is not None
        assert contact.first_name == "John"
        assert contact.last_name == "Doe"
        assert contact.phone == "+13335557777"
        assert contact.email == "john.doe@example.com"
    
    def test_contact_updated_webhook(self, webhook_service, sample_contact):
        """Test contact.updated webhook handling."""
        payload = self.create_webhook_payload("contact.updated", {
            "object": "contact",
            "id": sample_contact.openphone_contact_id,
            "name": "Test Updated User",
            "firstName": "Test Updated",
            "lastName": "User",
            "phoneNumbers": [
                {
                    "id": "PN123",
                    "number": "+13335558888",
                    "type": "mobile"
                }
            ],
            "emails": ["updated@example.com"],
            "updatedAt": datetime.now(UTC).isoformat()
        })
        
        result = webhook_service.handle_webhook(payload)
        
        assert result['success'] is True
        assert result['action'] == 'contact_updated'
        
        # Verify contact updated
        updated_contact = Contact.query.get(sample_contact.id)
        assert updated_contact.first_name == "Test Updated"
        assert updated_contact.phone == "+13335558888"
        assert updated_contact.email == "updated@example.com"
    
    def test_webhook_deduplication(self, webhook_service, sample_contact):
        """Test that duplicate webhooks are handled properly."""
        payload = self.create_webhook_payload("message.created", {
            "object": "message",
            "id": "MSG_DUP_123",
            "conversationId": "CONV123",
            "body": "Duplicate test",
            "from": "+12345678900",
            "to": ["+19876543210"],
            "direction": "incoming",
            "createdAt": datetime.now(UTC).isoformat()
        })
        
        # Process webhook twice
        result1 = webhook_service.handle_webhook(payload)
        result2 = webhook_service.handle_webhook(payload)
        
        assert result1['success'] is True
        assert result2['success'] is True
        
        # Verify only one activity created
        activities = Activity.query.filter_by(
            openphone_activity_id="MSG_DUP_123"
        ).all()
        assert len(activities) == 1
    
    def test_webhook_error_handling(self, webhook_service):
        """Test webhook error handling for malformed data."""
        # Missing required fields
        payload = self.create_webhook_payload("message.created", {
            "object": "message",
            "id": "MSG_ERROR_123"
            # Missing required fields like body, from, etc.
        })
        
        result = webhook_service.handle_webhook(payload)
        
        assert result['success'] is False
        assert 'error' in result
        
        # Verify no partial data saved
        activity = Activity.query.filter_by(
            openphone_activity_id="MSG_ERROR_123"
        ).first()
        assert activity is None
    
    def test_webhook_unknown_contact_handling(self, webhook_service):
        """Test webhook handling for unknown contacts."""
        payload = self.create_webhook_payload("message.created", {
            "object": "message",
            "id": "MSG_UNKNOWN_123",
            "conversationId": "CONV_NEW_123",
            "body": "Message from unknown number",
            "from": "+19998887777",  # Unknown number
            "to": ["+19876543210"],
            "direction": "incoming",
            "createdAt": datetime.now(UTC).isoformat()
        })
        
        result = webhook_service.handle_webhook(payload)
        
        assert result['success'] is True
        
        # Verify new contact created
        contact = Contact.query.filter_by(
            phone="+19998887777"
        ).first()
        assert contact is not None
        assert contact.first_name == "Unknown"
        assert contact.source == "webhook"
        
        # Verify activity linked to new contact
        activity = Activity.query.filter_by(
            openphone_activity_id="MSG_UNKNOWN_123"
        ).first()
        assert activity.contact_id == contact.id
    
    def test_webhook_signature_validation(self, app, webhook_service, signing_key):
        """Test webhook signature validation."""
        payload = self.create_webhook_payload("message.created", {
            "object": "message",
            "id": "MSG_SIG_123",
            "body": "Test signature",
            "from": "+12345678900",
            "to": ["+19876543210"],
            "direction": "incoming"
        })
        
        # Valid signature
        valid_signature = self.generate_signature(payload, signing_key)
        with app.test_request_context(
            json=payload,
            headers={'X-OpenPhone-Signature': valid_signature}
        ):
            result = webhook_service.handle_webhook(payload)
            assert result['success'] is True
        
        # Invalid signature
        with app.test_request_context(
            json=payload,
            headers={'X-OpenPhone-Signature': 'invalid_signature'}
        ):
            with pytest.raises(Exception):  # Should raise signature error
                webhook_service.handle_webhook(payload)
    
    def test_all_webhook_types_coverage(self, webhook_service):
        """Ensure all supported webhook types are tested."""
        supported_types = [
            'message.created',
            'message.updated', 
            'call.completed',
            'call.recording.completed',
            'contact.created',
            'contact.updated'
        ]
        
        for event_type in supported_types:
            assert hasattr(webhook_service, f"_handle_{event_type.replace('.', '_')}")
    
    @pytest.mark.parametrize("event_type,expected_action", [
        ("message.created", "message_created"),
        ("message.updated", "message_updated"),
        ("call.completed", "call_completed"),
        ("call.recording.completed", "recording_completed"),
        ("contact.created", "contact_created"),
        ("contact.updated", "contact_updated")
    ])
    def test_webhook_routing(self, webhook_service, event_type, expected_action):
        """Test that webhooks are routed to correct handlers."""
        # Create minimal valid payload for each type
        data = {
            "object": event_type.split('.')[0],
            "id": f"TEST_{event_type}_123"
        }
        
        # Add minimal required fields based on type
        if event_type.startswith("message"):
            data.update({
                "body": "Test",
                "from": "+11111111111",
                "to": ["+12222222222"],
                "direction": "incoming"
            })
        elif event_type.startswith("call"):
            data.update({
                "from": "+11111111111",
                "to": "+12222222222",
                "direction": "incoming"
            })
        elif event_type.startswith("contact"):
            data.update({
                "phoneNumbers": [{"number": "+11111111111"}]
            })
        
        payload = self.create_webhook_payload(event_type, data)
        
        with patch.object(webhook_service, f"_handle_{event_type.replace('.', '_')}") as mock_handler:
            mock_handler.return_value = {"success": True, "action": expected_action}
            
            result = webhook_service.handle_webhook(payload)
            
            assert mock_handler.called
            assert result['action'] == expected_action