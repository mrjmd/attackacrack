"""
TDD Tests for Campaign Repository Scheduling Methods - Phase 3C
Tests for new repository methods needed to support campaign scheduling

These tests MUST FAIL initially following TDD Red-Green-Refactor cycle.
Tests define the repository methods needed for scheduling functionality.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock, patch
from utils.datetime_utils import utc_now

# Repository and model imports
from repositories.campaign_repository import CampaignRepository
from repositories.base_repository import PaginationParams, PaginatedResult
from crm_database import Campaign
from extensions import db


class TestCampaignRepositoryScheduling:
    """TDD tests for campaign repository scheduling methods"""
    
    @pytest.fixture
    def campaign_repository(self, db_session):
        """Create campaign repository with test database session"""
        return CampaignRepository(db_session)
        
    @pytest.fixture
    def sample_campaigns(self, db_session):
        """Create sample campaigns for testing"""
        now = utc_now()
        
        campaigns = [
            # Scheduled campaign ready to run
            Campaign(
                name="Ready Campaign",
                status="scheduled",
                scheduled_at=now - timedelta(minutes=5),  # 5 minutes ago
                timezone="UTC"
            ),
            # Scheduled campaign not ready yet
            Campaign(
                name="Future Campaign", 
                status="scheduled",
                scheduled_at=now + timedelta(hours=1),  # 1 hour from now
                timezone="UTC"
            ),
            # Recurring campaign ready
            Campaign(
                name="Recurring Ready",
                status="scheduled", 
                scheduled_at=now - timedelta(minutes=10),
                next_run_at=now - timedelta(minutes=10),
                is_recurring=True,
                recurrence_pattern={"type": "daily", "interval": 1}
            ),
            # Archived campaign
            Campaign(
                name="Archived Campaign",
                status="complete",
                archived=True,
                archived_at=now - timedelta(days=7)
            ),
            # Draft campaign
            Campaign(
                name="Draft Campaign",
                status="draft"
            )
        ]
        
        for campaign in campaigns:
            db_session.add(campaign)
        db_session.commit()
        
        return campaigns
        
    def test_find_scheduled_campaigns_ready_to_run(self, campaign_repository, sample_campaigns):
        """Test finding campaigns ready for execution"""
        # Arrange
        current_time = utc_now()
        
        # Act - This will FAIL until method is implemented
        ready_campaigns = campaign_repository.find_scheduled_campaigns_ready_to_run(current_time)
        
        # Assert
        # Should return 2 campaigns: "Ready Campaign" and "Recurring Ready"
        assert len(ready_campaigns) == 2
        
        campaign_names = [c.name for c in ready_campaigns]
        assert "Ready Campaign" in campaign_names
        assert "Recurring Ready" in campaign_names
        assert "Future Campaign" not in campaign_names  # Not ready yet
        
        # All should have scheduled_at <= current_time
        for campaign in ready_campaigns:
            assert campaign.scheduled_at <= current_time
            assert campaign.status == "scheduled"
            
    def test_find_scheduled_campaigns_ready_to_run_empty(self, campaign_repository, db_session):
        """Test finding ready campaigns when none exist"""
        # Arrange - no campaigns in database
        current_time = utc_now()
        
        # Act - This will FAIL until method is implemented  
        ready_campaigns = campaign_repository.find_scheduled_campaigns_ready_to_run(current_time)
        
        # Assert
        assert len(ready_campaigns) == 0
        
    def test_find_scheduled_campaigns_by_status(self, campaign_repository, sample_campaigns):
        """Test finding campaigns by scheduled status"""
        # Act - This will FAIL until method is implemented
        scheduled_campaigns = campaign_repository.find_scheduled_campaigns()
        
        # Assert
        # Should return 3 scheduled campaigns from sample data
        assert len(scheduled_campaigns) == 3
        
        for campaign in scheduled_campaigns:
            assert campaign.status == "scheduled"
            
    def test_find_recurring_campaigns(self, campaign_repository, sample_campaigns):
        """Test finding recurring campaigns"""
        # Act - This will FAIL until method is implemented  
        recurring_campaigns = campaign_repository.find_recurring_campaigns()
        
        # Assert
        # Should return 1 recurring campaign from sample data
        assert len(recurring_campaigns) == 1
        assert recurring_campaigns[0].name == "Recurring Ready"
        assert recurring_campaigns[0].is_recurring is True
        assert recurring_campaigns[0].recurrence_pattern is not None
        
    def test_find_archived_campaigns(self, campaign_repository, sample_campaigns):
        """Test finding archived campaigns"""
        # Act - This will FAIL until method is implemented
        archived_campaigns = campaign_repository.find_archived_campaigns()
        
        # Assert
        # Should return 1 archived campaign from sample data
        assert len(archived_campaigns) == 1
        assert archived_campaigns[0].name == "Archived Campaign"
        assert archived_campaigns[0].archived is True
        assert archived_campaigns[0].archived_at is not None
        
    def test_find_campaigns_by_parent(self, campaign_repository, db_session):
        """Test finding campaigns created from duplication"""
        # Arrange - Create parent and child campaigns
        parent = Campaign(name="Original Campaign", status="complete")
        db_session.add(parent)
        db_session.commit()
        
        child1 = Campaign(name="Copy 1", status="draft", parent_campaign_id=parent.id)
        child2 = Campaign(name="Copy 2", status="scheduled", parent_campaign_id=parent.id)
        db_session.add(child1)
        db_session.add(child2)
        db_session.commit()
        
        # Act - This will FAIL until method is implemented
        child_campaigns = campaign_repository.find_campaigns_by_parent(parent.id)
        
        # Assert
        assert len(child_campaigns) == 2
        
        child_names = [c.name for c in child_campaigns]
        assert "Copy 1" in child_names
        assert "Copy 2" in child_names
        
        for campaign in child_campaigns:
            assert campaign.parent_campaign_id == parent.id
            
    def test_get_campaigns_by_timezone(self, campaign_repository, db_session):
        """Test getting campaigns filtered by timezone"""
        # Arrange
        ny_campaign = Campaign(name="NY Campaign", timezone="America/New_York")
        la_campaign = Campaign(name="LA Campaign", timezone="America/Los_Angeles") 
        utc_campaign = Campaign(name="UTC Campaign", timezone="UTC")
        
        db_session.add_all([ny_campaign, la_campaign, utc_campaign])
        db_session.commit()
        
        # Act - This will FAIL until method is implemented
        ny_campaigns = campaign_repository.get_campaigns_by_timezone("America/New_York")
        
        # Assert
        assert len(ny_campaigns) == 1
        assert ny_campaigns[0].name == "NY Campaign"
        assert ny_campaigns[0].timezone == "America/New_York"
        
    def test_update_campaign_schedule(self, campaign_repository, db_session):
        """Test updating campaign scheduling fields"""
        # Arrange
        campaign = Campaign(name="Test Campaign", status="draft")
        db_session.add(campaign)
        db_session.commit()
        
        scheduled_time = utc_now() + timedelta(hours=2)
        update_data = {
            'status': 'scheduled',
            'scheduled_at': scheduled_time,
            'timezone': 'America/New_York'
        }
        
        # Act - This will FAIL until method is implemented
        result = campaign_repository.update_schedule(campaign.id, update_data)
        
        # Assert
        assert result is True  # Update successful
        
        # Refresh from database
        db_session.refresh(campaign)
        assert campaign.status == 'scheduled'
        # Database stores naive datetime, so compare with naive version
        expected_naive = scheduled_time.replace(tzinfo=None) if scheduled_time.tzinfo else scheduled_time
        assert campaign.scheduled_at == expected_naive
        assert campaign.timezone == 'America/New_York'
        
    def test_update_recurring_campaign_next_run(self, campaign_repository, db_session):
        """Test updating next run time for recurring campaign"""
        # Arrange
        current_time = utc_now()
        campaign = Campaign(
            name="Recurring Campaign",
            status="scheduled",
            is_recurring=True,
            next_run_at=current_time
        )
        db_session.add(campaign)
        db_session.commit()
        
        new_next_run = current_time + timedelta(days=1)
        
        # Act - This will FAIL until method is implemented
        result = campaign_repository.update_next_run_time(campaign.id, new_next_run)
        
        # Assert
        assert result is True
        
        db_session.refresh(campaign)
        
        # Compare datetimes by converting to UTC if needed
        expected_utc = new_next_run.replace(tzinfo=None) if new_next_run.tzinfo else new_next_run
        actual_utc = campaign.next_run_at.replace(tzinfo=None) if campaign.next_run_at.tzinfo else campaign.next_run_at
        
        assert actual_utc == expected_utc
        
    def test_archive_campaign_repository_method(self, campaign_repository, db_session):
        """Test repository method for archiving campaign"""
        # Arrange
        campaign = Campaign(name="To Archive", status="complete")
        db_session.add(campaign)
        db_session.commit()
        
        archive_time = utc_now()
        
        # Act - This will FAIL until method is implemented
        result = campaign_repository.archive_campaign(campaign.id, archive_time)
        
        # Assert
        assert result is True
        
        db_session.refresh(campaign)
        assert campaign.archived is True
        
        # Compare datetimes by converting to UTC if needed
        expected_utc = archive_time.replace(tzinfo=None) if archive_time.tzinfo else archive_time
        actual_utc = campaign.archived_at.replace(tzinfo=None) if campaign.archived_at.tzinfo else campaign.archived_at
        
        assert actual_utc == expected_utc
        
    def test_unarchive_campaign_repository_method(self, campaign_repository, db_session):
        """Test repository method for unarchiving campaign"""
        # Arrange
        campaign = Campaign(
            name="Archived Campaign",
            status="complete", 
            archived=True,
            archived_at=utc_now() - timedelta(days=1)
        )
        db_session.add(campaign)
        db_session.commit()
        
        # Act - This will FAIL until method is implemented
        result = campaign_repository.unarchive_campaign(campaign.id)
        
        # Assert
        assert result is True
        
        db_session.refresh(campaign)
        assert campaign.archived is False
        assert campaign.archived_at is None
        
    def test_get_campaign_schedule_summary(self, campaign_repository, sample_campaigns):
        """Test getting schedule summary statistics"""
        # Act - This will FAIL until method is implemented
        summary = campaign_repository.get_schedule_summary()
        
        # Assert
        expected_summary = {
            'total_scheduled': 3,  # 3 scheduled campaigns in sample data
            'ready_to_run': 2,     # 2 ready to run 
            'recurring': 1,        # 1 recurring campaign
            'archived': 1          # 1 archived campaign
        }
        
        assert summary['total_scheduled'] == expected_summary['total_scheduled']
        assert summary['recurring'] == expected_summary['recurring'] 
        assert summary['archived'] == expected_summary['archived']
        
    def test_bulk_update_campaign_schedules(self, campaign_repository, db_session):
        """Test bulk updating multiple campaign schedules"""
        # Arrange
        campaigns = [
            Campaign(name=f"Campaign {i}", status="draft") for i in range(3)
        ]
        db_session.add_all(campaigns)
        db_session.commit()
        
        campaign_ids = [c.id for c in campaigns]
        new_scheduled_time = utc_now() + timedelta(hours=1)
        
        update_data = {
            'status': 'scheduled',
            'scheduled_at': new_scheduled_time,
            'timezone': 'UTC'
        }
        
        # Act - This will FAIL until method is implemented
        updated_count = campaign_repository.bulk_update_schedules(campaign_ids, update_data)
        
        # Assert  
        assert updated_count == 3
        
        # Verify all campaigns were updated
        for campaign in campaigns:
            db_session.refresh(campaign)
            assert campaign.status == 'scheduled'
            assert campaign.scheduled_at == new_scheduled_time
            assert campaign.timezone == 'UTC'
            
    def test_find_campaigns_with_failed_schedules(self, campaign_repository, db_session):
        """Test finding campaigns that failed to execute on schedule"""
        # Arrange - Create campaigns that should have run but didn't
        past_time = utc_now() - timedelta(hours=2)
        
        failed_campaign = Campaign(
            name="Failed Campaign",
            status="scheduled",  # Still scheduled but past time
            scheduled_at=past_time,
            timezone="UTC"
        )
        db_session.add(failed_campaign)
        db_session.commit()
        
        # Act - This will FAIL until method is implemented
        failed_campaigns = campaign_repository.find_failed_scheduled_campaigns()
        
        # Assert
        assert len(failed_campaigns) >= 1
        
        failed_names = [c.name for c in failed_campaigns]
        assert "Failed Campaign" in failed_names
        
        # All should be past their scheduled time but still in scheduled status
        for campaign in failed_campaigns:
            assert campaign.status == "scheduled"
            assert campaign.scheduled_at < utc_now() - timedelta(minutes=30)  # Grace period
            
    def test_get_next_scheduled_campaigns(self, campaign_repository, sample_campaigns):
        """Test getting next N campaigns scheduled to run"""
        # Act - This will FAIL until method is implemented
        next_campaigns = campaign_repository.get_next_scheduled_campaigns(limit=5)
        
        # Assert
        assert len(next_campaigns) <= 5
        
        # Should be ordered by scheduled_at ascending
        for i in range(1, len(next_campaigns)):
            assert next_campaigns[i-1].scheduled_at <= next_campaigns[i].scheduled_at
            
        # All should have scheduled_at in future
        current_time = utc_now()
        for campaign in next_campaigns:
            if campaign.scheduled_at:
                # Allow some that are ready to run (within last few minutes)
                assert campaign.scheduled_at >= current_time - timedelta(minutes=10)
                
    def test_search_scheduled_campaigns(self, campaign_repository, sample_campaigns):
        """Test searching within scheduled campaigns only"""
        # Act - This will FAIL until method is implemented  
        results = campaign_repository.search_scheduled_campaigns("Ready")
        
        # Assert
        # Should find campaigns with "Ready" in name that are scheduled
        assert len(results) >= 1
        
        found_names = [c.name for c in results]
        assert any("Ready" in name for name in found_names)
        
        # All results should be scheduled status
        for campaign in results:
            assert campaign.status == "scheduled"