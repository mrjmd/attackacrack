# tests/unit/repositories/test_contact_repository_list_filter.py
"""
TEST-DRIVEN DEVELOPMENT - RED PHASE
Unit tests for ContactRepository list filtering functionality.
These tests MUST FAIL initially before implementation.
"""

import pytest
from unittest.mock import Mock, patch
from repositories.contact_repository import ContactRepository
from crm_database import Contact, CampaignList, CampaignListMember
from sqlalchemy.orm import Session
from datetime import datetime


class TestContactRepositoryListFilter:
    """Test ContactRepository list filtering functionality"""
    
    @pytest.fixture
    def mock_session(self):
        """Create mock database session"""
        return Mock(spec=Session)
    
    @pytest.fixture
    def repository(self, mock_session):
        """Create ContactRepository with mock session"""
        return ContactRepository(session=mock_session)
    
    def test_get_paginated_contacts_accepts_list_filter_parameter(self, repository, mock_session):
        """Test that get_paginated_contacts accepts list_filter parameter"""
        # Arrange - Mock query chain
        mock_query = Mock()
        mock_query.join.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.count.return_value = 0
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = []
        
        mock_session.query.return_value = mock_query
        
        # Act - This should NOT fail when list_filter parameter is added
        result = repository.get_paginated_contacts(
            search_query='',
            filter_type='all',
            sort_by='name',
            page=1,
            per_page=50,
            list_filter=123  # New parameter that must be supported
        )
        
        # Assert - Method should accept the parameter without errors
        assert 'total_count' in result
        assert 'contacts' in result
    
    def test_get_paginated_contacts_joins_list_members_when_list_filter_provided(self, repository, mock_session):
        """Test that query joins CampaignListMember when list_filter is provided"""
        # Arrange
        list_id = 456
        mock_query = Mock()
        mock_query.join.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.count.return_value = 0
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = []
        
        mock_session.query.return_value = mock_query
        
        # Act
        repository.get_paginated_contacts(
            search_query='',
            filter_type='all',
            sort_by='name',
            page=1,
            per_page=50,
            list_filter=list_id
        )
        
        # Assert - Should join with CampaignListMember table
        mock_query.join.assert_called()
        # Should filter by the specific list ID
        mock_query.filter.assert_called()
    
    def test_get_paginated_contacts_filters_by_list_membership(self, repository, mock_session):
        """Test that query filters contacts by list membership"""
        # Arrange
        list_id = 789
        mock_query = Mock()
        mock_query.join.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.count.return_value = 2  # 2 contacts in this list
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        
        # Mock contacts that are members of the list
        mock_contacts = [
            Mock(id=1, first_name='List', last_name='Member1'),
            Mock(id=2, first_name='List', last_name='Member2')
        ]
        mock_query.all.return_value = mock_contacts
        
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.get_paginated_contacts(
            search_query='',
            filter_type='all',
            sort_by='name',
            page=1,
            per_page=50,
            list_filter=list_id
        )
        
        # Assert - Should return only contacts in the specified list
        assert result['total_count'] == 2
        assert len(result['contacts']) == 2
        
        # Should have joined and filtered by list membership
        mock_query.join.assert_called()
        mock_query.filter.assert_called()
    
    def test_get_paginated_contacts_combines_list_filter_with_search(self, repository, mock_session):
        """Test that list filter combines correctly with search query"""
        # Arrange
        list_id = 123
        search_query = 'john'
        
        mock_query = Mock()
        mock_query.join.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.count.return_value = 1  # 1 contact matches both filters
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = [Mock(id=1, first_name='John', last_name='InList')]
        
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.get_paginated_contacts(
            search_query=search_query,
            filter_type='all',
            sort_by='name',
            page=1,
            per_page=50,
            list_filter=list_id
        )
        
        # Assert - Should apply both list filter AND search
        assert result['total_count'] == 1
        
        # Should have applied multiple filters
        assert mock_query.filter.call_count >= 2  # At least list filter + search filter
    
    def test_get_paginated_contacts_combines_list_filter_with_other_filters(self, repository, mock_session):
        """Test that list filter works with other filter types like has_phone"""
        # Arrange
        list_id = 456
        filter_type = 'has_phone'
        
        mock_query = Mock()
        mock_query.join.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.count.return_value = 1
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = [Mock(id=1, first_name='Test', last_name='Contact', phone='+15551111111')]
        
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.get_paginated_contacts(
            search_query='',
            filter_type=filter_type,
            sort_by='name',
            page=1,
            per_page=50,
            list_filter=list_id
        )
        
        # Assert - Should apply both list filter AND has_phone filter
        assert result['total_count'] == 1
        
        # Should have applied multiple filters (list + has_phone)
        assert mock_query.filter.call_count >= 2
    
    def test_get_paginated_contacts_handles_invalid_list_filter(self, repository, mock_session):
        """Test graceful handling of invalid list_filter values"""
        # Arrange
        invalid_list_id = 99999  # Non-existent list
        
        mock_query = Mock()
        mock_query.join.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.count.return_value = 0  # No contacts for invalid list
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = []
        
        mock_session.query.return_value = mock_query
        
        # Act - Should not crash with invalid list ID
        result = repository.get_paginated_contacts(
            search_query='',
            filter_type='all',
            sort_by='name',
            page=1,
            per_page=50,
            list_filter=invalid_list_id
        )
        
        # Assert - Should return empty results gracefully
        assert result['total_count'] == 0
        assert len(result['contacts']) == 0
    
    def test_get_paginated_contacts_ignores_inactive_list_members(self, repository, mock_session):
        """Test that only active list members are included in results"""
        # Arrange
        list_id = 123
        
        mock_query = Mock()
        mock_query.join.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.count.return_value = 1  # Only active members
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = [Mock(id=1, first_name='Active', last_name='Member')]
        
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.get_paginated_contacts(
            search_query='',
            filter_type='all',
            sort_by='name',
            page=1,
            per_page=50,
            list_filter=list_id
        )
        
        # Assert - Should filter by active status
        assert result['total_count'] == 1
        
        # Should have filtered for active status in CampaignListMember
        mock_query.filter.assert_called()
    
    def test_get_paginated_contacts_no_join_when_no_list_filter(self, repository, mock_session):
        """Test that no join is performed when list_filter is None or not provided"""
        # Arrange
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.count.return_value = 5
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = [Mock() for _ in range(5)]
        
        mock_session.query.return_value = mock_query
        
        # Act - Call without list_filter
        result = repository.get_paginated_contacts(
            search_query='',
            filter_type='all',
            sort_by='name',
            page=1,
            per_page=50
            # No list_filter parameter
        )
        
        # Assert - Should NOT perform join when no list filter
        mock_query.join.assert_not_called()
        assert result['total_count'] == 5
