# app.py

from flask import Flask, render_template, g, request, redirect, url_for, flash, jsonify, session
from flask_cors import CORS
from crm_database import setup_database, Contact, ContactDetail, Property, ContactProperty, Job, Quote, Invoice, Appointment
from crm_manager import (
    add_contact, get_contact_by_id, list_contacts, update_contact, delete_contact,
    add_property, get_property_by_id, list_properties, update_property, delete_property,
    link_contact_to_property,
    add_job, get_job_by_id, list_jobs, update_job, delete_job,
    add_appointment, get_appointment_by_id, list_appointments, update_appointment, delete_appointment,
    add_quote, get_quote_by_id, list_quotes, update_quote, delete_quote,
    add_invoice, get_invoice_by_id, list_invoices, update_invoice, delete_invoice,
    convert_quote_to_invoice,
    find_or_create_job,
    IntegrationManager,
    list_customers # Import the new function
)
from property_radar_importer import run_property_radar_import
from csv_importer import import_contacts_from_csv
from sqlalchemy.orm import sessionmaker
from sqlalchemy import func
from datetime import datetime
import os

app = Flask(__name__, template_folder='templates')
app.secret_key = os.urandom(24)
CORS(app)

app.config['UPLOAD_FOLDER'] = 'uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

Session = sessionmaker(bind=setup_database().bind)
integration_manager = IntegrationManager()

@app.before_request
def before_request():
    g.session = Session()

@app.teardown_request
def teardown_request(exception):
    session = g.pop('session', None)
    if session is not None:
        session.close()

# --- Main & Auth Routes ---
@app.route('/')
def index():
    return render_template('dashboard.html')

@app.route('/settings')
def settings_page():
    return render_template('settings.html')

# --- NEW SECTION ROUTES ---
@app.route('/customers')
def customers_page():
    search_name = request.args.get('search_name', '').strip() or None
    customers = list_customers(g.session, search_name=search_name)
    return render_template('customers.html', 
                           customers=customers, 
                           current_search_name=request.args.get('search_name', ''))

@app.route('/marketing')
def marketing_page():
    return render_template('marketing.html')

@app.route('/finances')
def finances_page():
    return render_template('finances.html')


@app.route('/authorize/google')
def authorize_google():
    try:
        flow = integration_manager.get_google_auth_flow()
        authorization_url, state = flow.authorization_url(access_type='offline', include_granted_scopes='true')
        session['state'] = state
        return redirect(authorization_url)
    except FileNotFoundError as e:
        flash(str(e), 'error')
        return redirect(url_for('settings_page'))
    except Exception as e:
        flash(f"An error occurred during Google authorization: {e}", 'error')
        return redirect(url_for('settings_page'))

@app.route('/oauth2callback')
def oauth2callback():
    state = session['state']
    flow = integration_manager.get_google_auth_flow()
    flow.redirect_uri = url_for('oauth2callback', _external=True, _scheme='https')
    flow.fetch_token(authorization_response=request.url)
    credentials = flow.credentials
    integration_manager.save_google_credentials(credentials)
    flash('Google Account connected successfully!', 'success')
    return redirect(url_for('index'))

# --- API Endpoints for Dashboard ---
@app.route('/api/metrics')
def api_get_metrics():
    try:
        new_leads = g.session.query(Contact).filter(Contact.contact_status == 'new_lead').count()
        deals_won = g.session.query(Job).filter(Job.job_status == 'completed').count()
        current_month = datetime.now().month
        current_year = datetime.now().year
        revenue_this_month = g.session.query(func.sum(Invoice.amount)).filter(
            func.extract('month', Invoice.paid_date) == current_month,
            func.extract('year', Invoice.paid_date) == current_year,
            Invoice.status == 'paid'
        ).scalar() or 0
        total_quotes_sent = g.session.query(Quote).filter(Quote.status.in_(['sent', 'accepted', 'rejected', 'invoiced'])).count()
        conversion_rate = (deals_won / total_quotes_sent * 100) if total_quotes_sent > 0 else 0
        return jsonify({
            "new_leads": new_leads, 
            "deals_won": deals_won, 
            "revenue": round(revenue_this_month, 2), 
            "conversion_rate": round(conversion_rate, 1)
        })
    except Exception as e:
        print(f"--- ERROR fetching metrics: {e} ---")
        return jsonify({"error": "Could not fetch metrics"}), 500

