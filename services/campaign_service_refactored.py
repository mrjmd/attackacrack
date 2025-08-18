"""
CampaignService - Refactored with Repository Pattern
Business logic for text campaign system, now using CampaignRepository for data access
"""

import json
import random
import statistics
from datetime import datetime, time, timedelta
from typing import List, Dict, Optional, Tuple
from scipy import stats
from sqlalchemy.orm import Session

from repositories.campaign_repository import CampaignRepository
from repositories.contact_repository import ContactRepository
from repositories.contact_flag_repository import ContactFlagRepository
from repositories.base_repository import PaginationParams
from crm_database import Campaign, CampaignMembership, Contact, ContactFlag, Activity, db
import logging

logger = logging.getLogger(__name__)


class CampaignService:
    """Service for managing text campaigns with repository pattern"""
    
    def __init__(self, 
                 campaign_repository: Optional[CampaignRepository] = None,
                 contact_repository: Optional[ContactRepository] = None,
                 contact_flag_repository: Optional[ContactFlagRepository] = None,
                 openphone_service=None,
                 list_service=None,
                 session: Optional[Session] = None):
        """
        Initialize with injected dependencies and repositories.
        
        Args:
            campaign_repository: CampaignRepository for campaign data access
            contact_repository: ContactRepository for contact data access
            contact_flag_repository: ContactFlagRepository for flag management
            openphone_service: OpenPhoneService for SMS sending
            list_service: CampaignListService for list management
            session: Database session
        """
        self.session = session or db.session
        self.campaign_repository = campaign_repository or CampaignRepository(self.session, Campaign)
        self.contact_repository = contact_repository or ContactRepository(self.session, Contact)
        self.contact_flag_repository = contact_flag_repository or ContactFlagRepository(self.session, ContactFlag)
        self.openphone_service = openphone_service
        self.list_service = list_service
        
        # Business hours: weekdays 9am-6pm ET
        self.business_hours_start = time(9, 0)
        self.business_hours_end = time(18, 0)
        self.business_days = [0, 1, 2, 3, 4]  # Monday-Friday
    
    def create_campaign(self, 
                       name: str,
                       campaign_type: str = 'blast',
                       audience_type: str = 'mixed',
                       channel: str = 'sms',
                       template_a: str = '',
                       template_b: str = None,
                       daily_limit: int = 125,
                       business_hours_only: bool = True) -> Campaign:
        """
        Create a new marketing campaign.
        
        Args:
            name: Campaign name
            campaign_type: Type of campaign
            audience_type: Audience type
            channel: Communication channel
            template_a: Primary message template
            template_b: Optional B variant for A/B testing
            daily_limit: Max messages per day
            business_hours_only: Restrict to business hours
            
        Returns:
            Created Campaign
        """
        # Validate campaign type
        if campaign_type not in ['blast', 'automated', 'ab_test']:
            raise ValueError("Campaign type must be 'blast', 'automated', or 'ab_test'")
        
        # Validate audience type
        if audience_type not in ['cold', 'customer', 'mixed']:
            raise ValueError("Audience type must be 'cold', 'customer', or 'mixed'")
        
        # Validate channel
        if channel not in ['sms', 'email']:
            raise ValueError("Channel must be 'sms' or 'email'")
        
        # Email campaigns not yet supported
        if channel == 'email':
            raise ValueError("Email campaigns coming soon with SmartLead integration")
        
        # For A/B tests, require template_b
        if campaign_type == 'ab_test' and not template_b:
            raise ValueError("A/B test campaigns require both template_a and template_b")
        
        # Create A/B config for ab_test campaigns
        ab_config = None
        if campaign_type == 'ab_test':
            ab_config = {
                'min_sample_size': 100,
                'significance_threshold': 0.95,
                'current_split': 50,  # 50/50 split initially
                'winner_declared': False,
                'winner_variant': None
            }
        
        campaign = self.campaign_repository.create(
            name=name,
            campaign_type=campaign_type,
            audience_type=audience_type,
            channel=channel,
            template_a=template_a,
            template_b=template_b,
            daily_limit=daily_limit,
            business_hours_only=business_hours_only,
            ab_config=ab_config,
            status='draft'
        )
        
        self.campaign_repository.commit()
        logger.info(f"Created campaign: {campaign.id} - {name}")
        
        return campaign
    
    def add_recipients_from_list(self, campaign_id: int, list_id: int) -> int:
        """
        Add recipients from a campaign list.
        
        Args:
            campaign_id: Campaign ID
            list_id: List ID
            
        Returns:
            Number of recipients added
        """
        if not self.list_service:
            raise ValueError("CampaignListService not provided")
        
        # Get all active contacts from the list
        contacts = self.list_service.get_list_contacts(list_id)
        contact_ids = [c.id for c in contacts]
        
        # Add contacts to campaign
        added = self.campaign_repository.add_members_bulk(campaign_id, contact_ids)
        
        # Update campaign list reference
        campaign = self.campaign_repository.get_by_id(campaign_id)
        if campaign:
            campaign.list_id = list_id
            self.campaign_repository.commit()
        
        logger.info(f"Added {added} recipients to campaign {campaign_id} from list {list_id}")
        return added
    
    def add_recipients(self, campaign_id: int, contact_filters: Dict) -> int:
        """
        Add recipients to campaign based on filters.
        
        Args:
            campaign_id: Campaign ID
            contact_filters: Dictionary of filters
            
        Returns:
            Number of recipients added
        """
        campaign = self.campaign_repository.get_by_id(campaign_id)
        if not campaign:
            raise ValueError(f"Campaign {campaign_id} not found")
        
        # Get contacts based on filters
        contacts = self._get_filtered_contacts(contact_filters)
        contact_ids = [c.id for c in contacts]
        
        # Add to campaign
        added = self.campaign_repository.add_members_bulk(campaign_id, contact_ids)
        self.campaign_repository.commit()
        
        logger.info(f"Added {added} recipients to campaign {campaign_id}")
        return added
    
    def get_eligible_contacts(self, filters: Dict) -> List[Contact]:
        """Public interface for getting eligible contacts with filters"""
        return self._get_filtered_contacts(filters)
    
    def _get_filtered_contacts(self, filters: Dict) -> List[Contact]:
        """
        Get contacts based on filters.
        
        Args:
            filters: Dictionary of filters
            
        Returns:
            List of filtered contacts
        """
        # Start with all contacts or use repository filtering
        if filters.get('has_name_only'):
            # Get all contacts and filter in memory for complex logic
            contacts = self.contact_repository.get_all()
            # Only contacts with real names (not phone numbers)
            contacts = [c for c in contacts if not (c.first_name and c.first_name.startswith('+1'))]
        else:
            contacts = self.contact_repository.get_all()
        
        if filters.get('has_email'):
            contacts = [c for c in contacts if c.email]
        
        if filters.get('exclude_office_numbers'):
            # Exclude contacts flagged as office numbers
            office_ids = self.contact_flag_repository.get_contact_ids_with_flag_type('office_number')
            contacts = [c for c in contacts if c.id not in office_ids]
        
        if filters.get('exclude_opted_out'):
            opted_out_ids = self.contact_flag_repository.get_contact_ids_with_flag_type('opted_out')
            contacts = [c for c in contacts if c.id not in opted_out_ids]
        
        if filters.get('exclude_do_not_contact'):
            # Exclude contacts flagged as do not contact
            do_not_contact_ids = self.contact_flag_repository.get_contact_ids_with_flag_type('do_not_contact')
            contacts = [c for c in contacts if c.id not in do_not_contact_ids]
        
        if filters.get('exclude_recently_contacted'):
            # Exclude contacts that were recently texted
            recently_contacted_ids = self.contact_flag_repository.get_contact_ids_with_flag_type('recently_texted')
            contacts = [c for c in contacts if c.id not in recently_contacted_ids]
        
        if filters.get('exclude_current_campaign'):
            # Exclude contacts already in any active campaign
            active_campaigns = self.campaign_repository.get_active_campaigns()
            for active_campaign in active_campaigns:
                members = self.campaign_repository.get_campaign_members(active_campaign.id)
                member_ids = {m.contact_id for m in members.items}
                contacts = [c for c in contacts if c.id not in member_ids]
        
        return contacts
    
    def get_campaign_stats(self, campaign_id: int) -> Dict:
        """
        Get campaign statistics.
        
        Args:
            campaign_id: Campaign ID
            
        Returns:
            Dictionary of statistics
        """
        return self.campaign_repository.get_campaign_stats(campaign_id)
    
    def get_campaign_members(self, campaign_id: int, status: Optional[str] = None, 
                            page: int = 1, per_page: int = 50) -> Dict:
        """
        Get campaign members with pagination.
        
        Args:
            campaign_id: Campaign ID
            status: Optional status filter
            page: Page number
            per_page: Items per page
            
        Returns:
            Paginated members with metadata
        """
        pagination = PaginationParams(page=page, per_page=per_page)
        result = self.campaign_repository.get_campaign_members(
            campaign_id, status, pagination
        )
        
        return {
            'members': result.items,
            'total': result.total,
            'page': result.page,
            'per_page': result.per_page,
            'total_pages': result.pages,
            'has_prev': result.has_prev,
            'has_next': result.has_next
        }
    
    def update_member_status(self, campaign_id: int, contact_id: int, 
                           status: str, **kwargs) -> bool:
        """
        Update campaign member status.
        
        Args:
            campaign_id: Campaign ID
            contact_id: Contact ID
            status: New status
            **kwargs: Additional fields
            
        Returns:
            True if updated
        """
        success = self.campaign_repository.update_member_status(
            campaign_id, contact_id, status, **kwargs
        )
        
        if success:
            self.campaign_repository.commit()
            logger.info(f"Updated member status: campaign={campaign_id}, contact={contact_id}, status={status}")
        
        return success
    
    def get_campaigns_needing_send(self) -> List[Campaign]:
        """
        Get campaigns that need messages sent.
        
        Returns:
            List of campaigns with pending messages
        """
        return self.campaign_repository.get_campaigns_needing_send()
    
    def can_send_today(self, campaign_id: int) -> Tuple[bool, int]:
        """
        Check if campaign can send more messages today.
        
        Args:
            campaign_id: Campaign ID
            
        Returns:
            Tuple of (can_send, remaining_quota)
        """
        campaign = self.campaign_repository.get_by_id(campaign_id)
        if not campaign:
            return False, 0
        
        sent_today = self.campaign_repository.get_today_send_count(campaign_id)
        remaining = campaign.daily_limit - sent_today
        
        return remaining > 0, remaining
    
    def is_business_hours(self) -> bool:
        """
        Check if current time is within business hours.
        
        Returns:
            True if within business hours
        """
        now = datetime.now()
        current_time = now.time()
        current_day = now.weekday()
        
        # Check if it's a business day
        if current_day not in self.business_days:
            return False
        
        # Check if within business hours
        return self.business_hours_start <= current_time <= self.business_hours_end
    
    def assign_ab_variant(self, campaign_id: int, contact_id: int) -> str:
        """
        Assign A/B test variant to a contact.
        
        Args:
            campaign_id: Campaign ID
            contact_id: Contact ID
            
        Returns:
            Variant assignment ('A' or 'B')
        """
        campaign = self.campaign_repository.get_by_id(campaign_id)
        if not campaign or campaign.campaign_type != 'ab_test':
            return 'A'  # Default to A for non-A/B tests
        
        # Get current split from config
        ab_config = campaign.ab_config or {}
        current_split = ab_config.get('current_split', 50)
        
        # Random assignment based on split
        variant = 'A' if random.randint(1, 100) <= current_split else 'B'
        
        # Update member with variant
        member = self.campaign_repository.get_member_by_contact(campaign_id, contact_id)
        if member:
            member.variant = variant
            self.campaign_repository.commit()
        
        return variant
    
    def analyze_ab_test(self, campaign_id: int) -> Dict:
        """
        Analyze A/B test results.
        
        Args:
            campaign_id: Campaign ID
            
        Returns:
            Analysis results with winner if determined
        """
        campaign = self.campaign_repository.get_by_id(campaign_id)
        if not campaign or campaign.campaign_type != 'ab_test':
            return {'error': 'Not an A/B test campaign'}
        
        # Get results for each variant
        results = self.campaign_repository.get_ab_test_results(campaign_id)
        
        # Need minimum sample size for both variants
        ab_config = campaign.ab_config or {}
        min_sample = ab_config.get('min_sample_size', 100)
        
        if results['A']['sent'] < min_sample or results['B']['sent'] < min_sample:
            return {
                'status': 'insufficient_data',
                'message': f'Need at least {min_sample} sends per variant',
                'results': results
            }
        
        # Perform statistical test on response rates
        # Using chi-square test for independence
        a_responses = results['A']['responded']
        b_responses = results['B']['responded']
        a_non_responses = results['A']['sent'] - a_responses
        b_non_responses = results['B']['sent'] - b_responses
        
        # Chi-square test
        observed = [[a_responses, a_non_responses], [b_responses, b_non_responses]]
        chi2, p_value, _, _ = stats.chi2_contingency(observed)
        
        # Determine if there's a significant difference
        significance_threshold = ab_config.get('significance_threshold', 0.95)
        is_significant = (1 - p_value) >= significance_threshold
        
        winner = None
        if is_significant:
            # Determine winner based on response rate
            a_rate = results['A']['response_rate']
            b_rate = results['B']['response_rate']
            winner = 'A' if a_rate > b_rate else 'B'
            
            # Update campaign config with winner
            ab_config['winner_declared'] = True
            ab_config['winner_variant'] = winner
            campaign.ab_config = ab_config
            self.campaign_repository.commit()
        
        return {
            'status': 'complete' if is_significant else 'ongoing',
            'winner': winner,
            'confidence': (1 - p_value) * 100,
            'p_value': p_value,
            'results': results
        }
    
    def activate_campaign(self, campaign_id: int) -> bool:
        """
        Activate a campaign for sending.
        
        Args:
            campaign_id: Campaign ID
            
        Returns:
            True if activated
        """
        campaign = self.campaign_repository.get_by_id(campaign_id)
        if not campaign:
            return False
        
        if campaign.status == 'draft':
            campaign.status = 'active'
            self.campaign_repository.commit()
            logger.info(f"Activated campaign {campaign_id}")
            return True
        
        return False
    
    def pause_campaign(self, campaign_id: int) -> bool:
        """
        Pause an active campaign.
        
        Args:
            campaign_id: Campaign ID
            
        Returns:
            True if paused
        """
        campaign = self.campaign_repository.get_by_id(campaign_id)
        if not campaign:
            return False
        
        if campaign.status == 'active':
            campaign.status = 'paused'
            self.campaign_repository.commit()
            logger.info(f"Paused campaign {campaign_id}")
            return True
        
        return False
    
    def complete_campaign(self, campaign_id: int) -> bool:
        """
        Mark campaign as completed.
        
        Args:
            campaign_id: Campaign ID
            
        Returns:
            True if completed
        """
        campaign = self.campaign_repository.get_by_id(campaign_id)
        if not campaign:
            return False
        
        campaign.status = 'completed'
        self.campaign_repository.commit()
        logger.info(f"Completed campaign {campaign_id}")
        return True
    
    def clone_campaign(self, campaign_id: int, new_name: str) -> Campaign:
        """
        Clone an existing campaign.
        
        Args:
            campaign_id: ID of campaign to clone
            new_name: Name for new campaign
            
        Returns:
            Cloned campaign
        """
        cloned = self.campaign_repository.clone_campaign(campaign_id, new_name)
        self.campaign_repository.commit()
        logger.info(f"Cloned campaign {campaign_id} as {cloned.id}")
        return cloned
    
    def get_campaign_timeline(self, campaign_id: int) -> List[Dict]:
        """
        Get timeline of campaign events.
        
        Args:
            campaign_id: Campaign ID
            
        Returns:
            List of timeline events
        """
        return self.campaign_repository.get_campaign_timeline(campaign_id)
    
    def flag_contacted_members(self, campaign_id: int, contact_ids: List[int]) -> None:
        """
        Flag campaign members as recently contacted.
        
        Args:
            campaign_id: Campaign ID
            contact_ids: List of contact IDs that were contacted
        """
        campaign = self.campaign_repository.get_by_id(campaign_id)
        if not campaign:
            return
        
        # Create recently_texted flags for contacted members
        self.contact_flag_repository.bulk_create_flags(
            contact_ids=contact_ids,
            flag_type='recently_texted',
            flag_reason=f'Contacted via campaign: {campaign.name}',
            applies_to='sms'
        )
        
        logger.info(f"Flagged {len(contact_ids)} contacts as recently contacted from campaign {campaign_id}")
    
    def cleanup_expired_flags(self) -> int:
        """
        Clean up expired contact flags.
        
        Returns:
            Number of flags cleaned up
        """
        count = self.contact_flag_repository.cleanup_expired_flags()
        self.contact_flag_repository.commit()
        logger.info(f"Cleaned up {count} expired contact flags")
        return count