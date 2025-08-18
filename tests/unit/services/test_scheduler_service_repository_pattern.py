"""
Test Suite for SchedulerService Repository Pattern Refactoring

Tests for scheduler service refactored to use repository pattern,
ensuring all database violations are eliminated while preserving
exact scheduling functionality.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import date, datetime, timedelta
from services.scheduler_service import SchedulerService
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