# csv_importer.py

import pandas as pd
import os
from datetime import datetime
from crm_database import setup_database, Contact, ContactDetail, ContactSource
from sqlalchemy.orm import sessionmaker

# Initialize database session factory for standalone testing
_Session_for_testing = sessionmaker(bind=setup_database().bind)

def import_contacts_from_csv(session, file_path, contact_type, source_description="CSV Import"):
    """
    Imports contacts from a CSV file into the CRM database.

    Args:
        session: The SQLAlchemy session object.
        file_path (str): Path to the CSV file.
        contact_type (str): The type to assign to contacts imported from this CSV (e.g., 'realtor', 'homeowner').
        source_description (str): A description for the ContactSource log entry.

    Returns:
        tuple: (bool, str): True if successful, False otherwise, and a summary message.
    """
    if not os.path.exists(file_path):
        return False, f"Error: CSV file not found at {file_path}"

    try:
        df = pd.read_csv(file_path)
        
        # Expected columns (case-insensitive check for flexibility)
        # We'll try to map common names to our schema
        col_map = {
            'first_name': ['first name', 'firstname', 'given name'],
            'last_name': ['last name', 'lastname', 'surname'],
            'phone_number': ['phone', 'phone number', 'mobile', 'mobile phone'],
            'email': ['email', 'email address'],
            'notes': ['notes', 'description']
        }
        
        # Find actual column names in DataFrame
        df_cols = {col.lower(): col for col in df.columns}
        
        # Map DataFrame columns to our internal names
        mapped_cols = {}
        for internal_name, possible_names in col_map.items():
            for pn in possible_names:
                if pn in df_cols:
                    mapped_cols[internal_name] = df_cols[pn]
                    break

        required_cols = ['first_name', 'last_name'] # At least name is required
        if not all(rc in mapped_cols for rc in required_cols):
            return False, "Error: CSV must contain 'First Name' and 'Last Name' columns (or common variations)."

        imported_count = 0
        updated_count = 0
        skipped_count = 0

        # Log the CSV import as a source
        # For CSV, we don't have a specific 'source_id' like PropertyRadarQuery, so we'll use 0 or None
        # and rely on source_type and description.
        csv_source_log = ContactSource(
            source_type='CSV_Import',
            source_id=0, # Placeholder, will update contact_source.original_data with filename
            import_date=datetime.now(),
            original_data={'filename': os.path.basename(file_path), 'description': source_description}
        )
        session.add(csv_source_log)
        session.flush() # Get ID for csv_source_log if needed, though not strictly used as FK

        for index, row in df.iterrows():
            first_name = row[mapped_cols['first_name']]
            last_name = row[mapped_cols['last_name']]
            phone_value = row.get(mapped_cols.get('phone_number'))
            email_value = row.get(mapped_cols.get('email'))
            notes = row.get(mapped_cols.get('notes'))

            # Basic de-duplication: Try to find existing contact by phone or email
            existing_contact = None
            if pd.notna(phone_value):
                existing_phone_detail = session.query(ContactDetail).filter_by(type='phone', value=str(phone_value)).first()
                if existing_phone_detail:
                    existing_contact = existing_phone_detail.contact
            if not existing_contact and pd.notna(email_value):
                existing_email_detail = session.query(ContactDetail).filter_by(type='email', value=str(email_value)).first()
                if existing_email_detail:
                    existing_contact = existing_email_detail.contact
            
            # If no phone/email, try by name (less reliable)
            if not existing_contact and pd.notna(first_name) and pd.notna(last_name):
                existing_contact = session.query(Contact).filter_by(first_name=first_name, last_name=last_name).first()


            if existing_contact:
                # Update existing contact (e.g., notes, contact_type if it's 'unknown')
                contact = existing_contact
                if contact.contact_type == 'unknown' or contact.contact_type is None:
                    contact.contact_type = contact_type
                if pd.notna(notes) and (contact.notes is None or notes not in contact.notes):
                    contact.notes = (contact.notes + "\n" + str(notes)).strip() if contact.notes else str(notes)
                
                # Add new phone/email details if they don't exist for this contact
                if pd.notna(phone_value):
                    if not session.query(ContactDetail).filter_by(contact_id=contact.id, type='phone', value=str(phone_value)).first():
                        session.add(ContactDetail(contact=contact, type='phone', value=str(phone_value), label='mobile', status='active'))
                if pd.notna(email_value):
                    if not session.query(ContactDetail).filter_by(contact_id=contact.id, type='email', value=str(email_value)).first():
                        session.add(ContactDetail(contact=contact, type='email', value=str(email_value), label='personal', status='active'))
                
                updated_count += 1
                print(f"Updated existing contact: {contact.first_name} {contact.last_name}")
            else:
                # Create new contact
                contact = Contact(
                    first_name=first_name,
                    last_name=last_name,
                    contact_type=contact_type,
                    contact_status='new_lead',
                    notes=str(notes) if pd.notna(notes) else None
                )
                session.add(contact)
                session.flush() # Get contact ID

                if pd.notna(phone_value):
                    session.add(ContactDetail(contact=contact, type='phone', value=str(phone_value), label='mobile', status='active'))
                if pd.notna(email_value):
                    session.add(ContactDetail(contact=contact, type='email', value=str(email_value), label='personal', status='active'))
                
                imported_count += 1
                print(f"Added new contact: {contact.first_name} {contact.last_name}")

            # Link contact to the CSV import source
            existing_contact_source = session.query(ContactSource).filter_by(
                contact_id=contact.id, source_type='CSV_Import', source_id=csv_source_log.id
            ).first()
            if not existing_contact_source:
                session.add(ContactSource(contact_id=contact.id, source_type='CSV_Import', source_id=csv_source_log.id))

        session.commit()
        summary_message = f"CSV import complete. Added: {imported_count}, Updated: {updated_count}, Skipped: {skipped_count}."
        return True, summary_message

    except Exception as e:
        session.rollback()
        return False, f"Error processing CSV: {e}"
    finally:
        session.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Import contacts from a CSV file.")
    parser.add_argument("file_path", type=str, help="Path to the CSV file.")
    parser.add_argument("--contact_type", type=str, default="unknown",
                        help="Type of contacts in the CSV (e.g., 'realtor', 'homeowner').")
    parser.add_argument("--description", type=str, default="Manual CSV Import",
                        help="A description for this import log.")
    args = parser.parse_args()

    # Ensure database is set up for standalone run
    setup_database()
    session = _Session_for_testing()

    success, message = import_contacts_from_csv(session, args.file_path, args.contact_type, args.description)
    print(message)
    session.close()
