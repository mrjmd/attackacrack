# integrations.py

import os
import pickle
import requests
from datetime import datetime
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from email.utils import parsedate_to_datetime
from dotenv import load_dotenv

load_dotenv()

class IntegrationManager:
    def __init__(self):
        self.google_creds = None
        self.openphone_api_key = os.getenv("OPENPHONE_API_KEY")
        self.openphone_phone_number = os.getenv("OPENPHONE_PHONE_NUMBER")
        self.token_file = 'token.pickle'
        self.openphone_key_file = 'openphone.key'
        self.load_credentials()

    def load_credentials(self):
        """Load saved credentials from files."""
        if os.path.exists(self.token_file):
            with open(self.token_file, 'rb') as token:
                self.google_creds = pickle.load(token)
        if os.path.exists(self.openphone_key_file):
            with open(self.openphone_key_file, 'r') as f:
                self.openphone_api_key = f.read().strip()

    def save_google_credentials(self, creds):
        """Saves Google credentials to a file."""
        self.google_creds = creds
        with open(self.token_file, 'wb') as token:
            pickle.dump(self.google_creds, token)

    def save_openphone_key(self, api_key):
        """Saves OpenPhone API key to a file."""
        self.openphone_api_key = api_key
        with open(self.openphone_key_file, 'w') as f:
            f.write(api_key)

    def is_google_authenticated(self):
        """Check if Google credentials are valid."""
        return self.google_creds and self.google_creds.valid

    def is_openphone_configured(self):
        """Check if OpenPhone API key is set."""
        return self.openphone_api_key is not None

    def get_google_auth_flow(self):
        """Creates and returns a Google OAuth flow instance."""
        if not os.path.exists('client_secret.json'):
            raise FileNotFoundError("CRITICAL: 'client_secret.json' not found.")
        
        flow = Flow.from_client_secrets_file(
            'client_secret.json',
            scopes=[
                'https://www.googleapis.com/auth/calendar.readonly',
                'https://www.googleapis.com/auth/gmail.readonly'
            ],
            redirect_uri='https://127.0.0.1:5000/oauth2callback'
        )
        return flow

    def get_calendar_events(self):
        if not self.is_google_authenticated(): return None
        try:
            service = build('calendar', 'v3', credentials=self.google_creds)
            now = datetime.utcnow().isoformat() + 'Z'
            events_result = service.events().list(
                calendarId='primary', timeMin=now,
                maxResults=5, singleEvents=True,
                orderBy='startTime'
            ).execute()
            events = events_result.get('items', [])
            formatted_events = []
            for event in events:
                start = event['start'].get('dateTime', event['start'].get('date'))
                start_dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
                formatted_time = start_dt.strftime('%b %d, %I:%M %p')
                attendees = event.get('attendees', [])
                with_str = ', '.join([a.get('email') for a in attendees if not a.get('resource')])
                formatted_events.append({'title': event['summary'], 'time': formatted_time, 'with': with_str})
            return formatted_events
        except Exception as e:
            print(f"--- ERROR fetching calendar events: {e} ---")
            return []

    def get_recent_emails(self):
        if not self.is_google_authenticated(): return None
        try:
            service = build('gmail', 'v1', credentials=self.google_creds)
            results = service.users().messages().list(userId='me', labelIds=['INBOX'], maxResults=5).execute()
            messages = results.get('messages', [])
            formatted_emails = []
            for msg in messages:
                msg_data = service.users().messages().get(userId='me', id=msg['id']).execute()
                headers = msg_data['payload']['headers']
                subject = next((i['value'] for i in headers if i['name'] == 'Subject'), 'No Subject')
                sender = next((i['value'] for i in headers if i['name'] == 'From'), 'Unknown')
                date_str = next((i['value'] for i in headers if i['name'] == 'Date'), None)
                time_ago = 'Recent'
                if date_str:
                    try:
                        dt = parsedate_to_datetime(date_str)
                        delta = datetime.now(dt.tzinfo) - dt
                        if delta.days > 0: time_ago = f"{delta.days}d ago"
                        elif delta.seconds > 3600: time_ago = f"{delta.seconds // 3600}h ago"
                        else: time_ago = f"{delta.seconds // 60}m ago"
                    except: pass
                formatted_emails.append({'from': sender, 'subject': subject, 'snippet': msg_data['snippet'], 'time': time_ago})
            return formatted_emails
        except Exception as e:
            print(f"--- ERROR fetching emails: {e} ---")
            return []

    def get_recent_texts(self):
        if not self.is_openphone_configured(): return None
        try:
            url = f"{os.getenv('OPENPHONE_BASE_URL', 'https://api.openphone.com/v1')}/conversations?limit=5"
            headers = {"Authorization": f"Bearer {self.openphone_api_key}"}
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
            formatted_texts = []
            for convo in data.get('conversations', []):
                latest_message = convo.get('latestMessage', {})
                snippet = latest_message.get('body', 'No message body')
                from_number = 'Unknown'
                for p in convo.get('participants', []):
                    if p.get('phoneNumber') != self.openphone_phone_number:
                        from_number = p.get('phoneNumber')
                        break
                time_ago = 'Recent'
                timestamp_str = latest_message.get('createdAt')
                if timestamp_str:
                    dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                    delta = datetime.now(dt.tzinfo) - dt
                    if delta.days > 0: time_ago = f"{delta.days}d ago"
                    elif delta.seconds > 3600: time_ago = f"{delta.seconds // 3600}h ago"
                    else: time_ago = f"{delta.seconds // 60}m ago"
                formatted_texts.append({'from': from_number, 'snippet': snippet, 'time': time_ago})
            return formatted_texts
        except requests.exceptions.RequestException as e:
            print(f"--- ERROR fetching texts from OpenPhone: {e} ---")
            if hasattr(e, 'response') and e.response is not None:
                print(f"OpenPhone API Error: {e.response.status_code} - {e.response.text}")
            return []
        except Exception as e:
            print(f"--- An unexpected error occurred while processing texts: {e} ---")
            return []
