"""
Comprehensive tests for services with proper mocking
"""
import pytest
from unittest.mock import Mock, patch, MagicMock, mock_open
from datetime import datetime, date, timedelta
import json
import pandas as pd
from io import StringIO

from crm_database import db, Contact, Campaign, CampaignList, CampaignMembership, Activity, Conversation
from services.openphone_webhook_service import OpenPhoneWebhookService
from services.campaign_service import CampaignService  
from services.campaign_list_service import CampaignListService
from services.csv_import_service import CSVImportService
from services.message_service import MessageService
from services.property_service import PropertyService
from services.invoice_service import InvoiceService
from services.ai_service import AIService


class TestOpenPhoneWebhookServiceComprehensive:
    """Comprehensive tests for webhook service"""
    
    @pytest.fixture
    def webhook_service(self, app):
        with app.app_context():
            yield OpenPhoneWebhookService()
    
    def test_process_message_webhook(self, webhook_service, app):
        """Test processing a message webhook"""
        with app.app_context():
            webhook_data = {
                'id': 'msg_test_123',
                'type': 'message',
                'object': 'message',
                'phoneNumberId': 'PN123',
                'conversationId': 'conv_123', 
                'from': '+15551234567',
                'to': ['+16176681677'],
                'body': 'Test message',
                'direction': 'incoming',
                'status': 'delivered',
                'createdAt': '2024-01-01T12:00:00Z'
            }
            
            result = webhook_service.process_webhook(webhook_data)
            
            assert result['status'] == 'success'
            assert 'activity_id' in result
            
            # Verify activity was created
            activity = Activity.query.filter_by(openphone_id='msg_test_123').first()
            assert activity is not None
            assert activity.body == 'Test message'
    
    def test_process_call_webhook(self, webhook_service, app):
        """Test processing a call webhook"""
        with app.app_context():
            webhook_data = {
                'id': 'call_test_123',
                'type': 'call',
                'object': 'call',
                'phoneNumberId': 'PN123',
                'conversationId': 'conv_123',
                'from': '+15551234567',
                'to': '+16176681677',
                'direction': 'incoming',
                'status': 'completed',
                'duration': 120,
                'createdAt': '2024-01-01T12:00:00Z'
            }
            
            result = webhook_service.process_webhook(webhook_data)
            
            assert result['status'] == 'success'
            
            # Verify activity was created
            activity = Activity.query.filter_by(openphone_id='call_test_123').first()
            assert activity is not None
            assert activity.activity_type == 'call'
            assert activity.call_duration == 120
    
    def test_duplicate_webhook(self, webhook_service, app):
        """Test handling duplicate webhooks"""
        with app.app_context():
            webhook_data = {
                'id': 'dup_test_123',
                'type': 'message',
                'from': '+15551234567',
                'to': ['+16176681677'],
                'body': 'Test',
                'direction': 'incoming',
                'createdAt': '2024-01-01T12:00:00Z'
            }
            
            # Process first time
            result1 = webhook_service.process_webhook(webhook_data)
            assert result1['status'] == 'success'
            
            # Process duplicate
            result2 = webhook_service.process_webhook(webhook_data)
            assert result2['status'] == 'skipped'
            assert result2['reason'] == 'duplicate'


