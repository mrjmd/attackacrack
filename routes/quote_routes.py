from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from services.quote_service import QuoteService
from services.job_service import JobService
from services.invoice_service import InvoiceService
from crm_database import ProductService

quote_bp = Blueprint('quote', __name__)

quote_service = QuoteService()
job_service = JobService()

@quote_bp.route('/')
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
    quote = None
    if quote_id:
        quote = quote_service.get_quote_by_id(quote_id)

    if request.method == 'POST':
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Invalid JSON'}), 400
        
        if quote_id:
            quote = quote_service.update_quote(quote_id, data)
        else:
            quote = quote_service.create_quote(data)
        
        if quote:
            return jsonify({'redirect': url_for('quote.view', quote_id=quote.id)})
        else:
            return jsonify({'error': 'Could not save quote'}), 500

    jobs = job_service.get_all_jobs()
    product_services = ProductService.query.all()
    return render_template('add_edit_quote_form.html', quote=quote, jobs=jobs, product_services=product_services)

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
        # --- THIS IS THE ONLY CHANGE IN THIS FILE ---
        # Corrected the url_for endpoint from 'invoice.view' to 'invoice.invoice_detail'
        return redirect(url_for('invoice.invoice_detail', invoice_id=new_invoice.id))
    else:
        flash('Failed to convert quote. Quote not found.', 'danger')
        return redirect(url_for('quote.view', quote_id=quote_id))
