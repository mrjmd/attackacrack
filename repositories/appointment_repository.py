"""
AppointmentRepository - Data access layer for Appointment model
"""

from typing import List, Optional
from datetime import date, datetime
from sqlalchemy import desc, asc, or_, and_
from repositories.base_repository import BaseRepository, PaginatedResult
from crm_database import Appointment


class AppointmentRepository(BaseRepository):
    """Repository for Appointment data access"""
    
    def __init__(self, session):
        """Initialize repository with database session"""
        super().__init__(session, Appointment)
    
    def find_by_contact_id(self, contact_id: int) -> List:
        """
        Find all appointments for a contact.
        
        Args:
            contact_id: ID of the contact
            
        Returns:
            List of Appointment objects ordered by date and time
        """
        return self.session.query(self.model_class)\
            .filter_by(contact_id=contact_id)\
            .order_by(asc(self.model_class.date), asc(self.model_class.time))\
            .all()
    
    def find_by_date(self, appointment_date: date) -> List:
        """
        Find all appointments on a specific date.
        
        Args:
            appointment_date: Date to search for
            
        Returns:
            List of Appointment objects ordered by time
        """
        return self.session.query(self.model_class)\
            .filter_by(date=appointment_date)\
            .order_by(asc(self.model_class.time))\
            .all()
    
    def find_by_date_range(self, start_date: date, end_date: date) -> List:
        """
        Find appointments within a date range.
        
        Args:
            start_date: Start of date range
            end_date: End of date range
            
        Returns:
            List of Appointment objects ordered by date and time
        """
        return self.session.query(self.model_class)\
            .filter(self.model_class.date >= start_date)\
            .filter(self.model_class.date <= end_date)\
            .order_by(asc(self.model_class.date), asc(self.model_class.time))\
            .all()
    
    def find_by_job_id(self, job_id: int) -> List:
        """
        Find all appointments for a specific job.
        
        Args:
            job_id: ID of the job
            
        Returns:
            List of Appointment objects ordered by date and time
        """
        return self.session.query(self.model_class)\
            .filter_by(job_id=job_id)\
            .order_by(asc(self.model_class.date), asc(self.model_class.time))\
            .all()
    
    def find_by_google_event_id(self, google_event_id: str) -> Optional:
        """
        Find appointment by Google Calendar event ID.
        
        Args:
            google_event_id: Google Calendar event ID
            
        Returns:
            Appointment object or None if not found
        """
        return self.session.query(self.model_class)\
            .filter_by(google_calendar_event_id=google_event_id)\
            .first()
    
    def find_upcoming_appointments(self, limit: int = 50) -> List:
        """
        Find upcoming appointments from today onwards.
        
        Args:
            limit: Maximum number of results
            
        Returns:
            List of upcoming Appointment objects
        """
        today = date.today()
        return self.session.query(self.model_class)\
            .filter(self.model_class.date >= today)\
            .order_by(asc(self.model_class.date), asc(self.model_class.time))\
            .limit(limit)\
            .all()
    
    def find_past_appointments(self, limit: int = 50) -> List:
        """
        Find past appointments before today.
        
        Args:
            limit: Maximum number of results
            
        Returns:
            List of past Appointment objects
        """
        today = date.today()
        return self.session.query(self.model_class)\
            .filter(self.model_class.date < today)\
            .order_by(desc(self.model_class.date), desc(self.model_class.time))\
            .limit(limit)\
            .all()
    
    def update_google_event_id(self, appointment_id: int, google_event_id: str):
        """
        Update the Google Calendar event ID for an appointment.
        
        Args:
            appointment_id: ID of the appointment
            google_event_id: New Google Calendar event ID
            
        Returns:
            Updated Appointment object
        """
        appointment = self.session.get(self.model_class, appointment_id)
        if appointment:
            appointment.google_calendar_event_id = google_event_id
            self.session.commit()
        return appointment
    
    def count_by_contact(self, contact_id: int) -> int:
        """
        Count appointments for a contact.
        
        Args:
            contact_id: ID of the contact
            
        Returns:
            Count of appointments
        """
        return self.session.query(self.model_class)\
            .filter_by(contact_id=contact_id)\
            .count()
    
    def search(self, query: str) -> List:
        """
        Search appointments by title or description.
        
        Args:
            query: Search query string
            
        Returns:
            List of matching Appointment objects
        """
        if not query:
            return []
        
        search_filter = or_(
            self.model_class.title.ilike(f'%{query}%'),
            self.model_class.description.ilike(f'%{query}%')
        )
        
        return self.session.query(self.model_class)\
            .filter(search_filter)\
            .limit(100)\
            .all()