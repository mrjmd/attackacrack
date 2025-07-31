"""
Comprehensive tests for routes with proper mocking
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
import json
from flask import url_for, session
from crm_database import db, Contact, Campaign, CampaignList, Property, Job, Quote, Invoice


class TestMainRoutesComprehensive:
    """Comprehensive tests for main routes"""
    
    def test_dashboard(self, client):
        """Test dashboard page"""
        response = client.get('/dashboard')
        assert response.status_code == 200
        assert b'Dashboard' in response.data or b'Overview' in response.data
    
    def test_index_redirect(self, client):
        """Test index redirects to dashboard"""
        response = client.get('/')
        assert response.status_code == 302
        assert response.location.endswith('/dashboard')
    
    def test_settings_page(self, client):
        """Test settings page"""
        response = client.get('/settings')
        assert response.status_code == 200
        assert b'Settings' in response.data
    
    @patch('services.csv_import_service.CSVImportService.import_csv')
    def test_import_csv_post(self, mock_import, client, app):
        """Test CSV import POST"""
        with app.app_context():
            # Create campaign list
            campaign_list = CampaignList(name='Test List')
            db.session.add(campaign_list)
            db.session.commit()
            
            mock_import.return_value = {
                'success': True,
                'imported': 5,
                'errors': 0
            }
            
            data = {
                'file': (b'first_name,phone\\nJohn,5551234567', 'test.csv'),
                'list_id': campaign_list.id
            }
            
            response = client.post('/import_csv', 
                                   data=data,
                                   content_type='multipart/form-data',
                                   follow_redirects=True)
            
            assert response.status_code == 200
            mock_import.assert_called_once()


class TestContactRoutesComprehensive:
    """Comprehensive tests for contact routes"""
    
    def test_contact_list(self, client):
        """Test contact list page"""
        response = client.get('/contacts/')
        assert response.status_code == 200
        assert b'Contacts' in response.data or b'contact' in response.data
    
    def test_contact_detail(self, client):
        """Test contact detail page"""
        response = client.get('/contacts/1')
        assert response.status_code == 200
    
    @patch('services.contact_service.ContactService.add_contact')
    def test_add_contact_post(self, mock_add, client, app):
        """Test adding a contact"""
        with app.app_context():
            mock_contact = Contact(id=2, first_name='New', last_name='Contact')
            mock_add.return_value = mock_contact
            
            response = client.post('/contacts/add', data={
                'first_name': 'New',
                'last_name': 'Contact',
                'phone': '+15551234567',
                'email': 'new@example.com'
            }, follow_redirects=True)
            
            assert response.status_code == 200
            mock_add.assert_called_once()
    
    def test_conversations_page(self, client):
        """Test conversations page"""
        response = client.get('/contacts/conversations')
        assert response.status_code == 200
        assert b'Conversations' in response.data or b'Messages' in response.data


class TestCampaignRoutesComprehensive:
    """Comprehensive tests for campaign routes"""
    
    def test_campaigns_index(self, client):
        """Test campaigns index"""
        response = client.get('/campaigns')
        assert response.status_code == 200
        assert b'Campaigns' in response.data
    
    def test_new_campaign_page(self, client):
        """Test new campaign page"""
        response = client.get('/campaigns/new')
        assert response.status_code == 200
        assert b'Create' in response.data or b'New Campaign' in response.data
    
    @patch('services.campaign_service.CampaignService.create_campaign')
    def test_create_campaign_post(self, mock_create, client, app):
        """Test creating a campaign via POST"""
        with app.app_context():
            mock_campaign = Campaign(id=1, name='Test Campaign')
            mock_create.return_value = mock_campaign
            
            response = client.post('/campaigns/new', data={
                'name': 'Test Campaign',
                'template_a': 'Hello {first_name}!',
                'audience_type': 'all',
                'use_quiet_hours': 'on',
                'quiet_hours_start': '21:00',
                'quiet_hours_end': '09:00'
            }, follow_redirects=True)
            
            assert response.status_code == 200
            mock_create.assert_called_once()
    
    @patch('services.campaign_service.CampaignService.send_campaign')
    def test_send_campaign(self, mock_send, client, app):
        """Test sending a campaign"""
        with app.app_context():
            # Create campaign
            campaign = Campaign(name='Test', status='draft')
            db.session.add(campaign)
            db.session.commit()
            
            mock_send.return_value = True
            
            response = client.post(f'/campaigns/{campaign.id}/send')
            
            assert response.status_code == 302
            mock_send.assert_called_once_with(campaign.id)
    
    def test_campaign_lists_index(self, client):
        """Test campaign lists page"""
        response = client.get('/campaigns/lists')
        assert response.status_code == 200
        assert b'Lists' in response.data


class TestAPIRoutesComprehensive:
    """Comprehensive tests for API routes"""
    
    @patch('services.contact_service.ContactService.get_all_contacts')
    def test_api_contacts(self, mock_get_contacts, client):
        """Test contacts API"""
        mock_get_contacts.return_value = [
            Contact(id=1, first_name='Test', last_name='User')
        ]
        
        response = client.get('/api/contacts')
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['success'] is True
        assert len(data['contacts']) == 1
    
    @patch('services.openphone_webhook_service.OpenPhoneWebhookService.process_webhook')
    def test_openphone_webhook_valid(self, mock_process, client):
        """Test valid webhook"""
        mock_process.return_value = {'status': 'success', 'activity_id': 123}
        
        webhook_data = {
            'id': 'test_123',
            'type': 'message',
            'from': '+15551234567',
            'body': 'Test message'
        }
        
        response = client.post('/api/openphone/webhook',
                               json=webhook_data,
                               headers={'X-Openphone-Signature': 'valid_signature'})
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'success'
    
    def test_openphone_webhook_no_signature(self, client):
        """Test webhook without signature"""
        response = client.post('/api/openphone/webhook',
                               json={'test': 'data'})
        
        assert response.status_code == 401
    
    @patch('services.message_service.MessageService.get_latest_conversations')
    def test_latest_conversations_api(self, mock_get_convos, client):
        """Test latest conversations API"""
        mock_get_convos.return_value = [
            {
                'contact_name': 'Test User',
                'last_message': 'Hello',
                'timestamp': '2024-01-01T12:00:00Z'
            }
        ]
        
        response = client.get('/api/messages/latest_conversations')
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert 'conversations' in data
        assert len(data['conversations']) == 1


class TestPropertyRoutesComprehensive:
    """Comprehensive tests for property routes"""
    
    def test_properties_list(self, client):
        """Test properties list page"""
        response = client.get('/properties/')
        assert response.status_code == 200
        assert b'Properties' in response.data or b'properties' in response.data
    
    def test_property_detail(self, client):
        """Test property detail page"""
        response = client.get('/properties/1')
        assert response.status_code == 200
    
    @patch('services.property_service.PropertyService.add_property')
    def test_add_property_post(self, mock_add, client, app):
        """Test adding a property"""
        with app.app_context():
            mock_property = Property(id=2, address='456 Test Ave')
            mock_add.return_value = mock_property
            
            response = client.post('/properties/add', data={
                'address': '456 Test Ave',
                'contact_id': '1'
            }, follow_redirects=True)
            
            assert response.status_code == 200


class TestJobRoutesComprehensive:
    """Comprehensive tests for job routes"""
    
    def test_jobs_list(self, client):
        """Test jobs list page"""
        response = client.get('/jobs/')
        assert response.status_code == 200
    
    def test_job_detail(self, client):
        """Test job detail page"""
        response = client.get('/jobs/job/1')
        assert response.status_code == 200
    
    @patch('services.job_service.JobService.add_job')
    def test_add_job_post(self, mock_add, client, app):
        """Test adding a job"""
        with app.app_context():
            mock_job = Job(id=2, description='New Job')
            mock_add.return_value = mock_job
            
            response = client.post('/jobs/job/add', data={
                'description': 'New Job',
                'property_id': '1',
                'status': 'Active'
            }, follow_redirects=True)
            
            assert response.status_code == 200


class TestQuoteRoutesComprehensive:
    """Comprehensive tests for quote routes"""
    
    def test_quotes_list(self, client):
        """Test quotes list page"""
        response = client.get('/quotes/')
        assert response.status_code == 200
    
    def test_quote_detail(self, client):
        """Test quote detail page"""
        response = client.get('/quotes/quote/1')
        assert response.status_code == 200
    
    @patch('services.quote_service.QuoteService.create_quote')
    def test_add_quote_post(self, mock_create, client, app):
        """Test adding a quote"""
        with app.app_context():
            mock_quote = Quote(id=2, subtotal=100, total_amount=100)
            mock_create.return_value = mock_quote
            
            response = client.post('/quotes/quote/add', data={
                'job_id': '1',
                'line_items-0-description': 'Test Item',
                'line_items-0-quantity': '1',
                'line_items-0-price': '100.00'
            }, follow_redirects=True)
            
            assert response.status_code == 200


class TestInvoiceRoutesComprehensive:
    """Comprehensive tests for invoice routes"""
    
    def test_invoices_list(self, client):
        """Test invoices list page"""
        response = client.get('/invoices/')
        assert response.status_code == 200
    
    def test_invoice_detail(self, client):
        """Test invoice detail page"""
        response = client.get('/invoices/1')
        assert response.status_code == 200
    
    @patch('services.invoice_service.InvoiceService.create_invoice')
    def test_add_invoice_post(self, mock_create, client, app):
        """Test adding an invoice"""
        with app.app_context():
            mock_invoice = Invoice(id=2, subtotal=100, total_amount=100)
            mock_create.return_value = mock_invoice
            
            response = client.post('/invoices/add', data={
                'job_id': '1',
                'due_date': '2024-12-31',
                'line_items-0-description': 'Test Item',
                'line_items-0-quantity': '1',
                'line_items-0-unit_price': '100.00'
            }, follow_redirects=True)
            
            assert response.status_code == 200


class TestSettingsRoutesComprehensive:
    """Comprehensive tests for settings routes"""
    
    @patch('services.quickbooks_service.QuickBooksService')
    def test_quickbooks_settings(self, mock_qb, client):
        """Test QuickBooks settings page"""
        mock_instance = Mock()
        mock_instance.is_authenticated.return_value = False
        mock_qb.return_value = mock_instance
        
        response = client.get('/quickbooks')
        assert response.status_code == 200
        assert b'QuickBooks' in response.data
    
    @patch('services.quickbooks_service.QuickBooksService')
    @patch('services.quickbooks_sync_service.QuickBooksSyncService')
    def test_quickbooks_sync_authenticated(self, mock_sync_service, mock_qb_service, client, app):
        """Test QuickBooks sync when authenticated"""
        with app.app_context():
            # Mock authenticated QuickBooks
            mock_qb = Mock()
            mock_qb.is_authenticated.return_value = True
            mock_qb_service.return_value = mock_qb
            
            # Mock sync service
            mock_sync = Mock()
            mock_sync.sync_all.return_value = None
            mock_sync_service.return_value = mock_sync
            
            response = client.post('/quickbooks/sync', data={
                'sync_type': 'all'
            })
            
            # Should redirect
            assert response.status_code == 302
    
    def test_automation_settings(self, client):
        """Test automation settings page"""
        response = client.get('/settings/automation')
        assert response.status_code == 200
        assert b'Automation' in response.data or b'Automated' in response.data