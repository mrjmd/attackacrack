from typing import Optional, List, Dict, Any
# Model imports removed - using repositories only
from repositories.quote_repository import QuoteRepository
from repositories.quote_line_item_repository import QuoteLineItemRepository
from services.common.result import Result
from logging_config import get_logger

logger = get_logger(__name__)

class QuoteService:
    def __init__(self, quote_repository: QuoteRepository, line_item_repository: QuoteLineItemRepository):
        """Initialize QuoteService with repository dependencies.
        
        Args:
            quote_repository: Repository for Quote data access
            line_item_repository: Repository for QuoteLineItem data access
        """
        self.quote_repository = quote_repository
        self.line_item_repository = line_item_repository

    def get_all_quotes(self) -> List[Dict[str, Any]]:
        """Get all quotes ordered by ID descending.
        
        Returns:
            List of Quote objects
        """
        return self.quote_repository.find_all_ordered_by_id_desc()

    def get_quote_by_id(self, quote_id: int) -> Optional[Dict[str, Any]]:
        """Get a quote by ID.
        
        Args:
            quote_id: ID of the quote
            
        Returns:
            Quote object or None if not found
        """
        return self.quote_repository.get_by_id(quote_id)

    def _calculate_quote_total(self, line_items_data: List[Dict[str, Any]]) -> float:
        """Calculate total amount from line items.
        
        Args:
            line_items_data: List of line item data
            
        Returns:
            Total amount
        """
        total = 0
        for item_data in line_items_data:
            total += self.line_item_repository.calculate_line_total(item_data)
        return total

    def create_quote(self, data: Dict[str, Any]) -> Result[Dict[str, Any]]:
        """Create a new quote with line items.
        
        Args:
            data: Quote data including line items
            
        Returns:
            Result containing the created Quote or error
        """
        try:
            # Calculate total from line items
            line_items_data = data.get('line_items', [])
            total_amount = self._calculate_quote_total(line_items_data)
            
            # Create quote
            new_quote = self.quote_repository.create(
                job_id=data['job_id'],
                status=data.get('status', 'Draft'),
                subtotal=total_amount,
                tax_amount=0,
                total_amount=total_amount
            )
            
            # Create line items
            if line_items_data:
                self.line_item_repository.bulk_create_line_items(new_quote.id, line_items_data)
            
            return Result.success(new_quote)
        except Exception as e:
            logger.error("Error creating quote", error=str(e))
            return Result.failure(str(e))

    def update_quote(self, quote_id: int, data: Dict[str, Any]) -> Result[Dict[str, Any]]:
        """Update an existing quote and its line items.
        
        Args:
            quote_id: ID of the quote to update
            data: Updated quote data including line items
            
        Returns:
            Result containing the updated Quote or error
        """
        try:
            quote = self.quote_repository.get_by_id(quote_id)
            if not quote:
                return Result.failure(f"Quote {quote_id} not found")

            # Handle line items
            line_items_data = data.get('line_items', [])
            incoming_item_ids = {str(item['id']) for item in line_items_data if item.get('id')}
            existing_items = self.line_item_repository.find_by_quote_id(quote_id)
            
            # Delete removed line items
            for existing_item in existing_items:
                if str(existing_item.id) not in incoming_item_ids:
                    self.line_item_repository.delete_by_id(existing_item.id)
            
            # Update existing and create new line items
            items_to_update = [item for item in line_items_data if item.get('id')]
            items_to_create = [item for item in line_items_data if not item.get('id')]
            
            if items_to_update:
                self.line_item_repository.bulk_update_line_items(items_to_update)
            
            if items_to_create:
                self.line_item_repository.bulk_create_line_items(quote_id, items_to_create)
            
            # Calculate new total
            total_amount = self._calculate_quote_total(line_items_data)
            
            # Update quote
            updated_quote = self.quote_repository.update_by_id(
                quote_id,
                job_id=data.get('job_id', quote.job_id),
                status=data.get('status', quote.status),
                subtotal=total_amount,
                total_amount=total_amount
            )
            
            return Result.success(updated_quote)
        except Exception as e:
            logger.error("Error updating quote", error=str(e), quote_id=quote_id)
            return Result.failure(str(e))

    def delete_quote(self, quote_id: int) -> Result[Dict[str, Any]]:
        """Delete a quote and its line items.
        
        Args:
            quote_id: ID of the quote to delete
            
        Returns:
            Result containing the deleted Quote or error
        """
        try:
            quote = self.quote_repository.get_by_id(quote_id)
            if not quote:
                return Result.failure(f"Quote {quote_id} not found")
            
            # Delete line items first
            self.line_item_repository.delete_by_quote_id(quote_id)
            
            # Delete the quote
            self.quote_repository.delete(quote)
            
            return Result.success(quote)
        except Exception as e:
            logger.error("Error deleting quote", error=str(e), quote_id=quote_id)
            return Result.failure(str(e))
