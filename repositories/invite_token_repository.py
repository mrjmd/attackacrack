"""
InviteTokenRepository - Data access layer for InviteToken entities
Isolates all database queries related to invite tokens
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from utils.datetime_utils import utc_now
from sqlalchemy import or_, and_, func, desc, asc
from sqlalchemy.orm import Query
from sqlalchemy.exc import SQLAlchemyError
from repositories.base_repository import BaseRepository, PaginationParams, PaginatedResult, SortOrder
from crm_database import InviteToken
import logging

logger = logging.getLogger(__name__)


class InviteTokenRepository(BaseRepository[InviteToken]):
    """Repository for InviteToken data access"""
    
    def __init__(self, session):
        """Initialize repository with database session"""
        super().__init__(session, InviteToken)
    
    def search(self, query: str, fields: Optional[List[str]] = None) -> List[InviteToken]:
        """
        Search invite tokens by text query across multiple fields.
        
        Args:
            query: Search query string
            fields: Specific fields to search (default: email, token)
            
        Returns:
            List of matching invite tokens
        """
        if not query:
            return []
        
        try:
            search_fields = fields or ['email', 'token']
            
            conditions = []
            for field in search_fields:
                if hasattr(InviteToken, field):
                    conditions.append(getattr(InviteToken, field).ilike(f'%{query}%'))
            
            if not conditions:
                return []
            
            return self.session.query(InviteToken).filter(or_(*conditions)).all()
        except SQLAlchemyError as e:
            logger.error(f"Error searching invite tokens: {e}")
            return []
    
    def find_by_token(self, token: str) -> Optional[InviteToken]:
        """
        Find invite token by token string.
        
        Args:
            token: Token string to search for
            
        Returns:
            InviteToken or None
        """
        try:
            return self.session.query(InviteToken).filter_by(token=token).first()
        except SQLAlchemyError as e:
            logger.error(f"Error finding invite by token: {e}")
            return None
    
    def find_by_email(self, email: str) -> List[InviteToken]:
        """
        Find all invite tokens for an email address.
        
        Args:
            email: Email to search for
            
        Returns:
            List of invite tokens for the email
        """
        try:
            return self.session.query(InviteToken).filter_by(email=email).all()
        except SQLAlchemyError as e:
            logger.error(f"Error finding invites by email: {e}")
            return []
    
    def find_unused_invites_by_email(self, email: str) -> List[InviteToken]:
        """
        Find unused invite tokens for an email address.
        
        Args:
            email: Email to search for
            
        Returns:
            List of unused invite tokens for the email
        """
        try:
            return self.session.query(InviteToken).filter_by(email=email, used=False).all()
        except SQLAlchemyError as e:
            logger.error(f"Error finding unused invites by email: {e}")
            return []
    
    def find_valid_invite_by_email(self, email: str) -> Optional[InviteToken]:
        """
        Find a valid (unused and unexpired) invite for an email.
        
        Args:
            email: Email to search for
            
        Returns:
            Valid InviteToken or None
        """
        try:
            now = utc_now()
            return (self.session.query(InviteToken)
                   .filter(
                       and_(
                           InviteToken.email == email,
                           InviteToken.used == False,
                           InviteToken.expires_at > now
                       )
                   )
                   .first())
        except SQLAlchemyError as e:
            logger.error(f"Error finding valid invite by email: {e}")
            return None
    
    def get_expired_invites(self) -> List[InviteToken]:
        """
        Get all expired invite tokens.
        
        Returns:
            List of expired invite tokens
        """
        try:
            now = utc_now()
            return (self.session.query(InviteToken)
                   .filter(InviteToken.expires_at < now)
                   .all())
        except SQLAlchemyError as e:
            logger.error(f"Error getting expired invites: {e}")
            return []
    
    def get_unused_invites(self) -> List[InviteToken]:
        """
        Get all unused invite tokens.
        
        Returns:
            List of unused invite tokens
        """
        try:
            return self.session.query(InviteToken).filter_by(used=False).all()
        except SQLAlchemyError as e:
            logger.error(f"Error getting unused invites: {e}")
            return []
    
    def get_used_invites(self) -> List[InviteToken]:
        """
        Get all used invite tokens.
        
        Returns:
            List of used invite tokens
        """
        try:
            return self.session.query(InviteToken).filter_by(used=True).all()
        except SQLAlchemyError as e:
            logger.error(f"Error getting used invites: {e}")
            return []
    
    def get_invites_by_creator(self, created_by_id: int) -> List[InviteToken]:
        """
        Get invite tokens created by a specific user.
        
        Args:
            created_by_id: ID of the user who created the invites
            
        Returns:
            List of invite tokens created by the user
        """
        try:
            return self.session.query(InviteToken).filter_by(created_by_id=created_by_id).all()
        except SQLAlchemyError as e:
            logger.error(f"Error getting invites by creator: {e}")
            return []
    
    def mark_as_used(self, invite_id: int, used_time: Optional[datetime] = None) -> Optional[InviteToken]:
        """
        Mark an invite token as used.
        
        Args:
            invite_id: Invite token ID
            used_time: Time when invite was used
            
        Returns:
            Updated InviteToken or None if not found
        """
        try:
            invite = self.session.get(InviteToken, invite_id)
            if invite:
                invite.used = True
                invite.used_at = used_time
                self.session.flush()
                return invite
            return None
        except SQLAlchemyError as e:
            logger.error(f"Error marking invite as used: {e}")
            self.session.rollback()
            return None
    
    def get_pending_invites(self, pagination_params: PaginationParams, 
                           current_time: Optional[datetime] = None) -> PaginatedResult[InviteToken]:
        """
        Get paginated list of pending (unused and unexpired) invite tokens.
        
        Args:
            pagination_params: Pagination parameters
            current_time: Current time for expiry check (defaults to )
            
        Returns:
            Paginated result of pending invites
        """
        try:
            now = current_time or utc_now()
            
            # Build query for pending invites
            query = (self.session.query(InviteToken)
                    .filter(
                        and_(
                            InviteToken.used == False,
                            InviteToken.expires_at > now
                        )
                    )
                    .order_by(desc(InviteToken.created_at)))
            
            # Get total count
            total = query.count()
            
            # Get paginated items
            items = query.offset(pagination_params.offset).limit(pagination_params.limit).all()
            
            return PaginatedResult(
                items=items,
                total=total,
                page=pagination_params.page,
                per_page=pagination_params.per_page
            )
        except SQLAlchemyError as e:
            logger.error(f"Error getting pending invites: {e}")
            return PaginatedResult(
                items=[],
                total=0,
                page=pagination_params.page,
                per_page=pagination_params.per_page
            )
    
    def cleanup_expired_invites(self) -> int:
        """
        Delete all expired invite tokens.
        
        Returns:
            Number of deleted invite tokens
        """
        try:
            now = utc_now()
            count = (self.session.query(InviteToken)
                    .filter(InviteToken.expires_at < now)
                    .delete(synchronize_session=False))
            self.session.flush()
            return count
        except SQLAlchemyError as e:
            logger.error(f"Error cleaning up expired invites: {e}")
            self.session.rollback()
            return 0
    
    def get_invite_stats(self) -> Dict[str, int]:
        """
        Get statistics about invite tokens.
        
        Returns:
            Dictionary with various invite counts
        """
        try:
            total_invites = self.session.query(InviteToken).count()
            used_invites = self.session.query(InviteToken).filter_by(used=True).count()
            unused_invites = self.session.query(InviteToken).filter_by(used=False).count()
            
            now = utc_now()
            expired_invites = (self.session.query(InviteToken)
                             .filter(InviteToken.expires_at < now)
                             .count())
            
            return {
                'total_invites': total_invites,
                'used_invites': used_invites,
                'unused_invites': unused_invites,
                'expired_invites': expired_invites
            }
        except SQLAlchemyError as e:
            logger.error(f"Error getting invite stats: {e}")
            return {
                'total_invites': 0,
                'used_invites': 0,
                'unused_invites': 0,
                'expired_invites': 0
            }
    
    def get_recent_invites(self, days: int = 30, limit: int = 10) -> List[InviteToken]:
        """
        Get recently created invite tokens.
        
        Args:
            days: Number of days to look back
            limit: Maximum number of invites to return
            
        Returns:
            List of recently created invite tokens
        """
        if days <= 0 or limit <= 0:
            return []
        
        try:
            cutoff_date = utc_now() - timedelta(days=days)
            return (self.session.query(InviteToken)
                   .filter(InviteToken.created_at >= cutoff_date)
                   .order_by(desc(InviteToken.created_at))
                   .limit(limit)
                   .all())
        except SQLAlchemyError as e:
            logger.error(f"Error getting recent invites: {e}")
            return []
    
    def get_invites_expiring_soon(self, hours: int = 24) -> List[InviteToken]:
        """
        Get invite tokens expiring soon.
        
        Args:
            hours: Number of hours to look ahead
            
        Returns:
            List of invite tokens expiring soon
        """
        if hours <= 0:
            return []
        
        try:
            now = utc_now()
            cutoff_time = now + timedelta(hours=hours)
            return (self.session.query(InviteToken)
                   .filter(
                       and_(
                           InviteToken.expires_at <= cutoff_time,
                           InviteToken.expires_at > now,
                           InviteToken.used == False
                       )
                   )
                   .order_by(asc(InviteToken.expires_at))
                   .all())
        except SQLAlchemyError as e:
            logger.error(f"Error getting invites expiring soon: {e}")
            return []
    
    def get_paginated_invites(
        self,
        pagination: PaginationParams,
        used_filter: Optional[bool] = None,
        role_filter: Optional[str] = None
    ) -> PaginatedResult[InviteToken]:
        """
        Get paginated invite tokens with optional filtering.
        
        Args:
            pagination: Pagination parameters
            used_filter: Filter by used status (None for all)
            role_filter: Filter by role
            
        Returns:
            PaginatedResult with invite tokens
        """
        try:
            query = self.session.query(InviteToken)
            
            # Apply filters
            if used_filter is not None:
                query = query.filter_by(used=used_filter)
            if role_filter:
                query = query.filter_by(role=role_filter)
            
            # Apply ordering
            query = query.order_by(desc(InviteToken.created_at))
            
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
            logger.error(f"Error getting paginated invites: {e}")
            return PaginatedResult(items=[], total=0, page=1, per_page=pagination.per_page)
    
    def bulk_expire_invites_by_email(self, email: str) -> int:
        """
        Bulk expire all unused invites for an email.
        
        Args:
            email: Email address
            
        Returns:
            Number of expired invites
        """
        try:
            now = utc_now()
            count = (self.session.query(InviteToken)
                    .filter(
                        and_(
                            InviteToken.email == email,
                            InviteToken.used == False
                        )
                    )
                    .update({'expires_at': now}, synchronize_session=False))
            self.session.flush()
            return count
        except SQLAlchemyError as e:
            logger.error(f"Error bulk expiring invites: {e}")
            self.session.rollback()
            return 0