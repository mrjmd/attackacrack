import pytest
from services.contact_service import ContactService
from crm_database import Contact

# The 'app' and 'db_session' fixtures are now passed in from conftest.py

def test_add_contact(app, db_session):
    """Test adding a new contact to the database."""
    contact_service = ContactService()
    contact = contact_service.add_contact(
        first_name='John',
        last_name='Doe',
        email='john.doe@example.com',
        phone='1234567890'
    )
    assert contact.id is not None
    assert contact.first_name == 'John'

    retrieved_contact = db_session.get(Contact, contact.id)
    assert retrieved_contact is not None
    assert retrieved_contact.email == 'john.doe@example.com'

def test_get_all_contacts(app):
    """Test retrieving all contacts from the database."""
    contact_service = ContactService()
    # Add a new contact to the existing seeded data
    contact_service.add_contact(first_name='Jane', last_name='Smith', email='jane@example.com', phone='222')

    all_contacts = contact_service.get_all_contacts()
    # We expect the seeded contact + the new one
    assert len(all_contacts) == 2
    assert all_contacts[0].first_name == 'Test' # From conftest.py
    assert all_contacts[1].first_name == 'Jane'

def test_get_contact_by_id(app):
    """Test retrieving a single contact by their ID."""
    contact_service = ContactService()
    # The contact with ID 1 is seeded in conftest.py
    retrieved_contact = contact_service.get_contact_by_id(1)
    assert retrieved_contact is not None
    assert retrieved_contact.id == 1
    assert retrieved_contact.first_name == 'Test'

    non_existent_contact = contact_service.get_contact_by_id(999)
    assert non_existent_contact is None

def test_update_contact(app, db_session):
    """Test updating an existing contact's details."""
    contact_service = ContactService()
    contact = db_session.get(Contact, 1) # Get the seeded contact

    updated_contact = contact_service.update_contact(
        contact,
        first_name='Updated',
        email='updated@example.com'
    )
    assert updated_contact.first_name == 'Updated'
    assert updated_contact.last_name == 'User' # Should remain the same
    assert updated_contact.email == 'updated@example.com'

    retrieved_contact = db_session.get(Contact, 1)
    assert retrieved_contact.first_name == 'Updated'

def test_delete_contact(app, db_session):
    """Test deleting a contact from the database."""
    contact_service = ContactService()
    # Add a temporary contact to be deleted
    contact_to_delete = contact_service.add_contact(first_name='ToBe', last_name='Deleted', email='delete@me.com', phone='444')
    
    # Ensure we have 2 contacts before deletion (seeded + new)
    assert len(contact_service.get_all_contacts()) == 2

    contact_service.delete_contact(contact_to_delete)

    deleted_contact = db_session.get(Contact, contact_to_delete.id)
    assert deleted_contact is None
    
    # Ensure we are back to having only the 1 seeded contact
    all_contacts = contact_service.get_all_contacts()
    assert len(all_contacts) == 1
    assert all_contacts[0].first_name == 'Test'