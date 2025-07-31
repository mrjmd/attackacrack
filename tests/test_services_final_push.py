"""
Final push for service coverage - fixing the most common patterns
"""
import pytest
from unittest.mock import Mock, patch, MagicMock, ANY
from datetime import datetime, date, timedelta
import os
from crm_database import db, Contact, Property, Job, Campaign, CampaignList, Quote, Invoice


class TestServicesWithDatabase:
    """Test services with actual database operations"""
    
    def test_property_service_complete(self, app):
        """Test property service with database"""
        with app.app_context():
            from services.property_service import PropertyService
            service = PropertyService()
            
            # Create test contact
            contact = Contact(first_name='Test', last_name='Owner', phone='+15551112222')
            db.session.add(contact)
            db.session.commit()
            
            # Test add property
            prop_data = {
                'address': '123 Test St',
                'contact_id': contact.id
            }
            new_prop = service.add_property(prop_data)
            assert new_prop is not None
            assert new_prop.address == '123 Test St'
            
            # Test get property
            retrieved = service.get_property_by_id(new_prop.id)
            assert retrieved.id == new_prop.id
            
            # Test update property
            updated = service.update_property(new_prop.id, {'address': '456 New St'})
            assert updated.address == '456 New St'
            
            # Test delete property
            result = service.delete_property(new_prop.id)
            assert result is True
            
            # Clean up
            db.session.delete(contact)
            db.session.commit()
    
    def test_job_service_complete(self, app):
        """Test job service with database"""
        with app.app_context():
            from services.job_service import JobService
            service = JobService()
            
            # Create test data
            contact = Contact(first_name='Test', last_name='Customer', phone='+15553334444')
            db.session.add(contact)
            db.session.commit()
            
            property = Property(address='789 Job St', contact_id=contact.id)
            db.session.add(property)
            db.session.commit()
            
            # Test add job - use correct parameters
            job_data = {
                'property_id': property.id,
                'job_type': 'Maintenance',
                'status': 'Scheduled',
                'scheduled_date': date.today() + timedelta(days=7)
            }
            new_job = service.add_job(job_data)
            assert new_job is not None
            assert new_job.job_type == 'Maintenance'
            
            # Test get jobs
            jobs = service.get_jobs_for_property(property.id)
            assert len(jobs) >= 1
            
            # Clean up
            if new_job:
                db.session.delete(new_job)
            db.session.delete(property)
            db.session.delete(contact)
            db.session.commit()
    
    def test_quote_service_complete(self, app):
        """Test quote service with database"""
        with app.app_context():
            from services.quote_service import QuoteService
            service = QuoteService()
            
            # Create test job
            contact = Contact(first_name='Quote', last_name='Test', phone='+15556667777')
            db.session.add(contact)
            db.session.commit()
            
            property = Property(address='999 Quote Ave', contact_id=contact.id)
            db.session.add(property)
            db.session.commit()
            
            job = Job(property_id=property.id, job_type='Installation', status='Quoted')
            db.session.add(job)
            db.session.commit()
            
            # Test create quote with correct fields
            quote_data = {
                'job_id': job.id,
                'subtotal': 1000.00,
                'tax_amount': 80.00,
                'total_amount': 1080.00,
                'valid_until': (date.today() + timedelta(days=30)).isoformat(),
                'status': 'Pending'
            }
            
            # Create quote
            new_quote = service.create_quote(quote_data)
            assert new_quote is not None
            assert new_quote.subtotal == 1000.00
            
            # Test get quote
            retrieved = service.get_quote_by_id(new_quote.id)
            assert retrieved.id == new_quote.id
            
            # Clean up
            db.session.delete(new_quote)
            db.session.delete(job)
            db.session.delete(property)
            db.session.delete(contact)
            db.session.commit()
    
    def test_campaign_list_service_operations(self, app):
        """Test campaign list service operations"""
        with app.app_context():
            from services.campaign_list_service import CampaignListService
            service = CampaignListService()
            
            # Test create list
            list_data = {
                'name': 'Test List',
                'description': 'Test campaign list'
            }
            new_list = service.create_list(
                name=list_data['name'],
                description=list_data['description']
            )
            assert new_list is not None
            assert new_list.name == 'Test List'
            
            # Test get list
            retrieved = service.get_list_by_id(new_list.id)
            assert retrieved.id == new_list.id
            
            # Test update list
            updated = service.update_list(new_list.id, name='Updated List')
            assert updated.name == 'Updated List'
            
            # Test delete list
            result = service.delete_list(new_list.id)
            assert result is True
    
    @patch('services.ai_service.openai')
    @patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key'})
    def test_ai_service_with_mock(self, mock_openai, app):
        """Test AI service with mocked OpenAI"""
        with app.app_context():
            from services.ai_service import AIService
            
            # Mock the OpenAI client
            mock_client = MagicMock()
            mock_openai.OpenAI.return_value = mock_client
            
            service = AIService()
            assert service.client is not None
            
            # Test summarize conversation
            mock_response = MagicMock()
            mock_response.choices = [MagicMock(message=MagicMock(content='Summary of conversation'))]
            mock_client.chat.completions.create.return_value = mock_response
            
            messages = [
                {'role': 'user', 'content': 'Hello'},
                {'role': 'assistant', 'content': 'Hi there!'}
            ]
            
            summary = service.summarize_conversation(messages)
            assert summary == 'Summary of conversation'
    
    def test_csv_import_service_operations(self, app):
        """Test CSV import service operations"""
        with app.app_context():
            from services.csv_import_service import CSVImportService
            service = CSVImportService()
            
            # Test phone normalization
            assert service.normalize_phone_number('5551234567') == '+15551234567'
            assert service.normalize_phone_number('+15551234567') == '+15551234567'
            assert service.normalize_phone_number('555-123-4567') == '+15551234567'
            assert service.normalize_phone_number('(555) 123-4567') == '+15551234567'
            assert service.normalize_phone_number('invalid') is None
    
    @patch.dict(os.environ, {'OPENPHONE_API_KEY': 'test-api-key'})
    def test_openphone_service_with_env(self, app):
        """Test OpenPhone service with environment variable"""
        with app.app_context():
            from services.openphone_service import OpenPhoneService
            
            service = OpenPhoneService()
            assert service.api_key == 'test-api-key'
            assert service.headers['Authorization'] == 'test-api-key'
    
    def test_message_service_operations(self, app):
        """Test message service operations"""
        with app.app_context():
            from services.message_service import MessageService
            from crm_database import Conversation, Activity
            
            service = MessageService()
            
            # Create test contact
            contact = Contact(first_name='Message', last_name='Test', phone='+15558889999')
            db.session.add(contact)
            db.session.commit()
            
            # Test get or create conversation
            convo = service.get_or_create_conversation(
                contact_id=contact.id,
                openphone_convo_id='test-convo-123'
            )
            assert convo is not None
            assert convo.contact_id == contact.id
            
            # Test get activities
            activities = service.get_activities_for_contact(contact.id)
            assert isinstance(activities, list)
            
            # Test get latest conversations
            latest = service.get_latest_conversations_from_db(limit=5)
            assert isinstance(latest, list)
            
            # Clean up
            Conversation.query.filter_by(contact_id=contact.id).delete()
            db.session.delete(contact)
            db.session.commit()