"""
Test CSV import with real scenario to find the exact bug

This test simulates exactly what happens in production to identify
where the campaign list creation fails.
"""

import pytest
import io
import tempfile
import os
from werkzeug.datastructures import FileStorage

from app import create_app
from crm_database import CampaignList, CSVImport, Contact, CampaignListMember
from extensions import db


def test_real_csv_import_scenario():
    """
    Test the exact scenario that happens in production where:
    1. User uploads CSV with name "Test-List-2"
    2. Import shows success: 1788 imported, 1729 updated  
    3. "View List" button appears
    4. Clicking button gives 404 because NO list was created
    5. Database query shows no new lists created
    """
    app = create_app()
    with app.app_context():
        # Clear existing data to start fresh
        db.session.query(CampaignListMember).delete()
        db.session.query(CampaignList).delete()
        db.session.query(Contact).delete()  
        db.session.query(CSVImport).delete()
        db.session.commit()
        
        # Create a CSV that would result in many imports and updates (like the real scenario)
        csv_content = "first_name,last_name,phone,email\n"
        
        # Create some existing contacts (to trigger updates)
        existing_phones = []
        for i in range(1729):  # Number that would be "updated"
            phone = f"+1234555{i:04d}"
            existing_phones.append(phone)
            contact = Contact(
                first_name=f"Existing{i}",
                last_name="User",
                phone=phone,
                email=f"existing{i}@example.com"
            )
            db.session.add(contact)
            csv_content += f"Updated{i},User,{phone},updated{i}@example.com\n"
        
        # Create new contacts (to trigger imports)  
        for i in range(1788 - 1729):  # Additional new contacts
            phone = f"+1234556{i:04d}"
            csv_content += f"New{i},User,{phone},new{i}@example.com\n"
        
        db.session.commit()
        
        print(f"Created {len(existing_phones)} existing contacts")
        line_count = csv_content.count('\n')
        print(f"CSV content has {line_count} lines")
        
        # Get the CSV import service
        csv_service = app.services.get('csv_import')
        if not csv_service:
            pytest.fail("CSV service not available")
        
        # Create file storage object
        file_storage = FileStorage(
            stream=io.BytesIO(csv_content.encode('utf-8')),
            filename='Test-List-2.csv',  # Exact filename from user report
            content_type='text/csv'
        )
        
        # Check initial state
        initial_list_count = db.session.query(CampaignList).count()
        initial_import_count = db.session.query(CSVImport).count()
        
        print(f"Initial lists: {initial_list_count}, imports: {initial_import_count}")
        
        # Import the CSV using the same method as the route
        list_name = "Test-List-2"  # Exact name from user report
        result = csv_service.import_csv(
            file=file_storage,
            list_name=list_name
        )
        
        print(f"Import result: {result}")
        
        # Check what actually happened
        final_list_count = db.session.query(CampaignList).count()
        final_import_count = db.session.query(CSVImport).count()
        
        print(f"Final lists: {final_list_count}, imports: {final_import_count}")
        
        # Handle both sync and async responses
        is_async = result.get('async', False)
        is_success = result.get('success', False)
        
        # For async processing, success means the list was created and task queued
        if is_async:
            assert result.get('status') == 'queued', f"Async import should be queued, got: {result}"
            assert result.get('task_id'), f"Async import should have task_id, got: {result}"
            imported = 0  # Async doesn't report these immediately
            updated = 0
            print(f"Async processing: task_id={result.get('task_id')}, list_id={result.get('list_id')}")
        else:
            # Sync processing
            assert is_success, f"Sync import should succeed, got: {result}"
            imported = result.get('imported', 0)
            updated = result.get('updated', 0)
            print(f"Sync processing: {imported} imported, {updated} updated")
        
        # The key test: was a list actually created?
        if final_list_count == initial_list_count:
            # BUG CONFIRMED: Import succeeded but no list created
            list_id = result.get('list_id')
            if is_async:
                pytest.fail(f"BUG CONFIRMED: Async import queued but no campaign list was created. list_id returned: {list_id}")
            else:
                pytest.fail(f"BUG CONFIRMED: Import succeeded ({imported} imported, {updated} updated) but no campaign list was created. list_id returned: {list_id}")
        
        # If we get here, a list was created (bug not reproduced)
        created_lists = db.session.query(CampaignList).filter_by(name=list_name).all()
        print(f"Created lists with name '{list_name}': {len(created_lists)}")
        
        if len(created_lists) == 0:
            pytest.fail(f"No list created with name '{list_name}' even though total list count increased")
        
        created_list = created_lists[0]
        returned_list_id = result.get('list_id')
        
        if returned_list_id != created_list.id:
            pytest.fail(f"Returned list_id {returned_list_id} doesn't match created list ID {created_list.id}")
        
        # Check if list has members
        members_count = db.session.query(CampaignListMember).filter_by(list_id=created_list.id).count()
        expected_members = imported + updated
        
        if members_count != expected_members:
            pytest.fail(f"List should have {expected_members} members, found {members_count}")
        
        print(f"SUCCESS: List created with ID {created_list.id} and {members_count} members")


