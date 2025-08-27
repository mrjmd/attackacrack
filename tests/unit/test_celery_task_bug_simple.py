"""
Simple test to identify the Celery task bug by reproducing its logic
"""

import pytest
import io
from unittest.mock import MagicMock
from werkzeug.datastructures import FileStorage

from app import create_app
from crm_database import CampaignList, Contact, CSVImport, CampaignListMember
from extensions import db


def test_celery_task_logic_simulation():
    """
    Simulate what the Celery task does to find where campaign list creation fails
    """
    app = create_app()
    with app.app_context():
        # Clear data
        db.session.query(CampaignListMember).delete()
        db.session.query(CampaignList).delete()
        db.session.query(Contact).delete()
        db.session.query(CSVImport).delete()
        db.session.commit()
        
        # Simulate exactly what the Celery task does
        csv_content = """first_name,last_name,phone
John,Doe,+15551234567
Jane,Smith,+15559876543"""
        
        list_name = "Task-Simulation-Test"
        filename = "simulation-test.csv"
        
        # Step 1: Get CSV import service (like the task does)
        csv_import_service = app.services.get('csv_import')
        assert csv_import_service is not None, "CSV service should be available"
        
        # Step 2: Create file-like object (like the task does)
        file_stream = io.BytesIO(csv_content.encode('utf-8'))
        mock_file = FileStorage(stream=file_stream, filename=filename)
        
        # Step 3: Call _process_sync_with_fallback (like the task does)
        result = csv_import_service._process_sync_with_fallback(
            file=mock_file,
            list_name=list_name
        )
        
        print(f"Task simulation result: {result}")
        
        # Check if list was created
        list_count = db.session.query(CampaignList).count()
        print(f"Lists after simulation: {list_count}")
        
        if list_count == 0:
            pytest.fail(f"CRITICAL BUG: _process_sync_with_fallback doesn't create campaign list. Result: {result}")
        
        # Check if result includes list_id
        if result.get('list_id') is None:
            pytest.fail(f"BUG: _process_sync_with_fallback doesn't return list_id. Result: {result}")
        
        # Verify list exists and has correct name
        list_id = result['list_id']
        created_list = db.session.query(CampaignList).get(list_id)
        
        if not created_list:
            pytest.fail(f"BUG: list_id {list_id} returned but list doesn't exist in database")
        
        if created_list.name != list_name:
            pytest.fail(f"BUG: List name is '{created_list.name}', expected '{list_name}'")
        
        print("SUCCESS: Task simulation creates campaign list correctly")


def test_basic_import_csv_method():
    """
    Test the _basic_import_csv method specifically since that's what _process_sync_with_fallback calls
    """
    app = create_app()
    with app.app_context():
        # Clear data
        db.session.query(CampaignListMember).delete()
        db.session.query(CampaignList).delete()
        db.session.query(Contact).delete()
        db.session.query(CSVImport).delete()
        db.session.commit()
        
        csv_content = "first_name,last_name,phone\nTest,User,+15551234567"
        list_name = "Basic-Import-Test"
        
        csv_service = app.services.get('csv_import')
        
        file_storage = FileStorage(
            stream=io.BytesIO(csv_content.encode('utf-8')),
            filename='basic-test.csv',
            content_type='text/csv'
        )
        
        # Call _basic_import_csv directly
        result = csv_service._basic_import_csv(
            file=file_storage,
            list_name=list_name
        )
        
        print(f"_basic_import_csv result: {result}")
        
        # This method calls import_contacts with create_list=True by default
        list_count = db.session.query(CampaignList).count()
        
        if list_count == 0:
            pytest.fail(f"BUG: _basic_import_csv doesn't create campaign list. Result: {result}")
        
        if result.get('list_id') is None:
            pytest.fail(f"BUG: _basic_import_csv doesn't return list_id. Result: {result}")
        
        print("SUCCESS: _basic_import_csv creates campaign list")


