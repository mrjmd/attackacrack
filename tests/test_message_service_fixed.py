"""
Fixed tests for Message Service
"""
import pytest
from datetime import datetime
from unittest.mock import Mock, patch
from services.message_service import MessageService
from crm_database import db, Conversation, Activity


class TestMessageServiceFixed:
    """Fixed test cases for Message service"""
    
    @pytest.fixture
    def message_service(self, app):
        """Create a message service instance"""
        with app.app_context():
            service = MessageService()
            yield service
    
    def test_get_or_create_conversation(self, message_service, app):
        """Test getting or creating conversation"""
        with app.app_context():
            # Test creating new conversation
            conversation = message_service.get_or_create_conversation(
                contact_id=1,
                openphone_convo_id='test-conv-123',
                participants=['+15551234567', '+15559999999']
            )
            assert conversation is not None
            assert conversation.contact_id == 1
            assert conversation.conversation_id == 'test-conv-123'
            
            # Test getting existing conversation
            same_conversation = message_service.get_or_create_conversation(
                contact_id=1,
                openphone_convo_id='test-conv-123'
            )
            assert same_conversation.id == conversation.id
            
            # Clean up
            db.session.delete(conversation)
            db.session.commit()
    
    def test_get_activities_for_contact(self, message_service, app):
        """Test getting activities for a contact"""
        with app.app_context():
            # Create conversation first
            conversation = Conversation(
                contact_id=1,
                phone_number='+15551234567',
                conversation_id='test-conv-123',
                channel='sms'
            )
            db.session.add(conversation)
            db.session.commit()
            
            # Create activities
            activity1 = Activity(
                conversation_id=conversation.id,
                type='message',
                direction='incoming',
                content='Hello',
                from_number='+15551234567',
                to_number='+15559999999',
                created_at=datetime.utcnow()
            )
            activity2 = Activity(
                conversation_id=conversation.id,
                type='message',
                direction='outgoing',
                content='Hi there',
                from_number='+15559999999',
                to_number='+15551234567',
                created_at=datetime.utcnow()
            )
            db.session.add_all([activity1, activity2])
            db.session.commit()
            
            # Test getting activities
            result = message_service.get_activities_for_contact(1)
            assert len(result) >= 2
            
            # Clean up
            db.session.query(Activity).filter_by(conversation_id=conversation.id).delete()
            db.session.delete(conversation)
            db.session.commit()
    
    def test_get_latest_conversations_from_db(self, message_service, app):
        """Test getting latest conversations"""
        with app.app_context():
            # Create test conversations
            conv1 = Conversation(
                contact_id=1,
                phone_number='+15551234567',
                conversation_id='test-conv-1',
                channel='sms',
                last_activity_at=datetime.utcnow()
            )
            conv2 = Conversation(
                contact_id=2,
                phone_number='+15551234568',
                conversation_id='test-conv-2',
                channel='voice',
                last_activity_at=datetime.utcnow() - timedelta(hours=1)
            )
            db.session.add_all([conv1, conv2])
            db.session.commit()
            
            # Test getting latest conversations
            result = message_service.get_latest_conversations_from_db(limit=5)
            assert len(result) >= 2
            # Should be ordered by last_activity_at desc
            if len(result) >= 2:
                assert result[0].last_activity_at >= result[1].last_activity_at
            
            # Clean up
            db.session.delete(conv1)
            db.session.delete(conv2)
            db.session.commit()