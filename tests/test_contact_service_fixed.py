"""
Fixed tests for Contact Service
"""
import pytest
from services.contact_service import ContactService
from crm_database import db, Contact


class TestContactServiceFixed:
    """Fixed test cases for Contact service"""
    
    @pytest.fixture
    def contact_service(self, app):
        """Create a contact service instance"""
        with app.app_context():
            service = ContactService()
            yield service
    
    def test_get_all_contacts(self, contact_service, app):
        """Test getting all contacts"""
        with app.app_context():
            # Create test contacts
            contact1 = Contact(
                first_name='John',
                last_name='Doe',
                email='john@example.com',
                phone='+15551234567'
            )
            contact2 = Contact(
                first_name='Jane',
                last_name='Smith',
                email='jane@example.com',
                phone='+15551234568'
            )
            db.session.add_all([contact1, contact2])
            db.session.commit()
            
            # Get all contacts
            contacts = contact_service.get_all_contacts()
            assert len(contacts) >= 2  # May include seeded data
            
            # Clean up
            db.session.delete(contact1)
            db.session.delete(contact2)
            db.session.commit()
    
    def test_get_contact_by_id(self, contact_service, app):
        """Test getting contact by ID"""
        with app.app_context():
            # Create test contact
            contact = Contact(
                first_name='Test',
                last_name='Contact',
                email='test@example.com',
                phone='+15559999999'
            )
            db.session.add(contact)
            db.session.commit()
            
            # Get by ID
            result = contact_service.get_contact_by_id(contact.id)
            assert result is not None
            assert result.id == contact.id
            assert result.first_name == 'Test'
            
            # Test non-existent ID
            result = contact_service.get_contact_by_id(99999)
            assert result is None
            
            # Clean up
            db.session.delete(contact)
            db.session.commit()
    
    def test_add_contact(self, contact_service, app):
        """Test adding a contact"""
        with app.app_context():
            contact = contact_service.add_contact(
                first_name='New',
                last_name='Contact',
                email='new@example.com',
                phone='+15558888888'
            )
            assert contact is not None
            assert contact.first_name == 'New'
            assert contact.email == 'new@example.com'
            
            # Clean up
            db.session.delete(contact)
            db.session.commit()
    
    def test_update_contact(self, contact_service, app):
        """Test updating a contact"""
        with app.app_context():
            # Create test contact
            contact = Contact(
                first_name='Original',
                last_name='Name',
                email='original@example.com',
                phone='+15557777777'
            )
            db.session.add(contact)
            db.session.commit()
            
            # Update contact
            update_data = {
                'first_name': 'Updated',
                'email': 'updated@example.com'
            }
            
            updated = contact_service.update_contact(contact.id, update_data)
            assert updated is not None
            assert updated.first_name == 'Updated'
            assert updated.email == 'updated@example.com'
            assert updated.last_name == 'Name'  # Unchanged
            
            # Test non-existent ID
            result = contact_service.update_contact(99999, update_data)
            assert result is None
            
            # Clean up
            db.session.delete(contact)
            db.session.commit()
    
    def test_delete_contact(self, contact_service, app):
        """Test deleting a contact"""
        with app.app_context():
            # Create test contact
            contact = Contact(
                first_name='ToDelete',
                last_name='Contact',
                email='delete@example.com',
                phone='+15556666666'
            )
            db.session.add(contact)
            db.session.commit()
            contact_id = contact.id
            
            # Delete contact
            result = contact_service.delete_contact(contact_id)
            assert result is True
            
            # Verify it's deleted
            deleted = Contact.query.get(contact_id)
            assert deleted is None
            
            # Test deleting non-existent contact
            result = contact_service.delete_contact(99999)
            assert result is False
    
    
    def test_get_contact_by_phone(self, contact_service, app):
        """Test getting contact by phone number"""
        with app.app_context():
            # Create test contact
            contact = Contact(
                first_name='Phone',
                last_name='Test',
                email='phone@example.com',
                phone='+15553333333'
            )
            db.session.add(contact)
            db.session.commit()
            
            # Get by phone
            result = contact_service.get_contact_by_phone('+15553333333')
            assert result is not None
            assert result.phone == '+15553333333'
            
            # Test non-existent phone
            result = contact_service.get_contact_by_phone('+15552222222')
            assert result is None
            
            # Clean up
            db.session.delete(contact)
            db.session.commit()