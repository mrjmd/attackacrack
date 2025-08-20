# tests/test_appointment_service_simple.py
"""
Improved tests for AppointmentService matching the actual implementation.
Addresses TODO items from original test file with comprehensive coverage.
"""

import pytest
from unittest.mock import MagicMock, patch
from services.appointment_service_refactored import AppointmentService
from crm_database import Appointment, Contact, Property
from repositories.appointment_repository import AppointmentRepository
from datetime import date, time
import time as time_module


@pytest.fixture
def appointment_service(app):
    """Fixture to provide AppointmentService instance from app context"""
    with app.app_context():
        return app.services.get('appointment')


@pytest.fixture
def test_contact_with_property(app, db_session):
    """Fixture providing a contact with associated property for appointments"""
    timestamp = str(int(time_module.time() * 1000000))[-6:]
    
    contact = Contact(
        first_name=f"Appt{timestamp}",
        last_name="TestUser",
        phone=f"+155510{timestamp}",
        email=f"appt{timestamp}@example.com"
    )
    db_session.add(contact)
    db_session.flush()
    
    property_obj = Property(
        address=f"123 Appointment St #{timestamp}",
        contact_id=contact.id
    )
    db_session.add(property_obj)
    db_session.commit()
    
    return contact, property_obj


class TestAppointmentService:
    """Test AppointmentService methods"""
    
    @patch('services.appointment_service_refactored.AppointmentService._sync_to_google_calendar')
    def test_add_appointment_success(self, mock_create_event, appointment_service, 
                                   test_contact_with_property):
        """Test successful appointment creation with Google Calendar integration"""
        # Arrange
        contact, property_obj = test_contact_with_property
        mock_create_event.return_value = 'google_event_123'
        
        appointment_data = {
            'title': 'Foundation Assessment',
            'description': 'Initial assessment of foundation cracks',
            'date': date(2025, 8, 15),
            'time': time(10, 30),
            'contact_id': contact.id
        }
        
        # Act
        result = appointment_service.add_appointment(**appointment_data)
        
        # Assert
        assert result.is_success
        new_appointment = result.data
        assert new_appointment is not None
        assert new_appointment.id is not None
        assert new_appointment.title == 'Foundation Assessment'
        assert new_appointment.description == 'Initial assessment of foundation cracks'
        assert new_appointment.date == date(2025, 8, 15)
        assert new_appointment.time == time(10, 30)
        assert new_appointment.contact_id == contact.id
        assert new_appointment.google_calendar_event_id == 'google_event_123'
        
        # Verify Google Calendar API was called
        mock_create_event.assert_called_once()
    
    @patch('services.appointment_service_refactored.AppointmentService._sync_to_google_calendar')
    def test_add_appointment_google_calendar_failure(self, mock_create_event, 
                                                    appointment_service, 
                                                    test_contact_with_property):
        """Test appointment creation when Google Calendar API fails"""
        # Arrange
        contact, property_obj = test_contact_with_property
        mock_create_event.side_effect = Exception("Google Calendar API Error")
        
        appointment_data = {
            'title': 'API Failure Test',
            'description': 'Test handling of Google Calendar failure',
            'date': date(2025, 8, 15),
            'time': time(14, 0),
            'contact_id': contact.id
        }
        
        # Act
        result = appointment_service.add_appointment(**appointment_data)
        
        # Assert
        # Appointment should still be created locally even if Google Calendar fails
        assert result.is_success
        new_appointment = result.data
        assert new_appointment is not None
        assert new_appointment.title == 'API Failure Test'
        # Google Calendar event ID should be None due to failure
        assert new_appointment.google_calendar_event_id is None
        
        mock_create_event.assert_called_once()
    
    @patch('services.appointment_service_refactored.AppointmentService._sync_to_google_calendar')
    def test_add_appointment_minimal_data(self, mock_create_event, appointment_service, 
                                        test_contact_with_property):
        """Test appointment creation with minimal required data"""
        # Arrange
        contact, property_obj = test_contact_with_property
        mock_create_event.return_value = {'id': 'minimal_event_123'}
        
        # Act
        result = appointment_service.add_appointment(
            title='Minimal Appointment',
            date=date(2025, 8, 15),
            time=time(10, 0),
            contact_id=contact.id
        )
        
        # Assert
        assert result.is_success
        new_appointment = result.data
        assert new_appointment is not None
        assert new_appointment.title == 'Minimal Appointment'
        assert new_appointment.description is None
    
    def test_add_appointment_missing_required_fields(self, appointment_service):
        """Test appointment creation with missing required fields"""
        # Missing contact_id should cause database constraint error
        result = appointment_service.add_appointment(
            title='Incomplete Appointment',
            date=date(2025, 8, 15),
            time=time(10, 0)
            # Missing contact_id
        )
        assert result.is_failure
        assert "APPOINTMENT_CREATE_ERROR" in result.error_code
    
    def test_get_all_appointments(self, appointment_service, test_contact_with_property):
        """Test retrieving all appointments"""
        # Arrange
        contact, property_obj = test_contact_with_property
        result = appointment_service.get_all_appointments()
        assert result.is_success
        initial_count = len(result.data)
        
        with patch('services.appointment_service_refactored.AppointmentService._sync_to_google_calendar') as mock_create:
            mock_create.return_value = {'id': 'test_event'}
            
            # Create test appointments
            for i in range(3):
                result = appointment_service.add_appointment(
                    title=f'Test Appointment {i}',
                    date=date(2025, 8, 15 + i),
                    time=time(10, 0),
                    contact_id=contact.id
                )
                assert result.is_success
        
        # Act
        result = appointment_service.get_all_appointments()
        
        # Assert
        assert result.is_success
        all_appointments = result.data
        assert len(all_appointments) == initial_count + 3
        
        # Verify our appointments are included
        appointment_titles = [a.title for a in all_appointments]
        assert 'Test Appointment 0' in appointment_titles
        assert 'Test Appointment 1' in appointment_titles
        assert 'Test Appointment 2' in appointment_titles
    
    def test_get_appointment_by_id_success(self, appointment_service, test_contact_with_property):
        """Test successful appointment retrieval by ID"""
        # Arrange
        contact, property_obj = test_contact_with_property
        
        with patch('services.appointment_service_refactored.AppointmentService._sync_to_google_calendar') as mock_create:
            mock_create.return_value = {'id': 'retrieve_test_event'}
            
            result = appointment_service.add_appointment(
                title='Retrieve Test Appointment',
                date=date(2025, 8, 16),
                time=time(15, 30),
                contact_id=contact.id
            )
            assert result.is_success
            created_appointment = result.data
        
        # Act
        result = appointment_service.get_appointment_by_id(created_appointment.id)
        
        # Assert
        assert result.is_success
        retrieved_appointment = result.data
        assert retrieved_appointment is not None
        assert retrieved_appointment.id == created_appointment.id
        assert retrieved_appointment.title == 'Retrieve Test Appointment'
    
    def test_get_appointment_by_id_not_found(self, appointment_service, db_session):
        """Test retrieving non-existent appointment"""
        # Ensure clean database state
        db_session.rollback()
        result = appointment_service.get_appointment_by_id(999999)
        assert result.is_failure
        assert "APPOINTMENT_NOT_FOUND" in result.error_code
    
    @patch('services.google_calendar_service.GoogleCalendarService.delete_event')
    def test_delete_appointment_success(self, mock_delete_event, appointment_service, 
                                      test_contact_with_property, db_session):
        """Test successful appointment deletion with Google Calendar cleanup"""
        # Arrange
        contact, property_obj = test_contact_with_property
        mock_delete_event.return_value = True
        
        with patch('services.appointment_service_refactored.AppointmentService._sync_to_google_calendar') as mock_create:
            mock_create.return_value = {'id': 'event_to_delete_123'}
            
            # Create appointment first
            result = appointment_service.add_appointment(
                title='Appointment to Delete',
                date=date(2025, 8, 15),
                time=time(11, 0),
                contact_id=contact.id
            )
            assert result.is_success
            appointment = result.data
        
        appointment_id = appointment.id
        google_event_id = appointment.google_calendar_event_id
        
        # Act
        result = appointment_service.delete_appointment(appointment)
        
        # Assert
        assert result.is_success
        mock_delete_event.assert_called_once_with(google_event_id)
        
        # Verify appointment is deleted from database
        deleted_appointment = db_session.get(Appointment, appointment_id)
        assert deleted_appointment is None
    
    @patch('services.google_calendar_service.GoogleCalendarService.delete_event')
    def test_delete_appointment_google_calendar_failure(self, mock_delete_event, 
                                                       appointment_service, 
                                                       test_contact_with_property, db_session):
        """Test appointment deletion when Google Calendar API fails"""
        # Arrange
        contact, property_obj = test_contact_with_property
        mock_delete_event.side_effect = Exception("Google Calendar delete failed")
        
        with patch('services.appointment_service_refactored.AppointmentService._sync_to_google_calendar') as mock_create:
            mock_create.return_value = {'id': 'event_delete_fail_123'}
            
            # Create appointment
            result = appointment_service.add_appointment(
                title='Delete Fail Test',
                date=date(2025, 8, 15),
                time=time(12, 0),
                contact_id=contact.id
            )
            assert result.is_success
            appointment = result.data
        
        appointment_id = appointment.id
        
        # Act - the service now handles errors gracefully
        result = appointment_service.delete_appointment(appointment)
        
        # Assert
        # Should succeed locally even if Google Calendar fails
        assert result.is_success
        mock_delete_event.assert_called_once()
        
        # The appointment should be deleted locally despite Google Calendar failure
        # This is the desired behavior - we don't want to lose local operations due to external service failures
        remaining_appointment = db_session.get(Appointment, appointment_id)
        assert remaining_appointment is None  # Should be deleted locally
    
    @patch('services.google_calendar_service.GoogleCalendarService.delete_event')
    def test_delete_appointment_without_google_event(self, mock_delete_event, 
                                                   appointment_service, 
                                                   test_contact_with_property, db_session):
        """Test deleting appointment that has no associated Google Calendar event"""
        # Arrange
        contact, property_obj = test_contact_with_property
        
        with patch('services.appointment_service_refactored.AppointmentService._sync_to_google_calendar') as mock_create:
            mock_create.return_value = None  # No Google event created
            
            # Create appointment without Google Calendar event
            result = appointment_service.add_appointment(
                title='No Google Event',
                date=date(2025, 8, 15),
                time=time(13, 0),
                contact_id=contact.id
            )
            assert result.is_success
            appointment = result.data
        
        appointment_id = appointment.id
        
        # Act
        result = appointment_service.delete_appointment(appointment)
        assert result.is_success
        
        # Assert
        mock_delete_event.assert_not_called()  # Should not try to delete non-existent event
        
        # Verify local deletion happened
        deleted_appointment = db_session.get(Appointment, appointment_id)
        assert deleted_appointment is None
    
    def test_update_appointment_success(self, appointment_service, test_contact_with_property):
        """Test successful appointment update"""
        # Arrange
        contact, property_obj = test_contact_with_property
        
        with patch('services.appointment_service_refactored.AppointmentService._sync_to_google_calendar') as mock_create:
            mock_create.return_value = {'id': 'update_test_event'}
            
            # Create appointment
            result = appointment_service.add_appointment(
                title='Original Title',
                description='Original description',
                date=date(2025, 8, 15),
                time=time(10, 0),
                contact_id=contact.id
            )
            assert result.is_success
            appointment = result.data
        
        # Act
        result = appointment_service.update_appointment(
            appointment,
            title='Updated Title',
            description='Updated description'
        )
        
        # Assert
        assert result.is_success
        updated_appointment = result.data
        assert updated_appointment is not None
        assert updated_appointment.title == 'Updated Title'
        assert updated_appointment.description == 'Updated description'
        # Unchanged fields should remain
        assert updated_appointment.date == date(2025, 8, 15)
        assert updated_appointment.time == time(10, 0)
        assert updated_appointment.contact_id == contact.id


