from flask import Blueprint, render_template, request, redirect, url_for
from services.appointment_service import AppointmentService
from services.contact_service import ContactService
from services.message_service import MessageService
from services.ai_service import AIService
from datetime import datetime

appointment_bp = Blueprint('appointment', __name__)

@appointment_bp.route('/')
def list_all():
    appointment_service = AppointmentService()
    all_appointments = appointment_service.get_all_appointments()
    return render_template('appointment_list.html', appointments=all_appointments)

@appointment_bp.route('/<int:appointment_id>')
def appointment_detail(appointment_id):
    appointment_service = AppointmentService()
    appointment = appointment_service.get_appointment_by_id(appointment_id)
    return render_template('appointment_detail.html', appointment=appointment)

@appointment_bp.route('/add', methods=['GET', 'POST'])
def add_appointment():
    appointment_service = AppointmentService()
    contact_service = ContactService()

    if request.method == 'POST':
        appointment_service.add_appointment(
            title=request.form['title'],
            description=request.form['description'],
            date=datetime.strptime(request.form['date'], '%Y-%m-%d').date(),
            time=datetime.strptime(request.form['time'], '%H:%M').time(),
            contact_id=request.form['contact_id'],
            appt_type=request.form['appt_type']
        )
        return redirect(url_for('appointment.list_all'))

    # --- FIX FOR TypeError ---
    # Initialize prefilled_data with a null contact_id
    contact_id = request.args.get('contact_id', type=int)
    appt_type = request.args.get('type', 'Appointment')
    prefilled_data = {'appt_type': appt_type, 'contact_id': None} 
    
    if contact_id:
        contact = contact_service.get_contact_by_id(contact_id)
        if contact:
            prefilled_data['contact_id'] = contact.id
            prefilled_data['title'] = f"{appt_type}: {contact.first_name} {contact.last_name}"
    # --- END FIX ---

    contacts = contact_service.get_all_contacts()
    return render_template('add_edit_appointment_form.html', contacts=contacts, prefilled=prefilled_data)

@appointment_bp.route('/<int:appointment_id>/edit', methods=['GET', 'POST'])
def edit_appointment(appointment_id):
    # This function will need a similar update if you enable the edit button
    appointment_service = AppointmentService()
    contact_service = ContactService()
    appointment = appointment_service.get_appointment_by_id(appointment_id)
    # ... (rest of edit logic)
    contacts = contact_service.get_all_contacts()
    return render_template('add_edit_appointment_form.html', appointment=appointment, contacts=contacts, prefilled={})


@appointment_bp.route('/<int:appointment_id>/delete', methods=['POST'])
def delete_appointment(appointment_id):
    # --- FIX FOR NameError ---
    # Instantiate the service inside the function
    appointment_service = AppointmentService()
    # --- END FIX ---
    appointment = appointment_service.get_appointment_by_id(appointment_id)
    if appointment:
        appointment_service.delete_appointment(appointment)
    return redirect(url_for('appointment.list_all'))
