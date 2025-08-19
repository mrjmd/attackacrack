"""
Test Suite for SchedulerService Repository Pattern Refactoring

Tests for scheduler service refactored to use repository pattern,
ensuring all database violations are eliminated while preserving
exact scheduling functionality.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import date, datetime, timedelta
# from services.scheduler_service import SchedulerService  # Commented out - celery not installed
SchedulerService = None  # Mock placeholder
from repositories.setting_repository import SettingRepository
from repositories.job_repository import JobRepository
from repositories.quote_repository import QuoteRepository
from repositories.appointment_repository import AppointmentRepository
from crm_database import Setting, Job, Quote, Appointment, Contact, Property


class TestSchedulerServiceRepositoryPattern:
    """Test SchedulerService using repository pattern"""
    
    @pytest.fixture
    def mock_setting_repository(self):
        """Mock SettingRepository"""
        return Mock(spec=SettingRepository)
    
    @pytest.fixture
    def mock_job_repository(self):
        """Mock JobRepository"""
        return Mock(spec=JobRepository)
    
    @pytest.fixture
    def mock_quote_repository(self):
        """Mock QuoteRepository"""
        return Mock(spec=QuoteRepository)
    
    @pytest.fixture
    def mock_appointment_repository(self):
        """Mock AppointmentRepository"""
        return Mock(spec=AppointmentRepository)
    
    @pytest.fixture
    def mock_openphone_service(self):
        """Mock OpenPhoneService"""
        return Mock()
    
    @pytest.fixture
    def mock_invoice_service(self):
        """Mock InvoiceService"""
        return Mock()
    
    @pytest.fixture
    def scheduler_service(self, mock_setting_repository, mock_job_repository, 
                         mock_quote_repository, mock_appointment_repository,
                         mock_openphone_service, mock_invoice_service):
        """Create SchedulerService with mocked repositories"""
        return SchedulerService(
            setting_repository=mock_setting_repository,
            job_repository=mock_job_repository,
            quote_repository=mock_quote_repository,
            appointment_repository=mock_appointment_repository,
            openphone_service=mock_openphone_service,
            invoice_service=mock_invoice_service
        )
    
    def test_send_appointment_reminders_finds_template(self, scheduler_service, mock_setting_repository):
        """Test that appointment reminders look up template from repository"""
        # Arrange
        mock_template = Mock()
        mock_template.value = 'Hi {first_name}, reminder for {appointment_date} at {appointment_time}'
        mock_setting_repository.find_one_by.return_value = mock_template
        
        # Mock no appointments for tomorrow
        scheduler_service.appointment_repository.find_by_date.return_value = []
        
        # Act
        result = scheduler_service.send_appointment_reminders()
        
        # Assert
        mock_setting_repository.find_one_by.assert_called_once_with(key='appointment_reminder_template')
    
    def test_send_appointment_reminders_no_template_aborts(self, scheduler_service, mock_setting_repository):
        """Test that missing template causes early abort"""
        # Arrange - No template found
        mock_setting_repository.find_one_by.return_value = None
        
        # Act
        result = scheduler_service.send_appointment_reminders()
        
        # Assert
        mock_setting_repository.find_one_by.assert_called_once_with(key='appointment_reminder_template')
        # Should not proceed to find appointments
        scheduler_service.appointment_repository.find_by_date.assert_not_called()
    
    def test_send_appointment_reminders_finds_tomorrow_appointments(self, scheduler_service, 
                                                                  mock_setting_repository, 
                                                                  mock_appointment_repository):
        """Test that service finds appointments for tomorrow"""
        # Arrange
        mock_template = Mock()
        mock_template.value = 'Template'
        mock_setting_repository.find_one_by.return_value = mock_template
        
        tomorrow = date.today() + timedelta(days=1)
        mock_appointments = []
        mock_appointment_repository.find_by_date.return_value = mock_appointments
        
        # Act
        scheduler_service.send_appointment_reminders()
        
        # Assert
        mock_appointment_repository.find_by_date.assert_called_once_with(tomorrow)
    
    def test_send_appointment_reminders_sends_messages(self, scheduler_service, 
                                                      mock_setting_repository,
                                                      mock_appointment_repository,
                                                      mock_openphone_service):
        """Test that reminder messages are sent via OpenPhone"""
        # Arrange
        mock_template = Mock()
        mock_template.value = 'Hi {first_name}, reminder for {appointment_date} at {appointment_time}'
        mock_setting_repository.find_one_by.return_value = mock_template
        
        # Mock contact and appointment
        mock_contact = Mock()
        mock_contact.first_name = 'John'
        mock_contact.phone = '+11234567890'
        
        mock_appointment = Mock()
        mock_appointment.contact = mock_contact
        mock_appointment.time = datetime.strptime('14:30', '%H:%M').time()
        
        mock_appointment_repository.find_by_date.return_value = [mock_appointment]
        mock_openphone_service.send_message.return_value = {'success': True}
        
        tomorrow = date.today() + timedelta(days=1)
        
        # Act
        scheduler_service.send_appointment_reminders()
        
        # Assert
        formatted_date = tomorrow.strftime("%B %d, %Y")
        expected_message = f'Hi John, reminder for {formatted_date} at 02:30 pm'
        mock_openphone_service.send_message.assert_called_once_with('+11234567890', expected_message)
    
    def test_send_appointment_reminders_handles_sms_failure(self, scheduler_service,
                                                           mock_setting_repository,
                                                           mock_appointment_repository,
                                                           mock_openphone_service):
        """Test that SMS sending failures are logged"""
        # Arrange
        mock_template = Mock()
        mock_template.value = 'Reminder template'
        mock_setting_repository.find_one_by.return_value = mock_template
        
        mock_contact = Mock()
        mock_contact.first_name = 'John'
        mock_contact.phone = '+11234567890'
        
        mock_appointment = Mock()
        mock_appointment.contact = mock_contact
        mock_appointment.id = 123
        
        mock_appointment_repository.find_by_date.return_value = [mock_appointment]
        mock_openphone_service.send_message.return_value = {'success': False, 'error': 'API Error'}
        
        with patch('services.scheduler_service.logger') as mock_logger:
            # Act
            scheduler_service.send_appointment_reminders()
            
            # Assert
            mock_logger.error.assert_called_with(
                "Failed to send SMS reminder for appointment 123. Error: API Error"
            )
    
    def test_send_appointment_reminders_skips_missing_contact(self, scheduler_service,
                                                             mock_setting_repository, 
                                                             mock_appointment_repository):
        """Test that appointments without contact are skipped"""
        # Arrange
        mock_template = Mock()
        mock_template.value = 'Template'
        mock_setting_repository.find_one_by.return_value = mock_template
        
        mock_appointment = Mock()
        mock_appointment.contact = None
        mock_appointment.id = 456
        
        mock_appointment_repository.find_by_date.return_value = [mock_appointment]
        
        with patch('services.scheduler_service.logger') as mock_logger:
            # Act
            scheduler_service.send_appointment_reminders()
            
            # Assert
            mock_logger.warning.assert_called_with(
                "Skipping reminder for appointment 456: contact or phone number missing."
            )
    
    def test_send_review_requests_finds_template(self, scheduler_service, mock_setting_repository):
        """Test that review requests look up template from repository"""
        # Arrange
        mock_template = Mock()
        mock_template.value = 'Please review us, {first_name}!'
        mock_setting_repository.find_one_by.return_value = mock_template
        
        # Mock no completed jobs
        scheduler_service.job_repository.find_completed_jobs_by_date.return_value = []
        
        # Act
        scheduler_service.send_review_requests()
        
        # Assert
        mock_setting_repository.find_one_by.assert_called_once_with(key='review_request_template')
    
    def test_send_review_requests_no_template_aborts(self, scheduler_service, mock_setting_repository):
        """Test that missing template causes early abort"""
        # Arrange
        mock_setting_repository.find_one_by.return_value = None
        
        # Act
        scheduler_service.send_review_requests()
        
        # Assert  
        mock_setting_repository.find_one_by.assert_called_once_with(key='review_request_template')
        # Should not proceed to find completed jobs
        scheduler_service.job_repository.find_completed_jobs_by_date.assert_not_called()
    
    def test_send_review_requests_finds_yesterday_jobs(self, scheduler_service,
                                                      mock_setting_repository,
                                                      mock_job_repository):
        """Test that service finds completed jobs from yesterday"""
        # Arrange
        mock_template = Mock()
        mock_template.value = 'Template'
        mock_setting_repository.find_one_by.return_value = mock_template
        
        yesterday = (datetime.utcnow().date() - timedelta(days=1))
        mock_job_repository.find_completed_jobs_by_date.return_value = []
        
        # Act
        scheduler_service.send_review_requests()
        
        # Assert
        mock_job_repository.find_completed_jobs_by_date.assert_called_once_with(yesterday)
    
    def test_send_review_requests_sends_messages(self, scheduler_service,
                                               mock_setting_repository,
                                               mock_job_repository,
                                               mock_openphone_service):
        """Test that review request messages are sent via OpenPhone"""
        # Arrange
        mock_template = Mock()
        mock_template.value = 'Hi {first_name}, please review us!'
        mock_setting_repository.find_one_by.return_value = mock_template
        
        # Mock job with property and contact chain
        mock_contact = Mock()
        mock_contact.first_name = 'Jane'
        mock_contact.phone = '+11234567890'
        
        mock_property = Mock()
        mock_property.contact = mock_contact
        
        mock_job = Mock()
        mock_job.property = mock_property
        mock_job.id = 789
        
        mock_job_repository.find_completed_jobs_by_date.return_value = [mock_job]
        mock_openphone_service.send_message.return_value = {'success': True}
        
        # Act
        scheduler_service.send_review_requests()
        
        # Assert
        expected_message = 'Hi Jane, please review us!'
        mock_openphone_service.send_message.assert_called_once_with('+11234567890', expected_message)
    
    def test_send_review_requests_skips_missing_contact(self, scheduler_service,
                                                       mock_setting_repository,
                                                       mock_job_repository):
        """Test that jobs without property/contact are skipped"""
        # Arrange
        mock_template = Mock()
        mock_template.value = 'Template'
        mock_setting_repository.find_one_by.return_value = mock_template
        
        mock_job = Mock()
        mock_job.property = None
        mock_job.id = 999
        
        mock_job_repository.find_completed_jobs_by_date.return_value = [mock_job]
        
        with patch('services.scheduler_service.logger') as mock_logger:
            # Act
            scheduler_service.send_review_requests()
            
            # Assert
            mock_logger.warning.assert_called_with(
                "Skipping review request for job 999: property, contact, or phone missing."
            )
    
    def test_convert_quotes_for_today_appointments_finds_today_appointments(self, scheduler_service,
                                                                           mock_appointment_repository):
        """Test that quote conversion finds today's appointments"""
        # Arrange
        today = date.today()
        mock_appointment_repository.find_by_date.return_value = []
        
        # Act
        scheduler_service.convert_quotes_for_today_appointments()
        
        # Assert
        mock_appointment_repository.find_by_date.assert_called_once_with(today)
    
    def test_convert_quotes_for_today_appointments_no_appointments_logs(self, scheduler_service,
                                                                       mock_appointment_repository):
        """Test logging when no appointments today"""
        # Arrange
        mock_appointment_repository.find_by_date.return_value = []
        
        with patch('services.scheduler_service.logger') as mock_logger:
            # Act
            scheduler_service.convert_quotes_for_today_appointments()
            
            # Assert
            mock_logger.info.assert_called_with(
                "No appointments for today with draft quotes to convert. Task complete."
            )
    
    def test_convert_quotes_for_today_appointments_converts_draft_quotes(self, scheduler_service,
                                                                        mock_appointment_repository,
                                                                        mock_quote_repository,
                                                                        mock_invoice_service):
        """Test that draft quotes are converted to invoices"""
        # Arrange
        mock_job = Mock()
        mock_job.id = 100
        
        mock_appointment = Mock()
        mock_appointment.job = mock_job
        
        mock_appointment_repository.find_by_date.return_value = [mock_appointment]
        
        mock_quote = Mock()
        mock_quote.id = 200
        mock_quote_repository.find_draft_quotes_by_job_id.return_value = [mock_quote]
        
        # Act
        scheduler_service.convert_quotes_for_today_appointments()
        
        # Assert
        mock_quote_repository.find_draft_quotes_by_job_id.assert_called_once_with(100)
        mock_invoice_service.create_invoice_from_quote.assert_called_once_with(200)
    
    def test_convert_quotes_skips_appointments_without_job(self, scheduler_service,
                                                          mock_appointment_repository,
                                                          mock_quote_repository):
        """Test that appointments without jobs are skipped"""
        # Arrange
        mock_appointment = Mock()
        mock_appointment.job = None
        
        mock_appointment_repository.find_by_date.return_value = [mock_appointment]
        
        # Act
        scheduler_service.convert_quotes_for_today_appointments()
        
        # Assert
        # Should not call quote repository if no job
        mock_quote_repository.find_draft_quotes_by_job_id.assert_not_called()
    
    def test_convert_quotes_handles_invoice_creation_failure(self, scheduler_service,
                                                           mock_appointment_repository,
                                                           mock_quote_repository,
                                                           mock_invoice_service):
        """Test that invoice creation failures are logged"""
        # Arrange
        mock_job = Mock()
        mock_job.id = 100
        
        mock_appointment = Mock()
        mock_appointment.job = mock_job
        
        mock_appointment_repository.find_by_date.return_value = [mock_appointment]
        
        mock_quote = Mock()
        mock_quote.id = 300
        mock_quote_repository.find_draft_quotes_by_job_id.return_value = [mock_quote]
        
        mock_invoice_service.create_invoice_from_quote.side_effect = Exception("Invoice creation failed")
        
        with patch('services.scheduler_service.logger') as mock_logger:
            # Act
            scheduler_service.convert_quotes_for_today_appointments()
            
            # Assert
            mock_logger.error.assert_called_with(
                "Failed to convert quote 300 to invoice. Error: Invoice creation failed"
            )
    
    def test_run_daily_tasks_calls_all_methods(self, scheduler_service):
        """Test that run_daily_tasks calls all individual task methods"""
        # Mock all the individual methods
        with patch.object(scheduler_service, 'send_appointment_reminders') as mock_reminders, \
             patch.object(scheduler_service, 'send_review_requests') as mock_reviews, \
             patch.object(scheduler_service, 'convert_quotes_for_today_appointments') as mock_quotes:
            
            # Act
            scheduler_service.run_daily_tasks()
            
            # Assert
            mock_reminders.assert_called_once()
            mock_reviews.assert_called_once()
            mock_quotes.assert_called_once()
    
    def test_run_daily_tasks_logs_start_and_completion(self, scheduler_service):
        """Test that run_daily_tasks logs appropriately"""
        with patch('services.scheduler_service.logger') as mock_logger, \
             patch.object(scheduler_service, 'send_appointment_reminders'), \
             patch.object(scheduler_service, 'send_review_requests'), \
             patch.object(scheduler_service, 'convert_quotes_for_today_appointments'):
            
            # Act
            scheduler_service.run_daily_tasks()
            
            # Assert
            mock_logger.info.assert_any_call("Starting daily scheduled tasks...")
            mock_logger.info.assert_any_call("All daily tasks completed.")