"""
Tests for critical services with low coverage
"""
import pytest
from unittest.mock import Mock, patch, MagicMock, call
from datetime import datetime, date, timedelta
import json
import pandas as pd
from io import StringIO

from crm_database import db


class TestCampaignServiceDetailed:
    """Detailed tests for CampaignService"""
    
    def test_create_campaign_all_types(self, app):
        """Test creating campaigns of all types"""
        with app.app_context():
            from services.campaign_service import CampaignService
            from crm_database import Campaign
            
            service = CampaignService()
            
            # Test blast campaign
            campaign1 = service.create_campaign(
                name='Blast Campaign',
                campaign_type='blast',
                audience_type='cold',
                template_a='Hello {first_name}!'
            )
            assert campaign1.campaign_type == 'blast'
            assert campaign1.audience_type == 'cold'
            
            # Test automated campaign
            campaign2 = service.create_campaign(
                name='Automated Campaign',
                campaign_type='automated',
                audience_type='customer',
                template_a='Welcome back!'
            )
            assert campaign2.campaign_type == 'automated'
            
            # Test A/B test campaign
            campaign3 = service.create_campaign(
                name='AB Test',
                campaign_type='ab_test',
                audience_type='mixed',
                template_a='Version A',
                template_b='Version B'
            )
            assert campaign3.campaign_type == 'ab_test'
            assert campaign3.template_b == 'Version B'
            
            # Clean up
            db.session.query(Campaign).filter(Campaign.id.in_([campaign1.id, campaign2.id, campaign3.id])).delete()
            db.session.commit()
    
    def test_create_campaign_validation(self, app):
        """Test campaign creation validation"""
        with app.app_context():
            from services.campaign_service import CampaignService
            
            service = CampaignService()
            
            # Test invalid campaign type
            with pytest.raises(ValueError, match='Campaign type must be'):
                service.create_campaign(
                    name='Invalid',
                    campaign_type='invalid_type'
                )
            
            # Test invalid audience type
            with pytest.raises(ValueError, match='Audience type must be'):
                service.create_campaign(
                    name='Invalid',
                    audience_type='invalid_audience'
                )
            
            # Test invalid channel
            with pytest.raises(ValueError, match='Channel must be'):
                service.create_campaign(
                    name='Invalid',
                    channel='invalid_channel'
                )
            
            # Test email channel (not supported)
            with pytest.raises(ValueError, match='Email campaigns coming soon'):
                service.create_campaign(
                    name='Email Campaign',
                    channel='email'
                )
            
            # Test A/B test without template_b
            with pytest.raises(ValueError, match='A/B test campaigns require'):
                service.create_campaign(
                    name='AB Test',
                    campaign_type='ab_test',
                    template_a='Only A'
                )
    
    @patch('services.openphone_service.OpenPhoneService')
    def test_campaign_sending_process(self, mock_openphone, app):
        """Test the campaign sending process"""
        with app.app_context():
            from services.campaign_service import CampaignService
            from crm_database import Campaign, Contact, CampaignList, CampaignListMember
            
            # Mock OpenPhone
            mock_instance = Mock()
            mock_instance.send_sms.return_value = ({'success': True, 'id': 'msg_123'}, None)
            mock_openphone.return_value = mock_instance
            
            service = CampaignService()
            
            # Create test contacts
            contact1 = Contact(first_name='Test1', last_name='User1', phone='+15559991111')
            contact2 = Contact(first_name='Test2', last_name='User2', phone='+15559992222')
            db.session.add_all([contact1, contact2])
            db.session.commit()
            
            # Create campaign list
            campaign_list = CampaignList(name='Test Send List')
            db.session.add(campaign_list)
            db.session.commit()
            
            # Add contacts to list
            member1 = CampaignListMember(list_id=campaign_list.id, contact_id=contact1.id)
            member2 = CampaignListMember(list_id=campaign_list.id, contact_id=contact2.id)
            db.session.add_all([member1, member2])
            db.session.commit()
            
            # Create campaign
            campaign = service.create_campaign(
                name='Send Test',
                template_a='Hello {first_name}!',
                audience_type='mixed'
            )
            
            # Add recipients
            count = service.add_recipients_from_list(campaign.id, campaign_list.id)
            assert count == 2
            
            # Start campaign
            result = service.start_campaign(campaign.id)
            assert result is True
            assert campaign.status == 'sending'
            
            # Process queue
            results = service.process_campaign_queue()
            assert results['total_processed'] > 0
            
            # Clean up
            db.session.query(Campaign).filter_by(id=campaign.id).delete()
            db.session.query(CampaignList).filter_by(id=campaign_list.id).delete()
            db.session.query(Contact).filter(Contact.id.in_([contact1.id, contact2.id])).delete()
            db.session.commit()
    
    def test_campaign_analytics(self, app):
        """Test campaign analytics"""
        with app.app_context():
            from services.campaign_service import CampaignService
            from crm_database import Campaign, CampaignMembership
            
            service = CampaignService()
            
            # Create campaign
            campaign = Campaign(
                name='Analytics Test',
                template_a='Test message',
                status='completed'
            )
            db.session.add(campaign)
            db.session.commit()
            
            # Add some memberships with different statuses
            for i in range(5):
                membership = CampaignMembership(
                    campaign_id=campaign.id,
                    contact_id=1,
                    status='sent' if i < 3 else 'failed',
                    message_sent='Test message' if i < 3 else None
                )
                db.session.add(membership)
            db.session.commit()
            
            # Get analytics
            analytics = service.get_campaign_analytics(campaign.id)
            
            assert analytics['campaign_id'] == campaign.id
            assert analytics['total_recipients'] == 5
            assert analytics['sent'] == 3
            assert analytics['failed'] == 2
            assert analytics['delivery_rate'] == 60.0
            
            # Clean up
            db.session.query(CampaignMembership).filter_by(campaign_id=campaign.id).delete()
            db.session.query(Campaign).filter_by(id=campaign.id).delete()
            db.session.commit()
    
    @patch('services.contact_service.ContactService')
    def test_handle_opt_out(self, mock_contact_service, app):
        """Test opt-out handling"""
        with app.app_context():
            from services.campaign_service import CampaignService
            
            # Mock contact service
            mock_contact = Mock(id=1, first_name='John')
            mock_contact_service.return_value.get_contact_by_phone.return_value = mock_contact
            
            service = CampaignService()
            
            # Test opt-out
            result = service.handle_opt_out('+15551234567', 'STOP')
            assert result is True
            
            # Test non-opt-out message
            result = service.handle_opt_out('+15551234567', 'Regular message')
            assert result is False


