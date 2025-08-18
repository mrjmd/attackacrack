"""
Tests for UserRepository - Repository Pattern for User entities
Following TDD principles: RED phase - tests written BEFORE implementation
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from repositories.user_repository import UserRepository
from repositories.base_repository import PaginationParams, PaginatedResult, SortOrder
from crm_database import User


class TestUserRepository:
    """Test UserRepository functionality"""
    
    @pytest.fixture
    def mock_session(self):
        """Mock database session"""
        return Mock(spec=Session)
    
    @pytest.fixture
    def user_repository(self, mock_session):
        """Create UserRepository instance with mocked session"""
        return UserRepository(session=mock_session, model_class=User)
    
    @pytest.fixture
    def sample_user_data(self):
        """Sample user data for testing"""
        return {
            'email': 'test@example.com',
            'password_hash': 'hashed_password',
            'first_name': 'Test',
            'last_name': 'User',
            'role': 'marketer',
            'is_active': True,
            'created_at': datetime.utcnow()
        }
    
    @pytest.fixture
    def sample_user(self, sample_user_data):
        """Sample User instance"""
        user = User(**sample_user_data)
        user.id = 1
        return user
    
    # Test search method (required by BaseRepository abstract method)
    def test_search_by_email(self, user_repository, mock_session, sample_user):
        """Test searching users by email"""
        # Arrange
        mock_query = Mock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value.all.return_value = [sample_user]
        
        # Act
        result = user_repository.search("test@example.com", fields=['email'])
        
        # Assert
        assert len(result) == 1
        assert result[0] == sample_user
        mock_session.query.assert_called_once_with(User)
    
    def test_search_by_name(self, user_repository, mock_session, sample_user):
        """Test searching users by first_name"""
        # Arrange
        mock_query = Mock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value.all.return_value = [sample_user]
        
        # Act
        result = user_repository.search("Test", fields=['first_name'])
        
        # Assert
        assert len(result) == 1
        assert result[0] == sample_user
    
    def test_search_empty_query_returns_empty_list(self, user_repository):
        """Test that empty search query returns empty list"""
        # Act
        result = user_repository.search("")
        
        # Assert
        assert result == []
    
    def test_search_no_results(self, user_repository, mock_session):
        """Test search with no matching results"""
        # Arrange
        mock_query = Mock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value.all.return_value = []
        
        # Act
        result = user_repository.search("nonexistent")
        
        # Assert
        assert result == []
    
    # Test user-specific query methods
    def test_find_by_email_success(self, user_repository, mock_session, sample_user):
        """Test finding user by email - success case"""
        # Arrange
        mock_query = Mock()
        mock_session.query.return_value = mock_query
        mock_query.filter_by.return_value.first.return_value = sample_user
        
        # Act
        result = user_repository.find_by_email("test@example.com")
        
        # Assert
        assert result == sample_user
        mock_session.query.assert_called_once_with(User)
        mock_query.filter_by.assert_called_once_with(email="test@example.com")
    
    def test_find_by_email_not_found(self, user_repository, mock_session):
        """Test finding user by email - not found"""
        # Arrange
        mock_query = Mock()
        mock_session.query.return_value = mock_query
        mock_query.filter_by.return_value.first.return_value = None
        
        # Act
        result = user_repository.find_by_email("nonexistent@example.com")
        
        # Assert
        assert result is None
    
    def test_find_by_role(self, user_repository, mock_session, sample_user):
        """Test finding users by role"""
        # Arrange
        mock_query = Mock()
        mock_session.query.return_value = mock_query
        mock_query.filter_by.return_value.all.return_value = [sample_user]
        
        # Act
        result = user_repository.find_by_role('admin')
        
        # Assert
        assert len(result) == 1
        assert result[0] == sample_user
        mock_query.filter_by.assert_called_once_with(role='admin')
    
    def test_find_active_users(self, user_repository, mock_session, sample_user):
        """Test finding only active users"""
        # Arrange
        mock_query = Mock()
        mock_session.query.return_value = mock_query
        mock_query.filter_by.return_value.all.return_value = [sample_user]
        
        # Act
        result = user_repository.find_active_users()
        
        # Assert
        assert len(result) == 1
        assert result[0] == sample_user
        mock_query.filter_by.assert_called_once_with(is_active=True)
    
    def test_find_inactive_users(self, user_repository, mock_session):
        """Test finding only inactive users"""
        # Arrange
        inactive_user = Mock()
        inactive_user.is_active = False
        mock_query = Mock()
        mock_session.query.return_value = mock_query
        mock_query.filter_by.return_value.all.return_value = [inactive_user]
        
        # Act
        result = user_repository.find_inactive_users()
        
        # Assert
        assert len(result) == 1
        assert result[0] == inactive_user
        mock_query.filter_by.assert_called_once_with(is_active=False)
    
    def test_get_user_stats(self, user_repository, mock_session):
        """Test getting user statistics"""
        # Arrange
        mock_session.query.return_value.count.return_value = 10
        mock_session.query.return_value.filter_by.return_value.count.return_value = 8
        
        # Act
        stats = user_repository.get_user_stats()
        
        # Assert
        assert 'total_users' in stats
        assert 'active_users' in stats
        assert 'inactive_users' in stats
        assert 'admin_users' in stats
        assert stats['total_users'] == 10
    
    def test_count_by_role(self, user_repository, mock_session):
        """Test counting users by role"""
        # Arrange
        mock_session.query.return_value.filter_by.return_value.count.return_value = 3
        
        # Act
        count = user_repository.count_by_role('admin')
        
        # Assert
        assert count == 3
        mock_session.query.assert_called_with(User)
    
    def test_get_recent_users(self, user_repository, mock_session, sample_user):
        """Test getting recently created users"""
        # Arrange
        mock_query = Mock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [sample_user]
        
        # Act
        result = user_repository.get_recent_users(days=7, limit=10)
        
        # Assert
        assert len(result) == 1
        assert result[0] == sample_user
    
    def test_update_last_login(self, user_repository, mock_session, sample_user):
        """Test updating user's last login timestamp"""
        # Arrange
        login_time = datetime.utcnow()
        mock_session.get.return_value = sample_user
        
        # Act
        result = user_repository.update_last_login(1, login_time)
        
        # Assert
        assert result == sample_user
        assert sample_user.last_login == login_time
        mock_session.get.assert_called_once_with(User, 1)
        mock_session.flush.assert_called_once()
    
    def test_update_last_login_user_not_found(self, user_repository, mock_session):
        """Test updating last login for non-existent user"""
        # Arrange
        mock_session.get.return_value = None
        
        # Act
        result = user_repository.update_last_login(999, datetime.utcnow())
        
        # Assert
        assert result is None
    
    def test_deactivate_user(self, user_repository, mock_session, sample_user):
        """Test deactivating a user"""
        # Arrange
        sample_user.is_active = True
        mock_session.get.return_value = sample_user
        
        # Act
        result = user_repository.deactivate_user(1)
        
        # Assert
        assert result == sample_user
        assert sample_user.is_active is False
        mock_session.flush.assert_called_once()
    
    def test_activate_user(self, user_repository, mock_session, sample_user):
        """Test activating a user"""
        # Arrange
        sample_user.is_active = False
        mock_session.get.return_value = sample_user
        
        # Act
        result = user_repository.activate_user(1)
        
        # Assert
        assert result == sample_user
        assert sample_user.is_active is True
        mock_session.flush.assert_called_once()
    
    def test_get_paginated_users_with_filters(self, user_repository, mock_session, sample_user):
        """Test getting paginated users with role filter"""
        # Arrange
        pagination = PaginationParams(page=1, per_page=10)
        mock_query = Mock()
        mock_session.query.return_value = mock_query
        mock_query.filter_by.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.count.return_value = 1
        mock_query.offset.return_value.limit.return_value.all.return_value = [sample_user]
        
        # Act
        result = user_repository.get_paginated_users(
            pagination=pagination,
            role_filter='admin',
            active_only=True
        )
        
        # Assert
        assert isinstance(result, PaginatedResult)
        assert len(result.items) == 1
        assert result.total == 1
        assert result.page == 1
    
    def test_search_users_with_multiple_fields(self, user_repository, mock_session, sample_user):
        """Test searching users across multiple fields"""
        # Arrange
        mock_query = Mock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value.all.return_value = [sample_user]
        
        # Act
        result = user_repository.search_users("test", search_fields=['email', 'first_name'])
        
        # Assert
        assert len(result) == 1
        assert result[0] == sample_user
    
    # Error handling tests
    def test_find_by_email_handles_database_error(self, user_repository, mock_session):
        """Test that database errors are handled gracefully"""
        # Arrange
        mock_session.query.side_effect = SQLAlchemyError("Database error")
        
        # Act
        result = user_repository.find_by_email("test@example.com")
        
        # Assert
        assert result is None
    
    def test_get_user_stats_handles_database_error(self, user_repository, mock_session):
        """Test that stats method handles database errors"""
        # Arrange
        mock_session.query.side_effect = SQLAlchemyError("Database error")
        
        # Act
        stats = user_repository.get_user_stats()
        
        # Assert
        assert all(count == 0 for count in stats.values())
    
    # Edge cases
    def test_search_with_special_characters(self, user_repository, mock_session):
        """Test search with special characters"""
        # Arrange
        mock_query = Mock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value.all.return_value = []
        
        # Act
        result = user_repository.search("test@domain.com")
        
        # Assert
        assert result == []
    
    def test_get_recent_users_with_zero_days(self, user_repository, mock_session):
        """Test getting recent users with 0 days should return empty list"""
        # Act
        result = user_repository.get_recent_users(days=0)
        
        # Assert
        assert result == []
    
    def test_get_recent_users_with_negative_limit(self, user_repository, mock_session):
        """Test getting recent users with negative limit should return empty list"""
        # Act
        result = user_repository.get_recent_users(limit=-1)
        
        # Assert
        assert result == []