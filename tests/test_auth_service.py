# tests/test_auth_service.py
"""
Comprehensive tests for AuthService covering user management, authentication,
and invite flow functionality.
"""

import pytest
from unittest.mock import MagicMock, patch, Mock
from datetime import datetime, timedelta
from services.auth_service import AuthService
from crm_database import User, InviteToken
from flask import Flask
from flask_bcrypt import Bcrypt


@pytest.fixture
def auth_service():
    """Fixture to provide AuthService instance"""
    return AuthService()


@pytest.fixture
def mock_user(db_session):
    """Fixture providing a test user"""
    from flask_bcrypt import generate_password_hash
    import time
    unique_id = str(int(time.time() * 1000000))[-6:]
    user = User(
        email=f'existing{unique_id}@example.com',
        password_hash=generate_password_hash('ValidPass123!').decode('utf-8'),
        first_name='Existing',
        last_name='User',
        role='admin',
        is_active=True
    )
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture
def mock_invite(db_session, mock_user):
    """Fixture providing a test invite token"""
    import time
    unique_id = str(int(time.time() * 1000000))[-6:]
    invite = InviteToken(
        email=f'newuser{unique_id}@example.com',
        token=f'test_token_{unique_id}',
        role='marketer',
        expires_at=datetime.utcnow() + timedelta(days=7),
        created_by_id=mock_user.id,
        used=False
    )
    db_session.add(invite)
    db_session.commit()
    return invite


class TestPasswordValidation:
    """Test password validation functionality"""
    
    def test_validate_password_success(self):
        """Test password validation with valid password"""
        is_valid, message = AuthService.validate_password('ValidPass123!')
        assert is_valid is True
        assert message == "Password is valid"
    
    def test_validate_password_too_short(self):
        """Test password validation with too short password"""
        is_valid, message = AuthService.validate_password('Pass1!')
        assert is_valid is False
        assert "at least 8 characters" in message
    
    def test_validate_password_no_uppercase(self):
        """Test password validation without uppercase"""
        is_valid, message = AuthService.validate_password('validpass123!')
        assert is_valid is False
        assert "uppercase letter" in message
    
    def test_validate_password_no_lowercase(self):
        """Test password validation without lowercase"""
        is_valid, message = AuthService.validate_password('VALIDPASS123!')
        assert is_valid is False
        assert "lowercase letter" in message
    
    def test_validate_password_no_number(self):
        """Test password validation without number"""
        is_valid, message = AuthService.validate_password('ValidPass!')
        assert is_valid is False
        assert "one number" in message
    
    def test_validate_password_no_special_char(self):
        """Test password validation without special character"""
        is_valid, message = AuthService.validate_password('ValidPass123')
        assert is_valid is False
        assert "special character" in message


class TestUserCreation:
    """Test user creation functionality"""
    
    def test_create_user_success(self, db_session):
        """Test successful user creation"""
        user, message = AuthService.create_user(
            email='newuser@example.com',
            password='ValidPass123!',
            first_name='New',
            last_name='User',
            role='marketer'
        )
        
        assert user is not None
        assert user.email == 'newuser@example.com'
        assert user.first_name == 'New'
        assert user.last_name == 'User'
        assert user.role == 'marketer'
        assert message == "User created successfully"
    
    def test_create_user_invalid_password(self, db_session):
        """Test user creation with invalid password"""
        user, message = AuthService.create_user(
            email='newuser@example.com',
            password='weak',
            first_name='New',
            last_name='User'
        )
        
        assert user is None
        assert "at least 8 characters" in message
    
    def test_create_user_duplicate_email(self, db_session, mock_user):
        """Test user creation with existing email"""
        user, message = AuthService.create_user(
            email=mock_user.email,
            password='ValidPass123!',
            first_name='Another',
            last_name='User'
        )
        
        assert user is None
        assert "already exists" in message


class TestAuthentication:
    """Test authentication functionality"""
    
    def test_authenticate_user_success(self, db_session, mock_user):
        """Test successful authentication"""
        user, message = AuthService.authenticate_user(
            email=mock_user.email,
            password='ValidPass123!'
        )
        
        assert user is not None
        assert user.id == mock_user.id
        assert message == "Authentication successful"
        assert user.last_login is not None
    
    def test_authenticate_user_wrong_password(self, db_session, mock_user):
        """Test authentication with wrong password"""
        user, message = AuthService.authenticate_user(
            email=mock_user.email,
            password='WrongPass123!'
        )
        
        assert user is None
        assert message == "Invalid email or password"
    
    def test_authenticate_user_nonexistent(self, db_session):
        """Test authentication with non-existent user"""
        user, message = AuthService.authenticate_user(
            email='nonexistent@example.com',
            password='ValidPass123!'
        )
        
        assert user is None
        assert message == "Invalid email or password"
    
    def test_authenticate_user_inactive(self, db_session, mock_user):
        """Test authentication with inactive user"""
        mock_user.is_active = False
        db_session.commit()
        
        user, message = AuthService.authenticate_user(
            email=mock_user.email,
            password='ValidPass123!'
        )
        
        assert user is None
        assert message == "Account is deactivated"


