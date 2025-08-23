"""
QuoteLineItemRepository - Data access layer for QuoteLineItem model
"""

from typing import List, Optional, Dict, Any
from repositories.base_repository import BaseRepository
from crm_database import QuoteLineItem


class QuoteLineItemRepository(BaseRepository):
    """Repository for QuoteLineItem data access"""
    
    def __init__(self, session):
        """Initialize repository with database session"""
        super().__init__(session, QuoteLineItem)
    
    def find_by_quote_id(self, quote_id: int) -> List:
        """
        Find all line items for a quote.
        
        Args:
            quote_id: ID of the quote
            
        Returns:
            List of QuoteLineItem objects
        """
        return self.session.query(self.model_class)\
            .filter_by(quote_id=quote_id)\
            .all()
    
    def find_by_product_id(self, product_id: int) -> List:
        """
        Find all line items for a product.
        
        Args:
            product_id: ID of the product
            
        Returns:
            List of QuoteLineItem objects
        """
        return self.session.query(self.model_class)\
            .filter_by(product_id=product_id)\
            .all()
    
    def delete_by_quote_id(self, quote_id: int) -> int:
        """
        Delete all line items for a quote.
        
        Args:
            quote_id: ID of the quote
            
        Returns:
            Number of items deleted
        """
        line_items = self.find_by_quote_id(quote_id)
        count = len(line_items)
        
        for item in line_items:
            self.delete(item)  # Use the base repository delete method
        
        return count
    
    def calculate_line_total(self, line_item_data: Dict[str, Any]) -> float:
        """
        Calculate the total for a line item.
        
        Args:
            line_item_data: Dictionary with quantity and unit_price
            
        Returns:
            Calculated line total
        """
        quantity = float(line_item_data.get('quantity', 0))
        unit_price = float(line_item_data.get('unit_price', 0))
        return quantity * unit_price
    
    def bulk_create_line_items(self, quote_id: int, line_items_data: List[Dict[str, Any]]) -> List:
        """
        Create multiple line items for a quote.
        
        Args:
            quote_id: ID of the quote
            line_items_data: List of line item data dictionaries
            
        Returns:
            List of created QuoteLineItem objects
        """
        created_items = []
        
        for item_data in line_items_data:
            line_item = QuoteLineItem(
                quote_id=quote_id,
                product_id=item_data.get('product_id'),
                description=item_data.get('description', ''),
                quantity=float(item_data.get('quantity', 0)),
                unit_price=float(item_data.get('unit_price', 0) if 'unit_price' in item_data else item_data.get('price', 0)),
                line_total=self.calculate_line_total(item_data)
            )
            created_items.append(line_item)
        
        if created_items:
            self.session.add_all(created_items)
            self.session.commit()
        
        return created_items
    
    def bulk_update_line_items(self, line_items_data: List[Dict[str, Any]]) -> List:
        """
        Update multiple line items.
        
        Args:
            line_items_data: List of line item data with IDs
            
        Returns:
            List of updated QuoteLineItem objects
        """
        updated_items = []
        
        for item_data in line_items_data:
            item_id = item_data.get('id')
            if item_id:
                line_item = self.session.get(QuoteLineItem, item_id)
                if line_item:
                    line_item.product_id = item_data.get('product_id', line_item.product_id)
                    line_item.description = item_data.get('description', line_item.description)
                    line_item.quantity = float(item_data.get('quantity', line_item.quantity))
                    line_item.unit_price = float(item_data.get('unit_price', item_data.get('price', line_item.unit_price)))
                    line_item.line_total = self.calculate_line_total({
                        'quantity': line_item.quantity,
                        'unit_price': line_item.unit_price
                    })
                    updated_items.append(line_item)
        
        if updated_items:
            self.session.commit()
        
        return updated_items
    
    def search(self, query: str) -> List:
        """
        Search line items by description.
        
        Args:
            query: Search query string
            
        Returns:
            List of matching QuoteLineItem objects
        """
        if not query:
            return []
        
        return self.session.query(self.model_class)\
            .filter(self.model_class.description.ilike(f'%{query}%'))\
            .limit(100)\
            .all()