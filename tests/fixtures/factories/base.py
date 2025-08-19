"""
Base Factory Class for Attack-a-Crack CRM Test Data Generation

This module provides the base factory class and common utilities for generating
realistic test data across all CRM models.
"""

# import factory  # Not installed

# Mock factory module
class factory:
    class Sequence:
        def __init__(self, func):
            self.func = func
    
    class LazyAttribute:
        def __init__(self, func):
            self.func = func
    
    @staticmethod
    def Faker(method_name):
        return lambda: f"fake_{method_name}"
# from factory.alchemy import SQLAlchemyModelFactory  # Not installed
# from faker import Faker  # Not installed

# Placeholder classes
class SQLAlchemyModelFactory:
    pass

class FakerClass:
    def __init__(self, *args, **kwargs):
        pass
    def name(self):
        return "Test Name"
    def email(self):
        return "test@example.com"
    def phone_number(self):
        return "555-1234"
    def address(self):
        return "123 Test St"

Faker = FakerClass
from extensions import db
from datetime import datetime, date, time, timedelta
import random

# Initialize Faker with US locale for realistic US addresses and phone numbers
fake = Faker('en_US')

class BaseFactory(SQLAlchemyModelFactory):
    """
    Base factory class for all CRM model factories.
    Provides common functionality and database session management.
    """
    
    class Meta:
        abstract = True
        sqlalchemy_session = db.session
        sqlalchemy_session_persistence = "commit"
    
    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        """Override create to handle session management properly"""
        obj = model_class(*args, **kwargs)
        cls._meta.sqlalchemy_session.add(obj)
        cls._meta.sqlalchemy_session.commit()
        return obj
    
    @classmethod
    def create_batch_with_session(cls, size, session=None, **kwargs):
        """
        Create a batch of objects and add them to the specified session.
        If no session provided, uses the default session.
        """
        if session:
            original_session = cls._meta.sqlalchemy_session
            cls._meta.sqlalchemy_session = session
        
        try:
            objects = cls.create_batch(size, **kwargs)
            return objects
        finally:
            if session:
                cls._meta.sqlalchemy_session = original_session
    
    @classmethod
    def build_batch_with_session(cls, size, session=None, **kwargs):
        """
        Build a batch of objects (without saving) for manual session management.
        """
        objects = cls.build_batch(size, **kwargs)
        if session:
            for obj in objects:
                session.add(obj)
        return objects


class USAddressProvider:
    """Provider for realistic US real estate addresses"""
    
    @staticmethod
    def street_address():
        """Generate realistic street address"""
        return fake.street_address()
    
    @staticmethod
    def real_estate_address():
        """Generate address formatted for real estate context"""
        return f"{fake.building_number()} {fake.street_name()} {fake.street_suffix()}"
    
    @staticmethod
    def full_address():
        """Generate full address with city, state, zip"""
        return f"{USAddressProvider.real_estate_address()}, {fake.city()}, {fake.state_abbr()} {fake.zipcode()}"


class PhoneProvider:
    """Provider for realistic US phone numbers"""
    
    @staticmethod
    def us_phone():
        """Generate realistic US phone number in E.164 format"""
        area_code = random.choice(['555', '415', '650', '707', '510', '408', '925', '831'])
        exchange = random.randint(200, 999)
        number = random.randint(1000, 9999)
        return f"+1{area_code}{exchange}{number}"
    
    @staticmethod
    def mobile_phone():
        """Generate mobile phone number (higher probability of modern area codes)"""
        area_code = random.choice(['555', '415', '650', '707', '510', '408'])
        exchange = random.randint(200, 999)
        number = random.randint(1000, 9999)
        return f"+1{area_code}{exchange}{number}"