class TestInviteFlow:
    """Test invite token functionality"""
    
    def test_generate_invite_token(self):
        """Test invite token generation"""
        token = AuthService.generate_invite_token()
        assert len(token) == 32
        assert token.isalnum()
    
    def test_create_invite_success(self, db_session, mock_user):
        """Test successful invite creation"""
        invite, message = AuthService.create_invite(
            email='invited@example.com',
            role='marketer',
            created_by_user=mock_user
        )
        
        assert invite is not None
        assert invite.email == 'invited@example.com'
        assert invite.role == 'marketer'
        assert invite.created_by_id == mock_user.id
        assert invite.used is False
        assert len(invite.token) == 32
        assert message == "Invite created successfully"
    
    def test_create_invite_existing_user(self, db_session, mock_user):
        """Test invite creation for existing user"""
        invite, message = AuthService.create_invite(
            email=mock_user.email,
            role='marketer',
            created_by_user=mock_user
        )
        
        assert invite is None
        assert "already exists" in message
    
    def test_create_invite_existing_unused(self, db_session, mock_user, mock_invite):
        """Test invite creation when unused invite exists"""
        invite, message = AuthService.create_invite(
            email=mock_invite.email,  # Use the same email as the existing invite
            role='admin',
            created_by_user=mock_user
        )
        
        assert invite is not None
        assert invite.id == mock_invite.id
        assert "Invite already sent to this email" == message
    
    def test_validate_invite_token_success(self, db_session, mock_invite):
        """Test successful invite token validation"""
        invite, message = AuthService.validate_invite_token(mock_invite.token)
        
        assert invite is not None
        assert invite.id == mock_invite.id
        assert message == "Valid invitation"
    
    def test_validate_invite_token_invalid(self, db_session):
        """Test invalid invite token validation"""
        invite, message = AuthService.validate_invite_token('invalid_token')
        
        assert invite is None
        assert message == "Invalid invitation token"
    
    def test_validate_invite_token_used(self, db_session, mock_invite):
        """Test validation of used invite token"""
        mock_invite.used = True
        db_session.commit()
        
        invite, message = AuthService.validate_invite_token(mock_invite.token)
        
        assert invite is None
        assert message == "This invitation has already been used"
    
    def test_validate_invite_token_expired(self, db_session, mock_invite):
        """Test validation of expired invite token"""
        mock_invite.expires_at = datetime.utcnow() - timedelta(days=1)
        db_session.commit()
        
        invite, message = AuthService.validate_invite_token(mock_invite.token)
        
        assert invite is None
        assert message == "This invitation has expired"
    
    def test_use_invite_token_success(self, db_session, mock_invite):
        """Test successful invite token usage"""
        user, message = AuthService.use_invite_token(
            token=mock_invite.token,
            password='ValidPass123!',
            first_name='New',
            last_name='User'
        )
        
        assert user is not None
        assert user.email == mock_invite.email
        assert user.role == 'marketer'
        assert message == "Account created successfully"
        
        # Verify invite is marked as used
        db_session.refresh(mock_invite)
        assert mock_invite.used is True
        assert mock_invite.used_at is not None
    
    def test_use_invite_token_invalid(self, db_session):
        """Test using invalid invite token"""
        user, message = AuthService.use_invite_token(
            token='invalid_token',
            password='ValidPass123!',
            first_name='New',
            last_name='User'
        )
        
        assert user is None
        assert message == "Invalid invitation token"
    
    def test_use_invite_token_weak_password(self, db_session, mock_invite):
        """Test using invite with weak password"""
        user, message = AuthService.use_invite_token(
            token=mock_invite.token,
            password='weak',
            first_name='New',
            last_name='User'
        )
        
        assert user is None
        assert "at least 8 characters" in message


class TestEmailInvites:
    """Test email invite functionality"""
    
    @patch('services.auth_service.mail')
    def test_send_invite_email_success(self, mock_mail, mock_invite):
        """Test successful invite email sending"""
        mock_mail.send = MagicMock()
        
        success, message = AuthService.send_invite_email(
            mock_invite,
            'https://example.com'
        )
        
        assert success is True
        assert message == "Invite email sent successfully"
        mock_mail.send.assert_called_once()
    
    @patch('services.auth_service.mail')
    def test_send_invite_email_failure(self, mock_mail, mock_invite):
        """Test invite email sending failure"""
        mock_mail.send = MagicMock(side_effect=Exception("SMTP error"))
        
        success, message = AuthService.send_invite_email(
            mock_invite,
            'https://example.com'
        )
        
        assert success is False
        assert "Failed to send email" in message
        assert "SMTP error" in message
    
    def test_send_invite_email_no_mail_service(self, mock_invite):
        """Test invite email when mail service not configured"""
        with patch('services.auth_service.mail', None):
            success, message = AuthService.send_invite_email(
                mock_invite,
                'https://example.com'
            )
            
            assert success is False
            assert message == "Email service not configured"


