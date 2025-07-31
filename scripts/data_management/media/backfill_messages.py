
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
from scripts.script_logger import get_logger

logger = get_logger(__name__)

import os
from datetime import datetime
import requests
from urllib3.exceptions import InsecureRequestWarning

# Suppress the InsecureRequestWarning from urllib3
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

# Import what we need from the main application
from app import create_app
from extensions import db
from crm_database import Contact, Message
from services.contact_service import ContactService

def run_backfill():
    """
    Connects to the OpenPhone API, fetches the last message from recent conversations,
    and saves any missing messages to the local database.
    """
    logger.info("--- Starting OpenPhone Message Backfill ---")
    
    app = create_app()
    
    with app.app_context():
        api_key = app.config.get('OPENPHONE_API_KEY')
        phone_number_id = app.config.get('OPENPHONE_PHONE_NUMBER_ID')

        if not all([api_key, phone_number_id]):
            logger.info("ERROR: Missing OpenPhone configuration in .env file. Aborting.")
            return

        headers = {"Authorization": api_key}
        contact_service = ContactService()

        # 1. Get recent conversations
        logger.info("Fetching recent conversations from OpenPhone...")
        conversations_url = f"https://api.openphone.com/v1/conversations?phoneNumberId={phone_number_id}&limit=50"
        try:
            convo_response = requests.get(conversations_url, headers=headers, verify=True)
            convo_response.raise_for_status()
            conversations = convo_response.json().get('data', [])
            logger.info(f"Found {len(conversations)} conversations to check.")
        except Exception as e:
            logger.info(f"ERROR: Could not fetch conversations: {e}")
            return

        # 2. For each conversation, get the LAST message and save it
        total_messages_added = 0
        for convo in conversations:
            last_activity_id = convo.get('lastActivityId')
            other_participant_number = convo.get('participants', [None])[0]
            
            if not last_activity_id or not other_participant_number:
                continue

            logger.info(f"\nProcessing conversation with {other_participant_number}...")
            
            # Find or create the contact
            contact = db.session.query(Contact).filter_by(phone=other_participant_number).first()
            if not contact:
                logger.info(f"  -> New contact found. Creating entry for {other_participant_number}.")
                contact = contact_service.add_contact(
                    first_name=other_participant_number,
                    last_name="(from backfill)",
                    phone=other_participant_number
                )

            # Check if we already have this specific message
            exists = db.session.query(Message).filter_by(openphone_id=last_activity_id).first()
            if exists:
                logger.info("  -> Latest message already exists in DB. Skipping.")
                continue

            # Fetch the single last message using the endpoint we know works
            message_url = f"https://api.openphone.com/v1/messages/{last_activity_id}"
            try:
                message_response = requests.get(message_url, headers=headers, verify=True)
                if message_response.status_code == 404:
                    logger.info("  -> Last activity was not a message (e.g., a call). Skipping.")
                    continue
                message_response.raise_for_status()
                msg_data = message_response.json().get('data', {})

                # Save the new message to our database
                new_message = Message(
                    openphone_id=msg_data.get('id'),
                    contact_id=contact.id,
                    body=msg_data.get('text'), # The key is 'text' in the message object
                    direction=msg_data.get('direction'),
                    timestamp=datetime.fromisoformat(msg_data.get('createdAt').replace('Z', '+00:00'))
                )
                db.session.add(new_message)
                total_messages_added += 1
                logger.info(f"  -> Added latest message to the database.")

            except Exception as e:
                logger.info(f"  -> ERROR: Could not fetch message {last_activity_id}: {e}")
                continue

        # Commit all the new messages at the end
        db.session.commit()
        logger.info("\n--- Backfill Complete ---")
        logger.info(f"Total new messages added: {total_messages_added}")

if __name__ == '__main__':
    run_backfill()
