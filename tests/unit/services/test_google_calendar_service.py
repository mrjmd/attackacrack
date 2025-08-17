"""
Unit tests for GoogleCalendarService
Tests the service in complete isolation using mocks
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime
from google.oauth2.credentials import Credentials
from googleapiclient.errors import HttpError
from services.google_calendar_service import GoogleCalendarService


class TestGoogleCalendarService:
    """Test suite for GoogleCalendarService"""
    
    @pytest.fixture
    def mock_credentials(self):
        """Mock Google OAuth2 credentials"""
        credentials = Mock(spec=Credentials)
        credentials.valid = True
        credentials.expired = False
        return credentials
    
    @pytest.fixture
    def service(self, mock_credentials):
        """Create service instance with mock credentials"""
        return GoogleCalendarService(credentials=mock_credentials)
    
    @pytest.fixture
    def mock_google_service(self):
        """Mock the Google Calendar API service"""
        mock_service = MagicMock()
        mock_events = MagicMock()
        mock_service.events.return_value = mock_events
        return mock_service, mock_events
    
    def test_init_without_credentials(self):
        """Test service initialization without credentials"""
        service = GoogleCalendarService()
        assert service.credentials is None
        assert service._service is None
    
    def test_init_with_credentials(self, mock_credentials):
        """Test service initialization with credentials"""
        service = GoogleCalendarService(credentials=mock_credentials)
        assert service.credentials == mock_credentials
        assert service._service is None  # Lazy loaded
    
    def test_set_credentials(self, service, mock_credentials):
        """Test updating credentials"""
        new_creds = Mock(spec=Credentials)
        service.set_credentials(new_creds)
        assert service.credentials == new_creds
        assert service._service is None  # Reset on credential change
    
    @patch('services.google_calendar_service.build')
    def test_get_upcoming_events_success(self, mock_build, service, mock_google_service):
        """Test successful retrieval of upcoming events"""
        mock_service, mock_events = mock_google_service
        mock_build.return_value = mock_service
        
        # Mock API response
        mock_events.list.return_value.execute.return_value = {
            'items': [
                {'id': '1', 'summary': 'Event 1'},
                {'id': '2', 'summary': 'Event 2'}
            ]
        }
        
        events = service.get_upcoming_events(count=2)
        
        assert len(events) == 2
        assert events[0]['summary'] == 'Event 1'
        mock_events.list.assert_called_once()
    
    def test_get_upcoming_events_no_credentials(self):
        """Test getting events without credentials"""
        service = GoogleCalendarService()  # No credentials
        events = service.get_upcoming_events()
        assert events == []
    
    @patch('services.google_calendar_service.build')
    def test_get_upcoming_events_api_error(self, mock_build, service, mock_google_service):
        """Test handling of API errors when getting events"""
        mock_service, mock_events = mock_google_service
        mock_build.return_value = mock_service
        
        # Mock API error
        mock_events.list.return_value.execute.side_effect = HttpError(
            resp=Mock(status=403),
            content=b'Forbidden'
        )
        
        events = service.get_upcoming_events()
        assert events == []
    
    @patch('services.google_calendar_service.build')
    def test_create_event_success(self, mock_build, service, mock_google_service):
        """Test successful event creation"""
        mock_service, mock_events = mock_google_service
        mock_build.return_value = mock_service
        
        # Mock API response
        created_event = {
            'id': 'new_event_123',
            'summary': 'Test Event',
            'htmlLink': 'https://calendar.google.com/event/123'
        }
        mock_events.insert.return_value.execute.return_value = created_event
        
        start_time = datetime(2025, 8, 20, 10, 0)
        end_time = datetime(2025, 8, 20, 11, 0)
        
        result = service.create_event(
            title='Test Event',
            description='Test Description',
            start_time=start_time,
            end_time=end_time,
            attendees=['test@example.com'],
            location='Test Location'
        )
        
        assert result == created_event
        mock_events.insert.assert_called_once()
        
        # Verify the event body
        call_args = mock_events.insert.call_args
        event_body = call_args[1]['body']
        assert event_body['summary'] == 'Test Event'
        assert event_body['description'] == 'Test Description'
        assert event_body['location'] == 'Test Location'
        assert len(event_body['attendees']) == 1
    
    def test_create_event_no_credentials(self):
        """Test creating event without credentials"""
        service = GoogleCalendarService()  # No credentials
        result = service.create_event(
            title='Test',
            description='Test',
            start_time=datetime.now(),
            end_time=datetime.now()
        )
        assert result is None
    
    @patch('services.google_calendar_service.build')
    def test_create_event_api_error(self, mock_build, service, mock_google_service):
        """Test handling of API errors when creating event"""
        mock_service, mock_events = mock_google_service
        mock_build.return_value = mock_service
        
        # Mock API error
        mock_events.insert.return_value.execute.side_effect = HttpError(
            resp=Mock(status=400),
            content=b'Bad Request'
        )
        
        result = service.create_event(
            title='Test',
            description='Test',
            start_time=datetime.now(),
            end_time=datetime.now()
        )
        assert result is None
    
    @patch('services.google_calendar_service.build')
    def test_delete_event_success(self, mock_build, service, mock_google_service):
        """Test successful event deletion"""
        mock_service, mock_events = mock_google_service
        mock_build.return_value = mock_service
        
        mock_events.delete.return_value.execute.return_value = {}
        
        result = service.delete_event('event_123')
        
        assert result is True
        mock_events.delete.assert_called_once_with(
            calendarId='primary',
            eventId='event_123'
        )
    
    def test_delete_event_no_credentials(self):
        """Test deleting event without credentials"""
        service = GoogleCalendarService()  # No credentials
        result = service.delete_event('event_123')
        assert result is False
    
    @patch('services.google_calendar_service.build')
    def test_delete_event_not_found(self, mock_build, service, mock_google_service):
        """Test deleting non-existent event (should return True)"""
        mock_service, mock_events = mock_google_service
        mock_build.return_value = mock_service
        
        # Mock 404 error
        mock_events.delete.return_value.execute.side_effect = HttpError(
            resp=Mock(status=404),
            content=b'Not Found'
        )
        
        result = service.delete_event('nonexistent_event')
        assert result is True  # Consider successful if already deleted
    
    @patch('services.google_calendar_service.build')
    def test_delete_event_api_error(self, mock_build, service, mock_google_service):
        """Test handling of API errors when deleting event"""
        mock_service, mock_events = mock_google_service
        mock_build.return_value = mock_service
        
        # Mock non-404 error
        mock_events.delete.return_value.execute.side_effect = HttpError(
            resp=Mock(status=403),
            content=b'Forbidden'
        )
        
        result = service.delete_event('event_123')
        assert result is False
    
    @patch('services.google_calendar_service.build')
    def test_update_event_success(self, mock_build, service, mock_google_service):
        """Test successful event update"""
        mock_service, mock_events = mock_google_service
        mock_build.return_value = mock_service
        
        # Mock getting existing event
        existing_event = {
            'id': 'event_123',
            'summary': 'Old Title',
            'description': 'Old Description'
        }
        mock_events.get.return_value.execute.return_value = existing_event
        
        # Mock update response
        updated_event = {
            'id': 'event_123',
            'summary': 'New Title',
            'description': 'Old Description'
        }
        mock_events.update.return_value.execute.return_value = updated_event
        
        result = service.update_event(
            'event_123',
            {'summary': 'New Title'}
        )
        
        assert result == updated_event
        mock_events.get.assert_called_once()
        mock_events.update.assert_called_once()
    
    @patch('services.google_calendar_service.build')
    def test_get_event_success(self, mock_build, service, mock_google_service):
        """Test successful event retrieval"""
        mock_service, mock_events = mock_google_service
        mock_build.return_value = mock_service
        
        # Mock API response
        event = {
            'id': 'event_123',
            'summary': 'Test Event'
        }
        mock_events.get.return_value.execute.return_value = event
        
        result = service.get_event('event_123')
        
        assert result == event
        mock_events.get.assert_called_once_with(
            calendarId='primary',
            eventId='event_123'
        )
    
    @patch('services.google_calendar_service.build')
    def test_get_event_not_found(self, mock_build, service, mock_google_service):
        """Test getting non-existent event"""
        mock_service, mock_events = mock_google_service
        mock_build.return_value = mock_service
        
        # Mock 404 error
        mock_events.get.return_value.execute.side_effect = HttpError(
            resp=Mock(status=404),
            content=b'Not Found'
        )
        
        result = service.get_event('nonexistent_event')
        assert result is None
    
    @patch('services.google_calendar_service.build')
    def test_list_calendars_success(self, mock_build, service, mock_google_service):
        """Test successful calendar listing"""
        mock_service, _ = mock_google_service
        mock_build.return_value = mock_service
        
        # Mock calendar list
        mock_calendar_list = MagicMock()
        mock_service.calendarList.return_value = mock_calendar_list
        mock_calendar_list.list.return_value.execute.return_value = {
            'items': [
                {'id': 'primary', 'summary': 'Primary Calendar'},
                {'id': 'work', 'summary': 'Work Calendar'}
            ]
        }
        
        calendars = service.list_calendars()
        
        assert len(calendars) == 2
        assert calendars[0]['summary'] == 'Primary Calendar'
        mock_calendar_list.list.assert_called_once()
    
    def test_list_calendars_no_credentials(self):
        """Test listing calendars without credentials"""
        service = GoogleCalendarService()  # No credentials
        calendars = service.list_calendars()
        assert calendars == []