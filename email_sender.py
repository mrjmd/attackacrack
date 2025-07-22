# email_sender.py

import requests
import os
from dotenv import load_dotenv
from crm_database import setup_database, Contact, ContactDetail, Campaign, CampaignContact
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import time
import argparse # For command line arguments

load_dotenv() # Load environment variables from .env file

SMARTLEAD_API_KEY = os.getenv("SMARTLEAD_API_KEY")
SMARTLEAD_BASE_URL = "https://api.smartlead.ai/v1" # Confirm from SmartLead API docs

# Initialize database session factory
Session = sessionmaker(bind=setup_database().bind)

def add_lead_to_smartlead_campaign(smartlead_campaign_id, contact_data):
    """
    Adds a lead to a SmartLead campaign.
    SmartLead typically expects a list of leads, even if it's just one.

    Args:
        smartlead_campaign_id (str): The ID of the SmartLead campaign to add the lead to.
        contact_data (dict): A dictionary containing lead details (e.g., {'email': '...', 'first_name': '...', 'custom_field_1': '...'}).

    Returns:
        tuple: (bool, dict or None): True if successful, False otherwise, and the API response data.
    """
    headers = {
        "Authorization": f"Bearer {SMARTLEAD_API_KEY}",
        "Content-Type": "application/json"
    }
    # SmartLead often takes a list of leads, even for a single addition
    payload = {
        "campaign_id": smartlead_campaign_id,
        "leads": [contact_data]
    }
    endpoint = f"{SMARTLEAD_BASE_URL}/leads" # Example endpoint for adding leads. Confirm with SmartLead docs.

    try:
        response = requests.post(endpoint, json=payload, headers=headers)
        response.raise_for_status() # Raise an exception for HTTP errors
        response_data = response.json()
        print(f"Added lead to SmartLead campaign {smartlead_campaign_id}. Response: {response_data}")
        return True, response_data
    except requests.exceptions.RequestException as e:
        print(f"Error adding lead to SmartLead: {e}")
        if hasattr(e, 'response'):
            print(f"SmartLead API Response Error: {e.response.text}")
        return False, None

def process_email_campaign(campaign_id):
    """
    Processes a specific email campaign by adding eligible contacts as leads to SmartLead.

    Args:
        campaign_id (int): The ID of the campaign to process.
    """
    session = Session()
    campaign = session.query(Campaign).get(campaign_id)

    if not campaign:
        print(f"Campaign with ID {campaign_id} not found.")
        session.close()
        return
    if campaign.type != 'email':
        print(f"Campaign {campaign_id} is not an email campaign (type: {campaign.type}).")
        session.close()
        return
    if campaign.status != 'active':
        print(f"Campaign {campaign_id} is not active (status: {campaign.status}).")
        session.close()
        return

    print(f"Processing Email campaign: {campaign.name}")

    # Get contacts for this campaign that are still pending
    pending_campaign_contacts = session.query(CampaignContact).filter(
        CampaignContact.campaign_id == campaign.id,
        CampaignContact.message_status == 'pending'
    ).limit(125).all() # Limit to 125 per run for consistency with SMS

    if not pending_campaign_contacts:
        print("No pending contacts for this campaign. Marking campaign as completed.")
        campaign.status = 'completed'
        session.commit()
        session.close()
        return

    # The SmartLead campaign ID should ideally be stored in the Campaign model itself
    # For 'crawl' phase, we'll assume it's in the message_template or a dedicated field.
    # For 'walk' phase, we'd add a smartlead_campaign_id column to the Campaign table.
    # For now, let's parse it from message_template or use a placeholder.
    # Example: "SmartLead Campaign ID: sl_campaign_123"
    smartlead_campaign_id = None
    if campaign.message_template and "SmartLead Campaign ID:" in campaign.message_template:
        smartlead_campaign_id = campaign.message_template.split("SmartLead Campaign ID:")[1].strip()
    
    if not smartlead_campaign_id:
        print("Error: SmartLead Campaign ID not found in campaign message_template. Cannot proceed.")
        session.close()
        return

    for cc in pending_campaign_contacts:
        contact = cc.contact
        email_detail = session.query(ContactDetail).filter(
            ContactDetail.contact_id == contact.id,
            ContactDetail.type == 'email',
            ContactDetail.status == 'active'
        ).first()

        if not email_detail:
            print(f"No active email found for contact {contact.first_name} {contact.last_name}. Skipping.")
            cc.message_status = 'failed_no_email'
            campaign.failed_count += 1
            session.commit()
            continue

        # Prepare data for SmartLead. SmartLead uses custom fields for personalization.
        # Ensure these match the custom fields defined in your SmartLead campaign.
        lead_data = {
            "email": email_detail.value,
            "first_name": contact.first_name,
            "last_name": contact.last_name,
            # Example of adding a custom field from a linked property
            # For 'crawl', this might be complex to get the *right* property if multiple.
            # For now, let's assume we can get the first property linked if needed for personalization.
            # "custom_property_address": contact.properties[0].address if contact.properties else ""
        }

        success, response_sl = add_lead_to_smartlead_campaign(smartlead_campaign_id, lead_data)

        if success:
            cc.message_status = 'sent_to_smartlead' # SmartLead handles the actual sending and tracking
            cc.sent_at = datetime.now()
            # SmartLead might return a lead ID or a message ID in its response. Store it.
            cc.external_message_id = response_sl.get('lead_id') or response_sl.get('id')
            campaign.sent_count += 1
            email_detail.last_attempt_date = datetime.now()
            email_detail.last_successful_date = datetime.now()
            email_detail.delivery_status = 'sent_to_smartlead' # Initial status
        else:
            cc.message_status = 'failed_smartlead_add'
            campaign.failed_count += 1
            email_detail.last_attempt_date = datetime.now()
            email_detail.delivery_status = 'failed_smartlead_add'

        session.commit()
        time.sleep(0.5) # Small pause for API rate limits

    print(f"Finished processing batch for email campaign {campaign.name}. Sent to SmartLead: {campaign.sent_count}, Failed: {campaign.failed_count}")
    session.close()

