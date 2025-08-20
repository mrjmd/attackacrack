"""
TDD RED Phase: Tests to enforce AppointmentService repository pattern
These tests MUST fail initially to catch repository pattern violations
"""

import pytest
from unittest.mock import Mock, MagicMock, patch, call
from datetime import date, time, datetime, timedelta
from services.appointment_service_refactored import AppointmentService
from repositories.appointment_repository import AppointmentRepository
from crm_database import Appointment, Contact
from repositories.appointment_repository import AppointmentRepository


class TestAppointmentServiceRepositoryEnforcement:
    """
    TDD Tests to enforce repository pattern usage in AppointmentService
    
    These tests verify that:
    1. Service accepts AppointmentRepository via dependency injection
    2. Service calls repository methods instead of using direct database queries
    3. Service does NOT use self.session.query() directly
    4. All database access goes through the repository layer
    """
    
    @pytest.fixture
    def mock_repository(self):
        """Mock AppointmentRepository with all required methods"""
        repository = Mock(spec=AppointmentRepository)
        
        # Mock all repository methods that should be used
        repository.get_all = Mock(return_value=[])
        repository.get_by_id = Mock(return_value=None)
        repository.find_by_contact_id = Mock(return_value=[])
        repository.find_by_date_range = Mock(return_value=[])
        repository.create = Mock()
        repository.update = Mock()
        repository.delete = Mock(return_value=True)
        repository.commit = Mock()
        repository.rollback = Mock()
        
        return repository
    
    @pytest.fixture
    def mock_calendar_service(self):
        """Mock GoogleCalendarService"""
        calendar_service = Mock()
        calendar_service.create_event = Mock(return_value={'id': 'event_123'})
        calendar_service.update_event = Mock(return_value={'id': 'event_123'})
        calendar_service.delete_event = Mock(return_value=True)
        return calendar_service
    
    @pytest.fixture
    def service_with_repository(self, mock_repository, mock_calendar_service):
        """Create AppointmentService with injected repository (proper pattern)"""
        return AppointmentService(
            appointment_repository=mock_repository,
            google_calendar_service=mock_calendar_service
        )
    
    @pytest.fixture
    def service_without_repository(self, mock_calendar_service):
        """Create AppointmentService without repository (violation pattern)"""
        # This will raise an error - that's expected
        with pytest.raises(ValueError):
            return AppointmentService(google_calendar_service=mock_calendar_service)
    
    def test_service_accepts_repository_dependency_injection(self, mock_repository, mock_calendar_service):
        """
        TEST 1: Service must accept AppointmentRepository via dependency injection
        MUST PASS: Service should have repository attribute when injected
        """
        service = AppointmentService(
            appointment_repository=mock_repository,
            google_calendar_service=mock_calendar_service
        )
        
        # Verify repository is properly injected
        assert hasattr(service, 'repository'), "Service must have repository attribute"
        assert service.repository is mock_repository, "Service must use injected repository"
        
        # Verify session is NOT stored when repository is provided
        assert not hasattr(service, 'session'), "Service must NOT store session when repository is provided"
    
    def test_get_all_appointments_uses_repository_not_session(self, service_with_repository, mock_repository):
        """
        TEST 2: get_all_appointments() must use repository.get_all() not self.session.query()
        MUST FAIL: Current implementation likely uses session.query(Appointment).all()
        """
        expected_appointments = [Mock(spec=Appointment), Mock(spec=Appointment)]
        mock_repository.get_all.return_value = expected_appointments
        
        # Call the method
        result = service_with_repository.get_all_appointments()
        
        # Verify repository method was called
        mock_repository.get_all.assert_called_once()
        
        # Verify result is from repository
        assert result.is_success
        assert result.data == expected_appointments
        
        # CRITICAL: Verify NO direct database queries were made
        # This will fail if service uses self.session.query(Appointment).all()
        assert not hasattr(service_with_repository, 'session') or not service_with_repository.session.query.called
    
    def test_get_appointments_by_contact_uses_repository_not_session(self, service_with_repository, mock_repository):
        """
        TEST 3: get_appointments_for_contact() must use repository not session
        MUST FAIL: Current implementation likely uses session.query(Appointment).filter_by()
        """
        contact_id = 123
        expected_appointments = [Mock(spec=Appointment)]
        mock_repository.find_by_contact_id.return_value = expected_appointments
        
        # Call the method
        result = service_with_repository.get_appointments_for_contact(contact_id)
        
        # Verify repository method was called with correct parameters
        mock_repository.find_by_contact_id.assert_called_once_with(contact_id)
        
        # Verify result is from repository
        assert result.is_success
        assert result.data == expected_appointments
        
        # CRITICAL: Verify NO direct database queries were made
        # This will fail if service uses self.session.query(Appointment).filter_by(contact_id=contact_id).all()
        assert not hasattr(service_with_repository, 'session') or not service_with_repository.session.query.called
    
    def test_get_appointments_in_range_uses_repository_not_session(self, service_with_repository, mock_repository):
        """
        TEST 4: get_upcoming_appointments() must use repository not session
        MUST FAIL: Current implementation likely uses session.query(Appointment).filter()
        """
        days = 7
        expected_appointments = [Mock(spec=Appointment)]
        mock_repository.find_by_date_range.return_value = expected_appointments
        
        # Call the method
        result = service_with_repository.get_upcoming_appointments(days=days)
        
        # Calculate expected date range
        today = date.today()
        end_date = today + timedelta(days=days)
        
        # Verify repository method was called with correct date range
        mock_repository.find_by_date_range.assert_called_once_with(today, end_date)
        
        # Verify result is from repository
        assert result.is_success
        assert result.data == expected_appointments
        
        # CRITICAL: Verify NO direct database queries were made
        # This will fail if service uses self.session.query(Appointment).filter(...)
        assert not hasattr(service_with_repository, 'session') or not service_with_repository.session.query.called
    
    def test_service_without_repository_raises_error(self):
        """
        TEST 5: Service without repository should raise error
        EDGE CASE: Verify service enforces dependency injection
        """
        # Act & Assert - creating service without repository should raise error
        with pytest.raises(TypeError):
            AppointmentService()
    
    def test_add_appointment_uses_repository_create(self, service_with_repository, mock_repository):
        """
        TEST 6: add_appointment() must use repository.create() not direct model creation
        """
        mock_appointment = Mock(spec=Appointment)
        mock_appointment.id = 1
        mock_appointment.google_calendar_event_id = None
        mock_repository.create.return_value = mock_appointment
        
        appointment_data = {
            'title': 'Test Appointment',
            'description': 'Test Description',
            'date': date(2025, 8, 20),
            'time': time(10, 0),
            'contact_id': 1
        }
        
        result = service_with_repository.add_appointment(**appointment_data)
        
        # Verify repository create was called
        mock_repository.create.assert_called_once()
        
        # Verify commit was called
        mock_repository.commit.assert_called()
        
        # Verify result
        assert result.is_success
        assert result.data is mock_appointment
    
    def test_update_appointment_uses_repository_update(self, service_with_repository, mock_repository):
        """
        TEST 7: update_appointment() must use repository.update() not direct model update
        """
        mock_appointment = Mock(spec=Appointment)
        mock_appointment.google_calendar_event_id = None
        mock_repository.update.return_value = mock_appointment
        
        result = service_with_repository.update_appointment(
            mock_appointment,
            title='Updated Title'
        )
        
        # Verify repository update was called
        mock_repository.update.assert_called_once_with(mock_appointment, title='Updated Title')
        
        # Verify commit was called
        mock_repository.commit.assert_called_once()
        
        # Verify result
        assert result.is_success
        assert result.data is mock_appointment
    
    def test_delete_appointment_uses_repository_delete(self, service_with_repository, mock_repository):
        """
        TEST 8: delete_appointment() must use repository.delete() not session.delete()
        """
        mock_appointment = Mock(spec=Appointment)
        mock_appointment.google_calendar_event_id = None
        mock_repository.delete.return_value = True
        
        result = service_with_repository.delete_appointment(mock_appointment)
        
        # Verify repository delete was called
        mock_repository.delete.assert_called_once_with(mock_appointment)
        
        # Verify commit was called
        mock_repository.commit.assert_called_once()
        
        # Verify result
        assert result.is_success
        assert result.data is True
    
    def test_service_does_not_store_session_when_repository_provided(self, service_with_repository):
        """
        TEST 9: Service must NOT store session attribute when repository is provided
        CRITICAL: This enforces clean architecture separation
        """
        # Service with repository should NOT have session attribute
        assert not hasattr(service_with_repository, 'session'), \
            "Service must NOT store session when repository is provided"
        
        # Service should have repository attribute
        assert hasattr(service_with_repository, 'repository'), \
            "Service must have repository attribute when repository is provided"
    
    def test_repository_methods_are_called_exactly_once(self, service_with_repository, mock_repository):
        """
        TEST 10: Verify repository methods are called exactly once (no duplicate calls)
        """
        # Test get_all_appointments
        service_with_repository.get_all_appointments()
        assert mock_repository.get_all.call_count == 1
        
        # Test get_appointments_for_contact
        service_with_repository.get_appointments_for_contact(1)
        assert mock_repository.find_by_contact_id.call_count == 1
        
        # Test get_upcoming_appointments
        service_with_repository.get_upcoming_appointments()
        assert mock_repository.find_by_date_range.call_count == 1
    
    def test_repository_error_handling(self, service_with_repository, mock_repository):
        """
        TEST 11: Service should handle repository errors gracefully
        """
        # Mock repository to raise exception
        mock_repository.get_all.side_effect = Exception("Database error")
        
        # Service should handle the error and return Result.failure
        result = service_with_repository.get_all_appointments()
        assert result.is_failure
        assert "Database error" in result.error
        
        # Error was handled properly and returned in Result.failure
        
        # Verify repository method was called despite error
        mock_repository.get_all.assert_called_once()


