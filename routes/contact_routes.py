from flask import Blueprint, render_template, request, redirect, url_for, current_app
from services.contact_service import ContactService
from services.message_service import MessageService

contact_bp = Blueprint('contact', __name__)

@contact_bp.route('/')
def list_all():
    contact_service = ContactService()
    all_contacts = contact_service.get_all_contacts()
    return render_template('contact_list.html', contacts=all_contacts)

@contact_bp.route('/conversations')
def conversation_list():
    message_service = MessageService()
    latest_messages = message_service.get_latest_conversations(limit=25)
    return render_template('conversation_list.html', messages=latest_messages)

@contact_bp.route('/<int:contact_id>')
def contact_detail(contact_id):
    contact_service = ContactService()
    message_service = MessageService()
    contact = contact_service.get_contact_by_id(contact_id)
    
    recent_messages = message_service.get_messages_for_contact(contact_id)[-5:]
    
    from api_integrations import get_emails_for_contact
    recent_emails = get_emails_for_contact(contact.email)

    return render_template(
        'contact_detail.html', 
        contact=contact,
        recent_messages=recent_messages,
        recent_emails=recent_emails
    )

@contact_bp.route('/<int:contact_id>/conversation', methods=['GET', 'POST'])
def conversation(contact_id):
    # --- THIS IS THE FIX ---
    # Instantiate the services inside this function
    contact_service = ContactService()
    message_service = MessageService()
    # --- END FIX ---
    
    contact = contact_service.get_contact_by_id(contact_id)
    
    if request.method == 'POST':
        message_body = request.form.get('body')
        from_number_id = current_app.config.get('OPENPHONE_PHONE_NUMBER_ID')
        if message_body and from_number_id:
            message_service.send_and_save_message(contact, message_body, from_number_id)
        return redirect(url_for('contact.conversation', contact_id=contact.id))

    messages = message_service.get_messages_for_contact(contact_id)
    return render_template('conversation_view.html', contact=contact, messages=messages)

@contact_bp.route('/add', methods=['GET', 'POST'])
def add_contact():
    contact_service = ContactService()
    if request.method == 'POST':
        contact_service.add_contact(
            first_name=request.form['first_name'],
            last_name=request.form['last_name'],
            email=request.form['email'],
            phone=request.form['phone']
        )
        return redirect(url_for('contact.list_all'))
    return render_template('add_edit_contact_form.html')

@contact_bp.route('/<int:contact_id>/edit', methods=['GET', 'POST'])
def edit_contact(contact_id):
    contact_service = ContactService()
    contact = contact_service.get_contact_by_id(contact_id)
    if request.method == 'POST':
        contact_service.update_contact(
            contact,
            first_name=request.form['first_name'],
            last_name=request.form['last_name'],
            email=request.form['email'],
            phone=request.form['phone']
        )
        return redirect(url_for('contact.contact_detail', contact_id=contact.id))
    return render_template('add_edit_contact_form.html', contact=contact)

@contact_bp.route('/<int:contact_id>/delete', methods=['POST'])
def delete_contact(contact_id):
    contact_service = ContactService()
    contact = contact_service.get_contact_by_id(contact_id)
    contact_service.delete_contact(contact)
    return redirect(url_for('contact.list_all'))
