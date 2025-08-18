"""
Tests for InviteTokenRepository - Repository Pattern for InviteToken entities
Following TDD principles: RED phase - tests written BEFORE implementation
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from repositories.invite_token_repository import InviteTokenRepository
from repositories.base_repository import PaginationParams, PaginatedResult, SortOrder
from crm_database import InviteToken, User


class TestInviteTokenRepository:
    """Test InviteTokenRepository functionality"""
    
    @pytest.fixture
    def mock_session(self):
        """Mock database session"""
        return Mock(spec=Session)
    
    @pytest.fixture
    def invite_repository(self, mock_session):
        """Create InviteTokenRepository instance with mocked session"""
        return InviteTokenRepository(session=mock_session, model_class=InviteToken)
    
    @pytest.fixture
    def sample_invite_data(self):
        """Sample invite token data for testing"""
        return {
            'email': 'invite@example.com',
            'token': 'abc123def456',
            'role': 'marketer',
            'created_at': datetime.utcnow(),
            'expires_at': datetime.utcnow() + timedelta(days=7),
            'used': False,
            'created_by_id': 1
        }
    
    @pytest.fixture
    def sample_invite(self, sample_invite_data):
        """Sample InviteToken instance"""
        invite = InviteToken(**sample_invite_data)
        invite.id = 1
        return invite
    
    @pytest.fixture
    def expired_invite(self, sample_invite_data):
        """Sample expired InviteToken instance"""
        data = sample_invite_data.copy()
        data['expires_at'] = datetime.utcnow() - timedelta(days=1)
        invite = InviteToken(**data)
        invite.id = 2
        return invite
    
    @pytest.fixture
    def used_invite(self, sample_invite_data):
        """Sample used InviteToken instance"""
        data = sample_invite_data.copy()
        data['used'] = True
        data['used_at'] = datetime.utcnow()
        invite = InviteToken(**data)
        invite.id = 3
        return invite
    
    # Test search method (required by BaseRepository abstract method)
    def test_search_by_email(self, invite_repository, mock_session, sample_invite):
        """Test searching invite tokens by email"""
        # Arrange
        mock_query = Mock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value.all.return_value = [sample_invite]
        
        # Act
        result = invite_repository.search("invite@example.com", fields=['email'])
        
        # Assert
        assert len(result) == 1
        assert result[0] == sample_invite
        mock_session.query.assert_called_once_with(InviteToken)
    
    def test_search_by_token(self, invite_repository, mock_session, sample_invite):
        """Test searching invite tokens by token"""
        # Arrange
        mock_query = Mock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value.all.return_value = [sample_invite]
        
        # Act
        result = invite_repository.search("abc123", fields=['token'])
        
        # Assert
        assert len(result) == 1
        assert result[0] == sample_invite
    
    def test_search_empty_query_returns_empty_list(self, invite_repository):
        """Test that empty search query returns empty list"""
        # Act
        result = invite_repository.search("")
        
        # Assert
        assert result == []
    
    # Test invite-specific query methods
    def test_find_by_token_success(self, invite_repository, mock_session, sample_invite):
        """Test finding invite by token - success case"""
        # Arrange
        mock_query = Mock()
        mock_session.query.return_value = mock_query
        mock_query.filter_by.return_value.first.return_value = sample_invite
        
        # Act
        result = invite_repository.find_by_token("abc123def456")
        
        # Assert
        assert result == sample_invite
        mock_session.query.assert_called_once_with(InviteToken)
        mock_query.filter_by.assert_called_once_with(token="abc123def456")
    
    def test_find_by_token_not_found(self, invite_repository, mock_session):
        """Test finding invite by token - not found"""
        # Arrange
        mock_query = Mock()
        mock_session.query.return_value = mock_query
        mock_query.filter_by.return_value.first.return_value = None
        
        # Act
        result = invite_repository.find_by_token("nonexistent")
        
        # Assert
        assert result is None
    
    def test_find_by_email(self, invite_repository, mock_session, sample_invite):
        """Test finding invites by email"""
        # Arrange
        mock_query = Mock()
        mock_session.query.return_value = mock_query
        mock_query.filter_by.return_value.all.return_value = [sample_invite]
        
        # Act
        result = invite_repository.find_by_email("invite@example.com")
        
        # Assert
        assert len(result) == 1
        assert result[0] == sample_invite
        mock_query.filter_by.assert_called_once_with(email="invite@example.com")
    
    def test_find_unused_invites_by_email(self, invite_repository, mock_session, sample_invite):
        """Test finding unused invites for an email"""
        # Arrange
        mock_query = Mock()
        mock_session.query.return_value = mock_query
        mock_query.filter_by.return_value.all.return_value = [sample_invite]
        
        # Act
        result = invite_repository.find_unused_invites_by_email("invite@example.com")
        
        # Assert
        assert len(result) == 1
        assert result[0] == sample_invite
        mock_query.filter_by.assert_called_once_with(email="invite@example.com", used=False)
    
    def test_find_valid_invite_by_email(self, invite_repository, mock_session, sample_invite):
        """Test finding valid (unused & unexpired) invite by email"""
        # Arrange
        mock_query = Mock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value.first.return_value = sample_invite
        
        # Act
        result = invite_repository.find_valid_invite_by_email("invite@example.com")
        
        # Assert
        assert result == sample_invite
        mock_session.query.assert_called_once_with(InviteToken)
    
    def test_find_valid_invite_by_email_not_found(self, invite_repository, mock_session):
        """Test finding valid invite when none exists"""
        # Arrange
        mock_query = Mock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value.first.return_value = None
        
        # Act
        result = invite_repository.find_valid_invite_by_email("nonexistent@example.com")
        
        # Assert
        assert result is None
    
    def test_get_expired_invites(self, invite_repository, mock_session, expired_invite):
        """Test getting all expired invites"""
        # Arrange
        mock_query = Mock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value.all.return_value = [expired_invite]
        
        # Act
        result = invite_repository.get_expired_invites()
        
        # Assert
        assert len(result) == 1
        assert result[0] == expired_invite
    
    def test_get_unused_invites(self, invite_repository, mock_session, sample_invite):
        """Test getting all unused invites"""
        # Arrange
        mock_query = Mock()
        mock_session.query.return_value = mock_query
        mock_query.filter_by.return_value.all.return_value = [sample_invite]
        
        # Act
        result = invite_repository.get_unused_invites()
        
        # Assert
        assert len(result) == 1
        assert result[0] == sample_invite
        mock_query.filter_by.assert_called_once_with(used=False)
    
    def test_get_used_invites(self, invite_repository, mock_session, used_invite):
        """Test getting all used invites"""
        # Arrange
        mock_query = Mock()
        mock_session.query.return_value = mock_query
        mock_query.filter_by.return_value.all.return_value = [used_invite]
        
        # Act
        result = invite_repository.get_used_invites()
        
        # Assert
        assert len(result) == 1
        assert result[0] == used_invite
        mock_query.filter_by.assert_called_once_with(used=True)
    
    def test_get_invites_by_creator(self, invite_repository, mock_session, sample_invite):
        """Test getting invites created by specific user"""
        # Arrange
        mock_query = Mock()
        mock_session.query.return_value = mock_query
        mock_query.filter_by.return_value.all.return_value = [sample_invite]
        
        # Act
        result = invite_repository.get_invites_by_creator(1)
        
        # Assert
        assert len(result) == 1
        assert result[0] == sample_invite
        mock_query.filter_by.assert_called_once_with(created_by_id=1)
    
    def test_mark_as_used(self, invite_repository, mock_session, sample_invite):
        """Test marking an invite as used"""
        # Arrange
        mock_session.get.return_value = sample_invite
        used_time = datetime.utcnow()
        
        # Act
        result = invite_repository.mark_as_used(1, used_time)
        
        # Assert
        assert result == sample_invite
        assert sample_invite.used is True
        assert sample_invite.used_at == used_time
        mock_session.flush.assert_called_once()
    
    def test_mark_as_used_invite_not_found(self, invite_repository, mock_session):
        """Test marking non-existent invite as used"""
        # Arrange
        mock_session.get.return_value = None
        
        # Act
        result = invite_repository.mark_as_used(999, datetime.utcnow())
        
        # Assert
        assert result is None
    
    def test_cleanup_expired_invites(self, invite_repository, mock_session):
        """Test cleaning up expired invites"""
        # Arrange
        mock_query = Mock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value.delete.return_value = 3
        
        # Act
        count = invite_repository.cleanup_expired_invites()
        
        # Assert
        assert count == 3
        mock_session.flush.assert_called_once()
    
    def test_get_invite_stats(self, invite_repository, mock_session):
        """Test getting invite statistics"""
        # Arrange
        mock_session.query.return_value.count.return_value = 10
        mock_session.query.return_value.filter_by.return_value.count.return_value = 5
        mock_session.query.return_value.filter.return_value.count.return_value = 2
        
        # Act
        stats = invite_repository.get_invite_stats()
        
        # Assert
        assert 'total_invites' in stats
        assert 'used_invites' in stats
        assert 'unused_invites' in stats
        assert 'expired_invites' in stats
        assert stats['total_invites'] == 10
    
    def test_get_recent_invites(self, invite_repository, mock_session, sample_invite):
        """Test getting recently created invites"""
        # Arrange
        mock_query = Mock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [sample_invite]
        
        # Act
        result = invite_repository.get_recent_invites(days=7, limit=10)
        
        # Assert
        assert len(result) == 1
        assert result[0] == sample_invite
    
    def test_get_invites_expiring_soon(self, invite_repository, mock_session, sample_invite):
        """Test getting invites expiring soon"""
        # Arrange
        mock_query = Mock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value.order_by.return_value.all.return_value = [sample_invite]
        
        # Act
        result = invite_repository.get_invites_expiring_soon(hours=24)
        
        # Assert
        assert len(result) == 1
        assert result[0] == sample_invite
    
    def test_get_paginated_invites(self, invite_repository, mock_session, sample_invite):
        """Test getting paginated invites with filters"""
        # Arrange
        pagination = PaginationParams(page=1, per_page=10)
        mock_query = Mock()
        mock_session.query.return_value = mock_query
        mock_query.filter_by.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.count.return_value = 1
        mock_query.offset.return_value.limit.return_value.all.return_value = [sample_invite]
        
        # Act
        result = invite_repository.get_paginated_invites(
            pagination=pagination,
            used_filter=False,
            role_filter='marketer'
        )
        
        # Assert
        assert isinstance(result, PaginatedResult)
        assert len(result.items) == 1
        assert result.total == 1
        assert result.page == 1
    
    def test_bulk_expire_invites_by_email(self, invite_repository, mock_session):
        """Test bulk expiring invites for specific email"""
        # Arrange
        mock_query = Mock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value.update.return_value = 2
        
        # Act
        count = invite_repository.bulk_expire_invites_by_email("test@example.com")
        
        # Assert
        assert count == 2
        mock_session.flush.assert_called_once()
    
    # Error handling tests
    def test_find_by_token_handles_database_error(self, invite_repository, mock_session):
        """Test that database errors are handled gracefully"""
        # Arrange
        mock_session.query.side_effect = SQLAlchemyError("Database error")
        
        # Act
        result = invite_repository.find_by_token("abc123")
        
        # Assert
        assert result is None
    
    def test_cleanup_expired_invites_handles_database_error(self, invite_repository, mock_session):
        """Test that cleanup method handles database errors"""
        # Arrange
        mock_session.query.side_effect = SQLAlchemyError("Database error")
        
        # Act
        count = invite_repository.cleanup_expired_invites()
        
        # Assert
        assert count == 0
    
    def test_get_invite_stats_handles_database_error(self, invite_repository, mock_session):
        """Test that stats method handles database errors"""
        # Arrange
        mock_session.query.side_effect = SQLAlchemyError("Database error")
        
        # Act
        stats = invite_repository.get_invite_stats()
        
        # Assert
        assert all(count == 0 for count in stats.values())
    
    # Edge cases
    def test_get_recent_invites_with_zero_days(self, invite_repository, mock_session):
        """Test getting recent invites with 0 days should return empty list"""
        # Act
        result = invite_repository.get_recent_invites(days=0)
        
        # Assert
        assert result == []
    
    def test_get_invites_expiring_soon_with_zero_hours(self, invite_repository, mock_session):
        """Test getting expiring invites with 0 hours should return empty list"""
        # Act
        result = invite_repository.get_invites_expiring_soon(hours=0)
        
        # Assert
        assert result == []
    
    def test_mark_as_used_with_invalid_data(self, invite_repository, mock_session, sample_invite):
        """Test marking invite as used with None values"""
        # Arrange
        mock_session.get.return_value = sample_invite
        
        # Act
        result = invite_repository.mark_as_used(1, None)
        
        # Assert
        assert result == sample_invite
        assert sample_invite.used is True
        assert sample_invite.used_at is None