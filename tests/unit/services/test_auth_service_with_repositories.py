"""
Tests for AuthService using Repository Pattern
Following TDD principles: RED phase - tests written BEFORE refactoring
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
from sqlalchemy.orm import Session

from services.auth_service_refactored import AuthService
from repositories.user_repository import UserRepository
from repositories.invite_token_repository import InviteTokenRepository
from services.common.result import Result, PagedResult
from crm_database import User, InviteToken


class TestAuthServiceWithRepositories:
    """Test AuthService with repository pattern integration"""
    
    @pytest.fixture
    def mock_session(self):
        """Mock database session"""
        return Mock(spec=Session)
    
    @pytest.fixture
    def mock_user_repository(self):
        """Mock UserRepository"""
        return Mock(spec=UserRepository)
    
    @pytest.fixture
    def mock_invite_repository(self):
        """Mock InviteTokenRepository"""
        return Mock(spec=InviteTokenRepository)
    
    @pytest.fixture
    def mock_email_service(self):
        """Mock email service"""
        return Mock()
    
    @pytest.fixture
    def auth_service(self, mock_session, mock_user_repository, mock_invite_repository, mock_email_service):
        """Create AuthService instance with mocked dependencies"""
        service = AuthService(email_service=mock_email_service, session=mock_session)
        # Inject repositories
        service.user_repository = mock_user_repository
        service.invite_repository = mock_invite_repository
        return service
    
    @pytest.fixture
    def sample_user(self):
        """Sample User instance"""
        user = User(
            id=1,
            email='test@example.com',
            password_hash='hashed_password',
            first_name='Test',
            last_name='User',
            role='marketer',
            is_active=True,
            created_at=datetime.utcnow()
        )
        user.id = 1
        return user
    
    @pytest.fixture
    def sample_invite(self):
        """Sample InviteToken instance"""
        invite = InviteToken(
            id=1,
            email='invite@example.com',
            token='abc123def456',
            role='marketer',
            created_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(days=7),
            used=False,
            created_by_id=1
        )
        invite.id = 1
        return invite
    
    # Tests for create_user method using repository
    def test_create_user_should_use_user_repository_to_check_existing(self, auth_service, mock_user_repository):
        """Test that create_user uses user repository to check for existing user"""
        # Arrange
        mock_user_repository.find_by_email.return_value = None
        
        # Act
        result = auth_service.create_user('new@example.com', 'Password123!', 'New', 'User')
        
        # Assert
        mock_user_repository.find_by_email.assert_called_once_with('new@example.com')
    
    def test_create_user_should_fail_when_user_exists_via_repository(self, auth_service, mock_user_repository, sample_user):
        """Test that create_user fails when repository finds existing user"""
        # Arrange
        mock_user_repository.find_by_email.return_value = sample_user
        
        # Act
        result = auth_service.create_user('test@example.com', 'Password123!', 'Test', 'User')
        
        # Assert
        assert result.is_failure
        assert result.error_code == "USER_EXISTS"
        mock_user_repository.find_by_email.assert_called_once_with('test@example.com')
    
    # Tests for authenticate_user method using repository
    def test_authenticate_user_should_use_user_repository(self, auth_service, mock_user_repository):
        """Test that authenticate_user uses user repository"""
        # Arrange
        mock_user_repository.find_by_email.return_value = None
        
        # Act
        result = auth_service.authenticate_user('test@example.com', 'password')
        
        # Assert
        mock_user_repository.find_by_email.assert_called_once_with('test@example.com')
        assert result.is_failure
        assert result.error_code == "INVALID_CREDENTIALS"
    
    def test_authenticate_user_should_succeed_with_valid_credentials_via_repository(self, auth_service, mock_user_repository, sample_user):
        """Test successful authentication using repository"""
        # Arrange
        mock_user_repository.find_by_email.return_value = sample_user
        mock_user_repository.update_last_login.return_value = sample_user
        
        with patch('services.auth_service_refactored.check_password_hash', return_value=True):
            # Act
            result = auth_service.authenticate_user('test@example.com', 'password')
            
            # Assert
            assert result.is_success
            assert result.data == sample_user
            mock_user_repository.find_by_email.assert_called_once_with('test@example.com')
            mock_user_repository.update_last_login.assert_called_once()
    
    # Tests for get_user_by_id method using repository
    def test_get_user_by_id_should_use_user_repository(self, auth_service, mock_user_repository, sample_user):
        """Test that get_user_by_id uses user repository"""
        # Arrange
        mock_user_repository.get_by_id.return_value = sample_user
        
        # Act
        result = auth_service.get_user_by_id(1)
        
        # Assert
        assert result.is_success
        assert result.data == sample_user
        mock_user_repository.get_by_id.assert_called_once_with(1)
    
    def test_get_user_by_id_should_fail_when_repository_returns_none(self, auth_service, mock_user_repository):
        """Test get_user_by_id failure when repository returns None"""
        # Arrange
        mock_user_repository.get_by_id.return_value = None
        
        # Act
        result = auth_service.get_user_by_id(999)
        
        # Assert
        assert result.is_failure
        assert result.error_code == "USER_NOT_FOUND"
        mock_user_repository.get_by_id.assert_called_once_with(999)
    
    # Tests for get_user_by_email method using repository
    def test_get_user_by_email_should_use_user_repository(self, auth_service, mock_user_repository, sample_user):
        """Test that get_user_by_email uses user repository"""
        # Arrange
        mock_user_repository.find_by_email.return_value = sample_user
        
        # Act
        result = auth_service.get_user_by_email('test@example.com')
        
        # Assert
        assert result.is_success
        assert result.data == sample_user
        mock_user_repository.find_by_email.assert_called_once_with('test@example.com')
    
    def test_get_user_by_email_should_fail_when_repository_returns_none(self, auth_service, mock_user_repository):
        """Test get_user_by_email failure when repository returns None"""
        # Arrange
        mock_user_repository.find_by_email.return_value = None
        
        # Act
        result = auth_service.get_user_by_email('nonexistent@example.com')
        
        # Assert
        assert result.is_failure
        assert result.error_code == "USER_NOT_FOUND"
        mock_user_repository.find_by_email.assert_called_once_with('nonexistent@example.com')
    
    # Tests for get_all_users method using repository
    def test_get_all_users_should_use_user_repository_pagination(self, auth_service, mock_user_repository, sample_user):
        """Test that get_all_users uses user repository pagination"""
        # Arrange
        from repositories.base_repository import PaginatedResult
        paginated_result = PaginatedResult(
            items=[sample_user],
            total=1,
            page=1,
            per_page=50
        )
        mock_user_repository.get_paginated.return_value = paginated_result
        
        # Act
        result = auth_service.get_all_users(page=1, per_page=50)
        
        # Assert
        assert isinstance(result, PagedResult)
        assert result.data == [sample_user]
        assert result.total == 1
        mock_user_repository.get_paginated.assert_called_once()
    
    # Tests for create_invite method using repository
    def test_create_invite_should_use_user_repository_to_check_existing(self, auth_service, mock_user_repository, mock_invite_repository):
        """Test that create_invite uses user repository to check existing user"""
        # Arrange
        mock_user_repository.find_by_email.return_value = None
        mock_invite_repository.find_valid_invite_by_email.return_value = None
        
        # Act
        result = auth_service.create_invite('new@example.com', 'marketer', 1)
        
        # Assert
        mock_user_repository.find_by_email.assert_called_once_with('new@example.com')
    
    def test_create_invite_should_fail_when_user_exists_via_repository(self, auth_service, mock_user_repository, mock_invite_repository, sample_user):
        """Test that create_invite fails when user repository finds existing user"""
        # Arrange
        mock_user_repository.find_by_email.return_value = sample_user
        
        # Act
        result = auth_service.create_invite('test@example.com', 'marketer', 1)
        
        # Assert
        assert result.is_failure
        assert result.error_code == "USER_EXISTS"
        mock_user_repository.find_by_email.assert_called_once_with('test@example.com')
    
    def test_create_invite_should_use_invite_repository_to_check_existing(self, auth_service, mock_user_repository, mock_invite_repository):
        """Test that create_invite uses invite repository to check existing invites"""
        # Arrange
        mock_user_repository.find_by_email.return_value = None
        mock_invite_repository.find_valid_invite_by_email.return_value = None
        
        # Act
        result = auth_service.create_invite('new@example.com', 'marketer', 1)
        
        # Assert
        mock_invite_repository.find_valid_invite_by_email.assert_called_once_with('new@example.com')
    
    def test_create_invite_should_fail_when_valid_invite_exists_via_repository(self, auth_service, mock_user_repository, mock_invite_repository, sample_invite):
        """Test that create_invite fails when valid invite exists"""
        # Arrange
        mock_user_repository.find_by_email.return_value = None
        mock_invite_repository.find_valid_invite_by_email.return_value = sample_invite
        
        # Act
        result = auth_service.create_invite('invite@example.com', 'marketer', 1)
        
        # Assert
        assert result.is_failure
        assert result.error_code == "INVITE_EXISTS"
    
    # Tests for validate_invite method using repository
    def test_validate_invite_should_use_invite_repository(self, auth_service, mock_invite_repository, sample_invite):
        """Test that validate_invite uses invite repository"""
        # Arrange
        mock_invite_repository.find_by_token.return_value = sample_invite
        
        # Act
        result = auth_service.validate_invite('abc123def456')
        
        # Assert
        assert result.is_success
        assert result.data == sample_invite
        mock_invite_repository.find_by_token.assert_called_once_with('abc123def456')
    
    def test_validate_invite_should_fail_when_repository_returns_none(self, auth_service, mock_invite_repository):
        """Test validate_invite failure when repository returns None"""
        # Arrange
        mock_invite_repository.find_by_token.return_value = None
        
        # Act
        result = auth_service.validate_invite('invalid_token')
        
        # Assert
        assert result.is_failure
        assert result.error_code == "INVALID_TOKEN"
        mock_invite_repository.find_by_token.assert_called_once_with('invalid_token')
    
    def test_validate_invite_should_fail_when_invite_is_used(self, auth_service, mock_invite_repository, sample_invite):
        """Test validate_invite failure when invite is used"""
        # Arrange
        sample_invite.used = True
        mock_invite_repository.find_by_token.return_value = sample_invite
        
        # Act
        result = auth_service.validate_invite('abc123def456')
        
        # Assert
        assert result.is_failure
        assert result.error_code == "TOKEN_USED"
    
    def test_validate_invite_should_fail_when_invite_is_expired(self, auth_service, mock_invite_repository, sample_invite):
        """Test validate_invite failure when invite is expired"""
        # Arrange
        sample_invite.expires_at = datetime.utcnow() - timedelta(days=1)
        mock_invite_repository.find_by_token.return_value = sample_invite
        
        # Act
        result = auth_service.validate_invite('abc123def456')
        
        # Assert
        assert result.is_failure
        assert result.error_code == "TOKEN_EXPIRED"
    
    # Tests for use_invite method using repositories
    def test_use_invite_should_mark_invite_as_used_via_repository(self, auth_service, mock_user_repository, mock_invite_repository, sample_invite):
        """Test that use_invite marks invite as used via repository"""
        # Arrange
        # Mock successful invite validation
        mock_invite_repository.find_by_token.return_value = sample_invite
        
        # Mock successful user creation
        created_user = User(
            id=2,
            email=sample_invite.email,
            password_hash='new_hash',
            first_name='New',
            last_name='User',
            role=sample_invite.role,
            is_active=True
        )
        created_user.id = 2
        
        # Mock repository methods
        mock_user_repository.find_by_email.return_value = None  # No existing user
        
        # Act
        with patch.object(auth_service, 'create_user', return_value=Result.success(created_user)):
            result = auth_service.use_invite('abc123def456', 'Password123!', 'New', 'User')
        
        # Assert
        assert result.is_success
        mock_invite_repository.find_by_token.assert_called_once_with('abc123def456')
        mock_invite_repository.mark_as_used.assert_called_once()
    
    # Integration tests - testing that methods work together
    def test_auth_service_should_inject_repositories_properly(self, mock_session, mock_email_service):
        """Test that AuthService properly initializes with repositories"""
        # Act
        service = AuthService(email_service=mock_email_service, session=mock_session)
        
        # Assert that repositories will be injected
        # This test verifies the structure is ready for dependency injection
        assert hasattr(service, 'session')
        assert service.email_service == mock_email_service
    
    def test_repositories_should_be_accessible_from_auth_service(self, auth_service):
        """Test that repositories are accessible from auth service"""
        # Assert
        assert hasattr(auth_service, 'user_repository')
        assert hasattr(auth_service, 'invite_repository')
        assert auth_service.user_repository is not None
        assert auth_service.invite_repository is not None
    
    # Error handling tests
    def test_auth_service_should_handle_repository_errors_gracefully(self, auth_service, mock_user_repository):
        """Test that auth service handles repository errors gracefully"""
        # Arrange
        mock_user_repository.find_by_email.side_effect = Exception("Database error")
        
        # Act & Assert
        # This should raise an exception since we haven't implemented error handling yet
        # This test documents current behavior - in future, we should wrap in try/catch
        with pytest.raises(Exception, match="Database error"):
            result = auth_service.get_user_by_email('test@example.com')
        
        mock_user_repository.find_by_email.assert_called_once_with('test@example.com')
    
    # Tests for repository method calls with correct parameters
    def test_create_user_should_use_repository_create_with_correct_parameters(self, auth_service, mock_user_repository):
        """Test that create_user calls repository.create with correct parameters"""
        # Arrange
        mock_user_repository.find_by_email.return_value = None
        mock_user_repository.create.return_value = Mock()
        
        # Act
        with patch('services.auth_service_refactored.generate_password_hash', return_value='hashed'):
            result = auth_service.create_user('new@example.com', 'Password123!', 'New', 'User')
        
        # Assert
        mock_user_repository.create.assert_called_once()
        call_args = mock_user_repository.create.call_args[1]  # keyword arguments
        assert call_args['email'] == 'new@example.com'
        assert call_args['first_name'] == 'New'
        assert call_args['last_name'] == 'User'
        assert call_args['password_hash'] == 'hashed'