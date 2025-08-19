from flask import Blueprint, render_template, request, redirect, url_for, current_app
from flask_login import login_required
from datetime import datetime

appointment_bp = Blueprint('appointment', __name__)

@appointment_bp.route('/')
@login_required
def list_all():
    appointment_service = current_app.services.get('appointment')
    result = appointment_service.get_all_appointments()
    if result.is_success:
        all_appointments = result.data
    else:
        all_appointments = []
        current_app.logger.error(f"Failed to get appointments: {result.error}")
    return render_template('appointment_list.html', appointments=all_appointments)

@appointment_bp.route('/<int:appointment_id>')
@login_required
def appointment_detail(appointment_id):
    appointment_service = current_app.services.get('appointment')
    result = appointment_service.get_appointment_by_id(appointment_id)
    if result.is_success:
        appointment = result.data
    else:
        appointment = None
        current_app.logger.error(f"Failed to get appointment: {result.error}")
    return render_template('appointment_detail.html', appointment=appointment)

@appointment_bp.route('/add', methods=['GET', 'POST'])
@login_required
def add_appointment():
    appointment_service = current_app.services.get('appointment')
    contact_service = current_app.services.get('contact')

    if request.method == 'POST':
        result = appointment_service.add_appointment(
            title=request.form['title'],
            description=request.form['description'],
            date=datetime.strptime(request.form['date'], '%Y-%m-%d').date(),
            time=datetime.strptime(request.form['time'], '%H:%M').time(),
            contact_id=request.form['contact_id'],
            appt_type=request.form['appt_type']
        )
        if result.is_failure:
            current_app.logger.error(f"Failed to add appointment: {result.error}")
        return redirect(url_for('appointment.list_all'))

    # --- FIX FOR TypeError ---
    # Initialize prefilled_data with a null contact_id
    contact_id = request.args.get('contact_id', type=int)
    appt_type = request.args.get('type', 'Appointment')
    prefilled_data = {'appt_type': appt_type, 'contact_id': None} 
    
    if contact_id:
        contact_result = contact_service.get_contact_by_id(contact_id)
        if contact_result and contact_result.is_success:
            contact = contact_result.data
            if contact:
                prefilled_data['contact_id'] = contact.id
                prefilled_data['title'] = f"{appt_type}: {contact.first_name} {contact.last_name}"
    # --- END FIX ---

    contacts_result = contact_service.get_all_contacts()
    contacts = contacts_result.data if contacts_result and contacts_result.is_success else []
    return render_template('add_edit_appointment_form.html', contacts=contacts, prefilled=prefilled_data)

@appointment_bp.route('/<int:appointment_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_appointment(appointment_id):
    # This function will need a similar update if you enable the edit button
    appointment_service = current_app.services.get('appointment')
    contact_service = current_app.services.get('contact')
    result = appointment_service.get_appointment_by_id(appointment_id)
    appointment = result.data if result and result.is_success else None
    # ... (rest of edit logic)
    contacts_result = contact_service.get_all_contacts()
    contacts = contacts_result.data if contacts_result and contacts_result.is_success else []
    return render_template('add_edit_appointment_form.html', appointment=appointment, contacts=contacts, prefilled={})


@appointment_bp.route('/<int:appointment_id>/delete', methods=['POST'])
@login_required
def delete_appointment(appointment_id):
    appointment_service = current_app.services.get('appointment')
    result = appointment_service.get_appointment_by_id(appointment_id)
    if result and result.is_success:
        appointment = result.data
        if appointment:
            delete_result = appointment_service.delete_appointment(appointment)
            if delete_result.is_failure:
                current_app.logger.error(f"Failed to delete appointment: {delete_result.error}")
    return redirect(url_for('appointment.list_all'))
