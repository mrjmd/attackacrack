# tests/test_scheduler_service_simple.py
"""
Comprehensive tests for scheduler service covering all Celery tasks.
"""

import pytest
from unittest.mock import MagicMock, patch, call
from datetime import date, datetime, time
from services import scheduler_service


class TestAppointmentReminders:
    """Test appointment reminder task functionality"""
    
    @patch('services.scheduler_service.send_sms')
    @patch('services.scheduler_service.date')
    @patch('services.scheduler_service.Setting')
    @patch('services.scheduler_service.db.session')
    def test_send_appointment_reminders_success(self, mock_session, mock_setting, mock_date, mock_send_sms):
        """Test successful sending of appointment reminders"""
        mock_date.today.return_value = date(2025, 1, 1)
        
        # Mock template setting
        mock_template = MagicMock()
        mock_template.value = 'Hi {first_name}, this is a reminder about your appointment on {appointment_date} at {appointment_time}.'
        mock_setting.query.filter_by.return_value.first.return_value = mock_template
        
        # Mock appointment with contact
        mock_contact = MagicMock()
        mock_contact.first_name = "John"
        mock_contact.phone = "+1555123456"
        
        mock_appointment = MagicMock()
        mock_appointment.contact = mock_contact
        mock_appointment.time = time(10, 0)
        mock_appointment.id = 1
        
        mock_session.query.return_value.filter.return_value.all.return_value = [mock_appointment]
        
        scheduler_service.send_appointment_reminders()
        
        mock_send_sms.assert_called_once_with(
            "+1555123456",
            "Hi John, this is a reminder about your appointment on January 02, 2025 at 10:00 am."
        )
    
    @patch('services.scheduler_service.Setting')
    @patch('services.scheduler_service.logging')
    def test_send_appointment_reminders_no_template(self, mock_logging, mock_setting):
        """Test appointment reminders when template is missing"""
        mock_setting.query.filter_by.return_value.first.return_value = None
        
        scheduler_service.send_appointment_reminders()
        
        mock_logging.warning.assert_called_with(
            "Appointment reminder template not found in settings. Aborting task."
        )
    
    @patch('services.scheduler_service.send_sms')
    @patch('services.scheduler_service.date')
    @patch('services.scheduler_service.Setting')  
    @patch('services.scheduler_service.db.session')
    def test_send_appointment_reminders_sms_failure(self, mock_session, mock_setting, mock_date, mock_send_sms):
        """Test appointment reminders when SMS sending fails"""
        mock_date.today.return_value = date(2025, 1, 1)
        mock_send_sms.side_effect = Exception("SMS API Error")
        
        # Mock template
        mock_template = MagicMock()
        mock_template.value = 'Test template {first_name}'
        mock_setting.query.filter_by.return_value.first.return_value = mock_template
        
        # Mock appointment
        mock_appointment = MagicMock()
        mock_appointment.contact.first_name = "John"
        mock_appointment.contact.phone = "+1555123456" 
        mock_appointment.time = time(10, 0)
        mock_appointment.id = 1
        
        mock_session.query.return_value.filter.return_value.all.return_value = [mock_appointment]
        
        with patch('services.scheduler_service.logging') as mock_logging:
            scheduler_service.send_appointment_reminders()
            
            mock_logging.error.assert_called_with(
                "Failed to send SMS reminder for appointment 1. Error: SMS API Error"
            )


class TestReviewRequests:
    """Test review request task functionality"""
    
    @patch('services.scheduler_service.send_sms')
    @patch('services.scheduler_service.datetime')
    @patch('services.scheduler_service.Setting')
    @patch('services.scheduler_service.Job')
    def test_send_review_requests_success(self, mock_job, mock_setting, mock_datetime, mock_send_sms):
        """Test successful sending of review requests"""
        mock_datetime.utcnow.return_value = datetime(2025, 1, 2)
        
        # Mock template setting
        mock_template = MagicMock()
        mock_template.value = 'Hi {first_name}, please leave us a review!'
        mock_setting.query.filter_by.return_value.first.return_value = mock_template
        
        # Mock completed job with contact chain
        mock_contact = MagicMock()
        mock_contact.first_name = "Jane"
        mock_contact.phone = "+1555987654"
        
        mock_property = MagicMock()
        mock_property.contact = mock_contact
        
        mock_job_instance = MagicMock()
        mock_job_instance.property = mock_property
        mock_job_instance.id = 1
        
        mock_job.query.filter.return_value.all.return_value = [mock_job_instance]
        
        scheduler_service.send_review_requests()
        
        mock_send_sms.assert_called_once_with(
            "+1555987654",
            "Hi Jane, please leave us a review!"
        )
    
    @patch('services.scheduler_service.Setting')
    @patch('services.scheduler_service.logging')
    def test_send_review_requests_no_template(self, mock_logging, mock_setting):
        """Test review requests when template is missing"""
        mock_setting.query.filter_by.return_value.first.return_value = None
        
        scheduler_service.send_review_requests()
        
        mock_logging.warning.assert_called_with(
            "Review request template not found in settings. Aborting task."
        )


