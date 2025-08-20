"""
CampaignService - Refactored with Repository Pattern
Business logic for text campaign system, now using CampaignRepository for data access
"""

import json
import random
import statistics
from datetime import datetime, time, timedelta
from typing import List, Dict, Optional, Tuple, Any
from scipy import stats
# Session import removed - using repositories only

from repositories.campaign_repository import CampaignRepository
from repositories.contact_repository import ContactRepository
from repositories.contact_flag_repository import ContactFlagRepository
from repositories.activity_repository import ActivityRepository
from repositories.base_repository import PaginationParams
from services.common.result import Result
# Model imports removed - using repositories only
import logging

logger = logging.getLogger(__name__)


class CampaignService:
    """Service for managing text campaigns with repository pattern"""
    
    def __init__(self, 
                 campaign_repository: Optional[CampaignRepository] = None,
                 contact_repository: Optional[ContactRepository] = None,
                 contact_flag_repository: Optional[ContactFlagRepository] = None,
                 activity_repository: Optional[ActivityRepository] = None,
                 openphone_service=None,
                 list_service=None,
):
        """
        Initialize with injected dependencies and repositories.
        
        Args:
            campaign_repository: CampaignRepository for campaign data access
            contact_repository: ContactRepository for contact data access
            contact_flag_repository: ContactFlagRepository for flag management
            activity_repository: ActivityRepository for activity tracking
            openphone_service: OpenPhoneService for SMS sending
            list_service: CampaignListService for list management
        """
        # Repositories must be injected - no fallback to direct instantiation
        self.campaign_repository = campaign_repository
        self.contact_repository = contact_repository
        self.contact_flag_repository = contact_flag_repository
        self.activity_repository = activity_repository
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
                       business_hours_only: bool = True) -> 'Result[Dict]':
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
            Result[Campaign]: Success with created campaign or failure with error
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
        
        try:
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
            
            # Handle both dict and object returns from repository
            campaign_id = campaign['id'] if isinstance(campaign, dict) else campaign.id
            logger.info(f"Created campaign: {campaign_id} - {name}")
            
            return Result.success(campaign)
        except Exception as e:
            logger.error(f"Failed to create campaign: {str(e)}")
            return Result.failure(f"Failed to create campaign: {str(e)}", code="CREATE_ERROR")
    
    def add_recipients_from_list(self, campaign_id: int, list_id: int) -> 'Result[int]':
        """
        Add recipients from a campaign list.
        
        Args:
            campaign_id: Campaign ID
            list_id: List ID
            
        Returns:
            Result[int]: Success with number of recipients added or failure with error
        """
        try:
            if not self.list_service:
                return Result.failure("CampaignListService not provided")
            
            # Get all active contacts from the list
            contacts_result = self.list_service.get_list_contacts(list_id)
            if contacts_result.is_failure:
                return Result.failure(f"Failed to get list contacts: {contacts_result.error}")
            
            contacts = contacts_result.data
            contact_ids = [c.get('id') if isinstance(c, dict) else c.id for c in contacts]
            
            # Add contacts to campaign
            added = self.campaign_repository.add_members_bulk(campaign_id, contact_ids)
            
            # Update campaign list reference
            campaign = self.campaign_repository.get_by_id(campaign_id)
            if campaign:
                campaign.list_id = list_id
                self.campaign_repository.commit()
            
            logger.info(f"Added {added} recipients to campaign {campaign_id} from list {list_id}")
            return Result.success(added)
            
        except Exception as e:
            logger.error(f"Failed to add recipients from list {list_id} to campaign {campaign_id}: {e}")
            return Result.failure(f"Failed to add recipients from list: {str(e)}")
    
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
        contact_ids = [c.id if hasattr(c, 'id') else c.get('id') for c in contacts]
        
        # Add to campaign
        added = self.campaign_repository.add_members_bulk(campaign_id, contact_ids)
        self.campaign_repository.commit()
        
        logger.info(f"Added {added} recipients to campaign {campaign_id}")
        return added
    
    def get_eligible_contacts(self, filters: Dict) -> List[Dict[str, Any]]:
        """Public interface for getting eligible contacts with filters"""
        return self._get_filtered_contacts(filters)
    
    def _get_filtered_contacts(self, filters: Dict) -> List[Dict[str, Any]]:
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
            contacts = [c for c in contacts if not (hasattr(c, 'first_name') and c.first_name and c.first_name.startswith('+1'))]
        else:
            contacts = self.contact_repository.get_all()
        
        if filters.get('has_email'):
            contacts = [c for c in contacts if hasattr(c, 'email') and c.email]
        
        if filters.get('exclude_office_numbers'):
            # Exclude contacts flagged as office numbers
            office_ids = self.contact_flag_repository.get_contact_ids_with_flag_type('office_number')
            contacts = [c for c in contacts if hasattr(c, 'id') and c.id not in office_ids]
        
        if filters.get('exclude_opted_out'):
            opted_out_ids = self.contact_flag_repository.get_contact_ids_with_flag_type('opted_out')
            contacts = [c for c in contacts if hasattr(c, 'id') and c.id not in opted_out_ids]
        
        if filters.get('exclude_do_not_contact'):
            # Exclude contacts flagged as do not contact
            do_not_contact_ids = self.contact_flag_repository.get_contact_ids_with_flag_type('do_not_contact')
            contacts = [c for c in contacts if hasattr(c, 'id') and c.id not in do_not_contact_ids]
        
        if filters.get('exclude_recently_contacted'):
            # Exclude contacts that were recently texted
            recently_contacted_ids = self.contact_flag_repository.get_contact_ids_with_flag_type('recently_texted')
            contacts = [c for c in contacts if hasattr(c, 'id') and c.id not in recently_contacted_ids]
        
        if filters.get('exclude_current_campaign'):
            # Exclude contacts already in any active campaign
            active_campaigns = self.campaign_repository.get_active_campaigns()
            for active_campaign in active_campaigns:
                members = self.campaign_repository.get_campaign_members(active_campaign.id)
                member_ids = {m.contact_id for m in members.items}
                contacts = [c for c in contacts if hasattr(c, 'id') and c.id not in member_ids]
        
        return contacts
    
    def get_by_id(self, campaign_id: int):
        """
        Get campaign by ID.
        
        Args:
            campaign_id: Campaign ID
            
        Returns:
            Campaign object or None if not found
        """
        return self.campaign_repository.get_by_id(campaign_id)
    
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
    
    def get_campaigns_needing_send(self) -> List[Dict[str, Any]]:
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
    
    def start_campaign(self, campaign_id: int) -> bool:
        """
        Start a campaign (alias for activate_campaign with running status).
        
        Args:
            campaign_id: Campaign ID
            
        Returns:
            True if started
        """
        return self.activate_campaign(campaign_id)
    
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
            campaign.status = 'running'
            self.campaign_repository.commit()
            logger.info(f"Started campaign {campaign_id}")
            return True
        
        return False
    
    def pause_campaign(self, campaign_id: int) -> bool:
        """
        Pause a running campaign.
        
        Args:
            campaign_id: Campaign ID
            
        Returns:
            True if paused
        """
        campaign = self.campaign_repository.get_by_id(campaign_id)
        if not campaign:
            return False
        
        if campaign.status == 'running':
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
    
    def clone_campaign(self, campaign_id: int, new_name: str) -> Dict[str, Any]:
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
        logger.info(f"Cloned campaign {campaign_id} as {cloned.id if hasattr(cloned, 'id') else cloned.get('id')}")
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
    
    def get_campaign_analytics(self, campaign_id: int) -> Dict[str, Any]:
        """
        Get analytics data for a specific campaign.
        
        Args:
            campaign_id: Campaign ID
            
        Returns:
            Dictionary with analytics data
        """
        try:
            # Get campaign memberships for analytics (more accurate than activities)
            memberships = self.campaign_repository.get_campaign_memberships(campaign_id)
            
            total_recipients = len(memberships)
            sent_count = len([m for m in memberships if m.status == 'sent'])
            # Count replies by checking for reply_activity_id
            response_count = len([m for m in memberships if m.reply_activity_id is not None])
            response_rate = (response_count / sent_count) if sent_count > 0 else 0
            
            return {
                'sent_count': sent_count,
                'response_count': response_count,
                'response_rate': round(response_rate, 2),
                'total_recipients': total_recipients,
                'sends_today': 0,  # TODO: Calculate actual sends today
                'daily_limit': 125,  # Default OpenPhone limit
                'ab_test': None  # TODO: Add A/B test analytics if needed
            }
        except Exception as e:
            logger.error(f"Error calculating analytics for campaign {campaign_id}: {e}")
            return {
                'sent_count': 0,
                'response_count': 0,
                'response_rate': 0,
                'total_recipients': 0,
                'sends_today': 0,
                'daily_limit': 125,
                'ab_test': None
            }
    
    def get_recent_sends(self, campaign_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get recent sends for a campaign.
        
        Args:
            campaign_id: Campaign ID
            limit: Maximum number of sends to return
            
        Returns:
            List of recent send information
        """
        try:
            # Get recent campaign memberships that have been sent
            memberships = self.campaign_repository.get_campaign_memberships(campaign_id)
            recent_sent = [m for m in memberships if m.status == 'sent'][:limit]
            
            # Convert to dict format for template with contact data
            sends = []
            for membership in recent_sent:
                # Get the contact information
                contact = None
                if self.contact_repository:
                    contact = self.contact_repository.get_by_id(membership.contact_id)
                
                sends.append({
                    'contact_id': membership.contact_id,
                    'contact': contact,  # Full contact object for template
                    'sent_at': membership.sent_at,
                    'status': membership.status,
                    'variant_sent': getattr(membership, 'variant_sent', 'A')
                })
            
            return sends
        except Exception as e:
            logger.error(f"Error getting recent sends for campaign {campaign_id}: {e}")
            return []
    
    def get_all_campaigns_with_analytics(self) -> List[Dict[str, Any]]:
        """
        Get all campaigns with their analytics data.
        
        Returns:
            List of campaigns with analytics information
        """
        campaigns = self.campaign_repository.get_all()
        campaign_data = []
        
        for campaign in campaigns:
            try:
                analytics = self.get_campaign_analytics(campaign.id)
                # Structure expected by template: {"campaign": {...}, "analytics": {...}}
                campaign_item = {
                    'campaign': {
                        'id': campaign.id,
                        'name': campaign.name,
                        'status': campaign.status,
                        'campaign_type': campaign.campaign_type,
                        'audience_type': campaign.audience_type,
                        'created_at': campaign.created_at
                    },
                    'analytics': {
                        'sent_count': analytics.get('sent_count', 0),
                        'response_count': analytics.get('response_count', 0),
                        'response_rate': analytics.get('response_rate', 0),
                        'total_recipients': analytics.get('total_recipients', 0),
                        'sends_today': analytics.get('sends_today', 0),
                        'daily_limit': analytics.get('daily_limit', 125),
                        'ab_test': analytics.get('ab_test', None)
                    }
                }
                campaign_data.append(campaign_item)
            except Exception as e:
                logger.error(f"Error getting analytics for campaign {campaign.id}: {e}")
                # Add campaign without analytics on error
                campaign_item = {
                    'campaign': {
                        'id': campaign.id,
                        'name': campaign.name,
                        'status': campaign.status,
                        'campaign_type': campaign.campaign_type,
                        'audience_type': campaign.audience_type,
                        'created_at': campaign.created_at
                    },
                    'analytics': {
                        'sent_count': 0,
                        'response_count': 0,
                        'response_rate': 0,
                        'total_recipients': 0,
                        'sends_today': 0,
                        'daily_limit': 125,
                        'ab_test': None
                    }
                }
                campaign_data.append(campaign_item)
        
        return campaign_data
    
    def get_audience_stats(self) -> Dict[str, int]:
        """
        Get statistics about the available audience for campaigns.
        
        Returns:
            Dictionary with audience statistics
        """
        if not self.contact_repository:
            return {
                'total_contacts': 0,
                'with_phone': 0,
                'never_contacted': 0,
                'cold_contacts': 0,
                'customers': 0
            }
        
        try:
            # Get total contacts
            total_contacts = self.contact_repository.count()
            
            # Get contacts with phone numbers
            with_phone = self.contact_repository.count_with_phone()
            
            # TODO: Implement these repository methods
            # Get never contacted (no messages)
            # never_contacted = self.contact_repository.count_never_contacted()
            never_contacted = 0  # Placeholder until method is implemented
            
            # Get cold vs customers
            # cold_contacts = self.contact_repository.count_by_type('cold')
            # customers = self.contact_repository.count_by_type('customer')
            cold_contacts = 0  # Placeholder until method is implemented
            customers = 0  # Placeholder until method is implemented
            
            return {
                'total_contacts': total_contacts,
                'with_phone': with_phone,
                'never_contacted': never_contacted,
                'cold_contacts': cold_contacts,
                'customers': customers
            }
        except Exception as e:
            logger.error(f"Error getting audience stats: {e}")
            return {
                'total_contacts': 0,
                'with_phone': 0,
                'never_contacted': 0,
                'cold_contacts': 0,
                'customers': 0
            }
    
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
    
    def process_campaign_queue(self) -> 'Result[Dict[str, Any]]':
        """
        Process pending campaign messages and send them via OpenPhone.
        
        Returns:
            Dict with statistics: messages_sent, messages_skipped, errors, daily_limits_reached
        """
        logger.info("Processing campaign queue")
        
        stats = {
            'messages_sent': 0,
            'messages_skipped': 0,
            'errors': [],
            'daily_limits_reached': []
        }
        
        try:
            # Find active campaigns that need to send messages
            active_campaigns = self.campaign_repository.get_active_campaigns()
            
            for campaign in active_campaigns:
                campaign_id = campaign.id
                campaign_name = campaign.name
                
                # Check if campaign can send today (daily limit)
                can_send, remaining = self.can_send_today(campaign_id)
                if not can_send:
                    logger.info(f"Campaign {campaign_name} has reached daily limit")
                    stats['daily_limits_reached'].append(campaign_name)
                    continue
                
                # Check business hours if required
                if campaign.business_hours_only and not self.is_business_hours():
                    logger.info(f"Skipping campaign {campaign_name} - outside business hours")
                    continue
                
                # Get pending members for this campaign
                pending_members = self.campaign_repository.get_pending_members(campaign_id, limit=remaining)
                
                logger.info(f"Processing {len(pending_members)} pending messages for campaign {campaign_name}")
                
                for member in pending_members:
                    try:
                        # Get contact info (should be already loaded via joinedload)
                        contact = member.contact if hasattr(member, 'contact') else self.contact_repository.get_by_id(member.contact_id)
                        if not contact or not contact.phone:
                            logger.warning(f"Skipping member {member.id} - no phone number")
                            self.campaign_repository.update_member_status(
                                campaign_id, member.contact_id, 'skipped'
                            )
                            stats['messages_skipped'] += 1
                            continue
                        
                        # Check for opt-out flags
                        if self.contact_flag_repository.check_contact_has_flag_type(contact.id, 'opted_out'):
                            logger.info(f"Skipping contact {contact.phone} - opted out")
                            self.campaign_repository.update_member_status(
                                campaign_id, member.contact_id, 'skipped'
                            )
                            stats['messages_skipped'] += 1
                            continue
                        
                        # Assign A/B variant if needed
                        variant = member.variant_sent
                        if not variant and campaign.campaign_type == 'ab_test':
                            variant = self.assign_ab_variant(campaign_id, member.contact_id)
                        
                        # Get message template
                        if variant == 'B' and campaign.template_b:
                            template = campaign.template_b
                        else:
                            template = campaign.template_a
                            variant = 'A'  # Default to A if not A/B test
                        
                        # Personalize message
                        message = self._personalize_message(template, contact)
                        
                        # Send message via OpenPhone
                        if self.openphone_service:
                            send_result = self.openphone_service.send_message(contact.phone, message)
                            
                            if send_result.get('success'):
                                # Update membership status
                                self.campaign_repository.update_member_status(
                                    campaign_id, member.contact_id, 'sent'
                                )
                                
                                # Update variant for A/B test
                                if variant:
                                    membership = self.campaign_repository.get_member_by_contact(campaign_id, member.contact_id)
                                    if membership:
                                        membership.variant_sent = variant
                                        self.campaign_repository.session.flush()
                                
                                # TODO: Create activity record (Activity model needs campaign_id field)
                                # For now, skip activity creation to focus on message sending
                                
                                stats['messages_sent'] += 1
                                logger.info(f"Sent message to {contact.phone}")
                                
                            else:
                                # Handle send failure
                                error_msg = send_result.get('error', 'Unknown error')
                                self.campaign_repository.update_member_status(
                                    campaign_id, member.contact_id, 'failed'
                                )
                                stats['messages_skipped'] += 1
                                stats['errors'].append(f"Failed to send to {contact.phone}: {error_msg}")
                                logger.error(f"Failed to send message to {contact.phone}: {error_msg}")
                        else:
                            # No OpenPhone service configured
                            logger.warning("No OpenPhone service configured - cannot send messages")
                            stats['messages_skipped'] += 1
                            
                    except Exception as e:
                        logger.error(f"Error processing member {member.id}: {e}")
                        stats['errors'].append(f"Error processing member {member.id}: {str(e)}")
                        stats['messages_skipped'] += 1
                        
                        # Mark as failed
                        try:
                            self.campaign_repository.update_member_status(
                                campaign_id, member.contact_id, 'failed'
                            )
                        except Exception as update_error:
                            logger.error(f"Failed to update member status: {update_error}")
            
            # Commit all changes
            self.campaign_repository.commit()
            
            logger.info(f"Campaign queue processing complete. Sent: {stats['messages_sent']}, Skipped: {stats['messages_skipped']}")
            
        except Exception as e:
            logger.error(f"Error processing campaign queue: {e}")
            stats['errors'].append(f"Queue processing error: {str(e)}")
            
        from services.common.result import Result
        return Result.success(stats)
    
    def handle_opt_out(self, phone: str, message: str) -> bool:
        """
        Handle opt-out request from incoming message.
        
        Args:
            phone: Phone number of the contact
            message: Message content to check for opt-out keywords
            
        Returns:
            True if opt-out was processed, False if not an opt-out
        """
        # Opt-out keywords (case-insensitive substring match)
        opt_out_keywords = [
            'stop', 'unsubscribe', 'opt out', 'opt-out', 'remove me', 
            'cancel', 'quit', 'end', 'leave me alone'
        ]
        
        message_lower = message.lower().strip()
        
        # Check if message contains any opt-out keywords
        is_opt_out = any(keyword in message_lower for keyword in opt_out_keywords)
        
        if is_opt_out:
            logger.info(f"Processing opt-out request from {phone}: {message}")
            
            try:
                # Find contact by phone
                contact = self.contact_repository.find_by_phone(phone)
                
                if contact:
                    # Create opt-out flag
                    self.contact_flag_repository.create_flag_for_contact(
                        contact_id=contact.id,
                        flag_type='opted_out',
                        flag_reason=f'STOP received: {message[:50]}',
                        applies_to='sms'
                    )
                    self.contact_flag_repository.commit()
                    
                    logger.info(f"Created opt-out flag for contact {contact.id} ({phone})")
                    return True
                else:
                    logger.warning(f"Could not find contact with phone {phone} for opt-out")
                    return False
                    
            except Exception as e:
                logger.error(f"Error processing opt-out for {phone}: {e}")
                return False
        
        return False
    
    def _personalize_message(self, template: str, contact) -> str:
        """
        Personalize message template with contact data.
        
        Args:
            template: Message template with placeholders
            contact: Contact object with data
            
        Returns:
            Personalized message
        """
        # Handle None/empty templates
        if not template:
            return ""
            
        try:
            # Replace common placeholders
            message = template
            
            # Helper function to check if a name is actually a phone number
            def is_phone_number(name):
                return name and (name.startswith('+1') or name.startswith('('))
            
            if hasattr(contact, 'first_name') and contact.first_name:
                # Don't use phone numbers as names in personalization
                replacement = '' if is_phone_number(contact.first_name) else contact.first_name
                message = message.replace('{first_name}', replacement)
                
            if hasattr(contact, 'last_name') and contact.last_name:
                # Skip last names that look like "(from OpenPhone)" or phone numbers
                if not (contact.last_name.startswith('(') or is_phone_number(contact.last_name)):
                    message = message.replace('{last_name}', contact.last_name)
                else:
                    message = message.replace('{last_name}', '')
                    
            if hasattr(contact, 'name') and contact.name:
                replacement = '' if is_phone_number(contact.name) else contact.name
                message = message.replace('{name}', replacement)
                
            if hasattr(contact, 'company_name') and contact.company_name:
                message = message.replace('{company}', contact.company_name)
                
            return message
        except Exception as e:
            logger.error(f"Error personalizing message: {e}")
            return template or ""