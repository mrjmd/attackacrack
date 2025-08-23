"""Tests for InvoiceLineItemRepository"""

import pytest
from decimal import Decimal
from unittest.mock import Mock
from repositories.invoice_line_item_repository import InvoiceLineItemRepository
from crm_database import InvoiceLineItem, Invoice, Product


class TestInvoiceLineItemRepository:
    """Test InvoiceLineItemRepository functionality"""
    
    @pytest.fixture
    def mock_session(self):
        """Create mock database session"""
        return Mock()
    
    @pytest.fixture
    def repository(self, mock_session):
        """Create InvoiceLineItemRepository instance with mocked session"""
        return InvoiceLineItemRepository(mock_session)
    
    @pytest.fixture
    def sample_line_item_data(self):
        """Sample line item data for testing"""
        return {
            'invoice_id': 1,
            'product_id': 2,
            'description': 'Premium service line item',
            'quantity': Decimal('2.0'),
            'unit_price': Decimal('150.00'),
            'line_total': Decimal('300.00'),
            'quickbooks_line_id': 'QB_LINE_123'
        }
    
    @pytest.fixture
    def sample_service_line_data(self):
        """Sample service line item data without product ID"""
        return {
            'invoice_id': 1,
            'product_id': None,
            'description': 'Custom labor charge',
            'quantity': Decimal('8.0'),
            'unit_price': Decimal('75.00'),
            'line_total': Decimal('600.00'),
            'quickbooks_line_id': None
        }
    
    # Core CRUD operations
    
    def test_create_line_item_with_product(self, repository, sample_line_item_data, mock_session):
        """Test creating a line item linked to a product"""
        # Arrange
        mock_session.add.return_value = None
        mock_session.flush.return_value = None
        
        # Act
        line_item = repository.create(**sample_line_item_data)
        
        # Assert
        assert isinstance(line_item, InvoiceLineItem)
        assert line_item.invoice_id == 1
        assert line_item.product_id == 2
        assert line_item.description == 'Premium service line item'
        assert line_item.quantity == Decimal('2.0')
        assert line_item.unit_price == Decimal('150.00')
        assert line_item.line_total == Decimal('300.00')
        assert line_item.quickbooks_line_id == 'QB_LINE_123'
        mock_session.add.assert_called_once()
    
    def test_create_service_line_item(self, repository, sample_service_line_data, mock_session):
        """Test creating a service line item without product link"""
        # Arrange
        mock_session.add.return_value = None
        mock_session.flush.return_value = None
        
        # Act
        line_item = repository.create(**sample_service_line_data)
        
        # Assert
        assert isinstance(line_item, InvoiceLineItem)
        assert line_item.invoice_id == 1
        assert line_item.product_id is None
        assert line_item.description == 'Custom labor charge'
        assert line_item.quantity == Decimal('8.0')
        assert line_item.unit_price == Decimal('75.00')
        assert line_item.line_total == Decimal('600.00')
        assert line_item.quickbooks_line_id is None
        mock_session.add.assert_called_once()
    
    # Invoice-specific queries
    
    def test_find_by_invoice_id(self, repository, mock_session):
        """Test finding line items by invoice ID"""
        # Arrange
        expected_line_items = [Mock(spec=InvoiceLineItem), Mock(spec=InvoiceLineItem)]
        mock_query = Mock()
        mock_query.filter_by.return_value.all.return_value = expected_line_items
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.find_by_invoice_id(1)
        
        # Assert
        assert result == expected_line_items
        mock_session.query.assert_called_once_with(InvoiceLineItem)
        mock_query.filter_by.assert_called_once_with(invoice_id=1)
    
    def test_find_by_invoice_id_empty_result(self, repository, mock_session):
        """Test finding line items by invoice ID with no results"""
        # Arrange
        mock_query = Mock()
        mock_query.filter_by.return_value.all.return_value = []
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.find_by_invoice_id(999)
        
        # Assert
        assert result == []
        mock_session.query.assert_called_once_with(InvoiceLineItem)
        mock_query.filter_by.assert_called_once_with(invoice_id=999)
    
    def test_find_by_product_id(self, repository, mock_session):
        """Test finding line items by product ID"""
        # Arrange
        expected_line_items = [Mock(spec=InvoiceLineItem), Mock(spec=InvoiceLineItem)]
        mock_query = Mock()
        mock_query.filter_by.return_value.all.return_value = expected_line_items
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.find_by_product_id(2)
        
        # Assert
        assert result == expected_line_items
        mock_session.query.assert_called_once_with(InvoiceLineItem)
        mock_query.filter_by.assert_called_once_with(product_id=2)
    
    def test_find_by_product_id_none(self, repository, mock_session):
        """Test finding line items with no product (service items)"""
        # Arrange
        expected_line_items = [Mock(spec=InvoiceLineItem)]
        mock_query = Mock()
        mock_query.filter_by.return_value.all.return_value = expected_line_items
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.find_by_product_id(None)
        
        # Assert
        assert result == expected_line_items
        mock_session.query.assert_called_once_with(InvoiceLineItem)
        mock_query.filter_by.assert_called_once_with(product_id=None)
    
    # QuickBooks-specific methods
    
    def test_find_by_quickbooks_line_id(self, repository, mock_session):
        """Test finding line item by QuickBooks line ID"""
        # Arrange
        expected_line_item = Mock(spec=InvoiceLineItem)
        expected_line_item.quickbooks_line_id = 'QB_LINE_123'
        mock_query = Mock()
        mock_query.filter_by.return_value.first.return_value = expected_line_item
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.find_by_quickbooks_line_id('QB_LINE_123')
        
        # Assert
        assert result == expected_line_item
        mock_session.query.assert_called_once_with(InvoiceLineItem)
        mock_query.filter_by.assert_called_once_with(quickbooks_line_id='QB_LINE_123')
    
    def test_find_by_quickbooks_line_id_not_found(self, repository, mock_session):
        """Test finding line item by QuickBooks line ID when not found"""
        # Arrange
        mock_query = Mock()
        mock_query.filter_by.return_value.first.return_value = None
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.find_by_quickbooks_line_id('NONEXISTENT')
        
        # Assert
        assert result is None
        mock_session.query.assert_called_once_with(InvoiceLineItem)
        mock_query.filter_by.assert_called_once_with(quickbooks_line_id='NONEXISTENT')
    
    def test_find_items_needing_sync(self, repository, mock_session):
        """Test finding line items that need QuickBooks sync"""
        # Arrange
        expected_items = [Mock(spec=InvoiceLineItem), Mock(spec=InvoiceLineItem)]
        mock_query = Mock()
        mock_filter = Mock()
        mock_query.filter.return_value = mock_filter
        mock_filter.all.return_value = expected_items
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.find_items_needing_sync()
        
        # Assert
        assert result == expected_items
        mock_session.query.assert_called_once_with(InvoiceLineItem)
        # Should filter for items without QB line ID
        mock_query.filter.assert_called_once()
    
    def test_find_synced_items(self, repository, mock_session):
        """Test finding line items synced with QuickBooks"""
        # Arrange
        expected_items = [Mock(spec=InvoiceLineItem)]
        mock_query = Mock()
        mock_filter = Mock()
        mock_query.filter.return_value = mock_filter
        mock_filter.all.return_value = expected_items
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.find_synced_items()
        
        # Assert
        assert result == expected_items
        mock_session.query.assert_called_once_with(InvoiceLineItem)
        # Should filter for items with QB line ID
        mock_query.filter.assert_called_once()
    
    # Calculation methods
    
    def test_calculate_invoice_subtotal(self, repository, mock_session):
        """Test calculating subtotal for an invoice"""
        # Arrange
        mock_line_items = [
            Mock(spec=InvoiceLineItem, line_total=Decimal('100.00')),
            Mock(spec=InvoiceLineItem, line_total=Decimal('200.00')),
            Mock(spec=InvoiceLineItem, line_total=Decimal('50.00'))
        ]
        mock_query = Mock()
        mock_query.filter_by.return_value.all.return_value = mock_line_items
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.calculate_invoice_subtotal(1)
        
        # Assert
        assert result == Decimal('350.00')
        mock_session.query.assert_called_once_with(InvoiceLineItem)
        mock_query.filter_by.assert_called_once_with(invoice_id=1)
    
    def test_calculate_invoice_subtotal_empty_invoice(self, repository, mock_session):
        """Test calculating subtotal for invoice with no line items"""
        # Arrange
        mock_query = Mock()
        mock_query.filter_by.return_value.all.return_value = []
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.calculate_invoice_subtotal(1)
        
        # Assert
        assert result == Decimal('0.00')
        mock_session.query.assert_called_once_with(InvoiceLineItem)
        mock_query.filter_by.assert_called_once_with(invoice_id=1)
    
    def test_get_product_usage_stats(self, repository, mock_session):
        """Test getting product usage statistics"""
        # Arrange - Only return items for product_id=1
        mock_line_items = [
            Mock(spec=InvoiceLineItem, product_id=1, quantity=Decimal('2.0'), line_total=Decimal('100.00')),
            Mock(spec=InvoiceLineItem, product_id=1, quantity=Decimal('1.0'), line_total=Decimal('50.00'))
        ]
        mock_query = Mock()
        mock_query.filter.return_value.all.return_value = mock_line_items
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.get_product_usage_stats(product_id=1)
        
        # Assert
        assert result['total_quantity'] == Decimal('3.0')
        assert result['total_revenue'] == Decimal('150.00')
        assert result['usage_count'] == 2
        mock_session.query.assert_called_once_with(InvoiceLineItem)
        mock_query.filter.assert_called_once()
    
    def test_get_product_usage_stats_no_usage(self, repository, mock_session):
        """Test getting product usage stats for unused product"""
        # Arrange
        mock_query = Mock()
        mock_query.filter.return_value.all.return_value = []
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.get_product_usage_stats(product_id=999)
        
        # Assert
        assert result['total_quantity'] == Decimal('0')
        assert result['total_revenue'] == Decimal('0.00')
        assert result['usage_count'] == 0
        mock_session.query.assert_called_once_with(InvoiceLineItem)
    
    # Bulk operations
    
    def test_delete_by_invoice_id(self, repository, mock_session):
        """Test deleting all line items for an invoice"""
        # Arrange
        mock_query = Mock()
        mock_filter = Mock()
        mock_query.filter_by.return_value = mock_filter
        mock_filter.delete.return_value = 3  # 3 items deleted
        mock_session.query.return_value = mock_query
        mock_session.flush.return_value = None
        
        # Act
        result = repository.delete_by_invoice_id(1)
        
        # Assert
        assert result == 3
        mock_session.query.assert_called_once_with(InvoiceLineItem)
        mock_query.filter_by.assert_called_once_with(invoice_id=1)
        mock_filter.delete.assert_called_once()
        mock_session.flush.assert_called_once()
    
    def test_bulk_create_line_items(self, repository, mock_session):
        """Test bulk creating line items"""
        # Arrange
        line_items_data = [
            {
                'invoice_id': 1,
                'description': 'Item 1',
                'quantity': Decimal('1.0'),
                'unit_price': Decimal('100.00'),
                'line_total': Decimal('100.00')
            },
            {
                'invoice_id': 1,
                'description': 'Item 2',
                'quantity': Decimal('2.0'),
                'unit_price': Decimal('50.00'),
                'line_total': Decimal('100.00')
            }
        ]
        mock_session.add_all.return_value = None
        mock_session.flush.return_value = None
        
        # Act
        result = repository.bulk_create_line_items(line_items_data)
        
        # Assert
        assert len(result) == 2
        for item in result:
            assert isinstance(item, InvoiceLineItem)
        mock_session.add_all.assert_called_once()
        mock_session.flush.assert_called_once()
    
    def test_bulk_create_line_items_empty_list(self, repository):
        """Test bulk creating with empty list"""
        # Act
        result = repository.bulk_create_line_items([])
        
        # Assert
        assert result == []
    
    def test_update_quickbooks_line_id(self, repository, mock_session):
        """Test updating QuickBooks line ID"""
        # Arrange
        mock_line_item = Mock(spec=InvoiceLineItem)
        mock_line_item.quickbooks_line_id = None
        mock_query = Mock()
        mock_query.filter_by.return_value.first.return_value = mock_line_item
        mock_session.query.return_value = mock_query
        mock_session.flush.return_value = None
        
        # Act
        result = repository.update_quickbooks_line_id(1, 'QB_LINE_456')
        
        # Assert
        assert result == mock_line_item
        assert mock_line_item.quickbooks_line_id == 'QB_LINE_456'
        mock_session.query.assert_called_once_with(InvoiceLineItem)
        mock_query.filter_by.assert_called_once_with(id=1)
        mock_session.flush.assert_called_once()
    
    def test_update_quickbooks_line_id_not_found(self, repository, mock_session):
        """Test updating QB line ID for non-existent item"""
        # Arrange
        mock_query = Mock()
        mock_query.filter_by.return_value.first.return_value = None
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.update_quickbooks_line_id(999, 'QB_LINE_456')
        
        # Assert
        assert result is None
        mock_session.query.assert_called_once_with(InvoiceLineItem)
        mock_query.filter_by.assert_called_once_with(id=999)
    
    # Search functionality
    
    def test_search_line_items(self, repository, mock_session):
        """Test searching line items by description"""
        # Arrange
        expected_items = [Mock(spec=InvoiceLineItem), Mock(spec=InvoiceLineItem)]
        mock_query = Mock()
        mock_filter = Mock()
        mock_query.filter.return_value = mock_filter
        mock_filter.all.return_value = expected_items
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.search('labor')
        
        # Assert
        assert result == expected_items
        mock_session.query.assert_called_once_with(InvoiceLineItem)
        mock_query.filter.assert_called_once()
    
    def test_search_empty_query(self, repository):
        """Test searching with empty query returns empty list"""
        # Act
        result = repository.search('')
        
        # Assert
        assert result == []
    
    def test_search_none_query(self, repository):
        """Test searching with None query returns empty list"""
        # Act
        result = repository.search(None)
        
        # Assert
        assert result == []
    
    # Revenue analysis methods
    
    def test_get_revenue_by_product(self, repository, mock_session):
        """Test getting revenue breakdown by product"""
        # Arrange
        mock_result = [
            (1, 'Product A', Decimal('500.00')),
            (2, 'Product B', Decimal('300.00')),
            (None, 'Service Items', Decimal('750.00'))
        ]
        
        mock_session.query.return_value.outerjoin.return_value.group_by.return_value.all.return_value = mock_result
        
        # Act
        result = repository.get_revenue_by_product()
        
        # Assert
        assert len(result) == 3
        assert result[0] == {'product_id': 1, 'product_name': 'Product A', 'total_revenue': Decimal('500.00')}
        assert result[1] == {'product_id': 2, 'product_name': 'Product B', 'total_revenue': Decimal('300.00')}
        assert result[2] == {'product_id': None, 'product_name': 'Service Items', 'total_revenue': Decimal('750.00')}
    
    def test_get_top_selling_products(self, repository, mock_session):
        """Test getting top selling products by quantity"""
        # Arrange
        mock_result = [
            (1, 'Product A', Decimal('25.0')),
            (2, 'Product B', Decimal('20.0')),
            (3, 'Product C', Decimal('15.0'))
        ]
        
        mock_session.query.return_value.join.return_value.group_by.return_value.order_by.return_value.limit.return_value.all.return_value = mock_result
        
        # Act
        result = repository.get_top_selling_products(limit=3)
        
        # Assert
        assert len(result) == 3
        assert result[0] == {'product_id': 1, 'product_name': 'Product A', 'total_quantity': Decimal('25.0')}
        assert result[1] == {'product_id': 2, 'product_name': 'Product B', 'total_quantity': Decimal('20.0')}
        assert result[2] == {'product_id': 3, 'product_name': 'Product C', 'total_quantity': Decimal('15.0')}
    
    # Edge cases and validation
    
    def test_validate_line_total_calculation(self, repository, mock_session):
        """Test validation that line total matches quantity × unit price"""
        # Arrange
        mock_line_items = [
            Mock(spec=InvoiceLineItem, 
                 quantity=Decimal('2.0'), 
                 unit_price=Decimal('50.00'), 
                 line_total=Decimal('100.00')),  # Correct
            Mock(spec=InvoiceLineItem, 
                 quantity=Decimal('3.0'), 
                 unit_price=Decimal('25.00'), 
                 line_total=Decimal('70.00'))   # Incorrect (should be 75.00)
        ]
        mock_query = Mock()
        mock_query.filter_by.return_value.all.return_value = mock_line_items
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.validate_line_totals(1)
        
        # Assert
        assert len(result) == 1  # One invalid item found
        assert result[0]['expected_total'] == Decimal('75.00')
        assert result[0]['actual_total'] == Decimal('70.00')
        mock_session.query.assert_called_once_with(InvoiceLineItem)
        mock_query.filter_by.assert_called_once_with(invoice_id=1)
    
    def test_validate_line_total_calculation_all_correct(self, repository, mock_session):
        """Test validation when all line totals are correct"""
        # Arrange
        mock_line_items = [
            Mock(spec=InvoiceLineItem, 
                 quantity=Decimal('2.0'), 
                 unit_price=Decimal('50.00'), 
                 line_total=Decimal('100.00')),
            Mock(spec=InvoiceLineItem, 
                 quantity=Decimal('1.0'), 
                 unit_price=Decimal('25.00'), 
                 line_total=Decimal('25.00'))
        ]
        mock_query = Mock()
        mock_query.filter_by.return_value.all.return_value = mock_line_items
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.validate_line_totals(1)
        
        # Assert
        assert result == []  # No validation errors
        mock_session.query.assert_called_once_with(InvoiceLineItem)
        mock_query.filter_by.assert_called_once_with(invoice_id=1)