class BusinessProvider:
    """Provider for real estate business context"""
    
    PROPERTY_TYPES = [
        'residential', 'commercial', 'industrial', 'retail', 'office', 
        'warehouse', 'mixed_use', 'land'
    ]
    
    LEAD_SOURCES = [
        'website', 'referral', 'cold-call', 'email_campaign', 'social_media',
        'walk_in', 'trade_show', 'google_ads', 'yelp', 'craigslist'
    ]
    
    CUSTOMER_TYPES = ['prospect', 'customer', 'former_customer']
    
    SERVICE_DESCRIPTIONS = [
        'Foundation crack repair', 'Basement waterproofing', 'Structural repair',
        'Concrete leveling', 'Crack injection', 'French drain installation',
        'Sump pump installation', 'Wall stabilization', 'Floor leveling'
    ]
    
    @staticmethod
    def property_type():
        return random.choice(BusinessProvider.PROPERTY_TYPES)
    
    @staticmethod
    def lead_source():
        return random.choice(BusinessProvider.LEAD_SOURCES)
    
    @staticmethod
    def customer_type():
        return random.choice(BusinessProvider.CUSTOMER_TYPES)
    
    @staticmethod
    def service_description():
        return random.choice(BusinessProvider.SERVICE_DESCRIPTIONS)
    
    @staticmethod
    def job_description():
        """Generate realistic job description for construction/repair work"""
        service = BusinessProvider.service_description()
        location = random.choice(['basement', 'foundation', 'crawl space', 'garage', 'exterior'])
        severity = random.choice(['minor', 'moderate', 'severe', 'extensive'])
        return f"{severity.title()} {service.lower()} needed in {location}"


class DateTimeProvider:
    """Provider for realistic date/time generation"""
    
    @staticmethod
    def recent_date(days_back=30):
        """Generate date within last N days"""
        return fake.date_between(start_date=f'-{days_back}d', end_date='today')
    
    @staticmethod
    def future_date(days_ahead=90):
        """Generate future date within N days"""
        return fake.date_between(start_date='today', end_date=f'+{days_ahead}d')
    
    @staticmethod
    def business_hours_time():
        """Generate time during business hours (8 AM - 6 PM)"""
        hour = random.randint(8, 17)
        minute = random.choice([0, 15, 30, 45])
        return time(hour, minute)
    
    @staticmethod
    def recent_datetime(days_back=30):
        """Generate datetime within last N days"""
        return fake.date_time_between(start_date=f'-{days_back}d', end_date='now')
    
    @staticmethod
    def future_datetime(days_ahead=90):
        """Generate future datetime within N days"""
        return fake.date_time_between(start_date='now', end_date=f'+{days_ahead}d')


class FinancialProvider:
    """Provider for realistic financial data"""
    
    @staticmethod
    def service_price():
        """Generate realistic service pricing ($500 - $15,000)"""
        base_prices = [500, 750, 1000, 1500, 2500, 3500, 5000, 7500, 10000, 15000]
        return random.choice(base_prices) + random.randint(0, 500)
    
    @staticmethod
    def hourly_rate():
        """Generate realistic hourly rate ($75 - $200)"""
        return random.randint(75, 200)
    
    @staticmethod
    def tax_rate():
        """Generate realistic tax rate (6% - 10%)"""
        return round(random.uniform(0.06, 0.10), 3)
    
    @staticmethod
    def payment_terms():
        """Generate common payment terms"""
        return random.choice(['Net 30', 'Net 15', 'Due on receipt', 'Net 60', '2/10 Net 30'])


# Factory traits for common scenarios
class FactoryTraits:
    """Common factory traits and mixins"""
    
    @staticmethod
    def with_timestamps():
        """Add realistic created/updated timestamps"""
        created = DateTimeProvider.recent_datetime(90)
        return {
            'created_at': created,
            'updated_at': fake.date_time_between(start_date=created, end_date='now')
        }
    
    @staticmethod
    def as_new_customer():
        """Customer acquired recently"""
        return {
            'customer_type': 'customer',
            'customer_since': DateTimeProvider.recent_date(30),
            'lead_source': BusinessProvider.lead_source()
        }
    
    @staticmethod
    def as_prospect():
        """Potential customer, not yet converted"""
        return {
            'customer_type': 'prospect',
            'customer_since': None,
            'lead_source': BusinessProvider.lead_source()
        }
    
    @staticmethod
    def with_quickbooks_sync():
        """Add QuickBooks integration fields"""
        return {
            'quickbooks_customer_id': fake.uuid4()[:20],
            'quickbooks_sync_token': str(random.randint(1, 100))
        }