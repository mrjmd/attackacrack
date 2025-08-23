from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app
from auth_utils import login_required
# ProductService now accessed via service registry

quote_bp = Blueprint('quote', __name__)

@quote_bp.route('/')
@login_required
def list_all():
    quote_service = current_app.services.get('quote')
    quotes = quote_service.get_all_quotes()
    return render_template('quote_list.html', quotes=quotes)

@quote_bp.route('/quote/<int:quote_id>')
@login_required
def view(quote_id):
    quote_service = current_app.services.get('quote')
    quote = quote_service.get_quote_by_id(quote_id)
    return render_template('quote_detail.html', quote=quote)

@quote_bp.route('/new', methods=['GET', 'POST'])
@quote_bp.route('/add', methods=['GET', 'POST'])
@quote_bp.route('/<int:quote_id>/edit', methods=['GET', 'POST'])
@login_required
def add_edit(quote_id=None):
    quote_service = current_app.services.get('quote')
    job_service = current_app.services.get('job')
    
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
    product_service = current_app.services.get('product')
    product_services = product_service.get_all()
    return render_template('add_edit_quote_form.html', quote=quote, jobs=jobs, product_services=product_services)

@quote_bp.route('/quote/<int:quote_id>/delete', methods=['POST'])
@login_required
def delete(quote_id):
    quote_service = current_app.services.get('quote')
    quote_service.delete_quote(quote_id)
    flash('Quote deleted successfully!', 'success')
    return redirect(url_for('quote.list_all'))

@quote_bp.route('/quote/<int:quote_id>/convert', methods=['POST'])
@login_required
def convert_quote_to_invoice(quote_id):
    """
    Handles the POST request to convert a quote into an invoice.
    """
    invoice_service = current_app.services.get('invoice')
    new_invoice = invoice_service.create_invoice_from_quote(quote_id)
    if new_invoice:
        flash('Quote successfully converted to Invoice!', 'success')
        # --- THIS IS THE ONLY CHANGE IN THIS FILE ---
        # Corrected the url_for endpoint from 'invoice.view' to 'invoice.invoice_detail'
        return redirect(url_for('invoice.invoice_detail', invoice_id=new_invoice.id))
    else:
        flash('Failed to convert quote. Quote not found.', 'danger')
        return redirect(url_for('quote.view', quote_id=quote_id))
