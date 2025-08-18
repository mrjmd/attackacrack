"""
Tests for QuoteRepository
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import date, datetime
from repositories.quote_repository import QuoteRepository
from repositories.base_repository import PaginatedResult
from crm_database import Quote


class TestQuoteRepository:
    """Test suite for QuoteRepository"""
    
    @pytest.fixture
    def mock_session(self):
        """Mock database session"""
        session = MagicMock()
        return session
    
    @pytest.fixture
    def repository(self, mock_session):
        """Create QuoteRepository with mocked session"""
        return QuoteRepository(mock_session, Quote)
    
    def test_find_by_job_id(self, repository, mock_session):
        """Test finding quotes by job ID"""
        # Arrange
        mock_quotes = [Mock(id=1, job_id=123)]
        mock_query = Mock()
        mock_query.filter_by.return_value.all.return_value = mock_quotes
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.find_by_job_id(123)
        
        # Assert
        assert result == mock_quotes
        mock_query.filter_by.assert_called_once_with(job_id=123)
    
    def test_find_by_status(self, repository, mock_session):
        """Test finding quotes by status"""
        # Arrange
        mock_quotes = [Mock(id=1, status="Draft")]
        mock_query = Mock()
        mock_query.filter_by.return_value.all.return_value = mock_quotes
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.find_by_status("Draft")
        
        # Assert
        assert result == mock_quotes
        mock_query.filter_by.assert_called_once_with(status="Draft")
    
    def test_find_by_quickbooks_id(self, repository, mock_session):
        """Test finding quote by QuickBooks ID"""
        # Arrange
        mock_quote = Mock(id=1, quickbooks_estimate_id="QB123")
        mock_query = Mock()
        mock_query.filter_by.return_value.first.return_value = mock_quote
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.find_by_quickbooks_id("QB123")
        
        # Assert
        assert result == mock_quote
        mock_query.filter_by.assert_called_once_with(quickbooks_estimate_id="QB123")
    
    def test_find_expiring_quotes(self, repository, mock_session):
        """Test finding quotes expiring soon"""
        # Arrange
        mock_quotes = [Mock(id=1)]
        mock_query = Mock()
        # Chain the filter calls
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = mock_quotes
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.find_expiring_quotes(days=7)
        
        # Assert
        assert result == mock_quotes
        assert mock_query.filter.call_count == 2
    
    def test_calculate_totals(self, repository, mock_session):
        """Test calculating quote totals"""
        # Arrange
        mock_quote = Mock(id=1, subtotal=100.00, tax_amount=10.00)
        mock_query = Mock()
        mock_query.get.return_value = mock_quote
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.calculate_totals(1)
        
        # Assert
        assert result == mock_quote
        assert mock_quote.total_amount == 110.00
        mock_session.commit.assert_called_once()
    
    def test_update_status(self, repository, mock_session):
        """Test updating quote status"""
        # Arrange
        mock_quote = Mock(id=1, status="Draft")
        mock_query = Mock()
        mock_query.get.return_value = mock_quote
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.update_status(1, "Sent")
        
        # Assert
        assert result == mock_quote
        assert mock_quote.status == "Sent"
        mock_session.commit.assert_called_once()
    
    def test_find_by_date_range(self, repository, mock_session):
        """Test finding quotes in date range"""
        # Arrange
        start_date = date(2025, 8, 1)
        end_date = date(2025, 8, 31)
        mock_quotes = [Mock(id=1)]
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = mock_quotes
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.find_by_date_range(start_date, end_date)
        
        # Assert
        assert result == mock_quotes
        assert mock_query.filter.call_count == 2
    
    def test_search(self, repository, mock_session):
        """Test searching quotes"""
        # Arrange
        mock_quotes = [Mock(id=1)]
        mock_query = Mock()
        mock_query.join.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.distinct.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = mock_quotes
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.search("QB123")
        
        # Assert
        assert result == mock_quotes
        mock_query.filter.assert_called()


class TestQuoteRepositorySchedulerMethods:
    """Test specialized methods for scheduler service needs"""
    
    @pytest.fixture
    def mock_session(self):
        """Mock database session"""
        return MagicMock()
    
    @pytest.fixture
    def repository(self, mock_session):
        """Create QuoteRepository instance"""
        return QuoteRepository(mock_session, Quote)
    
    def test_find_draft_quotes_by_job_id(self, repository, mock_session):
        """Test finding draft quotes by job ID (scheduler service pattern)"""
        # Arrange
        job_id = 123
        mock_draft_quotes = [
            Mock(id=1, job_id=123, status='Draft'),
            Mock(id=2, job_id=123, status='Draft')
        ]
        
        mock_query = Mock()
        mock_query.filter_by.return_value.all.return_value = mock_draft_quotes
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.find_draft_quotes_by_job_id(job_id)
        
        # Assert
        assert result == mock_draft_quotes
        mock_query.filter_by.assert_called_once_with(job_id=job_id, status='Draft')
    
    def test_find_draft_quotes_by_job_id_no_results(self, repository, mock_session):
        """Test finding draft quotes when none exist for job"""
        # Arrange
        job_id = 999
        
        mock_query = Mock()
        mock_query.filter_by.return_value.all.return_value = []
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.find_draft_quotes_by_job_id(job_id)
        
        # Assert
        assert result == []
        mock_query.filter_by.assert_called_once_with(job_id=job_id, status='Draft')
    
    def test_find_draft_quotes_excludes_other_statuses(self, repository, mock_session):
        """Test that only Draft status quotes are returned"""
        # Arrange - This test verifies the filter is correct
        job_id = 456
        mock_draft_quotes = [Mock(id=3, job_id=456, status='Draft')]
        
        mock_query = Mock()
        mock_query.filter_by.return_value.all.return_value = mock_draft_quotes
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.find_draft_quotes_by_job_id(job_id)
        
        # Assert
        assert all(quote.status == 'Draft' for quote in result)
        mock_query.filter_by.assert_called_once_with(job_id=job_id, status='Draft')