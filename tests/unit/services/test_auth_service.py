# tests/test_auth_service.py

import pytest
from unittest.mock import Mock, patch, MagicMock
from services.auth_service_refactored import AuthService
from services.common.result import Result
from crm_database import User, InviteToken
from datetime import datetime, timedelta
from flask import Flask
from werkzeug.security import generate_password_hash

class TestAuthService:
    """Test AuthService methods"""
    
    @pytest.fixture
    def mock_user_repository(self):
        """Create mock user repository"""
        repo = Mock()
        repo.find_by_email = Mock()
        repo.create = Mock()
        repo.update = Mock()
        repo.get_by_id = Mock()
        repo.find_all = Mock()
        repo.commit = Mock()
        repo.rollback = Mock()
        repo.update_last_login = Mock()
        return repo
    
    @pytest.fixture
    def mock_invite_repository(self):
        """Create mock invite repository"""
        repo = Mock()
        repo.find_by_token = Mock()
        repo.create = Mock()
        repo.update = Mock()
        repo.delete = Mock()
        repo.commit = Mock()
        repo.rollback = Mock()
        repo.find_valid_invite_by_email = Mock()
        repo.mark_as_used = Mock()
        return repo
    
    @pytest.fixture
    def mock_email_service(self):
        """Create mock email service"""
        service = Mock()
        service.send_invite = Mock(return_value=Result.success("Email sent"))
        return service
    
    @pytest.fixture
    def auth_service(self, mock_user_repository, mock_invite_repository, mock_email_service):
        """Create AuthService with mocked dependencies"""
        return AuthService(
            email_service=mock_email_service,
            user_repository=mock_user_repository,
            invite_repository=mock_invite_repository
        )

    def test_create_user_success(self, auth_service, mock_user_repository):
        """Test successful user creation"""
        # Setup mocks
        mock_user_repository.find_by_email.return_value = None  # No existing user
        mock_user_repository.commit = Mock()
        
        mock_user = Mock(spec=User)
        mock_user.id = 1
        mock_user.email = 'newuser@example.com'
        mock_user.first_name = 'New'
        mock_user.last_name = 'User'
        mock_user.role = 'marketer'
        mock_user.password_hash = 'hashed_password'
        mock_user_repository.create.return_value = mock_user
        
        # Call the service method
        result = auth_service.create_user(
            email='newuser@example.com',
            password='Password123!',
            first_name='New',
            last_name='User',
            role='marketer'
        )

        # Assert
        assert result.is_success
        user = result.data
        assert user is not None
        assert user.email == 'newuser@example.com'
        assert user.first_name == 'New'
        assert user.last_name == 'User'
        assert user.role == 'marketer'
        
        # Verify repository was called
        mock_user_repository.create.assert_called_once()
        
    def test_create_user_duplicate_email(self, auth_service, mock_user_repository):
        """Test creating user with duplicate email"""
        # Setup - existing user found
        existing_user = Mock(spec=User)
        existing_user.email = 'duplicate@example.com'
        mock_user_repository.find_by_email.return_value = existing_user
        
        # Try to create another user with same email
        result = auth_service.create_user(
            email='duplicate@example.com',
            password='Password456!',
            first_name='Second',
            last_name='User'
        )
        
        assert result.is_failure
        assert "already exists" in result.error

    def test_authenticate_user_success(self, auth_service, mock_user_repository):
        """Test successful authentication"""
        # Setup mock user
        mock_user = Mock(spec=User)
        mock_user.id = 1
        mock_user.email = 'auth@example.com'
        mock_user.is_active = True
        mock_user.password_hash = generate_password_hash('Password123!')
        mock_user.last_login = None
        
        mock_user_repository.find_by_email.return_value = mock_user
        mock_user_repository.update_last_login = Mock()
        mock_user_repository.commit = Mock()
        
        # Authenticate
        with patch('services.auth_service_refactored.check_password_hash', return_value=True):
            result = auth_service.authenticate_user('auth@example.com', 'Password123!')
        
        assert result.is_success
        user = result.data
        assert user is not None
        assert user.email == 'auth@example.com'

    def test_authenticate_user_wrong_password(self, auth_service, mock_user_repository):
        """Test authentication with wrong password"""
        # Setup mock user
        mock_user = Mock(spec=User)
        mock_user.email = 'wrongpass@example.com'
        mock_user.is_active = True
        mock_user.password_hash = generate_password_hash('Password123!')
        
        mock_user_repository.find_by_email.return_value = mock_user
        
        # Try to authenticate with wrong password
        with patch('services.auth_service_refactored.check_password_hash', return_value=False):
            result = auth_service.authenticate_user('wrongpass@example.com', 'WrongPassword!')
        
        assert result.is_failure
        assert "Invalid email or password" in result.error

    def test_authenticate_user_not_found(self, auth_service, mock_user_repository):
        """Test authentication with non-existent user"""
        # Setup - no user found
        mock_user_repository.find_by_email.return_value = None
        
        result = auth_service.authenticate_user('nonexistent@example.com', 'Password123!')
        
        assert result.is_failure
        assert "Invalid email or password" in result.error

    def test_authenticate_user_inactive(self, auth_service, mock_user_repository):
        """Test authentication with inactive user"""
        # Setup mock inactive user
        mock_user = Mock(spec=User)
        mock_user.email = 'inactive@example.com'
        mock_user.is_active = False
        mock_user.password_hash = generate_password_hash('Password123!')
        
        mock_user_repository.find_by_email.return_value = mock_user
        
        # Try to authenticate
        result = auth_service.authenticate_user('inactive@example.com', 'Password123!')
        
        assert result.is_failure
        assert "Account is deactivated" in result.error

    def test_validate_password(self, auth_service):
        """Test password validation"""
        # Valid passwords - returns Result
        result = auth_service.validate_password('Password123!')
        assert result.is_success
        result = auth_service.validate_password('Complex1@Password')
        assert result.is_success
        
        # Invalid passwords
        result = auth_service.validate_password('short')
        assert result.is_failure  # Too short
        result = auth_service.validate_password('nouppercase123!')
        assert result.is_failure  # No uppercase
        result = auth_service.validate_password('NOLOWERCASE123!')
        assert result.is_failure  # No lowercase
        result = auth_service.validate_password('NoNumbers!')
        assert result.is_failure  # No numbers
        result = auth_service.validate_password('NoSpecial123')
        assert result.is_failure  # No special chars

    def test_change_password_success(self, auth_service, mock_user_repository):
        """Test successful password change"""
        # Setup mock user
        mock_user = Mock(spec=User)
        mock_user.id = 1
        mock_user.email = 'changepass@example.com'
        mock_user.password_hash = generate_password_hash('OldPassword123!')
        
        mock_user_repository.get_by_id.return_value = mock_user
        mock_user_repository.update = Mock()
        mock_user_repository.commit = Mock()
        
        # Change password
        with patch('services.auth_service_refactored.check_password_hash', return_value=True):
            with patch('services.auth_service_refactored.generate_password_hash', return_value='new_hash'):
                result = auth_service.change_password(mock_user.id, 'OldPassword123!', 'NewPassword456!')
        
        assert result.is_success
        assert result.data is True

    def test_change_password_wrong_current(self, auth_service, mock_user_repository):
        """Test password change with wrong current password"""
        # Setup mock user
        mock_user = Mock(spec=User)
        mock_user.id = 1
        mock_user.email = 'wrongcurrent@example.com'
        mock_user.password_hash = generate_password_hash('CurrentPassword123!')
        
        mock_user_repository.get_by_id.return_value = mock_user
        
        # Try to change password with wrong current password
        with patch('services.auth_service_refactored.check_password_hash', return_value=False):
            result = auth_service.change_password(mock_user.id, 'WrongPassword123!', 'NewPassword456!')
        
        assert result.is_failure
        assert "Invalid current password" in result.error

    def test_create_invite_success(self, auth_service, mock_user_repository, mock_invite_repository):
        """Test successful invite creation"""
        # Setup admin user
        admin_user = Mock(spec=User)
        admin_user.id = 1
        admin_user.email = 'admin@example.com'
        admin_user.role = 'admin'
        
        # Setup mock invite
        mock_invite = Mock(spec=InviteToken)
        mock_invite.email = 'invitee@example.com'
        mock_invite.role = 'marketer'
        mock_invite.created_by_id = admin_user.id
        mock_invite.token = 'test_token'
        mock_invite.expires_at = datetime.utcnow() + timedelta(days=7)
        
        mock_user_repository.find_by_email.return_value = None  # No existing user
        mock_invite_repository.find_valid_invite_by_email = Mock(return_value=None)
        mock_invite_repository.create.return_value = mock_invite
        mock_invite_repository.commit = Mock()
        
        # Create invite
        result = auth_service.create_invite('invitee@example.com', 'marketer', admin_user.id)
        
        assert result.is_success
        invite = result.data
        assert invite is not None
        assert invite.email == 'invitee@example.com'
        assert invite.role == 'marketer'

    def test_validate_invite_token_valid(self, auth_service, mock_invite_repository):
        """Test validating a valid invite token"""
        # Setup valid invite
        mock_invite = Mock(spec=InviteToken)
        mock_invite.id = 1
        mock_invite.token = 'valid_token'
        mock_invite.email = 'validinvite@example.com'
        mock_invite.expires_at = datetime.utcnow() + timedelta(days=7)
        mock_invite.used = False
        
        mock_invite_repository.find_by_token.return_value = mock_invite
        
        # Validate token
        result = auth_service.validate_invite('valid_token')
        
        assert result.is_success
        validated_invite = result.data
        assert validated_invite is not None
        assert validated_invite.id == mock_invite.id

    def test_validate_invite_token_expired(self, auth_service, mock_invite_repository):
        """Test validating an expired invite token"""
        # Setup expired invite
        mock_invite = Mock(spec=InviteToken)
        mock_invite.token = 'expired_token'
        mock_invite.email = 'expired@example.com'
        mock_invite.expires_at = datetime.utcnow() - timedelta(days=1)  # Expired
        mock_invite.used = False
        
        mock_invite_repository.find_by_token.return_value = mock_invite
        
        # Validate token
        result = auth_service.validate_invite('expired_token')
        
        assert result.is_failure
        assert "expired" in result.error.lower()

    def test_send_invite_email(self, auth_service, mock_email_service):
        """Test sending invite email"""
        # Create mock invite
        invite = Mock(spec=InviteToken)
        invite.email = 'invitee@example.com'
        invite.token = 'test_token'
        invite.role = 'marketer'
        invite.expires_at = datetime.utcnow() + timedelta(days=7)
        
        # Mock email service response
        mock_email_service.send_invite.return_value = None  # Email service doesn't return Result
        
        # Send email
        result = auth_service.send_invite_email(invite, 'http://localhost:5000')
        
        # Assert
        assert result.is_success
        assert result.data is True
        mock_email_service.send_invite.assert_called_once()

    def test_toggle_user_status(self, auth_service, mock_user_repository):
        """Test toggling user status"""
        # Setup mock user - initially active
        mock_user = Mock(spec=User)
        mock_user.id = 1
        mock_user.email = 'toggle@example.com'
        mock_user.is_active = True
        
        updated_user = Mock(spec=User)
        updated_user.id = 1
        updated_user.email = 'toggle@example.com'
        updated_user.is_active = False
        
        mock_user_repository.get_by_id.return_value = mock_user
        mock_user_repository.update_by_id.return_value = updated_user
        mock_user_repository.commit = Mock()
        
        # Toggle status (deactivate)
        result = auth_service.toggle_user_status(mock_user.id)
        
        assert result.is_success
        # Verify repository update was called with correct parameters
        mock_user_repository.update_by_id.assert_called_with(mock_user.id, is_active=False)


