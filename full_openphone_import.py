import os
import requests
import json
from datetime import datetime, timezone
from urllib3.exceptions import InsecureRequestWarning
from collections import Counter

# Suppress the InsecureRequestWarning from urllib3
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

# Import what we need from the main application
from app import create_app
from extensions import db
from crm_database import Contact, Conversation, Activity, MediaAttachment
from services.contact_service import ContactService

# --- CONFIGURATION ---
MEDIA_UPLOAD_FOLDER = 'uploads/media'
# Set to None for the full import.
DRY_RUN_LIMIT = None 

def run_full_import():
    """
    Performs a one-time, comprehensive import of all conversations, messages,
    calls, and media from OpenPhone into the new data model.
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

        print("\n--- Step 1: Fetching Conversations ---")
        all_conversations = []
        page_token = None
        
        # --- THIS IS THE FINAL CORRECTED LOGIC ---
        if DRY_RUN_LIMIT:
            print(f"\n--- !!! INITIATING DRY RUN: FETCHING ONLY {DRY_RUN_LIMIT} conversations !!! ---")
            url = f"https://api.openphone.com/v1/conversations?phoneNumberId={phone_number_id}"
            params = {'maxResults': DRY_RUN_LIMIT}
            try:
                response = requests.get(url, headers=headers, params=params, verify=False)
                response.raise_for_status()
                all_conversations = response.json().get('data', [])
                print(f"Fetched {len(all_conversations)} conversations for dry run.")
            except Exception as e:
                print(f"ERROR: Could not fetch conversations for dry run: {e}")
                return
        else:
            print("\n--- INITIATING FULL IMPORT: Fetching all conversations in pages of 100 ---")
            while True:
                url = f"https://api.openphone.com/v1/conversations?phoneNumberId={phone_number_id}"
                params = {'maxResults': 100}
                if page_token:
                    params['pageToken'] = page_token
                try:
                    response = requests.get(url, headers=headers, params=params, verify=False)
                    response.raise_for_status()
                    data = response.json()
                    all_conversations.extend(data.get('data', []))
                    page_token = data.get('nextPageToken')
                    print(f"Fetched a page of conversations, total now: {len(all_conversations)}")
                    if not page_token:
                        break
                except Exception as e:
                    print(f"ERROR: Could not fetch conversations: {e}")
                    return
        # --- END CORRECTED LOGIC ---
        
        print(f"Found {len(all_conversations)} conversations to process.")

        for i, convo_data in enumerate(all_conversations):
            openphone_convo_id = convo_data.get('id')
            participants = convo_data.get('participants', [])
            other_participants = [p for p in participants if p != user_phone_number]
            
            if not other_participants:
                continue

            primary_participant = other_participants[0]
            print(f"\n--- Processing Conversation {i+1}/{len(all_conversations)} with {primary_participant} ---")

            contact = contact_service.get_contact_by_phone(primary_participant)
            if not contact:
                contact_name = convo_data.get('name') or primary_participant
                contact = contact_service.add_contact(first_name=contact_name, last_name="(from import)", phone=primary_participant)

            conversation = db.session.query(Conversation).filter_by(openphone_id=openphone_convo_id).first()
            if not conversation:
                conversation = Conversation(
                    openphone_id=openphone_convo_id,
                    contact_id=contact.id,
                    participants=','.join(participants)
                )
                db.session.add(conversation)
                db.session.commit()

            all_activities = []
            
            page_token = None
            while True:
                url = "https://api.openphone.com/v1/messages"
                params = {
                    'phoneNumberId': phone_number_id,
                    'participants[]': other_participants,
                    'maxResults': 100
                }
                if page_token: params['pageToken'] = page_token
                try:
                    res = requests.get(url, headers=headers, params=params, verify=False)
                    res.raise_for_status()
                    data = res.json()
                    all_activities.extend(data.get('data', []))
                    page_token = data.get('nextPageToken')
                    if not page_token: break
                except Exception as e:
                    print(f"  -> ERROR fetching messages: {e}")
                    break
            
            page_token = None
            while True:
                url = "https://api.openphone.com/v1/calls"
                params = {
                    'phoneNumberId': phone_number_id,
                    'participants[]': [primary_participant],
                    'maxResults': 100
                }
                if page_token: params['pageToken'] = page_token
                try:
                    res = requests.get(url, headers=headers, params=params, verify=False)
                    res.raise_for_status()
                    data = res.json()
                    all_activities.extend(data.get('data', []))
                    page_token = data.get('nextPageToken')
                    if not page_token: break
                except Exception as e:
                    print(f"  -> ERROR fetching calls: {e}")
                    break

            all_activities.sort(key=lambda x: x.get('createdAt'))
            print(f"  -> Found {len(all_activities)} total activities (messages and calls).")
            
            for activity_data in all_activities:
                activity_id = activity_data.get('id')
                
                if not db.session.query(Activity).filter_by(openphone_id=activity_id).first():
                    timestamp = datetime.fromisoformat(activity_data.get('createdAt').replace('Z', '')).replace(tzinfo=timezone.utc)
                    
                    new_activity = Activity(
                        conversation_id=conversation.id,
                        openphone_id=activity_id,
                        type=activity_data.get('type'),
                        direction=activity_data.get('direction'),
                        status=activity_data.get('status') or activity_data.get('callStatus'),
                        body=activity_data.get('text') or activity_data.get('body'),
                        duration=activity_data.get('duration'),
                        recording_url=activity_data.get('recordingUrl'),
                        voicemail_url=activity_data.get('voicemailUrl'),
                        created_at=timestamp
                    )
                    db.session.add(new_activity)
                    db.session.flush()

                    for media_url in activity_data.get('media', []):
                        try:
                            media_res = requests.get(media_url, verify=False)
                            if media_res.status_code == 200:
                                filename = media_url.split('/')[-1].split('?')[0]
                                local_path = os.path.join(MEDIA_UPLOAD_FOLDER, filename)
                                with open(local_path, 'wb') as f:
                                    f.write(media_res.content)
                                
                                new_media = MediaAttachment(
                                    activity_id=new_activity.id,
                                    source_url=media_url,
                                    local_path=local_path,
                                    content_type=media_res.headers.get('Content-Type')
                                )
                                db.session.add(new_media)
                        except Exception as e:
                            print(f"    -> ERROR downloading media {media_url}: {e}")
            
            if all_activities:
                last_activity_ts = datetime.fromisoformat(all_activities[-1].get('createdAt').replace('Z', '')).replace(tzinfo=timezone.utc)
                conversation.last_activity_at = last_activity_ts

        db.session.commit()
        print("\n--- Full Import Complete ---")

if __name__ == '__main__':
    run_full_import()