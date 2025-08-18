"""
JobRepository - Data access layer for Job model
"""

from typing import List, Optional
from datetime import date, datetime
from repositories.base_repository import BaseRepository
from sqlalchemy import desc, asc, or_, and_, func


class JobRepository(BaseRepository):
    """Repository for Job data access"""
    
    def find_completed_jobs_by_date(self, completion_date: date) -> List:
        """
        Find completed jobs by completion date.
        
        This method is specifically designed for scheduler service needs,
        matching the pattern from scheduler_service.py line 66-69:
        Job.query.filter(Job.status == 'Completed', db.func.date(Job.completed_at) == yesterday).all()
        
        Args:
            completion_date: Date to filter completed jobs by
            
        Returns:
            List of Job objects completed on the specified date
        """
        return self.session.query(self.model_class)\
            .filter(
                self.model_class.status == 'Completed',
                func.date(self.model_class.completed_at) == completion_date
            )\
            .all()
    
    def search(self, query: str, fields: Optional[List[str]] = None) -> List:
        """
        Search jobs by description.
        
        Args:
            query: Search query string
            fields: Fields to search in (ignored, searches description by default)
            
        Returns:
            List of matching Job objects
        """
        if not query:
            return []
        
        search_filter = self.model_class.description.ilike(f'%{query}%')
        
        return self.session.query(self.model_class)\
            .filter(search_filter)\
            .limit(100)\
            .all()
    
    def find_active_job_by_property_id(self, property_id: int) -> Optional:
        """
        Find the active job for a given property.
        
        This method supports JobService.get_or_create_active_job() line 18-21:
        self.session.query(Job).filter_by(property_id=property_id, status='Active').first()
        
        Args:
            property_id: ID of the property to find active job for
            
        Returns:
            Job object if found, None otherwise
        """
        return self.session.query(self.model_class)\
            .filter_by(
                property_id=property_id,
                status='Active'
            )\
            .first()