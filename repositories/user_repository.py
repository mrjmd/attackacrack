"""
UserRepository - Data access layer for User entities
Isolates all database queries related to users
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy import or_, and_, func, desc, asc
from sqlalchemy.orm import Query
from sqlalchemy.exc import SQLAlchemyError
from repositories.base_repository import BaseRepository, PaginationParams, PaginatedResult, SortOrder
from crm_database import User
import logging

logger = logging.getLogger(__name__)


class UserRepository(BaseRepository[User]):
    """Repository for User data access"""
    
    def search(self, query: str, fields: Optional[List[str]] = None) -> List[User]:
        """
        Search users by text query across multiple fields.
        
        Args:
            query: Search query string
            fields: Specific fields to search (default: email, name)
            
        Returns:
            List of matching users
        """
        if not query:
            return []
        
        try:
            search_fields = fields or ['email', 'first_name', 'last_name']
            
            conditions = []
            for field in search_fields:
                if hasattr(User, field):
                    conditions.append(getattr(User, field).ilike(f'%{query}%'))
            
            if not conditions:
                return []
            
            return self.session.query(User).filter(or_(*conditions)).all()
        except SQLAlchemyError as e:
            logger.error(f"Error searching users: {e}")
            return []
    
    def find_by_email(self, email: str) -> Optional[User]:
        """
        Find user by email address.
        
        Args:
            email: Email to search for
            
        Returns:
            User or None
        """
        try:
            return self.session.query(User).filter_by(email=email).first()
        except SQLAlchemyError as e:
            logger.error(f"Error finding user by email: {e}")
            return None
    
    def find_by_role(self, role: str) -> List[User]:
        """
        Find users by role.
        
        Args:
            role: Role to search for
            
        Returns:
            List of users with the specified role
        """
        try:
            return self.session.query(User).filter_by(role=role).all()
        except SQLAlchemyError as e:
            logger.error(f"Error finding users by role: {e}")
            return []
    
    def find_active_users(self) -> List[User]:
        """
        Find all active users.
        
        Returns:
            List of active users
        """
        try:
            return self.session.query(User).filter_by(is_active=True).all()
        except SQLAlchemyError as e:
            logger.error(f"Error finding active users: {e}")
            return []
    
    def find_inactive_users(self) -> List[User]:
        """
        Find all inactive users.
        
        Returns:
            List of inactive users
        """
        try:
            return self.session.query(User).filter_by(is_active=False).all()
        except SQLAlchemyError as e:
            logger.error(f"Error finding inactive users: {e}")
            return []
    
    def get_user_stats(self) -> Dict[str, int]:
        """
        Get statistics about users.
        
        Returns:
            Dictionary with various user counts
        """
        try:
            total_users = self.session.query(User).count()
            active_users = self.session.query(User).filter_by(is_active=True).count()
            inactive_users = self.session.query(User).filter_by(is_active=False).count()
            admin_users = self.session.query(User).filter_by(role='admin').count()
            
            return {
                'total_users': total_users,
                'active_users': active_users,
                'inactive_users': inactive_users,
                'admin_users': admin_users
            }
        except SQLAlchemyError as e:
            logger.error(f"Error getting user stats: {e}")
            return {
                'total_users': 0,
                'active_users': 0,
                'inactive_users': 0,
                'admin_users': 0
            }
    
    def count_by_role(self, role: str) -> int:
        """
        Count users by role.
        
        Args:
            role: Role to count
            
        Returns:
            Number of users with the specified role
        """
        try:
            return self.session.query(User).filter_by(role=role).count()
        except SQLAlchemyError as e:
            logger.error(f"Error counting users by role: {e}")
            return 0
    
    def get_recent_users(self, days: int = 30, limit: int = 10) -> List[User]:
        """
        Get recently created users.
        
        Args:
            days: Number of days to look back
            limit: Maximum number of users to return
            
        Returns:
            List of recently created users
        """
        if days <= 0 or limit <= 0:
            return []
        
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            return (self.session.query(User)
                   .filter(User.created_at >= cutoff_date)
                   .order_by(desc(User.created_at))
                   .limit(limit)
                   .all())
        except SQLAlchemyError as e:
            logger.error(f"Error getting recent users: {e}")
            return []
    
    def update_last_login(self, user_id: int, login_time: datetime) -> Optional[User]:
        """
        Update user's last login timestamp.
        
        Args:
            user_id: User ID
            login_time: Login timestamp
            
        Returns:
            Updated user or None if not found
        """
        try:
            user = self.session.get(User, user_id)
            if user:
                user.last_login = login_time
                self.session.flush()
                return user
            return None
        except SQLAlchemyError as e:
            logger.error(f"Error updating last login: {e}")
            self.session.rollback()
            return None
    
    def deactivate_user(self, user_id: int) -> Optional[User]:
        """
        Deactivate a user.
        
        Args:
            user_id: User ID
            
        Returns:
            Updated user or None if not found
        """
        try:
            user = self.session.get(User, user_id)
            if user:
                user.is_active = False
                self.session.flush()
                return user
            return None
        except SQLAlchemyError as e:
            logger.error(f"Error deactivating user: {e}")
            self.session.rollback()
            return None
    
    def activate_user(self, user_id: int) -> Optional[User]:
        """
        Activate a user.
        
        Args:
            user_id: User ID
            
        Returns:
            Updated user or None if not found
        """
        try:
            user = self.session.get(User, user_id)
            if user:
                user.is_active = True
                self.session.flush()
                return user
            return None
        except SQLAlchemyError as e:
            logger.error(f"Error activating user: {e}")
            self.session.rollback()
            return None
    
    def get_paginated_users(
        self,
        pagination: PaginationParams,
        role_filter: Optional[str] = None,
        active_only: bool = False
    ) -> PaginatedResult[User]:
        """
        Get paginated users with optional filtering.
        
        Args:
            pagination: Pagination parameters
            role_filter: Optional role to filter by
            active_only: If True, only return active users
            
        Returns:
            PaginatedResult with users
        """
        try:
            query = self.session.query(User)
            
            # Apply filters
            if role_filter:
                query = query.filter_by(role=role_filter)
            if active_only:
                query = query.filter_by(is_active=True)
            
            # Apply ordering
            query = query.order_by(asc(User.email))
            
            # Get total count
            total = query.count()
            
            # Apply pagination
            items = query.offset(pagination.offset).limit(pagination.limit).all()
            
            return PaginatedResult(
                items=items,
                total=total,
                page=pagination.page,
                per_page=pagination.per_page
            )
        except SQLAlchemyError as e:
            logger.error(f"Error getting paginated users: {e}")
            return PaginatedResult(items=[], total=0, page=1, per_page=pagination.per_page)
    
    def search_users(self, query: str, search_fields: Optional[List[str]] = None) -> List[User]:
        """
        Search users across multiple fields.
        
        Args:
            query: Search query string
            search_fields: Fields to search in
            
        Returns:
            List of matching users
        """
        if not query:
            return []
        
        try:
            fields = search_fields or ['email', 'first_name', 'last_name']
            conditions = []
            
            for field in fields:
                if hasattr(User, field):
                    conditions.append(getattr(User, field).ilike(f'%{query}%'))
            
            if not conditions:
                return []
            
            return self.session.query(User).filter(or_(*conditions)).all()
        except SQLAlchemyError as e:
            logger.error(f"Error searching users: {e}")
            return []