# routes/quote_routes.py

from flask import Blueprint, render_template, g, request, redirect, url_for, flash
from crm_manager import list_quotes, get_quote_by_id, add_quote, update_quote, delete_quote, convert_quote_to_invoice
from crm_database import Contact, Property, Job
from datetime import datetime

quote_bp = Blueprint('quote', __name__, url_prefix='/quotes')

def get_quote_statuses():
    return ['All', 'draft', 'sent', 'accepted', 'rejected', 'expired', 'invoiced']

@quote_bp.route('/')
def list_all():
    quotes = list_quotes(g.session,
                         status=request.args.get('status'),
                         contact_id=request.args.get('contact_id', type=int),
                         property_id=request.args.get('property_id', type=int),
                         job_id=request.args.get('job_id', type=int))
    
    contacts = g.session.query(Contact).order_by(Contact.first_name).all()
    properties = g.session.query(Property).order_by(Property.address).all()
    jobs = g.session.query(Job).order_by(Job.job_name).all()

    return render_template('quote_list.html',
                           quotes=quotes,
                           quote_statuses=get_quote_statuses(),
                           contacts=contacts,
                           properties=properties,
                           jobs=jobs,
                           current_status=request.args.get('status'),
                           current_contact_id=request.args.get('contact_id', type=int),
                           current_property_id=request.args.get('property_id', type=int),
                           current_job_id=request.args.get('job_id', type=int))

@quote_bp.route('/<int:quote_id>')
def detail(quote_id):
    quote = get_quote_by_id(g.session, quote_id)
    if not quote:
        flash('Quote not found.', 'error')
        return redirect(url_for('quote.list_all'))
    return render_template('quote_detail.html', quote=quote)

@quote_bp.route('/add', methods=['GET', 'POST'])
def add():
    contacts = g.session.query(Contact).order_by(Contact.first_name).all()
    properties = g.session.query(Property).order_by(Property.address).all()
    if request.method == 'POST':
        # Date parsing
        sent_date = datetime.strptime(request.form['sent_date'], '%Y-%m-%d') if request.form.get('sent_date') else None
        accepted_date = datetime.strptime(request.form['accepted_date'], '%Y-%m-%d') if request.form.get('accepted_date') else None
        valid_until = datetime.strptime(request.form['valid_until'], '%Y-%m-%d') if request.form.get('valid_until') else None

        new_quote = add_quote(g.session,
                              contact_id=request.form.get('contact_id', type=int),
                              quote_number=request.form['quote_number'],
                              amount=request.form.get('amount', type=float),
                              status=request.form.get('status', 'draft'),
                              property_id=request.form.get('property_id', type=int),
                              details=request.form.get('details'),
                              sent_date=sent_date,
                              accepted_date=accepted_date,
                              valid_until=valid_until)
        if new_quote:
            flash('Quote added successfully!', 'success')
            return redirect(url_for('quote.list_all'))
        else:
            flash('Error adding quote.', 'error')
    return render_template('add_edit_quote_form.html', form_title="Add New Quote", contacts=contacts, properties=properties, quote_statuses=get_quote_statuses())

@quote_bp.route('/edit/<int:quote_id>', methods=['GET', 'POST'])
def edit(quote_id):
    quote = get_quote_by_id(g.session, quote_id)
    if not quote:
        flash('Quote not found', 'error')
        return redirect(url_for('quote.list_all'))
    
    if request.method == 'POST':
        update_data = request.form.to_dict()
        for date_field in ['sent_date', 'accepted_date', 'valid_until']:
            if update_data.get(date_field):
                update_data[date_field] = datetime.strptime(update_data[date_field], '%Y-%m-%d')
            else:
                update_data[date_field] = None
        
        if update_quote(g.session, quote_id, **update_data):
            flash('Quote updated successfully!', 'success')
            return redirect(url_for('quote.detail', quote_id=quote_id))
        else:
            flash('Error updating quote.', 'error')

    contacts = g.session.query(Contact).order_by(Contact.first_name).all()
    properties = g.session.query(Property).order_by(Property.address).all()
    return render_template('add_edit_quote_form.html', quote=quote, form_title="Edit Quote", contacts=contacts, properties=properties, quote_statuses=get_quote_statuses())

@quote_bp.route('/delete/<int:quote_id>', methods=['POST'])
def delete(quote_id):
    quote = get_quote_by_id(g.session, quote_id)
    if delete_quote(g.session, quote_id):
        flash(f'Quote "{quote.quote_number}" deleted.', 'success')
    else:
        flash('Error deleting quote.', 'error')
    return redirect(url_for('quote.list_all'))

@quote_bp.route('/convert_to_invoice/<int:quote_id>', methods=['POST'])
def convert_to_invoice_route(quote_id):
    success, message_or_invoice = convert_quote_to_invoice(g.session, quote_id)
    if success:
        flash(f'Quote converted to invoice successfully! Invoice # {message_or_invoice.invoice_number}', 'success')
        return redirect(url_for('invoice.detail', invoice_id=message_or_invoice.id))
    else:
        flash(f'Failed to convert quote: {message_or_invoice}', 'error')
        return redirect(url_for('quote.detail', quote_id=quote_id))
