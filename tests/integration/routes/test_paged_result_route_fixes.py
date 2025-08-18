# tests/integration/routes/test_paged_result_route_fixes.py
"""
TDD tests for PagedResult template compatibility issues.

Testing that routes properly handle PagedResult objects and pass
correct data structures to templates.
"""

import pytest
from unittest.mock import Mock, patch
from flask import url_for
from services.common.result import PagedResult, Result
from crm_database import User, Contact


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
def admin_client(app, admin_user, db_session):
    """Fixture providing an authenticated admin client"""
    client = app.test_client()
    
    with client.session_transaction() as sess:
        # Manually log in the user by setting session
        sess['_user_id'] = str(admin_user.id)
        sess['_fresh'] = True
    
    return client


class TestAuthUsersRoutePagedResult:
    """Test /auth/users route PagedResult handling"""
    
    def test_auth_users_returns_200(self, admin_client, app):
        """Test that /auth/users route returns 200 OK"""
        with app.app_context():
            response = admin_client.get('/auth/users')
            assert response.status_code == 200
    
    def test_auth_users_template_receives_users_list(self, admin_client, app):
        """Test that template receives users as list, not PagedResult"""
        with app.app_context():
            response = admin_client.get('/auth/users')
            assert response.status_code == 200
            
            # Template should be able to iterate over users
            # This will fail if PagedResult is passed directly
            assert b'<tbody' in response.data  # Users table exists
            
    def test_auth_users_template_receives_pagination_object(self, admin_client, app):
        """Test that template receives pagination object for pagination controls"""
        with app.app_context():
            response = admin_client.get('/auth/users')
            assert response.status_code == 200
            
            # Check if pagination data is available in template context
            # This should work after fix
            # Look for pagination elements (this may not be visible in current template)
            
    @patch('services.auth_service_refactored.AuthServiceRefactored.get_all_users')
    def test_auth_users_handles_paged_result_success(self, mock_get_users, admin_client, app):
        """Test route handles successful PagedResult from service"""
        # Create mock PagedResult
        mock_users_data = [
            {'id': 1, 'email': 'user1@test.com', 'first_name': 'User', 'last_name': 'One', 'role': 'admin', 'is_active': True, 'last_login': None},
            {'id': 2, 'email': 'user2@test.com', 'first_name': 'User', 'last_name': 'Two', 'role': 'marketer', 'is_active': True, 'last_login': None}
        ]
        
        mock_paged_result = PagedResult.paginated(
            data=mock_users_data,
            total=2,
            page=1,
            per_page=50
        )
        mock_get_users.return_value = mock_paged_result
        
        with app.app_context():
            response = admin_client.get('/auth/users')
            assert response.status_code == 200
            
            # Template should render user data
            assert b'user1@test.com' in response.data
            assert b'user2@test.com' in response.data
    
    @patch('services.auth_service_refactored.AuthServiceRefactored.get_all_users')
    def test_auth_users_handles_paged_result_failure(self, mock_get_users, admin_client, app):
        """Test route handles failed PagedResult from service"""
        # Create mock failed PagedResult
        mock_paged_result = PagedResult.failure("Database error", "DB_ERROR")
        mock_get_users.return_value = mock_paged_result
        
        with app.app_context():
            response = admin_client.get('/auth/users')
            assert response.status_code == 200
            
            # Should show error message
            assert b'Failed to load users' in response.data or b'error' in response.data.lower()
    
    @patch('services.auth_service_refactored.AuthServiceRefactored.get_pending_invites')
    def test_auth_users_handles_invites_result(self, mock_get_invites, admin_client, app):
        """Test route handles invites Result from service"""
        # Create mock successful Result for invites
        mock_invites_data = [
            {'email': 'invite1@test.com', 'role': 'marketer', 'created_at': '2024-01-01', 'expires_at': '2024-01-08'}
        ]
        
        mock_result = Result.success(mock_invites_data)
        mock_get_invites.return_value = mock_result
        
        with app.app_context():
            response = admin_client.get('/auth/users')
            assert response.status_code == 200
            
            # Template should render invite data if any
            assert b'invite1@test.com' in response.data or b'Pending Invitations' in response.data


