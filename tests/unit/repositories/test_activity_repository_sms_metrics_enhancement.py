"""
TDD RED Phase: Tests for ActivityRepository SMS Metrics Enhancement
These tests MUST FAIL initially - testing new methods needed for SMSMetricsService refactoring
"""

import pytest
from datetime import datetime, timedelta
from utils.datetime_utils import utc_now
from unittest.mock import Mock, patch
from repositories.activity_repository import ActivityRepository
from repositories.base_repository import PaginationParams
from crm_database import Activity, Contact


class TestActivityRepositorySMSMetricsEnhancement:
    """Test SMS metrics-specific methods for ActivityRepository"""
    
    @pytest.fixture
    def repository(self, db_session):
        """Create ActivityRepository instance"""
        return ActivityRepository(session=db_session)
    
    @pytest.fixture
    def sample_contact(self, db_session):
        """Create a sample contact for testing"""
        contact = Contact(phone='+11234567890', first_name='Test', last_name='User')
        db_session.add(contact)
        db_session.flush()
        return contact
    
    @pytest.fixture
    def sample_activities(self, db_session, sample_contact):
        """Create sample activities for testing"""
        activities = []
        
        # Create message activities with different statuses
        activities.append(Activity(
            contact_id=sample_contact.id,
            activity_type='message',
            direction='outgoing',
            status='sent',
            created_at=utc_now()
        ))
        
        activities.append(Activity(
            contact_id=sample_contact.id,
            activity_type='message',
            direction='outgoing',
            status='delivered',
            created_at=utc_now() - timedelta(hours=1)
        ))
        
        activities.append(Activity(
            contact_id=sample_contact.id,
            activity_type='message',
            direction='outgoing',
            status='failed',
            activity_metadata={'bounce_type': 'hard', 'bounce_details': 'Invalid number'},
            created_at=utc_now() - timedelta(hours=2)
        ))
        
        activities.append(Activity(
            contact_id=sample_contact.id,
            activity_type='message',
            direction='incoming',
            status='received',
            created_at=utc_now() - timedelta(hours=3)
        ))
        
        for activity in activities:
            db_session.add(activity)
        
        db_session.flush()
        return activities

    def test_update_activity_status_with_metadata(self, repository, sample_activities):
        """Test updating activity status with metadata - MUST FAIL initially"""
        # Get the first activity
        activity = sample_activities[0]
        
        # This method should exist and update status with metadata
        bounce_metadata = {
            'bounce_type': 'hard',
            'bounce_details': 'Invalid number',
            'bounced_at': utc_now().isoformat()
        }
        
        # This method doesn't exist yet - should fail
        result = repository.update_activity_status_with_metadata(
            activity_id=activity.id,
            status='failed',
            metadata=bounce_metadata
        )
        
        # Verify update was successful
        assert result is not None
        assert result.status == 'failed'
        assert result.activity_metadata is not None
        assert result.activity_metadata['bounce_type'] == 'hard'
        assert result.activity_metadata['bounce_details'] == 'Invalid number'
        assert 'bounced_at' in result.activity_metadata
    
    def test_find_messages_by_date_range_and_direction(self, repository, sample_activities):
        """Test finding messages by date range and direction - MUST FAIL initially"""
        # Date range for the last 24 hours
        since_date = utc_now() - timedelta(hours=24)
        
        # This method should exist to find outgoing messages in date range
        outgoing_messages = repository.find_messages_by_date_range_and_direction(
            since_date=since_date,
            direction='outgoing'
        )
        
        # Should return 3 outgoing messages
        assert len(outgoing_messages) == 3
        for message in outgoing_messages:
            assert message.activity_type == 'message'
            assert message.direction == 'outgoing'
            assert message.created_at >= since_date
    
    def test_find_messages_by_contact_with_order(self, repository, sample_activities, sample_contact):
        """Test finding messages by contact with specific ordering - MUST FAIL initially"""
        # This method should exist to find messages for a contact ordered by creation time
        messages = repository.find_messages_by_contact_with_order(
            contact_id=sample_contact.id,
            order='created_at_desc',
            limit=10
        )
        
        # Should return 4 messages (3 outgoing, 1 incoming) ordered by creation time desc
        assert len(messages) == 4
        for message in messages:
            assert message.contact_id == sample_contact.id
            assert message.activity_type == 'message'
        
        # Verify ordering (newest first)
        for i in range(len(messages) - 1):
            assert messages[i].created_at >= messages[i + 1].created_at
    
    def test_get_message_status_counts_by_categories(self, repository, sample_activities):
        """Test getting message counts by status categories - MUST FAIL initially"""
        # Define status categories like in SMS metrics service
        status_categories = {
            'delivered': ['delivered', 'sent', 'received'],
            'bounced': ['failed', 'undelivered', 'rejected', 'blocked'],
            'pending': ['queued', 'sending', 'pending']
        }
        
        # This method should exist to count messages by status categories
        counts = repository.get_message_status_counts_by_categories(
            status_categories=status_categories,
            since_date=utc_now() - timedelta(hours=24),
            direction='outgoing'
        )
        
        # Should return counts for each category
        assert 'delivered' in counts
        assert 'bounced' in counts  
        assert 'pending' in counts
        assert counts['delivered'] == 2  # 'sent' and 'delivered' activities
        assert counts['bounced'] == 1    # 'failed' activity
        assert counts['pending'] == 0    # No pending activities
    
    def test_find_activities_with_bounce_metadata(self, repository, sample_activities):
        """Test finding activities with bounce metadata - MUST FAIL initially"""
        # This method should exist to find activities that have bounce information
        bounced_activities = repository.find_activities_with_bounce_metadata(
            since_date=utc_now() - timedelta(hours=24)
        )
        
        # Should find the activity with bounce metadata
        assert len(bounced_activities) == 1
        bounced = bounced_activities[0]
        assert bounced.activity_metadata is not None
        assert 'bounce_type' in bounced.activity_metadata
        assert bounced.activity_metadata['bounce_type'] == 'hard'
    
    def test_get_daily_message_stats(self, repository, sample_activities):
        """Test getting daily message statistics - MUST FAIL initially"""
        # This method should exist to get daily stats for dashboard/metrics
        stats = repository.get_daily_message_stats(days=7)
        
        # Should return list of daily stats
        assert isinstance(stats, list)
        assert len(stats) == 7  # 7 days of data
        
        # Each stat should have required fields
        today_stat = next((s for s in stats if s['date'] == utc_now().date()), None)
        assert today_stat is not None
        assert 'sent' in today_stat
        assert 'bounced' in today_stat
        assert 'bounce_rate' in today_stat
        assert today_stat['sent'] >= 0
        assert today_stat['bounced'] >= 0
    
    def test_update_activity_metadata(self, repository, sample_activities):
        """Test updating activity metadata - MUST FAIL initially"""
        activity = sample_activities[0]
        
        # New metadata to merge
        new_metadata = {
            'delivery_status': 'confirmed',
            'carrier_info': 'verizon'
        }
        
        # This method should exist to update/merge metadata
        result = repository.update_activity_metadata(
            activity_id=activity.id,
            metadata=new_metadata,
            merge=True
        )
        
        # Verify metadata was updated
        assert result is not None
        assert result.activity_metadata is not None
        assert result.activity_metadata['delivery_status'] == 'confirmed'
        assert result.activity_metadata['carrier_info'] == 'verizon'
        # Original metadata should still exist if merge=True
        assert result.updated_at is not None
    
    def test_find_failed_messages_with_details(self, repository, sample_activities):
        """Test finding failed messages with bounce details - MUST FAIL initially"""
        # This method should exist to find failed messages for bounce analysis
        failed_messages = repository.find_failed_messages_with_details(
            since_date=utc_now() - timedelta(hours=24),
            bounce_types=['hard', 'soft']
        )
        
        # Should find the failed message with bounce details
        assert len(failed_messages) == 1
        failed = failed_messages[0]
        assert failed.status == 'failed'
        assert failed.activity_metadata is not None
        assert failed.activity_metadata['bounce_type'] in ['hard', 'soft']
    
    def test_get_contact_message_summary(self, repository, sample_activities, sample_contact):
        """Test getting message summary for a contact - MUST FAIL initially"""
        # This method should exist to get comprehensive message stats for a contact
        summary = repository.get_contact_message_summary(contact_id=sample_contact.id)
        
        # Should return comprehensive summary
        assert summary is not None
        assert 'total_messages' in summary
        assert 'sent_count' in summary
        assert 'received_count' in summary
        assert 'delivered_count' in summary
        assert 'bounced_count' in summary
        assert 'recent_messages' in summary
        
        # Verify counts
        assert summary['total_messages'] == 4
        assert summary['sent_count'] == 3      # 3 outgoing messages
        assert summary['received_count'] == 1   # 1 incoming message
        assert summary['delivered_count'] == 1  # 1 delivered message
        assert summary['bounced_count'] == 1    # 1 failed message
        
        # Recent messages should be limited and ordered
        assert len(summary['recent_messages']) <= 10
    
    def test_bulk_update_activities_status(self, repository, sample_activities):
        """Test bulk updating multiple activities status - MUST FAIL initially"""
        # Get activity IDs to update
        activity_ids = [act.id for act in sample_activities[:2]]
        
        # This method should exist to bulk update activity statuses
        updated_count = repository.bulk_update_activities_status(
            activity_ids=activity_ids,
            status='processed',
            metadata={'processed_at': utc_now().isoformat()}
        )
        
        # Should return count of updated activities
        assert updated_count == 2
        
        # Verify activities were updated
        for activity_id in activity_ids:
            activity = repository.get_by_id(activity_id)
            assert activity.status == 'processed'
            assert activity.activity_metadata is not None
            assert 'processed_at' in activity.activity_metadata