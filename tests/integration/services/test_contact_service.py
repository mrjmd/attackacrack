# tests/test_contact_service_improved.py
"""
Improved comprehensive tests for ContactService following enterprise standards with Result pattern.
"""

import pytest
from unittest.mock import MagicMock, patch, Mock
from services.contact_service_refactored import ContactService
from services.common.result import Result
from crm_database import Contact
from repositories.contact_repository import ContactRepository
from repositories.campaign_repository import CampaignRepository
from repositories.contact_flag_repository import ContactFlagRepository
import time


@pytest.fixture
def contact_service(db_session):
    """Fixture to provide ContactService instance with real repositories"""
    from crm_database import Contact, Campaign, ContactFlag
    
    contact_repo = ContactRepository(session=db_session, model_class=Contact)
    campaign_repo = CampaignRepository(session=db_session, model_class=Campaign)
    contact_flag_repo = ContactFlagRepository(session=db_session, model_class=ContactFlag)
    
    return ContactService(
        contact_repository=contact_repo,
        campaign_repository=campaign_repo,
        contact_flag_repository=contact_flag_repo
    )


@pytest.fixture
def unique_contact_data():
    """Fixture providing unique contact data to avoid conflicts"""
    timestamp = str(int(time.time() * 1000000))[-6:]
    return {
        'first_name': f'John{timestamp}',
        'last_name': f'Doe{timestamp}', 
        'email': f'john{timestamp}@example.com',
        'phone': f'+155500{timestamp}'
    }


