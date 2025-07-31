
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
from scripts.script_logger import get_logger

logger = get_logger(__name__)

import os
import pickle
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
import json

SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/calendar'
]
TOKEN_FILE = 'token.pickle'
CLIENT_SECRET_FILE = 'client_secret.json'

def main():
    creds = None
    
    if not os.path.exists(CLIENT_SECRET_FILE):
        logger.info(f"Error: '{CLIENT_SECRET_FILE}' not found in the current directory.")
        logger.info("Please ensure your Google Cloud project's client_secret.json is in the same directory as this script.")
        return

    with open(CLIENT_SECRET_FILE, 'r') as f:
        client_config = json.load(f)

    try:
        flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
        # IMPORTANT: Request offline access to get a refresh token
        creds = flow.run_local_server(port=8989, access_type='offline') 
        
        with open(TOKEN_FILE, 'wb') as token:
            pickle.dump(creds, token)
        logger.info(f"\nSuccessfully generated and saved credentials to '{TOKEN_FILE}'.")
        logger.info("You can now remove this 'generate_token.py' script.")
        
    except Exception as e:
        logger.info(f"An error occurred during the OAuth flow: {e}")
        logger.info("Please ensure your client_secret.json is correct and you have internet access.")

if __name__ == '__main__':
    main()
