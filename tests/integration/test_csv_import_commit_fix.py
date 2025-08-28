"""
Integration test to verify CSV import commits CampaignListMember records properly.

This test addresses the critical bug where imports show "X imported" but fewer 
contacts appear in lists due to missing database commits.
"""

import pytest
from io import BytesIO
from werkzeug.datastructures import FileStorage
from app import create_app
from extensions import db
from crm_database import Contact, CampaignList, CampaignListMember, CSVImport
from utils.datetime_utils import utc_now


class TestCSVImportCommitFix:
    """Integration test for CSV import list member commit fix."""
    
    @pytest.fixture
    def app(self):
        """Create test app."""
        app = create_app('testing')
        with app.app_context():
            db.create_all()
            yield app
            db.session.remove()
            db.drop_all()
    
    @pytest.fixture
    def client(self, app):
        """Create test client."""
        return app.test_client()
    
    @pytest.fixture
    def csv_import_service(self, app):
        """Get CSV import service from app."""
        with app.app_context():
            return app.services.get('csv_import')
    
    def test_csv_import_commits_all_list_members(self, app, csv_import_service):
        """Test that ALL imported contacts are added to campaign list members."""
        
        with app.app_context():
            # Create CSV data with 150 contacts to test periodic commits
            csv_data = "first_name,last_name,phone,email\n"
            for i in range(150):
                # Use unique phone numbers
                csv_data += f"Test{i},User{i},+1555{i:07d},test{i}@example.com\n"
            
            # Create file-like object
            csv_file = FileStorage(
                stream=BytesIO(csv_data.encode()),
                filename="test_commit_fix.csv",
                content_type="text/csv"
            )
            
            # Import the CSV with list creation
            result = csv_import_service.import_contacts(
                file=csv_file,
                list_name="Test Import List",
                create_list=True,
                imported_by="test_user",
                duplicate_strategy='merge'
            )
            
            # Check import results
            assert result['successful'] == 150, f"Expected 150 successful imports, got {result['successful']}"
            assert result['list_id'] is not None, "List should have been created"
            
            # CRITICAL: Verify all contacts are in the campaign list
            list_id = result['list_id']
            
            # Count actual campaign list members
            member_count = CampaignListMember.query.filter_by(
                list_id=list_id,
                status='active'
            ).count()
            
            assert member_count == 150, \
                f"Expected 150 list members, but only {member_count} were committed to database"
            
            # Verify the list stats are correct
            campaign_list = CampaignList.query.get(list_id)
            assert campaign_list is not None, "Campaign list should exist"
            assert campaign_list.name == "Test Import List"
            
            # Verify all contacts exist
            contacts_in_list = db.session.query(Contact).join(
                CampaignListMember,
                Contact.id == CampaignListMember.contact_id
            ).filter(
                CampaignListMember.list_id == list_id
            ).count()
            
            assert contacts_in_list == 150, \
                f"Expected 150 contacts in list, found {contacts_in_list}"
    
    def test_duplicate_contacts_added_to_list(self, app, csv_import_service):
        """Test that duplicate/existing contacts are still added to new lists."""
        
        with app.app_context():
            # First, create some existing contacts
            existing_contacts = []
            for i in range(20):
                contact = Contact(
                    first_name=f"Existing{i}",
                    last_name=f"User{i}",
                    phone=f"+1555000{i:04d}",
                    email=f"existing{i}@example.com"
                )
                db.session.add(contact)
                existing_contacts.append(contact)
            db.session.commit()
            
            # Now import a CSV with the same phone numbers
            csv_data = "first_name,last_name,phone,email\n"
            for i in range(20):
                # Use same phone numbers as existing contacts
                csv_data += f"Updated{i},Name{i},+1555000{i:04d},new{i}@example.com\n"
            
            csv_file = FileStorage(
                stream=BytesIO(csv_data.encode()),
                filename="test_duplicates.csv",
                content_type="text/csv"
            )
            
            # Import with merge strategy
            result = csv_import_service.import_contacts(
                file=csv_file,
                list_name="Duplicate Test List",
                create_list=True,
                imported_by="test_user",
                duplicate_strategy='merge'
            )
            
            # Check results
            assert result['successful'] == 20, f"Expected 20 successful, got {result['successful']}"
            assert result['duplicates'] == 20, f"Expected 20 duplicates, got {result['duplicates']}"
            assert result['list_id'] is not None
            
            # CRITICAL: Verify duplicate contacts were added to the list
            list_id = result['list_id']
            member_count = CampaignListMember.query.filter_by(
                list_id=list_id,
                status='active'
            ).count()
            
            assert member_count == 20, \
                f"Expected 20 duplicate contacts in list, but only {member_count} were added"
            
            # Verify the existing contacts were enriched (merge strategy)
            for i, contact in enumerate(existing_contacts):
                db.session.refresh(contact)
                # First name should be updated if it was missing or invalid
                if contact.first_name in [None, '', f'+1555000{i:04d}']:
                    assert contact.first_name == f"Updated{i}", \
                        f"Contact {i} first name should have been updated"
    
    def test_large_import_commits_properly(self, app, csv_import_service):
        """Test that large imports with multiple commit batches work correctly."""
        
        with app.app_context():
            # Create CSV with 350 contacts (triggers multiple 100-record commits)
            csv_data = "first_name,last_name,phone,email\n"
            for i in range(350):
                csv_data += f"Large{i},Import{i},+1556{i:07d},large{i}@example.com\n"
            
            csv_file = FileStorage(
                stream=BytesIO(csv_data.encode()),
                filename="test_large_import.csv",
                content_type="text/csv"
            )
            
            # Import the large CSV
            result = csv_import_service.import_contacts(
                file=csv_file,
                list_name="Large Import List",
                create_list=True,
                imported_by="test_user"
            )
            
            # Verify all contacts were imported
            assert result['successful'] == 350, \
                f"Expected 350 successful imports, got {result['successful']}"
            
            # CRITICAL: Verify ALL contacts are in the list (not just first 100)
            list_id = result['list_id']
            member_count = CampaignListMember.query.filter_by(
                list_id=list_id,
                status='active'
            ).count()
            
            assert member_count == 350, \
                f"Large import failed: Expected 350 members, only {member_count} committed"
            
            # Verify contacts were actually created
            created_contacts = Contact.query.filter(
                Contact.phone.like('+1556%')
            ).count()
            
            assert created_contacts == 350, \
                f"Expected 350 contacts created, found {created_contacts}"