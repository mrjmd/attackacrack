from flask import Blueprint, jsonify, request
from services.contact_service import ContactService
from services.message_service import MessageService

api_bp = Blueprint('api', __name__)

@api_bp.route('/contacts')
def get_contacts():
    contact_service = ContactService()
    contacts = contact_service.get_all_contacts()
    contact_list = [{'id': c.id, 'first_name': c.first_name, 'last_name': c.last_name, 'email': c.email, 'phone': c.phone} for c in contacts]
    return jsonify(contact_list)

@api_bp.route('/messages/latest_conversations')
def get_latest_conversations():
    message_service = MessageService()
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

# --- NEW ENDPOINT FOR CONVERSATION POLLING ---
@api_bp.route('/contacts/<int:contact_id>/messages')
def get_contact_messages(contact_id):
    """
    Provides a JSON list of all messages for a specific contact.
    """
    message_service = MessageService()
    messages = message_service.get_messages_for_contact(contact_id)
    messages_json = [
        {
            'body': msg.body,
            'direction': msg.direction,
            'timestamp': msg.timestamp.strftime('%b %d, %I:%M %p')
        }
        for msg in messages
    ]
    return jsonify(messages_json)
# --- END NEW ENDPOINT ---

@api_bp.route('/webhooks/openphone', methods=['POST'])
def openphone_webhook():
    message_service = MessageService()
    data = request.json
    print(f"Received webhook: {data}")
    
    if data.get('type') == 'token.validated':
        return jsonify(success=True)

    message_service.process_incoming_webhook(data)
    
    return jsonify(success=True)
