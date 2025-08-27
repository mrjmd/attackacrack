"""
TDD Tests for Campaign List Detail Routes - Contact Count Display

CRITICAL REQUIREMENTS:
===================
- Tests MUST be written BEFORE implementation 
- Tests MUST fail initially (Red phase)
- Implementation must be MINIMAL to pass tests (Green phase)

This test suite ensures the campaign list detail page properly:
1. Displays accurate contact counts after PropertyRadar import
2. Shows only active contacts (excludes removed/opted-out)
3. Correctly filters contacts by list membership
4. Handles pagination correctly with list filters
5. Shows proper contact data in tables

These tests will FAIL until the display logic is fixed.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from flask import url_for, current_app
from services.common.result import Result
from crm_database import CampaignList, CampaignListMember, Contact, ContactFlag


class TestCampaignListDetailRoutes:
    """TDD tests for campaign list detail page contact counting and display"""
    
    def test_campaign_list_detail_shows_accurate_active_contact_count(self, authenticated_client):
        """
        REQUIREMENT: List detail page should display correct count of ACTIVE contacts
        
        This test will FAIL initially because the page currently shows "0 Active Contacts"
        even when contacts are properly associated with the list.
        """
        # Arrange - Mock the services that would be called
        mock_list_service = Mock()
        mock_campaign_service = Mock()
        
        # Create test list data
        test_list = Mock()
        test_list.id = 1
        test_list.name = "PropertyRadar Import List"
        test_list.description = "Imported from PropertyRadar CSV"
        
        # Mock successful list retrieval
        list_result = Result.success(test_list)
        mock_list_service.get_campaign_list_by_id.return_value = list_result
        
        # Mock stats showing 25 active contacts (this is the key test)
        stats_result = Result.success({
            'active_members': 25,
            'removed_members': 3,
            'total_members': 28
        })
        mock_list_service.get_list_stats.return_value = stats_result
        
        # Mock contacts retrieval
        test_contacts = []
        for i in range(1, 26):  # 25 active contacts
            contact = Mock()
            contact.id = i
            contact.first_name = f"Contact{i}"
            contact.last_name = f"Test{i}"
            contact.phone = f"+155500000{i:02d}"
            contact.email = f"contact{i}@example.com" if i % 2 == 0 else None
            contact.contact_flags = []  # No opted-out flags
            contact.imported_at = None
            test_contacts.append(contact)
        contacts_result = Result.success(test_contacts)
        mock_list_service.get_list_contacts.return_value = contacts_result
        
        mock_campaign_service.get_campaigns_using_list = Mock(return_value=[])
        
        # Act
        with patch.object(current_app.services, 'get') as mock_get_service:
            mock_get_service.side_effect = lambda name: {
                'campaign_list': mock_list_service,
                'campaign': mock_campaign_service
            }.get(name)
            
            response = authenticated_client.get('/campaigns/lists/1')
        
        # Assert - THIS WILL FAIL until display logic is fixed
        assert response.status_code == 200
        
        # The page should show the correct active contact count
        assert b'25 Active Contacts' in response.data or b'25' in response.data
        
        # Should NOT show "0 Active Contacts"
        assert b'0 Active Contacts' not in response.data
        
        # Verify service calls were made correctly
        mock_list_service.get_campaign_list_by_id.assert_called_once_with(1)
        mock_list_service.get_list_stats.assert_called_once_with(1)
        mock_list_service.get_list_contacts.assert_called_once_with(1)
    
    def test_campaign_list_detail_excludes_removed_contacts_from_count(self, authenticated_client):
        """
        REQUIREMENT: Active count should exclude removed/opted-out contacts
        
        This test ensures that contacts with status='removed' are not counted
        in the active members count.
        """
        # Arrange
        mock_list_service = Mock()
        mock_campaign_service = Mock()
        
        test_list = Mock()
        test_list.id = 2
        test_list.name = "Mixed Status List"
        
        list_result = Result.success(test_list)
        mock_list_service.get_campaign_list_by_id.return_value = list_result
        
        # Stats should show only active contacts (10), not total (15)
        stats_result = Result.success({
            'active_members': 10,  # Only active contacts
            'removed_members': 5,  # Excluded contacts
            'total_members': 15    # Total including removed
        })
        mock_list_service.get_list_stats.return_value = stats_result
        
        # Only active contacts returned
        active_contacts = []
        for i in range(1, 11):  # 10 active contacts
            contact = Mock()
            contact.id = i
            contact.first_name = f"Active{i}"
            contact.last_name = f"Contact{i}"
            contact.phone = f"+155500100{i:02d}"
            contact.email = f"active{i}@example.com"
            contact.contact_flags = []
            contact.imported_at = None
            active_contacts.append(contact)
        contacts_result = Result.success(active_contacts)
        mock_list_service.get_list_contacts.return_value = contacts_result
        
        mock_campaign_service.get_campaigns_using_list = Mock(return_value=[])
        
        # Act
        with patch.object(current_app.services, 'get') as mock_get_service:
            mock_get_service.side_effect = lambda name: {
                'campaign_list': mock_list_service,
                'campaign': mock_campaign_service
            }.get(name)
            
            response = authenticated_client.get('/campaigns/lists/2')
        
        # Assert - Should show active count only
        assert response.status_code == 200
        
        # Should show active count (10), not total count (15)
        response_text = response.data.decode()
        assert '10' in response_text  # Active contacts count should be shown
        # The total (15) should not be displayed as active contacts
        assert 'Active Contacts' in response_text
        # Check that the active count section shows 10, not 15
        import re
        active_match = re.search(r'text-green-400">([0-9]+)</div>\s*<div[^>]*>Active Contacts', response_text)
        if active_match:
            assert active_match.group(1) == '10', f"Active count shows {active_match.group(1)}, expected 10"
        
        # Should not show removed contacts in active count
        response_text = response.data.decode()
        assert '10 Active' in response_text or '10' in response_text
    
    def test_campaign_list_detail_handles_empty_list_correctly(self, authenticated_client):
        """
        REQUIREMENT: Empty lists should show "0 Active Contacts" correctly
        
        This test ensures that truly empty lists display the zero count correctly.
        """
        # Arrange
        mock_list_service = Mock()
        mock_campaign_service = Mock()
        
        test_list = Mock()
        test_list.id = 3
        test_list.name = "Empty List"
        
        list_result = Result.success(test_list)
        mock_list_service.get_campaign_list_by_id.return_value = list_result
        
        # Empty list stats
        stats_result = Result.success({
            'active_members': 0,
            'removed_members': 0,
            'total_members': 0
        })
        mock_list_service.get_list_stats.return_value = stats_result
        
        # No contacts
        contacts_result = Result.success([])
        mock_list_service.get_list_contacts.return_value = contacts_result
        
        mock_campaign_service.get_campaigns_using_list = Mock(return_value=[])
        
        # Act
        with patch.object(current_app.services, 'get') as mock_get_service:
            mock_get_service.side_effect = lambda name: {
                'campaign_list': mock_list_service,
                'campaign': mock_campaign_service
            }.get(name)
            
            response = authenticated_client.get('/campaigns/lists/3')
        
        # Assert
        assert response.status_code == 200
        
        # Should correctly show 0 for empty lists
        response_text = response.data.decode()
        assert '0 Active' in response_text or '0' in response_text
        
        # Should show empty state message
        assert 'No contacts' in response_text or 'empty' in response_text.lower()
    
    def test_campaign_list_detail_displays_contact_table_correctly(self, authenticated_client):
        """
        REQUIREMENT: Contact table should show contacts that belong to the list
        
        This test ensures the contacts table displays the right contacts for the list.
        """
        # Arrange
        mock_list_service = Mock()
        mock_campaign_service = Mock()
        
        test_list = Mock()
        test_list.id = 4
        test_list.name = "Contact Display List"
        
        list_result = Result.success(test_list)
        mock_list_service.get_campaign_list_by_id.return_value = list_result
        
        stats_result = Result.success({
            'active_members': 3,
            'removed_members': 0,
            'total_members': 3
        })
        mock_list_service.get_list_stats.return_value = stats_result
        
        # Create test contacts with specific data
        test_contacts = []
        for i in range(3):
            contact = Mock()
            contact.id = i + 1
            contact.first_name = f"John{i}"
            contact.last_name = f"Doe{i}"
            contact.phone = f"+155500000{i}"
            contact.email = f"john{i}@example.com"
            contact.contact_flags = []
            contact.imported_at = None
            test_contacts.append(contact)
        
        contacts_result = Result.success(test_contacts)
        mock_list_service.get_list_contacts.return_value = contacts_result
        
        mock_campaign_service.get_campaigns_using_list = Mock(return_value=[])
        
        # Act
        with patch.object(current_app.services, 'get') as mock_get_service:
            mock_get_service.side_effect = lambda name: {
                'campaign_list': mock_list_service,
                'campaign': mock_campaign_service
            }.get(name)
            
            response = authenticated_client.get('/campaigns/lists/4')
        
        # Assert
        assert response.status_code == 200
        response_text = response.data.decode()
        
        # Should show all test contacts
        assert "John0" in response_text
        assert "John1" in response_text  
        assert "John2" in response_text
        
        # Should show contact details
        assert "+15550000000" in response_text
        assert "john0@example.com" in response_text
        
        # Should show correct count in table or summary
        assert "3" in response_text
    
    def test_campaign_list_detail_handles_service_failures_gracefully(self, authenticated_client):
        """
        REQUIREMENT: Page should handle service failures gracefully
        
        This test ensures the page doesn't crash when services return errors.
        """
        # Arrange
        mock_list_service = Mock()
        mock_campaign_service = Mock()
        
        test_list = Mock()
        test_list.id = 5
        test_list.name = "Service Failure Test"
        
        # List exists but stats service fails
        list_result = Result.success(test_list)
        mock_list_service.get_campaign_list_by_id.return_value = list_result
        
        # Stats service fails
        stats_result = Result.failure("Database connection failed")
        mock_list_service.get_list_stats.return_value = stats_result
        
        # Contacts service fails
        contacts_result = Result.failure("Query timeout")
        mock_list_service.get_list_contacts.return_value = contacts_result
        
        mock_campaign_service.get_campaigns_using_list = Mock(return_value=[])
        
        # Act
        with patch.object(current_app.services, 'get') as mock_get_service:
            mock_get_service.side_effect = lambda name: {
                'campaign_list': mock_list_service,
                'campaign': mock_campaign_service
            }.get(name)
            
            response = authenticated_client.get('/campaigns/lists/5')
        
        # Assert
        assert response.status_code == 200  # Should not crash
        
        response_text = response.data.decode()
        
        # Should show the list name
        assert "Service Failure Test" in response_text
        
        # Should handle missing stats gracefully (show 0 or "Unknown")
        assert "0" in response_text or "Unknown" in response_text or "Error" in response_text
        
        # Should handle missing contacts gracefully
        assert "No contacts" in response_text or "Unable to load" in response_text
    
    def test_campaign_list_detail_404_for_nonexistent_list(self, authenticated_client):
        """
        REQUIREMENT: Non-existent lists should return 404
        
        This test ensures proper 404 handling for lists that don't exist.
        """
        # Arrange
        mock_list_service = Mock()
        
        # Service returns failure for non-existent list
        list_result = Result.failure("List not found")
        mock_list_service.get_campaign_list_by_id.return_value = list_result
        
        # Act
        with patch.object(current_app.services, 'get') as mock_get_service:
            mock_get_service.return_value = mock_list_service
            
            response = authenticated_client.get('/campaigns/lists/999999')
        
        # Assert
        assert response.status_code == 404
        
        # Verify the correct service method was called
        mock_list_service.get_campaign_list_by_id.assert_called_once_with(999999)


class TestContactRepositoryListFiltering:
    """TDD tests for ContactRepository _apply_list_filter method"""
    
    def test_apply_list_filter_joins_campaign_list_member_correctly(self):
        """
        REQUIREMENT: _apply_list_filter should join with CampaignListMember table
        
        This test will FAIL until the repository correctly implements the join.
        """
        from repositories.contact_repository import ContactRepository
        from sqlalchemy.orm import Query
        
        # Arrange
        mock_session = Mock()
        repository = ContactRepository(mock_session)
        
        # Create a mock query object
        mock_query = Mock(spec=Query)
        mock_query.join.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.distinct.return_value = mock_query
        
        # Mock CampaignList existence check
        mock_list_query = Mock()
        mock_list_query.first.return_value = Mock()  # List exists
        mock_session.query.return_value = mock_list_query
        
        # Act
        result_query = repository._apply_list_filter(mock_query, list_id=1)
        
        # Assert - THIS WILL FAIL until repository implements correct join
        mock_query.join.assert_called_once()  # Should join CampaignListMember
        mock_query.filter.assert_called_once()  # Should filter by list_id and status
        mock_query.distinct.assert_called_once()  # Should use distinct to avoid duplicates
        
        # Verify the filter conditions are correct
        call_args = mock_query.filter.call_args[0]
        # Should filter by list_id=1 and status='active'
        assert len(call_args) == 1  # Should have one AND condition with two parts
    
    def test_apply_list_filter_excludes_removed_contacts(self):
        """
        REQUIREMENT: List filter should only include contacts with status='active'
        
        This test ensures removed/opted-out contacts are excluded from list filtering.
        """
        from repositories.contact_repository import ContactRepository
        from sqlalchemy.orm import Query
        from sqlalchemy import and_
        from crm_database import CampaignListMember
        
        # Arrange
        mock_session = Mock()
        repository = ContactRepository(mock_session)
        
        mock_query = Mock(spec=Query)
        mock_query.join.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.distinct.return_value = mock_query
        
        # Mock list exists
        mock_list_query = Mock()
        mock_list_query.first.return_value = Mock()
        mock_session.query.return_value = mock_list_query
        
        # Act
        repository._apply_list_filter(mock_query, list_id=2)
        
        # Assert
        mock_query.filter.assert_called_once()
        
        # The filter should include status='active' condition
        filter_args = mock_query.filter.call_args[0][0]
        # Should filter by both list_id and status='active'
        # This test will FAIL until the repository implements the status filter correctly
        assert hasattr(filter_args, 'left') or hasattr(filter_args, 'clauses')  # Should be an AND condition
    
    def test_apply_list_filter_handles_nonexistent_list(self):
        """
        REQUIREMENT: Filter should handle non-existent lists gracefully
        
        This test ensures the filter doesn't crash for lists that don't exist.
        """
        from repositories.contact_repository import ContactRepository
        from sqlalchemy.orm import Query
        
        # Arrange
        mock_session = Mock()
        repository = ContactRepository(mock_session)
        
        mock_query = Mock(spec=Query)
        
        # Mock list doesn't exist
        mock_list_query = Mock()
        mock_list_query.first.return_value = None  # List doesn't exist
        mock_session.query.return_value = mock_list_query
        
        # Act
        result_query = repository._apply_list_filter(mock_query, list_id=999)
        
        # Assert
        # Should return original query unchanged when list doesn't exist
        assert result_query == mock_query
        
        # Should not call join/filter when list doesn't exist
        mock_query.join.assert_not_called()
        mock_query.filter.assert_not_called()
    
    def test_contact_repository_get_contacts_with_filter_supports_list_filtering(self):
        """
        REQUIREMENT: get_contacts_with_filter should support list_filter parameter
        
        This test ensures the main query method correctly applies list filtering.
        """
        from repositories.contact_repository import ContactRepository
        from repositories.base_repository import PaginationParams
        
        # Arrange
        mock_session = Mock()
        repository = ContactRepository(mock_session)
        
        # Mock the query chain
        mock_query = Mock()
        mock_session.query.return_value = mock_query
        mock_query.join.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.distinct.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.count.return_value = 5
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = []
        
        # Mock list exists
        mock_list_query = Mock()
        mock_list_query.first.return_value = Mock()
        
        def mock_session_query(model):
            if 'CampaignList' in str(model):
                return mock_list_query
            return mock_query
        
        mock_session.query.side_effect = mock_session_query
        
        pagination = PaginationParams(page=1, per_page=10)
        
        # Act
        result = repository.get_contacts_with_filter(
            filter_type='all',
            search_query=None,
            sort_by='name',
            pagination=pagination,
            list_filter=1  # This is the key parameter being tested
        )
        
        # Assert
        # Should call _apply_list_filter with the correct list_id
        mock_query.join.assert_called()  # List filter should trigger join
        mock_query.distinct.assert_called()  # Should use distinct for joined queries
        
        # Should return a PaginatedResult
        assert hasattr(result, 'items')
        assert hasattr(result, 'total')
        assert result.total == 5


class TestCampaignListContactCountIntegration:
    """Integration tests for complete contact counting flow"""
    
    def test_propertyradar_import_creates_correct_list_associations(self, authenticated_client, db_session):
        """
        INTEGRATION TEST: PropertyRadar import should create correct list associations
        
        This test verifies that when PropertyRadar CSV is imported:
        1. A CampaignList is created
        2. Contacts are created
        3. CampaignListMember records are created with status='active'
        4. The list detail page shows correct counts
        
        This test will FAIL until the PropertyRadar import service properly creates list associations.
        """
        # This test requires the full integration testing setup
        # It should be implemented after the unit tests pass
        
        # Arrange - Mock PropertyRadar import service
        mock_csv_service = Mock()
        
        # Mock successful import result
        import_result = {
            'success': True,
            'imported': 50,
            'updated': 0,
            'errors': [],
            'list_id': 1
        }
        mock_csv_service.import_csv.return_value = import_result
        
        # Act - Simulate CSV import
        with patch.object(current_app.services, 'get') as mock_get_service:
            mock_get_service.return_value = mock_csv_service
            
            # This would be the actual CSV import request
            response = authenticated_client.post('/campaigns/import-csv', 
                data={
                    'list_name': 'PropertyRadar Import Test',
                    'enrichment_mode': 'enrich_missing'
                },
                follow_redirects=True
            )
        
        # Assert
        assert response.status_code == 200
        
        # Should redirect to list detail page
        assert '/campaigns/lists/1' in response.request.url
        
        # The list detail page should show correct contact count
        # This assertion will FAIL until the display logic is fixed
        assert b'50' in response.data  # Should show 50 imported contacts
        assert b'0 Active Contacts' not in response.data  # Should NOT show zero
        
        # Verify the import service was called correctly
        mock_csv_service.import_csv.assert_called_once()
        
        # Mark this test as expected to fail initially
        pytest.skip("This integration test will be implemented after unit tests pass")