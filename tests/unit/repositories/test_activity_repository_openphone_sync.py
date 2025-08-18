"""
Tests for ActivityRepository OpenPhone sync methods
TDD RED Phase - These tests are written FIRST and MUST fail initially
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock
from repositories.activity_repository import ActivityRepository
from crm_database import Activity, Contact


class TestActivityRepositoryOpenPhoneSync:
    """Test OpenPhone sync methods for ActivityRepository"""
    
    @pytest.fixture
    def mock_session(self):
        """Mock database session"""
        session = MagicMock()
        return session
    
    @pytest.fixture
    def repository(self, mock_session):
        """Create ActivityRepository with mocked session"""
        return ActivityRepository(mock_session, Activity)
    
    def test_find_latest_by_type(self, repository, mock_session):
        """Test finding the latest activity of a specific type"""
        # Arrange
        mock_activity = Mock(id=1, activity_type='sms', created_at=datetime.now())
        mock_query = mock_session.query.return_value
        mock_query.filter_by.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.first.return_value = mock_activity
        
        # Act
        result = repository.find_latest_by_type('sms')
        
        # Assert
        assert result == mock_activity
        mock_session.query.assert_called_once_with(Activity)
        mock_query.filter_by.assert_called_once_with(activity_type='sms')
        mock_query.order_by.assert_called_once()
        mock_query.first.assert_called_once()
    
    def test_find_latest_by_type_no_results(self, repository, mock_session):
        """Test find_latest_by_type when no activities exist"""
        # Arrange
        mock_query = mock_session.query.return_value
        mock_query.filter_by.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.first.return_value = None
        
        # Act
        result = repository.find_latest_by_type('sms')
        
        # Assert
        assert result is None
        mock_session.query.assert_called_once_with(Activity)
        mock_query.filter_by.assert_called_once_with(activity_type='sms')
    
    def test_find_recent_by_type_with_contact(self, repository, mock_session):
        """Test finding recent activities by type with contact information"""
        # Arrange
        mock_contact = Mock(id=1, first_name='John', last_name='Doe')
        mock_activity1 = Mock(
            id=1, 
            activity_type='sms',
            direction='inbound',
            body='Test message 1',
            created_at=datetime.now(),
            contact=mock_contact
        )
        mock_activity2 = Mock(
            id=2,
            activity_type='sms', 
            direction='outbound',
            body='Test message 2 with longer content that should be truncated',
            created_at=datetime.now() - timedelta(minutes=5),
            contact=mock_contact
        )
        
        mock_query = mock_session.query.return_value
        mock_query.filter_by.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = [mock_activity1, mock_activity2]
        
        # Act
        result = repository.find_recent_by_type_with_contact('sms', limit=10)
        
        # Assert
        assert len(result) == 2
        assert result[0] == mock_activity1
        assert result[1] == mock_activity2
        mock_session.query.assert_called_once_with(Activity)
        mock_query.filter_by.assert_called_once_with(activity_type='sms')
        mock_query.order_by.assert_called_once()
        mock_query.limit.assert_called_once_with(10)
        mock_query.all.assert_called_once()
    
    def test_find_recent_by_type_with_contact_default_limit(self, repository, mock_session):
        """Test find_recent_by_type_with_contact uses default limit when not specified"""
        # Arrange
        mock_query = mock_session.query.return_value
        mock_query.filter_by.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = []
        
        # Act
        repository.find_recent_by_type_with_contact('sms')
        
        # Assert
        mock_query.limit.assert_called_once_with(10)  # Default limit should be 10
    
    def test_find_recent_by_type_with_contact_empty_results(self, repository, mock_session):
        """Test find_recent_by_type_with_contact when no activities exist"""
        # Arrange
        mock_query = mock_session.query.return_value
        mock_query.filter_by.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = []
        
        # Act
        result = repository.find_recent_by_type_with_contact('sms')
        
        # Assert
        assert result == []
        mock_session.query.assert_called_once_with(Activity)
        mock_query.filter_by.assert_called_once_with(activity_type='sms')
