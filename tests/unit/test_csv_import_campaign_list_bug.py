"""
Test cases for CSV import campaign list creation bug

This test module is designed to FAIL initially to prove that CSV imports
are not creating campaign lists in the database as expected.

CRITICAL BUG: CSV imports show success and a "View List" button,
but no campaign list is actually created in the database.
"""

import pytest
import tempfile
import csv
import io
from werkzeug.datastructures import FileStorage
from flask import Flask
from unittest.mock import Mock, patch

from services.csv_import_service import CSVImportService
from repositories.csv_import_repository import CSVImportRepository
from repositories.contact_csv_import_repository import ContactCSVImportRepository
from repositories.campaign_list_repository import CampaignListRepository
from repositories.campaign_list_member_repository import CampaignListMemberRepository
from repositories.contact_repository import ContactRepository
from services.contact_service_refactored import ContactService
from crm_database import CSVImport, CampaignList, Contact, CampaignListMember
from extensions import db


@pytest.fixture
def csv_import_service(app, db_session):
    """Create a CSV import service with all dependencies"""
    return CSVImportService(
        csv_import_repository=CSVImportRepository(db_session),
        contact_csv_import_repository=ContactCSVImportRepository(db_session),
        campaign_list_repository=CampaignListRepository(db_session),
        campaign_list_member_repository=CampaignListMemberRepository(db_session),
        contact_repository=ContactRepository(db_session),
        contact_service=ContactService(ContactRepository(db_session))
    )


@pytest.fixture
def sample_csv_file():
    """Create a sample CSV file for testing"""
    csv_data = """first_name,last_name,phone,email
John,Doe,+12345551234,john@example.com
Jane,Smith,+12345555678,jane@example.com
Bob,Johnson,+12345559999,bob@example.com"""
    
    # Create a temporary file-like object
    file_obj = io.StringIO(csv_data)
    file_storage = FileStorage(
        stream=io.BytesIO(csv_data.encode('utf-8')),
        filename='test_contacts.csv',
        content_type='text/csv'
    )
    return file_storage


