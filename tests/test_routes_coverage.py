"""
Comprehensive tests for all routes to achieve 90%+ coverage
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from flask import url_for
import json


class TestMainRoutes:
    """Tests for main routes"""
    
    def test_index_redirect(self, client):
        """Test index redirects to dashboard"""
        response = client.get('/')
        assert response.status_code == 302
        assert response.location.endswith('/dashboard')
    
    def test_dashboard(self, client):
        """Test dashboard page"""
        response = client.get('/dashboard')
        assert response.status_code == 200
        assert b'Dashboard' in response.data or b'Overview' in response.data
    
    def test_settings(self, client):
        """Test settings page"""
        response = client.get('/settings')
        assert response.status_code == 200
        assert b'Settings' in response.data
    
    def test_import_csv_get(self, client):
        """Test import CSV page"""
        response = client.get('/import_csv')
        assert response.status_code == 200
        assert b'Import' in response.data
    
    def test_import_property_radar_get(self, client):
        """Test property radar import page"""
        response = client.get('/import_property_radar')
        assert response.status_code == 200
        assert b'Property' in response.data or b'Import' in response.data


class TestContactRoutes:
    """Tests for contact routes"""
    
    def test_contacts_list(self, client):
        """Test contacts list page"""
        response = client.get('/contacts/')
        assert response.status_code == 200
        assert b'Contacts' in response.data or b'contact' in response.data
    
    def test_contact_detail(self, client):
        """Test contact detail page"""
        response = client.get('/contacts/1')
        assert response.status_code == 200
    
    def test_add_contact_get(self, client):
        """Test add contact page"""
        response = client.get('/contacts/add')
        assert response.status_code == 200
        assert b'Add' in response.data or b'Contact' in response.data
    
    def test_conversations(self, client):
        """Test conversations page"""
        response = client.get('/contacts/conversations')
        assert response.status_code == 200
        assert b'Conversations' in response.data or b'Messages' in response.data
    
    def test_conversation_detail(self, client):
        """Test conversation detail page"""
        response = client.get('/contacts/conversation/1')
        assert response.status_code == 200


class TestPropertyRoutes:
    """Tests for property routes"""
    
    def test_properties_list(self, client):
        """Test properties list page"""
        response = client.get('/properties/')
        assert response.status_code == 200
        assert b'Properties' in response.data or b'properties' in response.data
    
    def test_property_detail(self, client):
        """Test property detail page"""
        response = client.get('/properties/1')
        assert response.status_code == 200
    
    def test_add_property_get(self, client):
        """Test add property page"""
        response = client.get('/properties/add')
        assert response.status_code == 200
        assert b'Add' in response.data or b'Property' in response.data


class TestJobRoutes:
    """Tests for job routes"""
    
    def test_jobs_list(self, client):
        """Test jobs list page"""
        response = client.get('/jobs/')
        assert response.status_code == 200
        assert b'Jobs' in response.data or b'job' in response.data
    
    def test_job_detail(self, client):
        """Test job detail page"""
        response = client.get('/jobs/job/1')
        assert response.status_code == 200
    
    def test_add_job_get(self, client):
        """Test add job page"""
        response = client.get('/jobs/job/add')
        assert response.status_code == 200
        assert b'Add' in response.data or b'Job' in response.data


class TestQuoteRoutes:
    """Tests for quote routes"""
    
    def test_quotes_list(self, client):
        """Test quotes list page"""
        response = client.get('/quotes/')
        assert response.status_code == 200
        assert b'Quotes' in response.data or b'quote' in response.data
    
    def test_quote_detail(self, client):
        """Test quote detail page"""
        response = client.get('/quotes/quote/1')
        assert response.status_code == 200
    
    def test_add_quote_get(self, client):
        """Test add quote page"""
        response = client.get('/quotes/quote/add')
        assert response.status_code == 200
        assert b'Add' in response.data or b'Quote' in response.data


class TestInvoiceRoutes:
    """Tests for invoice routes"""
    
    def test_invoices_list(self, client):
        """Test invoices list page"""
        response = client.get('/invoices/')
        assert response.status_code == 200
        assert b'Invoices' in response.data or b'invoice' in response.data
    
    def test_invoice_detail(self, client):
        """Test invoice detail page"""
        response = client.get('/invoices/1')
        assert response.status_code == 200
    
    def test_add_invoice_get(self, client):
        """Test add invoice page"""
        response = client.get('/invoices/add')
        assert response.status_code == 200
        assert b'Add' in response.data or b'Invoice' in response.data


class TestAppointmentRoutes:
    """Tests for appointment routes"""
    
    def test_appointments_list(self, client):
        """Test appointments list page"""
        response = client.get('/appointments/')
        assert response.status_code == 200
        assert b'Appointments' in response.data or b'appointment' in response.data
    
    def test_add_appointment_get(self, client):
        """Test add appointment page"""
        response = client.get('/appointments/add')
        assert response.status_code == 200
        assert b'Add' in response.data or b'Appointment' in response.data


class TestCampaignRoutes:
    """Tests for campaign routes"""
    
    def test_campaigns_index(self, client):
        """Test campaigns index page"""
        response = client.get('/campaigns')
        assert response.status_code == 200
        assert b'Campaigns' in response.data
    
    def test_new_campaign_get(self, client):
        """Test new campaign page"""
        response = client.get('/campaigns/new')
        assert response.status_code == 200
        assert b'Create' in response.data or b'New Campaign' in response.data
    
    def test_campaign_lists(self, client):
        """Test campaign lists page"""
        response = client.get('/campaigns/lists')
        assert response.status_code == 200
        assert b'Lists' in response.data
    
    def test_new_list_get(self, client):
        """Test new list page"""
        response = client.get('/campaigns/lists/new')
        assert response.status_code == 200
        assert b'Create' in response.data or b'New List' in response.data
    
    def test_import_csv_campaign_get(self, client):
        """Test campaign CSV import page"""
        response = client.get('/campaigns/import-csv')
        assert response.status_code == 200
        assert b'Import' in response.data


class TestGrowthRoutes:
    """Tests for growth routes"""
    
    def test_growth_page(self, client):
        """Test growth page"""
        response = client.get('/growth')
        assert response.status_code == 200
        assert b'Growth' in response.data or b'Lead' in response.data
    
    def test_flags_page(self, client):
        """Test flags page"""
        response = client.get('/flags')
        assert response.status_code == 200
        assert b'Flag' in response.data


class TestSettingsRoutes:
    """Tests for settings routes"""
    
    def test_quickbooks_settings(self, client):
        """Test QuickBooks settings page"""
        response = client.get('/quickbooks')
        assert response.status_code == 200
        assert b'QuickBooks' in response.data
    
    def test_automation_settings(self, client):
        """Test automation settings page"""
        response = client.get('/settings/automation')
        assert response.status_code == 200
        assert b'Automation' in response.data or b'Automated' in response.data


class TestAuthRoutes:
    """Tests for auth routes"""
    
    @patch('services.quickbooks_service.QuickBooksService')
    def test_quickbooks_auth(self, mock_qb, client):
        """Test QuickBooks OAuth initiation"""
        mock_instance = Mock()
        mock_instance.get_authorization_url.return_value = 'https://oauth.example.com'
        mock_qb.return_value = mock_instance
        
        response = client.get('/auth/quickbooks')
        assert response.status_code == 302
        assert response.location == 'https://oauth.example.com'
    
    def test_quickbooks_callback_no_code(self, client):
        """Test OAuth callback without code"""
        response = client.get('/auth/quickbooks/callback')
        assert response.status_code == 302
        assert response.location.endswith('/settings')
    
    def test_quickbooks_disconnect(self, client):
        """Test QuickBooks disconnect"""
        response = client.post('/auth/quickbooks/disconnect')
        assert response.status_code == 302
        assert response.location.endswith('/quickbooks')


class TestAPIRoutes:
    """Tests for API routes"""
    
    def test_api_contacts(self, client):
        """Test contacts API"""
        response = client.get('/api/contacts')
        assert response.status_code == 200
        data = response.get_json()
        assert 'success' in data
        assert 'contacts' in data
    
    def test_api_contact_search(self, client):
        """Test contact search API"""
        response = client.get('/api/contacts/search?query=test')
        assert response.status_code == 200
        data = response.get_json()
        assert 'success' in data
        assert 'contacts' in data
    
    def test_api_latest_conversations(self, client):
        """Test latest conversations API"""
        response = client.get('/api/messages/latest_conversations')
        assert response.status_code == 200
        data = response.get_json()
        assert isinstance(data, list)
    
    def test_api_contact_conversation(self, client):
        """Test contact conversation API"""
        response = client.get('/api/contact/1/conversation')
        assert response.status_code == 200
        data = response.get_json()
        assert 'messages' in data
    
    def test_api_webhook_no_signature(self, client):
        """Test webhook without signature"""
        response = client.post('/api/openphone/webhook', json={'test': 'data'})
        assert response.status_code == 401
    
    @patch('services.openphone_webhook_service.OpenPhoneWebhookService')
    def test_api_webhook_with_signature(self, mock_webhook, client):
        """Test webhook with signature"""
        mock_instance = Mock()
        mock_instance.process_webhook.return_value = {'status': 'success'}
        mock_webhook.return_value = mock_instance
        
        response = client.post(
            '/api/openphone/webhook',
            json={'id': 'test_123', 'type': 'message'},
            headers={'X-Openphone-Signature': 'test_signature'}
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data['status'] == 'success'