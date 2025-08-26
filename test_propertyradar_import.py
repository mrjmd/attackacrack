#!/usr/bin/env python
"""
Quick test script to verify PropertyRadar CSV import functionality.
Run with: docker-compose exec web python test_propertyradar_import.py
"""

import sys
import os
from io import BytesIO
from werkzeug.datastructures import FileStorage

# Add app directory to path
sys.path.insert(0, '/app')

from app import create_app
from extensions import db
from services.propertyradar_import_service import PropertyRadarImportService
from services.csv_import_service import CSVImportService
from repositories.property_repository import PropertyRepository
from repositories.contact_repository import ContactRepository
from repositories.csv_import_repository import CSVImportRepository
from repositories.contact_csv_import_repository import ContactCSVImportRepository
from repositories.campaign_list_repository import CampaignListRepository
from repositories.campaign_list_member_repository import CampaignListMemberRepository
from services.contact_service_refactored import ContactService
from crm_database import Property, Contact, PropertyContact

def test_propertyradar_import():
    """Test importing PropertyRadar CSV with all fields"""
    
    # Create Flask app context
    app = create_app()
    
    with app.app_context():
        print("\n" + "="*60)
        print("PROPERTYRADAR CSV IMPORT TEST")
        print("="*60)
        
        # Initialize repositories
        property_repo = PropertyRepository(db.session)
        contact_repo = ContactRepository(db.session)
        csv_import_repo = CSVImportRepository(db.session)
        contact_csv_import_repo = ContactCSVImportRepository(db.session)
        campaign_list_repo = CampaignListRepository(db.session)
        campaign_list_member_repo = CampaignListMemberRepository(db.session)
        
        # Initialize contact service (check what parameters it actually needs)
        try:
            # Try with just the contact repository
            contact_service = ContactService(contact_repo)
        except Exception as e:
            print(f"Note: ContactService initialization: {e}")
            # Try alternative initialization
            contact_service = None
        
        # Initialize CSV import service
        csv_service = CSVImportService(
            csv_import_repository=csv_import_repo,
            contact_csv_import_repository=contact_csv_import_repo,
            campaign_list_repository=campaign_list_repo,
            campaign_list_member_repository=campaign_list_member_repo,
            contact_repository=contact_repo,
            contact_service=contact_service
        )
        
        # Read the CSV file
        csv_path = '/app/csvs/short-csv.csv'
        if not os.path.exists(csv_path):
            print(f"❌ CSV file not found: {csv_path}")
            print("Please copy the file with: docker cp csvs/short-csv.csv crm_web_app:/app/csvs/short-csv.csv")
            return False
        
        print(f"✅ Found CSV file: {csv_path}")
        
        # Create FileStorage object from CSV content
        with open(csv_path, 'rb') as f:
            csv_content = f.read()
        
        file_storage = FileStorage(
            stream=BytesIO(csv_content),
            filename='short-csv.csv',
            content_type='text/csv'
        )
        
        # Count initial records
        initial_properties = db.session.query(Property).count()
        initial_contacts = db.session.query(Contact).count()
        initial_associations = db.session.query(PropertyContact).count()
        
        print(f"\nInitial counts:")
        print(f"  Properties: {initial_properties}")
        print(f"  Contacts: {initial_contacts}")
        print(f"  Associations: {initial_associations}")
        
        # Import the CSV using the CSV service (which should delegate to PropertyRadar)
        print("\n📥 Importing CSV...")
        result = csv_service.import_csv(file_storage, list_name="PropertyRadar Test Import")
        
        # Check results
        if result['success']:
            print(f"✅ Import successful!")
            print(f"  Imported: {result['imported']}")
            print(f"  Updated: {result['updated']}")
            print(f"  List ID: {result['list_id']}")
            print(f"  Message: {result['message']}")
        else:
            print(f"❌ Import failed!")
            print(f"  Message: {result['message']}")
            print(f"  Errors: {result['errors'][:5]}")  # Show first 5 errors
            return False
        
        # Count final records
        final_properties = db.session.query(Property).count()
        final_contacts = db.session.query(Contact).count()
        final_associations = db.session.query(PropertyContact).count()
        
        print(f"\nFinal counts:")
        print(f"  Properties: {final_properties} (+{final_properties - initial_properties})")
        print(f"  Contacts: {final_contacts} (+{final_contacts - initial_contacts})")
        print(f"  Associations: {final_associations} (+{final_associations - initial_associations})")
        
        # Verify some specific data
        print("\n🔍 Verifying imported data...")
        
        # Check first property
        first_property = db.session.query(Property).filter_by(
            address='455 MIDDLE ST',
            zip_code='02184'
        ).first()
        
        if first_property:
            print(f"\n✅ Found property: {first_property.address}")
            print(f"  City: {first_property.city}")
            print(f"  ZIP: {first_property.zip_code}")
            print(f"  Type: {first_property.property_type}")
            print(f"  Year Built: {first_property.year_built}")
            print(f"  Square Feet: {first_property.square_feet}")
            print(f"  Bedrooms: {first_property.bedrooms}")
            print(f"  Bathrooms: {first_property.bathrooms}")
            print(f"  Est Value: ${first_property.estimated_value:,.0f}" if first_property.estimated_value else "  Est Value: N/A")
            print(f"  Est Equity: ${first_property.estimated_equity:,.0f}" if first_property.estimated_equity else "  Est Equity: N/A")
            print(f"  Owner Occupied: {first_property.owner_occupied}")
            print(f"  APN: {first_property.apn}")
            
            # Check associated contacts
            associations = db.session.query(PropertyContact).filter_by(property_id=first_property.id).all()
            print(f"\n  Associated Contacts: {len(associations)}")
            
            for assoc in associations:
                contact = db.session.query(Contact).get(assoc.contact_id)
                if contact:
                    print(f"    - {contact.first_name} {contact.last_name}")
                    print(f"      Phone: {contact.phone}")
                    print(f"      Email: {contact.email}")
                    print(f"      Primary: {assoc.is_primary}")
        else:
            print("❌ Could not find first property (455 MIDDLE ST)")
            
        # Check for dual contacts (property with both primary and secondary)
        print("\n🔍 Checking dual contact import...")
        property_with_dual = db.session.query(Property).filter_by(
            address='455 MIDDLE ST'  # This row has both JON and AIMEE
        ).first()
        
        if property_with_dual:
            assocs = db.session.query(PropertyContact).filter_by(
                property_id=property_with_dual.id
            ).all()
            
            if len(assocs) >= 2:
                print(f"✅ Found property with {len(assocs)} contacts")
                for assoc in assocs:
                    contact = db.session.query(Contact).get(assoc.contact_id)
                    if contact:
                        print(f"  - {contact.first_name} {contact.last_name} (Primary: {assoc.is_primary})")
            else:
                print(f"⚠️ Property has only {len(assocs)} contact(s), expected 2")
        
        print("\n" + "="*60)
        print("TEST COMPLETE")
        print("="*60)
        
        return True

if __name__ == '__main__':
    success = test_propertyradar_import()
    sys.exit(0 if success else 1)