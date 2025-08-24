"""
Unit tests for OpenPhoneReconciliationService

Tests the reconciliation service that fetches OpenPhone messages and 
syncs them with the local database.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch, call
from datetime import datetime, timedelta
from utils.datetime_utils import utc_now
from typing import Dict, Any, List

from services.openphone_reconciliation_service import OpenPhoneReconciliationService
from services.common.result import Result


class TestOpenPhoneReconciliationService:
    """Test suite for OpenPhoneReconciliationService"""
    
    @pytest.fixture
    def mock_activity_repository(self):
        """Create mock activity repository"""
        mock = Mock()
        mock.find_by_openphone_id = Mock(return_value=None)
        mock.create = Mock(return_value=Mock(id=1))
        mock.bulk_create = Mock(return_value=[])
        return mock
    
    @pytest.fixture
    def mock_conversation_repository(self):
        """Create mock conversation repository"""
        mock = Mock()
        mock.find_by_openphone_id = Mock(return_value=None)
        mock.find_or_create_for_contact = Mock(return_value=Mock(id=1))
        return mock
    
    @pytest.fixture
    def mock_contact_service(self):
        """Create mock contact service"""
        mock = Mock()
        mock.find_or_create_by_phone = Mock(
            return_value=Result.success({'id': 1, 'phone': '+16175551234'})
        )
        return mock
    
    @pytest.fixture
    def mock_openphone_api_client(self):
        """Create mock OpenPhone API client"""
        mock = Mock()
        mock.get_messages = Mock(return_value={
            'data': [],
            'cursor': None
        })
        return mock
    
    @pytest.fixture
    def service(self, mock_activity_repository, mock_conversation_repository, 
                mock_contact_service, mock_openphone_api_client):
        """Create service instance with mocked dependencies"""
        return OpenPhoneReconciliationService(
            activity_repository=mock_activity_repository,
            conversation_repository=mock_conversation_repository,
            contact_service=mock_contact_service,
            openphone_api_client=mock_openphone_api_client
        )
    
    def test_service_initialization(self, service):
        """Test service initializes with correct dependencies"""
        assert service.activity_repository is not None
        assert service.conversation_repository is not None
        assert service.contact_service is not None
        assert service.openphone_api_client is not None
        assert service.batch_size == 100  # Default batch size
        assert service.max_pages == 50  # Default max pages
    
    def test_reconcile_messages_success(self, service, mock_openphone_api_client):
        """Test successful message reconciliation"""
        # Arrange
        mock_messages = [
            {
                'id': 'msg_123',
                'conversationId': 'conv_123',
                'from': '+16175551234',
                'to': ['+16175555678'],
                'body': 'Test message',
                'direction': 'outgoing',
                'status': 'delivered',
                'createdAt': '2024-01-01T12:00:00Z',
                'type': 'message'
            }
        ]
        mock_openphone_api_client.get_messages.return_value = {
            'data': mock_messages,
            'cursor': None
        }
        
        # Act
        result = service.reconcile_messages(hours_back=24)
        
        # Assert
        assert result.is_success
        assert result.data['total_messages'] == 1
        assert result.data['new_messages'] == 1
        assert result.data['existing_messages'] == 0
        assert result.data['errors'] == []
        mock_openphone_api_client.get_messages.assert_called_once()
    
    def test_reconcile_messages_with_pagination(self, service, mock_openphone_api_client):
        """Test reconciliation handles pagination correctly"""
        # Arrange
        page1_messages = [{'id': f'msg_{i}', 'conversationId': 'conv_1', 
                          'from': '+16175551234', 'to': ['+16175555678'],
                          'body': f'Message {i}', 'direction': 'outgoing',
                          'status': 'delivered', 'createdAt': '2024-01-01T12:00:00Z',
                          'type': 'message'} for i in range(100)]
        
        page2_messages = [{'id': f'msg_{i+100}', 'conversationId': 'conv_1',
                          'from': '+16175551234', 'to': ['+16175555678'],
                          'body': f'Message {i+100}', 'direction': 'outgoing',
                          'status': 'delivered', 'createdAt': '2024-01-01T12:00:00Z',
                          'type': 'message'} for i in range(50)]
        
        mock_openphone_api_client.get_messages.side_effect = [
            {'data': page1_messages, 'cursor': 'cursor_1'},
            {'data': page2_messages, 'cursor': None}
        ]
        
        # Act
        result = service.reconcile_messages(hours_back=24)
        
        # Assert
        assert result.is_success
        assert result.data['total_messages'] == 150
        assert mock_openphone_api_client.get_messages.call_count == 2
    
    def test_reconcile_messages_skips_existing(self, service, mock_openphone_api_client,
                                              mock_activity_repository):
        """Test reconciliation skips existing messages"""
        # Arrange
        mock_messages = [
            {
                'id': 'msg_existing',
                'conversationId': 'conv_123',
                'from': '+16175551234',
                'to': ['+16175555678'],
                'body': 'Existing message',
                'direction': 'outgoing',
                'status': 'delivered',
                'createdAt': '2024-01-01T12:00:00Z',
                'type': 'message'
            }
        ]
        mock_openphone_api_client.get_messages.return_value = {
            'data': mock_messages,
            'cursor': None
        }
        
        # Mock existing activity
        mock_activity_repository.find_by_openphone_id.return_value = Mock(id=1)
        
        # Act
        result = service.reconcile_messages(hours_back=24)
        
        # Assert
        assert result.is_success
        assert result.data['total_messages'] == 1
        assert result.data['new_messages'] == 0
        assert result.data['existing_messages'] == 1
        mock_activity_repository.create.assert_not_called()
    
    def test_reconcile_messages_handles_api_error(self, service, mock_openphone_api_client):
        """Test reconciliation handles API errors gracefully"""
        # Arrange
        mock_openphone_api_client.get_messages.side_effect = Exception("API Error")
        
        # Act
        result = service.reconcile_messages(hours_back=24)
        
        # Assert
        # Service returns success with errors in the errors list
        assert result.is_success
        assert len(result.data['errors']) == 1
        assert result.data['errors'][0]['error'] == 'API Error'
        assert result.data['total_messages'] == 0
    
    def test_reconcile_messages_respects_max_pages(self, service, mock_openphone_api_client):
        """Test reconciliation respects max pages limit"""
        # Arrange
        service.max_pages = 2
        
        # Return cursor on every call to simulate infinite pagination
        mock_openphone_api_client.get_messages.return_value = {
            'data': [{'id': 'msg_1', 'conversationId': 'conv_1',
                     'from': '+16175551234', 'to': ['+16175555678'],
                     'body': 'Message', 'direction': 'outgoing',
                     'status': 'delivered', 'createdAt': '2024-01-01T12:00:00Z',
                     'type': 'message'}],
            'cursor': 'always_more'
        }
        
        # Act
        result = service.reconcile_messages(hours_back=24)
        
        # Assert
        assert result.is_success
        assert mock_openphone_api_client.get_messages.call_count == 2
        assert result.data['total_pages'] == 2
    
    def test_process_message_creates_activity(self, service, mock_activity_repository,
                                             mock_conversation_repository, mock_contact_service):
        """Test processing a message creates an activity record"""
        # Arrange
        message = {
            'id': 'msg_123',
            'conversationId': 'conv_123',
            'from': '+16175551234',
            'to': ['+16175555678'],
            'body': 'Test message',
            'direction': 'outgoing',
            'status': 'delivered',
            'createdAt': '2024-01-01T12:00:00Z',
            'type': 'message',
            'phoneNumberId': 'phone_123',
            'userId': 'user_123',
            'mediaUrls': []
        }
        
        mock_activity_repository.find_by_openphone_id.return_value = None
        mock_contact = Mock(id=1, phone='+16175551234')
        mock_contact_service.find_or_create_by_phone.return_value = Result.success(mock_contact)
        mock_conversation = Mock(id=1)
        mock_conversation_repository.find_or_create_for_contact.return_value = mock_conversation
        
        # Act
        result = service._process_message(message)
        
        # Assert
        assert result.is_success
        mock_activity_repository.create.assert_called_once()
        call_args = mock_activity_repository.create.call_args[0][0]
        assert call_args['openphone_id'] == 'msg_123'
        assert call_args['conversation_id'] == 1
        assert call_args['contact_id'] == 1
        assert call_args['activity_type'] == 'message'
        assert call_args['direction'] == 'outgoing'
        assert call_args['status'] == 'delivered'
        assert call_args['body'] == 'Test message'
    
    def test_process_message_handles_incoming(self, service, mock_activity_repository,
                                             mock_conversation_repository, mock_contact_service):
        """Test processing incoming messages correctly"""
        # Arrange
        message = {
            'id': 'msg_124',
            'conversationId': 'conv_124',
            'from': '+16175551234',  # External number
            'to': ['+16175555678'],  # Our number
            'body': 'Incoming message',
            'direction': 'incoming',
            'status': 'received',
            'createdAt': '2024-01-01T12:00:00Z',
            'type': 'message'
        }
        
        mock_activity_repository.find_by_openphone_id.return_value = None
        mock_contact = Mock(id=2, phone='+16175551234')
        mock_contact_service.find_or_create_by_phone.return_value = Result.success(mock_contact)
        mock_conversation = Mock(id=2)
        mock_conversation_repository.find_or_create_for_contact.return_value = mock_conversation
        
        # Act
        result = service._process_message(message)
        
        # Assert
        assert result.is_success
        mock_contact_service.find_or_create_by_phone.assert_called_with('+16175551234')
        call_args = mock_activity_repository.create.call_args[0][0]
        assert call_args['direction'] == 'incoming'
        assert call_args['from_number'] == '+16175551234'
    
    def test_process_message_handles_media_urls(self, service, mock_activity_repository,
                                               mock_conversation_repository, mock_contact_service):
        """Test processing messages with media attachments"""
        # Arrange
        message = {
            'id': 'msg_125',
            'conversationId': 'conv_125',
            'from': '+16175551234',
            'to': ['+16175555678'],
            'body': 'Message with media',
            'direction': 'outgoing',
            'status': 'delivered',
            'createdAt': '2024-01-01T12:00:00Z',
            'type': 'message',
            'mediaUrls': ['https://example.com/image1.jpg', 'https://example.com/image2.jpg']
        }
        
        mock_activity_repository.find_by_openphone_id.return_value = None
        mock_contact = Mock(id=3, phone='+16175551234')
        mock_contact_service.find_or_create_by_phone.return_value = Result.success(mock_contact)
        mock_conversation = Mock(id=3)
        mock_conversation_repository.find_or_create_for_contact.return_value = mock_conversation
        
        # Act
        result = service._process_message(message)
        
        # Assert
        assert result.is_success
        call_args = mock_activity_repository.create.call_args[0][0]
        assert call_args['media_urls'] == ['https://example.com/image1.jpg', 'https://example.com/image2.jpg']
    
    def test_batch_process_messages(self, service, mock_activity_repository,
                                   mock_conversation_repository, mock_contact_service):
        """Test batch processing of messages"""
        # Arrange
        messages = [
            {
                'id': f'msg_{i}',
                'conversationId': 'conv_1',
                'from': '+16175551234',
                'to': ['+16175555678'],
                'body': f'Message {i}',
                'direction': 'outgoing',
                'status': 'delivered',
                'createdAt': '2024-01-01T12:00:00Z',
                'type': 'message'
            } for i in range(10)
        ]
        
        mock_activity_repository.find_by_openphone_id.return_value = None
        mock_contact = Mock(id=1, phone='+16175551234')
        mock_contact_service.find_or_create_by_phone.return_value = Result.success(mock_contact)
        mock_conversation = Mock(id=1)
        mock_conversation_repository.find_or_create_for_contact.return_value = mock_conversation
        
        # Act
        results = service._batch_process_messages(messages)
        
        # Assert
        assert len(results['processed']) == 10
        assert len(results['errors']) == 0
        assert mock_activity_repository.create.call_count == 10
    
    def test_reconcile_with_date_range(self, service, mock_openphone_api_client):
        """Test reconciliation with specific date range"""
        # Arrange
        mock_openphone_api_client.get_messages.return_value = {
            'data': [],
            'cursor': None
        }
        
        # Act
        result = service.reconcile_messages(hours_back=48)
        
        # Assert
        assert result.is_success
        # Verify API was called with correct date range
        call_args = mock_openphone_api_client.get_messages.call_args
        assert 'since' in call_args[1]
        # Check that the date is approximately 48 hours ago
        since_str = call_args[1]['since']
        # Handle the double timezone issue - remove extra '+00:00' if present
        if since_str.endswith('+00:00Z'):
            since_str = since_str[:-1]  # Remove the 'Z' 
        elif since_str.endswith('Z'):
            since_str = since_str[:-1] + '+00:00'
        
        since_date = datetime.fromisoformat(since_str)
        from utils.datetime_utils import utc_now
        expected_date = utc_now() - timedelta(hours=48)
        assert abs((since_date - expected_date).total_seconds()) < 60  # Within 1 minute
    
    def test_reconcile_handles_rate_limiting(self, service, mock_openphone_api_client):
        """Test reconciliation handles rate limiting errors gracefully"""
        # Arrange
        from requests.exceptions import HTTPError
        
        # Simulate rate limit error
        rate_limit_response = Mock()
        rate_limit_response.status_code = 429
        rate_limit_error = HTTPError(response=rate_limit_response)
        
        mock_openphone_api_client.get_messages.side_effect = rate_limit_error
        
        # Act
        result = service.reconcile_messages(hours_back=24)
        
        # Assert - service handles error gracefully and returns success with errors
        assert result.is_success
        assert len(result.data['errors']) == 1
        assert mock_openphone_api_client.get_messages.call_count == 1
    
    def test_get_reconciliation_stats(self, service):
        """Test getting reconciliation statistics"""
        # Arrange
        service.stats = {
            'last_run': utc_now(),
            'total_processed': 1000,
            'total_errors': 5,
            'last_error': 'Sample error',
            'runs_today': 3
        }
        
        # Act
        stats = service.get_reconciliation_stats()
        
        # Assert
        assert stats['total_processed'] == 1000
        assert stats['total_errors'] == 5
        assert stats['last_error'] == 'Sample error'
        assert stats['runs_today'] == 3
        assert 'last_run' in stats
    
    def test_reconcile_updates_conversation_last_activity(self, service, mock_activity_repository,
                                                         mock_conversation_repository, mock_contact_service):
        """Test that reconciliation updates conversation last_activity_at"""
        # Arrange
        message = {
            'id': 'msg_126',
            'conversationId': 'conv_126',
            'from': '+16175551234',
            'to': ['+16175555678'],
            'body': 'Test message',
            'direction': 'outgoing',
            'status': 'delivered',
            'createdAt': '2024-01-01T12:00:00Z',
            'type': 'message'
        }
        
        mock_activity_repository.find_by_openphone_id.return_value = None
        mock_contact = Mock(id=1, phone='+16175551234')
        mock_contact_service.find_or_create_by_phone.return_value = Result.success(mock_contact)
        mock_conversation = Mock(id=1, last_activity_at=None)
        mock_conversation_repository.find_or_create_for_contact.return_value = mock_conversation
        
        # Act
        result = service._process_message(message)
        
        # Assert
        assert result.is_success
        mock_conversation_repository.update_last_activity.assert_called_once()
        # Check the keyword arguments
        call_kwargs = mock_conversation_repository.update_last_activity.call_args[1]
        assert call_kwargs['conversation_id'] == 1  # conversation_id
        assert isinstance(call_kwargs['activity_time'], datetime)  # activity_time