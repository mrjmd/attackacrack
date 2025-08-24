"""
TDD Tests for Campaign Scheduling Schema - Phase 3C
Tests database schema changes needed for campaign scheduling functionality

These tests MUST FAIL initially to follow TDD Red-Green-Refactor cycle.
Tests define the new database fields required for scheduling features.
"""

import pytest
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo
from crm_database import Campaign, db
from utils.datetime_utils import utc_now


class TestCampaignSchedulingSchema:
    """Test database schema for campaign scheduling features"""
    
    def test_campaign_has_scheduled_at_field(self, db_session):
        """Test Campaign model has scheduled_at datetime field for future execution"""
        # This will FAIL until we add scheduled_at field to Campaign model
        campaign = Campaign(
            name="Test Scheduled Campaign",
            status="scheduled",
            scheduled_at=utc_now() + timedelta(hours=2)
        )
        
        db_session.add(campaign)
        db_session.commit()
        
        # Verify field exists and is accessible
        assert hasattr(campaign, 'scheduled_at')
        assert campaign.scheduled_at is not None
        assert isinstance(campaign.scheduled_at, datetime)
        
    def test_campaign_has_timezone_field(self, db_session):
        """Test Campaign model has timezone field for timezone-aware scheduling"""
        # This will FAIL until we add timezone field to Campaign model
        campaign = Campaign(
            name="Test Timezone Campaign",
            status="draft",
            timezone="America/New_York"
        )
        
        db_session.add(campaign)
        db_session.commit()
        
        assert hasattr(campaign, 'timezone')
        assert campaign.timezone == "America/New_York"
        
    def test_campaign_has_recurrence_pattern_field(self, db_session):
        """Test Campaign model has recurrence_pattern JSON field for recurring campaigns"""
        # This will FAIL until we add recurrence_pattern field
        recurrence_config = {
            "type": "weekly",
            "interval": 1,
            "days_of_week": [1, 3, 5],  # Monday, Wednesday, Friday
            "end_date": "2025-12-31"
        }
        
        campaign = Campaign(
            name="Test Recurring Campaign",
            status="draft",
            recurrence_pattern=recurrence_config
        )
        
        db_session.add(campaign)
        db_session.commit()
        
        assert hasattr(campaign, 'recurrence_pattern')
        assert campaign.recurrence_pattern == recurrence_config
        assert campaign.recurrence_pattern["type"] == "weekly"
        
    def test_campaign_has_next_run_at_field(self, db_session):
        """Test Campaign model has next_run_at field for tracking next execution"""
        # This will FAIL until we add next_run_at field
        next_run = utc_now() + timedelta(days=7)
        
        campaign = Campaign(
            name="Test Next Run Campaign",
            status="scheduled",
            next_run_at=next_run
        )
        
        db_session.add(campaign)
        db_session.commit()
        
        assert hasattr(campaign, 'next_run_at')
        assert campaign.next_run_at == next_run
        
    def test_campaign_has_is_recurring_field(self, db_session):
        """Test Campaign model has is_recurring boolean field"""
        # This will FAIL until we add is_recurring field
        campaign = Campaign(
            name="Test Recurring Flag Campaign",
            status="draft",
            is_recurring=True
        )
        
        db_session.add(campaign)
        db_session.commit()
        
        assert hasattr(campaign, 'is_recurring')
        assert campaign.is_recurring is True
        
    def test_campaign_has_parent_campaign_id_field(self, db_session):
        """Test Campaign model has parent_campaign_id for duplicated campaigns"""
        # This will FAIL until we add parent_campaign_id field
        parent = Campaign(name="Original Campaign", status="complete")
        db_session.add(parent)
        db_session.commit()
        
        duplicate = Campaign(
            name="Duplicated Campaign",
            status="draft",
            parent_campaign_id=parent.id
        )
        
        db_session.add(duplicate)
        db_session.commit()
        
        assert hasattr(duplicate, 'parent_campaign_id')
        assert duplicate.parent_campaign_id == parent.id
        
    def test_campaign_has_archived_field(self, db_session):
        """Test Campaign model has archived boolean field and archived_at timestamp"""
        # This will FAIL until we add archived and archived_at fields
        archived_time = utc_now()
        
        campaign = Campaign(
            name="Test Archived Campaign",
            status="complete",
            archived=True,
            archived_at=archived_time
        )
        
        db_session.add(campaign)
        db_session.commit()
        
        assert hasattr(campaign, 'archived')
        assert hasattr(campaign, 'archived_at')
        assert campaign.archived is True
        assert campaign.archived_at == archived_time
        
    def test_campaign_status_includes_scheduled(self, db_session):
        """Test Campaign status field accepts 'scheduled' value"""
        # This will FAIL until we update status validation to include 'scheduled'
        campaign = Campaign(
            name="Test Scheduled Status",
            status="scheduled"
        )
        
        db_session.add(campaign)
        db_session.commit()
        
        assert campaign.status == "scheduled"
        
    def test_campaign_scheduling_fields_default_values(self, db_session):
        """Test that new scheduling fields have appropriate default values"""
        # This will FAIL until we set proper defaults
        campaign = Campaign(
            name="Test Defaults Campaign",
            status="draft"
        )
        
        db_session.add(campaign)
        db_session.commit()
        
        # Check default values
        assert campaign.scheduled_at is None
        assert campaign.timezone == "UTC"  # Should default to UTC
        assert campaign.recurrence_pattern is None
        assert campaign.next_run_at is None
        assert campaign.is_recurring is False
        assert campaign.parent_campaign_id is None
        assert campaign.archived is False
        assert campaign.archived_at is None
        
    def test_campaign_parent_relationship(self, db_session):
        """Test Campaign model has parent relationship for campaign duplication"""
        # This will FAIL until we add the relationship
        parent = Campaign(name="Original Campaign", status="complete")
        db_session.add(parent)
        db_session.commit()
        
        child = Campaign(
            name="Child Campaign",
            status="draft",
            parent_campaign_id=parent.id
        )
        db_session.add(child)
        db_session.commit()
        
        # Test relationship exists
        assert hasattr(Campaign, 'parent_campaign')
        assert hasattr(Campaign, 'child_campaigns')
        
        # Refresh from database to load relationships
        db_session.refresh(parent)
        db_session.refresh(child)
        
        assert child.parent_campaign.id == parent.id
        assert parent.child_campaigns.count() == 1
        assert parent.child_campaigns.first().id == child.id