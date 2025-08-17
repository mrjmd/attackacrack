"""
Campaign Factory for Test Data Generation

Provides factories for generating realistic Campaign, CampaignList, and related
model instances for testing SMS campaign functionality.
"""

import factory
from crm_database import Campaign, CampaignList, CampaignMembership, CampaignListMember, ContactFlag
from .base import BaseFactory, DateTimeProvider, fake
from .contact_factory import ContactFactory
from datetime import time
import random


class CampaignListFactory(BaseFactory):
    """Factory for generating CampaignList test instances"""
    
    class Meta:
        model = CampaignList
    
    name = factory.LazyFunction(lambda: f"{fake.catch_phrase()} - {fake.date_this_year().strftime('%B %Y')}")
    description = factory.Faker('text', max_nb_chars=200)
    created_at = factory.LazyFunction(lambda: DateTimeProvider.recent_datetime(30))
    created_by = 'test-user'
    is_dynamic = factory.fuzzy.FuzzyChoice([True, False])
    
    # Filter criteria for dynamic lists
    filter_criteria = factory.LazyFunction(lambda: {
        'customer_type': random.choice(['prospect', 'customer', 'all']),
        'lead_source': random.choice(['website', 'referral', 'all']),
        'days_since_contact': random.randint(30, 90)
    } if random.random() < 0.3 else None)
    
    # Factory traits
    class Params:
        # Trait: Prospect-focused list
        is_prospect_list = factory.Trait(
            name=factory.LazyFunction(lambda: f"Prospect Outreach - {fake.month_name()} {fake.year()}"),
            filter_criteria={
                'customer_type': 'prospect',
                'lead_source': 'all',
                'days_since_contact': 60
            },
            is_dynamic=True
        )
        
        # Trait: Customer retention list
        is_customer_list = factory.Trait(
            name=factory.LazyFunction(lambda: f"Customer Follow-up - {fake.month_name()}"),
            filter_criteria={
                'customer_type': 'customer',
                'days_since_last_job': 180
            },
            is_dynamic=True
        )
        
        # Trait: Static imported list
        is_static_list = factory.Trait(
            name=factory.LazyFunction(lambda: f"Imported List - {fake.date_this_month().strftime('%m/%d/%Y')}"),
            filter_criteria=None,
            is_dynamic=False
        )


class CampaignFactory(BaseFactory):
    """Factory for generating Campaign test instances"""
    
    class Meta:
        model = Campaign
    
    name = factory.LazyFunction(lambda: f"{fake.catch_phrase()} Campaign")
    status = factory.fuzzy.FuzzyChoice(['draft', 'running', 'paused', 'complete'])
    created_at = factory.LazyFunction(lambda: DateTimeProvider.recent_datetime(30))
    
    # Message templates
    template_a = factory.LazyFunction(lambda: f"Hi {{first_name}}, {fake.sentence(nb_words=12)} - Attack-a-Crack")
    template_b = factory.Maybe(
        'campaign_type',
        yes_declaration=factory.LazyFunction(lambda: f"Hello {{first_name}}, {fake.sentence(nb_words=10)} Call us today!"),
        no_declaration=None
    )
    
    # Campaign configuration
    campaign_type = factory.fuzzy.FuzzyChoice(['blast', 'automated', 'ab_test'])
    audience_type = factory.fuzzy.FuzzyChoice(['cold', 'customer', 'mixed'])
    channel = factory.fuzzy.FuzzyChoice(['sms', 'email'])
    daily_limit = factory.fuzzy.FuzzyInteger(50, 200)
    business_hours_only = True
    
    # Quiet hours (8 PM to 9 AM)
    quiet_hours_start = time(20, 0)
    quiet_hours_end = time(9, 0)
    
    # Contact handling
    on_existing_contact = factory.fuzzy.FuzzyChoice(['ignore', 'flag_for_review', 'adapt_script'])
    days_between_contacts = factory.fuzzy.FuzzyInteger(30, 90)
    
    # A/B test configuration for A/B campaigns
    ab_config = factory.Maybe(
        'campaign_type',
        yes_declaration=factory.LazyFunction(lambda: {
            'split_ratio': 50,  # 50/50 split
            'test_duration_hours': 24,
            'success_metric': 'response_rate'
        }),
        no_declaration=None
    )
    
    # Associate with a campaign list
    list = factory.SubFactory(CampaignListFactory)
    
    # Adaptive script for previously contacted
    adapt_script_template = factory.Maybe(
        'on_existing_contact',
        yes_declaration=factory.LazyFunction(lambda: f"Hi {{first_name}}, following up on our previous conversation. {fake.sentence(nb_words=8)}"),
        no_declaration=None
    )
    
    # Factory traits
    class Params:
        # Trait: SMS blast campaign
        is_sms_blast = factory.Trait(
            campaign_type='blast',
            channel='sms',
            audience_type='cold',
            template_a="Hi {first_name}, need foundation repair? We fix cracks fast! Free estimates. Reply STOP to opt out.",
            daily_limit=125
        )
        
        # Trait: A/B test campaign
        is_ab_test = factory.Trait(
            campaign_type='ab_test',
            template_b="Hello {first_name}, foundation problems? We're the crack experts! Free consultation. Text STOP to unsubscribe.",
            ab_config={
                'split_ratio': 50,
                'test_duration_hours': 48,
                'success_metric': 'response_rate'
            }
        )
        
        # Trait: Customer retention campaign
        is_retention = factory.Trait(
            audience_type='customer',
            template_a="Hi {first_name}, it's been a while! How's your foundation holding up? We offer maintenance checkups.",
            on_existing_contact='adapt_script',
            adapt_script_template="Hi {first_name}, hope your foundation is still solid! Annual maintenance reminder from Attack-a-Crack."
        )
        
        # Trait: Email campaign
        is_email = factory.Trait(
            channel='email',
            template_a="Subject: Foundation Repair Experts | Hi {first_name}, is your foundation showing cracks? We specialize in permanent repairs...",
            daily_limit=500  # Higher limit for email
        )


