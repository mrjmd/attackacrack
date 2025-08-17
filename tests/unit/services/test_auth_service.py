# tests/test_auth_service.py

import pytest
from unittest.mock import Mock, patch, MagicMock
from services.auth_service import AuthService
from crm_database import User, InviteToken
from datetime import datetime, timedelta
from flask import Flask

class TestAuthService:
    """Test AuthService methods"""

    def test_create_user_success(self, app, db_session):
        """Test successful user creation"""
        # Call the service method
        user, message = AuthService.create_user(
            email='newuser@example.com',
            password='Password123!',
            first_name='New',
            last_name='User',
            role='marketer'
        )

        # Assert
        assert user is not None
        assert user.email == 'newuser@example.com'
        assert user.first_name == 'New'
        assert user.last_name == 'User'
        assert user.role == 'marketer'
        assert message == "User created successfully"
        
        # Verify password was hashed (not stored as plain text)
        assert user.password_hash != 'Password123!'
        
    def test_create_user_duplicate_email(self, app, db_session):
        """Test creating user with duplicate email"""
        # Create first user
        AuthService.create_user(
            email='duplicate@example.com',
            password='Password123!',
            first_name='First',
            last_name='User'
        )
        
        # Try to create another user with same email
        user, message = AuthService.create_user(
            email='duplicate@example.com',
            password='Password456!',
            first_name='Second',
            last_name='User'
        )
        
        assert user is None
        assert "already exists" in message

    def test_authenticate_user_success(self, app, db_session):
        """Test successful authentication"""
        # Create a user
        AuthService.create_user(
            email='auth@example.com',
            password='Password123!',
            first_name='Auth',
            last_name='User'
        )
        
        # Authenticate
        user, message = AuthService.authenticate_user('auth@example.com', 'Password123!')
        
        assert user is not None
        assert user.email == 'auth@example.com'
        assert message == "Authentication successful"
        assert user.last_login is not None

    def test_authenticate_user_wrong_password(self, app, db_session):
        """Test authentication with wrong password"""
        # Create a user
        AuthService.create_user(
            email='wrongpass@example.com',
            password='Password123!',
            first_name='Wrong',
            last_name='Pass'
        )
        
        # Try to authenticate with wrong password
        user, message = AuthService.authenticate_user('wrongpass@example.com', 'WrongPassword!')
        
        assert user is None
        assert message == "Invalid email or password"

    def test_authenticate_user_not_found(self, app, db_session):
        """Test authentication with non-existent user"""
        user, message = AuthService.authenticate_user('nonexistent@example.com', 'Password123!')
        
        assert user is None
        assert message == "Invalid email or password"

    def test_authenticate_user_inactive(self, app, db_session):
        """Test authentication with inactive user"""
        # Create a user
        user, _ = AuthService.create_user(
            email='inactive@example.com',
            password='Password123!',
            first_name='Inactive',
            last_name='User'
        )
        
        # Make user inactive
        user.is_active = False
        db_session.commit()
        
        # Try to authenticate
        user, message = AuthService.authenticate_user('inactive@example.com', 'Password123!')
        
        assert user is None
        assert message == "Account is deactivated"

    def test_validate_password(self):
        """Test password validation"""
        # Valid passwords - returns tuple (is_valid, message)
        is_valid, _ = AuthService.validate_password('Password123!')
        assert is_valid is True
        is_valid, _ = AuthService.validate_password('Complex1@Password')
        assert is_valid is True
        
        # Invalid passwords
        is_valid, _ = AuthService.validate_password('short')
        assert is_valid is False  # Too short
        is_valid, _ = AuthService.validate_password('nouppercase123!')
        assert is_valid is False  # No uppercase
        is_valid, _ = AuthService.validate_password('NOLOWERCASE123!')
        assert is_valid is False  # No lowercase
        is_valid, _ = AuthService.validate_password('NoNumbers!')
        assert is_valid is False  # No numbers
        is_valid, _ = AuthService.validate_password('NoSpecial123')
        assert is_valid is False  # No special chars

    def test_change_password_success(self, app, db_session):
        """Test successful password change"""
        # Create a user
        user, _ = AuthService.create_user(
            email='changepass@example.com',
            password='OldPassword123!',
            first_name='Change',
            last_name='Pass'
        )
        
        # Change password
        success, message = AuthService.change_password(user, 'OldPassword123!', 'NewPassword456!')
        
        assert success is True
        assert message == "Password changed successfully"
        
        # Verify can authenticate with new password
        auth_user, _ = AuthService.authenticate_user('changepass@example.com', 'NewPassword456!')
        assert auth_user is not None

    def test_change_password_wrong_current(self, app, db_session):
        """Test password change with wrong current password"""
        # Create a user
        user, _ = AuthService.create_user(
            email='wrongcurrent@example.com',
            password='CurrentPassword123!',
            first_name='Wrong',
            last_name='Current'
        )
        
        # Try to change password with wrong current password
        success, message = AuthService.change_password(user, 'WrongPassword123!', 'NewPassword456!')
        
        assert success is False
        assert message == "Current password is incorrect"

    def test_create_invite_success(self, app, db_session):
        """Test successful invite creation"""
        # Create admin user
        admin_user, _ = AuthService.create_user(
            email='admin@example.com',
            password='Password123!',
            first_name='Admin',
            last_name='User',
            role='admin'
        )
        
        # Create invite
        invite, message = AuthService.create_invite('invitee@example.com', 'marketer', admin_user)
        
        assert invite is not None
        assert invite.email == 'invitee@example.com'
        assert invite.role == 'marketer'
        assert invite.created_by_id == admin_user.id
        assert message == "Invite created successfully"

    def test_validate_invite_token_valid(self, app, db_session):
        """Test validating a valid invite token"""
        # Create admin user and invite
        admin_user, _ = AuthService.create_user(
            email='admin2@example.com',
            password='Password123!',
            first_name='Admin',
            last_name='User',
            role='admin'
        )
        
        invite, _ = AuthService.create_invite('validinvite@example.com', 'marketer', admin_user)
        
        # Validate token - returns tuple (invite, message)
        validated_invite, message = AuthService.validate_invite_token(invite.token)
        
        assert validated_invite is not None
        assert validated_invite.id == invite.id

    def test_validate_invite_token_expired(self, app, db_session):
        """Test validating an expired invite token"""
        # Create admin user
        admin_user, _ = AuthService.create_user(
            email='admin3@example.com',
            password='Password123!',
            first_name='Admin',
            last_name='User',
            role='admin'
        )
        
        # Create invite with past expiration
        invite = InviteToken(
            email='expired@example.com',
            token='expired_token',
            role='marketer',
            expires_at=datetime.utcnow() - timedelta(days=1),
            created_by_id=admin_user.id
        )
        db_session.add(invite)
        db_session.commit()
        
        # Validate token - returns tuple (invite, message)
        validated_invite, message = AuthService.validate_invite_token('expired_token')
        
        assert validated_invite is None

    @patch('services.auth_service.mail.send')
    def test_send_invite_email(self, mock_send, app):
        """Test sending invite email"""
        # Mock mail configuration
        app.config['MAIL_DEFAULT_SENDER'] = 'noreply@example.com'
        
        # Create mock invite
        invite = Mock()
        invite.email = 'invitee@example.com'
        invite.token = 'test_token'
        invite.role = 'marketer'
        invite.expires_at = datetime.utcnow() + timedelta(days=7)
        
        # Send email
        success, message = AuthService.send_invite_email(invite, 'http://localhost:5000')
        
        # Assert
        assert success is True
        assert message == "Invite email sent successfully"
        mock_send.assert_called_once()

    def test_toggle_user_status(self, app, db_session):
        """Test toggling user status"""
        # Create a user
        user, _ = AuthService.create_user(
            email='toggle@example.com',
            password='Password123!',
            first_name='Toggle',
            last_name='User'
        )
        
        # User should be active by default
        assert user.is_active is True
        
        # Toggle status
        success, message = AuthService.toggle_user_status(user.id)
        
        assert success is True
        assert "deactivated" in message
        
        # Refresh user from database
        db_session.refresh(user)
        assert user.is_active is False
        
        # Toggle again
        success, message = AuthService.toggle_user_status(user.id)
        
        assert success is True
        assert "activated" in message
        
        # Refresh user from database
        db_session.refresh(user)
        assert user.is_active is True


