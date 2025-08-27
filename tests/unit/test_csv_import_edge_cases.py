"""
Test CSV import edge cases that might cause the campaign list bug

This tests specific scenarios that might prevent campaign list creation:
- Missing list_name parameter
- None list_name parameter  
- Empty string list_name
- Different code paths that might skip list creation
"""

import pytest
import io
from werkzeug.datastructures import FileStorage
from unittest.mock import patch, MagicMock

from services.csv_import_service import CSVImportService
from repositories.csv_import_repository import CSVImportRepository
from repositories.contact_csv_import_repository import ContactCSVImportRepository
from repositories.campaign_list_repository import CampaignListRepository
from repositories.campaign_list_member_repository import CampaignListMemberRepository
from repositories.contact_repository import ContactRepository
from services.contact_service_refactored import ContactService
from crm_database import CampaignList, Contact
from tasks.csv_import_tasks import process_large_csv_import


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
    csv_data = "first_name,last_name,phone\nJohn,Doe,+12345551234\nJane,Smith,+12345555678"
    return FileStorage(
        stream=io.BytesIO(csv_data.encode('utf-8')),
        filename='test.csv',
        content_type='text/csv'
    )


class TestCSVImportEdgeCaseBugs:
    """Test edge cases that might prevent campaign list creation"""
    
    def test_import_with_none_list_name(self, app, db_session, csv_import_service, sample_csv_file):
        """
        Test CSV import with None list_name parameter.
        This might cause the bug if None list_name skips list creation.
        """
        with app.app_context():
            result = csv_import_service.import_contacts(
                file=sample_csv_file,
                list_name=None,  # This might be the bug trigger
                create_list=True,
                imported_by="test_user"
            )
            
            assert result['successful'] > 0, "Import should succeed"
            
            # Check if list was created despite None list_name
            list_count = db_session.query(CampaignList).count()
            if list_count == 0:
                # This demonstrates the bug - None list_name prevents creation
                pytest.fail(f"FOUND BUG: None list_name prevents campaign list creation. Result: {result}")
            
            assert result.get('list_id') is not None, "Should still create list with default name"
    
    def test_import_with_empty_list_name(self, app, db_session, csv_import_service, sample_csv_file):
        """
        Test CSV import with empty string list_name parameter.
        """
        with app.app_context():
            result = csv_import_service.import_contacts(
                file=sample_csv_file,
                list_name="",  # Empty string might cause issues
                create_list=True,
                imported_by="test_user"
            )
            
            assert result['successful'] > 0, "Import should succeed"
            
            list_count = db_session.query(CampaignList).count()
            if list_count == 0:
                pytest.fail(f"FOUND BUG: Empty list_name prevents campaign list creation. Result: {result}")
            
            assert result.get('list_id') is not None, "Should create list with default name"
    
    def test_celery_task_with_none_list_name(self, app, db_session):
        """
        Test Celery task with None list_name - this might be the actual bug.
        """
        with app.app_context():
            csv_content = "first_name,last_name,phone\nTest,User,+15551234567"
            
            mock_task = MagicMock()
            mock_task.update_state = MagicMock()
            
            # Call Celery task with None list_name (common in real usage)
            result = process_large_csv_import(
                mock_task,
                file_content=csv_content.encode('utf-8'),
                filename="test.csv",
                list_name=None,  # This might be the bug!
                imported_by="test_user"
            )
            
            # Check if import succeeded but no list was created
            assert result.get('status') == 'success', f"Task should succeed, got: {result}"
            
            list_count = db_session.query(CampaignList).count()
            if list_count == 0:
                pytest.fail(f"FOUND BUG: Celery task with None list_name prevents campaign list creation. Result: {result}")
                
            # If we reach here, a list was created
            assert result.get('list_id') is not None, "Task should return list_id"
    
    def test_import_csv_method_with_none_list_name(self, app, db_session, csv_import_service, sample_csv_file):
        """
        Test the import_csv method (used by routes) with None list_name.
        This might be where the bug occurs in the real application.
        """
        with app.app_context():
            result = csv_import_service.import_csv(
                file=sample_csv_file,
                list_name=None  # This is often None in route calls
            )
            
            assert result.get('success', False), f"Import should succeed, got: {result}"
            
            list_count = db_session.query(CampaignList).count()
            if list_count == 0:
                pytest.fail(f"FOUND BUG: import_csv with None list_name prevents list creation. Result: {result}")
            
            assert result.get('list_id') is not None, "Should return list_id"
    
    def test_process_sync_with_fallback_with_none_list_name(self, app, db_session, csv_import_service, sample_csv_file):
        """
        Test _process_sync_with_fallback with None list_name.
        This is called by the Celery task and might be the bug source.
        """
        with app.app_context():
            result = csv_import_service._process_sync_with_fallback(
                file=sample_csv_file,
                list_name=None  # This might prevent list creation
            )
            
            assert result.get('success', False), f"Method should succeed, got: {result}"
            
            list_count = db_session.query(CampaignList).count()
            if list_count == 0:
                pytest.fail(f"FOUND BUG: _process_sync_with_fallback with None list_name prevents list creation. Result: {result}")
            
            assert result.get('list_id') is not None, "Should return list_id"
    
    def test_basic_import_csv_with_none_list_name(self, app, db_session, csv_import_service, sample_csv_file):
        """
        Test _basic_import_csv with None list_name.
        This might be the actual method that fails to create lists.
        """
        with app.app_context():
            result = csv_import_service._basic_import_csv(
                file=sample_csv_file,
                list_name=None  # This is the suspected bug trigger
            )
            
            assert result.get('success', False), f"Method should succeed, got: {result}"
            
            list_count = db_session.query(CampaignList).count()
            if list_count == 0:
                pytest.fail(f"FOUND BUG: _basic_import_csv with None list_name prevents list creation. Result: {result}")
            
            assert result.get('list_id') is not None, "Should return list_id"
    
    def test_import_contacts_create_list_false(self, app, db_session, csv_import_service, sample_csv_file):
        """
        Test import_contacts with create_list=False.
        This should NOT create a list and should return None list_id.
        """
        with app.app_context():
            result = csv_import_service.import_contacts(
                file=sample_csv_file,
                list_name="Test-List",
                create_list=False,  # Should NOT create list
                imported_by="test_user"
            )
            
            assert result['successful'] > 0, "Import should succeed"
            assert result.get('list_id') is None, "Should NOT return list_id when create_list=False"
            
            list_count = db_session.query(CampaignList).count()
            assert list_count == 0, "Should NOT create campaign list when create_list=False"
    
    def test_route_import_csv_default_behavior(self, app, client):
        """
        Test the actual route behavior to see if it passes parameters correctly.
        This simulates the real user flow that shows the bug.
        """
        with app.app_context():
            csv_data = "first_name,last_name,phone\nTest,User,+15551234567"
            
            # Test without explicit list_name (might default to None)
            response = client.post('/campaigns/import-csv', data={
                'csv_file': (io.BytesIO(csv_data.encode()), 'test.csv'),
                # No 'list_name' field - this might be the bug!
                'enrichment_mode': 'enrich_missing'
            }, content_type='multipart/form-data')
            
            # Should redirect or show success
            assert response.status_code in [200, 302], f"Route should work, got {response.status_code}"
            
            # Check if list was created
            from crm_database import CampaignList
            from extensions import db
            list_count = db.session.query(CampaignList).count()
            
            if list_count == 0:
                pytest.fail("FOUND BUG: Route import without explicit list_name prevents campaign list creation")
            
            # If we get here, list was created successfully
            assert list_count == 1, "Route should create campaign list"


