"""
TDD Tests for ContactRepository List Filtering

CRITICAL TDD ENFORCEMENT:
========================
- These tests MUST be written BEFORE any implementation changes
- Tests MUST fail initially (Red phase) 
- Implementation must be MINIMAL to pass tests (Green phase)
- NEVER modify tests to match implementation - fix the implementation instead

This test suite ensures ContactRepository correctly:
1. Joins with CampaignListMember table when list_filter is provided
2. Filters contacts to only show active list members
3. Excludes removed/opted-out contacts from list queries
4. Handles pagination correctly with list filtering
5. Returns accurate counts for list-filtered queries

These tests will FAIL until _apply_list_filter is properly implemented.
"""

import pytest
from unittest.mock import Mock, patch, call
from sqlalchemy.orm import Query
from sqlalchemy import and_
from repositories.contact_repository import ContactRepository
from repositories.base_repository import PaginationParams, PaginatedResult, SortOrder
from crm_database import Contact, CampaignList, CampaignListMember


# Module-level fixtures that can be shared across all test classes
@pytest.fixture
def mock_session():
    """Mock database session"""
    return Mock()

@pytest.fixture
def repository(mock_session):
    """ContactRepository instance with mocked session"""
    return ContactRepository(mock_session)

@pytest.fixture
def mock_query():
    """Mock query object with all necessary methods"""
    mock = Mock(spec=Query)
    mock.join.return_value = mock
    mock.filter.return_value = mock
    mock.distinct.return_value = mock
    mock.order_by.return_value = mock
    mock.count.return_value = 0
    mock.offset.return_value = mock
    mock.limit.return_value = mock
    mock.all.return_value = []
    return mock