def test_async_csv_import_real_scenario():
    """
    Test the async scenario that might be causing the bug.
    Large files go through Celery tasks which might lose the list creation.
    """
    app = create_app()
    with app.app_context():
        # Clear existing data
        db.session.query(CampaignListMember).delete()
        db.session.query(CampaignList).delete()
        db.session.query(Contact).delete()
        db.session.query(CSVImport).delete()
        db.session.commit()
        
        # Create a large CSV that would trigger async processing
        csv_content = "first_name,last_name,phone,email\n"
        for i in range(600):  # Large enough to trigger async
            csv_content += f"User{i},Test,+1234567{i:04d},user{i}@example.com\n"
        
        csv_service = app.services.get('csv_import')
        file_storage = FileStorage(
            stream=io.BytesIO(csv_content.encode('utf-8')),
            filename='Large-Test-List.csv',
            content_type='text/csv'
        )
        
        list_name = "Large-Test-List"
        
        # This should trigger async processing
        result = csv_service.import_csv(
            file=file_storage,
            list_name=list_name
        )
        
        print(f"Async import result: {result}")
        
        # Check if async result includes list_id
        if result.get('async'):
            # Async processing - the bug might be here
            task_id = result.get('task_id')
            print(f"Async task ID: {task_id}")
            
            # The issue is that async tasks might not return list_id properly
            # and the UI shows "View List" based on task completion, not actual list creation
            if 'list_id' not in result:
                print("POTENTIAL BUG: Async task doesn't provide list_id immediately")
        else:
            # Sync processing - check if list was created
            list_count = db.session.query(CampaignList).count()
            if list_count == 0:
                pytest.fail(f"Sync processing failed to create list. Result: {result}")
            
            list_id = result.get('list_id')
            if list_id is None:
                pytest.fail(f"Sync processing didn't return list_id. Result: {result}")


def test_form_data_handling_scenario():
    """
    Test the exact form data handling that might cause the bug.
    This simulates the form submission from the UI.
    """
    app = create_app()
    
    with app.test_client() as client:
        with app.app_context():
            # Clear existing data
            db.session.query(CampaignListMember).delete()
            db.session.query(CampaignList).delete()
            db.session.query(Contact).delete()
            db.session.query(CSVImport).delete()
            db.session.commit()
            
            # Create CSV data
            csv_data = "first_name,last_name,phone\n"
            for i in range(10):
                csv_data += f"User{i},Test,+1234567{i:03d}\n"
            
            # Simulate the exact form submission
            response = client.post('/campaigns/import-csv', data={
                'csv_file': (io.BytesIO(csv_data.encode()), 'form-test.csv'),
                'list_name': 'Form-Test-List',  # Explicit list name
                'enrichment_mode': 'enrich_missing'
            }, content_type='multipart/form-data')
            
            print(f"Form response status: {response.status_code}")
            
            # Check if list was created
            list_count = db.session.query(CampaignList).count()
            if list_count == 0:
                # Get response data to see what happened
                if response.status_code == 302:
                    location = response.headers.get('Location', '')
                    print(f"Redirect location: {location}")
                else:
                    print(f"Response data: {response.get_data(as_text=True)}")
                
                pytest.fail("Form submission failed to create campaign list")
            
            created_list = db.session.query(CampaignList).filter_by(name='Form-Test-List').first()
            if not created_list:
                pytest.fail("List created but with wrong name")
            
            # Check redirect behavior
            if response.status_code == 302:
                location = response.headers.get('Location', '')
                expected_location = f'/campaigns/lists/{created_list.id}'
                if expected_location not in location:
                    print(f"Redirect location: {location}, expected to contain: {expected_location}")
                    # This might be where the bug is - wrong redirect after import


if __name__ == '__main__':
    # Run the real scenario test
    test_real_csv_import_scenario()