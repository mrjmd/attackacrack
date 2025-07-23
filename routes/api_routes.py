from flask import Blueprint, jsonify
from services.contact_service import ContactService

api_bp = Blueprint('api', __name__)
contact_service = ContactService()

@api_bp.route('/contacts')
def get_contacts():
    """
    Provides a JSON list of all contacts.
    """
    contacts = contact_service.get_all_contacts()
    # Convert the contact objects to a JSON-serializable list of dictionaries
    contact_list = [
        {
            'id': c.id, 
            'first_name': c.first_name,
            'last_name': c.last_name,
            'email': c.email,
            'phone': c.phone
        } 
        for c in contacts
    ]
    return jsonify(contact_list)

# You can add more API endpoints here as needed, for example:
@api_bp.route('/contacts/<int:contact_id>')
def get_contact(contact_id):
    """
    Provides JSON data for a single contact.
    """
    contact = contact_service.get_contact_by_id(contact_id)
    if contact:
        return jsonify({
            'id': contact.id, 
            'first_name': contact.first_name,
            'last_name': contact.last_name,
            'email': contact.email,
            'phone': contact.phone
        })
    return jsonify({'error': 'Contact not found'}), 404
