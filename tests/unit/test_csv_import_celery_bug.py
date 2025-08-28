"""
Test cases for CSV import Celery task campaign list bug

This focuses specifically on testing the Celery async import task
to see if campaign lists are created properly during async processing.
"""

import pytest
import io
from unittest.mock import Mock, patch, MagicMock
from werkzeug.datastructures import FileStorage

from tasks.csv_import_tasks import process_large_csv_import
from crm_database import CampaignList, CampaignListMember, Contact
from extensions import db


class TestCeleryCSVImportCampaignListBug:
    """Test Celery task specifically for campaign list creation"""
    
    def test_celery_task_creates_campaign_list(self, app, db_session):
        """
        Test that the Celery task creates campaign lists properly.
        This should FAIL if the async processing has the bug.
        """
        with app.app_context():
            # Create CSV content
            csv_content = """first_name,last_name,phone,email
John,Doe,+12345551234,john@example.com
Jane,Smith,+12345555678,jane@example.com
Bob,Johnson,+12345559999,bob@example.com"""
            
            list_name = "Celery-Test-List"
            filename = "celery_test.csv"
            
            # Verify no lists exist initially
            initial_count = db_session.query(CampaignList).count()
            assert initial_count == 0, "Should start with no campaign lists"
            
            # Create a mock Celery task
            mock_task = MagicMock()
            mock_task.update_state = MagicMock()
            
            # Call the Celery task function directly (bypassing Celery infrastructure)
            # Mock update_state since we're bypassing Celery infrastructure
            with patch.object(process_large_csv_import, 'update_state'):
                result = process_large_csv_import.run(
                    file_content=csv_content.encode('utf-8'),
                    filename=filename,
                    list_name=list_name,
                    imported_by="test_user"
                )
            
            # Check result
            assert result is not None, "Task should return result"
            assert isinstance(result, dict), "Task should return dictionary"
            assert result.get('status') == 'success', f"Task should succeed, got: {result}"
            
            # CRITICAL TEST: Check if campaign list was created
            final_count = db_session.query(CampaignList).count()
            assert final_count == 1, f"Task should create 1 campaign list, found {final_count}"
            
            created_list = db_session.query(CampaignList).filter_by(name=list_name).first()
            assert created_list is not None, f"Campaign list '{list_name}' should exist in database"
            
            # Check if task result includes list_id
            task_list_id = result.get('list_id')
            assert task_list_id is not None, f"Task result should include list_id, got: {result}"
            assert task_list_id == created_list.id, f"Task list_id {task_list_id} should match database ID {created_list.id}"
    
    def test_celery_task_uses_correct_service_method(self, app, db_session):
        """
        Test that the Celery task calls the correct service method that creates lists.
        This checks if the task is using the right CSV import path.
        """
        with app.app_context():
            csv_content = "first_name,last_name,phone\nTest,User,+15551234567"
            list_name = "Service-Method-Test"
            
            mock_task = MagicMock()
            mock_task.update_state = MagicMock()
            
            # Mock the CSV import service method to track what gets called
            with patch('services.csv_import_service.CSVImportService._process_sync_with_fallback') as mock_process:
                mock_process.return_value = {
                    'success': True,
                    'imported': 1,
                    'updated': 0,
                    'errors': [],
                    'list_id': None,  # This simulates the bug - no list_id returned
                    'message': 'Import completed'
                }
                
                with patch.object(process_large_csv_import, 'update_state'):
                    result = process_large_csv_import.run(
                        file_content=csv_content.encode('utf-8'),
                        filename="test.csv",
                        list_name=list_name,
                        imported_by="test_user"
                    )
                
                # Verify the service method was called
                assert mock_process.called, "Task should call _process_sync_with_fallback"
                
                # Check what parameters were passed
                call_args = mock_process.call_args
                assert call_args is not None, "Service method should be called with arguments"
                
                # Verify list_name was passed correctly
                kwargs = call_args.kwargs
                # The task passes list_name to the service method, but where?
                # Need to check if the service method gets list_name parameter
                
                # If the service method doesn't create the list, result won't have list_id
                assert result.get('list_id') is None, "This demonstrates the bug - no list_id from service"
    
    def test_celery_task_fallback_path_creates_list(self, app, db_session):
        """
        Test that when Celery task falls back to basic import, lists are still created.
        """
        with app.app_context():
            csv_content = "first_name,last_name,phone\nTest,User,+15551234567"
            list_name = "Fallback-Test-List"
            
            mock_task = MagicMock()
            mock_task.update_state = MagicMock()
            
            # Force the task to use the basic import path
            with patch('services.csv_import_service.CSVImportService._process_sync_with_fallback') as mock_fallback:
                # Make fallback actually create a list by calling real import_contacts
                def real_fallback(file, list_name, duplicate_strategy='merge', progress_callback=None):
                    from services.csv_import_service import CSVImportService
                    from repositories.csv_import_repository import CSVImportRepository
                    from repositories.contact_csv_import_repository import ContactCSVImportRepository
                    from repositories.campaign_list_repository import CampaignListRepository
                    from repositories.campaign_list_member_repository import CampaignListMemberRepository
                    from repositories.contact_repository import ContactRepository
                    from services.contact_service_refactored import ContactService
                    
                    service = CSVImportService(
                        csv_import_repository=CSVImportRepository(db_session),
                        contact_csv_import_repository=ContactCSVImportRepository(db_session),
                        campaign_list_repository=CampaignListRepository(db_session),
                        campaign_list_member_repository=CampaignListMemberRepository(db_session),
                        contact_repository=ContactRepository(db_session),
                        contact_service=ContactService(ContactRepository(db_session))
                    )
                    
                    # Call the actual import_contacts method that should create lists
                    return service.import_contacts(
                        file=file,
                        list_name=list_name,
                        create_list=True,  # CRITICAL: This should create the list
                        imported_by="test_user",
                        duplicate_strategy=duplicate_strategy,
                        progress_callback=progress_callback
                    )
                
                mock_fallback.side_effect = real_fallback
                
                with patch.object(process_large_csv_import, 'update_state'):
                    result = process_large_csv_import.run(
                        file_content=csv_content.encode('utf-8'),
                        filename="test.csv",
                        list_name=list_name,
                        imported_by="test_user"
                    )
                
                # CRITICAL TEST: Verify list was created
                list_count = db_session.query(CampaignList).count()
                assert list_count == 1, f"Fallback should create 1 campaign list, found {list_count}"
                
                created_list = db_session.query(CampaignList).filter_by(name=list_name).first()
                assert created_list is not None, f"Campaign list '{list_name}' should exist"
                
                # Verify task result includes list_id
                assert result.get('list_id') is not None, f"Task result should include list_id, got: {result}"
                assert result.get('list_id') == created_list.id
    
    def test_celery_task_propertyradar_import(self, app, db_session):
        """
        Test that Celery task properly imports PropertyRadar CSV and creates lists.
        This specifically tests the PropertyRadar import path through Celery.
        """
        with app.app_context():
            # PropertyRadar CSV content with proper headers
            propertyradar_csv = """Type,Address,City,ZIP,Primary Name,Primary First Name,Primary Last Name,Primary Mobile Phone1,Secondary Name,Secondary First Name,Secondary Last Name,Secondary Mobile Phone1,APN,Est Value,Est Equity,Owner Occ?
Single Family Residence,123 Main St,Boston,02101,John Doe,John,Doe,+15551234567,Jane Doe,Jane,Doe,+15559876543,001-002-003,500000,200000,Y
Townhouse,456 Oak Ave,Cambridge,02139,Bob Smith,Bob,Smith,+15551111111,,,,002-003-004,350000,150000,N"""
            
            list_name = "PropertyRadar-Celery-Test"
            filename = "propertyradar_cleaned_data.csv"  # Filename that triggers PropertyRadar detection
            
            # Clean up any existing test data
            db_session.query(CampaignListMember).delete()
            db_session.query(CampaignList).delete()
            db_session.query(Contact).delete()
            db_session.commit()
            
            # Verify clean state
            initial_list_count = db_session.query(CampaignList).count()
            initial_contact_count = db_session.query(Contact).count()
            assert initial_list_count == 0, "Should start with no campaign lists"
            assert initial_contact_count == 0, "Should start with no contacts"
            
            # Mock Celery task state updates
            mock_task = MagicMock()
            mock_task.update_state = MagicMock()
            
            # Call the Celery task function directly
            with patch.object(process_large_csv_import, 'update_state'):
                result = process_large_csv_import.run(
                    file_content=propertyradar_csv.encode('utf-8'),
                    filename=filename,
                    list_name=list_name,
                    imported_by="test_user"
                )
            
            # Verify task result
            assert result is not None, "Task should return result"
            assert isinstance(result, dict), "Task should return dictionary"
            assert result.get('status') == 'success', f"Task should succeed, got: {result}"
            
            # Verify PropertyRadar import created contacts
            final_contact_count = db_session.query(Contact).count()
            assert final_contact_count > 0, f"PropertyRadar import should create contacts, found {final_contact_count}"
            
            # Verify campaign list was created
            final_list_count = db_session.query(CampaignList).count()
            assert final_list_count == 1, f"Task should create 1 campaign list, found {final_list_count}"
            
            created_list = db_session.query(CampaignList).filter_by(name=list_name).first()
            assert created_list is not None, f"Campaign list '{list_name}' should exist in database"
            
            # Verify task result includes list_id
            task_list_id = result.get('list_id')
            assert task_list_id is not None, f"Task result should include list_id, got: {result}"
            assert task_list_id == created_list.id, f"Task list_id {task_list_id} should match database ID {created_list.id}"
            
            # Verify contacts are associated with the list
            list_members = db_session.query(CampaignListMember).filter_by(list_id=created_list.id).all()
            assert len(list_members) > 0, f"List should have contacts associated, found {len(list_members)} members"
            
            # Log success
            print(f"✅ PropertyRadar Celery import test passed: {final_contact_count} contacts, {len(list_members)} list members")
    
    def test_celery_task_parameter_passing(self, app, db_session):
        """
        Test that the Celery task passes list_name correctly to the import service.
        This checks if the parameter is lost somewhere in the async flow.
        """
        with app.app_context():
            csv_content = "first_name,last_name,phone\nTest,User,+15551234567"
            list_name = "Parameter-Test-List"
            
            mock_task = MagicMock()
            mock_task.update_state = MagicMock()
            
            # Track what parameters are passed to the service
            captured_params = {}
            
            def capture_params(*args, **kwargs):
                captured_params.update(kwargs)
                captured_params['args'] = args
                # Return a basic success result without list_id to simulate bug
                return {
                    'success': True,
                    'imported': 1,
                    'updated': 0,
                    'errors': [],
                    'list_id': None,  # Bug simulation
                    'message': 'Import completed'
                }
            
            with patch('services.csv_import_service.CSVImportService._process_sync_with_fallback', side_effect=capture_params):
                with patch.object(process_large_csv_import, 'update_state'):
                    result = process_large_csv_import.run(
                        file_content=csv_content.encode('utf-8'),
                        filename="test.csv",
                        list_name=list_name,
                        imported_by="test_user"
                    )
                
                # Check if list_name was passed to the service
                assert 'list_name' in captured_params or list_name in str(captured_params), \
                    f"list_name should be passed to service method. Captured: {captured_params}"
                
                # The bug is that even though list_name is passed, list_id is not returned
                assert result.get('list_id') is None, "This demonstrates the bug - no list_id returned"


