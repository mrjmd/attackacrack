"""
CampaignMembershipRepository - Data access layer for CampaignMembership model
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from utils.datetime_utils import utc_now
from sqlalchemy import desc, and_, or_
from repositories.base_repository import BaseRepository
from crm_database import CampaignMembership


class CampaignMembershipRepository(BaseRepository):
    """Repository for CampaignMembership data access"""
    
    def __init__(self, session):
        """Initialize repository with database session"""
        super().__init__(session, CampaignMembership)
    
    def find_by_contact_and_campaign(self, contact_id: int, campaign_id: int) -> Optional[CampaignMembership]:
        """
        Find membership by contact and campaign IDs.
        
        Args:
            contact_id: ID of the contact
            campaign_id: ID of the campaign
            
        Returns:
            CampaignMembership object or None if not found
        """
        return self.session.query(self.model_class)\
            .filter_by(contact_id=contact_id, campaign_id=campaign_id)\
            .first()
    
    def find_active_memberships_for_contact(self, contact_id: int, hours_window: int = 72) -> List[CampaignMembership]:
        """
        Find active campaign memberships for a contact within a time window.
        
        Args:
            contact_id: ID of the contact
            hours_window: Time window in hours to consider memberships active
            
        Returns:
            List of CampaignMembership objects that were sent within the window
        """
        cutoff_time = utc_now() - timedelta(hours=hours_window)
        
        return self.session.query(self.model_class)\
            .filter(
                and_(
                    self.model_class.contact_id == contact_id,
                    self.model_class.status == 'sent',
                    self.model_class.sent_at >= cutoff_time,
                    self.model_class.reply_activity_id.is_(None)  # Not yet replied
                )
            )\
            .order_by(desc(self.model_class.sent_at))\
            .all()
    
    def find_by_sent_activity_id(self, activity_id: int) -> Optional[CampaignMembership]:
        """
        Find membership by sent activity ID.
        
        Args:
            activity_id: ID of the sent activity
            
        Returns:
            CampaignMembership object or None if not found
        """
        return self.session.query(self.model_class)\
            .filter_by(sent_activity_id=activity_id)\
            .first()
    
    def find_by_campaign_id(self, campaign_id: int) -> List[CampaignMembership]:
        """
        Find all memberships for a campaign.
        
        Args:
            campaign_id: ID of the campaign
            
        Returns:
            List of CampaignMembership objects for the campaign
        """
        return self.session.query(self.model_class)\
            .filter_by(campaign_id=campaign_id)\
            .all()
    
    def find_pending_for_campaign(self, campaign_id: int, limit: int = 100) -> List[CampaignMembership]:
        """
        Find pending memberships for a campaign.
        
        Args:
            campaign_id: ID of the campaign
            limit: Maximum number of results
            
        Returns:
            List of pending CampaignMembership objects
        """
        return self.session.query(self.model_class)\
            .filter_by(campaign_id=campaign_id, status='pending')\
            .limit(limit)\
            .all()
    
    def update_membership_status(self, membership_id: int, status: str, **kwargs) -> Optional[CampaignMembership]:
        """
        Update membership status and additional fields.
        
        Args:
            membership_id: ID of the membership
            status: New status value
            **kwargs: Additional fields to update
            
        Returns:
            Updated CampaignMembership object or None if not found
        """
        membership = self.get_by_id(membership_id)
        if membership:
            membership.status = status
            for key, value in kwargs.items():
                if hasattr(membership, key):
                    setattr(membership, key, value)
            self.session.commit()
        return membership
    
    def mark_as_replied(self, membership_id: int, reply_activity_id: int, 
                       sentiment: Optional[str] = None) -> Optional[CampaignMembership]:
        """
        Mark a membership as replied with sentiment analysis.
        
        Args:
            membership_id: ID of the membership
            reply_activity_id: ID of the reply activity
            sentiment: Sentiment of the reply (positive/negative/neutral)
            
        Returns:
            Updated CampaignMembership object or None if not found
        """
        membership = self.get_by_id(membership_id)
        if membership:
            membership.reply_activity_id = reply_activity_id
            membership.response_sentiment = sentiment
            
            # Update status based on sentiment
            if sentiment == 'positive':
                membership.status = 'replied_positive'
            elif sentiment == 'negative':
                membership.status = 'replied_negative'
            else:
                membership.status = 'replied'
            
            self.session.commit()
        return membership
    
    def count_by_status(self, campaign_id: int) -> Dict[str, int]:
        """
        Count memberships by status for a campaign.
        
        Args:
            campaign_id: ID of the campaign
            
        Returns:
            Dictionary with status as key and count as value
        """
        from sqlalchemy import func
        
        results = self.session.query(
            self.model_class.status,
            func.count(self.model_class.id)
        ).filter_by(campaign_id=campaign_id)\
        .group_by(self.model_class.status)\
        .all()
        
        return {status: count for status, count in results}
    
    def find_recent_replies(self, campaign_id: int, limit: int = 50) -> List[CampaignMembership]:
        """
        Find recent replies for a campaign.
        
        Args:
            campaign_id: ID of the campaign
            limit: Maximum number of results
            
        Returns:
            List of CampaignMembership objects with replies
        """
        return self.session.query(self.model_class)\
            .filter(
                and_(
                    self.model_class.campaign_id == campaign_id,
                    self.model_class.reply_activity_id.isnot(None)
                )
            )\
            .order_by(desc(self.model_class.id))\
            .limit(limit)\
            .all()
    
    def search(self, query: str, fields: Optional[List[str]] = None) -> List[CampaignMembership]:
        """
        Search campaign memberships by text query.
        
        Args:
            query: Search query string
            fields: Fields to search in (defaults to status and variant_sent)
            
        Returns:
            List of matching CampaignMembership objects
        """
        if not query:
            return []
        
        # Default search fields for campaign membership
        if fields is None:
            fields = ['status', 'variant_sent', 'response_sentiment']
        
        from sqlalchemy import or_
        
        # Build search conditions
        search_conditions = []
        for field in fields:
            if hasattr(self.model_class, field):
                column = getattr(self.model_class, field)
                search_conditions.append(column.ilike(f'%{query}%'))
        
        if not search_conditions:
            return []
        
        return self.session.query(self.model_class)\
            .filter(or_(*search_conditions))\
            .all()