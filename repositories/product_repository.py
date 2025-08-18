"""
ProductRepository - Data access layer for Product entities
Isolates all database queries related to products
"""

from typing import List, Optional, Dict, Any
from decimal import Decimal
from sqlalchemy import or_, and_, func
from repositories.base_repository import BaseRepository
from crm_database import Product
import logging

logger = logging.getLogger(__name__)


class ProductRepository(BaseRepository[Product]):
    """Repository for Product data access"""
    
    def search(self, query: str, fields: Optional[List[str]] = None) -> List[Product]:
        """
        Search products by text query across multiple fields.
        
        Args:
            query: Search query string
            fields: Specific fields to search (default: name, description)
            
        Returns:
            List of matching products
        """
        if not query:
            return []
        
        search_fields = fields or ['name', 'description']
        
        conditions = []
        for field in search_fields:
            if hasattr(Product, field):
                conditions.append(getattr(Product, field).ilike(f'%{query}%'))
        
        if not conditions:
            return []
        
        return self.session.query(Product).filter(or_(*conditions)).all()
    
    def find_by_quickbooks_item_id(self, quickbooks_item_id: str) -> Optional[Product]:
        """
        Find product by QuickBooks item ID.
        
        Args:
            quickbooks_item_id: QuickBooks item ID
            
        Returns:
            Product or None
        """
        return self.session.query(Product).filter_by(
            quickbooks_item_id=quickbooks_item_id
        ).first()
    
    def find_by_name(self, name: str) -> Optional[Product]:
        """
        Find product by exact name match.
        
        Args:
            name: Product name
            
        Returns:
            Product or None
        """
        return self.session.query(Product).filter_by(name=name).first()
    
    def find_by_item_type(self, item_type: str) -> List[Product]:
        """
        Find products by item type.
        
        Args:
            item_type: Type of item ('service', 'inventory', 'non_inventory')
            
        Returns:
            List of products matching the type
        """
        return self.session.query(Product).filter_by(item_type=item_type).all()
    
    def find_active_products(self) -> List[Product]:
        """
        Find all active products.
        
        Returns:
            List of active products
        """
        return self.session.query(Product).filter_by(active=True).all()
    
    def find_inactive_products(self) -> List[Product]:
        """
        Find all inactive products.
        
        Returns:
            List of inactive products
        """
        return self.session.query(Product).filter_by(active=False).all()
    
    def find_low_inventory_products(self) -> List[Product]:
        """
        Find products with low inventory (quantity <= reorder point).
        
        Returns:
            List of products that need reordering
        """
        return self.session.query(Product).filter(
            and_(
                Product.quantity_on_hand.isnot(None),
                Product.reorder_point.isnot(None),
                Product.quantity_on_hand <= Product.reorder_point
            )
        ).all()
    
    def find_products_for_reorder(self) -> List[Product]:
        """
        Find products that need reordering.
        Alias for find_low_inventory_products for clarity.
        
        Returns:
            List of products needing reorder
        """
        return self.find_low_inventory_products()
    
    def update_inventory_quantity(self, product_id: int, new_quantity: int) -> Optional[Product]:
        """
        Update inventory quantity for a product.
        
        Args:
            product_id: ID of product to update
            new_quantity: New quantity on hand
            
        Returns:
            Updated product or None if not found
        """
        product = self.session.query(Product).filter_by(id=product_id).first()
        if product:
            product.quantity_on_hand = new_quantity
            self.session.flush()
        return product
    
    def search_products(self, query: str, limit: Optional[int] = None) -> List[Product]:
        """
        Search products by name and description with optional limit.
        This is a convenience method that wraps the abstract search method.
        
        Args:
            query: Search query string
            limit: Maximum number of results to return
            
        Returns:
            List of matching products
        """
        results = self.search(query)
        
        if limit and len(results) > limit:
            return results[:limit]
            
        return results
    
    def find_products_needing_sync(self) -> List[Product]:
        """
        Find products that need QuickBooks sync (no QB item ID).
        
        Returns:
            List of products without QuickBooks sync
        """
        return self.session.query(Product).filter(
            or_(
                Product.quickbooks_item_id.is_(None),
                Product.quickbooks_item_id == ''
            )
        ).all()
    
    def find_synced_products(self) -> List[Product]:
        """
        Find products that are synced with QuickBooks.
        
        Returns:
            List of products with QuickBooks sync
        """
        return self.session.query(Product).filter(
            and_(
                Product.quickbooks_item_id.isnot(None),
                Product.quickbooks_item_id != ''
            )
        ).all()
    
    def update_quickbooks_sync_info(self, product_id: int, quickbooks_item_id: str, 
                                   sync_token: str) -> Optional[Product]:
        """
        Update QuickBooks sync information for a product.
        
        Args:
            product_id: ID of product to update
            quickbooks_item_id: QuickBooks item ID
            sync_token: QuickBooks sync token
            
        Returns:
            Updated product or None if not found
        """
        product = self.session.query(Product).filter_by(id=product_id).first()
        if product:
            product.quickbooks_item_id = quickbooks_item_id
            product.quickbooks_sync_token = sync_token
            self.session.flush()
        return product
    
    def get_product_count_by_type(self, item_type: str) -> int:
        """
        Get count of products by type.
        
        Args:
            item_type: Type of item to count
            
        Returns:
            Number of products of the specified type
        """
        return self.session.query(Product).filter_by(item_type=item_type).count()
    
    def get_total_inventory_value(self) -> Decimal:
        """
        Calculate total inventory value (quantity * unit_price for inventory items).
        
        Returns:
            Total value of inventory on hand
        """
        inventory_products = self.session.query(Product).filter_by(item_type='inventory').all()
        
        total_value = Decimal('0')
        for product in inventory_products:
            if (product.quantity_on_hand is not None and 
                product.unit_price is not None and 
                product.quantity_on_hand > 0):
                total_value += (Decimal(str(product.quantity_on_hand)) * product.unit_price)
        
        return total_value
    
    def get_products_summary(self) -> Dict[str, int]:
        """
        Get comprehensive summary of product statistics.
        
        Returns:
            Dictionary with various product counts
        """
        total_products = self.session.query(Product).count()
        active_products = self.session.query(Product).filter_by(active=True).count()
        inactive_products = self.session.query(Product).filter_by(active=False).count()
        service_products = self.session.query(Product).filter_by(item_type='service').count()
        inventory_products = self.session.query(Product).filter_by(item_type='inventory').count()
        non_inventory_products = self.session.query(Product).filter_by(item_type='non_inventory').count()
        
        return {
            'total_products': total_products,
            'active_products': active_products,
            'inactive_products': inactive_products,
            'service_products': service_products,
            'inventory_products': inventory_products,
            'non_inventory_products': non_inventory_products
        }
    
    def bulk_update_prices(self, product_updates: Dict[int, Decimal]) -> int:
        """
        Bulk update product prices.
        
        Args:
            product_updates: Dictionary of {product_id: new_price}
            
        Returns:
            Number of products updated
        """
        if not product_updates:
            return 0
            
        product_ids = list(product_updates.keys())
        products = self.session.query(Product).filter(
            Product.id.in_(product_ids)
        ).all()
        
        updated_count = 0
        for product in products:
            if product.id in product_updates:
                product.unit_price = product_updates[product.id]
                updated_count += 1
        
        self.session.flush()
        return updated_count
    
    def deactivate_product(self, product_id: int) -> Optional[Product]:
        """
        Deactivate a product.
        
        Args:
            product_id: ID of product to deactivate
            
        Returns:
            Updated product or None if not found
        """
        product = self.session.query(Product).filter_by(id=product_id).first()
        if product:
            product.active = False
            self.session.flush()
        return product
    
    def activate_product(self, product_id: int) -> Optional[Product]:
        """
        Activate a product.
        
        Args:
            product_id: ID of product to activate
            
        Returns:
            Updated product or None if not found
        """
        product = self.session.query(Product).filter_by(id=product_id).first()
        if product:
            product.active = True
            self.session.flush()
        return product