class TestContactCRUDOperations:
    """Test Contact CRUD operations with proper isolation"""
    
    def test_add_contact_success(self, contact_service, unique_contact_data, db_session):
        """Test successful contact creation with all fields"""
        # Arrange
        contact_data = unique_contact_data
        
        # Act
        result = contact_service.add_contact(**contact_data)
        
        # Assert
        assert result.is_success
        assert result.data is not None
        
        # Result.data contains the Contact model instance
        contact = result.data
        assert contact.id is not None
        assert contact.first_name == contact_data['first_name']
        assert contact.last_name == contact_data['last_name']
        assert contact.email == contact_data['email']
        assert contact.phone == contact_data['phone']
        
        # Verify database persistence
        retrieved_contact = db_session.get(Contact, contact.id)
        assert retrieved_contact is not None
        assert retrieved_contact.email == contact_data['email']
    
    def test_add_contact_minimal_data(self, contact_service, db_session):
        """Test contact creation with minimal required data"""
        timestamp = str(int(time.time() * 1000000))[-6:]
        
        # Required fields per actual API
        result = contact_service.add_contact(
            first_name=f'Minimal{timestamp}',
            last_name=f'Last{timestamp}',
            phone=f'+155501{timestamp}'
        )
        
        assert result.is_success
        contact = result.data
        assert contact is not None
        assert contact.first_name == f'Minimal{timestamp}'
        assert contact.last_name == f'Last{timestamp}'
        assert contact.phone == f'+155501{timestamp}'
        assert contact.email is None
    
    def test_add_contact_duplicate_phone(self, contact_service, unique_contact_data):
        """Test that duplicate phone numbers are handled appropriately"""
        # Create first contact
        first_result = contact_service.add_contact(**unique_contact_data)
        assert first_result.is_success
        
        # Try to create another with same phone
        second_result = contact_service.add_contact(
            first_name='Different',
            last_name='Name',
            email='different@example.com',
            phone=unique_contact_data['phone']  # Same phone
        )
        
        # Should return failure with duplicate error
        assert second_result.is_failure
        assert second_result.error_code == "DUPLICATE_PHONE"
    
    def test_get_all_contacts(self, contact_service, unique_contact_data):
        """Test retrieving all contacts"""
        # Get initial count
        initial_result = contact_service.get_all_contacts()
        assert initial_result.is_success
        initial_count = len(initial_result.data)
        
        # Add known contact
        add_result = contact_service.add_contact(**unique_contact_data)
        assert add_result.is_success
        
        # Verify count increased
        all_result = contact_service.get_all_contacts()
        assert all_result.is_success
        all_contacts = all_result.data
        assert len(all_contacts) == initial_count + 1
        
        # Verify our contact is in the list
        contact_emails = [c.email for c in all_contacts if c.email]
        assert unique_contact_data['email'] in contact_emails
    
    def test_get_contact_by_id_success(self, contact_service, unique_contact_data):
        """Test successful contact retrieval by ID"""
        # Create contact
        create_result = contact_service.add_contact(**unique_contact_data)
        assert create_result.is_success
        created_contact = create_result.data
        
        # Retrieve by ID
        get_result = contact_service.get_contact_by_id(created_contact.id)
        
        assert get_result.is_success
        retrieved_contact = get_result.data
        assert retrieved_contact is not None
        assert retrieved_contact.id == created_contact.id
        assert retrieved_contact.email == unique_contact_data['email']
    
    def test_get_contact_by_id_not_found(self, contact_service):
        """Test contact retrieval with non-existent ID"""
        result = contact_service.get_contact_by_id(999999)
        assert result.is_failure
        assert result.error_code == "NOT_FOUND"
    
    def test_get_contact_by_phone_success(self, contact_service, unique_contact_data):
        """Test successful contact retrieval by phone"""
        # Create contact
        create_result = contact_service.add_contact(**unique_contact_data)
        assert create_result.is_success
        
        # Retrieve by phone
        get_result = contact_service.get_contact_by_phone(unique_contact_data['phone'])
        
        assert get_result.is_success
        retrieved_contact = get_result.data
        assert retrieved_contact is not None
        assert retrieved_contact.phone == unique_contact_data['phone']
        assert retrieved_contact.email == unique_contact_data['email']
    
    def test_get_contact_by_phone_not_found(self, contact_service):
        """Test contact retrieval with non-existent phone"""
        result = contact_service.get_contact_by_phone('+1555999999')
        assert result.is_failure
        assert result.error_code == "NOT_FOUND"
    
    def test_update_contact_success(self, contact_service, unique_contact_data):
        """Test successful contact update"""
        # Create contact
        create_result = contact_service.add_contact(**unique_contact_data)
        assert create_result.is_success
        contact = create_result.data
        
        # Update data
        update_data = {
            'first_name': 'UpdatedFirst',
            'email': 'updated@example.com'
        }
        
        # Update contact
        update_result = contact_service.update_contact(contact.id, **update_data)
        
        assert update_result.is_success
        updated_contact = update_result.data
        assert updated_contact is not None
        assert updated_contact.first_name == 'UpdatedFirst'
        assert updated_contact.email == 'updated@example.com'
        # Unchanged fields should remain
        assert updated_contact.last_name == unique_contact_data['last_name']
        assert updated_contact.phone == unique_contact_data['phone']
    
    def test_update_contact_not_found(self, contact_service):
        """Test updating non-existent contact"""
        result = contact_service.update_contact(999999, first_name='NotFound')
        assert result.is_failure
        assert result.error_code == "NOT_FOUND"
    
    def test_delete_contact_success(self, contact_service, unique_contact_data, db_session):
        """Test successful contact deletion"""
        # Create contact
        create_result = contact_service.add_contact(**unique_contact_data)
        assert create_result.is_success
        contact = create_result.data
        contact_id = contact.id
        
        # Get initial count
        initial_result = contact_service.get_all_contacts()
        assert initial_result.is_success
        initial_count = len(initial_result.data)
        
        # Delete contact
        delete_result = contact_service.delete_contact(contact_id)
        assert delete_result.is_success
        
        # Verify deletion
        after_delete_result = contact_service.get_all_contacts()
        assert after_delete_result.is_success
        assert len(after_delete_result.data) == initial_count - 1
        assert db_session.get(Contact, contact_id) is None
        
        # Verify contact not found
        get_result = contact_service.get_contact_by_id(contact_id)
        assert get_result.is_failure
    
    def test_delete_contact_not_found(self, contact_service):
        """Test deleting non-existent contact"""
        initial_result = contact_service.get_all_contacts()
        assert initial_result.is_success
        initial_count = len(initial_result.data)
        
        # Should return failure for non-existent contact
        delete_result = contact_service.delete_contact(999999)
        assert delete_result.is_failure
        assert delete_result.error_code == "NOT_FOUND"
        
        # Count should remain the same
        after_result = contact_service.get_all_contacts()
        assert after_result.is_success
        assert len(after_result.data) == initial_count


