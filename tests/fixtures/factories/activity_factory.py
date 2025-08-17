"""
Activity Factory for Test Data Generation

Provides factories for generating realistic Activity model instances
for tracking contact interactions and events.
"""

import factory
from factory import fuzzy
from crm_database import Activity, Contact
from datetime import datetime, timedelta
from .base import (
    BaseFactory, PhoneProvider, BusinessProvider, DateTimeProvider, 
    FactoryTraits, fake
)
import random


class ActivityFactory(BaseFactory):
    """Factory for generating Activity test instances with realistic data"""
    
    class Meta:
        model = Activity
    
    # Core activity information
    activity_type = factory.LazyFunction(lambda: random.choice([
        'call', 'message', 'voicemail', 'email'
    ]))
    
    direction = factory.LazyFunction(lambda: random.choice(['incoming', 'outgoing']))
    status = factory.LazyFunction(lambda: random.choice([
        'answered', 'missed', 'delivered', 'completed', 'failed'
    ]))
    
    body = factory.LazyAttribute(lambda obj: {
        'call': 'Called customer to discuss project requirements',
        'message': 'Sent follow-up message with quote details', 
        'voicemail': 'Left voicemail about upcoming appointment',
        'email': 'Sent email with quote and service information'
    }.get(obj.activity_type, f"{obj.activity_type.title()} activity completed"))
    
    # OpenPhone ID and relationships  
    openphone_id = factory.LazyFunction(lambda: f"op_{fake.uuid4()[:16]}")
    conversation_id = factory.SubFactory('tests.fixtures.factories.conversation_factory.ConversationFactory')
    contact_id = factory.SubFactory('tests.fixtures.factories.contact_factory.ContactFactory')
    user_id = factory.SubFactory('tests.fixtures.factories.user_factory.UserFactory')
    
    # Participants
    from_number = factory.LazyFunction(lambda: PhoneProvider.us_phone())
    to_numbers = factory.LazyFunction(lambda: [PhoneProvider.us_phone()])
    phone_number_id = factory.LazyFunction(lambda: f"pn_{fake.uuid4()[:12]}")
    
    # Media and attachments
    media_urls = factory.LazyFunction(lambda: [] if random.random() > 0.2 else [fake.url()])
    
    # Call-specific fields
    duration_seconds = factory.LazyAttribute(lambda obj: (
        random.randint(30, 1800) if obj.activity_type == 'call' else None
    ))
    recording_url = factory.LazyAttribute(lambda obj: (
        fake.url() if obj.activity_type == 'call' and random.random() < 0.3 else None
    ))
    voicemail_url = factory.LazyAttribute(lambda obj: (
        fake.url() if obj.activity_type == 'voicemail' else None
    ))
    
    # Email-specific fields  
    email_from = factory.LazyAttribute(lambda obj: (
        fake.email() if obj.activity_type == 'email' else None
    ))
    email_to = factory.LazyAttribute(lambda obj: (
        [fake.email()] if obj.activity_type == 'email' else None
    ))
    email_subject = factory.LazyAttribute(lambda obj: (
        fake.sentence(nb_words=6) if obj.activity_type == 'email' else None
    ))
    
    # Factory traits for different activity scenarios
    class Params:
        # Trait: Phone call activity
        is_phone_call = factory.Trait(
            activity_type='call',
            direction='outgoing',
            status=factory.LazyFunction(lambda: random.choice(['answered', 'missed'])),
            body=factory.LazyFunction(lambda: random.choice([
                'Initial contact call - discussed foundation issues',
                'Follow-up call to schedule inspection', 
                'Quote discussion and pricing questions',
                'Appointment confirmation call',
                'Post-job completion check-in'
            ])),
            duration_seconds=factory.LazyFunction(lambda: random.randint(120, 1800)),
            recording_url=factory.LazyFunction(lambda: fake.url() if random.random() < 0.5 else None)
        )
        
        # Trait: Email activity
        is_email = factory.Trait(
            activity_type='email',
            direction='outgoing',
            status='delivered',
            body=factory.LazyFunction(lambda: random.choice([
                'Sent initial quote and service information',
                'Follow-up email with additional details',
                'Invoice sent for completed work',
                'Thank you email and request for review',
                'Appointment reminder and preparation instructions'
            ])),
            email_from=factory.LazyFunction(fake.email),
            email_to=factory.LazyFunction(lambda: [fake.email()]),
            email_subject=factory.LazyFunction(lambda: fake.sentence(nb_words=6))
        )
        
        # Trait: SMS/Text activity  
        is_message = factory.Trait(
            activity_type='message',
            direction='outgoing',
            status='delivered',
            body=factory.LazyFunction(lambda: random.choice([
                'Reminder: Your appointment is tomorrow at 2 PM',
                'We\'re on our way! ETA 15 minutes',
                'Work completed! Invoice sent to your email',
                'Thanks for choosing us! Please review at [link]',
                'Follow-up: Any questions about the work?'
            ]))
        )
        
        # Trait: Voicemail activity
        is_voicemail = factory.Trait(
            activity_type='voicemail',
            direction='incoming', 
            status='completed',
            body=factory.LazyFunction(lambda: random.choice([
                'Left voicemail about foundation repair inquiry',
                'Customer called back about quote',
                'Voicemail requesting service appointment',
                'Follow-up voicemail after inspection'
            ])),
            voicemail_url=factory.LazyFunction(fake.url),
            duration_seconds=factory.LazyFunction(lambda: random.randint(30, 180))
        )
    
    @classmethod
    def create_activity_sequence(cls, contact, days_span=30, activity_count=None):
        """Create a realistic sequence of activities for a contact over time"""
        if activity_count is None:
            activity_count = random.randint(3, 10)
        
        activities = []
        start_date = datetime.now() - timedelta(days=days_span)
        
        # Create activities with realistic progression
        for i in range(activity_count):
            # Calculate activity date (spread over the time span)
            activity_date = start_date + timedelta(
                days=random.randint(0, days_span),
                hours=random.randint(8, 18),  # Business hours
                minutes=random.choice([0, 15, 30, 45])
            )
            
            # Choose activity type based on sequence
            if i == 0:
                # First contact is usually a call or website inquiry
                activity_type = random.choice(['call', 'email', 'sms'])
            elif i < activity_count // 2:
                # Early activities are mostly communication
                activity_type = random.choice(['call', 'email', 'meeting', 'note'])
            else:
                # Later activities include business transactions
                activity_type = random.choice([
                    'quote_sent', 'meeting', 'call', 'invoice_created', 'payment_received'
                ])
            
            activity = cls.create(
                contact_id=contact.id,
                activity_type=activity_type,
                created_at=activity_date,
                updated_at=activity_date
            )
            activities.append(activity)
        
        return sorted(activities, key=lambda a: a.created_at)
    
    @classmethod
    def create_campaign_activities(cls, contact_list, campaign_id):
        """Create SMS campaign activities for a list of contacts"""
        activities = []
        
        for contact in contact_list:
            activity = cls.create(
                contact_id=contact.id,
                is_sms=True,
                activity_metadata={
                    'campaign_id': campaign_id,
                    'message_type': 'campaign_blast',
                    'delivery_status': random.choice(['delivered', 'pending']),
                    'message_length': random.randint(80, 160)
                }
            )
            activities.append(activity)
        
        return activities