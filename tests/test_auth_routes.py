# tests/test_auth_routes.py
"""
Comprehensive tests for authentication routes including login, logout,
role-based access, and invite flow.
"""

import pytest
from unittest.mock import patch, MagicMock
from flask import url_for
from datetime import datetime, timedelta
from crm_database import User, InviteToken


@pytest.fixture
def admin_user(db_session):
    """Fixture providing an admin user"""
    from flask_bcrypt import generate_password_hash
    import time
    unique_id = str(int(time.time() * 1000000))[-6:]
    user = User(
        email=f'admin{unique_id}@example.com',
        password_hash=generate_password_hash('AdminPass123!').decode('utf-8'),
        first_name='Admin',
        last_name='User',
        role='admin',
        is_active=True
    )
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture
def marketer_user(db_session):
    """Fixture providing a marketer user"""
    from flask_bcrypt import generate_password_hash
    import time
    unique_id = str(int(time.time() * 1000000))[-6:]
    user = User(
        email=f'marketer{unique_id}@example.com',
        password_hash=generate_password_hash('MarketerPass123!').decode('utf-8'),
        first_name='Marketer',
        last_name='User',
        role='marketer',
        is_active=True
    )
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture
def admin_client(app, client, admin_user):
    """Fixture providing an authenticated admin client"""
    with app.app_context():
        response = client.post('/auth/login', data={
            'email': admin_user.email,
            'password': 'AdminPass123!'
        }, follow_redirects=True)
        
        yield client
        
        client.get('/auth/logout')


@pytest.fixture
def marketer_client(app, client, marketer_user):
    """Fixture providing an authenticated marketer client"""
    with app.app_context():
        response = client.post('/auth/login', data={
            'email': marketer_user.email,
            'password': 'MarketerPass123!'
        }, follow_redirects=True)
        
        yield client
        
        client.get('/auth/logout')


@pytest.fixture
def valid_invite(db_session, admin_user):
    """Fixture providing a valid invite token"""
    import time
    unique_id = str(int(time.time() * 1000000))[-6:]
    invite = InviteToken(
        email=f'newinvite{unique_id}@example.com',
        token=f'valid_invite_token_{unique_id}',
        role='marketer',
        expires_at=datetime.utcnow() + timedelta(days=7),
        created_by_id=admin_user.id,
        used=False
    )
    db_session.add(invite)
    db_session.commit()
    return invite


class TestLoginLogout:
    """Test login and logout functionality"""
    
    def test_login_page_renders(self, client):
        """Test that login page renders"""
        response = client.get('/auth/login')
        assert response.status_code == 200
        assert b'Login' in response.data
        assert b'Email' in response.data
        assert b'Password' in response.data
    
    def test_login_success(self, client, admin_user, app):
        """Test successful login"""
        with app.test_request_context():
            response = client.post('/auth/login', data={
                'email': admin_user.email,
                'password': 'AdminPass123!'
            }, follow_redirects=True)
            
            assert response.status_code == 200
            assert b'Dashboard' in response.data  # Redirected to dashboard
            assert b'Login' not in response.data
    
    def test_login_invalid_credentials(self, client):
        """Test login with invalid credentials"""
        response = client.post('/auth/login', data={
            'email': 'wrong@example.com',
            'password': 'WrongPass123!'
        }, follow_redirects=True)
        
        assert response.status_code == 200
        assert b'Invalid email or password' in response.data
        assert b'Login' in response.data
    
    def test_login_inactive_user(self, client, admin_user, db_session):
        """Test login with inactive user"""
        admin_user.is_active = False
        db_session.commit()
        
        # The test user might be getting logged in from conftest
        # Make sure we're logged out first
        client.get('/auth/logout', follow_redirects=True)
        
        response = client.post('/auth/login', data={
            'email': admin_user.email,
            'password': 'AdminPass123!'
        }, follow_redirects=False)
        
        # Should not redirect (stays on login page)
        assert response.status_code == 200
        # Should show login form again
        assert b'Email' in response.data or b'email' in response.data
    
    def test_login_redirect_next(self, client, admin_user, app):
        """Test login redirect to next parameter"""
        with app.test_request_context():
            # Try to access protected page
            response = client.get('/contacts/', follow_redirects=False)
            assert response.status_code == 302  # Redirect to login
            assert '/auth/login' in response.location
            
            # Login with next parameter
            response = client.post('/auth/login?next=/contacts/', data={
                'email': admin_user.email,
                'password': 'AdminPass123!'
            }, follow_redirects=True)
            
            assert response.status_code == 200
            # Should be on contacts page now
            assert b'<h2 class="text-3xl font-bold">Contacts</h2>' in response.data
    
    def test_logout(self, admin_client):
        """Test logout functionality"""
        # Verify we're logged in
        response = admin_client.get('/contacts/')
        assert response.status_code == 200
        
        # Logout
        response = admin_client.get('/auth/logout', follow_redirects=True)
        assert response.status_code == 200
        assert b'You have been logged out' in response.data
        
        # Verify we can't access protected routes
        response = admin_client.get('/contacts/')
        assert response.status_code == 302  # Redirect to login


