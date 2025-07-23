# crm_manager.py

from crm_database import Contact, Property, Job, Appointment, Quote, Invoice

class CrmManager:
    def __init__(self, session):
        self.session = session

    # --- Contact Methods ---
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

    # --- Property Methods ---
    def add_property(self, **kwargs):
        new_property = Property(**kwargs)
        self.session.add(new_property)
        self.session.commit()
        return new_property

    def get_all_properties(self):
        return self.session.query(Property).all()

    def get_property_by_id(self, property_id):
        return self.session.query(Property).get(property_id)
    
    def update_property(self, property_obj, **kwargs):
        for key, value in kwargs.items():
            setattr(property_obj, key, value)
        self.session.commit()
        return property_obj

    def delete_property(self, property_obj):
        self.session.delete(property_obj)
        self.session.commit()

    # --- Job Methods ---
    def add_job(self, **kwargs):
        new_job = Job(**kwargs)
        self.session.add(new_job)
        self.session.commit()
        return new_job

    def get_all_jobs(self):
        return self.session.query(Job).all()

    def get_job_by_id(self, job_id):
        return self.session.query(Job).get(job_id)

    def update_job(self, job, **kwargs):
        for key, value in kwargs.items():
            setattr(job, key, value)
        self.session.commit()
        return job

    def delete_job(self, job):
        self.session.delete(job)
        self.session.commit()

    # --- Appointment Methods ---
    def add_appointment(self, **kwargs):
        new_appointment = Appointment(**kwargs)
        self.session.add(new_appointment)
        self.session.commit()
        return new_appointment

    def get_all_appointments(self):
        return self.session.query(Appointment).all()

    def get_appointment_by_id(self, appointment_id):
        return self.session.query(Appointment).get(appointment_id)

    def update_appointment(self, appointment, **kwargs):
        for key, value in kwargs.items():
            setattr(appointment, key, value)
        self.session.commit()
        return appointment

    def delete_appointment(self, appointment):
        self.session.delete(appointment)
        self.session.commit()

    # --- Quote Methods ---
    def add_quote(self, **kwargs):
        new_quote = Quote(**kwargs)
        self.session.add(new_quote)
        self.session.commit()
        return new_quote

    def get_all_quotes(self):
        return self.session.query(Quote).all()

    def get_quote_by_id(self, quote_id):
        return self.session.query(Quote).get(quote_id)
    
    def update_quote(self, quote, **kwargs):
        for key, value in kwargs.items():
            setattr(quote, key, value)
        self.session.commit()
        return quote

    def delete_quote(self, quote):
        self.session.delete(quote)
        self.session.commit()

    # --- Invoice Methods ---
    def add_invoice(self, **kwargs):
        new_invoice = Invoice(**kwargs)
        self.session.add(new_invoice)
        self.session.commit()
        return new_invoice

    def get_all_invoices(self):
        return self.session.query(Invoice).all()

    def get_invoice_by_id(self, invoice_id):
        return self.session.query(Invoice).get(invoice_id)

    def update_invoice(self, invoice, **kwargs):
        for key, value in kwargs.items():
            setattr(invoice, key, value)
        self.session.commit()
        return invoice

    def delete_invoice(self, invoice):
        self.session.delete(invoice)
        self.session.commit()

