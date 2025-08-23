# tests/test_auth_decorators.py
"""
Comprehensive tests for @login_required decorator protection and role-based access control
across all application routes.
"""

import pytest
from flask import url_for
from crm_database import User, InviteToken
from datetime import datetime, timedelta


@pytest.fixture(autouse=True)
def disable_login_disabled_for_auth_decorator_tests(request, app):
    """Override LOGIN_DISABLED for auth decorator tests only"""
    # Only apply to tests in this specific file
    if 'test_auth_decorators' in request.node.nodeid:
        original_value = app.config.get('LOGIN_DISABLED', True)
        app.config['LOGIN_DISABLED'] = False  # Enable auth checking for these tests
        yield
        app.config['LOGIN_DISABLED'] = original_value  # Restore original value
    else:
        yield


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
def admin_client(app, admin_user, db_session):
    """Fixture providing an authenticated admin client"""
    # Import here to avoid circular imports
    from flask_login import login_user
    
    client = app.test_client()
    
    with app.test_request_context():
        # Use Flask-Login's login_user instead of manual session manipulation
        login_user(admin_user)
        
        with client.session_transaction() as sess:
            # Copy the session data
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
    
    return client


@pytest.fixture
def marketer_client(app, marketer_user, db_session):
    """Fixture providing an authenticated marketer client"""
    # Import here to avoid circular imports
    from flask_login import login_user
    
    client = app.test_client()
    
    with app.test_request_context():
        # Use Flask-Login's login_user instead of manual session manipulation
        login_user(marketer_user)
        
        with client.session_transaction() as sess:
            # Copy the session data
            sess['_user_id'] = str(marketer_user.id)
            sess['_fresh'] = True
    
    return client


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


