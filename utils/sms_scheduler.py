# sms_scheduler.py

import os
import pandas as pd
import requests
import time
from datetime import datetime
from dotenv import load_dotenv
import logging

# --- Configuration ---
# Load environment variables from .env file
load_dotenv()

# Configure basic logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# OpenPhone API details
OPENPHONE_API_KEY = os.getenv("OPENPHONE_API_KEY")
OPENPHONE_PHONE_NUMBER = os.getenv("OPENPHONE_PHONE_NUMBER")
OPENPHONE_API_BASE_URL = "https://api.openphone.com/v1"

# CSV file path
CSV_FILE = "test.csv" # Still pointing to test.csv as per your output

# Message details
MESSAGE_TEMPLATE = "[TEST MESSAGE, IGNORE] Hi {name}, Matt Davis here—managing partner at Attack A Crack. You may have seen an email go out recently to Jack Conway agents about us as a new foundation repair resource. I wanted to introduce myself and make sure you have my number handy for any foundation concerns that come up.\n\nWith all the recent rain, we’re seeing a spike in calls about leaking basement cracks. If you’ve gotten anything like that, I’m happy to help. Feel free to send over any foundation or concrete questions or photos anytime for a quick answer."
MAX_MESSAGES_PER_RUN = 125

# Rate limiting and throttling
API_REQUEST_DELAY = 0.1
MESSAGE_THROTTLING_DELAY = 2

# --- Helper Functions ---

def send_openphone_message(to_number, content):
    if not OPENPHONE_API_KEY or not OPENPHONE_PHONE_NUMBER:
        logging.error("OpenPhone API Key or Phone Number not set in .env file.")
        return None, "error: config_missing"

    headers = {
        "Authorization": OPENPHONE_API_KEY,
        "Content-Type": "application/json"
    }
    payload = {
        "from": OPENPHONE_PHONE_NUMBER,
        "to": [to_number],
        "content": content
    }

    try:
        logging.info(f"Attempting to send message to {to_number}...")
        response = requests.post(f"{OPENPHONE_API_BASE_URL}/messages", headers=headers, json=payload)
        response.raise_for_status()

        data = response.json().get("data", {})
        message_id = data.get("id")
        status = data.get("status")

        if message_id and status:
            logging.info(f"Message sent to {to_number}. OpenPhone Message ID: {message_id}, Status: {status}")
            return message_id, status
        else:
            logging.error(f"Failed to get message_id or status from OpenPhone response for {to_number}. Response: {response.text}")
            return None, f"error: {response.status_code} - {response.text}"

    except requests.exceptions.HTTPError as http_err:
        logging.error(f"HTTP error sending to {to_number}: {http_err} - {response.text}")
        return None, f"error: http_error_{response.status_code}"
    except requests.exceptions.ConnectionError as conn_err:
        logging.error(f"Connection error sending to {to_number}: {conn_err}")
        return None, "error: connection_error"
    except requests.exceptions.Timeout as timeout_err:
        logging.error(f"Timeout error sending to {to_number}: {timeout_err}")
        return None, "error: timeout_error"
    except requests.exceptions.RequestException as req_err:
        logging.error(f"An unexpected request error occurred sending to {to_number}: {req_err}")
        return None, "error: unknown_request_error"
    except Exception as e:
        logging.critical(f"An unforeseen error occurred sending to {to_number}: {e}", exc_info=True)
        return None, "error: critical_failure"

def get_message_status(message_id):
    if not OPENPHONE_API_KEY:
        logging.error("OpenPhone API Key not set for status check.")
        return None

    headers = {
        "Authorization": OPENPHONE_API_KEY,
        "Content-Type": "application/json"
    }

    try:
        response = requests.get(f"{OPENPHONE_API_BASE_URL}/messages/{message_id}", headers=headers)
        response.raise_for_status()

        data = response.json().get("data", {})
        status = data.get("status")
        if status:
            logging.info(f"Fetched status for message ID {message_id}: {status}")
            return status
        else:
            logging.warning(f"Could not get status for message ID {message_id}. Response: {response.text}")
            return None

    except requests.exceptions.HTTPError as http_err:
        if response.status_code == 404:
            logging.warning(f"Message ID {message_id} not found on OpenPhone. It might have been too old or invalid. Error: {http_err}")
            return "error: not_found"
        logging.error(f"HTTP error fetching status for {message_id}: {http_err} - {response.text}")
        return f"error: http_error_{response.status_code}"
    except Exception as e:
        logging.error(f"Error fetching status for {message_id}: {e}", exc_info=True)
        return "error: status_fetch_failure"


