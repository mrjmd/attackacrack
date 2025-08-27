"""
Integration tests for campaign routes
Tests the full request/response cycle with real database
"""
import pytest
from flask import url_for
from crm_database import Campaign, CampaignMembership, Contact, CampaignList, CSVImport
from unittest.mock import patch, Mock


class TestCampaignRoutesIntegration:
    """Integration tests for campaign routes"""
    
    def test_campaign_list_page(self, authenticated_client, db_session):
        """Test campaign list page loads with campaigns"""
        # Create test campaigns
        campaign1 = Campaign(
            name="Test Campaign 1",
            campaign_type="blast",
            template_a="Test message",
            status="draft"
        )
        campaign2 = Campaign(
            name="Test Campaign 2",
            campaign_type="ab_test",
            template_a="Version A",
            template_b="Version B",
            status="running"
        )
        db_session.add_all([campaign1, campaign2])
        db_session.commit()
        
        # Request the page
        response = authenticated_client.get('/campaigns')
        
        # Assert
        assert response.status_code == 200
        assert b'Test Campaign 1' in response.data
        assert b'Test Campaign 2' in response.data
    
    def test_new_campaign_page(self, authenticated_client, db_session):
        """Test new campaign form page loads"""
        # Create a test list for the form
        test_list = CampaignList(
            name="Test List",
            description="Test list for campaign"
        )
        db_session.add(test_list)
        db_session.commit()
        
        # Request the page
        response = authenticated_client.get('/campaigns/new')
        
        # Assert
        assert response.status_code == 200
        assert b'Create New Campaign' in response.data
        assert b'Test List' in response.data
    
    def test_create_campaign_flow(self, authenticated_client, db_session):
        """Test creating a campaign through the form"""
        # Mock only the external SMS service
        with patch('services.openphone_service.OpenPhoneService.send_message') as mock_send:
            mock_send.return_value = {'success': True}
            
            # Create test contacts
            contacts = []
            for i in range(3):
                contact = Contact(
                    first_name=f"Test{i}",
                    last_name="User",
                    phone=f"+155500000{i}"
                )
                contacts.append(contact)
                db_session.add(contact)
            db_session.commit()
            
            # Submit campaign creation form
            response = authenticated_client.post('/campaigns', data={
                'name': 'Integration Test Campaign',
                'campaign_type': 'blast',
                'audience_type': 'mixed',
                'template_a': 'Hello {first_name}!',
                'daily_limit': '50',
                'business_hours_only': 'on',
                'has_name_only': 'on'
            }, follow_redirects=True)
            
            # Assert campaign was created
            assert response.status_code == 200
            campaign = Campaign.query.filter_by(name='Integration Test Campaign').first()
            assert campaign is not None
            assert campaign.campaign_type == 'blast'
            assert campaign.template_a == 'Hello {first_name}!'
            assert campaign.daily_limit == 50
            assert campaign.business_hours_only is True
    
    def test_campaign_detail_page(self, authenticated_client, db_session):
        """Test campaign detail page with analytics"""
        import time
        unique_id = str(int(time.time() * 1000000))[-6:]
        
        # Create campaign with recipients
        campaign = Campaign(
            name=f"Detail Test Campaign {unique_id}",
            campaign_type="blast",
            template_a="Test message",
            status="running"
        )
        db_session.add(campaign)
        db_session.commit()
        
        # Add some recipients with unique phone numbers
        for i in range(5):
            contact = Contact(
                first_name=f"Contact{i}",
                last_name="Test",
                phone=f"+1555{unique_id}{i:02d}"
            )
            db_session.add(contact)
            db_session.commit()
            
            membership = CampaignMembership(
                campaign_id=campaign.id,
                contact_id=contact.id,
                status='sent' if i < 3 else 'pending'
            )
            db_session.add(membership)
        db_session.commit()
        
        # Request the detail page
        response = authenticated_client.get(f'/campaigns/{campaign.id}')
        
        # Assert
        assert response.status_code == 200
        assert b'Detail Test Campaign' in response.data
        assert b'running' in response.data
    
    def test_start_campaign(self, authenticated_client, db_session):
        """Test starting a campaign"""
        import time
        unique_id = str(int(time.time() * 1000000))[-6:]
        
        # Create campaign with recipients
        campaign = Campaign(
            name=f"Start Test Campaign {unique_id}",
            campaign_type="blast",
            template_a="Test message",
            status="draft"
        )
        db_session.add(campaign)
        db_session.commit()
        
        # Add a recipient with unique phone
        contact = Contact(
            first_name="Test",
            last_name="User",
            phone=f"+1555{unique_id}99"
        )
        db_session.add(contact)
        db_session.commit()
        
        membership = CampaignMembership(
            campaign_id=campaign.id,
            contact_id=contact.id,
            status='pending'
        )
        db_session.add(membership)
        db_session.commit()
        
        # Start the campaign
        response = authenticated_client.post(
            f'/campaigns/{campaign.id}/start',
            follow_redirects=True
        )
        
        # Assert
        assert response.status_code == 200
        campaign = db_session.get(Campaign, campaign.id)
        assert campaign.status == 'running'
    
    def test_pause_campaign(self, authenticated_client, db_session):
        """Test pausing a running campaign"""
        import time
        unique_id = str(int(time.time() * 1000000))[-6:]
        
        # Create running campaign
        campaign = Campaign(
            name=f"Pause Test Campaign {unique_id}",
            campaign_type="blast",
            template_a="Test message",
            status="running"
        )
        db_session.add(campaign)
        db_session.commit()
        
        # Pause the campaign
        response = authenticated_client.post(
            f'/campaigns/{campaign.id}/pause',
            follow_redirects=True
        )
        
        # Assert
        assert response.status_code == 200
        campaign = db_session.get(Campaign, campaign.id)
        assert campaign.status == 'paused'
    
    def test_api_campaign_analytics(self, authenticated_client, db_session):
        """Test API endpoint for campaign analytics"""
        # Create campaign
        campaign = Campaign(
            name="API Test Campaign",
            campaign_type="blast",
            template_a="Test",
            status="running"
        )
        db_session.add(campaign)
        db_session.commit()
        
        # Request analytics via API
        response = authenticated_client.get(f'/api/campaigns/{campaign.id}/analytics')
        
        # Assert
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert 'analytics' in data
    
    def test_campaign_lists_page(self, authenticated_client, db_session):
        """Test campaign lists management page"""
        # Create test lists
        list1 = CampaignList(name="Static List", is_dynamic=False)
        list2 = CampaignList(
            name="Dynamic List",
            is_dynamic=True,
            filter_criteria={"has_phone": True}
        )
        db_session.add_all([list1, list2])
        db_session.commit()
        
        # Request the page
        response = authenticated_client.get('/campaigns/lists')
        
        # Assert
        assert response.status_code == 200
        assert b'Static List' in response.data
        assert b'Dynamic List' in response.data
    
    def test_create_campaign_list(self, authenticated_client, db_session):
        """Test creating a new campaign list"""
        import time
        unique_id = str(int(time.time() * 1000000))[-6:]
        
        # Submit list creation form
        response = authenticated_client.post('/campaigns/lists/new', data={
            'name': f'New Test List {unique_id}',
            'description': 'Test list description',
            'is_dynamic': ''
        }, follow_redirects=True)
        
        # Assert
        assert response.status_code == 200
        new_list = CampaignList.query.filter_by(name=f'New Test List {unique_id}').first()
        assert new_list is not None
        assert new_list.description == 'Test list description'
        assert new_list.is_dynamic == False
    
    def test_refresh_dynamic_list(self, authenticated_client, db_session):
        """Test refreshing a dynamic campaign list"""
        import time
        unique_id = str(int(time.time() * 1000000))[-6:]
        
        # Create dynamic list
        dynamic_list = CampaignList(
            name=f"Dynamic Test {unique_id}",
            is_dynamic=True,
            filter_criteria={"has_phone": True}
        )
        db_session.add(dynamic_list)
        db_session.commit()
        
        # Add contacts that match criteria with unique phones
        for i in range(3):
            contact = Contact(
                first_name=f"Dynamic{i}",
                last_name="Test",
                phone=f"+1555{unique_id}{i:02d}"
            )
            db_session.add(contact)
        db_session.commit()
        
        # Refresh the list
        response = authenticated_client.post(
            f'/campaigns/lists/{dynamic_list.id}/refresh',
            follow_redirects=True
        )
        
        # Assert - just check that refresh succeeded and we got redirected
        assert response.status_code == 200
    
    def test_campaign_lists_page_with_null_failed_imports(self, authenticated_client, db_session):
        """Test campaign lists page handles CSV imports with null failed_imports
        
        This reproduces a production bug where failed_imports could be None/NULL
        causing template crashes when checking 'import.failed_imports > 0'
        """
        from datetime import datetime
        
        # Create test lists
        list1 = CampaignList(name="Test List", is_dynamic=False)
        db_session.add(list1)
        db_session.commit()
        
        # Create CSV import with failed_imports as None (reproduces production bug)
        csv_import = CSVImport(
            filename="test.csv",
            imported_at=datetime.utcnow(),
            total_rows=10,
            successful_imports=8,
            failed_imports=None  # This should cause template crash at line 101
        )
        db_session.add(csv_import)
        db_session.commit()
        
        # Mock the CSV service to return our problematic import
        with patch('services.csv_import_service.CSVImportService.get_import_history') as mock_history:
            mock_history.return_value = [csv_import]
            
            # Request the page - this should crash with TypeError: 
            # "unsupported operand type(s) for >: 'NoneType' and 'int'"
            response = authenticated_client.get('/campaigns/lists')
            
            # This assertion will fail initially (RED phase) because template crashes
            assert response.status_code == 200
            assert b'test.csv' in response.data
            assert b'Complete' in response.data  # Should show "Complete" when failed_imports is None
    
    def test_campaign_lists_page_with_zero_failed_imports(self, authenticated_client, db_session):
        """Test campaign lists page correctly shows complete when failed_imports is 0
        
        This tests the edge case where failed_imports = 0 (not None)
        """
        from datetime import datetime
        
        # Create test lists
        list1 = CampaignList(name="Test List", is_dynamic=False)
        db_session.add(list1)
        db_session.commit()
        
        # Create CSV import with failed_imports = 0
        csv_import = CSVImport(
            filename="success_test.csv",
            imported_at=datetime.utcnow(),
            total_rows=10,
            successful_imports=10,
            failed_imports=0  # This should show "Complete"
        )
        db_session.add(csv_import)
        db_session.commit()
        
        # Mock the CSV service to return our successful import
        with patch('services.csv_import_service.CSVImportService.get_import_history') as mock_history:
            mock_history.return_value = [csv_import]
            
            # Request the page
            response = authenticated_client.get('/campaigns/lists')
            
            # Assert that it shows complete
            assert response.status_code == 200
            assert b'success_test.csv' in response.data
            assert b'Complete' in response.data  # Should show "Complete" when failed_imports = 0
            assert b'failed' not in response.data  # Should NOT show any "failed" text
    
    def test_campaign_lists_page_with_failed_imports_value(self, authenticated_client, db_session):
        """Test campaign lists page correctly shows failed imports when failed_imports has a value
        
        This ensures our fix doesn't break the normal case where failed_imports > 0
        """
        from datetime import datetime
        
        # Create test lists
        list1 = CampaignList(name="Test List", is_dynamic=False)
        db_session.add(list1)
        db_session.commit()
        
        # Create CSV import with failed_imports > 0
        csv_import = CSVImport(
            filename="failed_test.csv",
            imported_at=datetime.utcnow(),
            total_rows=10,
            successful_imports=7,
            failed_imports=3  # This should show "3 failed" badge
        )
        db_session.add(csv_import)
        db_session.commit()
        
        # Mock the CSV service to return our import with failures
        with patch('services.csv_import_service.CSVImportService.get_import_history') as mock_history:
            mock_history.return_value = [csv_import]
            
            # Request the page
            response = authenticated_client.get('/campaigns/lists')
            
            # Assert that it shows the failed count
            assert response.status_code == 200
            assert b'failed_test.csv' in response.data
            assert b'3 failed' in response.data  # Should show "3 failed" badge
            assert b'Complete' not in response.data  # Should NOT show "Complete"
    
    def test_campaign_list_detail_success(self, authenticated_client, db_session):
        """Test campaign list detail page loads when list exists"""
        import time
        unique_id = str(int(time.time() * 1000000))[-6:]
        
        # Create test list
        campaign_list = CampaignList(
            name=f"Detail Test List {unique_id}",
            description="Test list for detail page",
            is_dynamic=False
        )
        db_session.add(campaign_list)
        db_session.commit()
        
        # Add test contacts to the list
        contacts = []
        for i in range(3):
            contact = Contact(
                first_name=f"TestContact{i}",
                last_name="User",
                phone=f"+1555{unique_id}{i:02d}",
                email=f"test{i}_{unique_id}@example.com"
            )
            contacts.append(contact)
            db_session.add(contact)
        db_session.commit()
        
        # Add contacts to the list using direct membership (bypassing service for test setup)
        from crm_database import CampaignListMember
        for contact in contacts:
            member = CampaignListMember(
                list_id=campaign_list.id,
                contact_id=contact.id,
                status='active',
                added_by='test'
            )
            db_session.add(member)
        db_session.commit()
        
        # Request the detail page
        response = authenticated_client.get(f'/campaigns/lists/{campaign_list.id}')
        
        # Assert
        assert response.status_code == 200
        assert f'Detail Test List {unique_id}'.encode() in response.data
        assert b'Test list for detail page' in response.data
        assert b'Active Contacts' in response.data
        assert b'3' in response.data  # Should show 3 active contacts
    
    def test_campaign_list_detail_not_found(self, authenticated_client, db_session):
        """Test 404 error when campaign list doesn't exist"""
        # Request non-existent list
        response = authenticated_client.get('/campaigns/lists/999999')
        
        # Should return 404
        assert response.status_code == 404
    
    def test_campaign_list_detail_service_failure(self, authenticated_client, db_session):
        """Test 404 error when service returns failure Result"""
        with patch('services.campaign_list_service_refactored.CampaignListServiceRefactored.get_campaign_list_by_id') as mock_service:
            # Mock service to return failure Result
            from services.common.result import Result
            mock_service.return_value = Result.failure("Database error")
            
            # Request the page
            response = authenticated_client.get('/campaigns/lists/1')
            
            # Should return 404
            assert response.status_code == 404
    
    def test_campaign_list_detail_service_success_with_none_data(self, authenticated_client, db_session):
        """Test 404 error when service returns success but with None data"""
        with patch('services.campaign_list_service_refactored.CampaignListServiceRefactored.get_campaign_list_by_id') as mock_service:
            # Mock service to return success with None data
            from services.common.result import Result
            mock_service.return_value = Result.success(None)
            
            # Request the page
            response = authenticated_client.get('/campaigns/lists/1')
            
            # Should return 404
            assert response.status_code == 404
    
    def test_csv_import_view_list_button_integration(self, authenticated_client, db_session):
        """Test that View List button works after CSV import creates a list
        
        This integration test verifies the complete flow:
        1. CSV import creates a campaign list
        2. The View List redirect works correctly
        3. The campaign list detail page renders without 404 error
        """
        import time
        import io
        from unittest.mock import patch, Mock
        
        unique_id = str(int(time.time() * 1000000))[-6:]
        list_name = f"CSV Import Test List {unique_id}"
        
        # Create test list in database (simulating successful CSV import)
        from crm_database import CampaignList, Contact, CampaignListMember
        
        campaign_list = CampaignList(
            name=list_name,
            description="Created by CSV import test",
            is_dynamic=False
        )
        db_session.add(campaign_list)
        db_session.commit()
        
        # Add some test contacts (simulating CSV import result)
        contacts = []
        for i in range(5):
            contact = Contact(
                first_name=f"Imported{i}",
                last_name="Contact",
                phone=f"+1555{unique_id}{i:02d}",
                email=f"imported{i}_{unique_id}@example.com"
            )
            contacts.append(contact)
            db_session.add(contact)
        db_session.commit()
        
        # Add contacts to list (simulating import process)
        for contact in contacts:
            member = CampaignListMember(
                list_id=campaign_list.id,
                contact_id=contact.id,
                status='active',
                added_by='csv_import'
            )
            db_session.add(member)
        db_session.commit()
        
        # Mock CSV service to return successful import result
        mock_result = {
            'success': True,
            'imported': 5,
            'updated': 0,
            'errors': [],
            'list_id': campaign_list.id  # This is the critical part
        }
        
        with patch('services.csv_import_service.CSVImportService.import_csv') as mock_import:
            mock_import.return_value = mock_result
            
            # Create mock CSV file
            csv_content = f"""first_name,last_name,phone,email\nImported0,Contact,+1555{unique_id}00,imported0_{unique_id}@example.com\nImported1,Contact,+1555{unique_id}01,imported1_{unique_id}@example.com"""
            csv_file = (io.BytesIO(csv_content.encode()), 'test_import.csv')
            
            # Submit CSV import form (this should redirect to list detail)
            response = authenticated_client.post('/campaigns/import-csv', data={
                'list_name': list_name,
                'enrichment_mode': 'enrich_missing',
                'csv_file': csv_file
            }, follow_redirects=True)
            
            # Verify successful redirect to list detail page
            assert response.status_code == 200
            
            # Check that we're on the list detail page
            assert list_name.encode() in response.data
            assert b'Created by CSV import test' in response.data
            assert b'Active Contacts' in response.data
            assert b'5' in response.data  # Should show 5 imported contacts
            
            # Verify the URL contains the list ID
            assert f'/campaigns/lists/{campaign_list.id}' in response.request.url
    
    def test_csv_import_nonexistent_list_redirect_safe(self, authenticated_client, db_session):
        """Test that CSV import with invalid list_id handles gracefully
        
        This tests the edge case where CSV service returns a list_id
        that doesn't exist in the database (shouldn't happen, but good to test)
        """
        import io
        from unittest.mock import patch
        
        # Mock CSV service to return invalid list_id
        mock_result = {
            'success': True,
            'imported': 2,
            'updated': 0,
            'errors': [],
            'list_id': 999999  # Non-existent list
        }
        
        with patch('services.csv_import_service.CSVImportService.import_csv') as mock_import:
            mock_import.return_value = mock_result
            
            # Create mock CSV file
            csv_content = "first_name,last_name,phone\nTest,User,+15551234567"
            csv_file = (io.BytesIO(csv_content.encode()), 'test.csv')
            
            # Submit CSV import form
            response = authenticated_client.post('/campaigns/import-csv', data={
                'list_name': 'Test List',
                'enrichment_mode': 'enrich_missing',
                'csv_file': csv_file
            }, follow_redirects=True)
            
            # Should handle the 404 gracefully (redirect to 404 page or handle error)
            # The exact behavior may vary, but it shouldn't crash
            assert response.status_code in [200, 404]  # Allow either behavior
            
            # If 404, verify it's the right kind of 404
            if response.status_code == 404:
                # This is the expected behavior for non-existent list
                pass
            else:
                # If it doesn't 404, it should show an error message
                assert b'Import' in response.data  # Should be on import or error page
    
    def test_route_demonstrates_result_pattern_usage(self, authenticated_client, db_session):
        """Test demonstrating that the route correctly handles Result objects
        
        This test verifies that the fix to handle Result objects is working:
        - Before fix: route checked `if not campaign_list` on Result object (always truthy)
        - After fix: route checks `if not list_result.is_success or not list_result.data`
        """
        import time
        from unittest.mock import patch, Mock
        from services.common.result import Result
        
        unique_id = str(int(time.time() * 1000000))[-6:]
        
        # Create test list in database
        from crm_database import CampaignList
        campaign_list = CampaignList(
            name=f"Result Pattern Test {unique_id}",
            description="Verifies Result object handling",
            is_dynamic=False
        )
        db_session.add(campaign_list)
        db_session.commit()
        
        # Test 1: Simulate what would happen with the old broken code
        # The old code would check `if not campaign_list` where campaign_list is a Result object
        # A Result object is always truthy, so this check would always fail
        with patch('services.campaign_list_service_refactored.CampaignListServiceRefactored.get_campaign_list_by_id') as mock_service:
            # Return a successful Result with our test data
            mock_service.return_value = Result.success(campaign_list)
            
            # Request the page - this should work with the new code
            response = authenticated_client.get(f'/campaigns/lists/{campaign_list.id}')
            
            # Should succeed with proper Result handling
            assert response.status_code == 200
            assert f'Result Pattern Test {unique_id}'.encode() in response.data
            assert b'Verifies Result object handling' in response.data
        
        # Test 2: Demonstrate the fix correctly handles failure Result
        with patch('services.campaign_list_service_refactored.CampaignListServiceRefactored.get_campaign_list_by_id') as mock_service:
            # Return a failed Result
            mock_service.return_value = Result.failure("List not found")
            
            # Request the page - should return 404
            response = authenticated_client.get(f'/campaigns/lists/{campaign_list.id}')
            
            # Should return 404 with proper Result handling
            assert response.status_code == 404
        
        # Test 3: Demonstrate the fix correctly handles success Result with None data
        with patch('services.campaign_list_service_refactored.CampaignListServiceRefactored.get_campaign_list_by_id') as mock_service:
            # Return a successful Result but with None data
            mock_service.return_value = Result.success(None)
            
            # Request the page - should return 404
            response = authenticated_client.get(f'/campaigns/lists/{campaign_list.id}')
            
            # Should return 404 because data is None
            assert response.status_code == 404
    
    def test_result_handling_pattern_understanding(self, authenticated_client, db_session):
        """Understand the Result pattern and demonstrate the fix
        
        This test demonstrates:
        1. How Result objects behave in boolean context (__bool__ returns is_success)
        2. Why explicit checking is better than implicit boolean checks
        3. The importance of checking both success state AND data presence
        """
        from services.common.result import Result
        from crm_database import CampaignList
        
        # Create a Result object (like service would return)
        test_data = CampaignList(name="Test", description="Test")
        success_result = Result.success(test_data)
        failure_result = Result.failure("Not found")
        
        # UNDERSTAND THE ACTUAL RESULT PATTERN:
        # Result objects have __bool__ method that returns is_success
        # So success Results are truthy, failure Results are falsy
        assert bool(success_result) == True   # Success Results are truthy
        assert bool(failure_result) == False  # Failure Results are falsy
        
        # OLD POTENTIALLY BROKEN PATTERN (depending on the issue):
        # If the old code did `if not campaign_list` where campaign_list is Result
        old_check_success = not success_result  # This is False (correct for success)
        old_check_failure = not failure_result  # This is True (correct for failure)
        
        # The old pattern would actually work correctly IF the service returns Result objects!
        assert old_check_success == False    # Success -> don't 404 (correct!)
        assert old_check_failure == True     # Failure -> do 404 (correct!)
        
        # THE ACTUAL ISSUE was probably that the old code expected a plain object, not Result
        # If service returned Result but route expected plain object:
        # - Route check: `if not campaign_list` where campaign_list is a Result
        # - This would work, but then accessing campaign_list.name would fail
        # - The fix is to extract data: campaign_list = list_result.data
        
        # NEW EXPLICIT RESULT PATTERN (what the fix implements):
        # Explicitly check both success state AND data presence
        new_check_success = not success_result.is_success or not success_result.data
        new_check_failure = not failure_result.is_success or not failure_result.data
        
        # Demonstrate the explicit pattern: checks both success state and data
        assert new_check_success == False    # Success with data -> don't 404
        assert new_check_failure == True     # Failure -> do 404
        
        # Test with success Result but None data (important edge case)
        none_data_result = Result.success(None)
        new_check_none_data = not none_data_result.is_success or not none_data_result.data
        assert new_check_none_data == True   # Success but no data -> do 404 (correct!)
        
        # This pattern is more explicit and handles the edge case where
        # service returns success=True but data=None (which should 404)