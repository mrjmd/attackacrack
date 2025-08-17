"""
InvoiceRepository - Data access layer for Invoice model
"""

from typing import List, Optional
from datetime import date, datetime
from sqlalchemy import desc, asc, or_, and_
from repositories.base_repository import BaseRepository, PaginatedResult
from crm_database import Invoice, Job


class InvoiceRepository(BaseRepository):
    """Repository for Invoice data access"""
    
    def find_by_job_id(self, job_id: int) -> List:
        """
        Find all invoices for a job.
        
        Args:
            job_id: ID of the job
            
        Returns:
            List of Invoice objects
        """
        return self.session.query(self.model_class)\
            .filter_by(job_id=job_id)\
            .all()
    
    def find_by_status(self, status: str) -> List:
        """
        Find invoices by status.
        
        Args:
            status: Invoice status (Draft, Sent, etc.)
            
        Returns:
            List of Invoice objects
        """
        return self.session.query(self.model_class)\
            .filter_by(status=status)\
            .all()
    
    def find_by_payment_status(self, payment_status: str) -> List:
        """
        Find invoices by payment status.
        
        Args:
            payment_status: Payment status (unpaid, partial, paid, overdue)
            
        Returns:
            List of Invoice objects
        """
        return self.session.query(self.model_class)\
            .filter_by(payment_status=payment_status)\
            .all()
    
    def find_overdue_invoices(self) -> List:
        """
        Find all overdue invoices.
        
        Returns:
            List of overdue Invoice objects
        """
        today = date.today()
        return self.session.query(self.model_class)\
            .filter(self.model_class.due_date < today)\
            .filter(self.model_class.payment_status != 'paid')\
            .all()
    
    def find_by_quickbooks_id(self, quickbooks_id: str) -> Optional:
        """
        Find invoice by QuickBooks ID.
        
        Args:
            quickbooks_id: QuickBooks invoice ID
            
        Returns:
            Invoice object or None if not found
        """
        return self.session.query(self.model_class)\
            .filter_by(quickbooks_invoice_id=quickbooks_id)\
            .first()
    
    def update_payment_status(self, invoice_id: int, status: str, 
                            paid_date: Optional[datetime] = None):
        """
        Update invoice payment status.
        
        Args:
            invoice_id: ID of the invoice
            status: New payment status
            paid_date: Optional payment date
            
        Returns:
            Updated Invoice object
        """
        invoice = self.session.query(self.model_class).get(invoice_id)
        if invoice:
            invoice.payment_status = status
            if paid_date:
                invoice.paid_date = paid_date
            self.session.commit()
        return invoice
    
    def calculate_totals(self, invoice_id: int):
        """
        Calculate and update invoice totals.
        
        Args:
            invoice_id: ID of the invoice
            
        Returns:
            Updated Invoice object with calculated totals
        """
        invoice = self.session.query(self.model_class).get(invoice_id)
        if invoice:
            # Calculate total amount
            invoice.total_amount = invoice.subtotal + invoice.tax_amount
            # Calculate balance due
            invoice.balance_due = invoice.total_amount - invoice.amount_paid
            self.session.commit()
        return invoice
    
    def find_by_date_range(self, start_date: date, end_date: date) -> List:
        """
        Find invoices within a date range.
        
        Args:
            start_date: Start of date range
            end_date: End of date range
            
        Returns:
            List of Invoice objects
        """
        return self.session.query(self.model_class)\
            .filter(self.model_class.invoice_date >= start_date)\
            .filter(self.model_class.invoice_date <= end_date)\
            .all()
    
    def search(self, query: str) -> List:
        """
        Search invoices by QuickBooks ID or join with Job for broader search.
        
        Args:
            query: Search query string
            
        Returns:
            List of matching Invoice objects
        """
        if not query:
            return []
        
        # Search by QuickBooks ID or status
        search_filter = or_(
            self.model_class.quickbooks_invoice_id.ilike(f'%{query}%'),
            self.model_class.status.ilike(f'%{query}%')
        )
        
        return self.session.query(self.model_class)\
            .join(Job)\
            .filter(search_filter)\
            .distinct()\
            .limit(100)\
            .all()