class TestAppointmentErrorHandling:
    """Test error handling scenarios"""
    
    def test_add_appointment_with_invalid_contact(self, appointment_service):
        """Test appointment creation with non-existent contact"""
        # With foreign keys disabled in tests, this won't raise an exception
        # Instead, test that it handles the missing contact gracefully
        result = appointment_service.add_appointment(
            title='Invalid Contact Appointment',
            date=date(2025, 8, 15),
            time=time(10, 0),
            contact_id=999999  # Non-existent contact
        )
        
        # The appointment is created but Google Calendar event fails
        # because contact is None
        assert result.is_success
        appointment = result.data
        assert appointment is not None
        assert appointment.contact_id == 999999
    
    @patch('services.appointment_service_refactored.AppointmentService._sync_to_google_calendar')
    def test_add_appointment_database_error(self, mock_create_event, appointment_service):
        """Test handling of database errors during appointment creation"""
        # Arrange
        mock_create_event.return_value = {'id': 'db_error_event'}
        
        with patch.object(appointment_service.repository, 'create') as mock_create:
            mock_create.side_effect = Exception("Database error")
            
            result = appointment_service.add_appointment(
                title='Database Error Test',
                date=date(2025, 8, 15),
                time=time(10, 0),
                contact_id=1
            )
            
            # Service now handles errors gracefully
            assert result.is_failure
            assert "Database error" in result.error
    
    @patch('services.appointment_service_refactored.AppointmentService._sync_to_google_calendar')
    def test_appointment_google_calendar_integration_resilience(self, mock_create_event, 
                                                               appointment_service, 
                                                               test_contact_with_property):
        """Test that appointment system is resilient to Google Calendar issues"""
        # Arrange
        contact, property_obj = test_contact_with_property
        
        # Test various Google Calendar failure scenarios
        failure_scenarios = [
            None,  # No response
            {},    # Empty response
            {'error': 'API Error'},  # Error response
        ]
        
        successful_appointments = []
        for i, response in enumerate(failure_scenarios):
            mock_create_event.return_value = response
            
            result = appointment_service.add_appointment(
                title=f'Resilience Test {i}',
                date=date(2025, 8, 22 + i),
                time=time(10, 0),
                contact_id=contact.id
            )
            
            if result.is_success:
                successful_appointments.append(result.data)
        
        # Assert - appointments should still be created even with Google Calendar issues
        assert len(successful_appointments) == 3  # All should succeed locally
        
        # Verify Google Calendar IDs handle various responses appropriately
        for i, appointment in enumerate(successful_appointments):
            response = failure_scenarios[i]
            if response and response.get('id'):
                assert appointment.google_calendar_event_id == response['id']
            else:
                assert appointment.google_calendar_event_id is None


