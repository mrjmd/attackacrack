"""
SettingRepository - Data access layer for Setting model
"""

from typing import List, Optional
from repositories.base_repository import BaseRepository
from sqlalchemy import or_


class SettingRepository(BaseRepository):
    """Repository for Setting data access"""
    
    def search(self, query: str, fields: Optional[List[str]] = None) -> List:
        """
        Search settings by key or value.
        
        Args:
            query: Search query string
            fields: Fields to search in (ignored, searches key and value by default)
            
        Returns:
            List of matching Setting objects
        """
        if not query:
            return []
        
        search_filter = or_(
            self.model_class.key.ilike(f'%{query}%'),
            self.model_class.value.ilike(f'%{query}%')
        )
        
        return self.session.query(self.model_class)\
            .filter(search_filter)\
            .limit(100)\
            .all()