class TestCSVImportCampaignListCreationBug:
    """Test cases that should initially FAIL to prove the bug exists"""
    
    def test_csv_import_creates_campaign_list_in_database(self, app, db_session, csv_import_service, sample_csv_file):
        """
        Test that CSV import actually creates a campaign list in the database.
        
        This test should FAIL initially because the bug prevents campaign lists
        from being created despite showing success.
        """
        with app.app_context():
            # Verify no campaign lists exist initially
            initial_count = db_session.query(CampaignList).count()
            assert initial_count == 0, "Database should start with no campaign lists"
            
            # Import CSV with list creation enabled
            list_name = "Test-Import-List"
            result = csv_import_service.import_contacts(
                file=sample_csv_file,
                list_name=list_name,
                create_list=True,  # This should create a list
                imported_by="test_user"
            )
            
            # Check that import was reported as successful
            assert result['successful'] > 0, f"Import should be successful, got: {result}"
            assert result.get('list_id') is not None, f"Import should return list_id, got: {result}"
            
            # CRITICAL TEST: Verify campaign list was actually created in database
            final_count = db_session.query(CampaignList).count()
            assert final_count == 1, f"Should have created 1 campaign list, found {final_count}"
            
            # Verify the list has the correct name and properties
            created_list = db_session.query(CampaignList).filter_by(name=list_name).first()
            assert created_list is not None, f"Campaign list '{list_name}' should exist in database"
            assert created_list.name == list_name
            
            # Verify the list_id in result matches the actual database ID
            assert result['list_id'] == created_list.id, f"Returned list_id {result['list_id']} should match database ID {created_list.id}"
    
    def test_csv_import_creates_list_members(self, app, db_session, csv_import_service, sample_csv_file):
        """
        Test that CSV import creates campaign list members.
        
        This test should FAIL initially if list creation is broken.
        """
        with app.app_context():
            # Import CSV with list creation
            list_name = "Test-Members-List"
            result = csv_import_service.import_contacts(
                file=sample_csv_file,
                list_name=list_name,
                create_list=True,
                imported_by="test_user"
            )
            
            # Verify import success
            assert result['successful'] > 0
            list_id = result.get('list_id')
            assert list_id is not None, "Import should return valid list_id"
            
            # CRITICAL TEST: Verify list members were created
            members_count = db_session.query(CampaignListMember).filter_by(list_id=list_id).count()
            expected_members = result['successful']  # Should match successful imports
            assert members_count == expected_members, f"Should have {expected_members} list members, found {members_count}"
            
            # Verify members link to correct contacts
            members = db_session.query(CampaignListMember).filter_by(list_id=list_id).all()
            for member in members:
                contact = db_session.query(Contact).get(member.contact_id)
                assert contact is not None, f"Member {member.id} should link to valid contact"
                assert contact.phone is not None, "Contact should have phone number"
    
    def test_async_csv_import_creates_campaign_list(self, app, db_session, csv_import_service):
        """
        Test that async CSV import (via Celery) creates campaign lists.
        
        This test should FAIL initially because async imports likely have the same bug.
        """
        with app.app_context():
            # Create larger CSV content to trigger async processing
            csv_content = "first_name,last_name,phone,email\n"
            for i in range(600):  # Large enough to trigger async
                csv_content += f"User{i},Test{i},+1234555{i:04d},user{i}@example.com\n"
            
            file_storage = FileStorage(
                stream=io.BytesIO(csv_content.encode('utf-8')),
                filename='large_test.csv',
                content_type='text/csv'
            )
            
            list_name = "Test-Async-List"
            
            # Mock the async task to run synchronously for testing
            with patch('services.csv_import_service.CSVImportService.create_async_import_task') as mock_async:
                # Make it fall back to sync processing
                mock_async.side_effect = Exception("Force sync fallback")
                
                result = csv_import_service.import_csv(
                    file=file_storage,
                    list_name=list_name
                )
                
                # Verify result shows success
                assert result.get('success', False), f"Import should be successful, got: {result}"
                assert result.get('list_id') is not None, f"Should return list_id, got: {result}"
                
                # CRITICAL TEST: Verify campaign list exists in database
                list_count = db_session.query(CampaignList).count()
                assert list_count == 1, f"Should have created 1 campaign list, found {list_count}"
                
                created_list = db_session.query(CampaignList).filter_by(name=list_name).first()
                assert created_list is not None, f"Campaign list '{list_name}' should exist"
    
    def test_view_list_button_links_to_valid_list(self, app, db_session, csv_import_service, sample_csv_file):
        """
        Test that the "View List" button links to a valid, existing campaign list.
        
        This test simulates the user flow where they see a "View List" button
        after import but get a 404 when clicking it.
        """
        with app.app_context():
            list_name = "Test-View-List"
            result = csv_import_service.import_contacts(
                file=sample_csv_file,
                list_name=list_name,
                create_list=True,
                imported_by="test_user"
            )
            
            # Import should report success and return list_id
            assert result['successful'] > 0
            list_id = result.get('list_id')
            assert list_id is not None, "Import should return list_id for View List button"
            
            # CRITICAL TEST: The list_id should correspond to an actual database record
            campaign_list = db_session.query(CampaignList).get(list_id)
            assert campaign_list is not None, f"Campaign list with ID {list_id} should exist (for View List button)"
            assert campaign_list.name == list_name
            
            # Simulate checking if the list has members (for the UI display)
            members_count = db_session.query(CampaignListMember).filter_by(list_id=list_id).count()
            assert members_count > 0, f"List {list_id} should have members for display"
    
    def test_import_metadata_includes_list_id(self, app, db_session, csv_import_service, sample_csv_file):
        """
        Test that CSV import metadata correctly includes the created list_id.
        
        This tests the linkage between CSVImport record and CampaignList.
        """
        with app.app_context():
            list_name = "Test-Metadata-List"
            result = csv_import_service.import_contacts(
                file=sample_csv_file,
                list_name=list_name,
                create_list=True,
                imported_by="test_user"
            )
            
            # Get the import record
            import_id = result.get('import_id')
            assert import_id is not None, "Import should return import_id"
            
            csv_import = db_session.query(CSVImport).get(import_id)
            assert csv_import is not None, "CSV import record should exist"
            
            # Check if list_id is stored in metadata or linked
            list_id = result.get('list_id')
            assert list_id is not None, "Result should include list_id"
            
            # CRITICAL TEST: Verify the list actually exists and can be found
            campaign_list = db_session.query(CampaignList).get(list_id)
            assert campaign_list is not None, f"Campaign list {list_id} should exist in database"
            
            # Check if the import metadata references the list
            if csv_import.import_metadata:
                # If stored in metadata, verify it matches
                if 'list_id' in csv_import.import_metadata:
                    assert csv_import.import_metadata['list_id'] == list_id
    
    def test_multiple_imports_create_separate_lists(self, app, db_session, csv_import_service):
        """
        Test that multiple CSV imports create separate campaign lists.
        """
        with app.app_context():
            # Create two different CSV files
            csv1_content = "first_name,last_name,phone\nJohn,Doe,+12345551111\nJane,Smith,+12345552222"
            csv2_content = "first_name,last_name,phone\nBob,Wilson,+12345553333\nAlice,Brown,+12345554444"
            
            file1 = FileStorage(
                stream=io.BytesIO(csv1_content.encode('utf-8')),
                filename='contacts1.csv',
                content_type='text/csv'
            )
            
            file2 = FileStorage(
                stream=io.BytesIO(csv2_content.encode('utf-8')),
                filename='contacts2.csv', 
                content_type='text/csv'
            )
            
            # Import first CSV
            result1 = csv_import_service.import_contacts(
                file=file1,
                list_name="First-Import-List",
                create_list=True,
                imported_by="test_user"
            )
            
            # Import second CSV  
            result2 = csv_import_service.import_contacts(
                file=file2,
                list_name="Second-Import-List", 
                create_list=True,
                imported_by="test_user"
            )
            
            # Both should be successful
            assert result1['successful'] > 0
            assert result2['successful'] > 0
            
            list_id1 = result1.get('list_id')
            list_id2 = result2.get('list_id')
            
            assert list_id1 is not None, "First import should create list"
            assert list_id2 is not None, "Second import should create list"
            assert list_id1 != list_id2, "Each import should create separate list"
            
            # CRITICAL TEST: Both lists should exist in database
            total_lists = db_session.query(CampaignList).count()
            assert total_lists == 2, f"Should have 2 campaign lists, found {total_lists}"
            
            list1 = db_session.query(CampaignList).get(list_id1)
            list2 = db_session.query(CampaignList).get(list_id2)
            
            assert list1 is not None, f"First list {list_id1} should exist"
            assert list2 is not None, f"Second list {list_id2} should exist"
            assert list1.name == "First-Import-List"
            assert list2.name == "Second-Import-List"


