"""
Simple tests focusing on achieving coverage for services and routes
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, date, timedelta
import json

from crm_database import db


class TestSimpleServices:
    """Simple service tests that should pass"""
    
    def test_contact_service_basics(self, app):
        """Test ContactService basic operations"""
        with app.app_context():
            from services.contact_service import ContactService
            service = ContactService()
            
            # These should work with seeded data
            contacts = service.get_all_contacts()
            assert isinstance(contacts, list)
            
            contact = service.get_contact_by_id(1)
            assert contact is not None
    
    def test_property_service_basics(self, app):
        """Test PropertyService basic operations"""
        with app.app_context():
            from services.property_service import PropertyService
            service = PropertyService()
            
            properties = service.get_all_properties()
            assert isinstance(properties, list)
            
            prop = service.get_property_by_id(1)
            assert prop is not None
            
            props_for_contact = service.get_properties_for_contact(1)
            assert isinstance(props_for_contact, list)
    
    def test_job_service_basics(self, app):
        """Test JobService basic operations"""
        with app.app_context():
            from services.job_service import JobService
            service = JobService()
            
            jobs = service.get_all_jobs()
            assert isinstance(jobs, list)
            
            job = service.get_job_by_id(1)
            assert job is not None
    
    def test_invoice_service_basics(self, app):
        """Test InvoiceService basic operations"""
        with app.app_context():
            from services.invoice_service import InvoiceService
            service = InvoiceService()
            
            invoices = service.get_all_invoices()
            assert isinstance(invoices, list)
            
            invoice = service.get_invoice_by_id(1)
            assert invoice is not None
    
    def test_quote_service_basics(self, app):
        """Test QuoteService basic operations"""
        with app.app_context():
            from services.quote_service import QuoteService
            service = QuoteService()
            
            quotes = service.get_all_quotes()
            assert isinstance(quotes, list)
            
            quote = service.get_quote_by_id(1)
            assert quote is not None
    
    def test_message_service_basics(self, app):
        """Test MessageService basic operations"""
        with app.app_context():
            from services.message_service import MessageService
            service = MessageService()
            
            # Get latest conversations
            conversations = service.get_latest_conversations_from_db(limit=5)
            assert isinstance(conversations, list)
            
            # Get activities for contact
            activities = service.get_activities_for_contact(1)
            assert isinstance(activities, list)
    
    def test_appointment_service_basics(self, app):
        """Test AppointmentService basic operations"""
        with app.app_context():
            from services.appointment_service import AppointmentService
            service = AppointmentService()
            
            appointments = service.get_all_appointments()
            assert isinstance(appointments, list)
    
    @patch.dict('os.environ', {'QUICKBOOKS_CLIENT_ID': 'test', 'QUICKBOOKS_CLIENT_SECRET': 'test'})
    def test_quickbooks_service_basics(self, app):
        """Test QuickBooksService basic operations"""
        with app.app_context():
            from services.quickbooks_service import QuickBooksService
            service = QuickBooksService()
            
            # Check if authenticated (should be False)
            assert service.is_authenticated() is False
            
            # Get auth URL
            url = service.get_authorization_url()
            assert 'oauth2' in url
    
    def test_campaign_list_service_basics(self, app):
        """Test CampaignListService basic operations"""
        with app.app_context():
            from services.campaign_list_service import CampaignListService
            service = CampaignListService()
            
            lists = service.get_all_lists()
            assert isinstance(lists, list)


class TestSimpleRoutes:
    """Simple route tests that should pass"""
    
    def test_main_routes(self, client):
        """Test main routes"""
        # Index redirects
        response = client.get('/')
        assert response.status_code == 302
        
        # Dashboard
        response = client.get('/dashboard')
        assert response.status_code == 200
        
        # Settings
        response = client.get('/settings')
        assert response.status_code == 200
    
    def test_contact_routes(self, client):
        """Test contact routes"""
        response = client.get('/contacts/')
        assert response.status_code == 200
        
        response = client.get('/contacts/1')
        assert response.status_code == 200
        
        response = client.get('/contacts/add')
        assert response.status_code == 200
        
        response = client.get('/contacts/conversations')
        assert response.status_code == 200
    
    def test_property_routes(self, client):
        """Test property routes"""
        response = client.get('/properties/')
        assert response.status_code == 200
        
        response = client.get('/properties/1')
        assert response.status_code == 200
        
        response = client.get('/properties/add')
        assert response.status_code == 200
    
    def test_job_routes(self, client):
        """Test job routes"""
        response = client.get('/jobs/')
        assert response.status_code == 200
        
        response = client.get('/jobs/job/1')
        assert response.status_code == 200
        
        response = client.get('/jobs/job/add')
        assert response.status_code == 200
    
    def test_quote_routes(self, client):
        """Test quote routes"""
        response = client.get('/quotes/')
        assert response.status_code == 200
        
        response = client.get('/quotes/quote/1')
        assert response.status_code == 200
        
        response = client.get('/quotes/quote/add')
        assert response.status_code == 200
    
    def test_invoice_routes(self, client):
        """Test invoice routes"""
        response = client.get('/invoices/')
        assert response.status_code == 200
        
        response = client.get('/invoices/1')
        assert response.status_code == 200
        
        response = client.get('/invoices/add')
        assert response.status_code == 200
    
    def test_appointment_routes(self, client):
        """Test appointment routes"""
        response = client.get('/appointments/')
        assert response.status_code == 200
        
        response = client.get('/appointments/add')
        assert response.status_code == 200
    
    def test_campaign_routes(self, client):
        """Test campaign routes"""
        response = client.get('/campaigns')
        assert response.status_code == 200
        
        response = client.get('/campaigns/new')
        assert response.status_code == 200
        
        response = client.get('/campaigns/lists')
        assert response.status_code == 200
    
    def test_growth_routes(self, client):
        """Test growth routes"""
        response = client.get('/growth')
        assert response.status_code == 200
        
        response = client.get('/flags')
        assert response.status_code == 200
    
    def test_settings_routes(self, client):
        """Test settings routes"""
        response = client.get('/quickbooks')
        assert response.status_code == 200
        
        response = client.get('/settings/automation')
        assert response.status_code == 200
    
    def test_import_routes(self, client):
        """Test import routes"""
        response = client.get('/import_csv')
        assert response.status_code == 200
        
        response = client.get('/import_property_radar')
        assert response.status_code == 200


class TestAPIEndpoints:
    """Test API endpoints"""
    
    def test_api_basics(self, client):
        """Test basic API endpoints"""
        # Contacts API
        response = client.get('/api/contacts')
        assert response.status_code == 200
        data = response.get_json()
        assert data is not None
        
        # Search API 
        response = client.get('/api/contacts/search?query=test')
        assert response.status_code == 200
        
        # Latest conversations
        response = client.get('/api/messages/latest_conversations')
        assert response.status_code == 200
        
        # Contact conversation
        response = client.get('/api/contact/1/conversation')
        assert response.status_code == 200
    
    def test_webhook_endpoint(self, client):
        """Test webhook endpoint"""
        # Without signature should return 401
        response = client.post('/api/openphone/webhook', json={'test': 'data'})
        assert response.status_code == 401


# Additional focused tests for specific services
class TestServiceMethods:
    """Test specific service methods for coverage"""
    
    def test_campaign_service_methods(self, app):
        """Test CampaignService methods"""
        with app.app_context():
            from services.campaign_service import CampaignService
            from crm_database import Contact
            
            service = CampaignService()
            
            # Test personalize message
            contact = Contact(first_name='Test', last_name='User')
            template = "Hello {first_name}!"
            result = service._personalize_message(template, contact)
            assert "Test" in result
            
            # Test is business hours
            is_business = service._is_business_hours()
            assert isinstance(is_business, bool)
    
    @patch('services.openphone_service.OpenPhoneService')
    def test_openphone_webhook_methods(self, mock_openphone, app):
        """Test OpenPhoneWebhookService methods"""
        with app.app_context():
            from services.openphone_webhook_service import OpenPhoneWebhookService
            
            service = OpenPhoneWebhookService()
            
            # Test phone normalization
            normalized = service._normalize_phone('5551234567')
            assert normalized == '+15551234567'
            
            # Test parse participant name
            first, last = service._parse_participant_name('John Doe')
            assert first == 'John'
            assert last == 'Doe'
            
            # Test empty name
            first, last = service._parse_participant_name('')
            assert first == 'Unknown'
            assert last == ''
    
    def test_csv_import_methods(self, app):
        """Test CSVImportService methods"""
        with app.app_context():
            from services.csv_import_service import CSVImportService
            from services.contact_service import ContactService
            
            service = CSVImportService(ContactService())
            
            # Test phone normalization
            normalized = service._normalize_phone_number('(555) 123-4567')
            assert normalized == '+15551234567'
            
            # Test invalid phone
            normalized = service._normalize_phone_number('invalid')
            assert normalized is None
    
    @patch.dict('os.environ', {'GEMINI_API_KEY': 'test_key'})
    def test_ai_service_init(self, app):
        """Test AIService initialization"""
        with app.app_context():
            from services.ai_service import AIService
            
            # Should initialize without error
            service = AIService()
            assert service is not None