class TestLoginRequiredProtection:
    """Test that all protected routes require authentication"""
    
    def _check_auth_required(self, client, app, route, method='GET'):
        """Helper method to check if route requires authentication based on LOGIN_DISABLED setting"""
        if method == 'GET':
            response = client.get(route, follow_redirects=False)
        else:
            response = client.post(route, follow_redirects=False)
        
        # If LOGIN_DISABLED is True (testing mode), routes should be accessible or not found
        if app.config.get('LOGIN_DISABLED', False):
            assert response.status_code in [200, 404, 405], f"Route {route} should be accessible, not found, or method not allowed when LOGIN_DISABLED=True"
        else:
            # In production mode, should redirect to login or be not found
            assert response.status_code in [302, 404, 405], f"Route {route} should redirect, be not found, or method not allowed when LOGIN_DISABLED=False"
            if response.status_code == 302:
                assert '/auth/login' in response.location
    
    def test_main_routes_require_login(self, client, app):
        """Test main routes require authentication"""
        protected_routes = [
            '/dashboard',
            '/settings',
            '/customers',
            '/finances',
            '/marketing',
            '/import_csv',
            '/import_property_radar'
        ]
        
        for route in protected_routes:
            response = client.get(route, follow_redirects=False)
            
            # If LOGIN_DISABLED is True (testing mode), routes should be accessible
            if app.config.get('LOGIN_DISABLED', False):
                assert response.status_code == 200, f"Route {route} should be accessible when LOGIN_DISABLED=True"
            else:
                # In production mode, should redirect to login
                assert response.status_code == 302, f"Route {route} should redirect to login when LOGIN_DISABLED=False"
                assert '/auth/login' in response.location
    
    def test_contact_routes_require_login(self, client, app):
        """Test contact routes require authentication"""
        protected_routes = [
            '/contacts/',
            '/contacts/1',
            '/contacts/conversations',
            '/contacts/add',
            '/contacts/1/edit',
            '/contacts/1/conversation'
        ]
        
        for route in protected_routes:
            response = client.get(route, follow_redirects=False)
            
            # If LOGIN_DISABLED is True (testing mode), check appropriate responses
            if app.config.get('LOGIN_DISABLED', False):
                # Routes should be accessible (200) or not found (404) if data doesn't exist
                assert response.status_code in [200, 404], f"Route {route} should be accessible or not found when LOGIN_DISABLED=True"
            else:
                # In production mode, should redirect to login or be not found
                assert response.status_code in [302, 404], f"Route {route} should redirect or be not found when LOGIN_DISABLED=False"
                if response.status_code == 302:
                    assert '/auth/login' in response.location
    
    def test_property_routes_require_login(self, client, app):
        """Test property routes require authentication"""
        protected_routes = [
            ('/properties/', 'GET'),
            ('/properties/add', 'GET'),
            ('/properties/1', 'GET'),
            ('/properties/1/edit', 'GET'),
            ('/properties/1/delete', 'POST')
        ]
        
        for route, method in protected_routes:
            self._check_auth_required(client, app, route, method)
    
    def test_job_routes_require_login(self, client, app):
        """Test job routes require authentication"""
        protected_routes = [
            ('/jobs/', 'GET'),
            ('/jobs/add', 'GET'),
            ('/jobs/1', 'GET'),
            ('/jobs/1/edit', 'GET')
        ]
        
        for route, method in protected_routes:
            self._check_auth_required(client, app, route, method)
    
    def test_quote_routes_require_login(self, client, app):
        """Test quote routes require authentication"""
        protected_routes = [
            ('/quotes/', 'GET'),
            ('/quotes/add', 'GET'),
            ('/quotes/1', 'GET'),
            ('/quotes/1/edit', 'GET'),
            ('/quotes/1/print', 'GET')
        ]
        
        for route, method in protected_routes:
            self._check_auth_required(client, app, route, method)
    
    def test_invoice_routes_require_login(self, client, app):
        """Test invoice routes require authentication"""
        protected_routes = [
            ('/invoices/', 'GET'),
            ('/invoices/add', 'GET'),
            ('/invoices/1', 'GET'),
            ('/invoices/1/edit', 'GET'),
            ('/invoices/1/print', 'GET')
        ]
        
        for route, method in protected_routes:
            self._check_auth_required(client, app, route, method)
    
    def test_appointment_routes_require_login(self, client, app):
        """Test appointment routes require authentication"""
        protected_routes = [
            ('/appointments/', 'GET'),
            ('/appointments/add', 'GET'),
            ('/appointments/1', 'GET'),
            ('/appointments/1/edit', 'GET'),
            ('/appointments/1/delete', 'POST')
        ]
        
        for route, method in protected_routes:
            self._check_auth_required(client, app, route, method)
    
    def test_campaign_routes_require_login(self, client, app):
        """Test campaign routes require authentication"""
        protected_routes = [
            '/campaigns/',
            '/campaigns/create',
            '/campaigns/1',
            '/campaigns/1/edit',
            '/campaigns/1/recipients',
            '/campaigns/1/schedule',
            '/campaigns/1/send',
            '/campaigns/1/ab_results',
            '/campaigns/1/clone',
            '/campaigns/lists',
            '/campaigns/lists/create',
            '/campaigns/lists/1',
            '/campaigns/lists/1/import',
            '/campaigns/lists/1/export'
        ]
        
        for route in protected_routes:
            self._check_auth_required(client, app, route, 'GET')
    
    def test_settings_routes_require_login(self, client, app):
        """Test settings routes require authentication"""
        protected_routes = [
            '/settings/',
            '/settings/appointment-reminder',
            '/settings/review-request',
            '/settings/welcome-message',
            '/settings/general'
        ]
        
        for route in protected_routes:
            self._check_auth_required(client, app, route, 'GET')
    
    def test_growth_routes_require_login(self, client, app):
        """Test growth analytics routes require authentication"""
        protected_routes = [
            '/growth/',
            '/growth/analytics'
        ]
        
        for route in protected_routes:
            self._check_auth_required(client, app, route, 'GET')
    
    def test_api_routes_require_login(self, client, app):
        """Test API routes require authentication"""
        protected_routes = [
            '/api/contacts',
            '/api/messages/latest_conversations',
            '/api/contacts/1/messages',
            '/api/appointments/generate_summary/1'
        ]
        
        for route in protected_routes:
            self._check_auth_required(client, app, route, 'GET')


