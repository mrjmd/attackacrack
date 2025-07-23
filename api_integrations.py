# ===================================================================
print("--- LOADING LATEST api_integrations.py (Final Fix) ---")
# ===================================================================

import os
import pickle
from datetime import datetime, timedelta
import json

from flask import current_app
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import requests
# Suppress the InsecureRequestWarning from urllib3
from urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)


# Define the scopes for all Google services we'll use
SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/calendar.readonly'
]
TOKEN_FILE = 'token.pickle'

def get_google_creds():
    """
    Gets valid Google API credentials. Handles token refresh and new user login.
    """
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
        now = datetime.utcnow().isoformat() + 'Z'
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

def get_recent_openphone_texts(count=5):
    """
    Fetches and processes recent conversations from OpenPhone, including the latest message body.
    Returns a tuple: (processed_data, error_message)
    """
    try:
        api_key = current_app.config.get('OPENPHONE_API_KEY')
        phone_number_id = current_app.config.get('OPENPHONE_PHONE_NUMBER_ID')

        if not api_key:
            return ([], "OpenPhone API Key is not configured in config.py.")
        if not phone_number_id:
            return ([], "OPENPHONE_PHONE_NUMBER_ID is not configured in config.py.")

        headers = {"Authorization": api_key}

        # Step 1: Get the list of recent conversations
        conversations_url = f"https://api.openphone.com/v1/conversations?phoneNumberId={phone_number_id}&limit={count}"
        conversation_response = requests.get(conversations_url, headers=headers, verify=False)
        conversation_response.raise_for_status()
        conversations = conversation_response.json().get('data', [])

        processed_conversations = []
        for convo in conversations:
            last_activity_id = convo.get('lastActivityId')
            if not last_activity_id:
                continue

            message_url = f"https://api.openphone.com/v1/messages/{last_activity_id}"
            message_response = requests.get(message_url, headers=headers, verify=False)
            
            latest_message_body = ""
            if message_response.status_code == 404:
                latest_message_body = "[Last activity was not a text message]"
            else:
                message_response.raise_for_status()
                message_data = message_response.json()
                
                # --- THIS IS THE FIX ---
                # The message body is inside the 'data' object, under the key 'text'.
                latest_message_body = message_data.get('data', {}).get('text', "[Message with no body]")
                # ------------------------

            other_participant_number = convo.get('participants', [None])[0]

            processed_conversations.append({
                'contact_name': convo.get('name'),
                'contact_number': other_participant_number,
                'latest_message_body': latest_message_body
            })
        
        return (processed_conversations, None)

    except requests.exceptions.HTTPError as http_err:
        error_msg = f"HTTP Error: {http_err}"
        print(error_msg)
        return ([], error_msg)
    except Exception as e:
        error_msg = f"An unexpected error occurred: {e}"
        print(error_msg)
        return ([], error_msg)
