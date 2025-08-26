# tests/unit/services/test_contact_service_list_filter.py
"""
TEST-DRIVEN DEVELOPMENT - RED PHASE
Unit tests for ContactService list filtering functionality.
These tests MUST FAIL initially before implementation.
"""

import pytest
from unittest.mock import Mock, patch
from services.contact_service_refactored import ContactService
from repositories.contact_repository import ContactRepository
from repositories.campaign_repository import CampaignRepository
from crm_database import Contact, CampaignList


class TestContactServiceListFilter:
    """Test ContactService list filtering functionality"""
    
    @pytest.fixture
    def mock_contact_repository(self):
        """Create mock contact repository for testing"""
        return Mock(spec=ContactRepository)
    
    @pytest.fixture
    def mock_campaign_repository(self):
        """Create mock campaign repository for testing"""
        return Mock(spec=CampaignRepository)
    
    @pytest.fixture
    def contact_service(self, mock_contact_repository, mock_campaign_repository):
        """Create ContactService with mocked repositories"""
        return ContactService(
            contact_repository=mock_contact_repository,
            campaign_repository=mock_campaign_repository
        )
    
    def test_get_contacts_page_accepts_list_filter_parameter(self, contact_service, mock_contact_repository):
        """Test that get_contacts_page method accepts list_filter parameter"""
        # Arrange
        mock_contacts = [Mock(id=1, first_name='Test', last_name='Contact')]
        mock_contact_repository.get_paginated_contacts.return_value = {
            'contacts': mock_contacts,
            'total_count': 1,
            'page': 1,
            'total_pages': 1,
            'has_prev': False,
            'has_next': False
        }
        
        # Act - This should NOT fail when list_filter parameter is added
        result = contact_service.get_contacts_page(
            search_query='',
            filter_type='all',
            sort_by='name',
            page=1,
            per_page=50,
            list_filter=123  # New parameter that must be supported
        )
        
        # Assert - Method should accept the parameter without errors
        assert result is not None
        assert 'total_count' in result
    
    def test_get_contacts_page_passes_list_filter_to_repository(self, contact_service, mock_contact_repository):
        """Test that list_filter parameter is passed to repository method"""
        # Arrange
        list_id = 456
        mock_contact_repository.get_paginated_contacts.return_value = {
            'contacts': [],
            'total_count': 0,
            'page': 1,
            'total_pages': 0,
            'has_prev': False,
            'has_next': False
        }
        
        # Act
        contact_service.get_contacts_page(
            search_query='test',
            filter_type='has_phone',
            sort_by='name',
            page=1,
            per_page=25,
            list_filter=list_id
        )
        
        # Assert - Repository method should be called with list_filter
        mock_contact_repository.get_paginated_contacts.assert_called_once_with(
            search_query='test',
            filter_type='has_phone',
            sort_by='name',
            page=1,
            per_page=25,
            list_filter=list_id  # This parameter must be passed through
        )
    
    def test_get_contacts_page_handles_none_list_filter(self, contact_service, mock_contact_repository):
        """Test that None/empty list_filter is handled correctly"""
        # Arrange
        mock_contact_repository.get_paginated_contacts.return_value = {
            'contacts': [],
            'total_count': 0,
            'page': 1,
            'total_pages': 0,
            'has_prev': False,
            'has_next': False
        }
        
        # Act - Call without list_filter (should default to None or 'all')
        contact_service.get_contacts_page(
            search_query='',
            filter_type='all',
            sort_by='name',
            page=1,
            per_page=50
        )
        
        # Assert - Should pass None or default value for list_filter
        args, kwargs = mock_contact_repository.get_paginated_contacts.call_args
        
        # Should either have list_filter=None in kwargs or be called with positional args
        # The exact implementation will depend on how we handle the default
        assert mock_contact_repository.get_paginated_contacts.called
    
    def test_get_contacts_page_filters_by_specific_list(self, contact_service, mock_contact_repository):
        """Test filtering contacts by specific list returns only list members"""
        # Arrange - Mock repository to return only contacts in specific list
        list_id = 789
        mock_list_contacts = [
            Mock(id=1, first_name='List', last_name='Member1'),
            Mock(id=2, first_name='List', last_name='Member2')
        ]
        
        mock_contact_repository.get_paginated_contacts.return_value = {
            'contacts': mock_list_contacts,
            'total_count': 2,  # Only contacts in this list
            'page': 1,
            'total_pages': 1,
            'has_prev': False,
            'has_next': False
        }
        
        # Act - Filter by specific list
        result = contact_service.get_contacts_page(
            search_query='',
            filter_type='all',
            sort_by='name',
            page=1,
            per_page=50,
            list_filter=list_id
        )
        
        # Assert - Should return only contacts in the list
        assert result['total_count'] == 2
        assert len(result['contacts']) == 2
        
        # Verify repository was called with list filter
        mock_contact_repository.get_paginated_contacts.assert_called_once_with(
            search_query='',
            filter_type='all',
            sort_by='name',
            page=1,
            per_page=50,
            list_filter=list_id
        )
    
    def test_get_contacts_page_combines_list_filter_with_search(self, contact_service, mock_contact_repository):
        """Test that list filter works in combination with search"""
        # Arrange
        list_id = 123
        mock_contact_repository.get_paginated_contacts.return_value = {
            'contacts': [Mock(id=1, first_name='John', last_name='InList')],
            'total_count': 1,  # Only 1 contact matches both list filter AND search
            'page': 1,
            'total_pages': 1,
            'has_prev': False,
            'has_next': False
        }
        
        # Act - Combine list filter with search
        result = contact_service.get_contacts_page(
            search_query='john',
            filter_type='all',
            sort_by='name',
            page=1,
            per_page=50,
            list_filter=list_id
        )
        
        # Assert - Should return filtered results
        assert result['total_count'] == 1
        
        # Verify both filters were applied
        mock_contact_repository.get_paginated_contacts.assert_called_once_with(
            search_query='john',
            filter_type='all',
            sort_by='name',
            page=1,
            per_page=50,
            list_filter=list_id
        )
    
    def test_get_contacts_page_combines_list_filter_with_other_filters(self, contact_service, mock_contact_repository):
        """Test that list filter works with other filter types"""
        # Arrange
        list_id = 456
        mock_contact_repository.get_paginated_contacts.return_value = {
            'contacts': [Mock(id=1, first_name='Test', last_name='Contact', phone='+15551111111')],
            'total_count': 1,  # Contacts in list AND with phone
            'page': 1,
            'total_pages': 1,
            'has_prev': False,
            'has_next': False
        }
        
        # Act - Combine list filter with has_phone filter
        result = contact_service.get_contacts_page(
            search_query='',
            filter_type='has_phone',
            sort_by='name',
            page=1,
            per_page=50,
            list_filter=list_id
        )
        
        # Assert - Should return contacts matching both filters
        assert result['total_count'] == 1
        
        # Verify all filters were applied
        mock_contact_repository.get_paginated_contacts.assert_called_once_with(
            search_query='',
            filter_type='has_phone',
            sort_by='name',
            page=1,
            per_page=50,
            list_filter=list_id
        )
    
    def test_get_available_lists_method_exists(self, contact_service, mock_campaign_repository):
        """Test that service provides method to get available lists for dropdown"""
        # Arrange - Mock campaign repository to return available lists
        mock_lists = [
            Mock(id=1, name='VIP Customers', description='High value customers'),
            Mock(id=2, name='New Leads', description='Recently acquired leads')
        ]
        mock_campaign_repository.get_all_lists.return_value = mock_lists
        
        # Act - This method should exist on the service
        result = contact_service.get_available_lists()
        
        # Assert - Should return list of available campaign lists
        assert result == mock_lists
        mock_campaign_repository.get_all_lists.assert_called_once()
    
    def test_get_available_lists_handles_repository_errors(self, contact_service, mock_campaign_repository):
        """Test that get_available_lists handles repository errors gracefully"""
        # Arrange - Mock repository to raise exception
        mock_campaign_repository.get_all_lists.side_effect = Exception("Database error")
        
        # Act - Should not crash when repository fails
        result = contact_service.get_available_lists()
        
        # Assert - Should return empty list on error
        assert result == []