class TestRoleBasedAccessControl:
    """Test role-based access control for admin vs marketer roles"""
    
    def test_admin_only_routes(self, admin_client, marketer_client):
        """Test routes that only admins can access"""
        admin_only_get_routes = [
            '/auth/users',
            '/auth/invite'
        ]
        
        admin_only_post_routes = [
            '/auth/users/1/toggle-status'
        ]
        
        # Test GET routes
        for route in admin_only_get_routes:
            # Admin can access
            admin_response = admin_client.get(route, follow_redirects=False)
            assert admin_response.status_code != 403  # Not forbidden
            
            # Marketer cannot access
            marketer_response = marketer_client.get(route, follow_redirects=False)
            assert marketer_response.status_code == 302  # Redirected
            assert '/dashboard' in marketer_response.location
        
        # Test POST routes
        for route in admin_only_post_routes:
            # Admin can access (might get 404 if user doesn't exist, but not 403)
            admin_response = admin_client.post(route, follow_redirects=False)
            assert admin_response.status_code != 403  # Not forbidden
            
            # Marketer cannot access
            marketer_response = marketer_client.post(route, follow_redirects=False)
            assert marketer_response.status_code == 302  # Redirected
            assert '/dashboard' in marketer_response.location
    
    def test_both_roles_can_access_general_routes(self, admin_client, marketer_client):
        """Test routes that both admins and marketers can access"""
        general_routes = [
            '/dashboard',
            '/contacts/',
            '/properties/',
            '/jobs/',
            '/quotes/',
            '/invoices/',
            '/appointments/',
            '/campaigns',  # Campaigns list route
            '/settings',
            '/marketing'
        ]
        
        for route in general_routes:
            # Admin can access
            admin_response = admin_client.get(route, follow_redirects=False)
            assert admin_response.status_code == 200, f"Admin could not access {route}"
            
            # Marketer can access
            marketer_response = marketer_client.get(route, follow_redirects=False)
            assert marketer_response.status_code == 200, f"Marketer could not access {route}"
    
    def test_admin_sees_full_ui(self, admin_client):
        """Test that admin users see all UI elements"""
        response = admin_client.get('/dashboard')
        assert response.status_code == 200
        # Admin should see user management link
        assert b'Manage Users' in response.data or b'Users' in response.data
    
    def test_marketer_sees_limited_ui(self, marketer_client):
        """Test that marketer users see limited UI elements"""
        response = marketer_client.get('/dashboard')
        assert response.status_code == 200
        # Marketer should not see user management link
        assert b'Manage Users' not in response.data


class TestAuthenticationFlow:
    """Test complete authentication flow"""
    
    def test_login_logout_flow(self, client, admin_user, app):
        """Test complete login and logout flow"""
        # Start unauthenticated
        response = client.get('/dashboard')
        assert response.status_code == 302
        assert '/auth/login' in response.location
        
        # Login
        with app.test_request_context():
            response = client.post('/auth/login', data={
                'email': admin_user.email,
                'password': 'AdminPass123!'
            }, follow_redirects=True)
            assert response.status_code == 200
            assert b'Dashboard' in response.data
        
        # Now authenticated
        response = client.get('/dashboard')
        assert response.status_code == 200
        
        # Logout
        response = client.get('/auth/logout', follow_redirects=True)
        assert response.status_code == 200
        assert b'You have been logged out' in response.data
        
        # No longer authenticated
        response = client.get('/dashboard')
        assert response.status_code == 302
        assert '/auth/login' in response.location
    
    def test_remember_me_functionality(self, client, admin_user, app):
        """Test remember me checkbox functionality"""
        with app.test_request_context():
            # Login with remember me
            response = client.post('/auth/login', data={
                'email': admin_user.email,
                'password': 'AdminPass123!',
                'remember': 'on'
            }, follow_redirects=True)
            
            assert response.status_code == 200
            # Would need to inspect actual cookies to verify remember_me token
    
    def test_next_url_redirect(self, client, admin_user, app):
        """Test redirect to next URL after login"""
        # Ensure user is logged out first
        client.get('/auth/logout')
        
        # Try to access protected page
        response = client.get('/properties/', follow_redirects=False)
        assert response.status_code == 302
        login_url = response.location
        assert '/auth/login?next=%2Fproperties%2F' in login_url
        
        # Login and should redirect to properties
        with app.test_request_context():
            response = client.post('/auth/login?next=/properties/', data={
                'email': admin_user.email,
                'password': 'AdminPass123!'
            }, follow_redirects=True)
            
            assert response.status_code == 200
            assert b'Properties' in response.data
            assert b'<h2 class="text-3xl font-bold">Properties</h2>' in response.data


