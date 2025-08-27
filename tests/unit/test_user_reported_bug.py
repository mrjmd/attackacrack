"""
Test to reproduce the exact user-reported bug

User reported:
1. User imports CSV with name "Test-List-2" 
2. Import shows success: 1788 imported, 1729 updated
3. "View List" button appears
4. Clicking button gives 404 because NO list was created
5. Database query shows only 2 lists exist (ID 7, 8) - no new lists created
6. CSV imports show "List: N/A" in database

The issue is likely that the async task doesn't return list_id properly to the UI,
OR the UI shows "View List" prematurely before the task creates the list.
"""

import pytest
import io
from unittest.mock import patch, MagicMock
from werkzeug.datastructures import FileStorage

from app import create_app
from crm_database import CampaignList, CSVImport, Contact, CampaignListMember
from extensions import db


def test_user_reported_async_scenario():
    """
    Reproduce the exact scenario reported by the user.
    The bug is that UI shows "View List" button from async response,
    but no list_id is available because async task hasn't completed yet.
    """
    app = create_app()
    
    with app.test_client() as client:
        with app.app_context():
            # Clear existing data to match user's scenario
            db.session.query(CampaignListMember).delete()
            db.session.query(CampaignList).delete()
            db.session.query(Contact).delete()  
            db.session.query(CSVImport).delete()
            db.session.commit()
            
            # Recreate the existing lists that user mentioned (ID 7, 8)
            existing_list1 = CampaignList(id=7, name="VIP Customers", description="Existing list 1")
            existing_list2 = CampaignList(id=8, name="New Leads", description="Existing list 2")
            db.session.add(existing_list1)
            db.session.add(existing_list2)
            db.session.commit()
            
            # Create CSV that would match user's reported numbers (1788 imported, 1729 updated)
            csv_content = "first_name,last_name,phone,email\n"
            
            # First, create existing contacts that would be "updated" (1729)
            for i in range(1729):
                phone = f"+1555000{i:04d}"
                existing_contact = Contact(
                    first_name=f"Existing{i}",
                    last_name="User", 
                    phone=phone,
                    email=f"existing{i}@example.com"
                )
                db.session.add(existing_contact)
                # Add these to CSV as updated records
                csv_content += f"Updated{i},User,{phone},updated{i}@example.com\n"
            
            # Add new contacts that would be "imported" (59 new = 1788 total - 1729 existing) 
            for i in range(59):
                phone = f"+1555999{i:03d}"
                csv_content += f"New{i},User,{phone},new{i}@example.com\n"
            
            db.session.commit()
            
            print(f"Setup: {Contact.query.count()} existing contacts, {CampaignList.query.count()} existing lists")
            
            # Submit the CSV import via the route (exactly like the user did)
            response = client.post('/campaigns/import-csv', data={
                'csv_file': (io.BytesIO(csv_content.encode()), 'Test-List-2.csv'),
                'list_name': 'Test-List-2',
                'enrichment_mode': 'enrich_missing'
            }, content_type='multipart/form-data')
            
            print(f"Route response status: {response.status_code}")
            
            # Check immediate database state (what user would see right after upload)
            immediate_list_count = db.session.query(CampaignList).count()
            
            print(f"Lists immediately after upload: {immediate_list_count}")
            
            # This reproduces the bug: User sees "success" but no new list is created
            if immediate_list_count == 2:  # Still only the original 2 lists
                print("BUG REPRODUCED: CSV upload doesn't create campaign list immediately")
                
                # Check if response redirected to an import progress page
                if response.status_code == 302:
                    location = response.headers.get('Location', '')
                    print(f"Redirected to: {location}")
                    
                    # If redirected to progress page, the UI might show "View List" 
                    # even though no list exists yet
                    if 'import-progress' in location or 'import-status' in location:
                        print("BUG: User redirected to progress page with potential 'View List' button")
                        print("But no list_id exists because async task hasn't completed")
                        
                        # This is exactly what the user experienced:
                        # 1. Upload CSV → gets progress page 
                        # 2. Progress page shows "View List" button
                        # 3. Button uses non-existent list_id → 404
                        
                        pytest.fail("BUG CONFIRMED: Async upload shows 'View List' but no list created")
            
            # If we get here, a list was created immediately (bug not reproduced)
            new_lists = db.session.query(CampaignList).filter(CampaignList.id > 8).all()
            if len(new_lists) > 0:
                print(f"SUCCESS: List created immediately: {new_lists[0].name}")
            else:
                pytest.fail("Expected either bug reproduction or immediate list creation")


