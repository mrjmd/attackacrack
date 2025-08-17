"""
QuoteRepository - Data access layer for Quote model
"""

from typing import List, Optional
from datetime import date, datetime, timedelta
from sqlalchemy import desc, asc, or_, and_
from repositories.base_repository import BaseRepository, PaginatedResult
from crm_database import Quote, Job


class QuoteRepository(BaseRepository):
    """Repository for Quote data access"""
    
    def find_by_job_id(self, job_id: int) -> List:
        """
        Find all quotes for a job.
        
        Args:
            job_id: ID of the job
            
        Returns:
            List of Quote objects
        """
        return self.session.query(self.model_class)\
            .filter_by(job_id=job_id)\
            .all()
    
    def find_by_status(self, status: str) -> List:
        """
        Find quotes by status.
        
        Args:
            status: Quote status (Draft, Sent, Accepted, etc.)
            
        Returns:
            List of Quote objects
        """
        return self.session.query(self.model_class)\
            .filter_by(status=status)\
            .all()
    
    def find_by_quickbooks_id(self, quickbooks_id: str) -> Optional:
        """
        Find quote by QuickBooks estimate ID.
        
        Args:
            quickbooks_id: QuickBooks estimate ID
            
        Returns:
            Quote object or None if not found
        """
        return self.session.query(self.model_class)\
            .filter_by(quickbooks_estimate_id=quickbooks_id)\
            .first()
    
    def find_expiring_quotes(self, days: int = 7) -> List:
        """
        Find quotes expiring within specified days.
        
        Args:
            days: Number of days to look ahead
            
        Returns:
            List of Quote objects expiring soon
        """
        today = date.today()
        end_date = today + timedelta(days=days)
        
        return self.session.query(self.model_class)\
            .filter(self.model_class.expiration_date <= end_date)\
            .filter(self.model_class.expiration_date >= today)\
            .all()
    
    def calculate_totals(self, quote_id: int):
        """
        Calculate and update quote totals.
        
        Args:
            quote_id: ID of the quote
            
        Returns:
            Updated Quote object with calculated totals
        """
        quote = self.session.query(self.model_class).get(quote_id)
        if quote:
            # Calculate total amount
            quote.total_amount = quote.subtotal + quote.tax_amount
            self.session.commit()
        return quote
    
    def update_status(self, quote_id: int, status: str):
        """
        Update quote status.
        
        Args:
            quote_id: ID of the quote
            status: New status
            
        Returns:
            Updated Quote object
        """
        quote = self.session.query(self.model_class).get(quote_id)
        if quote:
            quote.status = status
            self.session.commit()
        return quote
    
    def find_by_date_range(self, start_date: date, end_date: date) -> List:
        """
        Find quotes within a date range.
        
        Args:
            start_date: Start of date range
            end_date: End of date range
            
        Returns:
            List of Quote objects
        """
        return self.session.query(self.model_class)\
            .filter(self.model_class.created_at >= start_date)\
            .filter(self.model_class.created_at <= end_date)\
            .all()
    
    def search(self, query: str) -> List:
        """
        Search quotes by QuickBooks ID or status.
        
        Args:
            query: Search query string
            
        Returns:
            List of matching Quote objects
        """
        if not query:
            return []
        
        # Search by QuickBooks ID or status
        search_filter = or_(
            self.model_class.quickbooks_estimate_id.ilike(f'%{query}%'),
            self.model_class.status.ilike(f'%{query}%')
        )
        
        return self.session.query(self.model_class)\
            .join(Job)\
            .filter(search_filter)\
            .distinct()\
            .limit(100)\
            .all()