class TestCampaignServiceComprehensive:
    """Comprehensive tests for campaign service"""
    
    @pytest.fixture
    def campaign_service(self, app):
        with app.app_context():
            yield CampaignService()
    
    @pytest.fixture
    def sample_contacts(self, app):
        with app.app_context():
            contacts = []
            for i in range(3):
                contact = Contact(
                    first_name=f'Test{i}',
                    last_name=f'User{i}',
                    phone=f'+1555000100{i}'
                )
                db.session.add(contact)
                contacts.append(contact)
            db.session.commit()
            return contacts
    
    def test_create_campaign_basic(self, campaign_service, app):
        """Test creating a basic campaign"""
        with app.app_context():
            data = {
                'name': 'Test Campaign',
                'template_a': 'Hello {first_name}!',
                'audience_type': 'all'
            }
            
            campaign = campaign_service.create_campaign(data)
            
            assert campaign is not None
            assert campaign.name == 'Test Campaign'
            assert campaign.template_a == 'Hello {first_name}!'
            assert campaign.status == 'draft'
    
    @patch('services.openphone_service.OpenPhoneService.send_sms')
    def test_send_campaign(self, mock_send_sms, campaign_service, sample_contacts, app):
        """Test sending a campaign"""
        mock_send_sms.return_value = {'success': True}
        
        with app.app_context():
            # Create campaign
            campaign = Campaign(
                name='Test Send',
                template_a='Hello {first_name}!',
                audience_type='all',
                status='draft'
            )
            db.session.add(campaign)
            db.session.commit()
            
            # Send campaign
            result = campaign_service.send_campaign(campaign.id)
            
            assert result is True
            assert campaign.status == 'sent'
            
            # Verify messages were sent
            assert mock_send_sms.call_count == len(sample_contacts)
    
    def test_get_campaign_stats(self, campaign_service, app):
        """Test getting campaign statistics"""
        with app.app_context():
            # Create campaign with memberships
            campaign = Campaign(name='Stats Test', status='sent')
            db.session.add(campaign)
            db.session.commit()
            
            # Add memberships
            for i in range(5):
                membership = CampaignMembership(
                    campaign_id=campaign.id,
                    contact_id=1,  # Use seeded contact
                    status='sent' if i < 3 else 'failed'
                )
                db.session.add(membership)
            db.session.commit()
            
            stats = campaign_service.get_campaign_stats(campaign.id)
            
            assert stats['total_recipients'] == 5
            assert stats['sent'] == 3
            assert stats['failed'] == 2


class TestCampaignListServiceComprehensive:
    """Comprehensive tests for campaign list service"""
    
    @pytest.fixture
    def list_service(self, app):
        with app.app_context():
            yield CampaignListService()
    
    def test_create_list(self, list_service, app):
        """Test creating a campaign list"""
        with app.app_context():
            data = {
                'name': 'VIP Customers',
                'description': 'High value customers'
            }
            
            campaign_list = list_service.create_list(data)
            
            assert campaign_list is not None
            assert campaign_list.name == 'VIP Customers'
            assert campaign_list.description == 'High value customers'
    
    def test_add_remove_contacts(self, list_service, app):
        """Test adding and removing contacts from list"""
        with app.app_context():
            # Create list
            campaign_list = list_service.create_list({'name': 'Test List'})
            
            # Add contact
            result = list_service.add_contact_to_list(campaign_list.id, 1)
            assert result is True
            
            # Verify contact is in list
            members = list_service.get_list_members(campaign_list.id)
            assert len(members) == 1
            
            # Remove contact
            result = list_service.remove_contact_from_list(campaign_list.id, 1)
            assert result is True
            
            # Verify contact removed
            members = list_service.get_list_members(campaign_list.id)
            assert len(members) == 0


class TestCSVImportServiceComprehensive:
    """Comprehensive tests for CSV import service"""
    
    @pytest.fixture
    def csv_service(self, app):
        with app.app_context():
            yield CSVImportService()
    
    def test_import_valid_csv(self, csv_service, app):
        """Test importing a valid CSV"""
        with app.app_context():
            # Create campaign list
            campaign_list = CampaignList(name='Import Test')
            db.session.add(campaign_list)
            db.session.commit()
            
            # Create CSV data
            csv_data = StringIO(
                "first_name,last_name,phone\\n"
                "John,Doe,5551234567\\n"
                "Jane,Smith,5551234568"
            )
            
            result = csv_service.import_csv(csv_data, 'test.csv', campaign_list.id)
            
            assert result['imported'] == 2
            assert result['errors'] == 0
            
            # Verify contacts created
            john = Contact.query.filter_by(phone='+15551234567').first()
            assert john is not None
            assert john.first_name == 'John'
    
    def test_phone_normalization(self, csv_service, app):
        """Test phone number normalization"""
        with app.app_context():
            # Test various formats
            assert csv_service._normalize_phone_number('5551234567') == '+15551234567'
            assert csv_service._normalize_phone_number('(555) 123-4567') == '+15551234567'
            assert csv_service._normalize_phone_number('+1 555 123 4567') == '+15551234567'
            assert csv_service._normalize_phone_number('invalid') is None


