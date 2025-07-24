from flask import Blueprint, jsonify, request
from services.contact_service import ContactService
from services.message_service import MessageService

api_bp = Blueprint('api', __name__)
# We can now safely instantiate the services at the module level.
# The internal components (like the AI model) will initialize themselves
# when they are first used within a request.
contact_service = ContactService()
message_service = MessageService()

@api_bp.route('/contacts')
def get_contacts():
    contacts = contact_service.get_all_contacts()
    contact_list = [{'id': c.id, 'first_name': c.first_name, 'last_name': c.last_name, 'email': c.email, 'phone': c.phone} for c in contacts]
    return jsonify(contact_list)

@api_bp.route('/messages/latest_conversations')
def get_latest_conversations():
    latest_messages = message_service.get_latest_conversations(limit=5)
    conversations_json = [
        {
            'contact_id': msg.contact.id,
            'contact_name': msg.contact.first_name,
            'contact_number': msg.contact.phone,
            'latest_message_body': msg.body
        }
        for msg in latest_messages
    ]
    return jsonify(conversations_json)

@api_bp.route('/webhooks/openphone', methods=['POST'])
def openphone_webhook():
    """
    Receives incoming event notifications from OpenPhone.
    """
    data = request.json
    print(f"Received webhook: {data}")
    
    if data.get('type') == 'token.validated':
        return jsonify(success=True)

    message_service.process_incoming_webhook(data)
    
    return jsonify(success=True)
