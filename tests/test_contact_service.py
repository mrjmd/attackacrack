import pytest
from services.contact_service import ContactService
from crm_database import Contact # Import Contact model
from crm_database import db # Import db for session access

def test_add_contact(app, db_session):
    """Test adding a new contact to the database."""
    contact_service = ContactService()
    new_contact = contact_service.add_contact(first_name='Jane', last_name='Smith', email='jane@example.com', phone='222') # Changed to Jane Smith
    
    assert new_contact is not None
    assert new_contact.first_name == 'Jane' # Changed assertion
    assert new_contact.last_name == 'Smith' # Changed assertion
    assert new_contact.email == 'jane@example.com' # Changed assertion
    assert new_contact.phone == '222' # Changed assertion

    # Verify it's in the database
    # Refactored: Using Session.get() instead of Query.get()
    retrieved_contact = db.session.get(Contact, new_contact.id)
    assert retrieved_contact == new_contact

def test_get_all_contacts(app, db_session):
    """Test retrieving all contacts from the database."""
    contact_service = ContactService()
    
    # Get the initial count of contacts from the database
    # This accounts for the single contact seeded by conftest.py
    initial_contact_count = len(contact_service.get_all_contacts())
    
    # Add a new contact for this specific test
    contact_service.add_contact(first_name='Another', last_name='Contact', email='another@example.com', phone='555')
    
    all_contacts = contact_service.get_all_contacts()
    # We expect the count to be one more than the initial count
    assert len(all_contacts) == initial_contact_count + 1

def test_get_contact_by_id(app, db_session):
    """Test retrieving a single contact by ID."""
    contact_service = ContactService()
    # Assuming conftest seeds a contact with ID 1 as "Test User"
    contact = contact_service.get_contact_by_id(1)
    assert contact is not None
    assert contact.id == 1
    assert contact.first_name == 'Test' # Aligned with conftest.py seeding
    assert contact.last_name == 'User' # Aligned with conftest.py seeding

    # Test for non-existent contact
    non_existent_contact = contact_service.get_contact_by_id(999)
    assert non_existent_contact is None

def test_update_contact(app, db_session):
    """Test updating an existing contact."""
    contact_service = ContactService()
    # Assuming conftest seeds a contact with ID 1
    # The update_contact method now expects contact_id, not a contact object
    updated_contact = contact_service.update_contact(1, first_name='UpdatedTest', email='updated@user.com') # Changed names to avoid conflict
    
    assert updated_contact is not None
    assert updated_contact.first_name == 'UpdatedTest' # Aligned with update
    assert updated_contact.last_name == 'User' # Last name should remain unchanged if not provided
    assert updated_contact.email == 'updated@user.com' # Aligned with update

    # Refactored: Using Session.get() instead of Query.get()
    retrieved_contact = db.session.get(Contact, 1)
    assert retrieved_contact.first_name == 'UpdatedTest' # Aligned with update
    assert retrieved_contact.email == 'updated@user.com' # Aligned with update

def test_delete_contact(app, db_session):
    """Test deleting a contact from the database."""
    contact_service = ContactService()
    
    # Get the initial count of contacts
    initial_contact_count = len(contact_service.get_all_contacts())

    # Add a temporary contact to be deleted
    contact_to_delete = contact_service.add_contact(first_name='ToBe', last_name='Deleted', email='delete@me.com', phone='444')
    
    # Ensure we have one more contact than initially
    assert len(contact_service.get_all_contacts()) == initial_contact_count + 1
    
    # The delete_contact method now expects contact_id, not a contact object
    contact_service.delete_contact(contact_to_delete.id)
    
    # After deletion, we should be back to the initial count
    remaining_contacts = contact_service.get_all_contacts()
    assert len(remaining_contacts) == initial_contact_count
    # Refactored: Using Session.get() instead of Query.get()
    assert db.session.get(Contact, contact_to_delete.id) is None
