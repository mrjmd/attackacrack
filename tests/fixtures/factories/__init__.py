"""
Test Data Factories for Attack-a-Crack CRM

This module provides comprehensive factory classes for generating realistic
test data across all CRM models using Factory Boy and Faker.

Usage:
    from tests.fixtures.factories import ContactFactory, CampaignFactory
    
    # Create single instance
    contact = ContactFactory.create()
    
    # Create with specific attributes
    contact = ContactFactory.create(is_established_customer=True)
    
    # Create batch
    contacts = ContactFactory.create_batch(10)
    
    # Build without saving (for manual session management)
    contact = ContactFactory.build()
"""

from .base import BaseFactory, FactoryTraits
from .contact_factory import ContactFactory
from .campaign_factory import CampaignFactory  
from .user_factory import UserFactory
from .job_factory import JobFactory
from .property_factory import PropertyFactory
from .activity_factory import ActivityFactory
from .conversation_factory import ConversationFactory
from .webhook_event_factory import WebhookEventFactory

__all__ = [
    'BaseFactory',
    'FactoryTraits', 
    'ContactFactory',
    'CampaignFactory',
    'UserFactory',
    'JobFactory',
    'PropertyFactory',
    'ActivityFactory',
    'ConversationFactory',
    'WebhookEventFactory'
]