class TestAuthServiceAppInit:
    """Test AuthService app initialization"""
    
    @pytest.fixture
    def mock_repositories(self):
        """Create mock repositories for app init tests"""
        return {
            'user_repository': Mock(),
            'invite_repository': Mock()
        }
    
    # Removed obsolete init_app tests - init_app method removed in refactored service


class TestSessionManagement:
    """Test session management"""
    
    @pytest.fixture
    def auth_service_with_repos(self):
        """Create auth service with mocked repositories for session tests"""
        mock_user_repo = Mock()
        mock_invite_repo = Mock()
        mock_email_service = Mock()
        return AuthService(
            email_service=mock_email_service,
            user_repository=mock_user_repo,
            invite_repository=mock_invite_repo
        )
    
    @patch('services.auth_service_refactored.flask_login_user')
    def test_login_user(self, mock_login_user, auth_service_with_repos):
        """Test user session login"""
        mock_user = Mock(spec=User)
        mock_user_dict = {'id': 1, 'email': 'test@example.com'}
        
        # Mock flask_login_user to return True (successful login)
        mock_login_user.return_value = True
        
        result = auth_service_with_repos.login_user(mock_user_dict, remember=True)
        
        mock_login_user.assert_called_once_with(mock_user_dict, remember=True)
        assert result.is_success
    
    @patch('services.auth_service_refactored.flask_logout_user')
    def test_logout_user(self, mock_logout_user, auth_service_with_repos):
        """Test user session logout"""
        result = auth_service_with_repos.logout_user()
        
        mock_logout_user.assert_called_once()
        assert result.is_success