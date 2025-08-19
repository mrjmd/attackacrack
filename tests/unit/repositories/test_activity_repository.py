"""
Tests for ActivityRepository
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime
from repositories.activity_repository import ActivityRepository
from repositories.base_repository import PaginatedResult
from crm_database import Activity


class TestActivityRepository:
    """Test suite for ActivityRepository"""
    
    @pytest.fixture
    def mock_session(self):
        """Mock database session"""
        session = MagicMock()
        return session
    
    @pytest.fixture
    def repository(self, mock_session):
        """Create ActivityRepository with mocked session"""
        return ActivityRepository(mock_session, Activity)
    
    def test_find_by_conversation_id(self, repository, mock_session):
        """Test finding activities by conversation ID"""
        # Arrange
        mock_activities = [Mock(id=1), Mock(id=2)]
        mock_query = Mock()
        mock_query.filter_by.return_value.order_by.return_value.all.return_value = mock_activities
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.find_by_conversation_id(123)
        
        # Assert
        assert result == mock_activities
        mock_query.filter_by.assert_called_once_with(conversation_id=123)
    
    def test_find_by_contact_id(self, repository, mock_session):
        """Test finding activities by contact ID"""
        # Arrange
        mock_activities = [Mock(id=1), Mock(id=2)]
        mock_query = Mock()
        mock_query.filter_by.return_value.order_by.return_value.limit.return_value.all.return_value = mock_activities
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.find_by_contact_id(456, limit=10)
        
        # Assert
        assert result == mock_activities
        mock_query.filter_by.assert_called_once_with(contact_id=456)
    
    def test_find_recent_activities(self, repository, mock_session):
        """Test finding recent activities"""
        # Arrange
        mock_activities = [Mock(id=1), Mock(id=2)]
        mock_query = Mock()
        mock_query.order_by.return_value.limit.return_value.all.return_value = mock_activities
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.find_recent_activities(limit=20)
        
        # Assert
        assert result == mock_activities
        mock_query.order_by.assert_called_once()
        mock_query.order_by.return_value.limit.assert_called_once_with(20)
    
    def test_find_by_type(self, repository, mock_session):
        """Test finding activities by type"""
        # Arrange
        mock_activities = [Mock(id=1, type="sms")]
        mock_query = Mock()
        mock_query.filter_by.return_value.all.return_value = mock_activities
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.find_by_type("sms")
        
        # Assert
        assert result == mock_activities
        mock_query.filter_by.assert_called_once_with(activity_type="sms")
    
    def test_find_by_openphone_id(self, repository, mock_session):
        """Test finding activity by OpenPhone ID"""
        # Arrange
        mock_activity = Mock(id=1, openphone_id="op_123")
        mock_query = Mock()
        mock_query.filter_by.return_value.first.return_value = mock_activity
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.find_by_openphone_id("op_123")
        
        # Assert
        assert result == mock_activity
        mock_query.filter_by.assert_called_once_with(openphone_id="op_123")
    
    def test_get_activities_page(self, repository, mock_session):
        """Test getting paginated activities"""
        # Arrange
        mock_activities = [Mock(id=1), Mock(id=2)]
        mock_query = Mock()
        mock_session.query.return_value = mock_query
        mock_query.count.return_value = 100
        mock_query.order_by.return_value.limit.return_value.offset.return_value.all.return_value = mock_activities
        
        # Act
        result = repository.get_activities_page(page=2, per_page=20)
        
        # Assert
        assert isinstance(result, PaginatedResult)
        assert result.items == mock_activities
        assert result.total == 100
        assert result.page == 2
        assert result.per_page == 20
    
    def test_count_by_type(self, repository, mock_session):
        """Test counting activities by type"""
        # Arrange
        mock_query = Mock()
        mock_query.filter_by.return_value.count.return_value = 42
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.count_by_type("call")
        
        # Assert
        assert result == 42
        mock_query.filter_by.assert_called_once_with(activity_type="call")
    
    def test_update_activity_summary(self, repository, mock_session):
        """Test updating activity summary"""
        # Arrange
        mock_activity = Mock(id=1, summary=None)
        mock_query = Mock()
        mock_query.get.return_value = mock_activity
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.update_activity_summary(1, "New summary text")
        
        # Assert
        assert result == mock_activity
        assert mock_activity.summary == "New summary text"
        mock_session.commit.assert_called_once()
    
    def test_find_unprocessed_activities(self, repository, mock_session):
        """Test finding unprocessed activities"""
        # Arrange
        mock_activities = [Mock(id=1), Mock(id=2)]
        mock_query = Mock()
        mock_query.filter_by.return_value.limit.return_value.all.return_value = mock_activities
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.find_unprocessed_activities(limit=50)
        
        # Assert
        assert result == mock_activities
        mock_query.filter_by.assert_called_once_with(processed=False)
    
    def test_mark_as_processed(self, repository, mock_session):
        """Test marking activity as processed"""
        # Arrange
        mock_activity = Mock(id=1, processed=False)
        mock_query = Mock()
        mock_query.get.return_value = mock_activity
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.mark_as_processed(1)
        
        # Assert
        assert result is True
        assert mock_activity.processed is True
        mock_session.commit.assert_called_once()