# api_integrations.py

import os
import pickle
from datetime import datetime, timedelta, UTC
import json

from flask import current_app
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import requests
from services.contact_service import ContactService
from urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)


SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/calendar'
]
TOKEN_FILE = 'token.pickle'

def get_google_creds():
    creds = None
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, 'rb') as token:
            creds = pickle.load(token)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                print(f"Error refreshing Google token: {e}")
                print("Please delete token.pickle and re-run the application.")
                return None
        else:
            try:
                client_id = current_app.config.get('GOOGLE_CLIENT_ID')
                client_secret = current_app.config.get('GOOGLE_CLIENT_SECRET')

                if not client_id or not client_secret:
                    print("="*80)
                    print("FATAL OAUTH ERROR: 'GOOGLE_CLIENT_ID' or 'GOOGLE_CLIENT_SECRET' is missing.")
                    print("ACTION: Please ensure these variables are correctly set in your .env file.")
                    print("="*80)
                    return None

                client_config = {
                    "installed": {
                        "client_id": client_id,
                        "project_id": current_app.config.get('GOOGLE_PROJECT_ID'),
                        "client_secret": client_secret,
                        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                        "token_uri": "https://oauth2.googleapis.com/token",
                        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                        "redirect_uris": ["http://localhost:8989/"] 
                    }
                }
                flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
                creds = flow.run_local_server(port=8989) 
            except Exception as e:
                print(f"FATAL: Could not get new Google credentials. Error: {e}")
                print("ACTION: Please verify your .env file and Google Cloud project settings.")
                return None
        
        with open(TOKEN_FILE, 'wb') as token:
            pickle.dump(creds, token)
    return creds

def get_upcoming_calendar_events(count=5):
    creds = get_google_creds()
    if not creds: return []
    try:
        service = build('calendar', 'v3', credentials=creds)
        now = datetime.now(UTC).isoformat()
        events_result = service.events().list(calendarId='primary', timeMin=now, maxResults=count, singleEvents=True, orderBy='startTime').execute()
        return events_result.get('items', [])
    except Exception as e:
        print(f"Error fetching Google Calendar events: {e}")
        return []

def get_recent_gmail_messages(count=5):
    creds = get_google_creds()
    if not creds: return []
    try:
        service = build('gmail', 'v1', credentials=creds)
        results = service.users().messages().list(userId='me', labelIds=['INBOX', 'UNREAD'], maxResults=count).execute()
        messages_info = results.get('messages', [])
        emails = []
        for msg_info in messages_info:
            msg = service.users().messages().get(userId='me', id=msg_info['id'], format='metadata', metadataHeaders=['From', 'Subject']).execute()
            headers = msg['payload']['headers']
            subject = next((h['value'] for h in headers if h['name'] == 'Subject'), 'No Subject')
            sender = next((h['value'] for h in headers if h['name'] == 'From'), 'Unknown Sender')
            emails.append({'id': msg['id'], 'threadId': msg['threadId'], 'subject': subject, 'sender': sender})
        return emails
    except Exception as e:
        print(f"Error fetching Gmail messages: {e}")
        return []

def get_emails_for_contact(email_address, count=5):
    if not email_address:
        return []
        
    creds = get_google_creds()
    if not creds: return []
    try:
        service = build('gmail', 'v1', credentials=creds)
        query = f"from:{email_address} OR to:{email_address}"
        results = service.users().messages().list(userId='me', q=query, maxResults=count).execute()
        messages_info = results.get('messages', [])
        
        emails = []
        for msg_info in messages_info:
            msg = service.users().messages().get(userId='me', id=msg_info['id'], format='metadata', metadataHeaders=['From', 'Subject', 'Date']).execute()
            headers = msg['payload']['headers']
            subject = next((h['value'] for h in headers if h['name'] == 'Subject'), 'No Subject')
            sender = next((h['value'] for h in headers if h['name'] == 'From'), 'Unknown Sender')
            date = next((h['value'] for h in headers if h['name'] == 'Date'), '')
            emails.append({'subject': subject, 'sender': sender, 'date': date})
        return emails
    except Exception as e:
        print(f"Error fetching emails for contact {email_address}: {e}")
        return []


