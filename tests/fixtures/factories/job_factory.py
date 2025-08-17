"""
Job Factory for Test Data Generation

Provides factories for generating realistic Job model instances
with proper relationships to properties and realistic construction descriptions.
"""

import factory
from crm_database import Job
from .base import BaseFactory, BusinessProvider, DateTimeProvider
from datetime import datetime
import random


class JobFactory(BaseFactory):
    """Factory for generating Job test instances with realistic construction job data"""
    
    class Meta:
        model = Job
    
    # Generate realistic job descriptions
    description = factory.LazyFunction(BusinessProvider.job_description)
    status = factory.fuzzy.FuzzyChoice(['Active', 'Completed', 'On Hold', 'Cancelled'])
    
    # Complete jobs have completion dates
    completed_at = factory.LazyAttribute(
        lambda obj: DateTimeProvider.recent_datetime(60) if obj.status == 'Completed' else None
    )
    
    # Associate with a property (required)
    property = factory.SubFactory('tests.fixtures.factories.property_factory.PropertyFactory')
    
    # Factory traits for different job scenarios
    class Params:
        # Trait: Active job (in progress)
        is_active = factory.Trait(
            status='Active',
            completed_at=None,
            description=factory.LazyFunction(lambda: f"Ongoing {BusinessProvider.service_description().lower()}")
        )
        
        # Trait: Completed job with recent completion
        is_completed = factory.Trait(
            status='Completed',
            completed_at=factory.LazyFunction(lambda: DateTimeProvider.recent_datetime(30))
        )
        
        # Trait: Emergency/urgent job
        is_emergency = factory.Trait(
            status='Active',
            description=factory.LazyFunction(lambda: f"EMERGENCY: {BusinessProvider.service_description()}")
        )
        
        # Trait: Large commercial job
        is_large_commercial = factory.Trait(
            description=factory.LazyFunction(lambda: f"Commercial {random.choice(['foundation', 'structural', 'waterproofing'])} project - {random.randint(5000, 20000)} sq ft")
        )
    
    @classmethod
    def with_quotes_and_invoices(cls, **kwargs):
        """Create job with associated quotes and invoices"""
        from .quote_factory import QuoteFactory
        from .invoice_factory import InvoiceFactory
        
        job = cls.create(**kwargs)
        
        # Create 1-2 quotes
        quotes = QuoteFactory.create_batch(random.randint(1, 2), job=job)
        
        # If job is completed, create invoices
        invoices = []
        if job.status == 'Completed':
            for quote in quotes:
                # 80% chance each quote becomes an invoice
                if random.random() < 0.8:
                    invoice = InvoiceFactory.create(job=job, quote=quote)
                    invoices.append(invoice)
        
        return job, quotes, invoices
    
    @classmethod
    def create_project_timeline(cls, property_obj, phases=None):
        """Create a multi-phase project with jobs in sequence"""
        if phases is None:
            phases = [
                "Site assessment and evaluation",
                "Foundation crack repair",
                "Waterproofing application",
                "Final inspection and cleanup"
            ]
        
        jobs = []
        base_date = DateTimeProvider.recent_datetime(90)
        
        for i, phase_desc in enumerate(phases):
            # Each phase starts after the previous one
            if i == 0:
                status = 'Completed'
                completed_date = base_date
            elif i == len(phases) - 1:
                status = 'Active'
                completed_date = None
            else:
                status = random.choice(['Completed', 'Active'])
                completed_date = DateTimeProvider.recent_datetime(60) if status == 'Completed' else None
            
            job = cls.create(
                property=property_obj,
                description=phase_desc,
                status=status,
                completed_at=completed_date
            )
            jobs.append(job)
        
        return jobs