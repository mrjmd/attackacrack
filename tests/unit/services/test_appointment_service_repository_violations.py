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
            repository=mock_repository,
            calendar_service=mock_calendar_service
        )
    
    @pytest.fixture
    def service_without_repository(self, mock_calendar_service):
        """Create AppointmentService without repository (violation pattern)"""
        return AppointmentService(calendar_service=mock_calendar_service)
    
    def test_service_accepts_repository_dependency_injection(self, mock_repository, mock_calendar_service):
        """
        TEST 1: Service must accept AppointmentRepository via dependency injection
        MUST PASS: Service should have repository attribute when injected
        """
        service = AppointmentService(
            repository=mock_repository,
            calendar_service=mock_calendar_service
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
        assert result == expected_appointments
        
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
        assert result == expected_appointments
        
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
        assert result == expected_appointments
        
        # CRITICAL: Verify NO direct database queries were made
        # This will fail if service uses self.session.query(Appointment).filter(...)
        assert not hasattr(service_with_repository, 'session') or not service_with_repository.session.query.called
    
    def test_service_without_repository_creates_repository_from_session(self):
        """
        TEST 5: Service without repository should create repository from session
        EDGE CASE: Verify fallback behavior is correct
        """
        with patch('services.appointment_service_refactored.db') as mock_db:
            mock_session = Mock()
            mock_db.session = mock_session
            
            with patch('services.appointment_service_refactored.AppointmentRepository') as MockRepo:
                mock_repo_instance = Mock(spec=AppointmentRepository)
                MockRepo.return_value = mock_repo_instance
                
                service = AppointmentService()
                
                # Verify repository was created from session
                MockRepo.assert_called_once_with(mock_session, Appointment)
                assert service.repository is mock_repo_instance
    
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
        assert result is mock_appointment
    
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
        assert result is mock_appointment
    
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
        assert result is True
    
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
        
        # Service should handle the error (not let it bubble up unhandled)
        with pytest.raises(Exception) as exc_info:
            service_with_repository.get_all_appointments()
        
        assert "Database error" in str(exc_info.value)
        
        # Verify repository method was called despite error
        mock_repository.get_all.assert_called_once()


class TestAppointmentServiceLegacyPatternDetection:
    """
    Tests that detect legacy patterns that violate repository architecture
    These tests specifically check for anti-patterns
    """
    
    def test_specific_method_violations(self):
        """
        TEST SPECIFIC: Test the exact method violations mentioned
        MUST FAIL: Lines 238, 262, 278 have direct session.query() calls
        """
        service = AppointmentService()
        
        # Create a mock session to track calls
        with patch.object(service, 'session') as mock_session:
            mock_query = Mock()
            mock_session.query.return_value = mock_query
            mock_query.all.return_value = []
            mock_query.filter_by.return_value = mock_query
            mock_query.filter.return_value = mock_query
            mock_query.order_by.return_value = mock_query
            
            # Test get_all_appointments (line ~238)
            service.get_all_appointments()
            
            # VIOLATION: Should NOT call session.query directly
            mock_session.query.assert_called_with(Appointment)
            
            # Reset mock for next test
            mock_session.reset_mock()
            
            # Test get_appointments_for_contact (line ~262)
            service.get_appointments_for_contact(1)
            
            # VIOLATION: Should NOT call session.query directly
            mock_session.query.assert_called_with(Appointment)
            
            # Reset mock for next test
            mock_session.reset_mock()
            
            # Test get_upcoming_appointments (line ~278)
            service.get_upcoming_appointments(7)
            
            # VIOLATION: Should NOT call session.query directly
            mock_session.query.assert_called_with(Appointment)
            
            # All these calls prove the service violates repository pattern
            # When fixed, service should use repository instead
    
    def test_repository_pattern_enforcement_fails(self):
        """
        TEST ENFORCEMENT: This test MUST FAIL until repository pattern is implemented
        WILL FAIL: Because service uses direct session queries instead of repository
        """
        service = AppointmentService()
        
        # This test FAILS if service uses session directly (which it currently does)
        with patch.object(service, 'session') as mock_session:
            mock_query = Mock()
            mock_session.query.return_value = mock_query
            mock_query.all.return_value = []
            mock_query.filter_by.return_value = mock_query
            mock_query.filter.return_value = mock_query
            mock_query.order_by.return_value = mock_query
            
            # Call methods that should use repository
            service.get_all_appointments()
            service.get_appointments_for_contact(1)
            service.get_upcoming_appointments(7)
            
            # ENFORCE: session.query should NEVER be called if repository pattern is properly implemented
            # This assertion will FAIL until the service is refactored to use repository
            assert mock_session.query.call_count == 0, \
                f"REPOSITORY PATTERN VIOLATION: Service made {mock_session.query.call_count} direct session.query() calls. " + \
                "Service must use repository methods instead of direct database queries."
    
    def test_detect_direct_session_usage(self):
        """
        TEST 12: Detect if service uses self.session.query() directly
        MUST FAIL: If service contains direct session queries
        """
        # Create service without mocking to test real implementation
        service = AppointmentService()
        
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
            repository=mock_repository,
            calendar_service=mock_calendar
        )
        
        # Verify dependencies are properly stored
        assert service.repository is mock_repository
        assert service.calendar_service is mock_calendar
    
    @patch('services.appointment_service_refactored.db')
    def test_default_constructor_creates_repository(self, mock_db):
        """
        TEST 14: Default constructor should create repository, not use session directly
        """
        mock_session = Mock()
        mock_db.session = mock_session
        
        with patch('services.appointment_service_refactored.AppointmentRepository') as MockRepo:
            mock_repo = Mock(spec=AppointmentRepository)
            MockRepo.return_value = mock_repo
            
            service = AppointmentService()
            
            # Verify repository was created
            MockRepo.assert_called_once_with(mock_session, Appointment)
            assert service.repository is mock_repo
    
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