def get_recent_openphone_texts(contact_service: ContactService, count=5):
    try:
        api_key = current_app.config.get('OPENPHONE_API_KEY')
        phone_number_id = current_app.config.get('OPENPHONE_PHONE_NUMBER_ID')

        if not api_key or not phone_number_id:
            return ([], "OpenPhone API Key or Phone Number ID is not configured.")

        # The header is now in the correct format, without "Bearer ".
        headers = {"Authorization": api_key}
        
        conversations_url = f"https://api.openphone.com/v1/conversations?phoneNumberId={phone_number_id}&limit={count}"
        
        conversation_response = requests.get(conversations_url, headers=headers, verify=False)
        conversation_response.raise_for_status()
        conversations = conversation_response.json().get('data', [])

        processed_conversations = []
        for convo in conversations:
            last_activity_type = convo.get('lastActivityType')
            latest_message_body = ""

            if last_activity_type == 'message':
                last_activity_id = convo.get('lastActivityId')
                message_url = f"https://api.openphone.com/v1/messages/{last_activity_id}"
                message_response = requests.get(message_url, headers=headers, verify=False)
                if message_response.status_code == 200:
                    message_data = message_response.json()
                    latest_message_body = message_data.get('data', {}).get('text', "[Message with no body]")
                else:
                    latest_message_body = f"[Error fetching message: {message_response.status_code}]"
            elif last_activity_type == 'call':
                latest_message_body = "[Last activity was a phone call]"
            else:
                latest_message_body = f"[Last activity: {last_activity_type or 'Unknown'}]"

            other_participant_number = next((p for p in convo.get('participants', []) if p != current_app.config.get('OPENPHONE_PHONE_NUMBER')), None)
            contact = contact_service.get_contact_by_phone(other_participant_number) if other_participant_number else None

            processed_conversations.append({
                'contact_id': contact.id if contact else None,
                'contact_name': convo.get('name') or (contact.first_name if contact else None),
                'contact_number': other_participant_number,
                'latest_message_body': latest_message_body
            })
        
        return (processed_conversations, None)

    except Exception as e:
        # We can leave the detailed exception logging for now, it's useful.
        print(f"\n--- [DEBUG] An exception occurred in get_recent_openphone_texts ---")
        print(f"--- [DEBUG] Exception Type: {type(e).__name__}")
        print(f"--- [DEBUG] Exception Details: {e}")
        return ([], str(e))

def create_google_calendar_event(title, description, start_time, end_time, attendees: list, location: str = None):
    creds = get_google_creds()
    if not creds:
        print("Could not create Google Calendar event: invalid credentials.")
        return None
    try:
        service = build('calendar', 'v3', credentials=creds)
        event = {
            'summary': title,
            'description': description,
            'start': {'dateTime': start_time.isoformat(), 'timeZone': 'America/New_York'},
            'end': {'dateTime': end_time.isoformat(), 'timeZone': 'America/New_York'},
            'attendees': [{'email': email} for email in attendees],
        }
        if location:
            event['location'] = location
        created_event = service.events().insert(calendarId='primary', body=event).execute()
        print(f"Event created: {created_event.get('htmlLink')}")
        return created_event
    except Exception as e:
        print(f"Error creating Google Calendar event: {e}")
        return None

def delete_google_calendar_event(event_id: str):
    creds = get_google_creds()
    if not creds:
        print("Could not delete Google Calendar event: invalid credentials.")
        return False
    try:
        service = build('calendar', 'v3', credentials=creds)
        service.events().delete(calendarId='primary', eventId=event_id).execute()
        print(f"Successfully deleted Google Calendar event: {event_id}")
        return True
    except Exception as e:
        print(f"Error deleting Google Calendar event {event_id}: {e}")
        return False