@app.route('/api/pipeline')
def api_get_pipeline():
    try:
        pipeline_data = [
            { "name": "New Leads", "value": g.session.query(Contact).filter(Contact.contact_status == 'new_lead').count(), "color": "bg-gray-500" },
            { "name": "Quoted", "value": g.session.query(Quote).filter(Quote.status.in_(['draft', 'sent'])).count(), "color": "bg-blue-500" },
            { "name": "Accepted", "value": g.session.query(Quote).filter(Quote.status == 'accepted').count(), "color": "bg-indigo-500" },
            { "name": "Jobs In Progress", "value": g.session.query(Job).filter(Job.job_status == 'in_progress').count(), "color": "bg-purple-500" },
            { "name": "Jobs Completed", "value": g.session.query(Job).filter(Job.job_status == 'completed').count(), "color": "bg-green-500" },
        ]
        return jsonify(pipeline_data)
    except Exception as e:
        print(f"--- ERROR fetching pipeline data: {e} ---")
        return jsonify({"error": "Could not fetch pipeline data"}), 500

@app.route('/api/tasks')
def api_get_tasks():
    return jsonify([
        { "text": "Follow up with Acme Corp", "due": "Today", "completed": False },
        { "text": "Prepare presentation for Globex", "due": "Tomorrow", "completed": False }
    ])

@app.route('/api/calendar-events')
def api_get_calendar_events():
    if not integration_manager.is_google_authenticated():
        return jsonify({"error": "Google account not authenticated"}), 401
    events = integration_manager.get_calendar_events()
    return jsonify(events)

@app.route('/api/emails')
def api_get_emails():
    if not integration_manager.is_google_authenticated():
        return jsonify({"error": "Google account not authenticated"}), 401
    emails = integration_manager.get_recent_emails()
    return jsonify(emails)

@app.route('/api/texts')
def api_get_texts():
    if not integration_manager.is_openphone_configured():
        return jsonify({"error": "OpenPhone API key not configured"}), 401
    texts = integration_manager.get_recent_texts()
    return jsonify(texts)

@app.route('/api/settings', methods=['GET', 'POST'])
def api_manage_settings():
    if request.method == 'POST':
        data = request.get_json()
        if not data:
            return jsonify({"error": "Invalid JSON"}), 400
        openphone_key = data.get('openphone_api_key')
        if openphone_key:
            integration_manager.save_openphone_key(openphone_key)
            return jsonify({"message": "Settings saved successfully"}), 200
        return jsonify({"error": "Invalid data"}), 400
    else:
        return jsonify({"openphone_api_key": integration_manager.openphone_api_key})

# --- Helper Functions (for dropdowns) ---
def get_contact_types(): return ['All', 'homeowner', 'realtor', 'property_manager', 'inspector', 'builder', 'other']
def get_contact_statuses(): return ['All', 'new_lead', 'contacted', 'active', 'do_not_contact', 'archived']
def get_customer_statuses(): return ['All', 'not_customer', 'quoted', 'job_completed', 'repeat_customer']
def get_payment_statuses(): return ['All', 'no_payment_due', 'payment_pending', 'payment_collected', 'overdue']
def get_job_statuses(): return ['All', 'pending', 'in_progress', 'completed', 'on_hold']
def get_appointment_types(): return ['All', 'initial_consult', 'estimate', 'job_start', 'follow_up', 'site_visit', 'other']
def get_appointment_statuses(): return ['All', 'scheduled', 'completed', 'cancelled', 'no_show', 'rescheduled']
def get_quote_statuses(): return ['All', 'draft', 'sent', 'accepted', 'rejected', 'expired', 'invoiced']
def get_invoice_statuses(): return ['All', 'issued', 'paid', 'partially_paid', 'overdue', 'cancelled']

# --- Contact Routes ---
@app.route('/contacts_list')
def contacts_list_page():
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
    return render_template('contact_list.html', contacts=contacts, contact_types=get_contact_types(), contact_statuses=get_contact_statuses(), customer_statuses=get_customer_statuses(), payment_statuses=get_payment_statuses(), current_contact_type=filters['contact_type'], current_contact_status=filters['contact_status'], current_customer_status=filters['customer_status'], current_payment_status=filters['payment_status'], current_has_open_estimates=filters['has_open_estimates'], current_has_unpaid_invoices=filters['has_unpaid_invoices'], current_search_name=request.args.get('search_name', ''))

