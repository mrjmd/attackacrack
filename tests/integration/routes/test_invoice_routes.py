# tests/integration/routes/test_invoice_routes.py
"""
Comprehensive tests for invoice routes to verify:
1. Service registry usage (not direct instantiation)
2. Authentication and authorization
3. Route functionality
4. Template rendering
5. Error handling

These tests are written FIRST to verify the route layer properly
uses dependency injection via the service registry.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from flask import url_for
from datetime import date, datetime
from crm_database import Invoice, Job, Property, Contact


class TestInvoiceRoutesServiceRegistry:
    """Test that invoice routes use service registry instead of direct instantiation"""
    
    def test_invoice_routes_use_service_registry_not_direct_instantiation(self, app):
        """Test that invoice routes use current_app.services.get() instead of direct service creation"""
        with app.app_context():
            # Verify invoice service is registered and available
            invoice_service = app.services.get('invoice')
            assert invoice_service is not None
            assert hasattr(invoice_service, 'get_all_invoices')
            
            # Verify job service is registered and available
            job_service = app.services.get('job')
            assert job_service is not None
            assert hasattr(job_service, 'get_all_jobs')
    
    @patch('routes.invoice_routes.current_app')
    def test_list_all_route_uses_service_registry(self, mock_current_app, authenticated_client):
        """Test that list_all route uses service registry"""
        # Setup mock services
        mock_invoice_service = Mock()
        mock_invoice_service.get_all_invoices.return_value = []
        
        # Create a mock services object with a regular Mock get method
        mock_services = Mock()
        mock_services.get = Mock(return_value=mock_invoice_service)
        mock_current_app.services = mock_services
        
        # Make request
        response = authenticated_client.get('/invoices/')
        
        # Verify service registry was called
        mock_services.get.assert_called_with('invoice')
        mock_invoice_service.get_all_invoices.assert_called_once()
        assert response.status_code == 200
    
    @patch('routes.invoice_routes.current_app')
    def test_invoice_detail_route_uses_service_registry(self, mock_current_app, authenticated_client):
        """Test that invoice_detail route uses service registry"""
        # Setup mock services
        mock_invoice_service = Mock()
        mock_invoice = Mock()
        mock_invoice.id = 1
        mock_invoice.total_amount = 100.00
        mock_invoice.due_date = '2025-01-01'
        mock_invoice.status = 'Unpaid'
        mock_job = Mock()
        mock_job.id = 1
        mock_job.description = 'Test Job'
        mock_invoice.job = mock_job
        mock_invoice_service.get_invoice_by_id.return_value = mock_invoice
        
        # Create a mock services object with a regular Mock get method
        mock_services = Mock()
        mock_services.get = Mock(return_value=mock_invoice_service)
        mock_current_app.services = mock_services
        
        # Make request
        response = authenticated_client.get('/invoices/1')
        
        # Verify service registry was called
        mock_services.get.assert_called_with('invoice')
        mock_invoice_service.get_invoice_by_id.assert_called_once_with(1)
        assert response.status_code == 200
    
    @patch('routes.invoice_routes.current_app')
    def test_add_invoice_get_uses_service_registry(self, mock_current_app, authenticated_client):
        """Test that add_invoice GET route uses service registry for job service"""
        # Setup mock services
        mock_job_service = Mock()
        mock_job_service.get_all_jobs.return_value = []
        
        # Mock the service registry to return different services based on the name
        def mock_get_service(service_name):
            if service_name == 'job':
                return mock_job_service
            return Mock()
        
        # Create a mock services object with a regular Mock get method
        mock_services = Mock()
        mock_services.get = Mock(side_effect=mock_get_service)
        mock_current_app.services = mock_services
        
        # Make request
        response = authenticated_client.get('/invoices/add')
        
        # Verify service registry was called for job service
        mock_services.get.assert_any_call('job')
        mock_job_service.get_all_jobs.assert_called_once()
        assert response.status_code == 200
    
    @patch('routes.invoice_routes.current_app')
    def test_add_invoice_post_uses_service_registry(self, mock_current_app, authenticated_client):
        """Test that add_invoice POST route uses service registry"""
        # Setup mock services
        mock_invoice_service = Mock()
        mock_invoice_service.add_invoice.return_value = None
        mock_invoice_service.get_all_invoices.return_value = []  # For redirect to list_all
        
        # Create a mock services object with a regular Mock get method
        mock_services = Mock()
        mock_services.get = Mock(return_value=mock_invoice_service)
        mock_current_app.services = mock_services
        
        # Make request
        response = authenticated_client.post('/invoices/add', data={
            'amount': '100.00',
            'due_date': '2025-01-01',
            'status': 'Unpaid',
            'job_id': '1'
        }, follow_redirects=True)
        
        # Verify service registry was called
        mock_services.get.assert_any_call('invoice')
        mock_invoice_service.add_invoice.assert_called_once()
        assert response.status_code == 200
    
    @patch('routes.invoice_routes.current_app')
    def test_edit_invoice_get_uses_service_registry(self, mock_current_app, authenticated_client):
        """Test that edit_invoice GET route uses service registry"""
        # Setup mock services
        mock_invoice_service = Mock()
        mock_job_service = Mock()
        mock_invoice = Mock()
        mock_invoice.id = 1  # Add id for template URL generation
        mock_invoice.job_id = 1
        mock_invoice.status = 'Unpaid'
        mock_invoice.total_amount = 100.00
        mock_invoice.issue_date = date(2025, 1, 1)  # Use actual date object
        mock_invoice.due_date = date(2025, 2, 1)  # Use actual date object
        
        mock_invoice_service.get_invoice_by_id.return_value = mock_invoice
        mock_job_service.get_all_jobs.return_value = []
        
        def mock_get_service(service_name):
            if service_name == 'invoice':
                return mock_invoice_service
            elif service_name == 'job':
                return mock_job_service
            return Mock()
        
        # Create a mock services object with a regular Mock get method
        mock_services = Mock()
        mock_services.get = Mock(side_effect=mock_get_service)
        mock_current_app.services = mock_services
        
        # Make request
        response = authenticated_client.get('/invoices/1/edit')
        
        # Verify service registry was called for both services
        mock_services.get.assert_any_call('invoice')
        mock_services.get.assert_any_call('job')
        mock_invoice_service.get_invoice_by_id.assert_called_once_with(1)
        mock_job_service.get_all_jobs.assert_called_once()
        assert response.status_code == 200
    
    @patch('routes.invoice_routes.current_app')
    def test_edit_invoice_post_uses_service_registry(self, mock_current_app, authenticated_client):
        """Test that edit_invoice POST route uses service registry"""
        # Setup mock services
        mock_invoice_service = Mock()
        mock_invoice = Mock()
        mock_invoice.id = 1
        mock_invoice.total_amount = 150.00
        mock_invoice.due_date = '2025-02-01'
        mock_invoice.status = 'Paid'
        mock_job = Mock()
        mock_job.id = 1
        mock_job.description = 'Test Job'
        mock_invoice.job = mock_job
        
        mock_invoice_service.get_invoice_by_id.return_value = mock_invoice
        mock_invoice_service.update_invoice.return_value = None
        
        # Create a mock services object with a regular Mock get method
        mock_services = Mock()
        mock_services.get = Mock(return_value=mock_invoice_service)
        mock_current_app.services = mock_services
        
        # Make request
        response = authenticated_client.post('/invoices/1/edit', data={
            'amount': '150.00',
            'due_date': '2025-02-01',
            'status': 'Paid',
            'job_id': '1'
        }, follow_redirects=True)
        
        # Verify service registry was called
        mock_services.get.assert_any_call('invoice')
        mock_invoice_service.get_invoice_by_id.assert_called_with(1)
        mock_invoice_service.update_invoice.assert_called_once()
        assert response.status_code == 200
    
    @patch('routes.invoice_routes.current_app')
    def test_delete_invoice_uses_service_registry(self, mock_current_app, authenticated_client):
        """Test that delete_invoice route uses service registry"""
        # Setup mock services
        mock_invoice_service = Mock()
        mock_invoice = Mock()
        mock_invoice.id = 1  # Add id for redirect after delete
        
        mock_invoice_service.get_invoice_by_id.return_value = mock_invoice
        mock_invoice_service.delete_invoice.return_value = None
        mock_invoice_service.get_all_invoices.return_value = []  # For redirect to list_all
        
        # Create a mock services object with a regular Mock get method
        mock_services = Mock()
        mock_services.get = Mock(return_value=mock_invoice_service)
        mock_current_app.services = mock_services
        
        # Make request
        response = authenticated_client.post('/invoices/1/delete', follow_redirects=True)
        
        # Verify service registry was called
        mock_services.get.assert_called_with('invoice')
        mock_invoice_service.get_invoice_by_id.assert_called_once_with(1)
        mock_invoice_service.delete_invoice.assert_called_once_with(mock_invoice)
        assert response.status_code == 200


class TestInvoiceRoutesAuthentication:
    """Test authentication requirements for invoice routes"""
    
    def test_all_invoice_routes_require_authentication(self, client):
        """Test that all invoice routes require authentication"""
        # Ensure we're logged out
        client.get('/auth/logout')
        
        protected_routes = [
            '/invoices/',
            '/invoices/1',
            '/invoices/add',
            '/invoices/1/edit',
        ]
        
        for route in protected_routes:
            response = client.get(route, follow_redirects=False)
            assert response.status_code == 302, f"Expected redirect for {route}, got {response.status_code}"
            assert '/auth/login' in response.location
    
    def test_delete_invoice_requires_authentication(self, client):
        """Test that delete invoice POST route requires authentication"""
        # Ensure we're logged out
        client.get('/auth/logout')
        
        response = client.post('/invoices/1/delete', follow_redirects=False)
        assert response.status_code == 302
        assert '/auth/login' in response.location


class TestInvoiceRoutesFunctionality:
    """Test invoice routes functionality with real services"""
    
    def test_list_all_invoices_renders_template(self, authenticated_client, app, db_session):
        """Test that list all invoices renders the correct template"""
        with app.app_context():
            response = authenticated_client.get('/invoices/')
            assert response.status_code == 200
            # Should contain invoice list elements
            assert b'invoice' in response.data or b'Invoice' in response.data
    
    def test_invoice_detail_with_existing_invoice(self, authenticated_client, app, db_session):
        """Test invoice detail page with existing invoice"""
        with app.app_context():
            response = authenticated_client.get('/invoices/1')
            assert response.status_code == 200
            # Should contain invoice detail elements
            assert b'invoice' in response.data or b'Invoice' in response.data
    
    def test_add_invoice_get_renders_form(self, authenticated_client, app):
        """Test that add invoice GET renders the form"""
        with app.app_context():
            response = authenticated_client.get('/invoices/add')
            assert response.status_code == 200
            # Should contain form elements
            assert b'amount' in response.data or b'Amount' in response.data
            assert b'due_date' in response.data or b'Due Date' in response.data
            assert b'status' in response.data or b'Status' in response.data
    
    def test_edit_invoice_get_renders_form(self, authenticated_client, app):
        """Test that edit invoice GET renders the form with existing data"""
        with app.app_context():
            response = authenticated_client.get('/invoices/1/edit')
            assert response.status_code == 200
            # Should contain form elements
            assert b'amount' in response.data or b'Amount' in response.data
            assert b'due_date' in response.data or b'Due Date' in response.data
            assert b'status' in response.data or b'Status' in response.data


class TestInvoiceRoutesErrorHandling:
    """Test error handling in invoice routes"""
    
    def test_invoice_detail_nonexistent_invoice(self, authenticated_client, app):
        """Test invoice detail with non-existent invoice ID"""
        with app.app_context():
            # Try to access an invoice that doesn't exist
            response = authenticated_client.get('/invoices/999999')
            # Should handle gracefully (either 404 or redirect)
            assert response.status_code in [200, 404, 302]
    
    def test_edit_nonexistent_invoice(self, authenticated_client, app):
        """Test edit route with non-existent invoice ID"""
        with app.app_context():
            response = authenticated_client.get('/invoices/999999/edit')
            # Should handle gracefully (either 404 or redirect)
            assert response.status_code in [200, 404, 302]
    
    def test_delete_nonexistent_invoice(self, authenticated_client, app):
        """Test delete route with non-existent invoice ID"""
        with app.app_context():
            response = authenticated_client.post('/invoices/999999/delete', follow_redirects=True)
            # Should handle gracefully (either 404 or redirect)
            assert response.status_code in [200, 404, 302]
