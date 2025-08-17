"""
WebhookEvent Factory for Test Data Generation

Provides factories for generating realistic WebhookEvent model instances
for testing OpenPhone webhook processing and event logging.
"""

import factory
from factory import fuzzy
from crm_database import WebhookEvent
from datetime import datetime, timedelta
from .base import (
    BaseFactory, PhoneProvider, DateTimeProvider, 
    FactoryTraits, fake
)
import random
import json


def _generate_event_data(event_type):
    """Generate realistic event data based on event type"""
    if event_type.startswith('message.'):
        return {
            'object': {
                'id': f"msg_{fake.uuid4()[:16]}",
                'direction': random.choice(['incoming', 'outgoing']),
                'from': PhoneProvider.us_phone(),
                'to': PhoneProvider.us_phone(),
                'text': random.choice([
                    "Hi, I'm interested in foundation repair",
                    "Can you give me a quote?",
                    "When can you come out for an inspection?",
                    "Thanks for the quick response!",
                    "I have a few more questions"
                ]),
                'conversationId': f"conv_{fake.uuid4()[:16]}",
                'media': [] if random.random() > 0.2 else [
                    {'type': 'image', 'url': fake.url()}
                ],
                'status': 'received',
                'createdAt': DateTimeProvider.recent_datetime(1).isoformat()
            }
        }
    elif event_type.startswith('call.'):
        return {
            'object': {
                'id': f"call_{fake.uuid4()[:16]}",
                'direction': random.choice(['incoming', 'outgoing']),
                'participants': [PhoneProvider.us_phone(), '+14155551000'],
                'duration': random.randint(30, 1800),  # 30 seconds to 30 minutes
                'status': random.choice(['completed', 'missed', 'failed']),
                'answeredAt': DateTimeProvider.recent_datetime(1).isoformat(),
                'completedAt': DateTimeProvider.recent_datetime(1).isoformat()
            }
        }
    elif event_type.startswith('contact.'):
        return {
            'object': {
                'id': f"contact_{fake.uuid4()[:16]}",
                'phone_number': PhoneProvider.us_phone(),
                'name': fake.name(),
                'email': fake.email() if random.random() < 0.7 else None,
                'tags': random.sample(['prospect', 'customer', 'hot_lead'], k=random.randint(0, 2))
            }
        }
    else:
        return {
            'object': {
                'id': fake.uuid4(), 
                'data': 'generic_event_data'
            }
        }