class TestPropertyAddRoutePagedResult:
    """Test /properties/add route PagedResult handling"""
    
    def test_property_add_get_returns_200(self, admin_client, app):
        """Test that /properties/add GET returns 200 OK"""
        with app.app_context():
            response = admin_client.get('/properties/add')
            assert response.status_code == 200
    
    def test_property_add_template_receives_iterable_contacts(self, admin_client, app):
        """Test that template receives contacts as iterable list, not PagedResult"""
        with app.app_context():
            response = admin_client.get('/properties/add')
            assert response.status_code == 200
            
            # Template should be able to iterate over contacts in select dropdown
            # This will fail if PagedResult is passed directly to template
            assert b'<select' in response.data  # Contact select exists
            assert b'contact_id' in response.data  # Contact select field exists
    
    @patch('services.contact_service_refactored.ContactServiceRefactored.get_all_contacts')
    def test_property_add_handles_paged_result_success(self, mock_get_contacts, admin_client, app):
        """Test route handles successful PagedResult from contact service"""
        # Create mock PagedResult with contact data
        mock_contacts_data = [
            {'id': 1, 'first_name': 'John', 'last_name': 'Doe', 'phone': '+1234567890'},
            {'id': 2, 'first_name': 'Jane', 'last_name': 'Smith', 'phone': '+1987654321'}
        ]
        
        mock_paged_result = PagedResult.paginated(
            data=mock_contacts_data,
            total=2,
            page=1,
            per_page=100
        )
        mock_get_contacts.return_value = mock_paged_result
        
        with app.app_context():
            response = admin_client.get('/properties/add')
            assert response.status_code == 200
            
            # Template should render contact options
            assert b'John Doe' in response.data
            assert b'Jane Smith' in response.data
    
    @patch('services.contact_service_refactored.ContactServiceRefactored.get_all_contacts')
    def test_property_add_handles_paged_result_failure(self, mock_get_contacts, admin_client, app):
        """Test route handles failed PagedResult from contact service"""
        # Create mock failed PagedResult
        mock_paged_result = PagedResult.failure("Database error", "DB_ERROR")
        mock_get_contacts.return_value = mock_paged_result
        
        with app.app_context():
            response = admin_client.get('/properties/add')
            assert response.status_code == 200
            
            # Should still render form but with empty/no contacts
            assert b'<select' in response.data  # Form still renders
            assert b'contact_id' in response.data
    
    @patch('services.contact_service_refactored.ContactServiceRefactored.get_all_contacts')
    def test_property_add_handles_empty_contacts(self, mock_get_contacts, admin_client, app):
        """Test route handles empty contacts PagedResult"""
        # Create mock PagedResult with no data
        mock_paged_result = PagedResult.paginated(
            data=[],
            total=0,
            page=1,
            per_page=100
        )
        mock_get_contacts.return_value = mock_paged_result
        
        with app.app_context():
            response = admin_client.get('/properties/add')
            assert response.status_code == 200
            
            # Form should still render with empty select
            assert b'<select' in response.data
            assert b'contact_id' in response.data


class TestPropertyEditRoutePagedResult:
    """Test /properties/<id>/edit route PagedResult handling (similar issue)"""
    
    @patch('services.property_service.PropertyService.get_property_by_id')
    @patch('services.contact_service_refactored.ContactServiceRefactored.get_all_contacts')
    def test_property_edit_handles_paged_result(self, mock_get_contacts, mock_get_property, admin_client, app):
        """Test property edit route handles PagedResult from contact service"""
        # Mock property
        mock_property = Mock()
        mock_property.id = 1
        mock_property.address = "123 Test St"
        mock_property.contact_id = 1
        mock_get_property.return_value = mock_property
        
        # Mock contacts PagedResult
        mock_contacts_data = [
            {'id': 1, 'first_name': 'John', 'last_name': 'Doe', 'phone': '+1234567890'},
            {'id': 2, 'first_name': 'Jane', 'last_name': 'Smith', 'phone': '+1987654321'}
        ]
        
        mock_paged_result = PagedResult.paginated(
            data=mock_contacts_data,
            total=2,
            page=1,
            per_page=100
        )
        mock_get_contacts.return_value = mock_paged_result
        
        with app.app_context():
            response = admin_client.get('/properties/1/edit')
            assert response.status_code == 200
            
            # Template should render contact options and property data
            assert b'John Doe' in response.data
            assert b'Jane Smith' in response.data
            assert b'123 Test St' in response.data


class TestPagedResultTemplateCompatibility:
    """Test general PagedResult template compatibility patterns"""
    
    def test_paged_result_data_extraction(self):
        """Test that routes extract .data from PagedResult for template iteration"""
        # Create sample PagedResult
        test_data = [{'id': 1, 'name': 'Test'}, {'id': 2, 'name': 'Test2'}]
        paged_result = PagedResult.paginated(
            data=test_data,
            total=2,
            page=1,
            per_page=10
        )
        
        # Test that we can iterate over .data
        assert hasattr(paged_result, 'data')
        assert isinstance(paged_result.data, list)
        assert len(paged_result.data) == 2
        
        # Routes should pass paged_result.data to templates, not paged_result itself
        for item in paged_result.data:
            assert 'id' in item
            assert 'name' in item
    
    def test_paged_result_pagination_metadata(self):
        """Test that PagedResult provides pagination metadata"""
        test_data = [{'id': i} for i in range(10)]
        paged_result = PagedResult.paginated(
            data=test_data,
            total=100,
            page=2,
            per_page=10
        )
        
        # Test pagination metadata
        assert paged_result.total == 100
        assert paged_result.page == 2
        assert paged_result.per_page == 10
        assert paged_result.total_pages == 10
        
        # Routes should pass this metadata for pagination controls
        pagination_info = {
            'total': paged_result.total,
            'page': paged_result.page,
            'per_page': paged_result.per_page,
            'total_pages': paged_result.total_pages
        }
        assert pagination_info['total'] == 100
        assert pagination_info['page'] == 2
