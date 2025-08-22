"""
Test Celery Beat schedule configuration
Following TDD principles - tests written FIRST
"""

import pytest
from unittest.mock import patch, MagicMock


class TestCeleryBeatConfiguration:
    """Test Celery Beat schedule is properly configured"""
    
    def test_beat_schedule_includes_daily_tasks(self):
        """Test that beat schedule includes the daily tasks"""
        # Import after mocking to ensure clean state
        with patch('app.create_app') as mock_create_app:
            mock_app = MagicMock()
            mock_create_app.return_value = mock_app
            
            # Import celery_worker to get the configuration
            import celery_worker
            
            # Verify daily tasks are scheduled
            assert 'run-daily-tasks' in celery_worker.celery.conf.beat_schedule
            
            daily_task_config = celery_worker.celery.conf.beat_schedule['run-daily-tasks']
            assert daily_task_config['task'] == 'services.scheduler_service.run_daily_tasks'
            # Should run every 24 hours (86400 seconds)
            assert daily_task_config['schedule'] == 3600.0 * 24
    
    def test_beat_schedule_includes_campaign_queue_processing(self):
        """Test that beat schedule includes campaign queue processing"""
        # Import after mocking to ensure clean state
        with patch('app.create_app') as mock_create_app:
            mock_app = MagicMock()
            mock_create_app.return_value = mock_app
            
            # Import celery_worker to get the configuration
            import celery_worker
            
            # Verify campaign queue processing is scheduled
            assert 'process-campaign-queue' in celery_worker.celery.conf.beat_schedule
            
            campaign_task_config = celery_worker.celery.conf.beat_schedule['process-campaign-queue']
            assert campaign_task_config['task'] == 'tasks.campaign_tasks.process_campaign_queue'
            # Should run every 60 seconds
            assert campaign_task_config['schedule'] == 60.0
    
    def test_beat_schedule_has_correct_timezone(self):
        """Test that beat schedule uses UTC timezone"""
        # Import after mocking to ensure clean state
        with patch('app.create_app') as mock_create_app:
            mock_app = MagicMock()
            mock_create_app.return_value = mock_app
            
            # Import celery_worker to get the configuration
            import celery_worker
            
            # Verify timezone is set to UTC
            assert celery_worker.celery.conf.timezone == 'UTC'
    
    def test_beat_schedule_contains_both_tasks(self):
        """Test that beat schedule contains exactly the expected tasks"""
        # Import after mocking to ensure clean state
        with patch('app.create_app') as mock_create_app:
            mock_app = MagicMock()
            mock_create_app.return_value = mock_app
            
            # Import celery_worker to get the configuration
            import celery_worker
            
            beat_schedule = celery_worker.celery.conf.beat_schedule
            
            # Should have exactly these two tasks
            expected_tasks = {'run-daily-tasks', 'process-campaign-queue'}
            actual_tasks = set(beat_schedule.keys())
            
            assert actual_tasks == expected_tasks
    
    def test_campaign_queue_task_interval_is_60_seconds(self):
        """Test that campaign queue processing runs every 60 seconds"""
        # Import after mocking to ensure clean state
        with patch('app.create_app') as mock_create_app:
            mock_app = MagicMock()
            mock_create_app.return_value = mock_app
            
            # Import celery_worker to get the configuration
            import celery_worker
            
            campaign_config = celery_worker.celery.conf.beat_schedule.get('process-campaign-queue')
            
            # Should not be None
            assert campaign_config is not None
            
            # Should run every 60 seconds (not 60.0 to be strict about type)
            assert campaign_config['schedule'] == 60.0
    
    def test_daily_tasks_interval_is_24_hours(self):
        """Test that daily tasks run every 24 hours"""
        # Import after mocking to ensure clean state
        with patch('app.create_app') as mock_create_app:
            mock_app = MagicMock()
            mock_create_app.return_value = mock_app
            
            # Import celery_worker to get the configuration
            import celery_worker
            
            daily_config = celery_worker.celery.conf.beat_schedule.get('run-daily-tasks')
            
            # Should not be None
            assert daily_config is not None
            
            # Should run every 24 hours (3600 * 24 = 86400 seconds)
            assert daily_config['schedule'] == 3600.0 * 24
    
    def test_task_paths_are_correct_strings(self):
        """Test that task paths are properly formatted strings"""
        # Import after mocking to ensure clean state
        with patch('app.create_app') as mock_create_app:
            mock_app = MagicMock()
            mock_create_app.return_value = mock_app
            
            # Import celery_worker to get the configuration
            import celery_worker
            
            beat_schedule = celery_worker.celery.conf.beat_schedule
            
            # Check daily task path
            daily_task_path = beat_schedule['run-daily-tasks']['task']
            assert isinstance(daily_task_path, str)
            assert daily_task_path == 'services.scheduler_service.run_daily_tasks'
            
            # Check campaign task path
            campaign_task_path = beat_schedule['process-campaign-queue']['task']
            assert isinstance(campaign_task_path, str)
            assert campaign_task_path == 'tasks.campaign_tasks.process_campaign_queue'