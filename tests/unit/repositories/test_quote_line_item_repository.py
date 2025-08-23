"""
Tests for QuoteLineItemRepository - TDD RED PHASE
"""

import pytest
from unittest.mock import Mock, MagicMock
from repositories.quote_line_item_repository import QuoteLineItemRepository
from crm_database import QuoteLineItem


class TestQuoteLineItemRepository:
    """Test suite for QuoteLineItemRepository"""
    
    @pytest.fixture
    def mock_session(self):
        """Mock database session"""
        session = MagicMock()
        return session
    
    @pytest.fixture
    def repository(self, mock_session):
        """Create QuoteLineItemRepository with mocked session"""
        return QuoteLineItemRepository(mock_session)
    
    def test_find_by_quote_id(self, repository, mock_session):
        """Test finding line items by quote ID"""
        # Arrange
        mock_line_items = [
            Mock(id=1, quote_id=123, description="Item 1"),
            Mock(id=2, quote_id=123, description="Item 2")
        ]
        mock_query = Mock()
        mock_query.filter_by.return_value.all.return_value = mock_line_items
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.find_by_quote_id(123)
        
        # Assert
        assert result == mock_line_items
        mock_query.filter_by.assert_called_once_with(quote_id=123)
    
    def test_find_by_product_id(self, repository, mock_session):
        """Test finding line items by product ID"""
        # Arrange
        mock_line_items = [Mock(id=1, product_id=456)]
        mock_query = Mock()
        mock_query.filter_by.return_value.all.return_value = mock_line_items
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.find_by_product_id(456)
        
        # Assert
        assert result == mock_line_items
        mock_query.filter_by.assert_called_once_with(product_id=456)
    
    def test_delete_by_quote_id(self, repository, mock_session):
        """Test deleting all line items for a quote"""
        # Arrange
        mock_line_items = [Mock(id=1), Mock(id=2)]
        repository.find_by_quote_id = Mock(return_value=mock_line_items)
        repository.delete = Mock(return_value=True)  # Mock the base delete method
        
        # Act
        count = repository.delete_by_quote_id(123)
        
        # Assert
        assert count == 2
        repository.find_by_quote_id.assert_called_once_with(123)
        assert repository.delete.call_count == 2  # Check delete was called for each item
    
    def test_calculate_line_total(self, repository):
        """Test calculating line total for a line item"""
        # Arrange
        line_item_data = {
            'quantity': 2.5,
            'unit_price': 100.50
        }
        
        # Act
        total = repository.calculate_line_total(line_item_data)
        
        # Assert
        expected_total = 2.5 * 100.50
        assert abs(total - expected_total) < 0.01
    
    def test_calculate_line_total_zero_values(self, repository):
        """Test calculating line total with zero values"""
        # Arrange
        line_item_data = {
            'quantity': 0,
            'unit_price': 100.50
        }
        
        # Act
        total = repository.calculate_line_total(line_item_data)
        
        # Assert
        assert total == 0
    
    def test_bulk_create_line_items(self, repository, mock_session):
        """Test creating multiple line items at once"""
        # Arrange
        line_items_data = [
            {'description': 'Item 1', 'quantity': 1, 'unit_price': 100},
            {'description': 'Item 2', 'quantity': 2, 'unit_price': 200}
        ]
        quote_id = 123
        
        # Act
        created_items = repository.bulk_create_line_items(quote_id, line_items_data)
        
        # Assert
        assert len(created_items) == 2
        assert mock_session.add_all.called
        mock_session.commit.assert_called_once()
    
    def test_bulk_update_line_items(self, repository, mock_session):
        """Test updating multiple line items"""
        # Arrange
        existing_item_1 = Mock(id=1, description="Old 1")
        existing_item_2 = Mock(id=2, description="Old 2")
        mock_session.get.side_effect = [existing_item_1, existing_item_2]
        
        line_items_data = [
            {'id': 1, 'description': 'Updated Item 1', 'quantity': 1, 'unit_price': 150},
            {'id': 2, 'description': 'Updated Item 2', 'quantity': 3, 'unit_price': 250}
        ]
        
        # Act
        updated_items = repository.bulk_update_line_items(line_items_data)
        
        # Assert
        assert len(updated_items) == 2
        assert existing_item_1.description == 'Updated Item 1'
        assert existing_item_2.description == 'Updated Item 2'
        mock_session.commit.assert_called_once()