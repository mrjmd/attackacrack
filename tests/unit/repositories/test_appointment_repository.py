"""
Tests for AppointmentRepository
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime, date, time
from repositories.appointment_repository import AppointmentRepository
from repositories.base_repository import PaginatedResult
from crm_database import Appointment


class TestAppointmentRepository:
    """Test suite for AppointmentRepository"""
    
    @pytest.fixture
    def mock_session(self):
        """Mock database session"""
        session = MagicMock()
        return session
    
    @pytest.fixture
    def repository(self, mock_session):
        """Create AppointmentRepository with mocked session"""
        return AppointmentRepository(mock_session, Appointment)
    
    def test_find_by_contact_id(self, repository, mock_session):
        """Test finding appointments by contact ID"""
        # Arrange
        mock_appointments = [Mock(id=1), Mock(id=2)]
        mock_query = Mock()
        mock_query.filter_by.return_value.order_by.return_value.all.return_value = mock_appointments
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.find_by_contact_id(123)
        
        # Assert
        assert result == mock_appointments
        mock_query.filter_by.assert_called_once_with(contact_id=123)
    
    def test_find_by_date(self, repository, mock_session):
        """Test finding appointments by date"""
        # Arrange
        test_date = date(2025, 8, 17)
        mock_appointments = [Mock(id=1, date=test_date)]
        mock_query = Mock()
        mock_query.filter_by.return_value.order_by.return_value.all.return_value = mock_appointments
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.find_by_date(test_date)
        
        # Assert
        assert result == mock_appointments
        mock_query.filter_by.assert_called_once_with(date=test_date)
    
    def test_find_by_date_range(self, repository, mock_session):
        """Test finding appointments in date range"""
        # Arrange
        start_date = date(2025, 8, 1)
        end_date = date(2025, 8, 31)
        mock_appointments = [Mock(id=1), Mock(id=2)]
        mock_query = Mock()
        # Chain the filter calls
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value.all.return_value = mock_appointments
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.find_by_date_range(start_date, end_date)
        
        # Assert
        assert result == mock_appointments
        # The filter method is called twice (chained)
        assert mock_query.filter.call_count == 2
    
    def test_find_by_job_id(self, repository, mock_session):
        """Test finding appointments by job ID"""
        # Arrange
        mock_appointments = [Mock(id=1, job_id=456)]
        mock_query = Mock()
        mock_query.filter_by.return_value.order_by.return_value.all.return_value = mock_appointments
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.find_by_job_id(456)
        
        # Assert
        assert result == mock_appointments
        mock_query.filter_by.assert_called_once_with(job_id=456)
    
    def test_find_by_google_event_id(self, repository, mock_session):
        """Test finding appointment by Google Calendar event ID"""
        # Arrange
        mock_appointment = Mock(id=1, google_calendar_event_id="google_123")
        mock_query = Mock()
        mock_query.filter_by.return_value.first.return_value = mock_appointment
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.find_by_google_event_id("google_123")
        
        # Assert
        assert result == mock_appointment
        mock_query.filter_by.assert_called_once_with(google_calendar_event_id="google_123")
    
    def test_find_upcoming_appointments(self, repository, mock_session):
        """Test finding upcoming appointments"""
        # Arrange
        mock_appointments = [Mock(id=1), Mock(id=2)]
        mock_query = Mock()
        mock_query.filter.return_value.order_by.return_value.limit.return_value.all.return_value = mock_appointments
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.find_upcoming_appointments(limit=10)
        
        # Assert
        assert result == mock_appointments
        mock_query.filter.assert_called_once()
        mock_query.filter.return_value.order_by.return_value.limit.assert_called_once_with(10)
    
    def test_find_past_appointments(self, repository, mock_session):
        """Test finding past appointments"""
        # Arrange
        mock_appointments = [Mock(id=1), Mock(id=2)]
        mock_query = Mock()
        mock_query.filter.return_value.order_by.return_value.limit.return_value.all.return_value = mock_appointments
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.find_past_appointments(limit=20)
        
        # Assert
        assert result == mock_appointments
        mock_query.filter.assert_called_once()
    
    def test_update_google_event_id(self, repository, mock_session):
        """Test updating appointment's Google Calendar event ID"""
        # Arrange
        mock_appointment = Mock(id=1, google_calendar_event_id=None)
        mock_query = Mock()
        mock_query.get.return_value = mock_appointment
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.update_google_event_id(1, "new_google_id")
        
        # Assert
        assert result == mock_appointment
        assert mock_appointment.google_calendar_event_id == "new_google_id"
        mock_session.commit.assert_called_once()
    
    def test_count_by_contact(self, repository, mock_session):
        """Test counting appointments for a contact"""
        # Arrange
        mock_query = Mock()
        mock_query.filter_by.return_value.count.return_value = 5
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.count_by_contact(123)
        
        # Assert
        assert result == 5
        mock_query.filter_by.assert_called_once_with(contact_id=123)
    
    def test_search(self, repository, mock_session):
        """Test searching appointments"""
        # Arrange
        mock_appointments = [Mock(id=1)]
        mock_query = Mock()
        mock_query.filter.return_value.limit.return_value.all.return_value = mock_appointments
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.search("dental")
        
        # Assert
        assert result == mock_appointments
        mock_query.filter.assert_called_once()