class TestCSVImportParameterHandling:
    """Test how parameters are handled through the import flow"""
    
    def test_parameter_flow_tracking(self, app, db_session, csv_import_service, sample_csv_file):
        """
        Track how parameters flow through the import methods.
        This helps identify where list_name might get lost.
        """
        with app.app_context():
            # Track all method calls and their parameters
            call_tracker = []
            
            def track_import_contacts(*args, **kwargs):
                call_tracker.append({
                    'method': 'import_contacts',
                    'args': args,
                    'kwargs': kwargs
                })
                # Call original method
                return csv_import_service.__class__.import_contacts(csv_import_service, *args, **kwargs)
            
            def track_basic_import(*args, **kwargs):
                call_tracker.append({
                    'method': '_basic_import_csv',
                    'args': args,
                    'kwargs': kwargs
                })
                # Call original method
                return csv_import_service.__class__._basic_import_csv(csv_import_service, *args, **kwargs)
            
            # Patch methods to track calls
            with patch.object(csv_import_service, 'import_contacts', side_effect=track_import_contacts):
                with patch.object(csv_import_service, '_basic_import_csv', side_effect=track_basic_import):
                    
                    # Call import_csv (route-level method)
                    result = csv_import_service.import_csv(
                        file=sample_csv_file,
                        list_name=None  # Test with None
                    )
                    
                    # Analyze the call flow
                    print(f"Call tracker: {call_tracker}")
                    
                    # Check if list_name parameter is preserved through the chain
                    for call in call_tracker:
                        if 'list_name' in call['kwargs']:
                            list_name_value = call['kwargs']['list_name']
                            print(f"Method {call['method']} received list_name: {list_name_value}")
                            
                            if list_name_value is None:
                                print(f"POTENTIAL BUG: Method {call['method']} received None list_name")
                    
                    # Check final result
                    if result.get('list_id') is None:
                        pytest.fail(f"BUG CONFIRMED: Parameter flow resulted in no list_id. Calls: {call_tracker}, Result: {result}")
    
    def test_celery_task_parameter_inspection(self, app, db_session):
        """
        Inspect exactly what parameters the Celery task receives and passes on.
        """
        with app.app_context():
            csv_content = "first_name,last_name,phone\nTest,User,+15551234567"
            
            # Track service method calls from within Celery task
            service_calls = []
            
            def track_service_call(*args, **kwargs):
                service_calls.append({
                    'args': args,
                    'kwargs': kwargs
                })
                # Return mock result that might not include list_id
                return {
                    'success': True,
                    'imported': 1,
                    'updated': 0,
                    'errors': [],
                    'list_id': None,  # This simulates the bug
                    'message': 'Import completed'
                }
            
            mock_task = MagicMock()
            mock_task.update_state = MagicMock()
            
            with patch('services.csv_import_service.CSVImportService._process_sync_with_fallback', side_effect=track_service_call):
                result = process_large_csv_import(
                    mock_task,
                    file_content=csv_content.encode('utf-8'),
                    filename="test.csv",
                    list_name="Celery-Test-List",  # Pass explicit list_name
                    imported_by="test_user"
                )
                
                print(f"Service calls from Celery: {service_calls}")
                
                # Check if list_name was passed correctly
                if service_calls:
                    call = service_calls[0]
                    if 'list_name' not in call['kwargs'] and 'Celery-Test-List' not in str(call):
                        pytest.fail(f"BUG: Celery task didn't pass list_name to service. Calls: {service_calls}")
                
                # The bug is that service method returns None list_id even with valid list_name
                if result.get('list_id') is None:
                    print(f"CONFIRMED BUG: Service method doesn't return list_id despite receiving list_name")
                    # This is expected in this test since we're mocking the service call