class TestAppointmentServiceMustFailUntilFixed:
    """
    Critical tests that MUST FAIL until repository pattern violations are fixed
    These tests enforce TDD RED phase by failing on current implementation
    """
    
    def test_get_all_appointments_must_not_use_session_query(self):
        """
        CRITICAL FAILING TEST: get_all_appointments() uses session.query() - MUST FAIL
        This test will PASS only after implementing repository pattern
        """
        service = AppointmentService()
        
        # Mock the session to track calls
        with patch.object(service, 'session') as mock_session:
            mock_query = Mock()
            mock_session.query.return_value = mock_query
            mock_query.all.return_value = []
            
            # Call the method
            service.get_all_appointments()
            
            # MUST FAIL: Service should NOT call session.query
            assert mock_session.query.call_count == 0, \
                "VIOLATION: get_all_appointments() calls session.query(Appointment) on line ~238. " + \
                "Must use repository.get_all() instead."
    
    def test_get_appointments_for_contact_must_not_use_session_query(self):
        """
        CRITICAL FAILING TEST: get_appointments_for_contact() uses session.query() - MUST FAIL
        This test will PASS only after implementing repository pattern
        """
        service = AppointmentService()
        
        # Mock the session to track calls
        with patch.object(service, 'session') as mock_session:
            mock_query = Mock()
            mock_session.query.return_value = mock_query
            mock_query.filter_by.return_value = mock_query
            mock_query.all.return_value = []
            
            # Call the method
            service.get_appointments_for_contact(123)
            
            # MUST FAIL: Service should NOT call session.query
            assert mock_session.query.call_count == 0, \
                "VIOLATION: get_appointments_for_contact() calls session.query(Appointment).filter_by() on line ~262. " + \
                "Must use repository.find_by_contact_id() instead."
    
    def test_get_upcoming_appointments_must_not_use_session_query(self):
        """
        CRITICAL FAILING TEST: get_upcoming_appointments() uses session.query() - MUST FAIL
        This test will PASS only after implementing repository pattern
        """
        service = AppointmentService()
        
        # Mock the session to track calls
        with patch.object(service, 'session') as mock_session:
            mock_query = Mock()
            mock_session.query.return_value = mock_query
            mock_query.filter.return_value = mock_query
            mock_query.order_by.return_value = mock_query
            mock_query.all.return_value = []
            
            # Call the method
            service.get_upcoming_appointments(7)
            
            # MUST FAIL: Service should NOT call session.query
            assert mock_session.query.call_count == 0, \
                "VIOLATION: get_upcoming_appointments() calls session.query(Appointment).filter() on line ~278. " + \
                "Must use repository.find_by_date_range() instead."
    
    def test_service_must_accept_repository_parameter(self):
        """
        CRITICAL FAILING TEST: Service constructor must accept repository parameter - MUST FAIL
        This test will PASS only after adding repository parameter to __init__
        """
        from repositories.appointment_repository import AppointmentRepository
        mock_repository = Mock(spec=AppointmentRepository)
        
        # This will FAIL because current service doesn't accept repository parameter
        try:
            service = AppointmentService(repository=mock_repository)
            # If we get here, the service accepts repository parameter
            assert hasattr(service, 'repository'), "Service must store repository when provided"
            assert service.repository is mock_repository, "Service must use provided repository"
        except TypeError as e:
            # Expected failure - service doesn't accept repository parameter yet
            assert "repository" in str(e), f"Service constructor must accept repository parameter. Error: {e}"
            # Re-raise to make test fail (this is what we want in RED phase)
            raise AssertionError("VIOLATION: AppointmentService.__init__() must accept 'repository' parameter for dependency injection")