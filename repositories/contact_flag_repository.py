"""
ContactFlagRepository - Data access layer for ContactFlag entities
Manages contact flags for campaign filtering and compliance.

TDD Implementation: This is the minimal implementation to make tests fail with meaningful errors.
"""

from typing import List, Optional, Dict, Any, Set
from datetime import datetime
from sqlalchemy import or_, and_, func, desc, asc
from sqlalchemy.orm import Query
from repositories.base_repository import BaseRepository, PaginationParams, PaginatedResult, SortOrder
from crm_database import ContactFlag
import logging

logger = logging.getLogger(__name__)


class ContactFlagRepository(BaseRepository[ContactFlag]):
    """Repository for ContactFlag data access"""
    
    def __init__(self, session):
        """Initialize repository with database session"""
        super().__init__(session, ContactFlag)
    
    def search(self, query: str, fields: Optional[List[str]] = None) -> List[ContactFlag]:
        """
        Search contact flags by reason text.
        
        Args:
            query: Search query string
            fields: Specific fields to search (default: flag_reason)
            
        Returns:
            List of matching contact flags
        """
        if not query:
            return []
        
        search_fields = fields or ['flag_reason']
        
        conditions = []
        for field in search_fields:
            if hasattr(ContactFlag, field):
                conditions.append(getattr(ContactFlag, field).ilike(f'%{query}%'))
        
        if not conditions:
            return []
        
        return self.session.query(ContactFlag).filter(or_(*conditions)).all()
    
    # All other methods will raise NotImplementedError to ensure tests fail
    # This enforces the TDD RED phase
    
    def create_flag_for_contact(self, contact_id: int, flag_type: str, 
                              flag_reason: str = None, applies_to: str = 'sms', 
                              created_by: str = None) -> ContactFlag:
        """Create a flag for a specific contact"""
        flag = ContactFlag(
            contact_id=contact_id,
            flag_type=flag_type,
            flag_reason=flag_reason,
            applies_to=applies_to,
            created_by=created_by,
            created_at=datetime.utcnow()
        )
        self.session.add(flag)
        self.session.flush()
        logger.debug(f"Created ContactFlag {flag_type} for contact {contact_id}")
        return flag
    
    def create_temporary_flag(self, contact_id: int, flag_type: str, 
                            expires_at: datetime, flag_reason: str = None) -> ContactFlag:
        """Create a temporary flag with expiration date"""
        flag = ContactFlag(
            contact_id=contact_id,
            flag_type=flag_type,
            flag_reason=flag_reason,
            expires_at=expires_at,
            created_at=datetime.utcnow()
        )
        self.session.add(flag)
        self.session.flush()
        return flag
    
    def bulk_create_flags(self, contact_ids: List[int], flag_type: str, 
                         flag_reason: str = None, applies_to: str = 'sms') -> List[ContactFlag]:
        """Create the same flag for multiple contacts"""
        flags = []
        for contact_id in contact_ids:
            flag = ContactFlag(
                contact_id=contact_id,
                flag_type=flag_type,
                flag_reason=flag_reason,
                applies_to=applies_to,
                created_at=datetime.utcnow()
            )
            flags.append(flag)
        
        self.session.add_all(flags)
        self.session.flush()
        return flags
    
    def find_flags_by_contact_id(self, contact_id: int) -> List[ContactFlag]:
        """Find all flags for a specific contact"""
        return self.session.query(ContactFlag).filter(
            ContactFlag.contact_id == contact_id
        ).all()
    
    def find_flags_by_type(self, flag_type: str) -> List[ContactFlag]:
        """Find all flags of a specific type"""
        return self.session.query(ContactFlag).filter(
            ContactFlag.flag_type == flag_type
        ).all()
    
    def get_contact_ids_with_flag_type(self, flag_type: str) -> Set[int]:
        """Get contact IDs that have a specific flag type"""
        results = self.session.query(ContactFlag.contact_id).filter(
            ContactFlag.flag_type == flag_type
        ).all()
        return {result[0] for result in results}
    
    def check_contact_has_flag_type(self, contact_id: int, flag_type: str) -> bool:
        """Check if a specific contact has a specific flag type"""
        result = self.session.query(ContactFlag).filter(
            and_(ContactFlag.contact_id == contact_id, ContactFlag.flag_type == flag_type)
        ).first()
        return result is not None
    
    def get_active_flags_for_contact(self, contact_id: int) -> List[ContactFlag]:
        """Get only active (non-expired) flags for a contact"""
        now = datetime.utcnow()
        return self.session.query(ContactFlag).filter(
            and_(
                ContactFlag.contact_id == contact_id,
                or_(
                    ContactFlag.expires_at.is_(None),
                    ContactFlag.expires_at > now
                )
            )
        ).all()
    
    def get_expired_flags(self) -> List[ContactFlag]:
        """Find flags that have expired"""
        now = datetime.utcnow()
        return self.session.query(ContactFlag).filter(
            and_(
                ContactFlag.expires_at.is_not(None),
                ContactFlag.expires_at < now
            )
        ).all()
    
    def bulk_check_contacts_for_flag_type(self, contact_ids: List[int], flag_type: str) -> Dict[int, bool]:
        """Check multiple contacts for a specific flag type efficiently"""
        results = self.session.query(ContactFlag.contact_id).filter(
            and_(
                ContactFlag.contact_id.in_(contact_ids),
                ContactFlag.flag_type == flag_type
            )
        ).all()
        
        flagged_ids = {result[0] for result in results}
        return {contact_id: contact_id in flagged_ids for contact_id in contact_ids}
    
    def get_contacts_excluded_from_campaigns(self, channel: str = 'sms', 
                                           exclusion_flags: List[str] = None) -> Set[int]:
        """Get contacts that should be excluded from campaigns based on active flags"""
        if exclusion_flags is None:
            exclusion_flags = ['opted_out', 'do_not_contact', 'office_number', 'recently_texted']
        
        from datetime import datetime
        now = datetime.utcnow()
        
        results = self.session.query(ContactFlag.contact_id).filter(
            and_(
                ContactFlag.flag_type.in_(exclusion_flags),
                or_(
                    ContactFlag.applies_to == channel,
                    ContactFlag.applies_to == 'both'
                ),
                # Only include active flags (not expired)
                or_(
                    ContactFlag.expires_at.is_(None),  # Never expires
                    ContactFlag.expires_at > now       # Expires in the future
                )
            )
        ).distinct().all()
        
        return {result[0] for result in results}
    
    def filter_campaign_eligible_contacts(self, contact_ids: List[int], channel: str = 'sms') -> List[int]:
        """Filter a list of contacts to only campaign-eligible ones"""
        excluded_ids = self.get_contacts_excluded_from_campaigns(channel)
        return [contact_id for contact_id in contact_ids if contact_id not in excluded_ids]
    
    def update_flag_reason(self, flag_id: int, new_reason: str) -> Optional[ContactFlag]:
        """Update the reason for an existing flag"""
        flag = self.get_by_id(flag_id)
        if flag:
            flag.flag_reason = new_reason
            self.session.flush()
        return flag
    
    def extend_flag_expiration(self, flag_id: int, new_expiration: datetime) -> Optional[ContactFlag]:
        """Extend the expiration date of a temporary flag"""
        flag = self.get_by_id(flag_id)
        if flag:
            flag.expires_at = new_expiration
            self.session.flush()
        return flag
    
    def remove_flag_by_id(self, flag_id: int) -> bool:
        """Remove a specific flag by ID"""
        flag = self.get_by_id(flag_id)
        if flag:
            self.session.delete(flag)
            self.session.flush()
            return True
        return False
    
    def remove_flags_by_contact_and_type(self, contact_id: int, flag_type: str) -> int:
        """Remove all flags of a specific type for a contact"""
        count = self.session.query(ContactFlag).filter(
            and_(
                ContactFlag.contact_id == contact_id,
                ContactFlag.flag_type == flag_type
            )
        ).delete(synchronize_session=False)
        self.session.flush()
        return count
    
    def cleanup_expired_flags(self) -> int:
        """Remove all expired flags"""
        now = datetime.utcnow()
        count = self.session.query(ContactFlag).filter(
            and_(
                ContactFlag.expires_at.is_not(None),
                ContactFlag.expires_at < now
            )
        ).delete(synchronize_session=False)
        self.session.flush()
        return count
    
    def bulk_remove_flag_type_for_contacts(self, contact_ids: List[int], flag_type: str) -> int:
        """Remove a specific flag type from multiple contacts"""
        count = self.session.query(ContactFlag).filter(
            and_(
                ContactFlag.contact_id.in_(contact_ids),
                ContactFlag.flag_type == flag_type
            )
        ).delete(synchronize_session=False)
        self.session.flush()
        return count
    
    def find_active_flags(self, contact_id: int, flag_type: Optional[str] = None) -> List[ContactFlag]:
        """Find active (non-expired) flags for a contact, optionally filtered by type"""
        now = datetime.utcnow()
        query = self.session.query(ContactFlag).filter(
            and_(
                ContactFlag.contact_id == contact_id,
                or_(
                    ContactFlag.expires_at.is_(None),
                    ContactFlag.expires_at > now
                )
            )
        )
        
        if flag_type:
            query = query.filter(ContactFlag.flag_type == flag_type)
        
        return query.all()
    
    def find_by_flag_type(self, flag_type: str, active_only: bool = False) -> List[ContactFlag]:
        """Find all flags of a specific type"""
        query = self.session.query(ContactFlag).filter(
            ContactFlag.flag_type == flag_type
        )
        
        if active_only:
            now = datetime.utcnow()
            query = query.filter(
                or_(
                    ContactFlag.expires_at.is_(None),
                    ContactFlag.expires_at > now
                )
            )
        
        return query.all()
    
    def expire_flag(self, flag_id: int) -> Optional[ContactFlag]:
        """Expire a flag by setting its expiration date to now"""
        flag = self.get_by_id(flag_id)
        if flag:
            flag.expires_at = datetime.utcnow()
            self.session.flush()
        return flag
    
    def count_by_flag_type(self, flag_type: str, active_only: bool = True) -> int:
        """Count flags of a specific type"""
        query = self.session.query(ContactFlag).filter(
            ContactFlag.flag_type == flag_type
        )
        
        if active_only:
            now = datetime.utcnow()
            query = query.filter(
                or_(
                    ContactFlag.expires_at.is_(None),
                    ContactFlag.expires_at > now
                )
            )
        
        return query.count()
    
    def create_flag_for_contact_if_not_exists(self, contact_id: int, flag_type: str, 
                                            flag_reason: str = None) -> ContactFlag:
        """Create flag only if it doesn't already exist"""
        existing_flag = self.session.query(ContactFlag).filter(
            and_(
                ContactFlag.contact_id == contact_id,
                ContactFlag.flag_type == flag_type
            )
        ).first()
        
        if existing_flag:
            return existing_flag
        
        return self.create_flag_for_contact(
            contact_id=contact_id,
            flag_type=flag_type,
            flag_reason=flag_reason
        )
    
    def get_flag_statistics(self) -> Dict[str, int]:
        """Get statistics about flag usage"""
        results = self.session.query(
            ContactFlag.flag_type, 
            func.count(ContactFlag.id)
        ).group_by(ContactFlag.flag_type).all()
        
        return {flag_type: count for flag_type, count in results}