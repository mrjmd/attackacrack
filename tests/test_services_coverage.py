"""
Comprehensive tests for all services to achieve 90%+ coverage
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, date, timedelta
import json
import pandas as pd
from io import StringIO

from crm_database import db


class TestContactService:
    """Tests for ContactService"""
    
    def test_get_all_contacts(self, app):
        """Test getting all contacts"""
        with app.app_context():
            from services.contact_service import ContactService
            service = ContactService()
            
            contacts = service.get_all_contacts()
            assert isinstance(contacts, list)
            # Should have at least the seeded contact
            assert len(contacts) >= 1
    
    def test_get_contact_by_id(self, app):
        """Test getting contact by ID"""
        with app.app_context():
            from services.contact_service import ContactService
            service = ContactService()
            
            # Test with seeded contact
            contact = service.get_contact_by_id(1)
            assert contact is not None
            assert contact.id == 1
            
            # Test non-existent
            contact = service.get_contact_by_id(99999)
            assert contact is None
    
    def test_add_contact(self, app):
        """Test adding a contact"""
        with app.app_context():
            from services.contact_service import ContactService
            from crm_database import Contact
            
            service = ContactService()
            
            # Add new contact
            new_contact = service.add_contact(
                first_name='Test',
                last_name='Contact',
                phone='+15557777777',
                email='test.contact@example.com'
            )
            assert new_contact is not None
            assert new_contact.first_name == 'Test'
            assert new_contact.phone == '+15557777777'
            
            # Clean up
            db.session.delete(new_contact)
            db.session.commit()
    
    def test_delete_contact(self, app):
        """Test deleting a contact"""
        with app.app_context():
            from services.contact_service import ContactService
            from crm_database import Contact
            
            service = ContactService()
            
            # Create contact to delete
            contact = Contact(
                first_name='ToDelete',
                last_name='Contact',
                phone='+15558888888'
            )
            db.session.add(contact)
            db.session.commit()
            
            # Delete it
            result = service.delete_contact(contact.id)
            assert result is True
            
            # Verify deleted
            assert service.get_contact_by_id(contact.id) is None
    
    def test_search_contacts(self, app):
        """Test searching contacts"""
        with app.app_context():
            from services.contact_service import ContactService
            service = ContactService()
            
            # Search for seeded contact
            results = service.search_contacts('Doe')
            assert isinstance(results, list)
            assert any('Doe' in (c.last_name or '') for c in results)


class TestPropertyService:
    """Tests for PropertyService"""
    
    def test_get_all_properties(self, app):
        """Test getting all properties"""
        with app.app_context():
            from services.property_service import PropertyService
            service = PropertyService()
            
            properties = service.get_all_properties()
            assert isinstance(properties, list)
            # Should have at least seeded property
            assert len(properties) >= 1
    
    def test_get_property_by_id(self, app):
        """Test getting property by ID"""
        with app.app_context():
            from services.property_service import PropertyService
            service = PropertyService()
            
            # Test with seeded property
            prop = service.get_property_by_id(1)
            assert prop is not None
            assert prop.id == 1
            
            # Test non-existent
            prop = service.get_property_by_id(99999)
            assert prop is None
    
    def test_get_properties_for_contact(self, app):
        """Test getting properties for a contact"""
        with app.app_context():
            from services.property_service import PropertyService
            service = PropertyService()
            
            # Get properties for seeded contact
            properties = service.get_properties_for_contact(1)
            assert isinstance(properties, list)
            assert len(properties) >= 1
    
    def test_delete_property(self, app):
        """Test deleting a property"""
        with app.app_context():
            from services.property_service import PropertyService
            from crm_database import Property
            
            service = PropertyService()
            
            # Create property to delete
            prop = Property(
                address='999 Delete St',
                contact_id=1
            )
            db.session.add(prop)
            db.session.commit()
            
            # Delete it
            result = service.delete_property(prop.id)
            assert result is True
            
            # Verify deleted
            assert service.get_property_by_id(prop.id) is None


class TestJobService:
    """Tests for JobService"""
    
    def test_get_all_jobs(self, app):
        """Test getting all jobs"""
        with app.app_context():
            from services.job_service import JobService
            service = JobService()
            
            jobs = service.get_all_jobs()
            assert isinstance(jobs, list)
            # Should have at least seeded job
            assert len(jobs) >= 1
    
    def test_get_job_by_id(self, app):
        """Test getting job by ID"""
        with app.app_context():
            from services.job_service import JobService
            service = JobService()
            
            # Test with seeded job
            job = service.get_job_by_id(1)
            assert job is not None
            assert job.id == 1
            
            # Test non-existent
            job = service.get_job_by_id(99999)
            assert job is None
    
    def test_add_job(self, app):
        """Test adding a job"""
        with app.app_context():
            from services.job_service import JobService
            from crm_database import Job
            
            service = JobService()
            
            # Add new job
            job_data = {
                'property_id': 1,
                'description': 'Test Job',
                'status': 'Active'
            }
            
            new_job = service.add_job(job_data)
            assert new_job is not None
            assert new_job.description == 'Test Job'
            
            # Clean up
            db.session.delete(new_job)
            db.session.commit()
    
    def test_update_job(self, app):
        """Test updating a job"""
        with app.app_context():
            from services.job_service import JobService
            from crm_database import Job
            
            service = JobService()
            
            # Create job
            job = Job(
                property_id=1,
                description='Original',
                status='Active'
            )
            db.session.add(job)
            db.session.commit()
            
            # Update it
            updated = service.update_job(job.id, {'status': 'Completed'})
            assert updated is not None
            assert updated.status == 'Completed'
            
            # Clean up
            db.session.delete(job)
            db.session.commit()


class TestMessageService:
    """Tests for MessageService"""
    
    def test_get_latest_conversations_from_db(self, app):
        """Test getting latest conversations"""
        with app.app_context():
            from services.message_service import MessageService
            service = MessageService()
            
            conversations = service.get_latest_conversations_from_db(limit=5)
            assert isinstance(conversations, list)
            assert len(conversations) <= 5
    
    def test_get_or_create_conversation(self, app):
        """Test getting or creating conversation"""
        with app.app_context():
            from services.message_service import MessageService
            from crm_database import Conversation
            
            service = MessageService()
            
            # Create new conversation
            convo = service.get_or_create_conversation(
                contact_id=1,
                openphone_convo_id='test_convo_123'
            )
            assert convo is not None
            assert convo.contact_id == 1
            
            # Get existing conversation
            convo2 = service.get_or_create_conversation(
                contact_id=1,
                openphone_convo_id='test_convo_123'
            )
            assert convo2.id == convo.id
            
            # Clean up
            db.session.delete(convo)
            db.session.commit()
    
    def test_get_activities_for_contact(self, app):
        """Test getting activities for contact"""
        with app.app_context():
            from services.message_service import MessageService
            service = MessageService()
            
            activities = service.get_activities_for_contact(1)
            assert isinstance(activities, list)


class TestInvoiceService:
    """Tests for InvoiceService"""
    
    def test_get_all_invoices(self, app):
        """Test getting all invoices"""
        with app.app_context():
            from services.invoice_service import InvoiceService
            service = InvoiceService()
            
            invoices = service.get_all_invoices()
            assert isinstance(invoices, list)
            # Should have at least seeded invoice
            assert len(invoices) >= 1
    
    def test_get_invoice_by_id(self, app):
        """Test getting invoice by ID"""
        with app.app_context():
            from services.invoice_service import InvoiceService
            service = InvoiceService()
            
            # Test with seeded invoice
            invoice = service.get_invoice_by_id(1)
            assert invoice is not None
            assert invoice.id == 1
            
            # Test non-existent
            invoice = service.get_invoice_by_id(99999)
            assert invoice is None
    
    def test_create_invoice(self, app):
        """Test creating an invoice"""
        with app.app_context():
            from services.invoice_service import InvoiceService
            from crm_database import Invoice
            
            service = InvoiceService()
            
            # Create invoice
            invoice_data = {
                'job_id': 1,
                'due_date': date.today() + timedelta(days=30),
                'status': 'Unpaid'
            }
            
            new_invoice = service.create_invoice(invoice_data)
            assert new_invoice is not None
            assert new_invoice.job_id == 1
            
            # Clean up
            db.session.delete(new_invoice)
            db.session.commit()
    
    def test_update_invoice(self, app):
        """Test updating an invoice"""
        with app.app_context():
            from services.invoice_service import InvoiceService
            from crm_database import Invoice
            
            service = InvoiceService()
            
            # Create invoice
            invoice = Invoice(
                job_id=1,
                subtotal=100,
                total_amount=100,
                due_date=date.today() + timedelta(days=30),
                status='Unpaid'
            )
            db.session.add(invoice)
            db.session.commit()
            
            # Update it
            updated = service.update_invoice(invoice.id, {'status': 'Paid'})
            assert updated is not None
            assert updated.status == 'Paid'
            
            # Clean up
            db.session.delete(invoice)
            db.session.commit()
    
    def test_delete_invoice(self, app):
        """Test deleting an invoice"""
        with app.app_context():
            from services.invoice_service import InvoiceService
            from crm_database import Invoice
            
            service = InvoiceService()
            
            # Create invoice
            invoice = Invoice(
                job_id=1,
                subtotal=50,
                total_amount=50,
                due_date=date.today() + timedelta(days=30),
                status='Unpaid'
            )
            db.session.add(invoice)
            db.session.commit()
            
            # Delete it
            result = service.delete_invoice(invoice.id)
            assert result is True
            
            # Verify deleted
            assert service.get_invoice_by_id(invoice.id) is None


class TestQuoteService:
    """Tests for QuoteService"""
    
    def test_get_all_quotes(self, app):
        """Test getting all quotes"""
        with app.app_context():
            from services.quote_service import QuoteService
            service = QuoteService()
            
            quotes = service.get_all_quotes()
            assert isinstance(quotes, list)
            # Should have at least seeded quote
            assert len(quotes) >= 1
    
    def test_get_quote_by_id(self, app):
        """Test getting quote by ID"""
        with app.app_context():
            from services.quote_service import QuoteService
            service = QuoteService()
            
            # Test with seeded quote
            quote = service.get_quote_by_id(1)
            assert quote is not None
            assert quote.id == 1
            
            # Test non-existent
            quote = service.get_quote_by_id(99999)
            assert quote is None
    
    def test_create_quote(self, app):
        """Test creating a quote"""
        with app.app_context():
            from services.quote_service import QuoteService
            from crm_database import Quote
            
            service = QuoteService()
            
            # Create quote with line items
            quote_data = {
                'job_id': 1,
                'line_items': [
                    {
                        'description': 'Test Item',
                        'quantity': 1,
                        'price': 100.0
                    }
                ]
            }
            
            new_quote = service.create_quote(quote_data)
            assert new_quote is not None
            assert new_quote.job_id == 1
            assert new_quote.total_amount == 100.0
            
            # Clean up
            db.session.delete(new_quote)
            db.session.commit()


class TestAppointmentService:
    """Tests for AppointmentService"""
    
    def test_get_all_appointments(self, app):
        """Test getting all appointments"""
        with app.app_context():
            from services.appointment_service import AppointmentService
            service = AppointmentService()
            
            appointments = service.get_all_appointments()
            assert isinstance(appointments, list)
    
    def test_get_appointment_by_id(self, app):
        """Test getting appointment by ID"""
        with app.app_context():
            from services.appointment_service import AppointmentService
            from crm_database import Appointment
            
            service = AppointmentService()
            
            # Create appointment
            appointment = Appointment(
                title='Test Appointment',
                contact_id=1,
                scheduled_time=datetime.now() + timedelta(days=1)
            )
            db.session.add(appointment)
            db.session.commit()
            
            # Get it
            found = service.get_appointment_by_id(appointment.id)
            assert found is not None
            assert found.id == appointment.id
            
            # Clean up
            db.session.delete(appointment)
            db.session.commit()
    
    def test_add_appointment(self, app):
        """Test adding an appointment"""
        with app.app_context():
            from services.appointment_service import AppointmentService
            from crm_database import Appointment
            
            service = AppointmentService()
            
            # Add appointment
            appointment_data = {
                'title': 'New Appointment',
                'contact_id': 1,
                'scheduled_time': datetime.now() + timedelta(days=2)
            }
            
            new_appointment = service.add_appointment(appointment_data)
            assert new_appointment is not None
            assert new_appointment.title == 'New Appointment'
            
            # Clean up
            db.session.delete(new_appointment)
            db.session.commit()


class TestQuickBooksService:
    """Tests for QuickBooksService"""
    
    @patch.dict('os.environ', {
        'QUICKBOOKS_CLIENT_ID': 'test_id',
        'QUICKBOOKS_CLIENT_SECRET': 'test_secret',
        'QUICKBOOKS_SANDBOX': 'True'
    })
    def test_initialization(self, app):
        """Test service initialization"""
        with app.app_context():
            from services.quickbooks_service import QuickBooksService
            service = QuickBooksService()
            
            assert service.client_id == 'test_id'
            assert service.sandbox is True
    
    @patch.dict('os.environ', {
        'QUICKBOOKS_CLIENT_ID': 'test_id',
        'QUICKBOOKS_CLIENT_SECRET': 'test_secret'
    })
    def test_get_authorization_url(self, app):
        """Test OAuth URL generation"""
        with app.app_context():
            from services.quickbooks_service import QuickBooksService
            service = QuickBooksService()
            
            url = service.get_authorization_url('test_state')
            assert 'client_id=test_id' in url
            assert 'state=test_state' in url
            assert 'response_type=code' in url
    
    @patch.dict('os.environ', {
        'QUICKBOOKS_CLIENT_ID': 'test_id',
        'QUICKBOOKS_CLIENT_SECRET': 'test_secret'
    })
    def test_is_authenticated(self, app):
        """Test authentication check"""
        with app.app_context():
            from services.quickbooks_service import QuickBooksService
            service = QuickBooksService()
            
            # Should be False with no auth
            assert service.is_authenticated() is False


class TestCampaignListService:
    """Tests for CampaignListService"""
    
    def test_create_list(self, app):
        """Test creating a campaign list"""
        with app.app_context():
            from services.campaign_list_service import CampaignListService
            from crm_database import CampaignList
            
            service = CampaignListService()
            
            # Create list
            list_data = {
                'name': 'Test List',
                'description': 'Test Description'
            }
            
            new_list = service.create_list(list_data)
            assert new_list is not None
            assert new_list.name == 'Test List'
            
            # Clean up
            db.session.delete(new_list)
            db.session.commit()
    
    def test_get_all_lists(self, app):
        """Test getting all lists"""
        with app.app_context():
            from services.campaign_list_service import CampaignListService
            service = CampaignListService()
            
            lists = service.get_all_lists()
            assert isinstance(lists, list)
    
    def test_add_and_remove_contact(self, app):
        """Test adding and removing contacts from list"""
        with app.app_context():
            from services.campaign_list_service import CampaignListService
            from crm_database import CampaignList
            
            service = CampaignListService()
            
            # Create list
            campaign_list = CampaignList(name='Test List')
            db.session.add(campaign_list)
            db.session.commit()
            
            # Add contact
            result = service.add_contact_to_list(campaign_list.id, 1)
            assert result is True
            
            # Get members
            members = service.get_list_members(campaign_list.id)
            assert len(members) == 1
            
            # Remove contact
            result = service.remove_contact_from_list(campaign_list.id, 1)
            assert result is True
            
            # Verify removed
            members = service.get_list_members(campaign_list.id)
            assert len(members) == 0
            
            # Clean up
            db.session.delete(campaign_list)
            db.session.commit()