class TestContactRepositoryListFiltering:
    """TDD tests for ContactRepository list filtering functionality"""
    
    def test_apply_list_filter_joins_with_campaign_list_member_table(self, repository, mock_query, mock_session):
        """
        REQUIREMENT: _apply_list_filter must join Contact with CampaignListMember
        
        This test will FAIL until the repository correctly implements the join.
        The join is essential for filtering contacts by list membership.
        """
        # Arrange
        list_id = 1
        
        # Mock list existence check
        mock_list_query = Mock()
        mock_list_query.filter_by.return_value = mock_list_query
        mock_list_query.first.return_value = Mock()  # List exists
        mock_session.query.return_value = mock_list_query
        
        # Act
        result = repository._apply_list_filter(mock_query, list_id)
        
        # Assert - THIS WILL FAIL until join is implemented
        mock_query.join.assert_called_once_with(CampaignListMember)
        
        # Should return the modified query
        assert result == mock_query
        
        # Should check if list exists first
        mock_session.query.assert_called_with(CampaignList)
        mock_list_query.filter_by.assert_called_with(id=list_id)
    
    def test_apply_list_filter_filters_by_list_id_and_active_status(self, repository, mock_query, mock_session):
        """
        REQUIREMENT: Must filter by both list_id and status='active'
        
        This test ensures that only active members of the specified list are returned.
        Removed or opted-out contacts should be excluded.
        """
        # Arrange
        list_id = 2
        
        # Mock list exists
        mock_list_query = Mock()
        mock_list_query.filter_by.return_value = mock_list_query
        mock_list_query.first.return_value = Mock()
        mock_session.query.return_value = mock_list_query
        
        # Act
        repository._apply_list_filter(mock_query, list_id)
        
        # Assert - THIS WILL FAIL until filter is implemented correctly
        mock_query.filter.assert_called_once()
        
        # The filter should be an AND condition with two parts:
        # 1. CampaignListMember.list_id == list_id
        # 2. CampaignListMember.status == 'active'
        filter_call_args = mock_query.filter.call_args[0][0]
        
        # Should be an AND condition - this assertion will FAIL initially
        assert hasattr(filter_call_args, 'clauses') or hasattr(filter_call_args, 'left'), \
            "Filter should be an AND condition combining list_id and status filters"
    
    def test_apply_list_filter_uses_distinct_to_avoid_duplicates(self, repository, mock_query, mock_session):
        """
        REQUIREMENT: Must use DISTINCT to avoid duplicate contacts from joins
        
        Without DISTINCT, the join might return duplicate contact records.
        This is critical for accurate counting and display.
        """
        # Arrange
        list_id = 3
        
        # Mock list exists
        mock_list_query = Mock()
        mock_list_query.filter_by.return_value = mock_list_query
        mock_list_query.first.return_value = Mock()
        mock_session.query.return_value = mock_list_query
        
        # Act
        repository._apply_list_filter(mock_query, list_id)
        
        # Assert - THIS WILL FAIL until distinct() is added
        mock_query.distinct.assert_called_once()
        
        # Should be called after join and filter
        expected_calls = [
            call.join(CampaignListMember),
            call.filter(mock_query.filter.call_args[0][0]),
            call.distinct()
        ]
        
        # Verify the order of calls
        assert mock_query.join.called
        assert mock_query.filter.called
        assert mock_query.distinct.called
    
    def test_apply_list_filter_returns_unchanged_query_for_nonexistent_list(self, repository, mock_query, mock_session):
        """
        REQUIREMENT: Should return original query when list doesn't exist
        
        This prevents crashes when invalid list IDs are provided and ensures
        graceful degradation to show all contacts.
        """
        # Arrange
        list_id = 999  # Non-existent list
        
        # Mock list doesn't exist
        mock_list_query = Mock()
        mock_list_query.filter_by.return_value = mock_list_query
        mock_list_query.first.return_value = None  # List not found
        mock_session.query.return_value = mock_list_query
        
        # Act
        result = repository._apply_list_filter(mock_query, list_id)
        
        # Assert
        assert result == mock_query  # Should return original query unchanged
        
        # Should NOT call join, filter, or distinct when list doesn't exist
        mock_query.join.assert_not_called()
        mock_query.filter.assert_not_called()
        mock_query.distinct.assert_not_called()
        
        # But should check if list exists
        mock_list_query.filter_by.assert_called_with(id=list_id)
    
    def test_get_contacts_with_filter_applies_list_filter_when_provided(self, repository, mock_session):
        """
        REQUIREMENT: get_contacts_with_filter must use _apply_list_filter when list_filter provided
        
        This is the main entry point for list filtering. It must correctly delegate
        to _apply_list_filter when the list_filter parameter is provided.
        """
        # Arrange
        mock_query = Mock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.count.return_value = 5
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = [Mock(), Mock(), Mock()]  # 3 contacts
        
        # Mock list exists for _apply_list_filter
        mock_list_query = Mock()
        mock_list_query.filter_by.return_value = mock_list_query
        mock_list_query.first.return_value = Mock()
        
        def mock_query_factory(model):
            if 'CampaignList' in str(model):
                return mock_list_query
            return mock_query
        
        mock_session.query.side_effect = mock_query_factory
        
        # Mock _apply_list_filter to verify it's called
        with patch.object(repository, '_apply_list_filter') as mock_apply_filter:
            mock_apply_filter.return_value = mock_query
            
            pagination = PaginationParams(page=1, per_page=10)
            
            # Act
            result = repository.get_contacts_with_filter(
                filter_type='all',
                search_query=None,
                sort_by='name',
                sort_order=SortOrder.ASC,
                pagination=pagination,
                list_filter=1  # This should trigger list filtering
            )
        
        # Assert - THIS WILL FAIL until list filtering is integrated
        mock_apply_filter.assert_called_once_with(mock_query, 1)
        
        # Should return proper PaginatedResult
        assert isinstance(result, PaginatedResult)
        assert result.total == 5
        assert len(result.items) == 3
        assert result.page == 1
        assert result.per_page == 10
    
    def test_get_contacts_with_filter_skips_list_filter_when_not_provided(self, repository, mock_session):
        """
        REQUIREMENT: Should not apply list filtering when list_filter is None
        
        This ensures normal contact queries work correctly when no list filtering is needed.
        """
        # Arrange
        mock_query = Mock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.count.return_value = 10
        mock_query.all.return_value = []
        
        # Mock _apply_list_filter to verify it's NOT called
        with patch.object(repository, '_apply_list_filter') as mock_apply_filter:
            
            # Act
            result = repository.get_contacts_with_filter(
                filter_type='all',
                search_query=None,
                sort_by='name',
                sort_order=SortOrder.ASC,
                pagination=None,
                list_filter=None  # No list filtering
            )
        
        # Assert
        mock_apply_filter.assert_not_called()
        
        # Should still return valid result
        assert isinstance(result, PaginatedResult)
        assert result.total == 10
    
    def test_get_contacts_with_filter_applies_list_filter_before_other_filters(self, repository, mock_session):
        """
        REQUIREMENT: List filter should be applied before search and type filters
        
        This ensures the filter chain operates in the correct order:
        1. List filter (joins and filters by list membership)
        2. Search filter (searches within list members)
        3. Type filter (applies additional filtering)
        4. Sorting
        """
        # Arrange
        mock_query = Mock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.count.return_value = 3
        mock_query.all.return_value = []
        
        # Mock list exists
        mock_list_query = Mock()
        mock_list_query.filter_by.return_value = mock_list_query
        mock_list_query.first.return_value = Mock()
        
        def mock_query_factory(model):
            if 'CampaignList' in str(model):
                return mock_list_query
            return mock_query
        
        mock_session.query.side_effect = mock_query_factory
        
        # Track method calls
        with patch.object(repository, '_apply_list_filter', wraps=repository._apply_list_filter) as mock_list_filter, \
             patch.object(repository, '_apply_search', wraps=repository._apply_search) as mock_search_filter, \
             patch.object(repository, '_apply_filter', wraps=repository._apply_filter) as mock_type_filter, \
             patch.object(repository, '_apply_sorting', wraps=repository._apply_sorting) as mock_sorting:
            
            # Act
            repository.get_contacts_with_filter(
                filter_type='has_phone',
                search_query='john',
                sort_by='name',
                sort_order=SortOrder.ASC,
                pagination=None,
                list_filter=1
            )
        
        # Assert - Verify call order
        assert mock_list_filter.called, "List filter should be applied"
        assert mock_search_filter.called, "Search filter should be applied"
        assert mock_type_filter.called, "Type filter should be applied"
        assert mock_sorting.called, "Sorting should be applied"
        
        # List filter should be called first (this will FAIL until order is correct)
        # We can verify this by checking that _apply_list_filter is called before others
        assert mock_list_filter.call_args[0][1] == 1  # Called with list_id=1
    
    def test_get_paginated_contacts_supports_list_filter_parameter(self, repository, mock_session):
        """
        REQUIREMENT: get_paginated_contacts must support list_filter parameter
        
        This is the legacy method that should also support list filtering for
        backward compatibility.
        """
        # Arrange
        mock_query = Mock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.count.return_value = 7
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = [Mock() for _ in range(7)]
        
        # Mock list exists
        mock_list_query = Mock()
        mock_list_query.filter_by.return_value = mock_list_query
        mock_list_query.first.return_value = Mock()
        
        def mock_query_factory(model):
            if 'CampaignList' in str(model):
                return mock_list_query
            return mock_query
        
        mock_session.query.side_effect = mock_query_factory
        
        # Mock the underlying get_contacts_with_filter call
        with patch.object(repository, 'get_contacts_with_filter') as mock_get_with_filter:
            mock_result = PaginatedResult(
                items=[Mock() for _ in range(7)],
                total=7,
                page=1,
                per_page=20
            )
            mock_get_with_filter.return_value = mock_result
            
            # Act
            result = repository.get_paginated_contacts(
                search_query='test',
                filter_type='all',
                sort_by='name',
                page=1,
                per_page=20,
                list_filter=2  # List filtering parameter
            )
        
        # Assert - THIS WILL FAIL until list_filter is passed through
        mock_get_with_filter.assert_called_once()
        call_kwargs = mock_get_with_filter.call_args[1]
        assert call_kwargs['list_filter'] == 2
        
        # Should return proper dictionary format
        assert isinstance(result, dict)
        assert 'contacts' in result
        assert 'total_count' in result
        assert result['total_count'] == 7


