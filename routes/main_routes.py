from flask import Blueprint, render_template, redirect, url_for, request, flash
from werkzeug.utils import secure_filename
import os
from datetime import datetime

from services.contact_service import ContactService
from services.property_service import PropertyService
from services.job_service import JobService
from services.quote_service import QuoteService
from services.appointment_service import AppointmentService
from csv_importer import CsvImporter
from property_radar_importer import PropertyRadarImporter
from api_integrations import get_upcoming_calendar_events, get_recent_gmail_messages, get_recent_openphone_texts

main_bp = Blueprint('main', __name__)
contact_service = ContactService()
property_service = PropertyService()
job_service = JobService()
quote_service = QuoteService()
appointment_service = AppointmentService()


@main_bp.route('/')
def index():
    return redirect(url_for('main.dashboard'))

@main_bp.route('/dashboard')
def dashboard():
    stats = {
        'contact_count': len(contact_service.get_all_contacts()),
        'property_count': len(property_service.get_all_properties()),
        'active_jobs': len([j for j in job_service.get_all_jobs() if j.status == 'Active']),
        'pending_quotes': len([q for q in quote_service.get_all_quotes() if q.status == 'Sent'])
    }
    
    internal_appointments = appointment_service.get_all_appointments()

    google_events = get_upcoming_calendar_events()
    gmail_messages = get_recent_gmail_messages()
    openphone_texts, openphone_error = get_recent_openphone_texts()

    return render_template(
        'dashboard.html', 
        stats=stats, 
        appointments=internal_appointments,
        google_events=google_events,
        gmail_messages=gmail_messages,
        openphone_texts=openphone_texts,
        openphone_error=openphone_error
    )

@main_bp.route('/settings')
def settings():
    return render_template('settings.html')

@main_bp.route('/import_csv', methods=['GET', 'POST'])
def import_csv():
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file part')
            return redirect(request.url)
        file = request.files['file']
        if file.filename == '':
            flash('No selected file')
            return redirect(request.url)
        if file:
            filename = secure_filename(file.filename)
            filepath = os.path.join('/tmp', filename)
            file.save(filepath)
            
            # Correctly initialize the importer with the ContactService
            importer = CsvImporter(contact_service)
            importer.import_data(filepath)
            
            flash('CSV data imported successfully!')
            return redirect(url_for('contact.list_all'))
            
    return render_template('import_csv.html')

@main_bp.route('/import_property_radar', methods=['GET', 'POST'])
def import_property_radar():
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file part')
            return redirect(request.url)
        file = request.files['file']
        if file.filename == '':
            flash('No selected file')
            return redirect(request.url)
        if file:
            filename = secure_filename(file.filename)
            filepath = os.path.join('/tmp', filename)
            file.save(filepath)

            # Correctly initialize the importer with both required services
            importer = PropertyRadarImporter(contact_service, property_service)
            importer.import_data(filepath)

            flash('Property Radar data imported successfully!')
            return redirect(url_for('property.list_all'))

    return render_template('import_property_radar.html')


# --- Placeholder routes from original file ---
@main_bp.route('/customers')
def customers():
    return render_template('customers.html')

@main_bp.route('/finances')
def finances():
    return render_template('finances.html')

@main_bp.route('/marketing')
def marketing():
    return render_template('marketing.html')
