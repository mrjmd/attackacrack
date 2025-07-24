from extensions import db
from crm_database import Message, Contact, Property
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

    def _parse_email_from_text(self, text):
        if not text:
            return None
        email_regex = r'[\w\.-]+@[\w\.-]+\.\w+'
        match = re.search(email_regex, text)
        return match.group(0) if match else None

    def get_messages_for_contact(self, contact_id):
        return self.session.query(Message).filter_by(contact_id=contact_id).order_by(Message.timestamp.asc()).all()

    def get_latest_conversations(self, limit=5):
        latest_message_subquery = self.session.query(
            db.func.max(Message.id)
        ).group_by(Message.contact_id).subquery()
        return self.session.query(Message).filter(
            Message.id.in_(latest_message_subquery.select())
        ).order_by(Message.timestamp.desc()).limit(limit).all()

    def process_incoming_webhook(self, webhook_data):
        """
        Processes incoming messages. Now saves the message first for resilience.
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

        # Step 1: Find or create the contact.
        contact = self.session.query(Contact).filter_by(phone=from_number).first()
        if not contact:
            contact = self.contact_service.add_contact(
                first_name=from_number,
                last_name="(New SMS Contact)",
                phone=from_number
            )
        
        # Step 2: Save the message immediately. This is the most critical step.
        existing_message = self.session.query(Message).filter_by(openphone_id=openphone_id).first()
        if not existing_message:
            new_message = Message(
                openphone_id=openphone_id,
                contact_id=contact.id,
                body=message_body,
                direction='incoming',
                timestamp=datetime.utcnow()
            )
            self.session.add(new_message)
            self.session.commit()
            print(f"Successfully saved new message {openphone_id} to database.")
        
        # Step 3: Now that the message is safe, attempt the "enhancements" (AI, etc.).
        email = self._parse_email_from_text(message_body)

        # --- ADDED DEBUGGING ---
        print("--- Attempting to extract address with AI... ---")
        address = self.ai_service.extract_address_from_text(message_body)
        print(f"--- AI extraction result: {address} ---")
        # --- END DEBUGGING ---

        # Update contact with email if found
        if email and not contact.email:
            print(f"Updating contact email for {from_number} to {email}")
            self.contact_service.update_contact(contact, email=email)
        
        # Create property if an address is found
        if address:
            existing_property = self.session.query(Property).filter_by(
                contact_id=contact.id, 
                address=address
            ).first()
            if not existing_property:
                print(f"Found new address via AI: {address}. Creating property for contact {contact.id}")
                self.property_service.add_property(address=address, contact_id=contact.id)
        
        return contact

    def send_and_save_message(self, contact, message_body, from_number_id):
        response_data, error = self.openphone_service.send_sms(
            to_number=contact.phone,
            from_number_id=from_number_id,
            body=message_body
        )

        if error:
            return None, error

        message_id_from_api = response_data.get('data', {}).get('id')
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
