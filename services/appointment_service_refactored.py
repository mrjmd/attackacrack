"""
AppointmentService - Refactored with dependency injection
Manages appointments with proper separation of concerns
"""

from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, timedelta, date
# Model and db imports removed - using repositories only
from services.google_calendar_service import GoogleCalendarService
from repositories.appointment_repository import AppointmentRepository
from services.common.result import Result
from logging_config import get_logger

logger = get_logger(__name__)


class AppointmentService:
    """Service for managing appointments with Google Calendar integration"""
    
    def __init__(self, 
                 appointment_repository: AppointmentRepository,
                 google_calendar_service: Optional[GoogleCalendarService] = None
    ):
        """
        Initialize AppointmentService with dependencies
        
        Args:
            appointment_repository: AppointmentRepository for data access
            google_calendar_service: GoogleCalendarService instance for calendar integration
        """
        if not appointment_repository:
            raise ValueError("AppointmentRepository must be provided via dependency injection")
        
        self.repository = appointment_repository
        self.calendar_service = google_calendar_service
    
    def add_appointment(self, **kwargs) -> Result[Dict]:
        """
        Add a new appointment with optional Google Calendar sync
        
        Args:
            title: Appointment title
            description: Appointment description
            date: Appointment date
            time: Appointment time
            contact_id: ID of the associated contact
            appt_type: Type of appointment (Assessment, Repair, Callback)
            sync_to_calendar: Whether to sync to Google Calendar (default: True)
            
        Returns:
            Result containing created Appointment instance
        """
        try:
            # Create the appointment using repository
            appointment_data = {
                'title': kwargs.get('title'),
                'description': kwargs.get('description'),
                'date': kwargs.get('date'),
                'time': kwargs.get('time'),
                'contact_id': kwargs.get('contact_id')
            }
            new_appointment = self.repository.create(**appointment_data)
            # Commit to get ID before calendar sync
            self.repository.commit()
            
            # Sync to Google Calendar if service available and not disabled
            sync_to_calendar = kwargs.get('sync_to_calendar', True)
            if self.calendar_service and sync_to_calendar:
                calendar_event_id = self._sync_to_google_calendar(new_appointment, kwargs)
                if calendar_event_id:
                    self.repository.update(new_appointment, google_calendar_event_id=calendar_event_id)
                    self.repository.commit()
            elif not self.calendar_service and sync_to_calendar:
                logger.warning(
                    "Google Calendar sync requested but calendar service not available",
                    appointment_id=new_appointment.id
                )
            
            return Result.success(new_appointment)
        except Exception as e:
            logger.error(f"Failed to add appointment: {str(e)}")
            self.repository.rollback()
            return Result.failure(f"Failed to add appointment: {str(e)}", code="APPOINTMENT_CREATE_ERROR")
    
    def _sync_to_google_calendar(self, appointment: Dict, options: Dict) -> Optional[str]:
        """
        Sync appointment to Google Calendar
        
        Args:
            appointment: Dict instance to sync
            options: Additional options (appt_type, etc.)
            
        Returns:
            Google Calendar event ID if successful, None otherwise
        """
        try:
            # Calculate appointment duration based on type
            start_datetime = datetime.combine(appointment.date, appointment.time)
            appt_type = options.get('appt_type', 'Assessment')
            duration_hours = self._get_appointment_duration(appt_type)
            end_datetime = start_datetime + timedelta(hours=duration_hours)
            
            # Build attendee list
            attendees = self._build_attendee_list(appointment)
            
            # Build description with contact info
            full_description = self._build_calendar_description(appointment)
            
            # Get location from contact's property
            location = self._get_appointment_location(appointment)
            
            # Create Google Calendar event
            created_event = self.calendar_service.create_event(
                title=appointment.title,
                description=full_description,
                start_time=start_datetime,
                end_time=end_datetime,
                attendees=attendees,
                location=location
            )
            
            if created_event:
                logger.info(
                    "Successfully synced appointment to Google Calendar",
                    appointment_id=appointment.id,
                    event_id=created_event.get('id')
                )
                return created_event.get('id')
            else:
                logger.warning(
                    "Failed to create Google Calendar event",
                    appointment_id=appointment.id
                )
                return None
                
        except Exception as e:
            logger.error(
                "Error syncing appointment to Google Calendar",
                error=str(e),
                appointment_id=appointment.id
            )
            return None
    
    def _get_appointment_duration(self, appt_type: str) -> float:
        """
        Get appointment duration in hours based on type
        
        Args:
            appt_type: Type of appointment
            
        Returns:
            Duration in hours
        """
        duration_map = {
            'Repair': 4.0,
            'Callback': 4.0,
            'Assessment': 0.5,
            'Inspection': 1.0,
            'Consultation': 1.0
        }
        return duration_map.get(appt_type, 0.5)
    
    def _build_attendee_list(self, appointment: Dict) -> List[str]:
        """
        Build list of attendee emails for calendar event
        
        Args:
            appointment: Dict instance
            
        Returns:
            List of email addresses
        """
        # Get default attendee from environment or config
        import os
        default_attendee = os.environ.get('DEFAULT_APPOINTMENT_ATTENDEE', 'mike.harrington.email@example.com')
        attendees = [default_attendee]
        
        # Add contact's email if available
        if appointment.contact and appointment.contact.email:
            attendees.append(appointment.contact.email)
        
        return attendees
    
    def _build_calendar_description(self, appointment: Dict) -> str:
        """
        Build detailed description for calendar event
        
        Args:
            appointment: Dict instance
            
        Returns:
            Formatted description string
        """
        description_parts = [appointment.description or ""]
        
        if appointment.contact:
            contact = appointment.contact
            contact_info = [
                "",  # Empty line
                "Customer Information:",
                f"Name: {contact.first_name} {contact.last_name}",
                f"Phone: {contact.phone}" if contact.phone else None,
                f"Email: {contact.email}" if contact.email else None
            ]
            # Filter out None values and join
            description_parts.extend([info for info in contact_info if info is not None])
        
        return "\n".join(description_parts)
    
    def _get_appointment_location(self, appointment: Dict) -> Optional[str]:
        """
        Get appointment location from contact's property
        
        Args:
            appointment: Dict instance
            
        Returns:
            Location string or None
        """
        if appointment.contact and appointment.contact.properties:
            # Use first property as location
            first_property = appointment.contact.properties[0]
            return first_property.address
        return None
    
    def get_all_appointments(self) -> Result[List[Dict]]:
        """
        Get all appointments
        
        Returns:
            Result containing list of all Appointment instances
        """
        try:
            appointments = self.repository.get_all()
            return Result.success(appointments)
        except Exception as e:
            logger.error(f"Failed to get all appointments: {str(e)}")
            return Result.failure(f"Failed to get all appointments: {str(e)}", code="APPOINTMENT_FETCH_ERROR")
    
    def get_appointment_by_id(self, appointment_id: int) -> Result[Optional[Dict]]:
        """
        Get appointment by ID
        
        Args:
            appointment_id: ID of the appointment
            
        Returns:
            Result containing Appointment instance or None
        """
        try:
            appointment = self.repository.get_by_id(appointment_id)
            if appointment:
                return Result.success(appointment)
            return Result.failure(f"Appointment with ID {appointment_id} not found", code="APPOINTMENT_NOT_FOUND")
        except Exception as e:
            logger.error(f"Failed to get appointment by ID: {str(e)}")
            return Result.failure(f"Failed to get appointment: {str(e)}", code="APPOINTMENT_FETCH_ERROR")
    
    def get_appointments_for_contact(self, contact_id: int) -> Result[List[Dict]]:
        """
        Get all appointments for a specific contact
        
        Args:
            contact_id: ID of the contact
            
        Returns:
            Result containing list of Appointment instances for the contact
        """
        try:
            appointments = self.repository.find_by_contact_id(contact_id)
            return Result.success(appointments)
        except Exception as e:
            logger.error(f"Failed to get appointments for contact: {str(e)}")
            return Result.failure(f"Failed to get appointments for contact: {str(e)}", code="APPOINTMENT_FETCH_ERROR")
    
    def get_upcoming_appointments(self, days: int = 7) -> Result[List[Dict]]:
        """
        Get upcoming appointments within specified days
        
        Args:
            days: Number of days to look ahead (default: 7)
            
        Returns:
            Result containing list of upcoming Appointment instances
        """
        try:
            today = date.today()
            end_date = today + timedelta(days=days)
            appointments = self.repository.find_by_date_range(today, end_date)
            return Result.success(appointments)
        except Exception as e:
            logger.error(f"Failed to get upcoming appointments: {str(e)}")
            return Result.failure(f"Failed to get upcoming appointments: {str(e)}", code="APPOINTMENT_FETCH_ERROR")
    
    def update_appointment(self, appointment: Dict, **kwargs) -> Result[Dict]:
        """
        Update an existing appointment
        
        Args:
            appointment: Dict instance to update
            **kwargs: Fields to update
            
        Returns:
            Result containing updated Appointment instance
        """
        try:
            # Track if calendar sync is needed
            calendar_fields_changed = False
            calendar_fields = {'title', 'description', 'date', 'time'}
            
            # Check which fields are changing
            for key in kwargs:
                if key in calendar_fields:
                    calendar_fields_changed = True
                    break
            
            # Update using repository
            appointment = self.repository.update(appointment, **kwargs)
            self.repository.commit()
            
            # Update Google Calendar if needed
            if (self.calendar_service and 
                hasattr(appointment, 'google_calendar_event_id') and
                appointment.google_calendar_event_id and 
                calendar_fields_changed):
                self._update_google_calendar_event(appointment)
            
            return Result.success(appointment)
        except Exception as e:
            logger.error(f"Failed to update appointment: {str(e)}")
            self.repository.rollback()
            return Result.failure(f"Failed to update appointment: {str(e)}", code="APPOINTMENT_UPDATE_ERROR")
    
    def _update_google_calendar_event(self, appointment: Dict) -> bool:
        """
        Update the Google Calendar event for an appointment
        
        Args:
            appointment: Dict with updated data
            
        Returns:
            True if successful, False otherwise
        """
        if not appointment.google_calendar_event_id:
            return False
        
        try:
            start_datetime = datetime.combine(appointment.date, appointment.time)
            # Use default duration for updates (can be enhanced)
            end_datetime = start_datetime + timedelta(hours=1)
            
            updates = {
                'summary': appointment.title,
                'description': self._build_calendar_description(appointment),
                'start': {
                    'dateTime': start_datetime.isoformat(),
                    'timeZone': 'America/New_York'
                },
                'end': {
                    'dateTime': end_datetime.isoformat(),
                    'timeZone': 'America/New_York'
                }
            }
            
            updated_event = self.calendar_service.update_event(
                appointment.google_calendar_event_id,
                updates
            )
            
            if updated_event:
                logger.info(
                    "Successfully updated Google Calendar event",
                    appointment_id=appointment.id,
                    event_id=appointment.google_calendar_event_id
                )
                return True
            
        except Exception as e:
            logger.error(
                "Failed to update Google Calendar event",
                appointment_id=appointment.id,
                event_id=appointment.google_calendar_event_id,
                error=str(e)
            )
        
        return False
    
    def delete_appointment(self, appointment: Dict) -> Result[bool]:
        """
        Delete an appointment and its Google Calendar event
        
        Args:
            appointment: Dict instance to delete
            
        Returns:
            Result containing True if successful, False otherwise
        """
        try:
            # Delete Google Calendar event first if it exists
            if self.calendar_service and hasattr(appointment, 'google_calendar_event_id') and appointment.google_calendar_event_id:
                logger.info(
                    "Deleting Google Calendar event",
                    event_id=appointment.google_calendar_event_id,
                    appointment_id=appointment.id if hasattr(appointment, 'id') else 'unknown'
                )
                calendar_deleted = self.calendar_service.delete_event(
                    appointment.google_calendar_event_id
                )
                if not calendar_deleted:
                    logger.warning(
                        "Failed to delete Google Calendar event",
                        event_id=appointment.google_calendar_event_id
                    )
            
            # Delete from local database using repository
            result = self.repository.delete(appointment)
            if result:
                self.repository.commit()
                logger.info("Successfully deleted appointment", appointment_id=appointment.id if hasattr(appointment, 'id') else 'unknown')
                return Result.success(True)
            return Result.failure("Failed to delete appointment from database", code="APPOINTMENT_DELETE_ERROR")
            
        except Exception as e:
            logger.error(
                "Error deleting appointment",
                appointment_id=appointment.id if hasattr(appointment, 'id') else 'unknown',
                error=str(e)
            )
            self.repository.rollback()
            return Result.failure(f"Failed to delete appointment: {str(e)}", code="APPOINTMENT_DELETE_ERROR")
    
    def reschedule_appointment(self, 
                              appointment: Dict,
                              new_date: Any,
                              new_time: Any) -> Result[Dict]:
        """
        Reschedule an appointment to a new date/time
        
        Args:
            appointment: Dict to reschedule
            new_date: New date for the appointment
            new_time: New time for the appointment
            
        Returns:
            Result containing updated Appointment instance
        """
        return self.update_appointment(
            appointment,
            date=new_date,
            time=new_time
        )
    
    def cancel_appointment(self, appointment: Dict) -> Result[Dict]:
        """
        Cancel an appointment (mark as cancelled rather than delete)
        
        Args:
            appointment: Dict to cancel
            
        Returns:
            Result containing updated Appointment instance
        """
        try:
            # Add a status field to track cancellation
            appointment = self.repository.update(appointment, is_cancelled=True)
            self.repository.commit()
            
            # Remove from Google Calendar if synced
            if self.calendar_service and hasattr(appointment, 'google_calendar_event_id') and appointment.google_calendar_event_id:
                self.calendar_service.delete_event(appointment.google_calendar_event_id)
                appointment = self.repository.update(appointment, google_calendar_event_id=None)
                self.repository.commit()
            
            logger.info("Appointment cancelled", appointment_id=appointment.id if hasattr(appointment, 'id') else 'unknown')
            return Result.success(appointment)
        except Exception as e:
            logger.error(f"Failed to cancel appointment: {str(e)}")
            self.repository.rollback()
            return Result.failure(f"Failed to cancel appointment: {str(e)}", code="APPOINTMENT_CANCEL_ERROR")