@app.route('/contacts/<int:contact_id>')
def contact_detail(contact_id):
    contact = get_contact_by_id(g.session, contact_id)
    if not contact:
        flash('Contact not found.', 'error')
        return redirect(url_for('contacts_list_page'))
    return render_template('contact_detail.html', contact=contact)

@app.route('/add_contact', methods=['GET', 'POST'])
def add_new_contact():
    if request.method == 'POST':
        phone_numbers = [{'value': v, 'label': l} for v, l in zip(request.form.getlist('phone_value[]'), request.form.getlist('phone_label[]')) if v]
        emails = [{'value': v, 'label': l} for v, l in zip(request.form.getlist('email_value[]'), request.form.getlist('email_label[]')) if v]
        new_contact = add_contact(g.session, first_name=request.form['first_name'], last_name=request.form['last_name'], contact_type=request.form['contact_type'], notes=request.form.get('notes'), phone_numbers=phone_numbers, emails=emails)
        if new_contact:
            flash(f'Contact "{new_contact.first_name} {new_contact.last_name}" added successfully!', 'success')
            return redirect(url_for('contacts_list_page'))
        else:
            flash('Error adding contact.', 'error')
    return render_template('add_edit_contact_form.html', form_title="Add New Contact", contact_types=get_contact_types())

@app.route('/edit_contact/<int:contact_id>', methods=['GET', 'POST'])
def edit_existing_contact(contact_id):
    contact = get_contact_by_id(g.session, contact_id)
    if not contact:
        flash('Contact not found.', 'error')
        return redirect(url_for('contacts_list_page'))
    if request.method == 'POST':
        if update_contact(g.session, contact_id, first_name=request.form['first_name'], last_name=request.form['last_name'], contact_type=request.form['contact_type'], new_contact_status=request.form['contact_status'], new_customer_status=request.form['customer_status'], new_payment_status=request.form['payment_status'], notes=request.form.get('notes')):
            flash('Contact updated successfully!', 'success')
            return redirect(url_for('contacts_list_page'))
        else:
            flash('Error updating contact.', 'error')
    return render_template('add_edit_contact_form.html', contact=contact, form_title="Edit Contact", contact_types=get_contact_types(), contact_statuses=get_contact_statuses(), customer_statuses=get_customer_statuses(), payment_statuses=get_payment_statuses())

@app.route('/delete_contact/<int:contact_id>', methods=['POST'])
def delete_existing_contact(contact_id):
    contact = get_contact_by_id(g.session, contact_id)
    if delete_contact(g.session, contact_id):
        flash(f'Contact "{contact.first_name} {contact.last_name}" deleted.', 'success')
    else:
        flash('Error deleting contact.', 'error')
    return redirect(url_for('contacts_list_page'))

# --- Import Routes ---
@app.route('/import_property_radar', methods=['GET', 'POST'])
def import_property_radar_data():
    if request.method == 'POST':
        # ... (code for this route is unchanged)
        return redirect(url_for('contacts_list_page'))
    return render_template('import_property_radar.html', form_title="Import PropertyRadar Data", now=datetime.now)

@app.route('/import_csv', methods=['GET', 'POST'])
def import_csv_data():
    if request.method == 'POST':
        # ... (code for this route is unchanged)
        return redirect(url_for('contacts_list_page'))
    return render_template('import_csv.html', form_title="Import Contacts from CSV", contact_types=get_contact_types())

# --- Property Routes ---
@app.route('/properties')
def property_list():
    filters = { 'city': request.args.get('city'), 'zip_code': request.args.get('zip_code'), 'min_value': request.args.get('min_value', type=int), 'has_foreclosure': request.args.get('has_foreclosure') == 'true' }
    properties = list_properties(g.session, **filters)
    return render_template('property_list.html', properties=properties, current_city=filters['city'], current_zip_code=filters['zip_code'], current_min_value=filters['min_value'], current_has_foreclosure=filters['has_foreclosure'])

@app.route('/properties/<int:property_id>')
def property_detail(property_id):
    prop = get_property_by_id(g.session, property_id)
    if not prop:
        flash('Property not found.', 'error')
        return redirect(url_for('property_list'))
    return render_template('property_detail.html', property=prop)

# ... (All other routes for properties, jobs, quotes, invoices, appointments follow here)

if __name__ == '__main__':
    app.run(port=5000, debug=True, ssl_context='adhoc')