def run_scheduler():
    logging.info("Starting OpenPhone SMS Scheduler.")
    df = None # Initialize df to None or an empty DataFrame

    try:
        # 1. Load contacts from CSV
        if not os.path.exists(CSV_FILE):
            logging.critical(f"CSV file not found at: {CSV_FILE}. Please create it with headers: name,phone_number,status,message_sent_at,openphone_message_id")
            return # Exit early if file not found, df remains None

        # NEW: Explicitly read 'phone_number' as a string to prevent issues with leading '+'
        df = pd.read_csv(CSV_FILE, dtype={'phone_number': str})
        logging.info(f"Loaded {len(df)} contacts from {CSV_FILE}.")

        # Ensure required columns exist, add if missing with default values
        for col in ["status", "message_sent_at", "openphone_message_id"]:
            if col not in df.columns:
                df[col] = ""
                logging.warning(f"Added missing column: '{col}' to DataFrame.")

        df['status'] = df['status'].astype(str)

        # Update message statuses for previously sent messages
        contacts_to_update_status = df[
            (df['status'] == 'sent') | (df['status'] == 'queued')
        ].copy()

        if not contacts_to_update_status.empty:
            logging.info(f"Checking status for {len(contacts_to_update_status)} previously sent messages...")
            for index, row in contacts_to_update_status.iterrows():
                message_id = row['openphone_message_id']
                if pd.notna(message_id) and str(message_id).strip() != "":
                    current_status = get_message_status(message_id)
                    if current_status and current_status != row['status']:
                        df.loc[index, 'status'] = current_status
                        logging.info(f"Updated contact {row['name']} ({row['phone_number']}) status to: {current_status}")
                    time.sleep(API_REQUEST_DELAY)
                else:
                    logging.warning(f"Skipping status update for contact {row['name']} due to missing OpenPhone Message ID.")
        else:
            logging.info("No previously sent messages with 'sent' or 'queued' status to update.")

        # Filter contacts to send messages to
        contacts_to_message = df[
            (df['status'] == 'nan') | (df['status'] == '') |
            (df['status'].str.startswith('error'))
        ].head(MAX_MESSAGES_PER_RUN).copy()


        if contacts_to_message.empty:
            logging.info("No new contacts to message or all desired messages sent for this run.")
            return

        logging.info(f"Attempting to send messages to {len(contacts_to_message)} contacts.")

        sent_count = 0
        for index, row in contacts_to_message.iterrows():
            name = row['name']
            phone_number = str(row['phone_number']).strip()

            if not phone_number.startswith('+') or len(phone_number) < 10:
                logging.warning(f"Skipping invalid phone number for {name}: {phone_number}. Must be E.164 format (e.g., +12025550123).")
                df.loc[index, 'status'] = 'error: invalid_phone_number'
                continue

            message_content = MESSAGE_TEMPLATE.format(name=name)

            message_id, send_status = send_openphone_message(phone_number, message_content)

            if message_id:
                df.loc[index, 'status'] = send_status
                df.loc[index, 'message_sent_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                df.loc[index, 'openphone_message_id'] = message_id
                sent_count += 1
            else:
                df.loc[index, 'status'] = send_status
                df.loc[index, 'message_sent_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            time.sleep(MESSAGE_THROTTLING_DELAY)

            if sent_count >= MAX_MESSAGES_PER_RUN:
                logging.info(f"Reached maximum messages per run ({MAX_MESSAGES_PER_RUN}). Stopping sending.")
                break


        logging.info(f"Finished sending messages. Sent {sent_count} messages in this run.")

    except pd.errors.EmptyDataError:
        logging.critical(f"The CSV file '{CSV_FILE}' is empty. Please add data.")
    except pd.errors.ParserError as pe:
        logging.critical(f"Error parsing CSV file '{CSV_FILE}': {pe}. Check CSV format.")
    except FileNotFoundError:
        # This block might not be reached if os.path.exists is checked first
        logging.critical(f"The CSV file '{CSV_FILE}' was not found. Ensure it's in the same directory as the script.")
    except Exception as e:
        logging.critical(f"An unexpected error occurred during script execution: {e}", exc_info=True)
    finally:
        # Only attempt to save if df was successfully loaded
        if df is not None:
            try:
                df.to_csv(CSV_FILE, index=False)
                logging.info(f"Updated contact data saved to {CSV_FILE}.")
            except Exception as e:
                logging.critical(f"Failed to save updated CSV file: {e}", exc_info=True)

# --- Main execution block ---
if __name__ == "__main__":
    run_scheduler()
