"""
Fixed tests for Scheduler Service (Celery tasks)
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, date, timedelta
from crm_database import db, Appointment, Contact, Job, Setting, Property


class TestSchedulerServiceFixed:
    """Fixed test cases for Scheduler service Celery tasks"""
    
    @patch('services.scheduler_service.send_sms')
    def test_send_appointment_reminders_no_template(self, mock_send_sms, app):
        """Test appointment reminders when template is missing"""
        with app.app_context():
            # Import inside context to avoid import errors
            from services.scheduler_service import send_appointment_reminders
            
            # Ensure no template exists
            Setting.query.filter_by(key='appointment_reminder_template').delete()
            db.session.commit()
            
            # Run task
            result = send_appointment_reminders()
            
            # Should not send any SMS
            mock_send_sms.assert_not_called()
    
    @patch('services.scheduler_service.send_sms')
    def test_send_appointment_reminders_no_appointments(self, mock_send_sms, app):
        """Test appointment reminders when no appointments exist"""
        with app.app_context():
            from services.scheduler_service import send_appointment_reminders
            
            # Create template
            template = Setting(
                key='appointment_reminder_template',
                value='Hi {first_name}, reminder about your appointment on {appointment_date} at {appointment_time}'
            )
            db.session.add(template)
            db.session.commit()
            
            # Ensure no appointments for tomorrow
            tomorrow = date.today() + timedelta(days=1)
            Appointment.query.filter_by(date=tomorrow).delete()
            db.session.commit()
            
            # Run task
            result = send_appointment_reminders()
            
            # Should not send any SMS
            mock_send_sms.assert_not_called()
            
            # Clean up
            db.session.delete(template)
            db.session.commit()
    
    @patch('services.scheduler_service.send_sms')
    def test_send_appointment_reminders_success(self, mock_send_sms, app):
        """Test successful appointment reminder sending"""
        with app.app_context():
            from services.scheduler_service import send_appointment_reminders
            
            # Create template
            template = Setting(
                key='appointment_reminder_template',
                value='Hi {first_name}, reminder about your appointment on {appointment_date} at {appointment_time}'
            )
            db.session.add(template)
            
            # Create contact
            contact = Contact(
                first_name='Test',
                last_name='Customer',
                phone='+15551234567'
            )
            db.session.add(contact)
            db.session.commit()
            
            # Create appointment for tomorrow
            tomorrow = date.today() + timedelta(days=1)
            appointment = Appointment(
                contact_id=contact.id,
                date=tomorrow,
                time=datetime.strptime('14:30', '%H:%M').time(),
                description='Test appointment'
            )
            db.session.add(appointment)
            db.session.commit()
            
            # Run task
            result = send_appointment_reminders()
            
            # Should send SMS
            mock_send_sms.assert_called_once()
            args = mock_send_sms.call_args[0]
            assert args[0] == '+15551234567'
            assert 'Test' in args[1]
            assert tomorrow.strftime('%B %d, %Y') in args[1]
            
            # Clean up
            db.session.delete(appointment)
            db.session.delete(contact)
            db.session.delete(template)
            db.session.commit()
    
    @patch('services.scheduler_service.send_sms')
    def test_send_review_requests_no_jobs(self, mock_send_sms, app):
        """Test review requests when no completed jobs exist"""
        with app.app_context():
            from services.scheduler_service import send_review_requests
            
            # Create settings
            template_setting = Setting(
                key='review_request_template',
                value='Hi {first_name}, please review our service for {property_address}'
            )
            days_setting = Setting(
                key='days_after_job_completion',
                value='3'
            )
            db.session.add_all([template_setting, days_setting])
            db.session.commit()
            
            # Ensure no jobs match criteria
            Job.query.filter_by(status='Completed', review_sent=False).delete()
            db.session.commit()
            
            # Run task
            result = send_review_requests()
            
            # Should not send any SMS
            mock_send_sms.assert_not_called()
            
            # Clean up
            db.session.delete(template_setting)
            db.session.delete(days_setting)
            db.session.commit()
    
    @patch('services.scheduler_service.send_sms')
    def test_generate_quotes_for_upcoming_jobs(self, mock_send_sms, app):
        """Test quote generation for scheduled jobs"""
        with app.app_context():
            from services.scheduler_service import generate_quotes_for_upcoming_jobs
            
            # Create test data
            contact = Contact(
                first_name='Quote',
                last_name='Test',
                phone='+15559999999'
            )
            db.session.add(contact)
            db.session.commit()
            
            property = Property(
                address='123 Quote St',
                contact_id=contact.id
            )
            db.session.add(property)
            db.session.commit()
            
            # Create scheduled job
            job = Job(
                property_id=property.id,
                job_type='Installation',
                status='Scheduled',
                scheduled_date=date.today() + timedelta(days=14)
            )
            db.session.add(job)
            db.session.commit()
            
            with patch('services.scheduler_service.QuoteService') as mock_quote_service:
                mock_instance = Mock()
                mock_quote_service.return_value = mock_instance
                
                # Run task
                result = generate_quotes_for_upcoming_jobs()
                
                # Should attempt to create quote
                mock_instance.create_quote.assert_called()
            
            # Clean up
            db.session.delete(job)
            db.session.delete(property)
            db.session.delete(contact)
            db.session.commit()