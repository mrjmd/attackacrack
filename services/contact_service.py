from extensions import db
from crm_database import Contact

class ContactService:
    def __init__(self):
        self.session = db.session

    def add_contact(self, **kwargs):
        new_contact = Contact(**kwargs)
        self.session.add(new_contact)
        self.session.commit()
        return new_contact

    def get_all_contacts(self):
        return self.session.query(Contact).all()

    def get_contact_by_id(self, contact_id):
        return self.session.query(Contact).get(contact_id)

    def update_contact(self, contact, **kwargs):
        for key, value in kwargs.items():
            setattr(contact, key, value)
        self.session.commit()
        return contact

    def delete_contact(self, contact):
        self.session.delete(contact)
        self.session.commit()