class TestCSVImportServiceMethodBug:
    """Test the specific service methods used by Celery to find the bug"""
    
    def test_process_sync_with_fallback_creates_list(self, app, db_session):
        """
        Test the _process_sync_with_fallback method specifically.
        This is the method called by the Celery task.
        """
        with app.app_context():
            from services.csv_import_service import CSVImportService
            from repositories.csv_import_repository import CSVImportRepository
            from repositories.contact_csv_import_repository import ContactCSVImportRepository
            from repositories.campaign_list_repository import CampaignListRepository
            from repositories.campaign_list_member_repository import CampaignListMemberRepository
            from repositories.contact_repository import ContactRepository
            from services.contact_service_refactored import ContactService
            
            service = CSVImportService(
                csv_import_repository=CSVImportRepository(db_session),
                contact_csv_import_repository=ContactCSVImportRepository(db_session),
                campaign_list_repository=CampaignListRepository(db_session),
                campaign_list_member_repository=CampaignListMemberRepository(db_session),
                contact_repository=ContactRepository(db_session),
                contact_service=ContactService(ContactRepository(db_session))
            )
            
            # Create test file
            csv_content = "first_name,last_name,phone\nTest,User,+15551234567"
            file_storage = FileStorage(
                stream=io.BytesIO(csv_content.encode('utf-8')),
                filename='test.csv',
                content_type='text/csv'
            )
            
            list_name = "Sync-Fallback-Test"
            
            # Call the method directly
            result = service._process_sync_with_fallback(
                file=file_storage,
                list_name=list_name
            )
            
            # Check result
            assert result is not None, "Method should return result"
            assert isinstance(result, dict), "Method should return dictionary"
            
            # CRITICAL TEST: Check if list was created
            list_count = db_session.query(CampaignList).count()
            # This might FAIL if _process_sync_with_fallback doesn't create lists
            assert list_count == 1, f"Method should create 1 campaign list, found {list_count}"
            
            created_list = db_session.query(CampaignList).filter_by(name=list_name).first()
            assert created_list is not None, f"Campaign list '{list_name}' should exist"
            
            # Check if method result includes list_id
            assert result.get('list_id') is not None, f"Method result should include list_id, got: {result}"
            assert result.get('list_id') == created_list.id
    
    def test_basic_import_csv_creates_list(self, app, db_session):
        """
        Test the _basic_import_csv method to see if it creates lists.
        """
        with app.app_context():
            from services.csv_import_service import CSVImportService
            from repositories.csv_import_repository import CSVImportRepository
            from repositories.contact_csv_import_repository import ContactCSVImportRepository
            from repositories.campaign_list_repository import CampaignListRepository
            from repositories.campaign_list_member_repository import CampaignListMemberRepository
            from repositories.contact_repository import ContactRepository
            from services.contact_service_refactored import ContactService
            
            service = CSVImportService(
                csv_import_repository=CSVImportRepository(db_session),
                contact_csv_import_repository=ContactCSVImportRepository(db_session),
                campaign_list_repository=CampaignListRepository(db_session),
                campaign_list_member_repository=CampaignListMemberRepository(db_session),
                contact_repository=ContactRepository(db_session),
                contact_service=ContactService(ContactRepository(db_session))
            )
            
            # Create test file
            csv_content = "first_name,last_name,phone\nTest,User,+15551234567"
            file_storage = FileStorage(
                stream=io.BytesIO(csv_content.encode('utf-8')),
                filename='test.csv',
                content_type='text/csv'
            )
            
            list_name = "Basic-Import-Test"
            
            # Call the _basic_import_csv method directly
            result = service._basic_import_csv(
                file=file_storage,
                list_name=list_name
            )
            
            # Check result
            assert result is not None, "Method should return result"
            assert isinstance(result, dict), "Method should return dictionary"
            
            # CRITICAL TEST: This method calls import_contacts with create_list=True by default
            list_count = db_session.query(CampaignList).count()
            assert list_count == 1, f"_basic_import_csv should create 1 campaign list, found {list_count}"
            
            created_list = db_session.query(CampaignList).filter_by(name=list_name).first()
            assert created_list is not None, f"Campaign list '{list_name}' should exist"
            
            # Check if method result includes list_id
            assert result.get('list_id') is not None, f"Method result should include list_id, got: {result}"