class CampaignMembershipFactory(BaseFactory):
    """Factory for generating CampaignMembership test instances"""
    
    class Meta:
        model = CampaignMembership
    
    contact = factory.SubFactory('tests.fixtures.factories.contact_factory.ContactFactory')
    campaign = factory.SubFactory(CampaignFactory)
    status = factory.fuzzy.FuzzyChoice(['pending', 'sent', 'failed', 'replied_positive', 'replied_negative', 'suppressed'])
    
    # A/B variant assignment
    variant_sent = factory.Maybe(
        'status',
        yes_declaration=factory.fuzzy.FuzzyChoice(['A', 'B']),
        no_declaration=None
    )
    
    # Sent timestamp for sent messages
    sent_at = factory.Maybe(
        'status',
        yes_declaration=factory.LazyFunction(lambda: DateTimeProvider.recent_datetime(7)),
        no_declaration=None
    )
    
    # Message content that was actually sent
    message_sent = factory.Maybe(
        'status',
        yes_declaration=factory.LazyFunction(lambda: f"Hi John, {fake.sentence(nb_words=10)} - Attack-a-Crack"),
        no_declaration=None
    )
    
    # Response analysis
    response_sentiment = factory.Maybe(
        'status',
        yes_declaration=factory.fuzzy.FuzzyChoice(['positive', 'negative', 'neutral']),
        no_declaration=None
    )
    
    # Contact history
    previous_contact_date = factory.LazyFunction(lambda: DateTimeProvider.recent_datetime(180) if random.random() < 0.3 else None)
    previous_contact_type = factory.Maybe(
        'previous_contact_date',
        yes_declaration=factory.fuzzy.FuzzyChoice(['sms', 'email', 'call']),
        no_declaration=None
    )
    previous_response = factory.Maybe(
        'previous_contact_date',
        yes_declaration=factory.fuzzy.FuzzyChoice(['positive', 'negative', 'no_response']),
        no_declaration=None
    )
    
    # Pre-send flags for compliance
    pre_send_flags = factory.LazyFunction(lambda: {
        'is_mobile': True,
        'opt_out_status': 'none',
        'recently_contacted': random.random() < 0.1
    })


class CampaignListMemberFactory(BaseFactory):
    """Factory for generating CampaignListMember test instances"""
    
    class Meta:
        model = CampaignListMember
    
    list = factory.SubFactory(CampaignListFactory)
    contact = factory.SubFactory('tests.fixtures.factories.contact_factory.ContactFactory')
    added_at = factory.LazyFunction(lambda: DateTimeProvider.recent_datetime(30))
    added_by = 'test-user'
    status = factory.fuzzy.FuzzyChoice(['active', 'removed', 'suppressed'])
    
    # Import metadata for tracking source
    import_metadata = factory.LazyFunction(lambda: {
        'source': random.choice(['csv_import', 'manual_add', 'api_sync', 'dynamic_filter']),
        'batch_id': fake.uuid4()[:8] if random.random() < 0.5 else None
    })