def test_async_ui_flow_bug():
    """
    Test the specific UI flow bug where async tasks show "View List" prematurely
    """
    app = create_app()
    with app.app_context():
        # Clear data
        db.session.query(CampaignListMember).delete()
        db.session.query(CampaignList).delete()
        db.session.query(Contact).delete()
        db.session.query(CSVImport).delete()
        db.session.commit()
        
        # Create large CSV that triggers async processing
        csv_content = "first_name,last_name,phone\n"
        for i in range(600):  # Large enough to trigger async
            csv_content += f"User{i},Test,+1234567{i:04d}\n"
        
        csv_service = app.services.get('csv_import')
        file_storage = FileStorage(
            stream=io.BytesIO(csv_content.encode('utf-8')),
            filename='large-async-test.csv',
            content_type='text/csv'
        )
        
        list_name = "Async-UI-Test"
        
        # Call import_csv (like the route does)
        result = csv_service.import_csv(file=file_storage, list_name=list_name)
        
        print(f"Async import result: {result}")
        
        # Check if this is an async result
        if result.get('async'):
            task_id = result.get('task_id')
            print(f"Task ID: {task_id}")
            
            # The BUG: UI would show "View List" button based on task_id
            # But list_id is not available in the async response
            list_id = result.get('list_id')
            
            if list_id is None:
                # This is the bug: No list_id provided for "View List" button
                print("BUG: Async response doesn't include list_id")
                
                # Check if any list was created immediately
                list_count = db.session.query(CampaignList).count()
                if list_count == 0:
                    pytest.fail("CRITICAL BUG: Async import provides no list_id and creates no list immediately")
                else:
                    print(f"List was created immediately despite async response: {list_count} lists")
            else:
                print(f"List ID provided in async response: {list_id}")
                # Verify this list actually exists
                created_list = db.session.query(CampaignList).get(list_id)
                if not created_list:
                    pytest.fail(f"BUG: Async response claims list_id {list_id} but list doesn't exist")
        else:
            # Sync processing - should have list_id
            list_id = result.get('list_id')
            if list_id is None:
                pytest.fail("BUG: Sync processing didn't return list_id")


def test_csv_import_metadata_bug():
    """
    Test the metadata issue where CSV imports show "List: N/A" 
    """
    app = create_app()
    with app.app_context():
        # Clear data
        db.session.query(CampaignListMember).delete()
        db.session.query(CampaignList).delete()
        db.session.query(Contact).delete()
        db.session.query(CSVImport).delete()
        db.session.commit()
        
        csv_content = "first_name,last_name,phone\nMeta,Test,+15551234567"
        list_name = "Metadata-Test"
        
        csv_service = app.services.get('csv_import')
        file_storage = FileStorage(
            stream=io.BytesIO(csv_content.encode('utf-8')),
            filename='metadata-test.csv',
            content_type='text/csv'
        )
        
        result = csv_service.import_csv(file=file_storage, list_name=list_name)
        
        print(f"Import result: {result}")
        
        # Check the CSV import record metadata
        import_id = result.get('import_id')
        if import_id:
            csv_import = db.session.query(CSVImport).get(import_id)
            if csv_import:
                print(f"CSV import metadata: {csv_import.import_metadata}")
                
                # Check if list_id is stored in metadata
                if csv_import.import_metadata is None:
                    print("BUG: CSV import metadata is None - this causes 'List: N/A' display")
                    
                    # This might be the bug - metadata should include list info
                    list_id = result.get('list_id')
                    if list_id:
                        print(f"List {list_id} was created but not stored in CSV import metadata")
                        pytest.fail("BUG: List created but not linked in CSV import metadata")
                else:
                    print(f"Metadata contains: {csv_import.import_metadata}")
                    
                    # Check if list_id is in the metadata
                    meta_list_id = csv_import.import_metadata.get('list_id')
                    result_list_id = result.get('list_id')
                    
                    if meta_list_id != result_list_id:
                        pytest.fail(f"BUG: Metadata list_id {meta_list_id} doesn't match result list_id {result_list_id}")


if __name__ == '__main__':
    test_user_reported_async_scenario()