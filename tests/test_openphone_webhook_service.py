"""
Tests for OpenPhone Webhook Service
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
from services.openphone_webhook_service import OpenPhoneWebhookService
from crm_database import db, Contact, Activity, Conversation, Job, Property


class TestOpenPhoneWebhookService:
    """Test cases for OpenPhone webhook service"""
    
    @pytest.fixture
    def webhook_service(self, app):
        """Create webhook service instance"""
        with app.app_context():
            service = OpenPhoneWebhookService()
            yield service
            # Clean up
            Activity.query.delete()
            # RecordingUrl table removed
            Conversation.query.delete()
            Contact.query.filter(Contact.id > 1).delete()
            db.session.commit()
    
    @pytest.fixture
    def sample_message_webhook(self):
        """Sample message webhook payload"""
        return {
            'id': 'msg_123',
            'object': 'message',
            'phoneNumberId': 'PN123',
            'conversationId': 'conv_123',
            'from': '+15551234567',
            'to': ['+16176681677'],
            'body': 'Hello, this is a test message',
            'direction': 'incoming',
            'status': 'delivered',
            'media': [],
            'createdAt': '2024-01-01T12:00:00Z',
            'userId': 'user_123',
            'type': 'message'
        }
    
    @pytest.fixture
    def sample_call_webhook(self):
        """Sample call webhook payload"""
        return {
            'id': 'call_123',
            'object': 'call',
            'phoneNumberId': 'PN123',
            'conversationId': 'conv_123',
            'from': '+15551234567',
            'to': '+16176681677',
            'direction': 'incoming',
            'status': 'completed',
            'answeredAt': '2024-01-01T12:00:00Z',
            'completedAt': '2024-01-01T12:15:00Z',
            'createdAt': '2024-01-01T12:00:00Z',
            'duration': 900,
            'participants': [
                {
                    'phoneNumber': '+15551234567',
                    'name': 'John Doe',
                    'userId': None
                },
                {
                    'phoneNumber': '+16176681677',
                    'name': 'Agent',
                    'userId': 'user_123'
                }
            ],
            'recordingUrl': 'https://example.com/recording.mp3',
            'recordingId': 'rec_123',
            'voicemail': None,
            'type': 'call'
        }
    
    def test_process_webhook_new_contact_from_message(self, webhook_service, sample_message_webhook, app):
        """Test processing message webhook creates new contact"""
        with app.app_context():
            result = webhook_service.process_webhook(sample_message_webhook)
            
            assert result is not None
            assert result['status'] == 'success'
            assert 'activity_id' in result
            
            # Verify contact was created
            contact = Contact.query.filter_by(phone='+15551234567').first()
            assert contact is not None
            assert contact.first_name == 'Unknown'
            
            # Verify activity was created
            activity = Activity.query.filter_by(openphone_id='msg_123').first()
            assert activity is not None
            assert activity.activity_type == 'message'
            assert activity.direction == 'incoming'
            assert activity.body == 'Hello, this is a test message'
            
            # Verify conversation was created
            conversation = Conversation.query.filter_by(openphone_conversation_id='conv_123').first()
            assert conversation is not None
            assert conversation.contact_id == contact.id
    
    def test_process_webhook_existing_contact(self, webhook_service, sample_message_webhook, app):
        """Test processing webhook with existing contact"""
        with app.app_context():
            # Create existing contact
            existing = Contact(
                first_name='John',
                last_name='Doe',
                phone='+15551234567'
            )
            db.session.add(existing)
            db.session.commit()
            
            result = webhook_service.process_webhook(sample_message_webhook)
            
            # Should use existing contact
            activity = Activity.query.filter_by(openphone_id='msg_123').first()
            assert activity.contact_id == existing.id
            
            # Should not create duplicate contact
            contacts = Contact.query.filter_by(phone='+15551234567').all()
            assert len(contacts) == 1
    
    def test_process_webhook_duplicate_activity(self, webhook_service, sample_message_webhook, app):
        """Test processing duplicate webhook (idempotency)"""
        with app.app_context():
            # Process once
            result1 = webhook_service.process_webhook(sample_message_webhook)
            
            # Process same webhook again
            result2 = webhook_service.process_webhook(sample_message_webhook)
            
            # Should skip duplicate
            assert result2['status'] == 'skipped'
            assert result2['reason'] == 'duplicate'
            
            # Should only have one activity
            activities = Activity.query.filter_by(openphone_id='msg_123').all()
            assert len(activities) == 1
    
    def test_process_call_webhook_with_recording(self, webhook_service, sample_call_webhook, app):
        """Test processing call webhook with recording"""
        with app.app_context():
            result = webhook_service.process_webhook(sample_call_webhook)
            
            assert result['status'] == 'success'
            
            # Verify call activity
            activity = Activity.query.filter_by(openphone_id='call_123').first()
            assert activity is not None
            assert activity.activity_type == 'call'
            assert activity.call_duration == 900
            assert activity.recording_url == 'https://example.com/recording.mp3'
            
            # Recording URL is stored directly on activity
    
    def test_process_voicemail_webhook(self, webhook_service, app):
        """Test processing voicemail webhook"""
        voicemail_webhook = {
            'id': 'vm_123',
            'object': 'call',
            'phoneNumberId': 'PN123',
            'conversationId': 'conv_123',
            'from': '+15551234567',
            'to': '+16176681677',
            'direction': 'incoming',
            'status': 'voicemail',
            'createdAt': '2024-01-01T12:00:00Z',
            'voicemail': {
                'url': 'https://example.com/voicemail.mp3',
                'duration': 30,
                'transcription': 'This is a test voicemail'
            },
            'type': 'call'
        }
        
        with app.app_context():
            result = webhook_service.process_webhook(voicemail_webhook)
            
            activity = Activity.query.filter_by(openphone_id='vm_123').first()
            assert activity.activity_type == 'voicemail'
            assert activity.recording_url == 'https://example.com/voicemail.mp3'
            assert activity.body == 'This is a test voicemail'
            assert activity.call_duration == 30
    
    def test_process_outgoing_message(self, webhook_service, app):
        """Test processing outgoing message webhook"""
        outgoing_webhook = {
            'id': 'msg_out_123',
            'object': 'message',
            'phoneNumberId': 'PN123',
            'conversationId': 'conv_123',
            'from': '+16176681677',  # Our number
            'to': ['+15551234567'],
            'body': 'Outgoing message',
            'direction': 'outgoing',
            'status': 'sent',
            'createdAt': '2024-01-01T12:00:00Z',
            'userId': 'user_123',
            'type': 'message'
        }
        
        with app.app_context():
            result = webhook_service.process_webhook(outgoing_webhook)
            
            activity = Activity.query.filter_by(openphone_id='msg_out_123').first()
            assert activity.direction == 'outgoing'
            assert activity.from_number == '+16176681677'
            assert activity.to_number == '+15551234567'
            assert activity.user_id == 'user_123'
    
    def test_extract_phone_numbers_from_participants(self, webhook_service):
        """Test extracting phone numbers from participants"""
        participants = [
            {'phoneNumber': '+15551234567', 'name': 'John'},
            {'phoneNumber': '+16176681677', 'name': 'Agent', 'userId': 'user_123'}
        ]
        
        from_phone, to_phone = webhook_service._extract_phone_numbers(
            {'participants': participants, 'direction': 'incoming'}
        )
        
        assert from_phone == '+15551234567'
        assert to_phone == '+16176681677'
    
    def test_extract_phone_numbers_from_fields(self, webhook_service):
        """Test extracting phone numbers from from/to fields"""
        # Message format
        from_phone, to_phone = webhook_service._extract_phone_numbers({
            'from': '+15551234567',
            'to': ['+16176681677'],
            'direction': 'incoming'
        })
        
        assert from_phone == '+15551234567'
        assert to_phone == '+16176681677'
        
        # Call format
        from_phone, to_phone = webhook_service._extract_phone_numbers({
            'from': '+15551234567',
            'to': '+16176681677',
            'direction': 'incoming'
        })
        
        assert from_phone == '+15551234567'
        assert to_phone == '+16176681677'
    
    def test_find_or_create_contact_with_name(self, webhook_service, app):
        """Test contact creation with name from webhook"""
        with app.app_context():
            webhook_data = {
                'from': '+15551234567',
                'participants': [
                    {'phoneNumber': '+15551234567', 'name': 'John Doe'}
                ]
            }
            
            contact = webhook_service._find_or_create_contact('+15551234567', webhook_data)
            
            assert contact.first_name == 'John'
            assert contact.last_name == 'Doe'
    
    def test_find_or_create_contact_existing_with_job(self, webhook_service, app):
        """Test finding contact with active job"""
        with app.app_context():
            # Create contact with property and job
            contact = Contact(first_name='Test', phone='+15551234567')
            property = Property(address='123 Test St', contact=contact)
            job = Job(description='Test Job', property=property, status='Active')
            
            db.session.add_all([contact, property, job])
            db.session.commit()
            
            found_contact = webhook_service._find_or_create_contact('+15551234567', {})
            
            assert found_contact.id == contact.id
            # Should have job relationship loaded
            assert len(found_contact.properties) == 1
            assert len(found_contact.properties[0].jobs) == 1
    
    def test_update_conversation_activity(self, webhook_service, app):
        """Test updating conversation with latest activity"""
        with app.app_context():
            contact = Contact(first_name='Test', phone='+15551234567')
            conversation = Conversation(
                openphone_conversation_id='conv_123',
                contact=contact,
                last_activity_at=datetime(2024, 1, 1, 10, 0, 0)
            )
            db.session.add_all([contact, conversation])
            db.session.commit()
            
            # Create activity with later timestamp
            activity = Activity(
                openphone_id='msg_123',
                conversation_id=conversation.id,
                contact_id=contact.id,
                activity_type='message',
                created_at=datetime(2024, 1, 1, 12, 0, 0)
            )
            
            webhook_service._update_conversation_activity(conversation, activity)
            
            assert conversation.last_activity_at == datetime(2024, 1, 1, 12, 0, 0)
            assert conversation.last_message_preview == ''  # No body in activity
    
    def test_create_conversation_from_activity(self, webhook_service, app):
        """Test creating conversation from activity"""
        with app.app_context():
            contact = Contact(first_name='Test', phone='+15551234567')
            db.session.add(contact)
            db.session.commit()
            
            activity = Activity(
                openphone_id='msg_123',
                openphone_conversation_id='conv_123',
                contact_id=contact.id,
                activity_type='message',
                body='Test message',
                created_at=datetime(2024, 1, 1, 12, 0, 0)
            )
            
            conversation = webhook_service._create_conversation_from_activity(activity)
            
            assert conversation.openphone_conversation_id == 'conv_123'
            assert conversation.contact_id == contact.id
            assert conversation.last_message_preview == 'Test message'
            assert conversation.last_activity_at == datetime(2024, 1, 1, 12, 0, 0)
    
    def test_process_webhook_with_media(self, webhook_service, app):
        """Test processing message with media attachments"""
        webhook_with_media = {
            'id': 'msg_media_123',
            'object': 'message',
            'phoneNumberId': 'PN123',
            'conversationId': 'conv_123',
            'from': '+15551234567',
            'to': ['+16176681677'],
            'body': 'Check out this image',
            'direction': 'incoming',
            'status': 'delivered',
            'media': [
                {
                    'url': 'https://example.com/image1.jpg',
                    'type': 'image/jpeg'
                },
                {
                    'url': 'https://example.com/image2.png',
                    'type': 'image/png'
                }
            ],
            'createdAt': '2024-01-01T12:00:00Z',
            'type': 'message'
        }
        
        with app.app_context():
            result = webhook_service.process_webhook(webhook_with_media)
            
            activity = Activity.query.filter_by(openphone_id='msg_media_123').first()
            assert activity.media_urls is not None
            assert len(activity.media_urls) == 2
            assert activity.media_urls[0]['url'] == 'https://example.com/image1.jpg'
    
    def test_process_webhook_error_handling(self, webhook_service, app):
        """Test webhook processing error handling"""
        with app.app_context():
            # Invalid webhook data (empty dict)
            result = webhook_service.process_webhook({})
            assert result['status'] == 'ignored'
            assert 'Unknown event type' in result['reason']
            
            # Unknown event type
            result = webhook_service.process_webhook({'type': 'unknown.event'})
            assert result['status'] == 'ignored'
            assert 'Unknown event type' in result['reason']
    
    def test_process_webhook_database_error(self, webhook_service, sample_message_webhook, app):
        """Test handling database errors during webhook processing"""
        with app.app_context():
            # Mock database error
            with patch.object(db.session, 'commit', side_effect=Exception('DB Error')):
                result = webhook_service.process_webhook(sample_message_webhook)
            
            assert result['status'] == 'error'
            assert 'DB Error' in result['message'] or 'Error processing webhook' in result['message']
            
            # Verify no data was saved
            activities = Activity.query.all()
            assert len(activities) == 0
    
    def test_parse_participant_name(self, webhook_service):
        """Test parsing participant names"""
        # Full name
        first, last = webhook_service._parse_participant_name('John Doe')
        assert first == 'John'
        assert last == 'Doe'
        
        # Single name
        first, last = webhook_service._parse_participant_name('John')
        assert first == 'John'
        assert last == ''
        
        # Multiple parts
        first, last = webhook_service._parse_participant_name('John Paul Smith')
        assert first == 'John'
        assert last == 'Paul Smith'
        
        # Empty/None
        first, last = webhook_service._parse_participant_name('')
        assert first == 'Unknown'
        assert last == ''
        
        first, last = webhook_service._parse_participant_name(None)
        assert first == 'Unknown'
        assert last == ''
    
    def test_normalize_phone_number(self, webhook_service):
        """Test phone number normalization"""
        # Already formatted
        assert webhook_service._normalize_phone('+15551234567') == '+15551234567'
        
        # Missing +
        assert webhook_service._normalize_phone('15551234567') == '+15551234567'
        
        # 10-digit US number
        assert webhook_service._normalize_phone('5551234567') == '+15551234567'
        
        # With formatting
        assert webhook_service._normalize_phone('(555) 123-4567') == '+15551234567'
        assert webhook_service._normalize_phone('555-123-4567') == '+15551234567'
        assert webhook_service._normalize_phone('555.123.4567') == '+15551234567'
    
    @patch('services.openphone_webhook_service.datetime')
    def test_webhook_timestamp_parsing(self, mock_datetime, webhook_service, sample_message_webhook, app):
        """Test parsing webhook timestamps"""
        # Mock datetime.utcnow for consistent testing
        mock_now = datetime(2024, 1, 1, 13, 0, 0)
        mock_datetime.utcnow.return_value = mock_now
        mock_datetime.fromisoformat = datetime.fromisoformat
        
        with app.app_context():
            result = webhook_service.process_webhook(sample_message_webhook)
            
            activity = Activity.query.filter_by(openphone_id='msg_123').first()
            # Should parse ISO format timestamp
            assert activity.created_at == datetime(2024, 1, 1, 12, 0, 0)