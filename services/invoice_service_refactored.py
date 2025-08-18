"""
InvoiceService Refactored - Following Result Pattern and Repository Pattern
Handles invoice management operations with proper dependency injection and error handling
"""

import logging
from typing import Optional, Dict, Any
from datetime import date, timedelta
from decimal import Decimal

from crm_database import Invoice, Quote, db
from services.common.result import Result
from repositories.invoice_repository import InvoiceRepository
from repositories.quote_repository import QuoteRepository

logger = logging.getLogger(__name__)


class InvoiceServiceRefactored:
    """
    Refactored InvoiceService using Result pattern and Repository pattern.
    
    This service handles all invoice-related business logic with:
    - Dependency injection for repositories
    - Result pattern for consistent error handling
    - No direct database queries (uses repositories)
    - Instance methods instead of static methods
    """
    
    def __init__(self, 
                 invoice_repository: Optional[InvoiceRepository] = None,
                 quote_repository: Optional[QuoteRepository] = None):
        """
        Initialize service with repository dependencies.
        
        Args:
            invoice_repository: Repository for invoice data access
            quote_repository: Repository for quote data access
        """
        # Use default repositories if not provided
        self.invoice_repository = invoice_repository or InvoiceRepository(db.session, Invoice)
        self.quote_repository = quote_repository or QuoteRepository(db.session, Quote)
        self.logger = logger
    
    def get_all_invoices(self) -> Result[list]:
        """
        Retrieve all invoices.
        
        Returns:
            Result containing list of invoices or error
        """
        try:
            invoices = self.invoice_repository.get_all()
            return Result.success(invoices)
        except Exception as e:
            self.logger.error(f"Error retrieving all invoices: {str(e)}")
            return Result.failure(
                "Failed to retrieve invoices",
                code="INVOICE_RETRIEVAL_ERROR"
            )
    
    def get_invoice_by_id(self, invoice_id: int) -> Result[Invoice]:
        """
        Retrieve an invoice by ID.
        
        Args:
            invoice_id: ID of the invoice to retrieve
            
        Returns:
            Result containing the invoice or error
        """
        if not invoice_id:
            return Result.failure(
                "Invalid invoice ID provided",
                code="INVALID_INPUT"
            )
        
        try:
            invoice = self.invoice_repository.get_by_id(invoice_id)
            if not invoice:
                return Result.failure(
                    f"Invoice with ID {invoice_id} not found",
                    code="INVOICE_NOT_FOUND"
                )
            return Result.success(invoice)
        except Exception as e:
            self.logger.error(f"Error retrieving invoice {invoice_id}: {str(e)}")
            return Result.failure(
                "Failed to retrieve invoice",
                code="INVOICE_RETRIEVAL_ERROR"
            )
    
    def create_invoice(self, data: Dict[str, Any]) -> Result[Invoice]:
        """
        Create a new invoice.
        
        Args:
            data: Dictionary containing invoice data
            
        Returns:
            Result containing the created invoice or error
        """
        # Validate job_id specifically first (more specific validation)
        if 'job_id' in data and data['job_id'] is not None:
            if not isinstance(data['job_id'], int) or data['job_id'] <= 0:
                return Result.failure(
                    "Invalid job_id provided",
                    code="INVALID_INPUT"
                )
        
        # Validate required fields
        required_fields = ['job_id', 'subtotal', 'due_date']
        missing_fields = [field for field in required_fields if field not in data or data[field] is None]
        
        if missing_fields:
            return Result.failure(
                f"Missing required fields: {', '.join(missing_fields)}",
                code="INVALID_INPUT"
            )
        
        try:
            # Prepare invoice data with calculated totals
            invoice_data = self._prepare_invoice_data(data)
            
            # Create the invoice
            invoice = self.invoice_repository.create(invoice_data)
            return Result.success(invoice)
            
        except Exception as e:
            self.logger.error(f"Error creating invoice: {str(e)}")
            return Result.failure(
                "Failed to create invoice",
                code="INVOICE_CREATION_ERROR"
            )
    
    def update_invoice(self, invoice_id: int, data: Dict[str, Any]) -> Result[Invoice]:
        """
        Update an existing invoice.
        
        Args:
            invoice_id: ID of the invoice to update
            data: Dictionary containing updated data
            
        Returns:
            Result containing the updated invoice or error
        """
        try:
            # Check if invoice exists
            existing_invoice = self.invoice_repository.get_by_id(invoice_id)
            if not existing_invoice:
                return Result.failure(
                    f"Invoice with ID {invoice_id} not found",
                    code="INVOICE_NOT_FOUND"
                )
            
            # Prepare update data with recalculated totals if amounts changed
            update_data = self._prepare_update_data(data, existing_invoice)
            
            # Update the invoice
            updated_invoice = self.invoice_repository.update(invoice_id, update_data)
            return Result.success(updated_invoice)
            
        except Exception as e:
            self.logger.error(f"Error updating invoice {invoice_id}: {str(e)}")
            return Result.failure(
                "Failed to update invoice",
                code="INVOICE_UPDATE_ERROR"
            )
    
    def delete_invoice(self, invoice_id: int) -> Result[Invoice]:
        """
        Delete an invoice.
        
        Args:
            invoice_id: ID of the invoice to delete
            
        Returns:
            Result containing the deleted invoice or error
        """
        try:
            # Check if invoice exists
            existing_invoice = self.invoice_repository.get_by_id(invoice_id)
            if not existing_invoice:
                return Result.failure(
                    f"Invoice with ID {invoice_id} not found",
                    code="INVOICE_NOT_FOUND"
                )
            
            # Delete the invoice
            self.invoice_repository.delete(invoice_id)
            return Result.success(existing_invoice)
            
        except Exception as e:
            self.logger.error(f"Error deleting invoice {invoice_id}: {str(e)}")
            return Result.failure(
                "Failed to delete invoice",
                code="INVOICE_DELETION_ERROR"
            )
    
    def create_invoice_from_quote(self, quote_id: int) -> Result[Invoice]:
        """
        Create an invoice from an existing quote.
        
        Args:
            quote_id: ID of the quote to convert
            
        Returns:
            Result containing the created invoice or error
        """
        try:
            # Retrieve the quote
            quote = self.quote_repository.get_by_id(quote_id)
            if not quote:
                return Result.failure(
                    f"Quote with ID {quote_id} not found",
                    code="QUOTE_NOT_FOUND"
                )
            
            # Check if quote is already accepted
            if quote.status == 'Accepted':
                return Result.failure(
                    "Quote has already been accepted and converted to an invoice",
                    code="QUOTE_ALREADY_ACCEPTED"
                )
            
            # Update quote status to 'Accepted'
            try:
                self.quote_repository.update(quote_id, {'status': 'Accepted'})
            except Exception as e:
                self.logger.error(f"Error updating quote {quote_id} status: {str(e)}")
                return Result.failure(
                    "Failed to update quote status",
                    code="QUOTE_UPDATE_ERROR"
                )
            
            # Prepare invoice data from quote
            invoice_data = {
                'job_id': quote.job_id,
                'quote_id': quote_id,
                'subtotal': quote.subtotal,
                'tax_amount': quote.tax_amount,
                'due_date': date.today() + timedelta(days=30),
                'status': 'Unpaid',
                'payment_status': 'unpaid'
            }
            
            # Calculate totals
            invoice_data = self._prepare_invoice_data(invoice_data)
            
            # Create the invoice
            invoice = self.invoice_repository.create(invoice_data)
            return Result.success(invoice)
            
        except Exception as e:
            self.logger.error(f"Error creating invoice from quote {quote_id}: {str(e)}")
            return Result.failure(
                "Failed to create invoice from quote",
                code="INVOICE_CREATION_ERROR"
            )
    
    def _prepare_invoice_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Prepare invoice data with calculated totals and defaults.
        
        Args:
            data: Raw invoice data
            
        Returns:
            Dictionary with calculated totals and defaults
        """
        prepared_data = data.copy()
        
        # Ensure decimal types
        subtotal = Decimal(str(data.get('subtotal', 0)))
        tax_amount = Decimal(str(data.get('tax_amount', 0)))
        amount_paid = Decimal(str(data.get('amount_paid', 0)))
        
        # Calculate totals
        total_amount = subtotal + tax_amount
        balance_due = total_amount - amount_paid
        
        # Set calculated values
        prepared_data.update({
            'subtotal': subtotal,
            'tax_amount': tax_amount,
            'total_amount': total_amount,
            'amount_paid': amount_paid,
            'balance_due': balance_due
        })
        
        # Set defaults
        if 'status' not in prepared_data:
            prepared_data['status'] = 'Draft'
        if 'payment_status' not in prepared_data:
            prepared_data['payment_status'] = 'unpaid'
        if 'invoice_date' not in prepared_data:
            prepared_data['invoice_date'] = date.today()
        
        return prepared_data
    
    def _prepare_update_data(self, data: Dict[str, Any], existing_invoice: Invoice) -> Dict[str, Any]:
        """
        Prepare update data with recalculated totals if needed.
        
        Args:
            data: Update data
            existing_invoice: Current invoice instance
            
        Returns:
            Dictionary with recalculated totals if amounts changed
        """
        update_data = data.copy()
        
        # Check if any amount fields are being updated
        amount_fields = ['subtotal', 'tax_amount', 'amount_paid']
        amounts_changed = any(field in data for field in amount_fields)
        
        if amounts_changed:
            # Get current and new values
            subtotal = Decimal(str(data.get('subtotal', existing_invoice.subtotal)))
            tax_amount = Decimal(str(data.get('tax_amount', existing_invoice.tax_amount)))
            amount_paid = Decimal(str(data.get('amount_paid', existing_invoice.amount_paid)))
            
            # Recalculate totals
            total_amount = subtotal + tax_amount
            balance_due = total_amount - amount_paid
            
            # Update the data
            update_data.update({
                'subtotal': subtotal,
                'tax_amount': tax_amount,
                'total_amount': total_amount,
                'amount_paid': amount_paid,
                'balance_due': balance_due
            })
        
        return update_data

# Alias for compatibility
InvoiceService = InvoiceServiceRefactored