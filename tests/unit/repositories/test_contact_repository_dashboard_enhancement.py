"""
Tests for ContactRepository dashboard-specific methods
These tests are written FIRST (TDD RED phase) before implementing the methods
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
from sqlalchemy import func
from repositories.contact_repository import ContactRepository
from crm_database import Contact, Activity
from tests.conftest import create_test_contact


class TestContactRepositoryDashboardEnhancements:
    """Test dashboard-specific methods for ContactRepository"""
    
    @pytest.fixture
    def repository(self, db_session):
        """Create ContactRepository instance"""
        return ContactRepository(session=db_session, model_class=Contact)
    
    def test_get_total_contacts_count(self, repository, db_session):
        """Test getting total count of contacts"""
        # Arrange - get initial count
        initial_count = repository.get_total_contacts_count()
        
        # Create test contacts
        contact1 = create_test_contact(phone='+11234567890', first_name='Test1')
        contact2 = create_test_contact(phone='+11234567891', first_name='Test2')
        db_session.add_all([contact1, contact2])
        db_session.commit()
        
        # Act
        result = repository.get_total_contacts_count()
        
        # Assert - should have 2 more than initial count
        assert result == initial_count + 2
    
    def test_get_contacts_added_this_week_count(self, repository, db_session):
        """Test counting contacts added in the last 7 days using Activity proxy"""
        # Arrange - create contacts with recent activities
        contact1 = create_test_contact(phone='+11234567890', first_name='Recent1')
        contact2 = create_test_contact(phone='+11234567891', first_name='Recent2')  
        old_contact = create_test_contact(phone='+11234567892', first_name='Old')
        db_session.add_all([contact1, contact2, old_contact])
        db_session.commit()
        
        # Create recent activities for contact1 and contact2
        recent_date = datetime.utcnow() - timedelta(days=3)
        old_date = datetime.utcnow() - timedelta(days=10)
        
        from crm_database import Activity
        activity1 = Activity(
            contact_id=contact1.id,
            activity_type='message',
            direction='incoming',
            created_at=recent_date
        )
        activity2 = Activity(
            contact_id=contact2.id, 
            activity_type='message',
            direction='incoming',
            created_at=recent_date
        )
        activity_old = Activity(
            contact_id=old_contact.id,
            activity_type='message', 
            direction='incoming',
            created_at=old_date
        )
        db_session.add_all([activity1, activity2, activity_old])
        db_session.commit()
        
        # Act
        result = repository.get_contacts_added_this_week_count()
        
        # Assert
        assert result == 2
    
    def test_get_data_quality_stats(self, repository, db_session):
        """Test getting contact data quality statistics"""
        # Arrange - get initial counts
        initial_stats = repository.get_data_quality_stats()
        
        # Create contacts with varying data quality
        contact_good_name = create_test_contact(
            phone='+11234567890',
            first_name='John',
            email='john@example.com'
        )
        contact_phone_number_name = create_test_contact(
            phone='+11234567891',
            first_name='+11234567891',  # Phone number as name (bad quality)
            email=None
        )
        contact_no_email = create_test_contact(
            phone='+11234567892',
            first_name='Jane',
            email=None
        )
        contact_empty_email = create_test_contact(
            phone='+11234567893', 
            first_name='Bob',
            email=''
        )
        
        db_session.add_all([
            contact_good_name,
            contact_phone_number_name, 
            contact_no_email,
            contact_empty_email
        ])
        db_session.commit()
        
        # Act
        result = repository.get_data_quality_stats()
        
        # Assert - check the increase
        assert result['total_contacts'] == initial_stats['total_contacts'] + 4
        assert result['contacts_with_names'] == initial_stats['contacts_with_names'] + 3  # Exclude phone number names
        assert result['contacts_with_emails'] == initial_stats['contacts_with_emails'] + 1  # Only non-null, non-empty emails
        
        # Check that the data quality logic works (focus on the logic, not exact score)
        assert 'data_quality_score' in result
        assert isinstance(result['data_quality_score'], int)
        assert 0 <= result['data_quality_score'] <= 100
        
    def test_get_data_quality_stats_empty_database(self, repository):
        """Test data quality stats with no contacts"""
        # Act  
        result = repository.get_data_quality_stats()
        
        # Assert
        assert result['total_contacts'] == 0
        assert result['contacts_with_names'] == 0
        assert result['contacts_with_emails'] == 0
        assert result['data_quality_score'] == 0
    
    def test_get_contacts_with_names_excludes_phone_numbers(self, repository, db_session):
        """Test that contacts with phone numbers as names are excluded from name count"""
        # Arrange
        good_contact = create_test_contact(phone='+11234567890', first_name='John')
        phone_as_name1 = create_test_contact(phone='+11234567891', first_name='+11234567891')
        phone_as_name2 = create_test_contact(phone='+11234567892', first_name='+1 (123) 456-7892')
        
        db_session.add_all([good_contact, phone_as_name1, phone_as_name2])
        db_session.commit()
        
        # Act
        result = repository.get_contacts_with_names_count()
        
        # Assert  
        assert result == 1  # Only 'John' should count
    
    def test_get_contacts_with_emails_count(self, repository, db_session):
        """Test counting contacts with valid email addresses"""
        # Arrange
        contact_with_email = create_test_contact(
            phone='+11234567890',
            email='test@example.com'
        )
        contact_no_email = create_test_contact(
            phone='+11234567891',
            email=None
        )
        contact_empty_email = create_test_contact(
            phone='+11234567892', 
            email=''
        )
        
        db_session.add_all([contact_with_email, contact_no_email, contact_empty_email])
        db_session.commit()
        
        # Act
        result = repository.get_contacts_with_emails_count()
        
        # Assert
        assert result == 1  # Only non-null, non-empty email counts