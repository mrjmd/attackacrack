"""
TDD Tests for Campaign Scheduling Celery Tasks - Phase 3C
Tests for background tasks that handle scheduled campaign execution

These tests MUST FAIL initially following TDD Red-Green-Refactor cycle.
Tests define the Celery tasks needed for automated campaign scheduling.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch, call
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from celery.exceptions import Retry
from utils.datetime_utils import utc_now

# Task imports that will FAIL until created
from tasks.campaign_scheduling_tasks import (
    check_scheduled_campaigns,
    execute_scheduled_campaign,
    calculate_recurring_schedules,
    cleanup_expired_campaigns,
    send_schedule_notifications
)
from services.common.result import Result


class TestCampaignSchedulingTasks:
    """TDD tests for campaign scheduling Celery tasks"""
    
    @pytest.fixture
    def mock_app_context(self):
        """Mock Flask app context for Celery tasks"""
        with patch('tasks.campaign_scheduling_tasks.create_app') as mock_create_app:
            mock_app = Mock()
            mock_context = Mock()
            # Set up context manager properly
            mock_context.__enter__ = Mock(return_value=mock_context)
            mock_context.__exit__ = Mock(return_value=None)
            mock_app.app_context.return_value = mock_context
            mock_create_app.return_value = mock_app
            
            # Mock service registry
            mock_services = Mock()
            mock_app.services = mock_services
            
            yield mock_app, mock_services, mock_context
    
    def test_check_scheduled_campaigns_task(self, mock_app_context):
        """Test task that checks for campaigns ready to execute"""
        mock_app, mock_services, mock_context = mock_app_context
        
        # Arrange
        mock_scheduling_service = Mock()
        mock_services.get.return_value = mock_scheduling_service
        
        # Mock ready campaigns
        ready_campaigns = [
            Mock(id=1, name="Campaign 1"),
            Mock(id=2, name="Campaign 2")
        ]
        mock_scheduling_service.get_campaigns_ready_to_run.return_value = ready_campaigns
        
        # Act - This will FAIL until task is implemented
        with patch('tasks.campaign_scheduling_tasks.execute_scheduled_campaign.delay') as mock_execute:
            result = check_scheduled_campaigns.apply()
            
        # Assert
        assert result.successful()
        task_result = result.result
        
        assert task_result['success'] is True
        assert task_result['campaigns_found'] == 2
        assert task_result['campaigns_queued'] == 2
        
        # Verify execute tasks were queued
        assert mock_execute.call_count == 2
        mock_execute.assert_has_calls([
            call(1),  # Campaign 1
            call(2)   # Campaign 2  
        ])
        
    def test_check_scheduled_campaigns_no_campaigns(self, mock_app_context):
        """Test check task when no campaigns are ready"""
        mock_app, mock_services, mock_context = mock_app_context
        
        # Arrange
        mock_scheduling_service = Mock()
        mock_services.get.return_value = mock_scheduling_service
        mock_scheduling_service.get_campaigns_ready_to_run.return_value = []
        
        # Act - This will FAIL until task is implemented
        result = check_scheduled_campaigns.apply()
        
        # Assert
        assert result.successful()
        task_result = result.result
        
        assert task_result['success'] is True
        assert task_result['campaigns_found'] == 0
        assert task_result['campaigns_queued'] == 0
        
    def test_execute_scheduled_campaign_task_success(self, mock_app_context):
        """Test executing a scheduled campaign successfully"""
        mock_app, mock_services, mock_context = mock_app_context
        
        # Arrange
        campaign_id = 1
        mock_scheduling_service = Mock()
        mock_campaign_service = Mock()
        
        mock_services.get.side_effect = lambda name: {
            'campaign_scheduling': mock_scheduling_service,
            'campaign': mock_campaign_service
        }[name]
        
        # Mock successful execution
        # Result imported at module level
        mock_scheduling_service.execute_scheduled_campaign.return_value = Result.success(
            {"campaign_id": campaign_id, "status": "running"}
        )
        mock_campaign_service.process_campaign_queue.return_value = {
            "messages_sent": 25,
            "messages_failed": 0
        }
        
        # Act - This will FAIL until task is implemented
        result = execute_scheduled_campaign.apply(args=[campaign_id])
        
        # Assert
        assert result.successful()
        task_result = result.result
        
        assert task_result['success'] is True
        assert task_result['campaign_id'] == campaign_id
        assert task_result['messages_sent'] == 25
        
        # Verify services were called
        mock_scheduling_service.execute_scheduled_campaign.assert_called_once_with(campaign_id)
        mock_campaign_service.process_campaign_queue.assert_called_once()
        
    def test_execute_scheduled_campaign_task_failure(self, mock_app_context):
        """Test handling campaign execution failure"""
        mock_app, mock_services, mock_context = mock_app_context
        
        # Arrange
        campaign_id = 1
        mock_scheduling_service = Mock()
        mock_services.get.return_value = mock_scheduling_service
        
        # Mock execution failure
        # Result imported at module level
        mock_scheduling_service.execute_scheduled_campaign.return_value = Result.failure(
            "Campaign not found"
        )
        
        # Act - This will FAIL until task is implemented
        result = execute_scheduled_campaign.apply(args=[campaign_id])
        
        # Assert
        assert result.successful()  # Task completes even if campaign fails
        task_result = result.result
        
        assert task_result['success'] is False
        assert task_result['campaign_id'] == campaign_id
        assert "not found" in task_result['error']
        
    def test_calculate_recurring_schedules_task(self, mock_app_context):
        """Test task that calculates next run times for recurring campaigns"""
        mock_app, mock_services, mock_context = mock_app_context
        
        # Arrange
        mock_scheduling_service = Mock()
        mock_campaign_repository = Mock()
        
        # Configure services.get to return different mocks
        def get_service(name):
            if name == 'campaign_scheduling':
                return mock_scheduling_service
            elif name == 'campaign_repository':
                return mock_campaign_repository
            return None
        
        mock_services.get.side_effect = get_service
        
        # Mock recurring campaigns
        recurring_campaigns = [
            Mock(id=1, name="Daily Campaign", recurrence_pattern={"type": "daily"}, scheduled_at=utc_now(), timezone="UTC"),
            Mock(id=2, name="Weekly Campaign", recurrence_pattern={"type": "weekly"}, scheduled_at=utc_now(), timezone="UTC")
        ]
        mock_campaign_repository.find_recurring_campaigns_needing_update.return_value = recurring_campaigns
        mock_campaign_repository.update_next_run_at.return_value = True
        mock_campaign_repository.commit.return_value = None
        
        # Mock next run calculations
        next_runs = [
            utc_now() + timedelta(days=1),  # Daily - tomorrow
            utc_now() + timedelta(days=7)   # Weekly - next week
        ]
        mock_scheduling_service.calculate_next_run.side_effect = next_runs
        
        # Act - This will FAIL until task is implemented
        result = calculate_recurring_schedules.apply()
        
        # Assert
        assert result.successful()
        task_result = result.result
        
        assert task_result['success'] is True
        assert task_result['campaigns_processed'] == 2
        assert task_result['campaigns_updated'] == 2
        
        # Verify next run calculations were made
        assert mock_scheduling_service.calculate_next_run.call_count == 2
        assert mock_campaign_repository.update_next_run_at.call_count == 2
        
    def test_cleanup_expired_campaigns_task(self, mock_app_context):
        """Test task that cleans up expired scheduled campaigns"""
        mock_app, mock_services, mock_context = mock_app_context
        
        # Arrange
        mock_campaign_repository = Mock()
        mock_services.get.return_value = mock_campaign_repository
        
        # Mock cleanup returning count
        mock_campaign_repository.cleanup_expired_recurring_campaigns.return_value = 2
        
        # Act - This will FAIL until task is implemented
        result = cleanup_expired_campaigns.apply()
        
        # Assert
        assert result.successful()
        task_result = result.result
        
        assert task_result['success'] is True
        assert task_result['campaigns_cleaned'] == 2
        
        # Verify cleanup was called
        mock_campaign_repository.cleanup_expired_recurring_campaigns.assert_called_once()
        mock_campaign_repository.commit.assert_called_once()
        
    def test_send_schedule_notifications_task(self, mock_app_context):
        """Test task that sends notifications about scheduled campaigns"""
        mock_app, mock_services, mock_context = mock_app_context
        
        # Arrange
        mock_scheduling_service = Mock()
        mock_activity_repository = Mock()
        
        def get_service(name):
            if name == 'campaign_scheduling':
                return mock_scheduling_service
            elif name == 'activity_repository':
                return mock_activity_repository
            return None
        
        mock_services.get.side_effect = get_service
        
        # Mock scheduled campaigns (not upcoming_campaigns)
        scheduled_campaigns = [
            Mock(id=1, name="Campaign 1", scheduled_at=utc_now() + timedelta(minutes=30)),
            Mock(id=2, name="Campaign 2", scheduled_at=utc_now() + timedelta(minutes=45))
        ]
        mock_scheduling_service.get_scheduled_campaigns.return_value = scheduled_campaigns
        
        # Mock activity repository methods
        mock_activity_repository.create.return_value = Mock()
        mock_activity_repository.commit.return_value = None
        
        # Act - This will FAIL until task is implemented  
        result = send_schedule_notifications.apply()
        
        # Assert
        assert result.successful()
        task_result = result.result
        
        assert task_result['success'] is True
        assert task_result['notifications_sent'] == 2
        
        # Verify activities were created
        assert mock_activity_repository.create.call_count == 2
        mock_activity_repository.commit.assert_called_once()
        
    def test_check_scheduled_campaigns_with_service_error(self, mock_app_context):
        """Test check task handling service errors"""
        mock_app, mock_services, mock_context = mock_app_context
        
        # Arrange
        mock_services.get.return_value = None  # Service not registered
        
        # Act - Task should handle error gracefully
        result = check_scheduled_campaigns.apply()
        
        # Assert
        assert result.successful()  # Task completes even with error
        task_result = result.result
        
        assert task_result['success'] is False
        assert 'Service not found' in task_result['error']
        assert task_result['campaigns_found'] == 0
        assert task_result['campaigns_queued'] == 0
            
    def test_execute_scheduled_campaign_with_retry(self, mock_app_context):
        """Test campaign execution with retry on transient failure"""
        mock_app, mock_services, mock_context = mock_app_context
        
        # Arrange
        campaign_id = 1
        mock_scheduling_service = Mock()
        mock_campaign_service = Mock()
        
        def get_service_mock(service_name):
            if service_name == 'campaign_scheduling':
                return mock_scheduling_service
            elif service_name == 'campaign':
                return mock_campaign_service
            return Mock()
        
        mock_services.get.side_effect = get_service_mock
        
        # Mock transient failure that should retry
        from services.common.result import Result
        mock_scheduling_service.execute_scheduled_campaign.return_value = Result.failure("Database connection error")
        
        # Act - Execute task, expecting it to retry and eventually fail
        result = execute_scheduled_campaign.apply(args=[campaign_id])
        
        # Assert the task failed but would have retried
        # Since we can't easily test the Celery retry mechanism in unit tests,
        # we verify the task handles retryable errors appropriately
        assert not result.successful()
        assert "Database connection error" in str(result.result)
        
    def test_scheduled_campaign_execution_with_timezone_handling(self, mock_app_context):
        """Test campaign execution respects timezone settings"""
        mock_app, mock_services, mock_context = mock_app_context
        
        # Arrange
        campaign_id = 1
        mock_scheduling_service = Mock()
        mock_campaign_service = Mock()
        
        def get_service_mock(service_name):
            if service_name == 'campaign_scheduling':
                return mock_scheduling_service
            elif service_name == 'campaign':
                return mock_campaign_service
            return Mock()
        
        mock_services.get.side_effect = get_service_mock
        
        # Mock successful campaign queue processing
        mock_campaign_service.process_campaign_queue.return_value = {
            'messages_sent': 5,
            'messages_failed': 0
        }
        
        # Mock campaign with timezone
        mock_campaign = Mock()
        mock_campaign.timezone = "America/New_York"
        mock_campaign.scheduled_at = datetime(2025, 8, 25, 14, 0, 0)  # 2 PM
        
        # Result imported at module level
        mock_scheduling_service.execute_scheduled_campaign.return_value = Result.success({
            "campaign_id": campaign_id,
            "timezone_used": "America/New_York",
            "local_time": "2025-08-25 14:00:00",
            "utc_time": "2025-08-25 18:00:00"
        })
        
        # Act - This will FAIL until timezone handling is implemented
        result = execute_scheduled_campaign.apply(args=[campaign_id])
        
        # Assert
        assert result.successful()
        task_result = result.result
        
        assert task_result['success'] is True
        assert 'timezone_used' in task_result
        assert 'local_time' in task_result
        assert 'utc_time' in task_result
        
    def test_bulk_schedule_campaigns_task(self, mock_app_context):
        """Test task for bulk scheduling multiple campaigns"""
        mock_app, mock_services, mock_context = mock_app_context
        
        # Arrange
        campaign_ids = [1, 2, 3]
        scheduled_time = utc_now() + timedelta(hours=2)
        timezone = "America/New_York"
        
        mock_scheduling_service = Mock()
        mock_services.get.return_value = mock_scheduling_service
        
        # Mock successful bulk scheduling
        # Result imported at module level
        mock_scheduling_service.bulk_schedule_campaigns.return_value = Result.success({
            "campaigns_scheduled": 3,
            "failed_campaigns": []
        })
        
        # Act - This will FAIL until bulk task is implemented
        from tasks.campaign_scheduling_tasks import bulk_schedule_campaigns
        result = bulk_schedule_campaigns.apply(args=[campaign_ids, scheduled_time.isoformat(), timezone])
        
        # Assert
        assert result.successful()
        task_result = result.result
        
        assert task_result['success'] is True
        assert task_result['campaigns_scheduled'] == 3
        assert task_result['failed_campaigns'] == []
        
        # Verify service method was called
        mock_scheduling_service.bulk_schedule_campaigns.assert_called_once_with(
            campaign_ids, scheduled_time, timezone
        )
        
    def test_periodic_schedule_maintenance_task(self, mock_app_context):
        """Test periodic maintenance task for campaign schedules"""
        mock_app, mock_services, mock_context = mock_app_context
        
        # Arrange
        mock_scheduling_service = Mock()
        mock_services.get.return_value = mock_scheduling_service
        
        # Mock maintenance operations
        mock_scheduling_service.cleanup_failed_schedules.return_value = 2  # 2 cleaned
        mock_scheduling_service.update_overdue_schedules.return_value = 1   # 1 updated
        mock_scheduling_service.validate_recurring_patterns.return_value = 0 # 0 fixed
        
        # Act - This will FAIL until maintenance task is implemented
        from tasks.campaign_scheduling_tasks import periodic_schedule_maintenance
        result = periodic_schedule_maintenance.apply()
        
        # Assert
        assert result.successful()
        task_result = result.result
        
        assert task_result['success'] is True
        assert task_result['failed_schedules_cleaned'] == 2
        assert task_result['overdue_schedules_updated'] == 1
        assert task_result['recurring_patterns_fixed'] == 0
        
        # Verify all maintenance operations were called
        mock_scheduling_service.cleanup_failed_schedules.assert_called_once()
        mock_scheduling_service.update_overdue_schedules.assert_called_once()  
        mock_scheduling_service.validate_recurring_patterns.assert_called_once()
        
    def test_schedule_campaign_with_validation_task(self, mock_app_context):
        """Test task that schedules campaign with validation"""
        mock_app, mock_services, mock_context = mock_app_context
        
        # Arrange
        campaign_data = {
            "campaign_id": 1,
            "scheduled_at": (utc_now() + timedelta(hours=1)).isoformat(),
            "timezone": "America/New_York",
            "validate_business_hours": True
        }
        
        mock_scheduling_service = Mock()
        mock_services.get.return_value = mock_scheduling_service
        
        # Mock validation success
        # Result imported at module level
        mock_scheduling_service.schedule_campaign_with_validation.return_value = Result.success({
            "campaign_id": 1,
            "scheduled": True,
            "warnings": ["Outside business hours"]
        })
        
        # Act - This will FAIL until validation task is implemented
        from tasks.campaign_scheduling_tasks import schedule_campaign_with_validation
        result = schedule_campaign_with_validation.apply(args=[campaign_data])
        
        # Assert
        assert result.successful()
        task_result = result.result
        
        assert task_result['success'] is True
        assert task_result['campaign_id'] == 1
        assert task_result['scheduled'] is True
        assert len(task_result['warnings']) == 1
        
    def test_task_error_handling_and_logging(self, mock_app_context):
        """Test proper error handling and logging in tasks"""
        mock_app, mock_services, mock_context = mock_app_context
        
        # Arrange
        mock_services.get.side_effect = Exception("Service registry failure")
        
        # Act & Assert - This will FAIL until error handling is implemented
        with patch('tasks.campaign_scheduling_tasks.logger') as mock_logger:
            result = check_scheduled_campaigns.apply()
            
            # Task should handle error gracefully
            assert not result.successful() or result.result['success'] is False
            
            # Verify error was logged
            mock_logger.error.assert_called()
            error_call = mock_logger.error.call_args[0][0]
            assert "error" in error_call.lower() or "failed" in error_call.lower()