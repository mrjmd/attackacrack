"""
Contact Factory for Test Data Generation

Provides factories for generating realistic Contact model instances
with proper relationships and business context.
"""

import factory
from factory import fuzzy
from crm_database import Contact
from datetime import datetime, date
from .base import (
    BaseFactory, PhoneProvider, BusinessProvider, 
    DateTimeProvider, FactoryTraits, fake
)
import random


class ContactFactory(BaseFactory):
    """Factory for generating Contact test instances with realistic data"""
    
    class Meta:
        model = Contact
    
    # Core contact information
    first_name = factory.Faker('first_name')
    last_name = factory.Faker('last_name')
    email = factory.LazyAttribute(lambda obj: f'{obj.first_name.lower()}.{obj.last_name.lower()}@{fake.domain_name()}')
    phone = factory.LazyFunction(PhoneProvider.us_phone)
    
    # Business context
    lead_source = factory.LazyFunction(BusinessProvider.lead_source)
    customer_type = factory.LazyFunction(BusinessProvider.customer_type)
    customer_since = factory.LazyAttribute(lambda obj: DateTimeProvider.recent_date(365) if obj.customer_type == 'customer' else None)
    
    # Financial fields with realistic defaults
    total_sales = factory.LazyAttribute(lambda obj: round(random.uniform(0, 50000), 2) if obj.customer_type == 'customer' else 0)
    outstanding_balance = factory.LazyAttribute(lambda obj: round(random.uniform(0, 5000), 2) if obj.customer_type == 'customer' else 0)
    last_payment_date = factory.LazyAttribute(lambda obj: DateTimeProvider.recent_date(60) if obj.customer_type == 'customer' else None)
    average_days_to_pay = factory.LazyAttribute(lambda obj: random.randint(15, 45) if obj.customer_type == 'customer' else None)
    
    # QuickBooks integration (some contacts)
    quickbooks_customer_id = factory.Maybe(
        'customer_type',
        yes_declaration=factory.LazyFunction(lambda: fake.uuid4()[:20]),
        no_declaration=None
    )
    quickbooks_sync_token = factory.Maybe(
        'quickbooks_customer_id',
        yes_declaration=factory.LazyFunction(lambda: str(random.randint(1, 100))),
        no_declaration=None
    )
    
    # Metadata for flexible data storage
    contact_metadata = factory.LazyFunction(lambda: {
        'preferred_contact_method': random.choice(['phone', 'email', 'text']),
        'best_time_to_call': random.choice(['morning', 'afternoon', 'evening']),
        'source_campaign': fake.catch_phrase() if random.random() < 0.3 else None
    })
    
    @factory.post_generation
    def set_payment_terms(obj, create, extracted, **kwargs):
        """Set payment terms for customers"""
        if obj.customer_type == 'customer':
            obj.payment_terms = random.choice(['Net 30', 'Net 15', 'Due on receipt'])
            obj.credit_limit = round(random.uniform(5000, 25000), 2)
    
    # Factory traits for different contact scenarios
    class Params:
        # Trait: New prospect from recent marketing campaign
        is_new_prospect = factory.Trait(
            customer_type='prospect',
            customer_since=None,
            lead_source='website',
            contact_metadata=factory.LazyFunction(lambda: {
                'campaign_source': 'Q1-2025-crack-repair',
                'utm_campaign': 'foundation-repair-ppc',
                'preferred_contact_method': 'email'
            })
        )
        
        # Trait: Established customer with history
        is_established_customer = factory.Trait(
            customer_type='customer',
            customer_since=factory.LazyFunction(lambda: DateTimeProvider.recent_date(730)),  # 2 years back
            total_sales=factory.LazyFunction(lambda: round(random.uniform(10000, 75000), 2)),
            outstanding_balance=factory.LazyFunction(lambda: round(random.uniform(0, 2000), 2)),
            payment_terms='Net 30',
            credit_limit=25000.00
        )
        
        # Trait: Contact with QuickBooks integration
        has_quickbooks = factory.Trait(
            quickbooks_customer_id=factory.LazyFunction(lambda: fake.uuid4()[:20]),
            quickbooks_sync_token=factory.LazyFunction(lambda: str(random.randint(1, 100))),
            customer_type='customer'
        )
        
        # Trait: Mobile-first contact (prefers SMS)
        is_mobile_first = factory.Trait(
            phone=factory.LazyFunction(PhoneProvider.mobile_phone),
            contact_metadata=factory.LazyFunction(lambda: {
                'preferred_contact_method': 'text',
                'best_time_to_call': 'evening',
                'mobile_carrier': random.choice(['Verizon', 'AT&T', 'T-Mobile', 'Sprint'])
            })
        )
    
    @classmethod
    def with_property(cls, property_address=None, **kwargs):
        """Create contact with associated property"""
        from .property_factory import PropertyFactory
        contact = cls.create(**kwargs)
        property_kwargs = {'contact': contact}
        if property_address:
            property_kwargs['address'] = property_address
        property_obj = PropertyFactory.create(**property_kwargs)
        return contact, property_obj
    
    @classmethod
    def with_full_history(cls, **kwargs):
        """Create contact with complete business history (property, jobs, quotes, invoices)"""
        from .property_factory import PropertyFactory
        from .job_factory import JobFactory
        from .quote_factory import QuoteFactory
        from .invoice_factory import InvoiceFactory
        
        # Create the contact
        contact = cls.create(is_established_customer=True, **kwargs)
        
        # Create property
        property_obj = PropertyFactory.create(contact=contact)
        
        # Create 1-3 jobs with quotes and invoices
        jobs = JobFactory.create_batch(random.randint(1, 3), property=property_obj)
        
        for job in jobs:
            # Each job has a quote
            quote = QuoteFactory.create(job=job)
            
            # 70% chance the job has an invoice (was accepted)
            if random.random() < 0.7:
                InvoiceFactory.create(job=job, quote=quote)
        
        return contact
    
    @classmethod
    def create_campaign_list(cls, size=50, list_name="Test Campaign List"):
        """Create a list of contacts suitable for campaign testing"""
        contacts = []
        
        # Mix of prospect and customer types
        for i in range(size):
            if i < size * 0.6:  # 60% prospects
                contact = cls.create(is_new_prospect=True)
            elif i < size * 0.9:  # 30% established customers  
                contact = cls.create(is_established_customer=True)
            else:  # 10% mobile-first
                contact = cls.create(is_mobile_first=True)
            contacts.append(contact)
        
        return contacts