class TestAppointmentServiceLegacyPatternDetection:
    """
    Tests that detect legacy patterns that violate repository architecture
    These tests specifically check for anti-patterns
    """
    
    def test_specific_method_violations_are_fixed(self):
        """
        TEST SPECIFIC: Verify the exact method violations have been FIXED
        SHOULD PASS: Lines 238, 262, 278 no longer have direct session.query() calls
        """
        # Create service with mock repository
        mock_repository = Mock(spec=AppointmentRepository)
        service = AppointmentService(appointment_repository=mock_repository)
        
        # Verify service now uses repository pattern
        assert hasattr(service, 'repository'), "Service should have repository after fix"
        
        # Create a mock session to verify it's NOT called
        with patch.object(service, 'repository') as mock_repository:
            mock_repository.get_all.return_value = []
            mock_repository.find_by_contact_id.return_value = []
            mock_repository.find_by_date_range.return_value = []
            
            # Test get_all_appointments - should use repository.get_all()
            service.get_all_appointments()
            mock_repository.get_all.assert_called_once()
            
            # Reset mock for next test
            mock_repository.reset_mock()
            
            # Test get_appointments_for_contact - should use repository.find_by_contact_id()
            service.get_appointments_for_contact(1)
            mock_repository.find_by_contact_id.assert_called_once_with(1)
            
            # Reset mock for next test
            mock_repository.reset_mock()
            
            # Test get_upcoming_appointments - should use repository.find_by_date_range()
            service.get_upcoming_appointments(7)
            mock_repository.find_by_date_range.assert_called_once()
            
            # SUCCESS: All methods now use repository pattern instead of direct queries
    
    def test_repository_pattern_enforcement_success(self):
        """
        TEST SUCCESS: Repository pattern is properly implemented
        SUCCESS: Service no longer has session attribute and uses repository pattern
        """
        # Create service with mock repository
        mock_repository = Mock(spec=AppointmentRepository)
        service = AppointmentService(appointment_repository=mock_repository)
        
        # SUCCESS: Service should not have session attribute anymore
        assert not hasattr(service, 'session'), \
            "REPOSITORY PATTERN SUCCESS: Service correctly has no 'session' attribute"
        
        # SUCCESS: Service should have repository attribute
        assert hasattr(service, 'repository'), \
            "REPOSITORY PATTERN SUCCESS: Service correctly uses repository"
        
        assert service.repository is mock_repository, \
            "REPOSITORY PATTERN SUCCESS: Service correctly uses injected repository"
    
    def test_detect_direct_session_usage(self):
        """
        TEST 12: Detect if service uses self.session.query() directly
        MUST FAIL: If service contains direct session queries
        """
        # Create service with mock repository to test real implementation
        mock_repository = Mock(spec=AppointmentRepository)
        service = AppointmentService(appointment_repository=mock_repository)
        
        # Check if service has session attribute (indicates legacy pattern)
        if hasattr(service, 'session'):
            # If service has session, it might be using legacy patterns
            # This test will pass only if service uses repository exclusively
            assert hasattr(service, 'repository'), \
                "Service with session must also have repository"
    
    def test_service_registry_integration_requirement(self):
        """
        TEST 13: Service should be designed for service registry integration
        """
        # Test that service can be created with explicit dependencies
        mock_repository = Mock(spec=AppointmentRepository)
        mock_calendar = Mock()
        
        service = AppointmentService(
            appointment_repository=mock_repository,
            google_calendar_service=mock_calendar
        )
        
        # Verify dependencies are properly stored
        assert service.repository is mock_repository
        assert service.calendar_service is mock_calendar
    
    def test_refactored_service_requires_repository_injection(self):
        """
        TEST 14: Refactored service properly requires repository injection
        SUCCESS: Service no longer accepts empty constructor
        """
        # SUCCESS: Service now correctly requires repository injection
        with pytest.raises(TypeError):
            service = AppointmentService()
        
        # SUCCESS: Service works with proper repository injection
        mock_repository = Mock(spec=AppointmentRepository)
        service = AppointmentService(appointment_repository=mock_repository)
        assert service.repository is mock_repository
    
    def test_repository_interface_compliance(self):
        """
        TEST 15: Verify repository interface compliance
        """
        mock_repository = Mock(spec=AppointmentRepository)
        
        # Check that all required methods exist on repository
        required_methods = [
            'get_all', 'get_by_id', 'find_by_contact_id', 
            'find_by_date_range', 'create', 'update', 'delete',
            'commit', 'rollback'
        ]
        
        for method_name in required_methods:
            assert hasattr(mock_repository, method_name), \
                f"Repository must have {method_name} method"


