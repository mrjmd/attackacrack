"""
Tests for webhook health check Celery tasks
"""

import pytest
from unittest.mock import Mock, MagicMock, patch, ANY
from datetime import datetime
from services.webhook_health_check_service import HealthCheckStatus, HealthCheckResult


class TestWebhookHealthTasks:
    """Test suite for webhook health check Celery tasks"""
    
    @patch('celery_worker.flask_app')
    def test_run_webhook_health_check_task_registered(self, mock_flask_app):
        """Test that run_webhook_health_check task is registered"""
        from celery_worker import celery
        
        # Assert task is registered
        assert 'tasks.webhook_health_tasks.run_webhook_health_check' in celery.tasks
    
    @patch('celery_worker.flask_app')
    def test_get_webhook_health_status_task_registered(self, mock_flask_app):
        """Test that get_webhook_health_status task is registered"""
        from celery_worker import celery
        
        # Assert task is registered
        assert 'tasks.webhook_health_tasks.get_webhook_health_status' in celery.tasks
    
    @patch('celery_worker.flask_app')
    def test_cleanup_old_health_checks_task_registered(self, mock_flask_app):
        """Test that cleanup_old_health_checks task is registered"""
        from celery_worker import celery
        
        # Assert task is registered
        assert 'tasks.webhook_health_tasks.cleanup_old_health_checks' in celery.tasks
    
    def test_health_check_result_dataclass(self):
        """Test HealthCheckResult dataclass initialization"""
        result = HealthCheckResult(
            status=HealthCheckStatus.SUCCESS,
            message_id='msg_123',
            response_time=1.5,
            sent_at=datetime.utcnow()
        )
        
        assert result.status == HealthCheckStatus.SUCCESS
        assert result.message_id == 'msg_123'
        assert result.response_time == 1.5
        assert result.sent_at is not None
        assert result.error_message is None
    
    def test_health_check_status_enum(self):
        """Test HealthCheckStatus enum values"""
        assert HealthCheckStatus.SENT.value == 'sent'
        assert HealthCheckStatus.SUCCESS.value == 'success'
        assert HealthCheckStatus.FAILED.value == 'failed'
        assert HealthCheckStatus.TIMEOUT.value == 'timeout'