class TestCSVImportServiceInternalBug:
    """Tests to identify where in the service the bug occurs"""
    
    def test_campaign_list_repository_create_works(self, app, db_session):
        """
        Test that the campaign list repository can create lists properly.
        This isolates whether the bug is in the repository or service.
        """
        with app.app_context():
            repo = CampaignListRepository(db_session)
            
            # Create a list directly through repository
            created_list = repo.create(
                name="Direct-Repo-Test",
                description="Testing repository creation",
                created_by="test_user"
            )
            
            assert created_list is not None, "Repository should create list"
            assert created_list.id is not None, "Created list should have ID"
            
            # Verify it exists in database
            db_list = db_session.query(CampaignList).get(created_list.id)
            assert db_list is not None, "List should exist in database"
            assert db_list.name == "Direct-Repo-Test"
    
    def test_csv_import_service_create_list_parameter(self, app, db_session, csv_import_service, sample_csv_file):
        """
        Test different values of create_list parameter to see which ones work.
        """
        with app.app_context():
            test_cases = [
                (True, "Should create list when create_list=True"),
                (False, "Should NOT create list when create_list=False")
            ]
            
            list_count = 0
            for create_list, description in test_cases:
                result = csv_import_service.import_contacts(
                    file=sample_csv_file,
                    list_name=f"Test-Create-{create_list}",
                    create_list=create_list,
                    imported_by="test_user"
                )
                
                if create_list:
                    list_count += 1
                    assert result.get('list_id') is not None, f"{description} - should return list_id"
                    
                    # Check database
                    total_lists = db_session.query(CampaignList).count()
                    assert total_lists == list_count, f"{description} - database should have {list_count} lists"
                else:
                    assert result.get('list_id') is None, f"{description} - should not return list_id"
                
                # Reset file pointer for next test
                sample_csv_file.stream.seek(0)


class TestCSVImportRouteBug:
    """Test the route-level behavior to identify where the bug occurs"""
    
    def test_import_csv_route_creates_list(self, app, client):
        """
        Test the /campaigns/import-csv route creates lists properly.
        This tests the full route → service → repository flow.
        """
        with app.app_context():
            # Create test CSV data
            csv_data = "first_name,last_name,phone\nTest,User,+15551234567"
            
            # Simulate file upload via route
            response = client.post('/campaigns/import-csv', data={
                'csv_file': (io.BytesIO(csv_data.encode()), 'test.csv'),
                'list_name': 'Route-Test-List',
                'enrichment_mode': 'enrich_missing'
            }, content_type='multipart/form-data')
            
            # Should redirect to list detail or show success
            assert response.status_code in [200, 302], f"Route should succeed, got {response.status_code}"
            
            # Check if list was created in database
            from crm_database import CampaignList
            list_count = db.session.query(CampaignList).count()
            assert list_count == 1, f"Route import should create 1 campaign list, found {list_count}"
            
            created_list = db.session.query(CampaignList).filter_by(name='Route-Test-List').first()
            assert created_list is not None, "Route should create list with correct name"