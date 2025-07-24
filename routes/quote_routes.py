from flask import Blueprint, render_template, request, redirect, url_for, jsonify
from services.quote_service import QuoteService
from services.job_service import JobService
from services.property_service import PropertyService
from services.contact_service import ContactService

quote_bp = Blueprint('quote', __name__)

@quote_bp.route('/')
def list_all():
    quote_service = QuoteService()
    all_quotes = quote_service.get_all_quotes()
    return render_template('quote_list.html', quotes=all_quotes)

@quote_bp.route('/<int:quote_id>')
def quote_detail(quote_id):
    quote_service = QuoteService()
    quote = quote_service.get_quote_by_id(quote_id)
    return render_template('quote_detail.html', quote=quote)

@quote_bp.route('/add', methods=['GET', 'POST'])
def add_quote():
    quote_service = QuoteService()
    job_service = JobService()
    property_service = PropertyService()
    contact_service = ContactService()

    if request.method == 'POST':
        data = request.get_json()
        property_id = data.get('property_id')
        line_items = data.get('line_items')
        
        if property_id and line_items:
            active_job = job_service.get_or_create_active_job(int(property_id))
            new_quote = quote_service.add_quote_with_line_items(active_job.id, line_items)
            return jsonify({'success': True, 'quote_id': new_quote.id})
            
        return jsonify({'success': False, 'error': 'Missing property or line items'}), 400

    # For GET request
    contact_id = request.args.get('contact_id')
    properties = []
    if contact_id:
        # If we came from a contact, only show their properties
        contact = contact_service.get_contact_by_id(contact_id)
        properties = contact.properties if contact else []
    else:
        # Otherwise, show all properties
        properties = property_service.get_all_properties()

    products = quote_service.get_all_products_and_services()
    return render_template('add_edit_quote_form.html', properties=properties, products=products, contact_id=contact_id)

@quote_bp.route('/<int:quote_id>/delete', methods=['POST'])
def delete_quote(quote_id):
    quote_service = QuoteService()
    quote = quote_service.get_quote_by_id(quote_id)
    quote_service.delete_quote(quote)
    return redirect(url_for('quote.list_all'))
