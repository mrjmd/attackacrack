from flask import Blueprint, render_template, current_app, redirect, url_for, request, flash
from extensions import db
from crm_database import Contact, Property, Job, Appointment, Invoice, Quote
from crm_manager import CrmManager
from csv_importer import CsvImporter
from property_radar_importer import PropertyRadarImporter
from werkzeug.utils import secure_filename
import os
from datetime import datetime

main_bp = Blueprint('main', __name__)
crm_manager = CrmManager(db.session)

@main_bp.route('/')
def index():
    return redirect(url_for('main.dashboard'))

@main_bp.route('/dashboard')
def dashboard():
    stats = {
        'contact_count': db.session.query(Contact).count(),
        'property_count': db.session.query(Property).count(),
        'active_jobs': db.session.query(Job).filter(Job.status == 'Active').count(),
        'pending_quotes': db.session.query(Quote).filter(Quote.status == 'Sent').count()
    }
    upcoming_appointments = db.session.query(Appointment).filter(
        Appointment.date >= datetime.utcnow().date()
    ).order_by(Appointment.date, Appointment.time).limit(5).all()
    return render_template('dashboard.html', stats=stats, appointments=upcoming_appointments)

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
            
            importer = CsvImporter(crm_manager)
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

            importer = PropertyRadarImporter(crm_manager)
            importer.import_data(filepath)

            flash('Property Radar data imported successfully!')
            return redirect(url_for('property.properties'))

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
