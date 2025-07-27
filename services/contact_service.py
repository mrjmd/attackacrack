# services/contact_service.py
from crm_database import db, Contact
from sqlalchemy.exc import IntegrityError

class ContactService:
    def __init__(self):
        self.session = db.session

    def add_contact(self, first_name, last_name, email=None, phone=None):
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
        # Using .get() for primary key lookup, which is efficient
        return self.session.query(Contact).get(contact_id)

    def get_contact_by_phone(self, phone_number):
        """
        Retrieves a contact by their phone number.
        """
        return self.session.query(Contact).filter_by(phone=phone_number).first()

    def update_contact(self, contact_id, **kwargs):
        contact = self.get_contact_by_id(contact_id)
        if not contact:
            return None # Contact not found

        for key, value in kwargs.items():
            setattr(contact, key, value)
        self.session.commit()
        return contact

    def delete_contact(self, contact_id):
        contact = self.get_contact_by_id(contact_id)
        if contact:
            self.session.delete(contact)
            self.session.commit()
            return True
        return False