class TestAppointmentBusinessLogic:
    """Test business logic and validation"""
    
    @patch('services.appointment_service_refactored.AppointmentService._sync_to_google_calendar')
    def test_appointment_date_validation(self, mock_create_event, appointment_service, 
                                        test_contact_with_property):
        """Test appointment date validation"""
        # Arrange
        contact, property_obj = test_contact_with_property
        mock_create_event.return_value = {'id': 'date_test_event'}
        
        # Test past date (should be allowed for record-keeping)
        result = appointment_service.add_appointment(
            title='Past Appointment',
            date=date(2020, 1, 1),
            time=time(10, 0),
            contact_id=contact.id
        )
        
        # Assert
        assert result.is_success
        assert result.data is not None
        assert result.data.date == date(2020, 1, 1)
    
    @patch('services.appointment_service_refactored.AppointmentService._sync_to_google_calendar')
    def test_appointment_contact_relationship(self, mock_create_event, appointment_service, 
                                            test_contact_with_property):
        """Test appointment-contact relationship integrity"""
        # Arrange
        contact, property_obj = test_contact_with_property
        mock_create_event.return_value = {'id': 'contact_relationship_event'}
        
        # Create appointment
        result = appointment_service.add_appointment(
            title='Contact Relationship Test',
            date=date(2025, 8, 20),
            time=time(8, 0),
            contact_id=contact.id
        )
        
        # Assert
        assert result.is_success
        appointment = result.data
        assert appointment is not None
        assert appointment.contact_id == contact.id
        # Note: The contact relationship might not be loaded in the Result object
        # This would require eager loading in the repository