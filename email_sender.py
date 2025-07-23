import base64
import os
import pickle
from email.mime.text import MIMEText

from flask import current_app
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# The scopes required for the Gmail API
SCOPES = ['https://www.googleapis.com/auth/gmail.send']
TOKEN_FILE = 'token.pickle' # This can remain as is

def get_gmail_service():
    """
    Authenticates with the Gmail API and returns the service object.
    This function handles token loading, validation, and refreshing.
    """
    creds = None

    # The token.pickle file stores the user's access and refresh tokens.
    # It's created automatically when the authorization flow completes for the first time.
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, 'rb') as token:
            creds = pickle.load(token)

    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            # CONSTRUCT credentials from Flask config instead of a client_secret.json file
            client_config = {
                "installed": {
                    "client_id": current_app.config['GOOGLE_CLIENT_ID'],
                    "project_id": current_app.config['GOOGLE_PROJECT_ID'],
                    "client_secret": current_app.config['GOOGLE_CLIENT_SECRET'],
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                    "redirect_uris": ["http://localhost"] # This is for local server flow
                }
            }
            flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
            creds = flow.run_local_server(port=0)
        
        # Save the credentials for the next run
        with open(TOKEN_FILE, 'wb') as token:
            pickle.dump(creds, token)

    return build('gmail', 'v1', credentials=creds)

def send_email(to, subject, message_text):
    """
    Creates and sends an email message using the authenticated Gmail service.
    
    Args:
        to: The recipient's email address.
        subject: The subject of the email.
        message_text: The plain text body of the email.
        
    Returns:
        The sent message object on success, or None on failure.
    """
    try:
        service = get_gmail_service()
        message = MIMEText(message_text)
        message['to'] = to
        message['subject'] = subject
        
        # The 'me' keyword refers to the authenticated user's email address.
        message['from'] = 'me'

        # The message body needs to be base64url encoded.
        encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()

        create_message = {
            'raw': encoded_message
        }
        
        send_message = (service.users().messages().send(userId="me", body=create_message).execute())
        print(f"Message Id: {send_message['id']}")
        return send_message
    except HttpError as error:
        print(f'An error occurred while sending email: {error}')
        return None
    except Exception as e:
        print(f'An unexpected error occurred: {e}')
        return None

