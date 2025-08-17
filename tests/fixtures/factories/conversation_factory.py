"""
Conversation Factory for Test Data Generation

Provides factories for generating realistic Conversation model instances
for OpenPhone SMS/call conversation tracking.
"""

import factory
from factory import fuzzy
from crm_database import Conversation, Contact, PhoneNumber
from datetime import datetime, timedelta
from .base import (
    BaseFactory, PhoneProvider, DateTimeProvider, 
    FactoryTraits, fake
)
import random


class ConversationFactory(BaseFactory):
    """Factory for generating Conversation test instances with realistic data"""
    
    class Meta:
        model = Conversation
    
    # Core conversation information
    openphone_id = factory.LazyFunction(lambda: f"conv_{fake.uuid4()[:16]}")
    name = factory.LazyFunction(lambda: f"Conversation with {fake.name()}")
    
    # Participants and phone details
    participants = factory.LazyFunction(lambda: f"{PhoneProvider.us_phone()},{PhoneProvider.us_phone()}")
    phone_number_id = factory.LazyFunction(lambda: f"pn_{fake.uuid4()[:12]}")
    
    # Activity tracking
    last_activity_at = factory.LazyFunction(lambda: DateTimeProvider.recent_datetime(30))
    last_activity_type = factory.LazyFunction(lambda: random.choice(['message', 'call']))
    last_activity_id = factory.LazyFunction(lambda: f"act_{fake.uuid4()[:16]}")
    
    # Relationships
    contact_id = factory.SubFactory('tests.fixtures.factories.contact_factory.ContactFactory')
    
    # Factory traits for different conversation scenarios
    class Params:
        # Trait: New inquiry conversation
        is_new_inquiry = factory.Trait(
            name="Foundation Repair Inquiry",
            last_activity_type='message',
            last_activity_at=factory.LazyFunction(lambda: DateTimeProvider.recent_datetime(3))
        )
        
        # Trait: Active sales conversation
        is_sales_conversation = factory.Trait(
            name="Sales Discussion - Foundation Repair",
            last_activity_type='message',
            last_activity_at=factory.LazyFunction(lambda: DateTimeProvider.recent_datetime(7))
        )
        
        # Trait: Support/follow-up conversation
        is_support_conversation = factory.Trait(
            name="Customer Support Follow-up",
            last_activity_type='call',
            last_activity_at=factory.LazyFunction(lambda: DateTimeProvider.recent_datetime(14))
        )
        
        # Trait: Long conversation thread
        is_lengthy_conversation = factory.Trait(
            name="Extended Customer Consultation",
            last_activity_type='message',
            last_activity_at=factory.LazyFunction(lambda: DateTimeProvider.recent_datetime(1))
        )
    
    @classmethod
    def create_conversation_thread(cls, contact, message_count=None, days_span=7):
        """Create a conversation with multiple realistic message exchanges"""
        if message_count is None:
            message_count = random.randint(3, 12)
        
        # Create the base conversation
        conversation = cls.create(
            contact_id=contact.id,
            conversation_metadata={
                'message_count': message_count,
                'conversation_type': random.choice(['inquiry', 'sales', 'support']),
                'spans_days': days_span
            }
        )
        
        # The conversation represents the latest state
        # Individual messages would be stored separately in a Message model
        # This factory focuses on the conversation summary/metadata
        
        return conversation
    
    @classmethod
    def create_campaign_responses(cls, contact_list, campaign_id):
        """Create conversations representing responses to a campaign"""
        conversations = []
        
        # 15-25% of contacts typically respond to campaigns
        response_count = max(1, int(len(contact_list) * random.uniform(0.15, 0.25)))
        responding_contacts = random.sample(contact_list, response_count)
        
        for contact in responding_contacts:
            conversation = cls.create(
                contact_id=contact.id,
                last_message_content=random.choice([
                    "Yes, I'm interested in learning more",
                    "Can you send me more information?",
                    "I'd like to schedule a consultation",
                    "What are your current pricing options?",
                    "Please remove me from your list",
                    "I already had this work done"
                ]),
                last_message_direction='inbound',
                conversation_metadata={
                    'campaign_id': campaign_id,
                    'response_type': random.choice(['interested', 'info_request', 'opt_out']),
                    'response_time_minutes': random.randint(5, 1440),  # 5 min to 24 hours
                    'conversation_type': 'campaign_response'
                }
            )
            conversations.append(conversation)
        
        return conversations
    
    @classmethod
    def create_customer_journey(cls, contact, stages=['inquiry', 'quote', 'sale', 'follow_up']):
        """Create conversations representing different stages of customer journey"""
        conversations = []
        base_date = datetime.now() - timedelta(days=30)
        
        for i, stage in enumerate(stages):
            conversation_date = base_date + timedelta(days=i*7 + random.randint(0, 3))
            
            stage_content = {
                'inquiry': "I'm interested in foundation repair services",
                'quote': "I received your quote, can we discuss the timeline?",
                'sale': "I'd like to move forward with the project",
                'follow_up': "The work was completed perfectly, thank you!"
            }
            
            conversation = cls.create(
                contact_id=contact.id,
                last_message_content=stage_content.get(stage, "Following up on our previous conversation"),
                last_message_at=conversation_date,
                created_at=conversation_date - timedelta(hours=1),
                updated_at=conversation_date,
                conversation_metadata={
                    'journey_stage': stage,
                    'stage_order': i + 1,
                    'total_stages': len(stages),
                    'conversation_type': stage
                }
            )
            conversations.append(conversation)
        
        return conversations