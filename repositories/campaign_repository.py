"""
CampaignRepository - Data access layer for Campaign entities
Isolates all database queries related to campaigns
"""

from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
from sqlalchemy import and_, or_, func, desc, asc
from sqlalchemy.orm import joinedload, Query
from repositories.base_repository import BaseRepository, PaginationParams, PaginatedResult, SortOrder
from crm_database import Campaign, CampaignMembership, Contact, ContactFlag, Activity
import logging

logger = logging.getLogger(__name__)


class CampaignRepository(BaseRepository[Campaign]):
    """Repository for Campaign data access"""
    
    def search(self, query: str, fields: Optional[List[str]] = None) -> List[Campaign]:
        """
        Search campaigns by text query.
        
        Args:
            query: Search query string
            fields: Specific fields to search (default: name, description)
            
        Returns:
            List of matching campaigns
        """
        if not query:
            return []
        
        search_fields = fields or ['name', 'template_a', 'template_b']
        
        conditions = []
        for field in search_fields:
            if hasattr(Campaign, field):
                column = getattr(Campaign, field)
                if column is not None:
                    conditions.append(column.ilike(f'%{query}%'))
        
        if not conditions:
            return []
        
        return self.session.query(Campaign).filter(or_(*conditions)).all()
    
    def get_active_campaigns(self) -> List[Campaign]:
        """
        Get all active campaigns.
        
        Returns:
            List of active campaigns
        """
        return self.find_by(status='active')
    
    def get_draft_campaigns(self) -> List[Campaign]:
        """
        Get all draft campaigns.
        
        Returns:
            List of draft campaigns
        """
        return self.find_by(status='draft')
    
    def get_completed_campaigns(self) -> List[Campaign]:
        """
        Get all completed campaigns.
        
        Returns:
            List of completed campaigns
        """
        return self.find_by(status='completed')
    
    def get_campaigns_by_type(self, campaign_type: str) -> List[Campaign]:
        """
        Get campaigns by type.
        
        Args:
            campaign_type: Type of campaign ('blast', 'automated', 'ab_test')
            
        Returns:
            List of campaigns of specified type
        """
        return self.find_by(campaign_type=campaign_type)
    
    def get_campaigns_by_channel(self, channel: str) -> List[Campaign]:
        """
        Get campaigns by channel.
        
        Args:
            channel: Channel type ('sms', 'email')
            
        Returns:
            List of campaigns for specified channel
        """
        return self.find_by(channel=channel)
    
    def get_campaigns_with_stats(self) -> List[Dict[str, Any]]:
        """
        Get all campaigns with statistics.
        
        Returns:
            List of campaigns with stats (sent, delivered, responded, opted_out counts)
        """
        campaigns = self.get_all()
        result = []
        
        for campaign in campaigns:
            stats = self.get_campaign_stats(campaign.id)
            result.append({
                'campaign': campaign,
                'stats': stats
            })
        
        return result
    
    def get_campaign_stats(self, campaign_id: int) -> Dict[str, int]:
        """
        Get statistics for a specific campaign.
        
        Args:
            campaign_id: Campaign ID
            
        Returns:
            Dictionary with campaign statistics
        """
        # Get membership counts by status
        memberships = self.session.query(
            CampaignMembership.status,
            func.count(CampaignMembership.id)
        ).filter(
            CampaignMembership.campaign_id == campaign_id
        ).group_by(CampaignMembership.status).all()
        
        stats = {
            'total_recipients': 0,
            'pending': 0,
            'sent': 0,
            'delivered': 0,
            'responded': 0,
            'opted_out': 0,
            'failed': 0
        }
        
        for status, count in memberships:
            stats[status] = count
            stats['total_recipients'] += count
        
        # Calculate response rate
        if stats['sent'] > 0:
            stats['response_rate'] = (stats['responded'] / stats['sent']) * 100
        else:
            stats['response_rate'] = 0
        
        # Calculate opt-out rate
        if stats['delivered'] > 0:
            stats['opt_out_rate'] = (stats['opted_out'] / stats['delivered']) * 100
        else:
            stats['opt_out_rate'] = 0
        
        return stats
    
    def get_campaign_members(
        self,
        campaign_id: int,
        status: Optional[str] = None,
        pagination: Optional[PaginationParams] = None
    ) -> PaginatedResult[CampaignMembership]:
        """
        Get campaign members with optional status filter.
        
        Args:
            campaign_id: Campaign ID
            status: Optional status filter
            pagination: Optional pagination parameters
            
        Returns:
            PaginatedResult of campaign memberships
        """
        query = self.session.query(CampaignMembership).filter(
            CampaignMembership.campaign_id == campaign_id
        )
        
        if status:
            query = query.filter(CampaignMembership.status == status)
        
        # Include contact data
        query = query.options(joinedload(CampaignMembership.contact))
        
        total = query.count()
        
        if pagination:
            items = query.offset(pagination.offset).limit(pagination.limit).all()
            return PaginatedResult(
                items=items,
                total=total,
                page=pagination.page,
                per_page=pagination.per_page
            )
        else:
            items = query.all()
            return PaginatedResult(
                items=items,
                total=total,
                page=1,
                per_page=total or 1
            )
    
    def get_pending_members(self, campaign_id: int, limit: int = 100) -> List[CampaignMembership]:
        """
        Get pending campaign members ready to send.
        
        Args:
            campaign_id: Campaign ID
            limit: Maximum number to return
            
        Returns:
            List of pending memberships
        """
        return self.session.query(CampaignMembership).filter(
            CampaignMembership.campaign_id == campaign_id,
            CampaignMembership.status == 'pending'
        ).options(
            joinedload(CampaignMembership.contact)
        ).limit(limit).all()
    
    def get_member_by_contact(self, campaign_id: int, contact_id: int) -> Optional[CampaignMembership]:
        """
        Get campaign membership for a specific contact.
        
        Args:
            campaign_id: Campaign ID
            contact_id: Contact ID
            
        Returns:
            CampaignMembership or None
        """
        return self.session.query(CampaignMembership).filter(
            CampaignMembership.campaign_id == campaign_id,
            CampaignMembership.contact_id == contact_id
        ).first()
    
    def add_member(
        self,
        campaign_id: int,
        contact_id: int,
        variant: Optional[str] = None,
        status: str = 'pending'
    ) -> CampaignMembership:
        """
        Add a contact to a campaign.
        
        Args:
            campaign_id: Campaign ID
            contact_id: Contact ID
            variant: A/B test variant ('A' or 'B')
            status: Initial status
            
        Returns:
            Created CampaignMembership
        """
        # Check if already exists
        existing = self.get_member_by_contact(campaign_id, contact_id)
        if existing:
            return existing
        
        membership = CampaignMembership(
            campaign_id=campaign_id,
            contact_id=contact_id,
            variant=variant,
            status=status
        )
        
        self.session.add(membership)
        self.session.flush()
        
        return membership
    
    def add_members_bulk(
        self,
        campaign_id: int,
        contact_ids: List[int],
        variant: Optional[str] = None
    ) -> int:
        """
        Add multiple contacts to a campaign.
        
        Args:
            campaign_id: Campaign ID
            contact_ids: List of contact IDs
            variant: A/B test variant for all contacts
            
        Returns:
            Number of members added
        """
        # Get existing members
        existing = self.session.query(CampaignMembership.contact_id).filter(
            CampaignMembership.campaign_id == campaign_id,
            CampaignMembership.contact_id.in_(contact_ids)
        ).all()
        
        existing_ids = {m[0] for m in existing}
        new_ids = [cid for cid in contact_ids if cid not in existing_ids]
        
        # Create new memberships
        memberships = [
            CampaignMembership(
                campaign_id=campaign_id,
                contact_id=contact_id,
                variant=variant,
                status='pending'
            )
            for contact_id in new_ids
        ]
        
        if memberships:
            self.session.bulk_save_objects(memberships)
            self.session.flush()
        
        return len(memberships)
    
    def update_member_status(
        self,
        campaign_id: int,
        contact_id: int,
        status: str,
        response_sentiment: Optional[str] = None,
        opted_out_at: Optional[datetime] = None
    ) -> bool:
        """
        Update campaign member status.
        
        Args:
            campaign_id: Campaign ID
            contact_id: Contact ID
            status: New status
            response_sentiment: Optional sentiment for responses
            opted_out_at: Optional opt-out timestamp
            
        Returns:
            True if updated, False if not found
        """
        membership = self.get_member_by_contact(campaign_id, contact_id)
        
        if not membership:
            return False
        
        membership.status = status
        
        if status == 'sent':
            membership.sent_at = datetime.utcnow()
        elif status == 'delivered':
            membership.delivered_at = datetime.utcnow()
        elif status == 'responded':
            membership.responded_at = datetime.utcnow()
            if response_sentiment:
                membership.response_sentiment = response_sentiment
        elif status == 'opted_out':
            membership.opted_out_at = opted_out_at or datetime.utcnow()
        
        self.session.flush()
        return True
    
    def get_campaigns_needing_send(self) -> List[Campaign]:
        """
        Get active campaigns that have pending messages to send.
        
        Returns:
            List of campaigns with pending messages
        """
        return self.session.query(Campaign).filter(
            Campaign.status == 'active'
        ).join(CampaignMembership).filter(
            CampaignMembership.status == 'pending'
        ).distinct().all()
    
    def get_today_send_count(self, campaign_id: int) -> int:
        """
        Get count of messages sent today for a campaign.
        
        Args:
            campaign_id: Campaign ID
            
        Returns:
            Number of messages sent today
        """
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        
        return self.session.query(CampaignMembership).filter(
            CampaignMembership.campaign_id == campaign_id,
            CampaignMembership.sent_at >= today_start
        ).count()
    
    def get_ab_test_results(self, campaign_id: int) -> Dict[str, Dict[str, Any]]:
        """
        Get A/B test results for a campaign.
        
        Args:
            campaign_id: Campaign ID
            
        Returns:
            Dictionary with results for each variant
        """
        results = {}
        
        for variant in ['A', 'B']:
            variant_stats = self.session.query(
                func.count(CampaignMembership.id).label('total'),
                func.sum(func.cast(CampaignMembership.status == 'sent', func.Integer)).label('sent'),
                func.sum(func.cast(CampaignMembership.status == 'delivered', func.Integer)).label('delivered'),
                func.sum(func.cast(CampaignMembership.status == 'responded', func.Integer)).label('responded'),
                func.sum(func.cast(CampaignMembership.status == 'opted_out', func.Integer)).label('opted_out')
            ).filter(
                CampaignMembership.campaign_id == campaign_id,
                CampaignMembership.variant == variant
            ).first()
            
            if variant_stats and variant_stats.total:
                results[variant] = {
                    'total': variant_stats.total or 0,
                    'sent': variant_stats.sent or 0,
                    'delivered': variant_stats.delivered or 0,
                    'responded': variant_stats.responded or 0,
                    'opted_out': variant_stats.opted_out or 0,
                    'response_rate': ((variant_stats.responded or 0) / variant_stats.sent * 100) if variant_stats.sent else 0,
                    'opt_out_rate': ((variant_stats.opted_out or 0) / variant_stats.sent * 100) if variant_stats.sent else 0
                }
            else:
                results[variant] = {
                    'total': 0,
                    'sent': 0,
                    'delivered': 0,
                    'responded': 0,
                    'opted_out': 0,
                    'response_rate': 0,
                    'opt_out_rate': 0
                }
        
        return results
    
    def get_recent_campaigns(self, days: int = 30) -> List[Campaign]:
        """
        Get campaigns created in the last N days.
        
        Args:
            days: Number of days to look back
            
        Returns:
            List of recent campaigns
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        return self.session.query(Campaign).filter(
            Campaign.created_at >= cutoff_date
        ).order_by(desc(Campaign.created_at)).all()
    
    def get_campaign_timeline(self, campaign_id: int) -> List[Dict[str, Any]]:
        """
        Get timeline of campaign events.
        
        Args:
            campaign_id: Campaign ID
            
        Returns:
            List of timeline events
        """
        campaign = self.get_by_id(campaign_id)
        if not campaign:
            return []
        
        timeline = []
        
        # Campaign created
        timeline.append({
            'timestamp': campaign.created_at,
            'event': 'created',
            'description': f'Campaign "{campaign.name}" created'
        })
        
        # Campaign activated
        if campaign.status == 'active' and campaign.updated_at:
            timeline.append({
                'timestamp': campaign.updated_at,
                'event': 'activated',
                'description': 'Campaign activated'
            })
        
        # Get send events
        first_send = self.session.query(func.min(CampaignMembership.sent_at)).filter(
            CampaignMembership.campaign_id == campaign_id
        ).scalar()
        
        if first_send:
            timeline.append({
                'timestamp': first_send,
                'event': 'first_send',
                'description': 'First message sent'
            })
        
        # Get response events
        first_response = self.session.query(func.min(CampaignMembership.responded_at)).filter(
            CampaignMembership.campaign_id == campaign_id
        ).scalar()
        
        if first_response:
            timeline.append({
                'timestamp': first_response,
                'event': 'first_response',
                'description': 'First response received'
            })
        
        # Sort timeline by timestamp
        timeline.sort(key=lambda x: x['timestamp'])
        
        return timeline
    
    def clone_campaign(self, campaign_id: int, new_name: str) -> Campaign:
        """
        Clone an existing campaign.
        
        Args:
            campaign_id: ID of campaign to clone
            new_name: Name for the new campaign
            
        Returns:
            Cloned campaign
        """
        original = self.get_by_id(campaign_id)
        if not original:
            raise ValueError(f"Campaign {campaign_id} not found")
        
        # Create new campaign with same settings
        cloned = Campaign(
            name=new_name,
            campaign_type=original.campaign_type,
            audience_type=original.audience_type,
            channel=original.channel,
            template_a=original.template_a,
            template_b=original.template_b,
            daily_limit=original.daily_limit,
            business_hours_only=original.business_hours_only,
            ab_config=original.ab_config,
            status='draft',
            list_id=original.list_id
        )
        
        self.session.add(cloned)
        self.session.flush()
        
        return cloned
    
    def find_by_statuses(self, statuses: List[str]) -> List[Campaign]:
        """
        Find campaigns by list of statuses.
        
        Args:
            statuses: List of status values to match
            
        Returns:
            List of campaigns matching any of the statuses
        """
        return self.session.query(Campaign).filter(
            Campaign.status.in_(statuses)
        ).all()