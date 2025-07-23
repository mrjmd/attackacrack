from flask import Blueprint, render_template, request, redirect, url_for
from services.appointment_service import AppointmentService
from services.contact_service import ContactService
from datetime import datetime

appointment_bp = Blueprint('appointment', __name__)
appointment_service = AppointmentService()
contact_service = ContactService()

@appointment_bp.route('/')
def list_all():
    all_appointments = appointment_service.get_all_appointments()
    return render_template('appointment_list.html', appointments=all_appointments)

@appointment_bp.route('/<int:appointment_id>')
def appointment_detail(appointment_id):
    appointment = appointment_service.get_appointment_by_id(appointment_id)
    return render_template('appointment_detail.html', appointment=appointment)

@appointment_bp.route('/add', methods=['GET', 'POST'])
def add_appointment():
    if request.method == 'POST':
        appointment_service.add_appointment(
            title=request.form['title'],
            date=datetime.strptime(request.form['date'], '%Y-%m-%d').date(),
            time=datetime.strptime(request.form['time'], '%H:%M').time(),
            contact_id=request.form['contact_id']
        )
        return redirect(url_for('appointment.list_all'))
    contacts = contact_service.get_all_contacts()
    return render_template('add_edit_appointment_form.html', contacts=contacts)

@appointment_bp.route('/<int:appointment_id>/edit', methods=['GET', 'POST'])
def edit_appointment(appointment_id):
    appointment = appointment_service.get_appointment_by_id(appointment_id)
    if request.method == 'POST':
        appointment_service.update_appointment(
            appointment,
            title=request.form['title'],
            date=datetime.strptime(request.form['date'], '%Y-%m-%d').date(),
            time=datetime.strptime(request.form['time'], '%H:%M').time(),
            contact_id=request.form['contact_id']
        )
        return redirect(url_for('appointment.appointment_detail', appointment_id=appointment.id))
    contacts = contact_service.get_all_contacts()
    return render_template('add_edit_appointment_form.html', appointment=appointment, contacts=contacts)

@appointment_bp.route('/<int:appointment_id>/delete', methods=['POST'])
def delete_appointment(appointment_id):
    appointment = appointment_service.get_appointment_by_id(appointment_id)
    appointment_service.delete_appointment(appointment)
    return redirect(url_for('appointment.list_all'))
