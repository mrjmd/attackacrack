from flask import Blueprint, jsonify, request
from services.contact_service import ContactService
from services.message_service import MessageService
from services.ai_service import AIService

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
    # This endpoint is now database-driven
    latest_conversations = message_service.get_latest_conversations_from_db(limit=5)
    conversations_json = []
    for conv in latest_conversations:
        last_activity = conv.activities[-1] if conv.activities else None
        conversations_json.append({
            'contact_id': conv.contact.id,
            'contact_name': conv.contact.first_name,
            'contact_number': conv.contact.phone,
            'latest_message_body': last_activity.body if last_activity else "No recent activity"
        })
    return jsonify(conversations_json)

# --- THIS IS THE FIX ---
@api_bp.route('/contacts/<int:contact_id>/messages')
def get_contact_messages(contact_id):
    """
    Provides a JSON list of all activities for a specific contact.
    """
    message_service = MessageService()
    # Use the new, correct service method
    activities = message_service.get_activities_for_contact(contact_id)
    # Format the data into the JSON structure the frontend expects
    messages_json = [
        {
            'body': act.body,
            'direction': act.direction,
            'timestamp': act.created_at.strftime('%b %d, %I:%M %p')
        }
        for act in activities
    ]
    return jsonify(messages_json)
# --- END FIX ---

@api_bp.route('/appointments/generate_summary/<int:contact_id>')
def generate_appointment_summary(contact_id):
    """
    Generates an AI summary of the conversation for a given contact.
    """
    message_service = MessageService()
    ai_service = AIService()
    
    # This should now get activities to be summarized
    activities = message_service.get_activities_for_contact(contact_id)
    summary = ai_service.summarize_conversation_for_appointment(activities)
    
    return jsonify({'summary': summary})

@api_bp.route('/webhooks/openphone', methods=['POST'])
def openphone_webhook():
    message_service = MessageService()
    data = request.json
    print(f"Received webhook: {data}")
    
    if data.get('type') == 'token.validated':
        return jsonify(success=True)

    message_service.process_incoming_webhook(data)
    
    return jsonify(success=True)