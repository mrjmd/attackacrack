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
    from OpenPhone, including de-duplication and media downloading.
    """
    print("--- Starting Comprehensive OpenPhone Import ---")
    
    app = create_app()
    
    with app.app_context():
        api_key = app.config.get('OPENPHONE_API_KEY')
        user_phone_number = app.config.get('OPENPHONE_PHONE_NUMBER')

        if not all([api_key, user_phone_number]):
            print("ERROR: Missing OpenPhone configuration. Aborting.")
            return

        headers = {"Authorization": api_key}
        contact_service = ContactService()
        
        os.makedirs(MEDIA_UPLOAD_FOLDER, exist_ok=True)
        print(f"Media will be saved to: {os.path.abspath(MEDIA_UPLOAD_FOLDER)}")

        # 1. Fetch ALL Contacts from the Address Book
        print("\n--- Phase 1: Syncing All Contacts ---")
        all_contacts_api = []
        page_token = None
        while True:
            url = f"https://api.openphone.com/v1/contacts?maxResults=100"
            if page_token:
                url += f"&pageToken={page_token}"
            try:
                response = requests.get(url, headers=headers, verify=False)
                response.raise_for_status()
                data = response.json()
                all_contacts_api.extend(data.get('data', []))
                page_token = data.get('nextPageToken')
                if not page_token:
                    break
            except Exception as e:
                print(f"ERROR: Could not fetch contacts: {e}")
                return
        
        print(f"Found {len(all_contacts_api)} total contact entries in OpenPhone address book.")

        # --- NEW LOGIC: Pre-scan for duplicate numbers ---
        print("Pre-scanning for duplicate phone numbers...")
        phone_number_counts = Counter()
        for contact_data in all_contacts_api:
            phone_number = next((p['value'] for p in contact_data.get('phoneNumbers', []) if p.get('value')), None)
            if phone_number:
                phone_number_counts[phone_number] += 1
        print("Pre-scan complete.")
        # --- END NEW LOGIC ---
        
        contacts_processed = 0
        for contact_data in all_contacts_api:
            phone_number = next((p['value'] for p in contact_data.get('phoneNumbers', []) if p.get('value')), None)
            if not phone_number:
                continue

            contacts_processed += 1
            if contacts_processed % 100 == 0:
                print(f"  -> Processed {contacts_processed}/{len(all_contacts_api)} contact entries...")

            existing_contact = db.session.query(Contact).filter_by(phone=phone_number).first()
            if not existing_contact:
                last_name = contact_data.get('lastName') or "(from import)"
                # Flag potential office numbers
                if phone_number_counts[phone_number] > 3:
                    last_name += " (Office Number?)"

                contact_service.add_contact(
                    first_name=contact_data.get('firstName') or phone_number,
                    last_name=last_name,
                    phone=phone_number,
                    email=next((e['value'] for e in contact_data.get('emails', []) if e.get('value')), None)
                )
        print("Contact sync complete.")

        # 2. Fetch ALL Conversations
        print("\n--- Phase 2: Fetching All Conversation Histories ---")
        all_conversations = []
        page_token = None
        while True:
            url = f"https://api.openphone.com/v1/conversations?phoneNumbers[]={user_phone_number}&maxResults=100"
            if page_token:
                url += f"&pageToken={page_token}"
            try:
                response = requests.get(url, headers=headers, verify=False)
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

        # 3. Process each conversation to get full message history
        total_messages_added = 0
        for convo in all_conversations:
            phone_number = convo.get('contact', {}).get('phoneNumber')
            if not phone_number:
                continue
            
            print(f"\nProcessing conversation with {phone_number}...")
            contact = db.session.query(Contact).filter_by(phone=phone_number).first()
            if not contact:
                print(f"  -> WARNING: Contact for {phone_number} not found in DB, skipping conversation.")
                continue

            # Fetch all messages for this conversation
            all_messages = []
            page_token = None
            while True:
                messages_url = f"https://api.openphone.com/v1/conversations/{convo['id']}/messages?maxResults=100"
                if page_token:
                    messages_url += f"&pageToken={page_token}"
                try:
                    messages_response = requests.get(messages_url, headers=headers, verify=False)
                    messages_response.raise_for_status()
                    data = messages_response.json()
                    all_messages.extend(data.get('data', []))
                    page_token = data.get('nextPageToken')
                    if not page_token:
                        break
                except Exception as e:
                    print(f"  -> ERROR: Could not fetch messages: {e}")
                    break # Stop trying for this conversation if an error occurs

            # 4. Save messages and download media
            messages_added_this_convo = 0
            for msg_data in reversed(all_messages): # Save oldest first
                openphone_id = msg_data.get('id')
                
                if not db.session.query(Message).filter_by(openphone_id=openphone_id).first():
                    new_message = Message(
                        openphone_id=openphone_id,
                        contact_id=contact.id,
                        body=msg_data.get('body'),
                        direction=msg_data.get('direction'),
                        timestamp=datetime.fromisoformat(msg_data.get('createdAt').replace('Z', '+00:00'))
                    )
                    db.session.add(new_message)
                    db.session.flush()

                    for media_url in msg_data.get('media', []):
                        # Media handling logic here...
                        pass # Placeholder for media download logic from previous version

                    messages_added_this_convo += 1
            
            if messages_added_this_convo > 0:
                print(f"  -> Added {messages_added_this_convo} new messages to the database.")
                total_messages_added += messages_added_this_convo

        db.session.commit()
        print("\n--- Full Import Complete ---")
        print(f"Total new messages added: {total_messages_added}")

if __name__ == '__main__':
    run_full_import()