def test_import_contacts_with_explicit_create_list():
    """
    Test import_contacts method with explicit create_list=True to confirm it works
    """
    app = create_app()
    with app.app_context():
        # Clear data
        db.session.query(CampaignListMember).delete()
        db.session.query(CampaignList).delete()
        db.session.query(Contact).delete()
        db.session.query(CSVImport).delete()
        db.session.commit()
        
        csv_content = "first_name,last_name,phone\nExplicit,Test,+15559876543"
        list_name = "Explicit-Create-Test"
        
        csv_service = app.services.get('csv_import')
        
        file_storage = FileStorage(
            stream=io.BytesIO(csv_content.encode('utf-8')),
            filename='explicit-test.csv',
            content_type='text/csv'
        )
        
        # Call import_contacts with explicit create_list=True
        result = csv_service.import_contacts(
            file=file_storage,
            list_name=list_name,
            create_list=True,  # Explicit
            imported_by="test_user"
        )
        
        print(f"import_contacts result: {result}")
        
        # This should definitely create a list
        list_count = db.session.query(CampaignList).count()
        
        if list_count == 0:
            pytest.fail(f"CRITICAL BUG: import_contacts with create_list=True doesn't create list. Result: {result}")
        
        if result.get('list_id') is None:
            pytest.fail(f"BUG: import_contacts doesn't return list_id. Result: {result}")
        
        created_list = db.session.query(CampaignList).filter_by(name=list_name).first()
        if not created_list:
            pytest.fail(f"List created but not with expected name '{list_name}'")
        
        # Check list has members
        members_count = db.session.query(CampaignListMember).filter_by(list_id=created_list.id).count()
        if members_count == 0:
            pytest.fail("List created but has no members")
        
        print("SUCCESS: import_contacts with create_list=True works correctly")


def test_parameter_flow_in_methods():
    """
    Test how the list_name parameter flows through the method chain to find where it gets lost
    """
    app = create_app()
    with app.app_context():
        # Clear data
        db.session.query(CampaignListMember).delete()
        db.session.query(CampaignList).delete()
        db.session.query(Contact).delete()
        db.session.query(CSVImport).delete()
        db.session.commit()
        
        csv_content = "first_name,last_name,phone\nParam,Test,+15551111111"
        list_name = "Parameter-Flow-Test"
        
        csv_service = app.services.get('csv_import')
        
        file_storage = FileStorage(
            stream=io.BytesIO(csv_content.encode('utf-8')),
            filename='param-test.csv',
            content_type='text/csv'
        )
        
        # Test the chain: import_csv -> _process_sync_with_fallback -> _basic_import_csv -> import_contacts
        
        # 1. Start with import_csv (route-level method)
        print(f"Step 1: Calling import_csv with list_name='{list_name}'")
        result1 = csv_service.import_csv(file=file_storage, list_name=list_name)
        print(f"import_csv result: {result1}")
        
        # Reset file for next test
        file_storage.stream.seek(0)
        
        # 2. Call _process_sync_with_fallback directly
        print(f"Step 2: Calling _process_sync_with_fallback with list_name='{list_name}'")
        result2 = csv_service._process_sync_with_fallback(file=file_storage, list_name=list_name)
        print(f"_process_sync_with_fallback result: {result2}")
        
        # Check if either method created a list
        list_count = db.session.query(CampaignList).count()
        print(f"Total lists after both tests: {list_count}")
        
        if list_count == 0:
            pytest.fail("BUG: Neither import_csv nor _process_sync_with_fallback created campaign list")
        
        # Find which method worked
        lists = db.session.query(CampaignList).all()
        for lst in lists:
            print(f"Created list: ID={lst.id}, Name='{lst.name}'")
        
        # Check which result had list_id
        if result1.get('list_id') is None and result2.get('list_id') is None:
            pytest.fail("BUG: Neither method returned list_id even though list was created")
        
        print("Parameter flow test completed")


if __name__ == '__main__':
    test_import_contacts_with_explicit_create_list()