class TestCSVImportServiceDetailed:
    """Detailed tests for CSVImportService"""
    
    def test_import_csv_full_workflow(self, app):
        """Test full CSV import workflow"""
        with app.app_context():
            from services.csv_import_service import CSVImportService
            from services.contact_service import ContactService
            from crm_database import CampaignList, Contact
            
            # Create campaign list
            campaign_list = CampaignList(name='Import Test List')
            db.session.add(campaign_list)
            db.session.commit()
            
            # Create CSV data
            csv_data = StringIO(
                "first_name,last_name,phone,email,address\n"
                "John,Doe,5558881111,john@example.com,123 Main St\n"
                "Jane,Smith,(555) 888-2222,jane@example.com,456 Oak Ave\n"
                "Invalid,Phone,not_a_phone,invalid@example.com,789 Pine St"
            )
            
            service = CSVImportService(ContactService())
            
            # Import CSV
            result = service.import_csv(csv_data, 'test.csv', campaign_list.id)
            
            assert result['success'] is True
            assert result['imported'] == 2  # 2 valid phone numbers
            assert result['errors'] == 1    # 1 invalid phone
            
            # Verify contacts created
            john = Contact.query.filter_by(phone='+15558881111').first()
            assert john is not None
            assert john.first_name == 'John'
            assert john.email == 'john@example.com'
            
            jane = Contact.query.filter_by(phone='+15558882222').first()
            assert jane is not None
            assert jane.first_name == 'Jane'
            
            # Clean up
            db.session.query(Contact).filter(Contact.phone.in_(['+15558881111', '+15558882222'])).delete()
            db.session.query(CampaignList).filter_by(id=campaign_list.id).delete()
            db.session.commit()
    
    def test_csv_validation(self, app):
        """Test CSV validation"""
        with app.app_context():
            from services.csv_import_service import CSVImportService
            from services.contact_service import ContactService
            
            service = CSVImportService(ContactService())
            
            # Test empty CSV
            empty_df = pd.DataFrame()
            valid, msg = service._validate_csv_structure(empty_df)
            assert valid is False
            assert 'empty' in msg.lower()
            
            # Test missing phone column
            no_phone_df = pd.DataFrame({
                'first_name': ['John'],
                'last_name': ['Doe']
            })
            valid, msg = service._validate_csv_structure(no_phone_df)
            assert valid is False
            assert 'phone' in msg
            
            # Test valid CSV
            valid_df = pd.DataFrame({
                'first_name': ['John'],
                'phone': ['5551234567']
            })
            valid, msg = service._validate_csv_structure(valid_df)
            assert valid is True
    
    def test_contact_enrichment(self, app):
        """Test enriching existing contacts"""
        with app.app_context():
            from services.csv_import_service import CSVImportService
            from services.contact_service import ContactService
            from crm_database import Contact, CampaignList
            
            # Create existing contact with minimal info
            contact = Contact(
                first_name='John',
                last_name='',
                phone='+15557777777',
                email=None
            )
            db.session.add(contact)
            db.session.commit()
            
            # Create campaign list
            campaign_list = CampaignList(name='Enrichment Test')
            db.session.add(campaign_list)
            db.session.commit()
            
            # Import CSV with additional data
            csv_data = StringIO(
                "first_name,last_name,phone,email,company\n"
                "John,Doe,5557777777,john.doe@example.com,Acme Corp"
            )
            
            service = CSVImportService(ContactService())
            result = service.import_csv(csv_data, 'enrich.csv', campaign_list.id)
            
            assert result['success'] is True
            assert result['updated'] == 1
            
            # Verify contact was enriched
            db.session.refresh(contact)
            assert contact.last_name == 'Doe'
            assert contact.email == 'john.doe@example.com'
            
            # Clean up
            db.session.delete(contact)
            db.session.delete(campaign_list)
            db.session.commit()


