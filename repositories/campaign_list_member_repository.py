"""
CampaignListMemberRepository - Data access layer for CampaignListMember entities
Isolates all database queries related to campaign list members
"""

from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime
from sqlalchemy import and_, or_, func, desc
from sqlalchemy.orm import Query, joinedload
from repositories.base_repository import BaseRepository
from crm_database import CampaignListMember, Contact
import logging

logger = logging.getLogger(__name__)


class CampaignListMemberRepository(BaseRepository[CampaignListMember]):
    """Repository for CampaignListMember data access"""
    
    def search(self, query: str, fields: Optional[List[str]] = None, limit: Optional[int] = None) -> List[CampaignListMember]:
        """
        Search campaign list members by contact information.
        
        Args:
            query: Search query string
            fields: Fields to search in contact info (default: first_name, last_name)
            limit: Maximum number of results to return
            
        Returns:
            List of matching campaign list members
        """
        if not query:
            return []
        
        search_fields = fields or ['first_name', 'last_name']
        
        # Build conditions for contact fields
        conditions = []
        for field in search_fields:
            if hasattr(Contact, field):
                conditions.append(getattr(Contact, field).ilike(f'%{query}%'))
        
        if not conditions:
            return []
        
        query_obj = self.session.query(CampaignListMember).join(Contact).filter(
            or_(*conditions)
        )
        
        if limit:
            query_obj = query_obj.limit(limit)
            
        return query_obj.all()
    
    def find_by_list_id(self, list_id: int) -> List[CampaignListMember]:
        """
        Find all members of a specific campaign list.
        
        Args:
            list_id: Campaign list ID
            
        Returns:
            List of campaign list members
        """
        return self.find_by(list_id=list_id)
    
    def find_by_contact_id(self, contact_id: int) -> List[CampaignListMember]:
        """
        Find all campaign list memberships for a contact.
        
        Args:
            contact_id: Contact ID
            
        Returns:
            List of campaign list members
        """
        return self.find_by(contact_id=contact_id)
    
    def find_by_list_and_contact(self, list_id: int, contact_id: int) -> Optional[CampaignListMember]:
        """
        Find specific membership by list and contact.
        
        Args:
            list_id: Campaign list ID
            contact_id: Contact ID
            
        Returns:
            Campaign list member or None
        """
        return self.find_one_by(list_id=list_id, contact_id=contact_id)
    
    def find_active_members(self, list_id: int) -> List[CampaignListMember]:
        """
        Find active members of a campaign list.
        
        Args:
            list_id: Campaign list ID
            
        Returns:
            List of active campaign list members
        """
        return self.find_by(list_id=list_id, status='active')
    
    def find_removed_members(self, list_id: int) -> List[CampaignListMember]:
        """
        Find removed members of a campaign list.
        
        Args:
            list_id: Campaign list ID
            
        Returns:
            List of removed campaign list members
        """
        return self.find_by(list_id=list_id, status='removed')
    
    def get_members_with_contacts(self, list_id: int, include_removed: bool = False) -> List[Tuple[CampaignListMember, Contact]]:
        """
        Get campaign list members with their contact information.
        
        Args:
            list_id: Campaign list ID
            include_removed: Whether to include removed members
            
        Returns:
            List of (member, contact) tuples
        """
        query = self.session.query(CampaignListMember, Contact).join(
            Contact, CampaignListMember.contact_id == Contact.id
        ).filter(CampaignListMember.list_id == list_id)
        
        if not include_removed:
            query = query.filter(CampaignListMember.status == 'active')
        
        return query.all()
    
    def get_active_members_with_contacts(self, list_id: int) -> List[Tuple[CampaignListMember, Contact]]:
        """
        Get active campaign list members with their contact information.
        
        Args:
            list_id: Campaign list ID
            
        Returns:
            List of (member, contact) tuples for active members
        """
        return self.get_members_with_contacts(list_id, include_removed=False)
    
    def get_contact_ids_in_list(self, list_id: int, include_removed: bool = False) -> List[int]:
        """
        Get all contact IDs in a campaign list.
        
        Args:
            list_id: Campaign list ID
            include_removed: Whether to include removed members
            
        Returns:
            List of contact IDs
        """
        query = self.session.query(CampaignListMember.contact_id).filter(
            CampaignListMember.list_id == list_id
        )
        
        if not include_removed:
            query = query.filter(CampaignListMember.status == 'active')
        
        return [row[0] for row in query.all()]
    
    def member_exists_in_list(self, list_id: int, contact_id: int) -> bool:
        """
        Check if a member exists in a campaign list.
        
        Args:
            list_id: Campaign list ID
            contact_id: Contact ID
            
        Returns:
            True if member exists, False otherwise
        """
        return self.exists(list_id=list_id, contact_id=contact_id)
    
    def get_member_status(self, list_id: int, contact_id: int) -> Optional[str]:
        """
        Get the status of a member in a campaign list.
        
        Args:
            list_id: Campaign list ID
            contact_id: Contact ID
            
        Returns:
            Member status or None if not found
        """
        member = self.find_one_by(list_id=list_id, contact_id=contact_id)
        return member.status if member else None
    
    def remove_contacts_from_list(self, list_id: int, contact_ids: List[int]) -> int:
        """
        Soft-delete members from a campaign list.
        
        Args:
            list_id: Campaign list ID
            contact_ids: List of contact IDs to remove
            
        Returns:
            Number of members removed
        """
        return self.update_many(
            filters={
                'list_id': list_id,
                'contact_id': contact_ids,
                'status': 'active'
            },
            updates={'status': 'removed'}
        )
    
    def reactivate_member(self, list_id: int, contact_id: int, added_by: str = None) -> bool:
        """
        Reactivate a removed member.
        
        Args:
            list_id: Campaign list ID
            contact_id: Contact ID
            added_by: User who reactivated the member
            
        Returns:
            True if reactivated, False if member not found
        """
        member = self.find_one_by(list_id=list_id, contact_id=contact_id)
        if member:
            self.update(
                member,
                status='active',
                added_at=datetime.utcnow(),
                added_by=added_by
            )
            return True
        return False
    
    def get_membership_stats(self, list_id: int) -> Dict[str, int]:
        """
        Get membership statistics for a campaign list.
        
        Args:
            list_id: Campaign list ID
            
        Returns:
            Dictionary with membership counts
        """
        total = self.count(list_id=list_id)
        active = self.count(list_id=list_id, status='active')
        removed = self.count(list_id=list_id, status='removed')
        
        return {
            'total': total,
            'active': active,
            'removed': removed
        }
    
    def get_members_added_by(self, added_by: str) -> List[CampaignListMember]:
        """
        Get all members added by a specific user.
        
        Args:
            added_by: User identifier
            
        Returns:
            List of campaign list members
        """
        return self.find_by(added_by=added_by)
    
    def get_members_added_after(self, date: datetime, list_id: Optional[int] = None) -> List[CampaignListMember]:
        """
        Get members added after a specific date.
        
        Args:
            date: Date threshold
            list_id: Optional list ID to filter by
            
        Returns:
            List of campaign list members
        """
        query = self.session.query(CampaignListMember).filter(
            CampaignListMember.added_at > date
        )
        
        if list_id:
            query = query.filter(CampaignListMember.list_id == list_id)
        
        return query.all()
    
    def bulk_update_status(self, list_id: int, contact_ids: List[int], new_status: str) -> int:
        """
        Bulk update status for multiple members.
        
        Args:
            list_id: Campaign list ID
            contact_ids: List of contact IDs
            new_status: New status to set
            
        Returns:
            Number of members updated
        """
        return self.update_many(
            filters={
                'list_id': list_id,
                'contact_id': contact_ids
            },
            updates={'status': new_status}
        )
    
    def get_recent_members(self, list_id: int, limit: int = 10) -> List[CampaignListMember]:
        """
        Get recently added members to a campaign list.
        
        Args:
            list_id: Campaign list ID
            limit: Maximum number of members to return
            
        Returns:
            List of recent campaign list members
        """
        return self.session.query(CampaignListMember).filter(
            CampaignListMember.list_id == list_id
        ).order_by(
            desc(CampaignListMember.added_at)
        ).limit(limit).all()
    
    def count_by_status(self, list_id: int) -> Dict[str, int]:
        """
        Count members by status for a campaign list.
        
        Args:
            list_id: Campaign list ID
            
        Returns:
            Dictionary with counts by status
        """
        counts = self.session.query(
            CampaignListMember.status,
            func.count(CampaignListMember.id).label('count')
        ).filter(
            CampaignListMember.list_id == list_id
        ).group_by(CampaignListMember.status).all()
        
        result = {'active': 0, 'removed': 0, 'suppressed': 0}
        for status, count in counts:
            result[status] = count
        
        return result
