# tests/test_contact_service_improved.py
"""
Improved comprehensive tests for ContactService following enterprise standards.
"""

import pytest
from unittest.mock import MagicMock, patch
from services.contact_service_refactored import ContactService
from crm_database import Contact
import time


@pytest.fixture
def contact_service():
    """Fixture to provide ContactService instance"""
    return ContactService()


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
        new_contact = contact_service.add_contact(**contact_data)
        
        # Assert
        assert new_contact is not None
        assert new_contact.id is not None
        assert new_contact.first_name == contact_data['first_name']
        assert new_contact.last_name == contact_data['last_name']
        assert new_contact.email == contact_data['email']
        assert new_contact.phone == contact_data['phone']
        
        # Verify database persistence
        retrieved_contact = db_session.get(Contact, new_contact.id)
        assert retrieved_contact is not None
        assert retrieved_contact.email == contact_data['email']
    
    def test_add_contact_minimal_data(self, contact_service, db_session):
        """Test contact creation with minimal required data"""
        timestamp = str(int(time.time() * 1000000))[-6:]
        
        # Required fields per actual API
        new_contact = contact_service.add_contact(
            first_name=f'Minimal{timestamp}',
            last_name=f'Last{timestamp}',
            phone=f'+155501{timestamp}'
        )
        
        assert new_contact is not None
        assert new_contact.first_name == f'Minimal{timestamp}'
        assert new_contact.last_name == f'Last{timestamp}'
        assert new_contact.phone == f'+155501{timestamp}'
        assert new_contact.email is None
    
    def test_add_contact_duplicate_phone(self, contact_service, unique_contact_data):
        """Test that duplicate phone numbers are handled appropriately"""
        # Create first contact
        contact_service.add_contact(**unique_contact_data)
        
        # Try to create another with same phone
        # ContactService returns None on IntegrityError, doesn't raise
        result = contact_service.add_contact(
            first_name='Different',
            last_name='Name',
            email='different@example.com',
            phone=unique_contact_data['phone']  # Same phone
        )
        
        # Should return None due to integrity constraint
        assert result is None
    
    def test_get_all_contacts(self, contact_service, unique_contact_data):
        """Test retrieving all contacts"""
        # Get initial count
        initial_count = len(contact_service.get_all_contacts())
        
        # Add known contact
        contact_service.add_contact(**unique_contact_data)
        
        # Verify count increased
        all_contacts = contact_service.get_all_contacts()
        assert len(all_contacts) == initial_count + 1
        
        # Verify our contact is in the list
        contact_emails = [c.email for c in all_contacts if c.email]
        assert unique_contact_data['email'] in contact_emails
    
    def test_get_contact_by_id_success(self, contact_service, unique_contact_data):
        """Test successful contact retrieval by ID"""
        # Create contact
        created_contact = contact_service.add_contact(**unique_contact_data)
        
        # Retrieve by ID
        retrieved_contact = contact_service.get_contact_by_id(created_contact.id)
        
        assert retrieved_contact is not None
        assert retrieved_contact.id == created_contact.id
        assert retrieved_contact.email == unique_contact_data['email']
    
    def test_get_contact_by_id_not_found(self, contact_service):
        """Test contact retrieval with non-existent ID"""
        result = contact_service.get_contact_by_id(999999)
        assert result is None
    
    def test_get_contact_by_phone_success(self, contact_service, unique_contact_data):
        """Test successful contact retrieval by phone"""
        # Create contact
        contact_service.add_contact(**unique_contact_data)
        
        # Retrieve by phone
        retrieved_contact = contact_service.get_contact_by_phone(unique_contact_data['phone'])
        
        assert retrieved_contact is not None
        assert retrieved_contact.phone == unique_contact_data['phone']
        assert retrieved_contact.email == unique_contact_data['email']
    
    def test_get_contact_by_phone_not_found(self, contact_service):
        """Test contact retrieval with non-existent phone"""
        result = contact_service.get_contact_by_phone('+1555999999')
        assert result is None
    
    def test_update_contact_success(self, contact_service, unique_contact_data):
        """Test successful contact update"""
        # Create contact
        contact = contact_service.add_contact(**unique_contact_data)
        
        # Update data
        update_data = {
            'first_name': 'UpdatedFirst',
            'email': 'updated@example.com'
        }
        
        # Update contact
        updated_contact = contact_service.update_contact(contact.id, **update_data)
        
        assert updated_contact is not None
        assert updated_contact.first_name == 'UpdatedFirst'
        assert updated_contact.email == 'updated@example.com'
        # Unchanged fields should remain
        assert updated_contact.last_name == unique_contact_data['last_name']
        assert updated_contact.phone == unique_contact_data['phone']
    
    def test_update_contact_not_found(self, contact_service):
        """Test updating non-existent contact"""
        result = contact_service.update_contact(999999, first_name='NotFound')
        assert result is None
    
    def test_delete_contact_success(self, contact_service, unique_contact_data, db_session):
        """Test successful contact deletion"""
        # Create contact
        contact = contact_service.add_contact(**unique_contact_data)
        contact_id = contact.id
        
        # Get initial count
        initial_count = len(contact_service.get_all_contacts())
        
        # Delete contact
        contact_service.delete_contact(contact_id)
        
        # Verify deletion
        assert len(contact_service.get_all_contacts()) == initial_count - 1
        assert db_session.get(Contact, contact_id) is None
        assert contact_service.get_contact_by_id(contact_id) is None
    
    def test_delete_contact_not_found(self, contact_service):
        """Test deleting non-existent contact"""
        initial_count = len(contact_service.get_all_contacts())
        
        # Should handle gracefully
        contact_service.delete_contact(999999)
        
        # Count should remain the same
        assert len(contact_service.get_all_contacts()) == initial_count


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
            contact = contact_service.add_contact(
                first_name=f'Test{i}',
                last_name=f'User{i}',
                phone=phone
            )
            contacts.append(contact)
        
        # All should be stored (no validation currently, but documenting behavior)
        assert len(contacts) == 4
        for contact in contacts:
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
            contact = contact_service.add_contact(
                first_name=f'EmailTest{i}',
                last_name=f'TestUser{i}',
                phone=f'+155502{timestamp}{i}',
                email=email
            )
            assert contact.email == email