class ContactFlagFactory(BaseFactory):
    """Factory for generating ContactFlag test instances for opt-outs and compliance"""
    
    class Meta:
        model = ContactFlag
    
    contact = factory.SubFactory('tests.fixtures.factories.contact_factory.ContactFactory')
    flag_type = factory.fuzzy.FuzzyChoice(['opted_out', 'office_number', 'recently_texted', 'do_not_contact'])
    applies_to = factory.fuzzy.FuzzyChoice(['sms', 'email', 'both'])
    created_at = factory.LazyFunction(lambda: DateTimeProvider.recent_datetime(30))
    created_by = 'system'
    
    # Flag reason based on type
    flag_reason = factory.LazyAttribute(lambda obj: {
        'opted_out': 'Customer replied STOP',
        'office_number': 'Identified as business line',
        'recently_texted': 'Contacted within 30 days',
        'do_not_contact': 'Manual suppression'
    }.get(obj.flag_type, 'Unknown'))
    
    # Expiration for temporary flags
    expires_at = factory.Maybe(
        'flag_type',
        yes_declaration=factory.LazyFunction(lambda: DateTimeProvider.future_datetime(30)),
        no_declaration=None
    )
    
    # Factory traits
    class Params:
        # Trait: SMS opt-out
        is_sms_optout = factory.Trait(
            flag_type='opted_out',
            applies_to='sms',
            flag_reason='Customer replied STOP to SMS',
            created_by='openphone_webhook'
        )
        
        # Trait: Email opt-out
        is_email_optout = factory.Trait(
            flag_type='opted_out',
            applies_to='email',
            flag_reason='Customer clicked unsubscribe',
            created_by='email_service'
        )
        
        # Trait: Recently contacted (temporary flag)
        is_recently_contacted = factory.Trait(
            flag_type='recently_texted',
            expires_at=factory.LazyFunction(lambda: DateTimeProvider.future_datetime(30)),
            flag_reason='SMS sent within 30-day window'
        )


# Utility methods for campaign testing scenarios
class CampaignTestScenarios:
    """Helper class for creating complex campaign test scenarios"""
    
    @staticmethod
    def create_active_campaign_with_members(member_count=25, **campaign_kwargs):
        """Create an active campaign with specified number of members"""
        from .contact_factory import ContactFactory
        
        # Create campaign
        campaign = CampaignFactory.create(status='running', **campaign_kwargs)
        
        # Create campaign list with members
        contacts = ContactFactory.create_batch(member_count)
        
        # Add contacts to campaign list
        for contact in contacts:
            CampaignListMemberFactory.create(list=campaign.list, contact=contact)
        
        # Create memberships in various states
        memberships = []
        for i, contact in enumerate(contacts):
            if i < member_count * 0.6:  # 60% sent
                membership = CampaignMembershipFactory.create(
                    campaign=campaign,
                    contact=contact,
                    status='sent'
                )
            elif i < member_count * 0.8:  # 20% pending
                membership = CampaignMembershipFactory.create(
                    campaign=campaign,
                    contact=contact,
                    status='pending'
                )
            else:  # 20% replied
                membership = CampaignMembershipFactory.create(
                    campaign=campaign,
                    contact=contact,
                    status=random.choice(['replied_positive', 'replied_negative'])
                )
            memberships.append(membership)
        
        return campaign, memberships
    
    @staticmethod
    def create_ab_test_scenario():
        """Create A/B test campaign with realistic split results"""
        campaign = CampaignFactory.create(is_ab_test=True, status='running')
        
        # Create 100 contacts for statistically significant test
        contacts = []
        memberships = []
        
        for i in range(100):
            contact = ContactFactory.create()
            contacts.append(contact)
            
            # Add to campaign list
            CampaignListMemberFactory.create(list=campaign.list, contact=contact)
            
            # Create membership with A/B split
            variant = 'A' if i < 50 else 'B'
            
            # Simulate different response rates (A: 15%, B: 8%)
            if variant == 'A' and random.random() < 0.15:
                status = 'replied_positive'
            elif variant == 'B' and random.random() < 0.08:
                status = 'replied_positive'
            else:
                status = 'sent'
            
            membership = CampaignMembershipFactory.create(
                campaign=campaign,
                contact=contact,
                status=status,
                variant_sent=variant
            )
            memberships.append(membership)
        
        return campaign, memberships