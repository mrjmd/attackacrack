from extensions import db
from crm_database import Invoice

class InvoiceService:
    def __init__(self):
        self.session = db.session

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
