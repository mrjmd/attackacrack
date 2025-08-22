"""
Tests for WebhookHealthCheckService
Following TDD principles - tests written before implementation
"""

import pytest
from unittest.mock import Mock, MagicMock, patch, call
from datetime import datetime, timedelta
from services.webhook_health_check_service import (
    WebhookHealthCheckService,
    HealthCheckResult,
    HealthCheckStatus
)


class TestWebhookHealthCheckService:
    """Test suite for WebhookHealthCheckService"""
    
    @pytest.fixture
    def mock_webhook_repository(self):
        """Mock webhook event repository"""
        return MagicMock()
    
    @pytest.fixture
    def mock_openphone_service(self):
        """Mock OpenPhone service"""
        return MagicMock()
    
    @pytest.fixture
    def mock_email_service(self):
        """Mock email service"""
        return MagicMock()
    
    @pytest.fixture
    def test_phone_number(self):
        """Test phone number for health checks"""
        return "+15551234567"
    
    @pytest.fixture
    def service(self, mock_webhook_repository, mock_openphone_service, mock_email_service, test_phone_number):
        """Create WebhookHealthCheckService with mocked dependencies"""
        return WebhookHealthCheckService(
            webhook_repository=mock_webhook_repository,
            openphone_service=mock_openphone_service,
            email_service=mock_email_service,
            test_phone_number=test_phone_number,
            alert_email="alerts@example.com"
        )
    
    def test_init_service(self, service, test_phone_number):
        """Test service initialization"""
        assert service.test_phone_number == test_phone_number
        assert service.alert_email == "alerts@example.com"
        assert service.health_check_timeout == 120  # 2 minutes default
        assert service.health_check_prefix == "[HEALTH_CHECK]"
    
    def test_generate_health_check_message(self, service):
        """Test health check message generation"""
        with patch('services.webhook_health_check_service.datetime') as mock_datetime:
            mock_datetime.utcnow.return_value = datetime(2025, 1, 22, 10, 30, 45)
            
            message = service._generate_health_check_message()
            
            assert message.startswith("[HEALTH_CHECK]")
            assert "2025-01-22T10:30:45" in message
            assert len(message.split("-")[-1]) == 8  # Check for UUID suffix
    
    def test_send_health_check_success(self, service, mock_openphone_service):
        """Test successful health check message sending"""
        # Arrange
        mock_openphone_service.send_message.return_value = {
            'success': True,
            'data': {'id': 'msg_123', 'status': 'sent'}
        }
        
        # Act
        result = service.send_health_check()
        
        # Assert
        assert result.status == HealthCheckStatus.SENT
        assert result.message_id == 'msg_123'
        assert result.sent_at is not None
        assert result.error_message is None
        mock_openphone_service.send_message.assert_called_once()
        
        # Verify message format
        call_args = mock_openphone_service.send_message.call_args
        assert call_args[0][0] == service.test_phone_number
        assert call_args[0][1].startswith("[HEALTH_CHECK]")
    
    def test_send_health_check_failure(self, service, mock_openphone_service):
        """Test failed health check message sending"""
        # Arrange
        mock_openphone_service.send_message.return_value = {
            'success': False,
            'error': 'API key not configured'
        }
        
        # Act
        result = service.send_health_check()
        
        # Assert
        assert result.status == HealthCheckStatus.FAILED
        assert result.message_id is None
        assert result.error_message == 'Failed to send health check: API key not configured'
        mock_openphone_service.send_message.assert_called_once()
    
    def test_verify_webhook_receipt_success(self, service, mock_webhook_repository):
        """Test successful webhook receipt verification"""
        # Arrange
        check_message = "[HEALTH_CHECK] Test at 2025-01-22T10:30:45-abc12345"
        sent_at = datetime.utcnow()
        
        # Mock webhook event with matching message
        mock_event = Mock(
            event_type='message.received',
            payload={'text': check_message},
            created_at=sent_at + timedelta(seconds=30)
        )
        
        # Mock the helper method instead of the complex query chain
        with patch.object(service, '_find_matching_webhook', return_value=mock_event):
            # Act
            result = service.verify_webhook_receipt(check_message, sent_at)
        
        # Assert
        assert result.status == HealthCheckStatus.SUCCESS
        assert result.received_at == mock_event.created_at
        assert result.response_time == 30.0
        assert result.error_message is None
    
    def test_verify_webhook_receipt_timeout(self, service, mock_webhook_repository):
        """Test webhook receipt verification timeout"""
        # Arrange
        check_message = "[HEALTH_CHECK] Test at 2025-01-22T10:30:45-abc12345"
        sent_at = datetime.utcnow() - timedelta(seconds=150)  # 2.5 minutes ago
        
        # Mock the helper method to return None (no matching webhook)
        with patch.object(service, '_find_matching_webhook', return_value=None):
            # Act
            with patch('time.sleep'):  # Mock sleep to speed up test
                result = service.verify_webhook_receipt(check_message, sent_at, timeout=1)
        
        # Assert
        assert result.status == HealthCheckStatus.TIMEOUT
        assert result.received_at is None
        assert result.error_message == 'Webhook not received within timeout period'
    
    def test_run_health_check_complete_success(self, service, mock_openphone_service, mock_webhook_repository):
        """Test complete health check flow - success"""
        # Arrange
        mock_openphone_service.send_message.return_value = {
            'success': True,
            'data': {'id': 'msg_123', 'status': 'sent'}
        }
        
        mock_event = Mock(
            event_type='message.received',
            payload={'text': '[HEALTH_CHECK] Test'},
            created_at=datetime.utcnow()
        )
        
        # Mock the helper method
        with patch.object(service, '_find_matching_webhook', return_value=mock_event):
            # Act
            with patch('time.sleep'):
                result = service.run_health_check()
        
        # Assert
        assert result.status == HealthCheckStatus.SUCCESS
        assert result.message_id == 'msg_123'
        assert result.response_time is not None
    
    def test_run_health_check_with_alert_on_failure(self, service, mock_openphone_service, mock_email_service):
        """Test health check triggers email alert on failure"""
        # Arrange
        mock_openphone_service.send_message.return_value = {
            'success': False,
            'error': 'API error'
        }
        mock_email_service.is_configured.return_value = True
        mock_email_service.send_email.return_value = (True, "Email sent")
        
        # Act
        result = service.run_health_check()
        
        # Assert
        assert result.status == HealthCheckStatus.FAILED
        mock_email_service.send_email.assert_called_once()
        
        # Verify email content
        email_call = mock_email_service.send_email.call_args[0][0]
        assert email_call.subject == "ALERT: OpenPhone Webhook Health Check Failed"
        assert "alerts@example.com" in email_call.recipients
        assert "API error" in email_call.body_text
    
    def test_run_health_check_with_alert_on_timeout(self, service, mock_openphone_service, mock_webhook_repository, mock_email_service):
        """Test health check triggers email alert on timeout"""
        # Arrange
        mock_openphone_service.send_message.return_value = {
            'success': True,
            'data': {'id': 'msg_123', 'status': 'sent'}
        }
        
        mock_email_service.is_configured.return_value = True
        mock_email_service.send_email.return_value = (True, "Email sent")
        
        # Mock the helper method to return None (timeout)
        with patch.object(service, '_find_matching_webhook', return_value=None):
            # Act
            with patch('time.sleep'):
                with patch.object(service, 'health_check_timeout', 1):  # Quick timeout for test
                    result = service.run_health_check()
        
        # Assert
        assert result.status == HealthCheckStatus.TIMEOUT
        mock_email_service.send_email.assert_called_once()
        
        # Verify email content
        email_call = mock_email_service.send_email.call_args[0][0]
        assert "Webhook Not Received" in email_call.subject
        assert "timeout period" in email_call.body_text
    
    def test_send_alert_email_not_configured(self, service, mock_email_service):
        """Test alert email when email service not configured"""
        # Arrange
        mock_email_service.is_configured.return_value = False
        result = HealthCheckResult(
            status=HealthCheckStatus.FAILED,
            error_message="Test failure"
        )
        
        # Act
        service._send_alert_email(result)
        
        # Assert
        mock_email_service.send_email.assert_not_called()
    
    def test_format_alert_email_content(self, service):
        """Test email alert content formatting"""
        # Arrange
        result = HealthCheckResult(
            status=HealthCheckStatus.TIMEOUT,
            message_id="msg_123",
            sent_at=datetime(2025, 1, 22, 10, 30, 0),
            error_message="Webhook not received within timeout period"
        )
        
        # Act
        subject, body = service._format_alert_email(result)
        
        # Assert
        assert "Webhook Not Received" in subject
        assert "msg_123" in body
        assert "2025-01-22 10:30:00" in body
        assert "timeout period" in body
    
    def test_get_health_check_status(self, service, mock_webhook_repository):
        """Test retrieving recent health check status"""
        # Arrange
        mock_events = [
            Mock(
                event_type='health_check.success',
                created_at=datetime.utcnow() - timedelta(hours=1),
                payload={'response_time': 1.5}
            ),
            Mock(
                event_type='health_check.timeout',
                created_at=datetime.utcnow() - timedelta(hours=2),
                payload={'error': 'Timeout'}
            )
        ]
        
        # Mock the helper method
        with patch.object(service, '_get_health_check_events', return_value=mock_events):
            # Act
            status = service.get_health_check_status(hours=24)
        
        # Assert
        assert status['total_checks'] == 2
        assert status['successful_checks'] == 1
        assert status['failed_checks'] == 1
        assert status['success_rate'] == 50.0
        assert status['average_response_time'] == 1.5
    
    def test_store_health_check_result(self, service, mock_webhook_repository):
        """Test storing health check result in repository"""
        # Arrange
        result = HealthCheckResult(
            status=HealthCheckStatus.SUCCESS,
            message_id="msg_123",
            sent_at=datetime.utcnow(),
            received_at=datetime.utcnow() + timedelta(seconds=2),
            response_time=2.0
        )
        
        # Act
        service._store_health_check_result(result)
        
        # Assert
        mock_webhook_repository.create.assert_called_once()
        create_call = mock_webhook_repository.create.call_args[0][0]
        assert create_call['event_type'] == 'health_check.success'
        assert create_call['event_id'].startswith('health_check_')
        assert create_call['payload']['message_id'] == 'msg_123'
        assert create_call['payload']['response_time'] == 2.0