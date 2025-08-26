# tests/unit/services/test_contact_service_filtered_count.py
"""
TEST-DRIVEN DEVELOPMENT - RED PHASE
Unit tests for ContactService filtered count functionality.
These tests MUST FAIL initially before implementation.
"""

import pytest
from unittest.mock import Mock, patch
from services.contact_service_refactored import ContactService
from repositories.contact_repository import ContactRepository
from crm_database import Contact


class TestContactServiceFilteredCount:
    """Test ContactService returns filtered counts correctly"""
    
    @pytest.fixture
    def mock_repository(self):
        """Create mock repository for testing"""
        return Mock(spec=ContactRepository)
    
    @pytest.fixture
    def contact_service(self, mock_repository):
        """Create ContactService with mocked repository"""
        return ContactService(contact_repository=mock_repository)
    
    def test_get_contacts_page_returns_filtered_count_with_search(self, contact_service, mock_repository):
        """Test that get_contacts_page returns filtered count when search is applied"""
        # Arrange - Mock repository to return filtered results
        mock_contacts = [
            Mock(id=1, first_name='John', last_name='Smith'),
            Mock(id=2, first_name='John', last_name='Doe')
        ]
        
        # Mock repository method should return filtered count (2) not total DB count
        mock_repository.get_paginated_contacts.return_value = {
            'contacts': mock_contacts,
            'total_count': 2,  # This should be FILTERED count, not total DB count
            'page': 1,
            'total_pages': 1,
            'has_prev': False,
            'has_next': False
        }
        
        # Act - Call with search query
        result = contact_service.get_contacts_page(
            search_query='john',
            filter_type='all',
            sort_by='name',
            page=1,
            per_page=50
        )
        
        # Assert - Should return filtered count
        assert result['total_count'] == 2
        assert len(result['contacts']) == 2
        
        # Verify repository was called with correct parameters
        mock_repository.get_paginated_contacts.assert_called_once_with(
            search_query='john',
            filter_type='all',
            sort_by='name',
            page=1,
            per_page=50,
            list_filter=None
        )
    
    def test_get_contacts_page_returns_filtered_count_with_filter_type(self, contact_service, mock_repository):
        """Test that get_contacts_page returns filtered count when filter type is applied"""
        # Arrange - Mock repository to return only contacts with phone
        mock_contacts = [
            Mock(id=1, first_name='Contact', last_name='WithPhone', phone='+15551111111')
        ]
        
        mock_repository.get_paginated_contacts.return_value = {
            'contacts': mock_contacts,
            'total_count': 1,  # Filtered count (only contacts with phone)
            'page': 1,
            'total_pages': 1,
            'has_prev': False,
            'has_next': False
        }
        
        # Act - Call with filter type
        result = contact_service.get_contacts_page(
            search_query='',
            filter_type='has_phone',
            sort_by='name',
            page=1,
            per_page=50
        )
        
        # Assert - Should return filtered count
        assert result['total_count'] == 1
        assert len(result['contacts']) == 1
        
        # Verify repository was called with filter
        mock_repository.get_paginated_contacts.assert_called_once_with(
            search_query='',
            filter_type='has_phone',
            sort_by='name',
            page=1,
            per_page=50,
            list_filter=None
        )
    
    def test_get_contacts_page_returns_full_count_when_no_filters(self, contact_service, mock_repository):
        """Test that get_contacts_page returns full count when no filters are applied"""
        # Arrange - Mock repository to return all contacts
        mock_contacts = [
            Mock(id=1, first_name='Contact', last_name='One'),
            Mock(id=2, first_name='Contact', last_name='Two'),
            Mock(id=3, first_name='Contact', last_name='Three')
        ]
        
        mock_repository.get_paginated_contacts.return_value = {
            'contacts': mock_contacts,
            'total_count': 3,  # Full database count
            'page': 1,
            'total_pages': 1,
            'has_prev': False,
            'has_next': False
        }
        
        # Act - Call with no filters
        result = contact_service.get_contacts_page(
            search_query='',
            filter_type='all',
            sort_by='name',
            page=1,
            per_page=50
        )
        
        # Assert - Should return full count
        assert result['total_count'] == 3
        assert len(result['contacts']) == 3
    
    def test_get_contacts_page_returns_combined_filter_count(self, contact_service, mock_repository):
        """Test filtered count when multiple filters are combined"""
        # Arrange - Mock repository to return contacts matching search AND filter
        mock_contacts = [
            Mock(id=1, first_name='John', last_name='Smith', phone='+15551111111')
        ]
        
        mock_repository.get_paginated_contacts.return_value = {
            'contacts': mock_contacts,
            'total_count': 1,  # Only 1 contact matches both search='john' AND filter='has_phone'
            'page': 1,
            'total_pages': 1,
            'has_prev': False,
            'has_next': False
        }
        
        # Act - Call with both search and filter
        result = contact_service.get_contacts_page(
            search_query='john',
            filter_type='has_phone',
            sort_by='name',
            page=1,
            per_page=50
        )
        
        # Assert - Should return count that matches both filters
        assert result['total_count'] == 1
        assert len(result['contacts']) == 1
        
        # Verify both filters were passed to repository
        mock_repository.get_paginated_contacts.assert_called_once_with(
            search_query='john',
            filter_type='has_phone',
            sort_by='name',
            page=1,
            per_page=50,
            list_filter=None
        )
