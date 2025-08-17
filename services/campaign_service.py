"""
Campaign Service - Business logic for text campaign system
Handles campaign creation, recipient management, A/B testing, and compliance
"""

import json
import random
import statistics
from datetime import datetime, time, timedelta
from typing import List, Dict, Optional, Tuple
from scipy import stats
from sqlalchemy import and_, or_, func

from extensions import db
from crm_database import Campaign, CampaignMembership, Contact, ContactFlag, Activity


class CampaignService:
    """Service for managing text campaigns with A/B testing and compliance"""
    
    def __init__(self, 
                 openphone_service=None,
                 list_service=None):
        """Initialize with injected dependencies
        
        Args:
            openphone_service: OpenPhoneService instance for SMS sending
            list_service: CampaignListService instance for list management
        """
        # Accept injected dependencies
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
        """Create a new marketing campaign"""
        
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
        
        campaign = Campaign(
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
        
        db.session.add(campaign)
        db.session.commit()
        
        return campaign
    
    def add_recipients_from_list(self, campaign_id: int, list_id: int) -> int:
        """Add recipients from a campaign list"""
        # Use injected list_service instead of creating new instance
        if not self.list_service:
            raise ValueError("CampaignListService not provided")
        
        # Get all active contacts from the list
        contacts = self.list_service.get_list_contacts(list_id)
        
        added = 0
        for contact in contacts:
            # Skip if already in campaign
            existing = CampaignMembership.query.filter_by(
                campaign_id=campaign_id,
                contact_id=contact.id
            ).first()
            
            if not existing:
                membership = CampaignMembership(
                    campaign_id=campaign_id,
                    contact_id=contact.id,
                    status='pending'
                )
                db.session.add(membership)
                added += 1
        
        # Update campaign list reference
        campaign = Campaign.query.get(campaign_id)
        campaign.list_id = list_id
        
        db.session.commit()
        return added
    
    def add_recipients(self, campaign_id: int, contact_filters: Dict) -> int:
        """Add recipients to campaign based on filters"""
        campaign = Campaign.query.get_or_404(campaign_id)
        
        # Build contact query based on filters
        query = Contact.query
        
        # Apply filters
        if contact_filters.get('has_name_only'):
            # Only contacts with real names (not phone numbers)
            query = query.filter(~Contact.first_name.like('%+1%'))
        
        if contact_filters.get('has_email'):
            query = query.filter(Contact.email.isnot(None))
            query = query.filter(Contact.email != '')
        
        if contact_filters.get('exclude_office_numbers'):
            # Exclude contacts flagged as office numbers
            office_contact_ids = db.session.query(ContactFlag.contact_id).filter(
                ContactFlag.flag_type == 'office_number'
            )
            query = query.filter(~Contact.id.in_(office_contact_ids))
        
        if contact_filters.get('exclude_opted_out'):
            # Exclude contacts who have opted out
            opted_out_ids = db.session.query(ContactFlag.contact_id).filter(
                and_(
                    ContactFlag.flag_type == 'opted_out',
                    ContactFlag.applies_to.in_(['sms', 'both'])
                )
            )
            query = query.filter(~Contact.id.in_(opted_out_ids))
        
        if contact_filters.get('min_days_since_contact'):
            # Only contacts not recently contacted
            days_ago = datetime.utcnow() - timedelta(days=contact_filters['min_days_since_contact'])
            recent_contact_ids = db.session.query(ContactFlag.contact_id).filter(
                and_(
                    ContactFlag.flag_type == 'recently_texted',
                    ContactFlag.created_at > days_ago
                )
            )
            query = query.filter(~Contact.id.in_(recent_contact_ids))
        
        # Get contacts
        contacts = query.all()
        
        # Create campaign memberships
        added_count = 0
        for contact in contacts:
            # Check if already in campaign
            existing = CampaignMembership.query.filter_by(
                campaign_id=campaign_id,
                contact_id=contact.id
            ).first()
            
            if not existing:
                # Pre-validate this contact
                flags = self._get_contact_flags(contact)
                
                membership = CampaignMembership(
                    campaign_id=campaign_id,
                    contact_id=contact.id,
                    status='pending',
                    pre_send_flags=flags
                )
                
                db.session.add(membership)
                added_count += 1
        
        db.session.commit()
        return added_count
    
    def start_campaign(self, campaign_id: int) -> bool:
        """Start a campaign (change status to running)"""
        campaign = Campaign.query.get_or_404(campaign_id)
        
        if campaign.status != 'draft':
            raise ValueError(f"Cannot start campaign with status '{campaign.status}'")
        
        # Validate campaign has recipients
        recipient_count = CampaignMembership.query.filter_by(
            campaign_id=campaign_id,
            status='pending'
        ).count()
        
        if recipient_count == 0:
            raise ValueError("Campaign has no pending recipients")
        
        campaign.status = 'running'
        db.session.commit()
        
        return True
    
    def process_campaign_queue(self) -> Dict:
        """Process pending campaign sends (called by Celery task)"""
        stats = {
            'campaigns_processed': 0,
            'messages_sent': 0,
            'messages_skipped': 0,
            'daily_limits_reached': [],
            'errors': []
        }
        
        # Get running campaigns
        running_campaigns = Campaign.query.filter_by(status='running').all()
        
        for campaign in running_campaigns:
            try:
                sent_today = self._get_daily_send_count(campaign.id)
                
                if sent_today >= campaign.daily_limit:
                    stats['daily_limits_reached'].append(campaign.name)
                    continue
                
                # Process pending sends for this campaign
                campaign_stats = self._process_campaign_sends(campaign)
                stats['messages_sent'] += campaign_stats['sent']
                stats['messages_skipped'] += campaign_stats['skipped']
                stats['campaigns_processed'] += 1
                
            except Exception as e:
                stats['errors'].append(f"Campaign {campaign.name}: {str(e)}")
        
        return stats
    
    def _process_campaign_sends(self, campaign: Campaign) -> Dict:
        """Process sends for a single campaign"""
        stats = {'sent': 0, 'skipped': 0}
        
        # Check if business hours (if required)
        if campaign.business_hours_only and not self._is_business_hours():
            return stats
        
        # Get how many we've already sent today
        sent_today = self._get_daily_send_count(campaign.id)
        remaining_today = max(0, campaign.daily_limit - sent_today)
        
        if remaining_today == 0:
            return stats
        
        # Get pending recipients, limited by remaining daily quota
        pending = CampaignMembership.query.filter_by(
            campaign_id=campaign.id,
            status='pending'
        ).limit(min(50, remaining_today)).all()  # Process in batches, respecting daily limit
        
        for membership in pending:
            try:
                # Skip if contact has no phone number
                if not membership.contact.phone:
                    membership.status = 'skipped'
                    membership.error_message = 'No phone number'
                    stats['skipped'] += 1
                    continue
                    
                # Check contact history
                history = self._check_contact_history(membership.contact, campaign)
                
                # Store history info in membership
                if history['has_history']:
                    membership.previous_contact_date = history['last_contact_date']
                    membership.previous_contact_type = history['last_contact_type'] 
                    membership.previous_response = history['previous_response']
                
                # Handle based on campaign settings
                if history['has_history'] and campaign.on_existing_contact != 'ignore':
                    # Check minimum days between contacts
                    if history['days_since'] < campaign.days_between_contacts:
                        membership.status = 'suppressed'
                        membership.pre_send_flags = {'reason': 'too_recent', 'days_since': history['days_since']}
                        stats['skipped'] += 1
                        continue
                    
                    # Handle negative responses
                    if history['previous_response'] == 'negative':
                        if campaign.on_existing_contact == 'flag_for_review':
                            membership.status = 'flagged'
                            membership.pre_send_flags = {'reason': 'negative_response'}
                            stats['skipped'] += 1
                            continue
                        elif campaign.on_existing_contact == 'skip':
                            membership.status = 'suppressed'
                            membership.pre_send_flags = {'reason': 'negative_response'}
                            stats['skipped'] += 1
                            continue
                
                # Final pre-send validation
                if self._should_skip_send(membership):
                    membership.status = 'skipped'
                    membership.override_action = 'skip'
                    stats['skipped'] += 1
                    continue
                
                # Determine which variant to send (for A/B tests)
                variant = self._determine_variant(campaign)
                
                # Choose template based on contact history
                if (history['has_history'] and 
                    campaign.on_existing_contact == 'adapt_script' and 
                    campaign.adapt_script_template):
                    template = campaign.adapt_script_template
                    membership.script_adapted = True
                else:
                    template = campaign.template_a if variant == 'A' else campaign.template_b
                
                # Personalize message with history context
                personalized_message = self._personalize_message(
                    template, 
                    membership.contact,
                    context={'previous_contact': history} if history['has_history'] else None
                )
                
                # Send message
                result = self._send_message(membership.contact.phone, personalized_message)
                
                if result.get('success', False):
                    membership.status = 'sent'
                    membership.variant_sent = variant
                    membership.message_sent = personalized_message
                    membership.sent_at = datetime.utcnow()
                    
                    # Create recently_texted flag
                    self._create_recently_texted_flag(membership.contact_id)
                    
                    stats['sent'] += 1
                else:
                    membership.status = 'failed'
                    membership.error_message = result.get('error', 'Send failed')
                    stats['skipped'] += 1
                
            except Exception as e:
                membership.status = 'failed'
                membership.error_message = str(e)
                stats['skipped'] += 1
        
        db.session.commit()
        
        # Update A/B test if needed
        if campaign.campaign_type == 'ab_test':
            self._update_ab_test_results(campaign)
        
        return stats
    
    def _determine_variant(self, campaign: Campaign) -> str:
        """Determine which variant to send for A/B test"""
        if campaign.campaign_type != 'ab_test':
            return 'A'
        
        ab_config = campaign.ab_config or {}
        
        # If winner declared, send winner variant
        if ab_config.get('winner_declared'):
            return ab_config.get('winner_variant', 'A')
        
        # Otherwise, use current split percentage
        split = ab_config.get('current_split', 50)
        return 'A' if random.randint(1, 100) <= split else 'B'
    
    def _update_ab_test_results(self, campaign: Campaign):
        """Update A/B test results and check for statistical significance"""
        if campaign.campaign_type != 'ab_test':
            return
        
        ab_config = campaign.ab_config or {}
        
        # Don't update if winner already declared
        if ab_config.get('winner_declared'):
            return
        
        # Get results for each variant
        variant_a_stats = self._get_variant_stats(campaign.id, 'A')
        variant_b_stats = self._get_variant_stats(campaign.id, 'B')
        
        # Check minimum sample size
        min_sample = ab_config.get('min_sample_size', 100)
        if variant_a_stats['sent'] < min_sample or variant_b_stats['sent'] < min_sample:
            return
        
        # Calculate response rates
        a_rate = variant_a_stats['responses'] / variant_a_stats['sent'] if variant_a_stats['sent'] > 0 else 0
        b_rate = variant_b_stats['responses'] / variant_b_stats['sent'] if variant_b_stats['sent'] > 0 else 0
        
        # Perform statistical significance test (Chi-square test)
        try:
            # Create contingency table
            responses_a = variant_a_stats['responses']
            responses_b = variant_b_stats['responses']
            no_response_a = variant_a_stats['sent'] - responses_a
            no_response_b = variant_b_stats['sent'] - responses_b
            
            contingency_table = [[responses_a, no_response_a], [responses_b, no_response_b]]
            chi2, p_value, _, _ = stats.chi2_contingency(contingency_table)
            
            significance_threshold = ab_config.get('significance_threshold', 0.95)
            
            if p_value < (1 - significance_threshold):
                # Statistical significance achieved!
                winner = 'A' if a_rate > b_rate else 'B'
                
                ab_config.update({
                    'winner_declared': True,
                    'winner_variant': winner,
                    'final_p_value': p_value,
                    'final_rates': {'A': a_rate, 'B': b_rate},
                    'winner_declared_at': datetime.utcnow().isoformat()
                })
                
                # Shift 90% of traffic to winner
                ab_config['current_split'] = 90 if winner == 'A' else 10
                
                campaign.ab_config = ab_config
                db.session.commit()
                
        except Exception as e:
            # Log error but don't fail the campaign
            pass
    
    def _get_variant_stats(self, campaign_id: int, variant: str) -> Dict:
        """Get statistics for a specific variant"""
        sent_count = CampaignMembership.query.filter_by(
            campaign_id=campaign_id,
            variant_sent=variant,
            status='sent'
        ).count()
        
        # Count responses (activities created after send)
        response_count = db.session.query(CampaignMembership).join(Activity).filter(
            CampaignMembership.campaign_id == campaign_id,
            CampaignMembership.variant_sent == variant,
            CampaignMembership.status == 'sent',
            Activity.created_at > CampaignMembership.sent_at,
            Activity.direction == 'incoming'
        ).count()
        
        return {
            'sent': sent_count,
            'responses': response_count
        }
    
    def _personalize_message(self, template: str, contact: Contact, context: Dict = None) -> str:
        """Personalize message template with contact data and context"""
        if not template:
            return ""
        
        # Replace placeholders
        message = template
        
        # Basic personalization
        first_name = contact.first_name if contact.first_name and not contact.first_name.startswith('+') else ''
        message = message.replace('{first_name}', first_name)
        
        # Context-based personalization
        if context and context.get('previous_contact'):
            history = context['previous_contact']
            if history['has_history']:
                # Add context placeholders
                message = message.replace('{days_since_contact}', str(history['days_since']))
                message = message.replace('{last_contact_type}', history['last_contact_type'])
                
                # Time-based greetings
                if history['days_since'] < 7:
                    message = message.replace('{time_greeting}', 'Following up from last week')
                elif history['days_since'] < 30:
                    message = message.replace('{time_greeting}', 'Following up from a few weeks ago')
                else:
                    message = message.replace('{time_greeting}', "It's been a while")
        message = message.replace('{last_name}', contact.last_name or '')
        message = message.replace('{email}', contact.email or '')
        
        # Handle contact metadata if available
        if contact.contact_metadata:
            metadata = contact.contact_metadata
            message = message.replace('{company}', metadata.get('company', ''))
            message = message.replace('{neighborhood}', metadata.get('neighborhood', ''))
        
        return message.strip()
    
    def _send_message(self, phone: str, message: str) -> Dict:
        """Send SMS message via OpenPhone"""
        try:
            # Use OpenPhone service to send message
            result = self.openphone_service.send_message(phone, message)
            return result
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _check_contact_history(self, contact: Contact, campaign: Campaign) -> Dict:
        """Check contact's previous interactions"""
        # Find most recent outgoing activity
        last_activity = Activity.query.filter(
            Activity.contact_id == contact.id,
            Activity.direction == 'outgoing',
            Activity.activity_type.in_(['message', 'email', 'call'])
        ).order_by(Activity.created_at.desc()).first()
        
        if not last_activity:
            return {'has_history': False}
        
        days_since = (datetime.utcnow() - last_activity.created_at).days
        
        # Check for response to last activity
        response = None
        if last_activity.activity_type == 'message':
            # Look for incoming message after our last outgoing
            response_activity = Activity.query.filter(
                Activity.contact_id == contact.id,
                Activity.direction == 'incoming',
                Activity.created_at > last_activity.created_at,
                Activity.activity_type == 'message'
            ).first()
            
            if response_activity:
                # Simple sentiment analysis
                response_text = response_activity.body.lower() if response_activity.body else ''
                if any(word in response_text for word in ['stop', 'unsubscribe', 'remove', 'no']):
                    response = 'negative'
                elif any(word in response_text for word in ['yes', 'interested', 'sure', 'ok']):
                    response = 'positive'
                else:
                    response = 'neutral'
        
        return {
            'has_history': True,
            'last_contact_date': last_activity.created_at,
            'last_contact_type': last_activity.activity_type,
            'days_since': days_since,
            'previous_response': response
        }
    
    def _should_skip_send(self, membership: CampaignMembership) -> bool:
        """Check if we should skip sending to this contact"""
        contact = membership.contact
        
        # Check for permanent opt-out flags
        opted_out = ContactFlag.query.filter_by(
            contact_id=contact.id,
            flag_type='opted_out',
            applies_to='sms'
        ).first() or ContactFlag.query.filter_by(
            contact_id=contact.id,
            flag_type='opted_out',
            applies_to='both'
        ).first()
        
        if opted_out:
            return True
        
        # Check for office number flag
        office_flag = ContactFlag.query.filter_by(
            contact_id=contact.id,
            flag_type='office_number'
        ).first()
        
        if office_flag:
            return True
        
        # Check for recent texting (within 30 days)
        recent_text = ContactFlag.query.filter(
            ContactFlag.contact_id == contact.id,
            ContactFlag.flag_type == 'recently_texted',
            ContactFlag.created_at > datetime.utcnow() - timedelta(days=30)
        ).first()
        
        if recent_text:
            return True
        
        return False
    
    def personalize_message(self, template: str, contact: Contact) -> str:
        """Public method for message personalization"""
        return self._personalize_message(template, contact)
    
    def is_business_hours(self) -> bool:
        """Check if current time is within business hours"""
        now = datetime.now()
        current_time = now.time()
        current_day = now.weekday()
        
        # Check if it's a business day
        if current_day not in self.business_days:
            return False
        
        # Check if within business hours
        return self.business_hours_start <= current_time <= self.business_hours_end
    
    def select_variant_for_recipient(self, campaign: Campaign) -> str:
        """Select A or B variant for A/B test based on current split"""
        if campaign.campaign_type != 'ab_test':
            return 'A'
        
        ab_config = campaign.ab_config or {}
        
        # If winner declared, use winner variant
        if ab_config.get('winner_declared'):
            return ab_config.get('winner_variant', 'A')
        
        # Use current split percentage
        current_split = ab_config.get('current_split', 50)
        
        # Random selection based on split
        import random
        return 'A' if random.randint(1, 100) <= current_split else 'B'
    
    def calculate_significance(self, stats_a: Dict, stats_b: Dict) -> Dict:
        """Calculate statistical significance between two variants"""
        try:
            sent_a = stats_a.get('sent', 0)
            sent_b = stats_b.get('sent', 0)
            responses_a = stats_a.get('responses', 0)
            responses_b = stats_b.get('responses', 0)
            
            if sent_a == 0 or sent_b == 0:
                return {
                    'p_value': 1.0,
                    'is_significant': False,
                    'confidence': 0.0
                }
            
            # Calculate response rates
            rate_a = responses_a / sent_a
            rate_b = responses_b / sent_b
            
            # Perform chi-square test
            no_response_a = sent_a - responses_a
            no_response_b = sent_b - responses_b
            
            contingency_table = [
                [responses_a, no_response_a],
                [responses_b, no_response_b]
            ]
            
            chi2, p_value, _, _ = stats.chi2_contingency(contingency_table)
            
            confidence = 1 - p_value
            is_significant = p_value < 0.05  # 95% confidence threshold
            
            return {
                'p_value': p_value,
                'is_significant': is_significant,
                'confidence': confidence,
                'rate_a': rate_a,
                'rate_b': rate_b
            }
        except Exception as e:
            return {
                'p_value': 1.0,
                'is_significant': False,
                'confidence': 0.0,
                'error': str(e)
            }
    
    def check_and_declare_ab_winner(self, campaign: Campaign) -> Dict:
        """Check if A/B test has reached significance and declare winner"""
        if campaign.campaign_type != 'ab_test':
            return {'winner_declared': False, 'reason': 'Not an A/B test'}
        
        ab_config = campaign.ab_config or {}
        
        # Already has winner
        if ab_config.get('winner_declared'):
            return {
                'winner_declared': True,
                'winner': ab_config.get('winner_variant')
            }
        
        # Get analytics for both variants
        analytics = self.get_campaign_analytics(campaign.id)
        
        stats_a = analytics.get('variant_a', {})
        stats_b = analytics.get('variant_b', {})
        
        # Check minimum sample size
        min_sample = ab_config.get('min_sample_size', 100)
        if stats_a.get('sent', 0) < min_sample or stats_b.get('sent', 0) < min_sample:
            return {
                'winner_declared': False,
                'reason': 'Insufficient sample size'
            }
        
        # Calculate significance
        significance = self.calculate_significance(stats_a, stats_b)
        
        if significance['is_significant']:
            # Determine winner
            winner = 'A' if stats_a.get('response_rate', 0) > stats_b.get('response_rate', 0) else 'B'
            
            # Update campaign
            ab_config['winner_declared'] = True
            ab_config['winner_variant'] = winner
            ab_config['final_p_value'] = significance['p_value']
            ab_config['confidence'] = significance['confidence']
            campaign.ab_config = ab_config
            
            db.session.commit()
            
            return {
                'winner_declared': True,
                'winner': winner,
                'confidence': significance['confidence'],
                'p_value': significance['p_value']
            }
        
        return {
            'winner_declared': False,
            'reason': 'Not yet statistically significant',
            'current_p_value': significance['p_value']
        }
    
    def is_opt_out_message(self, message: str) -> bool:
        """Check if message is an opt-out request"""
        if not message:
            return False
        
        opt_out_keywords = [
            'stop', 'unsubscribe', 'optout', 'opt-out', 
            'remove', 'cancel', 'quit', 'end'
        ]
        
        message_lower = message.lower().strip()
        return any(keyword in message_lower for keyword in opt_out_keywords)
    
    def should_send_to_contact(self, contact: Contact) -> bool:
        """Check if we should send messages to this contact"""
        # Check for opt-out flag
        opted_out = ContactFlag.query.filter_by(
            contact_id=contact.id,
            flag_type='opted_out'
        ).first()
        
        if opted_out:
            return False
        
        # Check for office number flag
        office_flag = ContactFlag.query.filter_by(
            contact_id=contact.id,
            flag_type='office_number'
        ).first()
        
        if office_flag:
            return False
        
        return True
    
    def _get_contact_flags(self, contact: Contact) -> List[str]:
        """Get list of flags for a contact"""
        flags = ContactFlag.query.filter_by(contact_id=contact.id).all()
        return [f.flag_type for f in flags]
    
    def _create_recently_texted_flag(self, contact_id: int):
        """Create a recently_texted flag for a contact"""
        flag = ContactFlag(
            contact_id=contact_id,
            flag_type='recently_texted',
            flag_reason='Sent campaign message',
            applies_to='sms',
            expires_at=datetime.utcnow() + timedelta(days=30),
            created_by='campaign_system'
        )
        db.session.add(flag)
    
    def _is_business_hours(self) -> bool:
        """Check if current time is within business hours"""
        now = datetime.now()
        
        # Check if weekday
        if now.weekday() not in self.business_days:
            return False
        
        # Check if within business hours
        current_time = now.time()
        return self.business_hours_start <= current_time <= self.business_hours_end
    
    def _get_daily_send_count(self, campaign_id: int) -> int:
        """Get number of messages sent today for a campaign"""
        today = datetime.utcnow().date()
        
        count = CampaignMembership.query.filter(
            CampaignMembership.campaign_id == campaign_id,
            CampaignMembership.status == 'sent',
            func.date(CampaignMembership.sent_at) == today
        ).count()
        
        return count
    
    def get_all_campaigns_with_analytics(self) -> List[Dict]:
        """Get all campaigns with their analytics"""
        campaigns = Campaign.query.order_by(Campaign.created_at.desc()).all()
        
        campaign_data = []
        for campaign in campaigns:
            analytics = self.get_campaign_analytics(campaign.id)
            campaign_data.append({
                'campaign': campaign,
                'analytics': analytics
            })
        
        return campaign_data
    
    def get_audience_stats(self) -> Dict:
        """Get statistics about available audience for campaigns"""
        total_contacts = Contact.query.count()
        
        # Contacts with real names (not phone numbers)
        named_contacts = Contact.query.filter(~Contact.first_name.like('%+1%')).count()
        
        # Contacts with emails
        email_contacts = Contact.query.filter(
            Contact.email.isnot(None),
            Contact.email != ''
        ).count()
        
        # Opted out contacts
        opted_out_count = db.session.query(Contact.id).join(ContactFlag).filter(
            ContactFlag.flag_type == 'opted_out',
            ContactFlag.applies_to.in_(['sms', 'both'])
        ).count()
        
        return {
            'total_contacts': total_contacts,
            'named_contacts': named_contacts,
            'email_contacts': email_contacts,
            'opted_out_count': opted_out_count,
            'available_contacts': total_contacts - opted_out_count
        }
    
    def pause_campaign(self, campaign_id: int) -> bool:
        """Pause a running campaign"""
        campaign = Campaign.query.get(campaign_id)
        if not campaign:
            return False
        
        if campaign.status == 'running':
            campaign.status = 'paused'
            db.session.commit()
            return True
        return False
    
    def get_campaign_recipients(self, campaign_id: int, status_filter: str = 'all', 
                               variant_filter: str = 'all', page: int = 1, 
                               per_page: int = 50) -> Dict:
        """Get paginated campaign recipients with filtering"""
        query = CampaignMembership.query.filter_by(campaign_id=campaign_id)
        
        if status_filter != 'all':
            query = query.filter_by(status=status_filter)
        
        if variant_filter != 'all':
            query = query.filter_by(variant=variant_filter)
        
        # Add joins to get contact info
        query = query.join(Contact)
        
        # Paginate
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        
        return {
            'recipients': pagination.items,
            'total': pagination.total,
            'pages': pagination.pages,
            'current_page': page
        }
    
    def get_recent_sends(self, campaign_id: int, limit: int = 10) -> List[CampaignMembership]:
        """Get recent message sends for a campaign"""
        return CampaignMembership.query.filter_by(
            campaign_id=campaign_id,
            status='sent'
        ).order_by(CampaignMembership.sent_at.desc()).limit(limit).all()
    
    def preview_audience(self, filters: Dict) -> Dict:
        """Preview campaign audience size based on filters"""
        # Build contact query based on filters
        query = Contact.query
        
        if filters.get('has_name_only'):
            query = query.filter(~Contact.first_name.like('%+1%'))
        
        if filters.get('has_email'):
            query = query.filter(Contact.email.isnot(None))
            query = query.filter(Contact.email != '')
        
        if filters.get('exclude_office_numbers'):
            office_contact_ids = db.session.query(ContactFlag.contact_id).filter(
                ContactFlag.flag_type == 'office_number'
            ).subquery()
            query = query.filter(~Contact.id.in_(office_contact_ids))
        
        # Always exclude opted out
        opted_out_ids = db.session.query(ContactFlag.contact_id).filter(
            ContactFlag.flag_type == 'opted_out',
            ContactFlag.applies_to.in_(['sms', 'both'])
        ).subquery()
        query = query.filter(~Contact.id.in_(opted_out_ids))
        
        if filters.get('min_days_since_contact'):
            days_ago = datetime.utcnow() - timedelta(days=filters['min_days_since_contact'])
            recent_contact_ids = db.session.query(ContactFlag.contact_id).filter(
                ContactFlag.flag_type == 'recently_texted',
                ContactFlag.created_at > days_ago
            ).subquery()
            query = query.filter(~Contact.id.in_(recent_contact_ids))
        
        # Get count and sample
        total_count = query.count()
        sample_contacts = query.limit(5).all()
        
        return {
            'total_count': total_count,
            'sample_contacts': [{
                'id': c.id,
                'name': c.first_name or c.phone,
                'phone': c.phone,
                'email': c.email
            } for c in sample_contacts]
        }
    
    def get_campaign_analytics(self, campaign_id: int) -> Dict:
        """Get comprehensive analytics for a campaign"""
        campaign = Campaign.query.get_or_404(campaign_id)
        
        # Basic stats
        total_recipients = CampaignMembership.query.filter_by(campaign_id=campaign_id).count()
        sent_count = CampaignMembership.query.filter_by(campaign_id=campaign_id, status='sent').count()
        pending_count = CampaignMembership.query.filter_by(campaign_id=campaign_id, status='pending').count()
        failed_count = CampaignMembership.query.filter_by(campaign_id=campaign_id, status='failed').count()
        
        # Response tracking
        responses = db.session.query(CampaignMembership).join(Activity).filter(
            CampaignMembership.campaign_id == campaign_id,
            CampaignMembership.status == 'sent',
            Activity.created_at > CampaignMembership.sent_at,
            Activity.direction == 'incoming'
        ).count()
        
        # Calculate rates
        response_rate = (responses / sent_count) if sent_count > 0 else 0
        
        analytics = {
            'campaign_name': campaign.name,
            'campaign_type': campaign.campaign_type,
            'status': campaign.status,
            'created_at': campaign.created_at,
            'total_recipients': total_recipients,
            'sent_count': sent_count,
            'pending_count': pending_count,
            'failed_count': failed_count,
            'response_count': responses,
            'response_rate': response_rate,
            'daily_limit': campaign.daily_limit,
            'sends_today': self._get_daily_send_count(campaign_id)
        }
        
        # A/B test specific analytics
        if campaign.campaign_type == 'ab_test':
            variant_a_stats = self._get_variant_stats(campaign_id, 'A')
            variant_b_stats = self._get_variant_stats(campaign_id, 'B')
            
            analytics['ab_test'] = {
                'variant_a': {
                    'sent': variant_a_stats['sent'],
                    'responses': variant_a_stats['responses'],
                    'rate': variant_a_stats['responses'] / variant_a_stats['sent'] if variant_a_stats['sent'] > 0 else 0
                },
                'variant_b': {
                    'sent': variant_b_stats['sent'],
                    'responses': variant_b_stats['responses'],
                    'rate': variant_b_stats['responses'] / variant_b_stats['sent'] if variant_b_stats['sent'] > 0 else 0
                },
                'config': campaign.ab_config
            }
        
        return analytics
    
    def handle_opt_out(self, phone: str, message: str) -> bool:
        """Handle opt-out request from incoming message"""
        # Detect opt-out keywords
        opt_out_keywords = ['stop', 'unsubscribe', 'remove', 'opt out', 'opt-out']
        message_lower = message.lower()
        
        is_opt_out = any(keyword in message_lower for keyword in opt_out_keywords)
        
        if is_opt_out:
            # Find contact by phone
            contact = Contact.query.filter_by(phone=phone).first()
            if contact:
                # Create opt-out flag
                flag = ContactFlag(
                    contact_id=contact.id,
                    flag_type='opted_out',
                    flag_reason=f'Requested opt-out via SMS: "{message}"',
                    applies_to='sms',
                    created_by='system_auto_detect'
                )
                db.session.add(flag)
                db.session.commit()
                
                return True
        
        return False
    
    def get_campaigns_using_list(self, list_id: int) -> List[Campaign]:
        """Get all campaigns that use a specific campaign list"""
        return Campaign.query.filter_by(list_id=list_id).all()