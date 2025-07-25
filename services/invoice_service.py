from extensions import db
from crm_database import Invoice, Quote
from datetime import datetime, timedelta

class InvoiceService:
    @staticmethod
    def get_all_invoices():
        return Invoice.query.all()

    @staticmethod
    def get_invoice_by_id(invoice_id):
        return Invoice.query.get(invoice_id)

    @staticmethod
    def create_invoice(data):
        new_invoice = Invoice(
            job_id=data['job_id'],
            amount=data['amount'],
            due_date=data['due_date'],
            status=data.get('status', 'Draft')
        )
        db.session.add(new_invoice)
        db.session.commit()
        return new_invoice

    @staticmethod
    def update_invoice(invoice_id, data):
        invoice = Invoice.query.get(invoice_id)
        if invoice:
            invoice.job_id = data.get('job_id', invoice.job_id)
            invoice.amount = data.get('amount', invoice.amount)
            invoice.due_date = data.get('due_date', invoice.due_date)
            invoice.status = data.get('status', invoice.status)
            db.session.commit()
        return invoice

    @staticmethod
    def delete_invoice(invoice_id):
        invoice = Invoice.query.get(invoice_id)
        if invoice:
            db.session.delete(invoice)
            db.session.commit()
        return invoice

    # --- CHANGE START ---
    # Added a new function to handle the conversion of a Quote to an Invoice.
    @staticmethod
    def create_invoice_from_quote(quote_id):
        """
        Creates an Invoice from a given Quote.
        - Fetches the quote by its ID.
        - Creates a new Invoice with the same job ID and amount.
        - Sets a default due date (30 days from now).
        - Updates the original quote's status to 'Accepted'.
        - Commits the changes to the database.
        - Returns the newly created invoice.
        """
        quote = Quote.query.get(quote_id)
        if not quote:
            return None

        # Create a new invoice based on the quote's data
        new_invoice = Invoice(
            job_id=quote.job_id,
            amount=quote.amount,
            due_date=datetime.utcnow().date() + timedelta(days=30),
            status='Unpaid'  # Set initial status for the new invoice
        )

        # Update the quote's status to reflect it has been converted
        quote.status = 'Accepted'

        db.session.add(new_invoice)
        db.session.commit()

        return new_invoice
    # --- CHANGE END ---
