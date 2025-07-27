from crm_database import Contact, db
from sqlalchemy.exc import IntegrityError # Added for handling potential IntegrityError

class ContactService:
    def __init__(self):
        self.session = db.session

    def add_contact(self, first_name, last_name, email=None, phone=None): # Changed kwargs to explicit args
        try:
            new_contact = Contact(first_name=first_name, last_name=last_name, email=email, phone=phone)
            self.session.add(new_contact)
            self.session.commit()
            return new_contact
        except IntegrityError:
            self.session.rollback()
            # Handle cases where email or phone might already exist if unique constraint is violated
            return None # Or raise a more specific error

    def get_all_contacts(self):
        return self.session.query(Contact).all()

    def get_contact_by_id(self, contact_id):
        # Refactored: Using Session.get() instead of Query.get()
        return self.session.get(Contact, contact_id)

    def get_contact_by_phone(self, phone_number):
        """Finds a contact by their phone number."""
        if not phone_number:
            return None
        return self.session.query(Contact).filter_by(phone=phone_number).first()

    def update_contact(self, contact_id, **kwargs): # Changed contact to contact_id
        # Refactored: Using Session.get() to retrieve the object
        contact = self.session.get(Contact, contact_id)
        if not contact:
            return None # Contact not found

        for key, value in kwargs.items():
            setattr(contact, key, value)
        self.session.commit()
        return contact

    def delete_contact(self, contact_id): # Changed contact to contact_id
        # Refactored: Using Session.get() to retrieve the object
        contact = self.session.get(Contact, contact_id)
        if contact:
            self.session.delete(contact)
            self.session.commit()
            return True # Indicate successful deletion
        return False # Indicate contact not found