class TestMessageServiceComprehensive:
    """Comprehensive tests for message service"""
    
    @pytest.fixture
    def message_service(self, app):
        with app.app_context():
            yield MessageService()
    
    @patch('services.openphone_service.OpenPhoneService.send_sms')
    def test_send_message(self, mock_send_sms, message_service, app):
        """Test sending a message"""
        mock_send_sms.return_value = {'success': True, 'id': 'msg_123'}
        
        with app.app_context():
            result = message_service.send_message(
                to_number='+15551234567',
                message='Test message',
                contact_id=1
            )
            
            assert result['success'] is True
            assert result['id'] == 'msg_123'
            mock_send_sms.assert_called_once_with('+15551234567', 'Test message')
    
    def test_format_phone_number(self, message_service, app):
        """Test phone number formatting"""
        with app.app_context():
            assert message_service._format_phone_number('5551234567') == '+15551234567'
            assert message_service._format_phone_number('+15551234567') == '+15551234567'
            assert message_service._format_phone_number('555-123-4567') == '+15551234567'


class TestPropertyServiceComprehensive:
    """Comprehensive tests for property service"""
    
    @pytest.fixture
    def property_service(self, app):
        with app.app_context():
            yield PropertyService()
    
    def test_get_all_properties(self, property_service, app):
        """Test getting all properties"""
        with app.app_context():
            properties = property_service.get_all_properties()
            assert isinstance(properties, list)
            # Should have seeded property
            assert len(properties) >= 1
    
    def test_get_property_by_id(self, property_service, app):
        """Test getting property by ID"""
        with app.app_context():
            # Get seeded property
            prop = property_service.get_property_by_id(1)
            assert prop is not None
            assert prop.id == 1
            
            # Non-existent
            prop = property_service.get_property_by_id(99999)
            assert prop is None


class TestAIServiceComprehensive:
    """Comprehensive tests for AI service"""
    
    @pytest.fixture  
    def ai_service(self, app):
        with app.app_context():
            with patch.dict('os.environ', {'GEMINI_API_KEY': 'test_key'}):
                yield AIService()
    
    @patch('google.generativeai.GenerativeModel')
    def test_summarize_conversation(self, mock_model, ai_service, app):
        """Test conversation summarization"""
        # Mock the AI response
        mock_response = Mock()
        mock_response.text = '{"summary": "Customer inquired about services"}'
        mock_instance = Mock()
        mock_instance.generate_content.return_value = mock_response
        mock_model.return_value = mock_instance
        
        with app.app_context():
            messages = [
                {'from': 'customer', 'body': 'Hi, I need help'},
                {'from': 'agent', 'body': 'How can I help you?'}
            ]
            
            result = ai_service.summarize_conversation(messages)
            
            assert result == {"summary": "Customer inquired about services"}
            mock_instance.generate_content.assert_called_once()
    
    @patch('google.generativeai.GenerativeModel')
    def test_extract_address(self, mock_model, ai_service, app):
        """Test address extraction"""
        mock_response = Mock()
        mock_response.text = '{"address": "123 Main St, City, State 12345"}'
        mock_instance = Mock()
        mock_instance.generate_content.return_value = mock_response
        mock_model.return_value = mock_instance
        
        with app.app_context():
            result = ai_service.extract_address("I live at 123 Main St")
            assert result == "123 Main St, City, State 12345"