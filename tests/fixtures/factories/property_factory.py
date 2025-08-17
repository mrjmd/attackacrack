"""
Property Factory for Test Data Generation

Provides factories for generating realistic Property model instances
with proper relationships to contacts.
"""

import factory
from crm_database import Property
from .base import BaseFactory, USAddressProvider, BusinessProvider
import random


class PropertyFactory(BaseFactory):
    """Factory for generating Property test instances with realistic addresses"""
    
    class Meta:
        model = Property
    
    # Generate realistic property addresses
    address = factory.LazyFunction(USAddressProvider.full_address)
    property_type = factory.LazyFunction(BusinessProvider.property_type)
    
    # Associate with a contact (required)
    contact = factory.SubFactory('tests.fixtures.factories.contact_factory.ContactFactory')
    
    # Factory traits for different property scenarios
    class Params:
        # Trait: Residential property
        is_residential = factory.Trait(
            property_type='residential',
            address=factory.LazyFunction(lambda: f"{random.randint(100, 9999)} {random.choice(['Oak', 'Maple', 'Pine', 'Cedar', 'Elm'])} {random.choice(['St', 'Ave', 'Dr', 'Ln', 'Ct'])}")
        )
        
        # Trait: Commercial property
        is_commercial = factory.Trait(
            property_type='commercial',
            address=factory.LazyFunction(lambda: f"{random.randint(100, 9999)} {random.choice(['Main', 'Business', 'Commerce', 'Industrial', 'Corporate'])} {random.choice(['Blvd', 'Ave', 'Dr', 'Pkwy'])}")
        )
        
        # Trait: Industrial property
        is_industrial = factory.Trait(
            property_type='industrial',
            address=factory.LazyFunction(lambda: f"{random.randint(1000, 9999)} {random.choice(['Industrial', 'Manufacturing', 'Warehouse', 'Distribution'])} {random.choice(['Way', 'Blvd', 'Dr', 'Pkwy'])}")
        )
    
    @classmethod
    def with_jobs(cls, job_count=None, **kwargs):
        """Create property with associated jobs"""
        from .job_factory import JobFactory
        
        property_obj = cls.create(**kwargs)
        
        if job_count is None:
            job_count = random.randint(1, 3)
        
        jobs = JobFactory.create_batch(job_count, property=property_obj)
        return property_obj, jobs
    
    @classmethod
    def create_multi_property_contact(cls, property_count=None, **contact_kwargs):
        """Create a contact with multiple properties (commercial client)"""
        from .contact_factory import ContactFactory
        
        # Create a commercial/established customer
        contact = ContactFactory.create(
            is_established_customer=True,
            customer_type='customer',
            **contact_kwargs
        )
        
        if property_count is None:
            property_count = random.randint(2, 5)
        
        properties = []
        for i in range(property_count):
            # Mix of property types for multi-property clients
            if i == 0:
                prop = cls.create(contact=contact, is_commercial=True)
            elif i < property_count * 0.7:
                prop = cls.create(contact=contact, property_type='commercial')
            else:
                prop = cls.create(contact=contact, property_type='industrial')
            properties.append(prop)
        
        return contact, properties