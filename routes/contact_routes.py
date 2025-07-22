# routes/contact_routes.py

from flask import Blueprint, render_template, g, request, redirect, url_for, flash
from crm_manager import list_contacts, get_contact_by_id, add_contact, update_contact, delete_contact

contact_bp = Blueprint('contact', __name__)

# Helper functions for dropdowns (could be moved to a utils file later)
def get_contact_types():
    return ['All', 'homeowner', 'realtor', 'property_manager', 'inspector', 'builder', 'other']
def get_contact_statuses():
    return ['All', 'new_lead', 'contacted', 'active', 'do_not_contact', 'archived']
def get_customer_statuses():
    return ['All', 'not_customer', 'quoted', 'job_completed', 'repeat_customer']
def get_payment_statuses():
    return ['All', 'no_payment_due', 'payment_pending', 'payment_collected', 'overdue']


@contact_bp.route('/contacts_list')
def list_all():
    filters = {
        'contact_type': request.args.get('contact_type'),
        'contact_status': request.args.get('contact_status'),
        'customer_status': request.args.get('customer_status'),
        'payment_status': request.args.get('payment_status'),
        'has_open_estimates': request.args.get('has_open_estimates') == 'true',
        'has_unpaid_invoices': request.args.get('has_unpaid_invoices') == 'true',
        'search_name': request.args.get('search_name', '').strip() or None
    }
    contacts = list_contacts(g.session, **filters)
    
    return render_template('contact_list.html', 
                           contacts=contacts,
                           contact_types=get_contact_types(),
                           contact_statuses=get_contact_statuses(),
                           customer_statuses=get_customer_statuses(),
                           payment_statuses=get_payment_statuses(),
                           current_filters=filters,
                           current_search_name=request.args.get('search_name', ''))

@contact_bp.route('/contacts/<int:contact_id>')
def detail(contact_id):
    contact = get_contact_by_id(g.session, contact_id)
    if not contact:
        flash('Contact not found.', 'error')
        return redirect(url_for('contact.list_all'))
    return render_template('contact_detail.html', contact=contact)

@contact_bp.route('/add_contact', methods=['GET', 'POST'])
def add():
    if request.method == 'POST':
        # Form processing logic...
        phone_numbers = [{'value': v, 'label': l} for v, l in zip(request.form.getlist('phone_value[]'), request.form.getlist('phone_label[]')) if v]
        emails = [{'value': v, 'label': l} for v, l in zip(request.form.getlist('email_value[]'), request.form.getlist('email_label[]')) if v]
        
        new_contact = add_contact(g.session, 
                                  first_name=request.form['first_name'],
                                  last_name=request.form['last_name'],
                                  contact_type=request.form['contact_type'],
                                  notes=request.form.get('notes'),
                                  phone_numbers=phone_numbers,
                                  emails=emails)
        if new_contact:
            flash(f'Contact "{new_contact.first_name} {new_contact.last_name}" added successfully!', 'success')
            return redirect(url_for('contact.list_all'))
        else:
            flash('Error adding contact.', 'error')

    return render_template('add_edit_contact_form.html', form_title="Add New Contact", contact_types=get_contact_types())

@contact_bp.route('/edit_contact/<int:contact_id>', methods=['GET', 'POST'])
def edit(contact_id):
    contact = get_contact_by_id(g.session, contact_id)
    if not contact:
        flash('Contact not found.', 'error')
        return redirect(url_for('contact.list_all'))

    if request.method == 'POST':
        # Simplified update logic for main fields
        updated = update_contact(g.session, contact_id,
                                 first_name=request.form['first_name'],
                                 last_name=request.form['last_name'],
                                 contact_type=request.form['contact_type'],
                                 contact_status=request.form['contact_status'],
                                 customer_status=request.form['customer_status'],
                                 payment_status=request.form['payment_status'],
                                 notes=request.form.get('notes'))
        # Handle contact details separately (delete and re-add is simplest for now)
        # ...
        if updated:
            flash('Contact updated successfully!', 'success')
            return redirect(url_for('contact.list_all'))
        else:
            flash('Error updating contact.', 'error')

    return render_template('add_edit_contact_form.html', contact=contact, form_title="Edit Contact",
                           contact_types=get_contact_types(),
                           contact_statuses=get_contact_statuses(),
                           customer_statuses=get_customer_statuses(),
                           payment_statuses=get_payment_statuses())

@contact_bp.route('/delete_contact/<int:contact_id>', methods=['POST'])
def delete(contact_id):
    contact = get_contact_by_id(g.session, contact_id) # Fetch for flash message
    if delete_contact(g.session, contact_id):
        flash(f'Contact "{contact.first_name} {contact.last_name}" deleted.', 'success')
    else:
        flash('Error deleting contact.', 'error')
    return redirect(url_for('contact.list_all'))