class TestAuthServiceAppInit:
    """Test AuthService app initialization"""
    
    @patch('services.auth_service.mail')
    def test_init_app_with_mail(self, mock_mail):
        """Test app initialization with mail configured"""
        app = Flask(__name__)
        app.config['MAIL_SERVER'] = 'smtp.example.com'
        
        AuthService.init_app(app)
        
        mock_mail.init_app.assert_called_once_with(app)
    
    @patch('services.auth_service.mail')
    def test_init_app_without_mail(self, mock_mail):
        """Test app initialization without mail configured"""
        app = Flask(__name__)
        # No MAIL_SERVER in config
        
        AuthService.init_app(app)
        
        mock_mail.init_app.assert_not_called()


class TestSessionManagement:
    """Test session management"""
    
    @patch('services.auth_service.login_user')
    def test_login_user_session(self, mock_login_user):
        """Test user session login"""
        mock_user = Mock()
        
        result = AuthService.login_user_session(mock_user, remember=True)
        
        mock_login_user.assert_called_once_with(mock_user, remember=True)
        assert result == mock_login_user.return_value
    
    @patch('services.auth_service.logout_user')
    def test_logout_user_session(self, mock_logout_user):
        """Test user session logout"""
        AuthService.logout_user_session()
        
        mock_logout_user.assert_called_once()