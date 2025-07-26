from extensions import db
from crm_database import Activity, Contact, Property, Conversation # Updated imports
from services.contact_service import ContactService
from services.property_service import PropertyService
from services.openphone_service import OpenPhoneService
from services.ai_service import AIService
from datetime import datetime
import re

class MessageService:
    def __init__(self):
        self.session = db.session
        self.contact_service = ContactService()
        self.property_service = PropertyService()
        self.openphone_service = OpenPhoneService()
        self.ai_service = AIService()

    def get_or_create_conversation(self, contact_id, openphone_convo_id=None, participants=None):
        """Finds an existing conversation or creates a new one."""
        # Try to find a conversation with the OpenPhone ID first for accuracy
        if openphone_convo_id:
            conversation = self.session.query(Conversation).filter_by(openphone_id=openphone_convo_id).first()
            if conversation:
                return conversation

        # If not found, look for any existing conversation with this contact
        conversation = self.session.query(Conversation).filter_by(contact_id=contact_id).first()
        if conversation:
            # If we now have an openphone_id, we should add it
            if openphone_convo_id and not conversation.openphone_id:
                conversation.openphone_id = openphone_convo_id
                self.session.commit()
            return conversation

        # If still no conversation, create a new one
        new_conversation = Conversation(
            contact_id=contact_id,
            openphone_id=openphone_convo_id,
            participants=','.join(participants) if participants else ''
        )
        self.session.add(new_conversation)
        self.session.commit()
        return new_conversation

    def get_activities_for_contact(self, contact_id):
        """Gets all activities for a contact, sorted chronologically."""
        return self.session.query(Activity).join(Conversation).filter(Conversation.contact_id == contact_id).order_by(Activity.created_at.asc()).all()

    def get_latest_conversations_from_db(self, limit=10):
        """Gets the most recent conversations from the local database."""
        return self.session.query(Conversation).order_by(Conversation.last_activity_at.desc()).limit(limit).all()

    def process_incoming_webhook(self, webhook_data):
        """
        Processes incoming activities (messages, calls) from webhooks,
        creating contacts and conversations as needed.
        """
        activity_type = webhook_data.get('type')
        if not activity_type:
            return None

        # This will need to be expanded to handle different webhook event types
        # For now, we focus on the 'message.new' or 'message.received' type
        if activity_type in ['message.new', 'message.received']:
            message_payload = webhook_data.get('data', {}).get('object', {})
            if not message_payload or message_payload.get('direction') != 'incoming':
                return None

            from_number = message_payload.get('from')
            openphone_id = message_payload.get('id')
            conversation_id_op = message_payload.get('conversationId')
            
            # Find or create the contact
            contact = self.contact_service.get_contact_by_phone(from_number)
            if not contact:
                contact = self.contact_service.add_contact(
                    first_name=from_number,
                    last_name="(New SMS Contact)",
                    phone=from_number
                )
            
            # Find or create the conversation
            conversation = self.get_or_create_conversation(contact.id, conversation_id_op)
            
            # Check if this activity already exists
            existing_activity = self.session.query(Activity).filter_by(openphone_id=openphone_id).first()
            if not existing_activity:
                new_activity = Activity(
                    conversation_id=conversation.id,
                    openphone_id=openphone_id,
                    type='message',
                    body=message_payload.get('body'),
                    direction='inbound',
                    status='delivered',
                    created_at=datetime.utcnow()
                )
                self.session.add(new_activity)
                conversation.last_activity_at = datetime.utcnow()
                self.session.commit()
                # AI enrichment logic would be called here
            return new_activity
        return None