class TestPasswordRequirements:
    """Test password validation requirements"""
    
    def test_password_validation_on_invite_accept(self, client, valid_invite):
        """Test password requirements when accepting invite"""
        weak_passwords = [
            'short',           # Too short
            'nouppercase123!', # No uppercase
            'NOLOWERCASE123!', # No lowercase
            'NoNumbers!',      # No numbers
            'NoSpecialChar123' # No special characters
        ]
        
        for weak_password in weak_passwords:
            response = client.post(f'/auth/accept-invite/{valid_invite.token}', data={
                'first_name': 'Test',
                'last_name': 'User',
                'password': weak_password,
                'confirm_password': weak_password
            }, follow_redirects=True)
            
            assert response.status_code == 200
            assert b'at least 8 characters' in response.data or \
                   b'uppercase letter' in response.data or \
                   b'lowercase letter' in response.data or \
                   b'one number' in response.data or \
                   b'special character' in response.data
    
    def test_password_validation_on_change(self, admin_client):
        """Test password requirements when changing password"""
        response = admin_client.post('/auth/profile', data={
            'action': 'change_password',
            'current_password': 'AdminPass123!',
            'new_password': 'weak',
            'confirm_password': 'weak'
        }, follow_redirects=True)
        
        assert response.status_code == 200
        assert b'at least 8 characters' in response.data


class TestSessionSecurity:
    """Test session security features"""
    
    def test_session_invalidation_on_logout(self, admin_client):
        """Test that session is properly invalidated on logout"""
        # Verify logged in
        response = admin_client.get('/dashboard')
        assert response.status_code == 200
        
        # Logout
        admin_client.get('/auth/logout')
        
        # Try to access protected route
        response = admin_client.get('/dashboard')
        assert response.status_code == 302
        assert '/auth/login' in response.location
    
    def test_inactive_user_cannot_login(self, client, admin_user, db_session):
        """Test that inactive users cannot login"""
        # Deactivate user
        admin_user.is_active = False
        db_session.commit()
        
        # Try to login
        response = client.post('/auth/login', data={
            'email': admin_user.email,
            'password': 'AdminPass123!'
        }, follow_redirects=True)
        
        assert response.status_code == 200
        assert b'Login' in response.data  # Still on login page
        
        # Verify cannot access protected routes
        response = client.get('/dashboard')
        assert response.status_code == 302
    
    def test_concurrent_sessions(self, app, admin_user):
        """Test that multiple sessions can exist for same user"""
        client1 = app.test_client()
        client2 = app.test_client()
        
        # Login with first client
        with app.test_request_context():
            response1 = client1.post('/auth/login', data={
                'email': admin_user.email,
                'password': 'AdminPass123!'
            }, follow_redirects=True)
            assert response1.status_code == 200
        
        # Login with second client
        with app.test_request_context():
            response2 = client2.post('/auth/login', data={
                'email': admin_user.email,
                'password': 'AdminPass123!'
            }, follow_redirects=True)
            assert response2.status_code == 200
        
        # Both should be able to access protected routes
        assert client1.get('/dashboard').status_code == 200
        assert client2.get('/dashboard').status_code == 200