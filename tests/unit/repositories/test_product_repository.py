"""Tests for ProductRepository"""

import pytest
from decimal import Decimal
from unittest.mock import Mock
from repositories.product_repository import ProductRepository
from crm_database import Product


class TestProductRepository:
    """Test ProductRepository functionality"""
    
    @pytest.fixture
    def mock_session(self):
        """Create mock database session"""
        return Mock()
    
    @pytest.fixture
    def repository(self, mock_session):
        """Create ProductRepository instance with mocked session"""
        return ProductRepository(mock_session, Product)
    
    @pytest.fixture
    def sample_product_data(self):
        """Sample product data for testing"""
        return {
            'name': 'Premium Service Package',
            'description': 'Comprehensive service offering',
            'quickbooks_item_id': 'QB_ITEM_123',
            'quickbooks_sync_token': 'ST_456',
            'item_type': 'service',
            'unit_price': Decimal('299.99'),
            'cost': Decimal('150.00'),
            'quantity_on_hand': None,  # Services don't have inventory
            'reorder_point': None,
            'taxable': True,
            'active': True,
            'income_account': 'Service Revenue'
        }
    
    @pytest.fixture
    def sample_inventory_data(self):
        """Sample inventory product data for testing"""
        return {
            'name': 'Hardware Component X',
            'description': 'Essential hardware component',
            'quickbooks_item_id': 'QB_INV_789',
            'quickbooks_sync_token': 'ST_101',
            'item_type': 'inventory',
            'unit_price': Decimal('45.99'),
            'cost': Decimal('25.00'),
            'quantity_on_hand': 150,
            'reorder_point': 25,
            'taxable': True,
            'active': True,
            'income_account': 'Product Sales'
        }
    
    # Core CRUD operations
    
    def test_create_service_product(self, repository, sample_product_data, mock_session):
        """Test creating a service product"""
        # Arrange
        mock_session.add.return_value = None
        mock_session.flush.return_value = None
        
        # Act
        product = repository.create(**sample_product_data)
        
        # Assert
        assert isinstance(product, Product)
        assert product.name == 'Premium Service Package'
        assert product.item_type == 'service'
        assert product.unit_price == Decimal('299.99')
        assert product.quantity_on_hand is None  # Services don't have inventory
        mock_session.add.assert_called_once()
    
    def test_create_inventory_product(self, repository, sample_inventory_data, mock_session):
        """Test creating an inventory product"""
        # Arrange
        mock_session.add.return_value = None
        mock_session.flush.return_value = None
        
        # Act
        product = repository.create(**sample_inventory_data)
        
        # Assert
        assert isinstance(product, Product)
        assert product.name == 'Hardware Component X'
        assert product.item_type == 'inventory'
        assert product.quantity_on_hand == 150
        assert product.reorder_point == 25
        mock_session.add.assert_called_once()
    
    def test_find_by_quickbooks_item_id_exists(self, repository, mock_session):
        """Test finding product by QuickBooks item ID when it exists"""
        # Arrange
        expected_product = Mock(spec=Product)
        expected_product.quickbooks_item_id = 'QB_ITEM_123'
        mock_query = Mock()
        mock_query.filter_by.return_value.first.return_value = expected_product
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.find_by_quickbooks_item_id('QB_ITEM_123')
        
        # Assert
        assert result == expected_product
        mock_session.query.assert_called_once_with(Product)
        mock_query.filter_by.assert_called_once_with(quickbooks_item_id='QB_ITEM_123')
    
    def test_find_by_quickbooks_item_id_not_exists(self, repository, mock_session):
        """Test finding product by QuickBooks item ID when it doesn't exist"""
        # Arrange
        mock_query = Mock()
        mock_query.filter_by.return_value.first.return_value = None
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.find_by_quickbooks_item_id('NONEXISTENT_ID')
        
        # Assert
        assert result is None
        mock_session.query.assert_called_once_with(Product)
        mock_query.filter_by.assert_called_once_with(quickbooks_item_id='NONEXISTENT_ID')
    
    def test_find_by_name_exists(self, repository, mock_session):
        """Test finding product by name when it exists"""
        # Arrange
        expected_product = Mock(spec=Product)
        expected_product.name = 'Premium Service Package'
        mock_query = Mock()
        mock_query.filter_by.return_value.first.return_value = expected_product
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.find_by_name('Premium Service Package')
        
        # Assert
        assert result == expected_product
        mock_session.query.assert_called_once_with(Product)
        mock_query.filter_by.assert_called_once_with(name='Premium Service Package')
    
    def test_find_by_name_not_exists(self, repository, mock_session):
        """Test finding product by name when it doesn't exist"""
        # Arrange
        mock_query = Mock()
        mock_query.filter_by.return_value.first.return_value = None
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.find_by_name('Nonexistent Product')
        
        # Assert
        assert result is None
        mock_session.query.assert_called_once_with(Product)
        mock_query.filter_by.assert_called_once_with(name='Nonexistent Product')
    
    # Item type filtering
    
    def test_find_by_item_type_service(self, repository, mock_session):
        """Test finding products by item type 'service'"""
        # Arrange
        expected_products = [Mock(spec=Product), Mock(spec=Product)]
        mock_query = Mock()
        mock_query.filter_by.return_value.all.return_value = expected_products
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.find_by_item_type('service')
        
        # Assert
        assert result == expected_products
        mock_session.query.assert_called_once_with(Product)
        mock_query.filter_by.assert_called_once_with(item_type='service')
    
    def test_find_by_item_type_inventory(self, repository, mock_session):
        """Test finding products by item type 'inventory'"""
        # Arrange
        expected_products = [Mock(spec=Product)]
        mock_query = Mock()
        mock_query.filter_by.return_value.all.return_value = expected_products
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.find_by_item_type('inventory')
        
        # Assert
        assert result == expected_products
        mock_session.query.assert_called_once_with(Product)
        mock_query.filter_by.assert_called_once_with(item_type='inventory')
    
    def test_find_by_item_type_empty_result(self, repository, mock_session):
        """Test finding products by item type with no results"""
        # Arrange
        mock_query = Mock()
        mock_query.filter_by.return_value.all.return_value = []
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.find_by_item_type('non_inventory')
        
        # Assert
        assert result == []
        mock_session.query.assert_called_once_with(Product)
        mock_query.filter_by.assert_called_once_with(item_type='non_inventory')
    
    # Status filtering
    
    def test_find_active_products(self, repository, mock_session):
        """Test finding active products"""
        # Arrange
        expected_products = [Mock(spec=Product), Mock(spec=Product), Mock(spec=Product)]
        mock_query = Mock()
        mock_query.filter_by.return_value.all.return_value = expected_products
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.find_active_products()
        
        # Assert
        assert result == expected_products
        mock_session.query.assert_called_once_with(Product)
        mock_query.filter_by.assert_called_once_with(active=True)
    
    def test_find_inactive_products(self, repository, mock_session):
        """Test finding inactive products"""
        # Arrange
        expected_products = [Mock(spec=Product)]
        mock_query = Mock()
        mock_query.filter_by.return_value.all.return_value = expected_products
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.find_inactive_products()
        
        # Assert
        assert result == expected_products
        mock_session.query.assert_called_once_with(Product)
        mock_query.filter_by.assert_called_once_with(active=False)
    
    # Inventory management
    
    def test_find_low_inventory_products(self, repository, mock_session):
        """Test finding products with low inventory"""
        # Arrange
        expected_products = [Mock(spec=Product)]
        mock_query = Mock()
        mock_filter = Mock()
        mock_query.filter.return_value = mock_filter
        mock_filter.all.return_value = expected_products
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.find_low_inventory_products()
        
        # Assert
        assert result == expected_products
        mock_session.query.assert_called_once_with(Product)
        # Should filter where quantity_on_hand <= reorder_point and both are not None
        mock_query.filter.assert_called_once()
    
    def test_find_products_for_reorder(self, repository, mock_session):
        """Test finding products that need reordering"""
        # Arrange
        expected_products = [Mock(spec=Product), Mock(spec=Product)]
        mock_query = Mock()
        mock_filter = Mock()
        mock_query.filter.return_value = mock_filter
        mock_filter.all.return_value = expected_products
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.find_products_for_reorder()
        
        # Assert
        assert result == expected_products
        mock_session.query.assert_called_once_with(Product)
        mock_query.filter.assert_called_once()
    
    def test_update_inventory_quantity(self, repository, mock_session):
        """Test updating inventory quantity for a product"""
        # Arrange
        mock_product = Mock(spec=Product)
        mock_product.quantity_on_hand = 100
        mock_query = Mock()
        mock_query.filter_by.return_value.first.return_value = mock_product
        mock_session.query.return_value = mock_query
        mock_session.flush.return_value = None
        
        # Act
        result = repository.update_inventory_quantity(1, 150)
        
        # Assert
        assert result == mock_product
        assert mock_product.quantity_on_hand == 150
        mock_session.query.assert_called_once_with(Product)
        mock_query.filter_by.assert_called_once_with(id=1)
        mock_session.flush.assert_called_once()
    
    def test_update_inventory_quantity_product_not_found(self, repository, mock_session):
        """Test updating inventory quantity when product doesn't exist"""
        # Arrange
        mock_query = Mock()
        mock_query.filter_by.return_value.first.return_value = None
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.update_inventory_quantity(999, 150)
        
        # Assert
        assert result is None
        mock_session.query.assert_called_once_with(Product)
        mock_query.filter_by.assert_called_once_with(id=999)
    
    # Search functionality
    
    def test_search_products_by_name(self, repository, mock_session):
        """Test searching products by name"""
        # Arrange
        expected_products = [Mock(spec=Product), Mock(spec=Product), Mock(spec=Product)]
        mock_query = Mock()
        mock_filter = Mock()
        mock_query.filter.return_value = mock_filter
        mock_filter.all.return_value = expected_products
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.search_products('Service', limit=2)
        
        # Assert
        assert len(result) == 2  # Should be limited
        mock_session.query.assert_called_once_with(Product)
        mock_query.filter.assert_called_once()
    
    def test_search_products_no_limit(self, repository, mock_session):
        """Test searching products without limit"""
        # Arrange
        expected_products = [Mock(spec=Product)]
        mock_query = Mock()
        mock_filter = Mock()
        mock_query.filter.return_value = mock_filter
        mock_filter.all.return_value = expected_products
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.search_products('Hardware')
        
        # Assert
        assert result == expected_products
        mock_session.query.assert_called_once_with(Product)
        mock_query.filter.assert_called_once()
        # Ensure limit was not called
        assert not hasattr(mock_filter, 'limit') or not mock_filter.limit.called
    
    def test_search_products_empty_query(self, repository):
        """Test searching products with empty query returns empty list"""
        # Act
        result = repository.search_products('')
        
        # Assert
        assert result == []
    
    def test_search_products_none_query(self, repository):
        """Test searching products with None query returns empty list"""
        # Act
        result = repository.search_products(None)
        
        # Assert
        assert result == []
    
    # QuickBooks sync specific methods
    
    def test_find_products_needing_sync(self, repository, mock_session):
        """Test finding products that need QuickBooks sync"""
        # Arrange
        expected_products = [Mock(spec=Product)]
        mock_query = Mock()
        mock_filter = Mock()
        mock_query.filter.return_value = mock_filter
        mock_filter.all.return_value = expected_products
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.find_products_needing_sync()
        
        # Assert
        assert result == expected_products
        mock_session.query.assert_called_once_with(Product)
        # Should filter for products without QuickBooks ID
        mock_query.filter.assert_called_once()
    
    def test_find_synced_products(self, repository, mock_session):
        """Test finding products that are synced with QuickBooks"""
        # Arrange
        expected_products = [Mock(spec=Product), Mock(spec=Product)]
        mock_query = Mock()
        mock_filter = Mock()
        mock_query.filter.return_value = mock_filter
        mock_filter.all.return_value = expected_products
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.find_synced_products()
        
        # Assert
        assert result == expected_products
        mock_session.query.assert_called_once_with(Product)
        # Should filter for products with QuickBooks ID
        mock_query.filter.assert_called_once()
    
    def test_update_quickbooks_sync_info(self, repository, mock_session):
        """Test updating QuickBooks sync information"""
        # Arrange
        mock_product = Mock(spec=Product)
        mock_product.quickbooks_item_id = None
        mock_product.quickbooks_sync_token = None
        mock_query = Mock()
        mock_query.filter_by.return_value.first.return_value = mock_product
        mock_session.query.return_value = mock_query
        mock_session.flush.return_value = None
        
        # Act
        result = repository.update_quickbooks_sync_info(1, 'QB_ITEM_456', 'ST_789')
        
        # Assert
        assert result == mock_product
        assert mock_product.quickbooks_item_id == 'QB_ITEM_456'
        assert mock_product.quickbooks_sync_token == 'ST_789'
        mock_session.query.assert_called_once_with(Product)
        mock_query.filter_by.assert_called_once_with(id=1)
        mock_session.flush.assert_called_once()
    
    def test_update_quickbooks_sync_info_product_not_found(self, repository, mock_session):
        """Test updating QuickBooks sync info when product doesn't exist"""
        # Arrange
        mock_query = Mock()
        mock_query.filter_by.return_value.first.return_value = None
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.update_quickbooks_sync_info(999, 'QB_ITEM_456', 'ST_789')
        
        # Assert
        assert result is None
        mock_session.query.assert_called_once_with(Product)
        mock_query.filter_by.assert_called_once_with(id=999)
    
    # Statistical methods
    
    def test_get_product_count_by_type(self, repository, mock_session):
        """Test getting product count by type"""
        # Arrange
        mock_session.query.return_value.filter_by.return_value.count.return_value = 5
        
        # Act
        result = repository.get_product_count_by_type('service')
        
        # Assert
        assert result == 5
        mock_session.query.assert_called_once_with(Product)
        mock_session.query.return_value.filter_by.assert_called_once_with(item_type='service')
    
    def test_get_total_inventory_value(self, repository, mock_session):
        """Test calculating total inventory value"""
        # Arrange
        mock_products = [
            Mock(spec=Product, quantity_on_hand=10, unit_price=Decimal('15.99')),
            Mock(spec=Product, quantity_on_hand=5, unit_price=Decimal('25.50')),
            Mock(spec=Product, quantity_on_hand=0, unit_price=Decimal('10.00')),  # Zero inventory
            Mock(spec=Product, quantity_on_hand=None, unit_price=Decimal('20.00'))  # Service item
        ]
        mock_query = Mock()
        mock_query.filter_by.return_value.all.return_value = mock_products
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.get_total_inventory_value()
        
        # Assert
        expected_value = (10 * Decimal('15.99')) + (5 * Decimal('25.50'))  # Only inventory items with qty > 0
        assert result == expected_value
        mock_session.query.assert_called_once_with(Product)
        mock_query.filter_by.assert_called_once_with(item_type='inventory')
    
    def test_get_products_summary(self, repository, mock_session):
        """Test getting comprehensive products summary"""
        # Arrange - Mock the query chain step by step
        mock_base_query = Mock()
        mock_session.query.return_value = mock_base_query
        
        # Mock total count (no filter_by)
        mock_base_query.count.return_value = 17
        
        # Mock filter_by queries
        mock_filtered_query = Mock()
        mock_base_query.filter_by.return_value = mock_filtered_query
        
        def mock_count_side_effect():
            # This gets called for each filter_by().count() call
            # Return different values in sequence
            call_count = getattr(mock_count_side_effect, 'call_count', 0)
            mock_count_side_effect.call_count = call_count + 1
            
            if call_count == 0: return 15  # active_products
            elif call_count == 1: return 2   # inactive_products
            elif call_count == 2: return 10  # service_products
            elif call_count == 3: return 5   # inventory_products
            elif call_count == 4: return 2   # non_inventory_products
            else: return 0
        
        mock_filtered_query.count.side_effect = mock_count_side_effect
        
        # Act
        result = repository.get_products_summary()
        
        # Assert
        assert result['total_products'] == 17
        assert result['active_products'] == 15
        assert result['inactive_products'] == 2
        assert result['service_products'] == 10
        assert result['inventory_products'] == 5
        assert result['non_inventory_products'] == 2
    
    # Edge cases and error conditions
    
    def test_create_product_with_minimal_data(self, repository, mock_session):
        """Test creating product with minimal required data"""
        # Arrange
        minimal_data = {
            'name': 'Basic Service',
            'item_type': 'service'
        }
        mock_session.add.return_value = None
        mock_session.flush.return_value = None
        
        # Act
        product = repository.create(**minimal_data)
        
        # Assert
        assert isinstance(product, Product)
        assert product.name == 'Basic Service'
        assert product.item_type == 'service'
        mock_session.add.assert_called_once()
    
    def test_bulk_update_prices(self, repository, mock_session):
        """Test bulk updating product prices"""
        # Arrange
        product_updates = {
            1: Decimal('199.99'),
            2: Decimal('299.99'),
            3: Decimal('399.99')
        }
        
        mock_products = []
        for product_id, price in product_updates.items():
            mock_product = Mock(spec=Product)
            mock_product.id = product_id
            mock_product.unit_price = Decimal('100.00')  # old price
            mock_products.append(mock_product)
        
        mock_query = Mock()
        mock_query.filter.return_value.all.return_value = mock_products
        mock_session.query.return_value = mock_query
        mock_session.flush.return_value = None
        
        # Act
        result = repository.bulk_update_prices(product_updates)
        
        # Assert
        assert result == 3  # number of products updated
        for i, product in enumerate(mock_products):
            expected_price = list(product_updates.values())[i]
            assert product.unit_price == expected_price
        mock_session.flush.assert_called_once()
    
    def test_bulk_update_prices_empty_dict(self, repository):
        """Test bulk updating with empty product updates dict"""
        # Act
        result = repository.bulk_update_prices({})
        
        # Assert
        assert result == 0
    
    def test_deactivate_product(self, repository, mock_session):
        """Test deactivating a product"""
        # Arrange
        mock_product = Mock(spec=Product)
        mock_product.active = True
        mock_query = Mock()
        mock_query.filter_by.return_value.first.return_value = mock_product
        mock_session.query.return_value = mock_query
        mock_session.flush.return_value = None
        
        # Act
        result = repository.deactivate_product(1)
        
        # Assert
        assert result == mock_product
        assert mock_product.active is False
        mock_session.query.assert_called_once_with(Product)
        mock_query.filter_by.assert_called_once_with(id=1)
        mock_session.flush.assert_called_once()
    
    def test_activate_product(self, repository, mock_session):
        """Test activating a product"""
        # Arrange
        mock_product = Mock(spec=Product)
        mock_product.active = False
        mock_query = Mock()
        mock_query.filter_by.return_value.first.return_value = mock_product
        mock_session.query.return_value = mock_query
        mock_session.flush.return_value = None
        
        # Act
        result = repository.activate_product(1)
        
        # Assert
        assert result == mock_product
        assert mock_product.active is True
        mock_session.query.assert_called_once_with(Product)
        mock_query.filter_by.assert_called_once_with(id=1)
        mock_session.flush.assert_called_once()
