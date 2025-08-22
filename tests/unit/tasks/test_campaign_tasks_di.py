"""Tests for campaign_tasks dependency injection.

These tests verify that campaign tasks properly use the service registry
rather than directly instantiating services.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
from tasks.campaign_tasks import process_campaign_queue, handle_incoming_message_opt_out


class TestCampaignTasksDependencyInjection:
    """Test that campaign tasks use proper dependency injection via service registry."""
    
    @pytest.fixture
    def mock_app(self):
        """Create a mock Flask app with service registry."""
        app = Mock()
        app.services = Mock()
        return app
    
    @pytest.fixture
    def mock_campaign_service(self):
        """Create a mock campaign service."""
        service = Mock()
        service.process_campaign_queue = Mock(return_value={
            'sent': 10,
            'failed': 2,
            'opted_out': 1
        })
        service.handle_opt_out = Mock(return_value=True)
        return service
    
    @patch('tasks.campaign_tasks.create_app')
    def test_process_campaign_queue_uses_service_registry(self, mock_create_app, mock_app, mock_campaign_service):
        """Test that process_campaign_queue gets service from registry."""
        # Arrange
        mock_create_app.return_value = mock_app
        mock_app.app_context.return_value.__enter__ = Mock(return_value=None)
        mock_app.app_context.return_value.__exit__ = Mock(return_value=None)
        mock_app.services.get.return_value = mock_campaign_service
        
        # Create a mock celery task
        mock_task = Mock()
        mock_task.request.retries = 0
        
        # Act
        result = process_campaign_queue.apply(task_id='test-task').get()
        
        # Assert
        mock_create_app.assert_called_once()
        mock_app.services.get.assert_called_once_with('campaign')
        mock_campaign_service.process_campaign_queue.assert_called_once()
        assert result['success'] is True
        assert result['stats']['sent'] == 10
    
    @patch('tasks.campaign_tasks.create_app')
    def test_process_campaign_queue_handles_missing_service(self, mock_create_app, mock_app):
        """Test that process_campaign_queue handles missing service gracefully."""
        # Arrange
        mock_create_app.return_value = mock_app
        mock_app.app_context.return_value.__enter__ = Mock(return_value=None)
        mock_app.app_context.return_value.__exit__ = Mock(return_value=None)
        mock_app.services.get.return_value = None  # Service not found
        
        # Act & Assert
        with pytest.raises(ValueError, match="Campaign service not registered"):
            process_campaign_queue.apply(task_id='test-task').get()
    
    @patch('tasks.campaign_tasks.create_app')
    def test_handle_incoming_message_opt_out_uses_service_registry(self, mock_create_app, mock_app, mock_campaign_service):
        """Test that handle_incoming_message_opt_out gets service from registry."""
        # Arrange
        mock_create_app.return_value = mock_app
        mock_app.app_context.return_value.__enter__ = Mock(return_value=None)
        mock_app.app_context.return_value.__exit__ = Mock(return_value=None)
        mock_app.services.get.return_value = mock_campaign_service
        
        phone = '+16175551234'
        message = 'STOP'
        
        # Act
        result = handle_incoming_message_opt_out.apply(args=[phone, message]).get()
        
        # Assert
        mock_create_app.assert_called_once()
        mock_app.services.get.assert_called_once_with('campaign')
        mock_campaign_service.handle_opt_out.assert_called_once_with(phone, message)
        assert result['success'] is True
        assert result['is_opt_out'] is True
        assert result['phone'] == phone
    
    @patch('tasks.campaign_tasks.create_app')
    def test_handle_incoming_message_opt_out_handles_missing_service(self, mock_create_app, mock_app):
        """Test that handle_incoming_message_opt_out handles missing service gracefully."""
        # Arrange
        mock_create_app.return_value = mock_app
        mock_app.app_context.return_value.__enter__ = Mock(return_value=None)
        mock_app.app_context.return_value.__exit__ = Mock(return_value=None)
        mock_app.services.get.return_value = None  # Service not found
        
        phone = '+16175551234'
        message = 'STOP'
        
        # Act
        result = handle_incoming_message_opt_out.apply(args=[phone, message]).get()
        
        # Assert
        assert result['success'] is False
        assert 'Campaign service not registered' in result['error']
        assert result['phone'] == phone
    
    @patch('tasks.campaign_tasks.create_app')
    def test_process_campaign_queue_handles_service_error(self, mock_create_app, mock_app, mock_campaign_service):
        """Test that process_campaign_queue handles service errors with retry."""
        # Arrange
        mock_create_app.return_value = mock_app
        mock_app.app_context.return_value.__enter__ = Mock(return_value=None)
        mock_app.app_context.return_value.__exit__ = Mock(return_value=None)
        mock_app.services.get.return_value = mock_campaign_service
        
        # Make the service raise an exception
        mock_campaign_service.process_campaign_queue.side_effect = Exception("Service error")
        
        # Act
        # The task will fail and attempt to retry 3 times, then raise MaxRetriesExceededError
        from celery.exceptions import MaxRetriesExceededError
        with pytest.raises(MaxRetriesExceededError):
            process_campaign_queue.apply(task_id='test-task').get()
        
        # Assert
        # The task should be called 4 times total (1 initial + 3 retries)
        assert mock_create_app.call_count == 4
        assert mock_app.services.get.call_count == 4
        assert mock_campaign_service.process_campaign_queue.call_count == 4
    
    @patch('tasks.campaign_tasks.create_app')
    def test_tasks_work_without_flask_context(self, mock_create_app, mock_app, mock_campaign_service):
        """Test that tasks create their own Flask app context when needed."""
        # Arrange
        mock_create_app.return_value = mock_app
        mock_app.app_context.return_value.__enter__ = Mock(return_value=None)
        mock_app.app_context.return_value.__exit__ = Mock(return_value=None)
        mock_app.services.get.return_value = mock_campaign_service
        
        # Act - Call task without existing Flask context
        result = process_campaign_queue.apply(task_id='test-task').get()
        
        # Assert - Task should create app and context
        mock_create_app.assert_called_once()
        mock_app.app_context.assert_called_once()
        assert result['success'] is True
