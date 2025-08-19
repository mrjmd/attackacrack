"""
Test InvoiceService Refactored - Following TDD principles
Tests for the refactored InvoiceService with Result pattern and repository injection
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, date, timedelta
from decimal import Decimal

from services.invoice_service_refactored import InvoiceServiceRefactored
from services.common.result import Result
from crm_database import Invoice, Quote
from repositories.invoice_repository import InvoiceRepository
from repositories.quote_repository import QuoteRepository


class TestInvoiceServiceRefactored:
    """Test suite for refactored InvoiceService with dependency injection"""
    
    @pytest.fixture
    def mock_invoice_repository(self):
        """Create a mock InvoiceRepository"""
        repository = Mock(spec=InvoiceRepository)
        return repository
    
    @pytest.fixture
    def mock_quote_repository(self):
        """Create a mock QuoteRepository"""
        repository = Mock(spec=QuoteRepository)
        return repository
    
    @pytest.fixture
    def service(self, mock_invoice_repository, mock_quote_repository):
        """Create InvoiceService instance with mocked repositories"""
        # Add required methods to mocks
        mock_invoice_repository.get_all = Mock()
        mock_invoice_repository.get_by_id = Mock()
        mock_invoice_repository.create = Mock()
        mock_invoice_repository.update = Mock()
        mock_invoice_repository.delete = Mock()
        
        mock_quote_repository.get_by_id = Mock()
        mock_quote_repository.update = Mock()
        
        return InvoiceServiceRefactored(
            invoice_repository=mock_invoice_repository,
            quote_repository=mock_quote_repository
        )
    
    @pytest.fixture
    def sample_invoice(self):
        """Create a sample invoice for testing"""
        invoice = Invoice(
            id=1,
            job_id=101,
            status='Draft',
            subtotal=Decimal('1000.00'),
            tax_amount=Decimal('100.00'),
            total_amount=Decimal('1100.00'),
            amount_paid=Decimal('0.00'),
            balance_due=Decimal('1100.00'),
            invoice_date=date.today(),
            due_date=date.today() + timedelta(days=30),
            payment_status='unpaid'
        )
        return invoice
    
    @pytest.fixture
    def sample_quote(self):
        """Create a sample quote for testing"""
        quote = Quote(
            id=1,
            job_id=101,
            status='Sent',
            subtotal=Decimal('1000.00'),
            tax_amount=Decimal('100.00'),
            total_amount=Decimal('1100.00'),
            expiration_date=date.today() + timedelta(days=30)
        )
        return quote
    
    @pytest.fixture
    def valid_invoice_data(self):
        """Valid data for creating an invoice"""
        return {
            'job_id': 101,
            'subtotal': Decimal('1000.00'),
            'tax_amount': Decimal('100.00'),
            'due_date': date.today() + timedelta(days=30),
            'status': 'Draft'
        }

    # --- get_all_invoices Tests ---
    
    def test_get_all_invoices_success(self, service, mock_invoice_repository, sample_invoice):
        """Test successful retrieval of all invoices"""
        # Arrange
        invoices = [sample_invoice]
        mock_invoice_repository.get_all.return_value = invoices
        
        # Act
        result = service.get_all_invoices_result()
        
        # Assert
        assert result.is_success
        assert result.data == invoices
        mock_invoice_repository.get_all.assert_called_once()
    
    def test_get_all_invoices_empty_list(self, service, mock_invoice_repository):
        """Test retrieval when no invoices exist"""
        # Arrange
        mock_invoice_repository.get_all.return_value = []
        
        # Act
        result = service.get_all_invoices_result()
        
        # Assert
        assert result.is_success
        assert result.data == []
        mock_invoice_repository.get_all.assert_called_once()
    
    def test_get_all_invoices_repository_error(self, service, mock_invoice_repository):
        """Test handling of repository errors"""
        # Arrange
        mock_invoice_repository.get_all.side_effect = Exception("Database error")
        
        # Act
        result = service.get_all_invoices_result()
        
        # Assert
        assert result.is_failure
        assert "Failed to retrieve invoices" in result.error
        assert result.error_code == "INVOICE_RETRIEVAL_ERROR"

    # --- get_invoice_by_id Tests ---
    
    def test_get_invoice_by_id_success(self, service, mock_invoice_repository, sample_invoice):
        """Test successful retrieval of invoice by ID"""
        # Arrange
        invoice_id = 1
        mock_invoice_repository.get_by_id.return_value = sample_invoice
        
        # Act
        result = service.get_invoice_by_id_result(invoice_id)
        
        # Assert
        assert result.is_success
        assert result.data == sample_invoice
        mock_invoice_repository.get_by_id.assert_called_once_with(invoice_id)
    
    def test_get_invoice_by_id_not_found(self, service, mock_invoice_repository):
        """Test when invoice is not found"""
        # Arrange
        invoice_id = 999
        mock_invoice_repository.get_by_id.return_value = None
        
        # Act
        result = service.get_invoice_by_id_result(invoice_id)
        
        # Assert
        assert result.is_failure
        assert result.error == f"Invoice with ID {invoice_id} not found"
        assert result.error_code == "INVOICE_NOT_FOUND"
    
    def test_get_invoice_by_id_invalid_id(self, service):
        """Test with invalid invoice ID"""
        # Act
        result = service.get_invoice_by_id_result(None)
        
        # Assert
        assert result.is_failure
        assert "Invalid invoice ID" in result.error
        assert result.error_code == "INVALID_INPUT"
    
    def test_get_invoice_by_id_repository_error(self, service, mock_invoice_repository):
        """Test repository error handling"""
        # Arrange
        invoice_id = 1
        mock_invoice_repository.get_by_id.side_effect = Exception("Database error")
        
        # Act
        result = service.get_invoice_by_id_result(invoice_id)
        
        # Assert
        assert result.is_failure
        assert "Failed to retrieve invoice" in result.error
        assert result.error_code == "INVOICE_RETRIEVAL_ERROR"

    # --- create_invoice Tests ---
    
    def test_create_invoice_success(self, service, mock_invoice_repository, valid_invoice_data, sample_invoice):
        """Test successful invoice creation"""
        # Arrange
        mock_invoice_repository.create.return_value = sample_invoice
        
        # Act
        result = service.create_invoice(valid_invoice_data)
        
        # Assert
        assert result.is_success
        assert result.data == sample_invoice
        mock_invoice_repository.create.assert_called_once()
        
        # Verify the data passed to repository includes calculated total
        call_args = mock_invoice_repository.create.call_args[0][0]
        assert call_args['total_amount'] == Decimal('1100.00')
        assert call_args['balance_due'] == Decimal('1100.00')
        assert call_args['amount_paid'] == Decimal('0.00')
    
    def test_create_invoice_missing_required_fields(self, service):
        """Test creation with missing required fields"""
        # Arrange
        invalid_data = {'job_id': 101}  # Missing other required fields
        
        # Act
        result = service.create_invoice(invalid_data)
        
        # Assert
        assert result.is_failure
        assert "Missing required fields" in result.error
        assert result.error_code == "INVALID_INPUT"
    
    def test_create_invoice_invalid_job_id(self, service):
        """Test creation with invalid job_id"""
        # Arrange - job_id as invalid integer
        invalid_data = {
            'job_id': -1,  # Invalid but present
            'subtotal': Decimal('1000.00'),
            'due_date': date.today() + timedelta(days=30)
        }
        
        # Act
        result = service.create_invoice(invalid_data)
        
        # Assert
        assert result.is_failure
        assert "Invalid job_id" in result.error
        assert result.error_code == "INVALID_INPUT"
    
    def test_create_invoice_missing_job_id(self, service):
        """Test creation with missing job_id (None)"""
        # Arrange
        invalid_data = {
            'job_id': None,
            'subtotal': Decimal('1000.00'),
            'due_date': date.today() + timedelta(days=30)
        }
        
        # Act
        result = service.create_invoice(invalid_data)
        
        # Assert
        assert result.is_failure
        assert "Missing required fields: job_id" in result.error
        assert result.error_code == "INVALID_INPUT"
    
    def test_create_invoice_calculates_totals(self, service, mock_invoice_repository, sample_invoice):
        """Test that invoice creation calculates totals correctly"""
        # Arrange
        data = {
            'job_id': 101,
            'subtotal': Decimal('500.00'),
            'tax_amount': Decimal('50.00'),
            'due_date': date.today() + timedelta(days=30)
        }
        mock_invoice_repository.create.return_value = sample_invoice
        
        # Act
        result = service.create_invoice(data)
        
        # Assert
        assert result.is_success
        call_args = mock_invoice_repository.create.call_args[0][0]
        assert call_args['total_amount'] == Decimal('550.00')
        assert call_args['balance_due'] == Decimal('550.00')
        assert call_args['amount_paid'] == Decimal('0.00')
    
    def test_create_invoice_repository_error(self, service, mock_invoice_repository, valid_invoice_data):
        """Test repository error during creation"""
        # Arrange
        mock_invoice_repository.create.side_effect = Exception("Database error")
        
        # Act
        result = service.create_invoice(valid_invoice_data)
        
        # Assert
        assert result.is_failure
        assert "Failed to create invoice" in result.error
        assert result.error_code == "INVOICE_CREATION_ERROR"

    # --- update_invoice Tests ---
    
    def test_update_invoice_success(self, service, mock_invoice_repository, sample_invoice):
        """Test successful invoice update"""
        # Arrange
        invoice_id = 1
        update_data = {'status': 'Sent', 'subtotal': Decimal('1200.00')}
        # Create a mock updated invoice
        updated_invoice = Mock(spec=Invoice)
        updated_invoice.status = 'Sent'
        updated_invoice.subtotal = Decimal('1200.00')
        
        mock_invoice_repository.get_by_id.return_value = sample_invoice
        mock_invoice_repository.update.return_value = updated_invoice
        
        # Act
        result = service.update_invoice(invoice_id, update_data)
        
        # Assert
        assert result.is_success
        assert result.data == updated_invoice
        mock_invoice_repository.get_by_id.assert_called_once_with(invoice_id)
        mock_invoice_repository.update.assert_called_once()
    
    def test_update_invoice_not_found(self, service, mock_invoice_repository):
        """Test updating non-existent invoice"""
        # Arrange
        invoice_id = 999
        update_data = {'status': 'Sent'}
        mock_invoice_repository.get_by_id.return_value = None
        
        # Act
        result = service.update_invoice(invoice_id, update_data)
        
        # Assert
        assert result.is_failure
        assert result.error == f"Invoice with ID {invoice_id} not found"
        assert result.error_code == "INVOICE_NOT_FOUND"
        mock_invoice_repository.update.assert_not_called()
    
    def test_update_invoice_recalculates_totals_on_amount_change(self, service, mock_invoice_repository, sample_invoice):
        """Test that updating amounts recalculates totals"""
        # Arrange
        invoice_id = 1
        update_data = {'subtotal': Decimal('1200.00'), 'tax_amount': Decimal('120.00')}
        # Create a mock updated invoice
        updated_invoice = Mock(spec=Invoice)
        updated_invoice.subtotal = Decimal('1200.00')
        updated_invoice.tax_amount = Decimal('120.00')
        
        mock_invoice_repository.get_by_id.return_value = sample_invoice
        mock_invoice_repository.update.return_value = updated_invoice
        
        # Act
        result = service.update_invoice(invoice_id, update_data)
        
        # Assert
        assert result.is_success
        call_args = mock_invoice_repository.update.call_args[0]
        update_dict = call_args[1]
        assert update_dict['total_amount'] == Decimal('1320.00')
        assert update_dict['balance_due'] == Decimal('1320.00')  # Since amount_paid stays 0
    
    def test_update_invoice_repository_error(self, service, mock_invoice_repository, sample_invoice):
        """Test repository error during update"""
        # Arrange
        invoice_id = 1
        update_data = {'status': 'Sent'}
        mock_invoice_repository.get_by_id.return_value = sample_invoice
        mock_invoice_repository.update.side_effect = Exception("Database error")
        
        # Act
        result = service.update_invoice(invoice_id, update_data)
        
        # Assert
        assert result.is_failure
        assert "Failed to update invoice" in result.error
        assert result.error_code == "INVOICE_UPDATE_ERROR"

    # --- delete_invoice Tests ---
    
    def test_delete_invoice_success(self, service, mock_invoice_repository, sample_invoice):
        """Test successful invoice deletion"""
        # Arrange
        invoice_id = 1
        mock_invoice_repository.get_by_id.return_value = sample_invoice
        mock_invoice_repository.delete.return_value = True
        
        # Act
        result = service.delete_invoice(invoice_id)
        
        # Assert
        assert result.is_success
        assert result.data == sample_invoice
        mock_invoice_repository.get_by_id.assert_called_once_with(invoice_id)
        mock_invoice_repository.delete.assert_called_once_with(invoice_id)
    
    def test_delete_invoice_not_found(self, service, mock_invoice_repository):
        """Test deleting non-existent invoice"""
        # Arrange
        invoice_id = 999
        mock_invoice_repository.get_by_id.return_value = None
        
        # Act
        result = service.delete_invoice(invoice_id)
        
        # Assert
        assert result.is_failure
        assert result.error == f"Invoice with ID {invoice_id} not found"
        assert result.error_code == "INVOICE_NOT_FOUND"
        mock_invoice_repository.delete.assert_not_called()
    
    def test_delete_invoice_repository_error(self, service, mock_invoice_repository, sample_invoice):
        """Test repository error during deletion"""
        # Arrange
        invoice_id = 1
        mock_invoice_repository.get_by_id.return_value = sample_invoice
        mock_invoice_repository.delete.side_effect = Exception("Database error")
        
        # Act
        result = service.delete_invoice(invoice_id)
        
        # Assert
        assert result.is_failure
        assert "Failed to delete invoice" in result.error
        assert result.error_code == "INVOICE_DELETION_ERROR"

    # --- create_invoice_from_quote Tests ---
    
    def test_create_invoice_from_quote_success(self, service, mock_quote_repository, mock_invoice_repository, sample_quote, sample_invoice):
        """Test successful invoice creation from quote"""
        # Arrange
        quote_id = 1
        mock_quote_repository.get_by_id.return_value = sample_quote
        mock_quote_repository.update.return_value = sample_quote
        mock_invoice_repository.create.return_value = sample_invoice
        
        # Act
        result = service.create_invoice_from_quote(quote_id)
        
        # Assert
        assert result.is_success
        assert result.data == sample_invoice
        
        # Verify quote was retrieved
        mock_quote_repository.get_by_id.assert_called_once_with(quote_id)
        
        # Verify quote status was updated
        mock_quote_repository.update.assert_called_once()
        update_call_args = mock_quote_repository.update.call_args[0]
        assert update_call_args[1]['status'] == 'Accepted'
        
        # Verify invoice was created with correct data
        mock_invoice_repository.create.assert_called_once()
        create_call_args = mock_invoice_repository.create.call_args[0][0]
        assert create_call_args['job_id'] == sample_quote.job_id
        assert create_call_args['quote_id'] == quote_id
        assert create_call_args['subtotal'] == sample_quote.subtotal
        assert create_call_args['tax_amount'] == sample_quote.tax_amount
        assert create_call_args['status'] == 'Unpaid'
        assert create_call_args['payment_status'] == 'unpaid'
    
    def test_create_invoice_from_quote_not_found(self, service, mock_quote_repository, mock_invoice_repository):
        """Test creating invoice from non-existent quote"""
        # Arrange
        quote_id = 999
        mock_quote_repository.get_by_id.return_value = None
        
        # Act
        result = service.create_invoice_from_quote(quote_id)
        
        # Assert
        assert result.is_failure
        assert result.error == f"Quote with ID {quote_id} not found"
        assert result.error_code == "QUOTE_NOT_FOUND"
        mock_quote_repository.update.assert_not_called()
        mock_invoice_repository.create.assert_not_called()
    
    def test_create_invoice_from_quote_already_accepted(self, service, mock_quote_repository, sample_quote):
        """Test creating invoice from already accepted quote"""
        # Arrange
        quote_id = 1
        sample_quote.status = 'Accepted'
        mock_quote_repository.get_by_id.return_value = sample_quote
        
        # Act
        result = service.create_invoice_from_quote(quote_id)
        
        # Assert
        assert result.is_failure
        assert "Quote has already been accepted" in result.error
        assert result.error_code == "QUOTE_ALREADY_ACCEPTED"
    
    def test_create_invoice_from_quote_sets_due_date(self, service, mock_quote_repository, mock_invoice_repository, sample_quote, sample_invoice):
        """Test that due date is set correctly (30 days from now)"""
        # Arrange
        quote_id = 1
        mock_quote_repository.get_by_id.return_value = sample_quote
        mock_quote_repository.update.return_value = sample_quote
        mock_invoice_repository.create.return_value = sample_invoice
        
        # Act
        result = service.create_invoice_from_quote(quote_id)
        
        # Assert
        assert result.is_success
        create_call_args = mock_invoice_repository.create.call_args[0][0]
        expected_due_date = date.today() + timedelta(days=30)
        assert create_call_args['due_date'] == expected_due_date
    
    def test_create_invoice_from_quote_quote_update_error(self, service, mock_quote_repository, sample_quote):
        """Test error when updating quote status fails"""
        # Arrange
        quote_id = 1
        mock_quote_repository.get_by_id.return_value = sample_quote
        mock_quote_repository.update.side_effect = Exception("Database error")
        
        # Act
        result = service.create_invoice_from_quote(quote_id)
        
        # Assert
        assert result.is_failure
        assert "Failed to update quote status" in result.error
        assert result.error_code == "QUOTE_UPDATE_ERROR"
    
    def test_create_invoice_from_quote_invoice_creation_error(self, service, mock_quote_repository, mock_invoice_repository, sample_quote):
        """Test error when invoice creation fails"""
        # Arrange
        quote_id = 1
        mock_quote_repository.get_by_id.return_value = sample_quote
        mock_quote_repository.update.return_value = sample_quote
        mock_invoice_repository.create.side_effect = Exception("Database error")
        
        # Act
        result = service.create_invoice_from_quote(quote_id)
        
        # Assert
        assert result.is_failure
        assert "Failed to create invoice from quote" in result.error
        assert result.error_code == "INVOICE_CREATION_ERROR"

    # --- Additional Edge Cases ---
    
    def test_create_invoice_with_zero_amounts(self, service, mock_invoice_repository, sample_invoice):
        """Test creating invoice with zero amounts"""
        # Arrange
        data = {
            'job_id': 101,
            'subtotal': Decimal('0.00'),
            'tax_amount': Decimal('0.00'),
            'due_date': date.today() + timedelta(days=30)
        }
        mock_invoice_repository.create.return_value = sample_invoice
        
        # Act
        result = service.create_invoice(data)
        
        # Assert
        assert result.is_success
        call_args = mock_invoice_repository.create.call_args[0][0]
        assert call_args['total_amount'] == Decimal('0.00')
        assert call_args['balance_due'] == Decimal('0.00')
    
    def test_update_invoice_with_payment(self, service, mock_invoice_repository, sample_invoice):
        """Test updating invoice with payment information"""
        # Arrange
        invoice_id = 1
        update_data = {
            'amount_paid': Decimal('500.00'),
            'payment_status': 'partial'
        }
        # Create a mock updated invoice
        updated_invoice = Mock(spec=Invoice)
        updated_invoice.amount_paid = Decimal('500.00')
        updated_invoice.payment_status = 'partial'
        
        mock_invoice_repository.get_by_id.return_value = sample_invoice
        mock_invoice_repository.update.return_value = updated_invoice
        
        # Act
        result = service.update_invoice(invoice_id, update_data)
        
        # Assert
        assert result.is_success
        call_args = mock_invoice_repository.update.call_args[0]
        update_dict = call_args[1]
        # Balance due should be recalculated: total_amount - amount_paid
        expected_balance = sample_invoice.total_amount - Decimal('500.00')
        assert update_dict['balance_due'] == expected_balance
    
    def test_service_initialization_requires_dependencies(self):
        """Test service initialization requires repository dependencies"""
        # Act & Assert - Service should raise ValueError without repositories
        with pytest.raises(ValueError, match="Invoice and Quote repositories must be provided"):
            InvoiceServiceRefactored()
        
        # Test with proper dependencies
        mock_invoice_repo = Mock(spec=InvoiceRepository)
        mock_quote_repo = Mock(spec=QuoteRepository)
        service = InvoiceServiceRefactored(
            invoice_repository=mock_invoice_repo,
            quote_repository=mock_quote_repo
        )
        
        assert service.invoice_repository is mock_invoice_repo
        assert service.quote_repository is mock_quote_repo
        assert hasattr(service, 'logger')