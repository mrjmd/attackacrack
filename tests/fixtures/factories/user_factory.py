"""
User Factory for Test Data Generation

Provides factories for generating realistic User model instances
with proper authentication and role assignments.
"""

import factory
from crm_database import User
from .base import BaseFactory, DateTimeProvider, fake
from flask_bcrypt import generate_password_hash
import random


class UserFactory(BaseFactory):
    """Factory for generating User test instances with realistic user data"""
    
    class Meta:
        model = User
    
    # User identification
    first_name = factory.Faker('first_name')
    last_name = factory.Faker('last_name')
    email = factory.LazyAttribute(lambda obj: f'{obj.first_name.lower()}.{obj.last_name.lower()}@attackacrack.com')
    
    # Default password hash for 'password123'
    password_hash = factory.LazyFunction(lambda: generate_password_hash('password123').decode('utf-8'))
    
    # Role assignment
    role = factory.fuzzy.FuzzyChoice(['admin', 'marketer'])
    is_active = True
    
    # Timestamps
    created_at = factory.LazyFunction(lambda: DateTimeProvider.recent_datetime(365))
    last_login = factory.LazyAttribute(lambda obj: DateTimeProvider.recent_datetime(7) if random.random() < 0.8 else None)
    
    # Legacy OpenPhone field (for some users)
    openphone_user_id = factory.Maybe(
        'role',
        yes_declaration=factory.LazyFunction(lambda: fake.uuid4()[:15]),
        no_declaration=None
    )
    
    # Factory traits for different user scenarios
    class Params:
        # Trait: Admin user with full access
        is_admin = factory.Trait(
            role='admin',
            email=factory.LazyAttribute(lambda obj: f'admin.{obj.first_name.lower()}@attackacrack.com'),
            openphone_user_id=factory.LazyFunction(lambda: fake.uuid4()[:15])
        )
        
        # Trait: Marketer user 
        is_marketer = factory.Trait(
            role='marketer',
            email=factory.LazyAttribute(lambda obj: f'marketing.{obj.first_name.lower()}@attackacrack.com')
        )
        
        # Trait: Inactive user
        is_inactive = factory.Trait(
            is_active=False,
            last_login=None
        )
        
        # Trait: New user (recently created)
        is_new = factory.Trait(
            created_at=factory.LazyFunction(lambda: DateTimeProvider.recent_datetime(7)),
            last_login=None
        )
    
    @classmethod
    def create_with_password(cls, password='password123', **kwargs):
        """Create user with specific password"""
        password_hash = generate_password_hash(password).decode('utf-8')
        return cls.create(password_hash=password_hash, **kwargs)
    
    @classmethod
    def create_admin_user(cls, **kwargs):
        """Create admin user with default admin settings"""
        return cls.create(
            is_admin=True,
            first_name='Admin',
            last_name='User',
            email='admin@attackacrack.com',
            **kwargs
        )
    
    @classmethod
    def create_test_users(cls):
        """Create a set of test users for different scenarios"""
        users = {}
        
        # Admin user
        users['admin'] = cls.create_admin_user()
        
        # Regular marketer
        users['marketer'] = cls.create(
            is_marketer=True,
            first_name='Marketing',
            last_name='User',
            email='marketer@attackacrack.com'
        )
        
        # Inactive user
        users['inactive'] = cls.create(
            is_inactive=True,
            first_name='Inactive',
            last_name='User',
            email='inactive@attackacrack.com'
        )
        
        # New user
        users['new'] = cls.create(
            is_new=True,
            first_name='New',
            last_name='User',
            email='new@attackacrack.com'
        )
        
        return users