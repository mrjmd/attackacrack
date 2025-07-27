from flask import Blueprint, render_template, request, redirect, url_for, current_app
from services.contact_service import ContactService
from services.message_service import MessageService 
from extensions import db
from crm_database import Activity, Conversation

contact_bp = Blueprint('contact', __name__)

@contact_bp.route('/')
def list_all():
    contact_service = ContactService()
    all_contacts = contact_service.get_all_contacts()
    return render_template('contact_list.html', contacts=all_contacts)

@contact_bp.route('/conversations')
def conversation_list():
    message_service = MessageService()
    latest_conversations = message_service.get_latest_conversations_from_db()
    return render_template('conversation_list.html', conversations=latest_conversations)

@contact_bp.route('/<int:contact_id>')
def contact_detail(contact_id):
    contact_service = ContactService()
    message_service = MessageService()
    contact = contact_service.get_contact_by_id(contact_id)
    
    activities = message_service.get_activities_for_contact(contact_id)
    
    from api_integrations import get_emails_for_contact
    recent_emails = get_emails_for_contact(contact.email)

    return render_template(
        'contact_detail.html', 
        contact=contact,
        activities=activities,
        recent_emails=recent_emails
    )

@contact_bp.route('/<int:contact_id>/conversation')
def conversation(contact_id):
    contact_service = ContactService()
    message_service = MessageService()
    contact = contact_service.get_contact_by_id(contact_id)
    activities = message_service.get_activities_for_contact(contact_id)
    
    return render_template('conversation_view.html', contact=contact, activities=activities)

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