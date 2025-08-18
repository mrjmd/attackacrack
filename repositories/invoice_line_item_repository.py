"""
InvoiceLineItemRepository - Data access layer for InvoiceLineItem entities
Isolates all database queries related to invoice line items
"""

from typing import List, Optional, Dict, Any
from decimal import Decimal
from sqlalchemy import or_, and_, func, desc
from repositories.base_repository import BaseRepository
from crm_database import InvoiceLineItem, Product
import logging

logger = logging.getLogger(__name__)


class InvoiceLineItemRepository(BaseRepository[InvoiceLineItem]):
    """Repository for InvoiceLineItem data access"""
    
    def search(self, query: str, fields: Optional[List[str]] = None) -> List[InvoiceLineItem]:
        """
        Search invoice line items by text query across multiple fields.
        
        Args:
            query: Search query string
            fields: Specific fields to search (default: description)
            
        Returns:
            List of matching invoice line items
        """
        if not query:
            return []
        
        search_fields = fields or ['description']
        
        conditions = []
        for field in search_fields:
            if hasattr(InvoiceLineItem, field):
                conditions.append(getattr(InvoiceLineItem, field).ilike(f'%{query}%'))
        
        if not conditions:
            return []
        
        return self.session.query(InvoiceLineItem).filter(or_(*conditions)).all()
    
    def find_by_invoice_id(self, invoice_id: int) -> List[InvoiceLineItem]:
        """
        Find all line items for a specific invoice.
        
        Args:
            invoice_id: ID of the invoice
            
        Returns:
            List of line items for the invoice
        """
        return self.session.query(InvoiceLineItem).filter_by(invoice_id=invoice_id).all()
    
    def find_by_product_id(self, product_id: Optional[int]) -> List[InvoiceLineItem]:
        """
        Find all line items for a specific product.
        
        Args:
            product_id: ID of the product (None for service items)
            
        Returns:
            List of line items using the product
        """
        return self.session.query(InvoiceLineItem).filter_by(product_id=product_id).all()
    
    def find_by_quickbooks_line_id(self, quickbooks_line_id: str) -> Optional[InvoiceLineItem]:
        """
        Find line item by QuickBooks line ID.
        
        Args:
            quickbooks_line_id: QuickBooks line ID
            
        Returns:
            InvoiceLineItem or None
        """
        return self.session.query(InvoiceLineItem).filter_by(
            quickbooks_line_id=quickbooks_line_id
        ).first()
    
    def find_items_needing_sync(self) -> List[InvoiceLineItem]:
        """
        Find line items that need QuickBooks sync (no QB line ID).
        
        Returns:
            List of line items without QuickBooks sync
        """
        return self.session.query(InvoiceLineItem).filter(
            or_(
                InvoiceLineItem.quickbooks_line_id.is_(None),
                InvoiceLineItem.quickbooks_line_id == ''
            )
        ).all()
    
    def find_synced_items(self) -> List[InvoiceLineItem]:
        """
        Find line items that are synced with QuickBooks.
        
        Returns:
            List of line items with QuickBooks sync
        """
        return self.session.query(InvoiceLineItem).filter(
            and_(
                InvoiceLineItem.quickbooks_line_id.isnot(None),
                InvoiceLineItem.quickbooks_line_id != ''
            )
        ).all()
    
    def calculate_invoice_subtotal(self, invoice_id: int) -> Decimal:
        """
        Calculate subtotal for an invoice from its line items.
        
        Args:
            invoice_id: ID of the invoice
            
        Returns:
            Sum of all line item totals for the invoice
        """
        line_items = self.find_by_invoice_id(invoice_id)
        total = Decimal('0.00')
        
        for item in line_items:
            if item.line_total:
                total += item.line_total
        
        return total
    
    def get_product_usage_stats(self, product_id: int) -> Dict[str, Any]:
        """
        Get usage statistics for a specific product.
        
        Args:
            product_id: ID of the product
            
        Returns:
            Dictionary with usage statistics
        """
        line_items = self.session.query(InvoiceLineItem).filter(
            InvoiceLineItem.product_id == product_id
        ).all()
        
        total_quantity = Decimal('0')
        total_revenue = Decimal('0.00')
        usage_count = len(line_items)
        
        for item in line_items:
            if item.quantity:
                total_quantity += item.quantity
            if item.line_total:
                total_revenue += item.line_total
        
        return {
            'total_quantity': total_quantity,
            'total_revenue': total_revenue,
            'usage_count': usage_count
        }
    
    def delete_by_invoice_id(self, invoice_id: int) -> int:
        """
        Delete all line items for an invoice.
        
        Args:
            invoice_id: ID of the invoice
            
        Returns:
            Number of line items deleted
        """
        deleted_count = self.session.query(InvoiceLineItem).filter_by(
            invoice_id=invoice_id
        ).delete()
        self.session.flush()
        return deleted_count
    
    def bulk_create_line_items(self, line_items_data: List[Dict[str, Any]]) -> List[InvoiceLineItem]:
        """
        Bulk create line items.
        
        Args:
            line_items_data: List of line item data dictionaries
            
        Returns:
            List of created line items
        """
        if not line_items_data:
            return []
        
        line_items = [InvoiceLineItem(**data) for data in line_items_data]
        self.session.add_all(line_items)
        self.session.flush()
        return line_items
    
    def update_quickbooks_line_id(self, line_item_id: int, quickbooks_line_id: str) -> Optional[InvoiceLineItem]:
        """
        Update QuickBooks line ID for a line item.
        
        Args:
            line_item_id: ID of the line item
            quickbooks_line_id: QuickBooks line ID
            
        Returns:
            Updated line item or None if not found
        """
        line_item = self.session.query(InvoiceLineItem).filter_by(id=line_item_id).first()
        if line_item:
            line_item.quickbooks_line_id = quickbooks_line_id
            self.session.flush()
        return line_item
    
    def get_revenue_by_product(self) -> List[Dict[str, Any]]:
        """
        Get revenue breakdown by product.
        
        Returns:
            List of dictionaries with product revenue data
        """
        # Query with LEFT JOIN to Product to get product names
        results = self.session.query(
            InvoiceLineItem.product_id,
            func.coalesce(Product.name, 'Service Items').label('product_name'),
            func.sum(InvoiceLineItem.line_total).label('total_revenue')
        ).outerjoin(Product).group_by(
            InvoiceLineItem.product_id,
            Product.name
        ).all()
        
        return [
            {
                'product_id': result[0],  # product_id
                'product_name': result[1],  # product_name
                'total_revenue': result[2] or Decimal('0.00')  # total_revenue
            }
            for result in results
        ]
    
    def get_top_selling_products(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get top selling products by quantity.
        
        Args:
            limit: Maximum number of products to return
            
        Returns:
            List of dictionaries with top selling product data
        """
        results = self.session.query(
            InvoiceLineItem.product_id,
            Product.name.label('product_name'),
            func.sum(InvoiceLineItem.quantity).label('total_quantity')
        ).join(Product).group_by(
            InvoiceLineItem.product_id,
            Product.name
        ).order_by(
            desc(func.sum(InvoiceLineItem.quantity))
        ).limit(limit).all()
        
        return [
            {
                'product_id': result[0],  # product_id
                'product_name': result[1],  # product_name
                'total_quantity': result[2] or Decimal('0')  # total_quantity
            }
            for result in results
        ]
    
    def validate_line_totals(self, invoice_id: int) -> List[Dict[str, Any]]:
        """
        Validate that line totals match quantity × unit price.
        
        Args:
            invoice_id: ID of the invoice to validate
            
        Returns:
            List of validation errors (empty if all correct)
        """
        line_items = self.find_by_invoice_id(invoice_id)
        validation_errors = []
        
        for item in line_items:
            if item.quantity and item.unit_price:
                expected_total = item.quantity * item.unit_price
                if item.line_total != expected_total:
                    validation_errors.append({
                        'line_item_id': item.id,
                        'expected_total': expected_total,
                        'actual_total': item.line_total,
                        'description': item.description
                    })
        
        return validation_errors
