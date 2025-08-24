"""
Tests for ConversationRepository dashboard-specific methods
These tests are written FIRST (TDD RED phase) before implementing the methods
"""

import pytest
from datetime import datetime, timedelta
from utils.datetime_utils import utc_now
from sqlalchemy.orm import selectinload, joinedload
from repositories.conversation_repository import ConversationRepository
from crm_database import Conversation, Contact, Activity
from tests.conftest import create_test_contact


class TestConversationRepositoryDashboardEnhancements:
    """Test dashboard-specific methods for ConversationRepository"""
    
    @pytest.fixture
    def repository(self, db_session):
        """Create ConversationRepository instance"""
        return ConversationRepository(session=db_session)
    
    def test_get_recent_conversations_with_activities_preloaded(self, repository, db_session):
        """Test getting recent conversations with activities and contacts preloaded"""
        # Arrange - create contacts and conversations with activities
        contact1 = create_test_contact(phone='+11234567890', first_name='John')
        contact2 = create_test_contact(phone='+11234567891', first_name='Jane')
        contact3 = create_test_contact(phone='+11234567892', first_name='Bob')
        db_session.add_all([contact1, contact2, contact3])
        db_session.commit()
        
        recent_time = utc_now() - timedelta(hours=1)
        old_time = utc_now() - timedelta(days=5)
        
        # Create conversations
        conv1 = Conversation(
            contact_id=contact1.id,
            last_activity_at=recent_time,
            openphone_id='conv_1'
        )
        conv2 = Conversation(
            contact_id=contact2.id,
            last_activity_at=recent_time - timedelta(hours=1),
            openphone_id='conv_2'
        )
        conv3 = Conversation(
            contact_id=contact3.id,
            last_activity_at=old_time,
            openphone_id='conv_3'
        )
        
        db_session.add_all([conv1, conv2, conv3])
        db_session.commit()
        
        # Create activities for each conversation
        activity1 = Activity(
            conversation_id=conv1.id,
            contact_id=contact1.id,
            activity_type='message',
            direction='incoming',
            body='Recent message from John',
            created_at=recent_time
        )
        activity2 = Activity(
            conversation_id=conv2.id, 
            contact_id=contact2.id,
            activity_type='message',
            direction='outgoing',
            body='Message to Jane',
            created_at=recent_time - timedelta(hours=1)
        )
        activity3 = Activity(
            conversation_id=conv3.id,
            contact_id=contact3.id,
            activity_type='message',
            direction='incoming', 
            body='Old message from Bob',
            created_at=old_time
        )
        
        db_session.add_all([activity1, activity2, activity3])
        db_session.commit()
        
        # Act
        result = repository.get_recent_conversations_with_activities(limit=20)
        
        # Assert
        assert len(result) == 3
        
        # Verify ordering by last_activity_at desc
        assert result[0].last_activity_at >= result[1].last_activity_at
        assert result[1].last_activity_at >= result[2].last_activity_at
        
        # Verify contact data is preloaded (no additional DB queries)
        assert result[0].contact.first_name is not None
        assert result[1].contact.first_name is not None
        assert result[2].contact.first_name is not None
        
        # Verify activities are preloaded
        assert len(result[0].activities) > 0
        assert len(result[1].activities) > 0
        assert len(result[2].activities) > 0
        
        # Verify only conversations with activities are returned
        for conv in result:
            assert len(conv.activities) > 0
    
    def test_get_recent_conversations_only_with_activities(self, repository, db_session):
        """Test that only conversations with activities are returned"""
        # Arrange
        contact1 = create_test_contact(phone='+11234567890', first_name='WithActivity')
        contact2 = create_test_contact(phone='+11234567891', first_name='NoActivity')
        db_session.add_all([contact1, contact2])
        db_session.commit()
        
        recent_time = utc_now() - timedelta(hours=1)
        
        # Conversation with activity
        conv_with_activity = Conversation(
            contact_id=contact1.id,
            last_activity_at=recent_time,
            openphone_id='conv_with_activity'
        )
        
        # Conversation without activity  
        conv_no_activity = Conversation(
            contact_id=contact2.id,
            last_activity_at=recent_time,
            openphone_id='conv_no_activity'
        )
        
        db_session.add_all([conv_with_activity, conv_no_activity])
        db_session.commit()
        
        # Add activity only to first conversation
        activity = Activity(
            conversation_id=conv_with_activity.id,
            contact_id=contact1.id,
            activity_type='message',
            direction='incoming',
            body='Test message',
            created_at=recent_time
        )
        db_session.add(activity)
        db_session.commit()
        
        # Act
        result = repository.get_recent_conversations_with_activities(limit=10)
        
        # Assert - only conversation with activity should be returned
        assert len(result) == 1
        assert result[0].id == conv_with_activity.id
        assert len(result[0].activities) == 1
    
    def test_get_recent_conversations_respects_limit(self, repository, db_session):
        """Test that the limit parameter is respected"""
        # Arrange - create more conversations than the limit
        contacts = []
        conversations = []
        
        for i in range(5):
            contact = create_test_contact(
                phone=f'+1123456789{i}',
                first_name=f'Contact{i}'
            )
            contacts.append(contact)
        
        db_session.add_all(contacts)
        db_session.commit()
        
        recent_time = utc_now() - timedelta(hours=1)
        
        for i, contact in enumerate(contacts):
            conv = Conversation(
                contact_id=contact.id,
                last_activity_at=recent_time - timedelta(minutes=i*10),
                openphone_id=f'conv_{i}'
            )
            conversations.append(conv)
        
        db_session.add_all(conversations)
        db_session.commit()
        
        # Add activities to all conversations
        for i, conv in enumerate(conversations):
            activity = Activity(
                conversation_id=conv.id,
                contact_id=conv.contact_id,
                activity_type='message',
                direction='incoming',
                body=f'Message {i}',
                created_at=recent_time - timedelta(minutes=i*10)
            )
            db_session.add(activity)
        
        db_session.commit()
        
        # Act
        result = repository.get_recent_conversations_with_activities(limit=3)
        
        # Assert
        assert len(result) == 3
        
        # Verify most recent conversations are returned first
        for i in range(len(result) - 1):
            assert result[i].last_activity_at >= result[i + 1].last_activity_at
    
    def test_get_recent_conversations_empty_database(self, repository):
        """Test getting recent conversations from empty database"""
        # Act
        result = repository.get_recent_conversations_with_activities(limit=10)
        
        # Assert
        assert result == []
        
    def test_get_recent_conversations_eager_loading_configuration(self, repository, db_session):
        """Test that the method uses proper eager loading to avoid N+1 queries"""
        # Arrange
        contact = create_test_contact(phone='+11234567890', first_name='TestUser')
        db_session.add(contact)
        db_session.commit()
        
        conv = Conversation(
            contact_id=contact.id,
            last_activity_at=utc_now(),
            openphone_id='test_conv'
        )
        db_session.add(conv)
        db_session.commit()
        
        # Add multiple activities to test selectinload
        for i in range(3):
            activity = Activity(
                conversation_id=conv.id,
                contact_id=contact.id,
                activity_type='message',
                direction='incoming',
                body=f'Message {i}',
                created_at=utc_now() - timedelta(minutes=i)
            )
            db_session.add(activity)
        
        db_session.commit()
        
        # Act
        result = repository.get_recent_conversations_with_activities(limit=1)
        
        # Assert
        assert len(result) == 1
        conversation = result[0]
        
        # Verify contact is loaded
        assert conversation.contact is not None
        assert conversation.contact.first_name == 'TestUser'
        
        # Verify activities are loaded
        assert len(conversation.activities) == 3
        
        # Verify we can access activity data without additional queries
        for activity in conversation.activities:
            assert activity.body is not None
            assert activity.activity_type == 'message'