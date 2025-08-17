"""
Unit tests for refactored AppointmentService with dependency injection
Tests all appointment functionality with mocked dependencies
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import date, time, datetime, timedelta
from services.appointment_service_refactored import AppointmentService
from services.google_calendar_service import GoogleCalendarService
from crm_database import Appointment, Contact, Property


class TestAppointmentServiceRefactored:
    """Test suite for refactored AppointmentService"""
    
    @pytest.fixture
    def mock_calendar_service(self):
        """Mock GoogleCalendarService"""
        mock = Mock(spec=GoogleCalendarService)
        mock.create_event = Mock(return_value={'id': 'google_event_123'})
        mock.update_event = Mock(return_value={'id': 'google_event_123'})
        mock.delete_event = Mock(return_value=True)
        return mock
    
    @pytest.fixture
    def mock_session(self):
        """Mock database session"""
        session = MagicMock()
        session.add = MagicMock()
        session.commit = MagicMock()
        session.rollback = MagicMock()
        session.delete = MagicMock()
        session.query = MagicMock()
        session.get = MagicMock()
        return session
    
    @pytest.fixture
    def mock_contact(self):
        """Mock contact with property"""
        contact = Mock(spec=Contact)
        contact.id = 1
        contact.first_name = "John"
        contact.last_name = "Doe"
        contact.email = "john@example.com"
        contact.phone = "+15551234567"
        
        property_obj = Mock(spec=Property)
        property_obj.address = "123 Main St"
        contact.properties = [property_obj]
        
        return contact
    
    @pytest.fixture
    def mock_appointment(self, mock_contact):
        """Mock appointment"""
        appointment = Mock(spec=Appointment)
        appointment.id = 1
        appointment.title = "Test Appointment"
        appointment.description = "Test Description"
        appointment.date = date(2025, 8, 20)
        appointment.time = time(10, 0)
        appointment.contact_id = 1
        appointment.contact = mock_contact
        appointment.google_calendar_event_id = None
        return appointment
    
    @pytest.fixture
    def service(self, mock_calendar_service, mock_session):
        """Create AppointmentService with mocked dependencies"""
        return AppointmentService(
            calendar_service=mock_calendar_service,
            session=mock_session
        )
    
    def test_init_without_dependencies(self):
        """Test initialization without dependencies"""
        service = AppointmentService()
        assert service.calendar_service is None
        assert service.session is not None  # Uses default db.session
    
    def test_init_with_dependencies(self, mock_calendar_service, mock_session):
        """Test initialization with dependencies"""
        service = AppointmentService(
            calendar_service=mock_calendar_service,
            session=mock_session
        )
        assert service.calendar_service == mock_calendar_service
        assert service.session == mock_session
    
    def test_add_appointment_with_calendar_sync(self, service, mock_contact, mock_session):
        """Test adding appointment with Google Calendar sync"""
        # Setup mock appointment that will be created
        mock_appointment = Mock(spec=Appointment)
        mock_appointment.id = 1
        mock_appointment.contact = mock_contact
        mock_appointment.date = date(2025, 8, 20)
        mock_appointment.time = time(10, 0)
        mock_appointment.title = "Test Meeting"
        mock_appointment.description = "Test Description"
        mock_appointment.google_calendar_event_id = None
        
        # Mock the Appointment constructor
        with patch('services.appointment_service_refactored.Appointment') as MockAppointment:
            MockAppointment.return_value = mock_appointment
            
            result = service.add_appointment(
                title="Test Meeting",
                description="Test Description",
                date=date(2025, 8, 20),
                time=time(10, 0),
                contact_id=1
            )
            
            # Verify appointment was created
            assert result == mock_appointment
            mock_session.add.assert_called_once_with(mock_appointment)
            assert mock_session.commit.call_count >= 1
            
            # Verify Google Calendar sync
            service.calendar_service.create_event.assert_called_once()
            assert mock_appointment.google_calendar_event_id == 'google_event_123'
    
    def test_add_appointment_without_calendar_sync(self, service, mock_session):
        """Test adding appointment with calendar sync disabled"""
        mock_appointment = Mock(spec=Appointment)
        
        with patch('services.appointment_service_refactored.Appointment') as MockAppointment:
            MockAppointment.return_value = mock_appointment
            
            result = service.add_appointment(
                title="Test Meeting",
                description="Test Description",
                date=date(2025, 8, 20),
                time=time(10, 0),
                contact_id=1,
                sync_to_calendar=False  # Disable sync
            )
            
            # Verify appointment was created but not synced
            assert result == mock_appointment
            service.calendar_service.create_event.assert_not_called()
    
    def test_add_appointment_no_calendar_service(self, mock_session):
        """Test adding appointment without calendar service"""
        service = AppointmentService(session=mock_session)  # No calendar service
        mock_appointment = Mock(spec=Appointment)
        
        with patch('services.appointment_service_refactored.Appointment') as MockAppointment:
            MockAppointment.return_value = mock_appointment
            
            result = service.add_appointment(
                title="Test Meeting",
                date=date(2025, 8, 20),
                time=time(10, 0),
                contact_id=1
            )
            
            assert result == mock_appointment
            mock_session.add.assert_called_once()
    
    def test_add_appointment_calendar_sync_failure(self, service, mock_session):
        """Test appointment creation when calendar sync fails"""
        service.calendar_service.create_event.return_value = None  # Sync fails
        mock_appointment = Mock(spec=Appointment)
        mock_appointment.google_calendar_event_id = None
        
        with patch('services.appointment_service_refactored.Appointment') as MockAppointment:
            MockAppointment.return_value = mock_appointment
            
            result = service.add_appointment(
                title="Test Meeting",
                date=date(2025, 8, 20),
                time=time(10, 0),
                contact_id=1
            )
            
            # Appointment should still be created
            assert result == mock_appointment
            # But no calendar event ID should be set
            assert mock_appointment.google_calendar_event_id is None
    
    def test_get_appointment_duration(self, service):
        """Test appointment duration calculation"""
        assert service._get_appointment_duration('Repair') == 4.0
        assert service._get_appointment_duration('Callback') == 4.0
        assert service._get_appointment_duration('Assessment') == 0.5
        assert service._get_appointment_duration('Inspection') == 1.0
        assert service._get_appointment_duration('Unknown') == 0.5  # Default
    
    def test_build_attendee_list(self, service, mock_appointment):
        """Test building attendee list"""
        attendees = service._build_attendee_list(mock_appointment)
        
        assert 'mike.harrington.email@example.com' in attendees  # Default
        assert 'john@example.com' in attendees  # Contact email
    
    def test_build_attendee_list_no_contact_email(self, service):
        """Test building attendee list when contact has no email"""
        appointment = Mock(spec=Appointment)
        appointment.contact = Mock(spec=Contact)
        appointment.contact.email = None
        
        attendees = service._build_attendee_list(appointment)
        
        assert len(attendees) == 1  # Only default attendee
        assert 'mike.harrington.email@example.com' in attendees
    
    def test_build_calendar_description(self, service, mock_appointment):
        """Test building calendar event description"""
        description = service._build_calendar_description(mock_appointment)
        
        assert "Test Description" in description
        assert "John Doe" in description
        assert "+15551234567" in description
        assert "john@example.com" in description
    
    def test_get_appointment_location(self, service, mock_appointment):
        """Test getting appointment location from property"""
        location = service._get_appointment_location(mock_appointment)
        assert location == "123 Main St"
    
    def test_get_appointment_location_no_property(self, service):
        """Test getting location when no property exists"""
        appointment = Mock(spec=Appointment)
        appointment.contact = Mock(spec=Contact)
        appointment.contact.properties = []
        
        location = service._get_appointment_location(appointment)
        assert location is None
    
    def test_get_all_appointments(self, service, mock_session):
        """Test getting all appointments"""
        mock_appointments = [Mock(), Mock()]
        mock_session.query.return_value.all.return_value = mock_appointments
        
        result = service.get_all_appointments()
        
        assert result == mock_appointments
        mock_session.query.assert_called_once()
    
    def test_get_appointment_by_id(self, service, mock_session, mock_appointment):
        """Test getting appointment by ID"""
        mock_session.get.return_value = mock_appointment
        
        result = service.get_appointment_by_id(1)
        
        assert result == mock_appointment
        mock_session.get.assert_called_once_with(Appointment, 1)
    
    def test_get_appointments_for_contact(self, service, mock_session):
        """Test getting appointments for specific contact"""
        mock_appointments = [Mock(), Mock()]
        mock_query = mock_session.query.return_value
        mock_query.filter_by.return_value.all.return_value = mock_appointments
        
        result = service.get_appointments_for_contact(1)
        
        assert result == mock_appointments
        mock_query.filter_by.assert_called_once_with(contact_id=1)
    
    def test_get_upcoming_appointments(self, service, mock_session):
        """Test getting upcoming appointments"""
        mock_appointments = [Mock(), Mock()]
        mock_query = mock_session.query.return_value
        mock_filter = mock_query.filter.return_value
        mock_order = mock_filter.order_by.return_value
        mock_order.all.return_value = mock_appointments
        
        result = service.get_upcoming_appointments(days=7)
        
        assert result == mock_appointments
        mock_session.query.assert_called_once()
    
    def test_update_appointment(self, service, mock_appointment, mock_session):
        """Test updating appointment"""
        mock_appointment.google_calendar_event_id = 'google_123'
        
        result = service.update_appointment(
            mock_appointment,
            title="Updated Title",
            description="Updated Description"
        )
        
        assert result == mock_appointment
        assert mock_appointment.title == "Updated Title"
        assert mock_appointment.description == "Updated Description"
        mock_session.commit.assert_called_once()
        
        # Calendar should be updated since fields changed
        service.calendar_service.update_event.assert_called_once()
    
    def test_update_appointment_no_calendar_change(self, service, mock_appointment, mock_session):
        """Test updating appointment without calendar-relevant changes"""
        # Update a non-calendar field
        mock_appointment.some_other_field = "old_value"
        
        result = service.update_appointment(
            mock_appointment,
            some_other_field="new_value"
        )
        
        assert result == mock_appointment
        # Calendar should not be updated
        service.calendar_service.update_event.assert_not_called()
    
    def test_delete_appointment_with_calendar(self, service, mock_appointment, mock_session):
        """Test deleting appointment with calendar event"""
        mock_appointment.google_calendar_event_id = 'google_123'
        
        result = service.delete_appointment(mock_appointment)
        
        assert result is True
        service.calendar_service.delete_event.assert_called_once_with('google_123')
        mock_session.delete.assert_called_once_with(mock_appointment)
        mock_session.commit.assert_called_once()
    
    def test_delete_appointment_without_calendar(self, service, mock_appointment, mock_session):
        """Test deleting appointment without calendar event"""
        mock_appointment.google_calendar_event_id = None
        
        result = service.delete_appointment(mock_appointment)
        
        assert result is True
        service.calendar_service.delete_event.assert_not_called()
        mock_session.delete.assert_called_once_with(mock_appointment)
    
    def test_delete_appointment_calendar_failure(self, service, mock_appointment, mock_session):
        """Test appointment deletion when calendar deletion fails"""
        mock_appointment.google_calendar_event_id = 'google_123'
        service.calendar_service.delete_event.return_value = False
        
        result = service.delete_appointment(mock_appointment)
        
        # Should still delete from database
        assert result is True
        mock_session.delete.assert_called_once()
    
    def test_delete_appointment_database_error(self, service, mock_appointment, mock_session):
        """Test appointment deletion with database error"""
        mock_session.delete.side_effect = Exception("DB Error")
        
        result = service.delete_appointment(mock_appointment)
        
        assert result is False
        mock_session.rollback.assert_called_once()
    
    def test_reschedule_appointment(self, service, mock_appointment, mock_session):
        """Test rescheduling appointment"""
        new_date = date(2025, 8, 25)
        new_time = time(14, 0)
        
        with patch.object(service, 'update_appointment') as mock_update:
            mock_update.return_value = mock_appointment
            
            result = service.reschedule_appointment(
                mock_appointment,
                new_date,
                new_time
            )
            
            mock_update.assert_called_once_with(
                mock_appointment,
                date=new_date,
                time=new_time
            )
            assert result == mock_appointment
    
    def test_cancel_appointment(self, service, mock_appointment, mock_session):
        """Test cancelling appointment"""
        mock_appointment.google_calendar_event_id = 'google_123'
        mock_appointment.is_cancelled = False
        
        result = service.cancel_appointment(mock_appointment)
        
        assert result == mock_appointment
        assert mock_appointment.is_cancelled is True
        service.calendar_service.delete_event.assert_called_once_with('google_123')
        assert mock_appointment.google_calendar_event_id is None
        assert mock_session.commit.call_count >= 1