class TestOpenPhoneWebhookServiceDetailed:
    """Detailed tests for OpenPhoneWebhookService"""
    
    def test_process_message_webhook(self, app):
        """Test processing message webhooks"""
        with app.app_context():
            from services.openphone_webhook_service import OpenPhoneWebhookService
            from crm_database import Activity, Contact
            
            service = OpenPhoneWebhookService()
            
            # Create test contact
            contact = Contact(
                first_name='Webhook',
                last_name='Test',
                phone='+15556666666'
            )
            db.session.add(contact)
            db.session.commit()
            
            # Process incoming message webhook
            webhook_data = {
                'id': 'msg_test_123',
                'type': 'message',
                'object': 'message',
                'phoneNumberId': 'PN123',
                'conversationId': 'conv_123',
                'from': '+15556666666',
                'to': ['+16176681677'],
                'body': 'Test webhook message',
                'direction': 'incoming',
                'status': 'delivered',
                'createdAt': '2024-01-01T12:00:00Z'
            }
            
            result = service.process_webhook(webhook_data)
            
            assert result['status'] == 'success'
            assert 'activity_id' in result
            
            # Verify activity created
            activity = Activity.query.filter_by(openphone_id='msg_test_123').first()
            assert activity is not None
            assert activity.body == 'Test webhook message'
            assert activity.direction == 'incoming'
            
            # Clean up
            db.session.delete(activity)
            db.session.delete(contact)
            db.session.commit()
    
    def test_process_call_webhook(self, app):
        """Test processing call webhooks"""
        with app.app_context():
            from services.openphone_webhook_service import OpenPhoneWebhookService
            from crm_database import Activity
            
            service = OpenPhoneWebhookService()
            
            # Process call webhook
            webhook_data = {
                'id': 'call_test_456',
                'type': 'call',
                'object': 'call',
                'phoneNumberId': 'PN123',
                'conversationId': 'conv_456',
                'from': '+15557777777',
                'to': '+16176681677',
                'direction': 'outgoing',
                'status': 'completed',
                'duration': 180,
                'recordingUrl': 'https://example.com/recording.mp3',
                'createdAt': '2024-01-01T13:00:00Z'
            }
            
            result = service.process_webhook(webhook_data)
            
            assert result['status'] == 'success'
            
            # Verify activity created
            activity = Activity.query.filter_by(openphone_id='call_test_456').first()
            assert activity is not None
            assert activity.activity_type == 'call'
            assert activity.call_duration == 180
            assert activity.recording_url == 'https://example.com/recording.mp3'
            
            # Clean up
            db.session.delete(activity)
            db.session.commit()
    
    def test_webhook_duplicate_handling(self, app):
        """Test duplicate webhook handling"""
        with app.app_context():
            from services.openphone_webhook_service import OpenPhoneWebhookService
            
            service = OpenPhoneWebhookService()
            
            webhook_data = {
                'id': 'dup_test_789',
                'type': 'message',
                'from': '+15558888888',
                'to': ['+16176681677'],
                'body': 'Duplicate test',
                'direction': 'incoming',
                'createdAt': '2024-01-01T14:00:00Z'
            }
            
            # Process first time
            result1 = service.process_webhook(webhook_data)
            assert result1['status'] == 'success'
            
            # Process duplicate
            result2 = service.process_webhook(webhook_data)
            assert result2['status'] == 'skipped'
            assert result2['reason'] == 'duplicate'


