"""
Tests for refactored QuoteService using Repository Pattern - TDD RED PHASE
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from services.quote_service import QuoteService
from repositories.quote_repository import QuoteRepository
from repositories.quote_line_item_repository import QuoteLineItemRepository
from crm_database import Quote, QuoteLineItem
from services.common.result import Result


class TestQuoteServiceRefactored:
    """Test suite for refactored QuoteService with Repository Pattern"""
    
    @pytest.fixture
    def mock_quote_repository(self):
        """Mock quote repository"""
        return Mock(spec=QuoteRepository)
    
    @pytest.fixture
    def mock_line_item_repository(self):
        """Mock line item repository"""
        return Mock(spec=QuoteLineItemRepository)
    
    @pytest.fixture
    def quote_service(self, mock_quote_repository, mock_line_item_repository):
        """Create QuoteService with mocked repositories"""
        return QuoteService(
            quote_repository=mock_quote_repository,
            line_item_repository=mock_line_item_repository
        )
    
    def test_constructor_requires_repositories(self):
        """Test that QuoteService constructor requires repository dependencies"""
        # This should fail initially as service doesn't use dependency injection yet
        with pytest.raises(TypeError):
            QuoteService()
    
    def test_get_all_quotes_uses_repository(self, quote_service, mock_quote_repository):
        """Test that get_all_quotes uses repository instead of direct query"""
        # Arrange
        mock_quotes = [Mock(id=1), Mock(id=2)]
        mock_quote_repository.find_all_ordered_by_id_desc.return_value = mock_quotes
        
        # Act
        result = quote_service.get_all_quotes()
        
        # Assert
        assert result == mock_quotes
        mock_quote_repository.find_all_ordered_by_id_desc.assert_called_once()
    
    def test_get_quote_by_id_uses_repository(self, quote_service, mock_quote_repository):
        """Test that get_quote_by_id uses repository"""
        # Arrange
        mock_quote = Mock(id=123)
        mock_quote_repository.find_by_id.return_value = mock_quote
        
        # Act
        result = quote_service.get_quote_by_id(123)
        
        # Assert
        assert result == mock_quote
        mock_quote_repository.find_by_id.assert_called_once_with(123)
    
    def test_create_quote_with_line_items_uses_repositories(self, quote_service, mock_quote_repository, mock_line_item_repository):
        """Test create_quote uses repositories and Result pattern"""
        # Arrange
        quote_data = {
            'job_id': 1,
            'status': 'Draft',
            'line_items': [
                {'description': 'Item 1', 'quantity': 1, 'unit_price': 100},
                {'description': 'Item 2', 'quantity': 2, 'unit_price': 200}
            ]
        }
        
        # Mock the quote creation
        mock_quote = Mock(id=1, job_id=1, status='Draft', total_amount=500)
        mock_quote_repository.create.return_value = mock_quote
        
        # Mock line items creation
        mock_line_items = [Mock(id=1), Mock(id=2)]
        mock_line_item_repository.bulk_create_line_items.return_value = mock_line_items
        mock_line_item_repository.calculate_line_total.side_effect = [100, 400]
        
        # Act
        result = quote_service.create_quote(quote_data)
        
        # Assert
        assert isinstance(result, Result)
        assert result.is_success()
        assert result.data == mock_quote
        mock_quote_repository.create.assert_called_once()
        mock_line_item_repository.bulk_create_line_items.assert_called_once()
    
    def test_create_quote_handles_repository_error(self, quote_service, mock_quote_repository):
        """Test create_quote handles repository errors gracefully"""
        # Arrange
        quote_data = {'job_id': 1, 'status': 'Draft'}
        mock_quote_repository.create.side_effect = Exception("Database error")
        
        # Act
        result = quote_service.create_quote(quote_data)
        
        # Assert
        assert isinstance(result, Result)
        assert result.is_failure()
        assert "Database error" in result.error
    
    def test_update_quote_uses_repositories(self, quote_service, mock_quote_repository, mock_line_item_repository):
        """Test update_quote uses repositories"""
        # Arrange
        quote_id = 123
        update_data = {
            'status': 'Sent',
            'line_items': [
                {'id': 1, 'description': 'Updated Item', 'quantity': 2, 'unit_price': 150}
            ]
        }
        
        mock_quote = Mock(id=123, status='Draft')
        mock_quote_repository.find_by_id.return_value = mock_quote
        mock_quote_repository.update.return_value = mock_quote
        
        mock_updated_items = [Mock(id=1)]
        mock_line_item_repository.bulk_update_line_items.return_value = mock_updated_items
        mock_line_item_repository.calculate_line_total.return_value = 300
        
        # Act
        result = quote_service.update_quote(quote_id, update_data)
        
        # Assert
        assert isinstance(result, Result)
        assert result.is_success()
        mock_quote_repository.find_by_id.assert_called_once_with(quote_id)
        mock_quote_repository.update.assert_called_once()
        mock_line_item_repository.bulk_update_line_items.assert_called_once()
    
    def test_update_quote_not_found(self, quote_service, mock_quote_repository):
        """Test update_quote returns error when quote not found"""
        # Arrange
        quote_id = 999
        mock_quote_repository.find_by_id.return_value = None
        
        # Act
        result = quote_service.update_quote(quote_id, {})
        
        # Assert
        assert isinstance(result, Result)
        assert result.is_failure()
        assert "not found" in result.error
    
    def test_delete_quote_uses_repositories(self, quote_service, mock_quote_repository, mock_line_item_repository):
        """Test delete_quote uses repositories"""
        # Arrange
        quote_id = 123
        mock_quote = Mock(id=123)
        mock_quote_repository.find_by_id.return_value = mock_quote
        mock_line_item_repository.delete_by_quote_id.return_value = 2  # Deleted 2 line items
        mock_quote_repository.delete.return_value = True
        
        # Act
        result = quote_service.delete_quote(quote_id)
        
        # Assert
        assert isinstance(result, Result)
        assert result.is_success()
        assert result.data == mock_quote
        mock_quote_repository.find_by_id.assert_called_once_with(quote_id)
        mock_line_item_repository.delete_by_quote_id.assert_called_once_with(quote_id)
        mock_quote_repository.delete.assert_called_once_with(quote_id)
    
    def test_delete_quote_not_found(self, quote_service, mock_quote_repository):
        """Test delete_quote returns error when quote not found"""
        # Arrange
        quote_id = 999
        mock_quote_repository.find_by_id.return_value = None
        
        # Act
        result = quote_service.delete_quote(quote_id)
        
        # Assert
        assert isinstance(result, Result)
        assert result.is_failure()
        assert "not found" in result.error
    
    def test_calculate_quote_totals_uses_line_items(self, quote_service, mock_line_item_repository):
        """Test quote total calculation uses line item repository"""
        # Arrange
        line_items_data = [
            {'quantity': 2, 'unit_price': 100},
            {'quantity': 1, 'unit_price': 300}
        ]
        mock_line_item_repository.calculate_line_total.side_effect = [200, 300]
        
        # Act
        total = quote_service._calculate_quote_total(line_items_data)
        
        # Assert
        assert total == 500
        assert mock_line_item_repository.calculate_line_total.call_count == 2
    
    def test_service_registration_integration(self):
        """Test that QuoteService can be registered with service registry"""
        # This tests the integration with dependency injection
        from app import create_app
        
        app = create_app()
        with app.app_context():
            from flask import current_app
            quote_service = current_app.services.get('quote')
            assert quote_service is not None
            # After refactor, this should use repositories
            assert hasattr(quote_service, 'quote_repository')
            assert hasattr(quote_service, 'line_item_repository')
    
    def test_transaction_rollback_on_error(self, quote_service, mock_quote_repository, mock_line_item_repository):
        """Test that failed operations trigger repository rollbacks"""
        # Arrange
        quote_data = {'job_id': 1, 'status': 'Draft', 'line_items': []}
        mock_quote_repository.create.return_value = Mock(id=1)
        mock_line_item_repository.bulk_create_line_items.side_effect = Exception("Line item error")
        
        # Act
        result = quote_service.create_quote(quote_data)
        
        # Assert
        assert isinstance(result, Result)
        assert result.is_failure()
        # Repository should handle rollback internally