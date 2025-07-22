# routes/appointment_routes.py

from flask import Blueprint, render_template, g, request, redirect, url_for, flash
from crm_manager import list_appointments, get_appointment_by_id, add_appointment, update_appointment, delete_appointment
from crm_database import Contact, Property, Job
from datetime import datetime

appointment_bp = Blueprint('appointment', __name__, url_prefix='/appointments')

def get_appointment_types():
    return ['All', 'initial_consult', 'estimate', 'job_start', 'follow_up', 'site_visit', 'other']

def get_appointment_statuses():
    return ['All', 'scheduled', 'completed', 'cancelled', 'no_show', 'rescheduled']

@appointment_bp.route('/')
def list_all():
    appointments = list_appointments(g.session, 
                                     status=request.args.get('status'),
                                     appointment_type=request.args.get('appointment_type'),
                                     contact_id=request.args.get('contact_id', type=int),
                                     property_id=request.args.get('property_id', type=int),
                                     job_id=request.args.get('job_id', type=int))
                                     
    contacts = g.session.query(Contact).order_by(Contact.first_name).all()
    properties = g.session.query(Property).order_by(Property.address).all()
    jobs = g.session.query(Job).order_by(Job.job_name).all()

    return render_template('appointment_list.html',
                           appointments=appointments,
                           appointment_types=get_appointment_types(),
                           appointment_statuses=get_appointment_statuses(),
                           contacts=contacts,
                           properties=properties,
                           jobs=jobs,
                           current_status=request.args.get('status'),
                           current_appointment_type=request.args.get('appointment_type'),
                           current_contact_id=request.args.get('contact_id', type=int),
                           current_property_id=request.args.get('property_id', type=int),
                           current_job_id=request.args.get('job_id', type=int))

@appointment_bp.route('/<int:appointment_id>')
def detail(appointment_id):
    appt = get_appointment_by_id(g.session, appointment_id)
    if not appt:
        flash('Appointment not found.', 'error')
        return redirect(url_for('appointment.list_all'))
    return render_template('appointment_detail.html', appointment=appt)

@appointment_bp.route('/add', methods=['GET', 'POST'])
def add():
    contacts = g.session.query(Contact).order_by(Contact.first_name).all()
    properties = g.session.query(Property).order_by(Property.address).all()
    if request.method == 'POST':
        scheduled_time_str = f"{request.form['scheduled_date']} {request.form.get('scheduled_time', '00:00')}"
        scheduled_time = datetime.strptime(scheduled_time_str, '%Y-%m-%d %H:%M')
        
        new_appt = add_appointment(g.session,
                                   contact_id=request.form.get('contact_id', type=int),
                                   appointment_type=request.form['appointment_type'],
                                   scheduled_time=scheduled_time,
                                   property_id=request.form.get('property_id', type=int),
                                   status=request.form.get('status', 'scheduled'),
                                   notes=request.form.get('notes'))
        if new_appt:
            flash('Appointment added successfully!', 'success')
            return redirect(url_for('appointment.list_all'))
        else:
            flash('Error adding appointment.', 'error')

    return render_template('add_edit_appointment_form.html', form_title="Add New Appointment", 
                           contacts=contacts, properties=properties, 
                           appointment_types=get_appointment_types(), 
                           appointment_statuses=get_appointment_statuses())

@appointment_bp.route('/edit/<int:appointment_id>', methods=['GET', 'POST'])
def edit(appointment_id):
    appt = get_appointment_by_id(g.session, appointment_id)
    if not appt:
        flash('Appointment not found.', 'error')
        return redirect(url_for('appointment.list_all'))

    if request.method == 'POST':
        update_data = request.form.to_dict()
        scheduled_time_str = f"{request.form['scheduled_date']} {request.form.get('scheduled_time', '00:00')}"
        update_data['scheduled_time'] = datetime.strptime(scheduled_time_str, '%Y-%m-%d %H:%M')
        
        if update_appointment(g.session, appointment_id, **update_data):
            flash('Appointment updated successfully!', 'success')
            return redirect(url_for('appointment.detail', appointment_id=appointment_id))
        else:
            flash('Error updating appointment.', 'error')

    contacts = g.session.query(Contact).order_by(Contact.first_name).all()
    properties = g.session.query(Property).order_by(Property.address).all()
    return render_template('add_edit_appointment_form.html', appointment=appt, form_title="Edit Appointment",
                           contacts=contacts, properties=properties,
                           appointment_types=get_appointment_types(),
                           appointment_statuses=get_appointment_statuses())

@appointment_bp.route('/delete/<int:appointment_id>', methods=['POST'])
def delete(appointment_id):
    appt = get_appointment_by_id(g.session, appointment_id)
    if delete_appointment(g.session, appointment_id):
        flash(f'Appointment "{appt.appointment_type}" deleted.', 'success')
    else:
        flash('Error deleting appointment.', 'error')
    return redirect(url_for('appointment.list_all'))
