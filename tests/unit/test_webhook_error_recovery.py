"""
Tests for Webhook Error Recovery System (P1-14 to P1-17)

Test suite for:
- Failed webhook queue table
- Exponential backoff retry logic
- Webhook replay mechanism
- Error recovery service

Following TDD: These tests should FAIL initially and guide implementation.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime, timedelta
from utils.datetime_utils import utc_now
from decimal import Decimal

from crm_database import FailedWebhookQueue  # This model needs to be created
from repositories.failed_webhook_queue_repository import FailedWebhookQueueRepository  # To be created
from services.webhook_error_recovery_service import WebhookErrorRecoveryService  # To be created


class TestFailedWebhookQueueModel:
    """Test the FailedWebhookQueue database model"""
    
    def test_failed_webhook_queue_model_creation(self):
        """Test creating FailedWebhookQueue model instance"""
        # Arrange
        webhook_data = {
            'event_id': 'evt_123',
            'event_type': 'message.received',
            'original_payload': {'data': 'test'},
            'error_message': 'Connection timeout',
            'retry_count': 0,
            'next_retry_at': utc_now() + timedelta(minutes=1),
            'max_retries': 5,
            'backoff_multiplier': Decimal('2.0'),
            'created_at': utc_now()
        }
        
        # Act
        failed_webhook = FailedWebhookQueue(**webhook_data)
        
        # Assert
        assert failed_webhook.event_id == 'evt_123'
        assert failed_webhook.event_type == 'message.received'
        assert failed_webhook.retry_count == 0
        assert failed_webhook.max_retries == 5
        assert failed_webhook.backoff_multiplier == Decimal('2.0')
        assert failed_webhook.original_payload == {'data': 'test'}
        assert not failed_webhook.resolved
        assert failed_webhook.resolved_at is None
    
    def test_failed_webhook_queue_exponential_backoff_calculation(self):
        """Test exponential backoff calculation for next retry time"""
        # This test defines the expected behavior for exponential backoff
        base_delay = 60  # 1 minute
        multiplier = Decimal('2.0')
        
        # Test cases for retry_count and expected delay
        test_cases = [
            (0, 60),      # First retry: 1 minute
            (1, 120),     # Second retry: 2 minutes
            (2, 240),     # Third retry: 4 minutes
            (3, 480),     # Fourth retry: 8 minutes
            (4, 960),     # Fifth retry: 16 minutes
        ]
        
        for retry_count, expected_seconds in test_cases:
            # Calculate expected delay using exponential backoff formula
            expected_delay = base_delay * (multiplier ** retry_count)
            assert int(expected_delay) == expected_seconds


class TestFailedWebhookQueueRepository:
    """Test the FailedWebhookQueueRepository"""
    
    @pytest.fixture
    def mock_session(self):
        """Mock database session"""
        return MagicMock()
    
    @pytest.fixture
    def repository(self, mock_session):
        """Create repository with mocked session"""
        return FailedWebhookQueueRepository(mock_session)
    
    def test_find_pending_retries(self, repository, mock_session):
        """Test finding failed webhooks ready for retry"""
        # Arrange
        now = utc_now()
        mock_failed_webhooks = [
            Mock(id=1, event_id='evt_1', next_retry_at=now - timedelta(minutes=1)),
            Mock(id=2, event_id='evt_2', next_retry_at=now - timedelta(minutes=5))
        ]
        
        # Create properly chained mock
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = mock_failed_webhooks
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.find_pending_retries(limit=10)
        
        # Assert
        assert result == mock_failed_webhooks
        assert len(result) == 2
        assert result[0].event_id == 'evt_1'
        mock_session.query.assert_called_once_with(FailedWebhookQueue)
    
    def test_increment_retry_count(self, repository, mock_session):
        """Test incrementing retry count and updating next retry time"""
        # Arrange
        mock_webhook = Mock()
        mock_webhook.id = 1
        mock_webhook.retry_count = 1
        mock_webhook.max_retries = 5  # Add this missing attribute
        mock_webhook.backoff_multiplier = Decimal('2.0')
        mock_webhook.created_at = utc_now()
        mock_session.get.return_value = mock_webhook
        
        # Act
        result = repository.increment_retry_count(1, base_delay_seconds=60)
        
        # Assert
        assert result == mock_webhook
        assert mock_webhook.retry_count == 2
        assert mock_webhook.last_retry_at is not None
        mock_session.commit.assert_called_once()
    
    def test_mark_as_resolved(self, repository, mock_session):
        """Test marking failed webhook as resolved"""
        # Arrange
        mock_webhook = Mock(id=1, resolved=False, resolved_at=None)
        mock_session.get.return_value = mock_webhook
        
        # Act
        result = repository.mark_as_resolved(1, "Successfully processed on retry")
        
        # Assert
        assert result == mock_webhook
        assert mock_webhook.resolved is True
        assert mock_webhook.resolved_at is not None
        assert mock_webhook.resolution_note == "Successfully processed on retry"
        mock_session.commit.assert_called_once()
    
    def test_find_exhausted_retries(self, repository, mock_session):
        """Test finding webhooks that have exhausted all retry attempts"""
        # Arrange
        mock_webhooks = [Mock(id=1, retry_count=5, max_retries=5)]
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = mock_webhooks
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.find_exhausted_retries()
        
        # Assert
        assert result == mock_webhooks
        assert len(result) == 1
        assert result[0].id == 1


class TestWebhookErrorRecoveryService:
    """Test the WebhookErrorRecoveryService"""
    
    @pytest.fixture
    def mock_failed_webhook_repository(self):
        """Mock FailedWebhookQueueRepository"""
        return Mock()
    
    @pytest.fixture
    def mock_webhook_service(self):
        """Mock webhook processing service"""
        return Mock()
    
    @pytest.fixture
    def mock_webhook_event_repository(self):
        """Mock WebhookEventRepository"""
        return Mock()
    
    @pytest.fixture
    def service(self, mock_failed_webhook_repository, mock_webhook_service, mock_webhook_event_repository):
        """Create WebhookErrorRecoveryService with mocked dependencies"""
        return WebhookErrorRecoveryService(
            failed_webhook_repository=mock_failed_webhook_repository,
            webhook_service=mock_webhook_service,
            webhook_event_repository=mock_webhook_event_repository
        )
    
    def test_queue_failed_webhook(self, service, mock_failed_webhook_repository):
        """Test queuing a failed webhook for retry"""
        # Arrange
        webhook_data = {
            'event_id': 'evt_123',
            'event_type': 'message.received',
            'payload': {'data': 'test'}
        }
        error_message = "Connection timeout"
        
        mock_failed_webhook = Mock(id=1)
        mock_failed_webhook_repository.find_by_event_id.return_value = None  # No existing webhook
        mock_failed_webhook_repository.create.return_value = mock_failed_webhook
        
        # Act
        result = service.queue_failed_webhook(webhook_data, error_message)
        
        # Assert
        assert result.is_success
        assert result.data == mock_failed_webhook
        mock_failed_webhook_repository.create.assert_called_once()
        
        # Verify the creation call had correct structure
        create_call_args = mock_failed_webhook_repository.create.call_args.kwargs
        assert create_call_args['event_id'] == 'evt_123'
        assert create_call_args['event_type'] == 'message.received'
        assert create_call_args['original_payload'] == webhook_data  # Full webhook data stored
        assert create_call_args['error_message'] == "Connection timeout"
        assert create_call_args['retry_count'] == 0
        assert create_call_args['max_retries'] == 5  # Default
    
    def test_queue_failed_webhook_with_custom_config(self, service, mock_failed_webhook_repository):
        """Test queuing failed webhook with custom retry configuration"""
        # Arrange
        webhook_data = {
            'event_id': 'evt_456',
            'event_type': 'call.completed',
            'payload': {'data': 'test'}
        }
        error_message = "Rate limit exceeded"
        retry_config = {
            'max_retries': 3,
            'backoff_multiplier': Decimal('1.5'),
            'base_delay_seconds': 120
        }
        
        # Act
        result = service.queue_failed_webhook(webhook_data, error_message, retry_config)
        
        # Assert
        create_call_args = mock_failed_webhook_repository.create.call_args.kwargs
        assert create_call_args['max_retries'] == 3
        assert create_call_args['backoff_multiplier'] == Decimal('1.5')
    
    def test_process_retry_success(self, service, mock_failed_webhook_repository, mock_webhook_service):
        """Test successful retry processing"""
        # Arrange
        mock_failed_webhook = Mock(
            id=1,
            event_id='evt_123',
            original_payload={'data': 'test'},
            retry_count=1
        )
        # Mock the model methods
        mock_failed_webhook.is_retry_exhausted.return_value = False
        mock_failed_webhook.can_retry_now.return_value = True
        
        # Mock successful webhook processing
        from services.common.result import Result
        mock_webhook_service.process_webhook.return_value = Result.success({'processed': True})
        
        # Act
        result = service.process_retry(mock_failed_webhook)
        
        # Assert
        assert result.is_success
        mock_webhook_service.process_webhook.assert_called_once_with({'data': 'test'})
        mock_failed_webhook_repository.mark_as_resolved.assert_called_once_with(
            1, "Successfully processed on retry attempt 2"
        )
    
    def test_process_retry_failure_increment_count(self, service, mock_failed_webhook_repository, mock_webhook_service):
        """Test retry processing failure - should increment retry count"""
        # Arrange
        mock_failed_webhook = Mock(
            id=1,
            event_id='evt_123',
            original_payload={'data': 'test'},
            retry_count=2,
            max_retries=5,
            base_delay_seconds=60
        )
        # Mock the model methods
        mock_failed_webhook.is_retry_exhausted.return_value = False
        mock_failed_webhook.can_retry_now.return_value = True
        
        # Mock failed webhook processing
        from services.common.result import Result
        mock_webhook_service.process_webhook.return_value = Result.failure("Still failing")
        
        # Act
        result = service.process_retry(mock_failed_webhook)
        
        # Assert
        assert result.is_failure
        mock_failed_webhook_repository.increment_retry_count.assert_called_once_with(
            1, base_delay_seconds=60
        )
    
    def test_process_retry_exhausted_retries(self, service, mock_failed_webhook_repository, mock_webhook_service):
        """Test retry processing when retries are exhausted"""
        # Arrange
        mock_failed_webhook = Mock(
            id=1,
            event_id='evt_123',
            original_payload={'data': 'test'},
            retry_count=5,
            max_retries=5
        )
        # Mock the model methods - this webhook has exhausted retries
        mock_failed_webhook.is_retry_exhausted.return_value = True
        mock_failed_webhook.can_retry_now.return_value = False
        
        # Mock failed webhook processing (won't be called in this case)
        from services.common.result import Result
        mock_webhook_service.process_webhook.return_value = Result.failure("Still failing")
        
        # Act
        result = service.process_retry(mock_failed_webhook)
        
        # Assert
        assert result.is_failure
        assert "exhausted" in result.error.lower()
        # Should not increment retry count when exhausted
        mock_failed_webhook_repository.increment_retry_count.assert_not_called()
        # Should not even try to process webhook
        mock_webhook_service.process_webhook.assert_not_called()
    
    def test_get_pending_retries(self, service, mock_failed_webhook_repository):
        """Test getting pending retries"""
        # Arrange
        mock_pending = [Mock(id=1), Mock(id=2)]
        mock_failed_webhook_repository.find_pending_retries.return_value = mock_pending
        
        # Act
        result = service.get_pending_retries(limit=10)
        
        # Assert
        assert result.is_success
        assert len(result.data) == 2
        mock_failed_webhook_repository.find_pending_retries.assert_called_once_with(limit=10)
    
    def test_manual_replay_webhook(self, service, mock_failed_webhook_repository, mock_webhook_service):
        """Test manual webhook replay functionality"""
        # Arrange
        failed_webhook_id = 1
        mock_failed_webhook = Mock(
            id=1,
            event_id='evt_123',
            original_payload={'data': 'test'},
            resolved=False
        )
        mock_failed_webhook_repository.get_by_id.return_value = mock_failed_webhook
        
        # Mock successful processing
        from services.common.result import Result
        mock_webhook_service.process_webhook.return_value = Result.success({'processed': True})
        
        # Act
        result = service.manual_replay_webhook(failed_webhook_id)
        
        # Assert
        assert result.is_success
        mock_failed_webhook_repository.get_by_id.assert_called_once_with(1)
        mock_webhook_service.process_webhook.assert_called_once_with({'data': 'test'})
        mock_failed_webhook_repository.mark_as_resolved.assert_called_once()
    
    def test_get_failure_statistics(self, service, mock_failed_webhook_repository):
        """Test getting failure statistics"""
        # Arrange
        mock_stats = {
            'total_failed': 10,
            'pending_retries': 5,
            'exhausted_retries': 2,
            'resolved': 3
        }
        mock_failed_webhook_repository.get_failure_statistics.return_value = mock_stats
        
        # Act
        result = service.get_failure_statistics()
        
        # Assert
        assert result.is_success
        assert result.data == mock_stats
        mock_failed_webhook_repository.get_failure_statistics.assert_called_once()