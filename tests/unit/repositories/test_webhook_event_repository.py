"""
Tests for WebhookEventRepository
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime
from repositories.webhook_event_repository import WebhookEventRepository
from repositories.base_repository import PaginatedResult
from crm_database import WebhookEvent


class TestWebhookEventRepository:
    """Test suite for WebhookEventRepository"""
    
    @pytest.fixture
    def mock_session(self):
        """Mock database session"""
        session = MagicMock()
        return session
    
    @pytest.fixture
    def repository(self, mock_session):
        """Create WebhookEventRepository with mocked session"""
        return WebhookEventRepository(mock_session, WebhookEvent)
    
    def test_find_by_event_id(self, repository, mock_session):
        """Test finding webhook event by event ID"""
        # Arrange
        mock_event = Mock(id=1, event_id="evt_123")
        mock_query = Mock()
        mock_query.filter_by.return_value.first.return_value = mock_event
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.find_by_event_id("evt_123")
        
        # Assert
        assert result == mock_event
        mock_query.filter_by.assert_called_once_with(event_id="evt_123")
    
    def test_find_by_event_type(self, repository, mock_session):
        """Test finding webhook events by type"""
        # Arrange
        mock_events = [Mock(id=1, event_type="message.received")]
        mock_query = Mock()
        mock_query.filter_by.return_value.all.return_value = mock_events
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.find_by_event_type("message.received")
        
        # Assert
        assert result == mock_events
        mock_query.filter_by.assert_called_once_with(event_type="message.received")
    
    def test_find_unprocessed_events(self, repository, mock_session):
        """Test finding unprocessed webhook events"""
        # Arrange
        mock_events = [Mock(id=1, processed=False)]
        mock_query = Mock()
        mock_query.filter_by.return_value.limit.return_value.all.return_value = mock_events
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.find_unprocessed_events(limit=50)
        
        # Assert
        assert result == mock_events
        mock_query.filter_by.assert_called_once_with(processed=False)
        mock_query.filter_by.return_value.limit.assert_called_once_with(50)
    
    def test_find_failed_events(self, repository, mock_session):
        """Test finding failed webhook events"""
        # Arrange
        mock_events = [Mock(id=1, error_message="Error processing")]
        mock_query = Mock()
        mock_query.filter.return_value.all.return_value = mock_events
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.find_failed_events()
        
        # Assert
        assert result == mock_events
        mock_query.filter.assert_called_once()
    
    def test_mark_as_processed(self, repository, mock_session):
        """Test marking webhook event as processed"""
        # Arrange
        mock_event = Mock(id=1, processed=False)
        mock_query = Mock()
        mock_query.get.return_value = mock_event
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.mark_as_processed(1)
        
        # Assert
        assert result == mock_event
        assert mock_event.processed is True
        assert mock_event.processed_at is not None
        mock_session.commit.assert_called_once()
    
    def test_mark_as_failed(self, repository, mock_session):
        """Test marking webhook event as failed"""
        # Arrange
        mock_event = Mock(id=1, error_message=None)
        mock_query = Mock()
        mock_query.get.return_value = mock_event
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.mark_as_failed(1, "Test error message")
        
        # Assert
        assert result == mock_event
        assert mock_event.error_message == "Test error message"
        mock_session.commit.assert_called_once()
    
    def test_count_by_event_type(self, repository, mock_session):
        """Test counting events by type"""
        # Arrange
        mock_query = Mock()
        mock_query.filter_by.return_value.count.return_value = 25
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.count_by_event_type("call.completed")
        
        # Assert
        assert result == 25
        mock_query.filter_by.assert_called_once_with(event_type="call.completed")
    
    def test_search(self, repository, mock_session):
        """Test searching webhook events"""
        # Arrange
        mock_events = [Mock(id=1)]
        mock_query = Mock()
        mock_query.filter.return_value.limit.return_value.all.return_value = mock_events
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.search("message")
        
        # Assert
        assert result == mock_events
        mock_query.filter.assert_called_once()