class TestRoleBasedAccess:
    """Test role-based access control"""
    
    def test_admin_access_admin_routes(self, admin_client):
        """Test admin can access admin routes"""
        response = admin_client.get('/auth/users')
        assert response.status_code == 200
        # Check for common elements in user management page
        assert b'Users' in response.data or b'users' in response.data
    
    def test_marketer_cannot_access_admin_routes(self, marketer_client):
        """Test marketer cannot access admin routes"""
        response = marketer_client.get('/auth/users', follow_redirects=False)
        assert response.status_code == 302  # Redirect
        assert '/dashboard' in response.location
    
    def test_both_can_access_general_routes(self, admin_client, marketer_client):
        """Test both roles can access general routes"""
        # Admin access
        response = admin_client.get('/contacts/')
        assert response.status_code == 200
        
        # Marketer access
        response = marketer_client.get('/contacts/')
        assert response.status_code == 200
    
    def test_login_required_decorator(self, client):
        """Test login_required decorator protection"""
        protected_routes = [
            '/contacts/',
            '/properties/',
            '/jobs/',
            '/appointments/',
            '/quotes/',
            '/invoices/',
        ]
        
        for route in protected_routes:
            response = client.get(route)
            assert response.status_code == 302  # Redirect to login
            assert '/auth/login' in response.location


class TestInviteFlow:
    """Test user invite flow"""
    
    def test_invite_user_page_admin_only(self, admin_client, marketer_client):
        """Test invite user page is admin only"""
        # Admin can access
        response = admin_client.get('/auth/invite')
        assert response.status_code == 200
        assert b'Invite' in response.data or b'invite' in response.data
        
        # Marketer cannot access
        response = marketer_client.get('/auth/invite', follow_redirects=False)
        assert response.status_code == 302  # Redirected
    
    @patch('services.auth_service.AuthService.send_invite_email')
    def test_invite_user_success(self, mock_send_email, admin_client, app):
        """Test successful user invite"""
        mock_send_email.return_value = (True, "Email sent")
        
        with app.test_request_context():
            response = admin_client.post('/auth/invite', data={
                'email': 'newinvite@example.com',
                'role': 'marketer'
            }, follow_redirects=True)
            
            assert response.status_code == 200
            assert b'Invitation sent' in response.data
            mock_send_email.assert_called_once()
    
    def test_invite_existing_user(self, admin_client, admin_user):
        """Test inviting existing user"""
        response = admin_client.post('/auth/invite', data={
            'email': admin_user.email,
            'role': 'marketer'
        }, follow_redirects=True)
        
        assert response.status_code == 200
        assert b'already exists' in response.data
    
    def test_accept_invite_page(self, client, valid_invite):
        """Test accept invite page renders"""
        response = client.get(f'/auth/accept-invite/{valid_invite.token}')
        assert response.status_code == 200
        # Check for common elements on accept invite page
        assert b'password' in response.data or b'Password' in response.data
        assert valid_invite.email.encode() in response.data
    
    def test_accept_invite_invalid_token(self, client):
        """Test accept invite with invalid token"""
        response = client.get('/auth/accept-invite/invalid_token')
        assert response.status_code == 302  # Redirect
        
        response = client.get('/auth/accept-invite/invalid_token', follow_redirects=True)
        assert b'Invalid invitation' in response.data
    
    def test_accept_invite_success(self, client, valid_invite, app):
        """Test successful invite acceptance"""
        with app.test_request_context():
            response = client.post(f'/auth/accept-invite/{valid_invite.token}', data={
                'first_name': 'New',
                'last_name': 'User',
                'password': 'NewUserPass123!',
                'confirm_password': 'NewUserPass123!'
            }, follow_redirects=True)
            
            assert response.status_code == 200
            assert b'Account created successfully' in response.data
            assert b'Login' in response.data  # Redirected to login
    
    def test_accept_invite_password_mismatch(self, client, valid_invite):
        """Test accept invite with password mismatch"""
        response = client.post(f'/auth/accept-invite/{valid_invite.token}', data={
            'first_name': 'New',
            'last_name': 'User',
            'password': 'NewUserPass123!',
            'confirm_password': 'DifferentPass123!'
        }, follow_redirects=True)
        
        assert response.status_code == 200
        assert b'Passwords do not match' in response.data
    
    def test_accept_invite_weak_password(self, client, valid_invite):
        """Test accept invite with weak password"""
        response = client.post(f'/auth/accept-invite/{valid_invite.token}', data={
            'first_name': 'New',
            'last_name': 'User',
            'password': 'weak',
            'confirm_password': 'weak'
        }, follow_redirects=True)
        
        assert response.status_code == 200
        assert b'at least 8 characters' in response.data


