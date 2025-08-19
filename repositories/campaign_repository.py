"""
CampaignRepository - Data access layer for Campaign entities
Isolates all database queries related to campaigns
"""

from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
from sqlalchemy import and_, or_, func, desc, asc
from sqlalchemy.orm import joinedload, selectinload, Query
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
        return self.find_by(status='running')
    
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
            variant_sent=variant,
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
                variant_sent=variant,
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
    
    # Dashboard-specific methods
    
    def get_active_campaigns_count(self) -> int:
        """
        Get count of active/running campaigns.
        
        Returns:
            Number of campaigns with status 'running'
        """
        return self.session.query(Campaign).filter_by(status='running').count()
    
    def get_recent_campaigns_with_limit(self, limit: int = 3) -> List[Campaign]:
        """
        Get recently created campaigns with limit.
        
        Args:
            limit: Maximum number of campaigns to return
            
        Returns:
            List of recent campaigns ordered by created_at desc
        """
        return self.session.query(Campaign).order_by(
            desc(Campaign.created_at)
        ).limit(limit).all()
    
    def calculate_average_campaign_response_rate(self) -> float:
        """
        Calculate average response rate across all campaigns with memberships.
        
        Returns:
            Average response rate as percentage (0-100)
        """
        # Get all campaigns with their memberships using eager loading
        campaigns = self.session.query(Campaign).options(
            selectinload(Campaign.memberships)
        ).all()
        
        if not campaigns:
            return 0
        
        response_rates = []
        
        for campaign in campaigns:
            # Calculate response rate for this campaign
            sent_statuses = ['sent', 'replied_positive', 'replied_negative']
            replied_statuses = ['replied_positive', 'replied_negative']
            
            sent_count = sum(1 for m in campaign.memberships if m.status in sent_statuses)
            
            if sent_count > 0:
                replied_count = sum(1 for m in campaign.memberships if m.status in replied_statuses)
                response_rate = (replied_count / sent_count) * 100
                response_rates.append(response_rate)
        
        if not response_rates:
            return 0
        
        return round(sum(response_rates) / len(response_rates), 1)
    
    def get_pending_campaign_queue_size(self) -> int:
        """
        Get count of pending campaign messages across all campaigns.
        
        Returns:
            Number of campaign memberships with status 'pending'
        """
        return self.session.query(CampaignMembership).filter_by(status='pending').count()
    
    # SMS Metrics Enhancement Methods
    
    def get_campaign_metrics_with_bounce_analysis(self, campaign_id: int) -> Dict[str, Any]:
        """
        Get comprehensive campaign metrics with detailed bounce analysis.
        
        Args:
            campaign_id: Campaign ID to analyze
            
        Returns:
            Dictionary with comprehensive metrics including bounce analysis
        """
        # Get basic stats
        stats = self.get_campaign_stats(campaign_id)
        
        # Get memberships for detailed analysis
        memberships = self.session.query(CampaignMembership).filter(
            CampaignMembership.campaign_id == campaign_id
        ).all()
        
        # Enhanced bounce analysis
        bounce_breakdown = {
            'hard': 0,
            'soft': 0,
            'carrier_rejection': 0,
            'capability': 0,
            'unknown': 0
        }
        
        # Analyze failed memberships
        failed_memberships = [m for m in memberships if m.status == 'failed']
        for membership in failed_memberships:
            if membership.membership_metadata and 'bounce_info' in membership.membership_metadata:
                bounce_type = membership.membership_metadata['bounce_info'].get('bounce_type', 'unknown')
                if bounce_type in bounce_breakdown:
                    bounce_breakdown[bounce_type] += 1
                else:
                    bounce_breakdown['unknown'] += 1
        
        # Calculate rates
        total_sent = stats.get('sent', 0)
        bounce_rate = (stats.get('failed', 0) / total_sent * 100) if total_sent > 0 else 0
        delivery_rate = (stats.get('delivered', 0) / total_sent * 100) if total_sent > 0 else 0
        
        # Status indicator based on bounce rate
        if bounce_rate > 5.0:
            status_indicator = 'critical'
        elif bounce_rate > 3.0:
            status_indicator = 'warning'
        else:
            status_indicator = 'healthy'
        
        return {
            'total_contacts': stats.get('total_recipients', 0),
            'sent': stats.get('sent', 0),
            'delivered': stats.get('delivered', 0),
            'bounced': stats.get('failed', 0),  # Map 'failed' to 'bounced'
            'replied': stats.get('responded', 0),
            'opted_out': stats.get('opted_out', 0),
            'bounce_rate': bounce_rate,
            'delivery_rate': delivery_rate,
            'response_rate': stats.get('response_rate', 0),
            'bounce_breakdown': bounce_breakdown,
            'status_indicator': status_indicator
        }
    
    def get_membership_status_distribution(self, campaign_id: int) -> Dict[str, Any]:
        """
        Get detailed status distribution for campaign memberships.
        
        Args:
            campaign_id: Campaign ID to analyze
            
        Returns:
            Dictionary with status counts and percentages
        """
        memberships = self.session.query(CampaignMembership.status, func.count(CampaignMembership.id)).filter(
            CampaignMembership.campaign_id == campaign_id
        ).group_by(CampaignMembership.status).all()
        
        status_counts = {status: count for status, count in memberships}
        total_members = sum(status_counts.values())
        
        status_percentages = {}
        if total_members > 0:
            for status, count in status_counts.items():
                status_percentages[status] = (count / total_members) * 100
        
        return {
            'status_counts': status_counts,
            'status_percentages': status_percentages,
            'total_members': total_members
        }
    
    def get_campaign_memberships(self, campaign_id: int) -> List[CampaignMembership]:
        """
        Get all memberships for a campaign.
        
        Args:
            campaign_id: Campaign ID
            
        Returns:
            List of campaign memberships
        """
        try:
            return self.session.query(CampaignMembership).filter_by(campaign_id=campaign_id).all()
        except Exception as e:
            logger.error(f"Error getting campaign memberships: {e}")
            return []
    
    def find_memberships_with_activity_ids(self, campaign_id: int) -> List[CampaignMembership]:
        """
        Find memberships that have sent activity IDs.
        
        Args:
            campaign_id: Campaign ID to filter by
            
        Returns:
            List of memberships with sent_activity_id populated
        """
        return self.session.query(CampaignMembership).filter(
            CampaignMembership.campaign_id == campaign_id,
            CampaignMembership.sent_activity_id.isnot(None)
        ).all()
    
    def get_campaign_bounce_analysis(self, campaign_id: int) -> Dict[str, Any]:
        """
        Get detailed bounce analysis for a campaign.
        
        Args:
            campaign_id: Campaign ID to analyze
            
        Returns:
            Dictionary with detailed bounce analysis
        """
        memberships = self.session.query(CampaignMembership).filter(
            CampaignMembership.campaign_id == campaign_id,
            CampaignMembership.status == 'failed'
        ).all()
        
        bounce_types = {'hard': 0, 'soft': 0, 'carrier_rejection': 0, 'capability': 0, 'unknown': 0}
        bounce_reasons = {}
        problematic_contacts = []
        
        for membership in memberships:
            if membership.membership_metadata and 'bounce_info' in membership.membership_metadata:
                bounce_info = membership.membership_metadata['bounce_info']
                bounce_type = bounce_info.get('bounce_type', 'unknown')
                bounce_reason = bounce_info.get('bounce_reason', 'unknown')
                
                if bounce_type in bounce_types:
                    bounce_types[bounce_type] += 1
                else:
                    bounce_types['unknown'] += 1
                
                bounce_reasons[bounce_reason] = bounce_reasons.get(bounce_reason, 0) + 1
                
                if bounce_type == 'hard':
                    problematic_contacts.append({
                        'contact_id': membership.contact_id,
                        'bounce_type': bounce_type,
                        'bounce_reason': bounce_reason
                    })
        
        recommendations = []
        if bounce_types['hard'] > 0:
            recommendations.append('Remove contacts with hard bounces from future campaigns')
        if bounce_types['carrier_rejection'] > bounce_types['hard']:
            recommendations.append('Review message content for compliance issues')
        
        return {
            'total_bounces': len(memberships),
            'bounce_types': bounce_types,
            'bounce_reasons': bounce_reasons,
            'problematic_contacts': problematic_contacts,
            'recommendations': recommendations
        }
    
    def update_membership_with_bounce_info(self, membership_id: int, bounce_info: Dict[str, Any]) -> Optional[CampaignMembership]:
        """
        Update membership with detailed bounce information.
        
        Args:
            membership_id: Membership ID to update
            bounce_info: Bounce information to store
            
        Returns:
            Updated CampaignMembership or None if not found
        """
        membership = self.session.query(CampaignMembership).get(membership_id)
        if not membership:
            return None
        
        # Initialize metadata if needed
        if not membership.membership_metadata:
            membership.membership_metadata = {}
        
        # Store bounce info
        membership.membership_metadata['bounce_info'] = bounce_info
        membership.status = 'failed'  # Ensure status reflects bounce
        
        self.session.flush()
        return membership
    
    def get_campaign_performance_over_time(self, campaign_id: int, days: int = 7) -> Dict[str, Any]:
        """
        Get campaign performance metrics over time.
        
        Args:
            campaign_id: Campaign ID to analyze
            days: Number of days to analyze
            
        Returns:
            Dictionary with time-series performance data
        """
        daily_stats = []
        
        for i in range(days):
            day = datetime.utcnow().date() - timedelta(days=days-1-i)
            
            # Get memberships sent on this day
            day_memberships = self.session.query(CampaignMembership).filter(
                CampaignMembership.campaign_id == campaign_id,
                func.date(CampaignMembership.sent_at) == day
            ).all()
            
            sent = len(day_memberships)
            delivered = sum(1 for m in day_memberships if m.status == 'delivered')
            bounced = sum(1 for m in day_memberships if m.status == 'failed')
            bounce_rate = (bounced / sent * 100) if sent > 0 else 0
            
            daily_stats.append({
                'date': day,
                'sent': sent,
                'delivered': delivered,
                'bounced': bounced,
                'bounce_rate': bounce_rate
            })
        
        # Calculate trends
        total_sent = sum(s['sent'] for s in daily_stats)
        total_bounced = sum(s['bounced'] for s in daily_stats)
        avg_bounce_rate = (total_bounced / total_sent * 100) if total_sent > 0 else 0
        
        return {
            'daily_stats': daily_stats,
            'trends': {
                'avg_bounce_rate': avg_bounce_rate,
                'total_sent': total_sent,
                'total_bounced': total_bounced
            },
            'summary': {
                'period_days': days,
                'performance': 'good' if avg_bounce_rate < 3.0 else 'poor'
            }
        }
    
    def find_campaigns_with_high_bounce_rates(self, bounce_threshold: float = 10.0, min_sent_count: int = 1) -> List[Dict[str, Any]]:
        """
        Find campaigns with high bounce rates.
        
        Args:
            bounce_threshold: Bounce rate percentage threshold
            min_sent_count: Minimum messages sent to be included
            
        Returns:
            List of campaigns with high bounce rates
        """
        campaigns = self.get_all()
        high_bounce_campaigns = []
        
        for campaign in campaigns:
            stats = self.get_campaign_stats(campaign.id)
            
            sent_count = stats.get('sent', 0)
            if sent_count < min_sent_count:
                continue
            
            bounce_rate = (stats.get('bounced', 0) / sent_count * 100)
            
            if bounce_rate >= bounce_threshold:
                high_bounce_campaigns.append({
                    'campaign': campaign,
                    'bounce_rate': bounce_rate,
                    'sent_count': sent_count,
                    'bounce_count': stats.get('bounced', 0)
                })
        
        return sorted(high_bounce_campaigns, key=lambda x: x['bounce_rate'], reverse=True)
    
    def get_membership_timeline(self, campaign_id: int, hours: int = 24) -> List[Dict[str, Any]]:
        """
        Get timeline of membership status changes.
        
        Args:
            campaign_id: Campaign ID to analyze
            hours: Number of hours to look back
            
        Returns:
            List of timeline events
        """
        since_time = datetime.utcnow() - timedelta(hours=hours)
        
        # Get memberships with recent activity
        memberships = self.session.query(CampaignMembership).filter(
            CampaignMembership.campaign_id == campaign_id,
            CampaignMembership.sent_at >= since_time
        ).order_by(CampaignMembership.sent_at.desc()).all()
        
        timeline = []
        for membership in memberships:
            if membership.sent_at:
                timeline.append({
                    'timestamp': membership.sent_at,
                    'status': 'sent',
                    'contact_id': membership.contact_id,
                    'event_type': 'sent'
                })
        
        return timeline
    
    def bulk_update_membership_statuses(self, membership_ids: List[int], status: str, metadata: Dict[str, Any] = None) -> int:
        """
        Bulk update membership statuses.
        
        Args:
            membership_ids: List of membership IDs to update
            status: New status to set
            metadata: Optional metadata to set
            
        Returns:
            Number of memberships updated
        """
        if not membership_ids:
            return 0
        
        memberships = self.session.query(CampaignMembership).filter(
            CampaignMembership.id.in_(membership_ids)
        ).all()
        
        for membership in memberships:
            membership.status = status
            if metadata:
                if not membership.membership_metadata:
                    membership.membership_metadata = {}
                membership.membership_metadata.update(metadata)
        
        self.session.flush()
        return len(memberships)
    
    def calculate_campaign_roi_metrics(self, campaign_id: int) -> Dict[str, Any]:
        """
        Calculate campaign ROI and effectiveness metrics.
        
        Args:
            campaign_id: Campaign ID to analyze
            
        Returns:
            Dictionary with ROI analysis
        """
        stats = self.get_campaign_stats(campaign_id)
        
        # Basic cost assumptions (can be made configurable)
        cost_per_message = 0.02  # $0.02 per SMS
        value_per_response = 10.0  # $10 per positive response
        
        sent_count = stats.get('sent', 0)
        responded_count = stats.get('responded', 0)
        
        total_cost = sent_count * cost_per_message
        total_value = responded_count * value_per_response
        roi_percentage = ((total_value - total_cost) / total_cost * 100) if total_cost > 0 else 0
        
        effectiveness_score = min(100, (responded_count / sent_count * 100 * 2)) if sent_count > 0 else 0
        
        return {
            'cost_per_message': cost_per_message,
            'cost_per_response': total_cost / responded_count if responded_count > 0 else 0,
            'response_value': value_per_response,
            'roi_percentage': roi_percentage,
            'effectiveness_score': effectiveness_score
        }