class TestAIServiceDetailed:
    """Detailed tests for AIService"""
    
    @patch('google.generativeai.GenerativeModel')
    def test_summarize_conversation(self, mock_model, app):
        """Test conversation summarization"""
        with app.app_context():
            from services.ai_service import AIService
            
            # Mock AI response
            mock_response = Mock()
            mock_response.text = '{"summary": "Customer inquired about pricing and delivery options"}'
            mock_instance = Mock()
            mock_instance.generate_content.return_value = mock_response
            mock_model.return_value = mock_instance
            
            # Initialize service with mocked API key
            with patch.dict('os.environ', {'GEMINI_API_KEY': 'test_key'}):
                service = AIService()
            
            messages = [
                {'from': 'customer', 'body': 'How much does it cost?'},
                {'from': 'agent', 'body': 'Our service starts at $99/month'},
                {'from': 'customer', 'body': 'When can you deliver?'},
                {'from': 'agent', 'body': 'We can deliver within 2-3 business days'}
            ]
            
            result = service.summarize_conversation(messages)
            
            assert 'summary' in result
            assert 'pricing' in result['summary'].lower()
            assert 'delivery' in result['summary'].lower()
    
    @patch('google.generativeai.GenerativeModel')
    def test_extract_address(self, mock_model, app):
        """Test address extraction"""
        with app.app_context():
            from services.ai_service import AIService
            
            # Mock AI response
            mock_response = Mock()
            mock_response.text = '{"address": "123 Main Street, Springfield, IL 62701"}'
            mock_instance = Mock()
            mock_instance.generate_content.return_value = mock_response
            mock_model.return_value = mock_instance
            
            with patch.dict('os.environ', {'GEMINI_API_KEY': 'test_key'}):
                service = AIService()
            
            text = "I live at 123 Main Street in Springfield, Illinois 62701"
            result = service.extract_address(text)
            
            assert result == "123 Main Street, Springfield, IL 62701"
    
    @patch('google.generativeai.GenerativeModel')
    def test_ai_error_handling(self, mock_model, app):
        """Test AI service error handling"""
        with app.app_context():
            from services.ai_service import AIService
            
            # Mock AI error
            mock_instance = Mock()
            mock_instance.generate_content.side_effect = Exception("API Error")
            mock_model.return_value = mock_instance
            
            with patch.dict('os.environ', {'GEMINI_API_KEY': 'test_key'}):
                service = AIService()
            
            # Should handle error gracefully
            result = service.summarize_conversation([{'from': 'test', 'body': 'test'}])
            assert result == {"error": "Failed to summarize conversation"}


class TestQuickBooksServiceDetailed:
    """Detailed tests for QuickBooksService"""
    
    @patch.dict('os.environ', {
        'QUICKBOOKS_CLIENT_ID': 'test_client_id',
        'QUICKBOOKS_CLIENT_SECRET': 'test_client_secret',
        'QUICKBOOKS_SANDBOX': 'True'
    })
    def test_oauth_flow(self, app):
        """Test OAuth flow methods"""
        with app.app_context():
            from services.quickbooks_service import QuickBooksService
            
            service = QuickBooksService()
            
            # Test authorization URL generation
            auth_url = service.get_authorization_url('test_state_123')
            assert 'https://appcenter.intuit.com/connect/oauth2' in auth_url
            assert 'client_id=test_client_id' in auth_url
            assert 'state=test_state_123' in auth_url
            assert 'response_type=code' in auth_url
            assert 'sandbox' in auth_url  # Should use sandbox URL
            
            # Test scope
            assert 'com.intuit.quickbooks.accounting' in auth_url
    
    @patch('services.quickbooks_service.QuickBooksAuth')
    @patch('requests.post')
    @patch.dict('os.environ', {
        'QUICKBOOKS_CLIENT_ID': 'test_id',
        'QUICKBOOKS_CLIENT_SECRET': 'test_secret'
    })
    def test_exchange_authorization_code(self, mock_post, mock_auth, app):
        """Test exchanging authorization code for tokens"""
        with app.app_context():
            from services.quickbooks_service import QuickBooksService
            
            # Mock token response
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                'access_token': 'test_access_token',
                'refresh_token': 'test_refresh_token',
                'expires_in': 3600
            }
            mock_post.return_value = mock_response
            
            service = QuickBooksService()
            
            result = service.exchange_authorization_code(
                'test_code',
                'test_realm_id'
            )
            
            assert result is True
            mock_post.assert_called_once()
            
            # Verify token exchange request
            call_args = mock_post.call_args
            assert call_args[1]['data']['grant_type'] == 'authorization_code'
            assert call_args[1]['data']['code'] == 'test_code'