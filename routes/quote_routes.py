from flask import Blueprint, render_template, request, redirect, url_for, flash
from services.quote_service import QuoteService
from services.job_service import JobService
from services.invoice_service import InvoiceService
from crm_database import ProductService

# --- CHANGE START ---
# Corrected the Blueprint variable name back to 'quote_bp' to match what is
# expected by your app.py file. This fixes the ImportError.
quote_bp = Blueprint('quote_routes', __name__)
# --- CHANGE END ---

@quote_bp.route('/quotes')
def quote_list():
    quotes = QuoteService.get_all_quotes()
    return render_template('quote_list.html', quotes=quotes)

@quote_bp.route('/quote/<int:quote_id>')
def quote_detail(quote_id):
    quote = QuoteService.get_quote_by_id(quote_id)
    return render_template('quote_detail.html', quote=quote)

@quote_bp.route('/quote/add', methods=['GET', 'POST'])
@quote_bp.route('/quote/<int:quote_id>/edit', methods=['GET', 'POST'])
def add_edit_quote(quote_id=None):
    if quote_id:
        quote = QuoteService.get_quote_by_id(quote_id)
    else:
        quote = None

    if request.method == 'POST':
        data = {
            'job_id': request.form['job_id'],
            'amount': request.form['amount'],
            'status': request.form.get('status', 'Draft')
        }
        if quote_id:
            QuoteService.update_quote(quote_id, data)
            flash('Quote updated successfully!', 'success')
        else:
            new_quote = QuoteService.create_quote(data)
            quote_id = new_quote.id
            flash('Quote created successfully!', 'success')
        return redirect(url_for('quote_routes.quote_detail', quote_id=quote_id))

    jobs = JobService.get_all_jobs()
    return render_template('add_edit_quote_form.html', quote=quote, jobs=jobs)

@quote_bp.route('/quote/<int:quote_id>/delete', methods=['POST'])
def delete_quote(quote_id):
    QuoteService.delete_quote(quote_id)
    flash('Quote deleted successfully!', 'success')
    return redirect(url_for('quote_routes.quote_list'))

# --- THIS IS THE ONLY ADDITION TO THE FILE'S LOGIC ---
# A new route to handle the conversion from Quote to Invoice
@quote_bp.route('/quote/<int:quote_id>/convert', methods=['POST'])
def convert_quote_to_invoice(quote_id):
    """
    Handles the POST request to convert a quote into an invoice.
    """
    new_invoice = InvoiceService.create_invoice_from_quote(quote_id)
    if new_invoice:
        flash('Quote successfully converted to Invoice!', 'success')
        # Redirect to the detail page of the newly created invoice
        return redirect(url_for('invoice_routes.invoice_detail', invoice_id=new_invoice.id))
    else:
        flash('Failed to convert quote. Quote not found.', 'danger')
        return redirect(url_for('quote_routes.quote_detail', quote_id=quote_id))