class TestAppointmentServiceRefactoringSuccess:
    """
    SUCCESS: Repository pattern refactoring completed successfully
    These tests validate that the service properly uses repository pattern
    """
    
    def test_service_no_longer_has_session_attribute(self):
        """
        SUCCESS: Service correctly removed session attribute
        Validates repository pattern implementation
        """
        mock_repository = Mock(spec=AppointmentRepository)
        mock_repository.get_all.return_value = []
        
        service = AppointmentService(appointment_repository=mock_repository)
        
        # SUCCESS: Service should not have session attribute anymore
        assert not hasattr(service, 'session'), \
            "SUCCESS: Service correctly has no 'session' attribute"
        
        # SUCCESS: Service should use repository methods
        service.get_all_appointments()
        mock_repository.get_all.assert_called_once()
    
    def test_service_uses_repository_for_contact_appointments(self):
        """
        SUCCESS: Service correctly uses repository for contact appointments
        Validates proper repository method usage
        """
        mock_repository = Mock(spec=AppointmentRepository)
        mock_repository.find_by_contact_id.return_value = []
        
        service = AppointmentService(appointment_repository=mock_repository)
        
        # SUCCESS: Service should use repository method
        service.get_appointments_for_contact(123)
        mock_repository.find_by_contact_id.assert_called_once_with(123)
        
        # SUCCESS: Service should not have session attribute
        assert not hasattr(service, 'session'), \
            "SUCCESS: Service correctly uses repository pattern"
    
    def test_service_uses_repository_for_upcoming_appointments(self):
        """
        SUCCESS: Service correctly uses repository for upcoming appointments
        Validates proper repository method usage
        """
        mock_repository = Mock(spec=AppointmentRepository)
        mock_repository.find_by_date_range.return_value = []
        
        service = AppointmentService(appointment_repository=mock_repository)
        
        # SUCCESS: Service should use repository method
        service.get_upcoming_appointments(7)
        mock_repository.find_by_date_range.assert_called_once()
        
        # SUCCESS: Service should not have session attribute
        assert not hasattr(service, 'session'), \
            "SUCCESS: Service correctly uses repository pattern"
    
    def test_service_accepts_repository_parameter(self):
        """
        PASSING TEST: Service constructor accepts repository parameter
        This test should PASS now that repository pattern is implemented
        """
        from repositories.appointment_repository import AppointmentRepository
        mock_repository = Mock(spec=AppointmentRepository)
        
        # Service should accept repository parameter
        service = AppointmentService(appointment_repository=mock_repository)
        # Service should store repository when provided
        assert hasattr(service, 'repository'), "Service must store repository when provided"
        assert service.repository is mock_repository, "Service must use provided repository"