from extensions import db
from crm_database import Message, Contact
from services.contact_service import ContactService
from services.openphone_service import OpenPhoneService
from datetime import datetime

class MessageService:
    def __init__(self):
        self.session = db.session
        self.contact_service = ContactService()
        self.openphone_service = OpenPhoneService()

    def get_messages_for_contact(self, contact_id):
        """
        Fetches all messages for a given contact, ordered by timestamp.
        """
        return self.session.query(Message).filter_by(contact_id=contact_id).order_by(Message.timestamp.asc()).all()

    def get_latest_conversations(self, limit=5):
        """
        Gets the most recent message for the N most recent conversations.
        """
        latest_message_subquery = self.session.query(
            db.func.max(Message.id)
        ).group_by(Message.contact_id).subquery()

        latest_messages = self.session.query(Message).filter(
            Message.id.in_(latest_message_subquery.select())
        ).order_by(Message.timestamp.desc()).limit(limit).all()
        
        return latest_messages

    def process_incoming_webhook(self, webhook_data):
        """
        Processes the incoming message data from an OpenPhone webhook.
        """
        message_type = webhook_data.get('type')
        if message_type not in ['message.new', 'message.received']:
            return None

        message_payload = webhook_data.get('data', {}).get('object', {})
        if not message_payload or message_payload.get('direction') != 'incoming':
            return None

        from_number = message_payload.get('from')
        message_body = message_payload.get('body')
        openphone_id = message_payload.get('id')

        contact = self.session.query(Contact).filter_by(phone=from_number).first()
        if not contact:
            first_name = from_number
            last_name = "(New SMS Contact)"
            if message_body and " " in message_body and len(message_body.split()) > 1:
                parts = message_body.split()
                if parts[0].lower() in ['hi', 'hello', 'hey']:
                    first_name = parts[1]
                    if len(parts) > 2:
                        last_name = parts[2]

            contact = self.contact_service.add_contact(
                first_name=first_name,
                last_name=last_name,
                phone=from_number
            )
        
        existing_message = self.session.query(Message).filter_by(openphone_id=openphone_id).first()
        if existing_message:
            return contact

        new_message = Message(
            openphone_id=openphone_id,
            contact_id=contact.id,
            body=message_body,
            direction='incoming',
            timestamp=datetime.utcnow()
        )
        self.session.add(new_message)
        self.session.commit()
        return contact

    def send_and_save_message(self, contact, message_body, from_number_id):
        """
        Sends an SMS via the API and saves the outgoing message to our database.
        """
        response_data, error = self.openphone_service.send_sms(
            to_number=contact.phone,
            from_number_id=from_number_id,
            body=message_body
        )

        if error:
            return None, error

        # --- THIS IS THE FIX ---
        # The message ID is nested inside the 'data' object in the API response.
        message_id_from_api = response_data.get('data', {}).get('id')
        # -------------------------

        new_message = Message(
            openphone_id=message_id_from_api,
            contact_id=contact.id,
            body=message_body,
            direction='outgoing',
            timestamp=datetime.utcnow()
        )
        self.session.add(new_message)
        self.session.commit()
        return new_message, None