class TestPasswordManagement:
    """Test password change functionality"""
    
    def test_change_password_success(self, db_session, mock_user):
        """Test successful password change"""
        success, message = AuthService.change_password(
            mock_user,
            current_password='ValidPass123!',
            new_password='NewValidPass456!'
        )
        
        assert success is True
        assert message == "Password changed successfully"
        
        # Verify new password works
        user, _ = AuthService.authenticate_user(
            email=mock_user.email,
            password='NewValidPass456!'
        )
        assert user is not None
    
    def test_change_password_wrong_current(self, db_session, mock_user):
        """Test password change with wrong current password"""
        success, message = AuthService.change_password(
            mock_user,
            current_password='WrongPass123!',
            new_password='NewValidPass456!'
        )
        
        assert success is False
        assert message == "Current password is incorrect"
    
    def test_change_password_weak_new(self, db_session, mock_user):
        """Test password change with weak new password"""
        success, message = AuthService.change_password(
            mock_user,
            current_password='ValidPass123!',
            new_password='weak'
        )
        
        assert success is False
        assert "at least 8 characters" in message


class TestUserManagement:
    """Test user management functionality"""
    
    def test_toggle_user_status_activate(self, db_session, mock_user):
        """Test activating a deactivated user"""
        mock_user.is_active = False
        db_session.commit()
        
        success, message = AuthService.toggle_user_status(mock_user.id)
        
        assert success is True
        assert "activated successfully" in message
        db_session.refresh(mock_user)
        assert mock_user.is_active is True
    
    def test_toggle_user_status_deactivate(self, db_session, mock_user):
        """Test deactivating an active user"""
        success, message = AuthService.toggle_user_status(mock_user.id)
        
        assert success is True
        assert "deactivated successfully" in message
        db_session.refresh(mock_user)
        assert mock_user.is_active is False
    
    def test_toggle_user_status_not_found(self, db_session):
        """Test toggling status of non-existent user"""
        success, message = AuthService.toggle_user_status(99999)
        
        assert success is False
        assert message == "User not found"


class TestAppInitialization:
    """Test app initialization"""
    
    @patch('services.auth_service.bcrypt')
    @patch('services.auth_service.login_manager')
    @patch('services.auth_service.mail')
    def test_init_app_with_mail(self, mock_mail, mock_login_manager, mock_bcrypt):
        """Test app initialization with mail configured"""
        app = Flask(__name__)
        app.config['MAIL_SERVER'] = 'smtp.example.com'
        
        AuthService.init_app(app)
        
        mock_bcrypt.init_app.assert_called_once_with(app)
        mock_login_manager.init_app.assert_called_once_with(app)
        mock_mail.init_app.assert_called_once_with(app)
        assert mock_login_manager.login_view == 'auth.login'
        assert mock_login_manager.login_message == 'Please log in to access this page.'
    
    @patch('services.auth_service.bcrypt')
    @patch('services.auth_service.login_manager')
    @patch('services.auth_service.mail')
    def test_init_app_without_mail(self, mock_mail, mock_login_manager, mock_bcrypt):
        """Test app initialization without mail configured"""
        app = Flask(__name__)
        # No MAIL_SERVER in config
        
        AuthService.init_app(app)
        
        mock_bcrypt.init_app.assert_called_once_with(app)
        mock_login_manager.init_app.assert_called_once_with(app)
        mock_mail.init_app.assert_not_called()


class TestSessionManagement:
    """Test session management"""
    
    @patch('services.auth_service.login_user')
    def test_login_user_session(self, mock_login_user, mock_user):
        """Test user session login"""
        result = AuthService.login_user_session(mock_user, remember=True)
        
        mock_login_user.assert_called_once_with(mock_user, remember=True)
    
    @patch('services.auth_service.logout_user')
    def test_logout_user_session(self, mock_logout_user):
        """Test user session logout"""
        AuthService.logout_user_session()
        
        mock_logout_user.assert_called_once()
    
    def test_load_user(self, db_session, mock_user):
        """Test user loader for Flask-Login"""
        loaded_user = AuthService.load_user(str(mock_user.id))
        
        assert loaded_user is not None
        assert loaded_user.id == mock_user.id
    
    def test_load_user_not_found(self, db_session):
        """Test user loader with non-existent user"""
        loaded_user = AuthService.load_user('99999')
        
        assert loaded_user is None