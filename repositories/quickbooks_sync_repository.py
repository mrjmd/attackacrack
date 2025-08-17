"""
QuickBooksSyncRepository - Data access layer for QuickBooksSync model
"""

from typing import List, Optional
from datetime import datetime
from sqlalchemy import desc, or_, and_
from repositories.base_repository import BaseRepository, PaginatedResult


class QuickBooksSyncRepository(BaseRepository):
    """Repository for QuickBooksSync data access"""
    
    def find_by_entity_type(self, entity_type: str) -> List:
        """
        Find sync records by entity type.
        
        Args:
            entity_type: Type of entity (customer, item, invoice, estimate)
            
        Returns:
            List of QuickBooksSync objects
        """
        return self.session.query(self.model_class)\
            .filter_by(entity_type=entity_type)\
            .all()
    
    def find_by_entity_id(self, entity_id: str) -> Optional:
        """
        Find sync record by QuickBooks entity ID.
        
        Args:
            entity_id: QuickBooks entity ID
            
        Returns:
            QuickBooksSync object or None if not found
        """
        return self.session.query(self.model_class)\
            .filter_by(entity_id=entity_id)\
            .first()
    
    def find_by_local_id(self, local_id: int, local_table: str) -> Optional:
        """
        Find sync record by local entity ID and table.
        
        Args:
            local_id: Local CRM entity ID
            local_table: Local table name
            
        Returns:
            QuickBooksSync object or None if not found
        """
        return self.session.query(self.model_class)\
            .filter_by(local_id=local_id, local_table=local_table)\
            .first()
    
    def find_pending_syncs(self) -> List:
        """
        Find all pending sync records.
        
        Returns:
            List of pending QuickBooksSync objects
        """
        return self.session.query(self.model_class)\
            .filter_by(sync_status="pending")\
            .all()
    
    def find_failed_syncs(self) -> List:
        """
        Find all failed sync records.
        
        Returns:
            List of failed QuickBooksSync objects
        """
        return self.session.query(self.model_class)\
            .filter_by(sync_status="error")\
            .all()
    
    def update_sync_status(self, sync_id: int, status: str):
        """
        Update sync record status.
        
        Args:
            sync_id: ID of the sync record
            status: New sync status
            
        Returns:
            Updated QuickBooksSync object
        """
        sync_record = self.session.query(self.model_class).get(sync_id)
        if sync_record:
            sync_record.sync_status = status
            sync_record.last_synced = datetime.utcnow()
            self.session.commit()
        return sync_record
    
    def mark_as_failed(self, sync_id: int, error_message: str):
        """
        Mark sync record as failed.
        
        Args:
            sync_id: ID of the sync record
            error_message: Error description
            
        Returns:
            Updated QuickBooksSync object
        """
        sync_record = self.session.query(self.model_class).get(sync_id)
        if sync_record:
            sync_record.sync_status = "error"
            sync_record.error_message = error_message
            self.session.commit()
        return sync_record
    
    def search(self, query: str) -> List:
        """
        Search sync records by entity ID or type.
        
        Args:
            query: Search query string
            
        Returns:
            List of matching QuickBooksSync objects
        """
        if not query:
            return []
        
        search_filter = or_(
            self.model_class.entity_id.ilike(f'%{query}%'),
            self.model_class.entity_type.ilike(f'%{query}%')
        )
        
        return self.session.query(self.model_class)\
            .filter(search_filter)\
            .limit(100)\
            .all()