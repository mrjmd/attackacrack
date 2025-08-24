"""
TDD Integration Tests for Campaign Scheduling - Phase 3C  
End-to-end tests for complete campaign scheduling workflow

These tests MUST FAIL initially following TDD Red-Green-Refactor cycle.
Tests verify the complete integration of scheduling service, repository, and tasks.
"""

import pytest
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo
from unittest.mock import patch, Mock
from utils.datetime_utils import utc_now

# Integration imports
from services.campaign_scheduling_service import CampaignSchedulingService
from repositories.campaign_repository import CampaignRepository
from repositories.activity_repository import ActivityRepository
from crm_database import Campaign, Activity, db
from services.common.result import Result


class TestCampaignSchedulingIntegration:
    """Integration tests for complete campaign scheduling workflow"""
    
    @pytest.fixture
    def campaign_repository(self, db_session):
        """Create campaign repository with real database session"""
        return CampaignRepository(db_session)
        
    @pytest.fixture
    def activity_repository(self, db_session):
        """Create activity repository with real database session"""
        return ActivityRepository(db_session)
        
    @pytest.fixture
    def scheduling_service(self, campaign_repository, activity_repository):
        """Create scheduling service with real repositories"""
        # This will FAIL until service is created
        return CampaignSchedulingService(
            campaign_repository=campaign_repository,
            activity_repository=activity_repository
        )
        
    @pytest.fixture
    def sample_campaign(self, db_session):
        """Create a sample campaign for testing"""
        campaign = Campaign(
            name="Test Campaign",
            status="draft",
            template_a="Hello {{first_name}}, we have a great opportunity!",
            campaign_type="blast",
            daily_limit=125,
            business_hours_only=True,
            timezone="UTC"
        )
        
        db_session.add(campaign)
        db_session.commit()
        return campaign
        
    def test_complete_campaign_scheduling_workflow(self, scheduling_service, sample_campaign, db_session):
        """Test complete workflow: draft -> scheduled -> executed"""
        # Phase 1: Schedule the campaign
        scheduled_time = utc_now() + timedelta(hours=2)
        timezone = "America/New_York"
        
        # This will FAIL until scheduling service is implemented
        result = scheduling_service.schedule_campaign(
            campaign_id=sample_campaign.id,
            scheduled_at=scheduled_time,
            timezone=timezone
        )
        
        assert result.is_success
        
        # Verify campaign was updated in database
        db_session.refresh(sample_campaign)
        assert sample_campaign.status == "scheduled"
        # Compare as naive UTC since database stores timezone-naive datetimes
        expected_utc = scheduled_time.astimezone(ZoneInfo('UTC')).replace(tzinfo=None)
        assert sample_campaign.scheduled_at == expected_utc
        assert sample_campaign.timezone == timezone
        
        # Phase 2: Check if campaign is ready to run (simulate future time)
        future_time = scheduled_time + timedelta(minutes=5)
        ready_campaigns = scheduling_service.get_campaigns_ready_to_run(future_time)
        
        assert len(ready_campaigns) == 1
        assert ready_campaigns[0].id == sample_campaign.id
        
        # Phase 3: Execute the scheduled campaign
        execute_result = scheduling_service.execute_scheduled_campaign(sample_campaign.id)
        assert execute_result.is_success
        
        # Verify campaign status changed to running
        db_session.refresh(sample_campaign)
        assert sample_campaign.status == "running"
        assert sample_campaign.scheduled_at is None  # Cleared after execution
        
    def test_recurring_campaign_workflow(self, scheduling_service, sample_campaign, db_session):
        """Test complete recurring campaign workflow"""
        # Setup recurring configuration
        start_time = utc_now() + timedelta(hours=1)
        recurrence_config = {
            "type": "daily",
            "interval": 1,
            "end_date": (utc_now() + timedelta(days=30)).strftime("%Y-%m-%d")
        }
        
        # Create recurring campaign - This will FAIL until implemented
        result = scheduling_service.create_recurring_campaign(
            campaign_id=sample_campaign.id,
            start_at=start_time,
            recurrence_pattern=recurrence_config,
            timezone="America/New_York"
        )
        
        assert result.is_success
        
        # Verify recurring setup
        db_session.refresh(sample_campaign)
        assert sample_campaign.is_recurring is True
        assert sample_campaign.recurrence_pattern == recurrence_config
        # Compare as naive UTC since database stores timezone-naive datetimes
        expected_utc = start_time.astimezone(ZoneInfo('UTC')).replace(tzinfo=None)
        assert sample_campaign.next_run_at == expected_utc
        
        # Simulate execution
        execute_result = scheduling_service.execute_scheduled_campaign(sample_campaign.id)
        assert execute_result.is_success
        
        # Verify next run time was calculated  
        db_session.refresh(sample_campaign)
        expected_next_run = start_time + timedelta(days=1)  # Daily recurrence
        expected_next_utc = expected_next_run.astimezone(ZoneInfo('UTC')).replace(tzinfo=None)
        assert sample_campaign.next_run_at == expected_next_utc
        assert sample_campaign.is_recurring is True  # Still recurring
        
    def test_campaign_duplication_with_scheduling(self, scheduling_service, sample_campaign, db_session):
        """Test duplicating campaign and scheduling the copy"""
        # Duplicate with immediate scheduling
        scheduled_time = utc_now() + timedelta(hours=3)
        
        # This will FAIL until duplication with scheduling is implemented
        result = scheduling_service.duplicate_campaign(
            campaign_id=sample_campaign.id,
            new_name="Duplicate Campaign with Schedule",
            scheduled_at=scheduled_time,
            timezone="America/Los_Angeles"
        )
        
        assert result.is_success
        duplicate_id = result.data['campaign_id']
        
        # Verify duplicate was created and scheduled
        duplicate = db_session.get(Campaign, duplicate_id)
        assert duplicate is not None
        assert duplicate.name == "Duplicate Campaign with Schedule"
        assert duplicate.parent_campaign_id == sample_campaign.id
        assert duplicate.status == "scheduled"
        expected_utc_dup = scheduled_time.astimezone(ZoneInfo('UTC')).replace(tzinfo=None)
        assert duplicate.scheduled_at == expected_utc_dup
        assert duplicate.timezone == "America/Los_Angeles"
        
        # Verify original settings were copied
        assert duplicate.template_a == sample_campaign.template_a
        assert duplicate.campaign_type == sample_campaign.campaign_type
        assert duplicate.daily_limit == sample_campaign.daily_limit
        
    def test_timezone_conversion_integration(self, scheduling_service, sample_campaign, db_session):
        """Test timezone conversion works end-to-end"""
        # Schedule in Eastern Time
        local_time = datetime(2025, 8, 25, 14, 0, 0)  # 2 PM ET
        timezone = "America/New_York"
        
        # This will FAIL until timezone conversion is implemented
        result = scheduling_service.schedule_campaign(
            campaign_id=sample_campaign.id,
            scheduled_at=local_time,
            timezone=timezone
        )
        
        assert result.is_success
        
        # Verify time was converted to UTC and stored
        db_session.refresh(sample_campaign)
        
        # Convert expected time manually for verification
        et_zone = ZoneInfo("America/New_York")
        local_with_tz = local_time.replace(tzinfo=et_zone)
        expected_utc = local_with_tz.astimezone(ZoneInfo("UTC"))
        
        assert sample_campaign.scheduled_at == expected_utc.replace(tzinfo=None)
        assert sample_campaign.timezone == timezone
        
    def test_campaign_archiving_workflow(self, scheduling_service, sample_campaign, db_session):
        """Test complete campaign archiving workflow"""
        # First complete the campaign
        sample_campaign.status = "complete"
        db_session.commit()
        
        # Archive the campaign - This will FAIL until archiving is implemented
        result = scheduling_service.archive_campaign(
            campaign_id=sample_campaign.id,
            reason="Campaign completed successfully"
        )
        
        assert result.is_success
        
        # Verify campaign was archived
        db_session.refresh(sample_campaign)
        assert sample_campaign.archived is True
        assert sample_campaign.archived_at is not None
        
        # Verify archived campaigns can be retrieved
        archived_campaigns = scheduling_service.get_archived_campaigns()
        assert len(archived_campaigns) == 1
        assert archived_campaigns[0].id == sample_campaign.id
        
        # Test unarchiving
        unarchive_result = scheduling_service.unarchive_campaign(sample_campaign.id)
        assert unarchive_result.is_success
        
        db_session.refresh(sample_campaign)
        assert sample_campaign.archived is False
        assert sample_campaign.archived_at is None
        
    def test_bulk_campaign_scheduling(self, scheduling_service, db_session):
        """Test bulk scheduling multiple campaigns"""
        # Create multiple campaigns
        campaigns = []
        for i in range(3):
            campaign = Campaign(
                name=f"Bulk Campaign {i+1}",
                status="draft",
                template_a="Test message {{first_name}}",
                campaign_type="blast"
            )
            campaigns.append(campaign)
            db_session.add(campaign)
        
        db_session.commit()
        campaign_ids = [c.id for c in campaigns]
        
        # Bulk schedule - This will FAIL until bulk scheduling is implemented
        scheduled_time = utc_now() + timedelta(hours=4)
        result = scheduling_service.bulk_schedule_campaigns(
            campaign_ids=campaign_ids,
            scheduled_at=scheduled_time,
            timezone="UTC"
        )
        
        assert result.is_success
        assert result.data['campaigns_scheduled'] == 3
        
        # Verify all campaigns were scheduled
        for campaign in campaigns:
            db_session.refresh(campaign)
            assert campaign.status == "scheduled"
            expected_bulk_utc = scheduled_time.astimezone(ZoneInfo('UTC')).replace(tzinfo=None)
            assert campaign.scheduled_at == expected_bulk_utc
            assert campaign.timezone == "UTC"
            
    def test_failed_schedule_cleanup(self, scheduling_service, db_session):
        """Test cleanup of failed scheduled campaigns"""
        # Create campaign that should have run but failed (25+ hours ago to trigger cleanup)
        past_time = utc_now() - timedelta(hours=25)
        
        failed_campaign = Campaign(
            name="Failed Campaign",
            status="scheduled",  # Still scheduled but past time
            scheduled_at=past_time,
            timezone="UTC"
        )
        
        db_session.add(failed_campaign)
        db_session.commit()
        
        # Cleanup failed schedules - This will FAIL until cleanup is implemented
        cleanup_count = scheduling_service.cleanup_failed_schedules()
        
        assert cleanup_count > 0
        
        # Verify campaign was marked as failed
        db_session.refresh(failed_campaign)
        assert failed_campaign.status == "failed" or failed_campaign.status == "draft"
        
    def test_schedule_validation_integration(self, scheduling_service, sample_campaign):
        """Test complete schedule validation workflow"""
        # Test scheduling in the past (should fail)
        past_time = utc_now() - timedelta(hours=1)
        
        result = scheduling_service.schedule_campaign(
            campaign_id=sample_campaign.id,
            scheduled_at=past_time,
            timezone="UTC"
        )
        
        assert result.is_failure
        assert "past" in result.error.lower()
        
        # Test invalid timezone (should fail)  
        future_time = utc_now() + timedelta(hours=1)
        
        result = scheduling_service.schedule_campaign(
            campaign_id=sample_campaign.id,
            scheduled_at=future_time,
            timezone="Invalid/Timezone"
        )
        
        assert result.is_failure
        assert "timezone" in result.error.lower()
        
        # Test valid scheduling (should succeed)
        result = scheduling_service.schedule_campaign(
            campaign_id=sample_campaign.id,
            scheduled_at=future_time,
            timezone="America/New_York"
        )
        
        assert result.is_success
        
    def test_recurring_pattern_validation(self, scheduling_service, sample_campaign):
        """Test validation of recurring patterns"""
        start_time = utc_now() + timedelta(hours=1)
        
        # Test invalid recurrence type
        invalid_config = {
            "type": "invalid_type",
            "interval": 1
        }
        
        result = scheduling_service.create_recurring_campaign(
            campaign_id=sample_campaign.id,
            start_at=start_time,
            recurrence_pattern=invalid_config,
            timezone="UTC"
        )
        
        assert result.is_failure
        assert "recurrence" in result.error.lower() or "type" in result.error.lower()
        
        # Test valid weekly pattern
        valid_config = {
            "type": "weekly",
            "interval": 1,
            "days_of_week": [1, 3, 5],  # Mon, Wed, Fri
            "end_date": (utc_now() + timedelta(days=60)).strftime("%Y-%m-%d")
        }
        
        result = scheduling_service.create_recurring_campaign(
            campaign_id=sample_campaign.id,
            start_at=start_time,
            recurrence_pattern=valid_config,
            timezone="UTC"
        )
        
        assert result.is_success
        
    # NOTE: Calendar data integration test removed - feature not yet implemented
    # def test_campaign_calendar_data_integration(self, scheduling_service, db_session):
    #     """Test getting calendar data for scheduled campaigns"""
    #     # This would require implementing get_campaign_calendar_data method
    #     # in the campaign scheduling service - future enhancement
    #     pass
        
    def test_performance_bulk_operations(self, scheduling_service, db_session):
        """Test performance of bulk operations"""
        # Create many campaigns for performance testing
        campaigns = []
        for i in range(50):  # 50 campaigns
            campaign = Campaign(
                name=f"Performance Test Campaign {i+1}",
                status="draft",
                template_a="Test message",
                campaign_type="blast"
            )
            campaigns.append(campaign)
            
        db_session.add_all(campaigns)
        db_session.commit()
        
        campaign_ids = [c.id for c in campaigns]
        scheduled_time = utc_now() + timedelta(hours=1)
        
        # Time the bulk operation - This will FAIL until bulk operations are optimized
        import time
        start_time = time.time()
        
        result = scheduling_service.bulk_schedule_campaigns(
            campaign_ids=campaign_ids,
            scheduled_at=scheduled_time,
            timezone="UTC"
        )
        
        end_time = time.time()
        operation_time = end_time - start_time
        
        assert result.is_success
        assert result.data['campaigns_scheduled'] == 50
        
        # Should complete within reasonable time (adjust threshold as needed)
        assert operation_time < 5.0  # 5 seconds max for 50 campaigns
        
    @patch('tasks.campaign_scheduling_tasks.execute_scheduled_campaign.delay')
    def test_integration_with_celery_tasks(self, mock_task, scheduling_service, sample_campaign, db_session):
        """Test integration between service and Celery tasks"""
        # Schedule a campaign
        scheduled_time = utc_now() + timedelta(minutes=30)
        
        result = scheduling_service.schedule_campaign(
            campaign_id=sample_campaign.id,
            scheduled_at=scheduled_time,
            timezone="UTC"
        )
        
        assert result.is_success
        
        # Simulate the scheduled task check finding ready campaigns
        ready_campaigns = scheduling_service.get_campaigns_ready_to_run(scheduled_time + timedelta(minutes=5))
        
        # Verify the task would be triggered
        assert len(ready_campaigns) == 1
        assert ready_campaigns[0].id == sample_campaign.id
        
        # Simulate task execution
        execution_result = scheduling_service.execute_scheduled_campaign(sample_campaign.id)
        assert execution_result.is_success
        
        # Verify campaign state after task execution
        # Reload campaign from database instead of refreshing detached object
        updated_campaign = db_session.get(Campaign, sample_campaign.id)
        assert updated_campaign.status == "running"