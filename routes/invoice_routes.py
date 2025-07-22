# routes/invoice_routes.py

from flask import Blueprint, render_template, g, request, redirect, url_for, flash
from crm_manager import list_invoices, get_invoice_by_id, add_invoice, update_invoice, delete_invoice
from crm_database import Contact, Property, Job, Quote
from datetime import datetime

invoice_bp = Blueprint('invoice', __name__, url_prefix='/invoices')

def get_invoice_statuses():
    return ['All', 'issued', 'paid', 'partially_paid', 'overdue', 'cancelled']

@invoice_bp.route('/')
def list_all():
    invoices = list_invoices(g.session, 
                             status=request.args.get('status'),
                             contact_id=request.args.get('contact_id', type=int),
                             property_id=request.args.get('property_id', type=int),
                             job_id=request.args.get('job_id', type=int),
                             quote_id=request.args.get('quote_id', type=int))
                             
    contacts = g.session.query(Contact).order_by(Contact.first_name).all()
    properties = g.session.query(Property).order_by(Property.address).all()
    jobs = g.session.query(Job).order_by(Job.job_name).all()
    quotes = g.session.query(Quote).order_by(Quote.quote_number).all()

    return render_template('invoice_list.html',
                           invoices=invoices,
                           invoice_statuses=get_invoice_statuses(),
                           contacts=contacts,
                           properties=properties,
                           jobs=jobs,
                           quotes=quotes,
                           current_status=request.args.get('status'),
                           current_contact_id=request.args.get('contact_id', type=int),
                           current_property_id=request.args.get('property_id', type=int),
                           current_job_id=request.args.get('job_id', type=int),
                           current_quote_id=request.args.get('quote_id', type=int))

@invoice_bp.route('/<int:invoice_id>')
def detail(invoice_id):
    invoice = get_invoice_by_id(g.session, invoice_id)
    if not invoice:
        flash('Invoice not found.', 'error')
        return redirect(url_for('invoice.list_all'))
    return render_template('invoice_detail.html', invoice=invoice)

@invoice_bp.route('/add', methods=['GET', 'POST'])
def add():
    contacts = g.session.query(Contact).order_by(Contact.first_name).all()
    properties = g.session.query(Property).order_by(Property.address).all()
    quotes = g.session.query(Quote).order_by(Quote.quote_number).all()

    if request.method == 'POST':
        issue_date = datetime.strptime(request.form['issue_date'], '%Y-%m-%d') if request.form.get('issue_date') else None
        due_date = datetime.strptime(request.form['due_date'], '%Y-%m-%d') if request.form.get('due_date') else None
        paid_date = datetime.strptime(request.form['paid_date'], '%Y-%m-%d') if request.form.get('paid_date') else None

        new_invoice = add_invoice(g.session,
                                  contact_id=request.form.get('contact_id', type=int),
                                  invoice_number=request.form['invoice_number'],
                                  amount=request.form.get('amount', type=float),
                                  issue_date=issue_date,
                                  status=request.form.get('status', 'issued'),
                                  property_id=request.form.get('property_id', type=int),
                                  quote_id=request.form.get('quote_id', type=int),
                                  due_date=due_date,
                                  paid_date=paid_date,
                                  payment_method=request.form.get('payment_method'),
                                  details=request.form.get('details'))
        if new_invoice:
            flash('Invoice added successfully!', 'success')
            return redirect(url_for('invoice.list_all'))
        else:
            flash('Error adding invoice.', 'error')
            
    return render_template('add_edit_invoice_form.html', form_title="Add New Invoice", contacts=contacts, properties=properties, quotes=quotes, invoice_statuses=get_invoice_statuses())

@invoice_bp.route('/edit/<int:invoice_id>', methods=['GET', 'POST'])
def edit(invoice_id):
    invoice = get_invoice_by_id(g.session, invoice_id)
    if not invoice:
        flash('Invoice not found.', 'error')
        return redirect(url_for('invoice.list_all'))

    if request.method == 'POST':
        update_data = request.form.to_dict()
        for date_field in ['issue_date', 'due_date', 'paid_date']:
            if update_data.get(date_field):
                update_data[date_field] = datetime.strptime(update_data[date_field], '%Y-%m-%d')
            else:
                update_data[date_field] = None
        
        if update_invoice(g.session, invoice_id, **update_data):
            flash('Invoice updated successfully!', 'success')
            return redirect(url_for('invoice.detail', invoice_id=invoice_id))
        else:
            flash('Error updating invoice.', 'error')

    contacts = g.session.query(Contact).order_by(Contact.first_name).all()
    properties = g.session.query(Property).order_by(Property.address).all()
    quotes = g.session.query(Quote).order_by(Quote.quote_number).all()
    return render_template('add_edit_invoice_form.html', invoice=invoice, form_title="Edit Invoice", contacts=contacts, properties=properties, quotes=quotes, invoice_statuses=get_invoice_statuses())

@invoice_bp.route('/delete/<int:invoice_id>', methods=['POST'])
def delete(invoice_id):
    invoice = get_invoice_by_id(g.session, invoice_id)
    if delete_invoice(g.session, invoice_id):
        flash(f'Invoice "{invoice.invoice_number}" deleted.', 'success')
    else:
        flash('Error deleting invoice.', 'error')
    return redirect(url_for('invoice.list_all'))
