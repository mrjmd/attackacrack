"""
TDD Tests for CampaignSchedulingService - Phase 3C
Comprehensive tests for campaign scheduling functionality

These tests MUST FAIL initially following TDD Red-Green-Refactor cycle.
Tests define the complete API for campaign scheduling, timezone handling,
recurring campaigns, and campaign lifecycle management.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch, call
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo
from utils.datetime_utils import utc_now

# Imports that will FAIL until we create the service
from services.campaign_scheduling_service import CampaignSchedulingService
from repositories.campaign_repository import CampaignRepository
from repositories.activity_repository import ActivityRepository
from crm_database import Campaign, Activity
from services.common.result import Result


class TestCampaignSchedulingService:
    """TDD tests for campaign scheduling service"""
    
    @pytest.fixture
    def mock_campaign_repository(self):
        """Mock campaign repository for dependency injection"""
        mock_repo = Mock(spec=CampaignRepository)
        mock_repo.create.return_value = Mock(spec=Campaign)
        mock_repo.get_by_id.return_value = Mock(spec=Campaign)
        mock_repo.commit.return_value = None
        return mock_repo
        
    @pytest.fixture
    def mock_activity_repository(self):
        """Mock activity repository for tracking"""
        mock_repo = Mock(spec=ActivityRepository)
        mock_repo.create.return_value = Mock(spec=Activity)
        return mock_repo
        
    @pytest.fixture
    def scheduling_service(self, mock_campaign_repository, mock_activity_repository):
        """Create scheduling service with mocked dependencies"""
        # This will FAIL until we create CampaignSchedulingService
        return CampaignSchedulingService(
            campaign_repository=mock_campaign_repository,
            activity_repository=mock_activity_repository
        )
        
    def test_schedule_campaign_for_future_execution(self, scheduling_service, mock_campaign_repository):
        """Test scheduling a campaign for future execution"""
        # Arrange
        campaign_id = 1
        scheduled_time = utc_now() + timedelta(hours=2)
        timezone = "America/New_York"
        
        mock_campaign = Mock(spec=Campaign)
        mock_campaign.id = campaign_id
        mock_campaign.status = "draft"
        mock_campaign_repository.get_by_id.return_value = mock_campaign
        
        # Act - This will FAIL until method exists
        result = scheduling_service.schedule_campaign(
            campaign_id=campaign_id,
            scheduled_at=scheduled_time,
            timezone=timezone
        )
        
        # Assert
        assert result.is_success
        
        # Verify campaign was updated
        assert mock_campaign.status == "scheduled"
        # The service stores naive datetime, so compare without timezone
        assert mock_campaign.scheduled_at == scheduled_time.replace(tzinfo=None)
        assert mock_campaign.timezone == timezone
        mock_campaign_repository.commit.assert_called_once()
        
    def test_schedule_campaign_with_timezone_conversion(self, scheduling_service, mock_campaign_repository):
        """Test scheduling with timezone conversion to UTC"""
        # Arrange
        campaign_id = 1
        # 2 PM Eastern Time
        local_time = datetime(2025, 8, 25, 14, 0, 0)
        timezone = "America/New_York"
        
        mock_campaign = Mock(spec=Campaign)
        mock_campaign.id = campaign_id
        mock_campaign.status = "draft"
        mock_campaign_repository.get_by_id.return_value = mock_campaign
        
        # Act - This will FAIL until timezone conversion is implemented
        result = scheduling_service.schedule_campaign(
            campaign_id=campaign_id,
            scheduled_at=local_time,
            timezone=timezone
        )
        
        # Assert
        assert result.is_success
        
        # Verify timezone conversion occurred (2 PM ET = 6 PM UTC in summer)
        expected_utc = local_time.replace(tzinfo=ZoneInfo(timezone)).astimezone(ZoneInfo("UTC"))
        assert mock_campaign.scheduled_at == expected_utc.replace(tzinfo=None)
        
    def test_create_recurring_campaign_daily(self, scheduling_service, mock_campaign_repository):
        """Test creating daily recurring campaign"""
        # Arrange
        campaign_id = 1
        start_time = utc_now() + timedelta(hours=1)
        recurrence_config = {
            "type": "daily",
            "interval": 1,
            "end_date": "2025-12-31"
        }
        
        mock_campaign = Mock(spec=Campaign)
        mock_campaign.id = campaign_id
        mock_campaign.status = "draft"
        mock_campaign_repository.get_by_id.return_value = mock_campaign
        
        # Act - This will FAIL until recurring logic exists
        result = scheduling_service.create_recurring_campaign(
            campaign_id=campaign_id,
            start_at=start_time,
            recurrence_pattern=recurrence_config,
            timezone="UTC"
        )
        
        # Assert
        assert result.is_success
        
        # Verify recurring configuration
        assert mock_campaign.is_recurring is True
        assert mock_campaign.recurrence_pattern == recurrence_config
        assert mock_campaign.scheduled_at == start_time
        assert mock_campaign.next_run_at == start_time
        
    def test_create_recurring_campaign_weekly(self, scheduling_service, mock_campaign_repository):
        """Test creating weekly recurring campaign with specific days"""
        # Arrange
        campaign_id = 1
        start_time = utc_now() + timedelta(hours=1)
        recurrence_config = {
            "type": "weekly",
            "interval": 1,
            "days_of_week": [1, 3, 5],  # Monday, Wednesday, Friday
            "end_date": "2025-12-31"
        }
        
        mock_campaign = Mock(spec=Campaign)
        mock_campaign.status = "draft"
        mock_campaign_repository.get_by_id.return_value = mock_campaign
        
        # Act - This will FAIL until weekly recurrence logic exists
        result = scheduling_service.create_recurring_campaign(
            campaign_id=campaign_id,
            start_at=start_time,
            recurrence_pattern=recurrence_config,
            timezone="America/New_York"
        )
        
        # Assert
        assert result.is_success
        assert mock_campaign.recurrence_pattern["days_of_week"] == [1, 3, 5]
        
    def test_calculate_next_run_daily_recurring(self, scheduling_service):
        """Test calculating next run time for daily recurring campaign"""
        # Arrange
        current_time = datetime(2025, 8, 25, 10, 0, 0)  # Monday 10 AM
        recurrence_config = {
            "type": "daily",
            "interval": 1
        }
        
        # Act - This will FAIL until next run calculation exists
        next_run = scheduling_service.calculate_next_run(
            current_run=current_time,
            pattern=recurrence_config,
            timezone="UTC"
        )
        
        # Assert - Next run should be tomorrow at same time (timezone-aware)
        expected = (current_time + timedelta(days=1)).replace(tzinfo=ZoneInfo("UTC"))
        assert next_run == expected
        
    def test_calculate_next_run_weekly_recurring(self, scheduling_service):
        """Test calculating next run time for weekly recurring campaign"""
        # Arrange
        current_time = datetime(2025, 8, 25, 10, 0, 0)  # Monday 10 AM
        recurrence_config = {
            "type": "weekly",
            "interval": 1,
            "days_of_week": [0, 2, 4]  # Mon, Wed, Fri (0=Mon, 2=Wed, 4=Fri)
        }
        
        # Act - This will FAIL until weekly calculation exists
        next_run = scheduling_service.calculate_next_run(
            current_run=current_time,
            pattern=recurrence_config,
            timezone="UTC"
        )
        
        # Assert - Next run should be Wednesday (2 days later)
        expected = (current_time + timedelta(days=2)).replace(tzinfo=ZoneInfo("UTC"))
        assert next_run == expected
        
    def test_get_scheduled_campaigns_ready_to_run(self, scheduling_service, mock_campaign_repository):
        """Test getting campaigns ready for execution"""
        # Arrange
        current_time = utc_now()
        
        # Mock campaigns - some ready, some not
        ready_campaign = Mock(spec=Campaign)
        ready_campaign.id = 1
        ready_campaign.scheduled_at = current_time - timedelta(minutes=5)
        ready_campaign.status = "scheduled"
        
        future_campaign = Mock(spec=Campaign)
        future_campaign.id = 2
        future_campaign.scheduled_at = current_time + timedelta(hours=1)
        future_campaign.status = "scheduled"
        
        mock_campaign_repository.find_scheduled_campaigns_ready_to_run.return_value = [ready_campaign]
        
        # Act - This will FAIL until method exists
        ready_campaigns = scheduling_service.get_campaigns_ready_to_run(current_time)
        
        # Assert
        assert len(ready_campaigns) == 1
        assert ready_campaigns[0].id == 1
        mock_campaign_repository.find_scheduled_campaigns_ready_to_run.assert_called_once_with(current_time)
        
    def test_execute_scheduled_campaign_non_recurring(self, scheduling_service, mock_campaign_repository):
        """Test executing a one-time scheduled campaign"""
        # Arrange
        campaign_id = 1
        mock_campaign = Mock(spec=Campaign)
        mock_campaign.id = campaign_id
        mock_campaign.is_recurring = False
        mock_campaign.status = "scheduled"
        mock_campaign_repository.get_by_id.return_value = mock_campaign
        
        # Act - This will FAIL until execution logic exists
        result = scheduling_service.execute_scheduled_campaign(campaign_id)
        
        # Assert
        assert result.is_success
        
        # Verify campaign status changed to running
        assert mock_campaign.status == "running"
        assert mock_campaign.scheduled_at is None  # Clear scheduled time
        mock_campaign_repository.commit.assert_called_once()
        
    def test_execute_scheduled_campaign_recurring(self, scheduling_service, mock_campaign_repository):
        """Test executing recurring campaign and calculating next run"""
        # Arrange
        campaign_id = 1
        current_time = utc_now()
        
        mock_campaign = Mock(spec=Campaign)
        mock_campaign.id = campaign_id
        mock_campaign.is_recurring = True
        mock_campaign.status = "scheduled"
        mock_campaign.recurrence_pattern = {"type": "daily", "interval": 1}
        mock_campaign.timezone = "UTC"
        mock_campaign_repository.get_by_id.return_value = mock_campaign
        
        # Mock next run calculation
        with patch.object(scheduling_service, 'calculate_next_run') as mock_calc:
            next_run_time = current_time + timedelta(days=1)
            mock_calc.return_value = next_run_time
            
            # Act - This will FAIL until recurring execution logic exists
            result = scheduling_service.execute_scheduled_campaign(campaign_id)
        
        # Assert
        assert result.is_success
        
        # Verify campaign remains scheduled with new next run time
        assert mock_campaign.status == "running"  # Status changes during execution
        assert mock_campaign.next_run_at == next_run_time
        
    def test_duplicate_campaign(self, scheduling_service, mock_campaign_repository):
        """Test duplicating an existing campaign with all settings"""
        # Arrange
        original_id = 1
        original_campaign = Mock(spec=Campaign)
        original_campaign.id = original_id
        original_campaign.name = "Original Campaign"
        original_campaign.template_a = "Hello {{first_name}}"
        original_campaign.campaign_type = "blast"
        original_campaign.daily_limit = 125
        original_campaign.business_hours_only = True
        original_campaign.quiet_hours_start = time(20, 0)
        original_campaign.quiet_hours_end = time(9, 0)
        
        new_campaign = Mock(spec=Campaign)
        new_campaign.id = 2
        
        mock_campaign_repository.get_by_id.return_value = original_campaign
        mock_campaign_repository.create.return_value = new_campaign
        
        # Act - This will FAIL until duplication logic exists
        result = scheduling_service.duplicate_campaign(
            campaign_id=original_id,
            new_name="Duplicated Campaign"
        )
        
        # Assert
        assert result.is_success
        assert result.data['campaign_id'] == 2
        
        # Verify create was called with proper data
        mock_campaign_repository.create.assert_called_once()
        create_kwargs = mock_campaign_repository.create.call_args.kwargs
        
        assert create_kwargs['name'] == "Duplicated Campaign"
        assert create_kwargs['template_a'] == "Hello {{first_name}}"
        assert create_kwargs['campaign_type'] == "blast"
        assert create_kwargs['daily_limit'] == 125
        assert create_kwargs['parent_campaign_id'] == original_id
        assert create_kwargs['status'] == "draft"
        
    def test_duplicate_campaign_with_schedule(self, scheduling_service, mock_campaign_repository):
        """Test duplicating campaign with new schedule"""
        # Arrange
        original_id = 1
        scheduled_time = utc_now() + timedelta(hours=3)
        
        original_campaign = Mock(spec=Campaign)
        original_campaign.id = original_id
        original_campaign.name = "Original"
        
        new_campaign = Mock(spec=Campaign)
        new_campaign.id = 2
        
        mock_campaign_repository.get_by_id.return_value = original_campaign
        mock_campaign_repository.create.return_value = new_campaign
        
        # Act - This will FAIL until scheduling in duplication exists
        result = scheduling_service.duplicate_campaign(
            campaign_id=original_id,
            new_name="Scheduled Duplicate",
            scheduled_at=scheduled_time,
            timezone="America/New_York"
        )
        
        # Assert
        assert result.is_success
        
        # Verify scheduling was applied
        create_kwargs = mock_campaign_repository.create.call_args[1]
        assert create_kwargs['scheduled_at'] == scheduled_time
        assert create_kwargs['timezone'] == "America/New_York"
        assert create_kwargs['status'] == "scheduled"
        
    def test_archive_campaign(self, scheduling_service, mock_campaign_repository, mock_activity_repository):
        """Test archiving a completed campaign"""
        # Arrange
        campaign_id = 1
        mock_campaign = Mock(spec=Campaign)
        mock_campaign.id = campaign_id
        mock_campaign.status = "complete"
        mock_campaign_repository.get_by_id.return_value = mock_campaign
        
        # Act - This will FAIL until archiving logic exists
        result = scheduling_service.archive_campaign(
            campaign_id=campaign_id,
            reason="Campaign completed successfully"
        )
        
        # Assert
        assert result.is_success
        
        # Verify campaign was archived
        assert mock_campaign.archived is True
        assert mock_campaign.archived_at is not None
        mock_campaign_repository.commit.assert_called_once()
        
        # Verify activity was logged
        mock_activity_repository.create.assert_called_once()
        activity_kwargs = mock_activity_repository.create.call_args.kwargs
        assert activity_kwargs['body'] == "Campaign completed successfully"
        assert activity_kwargs['activity_type'] == "system"
        
    def test_get_archived_campaigns(self, scheduling_service, mock_campaign_repository):
        """Test retrieving archived campaigns"""
        # Arrange
        archived_campaigns = [Mock(spec=Campaign), Mock(spec=Campaign)]
        mock_campaign_repository.find_archived_campaigns.return_value = archived_campaigns
        
        # Act - This will FAIL until archived query exists
        result = scheduling_service.get_archived_campaigns()
        
        # Assert
        assert len(result) == 2
        mock_campaign_repository.find_archived_campaigns.assert_called_once()
        
    def test_unarchive_campaign(self, scheduling_service, mock_campaign_repository):
        """Test unarchiving a campaign"""
        # Arrange
        campaign_id = 1
        mock_campaign = Mock(spec=Campaign)
        mock_campaign.id = campaign_id
        mock_campaign.archived = True
        mock_campaign_repository.get_by_id.return_value = mock_campaign
        
        # Act - This will FAIL until unarchiving logic exists
        result = scheduling_service.unarchive_campaign(campaign_id)
        
        # Assert
        assert result.is_success
        
        # Verify campaign was unarchived
        assert mock_campaign.archived is False
        assert mock_campaign.archived_at is None
        mock_campaign_repository.commit.assert_called_once()
        
    def test_schedule_campaign_validation_errors(self, scheduling_service, mock_campaign_repository):
        """Test validation errors when scheduling campaigns"""
        # Test scheduling campaign that doesn't exist
        mock_campaign_repository.get_by_id.return_value = None
        
        result = scheduling_service.schedule_campaign(
            campaign_id=999,
            scheduled_at=utc_now() + timedelta(hours=1),
            timezone="UTC"
        )
        
        assert result.is_failure
        assert "not found" in result.error.lower()
        
    def test_schedule_campaign_past_time_validation(self, scheduling_service, mock_campaign_repository):
        """Test validation error for scheduling in the past"""
        # Arrange
        mock_campaign = Mock(spec=Campaign)
        mock_campaign.status = "draft"
        mock_campaign_repository.get_by_id.return_value = mock_campaign
        
        past_time = utc_now() - timedelta(hours=1)
        
        # Act - This will FAIL until validation exists
        result = scheduling_service.schedule_campaign(
            campaign_id=1,
            scheduled_at=past_time,
            timezone="UTC"
        )
        
        # Assert
        assert result.is_failure
        assert "past" in result.error.lower()
        
    def test_invalid_timezone_validation(self, scheduling_service, mock_campaign_repository):
        """Test validation error for invalid timezone"""
        # Arrange
        mock_campaign = Mock(spec=Campaign)
        mock_campaign.status = "draft"
        mock_campaign_repository.get_by_id.return_value = mock_campaign
        
        # Act - This will FAIL until timezone validation exists
        result = scheduling_service.schedule_campaign(
            campaign_id=1,
            scheduled_at=utc_now() + timedelta(hours=1),
            timezone="Invalid/Timezone"
        )
        
        # Assert
        assert result.is_failure
        assert "timezone" in result.error.lower()
        
    def test_recurring_campaign_end_date_validation(self, scheduling_service, mock_campaign_repository):
        """Test validation for recurring campaigns with end dates"""
        # Arrange
        mock_campaign = Mock(spec=Campaign)
        mock_campaign.status = "draft"
        mock_campaign_repository.get_by_id.return_value = mock_campaign
        
        past_end_date = (utc_now() - timedelta(days=1)).strftime("%Y-%m-%d")
        recurrence_config = {
            "type": "daily",
            "interval": 1,
            "end_date": past_end_date
        }
        
        # Act - This will FAIL until end date validation exists
        result = scheduling_service.create_recurring_campaign(
            campaign_id=1,
            start_at=utc_now() + timedelta(hours=1),
            recurrence_pattern=recurrence_config,
            timezone="UTC"
        )
        
        # Assert
        assert result.is_failure
        assert "end date" in result.error.lower()
        
    def test_get_campaign_schedule_info(self, scheduling_service, mock_campaign_repository):
        """Test getting comprehensive schedule information for a campaign"""
        # Arrange
        campaign_id = 1
        mock_campaign = Mock(spec=Campaign)
        mock_campaign.id = campaign_id
        mock_campaign.status = 'scheduled'  # Add status
        mock_campaign.scheduled_at = utc_now() + timedelta(hours=2)
        mock_campaign.timezone = "America/New_York"
        mock_campaign.is_recurring = True
        mock_campaign.next_run_at = utc_now() + timedelta(days=1)
        mock_campaign.recurrence_pattern = {"type": "daily", "interval": 1}
        mock_campaign.archived = False  # Add archived field
        
        mock_campaign_repository.get_by_id.return_value = mock_campaign
        
        # Act - This will FAIL until schedule info method exists
        result = scheduling_service.get_campaign_schedule_info(campaign_id)
        
        # Assert
        assert result.is_success
        schedule_info = result.data
        
        assert schedule_info['campaign_id'] == campaign_id
        assert schedule_info['is_scheduled'] is True
        assert schedule_info['is_recurring'] is True
        assert schedule_info['timezone'] == "America/New_York"
        assert 'next_run_at' in schedule_info
        assert 'recurrence_pattern' in schedule_info
        
    def test_cancel_scheduled_campaign(self, scheduling_service, mock_campaign_repository):
        """Test cancelling a scheduled campaign"""
        # Arrange
        campaign_id = 1
        mock_campaign = Mock(spec=Campaign)
        mock_campaign.id = campaign_id
        mock_campaign.status = "scheduled"
        mock_campaign_repository.get_by_id.return_value = mock_campaign
        
        # Act - This will FAIL until cancellation logic exists
        result = scheduling_service.cancel_scheduled_campaign(campaign_id)
        
        # Assert
        assert result.is_success
        
        # Verify campaign status changed back to draft
        assert mock_campaign.status == "draft"
        assert mock_campaign.scheduled_at is None
        assert mock_campaign.next_run_at is None
        mock_campaign_repository.commit.assert_called_once()