class TestQuoteConversion:
    """Test quote conversion task functionality"""
    
    @patch('services.scheduler_service.InvoiceService')
    @patch('services.scheduler_service.date')
    @patch('services.scheduler_service.db.session')
    @patch('services.scheduler_service.Quote')
    def test_convert_quotes_for_today_appointments_success(self, mock_quote, mock_session, mock_date, mock_invoice_service):
        """Test successful conversion of quotes to invoices"""
        mock_date.today.return_value = date(2025, 1, 1)
        
        # Mock appointment with job
        mock_job = MagicMock()
        mock_job.id = 1
        
        mock_appointment = MagicMock()
        mock_appointment.job = mock_job
        
        mock_session.query.return_value.filter.return_value.all.return_value = [mock_appointment]
        
        # Mock draft quote
        mock_draft_quote = MagicMock()
        mock_draft_quote.id = 1
        mock_quote.query.filter_by.return_value.all.return_value = [mock_draft_quote]
        
        scheduler_service.convert_quotes_for_today_appointments()
        
        mock_invoice_service.create_invoice_from_quote.assert_called_once_with(1)
    
    @patch('services.scheduler_service.date')
    @patch('services.scheduler_service.db.session')
    @patch('services.scheduler_service.logging')
    def test_convert_quotes_no_appointments_today(self, mock_logging, mock_session, mock_date):
        """Test quote conversion when no appointments for today"""
        mock_date.today.return_value = date(2025, 1, 1)
        mock_session.query.return_value.filter.return_value.all.return_value = []
        
        scheduler_service.convert_quotes_for_today_appointments()
        
        mock_logging.info.assert_called_with(
            "No appointments for today with draft quotes to convert. Task complete."
        )


class TestDailyTaskRunner:
    """Test the main daily task runner"""
    
    @patch('services.scheduler_service.send_appointment_reminders')
    @patch('services.scheduler_service.send_review_requests')  
    @patch('services.scheduler_service.convert_quotes_for_today_appointments')
    @patch('services.scheduler_service.logging')
    def test_run_daily_tasks_success(self, mock_logging, mock_convert, mock_review, mock_reminder):
        """Test successful execution of all daily tasks"""
        # Mock the delay() method for Celery tasks
        mock_reminder.delay = MagicMock()
        mock_review.delay = MagicMock()
        mock_convert.delay = MagicMock()
        
        scheduler_service.run_daily_tasks()
        
        # Verify all tasks were queued
        mock_reminder.delay.assert_called_once()
        mock_review.delay.assert_called_once()
        mock_convert.delay.assert_called_once()
        
        # Verify logging
        mock_logging.info.assert_has_calls([
            call("Starting daily scheduled tasks..."),
            call("All daily tasks have been queued.")
        ])


class TestSchedulerServiceErrorHandling:
    """Test error handling and edge cases"""
    
    @patch('services.scheduler_service.send_sms')
    @patch('services.scheduler_service.date')
    @patch('services.scheduler_service.Setting')
    @patch('services.scheduler_service.db.session')
    def test_appointment_reminder_missing_contact(self, mock_session, mock_setting, mock_date, mock_send_sms):
        """Test appointment reminders when contact is missing"""
        mock_date.today.return_value = date(2025, 1, 1)
        
        # Mock template
        mock_template = MagicMock()
        mock_template.value = 'Test template'
        mock_setting.query.filter_by.return_value.first.return_value = mock_template
        
        # Mock appointment without contact
        mock_appointment = MagicMock()
        mock_appointment.contact = None
        mock_appointment.id = 1
        
        mock_session.query.return_value.filter.return_value.all.return_value = [mock_appointment]
        
        with patch('services.scheduler_service.logging') as mock_logging:
            scheduler_service.send_appointment_reminders()
            
            mock_logging.warning.assert_called_with(
                "Skipping reminder for appointment 1: contact or phone number missing."
            )
            mock_send_sms.assert_not_called()
    
    @patch('services.scheduler_service.InvoiceService')
    @patch('services.scheduler_service.date')
    @patch('services.scheduler_service.db.session')
    @patch('services.scheduler_service.Quote')
    def test_quote_conversion_invoice_creation_failure(self, mock_quote, mock_session, mock_date, mock_invoice_service):
        """Test quote conversion when invoice creation fails"""
        mock_date.today.return_value = date(2025, 1, 1)
        mock_invoice_service.create_invoice_from_quote.side_effect = Exception("Invoice creation failed")
        
        # Mock setup
        mock_job = MagicMock()
        mock_job.id = 1
        
        mock_appointment = MagicMock()
        mock_appointment.job = mock_job
        
        mock_session.query.return_value.filter.return_value.all.return_value = [mock_appointment]
        
        mock_draft_quote = MagicMock()
        mock_draft_quote.id = 1
        mock_quote.query.filter_by.return_value.all.return_value = [mock_draft_quote]
        
        with patch('services.scheduler_service.logging') as mock_logging:
            scheduler_service.convert_quotes_for_today_appointments()
            
            mock_logging.error.assert_called_with(
                "Failed to convert quote 1 to invoice. Error: Invoice creation failed"
            )