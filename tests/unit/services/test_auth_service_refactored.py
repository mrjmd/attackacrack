"""
Tests for refactored AuthService with Result Pattern
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash

from services.auth_service_refactored import AuthService
from services.common.result import Result, PagedResult
from crm_database import User, InviteToken


class TestAuthServiceRefactored:
    """Test suite for refactored AuthService"""
    
    @pytest.fixture
    def mock_session(self):
        """Mock database session"""
        session = Mock()
        session.add = Mock()
        session.commit = Mock()
        session.rollback = Mock()
        session.delete = Mock()
        return session
    
    @pytest.fixture
    def mock_email_service(self):
        """Mock email service"""
        service = Mock()
        service.send_invite = Mock()
        return service
    
    @pytest.fixture
    def auth_service(self, mock_session, mock_email_service):
        """Create AuthService with mocked dependencies"""
        return AuthService(
            email_service=mock_email_service,
            session=mock_session
        )
    
    def test_validate_password_success(self, auth_service):
        """Test successful password validation"""
        result = auth_service.validate_password("StrongP@ss123")
        
        assert result.is_success == True
        assert result.data == "Password is valid"
    
    def test_validate_password_too_short(self, auth_service):
        """Test password validation - too short"""
        result = auth_service.validate_password("Short1!")
        
        assert result.is_failure == True
        assert result.error == "Password must be at least 8 characters long"
        assert result.error_code == "PASSWORD_TOO_SHORT"
    
    def test_validate_password_no_uppercase(self, auth_service):
        """Test password validation - no uppercase"""
        result = auth_service.validate_password("weakpass123!")
        
        assert result.is_failure == True
        assert result.error_code == "PASSWORD_NO_UPPERCASE"
    
    def test_validate_password_no_special(self, auth_service):
        """Test password validation - no special character"""
        result = auth_service.validate_password("WeakPass123")
        
        assert result.is_failure == True
        assert result.error_code == "PASSWORD_NO_SPECIAL"
    
    @patch('services.auth_service_refactored.User')
    def test_create_user_success(self, mock_user_class, auth_service, mock_session):
        """Test successful user creation"""
        # Setup
        mock_user_class.query.filter_by.return_value.first.return_value = None
        
        # Act
        result = auth_service.create_user(
            email="test@example.com",
            password="StrongP@ss123",
            first_name="Test",
            last_name="User",
            role="user"
        )
        
        # Assert
        assert result.is_success == True
        assert mock_session.add.called
        assert mock_session.commit.called
    
    @patch('services.auth_service_refactored.User')
    def test_create_user_already_exists(self, mock_user_class, auth_service):
        """Test user creation when user already exists"""
        # Setup
        existing_user = Mock()
        mock_user_class.query.filter_by.return_value.first.return_value = existing_user
        
        # Act
        result = auth_service.create_user(
            email="test@example.com",
            password="StrongP@ss123",
            name="Test User"
        )
        
        # Assert
        assert result.is_failure == True
        assert result.error == "User with this email already exists"
        assert result.error_code == "USER_EXISTS"
    
    @patch('services.auth_service_refactored.User')
    @patch('services.auth_service_refactored.check_password_hash')
    def test_authenticate_user_success(self, mock_check_password, mock_user_class, 
                                      auth_service, mock_session):
        """Test successful user authentication"""
        # Setup
        mock_user = Mock()
        mock_user.is_active = True
        mock_user.password_hash = "hashed"
        mock_user_class.query.filter_by.return_value.first.return_value = mock_user
        mock_check_password.return_value = True
        
        # Act
        result = auth_service.authenticate_user("test@example.com", "password")
        
        # Assert
        assert result.is_success == True
        assert result.data == mock_user
        assert mock_user.last_login is not None
        assert mock_session.commit.called
    
    @patch('services.auth_service_refactored.User')
    def test_authenticate_user_invalid_email(self, mock_user_class, auth_service):
        """Test authentication with invalid email"""
        # Setup
        mock_user_class.query.filter_by.return_value.first.return_value = None
        
        # Act
        result = auth_service.authenticate_user("invalid@example.com", "password")
        
        # Assert
        assert result.is_failure == True
        assert result.error_code == "INVALID_CREDENTIALS"
    
    @patch('services.auth_service_refactored.User')
    def test_authenticate_user_deactivated(self, mock_user_class, auth_service):
        """Test authentication with deactivated account"""
        # Setup
        mock_user = Mock()
        mock_user.is_active = False
        mock_user_class.query.filter_by.return_value.first.return_value = mock_user
        
        # Act
        result = auth_service.authenticate_user("test@example.com", "password")
        
        # Assert
        assert result.is_failure == True
        assert result.error_code == "ACCOUNT_DEACTIVATED"
    
    @patch('services.auth_service_refactored.flask_login_user')
    def test_login_user_success(self, mock_flask_login, auth_service):
        """Test successful user login"""
        # Setup
        mock_user = Mock()
        mock_flask_login.return_value = True
        
        # Act
        result = auth_service.login_user(mock_user, remember=True)
        
        # Assert
        assert result.is_success == True
        assert result.data == True
        mock_flask_login.assert_called_once_with(mock_user, remember=True)
    
    @patch('services.auth_service_refactored.flask_logout_user')
    def test_logout_user(self, mock_flask_logout, auth_service):
        """Test user logout"""
        # Act
        result = auth_service.logout_user()
        
        # Assert
        assert result.is_success == True
        mock_flask_logout.assert_called_once()
    
    @patch('services.auth_service_refactored.User')
    def test_get_user_by_id_found(self, mock_user_class, auth_service):
        """Test getting user by ID - found"""
        # Setup
        mock_user = Mock()
        mock_user_class.query.get.return_value = mock_user
        
        # Act
        result = auth_service.get_user_by_id(1)
        
        # Assert
        assert result.is_success == True
        assert result.data == mock_user
    
    @patch('services.auth_service_refactored.User')
    def test_get_user_by_id_not_found(self, mock_user_class, auth_service):
        """Test getting user by ID - not found"""
        # Setup
        mock_user_class.query.get.return_value = None
        
        # Act
        result = auth_service.get_user_by_id(999)
        
        # Assert
        assert result.is_failure == True
        assert result.error_code == "USER_NOT_FOUND"
    
    @patch('services.auth_service_refactored.User')
    def test_get_all_users_paginated(self, mock_user_class, auth_service):
        """Test getting all users with pagination"""
        # Setup
        mock_paginated = Mock()
        mock_paginated.items = [Mock(), Mock()]
        mock_paginated.total = 10
        mock_user_class.query.paginate.return_value = mock_paginated
        
        # Act
        result = auth_service.get_all_users(page=1, per_page=2)
        
        # Assert
        assert result.is_success == True
        assert len(result.data) == 2
        assert result.total == 10
        assert result.page == 1
        assert result.per_page == 2
    
    @patch('services.auth_service_refactored.InviteToken')
    @patch('services.auth_service_refactored.User')
    def test_create_invite_success(self, mock_user_class, mock_invite_class, 
                                  auth_service, mock_session):
        """Test successful invite creation"""
        # Setup
        mock_user_class.query.filter_by.return_value.first.return_value = None
        mock_invite_class.query.filter_by.return_value.first.return_value = None
        
        # Act
        result = auth_service.create_invite("new@example.com", "user", 1)
        
        # Assert
        assert result.is_success == True
        assert mock_session.add.called
        assert mock_session.commit.called
    
    @patch('services.auth_service_refactored.User')
    def test_create_invite_user_exists(self, mock_user_class, auth_service):
        """Test invite creation when user already exists"""
        # Setup
        existing_user = Mock()
        mock_user_class.query.filter_by.return_value.first.return_value = existing_user
        
        # Act
        result = auth_service.create_invite("existing@example.com", "user")
        
        # Assert
        assert result.is_failure == True
        assert result.error_code == "USER_EXISTS"
    
    def test_send_invite_email_success(self, auth_service, mock_email_service):
        """Test successful invite email sending"""
        # Setup
        mock_invite = Mock()
        mock_invite.token = "test_token"
        mock_invite.email = "test@example.com"
        mock_invite.role = "user"
        
        # Act
        result = auth_service.send_invite_email(mock_invite, "http://example.com")
        
        # Assert
        assert result.is_success == True
        mock_email_service.send_invite.assert_called_once()
    
    def test_send_invite_email_no_service(self, mock_session):
        """Test invite email when email service not configured"""
        # Setup
        auth_service = AuthService(email_service=None, session=mock_session)
        mock_invite = Mock()
        
        # Act
        result = auth_service.send_invite_email(mock_invite, "http://example.com")
        
        # Assert
        assert result.is_failure == True
        assert result.error_code == "EMAIL_NOT_CONFIGURED"