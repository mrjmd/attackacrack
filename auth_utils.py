# auth_utils.py
"""
Authentication utilities for testing and production
"""

from flask import current_app, g
from flask_login import current_user as flask_current_user
from unittest.mock import Mock

class CurrentUserProxy:
    """Proxy object that delegates to get_current_user() for LOGIN_DISABLED support"""
    def __getattr__(self, name):
        user = get_current_user()
        return getattr(user, name)
    
    def __bool__(self):
        return get_current_user().is_authenticated
    
    def __getitem__(self, key):
        return getattr(get_current_user(), key)

# Export current_user proxy for convenience
current_user = CurrentUserProxy()


def get_current_user():
    """
    Get current user, respecting LOGIN_DISABLED config for testing
    """
    # In testing mode with LOGIN_DISABLED, return mock user
    if current_app.config.get('LOGIN_DISABLED', False):
        if not hasattr(g, 'mock_user'):
            # Create a mock user object that behaves like a real user
            mock_user = Mock()
            mock_user.id = 1
            mock_user.email = 'test@example.com'
            mock_user.first_name = 'Test'
            mock_user.last_name = 'User'
            mock_user.role = 'admin'
            mock_user.is_admin = True
            mock_user.is_active = True
            mock_user.is_authenticated = True
            mock_user.is_anonymous = False
            mock_user.get_id.return_value = '1'
            g.mock_user = mock_user
        return g.mock_user
    
    # Normal production behavior
    return flask_current_user


def login_required(f):
    """Custom login_required decorator that respects LOGIN_DISABLED config"""
    from functools import wraps
    
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # In testing mode with LOGIN_DISABLED=True, allow access without authentication
        if current_app.config.get('LOGIN_DISABLED', False):
            return f(*args, **kwargs)
        
        # Otherwise, use normal Flask-Login behavior
        if not flask_current_user.is_authenticated:
            return current_app.login_manager.unauthorized()
        
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    """Decorator to require admin role, respects LOGIN_DISABLED"""
    from functools import wraps
    
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        # In testing mode with LOGIN_DISABLED, bypass admin check
        if current_app.config.get('LOGIN_DISABLED', False):
            return f(*args, **kwargs)
        
        current_user = get_current_user()
        if not current_user.is_admin:
            from flask import flash, redirect, url_for
            flash('Admin access required', 'error')
            return redirect(url_for('main.dashboard'))
        return f(*args, **kwargs)
    return decorated_function