class WebhookEventFactory(BaseFactory):
    """Factory for generating WebhookEvent test instances with realistic data"""
    
    class Meta:
        model = WebhookEvent
    
    # Core webhook information
    event_id = factory.LazyFunction(lambda: f"evt_{fake.uuid4()[:20]}")
    event_type = factory.LazyFunction(lambda: random.choice([
        'message.received', 'message.delivered', 'message.failed',
        'call.completed', 'call.missed', 'call.failed',
        'contact.created', 'contact.updated'
    ]))
    
    # API version
    api_version = factory.LazyFunction(lambda: random.choice(['v1', 'v2', 'v4']))
    
    # Processing status
    processed = factory.LazyFunction(lambda: random.choice([True, False]))
    processed_at = factory.LazyAttribute(lambda obj: (
        DateTimeProvider.recent_datetime(1) if obj.processed 
        else None
    ))
    
    # Timestamps
    created_at = factory.LazyFunction(lambda: DateTimeProvider.recent_datetime(7))
    
    # Webhook payload (JSON field)
    payload = factory.LazyAttribute(lambda obj: {
        'id': obj.event_id,
        'type': obj.event_type,
        'data': _generate_event_data(obj.event_type),
        'timestamp': obj.created_at.isoformat(),
        'webhook_id': fake.uuid4()
    })

    # Error information for failed processing
    error_message = factory.LazyAttribute(lambda obj: (
        None if obj.processed else random.choice([
            'Database connection timeout',
            'Invalid phone number format',
            'Contact creation failed',
            'Duplicate event detected',
            'Webhook signature validation failed'
        ])
    ))
    
    # Factory traits for different webhook scenarios
    class Params:
        # Trait: Message received webhook
        is_message_received = factory.Trait(
            event_type='message.received',
            processed=True,
            payload=factory.LazyFunction(lambda: {
                'id': f"evt_{fake.uuid4()[:20]}",
                'type': 'message.received',
                'data': {
                    'object': {
                        'id': f"msg_{fake.uuid4()[:16]}",
                        'direction': 'incoming',
                        'from': PhoneProvider.us_phone(),
                        'to': '+14155551000',  # Our business number
                        'text': random.choice([
                            "I need help with foundation cracks",
                            "Can you fix a leaking basement?",
                            "Looking for waterproofing services",
                            "What's your availability for next week?"
                        ]),
                        'conversationId': f"conv_{fake.uuid4()[:16]}",
                        'createdAt': DateTimeProvider.recent_datetime(1).isoformat(),
                        'status': 'received'
                    }
                },
                'timestamp': DateTimeProvider.recent_datetime(1).isoformat()
            })
        )
        
        # Trait: Call completed webhook
        is_call_completed = factory.Trait(
            event_type='call.completed',
            processed=True,
            payload=factory.LazyFunction(lambda: {
                'id': f"evt_{fake.uuid4()[:20]}",
                'type': 'call.completed',
                'data': {
                    'object': {
                        'id': f"call_{fake.uuid4()[:16]}",
                        'direction': random.choice(['incoming', 'outgoing']),
                        'participants': [PhoneProvider.us_phone(), '+14155551000'],
                        'duration': random.randint(120, 1800),  # 2-30 minutes
                        'status': 'completed',
                        'answeredAt': DateTimeProvider.recent_datetime(1).isoformat(),
                        'completedAt': DateTimeProvider.recent_datetime(1).isoformat()
                    }
                },
                'timestamp': DateTimeProvider.recent_datetime(1).isoformat()
            })
        )
        
        # Trait: Failed processing webhook
        is_failed_processing = factory.Trait(
            processed=False,
            error_message=factory.LazyFunction(lambda: random.choice([
                'Contact not found for phone number',
                'Database constraint violation',
                'Invalid webhook payload format',
                'Service temporarily unavailable'
            ]))
        )
        
        # Trait: Recent webhook (last hour)
        is_recent = factory.Trait(
            created_at=factory.LazyFunction(lambda: datetime.now() - timedelta(
                minutes=random.randint(1, 60)
            ))
        )
        
        # Trait: Webhook with media attachment
        has_media = factory.Trait(
            event_type='message.received',
            payload=factory.LazyFunction(lambda: {
                'id': f"evt_{fake.uuid4()[:20]}",
                'type': 'message.received',
                'data': {
                    'object': {
                        'id': f"msg_{fake.uuid4()[:16]}",
                        'direction': 'incoming',
                        'from': PhoneProvider.us_phone(),
                        'to': '+14155551000',
                        'text': 'Here are some photos of the foundation issue',
                        'conversationId': f"conv_{fake.uuid4()[:16]}",
                        'media': [
                            {
                                'type': 'image',
                                'url': fake.url(),
                                'filename': 'foundation_crack_1.jpg'
                            },
                            {
                                'type': 'image', 
                                'url': fake.url(),
                                'filename': 'foundation_crack_2.jpg'
                            }
                        ],
                        'createdAt': DateTimeProvider.recent_datetime(1).isoformat(),
                        'status': 'received'
                    }
                },
                'timestamp': DateTimeProvider.recent_datetime(1).isoformat()
            })
        )
    
    @classmethod
    def create_message_thread(cls, conversation_id, message_count=5):
        """Create a series of message webhooks for a conversation"""
        webhooks = []
        base_time = datetime.now() - timedelta(hours=2)
        
        for i in range(message_count):
            message_time = base_time + timedelta(minutes=i * random.randint(5, 30))
            direction = 'incoming' if i % 2 == 0 else 'outgoing'
            
            webhook = cls.create(
                event_type='message.received',
                created_at=message_time,
                processed=True,
                payload={
                    'id': f"evt_{fake.uuid4()[:20]}",
                    'type': 'message.received',
                    'data': {
                        'object': {
                            'id': f"msg_{fake.uuid4()[:16]}",
                            'direction': direction,
                            'from': PhoneProvider.us_phone() if direction == 'incoming' else '+14155551000',
                            'to': '+14155551000' if direction == 'incoming' else PhoneProvider.us_phone(),
                            'text': random.choice([
                                "Thanks for reaching out!",
                                "I can schedule an inspection for you",
                                "Our pricing starts at $2,500",
                                "When would be a good time to visit?",
                                "Perfect, I'll see you then"
                            ]),
                            'conversationId': conversation_id,
                            'createdAt': message_time.isoformat(),
                            'status': 'received'
                        }
                    },
                    'timestamp': message_time.isoformat()
                }
            )
            webhooks.append(webhook)
        
        return webhooks
    
    @classmethod
    def create_call_sequence(cls, phone_number, call_count=3):
        """Create a series of call webhooks for follow-up sequence"""
        webhooks = []
        base_time = datetime.now() - timedelta(days=7)
        
        for i in range(call_count):
            call_time = base_time + timedelta(days=i * 2, hours=random.randint(9, 17))
            call_status = random.choice(['completed', 'missed']) if i < call_count - 1 else 'completed'
            
            webhook = cls.create(
                event_type='call.completed',
                created_at=call_time,
                processed=True,
                payload={
                    'id': f"evt_{fake.uuid4()[:20]}",
                    'type': 'call.completed',
                    'data': {
                        'object': {
                            'id': f"call_{fake.uuid4()[:16]}",
                            'direction': 'outgoing',
                            'participants': ['+14155551000', phone_number],
                            'duration': random.randint(180, 900) if call_status == 'completed' else 0,
                            'status': call_status,
                            'answeredAt': call_time.isoformat(),
                            'completedAt': (call_time + timedelta(
                                seconds=random.randint(180, 900)
                            )).isoformat()
                        }
                    },
                    'timestamp': call_time.isoformat()
                }
            )
            webhooks.append(webhook)
        
        return webhooks
    
    @classmethod
    def create_error_scenarios(cls, error_types=None):
        """Create webhooks representing various error scenarios"""
        if error_types is None:
            error_types = [
                'database_timeout', 'invalid_format', 'duplicate_event',
                'signature_failed', 'service_unavailable'
            ]
        
        error_webhooks = []
        
        for error_type in error_types:
            webhook = cls.create(
                is_failed_processing=True,
                error_message=f"Simulated {error_type.replace('_', ' ')} error"
            )
            error_webhooks.append(webhook)
        
        return error_webhooks