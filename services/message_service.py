from extensions import db
from crm_database import Activity, Contact, Property, Conversation
from services.contact_service import ContactService
from services.property_service import PropertyService
from services.openphone_service import OpenPhoneService
from services.ai_service import AIService
from datetime import datetime
import re
# --- THIS IS A FIX: Import SQLAlchemy's relationship loading tools ---
from sqlalchemy.orm import subqueryload
# --- END FIX ---

class MessageService:
    def __init__(self):
        self.session = db.session
        self.contact_service = ContactService()
        self.property_service = PropertyService()
        self.openphone_service = OpenPhoneService()
        self.ai_service = AIService()

    def get_or_create_conversation(self, contact_id, openphone_convo_id=None, participants=None):
        if openphone_convo_id:
            conversation = self.session.query(Conversation).filter_by(openphone_id=openphone_convo_id).first()
            if conversation:
                return conversation

        conversation = self.session.query(Conversation).filter_by(contact_id=contact_id).first()
        if conversation:
            if openphone_convo_id and not conversation.openphone_id:
                conversation.openphone_id = openphone_convo_id
                self.session.commit()
            return conversation

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

    # --- THIS IS THE REWRITTEN, EFFICIENT FUNCTION ---
    def get_latest_conversations_from_db(self, limit=10):
        """
        Gets the most recent conversations from the local database, efficiently
        pre-loading the related contact and all activities to prevent N+1 queries.
        """
        return self.session.query(Conversation)\
            .options(
                subqueryload(Conversation.contact), 
                subqueryload(Conversation.activities)
            )\
            .order_by(Conversation.last_activity_at.desc())\
            .limit(limit)\
            .all()
    # --- END REWRITTEN FUNCTION ---

    def process_incoming_webhook(self, webhook_data):
        activity_type = webhook_data.get('type')
        if not activity_type:
            return None

        if activity_type in ['message.new', 'message.received']:
            message_payload = webhook_data.get('data', {}).get('object', {})
            if not message_payload or message_payload.get('direction') != 'incoming':
                return None

            from_number = message_payload.get('from')
            openphone_id = message_payload.get('id')
            conversation_id_op = message_payload.get('conversationId')
            
            contact = self.contact_service.get_contact_by_phone(from_number)
            if not contact:
                contact = self.contact_service.add_contact(
                    first_name=from_number,
                    last_name="(New SMS Contact)",
                    phone=from_number
                )
            
            conversation = self.get_or_create_conversation(contact.id, conversation_id_op)
            
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
            return new_activity
        return None