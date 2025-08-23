"""
Tests for InvoiceRepository
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import date, datetime
from repositories.invoice_repository import InvoiceRepository
from repositories.base_repository import PaginatedResult
from crm_database import Invoice


class TestInvoiceRepository:
    """Test suite for InvoiceRepository"""
    
    @pytest.fixture
    def mock_session(self):
        """Mock database session"""
        session = MagicMock()
        return session
    
    @pytest.fixture
    def repository(self, mock_session):
        """Create InvoiceRepository with mocked session"""
        return InvoiceRepository(mock_session)
    
    def test_find_by_job_id(self, repository, mock_session):
        """Test finding invoices by job ID"""
        # Arrange
        mock_invoices = [Mock(id=1, job_id=123)]
        mock_query = Mock()
        mock_query.filter_by.return_value.all.return_value = mock_invoices
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.find_by_job_id(123)
        
        # Assert
        assert result == mock_invoices
        mock_query.filter_by.assert_called_once_with(job_id=123)
    
    def test_find_by_status(self, repository, mock_session):
        """Test finding invoices by status"""
        # Arrange
        mock_invoices = [Mock(id=1, status="Draft")]
        mock_query = Mock()
        mock_query.filter_by.return_value.all.return_value = mock_invoices
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.find_by_status("Draft")
        
        # Assert
        assert result == mock_invoices
        mock_query.filter_by.assert_called_once_with(status="Draft")
    
    def test_find_by_payment_status(self, repository, mock_session):
        """Test finding invoices by payment status"""
        # Arrange
        mock_invoices = [Mock(id=1, payment_status="unpaid")]
        mock_query = Mock()
        mock_query.filter_by.return_value.all.return_value = mock_invoices
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.find_by_payment_status("unpaid")
        
        # Assert
        assert result == mock_invoices
        mock_query.filter_by.assert_called_once_with(payment_status="unpaid")
    
    def test_find_overdue_invoices(self, repository, mock_session):
        """Test finding overdue invoices"""
        # Arrange
        mock_invoices = [Mock(id=1)]
        mock_query = Mock()
        # Chain the filter calls
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = mock_invoices
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.find_overdue_invoices()
        
        # Assert
        assert result == mock_invoices
        assert mock_query.filter.call_count == 2
    
    def test_find_by_quickbooks_id(self, repository, mock_session):
        """Test finding invoice by QuickBooks ID"""
        # Arrange
        mock_invoice = Mock(id=1, quickbooks_invoice_id="QB123")
        mock_query = Mock()
        mock_query.filter_by.return_value.first.return_value = mock_invoice
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.find_by_quickbooks_id("QB123")
        
        # Assert
        assert result == mock_invoice
        mock_query.filter_by.assert_called_once_with(quickbooks_invoice_id="QB123")
    
    def test_update_payment_status(self, repository, mock_session):
        """Test updating invoice payment status"""
        # Arrange
        mock_invoice = Mock(id=1, payment_status="unpaid")
        mock_query = Mock()
        mock_query.get.return_value = mock_invoice
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.update_payment_status(1, "paid", paid_date=datetime.utcnow())
        
        # Assert
        assert result == mock_invoice
        assert mock_invoice.payment_status == "paid"
        assert mock_invoice.paid_date is not None
        mock_session.commit.assert_called_once()
    
    def test_calculate_totals(self, repository, mock_session):
        """Test calculating invoice totals"""
        # Arrange
        mock_invoice = Mock(
            id=1, 
            subtotal=100.00,
            tax_amount=10.00,
            amount_paid=50.00
        )
        mock_query = Mock()
        mock_query.get.return_value = mock_invoice
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.calculate_totals(1)
        
        # Assert
        assert result == mock_invoice
        assert mock_invoice.total_amount == 110.00
        assert mock_invoice.balance_due == 60.00
        mock_session.commit.assert_called_once()
    
    def test_find_by_date_range(self, repository, mock_session):
        """Test finding invoices in date range"""
        # Arrange
        start_date = date(2025, 8, 1)
        end_date = date(2025, 8, 31)
        mock_invoices = [Mock(id=1)]
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = mock_invoices
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.find_by_date_range(start_date, end_date)
        
        # Assert
        assert result == mock_invoices
        assert mock_query.filter.call_count == 2
    
    def test_search(self, repository, mock_session):
        """Test searching invoices"""
        # Arrange
        mock_invoices = [Mock(id=1)]
        mock_query = Mock()
        mock_query.join.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.distinct.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = mock_invoices
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.search("QB123")
        
        # Assert
        assert result == mock_invoices
        mock_query.filter.assert_called()