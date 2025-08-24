"""
GoogleCalendarService - Extracted from api_integrations.py
Handles all Google Calendar API interactions with proper dependency injection
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from utils.datetime_utils import utc_now
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from logging_config import get_logger

logger = get_logger(__name__)


class GoogleCalendarService:
    """Service for interacting with Google Calendar API"""
    
    def __init__(self, credentials: Optional[Credentials] = None):
        """
        Initialize Google Calendar Service with credentials
        
        Args:
            credentials: Google OAuth2 credentials object
        """
        self.credentials = credentials
        self._service = None
    
    def _get_service(self):
        """Get or create the Google Calendar service instance"""
        if not self._service and self.credentials:
            try:
                self._service = build('calendar', 'v3', credentials=self.credentials)
            except Exception as e:
                logger.error("Failed to build Google Calendar service", error=str(e))
                return None
        return self._service
    
    def set_credentials(self, credentials: Credentials):
        """
        Update credentials (useful when tokens are refreshed)
        
        Args:
            credentials: New Google OAuth2 credentials
        """
        self.credentials = credentials
        self._service = None  # Force rebuild with new credentials
    
    def get_upcoming_events(self, count: int = 5, calendar_id: str = 'primary') -> List[Dict[str, Any]]:
        """
        Get upcoming calendar events
        
        Args:
            count: Number of events to retrieve
            calendar_id: Calendar ID (default: 'primary')
            
        Returns:
            List of event dictionaries
        """
        if not self.credentials:
            logger.warning("No credentials available for Google Calendar")
            return []
        
        service = self._get_service()
        if not service:
            return []
        
        try:
            now = utc_now().isoformat() + 'Z'  # 'Z' indicates UTC time
            events_result = service.events().list(
                calendarId=calendar_id,
                timeMin=now,
                maxResults=count,
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            events = events_result.get('items', [])
            logger.info(f"Retrieved {len(events)} upcoming events")
            return events
            
        except HttpError as e:
            logger.error(f"Google Calendar API error: {e}")
            return []
        except Exception as e:
            logger.error("Error fetching Google Calendar events", error=str(e))
            return []
    
    def create_event(self, 
                    title: str,
                    description: str,
                    start_time: datetime,
                    end_time: datetime,
                    attendees: List[str] = None,
                    location: Optional[str] = None,
                    timezone: str = 'America/New_York',
                    calendar_id: str = 'primary') -> Optional[Dict[str, Any]]:
        """
        Create a new calendar event
        
        Args:
            title: Event title/summary
            description: Event description
            start_time: Event start datetime
            end_time: Event end datetime
            attendees: List of attendee email addresses
            location: Event location (optional)
            timezone: Timezone for the event
            calendar_id: Calendar ID (default: 'primary')
            
        Returns:
            Created event dictionary or None on failure
        """
        if not self.credentials:
            logger.error("Cannot create event: No credentials available")
            return None
        
        service = self._get_service()
        if not service:
            return None
        
        try:
            event = {
                'summary': title,
                'description': description,
                'start': {
                    'dateTime': start_time.isoformat(),
                    'timeZone': timezone,
                },
                'end': {
                    'dateTime': end_time.isoformat(),
                    'timeZone': timezone,
                },
            }
            
            if attendees:
                event['attendees'] = [{'email': email} for email in attendees]
            
            if location:
                event['location'] = location
            
            created_event = service.events().insert(
                calendarId=calendar_id,
                body=event
            ).execute()
            
            logger.info(
                "Google Calendar event created",
                event_id=created_event.get('id'),
                event_link=created_event.get('htmlLink')
            )
            return created_event
            
        except HttpError as e:
            logger.error(f"Google Calendar API error creating event: {e}")
            return None
        except Exception as e:
            logger.error("Error creating Google Calendar event", error=str(e))
            return None
    
    def update_event(self,
                    event_id: str,
                    updates: Dict[str, Any],
                    calendar_id: str = 'primary') -> Optional[Dict[str, Any]]:
        """
        Update an existing calendar event
        
        Args:
            event_id: ID of the event to update
            updates: Dictionary of fields to update
            calendar_id: Calendar ID (default: 'primary')
            
        Returns:
            Updated event dictionary or None on failure
        """
        if not self.credentials:
            logger.error("Cannot update event: No credentials available")
            return None
        
        service = self._get_service()
        if not service:
            return None
        
        try:
            # First get the existing event
            event = service.events().get(
                calendarId=calendar_id,
                eventId=event_id
            ).execute()
            
            # Apply updates
            event.update(updates)
            
            # Update the event
            updated_event = service.events().update(
                calendarId=calendar_id,
                eventId=event_id,
                body=event
            ).execute()
            
            logger.info("Google Calendar event updated", event_id=event_id)
            return updated_event
            
        except HttpError as e:
            logger.error(f"Google Calendar API error updating event: {e}")
            return None
        except Exception as e:
            logger.error("Error updating Google Calendar event", event_id=event_id, error=str(e))
            return None
    
    def delete_event(self, event_id: str, calendar_id: str = 'primary') -> bool:
        """
        Delete a calendar event
        
        Args:
            event_id: ID of the event to delete
            calendar_id: Calendar ID (default: 'primary')
            
        Returns:
            True if successful, False otherwise
        """
        if not self.credentials:
            logger.error("Cannot delete event: No credentials available")
            return False
        
        service = self._get_service()
        if not service:
            return False
        
        try:
            service.events().delete(
                calendarId=calendar_id,
                eventId=event_id
            ).execute()
            
            logger.info("Successfully deleted Google Calendar event", event_id=event_id)
            return True
            
        except HttpError as e:
            if e.resp.status == 404:
                logger.warning(f"Event {event_id} not found, may already be deleted")
                return True  # Consider it successful if already deleted
            logger.error(f"Google Calendar API error deleting event: {e}")
            return False
        except Exception as e:
            logger.error("Error deleting Google Calendar event", event_id=event_id, error=str(e))
            return False
    
    def get_event(self, event_id: str, calendar_id: str = 'primary') -> Optional[Dict[str, Any]]:
        """
        Get a specific calendar event
        
        Args:
            event_id: ID of the event to retrieve
            calendar_id: Calendar ID (default: 'primary')
            
        Returns:
            Event dictionary or None if not found
        """
        if not self.credentials:
            logger.warning("No credentials available for Google Calendar")
            return None
        
        service = self._get_service()
        if not service:
            return None
        
        try:
            event = service.events().get(
                calendarId=calendar_id,
                eventId=event_id
            ).execute()
            
            return event
            
        except HttpError as e:
            if e.resp.status == 404:
                logger.warning(f"Event {event_id} not found")
            else:
                logger.error(f"Google Calendar API error: {e}")
            return None
        except Exception as e:
            logger.error("Error fetching Google Calendar event", event_id=event_id, error=str(e))
            return None
    
    def list_calendars(self) -> List[Dict[str, Any]]:
        """
        List all available calendars for the authenticated user
        
        Returns:
            List of calendar dictionaries
        """
        if not self.credentials:
            logger.warning("No credentials available for Google Calendar")
            return []
        
        service = self._get_service()
        if not service:
            return []
        
        try:
            calendar_list = service.calendarList().list().execute()
            calendars = calendar_list.get('items', [])
            logger.info(f"Retrieved {len(calendars)} calendars")
            return calendars
            
        except HttpError as e:
            logger.error(f"Google Calendar API error listing calendars: {e}")
            return []
        except Exception as e:
            logger.error("Error listing calendars", error=str(e))
            return []