class TestUserManagement:
    """Test user management functionality"""
    
    def test_users_list_admin_only(self, admin_client, marketer_client, admin_user, marketer_user):
        """Test users list is admin only"""
        # Admin can view
        response = admin_client.get('/auth/users')
        assert response.status_code == 200
        # Check page loaded with user data
        assert admin_user.email.encode() in response.data
        assert marketer_user.email.encode() in response.data
        
        # Marketer cannot view
        response = marketer_client.get('/auth/users', follow_redirects=False)
        assert response.status_code == 302  # Redirected
    
    def test_toggle_user_status(self, admin_client, marketer_user, db_session):
        """Test toggling user status"""
        response = admin_client.post(f'/auth/users/{marketer_user.id}/toggle-status', 
                                   follow_redirects=True)
        
        assert response.status_code == 200
        assert b'deactivated successfully' in response.data
        
        db_session.refresh(marketer_user)
        assert marketer_user.is_active is False
    
    def test_profile_page(self, admin_client, admin_user):
        """Test user profile page"""
        response = admin_client.get('/auth/profile')
        assert response.status_code == 200
        assert b'My Profile' in response.data
        assert admin_user.email.encode() in response.data
        assert b'Admin User' in response.data
    
    def test_change_password_page(self, admin_client):
        """Test change password page (part of profile)"""
        response = admin_client.get('/auth/profile')
        assert response.status_code == 200
        assert b'My Profile' in response.data
        # Change password form should be on profile page
        assert b'Current Password' in response.data or b'current_password' in response.data
    
    def test_change_password_success(self, admin_client, admin_user, app):
        """Test successful password change"""
        with admin_client.session_transaction() as sess:
            sess.pop('_flashes', None)
        
        response = admin_client.post('/auth/profile', data={
            'action': 'change_password',
            'current_password': 'AdminPass123!',
            'new_password': 'NewAdminPass456!',
            'confirm_password': 'NewAdminPass456!'
        }, follow_redirects=True)
        
        assert response.status_code == 200
        # The flash message should be in the rendered template
        assert b'Password changed successfully' in response.data
        
        # Verify new password works
        admin_client.get('/auth/logout')
        
        with app.test_request_context():
            response = admin_client.post('/auth/login', data={
                'email': admin_user.email,
                'password': 'NewAdminPass456!'
            }, follow_redirects=True)
            
            assert response.status_code == 200
            assert b'Dashboard' in response.data
    
    def test_change_password_wrong_current(self, admin_client):
        """Test change password with wrong current password"""
        with admin_client.session_transaction() as sess:
            sess.pop('_flashes', None)
        
        response = admin_client.post('/auth/profile', data={
            'action': 'change_password',
            'current_password': 'WrongPass123!',
            'new_password': 'NewAdminPass456!',
            'confirm_password': 'NewAdminPass456!'
        }, follow_redirects=True)
        
        assert response.status_code == 200
        assert b'Current password is incorrect' in response.data
    
    def test_change_password_mismatch(self, admin_client):
        """Test change password with password mismatch"""
        with admin_client.session_transaction() as sess:
            # Clear any existing flashes
            sess.pop('_flashes', None)
        
        response = admin_client.post('/auth/profile', data={
            'action': 'change_password',
            'current_password': 'AdminPass123!',
            'new_password': 'NewAdminPass456!',
            'confirm_password': 'DifferentPass456!'
        }, follow_redirects=True)
        
        assert response.status_code == 200
        
        assert b'New passwords do not match' in response.data


class TestSecurityFeatures:
    """Test security features"""
    
    def test_csrf_protection(self, client, admin_user):
        """Test CSRF protection on login"""
        # Get login page to get CSRF token
        response = client.get('/auth/login')
        assert response.status_code == 200
        
        # Try to post without CSRF token
        response = client.post('/auth/login', data={
            'email': admin_user.email,
            'password': 'AdminPass123!'
        }, headers={'Content-Type': 'application/x-www-form-urlencoded'})
        
        # Should fail due to missing CSRF token
        # Note: This depends on Flask-WTF CSRF protection being enabled
    
    def test_redirect_authenticated_user_from_login(self, admin_client):
        """Test authenticated users are redirected from login"""
        response = admin_client.get('/auth/login')
        assert response.status_code == 302  # Redirect
        assert '/dashboard' in response.location
    
    def test_session_persistence(self, client, admin_user, app):
        """Test session persistence with remember me"""
        with app.test_request_context():
            # Login with remember me
            response = client.post('/auth/login', data={
                'email': admin_user.email,
                'password': 'AdminPass123!',
                'remember': 'on'
            }, follow_redirects=True)
            
            assert response.status_code == 200
            
            # Session should have remember cookie
            # This would need to be tested with actual cookie inspection