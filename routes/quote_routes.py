from flask import Blueprint, render_template, request, redirect, url_for, flash
from services.quote_service import QuoteService
from services.job_service import JobService
from services.invoice_service import InvoiceService
from crm_database import ProductService

quote_bp = Blueprint('quote', __name__)

quote_service = QuoteService()
# --- CHANGE 1 of 2: Instantiate the JobService ---
job_service = JobService()

@quote_bp.route('/quotes')
def list_all():
    quotes = quote_service.get_all_quotes()
    return render_template('quote_list.html', quotes=quotes)

@quote_bp.route('/quote/<int:quote_id>')
def view(quote_id):
    quote = quote_service.get_quote_by_id(quote_id)
    return render_template('quote_detail.html', quote=quote)

@quote_bp.route('/quote/add', methods=['GET', 'POST'])
@quote_bp.route('/quote/<int:quote_id>/edit', methods=['GET', 'POST'])
def add_edit(quote_id=None):
    if quote_id:
        quote = quote_service.get_quote_by_id(quote_id)
    else:
        quote = None

    if request.method == 'POST':
        data = {
            'job_id': request.form['job_id'],
            'amount': request.form['amount'],
            'status': request.form.get('status', 'Draft')
        }
        if quote_id:
            quote_service.update_quote(quote_id, data)
            flash('Quote updated successfully!', 'success')
        else:
            new_quote = quote_service.create_quote(data)
            quote_id = new_quote.id
            flash('Quote created successfully!', 'success')
        return redirect(url_for('quote.view', quote_id=quote_id))

    # --- CHANGE 2 of 2: Call the method on the instance ---
    jobs = job_service.get_all_jobs()
    return render_template('add_edit_quote_form.html', quote=quote, jobs=jobs)

@quote_bp.route('/quote/<int:quote_id>/delete', methods=['POST'])
def delete(quote_id):
    quote_service.delete_quote(quote_id)
    flash('Quote deleted successfully!', 'success')
    return redirect(url_for('quote.list_all'))

@quote_bp.route('/quote/<int:quote_id>/convert', methods=['POST'])
def convert_quote_to_invoice(quote_id):
    """
    Handles the POST request to convert a quote into an invoice.
    """
    new_invoice = InvoiceService.create_invoice_from_quote(quote_id)
    if new_invoice:
        flash('Quote successfully converted to Invoice!', 'success')
        return redirect(url_for('invoice.view', invoice_id=new_invoice.id))
    else:
        flash('Failed to convert quote. Quote not found.', 'danger')
        return redirect(url_for('quote.view', quote_id=quote_id))