if __name__ == "__main__":
    # This block is for testing the script directly.
    # In a real scenario, this script would be called by cron with a campaign_id.

    # Setup argument parser for command line execution
    parser = argparse.ArgumentParser(description="Process a SmartLead Email campaign.")
    parser.add_argument("--campaign_id", type=int, help="The ID of the Email campaign to process.")
    args = parser.parse_args()

    # Ensure database is set up
    setup_database()

    if args.campaign_id:
        process_email_campaign(args.campaign_id)
    else:
        print("No campaign ID provided. Running test campaign setup.")
        session = Session()
        try:
            # Check if a test campaign already exists to avoid duplicates
            test_email_campaign = session.query(Campaign).filter_by(name="Test Email Campaign").first()
            if not test_email_campaign:
                test_email_campaign = Campaign(
                    name="Test Email Campaign",
                    type='email',
                    status='active',
                    # IMPORTANT: Replace YOUR_SMARTLEAD_CAMPAIGN_ID_HERE with an actual SmartLead Campaign ID
                    message_template="SmartLead Campaign ID: YOUR_SMARTLEAD_CAMPAIGN_ID_HERE"
                )
                session.add(test_email_campaign)
                session.commit()
                print(f"Created test Email campaign with ID: {test_email_campaign.id}")
            else:
                print(f"Using existing test Email campaign with ID: {test_email_campaign.id}")
                test_email_campaign.status = 'active' # Ensure it's active for testing
                session.commit()

            # Add some contacts to the campaign (for testing, filter for homeowners with emails)
            contacts_for_email = session.query(Contact).join(Contact.contact_details).filter(
                Contact.contact_type == 'homeowner',
                ContactDetail.type == 'email',
                ContactDetail.status == 'active'
            ).limit(5).all() # Get first 5 eligible contacts for example

            if not contacts_for_email:
                print("No eligible contacts (homeowners with active emails) found in CRM. Please add some contacts first using crm_manager.py.")
                # Add a dummy contact if none exist for testing purposes
                dummy_contact = Contact(first_name="Email", last_name="Tester", contact_type="homeowner")
                session.add(dummy_contact)
                session.flush()
                session.add(ContactDetail(contact=dummy_contact, type='email', value='test@example.com', label='personal', status='active'))
                session.commit()
                contacts_for_email = [dummy_contact]
                print("Added a dummy contact for email testing.")

            for contact in contacts_for_email:
                # Check if contact is already in this campaign
                existing_cc = session.query(CampaignContact).filter_by(
                    campaign_id=test_email_campaign.id, contact_id=contact.id
                ).first()
                if not existing_cc:
                    campaign_contact = CampaignContact(campaign=test_email_campaign, contact=contact, message_status='pending')
                    session.add(campaign_contact)
                    test_email_campaign.total_recipients += 1
            session.commit()
            print(f"Added/Ensured {len(contacts_for_email)} contacts are in email campaign {test_email_campaign.id}")

            # Now, process the email campaign
            process_email_campaign(test_email_campaign.id)

        except Exception as e:
            session.rollback()
            print(f"An error occurred during test email campaign setup: {e}")
        finally:
            session.close()

    # To schedule this script to run daily at 9 AM ET using cron:
    # 1. Make the script executable: `chmod +x email_sender.py`
    # 2. Open your crontab: `crontab -e`
    # 3. Add the following line (replace /path/to/your/project with your actual path):
    #    0 9 * * 1-5 /usr/bin/python3 /path/to/your/project/email_sender.py --campaign_id <YOUR_EMAIL_CAMPAIGN_ID_HERE>
