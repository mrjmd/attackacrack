import os
import requests
import json
from datetime import datetime
from urllib3.exceptions import InsecureRequestWarning
from collections import Counter

# Suppress the InsecureRequestWarning from urllib3
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

# Import what we need from the main application
from app import create_app
from extensions import db
from crm_database import Contact, Message, MediaAttachment
from services.contact_service import ContactService

# --- CONFIGURATION ---
MEDIA_UPLOAD_FOLDER = 'uploads/media'

def run_full_import():
    """
    Performs a comprehensive import of all contacts and full conversation histories
    from OpenPhone, using the correct /v1/messages endpoint.
    """
    print("--- Starting Comprehensive OpenPhone Import ---")
    
    app = create_app()
    
    with app.app_context():
        api_key = app.config.get('OPENPHONE_API_KEY')
        user_phone_number = app.config.get('OPENPHONE_PHONE_NUMBER')
        phone_number_id = app.config.get('OPENPHONE_PHONE_NUMBER_ID')

        if not all([api_key, user_phone_number, phone_number_id]):
            print("ERROR: Missing OpenPhone configuration. Aborting.")
            return

        headers = {"Authorization": api_key}
        contact_service = ContactService()
        
        os.makedirs(MEDIA_UPLOAD_FOLDER, exist_ok=True)
        print(f"Media will be saved to: {os.path.abspath(MEDIA_UPLOAD_FOLDER)}")

        # 1. Fetch ALL Conversations
        print("\n--- Fetching All Conversations ---")
        all_conversations = []
        page_token = None
        while True:
            url = "https://api.openphone.com/v1/conversations"
            params = {
                'phoneNumbers[]': user_phone_number,
                'maxResults': 100
            }
            if page_token:
                params['pageToken'] = page_token
            
            try:
                response = requests.get(url, headers=headers, params=params, verify=False)
                response.raise_for_status()
                data = response.json()
                all_conversations.extend(data.get('data', []))
                page_token = data.get('nextPageToken')
                if not page_token:
                    break
            except Exception as e:
                print(f"ERROR: Could not fetch conversations: {e}")
                return
        
        print(f"Found {len(all_conversations)} conversations to process.")

        # Pre-scan for duplicate numbers
        phone_number_counts = Counter()
        for convo in all_conversations:
            other_participants = [p for p in convo.get('participants', []) if p != user_phone_number]
            if other_participants:
                phone_number_counts[other_participants[0]] += 1

        # 2. Process each conversation
        total_messages_added = 0
        for i, convo in enumerate(all_conversations):
            # --- THIS IS THE FIX for Group Chats ---
            # Filter out our own number to find the other participant(s)
            other_participants = [p for p in convo.get('participants', []) if p != user_phone_number]
            if not other_participants:
                continue # Skip conversations with no other participants
            
            # For now, we'll treat the first other participant as the primary contact for this conversation
            other_participant_phone = other_participants[0]
            # --- END FIX ---
            
            contact_id_from_convo = convo.get('contact', {}).get('id')

            if (i + 1) % 50 == 0:
                print(f"  -> Processing conversation {i+1}/{len(all_conversations)} with {other_participant_phone}...")

            contact = db.session.query(Contact).filter_by(phone=other_participant_phone).first()
            if not contact:
                # ... (Contact creation logic is unchanged)
                first_name = convo.get('name') or other_participant_phone
                last_name = "(from import)"
                email = None
                if contact_id_from_convo:
                    try:
                        contact_url = f"https://api.openphone.com/v1/contacts/{contact_id_from_convo}"
                        contact_response = requests.get(contact_url, headers=headers, verify=False)
                        if contact_response.status_code == 200:
                            full_contact_data = contact_response.json().get('data', {})
                            first_name = full_contact_data.get('firstName') or first_name
                            last_name = full_contact_data.get('lastName') or last_name
                            email = next((e['value'] for e in full_contact_data.get('emails', []) if e.get('isPrimary')), None)
                    except Exception as e:
                        print(f"  -> WARN: Could not enrich contact {contact_id_from_convo}: {e}")
                if phone_number_counts[other_participant_phone] > 3:
                    last_name += " (Office Number?)"
                contact = contact_service.add_contact(first_name=first_name, last_name=last_name, phone=other_participant_phone, email=email)

            # Fetch all messages for this conversation using the correct /v1/messages endpoint
            all_messages = []
            page_token = None
            while True:
                url = "https://api.openphone.com/v1/messages"
                params = {
                    'phoneNumberId': phone_number_id,
                    'participants[]': other_participant_phone,
                    'maxResults': 100
                }
                if page_token:
                    params['pageToken'] = page_token
                try:
                    messages_response = requests.get(url, headers=headers, params=params, verify=False)
                    messages_response.raise_for_status()
                    data = messages_response.json()
                    all_messages.extend(data.get('data', []))
                    page_token = data.get('nextPageToken')
                    if not page_token:
                        break
                except Exception as e:
                    print(f"  -> ERROR: Could not fetch messages for conversation with {other_participant_phone}: {e}")
                    break

            # Save messages and download media
            messages_added_this_convo = 0
            for msg_data in reversed(all_messages): # Save oldest first
                openphone_id = msg_data.get('id')
                
                if not db.session.query(Message).filter_by(openphone_id=openphone_id).first():
                    new_message = Message(
                        openphone_id=openphone_id,
                        contact_id=contact.id,
                        body=msg_data.get('body') or msg_data.get('text'),
                        direction=msg_data.get('direction'),
                        timestamp=datetime.fromisoformat(msg_data.get('createdAt').replace('Z', '+00:00'))
                    )
                    db.session.add(new_message)
                    db.session.flush()

                    for media_url in msg_data.get('media', []):
                        # Media handling logic can be added here
                        pass 

                    messages_added_this_convo += 1
            
            if messages_added_this_convo > 0:
                total_messages_added += messages_added_this_convo

        db.session.commit()
        print("\n--- Full Import Complete ---")
        print(f"Total new messages added: {total_messages_added}")

if __name__ == '__main__':
    run_full_import()