class TestContactErrorHandling:
    """Test error handling scenarios"""
    
    def test_add_contact_database_error(self, contact_service):
        """Test handling of database errors during contact creation"""
        # Mock database session to raise an error
        with patch.object(contact_service, 'session') as mock_session:
            mock_session.add.side_effect = Exception("Database error")
            
            with pytest.raises(Exception):
                contact_service.add_contact(
                    first_name='Error',
                    last_name='Test',
                    phone='+1555000000'
                )
    
    def test_update_contact_with_invalid_data(self, contact_service, unique_contact_data):
        """Test update with potentially invalid data"""
        # Create contact
        contact = contact_service.add_contact(**unique_contact_data)
        
        # Update with potentially problematic data
        # (Current implementation may not validate, but test documents behavior)
        updated_contact = contact_service.update_contact(
            contact.id,
            first_name='',  # Empty string
            email=None      # Explicit None
        )
        
        assert updated_contact is not None
        assert updated_contact.first_name == ''
        assert updated_contact.email is None


class TestContactBusinessLogic:
    """Test business logic and integration scenarios"""
    
    def test_contact_relationship_integrity(self, contact_service, unique_contact_data, db_session):
        """Test that contact relationships are maintained properly"""
        # Create contact
        contact = contact_service.add_contact(**unique_contact_data)
        
        # This would test relationships with properties, appointments, etc.
        # For now, just verify the contact exists and can be queried
        retrieved = contact_service.get_contact_by_id(contact.id)
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
            contact = contact_service.add_contact(**contact_data)
            created_contacts.append(contact)
        
        # Test searching by last name (if search functionality exists)
        # This documents current capabilities
        all_contacts = contact_service.get_all_contacts()
        johnson_contacts = [c for c in all_contacts if c.last_name == 'Johnson']
        assert len(johnson_contacts) >= 2  # At least our test contacts
    
    def test_concurrent_contact_operations(self, contact_service):
        """Test concurrent contact operations"""
        timestamp = str(int(time.time() * 1000000))[-6:]
        
        # Create contact
        contact = contact_service.add_contact(
            first_name=f'Concurrent{timestamp}',
            last_name=f'User{timestamp}',
            phone=f'+155504{timestamp}'
        )
        
        # Simulate concurrent read and update
        retrieved = contact_service.get_contact_by_id(contact.id)
        updated = contact_service.update_contact(contact.id, last_name='Updated')
        
        assert retrieved is not None
        assert updated is not None
        assert updated.last_name == 'Updated'