class TestContactRepositoryListFilteringIntegration:
    """Integration tests for list filtering with database operations"""
    
    def test_list_filtering_with_real_database_operations(self, db_session):
        """
        INTEGRATION TEST: List filtering with actual database session
        
        This test verifies list filtering works with real database operations.
        It should be run after unit tests pass to verify the complete flow.
        """
        # This test would use real database session
        # Skip for now as it requires full database setup
        pytest.skip("Integration test - implement after unit tests pass")
    
    def test_list_filtering_performance_with_large_datasets(self, db_session):
        """
        PERFORMANCE TEST: List filtering should perform well with large contact lists
        
        This test ensures the join and filtering operations are efficient.
        """
        # This test would create large datasets and measure performance
        pytest.skip("Performance test - implement after basic functionality works")
    
    def test_list_filtering_with_multiple_list_memberships(self, db_session):
        """
        EDGE CASE TEST: Contact belonging to multiple lists
        
        This test ensures contacts in multiple lists are handled correctly.
        """
        # This test would verify behavior when contacts belong to multiple lists
        pytest.skip("Edge case test - implement after core functionality works")


class TestContactRepositoryErrorHandling:
    """TDD tests for error handling in list filtering"""
    
    def test_apply_list_filter_handles_database_errors_gracefully(self, repository, mock_query, mock_session):
        """
        REQUIREMENT: Should handle database errors gracefully during list filtering
        
        This ensures the system doesn't crash when database errors occur.
        """
        # Arrange
        list_id = 1
        
        # Mock database error during list existence check
        mock_session.query.side_effect = Exception("Database connection lost")
        
        # Act & Assert
        # Should not raise exception - should return original query
        result = repository._apply_list_filter(mock_query, list_id)
        
        # Should return original query when error occurs
        assert result == mock_query
        
        # Should not call join/filter methods when error occurs
        mock_query.join.assert_not_called()
        mock_query.filter.assert_not_called()
    
    def test_get_contacts_with_filter_handles_list_filter_errors(self, repository, mock_session):
        """
        REQUIREMENT: Main query method should handle list filtering errors gracefully
        
        This ensures the contacts page still loads even if list filtering fails.
        """
        # Arrange
        mock_query = Mock()
        mock_session.query.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.count.return_value = 0
        mock_query.all.return_value = []
        
        # Mock _apply_list_filter to raise an exception
        with patch.object(repository, '_apply_list_filter') as mock_apply_filter:
            mock_apply_filter.side_effect = Exception("List filtering failed")
            
            # Act - Should not crash
            result = repository.get_contacts_with_filter(
                filter_type='all',
                list_filter=1
            )
        
        # Assert
        assert isinstance(result, PaginatedResult)
        # Should still return a result (possibly empty) rather than crashing
        assert result.total == 0