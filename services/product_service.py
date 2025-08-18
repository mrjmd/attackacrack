"""
ProductService - Business logic for product/service management
Minimal implementation to replace ProductService.query.all() violations.
"""

from typing import List
from crm_database import Product, db
import logging

logger = logging.getLogger(__name__)


class ProductService:
    """Service for product business logic"""
    
    def __init__(self):
        """Initialize service"""
        pass
    
    def get_all(self) -> List[Product]:
        """
        Get all products/services.
        
        Returns:
            List of all Product objects
        """
        try:
            return Product.query.all()
        except Exception as e:
            logger.error(f"Error retrieving all products: {e}")
            return []