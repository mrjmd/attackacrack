"""
AppointmentService - Refactored with dependency injection
Manages appointments with proper separation of concerns
"""

from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, timedelta
from extensions import db
from crm_database import Appointment, Contact
from services.google_calendar_service import GoogleCalendarService
from logging_config import get_logger

logger = get_logger(__name__)


class AppointmentService:
    """Service for managing appointments with Google Calendar integration"""
    
    def __init__(self, 
                 calendar_service: Optional[GoogleCalendarService] = None,
                 session=None):
        """
        Initialize AppointmentService with dependencies
        
        Args:
            calendar_service: GoogleCalendarService instance for calendar integration
            session: Database session (defaults to db.session)
        """
        self.calendar_service = calendar_service
        self.session = session or db.session
    
    def add_appointment(self, **kwargs) -> Appointment:
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
            Created Appointment instance
        """
        # Create the appointment in local database first
        new_appointment = Appointment(
            title=kwargs.get('title'),
            description=kwargs.get('description'),
            date=kwargs.get('date'),
            time=kwargs.get('time'),
            contact_id=kwargs.get('contact_id')
        )
        self.session.add(new_appointment)
        # Commit to get ID before calendar sync
        self.session.commit()
        
        # Sync to Google Calendar if service available and not disabled
        sync_to_calendar = kwargs.get('sync_to_calendar', True)
        if self.calendar_service and sync_to_calendar:
            calendar_event_id = self._sync_to_google_calendar(new_appointment, kwargs)
            if calendar_event_id:
                new_appointment.google_calendar_event_id = calendar_event_id
                self.session.commit()
        elif not self.calendar_service and sync_to_calendar:
            logger.warning(
                "Google Calendar sync requested but calendar service not available",
                appointment_id=new_appointment.id
            )
        
        return new_appointment
    
    def _sync_to_google_calendar(self, appointment: Appointment, options: Dict) -> Optional[str]:
        """
        Sync appointment to Google Calendar
        
        Args:
            appointment: Appointment instance to sync
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
    
    def _build_attendee_list(self, appointment: Appointment) -> List[str]:
        """
        Build list of attendee emails for calendar event
        
        Args:
            appointment: Appointment instance
            
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
    
    def _build_calendar_description(self, appointment: Appointment) -> str:
        """
        Build detailed description for calendar event
        
        Args:
            appointment: Appointment instance
            
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
    
    def _get_appointment_location(self, appointment: Appointment) -> Optional[str]:
        """
        Get appointment location from contact's property
        
        Args:
            appointment: Appointment instance
            
        Returns:
            Location string or None
        """
        if appointment.contact and appointment.contact.properties:
            # Use first property as location
            first_property = appointment.contact.properties[0]
            return first_property.address
        return None
    
    def get_all_appointments(self) -> List[Appointment]:
        """
        Get all appointments
        
        Returns:
            List of all Appointment instances
        """
        return self.session.query(Appointment).all()
    
    def get_appointment_by_id(self, appointment_id: int) -> Optional[Appointment]:
        """
        Get appointment by ID
        
        Args:
            appointment_id: ID of the appointment
            
        Returns:
            Appointment instance or None
        """
        return self.session.get(Appointment, appointment_id)
    
    def get_appointments_for_contact(self, contact_id: int) -> List[Appointment]:
        """
        Get all appointments for a specific contact
        
        Args:
            contact_id: ID of the contact
            
        Returns:
            List of Appointment instances for the contact
        """
        return self.session.query(Appointment).filter_by(contact_id=contact_id).all()
    
    def get_upcoming_appointments(self, days: int = 7) -> List[Appointment]:
        """
        Get upcoming appointments within specified days
        
        Args:
            days: Number of days to look ahead (default: 7)
            
        Returns:
            List of upcoming Appointment instances
        """
        from datetime import date
        today = date.today()
        end_date = today + timedelta(days=days)
        
        return self.session.query(Appointment).filter(
            Appointment.date >= today,
            Appointment.date <= end_date
        ).order_by(Appointment.date, Appointment.time).all()
    
    def update_appointment(self, appointment: Appointment, **kwargs) -> Appointment:
        """
        Update an existing appointment
        
        Args:
            appointment: Appointment instance to update
            **kwargs: Fields to update
            
        Returns:
            Updated Appointment instance
        """
        # Track if calendar sync is needed
        calendar_fields_changed = False
        calendar_fields = {'title', 'description', 'date', 'time'}
        
        for key, value in kwargs.items():
            if hasattr(appointment, key):
                setattr(appointment, key, value)
                if key in calendar_fields:
                    calendar_fields_changed = True
        
        self.session.commit()
        
        # Update Google Calendar if needed
        if (self.calendar_service and 
            appointment.google_calendar_event_id and 
            calendar_fields_changed):
            self._update_google_calendar_event(appointment)
        
        return appointment
    
    def _update_google_calendar_event(self, appointment: Appointment) -> bool:
        """
        Update the Google Calendar event for an appointment
        
        Args:
            appointment: Appointment with updated data
            
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
    
    def delete_appointment(self, appointment: Appointment) -> bool:
        """
        Delete an appointment and its Google Calendar event
        
        Args:
            appointment: Appointment instance to delete
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Delete Google Calendar event first if it exists
            if self.calendar_service and appointment.google_calendar_event_id:
                logger.info(
                    "Deleting Google Calendar event",
                    event_id=appointment.google_calendar_event_id,
                    appointment_id=appointment.id
                )
                calendar_deleted = self.calendar_service.delete_event(
                    appointment.google_calendar_event_id
                )
                if not calendar_deleted:
                    logger.warning(
                        "Failed to delete Google Calendar event",
                        event_id=appointment.google_calendar_event_id
                    )
            
            # Delete from local database
            self.session.delete(appointment)
            self.session.commit()
            
            logger.info("Successfully deleted appointment", appointment_id=appointment.id)
            return True
            
        except Exception as e:
            logger.error(
                "Error deleting appointment",
                appointment_id=appointment.id,
                error=str(e)
            )
            self.session.rollback()
            return False
    
    def reschedule_appointment(self, 
                              appointment: Appointment,
                              new_date: Any,
                              new_time: Any) -> Appointment:
        """
        Reschedule an appointment to a new date/time
        
        Args:
            appointment: Appointment to reschedule
            new_date: New date for the appointment
            new_time: New time for the appointment
            
        Returns:
            Updated Appointment instance
        """
        return self.update_appointment(
            appointment,
            date=new_date,
            time=new_time
        )
    
    def cancel_appointment(self, appointment: Appointment) -> Appointment:
        """
        Cancel an appointment (mark as cancelled rather than delete)
        
        Args:
            appointment: Appointment to cancel
            
        Returns:
            Updated Appointment instance
        """
        # Add a status field to track cancellation
        appointment.is_cancelled = True
        self.session.commit()
        
        # Remove from Google Calendar if synced
        if self.calendar_service and appointment.google_calendar_event_id:
            self.calendar_service.delete_event(appointment.google_calendar_event_id)
            appointment.google_calendar_event_id = None
            self.session.commit()
        
        logger.info("Appointment cancelled", appointment_id=appointment.id)
        return appointment