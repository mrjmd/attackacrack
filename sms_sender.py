# sms_sender.py

import requests
import os
from dotenv import load_dotenv
from crm_database import setup_database, Contact, ContactDetail, Campaign, CampaignContact
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import time
import argparse # For command line arguments

load_dotenv() # Load environment variables from .env file

OPENPHONE_API_KEY = os.getenv("OPENPHONE_API_KEY")
OPENPHONE_PHONE_NUMBER = os.getenv("OPENPHONE_PHONE_NUMBER") # Your OpenPhone number in E.164 format (e.g., +12025550123)
OPENPHONE_BASE_URL = "https://api.openphone.com/v1"

# Initialize database session factory
Session = sessionmaker(bind=setup_database().bind)

def send_openphone_sms(to_number, message_body, from_number_id):
    """
    Sends a single SMS via OpenPhone API.

    Args:
        to_number (str): The recipient's phone number in E.164 format.
        message_body (str): The content of the message.
        from_number_id (str): The OpenPhone number (in E.164 format) from which to send the message.
                              Confirm with OpenPhone API docs if this should be the number itself
                              or an internal OpenPhone ID for the number. Assuming E.164 number for now.

    Returns:
        tuple: (bool, str or None): True if successful, False otherwise, and the OpenPhone message ID.
    """
    headers = {
        "Authorization": OPENPHONE_API_KEY, # OpenPhone uses API key directly, not Bearer token
        "Content-Type": "application/json"
    }
    payload = {
        "phoneNumberId": from_number_id,
        "toPhoneNumber": to_number,
        "message": message_body
    }
    endpoint = f"{OPENPHONE_BASE_URL}/messages" # Confirm endpoint from OpenPhone API docs

    try:
        response = requests.post(endpoint, json=payload, headers=headers)
        response.raise_for_status() # Raise an exception for HTTP errors (4xx or 5xx)
        response_data = response.json()
        print(f"SMS sent to {to_number}. OpenPhone Message ID: {response_data.get('id')}")
        return True, response_data.get('id')
    except requests.exceptions.RequestException as e:
        print(f"Error sending SMS to {to_number}: {e}")
        if hasattr(e, 'response') and e.response.status_code == 429:
            print("Rate limit exceeded. Consider increasing delay.")
        return False, None

def process_sms_campaign(campaign_id):
    """
    Processes a specific SMS campaign by sending messages to eligible contacts.

    Args:
        campaign_id (int): The ID of the campaign to process.
    """
    session = Session()
    campaign = session.query(Campaign).get(campaign_id)

    if not campaign:
        print(f"Campaign with ID {campaign_id} not found.")
        session.close()
        return
    if campaign.type != 'sms':
        print(f"Campaign {campaign_id} is not an SMS campaign (type: {campaign.type}).")
        session.close()
        return
    if campaign.status != 'active':
        print(f"Campaign {campaign_id} is not active (status: {campaign.status}).")
        session.close()
        return

    print(f"Processing SMS campaign: {campaign.name}")

    # Get contacts for this campaign that are still pending
    # We limit to 125 per run as per your requirement for daily sending
    pending_campaign_contacts = session.query(CampaignContact).filter(
        CampaignContact.campaign_id == campaign.id,
        CampaignContact.message_status == 'pending'
    ).limit(125).all()

    if not pending_campaign_contacts:
        print("No pending contacts for this campaign. Marking campaign as completed.")
        campaign.status = 'completed' # Mark campaign as completed if no pending contacts
        session.commit()
        session.close()
        return

    for cc in pending_campaign_contacts:
        contact = cc.contact
        # Get the primary mobile number for the contact
        # Prioritize 'mobile' label, then any 'phone' type that is 'active'
        mobile_detail = session.query(ContactDetail).filter(
            ContactDetail.contact_id == contact.id,
            ContactDetail.type == 'phone',
            ContactDetail.status == 'active'
        ).order_by(
            # Order by label to prioritize 'mobile', then others
            ContactDetail.label == 'mobile'
        ).first()

        if not mobile_detail:
            print(f"No active mobile number found for contact {contact.first_name} {contact.last_name}. Skipping.")
            cc.message_status = 'failed_no_number'
            campaign.failed_count += 1
            session.commit()
            continue

        to_number = mobile_detail.value
        # Personalize message: Replace "[]" with the contact's first name
        message_body = campaign.message_template.replace("[]", f"{contact.first_name}")

        success, external_id = send_openphone_sms(to_number, message_body, OPENPHONE_PHONE_NUMBER)

        if success:
            cc.message_status = 'sent'
            cc.sent_at = datetime.now()
            cc.external_message_id = external_id
            campaign.sent_count += 1
            mobile_detail.last_attempt_date = datetime.now()
            mobile_detail.last_successful_date = datetime.now()
            mobile_detail.delivery_status = 'sent' # Initial status, will update with webhooks later
        else:
            cc.message_status = 'failed_send'
            campaign.failed_count += 1
            mobile_detail.last_attempt_date = datetime.now()
            mobile_detail.delivery_status = 'failed' # Initial status
            # For 'walk' phase: implement logic to try secondary number if available
            # For now, just log the failure.

        session.commit()
        # Pause to respect API rate limits (10 requests/sec) and carrier throttling (e.g., 1 message/sec)
        # 1.5 seconds per message ensures we are well within limits.
        time.sleep(1.5)

    print(f"Finished processing batch for campaign {campaign.name}. Sent: {campaign.sent_count}, Failed: {campaign.failed_count}")
    session.close()

