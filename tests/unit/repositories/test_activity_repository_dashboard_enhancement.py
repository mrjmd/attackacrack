"""
Tests for ActivityRepository dashboard-specific methods
These tests are written FIRST (TDD RED phase) before implementing the methods
"""

import pytest
from datetime import datetime, timedelta
from repositories.activity_repository import ActivityRepository
from crm_database import Activity, Contact
from tests.conftest import create_test_contact


class TestActivityRepositoryDashboardEnhancements:
    """Test dashboard-specific methods for ActivityRepository"""
    
    @pytest.fixture
    def repository(self, db_session):
        """Create ActivityRepository instance"""
        return ActivityRepository(session=db_session)
    
    def test_get_message_volume_data_by_days(self, repository, db_session):
        """Test getting message volume data for last N days"""
        # Arrange - create activities across different days
        contact = create_test_contact(phone='+11234567890')
        db_session.add(contact)
        db_session.commit()
        
        # Create activities for different days
        today = datetime.utcnow().date()
        yesterday = today - timedelta(days=1)
        two_days_ago = today - timedelta(days=2)
        
        # Today: 2 messages
        activity1_today = Activity(
            contact_id=contact.id,
            activity_type='message',
            direction='outgoing',
            created_at=datetime.combine(today, datetime.min.time())
        )
        activity2_today = Activity(
            contact_id=contact.id,
            activity_type='message', 
            direction='incoming',
            created_at=datetime.combine(today, datetime.min.time()) + timedelta(hours=1)
        )
        
        # Yesterday: 1 message
        activity_yesterday = Activity(
            contact_id=contact.id,
            activity_type='message',
            direction='outgoing',
            created_at=datetime.combine(yesterday, datetime.min.time())
        )
        
        # Two days ago: 0 messages (no activity created)
        
        # Also create a non-message activity that should be excluded
        call_activity = Activity(
            contact_id=contact.id,
            activity_type='call',
            direction='outgoing',
            created_at=datetime.combine(today, datetime.min.time())
        )
        
        db_session.add_all([
            activity1_today, activity2_today, 
            activity_yesterday, call_activity
        ])
        db_session.commit()
        
        # Act
        result = repository.get_message_volume_data(days=3)
        
        # Assert
        assert len(result) == 3
        
        # Check data structure and values
        day_data = {item['date']: item['count'] for item in result}
        assert day_data[two_days_ago] == 0
        assert day_data[yesterday] == 1  
        assert day_data[today] == 2
        
        # Verify ordering (should be chronological)
        assert result[0]['date'] == two_days_ago
        assert result[1]['date'] == yesterday
        assert result[2]['date'] == today
    
    def test_get_messages_sent_today_count(self, repository, db_session):
        """Test counting outgoing messages sent today"""
        # Arrange
        contact = create_test_contact(phone='+11234567890')
        db_session.add(contact)
        db_session.commit()
        
        # Use fixed times to avoid flaky tests based on when they run
        from datetime import time
        today_noon = datetime.combine(datetime.utcnow().date(), time(12, 0, 0))
        today_morning = datetime.combine(datetime.utcnow().date(), time(10, 0, 0))
        yesterday = today_noon - timedelta(days=1)
        
        # Today's outgoing messages (should be counted)
        outgoing_today1 = Activity(
            contact_id=contact.id,
            activity_type='message',
            direction='outgoing',
            created_at=today_noon
        )
        outgoing_today2 = Activity(
            contact_id=contact.id,
            activity_type='message',
            direction='outgoing', 
            created_at=today_morning
        )
        
        # Today's incoming message (should not be counted)
        incoming_today = Activity(
            contact_id=contact.id,
            activity_type='message',
            direction='incoming',
            created_at=today_noon
        )
        
        # Yesterday's outgoing message (should not be counted)
        outgoing_yesterday = Activity(
            contact_id=contact.id,
            activity_type='message',
            direction='outgoing',
            created_at=yesterday
        )
        
        # Today's non-message activity (should not be counted)
        call_today = Activity(
            contact_id=contact.id,
            activity_type='call',
            direction='outgoing',
            created_at=today_noon
        )
        
        db_session.add_all([
            outgoing_today1, outgoing_today2, incoming_today,
            outgoing_yesterday, call_today
        ])
        db_session.commit()
        
        # Act
        result = repository.get_messages_sent_today_count()
        
        # Assert
        assert result == 2
    
    def test_calculate_overall_response_rate(self, repository, db_session):
        """Test calculating overall response rate (incoming vs outgoing)"""
        # Arrange
        contact = create_test_contact(phone='+11234567890')
        db_session.add(contact)
        db_session.commit()
        
        # Create 4 outgoing messages
        for i in range(4):
            outgoing = Activity(
                contact_id=contact.id,
                activity_type='message',
                direction='outgoing',
                created_at=datetime.utcnow() - timedelta(minutes=i*10)
            )
            db_session.add(outgoing)
        
        # Create 2 incoming messages (responses)
        for i in range(2):
            incoming = Activity(
                contact_id=contact.id,
                activity_type='message', 
                direction='incoming',
                created_at=datetime.utcnow() - timedelta(minutes=i*15)
            )
            db_session.add(incoming)
        
        # Create non-message activities that should be excluded
        call = Activity(
            contact_id=contact.id,
            activity_type='call',
            direction='incoming',
            created_at=datetime.utcnow()
        )
        db_session.add(call)
        db_session.commit()
        
        # Act
        result = repository.calculate_overall_response_rate()
        
        # Assert - 2 incoming / 4 outgoing * 100 = 50%
        assert result == 50.0
    
    def test_calculate_overall_response_rate_no_outgoing(self, repository, db_session):
        """Test response rate calculation with no outgoing messages"""
        # Arrange - only incoming messages
        contact = create_test_contact(phone='+11234567890')
        db_session.add(contact)
        db_session.commit()
        
        incoming = Activity(
            contact_id=contact.id,
            activity_type='message',
            direction='incoming',
            created_at=datetime.utcnow()
        )
        db_session.add(incoming)
        db_session.commit()
        
        # Act
        result = repository.calculate_overall_response_rate()
        
        # Assert
        assert result == 0
    
    def test_get_distinct_contacts_with_recent_activity(self, repository, db_session):
        """Test counting distinct contacts with activity in last week"""
        # Arrange
        contact1 = create_test_contact(phone='+11234567890')
        contact2 = create_test_contact(phone='+11234567891')
        contact3 = create_test_contact(phone='+11234567892')
        db_session.add_all([contact1, contact2, contact3])
        db_session.commit()
        
        recent_date = datetime.utcnow() - timedelta(days=3)
        old_date = datetime.utcnow() - timedelta(days=10)
        
        # Recent activities for contact1 and contact2
        activity1a = Activity(
            contact_id=contact1.id,
            activity_type='message', 
            direction='incoming',
            created_at=recent_date
        )
        activity1b = Activity(
            contact_id=contact1.id,  # Same contact, multiple activities
            activity_type='message',
            direction='outgoing', 
            created_at=recent_date
        )
        activity2 = Activity(
            contact_id=contact2.id,
            activity_type='message',
            direction='incoming',
            created_at=recent_date  
        )
        
        # Old activity for contact3 (should not be counted)
        activity3 = Activity(
            contact_id=contact3.id,
            activity_type='message',
            direction='incoming',
            created_at=old_date
        )
        
        db_session.add_all([activity1a, activity1b, activity2, activity3])
        db_session.commit()
        
        # Act
        result = repository.get_distinct_contacts_with_recent_activity(days=7)
        
        # Assert - Only contact1 and contact2 should be counted (distinct)
        assert result == 2