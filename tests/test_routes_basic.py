"""
Basic tests for routes to improve coverage
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from flask import url_for
from crm_database import db, Contact, Campaign, CampaignList, QuickBooksAuth


class TestCampaignRoutes:
    """Test campaign routes"""
    
    def test_campaigns_index(self, client):
        """Test campaigns index page"""
        response = client.get('/campaigns')
        assert response.status_code == 200
        assert b'Campaigns' in response.data
    
    def test_new_campaign_page(self, client):
        """Test new campaign page"""
        response = client.get('/campaigns/new')
        assert response.status_code == 200
        assert b'Create New Campaign' in response.data
    
    @patch('services.campaign_service.CampaignService.create_campaign')
    def test_create_campaign(self, mock_create, client, app):
        """Test creating campaign via POST"""
        with app.app_context():
            mock_campaign = Campaign(id=1, name='Test')
            mock_create.return_value = mock_campaign
            
            response = client.post('/campaigns/new', data={
                'name': 'Test Campaign',
                'message_template': 'Hello',
                'target_audience': 'all'
            }, follow_redirects=True)
            
            assert response.status_code == 200
            mock_create.assert_called_once()
    
    def test_campaign_lists_page(self, client):
        """Test campaign lists page"""
        response = client.get('/campaigns/lists')
        assert response.status_code == 200
        assert b'Campaign Lists' in response.data
    
    def test_new_list_page(self, client):
        """Test new list page"""
        response = client.get('/campaigns/lists/new')
        assert response.status_code == 200
        assert b'Create New List' in response.data
    
    def test_import_csv_page(self, client):
        """Test import CSV page"""
        response = client.get('/campaigns/import-csv')
        assert response.status_code == 200
        assert b'Import' in response.data


class TestAuthRoutes:
    """Test authentication routes"""
    
    @patch('services.quickbooks_service.QuickBooksService')
    def test_quickbooks_auth_redirect(self, mock_qb, client):
        """Test QuickBooks OAuth initiation"""
        mock_instance = Mock()
        mock_instance.get_authorization_url.return_value = 'https://oauth.example.com'
        mock_qb.return_value = mock_instance
        
        response = client.get('/auth/quickbooks')
        assert response.status_code == 302
        assert response.location == 'https://oauth.example.com'
    
    def test_quickbooks_callback_no_state(self, client):
        """Test OAuth callback without state"""
        response = client.get('/auth/quickbooks/callback?code=test')
        assert response.status_code == 302
        assert response.location.endswith('/settings')
    
    def test_quickbooks_disconnect_get(self, client):
        """Test GET request to disconnect endpoint"""
        response = client.get('/auth/quickbooks/disconnect')
        assert response.status_code == 405  # Method not allowed
    
    def test_quickbooks_disconnect_post(self, client, app):
        """Test POST to disconnect"""
        with app.app_context():
            response = client.post('/auth/quickbooks/disconnect')
            assert response.status_code == 302
            assert response.location.endswith('/quickbooks')


class TestSettingsRoutes:
    """Test settings routes"""
    
    def test_quickbooks_settings_page(self, client):
        """Test QuickBooks settings page"""
        response = client.get('/quickbooks')
        assert response.status_code == 200
        assert b'QuickBooks Integration' in response.data
    
    @patch('services.quickbooks_service.QuickBooksService')
    def test_quickbooks_settings_authenticated(self, mock_qb, client, app):
        """Test QuickBooks settings when authenticated"""
        with app.app_context():
            # Mock authenticated service
            mock_instance = Mock()
            mock_instance.is_authenticated.return_value = True
            mock_instance.get_company_info.return_value = {
                'CompanyInfo': {
                    'CompanyName': 'Test Company',
                    'Country': 'US'
                }
            }
            mock_qb.return_value = mock_instance
            
            response = client.get('/quickbooks')
            assert response.status_code == 200
            assert b'Connected to QuickBooks' in response.data
            assert b'Test Company' in response.data
    
    @patch('services.quickbooks_sync_service.QuickBooksSyncService')
    def test_quickbooks_sync(self, mock_sync, client, app):
        """Test QuickBooks sync endpoint"""
        with app.app_context():
            # Add auth record
            auth = QuickBooksAuth(
                company_id='test_company',
                access_token='encrypted',
                refresh_token='encrypted',
                expires_at=db.func.now()
            )
            db.session.add(auth)
            db.session.commit()
            
            mock_sync_instance = Mock()
            mock_sync_instance.sync_all.return_value = None
            mock_sync.return_value = mock_sync_instance
            
            response = client.post('/quickbooks/sync', data={
                'sync_type': 'all'
            })
            
            assert response.status_code == 302
            mock_sync_instance.sync_all.assert_called_once()


class TestGrowthRoutes:
    """Test growth routes"""
    
    def test_growth_page(self, client):
        """Test growth management page"""
        response = client.get('/growth')
        assert response.status_code == 200
        assert b'Growth' in response.data or b'Lead' in response.data
    
    def test_flags_page(self, client):
        """Test flags page"""
        response = client.get('/flags')
        assert response.status_code == 200
        assert b'Flag' in response.data


class TestAPIRoutes:
    """Test API routes"""
    
    def test_api_contacts(self, client):
        """Test contacts API endpoint"""
        response = client.get('/api/contacts')
        assert response.status_code == 200
        data = response.get_json()
        assert 'success' in data
    
    @patch('services.openphone_webhook_service.OpenPhoneWebhookService.process_webhook')
    def test_openphone_webhook(self, mock_process, client):
        """Test OpenPhone webhook endpoint"""
        mock_process.return_value = {'status': 'success'}
        
        response = client.post('/api/openphone/webhook', 
                               json={'id': 'test_123', 'type': 'message'},
                               headers={'X-Openphone-Signature': 'test_signature'})
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['status'] == 'success'
    
    def test_latest_conversations(self, client):
        """Test latest conversations endpoint"""
        response = client.get('/api/messages/latest_conversations')
        assert response.status_code == 200
        data = response.get_json()
        assert 'conversations' in data
    
    def test_contact_conversation(self, client):
        """Test contact conversation endpoint"""
        response = client.get('/api/contact/1/conversation')
        assert response.status_code == 200
        data = response.get_json()
        assert 'messages' in data


class TestPropertyRoutes:
    """Test property routes"""
    
    def test_properties_index(self, client):
        """Test properties index page"""
        response = client.get('/properties/')
        assert response.status_code == 200
        assert b'Properties' in response.data
    
    def test_add_property_page(self, client):
        """Test add property page"""
        response = client.get('/properties/add')
        assert response.status_code == 200
        assert b'Add' in response.data or b'Property' in response.data
    
    def test_property_detail(self, client):
        """Test property detail page"""
        response = client.get('/properties/1')
        assert response.status_code == 200


class TestJobRoutes:
    """Test job routes"""
    
    def test_jobs_index(self, client):
        """Test jobs index page"""
        response = client.get('/jobs/')
        assert response.status_code == 200
        assert b'Jobs' in response.data or b'job' in response.data
    
    def test_add_job_page(self, client):
        """Test add job page"""
        response = client.get('/jobs/job/add')
        assert response.status_code == 200
        assert b'Add' in response.data or b'Job' in response.data
    
    def test_job_detail(self, client):
        """Test job detail page"""
        response = client.get('/jobs/job/1')
        assert response.status_code == 200


class TestQuoteRoutes:
    """Test quote routes"""
    
    def test_quotes_index(self, client):
        """Test quotes index page"""
        response = client.get('/quotes/')
        assert response.status_code == 200
        assert b'Quotes' in response.data or b'quote' in response.data
    
    def test_add_quote_page(self, client):
        """Test add quote page"""
        response = client.get('/quotes/quote/add')
        assert response.status_code == 200
        assert b'Add' in response.data or b'Quote' in response.data
    
    def test_quote_detail(self, client):
        """Test quote detail page"""
        response = client.get('/quotes/quote/1')
        assert response.status_code == 200


class TestInvoiceRoutes:
    """Test invoice routes"""
    
    def test_invoices_index(self, client):
        """Test invoices index page"""
        response = client.get('/invoices/')
        assert response.status_code == 200
        assert b'Invoices' in response.data or b'invoice' in response.data
    
    def test_add_invoice_page(self, client):
        """Test add invoice page"""
        response = client.get('/invoices/add')
        assert response.status_code == 200
        assert b'Add' in response.data or b'Invoice' in response.data
    
    def test_invoice_detail(self, client):
        """Test invoice detail page"""
        response = client.get('/invoices/1')
        assert response.status_code == 200