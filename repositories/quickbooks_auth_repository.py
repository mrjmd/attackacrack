"""
QuickBooksAuthRepository - Data access layer for QuickBooksAuth model
"""

from typing import Optional, Dict, Any, List
from datetime import datetime
from sqlalchemy import or_
from repositories.base_repository import BaseRepository
from crm_database import QuickBooksAuth


class QuickBooksAuthRepository(BaseRepository):
    """Repository for QuickBooksAuth data access"""
    
    def find_by_company_id(self, company_id: str) -> Optional[QuickBooksAuth]:
        """
        Find authentication record by QuickBooks company ID.
        
        Args:
            company_id: QuickBooks company ID
            
        Returns:
            QuickBooksAuth object or None if not found
        """
        return self.session.query(self.model_class)\
            .filter_by(company_id=company_id)\
            .first()
    
    def get_first_auth(self) -> Optional[QuickBooksAuth]:
        """
        Get the first authentication record (single company support).
        
        Returns:
            QuickBooksAuth object or None if not found
        """
        return self.session.query(self.model_class).first()
    
    def create_or_update_auth(self, auth_data: Dict[str, Any]) -> QuickBooksAuth:
        """
        Create or update authentication record.
        
        Args:
            auth_data: Dictionary with auth data including:
                - company_id: QuickBooks company ID
                - access_token: Encrypted access token
                - refresh_token: Encrypted refresh token
                - expires_at: Token expiration datetime
                
        Returns:
            Created or updated QuickBooksAuth object
        """
        company_id = auth_data['company_id']
        
        # Check if auth already exists
        auth = self.find_by_company_id(company_id)
        if not auth:
            auth = QuickBooksAuth(company_id=company_id)
            self.session.add(auth)
        
        # Update auth data
        auth.access_token = auth_data['access_token']
        auth.refresh_token = auth_data['refresh_token']
        auth.expires_at = auth_data['expires_at']
        auth.updated_at = datetime.utcnow()
        
        self.session.commit()
        return auth
    
    def update_tokens(self, auth_id: int, access_token: str, 
                     refresh_token: str, expires_at: datetime) -> Optional[QuickBooksAuth]:
        """
        Update access and refresh tokens for an auth record.
        
        Args:
            auth_id: ID of the auth record
            access_token: New encrypted access token
            refresh_token: New encrypted refresh token
            expires_at: New expiration datetime
            
        Returns:
            Updated QuickBooksAuth object or None if not found
        """
        auth = self.session.query(self.model_class).get(auth_id)
        if not auth:
            return None
        
        auth.access_token = access_token
        auth.refresh_token = refresh_token
        auth.expires_at = expires_at
        auth.updated_at = datetime.utcnow()
        
        self.session.commit()
        return auth
    
    def is_token_expired(self, auth_id: int) -> bool:
        """
        Check if the access token for an auth record is expired.
        
        Args:
            auth_id: ID of the auth record
            
        Returns:
            True if expired or record not found, False if still valid
        """
        auth = self.session.query(self.model_class).get(auth_id)
        if not auth:
            return True  # Treat missing record as expired
        
        return datetime.utcnow() >= auth.expires_at
    
    def delete_auth(self, auth_id: int) -> bool:
        """
        Delete authentication record.
        
        Args:
            auth_id: ID of the auth record to delete
            
        Returns:
            True if deleted, False if record not found
        """
        auth = self.session.query(self.model_class).get(auth_id)
        if not auth:
            return False
        
        self.session.delete(auth)
        self.session.commit()
        return True
    
    def search(self, query: str, fields: Optional[List[str]] = None) -> List[QuickBooksAuth]:
        """
        Search authentication records by company ID.
        
        Args:
            query: Search query string
            fields: Fields to search in (ignored for auth records)
            
        Returns:
            List of matching QuickBooksAuth objects
        """
        if not query:
            return []
        
        search_filter = self.model_class.company_id.ilike(f'%{query}%')
        
        return self.session.query(self.model_class)\
            .filter(search_filter)\
            .limit(100)\
            .all()