class TestContactValidation:
    """Test contact data validation and business rules"""
    
    def test_phone_number_normalization(self, contact_service):
        """Test that phone numbers are stored consistently"""
        timestamp = str(int(time.time() * 1000000))[-6:]
        
        # Test various phone formats
        phone_formats = [
            f'555{timestamp}',
            f'(555) {timestamp}',
            f'+1555{timestamp}',
            f'1-555-{timestamp}',
        ]
        
        contacts = []
        for i, phone in enumerate(phone_formats):
            result = contact_service.add_contact(
                first_name=f'Test{i}',
                last_name=f'User{i}',
                phone=phone
            )
            contacts.append(result)
        
        # All should be stored (no validation currently, but documenting behavior)
        assert len(contacts) == 4
        for result in contacts:
            assert result.is_success
            contact = result.data
            assert contact.phone is not None
    
    def test_email_validation_behavior(self, contact_service):
        """Test email validation behavior"""
        timestamp = str(int(time.time() * 1000000))[-6:]
        
        # Test various email formats
        test_emails = [
            f'valid{timestamp}@example.com',
            f'also.valid{timestamp}@test.co.uk',
            # Note: Currently no email validation in ContactService
            # This test documents current behavior
        ]
        
        for i, email in enumerate(test_emails):
            result = contact_service.add_contact(
                first_name=f'EmailTest{i}',
                last_name=f'TestUser{i}',
                phone=f'+155502{timestamp}{i}',
                email=email
            )
            assert result.is_success
            contact = result.data
            assert contact.email == email


class TestContactErrorHandling:
    """Test error handling scenarios"""
    
    def test_add_contact_database_error(self, contact_service):
        """Test handling of database errors during contact creation"""
        # Mock repository to raise an error
        with patch.object(contact_service.contact_repository, 'create') as mock_create:
            mock_create.side_effect = Exception("Database error")
            
            result = contact_service.add_contact(
                first_name='Error',
                last_name='Test',
                phone='+1555000000'
            )
            
            assert result.is_failure
            assert "Database error" in result.error
    
    def test_update_contact_with_invalid_data(self, contact_service, unique_contact_data):
        """Test update with potentially invalid data"""
        # Create contact
        create_result = contact_service.add_contact(**unique_contact_data)
        assert create_result.is_success
        contact = create_result.data
        
        # Update with potentially problematic data
        # (Current implementation may not validate, but test documents behavior)
        update_result = contact_service.update_contact(
            contact.id,
            first_name='',  # Empty string
            email=None      # Explicit None
        )
        
        assert update_result.is_success
        updated_contact = update_result.data
        assert updated_contact is not None
        assert updated_contact.first_name == ''
        assert updated_contact.email is None


class TestContactBusinessLogic:
    """Test business logic and integration scenarios"""
    
    def test_contact_relationship_integrity(self, contact_service, unique_contact_data, db_session):
        """Test that contact relationships are maintained properly"""
        # Create contact
        create_result = contact_service.add_contact(**unique_contact_data)
        assert create_result.is_success
        contact = create_result.data
        
        # This would test relationships with properties, appointments, etc.
        # For now, just verify the contact exists and can be queried
        get_result = contact_service.get_contact_by_id(contact.id)
        assert get_result.is_success
        retrieved = get_result.data
        assert retrieved is not None
        assert retrieved.id == contact.id
    
    def test_contact_search_functionality(self, contact_service):
        """Test contact search capabilities"""
        timestamp = str(int(time.time() * 1000000))[-6:]
        
        # Create contacts with searchable data
        search_contacts = [
            {'first_name': f'Alice{timestamp}', 'last_name': 'Johnson', 'phone': f'+155503{timestamp}1'},
            {'first_name': f'Bob{timestamp}', 'last_name': 'Smith', 'phone': f'+155503{timestamp}2'},
            {'first_name': f'Charlie{timestamp}', 'last_name': 'Johnson', 'phone': f'+155503{timestamp}3'},
        ]
        
        created_contacts = []
        for contact_data in search_contacts:
            result = contact_service.add_contact(**contact_data)
            assert result.is_success
            created_contacts.append(result.data)
        
        # Test searching by last name (if search functionality exists)
        # This documents current capabilities
        all_result = contact_service.get_all_contacts()
        assert all_result.is_success
        all_contacts = all_result.data
        johnson_contacts = [c for c in all_contacts if c.last_name == 'Johnson']
        assert len(johnson_contacts) >= 2  # At least our test contacts
    
    def test_concurrent_contact_operations(self, contact_service):
        """Test concurrent contact operations"""
        timestamp = str(int(time.time() * 1000000))[-6:]
        
        # Create contact
        create_result = contact_service.add_contact(
            first_name=f'Concurrent{timestamp}',
            last_name=f'User{timestamp}',
            phone=f'+155504{timestamp}'
        )
        assert create_result.is_success
        contact = create_result.data
        
        # Simulate concurrent read and update
        get_result = contact_service.get_contact_by_id(contact.id)
        update_result = contact_service.update_contact(contact.id, last_name='Updated')
        
        assert get_result.is_success
        retrieved = get_result.data
        assert retrieved is not None
        
        assert update_result.is_success
        updated = update_result.data
        assert updated is not None
        assert updated.last_name == 'Updated'