"""
CampaignListRepository - Data access layer for CampaignList entities
Isolates all database queries related to campaign lists
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlalchemy import or_, desc, asc
from sqlalchemy.orm import Query
from repositories.base_repository import BaseRepository, SortOrder
from crm_database import CampaignList
import logging

logger = logging.getLogger(__name__)


class CampaignListRepository(BaseRepository[CampaignList]):
    """Repository for CampaignList data access"""
    
    def search(self, query: str, fields: Optional[List[str]] = None, limit: Optional[int] = None) -> List[CampaignList]:
        """
        Search campaign lists by text query across multiple fields.
        
        Args:
            query: Search query string
            fields: Specific fields to search (default: name, description)
            limit: Maximum number of results to return
            
        Returns:
            List of matching campaign lists
        """
        if not query:
            return []
        
        search_fields = fields or ['name', 'description']
        
        conditions = []
        for field in search_fields:
            if hasattr(CampaignList, field):
                conditions.append(getattr(CampaignList, field).ilike(f'%{query}%'))
        
        if not conditions:
            return []
        
        query_obj = self.session.query(CampaignList).filter(or_(*conditions))
        if limit:
            query_obj = query_obj.limit(limit)
            
        return query_obj.all()
    
    def find_by_name(self, name: str) -> Optional[CampaignList]:
        """
        Find campaign list by name.
        
        Args:
            name: Campaign list name to search for
            
        Returns:
            CampaignList or None
        """
        return self.find_one_by(name=name)
    
    def find_dynamic_lists(self) -> List[CampaignList]:
        """
        Find all dynamic campaign lists.
        
        Returns:
            List of dynamic campaign lists
        """
        return self.find_by(is_dynamic=True)
    
    def find_static_lists(self) -> List[CampaignList]:
        """
        Find all static campaign lists.
        
        Returns:
            List of static campaign lists
        """
        return self.find_by(is_dynamic=False)
    
    def find_by_creator(self, created_by: str) -> List[CampaignList]:
        """
        Find campaign lists by creator.
        
        Args:
            created_by: Creator identifier
            
        Returns:
            List of campaign lists created by the user
        """
        return self.find_by(created_by=created_by)
    
    def get_lists_ordered_by_created_desc(self) -> List[CampaignList]:
        """
        Get all campaign lists ordered by creation date (newest first).
        
        Returns:
            List of campaign lists ordered by created_at DESC
        """
        return self.get_all(order_by='created_at', order=SortOrder.DESC)
    
    def get_recent_lists(self, limit: int = 10) -> List[CampaignList]:
        """
        Get recently created campaign lists.
        
        Args:
            limit: Maximum number of lists to return
            
        Returns:
            List of recent campaign lists
        """
        return self.session.query(CampaignList).order_by(
            desc(CampaignList.created_at)
        ).limit(limit).all()
    
    def update_timestamp(self, campaign_list: CampaignList) -> CampaignList:
        """
        Update the updated_at timestamp for a campaign list.
        
        Args:
            campaign_list: Campaign list to update
            
        Returns:
            Updated campaign list
        """
        return self.update(campaign_list, updated_at=datetime.utcnow())
    
    def get_list_counts_by_type(self) -> Dict[str, int]:
        """
        Get counts of lists by type (dynamic vs static).
        
        Returns:
            Dictionary with counts: {'dynamic': int, 'static': int, 'total': int}
        """
        total = self.count()
        dynamic = self.count(is_dynamic=True)
        static = total - dynamic
        
        return {
            'dynamic': dynamic,
            'static': static,
            'total': total
        }
    
    def find_lists_with_criteria(self) -> List[CampaignList]:
        """
        Find campaign lists that have filter criteria defined.
        
        Returns:
            List of campaign lists with filter criteria
        """
        return self.session.query(CampaignList).filter(
            CampaignList.filter_criteria.isnot(None)
        ).all()
    
    def find_lists_without_criteria(self) -> List[CampaignList]:
        """
        Find campaign lists that have no filter criteria.
        
        Returns:
            List of campaign lists without filter criteria
        """
        return self.session.query(CampaignList).filter(
            CampaignList.filter_criteria.is_(None)
        ).all()
    
    def update_filter_criteria(self, list_id: int, criteria: Dict[str, Any]) -> Optional[CampaignList]:
        """
        Update filter criteria for a campaign list.
        
        Args:
            list_id: Campaign list ID
            criteria: New filter criteria
            
        Returns:
            Updated campaign list or None if not found
        """
        return self.update_by_id(list_id, filter_criteria=criteria, updated_at=datetime.utcnow())
    
    def get_lists_created_after(self, date: datetime) -> List[CampaignList]:
        """
        Get campaign lists created after a specific date.
        
        Args:
            date: Date threshold
            
        Returns:
            List of campaign lists created after the date
        """
        return self.session.query(CampaignList).filter(
            CampaignList.created_at > date
        ).all()
    
    def get_lists_updated_after(self, date: datetime) -> List[CampaignList]:
        """
        Get campaign lists updated after a specific date.
        
        Args:
            date: Date threshold
            
        Returns:
            List of campaign lists updated after the date
        """
        return self.session.query(CampaignList).filter(
            CampaignList.updated_at > date
        ).all()
