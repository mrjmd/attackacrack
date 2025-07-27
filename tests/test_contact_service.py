import pytest
from services.contact_service import ContactService
from crm_database import Contact # Import Contact model
from crm_database import db # Import db for session access

def test_add_contact(app, db_session):
    """Test adding a new contact to the database."""
    contact_service = ContactService()
    new_contact = contact_service.add_contact(first_name='Test', last_name='User', email='test@example.com', phone='123-456-7890')
    
    assert new_contact is not None
    assert new_contact.first_name == 'Test'
    assert new_contact.last_name == 'User'
    assert new_contact.email == 'test@example.com'
    assert new_contact.phone == '123-456-7890'

    # Verify it's in the database
    retrieved_contact = Contact.query.get(new_contact.id)
    assert retrieved_contact == new_contact

def test_get_all_contacts(app, db_session):
    """Test retrieving all contacts from the database."""
    contact_service = ContactService()
    
    # Get the initial count of contacts from the database
    initial_contact_count = len(contact_service.get_all_contacts())
    
    # Add a new contact for this specific test
    contact_service.add_contact(first_name='Jane', last_name='Smith', email='jane@example.com', phone='222')
    
    all_contacts = contact_service.get_all_contacts()
    # We expect the count to be one more than the initial count
    assert len(all_contacts) == initial_contact_count + 1

def test_get_contact_by_id(app, db_session):
    """Test retrieving a single contact by their ID."""
    contact_service = ContactService()
    # Assuming conftest seeds a contact with ID 1 and name "Test User"
    retrieved_contact = contact_service.get_contact_by_id(1)
    assert retrieved_contact is not None
    assert retrieved_contact.id == 1
    assert retrieved_contact.first_name == 'Test' # Based on seeded data in conftest.py
    assert retrieved_contact.last_name == 'User'

    # Test for non-existent contact
    non_existent_contact = contact_service.get_contact_by_id(999)
    assert non_existent_contact is None

def test_update_contact(app, db_session):
    """Test updating an existing contact."""
    contact_service = ContactService()
    # Assuming conftest seeds a contact with ID 1
    updated_contact = contact_service.update_contact(1, first_name='Jonathan', email='jonathan.doe@example.com')
    
    assert updated_contact is not None
    assert updated_contact.first_name == 'Jonathan'
    assert updated_contact.last_name == 'User' # Last name should remain unchanged if not provided
    assert updated_contact.email == 'jonathan.doe@example.com'

    retrieved_contact = Contact.query.get(1)
    assert retrieved_contact.first_name == 'Jonathan'
    assert retrieved_contact.email == 'jonathan.doe@example.com'

def test_delete_contact(app, db_session):
    """Test deleting a contact from the database."""
    contact_service = ContactService()
    
    # Get the initial count of contacts
    initial_contact_count = len(contact_service.get_all_contacts())

    # Add a temporary contact to be deleted
    contact_to_delete = contact_service.add_contact(first_name='ToBe', last_name='Deleted', email='delete@me.com', phone='444')
    
    # Ensure we have one more contact than initially
    assert len(contact_service.get_all_contacts()) == initial_contact_count + 1
    
    contact_service.delete_contact(contact_to_delete.id)
    
    # After deletion, we should be back to the initial count
    remaining_contacts = contact_service.get_all_contacts()
    assert len(remaining_contacts) == initial_contact_count
    assert Contact.query.get(contact_to_delete.id) is None
