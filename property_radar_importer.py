# property_radar_importer.py

import requests
import os
from dotenv import load_dotenv
from crm_database import setup_database, Contact, ContactDetail, Property, ContactProperty, PropertyRadarQuery, ContactSource
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import argparse
import json

load_dotenv() # Load environment variables from .env file

PROPERTY_RADAR_API_KEY = os.getenv("PROPERTY_RADAR_API_KEY")
# Confirm the base URL from PropertyRadar's official API documentation
PROPERTY_RADAR_BASE_URL = "https://api.propertyradar.com/v1" # This is a common pattern, verify exact URL

# Initialize database session factory for standalone testing
_Session_for_testing = sessionmaker(bind=setup_database().bind)

def fetch_properties_from_propertyradar(session, query_params, description):
    """
    Fetches property data from PropertyRadar API and logs the query.

    Args:
        session: The SQLAlchemy session object.
        query_params (dict): Dictionary of parameters for the PropertyRadar search endpoint.
                             This will be highly dependent on PropertyRadar's specific API structure.
        description (str): A user-friendly description of this query for logging.

    Returns:
        tuple: (list, int or None): List of property data dictionaries, and the ID of the logged query.
    """
    headers = {
        "Authorization": f"Bearer {PROPERTY_RADAR_API_KEY}",
        "Content-Type": "application/json"
    }
    endpoint = f"{PROPERTY_RADAR_BASE_URL}/properties/search" # Example endpoint: verify with PR docs

    print(f"Attempting to fetch properties with query: {json.dumps(query_params, indent=2)}")

    try:
        response = requests.post(endpoint, json=query_params, headers=headers)
        response.raise_for_status() # Raise an exception for HTTP errors (4xx or 5xx)
        data = response.json()
        
        properties_data = data.get('results', []) # Adjust 'results' key based on actual API response structure
        print(f"Fetched {len(properties_data)} properties from PropertyRadar.")

        # Log the query parameters and results
        try:
            pr_query_log = PropertyRadarQuery(
                query_params=query_params,
                description=description,
                total_results=len(properties_data)
            )
            session.add(pr_query_log)
            session.commit()
            return properties_data, pr_query_log.id
        except Exception as e:
            session.rollback()
            print(f"Error logging PropertyRadar query: {e}")
            return properties_data, None # Still return data if fetch was successful

    except requests.exceptions.RequestException as e:
        print(f"Error fetching from PropertyRadar: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"PropertyRadar API Error Response: {e.response.text}")
        return [], None

def import_property_data(session, properties_data, pr_query_id):
    """
    Imports fetched property data and associated contacts into the CRM.

    Args:
        session: The SQLAlchemy session object.
        properties_data (list): List of dictionaries, each representing a property and its contacts.
        pr_query_id (int): The ID of the PropertyRadarQuery log entry this data belongs to.
    """
    new_contacts_count = 0
    existing_contacts_updated = 0
    new_properties_count = 0
    existing_properties_updated = 0

    try:
        for prop_data in properties_data:
            apn = prop_data.get('APN')
            if not apn:
                print(f"Skipping property due to missing APN: {prop_data.get('Address', 'Unknown Address')}")
                continue

            property_obj = session.query(Property).filter_by(apn=apn).first()
            if not property_obj:
                property_obj = Property(
                    apn=apn,
                    address=prop_data.get('Address'),
                    city=prop_data.get('City'),
                    zip_code=prop_data.get('ZIP'),
                    subdivision=prop_data.get('Subdivision'),
                    latitude=float(prop_data['Latitude']) if prop_data.get('Latitude') else None,
                    longitude=float(prop_data['Longitude']) if prop_data.get('Longitude') else None,
                    year_built=prop_data.get('Yr Built'),
                    purchase_date=datetime.strptime(prop_data['Purchase Date'], '%Y-%m-%d') if prop_data.get('Purchase Date') else None,
                    purchase_months_since=prop_data.get('Purchase Mos Since'),
                    sq_ft=prop_data.get('Sq Ft'),
                    beds=prop_data.get('Beds'),
                    baths=prop_data.get('Baths'),
                    est_value=prop_data.get('Est Value'),
                    est_equity_dollars=prop_data.get('Est Equity $'),
                    est_equity_percent=float(prop_data['Est Equity %']) if prop_data.get('Est Equity %') else None,
                    high_equity=prop_data.get('High Equity?'),
                    owner_occupied=prop_data.get('Owner Occ?'),
                    listed_for_sale=prop_data.get('Listed for Sale?'),
                    listing_status=prop_data.get('Listing Status'),
                    foreclosure=prop_data.get('Foreclosure?'),
                    mail_address=prop_data.get('Mail Address'),
                    mail_city=prop_data.get('Mail City'),
                    mail_state=prop_data.get('Mail State'),
                    mail_zip=prop_data.get('Mail ZIP'),
                    property_radar_id=prop_data.get('PropertyRadarID')
                )
                session.add(property_obj)
                new_properties_count += 1
                print(f"Added new property: {property_obj.address}")
            else:
                property_obj.est_value = prop_data.get('Est Value', property_obj.est_value)
                property_obj.est_equity_dollars = prop_data.get('Est Equity $', property_obj.est_equity_dollars)
                property_obj.est_equity_percent = float(prop_data['Est Equity %']) if prop_data.get('Est Equity %') else property_obj.est_equity_percent
                property_obj.listed_for_sale = prop_data.get('Listed for Sale?', property_obj.listed_for_sale)
                property_obj.listing_status = prop_data.get('Listing Status', property_obj.listing_status)
                property_obj.foreclosure = prop_data.get('Foreclosure?', property_obj.foreclosure)
                property_obj.high_equity = prop_data.get('High Equity?', property_obj.high_equity)
                existing_properties_updated += 1
                print(f"Updated existing property: {property_obj.address}")
            session.flush()

            contact_roles = {
                'primary_owner': {
                    'name': prop_data.get('Primary Name'),
                    'mobile': prop_data.get('Primary Mobile Phone1'),
                    'mobile_status': prop_data.get('Primary Mobile 1 Status'),
                    'email': prop_data.get('Primary Email1'),
                    'email_status': prop_data.get('Primary Email 1 Status'),
                    'type': 'homeowner' if prop_data.get('Owner Occ?') else 'absentee_owner'
                },
                'secondary_owner': {
                    'name': prop_data.get('Secondary Name'),
                    'mobile': prop_data.get('Secondary Mobile Phone1'),
                    'mobile_status': prop_data.get('Secondary Mobile 1 Status'),
                    'email': prop_data.get('Secondary Email1'),
                    'email_status': prop_data.get('Secondary Email 1 Status'),
                    'type': 'homeowner' if prop_data.get('Owner Occ?') else 'absentee_owner'
                }
            }

            for role, c_data in contact_roles.items():
                if not c_data.get('name') and not c_data.get('mobile') and not c_data.get('email'):
                    continue

                existing_contact = None
                if c_data.get('mobile'):
                    existing_contact_detail = session.query(ContactDetail).filter_by(type='phone', value=c_data['mobile']).first()
                    if existing_contact_detail:
                        existing_contact = existing_contact_detail.contact
                if not existing_contact and c_data.get('email'):
                    existing_contact_detail = session.query(ContactDetail).filter_by(type='email', value=c_data['email']).first()
                    if existing_contact_detail:
                        existing_contact = existing_contact_detail.contact
                
                if not existing_contact and c_data.get('name') and prop_data.get('Mail Address') and prop_data.get('Mail ZIP'):
                    first_name_search = c_data['name'].split(' ')[0] if c_data['name'] else None
                    last_name_search = ' '.join(c_data['name'].split(' ')[1:]) if c_data['name'] else None
                    if first_name_search and last_name_search:
                        existing_contact = session.query(Contact).filter_by(
                            first_name=first_name_search,
                            last_name=last_name_search
                        ).first()
                        if existing_contact:
                            # Access properties via the relationship, then check mail_address
                            linked_props = [cp.property for cp in existing_contact.properties if cp.mail_address == prop_data['Mail Address']]
                            if not linked_props:
                                existing_contact = None

                if not existing_contact:
                    first_name = c_data['name'].split(' ')[0] if c_data.get('name') else None
                    last_name = ' '.join(c_data['name'].split(' ')[1:]) if c_data.get('name') else None
                    contact = Contact(
                        first_name=first_name,
                        last_name=last_name,
                        contact_type=c_data.get('type', 'unknown'),
                        contact_status='new_lead'
                    )
                    session.add(contact)
                    session.flush()
                    new_contacts_count += 1
                    print(f"Added new contact: {contact.first_name} {contact.last_name}")
                else:
                    contact = existing_contact
                    existing_contacts_updated += 1
                    if contact.contact_type == 'new_lead' or contact.contact_type == 'unknown': # Allow update from generic to specific type
                        contact.contact_type = c_data['type']
                    print(f"Updated existing contact: {contact.first_name} {contact.last_name}")

                if c_data.get('mobile'):
                    existing_mobile_detail = session.query(ContactDetail).filter_by(contact_id=contact.id, type='phone', value=c_data['mobile']).first()
                    if not existing_mobile_detail:
                        session.add(ContactDetail(contact=contact, type='phone', value=c_data['mobile'], label='mobile', status=c_data.get('mobile_status', 'active')))
                    else:
                        existing_mobile_detail.status = c_data.get('mobile_status', existing_mobile_detail.status)
                        existing_mobile_detail.updated_at = datetime.now()

                if c_data.get('email'):
                    existing_email_detail = session.query(ContactDetail).filter_by(contact_id=contact.id, type='email', value=c_data['email']).first()
                    if not existing_email_detail:
                        session.add(ContactDetail(contact=contact, type='email', value=c_data['email'], label='personal', status=c_data.get('email_status', 'active')))
                    else:
                        existing_email_detail.status = c_data.get('email_status', existing_email_detail.status)
                        existing_email_detail.updated_at = datetime.now()

                existing_contact_property = session.query(ContactProperty).filter_by(
                    contact_id=contact.id, property_id=property_obj.id
                ).first()
                if not existing_contact_property:
                    session.add(ContactProperty(contact_id=contact.id, property_id=property_obj.id, role=role))
                    print(f"Linked {contact.first_name} to {property_obj.address} as {role}")
                else:
                    if existing_contact_property.role != role:
                        existing_contact_property.role = role
                        print(f"Updated role for {contact.first_name} on {property_obj.address} to {role}")

                existing_contact_source = session.query(ContactSource).filter_by(
                    contact_id=contact.id, source_id=pr_query_id, source_type='PropertyRadar_Query'
                ).first()
                if not existing_contact_source:
                    session.add(ContactSource(contact_id=contact.id, source_type='PropertyRadar_Query', source_id=pr_query_id, original_data=prop_data))
                    print(f"Logged source for {contact.first_name} from query {pr_query_id}")
                else:
                    if existing_contact_source.original_data != prop_data:
                        existing_contact_source.original_data = prop_data
                        print(f"Updated source data for {contact.first_name} from query {pr_query_id}")

        session.commit()
        pr_query = session.query(PropertyRadarQuery).get(pr_query_id)
        if pr_query:
            pr_query.new_contacts_added = new_contacts_count
            pr_query.existing_contacts_updated = existing_contacts_updated
            session.commit()

        print(f"\nImport Summary for Query ID {pr_query_id}:")
        print(f"  New properties added: {new_properties_count}")
        print(f"  Existing properties updated: {existing_properties_updated}")
        print(f"  New contacts added: {new_contacts_count}")
        print(f"  Existing contacts updated: {existing_contacts_updated}")
        return True # Indicate success
    except Exception as e:
        session.rollback()
        print(f"An error occurred during property data import: {e}")
        return False # Indicate failure


def run_property_radar_import(session, query_params, description="Web UI Import"):
    """
    Main function to run the PropertyRadar import process, callable from other modules.
    """
    properties_data, query_log_id = fetch_properties_from_propertyradar(session, query_params, description)
    if properties_data:
        return import_property_data(session, properties_data, query_log_id)
    return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Import property data from PropertyRadar.")
    parser.add_argument("--query_file", type=str, help="Path to a JSON file containing PropertyRadar query parameters.")
    parser.add_argument("--description", type=str, default="Manual PropertyRadar Import",
                        help="A description for this import query log.")
    args = parser.parse_args()

    # Ensure database is set up for standalone run
    setup_database()
    session = _Session_for_testing() # Use the testing session factory

    query_params = {}
    if args.query_file:
        try:
            with open(args.query_file, 'r') as f:
                query_params = json.load(f)
            print(f"Loaded query parameters from {args.query_file}")
        except FileNotFoundError:
            print(f"Error: Query file not found at {args.query_file}")
            exit(1)
        except json.JSONDecodeError:
            print(f"Error: Invalid JSON in query file {args.query_file}")
            exit(1)
    else:
        print("No query file provided. Using a default example query. Please customize.")
        query_params = {
            "filters": {
                "propertyType": "Residential",
                "yearBuilt": {"min": 1950},
                "estimatedValue": {"min": 600000},
                # "hasBasement": True, # Confirm if PropertyRadar API supports this filter directly
                "location": {
                    "zipCodes": ["02169", "02170", "02171", "02172", "02184", "02186", "02368", "02043"]
                }
            },
            "fields": [
                "APN", "Address", "City", "ZIP", "Subdivision", "Longitude", "Latitude",
                "Yr Built", "Purchase Date", "Purchase Mos Since", "Sq Ft", "Beds", "Baths",
                "Est Value", "Est Equity $", "Est Equity %", "Owner Occ?",
                "Listed for Sale?", "Listing Status", "Foreclosure?", "High Equity?",
                "Primary Name", "Primary Mobile Phone1", "Primary Mobile 1 Status",
                "Primary Email1", "Primary Email 1 Status",
                "Secondary Name", "Secondary Mobile Phone1", "Secondary Mobile 1 Status",
                "Secondary Email1", "Secondary Email 1 Status"
            ]
        }
        args.description = "Default PropertyRadar Query: Homes >$600k, built post-1950, example MA ZIPs"

    success = run_property_radar_import(session, query_params, args.description)
    if success:
        print("PropertyRadar import process completed successfully.")
    else:
        print("PropertyRadar import process failed.")
    
    session.close()

