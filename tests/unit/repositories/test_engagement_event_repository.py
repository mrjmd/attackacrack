"""
Tests for EngagementEventRepository - P4-01 Engagement Scoring System
TDD RED PHASE - These tests are written FIRST before implementation
"""

import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock, patch
from utils.datetime_utils import utc_now
from repositories.engagement_event_repository import EngagementEventRepository
from crm_database import EngagementEvent, Contact, Campaign, Activity
from tests.conftest import create_test_contact
from repositories.base_repository import PaginationParams


class TestEngagementEventRepository:
    """Test EngagementEventRepository with comprehensive coverage"""
    
    @pytest.fixture
    def repository(self, db_session):
        """Create EngagementEventRepository instance"""
        return EngagementEventRepository(session=db_session)
    
    @pytest.fixture
    def sample_contact(self, db_session):
        """Create sample contact for testing"""
        import uuid
        unique_phone = f'+1555{str(uuid.uuid4())[:8].replace("-", "")[:7]}'
        contact = create_test_contact(phone=unique_phone, first_name='Test', last_name='Contact')
        db_session.add(contact)
        db_session.commit()
        return contact
    
    @pytest.fixture 
    def sample_campaign(self, db_session):
        """Create sample campaign for testing"""
        from crm_database import Campaign
        import uuid
        unique_name = f'Test Campaign {str(uuid.uuid4())[:8]}'
        campaign = Campaign(name=unique_name, status='active')
        db_session.add(campaign)
        db_session.commit()
        return campaign
    
    def test_create_engagement_event_delivered(self, repository, db_session, sample_contact, sample_campaign):
        """Test creating a 'delivered' engagement event"""
        # Arrange
        event_data = {
            'contact_id': sample_contact.id,
            'campaign_id': sample_campaign.id,
            'event_type': 'delivered',
            'event_timestamp': utc_now(),
            'message_id': 'msg_123',
            'channel': 'sms'
        }
        
        # Act
        event = repository.create(**event_data)
        
        # Assert
        assert event.id is not None
        assert event.contact_id == sample_contact.id
        assert event.campaign_id == sample_campaign.id
        assert event.event_type == 'delivered'
        assert event.channel == 'sms'
        assert event.message_id == 'msg_123'
        assert event.event_timestamp is not None
    
    def test_create_engagement_event_opened(self, repository, db_session, sample_contact, sample_campaign):
        """Test creating an 'opened' engagement event"""
        # Arrange - First create delivered event
        delivered_event = repository.create(
            contact_id=sample_contact.id,
            campaign_id=sample_campaign.id,
            event_type='delivered',
            event_timestamp=utc_now() - timedelta(minutes=5),
            message_id='msg_123',
            channel='sms'
        )
        
        # Create opened event
        opened_data = {
            'contact_id': sample_contact.id,
            'campaign_id': sample_campaign.id,
            'event_type': 'opened',
            'event_timestamp': utc_now(),
            'message_id': 'msg_123',
            'channel': 'sms',
            'parent_event_id': delivered_event.id
        }
        
        # Act
        event = repository.create(**opened_data)
        
        # Assert
        assert event.event_type == 'opened'
        assert event.parent_event_id == delivered_event.id
        assert event.message_id == delivered_event.message_id
    
    def test_create_engagement_event_clicked(self, repository, db_session, sample_contact, sample_campaign):
        """Test creating a 'clicked' engagement event with URL tracking"""
        # Arrange
        event_data = {
            'contact_id': sample_contact.id,
            'campaign_id': sample_campaign.id,
            'event_type': 'clicked',
            'event_timestamp': utc_now(),
            'message_id': 'msg_123',
            'channel': 'sms',
            'click_url': 'https://example.com/landing',
            'event_metadata': {'user_agent': 'Mozilla/5.0', 'ip_address': '192.168.1.1'}
        }
        
        # Act
        event = repository.create(**event_data)
        
        # Assert
        assert event.event_type == 'clicked'
        assert event.click_url == 'https://example.com/landing'
        assert event.event_metadata['user_agent'] == 'Mozilla/5.0'
    
    def test_create_engagement_event_responded(self, repository, db_session, sample_contact, sample_campaign):
        """Test creating a 'responded' engagement event"""
        # Arrange
        event_data = {
            'contact_id': sample_contact.id,
            'campaign_id': sample_campaign.id,
            'event_type': 'responded',
            'event_timestamp': utc_now(),
            'message_id': 'msg_123',
            'channel': 'sms',
            'response_sentiment': 'positive',
            'response_text': 'Yes, I\'m interested!',
            'event_metadata': {'response_time_minutes': 15}
        }
        
        # Act
        event = repository.create(**event_data)
        
        # Assert
        assert event.event_type == 'responded'
        assert event.response_sentiment == 'positive'
        assert event.response_text == 'Yes, I\'m interested!'
    
    def test_create_engagement_event_converted(self, repository, db_session, sample_contact, sample_campaign):
        """Test creating a 'converted' engagement event with monetary value"""
        # Arrange
        event_data = {
            'contact_id': sample_contact.id,
            'campaign_id': sample_campaign.id,
            'event_type': 'converted',
            'event_timestamp': utc_now(),
            'message_id': 'msg_123',
            'channel': 'sms',
            'conversion_value': Decimal('250.00'),
            'conversion_type': 'appointment_booked',
            'event_metadata': {'appointment_id': 456}
        }
        
        # Act
        event = repository.create(**event_data)
        
        # Assert
        assert event.event_type == 'converted'
        assert event.conversion_value == Decimal('250.00')
        assert event.conversion_type == 'appointment_booked'
    
    def test_create_engagement_event_opted_out(self, repository, db_session, sample_contact, sample_campaign):
        """Test creating an 'opted_out' engagement event"""
        # Arrange
        event_data = {
            'contact_id': sample_contact.id,
            'campaign_id': sample_campaign.id,
            'event_type': 'opted_out',
            'event_timestamp': utc_now(),
            'message_id': 'msg_123',
            'channel': 'sms',
            'opt_out_method': 'keyword',
            'opt_out_keyword': 'STOP',
            'event_metadata': {'triggered_by': 'sms_response'}
        }
        
        # Act
        event = repository.create(**event_data)
        
        # Assert
        assert event.event_type == 'opted_out'
        assert event.opt_out_method == 'keyword'
        assert event.opt_out_keyword == 'STOP'
    
    def test_bulk_create_events_performance(self, repository, db_session, sample_contact, sample_campaign):
        """Test bulk creation of engagement events for performance"""
        # Arrange
        batch_size = 100
        events_data = []
        base_time = utc_now()
        
        for i in range(batch_size):
            events_data.append({
                'contact_id': sample_contact.id,
                'campaign_id': sample_campaign.id,
                'event_type': 'delivered',
                'event_timestamp': base_time + timedelta(seconds=i),
                'message_id': f'msg_{i:03d}',
                'channel': 'sms'
            })
        
        # Act
        events = repository.bulk_create(events_data)
        
        # Assert
        assert len(events) == batch_size
        assert all(event.id is not None for event in events)
        assert events[0].message_id == 'msg_000'
        assert events[-1].message_id == 'msg_099'
    
    def test_get_events_for_contact(self, repository, db_session, sample_contact, sample_campaign):
        """Test retrieving all events for a specific contact"""
        # Arrange
        event1 = repository.create(
            contact_id=sample_contact.id,
            campaign_id=sample_campaign.id,
            event_type='delivered',
            event_timestamp=utc_now() - timedelta(hours=2),
            message_id='msg_1',
            channel='sms'
        )
        event2 = repository.create(
            contact_id=sample_contact.id,
            campaign_id=sample_campaign.id,
            event_type='opened',
            event_timestamp=utc_now() - timedelta(hours=1),
            message_id='msg_1',
            channel='sms'
        )
        
        # Act
        events = repository.get_events_for_contact(sample_contact.id)
        
        # Assert
        assert len(events) == 2
        assert event1 in events
        assert event2 in events
    
    def test_get_events_for_campaign(self, repository, db_session, sample_contact, sample_campaign):
        """Test retrieving all events for a specific campaign"""
        # Arrange
        event1 = repository.create(
            contact_id=sample_contact.id,
            campaign_id=sample_campaign.id,
            event_type='delivered',
            event_timestamp=utc_now(),
            message_id='msg_1',
            channel='sms'
        )
        
        # Create another campaign and event
        from crm_database import Campaign
        other_campaign = Campaign(name='Other Campaign', status='active')
        db_session.add(other_campaign)
        db_session.commit()
        
        event2 = repository.create(
            contact_id=sample_contact.id,
            campaign_id=other_campaign.id,
            event_type='delivered',
            event_timestamp=utc_now(),
            message_id='msg_2',
            channel='sms'
        )
        
        # Act
        events = repository.get_events_for_campaign(sample_campaign.id)
        
        # Assert
        assert len(events) == 1
        assert event1 in events
        assert event2 not in events
    
    def test_get_events_by_date_range(self, repository, db_session, sample_contact, sample_campaign):
        """Test retrieving events within a specific date range"""
        # Arrange
        now = utc_now()
        
        # Event within range
        event_in_range = repository.create(
            contact_id=sample_contact.id,
            campaign_id=sample_campaign.id,
            event_type='delivered',
            event_timestamp=now - timedelta(hours=1),
            message_id='msg_1',
            channel='sms'
        )
        
        # Event outside range
        event_outside_range = repository.create(
            contact_id=sample_contact.id,
            campaign_id=sample_campaign.id,
            event_type='delivered',
            event_timestamp=now - timedelta(days=7),
            message_id='msg_2',
            channel='sms'
        )
        
        # Act
        start_date = now - timedelta(hours=2)
        end_date = now
        events = repository.get_events_by_date_range(start_date, end_date)
        
        # Assert
        assert len(events) == 1
        assert event_in_range in events
        assert event_outside_range not in events
    
    def test_get_events_by_type(self, repository, db_session, sample_contact, sample_campaign):
        """Test retrieving events filtered by event type"""
        # Arrange
        delivered_event = repository.create(
            contact_id=sample_contact.id,
            campaign_id=sample_campaign.id,
            event_type='delivered',
            event_timestamp=utc_now(),
            message_id='msg_1',
            channel='sms'
        )
        
        opened_event = repository.create(
            contact_id=sample_contact.id,
            campaign_id=sample_campaign.id,
            event_type='opened',
            event_timestamp=utc_now(),
            message_id='msg_1',
            channel='sms'
        )
        
        # Act
        delivered_events = repository.get_events_by_type('delivered')
        opened_events = repository.get_events_by_type('opened')
        
        # Assert
        assert delivered_event in delivered_events
        assert delivered_event not in opened_events
        assert opened_event in opened_events
        assert opened_event not in delivered_events
    
    def test_aggregate_events_by_type(self, repository, db_session, sample_contact, sample_campaign):
        """Test aggregating event counts by type"""
        # Arrange
        for _ in range(3):
            repository.create(
                contact_id=sample_contact.id,
                campaign_id=sample_campaign.id,
                event_type='delivered',
                event_timestamp=utc_now(),
                message_id=f'msg_{_}',
                channel='sms'
            )
        
        for _ in range(2):
            repository.create(
                contact_id=sample_contact.id,
                campaign_id=sample_campaign.id,
                event_type='opened',
                event_timestamp=utc_now(),
                message_id=f'msg_{_}',
                channel='sms'
            )
        
        repository.create(
            contact_id=sample_contact.id,
            campaign_id=sample_campaign.id,
            event_type='clicked',
            event_timestamp=utc_now(),
            message_id='msg_click',
            channel='sms'
        )
        
        # Act
        aggregation = repository.aggregate_events_by_type()
        
        # Assert
        assert aggregation['delivered'] == 3
        assert aggregation['opened'] == 2
        assert aggregation['clicked'] == 1
        assert aggregation.get('responded', 0) == 0
    
    def test_get_recent_events_for_scoring(self, repository, db_session, sample_contact, sample_campaign):
        """Test retrieving recent events for scoring calculations"""
        # Arrange
        now = utc_now()
        
        # Recent events (within 30 days)
        recent_event = repository.create(
            contact_id=sample_contact.id,
            campaign_id=sample_campaign.id,
            event_type='delivered',
            event_timestamp=now - timedelta(days=15),
            message_id='msg_recent',
            channel='sms'
        )
        
        # Old event (over 30 days)
        old_event = repository.create(
            contact_id=sample_contact.id,
            campaign_id=sample_campaign.id,
            event_type='delivered',
            event_timestamp=now - timedelta(days=45),
            message_id='msg_old',
            channel='sms'
        )
        
        # Act
        days_back = 30
        events = repository.get_recent_events_for_scoring(days_back)
        
        # Assert
        assert recent_event in events
        assert old_event not in events
    
    def test_get_conversion_events_with_value(self, repository, db_session, sample_contact, sample_campaign):
        """Test retrieving conversion events that have monetary value"""
        # Arrange
        conversion_with_value = repository.create(
            contact_id=sample_contact.id,
            campaign_id=sample_campaign.id,
            event_type='converted',
            event_timestamp=utc_now(),
            message_id='msg_1',
            channel='sms',
            conversion_value=Decimal('150.00')
        )
        
        conversion_without_value = repository.create(
            contact_id=sample_contact.id,
            campaign_id=sample_campaign.id,
            event_type='converted',
            event_timestamp=utc_now(),
            message_id='msg_2',
            channel='sms',
            conversion_value=None
        )
        
        # Act
        conversions = repository.get_conversion_events_with_value()
        
        # Assert
        assert conversion_with_value in conversions
        assert conversion_without_value not in conversions
    
    def test_create_event_with_invalid_data(self, repository, db_session):
        """Test that creating event with invalid data raises appropriate errors"""
        # Arrange - Missing required fields
        invalid_data = {
            'event_type': 'delivered',
            'event_timestamp': utc_now()
            # Missing contact_id, campaign_id, etc.
        }
        
        # Act & Assert
        with pytest.raises(Exception):
            repository.create(**invalid_data)
    
    def test_create_event_with_invalid_event_type(self, repository, db_session, sample_contact, sample_campaign):
        """Test that invalid event types are rejected"""
        # Arrange
        invalid_data = {
            'contact_id': sample_contact.id,
            'campaign_id': sample_campaign.id,
            'event_type': 'invalid_type',
            'event_timestamp': utc_now(),
            'message_id': 'msg_123',
            'channel': 'sms'
        }
        
        # Act & Assert
        with pytest.raises(ValueError, match="Invalid event type"):
            repository.create(**invalid_data)
    
    def test_create_event_with_invalid_channel(self, repository, db_session, sample_contact, sample_campaign):
        """Test that invalid channels are rejected"""
        # Arrange
        invalid_data = {
            'contact_id': sample_contact.id,
            'campaign_id': sample_campaign.id,
            'event_type': 'delivered',
            'event_timestamp': utc_now(),
            'message_id': 'msg_123',
            'channel': 'invalid_channel'
        }
        
        # Act & Assert
        with pytest.raises(ValueError, match="Invalid channel"):
            repository.create(**invalid_data)
    
    def test_get_engagement_funnel_data(self, repository, db_session, sample_contact, sample_campaign):
        """Test retrieving engagement funnel data for analytics"""
        # Arrange - Create full engagement funnel
        repository.create(
            contact_id=sample_contact.id,
            campaign_id=sample_campaign.id,
            event_type='delivered',
            event_timestamp=utc_now() - timedelta(minutes=30),
            message_id='msg_funnel',
            channel='sms'
        )
        
        repository.create(
            contact_id=sample_contact.id,
            campaign_id=sample_campaign.id,
            event_type='opened',
            event_timestamp=utc_now() - timedelta(minutes=25),
            message_id='msg_funnel',
            channel='sms'
        )
        
        repository.create(
            contact_id=sample_contact.id,
            campaign_id=sample_campaign.id,
            event_type='clicked',
            event_timestamp=utc_now() - timedelta(minutes=20),
            message_id='msg_funnel',
            channel='sms'
        )
        
        repository.create(
            contact_id=sample_contact.id,
            campaign_id=sample_campaign.id,
            event_type='responded',
            event_timestamp=utc_now() - timedelta(minutes=15),
            message_id='msg_funnel',
            channel='sms'
        )
        
        # Act
        funnel_data = repository.get_engagement_funnel_data(sample_campaign.id)
        
        # Assert
        assert funnel_data['delivered'] == 1
        assert funnel_data['opened'] == 1
        assert funnel_data['clicked'] == 1
        assert funnel_data['responded'] == 1
        assert funnel_data['converted'] == 0
    
    def test_search_events(self, repository, db_session, sample_contact, sample_campaign):
        """Test searching events by various criteria"""
        # Arrange
        event1 = repository.create(
            contact_id=sample_contact.id,
            campaign_id=sample_campaign.id,
            event_type='delivered',
            event_timestamp=utc_now(),
            message_id='msg_search_test',
            channel='sms',
            event_metadata={'subject': 'Special promotion'}
        )
        
        event2 = repository.create(
            contact_id=sample_contact.id,
            campaign_id=sample_campaign.id,
            event_type='opened',
            event_timestamp=utc_now(),
            message_id='msg_other',
            channel='email',
            event_metadata={'subject': 'Regular newsletter'}
        )
        
        # Act
        search_results = repository.search('special', fields=['event_metadata'])
        
        # Assert
        assert event1 in search_results
        assert event2 not in search_results
    
    def test_get_events_paginated(self, repository, db_session, sample_contact, sample_campaign):
        """Test paginated retrieval of events"""
        # Arrange
        for i in range(25):
            repository.create(
                contact_id=sample_contact.id,
                campaign_id=sample_campaign.id,
                event_type='delivered',
                event_timestamp=utc_now() + timedelta(seconds=i),
                message_id=f'msg_{i:02d}',
                channel='sms'
            )
        
        # Act
        pagination = PaginationParams(page=1, per_page=10)
        result = repository.get_paginated(pagination, order_by='event_timestamp')
        
        # Assert
        assert len(result.items) == 10
        assert result.total == 25
        assert result.pages == 3
        assert result.has_next is True
        assert result.has_prev is False
    
    def test_delete_old_events(self, repository, db_session, sample_contact, sample_campaign):
        """Test deletion of old events for data retention"""
        # Arrange
        now = utc_now()
        
        # Recent event (should be kept)
        recent_event = repository.create(
            contact_id=sample_contact.id,
            campaign_id=sample_campaign.id,
            event_type='delivered',
            event_timestamp=now - timedelta(days=30),
            message_id='msg_recent',
            channel='sms'
        )
        
        # Old event (should be deleted)
        old_event = repository.create(
            contact_id=sample_contact.id,
            campaign_id=sample_campaign.id,
            event_type='delivered',
            event_timestamp=now - timedelta(days=400),
            message_id='msg_old',
            channel='sms'
        )
        
        # Act
        cutoff_date = now - timedelta(days=365)  # 1 year retention
        deleted_count = repository.delete_events_older_than(cutoff_date)
        
        # Assert
        assert deleted_count == 1
        assert repository.get_by_id(recent_event.id) is not None
        assert repository.get_by_id(old_event.id) is None