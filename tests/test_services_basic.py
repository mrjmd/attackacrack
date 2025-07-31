"""
Basic tests for services to improve coverage
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, date, timedelta
import pandas as pd
from io import StringIO

# Import services
from services.quickbooks_service import QuickBooksService
from services.invoice_service import InvoiceService
from services.campaign_service import CampaignService
from services.csv_import_service import CSVImportService
from services.openphone_webhook_service import OpenPhoneWebhookService
from services.campaign_list_service import CampaignListService

# Import models
from crm_database import db, Contact, Invoice, Campaign, CampaignMembership, CampaignList


class TestQuickBooksServiceBasic:
    """Basic tests for QuickBooks service"""
    
    def test_initialization(self, app):
        """Test service initialization"""
        with app.app_context():
            with patch.dict('os.environ', {
                'QUICKBOOKS_CLIENT_ID': 'test_id',
                'QUICKBOOKS_CLIENT_SECRET': 'test_secret',
                'QUICKBOOKS_SANDBOX': 'True'
            }):
                service = QuickBooksService()
                assert service.client_id == 'test_id'
                assert service.sandbox is True
    
    def test_get_authorization_url(self, app):
        """Test OAuth URL generation"""
        with app.app_context():
            with patch.dict('os.environ', {
                'QUICKBOOKS_CLIENT_ID': 'test_id',
                'QUICKBOOKS_CLIENT_SECRET': 'test_secret'
            }):
                service = QuickBooksService()
                url = service.get_authorization_url('test_state')
                assert 'client_id=test_id' in url
                assert 'state=test_state' in url
    
    def test_is_authenticated_false(self, app):
        """Test authentication check when not authenticated"""
        with app.app_context():
            service = QuickBooksService()
            assert service.is_authenticated() is False


class TestInvoiceServiceBasic:
    """Basic tests for Invoice service"""
    
    def test_get_all_invoices(self, app):
        """Test getting all invoices"""
        with app.app_context():
            service = InvoiceService()
            invoices = service.get_all_invoices()
            assert isinstance(invoices, list)
    
    def test_get_invoice_by_id(self, app):
        """Test getting invoice by ID"""
        with app.app_context():
            service = InvoiceService()
            # Test with seeded invoice
            invoice = service.get_invoice_by_id(1)
            assert invoice is not None
            assert invoice.id == 1
            
            # Test non-existent
            invoice = service.get_invoice_by_id(99999)
            assert invoice is None
    
    def test_create_invoice_minimal(self, app):
        """Test creating minimal invoice"""
        with app.app_context():
            service = InvoiceService()
            data = {
                'job_id': 1,
                'due_date': date.today() + timedelta(days=30)
            }
            invoice = service.create_invoice(data)
            assert invoice is not None
            assert invoice.job_id == 1
            assert invoice.subtotal == 0
    
    def test_delete_invoice(self, app):
        """Test deleting invoice"""
        with app.app_context():
            service = InvoiceService()
            # Create invoice
            data = {
                'job_id': 1,
                'due_date': date.today() + timedelta(days=30)
            }
            invoice = service.create_invoice(data)
            invoice_id = invoice.id
            
            # Delete it
            result = service.delete_invoice(invoice_id)
            assert result is True
            
            # Verify deleted
            assert service.get_invoice_by_id(invoice_id) is None


class TestCampaignServiceBasic:
    """Basic tests for Campaign service"""
    
    def test_create_campaign(self, app):
        """Test creating a campaign"""
        with app.app_context():
            service = CampaignService()
            data = {
                'name': 'Test Campaign',
                'message_template': 'Hello {first_name}',
                'target_audience': 'all'
            }
            campaign = service.create_campaign(data)
            assert campaign is not None
            assert campaign.name == 'Test Campaign'
            assert campaign.status == 'draft'
    
    def test_get_all_campaigns(self, app):
        """Test getting all campaigns"""
        with app.app_context():
            service = CampaignService()
            campaigns = service.get_all_campaigns()
            assert isinstance(campaigns, list)
    
    def test_get_campaign_by_id(self, app):
        """Test getting campaign by ID"""
        with app.app_context():
            service = CampaignService()
            # Create campaign
            data = {'name': 'Test', 'message_template': 'Test', 'target_audience': 'all'}
            campaign = service.create_campaign(data)
            
            # Get it
            found = service.get_campaign_by_id(campaign.id)
            assert found is not None
            assert found.id == campaign.id
    
    def test_update_campaign(self, app):
        """Test updating campaign"""
        with app.app_context():
            service = CampaignService()
            # Create campaign
            campaign = service.create_campaign({
                'name': 'Original',
                'message_template': 'Test',
                'target_audience': 'all'
            })
            
            # Update it
            updated = service.update_campaign(campaign.id, {'name': 'Updated'})
            assert updated.name == 'Updated'
    
    def test_delete_campaign(self, app):
        """Test deleting campaign"""
        with app.app_context():
            service = CampaignService()
            # Create campaign
            campaign = service.create_campaign({
                'name': 'To Delete',
                'message_template': 'Test',
                'target_audience': 'all'
            })
            
            # Delete it
            result = service.delete_campaign(campaign.id)
            assert result is True
    
    def test_personalize_message(self, app):
        """Test message personalization"""
        with app.app_context():
            service = CampaignService()
            contact = Contact(first_name='John', last_name='Doe')
            template = "Hello {first_name} {last_name}!"
            result = service._personalize_message(template, contact)
            assert result == "Hello John Doe!"
    
    def test_get_campaign_stats(self, app):
        """Test getting campaign statistics"""
        with app.app_context():
            service = CampaignService()
            # Create campaign
            campaign = service.create_campaign({
                'name': 'Stats Test',
                'message_template': 'Test',
                'target_audience': 'all'
            })
            
            stats = service.get_campaign_stats(campaign.id)
            assert 'total_recipients' in stats
            assert 'sent' in stats
            assert 'failed' in stats
            assert 'success_rate' in stats


class TestCSVImportServiceBasic:
    """Basic tests for CSV Import service"""
    
    def test_import_csv_empty(self, app):
        """Test importing empty CSV"""
        with app.app_context():
            service = CSVImportService()
            csv_data = StringIO("")
            
            # Create list
            campaign_list = CampaignList(name='Test List')
            db.session.add(campaign_list)
            db.session.commit()
            
            result = service.import_csv(csv_data, 'empty.csv', campaign_list.id)
            assert result['success'] is False
    
    def test_import_csv_missing_phone(self, app):
        """Test importing CSV without phone column"""
        with app.app_context():
            service = CSVImportService()
            csv_data = StringIO("first_name,last_name\\nJohn,Doe")
            
            # Create list
            campaign_list = CampaignList(name='Test List')
            db.session.add(campaign_list)
            db.session.commit()
            
            result = service.import_csv(csv_data, 'test.csv', campaign_list.id)
            assert result['success'] is False
            assert 'phone' in result['message']
    
    def test_normalize_phone_number(self, app):
        """Test phone normalization"""
        with app.app_context():
            service = CSVImportService()
            assert service._normalize_phone_number('5551234567') == '+15551234567'
            assert service._normalize_phone_number('invalid') is None
    
    def test_get_import_history(self, app):
        """Test getting import history"""
        with app.app_context():
            service = CSVImportService()
            history = service.get_import_history()
            assert isinstance(history, list)


class TestOpenPhoneWebhookServiceBasic:
    """Basic tests for webhook service"""
    
    def test_process_webhook_invalid(self, app):
        """Test processing invalid webhook"""
        with app.app_context():
            service = OpenPhoneWebhookService()
            result = service.process_webhook({})
            assert result['status'] == 'error'
    
    def test_normalize_phone(self, app):
        """Test phone normalization"""
        with app.app_context():
            service = OpenPhoneWebhookService()
            assert service._normalize_phone('+15551234567') == '+15551234567'
            assert service._normalize_phone('5551234567') == '+15551234567'
            assert service._normalize_phone('(555) 123-4567') == '+15551234567'
    
    def test_parse_participant_name(self, app):
        """Test parsing participant names"""
        with app.app_context():
            service = OpenPhoneWebhookService()
            first, last = service._parse_participant_name('John Doe')
            assert first == 'John'
            assert last == 'Doe'
            
            first, last = service._parse_participant_name('')
            assert first == 'Unknown'
            assert last == ''


class TestCampaignListServiceBasic:
    """Basic tests for Campaign List service"""
    
    def test_create_list(self, app):
        """Test creating a campaign list"""
        with app.app_context():
            service = CampaignListService()
            data = {
                'name': 'Test List',
                'description': 'Test description'
            }
            campaign_list = service.create_list(data)
            assert campaign_list is not None
            assert campaign_list.name == 'Test List'
    
    def test_get_all_lists(self, app):
        """Test getting all lists"""
        with app.app_context():
            service = CampaignListService()
            lists = service.get_all_lists()
            assert isinstance(lists, list)
    
    def test_get_list_by_id(self, app):
        """Test getting list by ID"""
        with app.app_context():
            service = CampaignListService()
            # Create list
            campaign_list = service.create_list({'name': 'Test'})
            
            # Get it
            found = service.get_list_by_id(campaign_list.id)
            assert found is not None
            assert found.id == campaign_list.id
    
    def test_delete_list(self, app):
        """Test deleting list"""
        with app.app_context():
            service = CampaignListService()
            # Create list
            campaign_list = service.create_list({'name': 'To Delete'})
            
            # Delete it
            result = service.delete_list(campaign_list.id)
            assert result is True
    
    def test_add_contact_to_list(self, app):
        """Test adding contact to list"""
        with app.app_context():
            service = CampaignListService()
            
            # Create list
            campaign_list = service.create_list({'name': 'Test List'})
            
            # Get seeded contact
            contact = db.session.get(Contact, 1)
            
            # Add contact
            result = service.add_contact_to_list(campaign_list.id, contact.id)
            assert result is True
    
    def test_remove_contact_from_list(self, app):
        """Test removing contact from list"""
        with app.app_context():
            service = CampaignListService()
            
            # Create list and add contact
            campaign_list = service.create_list({'name': 'Test List'})
            contact = db.session.get(Contact, 1)
            service.add_contact_to_list(campaign_list.id, contact.id)
            
            # Remove contact
            result = service.remove_contact_from_list(campaign_list.id, contact.id)
            assert result is True
    
    def test_get_list_members(self, app):
        """Test getting list members"""
        with app.app_context():
            service = CampaignListService()
            
            # Create list
            campaign_list = service.create_list({'name': 'Test List'})
            
            members = service.get_list_members(campaign_list.id)
            assert isinstance(members, list)