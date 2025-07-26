import pytest
from app import create_app
from extensions import db
from services.contact_service import ContactService
from crm_database import Contact

@pytest.fixture
def app():
    """Create and configure a new app instance for each test."""
    app = create_app(test_config={
        'TESTING': True,
        'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
        'SQLALCHEMY_TRACK_MODIFICATIONS': False,
        'WTF_CSRF_ENABLED': False
    })

    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()

def test_add_contact(app):
    """Test adding a new contact to the database."""
    with app.app_context():
        contact_service = ContactService()
        contact = contact_service.add_contact(
            first_name='John',
            last_name='Doe',
            email='john.doe@example.com',
            phone='1234567890'
        )
        assert contact.id is not None
        assert contact.first_name == 'John'

        # --- THIS IS A FIX ---
        retrieved_contact = db.session.get(Contact, contact.id)
        # --- END FIX ---
        assert retrieved_contact is not None
        assert retrieved_contact.email == 'john.doe@example.com'

def test_get_all_contacts(app):
    """Test retrieving all contacts from the database."""
    with app.app_context():
        contact_service = ContactService()
        contact_service.add_contact(first_name='John', last_name='Doe', email='john@example.com', phone='111')
        contact_service.add_contact(first_name='Jane', last_name='Smith', email='jane@example.com', phone='222')

        all_contacts = contact_service.get_all_contacts()
        assert len(all_contacts) == 2
        assert all_contacts[0].first_name == 'John'
        assert all_contacts[1].first_name == 'Jane'

def test_get_contact_by_id(app):
    """Test retrieving a single contact by their ID."""
    with app.app_context():
        contact_service = ContactService()
        contact = contact_service.add_contact(first_name='Specific', last_name='User', email='specific@example.com', phone='333')

        retrieved_contact = contact_service.get_contact_by_id(contact.id)
        assert retrieved_contact is not None
        assert retrieved_contact.id == contact.id
        assert retrieved_contact.first_name == 'Specific'

        non_existent_contact = contact_service.get_contact_by_id(999)
        assert non_existent_contact is None

def test_update_contact(app):
    """Test updating an existing contact's details."""
    with app.app_context():
        contact_service = ContactService()
        contact = contact_service.add_contact(
            first_name='Original',
            last_name='Name',
            email='original@example.com',
            phone='1112223333'
        )

        updated_contact = contact_service.update_contact(
            contact,
            first_name='Updated',
            email='updated@example.com'
        )
        assert updated_contact.first_name == 'Updated'
        assert updated_contact.last_name == 'Name'
        assert updated_contact.email == 'updated@example.com'

        # --- THIS IS A FIX ---
        retrieved_contact = db.session.get(Contact, contact.id)
        # --- END FIX ---
        assert retrieved_contact.first_name == 'Updated'

def test_delete_contact(app):
    """Test deleting a contact from the database."""
    with app.app_context():
        contact_service = ContactService()
        contact_to_delete = contact_service.add_contact(first_name='ToBe', last_name='Deleted', email='delete@me.com', phone='444')
        contact_to_keep = contact_service.add_contact(first_name='To', last_name='Keep', email='keep@me.com', phone='555')

        contact_service.delete_contact(contact_to_delete)

        # --- THIS IS A FIX ---
        deleted_contact = db.session.get(Contact, contact_to_delete.id)
        # --- END FIX ---
        assert deleted_contact is None

        # --- THIS IS A FIX ---
        kept_contact = db.session.get(Contact, contact_to_keep.id)
        # --- END FIX ---
        assert kept_contact is not None
        
        all_contacts = contact_service.get_all_contacts()
        assert len(all_contacts) == 1