if __name__ == "__main__":
    # This block is for testing the script directly.
    # In a real scenario, this script would be called by cron with a campaign_id.

    # Setup argument parser for command line execution
    parser = argparse.ArgumentParser(description="Process an OpenPhone SMS campaign.")
    parser.add_argument("--campaign_id", type=int, help="The ID of the SMS campaign to process.")
    args = parser.parse_args()

    # Ensure database is set up (this creates the crm.db file and tables if they don't exist)
    # The session factory 'Session' is already bound to this engine.
    setup_database()

    if args.campaign_id:
        process_sms_campaign(args.campaign_id)
    else:
        print("No campaign ID provided. Running test campaign setup.")
        # Example: Create a test SMS campaign and add contacts
        session = Session()
        try:
            # Check if a test campaign already exists to avoid duplicates
            test_campaign = session.query(Campaign).filter_by(name="Test SMS Campaign").first()
            if not test_campaign:
                test_campaign = Campaign(
                    name="Test SMS Campaign",
                    type='sms',
                    status='active',
                    message_template="Hi [], Matt Davis here—managing partner at Attack A Crack. This is a test message from your new CRM automation system. Hope it's working!"
                )
                session.add(test_campaign)
                session.commit()
                print(f"Created test SMS campaign with ID: {test_campaign.id}")
            else:
                print(f"Using existing test SMS campaign with ID: {test_campaign.id}")
                test_campaign.status = 'active' # Ensure it's active for testing
                session.commit()

            # Add some contacts to the campaign (for testing, assume they exist or create some)
            # You would replace this with actual logic to select contacts for a campaign
            contacts_to_add = session.query(Contact).limit(5).all() # Get first 5 contacts for example
            if not contacts_to_add:
                print("No contacts found in CRM. Please add some contacts first using crm_manager.py.")
                # Add a dummy contact if none exist for testing purposes
                dummy_contact = Contact(first_name="Test", last_name="User", contact_type="test_lead")
                session.add(dummy_contact)
                session.flush()
                session.add(ContactDetail(contact=dummy_contact, type='phone', value='+15550001111', label='mobile', status='active'))
                session.commit()
                contacts_to_add = [dummy_contact]
                print("Added a dummy contact for testing.")

            for contact in contacts_to_add:
                # Check if contact is already in this campaign
                existing_cc = session.query(CampaignContact).filter_by(
                    campaign_id=test_campaign.id, contact_id=contact.id
                ).first()
                if not existing_cc:
                    campaign_contact = CampaignContact(campaign=test_campaign, contact=contact, message_status='pending')
                    session.add(campaign_contact)
                    test_campaign.total_recipients += 1
            session.commit()
            print(f"Added/Ensured {len(contacts_to_add)} contacts are in campaign {test_campaign.id}")

            # Now, process the campaign
            process_sms_campaign(test_campaign.id)

        except Exception as e:
            session.rollback()
            print(f"An error occurred during test campaign setup: {e}")
        finally:
            session.close()

    # To schedule this script to run daily at 9 AM ET using cron:
    # 1. Make the script executable: `chmod +x sms_sender.py`
    # 2. Open your crontab: `crontab -e`
    # 3. Add the following line (replace /path/to/your/project with your actual path):
    #    0 9 * * 1-5 /usr/bin/python3 /path/to/your/project/sms_sender.py --campaign_id <YOUR_CAMPAIGN_ID_HERE>
    #    This runs Monday-Friday at 9:00 AM.
