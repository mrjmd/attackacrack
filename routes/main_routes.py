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
from extensions import db
from crm_database import Setting

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    return redirect(url_for('main.dashboard'))

@main_bp.route('/dashboard')
def dashboard():
    contact_service = ContactService()
    property_service = PropertyService()
    job_service = JobService()
    quote_service = QuoteService()
    appointment_service = AppointmentService()
    
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

@main_bp.route('/settings/automation', methods=['GET', 'POST'])
def automation_settings():
    if request.method == 'POST':
        form_type = request.form.get('form_type')
        
        if form_type == 'reminder':
            template_key = 'appointment_reminder_template'
            template_text = request.form.get('reminder_template')
            flash_message = 'Reminder template saved successfully!'
        elif form_type == 'review':
            template_key = 'review_request_template'
            template_text = request.form.get('review_template')
            flash_message = 'Review request template saved successfully!'
        else:
            flash('Invalid form submission.', 'error')
            return redirect(url_for('main.automation_settings'))

        setting = db.session.query(Setting).filter_by(key=template_key).first()
        if setting:
            setting.value = template_text
        else:
            setting = Setting(key=template_key, value=template_text)
            db.session.add(setting)
        
        db.session.commit()
        flash(flash_message, 'success')
        return redirect(url_for('main.automation_settings'))

    # For GET request, fetch both templates
    reminder_setting = db.session.query(Setting).filter_by(key='appointment_reminder_template').first()
    review_setting = db.session.query(Setting).filter_by(key='review_request_template').first()

    reminder_text = reminder_setting.value if reminder_setting else "Hi [contact_first_name], this is a reminder for your appointment with Attack-a-Crack on [appointment_date] at [appointment_time]."
    review_text = review_setting.value if review_setting else "Hi [contact_first_name], we hope you're happy with the work we did! If you have a moment, we'd love it if you could leave us a review on Google: [Your Google Review Link]"
    
    return render_template('automation_settings.html', reminder_template_text=reminder_text, review_template_text=review_text)

@main_bp.route('/import_csv', methods=['GET', 'POST'])
def import_csv():
    contact_service = ContactService()
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
            
            importer = CsvImporter(contact_service)
            importer.import_data(filepath)
            
            flash('CSV data imported successfully!')
            return redirect(url_for('contact.list_all'))
            
    return render_template('import_csv.html')

@main_bp.route('/import_property_radar', methods=['GET', 'POST'])
def import_property_radar():
    contact_service = ContactService()
    property_service = PropertyService()
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
