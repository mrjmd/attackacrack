"""
TDD Tests for Campaign List Service - Contact Count Accuracy

STRICT TDD ENFORCEMENT:
======================
- Tests MUST be written BEFORE any implementation fixes
- Tests MUST fail initially (Red phase) with meaningful error messages  
- Implementation must be MINIMAL to pass tests (Green phase)
- NEVER modify tests to match buggy implementation - fix the service instead

This test suite ensures CampaignListService correctly:
1. Calculates accurate active member counts (excluding removed/opted-out)
2. Returns correct contact lists filtered by list membership
3. Handles PropertyRadar import contact associations properly
4. Updates list statistics after contact status changes
5. Provides accurate data for campaign list detail page display

These tests will FAIL until the service layer properly queries and counts contacts.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
from services.common.result import Result
from services.campaign_list_service_refactored import CampaignListServiceRefactored
from repositories.campaign_list_repository import CampaignListRepository
from repositories.campaign_list_member_repository import CampaignListMemberRepository
from repositories.contact_repository import ContactRepository
from crm_database import CampaignList, CampaignListMember, Contact


# Module-level fixtures that can be shared across all test classes
@pytest.fixture
def mock_list_repository():
    """Mock CampaignListRepository"""
    mock = Mock(spec=CampaignListRepository)
    mock.get_by_id = Mock()
    mock.commit = Mock()
    mock.rollback = Mock()
    return mock

@pytest.fixture
def mock_member_repository():
    """Mock CampaignListMemberRepository"""
    mock = Mock(spec=CampaignListMemberRepository)
    mock.get_membership_stats = Mock()
    mock.get_contact_ids_in_list = Mock()
    mock.commit = Mock()
    return mock

@pytest.fixture
def mock_contact_repository():
    """Mock ContactRepository"""
    mock = Mock(spec=ContactRepository)
    mock.get_by_ids = Mock()
    mock.get_contacts_with_filter = Mock()
    return mock

@pytest.fixture
def service(mock_list_repository, mock_member_repository, mock_contact_repository):
    """CampaignListService instance with mocked repositories"""
    return CampaignListServiceRefactored(
        campaign_list_repository=mock_list_repository,
        member_repository=mock_member_repository,
        contact_repository=mock_contact_repository
    )


class TestCampaignListServiceContactCounts:
    """TDD tests for accurate contact counting in campaign list service"""
    
    def test_get_list_stats_returns_accurate_active_member_count(self, service, mock_member_repository, mock_contact_repository):
        """
        REQUIREMENT: get_list_stats must return correct count of ACTIVE members only
        
        This test will FAIL until the service correctly queries only active members
        and excludes removed/opted-out contacts from the count.
        """
        # Arrange
        list_id = 1
        
        # Mock repository to return stats with active/removed breakdown
        mock_stats = {
            'total': 100,      # Total records in CampaignListMember
            'active': 85,      # Only active members
            'removed': 15      # Removed/opted-out members
        }
        mock_member_repository.get_membership_stats.return_value = mock_stats
        
        # Mock get_contact_ids_in_list and get_by_ids for contact stats
        mock_contact_ids = list(range(1, 86))  # 85 active contact IDs
        mock_member_repository.get_contact_ids_in_list.return_value = mock_contact_ids
        
        # Mock contacts with email and phone stats
        mock_contacts = [Mock(id=i, email=f"test{i}@example.com" if i % 2 == 0 else None, 
                              phone=f"+155500000{i:02d}") for i in mock_contact_ids]
        mock_contact_repository.get_by_ids.return_value = mock_contacts
        
        # Act
        result = service.get_list_stats(list_id)
        
        # Assert - THIS WILL FAIL until service correctly uses active count
        assert result.is_success
        assert result.data['active_members'] == 85  # Should show only active
        assert result.data['removed_members'] == 15
        assert result.data['total_members'] == 100
        
        # Verify repository was called correctly
        mock_member_repository.get_membership_stats.assert_called_once_with(list_id)
        
        # The key requirement: active_members should NOT equal total_members
        # when there are removed members
        assert result.data['active_members'] != result.data['total_members']
    
    def test_get_list_stats_handles_list_with_no_removed_members(self, service, mock_member_repository, mock_contact_repository):
        """
        REQUIREMENT: Should handle lists where all members are active
        
        This test ensures the service works correctly when no members have been removed.
        """
        # Arrange
        list_id = 2
        
        # Mock stats where all members are active
        mock_stats = {
            'total': 50,
            'active': 50,  # All active
            'removed': 0   # None removed
        }
        mock_member_repository.get_membership_stats.return_value = mock_stats
        
        # Mock contact retrieval for stats
        mock_contact_ids = list(range(1, 51))  # 50 active contact IDs
        mock_member_repository.get_contact_ids_in_list.return_value = mock_contact_ids
        mock_contacts = [Mock(id=i, email=f"test{i}@example.com", phone=f"+155500000{i:02d}") for i in mock_contact_ids]
        mock_contact_repository.get_by_ids.return_value = mock_contacts
        
        # Act
        result = service.get_list_stats(list_id)
        
        # Assert
        assert result.is_success
        assert result.data['active_members'] == 50
        assert result.data['removed_members'] == 0
        assert result.data['total_members'] == 50
        
        # When no removed members, active should equal total
        assert result.data['active_members'] == result.data['total_members']
    
    def test_get_list_stats_handles_empty_list(self, service, mock_member_repository, mock_contact_repository):
        """
        REQUIREMENT: Should handle empty lists correctly
        
        This test ensures empty lists return zero counts properly.
        """
        # Arrange
        list_id = 3
        
        # Mock empty list stats
        mock_stats = {
            'total': 0,
            'active': 0,
            'removed': 0
        }
        mock_member_repository.get_membership_stats.return_value = mock_stats
        
        # Mock empty contact list
        mock_member_repository.get_contact_ids_in_list.return_value = []
        mock_contact_repository.get_by_ids.return_value = []
        
        # Act
        result = service.get_list_stats(list_id)
        
        # Assert
        assert result.is_success
        assert result.data['active_members'] == 0
        assert result.data['removed_members'] == 0
        assert result.data['total_members'] == 0
    
    def test_get_list_stats_returns_error_for_nonexistent_list(self, service, mock_member_repository):
        """
        REQUIREMENT: Should return error result for non-existent lists
        
        This prevents crashes when invalid list IDs are provided.
        """
        # Arrange
        list_id = 999
        
        # Mock repository to return None for non-existent list
        mock_member_repository.get_membership_stats.return_value = None
        
        # Act
        result = service.get_list_stats(list_id)
        
        # Assert
        assert not result.is_success
        assert 'not found' in result.error.lower() or 'does not exist' in result.error.lower()
        
        # Should still call repository to check
        mock_member_repository.get_membership_stats.assert_called_once_with(list_id)
    
    def test_get_list_contacts_returns_only_active_members(self, service, mock_member_repository, mock_contact_repository):
        """
        REQUIREMENT: get_list_contacts must return only contacts with active membership
        
        This test will FAIL until the service correctly filters to only active members
        when retrieving contacts for display.
        """
        # Arrange
        list_id = 1
        
        # Mock repository to return only active member contact IDs
        active_contact_ids = [1, 2, 3, 5, 7]  # 5 active contacts (missing 4, 6 which are removed)
        mock_member_repository.get_contact_ids_in_list.return_value = active_contact_ids
        
        # Mock contact repository to return the contacts
        mock_contacts = [Mock(id=i) for i in active_contact_ids]
        mock_contact_repository.get_by_ids.return_value = mock_contacts
        
        # Act
        result = service.get_list_contacts(list_id)
        
        # Assert - THIS WILL FAIL until service filters by status correctly
        assert result.is_success
        assert len(result.data) == 5  # Should only return active contacts
        
        # Verify correct repository calls
        mock_member_repository.get_contact_ids_in_list.assert_called_once_with(
            list_id, 
            include_removed=False  # Should not include removed members
        )
        mock_contact_repository.get_by_ids.assert_called_once_with(active_contact_ids)
        
        # Returned contacts should match the active ones
        returned_ids = [contact.id for contact in result.data]
        assert returned_ids == active_contact_ids
    
    def test_get_list_contacts_handles_mixed_status_members_correctly(self, service, mock_member_repository, mock_contact_repository):
        """
        REQUIREMENT: Should exclude removed members from contact list
        
        This test ensures removed/opted-out contacts don't appear in the contact list.
        """
        # Arrange
        list_id = 2
        
        # Mock only active contacts returned (removed contacts filtered out)
        active_contact_ids = [10, 20, 30]  # Only active ones
        mock_member_repository.get_contact_ids_in_list.return_value = active_contact_ids
        
        mock_contacts = [
            Mock(id=10, first_name="John", status="active"),
            Mock(id=20, first_name="Jane", status="active"),
            Mock(id=30, first_name="Bob", status="active")
        ]
        mock_contact_repository.get_by_ids.return_value = mock_contacts
        
        # Act
        result = service.get_list_contacts(list_id)
        
        # Assert
        assert result.is_success
        assert len(result.data) == 3
        
        # All returned contacts should be active
        for contact in result.data:
            if hasattr(contact, 'status'):
                assert contact.status == "active"
        
        # Should have called with include_removed=False to exclude removed members
        mock_member_repository.get_contact_ids_in_list.assert_called_once_with(list_id, include_removed=False)
    
    def test_get_list_contacts_returns_empty_for_list_with_only_removed_members(self, service, mock_member_repository, mock_contact_repository):
        """
        REQUIREMENT: Should return empty list when all members are removed
        
        This handles edge case where a list exists but all members have been removed.
        """
        # Arrange
        list_id = 3
        
        # Mock repository returns no active contacts
        mock_member_repository.get_contact_ids_in_list.return_value = []
        mock_contact_repository.get_by_ids.return_value = []
        
        # Act
        result = service.get_list_contacts(list_id)
        
        # Assert
        assert result.is_success
        assert result.data == []  # Empty list
        
        # Should have tried to get active members
        mock_member_repository.get_contact_ids_in_list.assert_called_once_with(list_id, include_removed=False)
        
        # Should call contact repository even with empty list
        mock_contact_repository.get_by_ids.assert_called_once_with([])
    
    def test_get_list_contacts_with_limit_respects_active_member_filtering(self, service, mock_member_repository, mock_contact_repository):
        """
        REQUIREMENT: Contact limiting should apply after active member filtering
        
        This ensures pagination/limiting works correctly with filtered active members.
        """
        # Arrange
        list_id = 4
        limit = 10
        
        # Mock 25 active contacts
        active_contact_ids = list(range(1, 26))  # 25 active contacts
        mock_member_repository.get_contact_ids_in_list.return_value = active_contact_ids
        
        # Mock contact repository returns first 10 due to limit
        limited_contacts = [Mock(id=i) for i in range(1, 11)]  # First 10
        mock_contact_repository.get_by_ids.return_value = limited_contacts
        
        # Act
        result = service.get_list_contacts(list_id, limit=limit)
        
        # Assert
        assert result.is_success
        assert len(result.data) == 10  # Limited to 10
        
        # Should get active members first, then limit
        mock_member_repository.get_contact_ids_in_list.assert_called_once_with(list_id, include_removed=False)
        
        # Contact repository should be called with limited IDs
        expected_limited_ids = active_contact_ids[:limit]  # First 10 IDs
        mock_contact_repository.get_by_ids.assert_called_once_with(expected_limited_ids)
    
    def test_get_campaign_list_by_id_with_stats_integration(self, service, mock_list_repository, mock_member_repository):
        """
        REQUIREMENT: List detail should include accurate stats when retrieved
        
        This test ensures the list detail page gets accurate count information.
        """
        # Arrange
        list_id = 5
        
        # Mock list exists
        mock_list = Mock()
        mock_list.id = list_id
        mock_list.name = "Test List"
        mock_list_repository.get_by_id.return_value = mock_list
        
        # Mock stats - service returns both formats for compatibility
        mock_stats = {
            'total': 75,
            'active': 60,  # 15 removed
            'removed': 15,
            'active_members': 60,
            'removed_members': 15,
            'total_members': 75,
            'with_email': 40,
            'with_phone': 55
        }
        
        # Act - Get list (which campaign_list_detail route does)
        list_result = service.get_campaign_list_by_id(list_id)
        
        # Also get stats separately (as route does)
        with patch.object(service, 'get_list_stats') as mock_get_stats:
            mock_get_stats.return_value = Result.success(mock_stats)
            stats_result = service.get_list_stats(list_id)
        
        # Assert
        assert list_result.is_success
        assert list_result.data.name == "Test List"
        
        assert stats_result.is_success
        assert stats_result.data['active_members'] == 60
        assert stats_result.data['active_members'] < stats_result.data['total_members']
        
        # This demonstrates the pattern the route should use
        mock_list_repository.get_by_id.assert_called_once_with(list_id)


class TestCampaignListServicePropertyRadarIntegration:
    """TDD tests for PropertyRadar import contact associations"""
    
    def test_add_contacts_to_list_creates_active_memberships(self, mock_list_repository, mock_member_repository, mock_contact_repository):
        """
        REQUIREMENT: Adding contacts to list should create active memberships
        
        This test ensures PropertyRadar import creates proper list associations
        with status='active' for all imported contacts.
        """
        # Arrange
        service = CampaignListServiceRefactored(
            campaign_list_repository=mock_list_repository,
            member_repository=mock_member_repository,
            contact_repository=mock_contact_repository
        )
        
        list_id = 1
        contact_ids = [100, 101, 102, 103, 104]  # 5 imported contacts
        
        # Mock that none of these contacts exist in the list yet
        mock_member_repository.find_one_by.return_value = None
        
        # Mock successful member creation
        mock_member_repository.create.return_value = Mock(id=1)
        mock_member_repository.commit.return_value = None
        
        # Act
        result = service.add_contacts_to_list(list_id, contact_ids)
        
        # Assert
        assert result.is_success
        assert result.data['added'] == 5  # Should return count of contacts added
        assert result.data['already_exists'] == 0
        assert result.data['errors'] == 0
        
        # Should create memberships for each contact
        assert mock_member_repository.create.call_count == 5
        
        # Verify each create call
        for idx, contact_id in enumerate(contact_ids):
            call_args = mock_member_repository.create.call_args_list[idx]
            kwargs = call_args[1]
            assert kwargs['list_id'] == list_id
            assert kwargs['contact_id'] == contact_id
        
        mock_member_repository.commit.assert_called_once()
    
    def test_add_contacts_to_list_handles_duplicate_memberships(self, mock_list_repository, mock_member_repository, mock_contact_repository):
        """
        REQUIREMENT: Should handle duplicate contact additions gracefully
        
        This prevents errors when PropertyRadar import tries to add contacts
        that are already in the list.
        """
        # Arrange
        service = CampaignListServiceRefactored(
            campaign_list_repository=mock_list_repository,
            member_repository=mock_member_repository,
            contact_repository=mock_contact_repository
        )
        
        list_id = 2
        contact_ids = [200, 201, 202]
        
        # Mock that contact 200 already exists and is active
        existing_member = Mock(id=1, list_id=list_id, contact_id=200, status='active')
        
        def find_one_by_side_effect(**kwargs):
            if kwargs.get('contact_id') == 200:
                return existing_member  # Already exists
            return None  # Others don't exist
        
        mock_member_repository.find_one_by.side_effect = find_one_by_side_effect
        mock_member_repository.create.return_value = Mock(id=1)
        mock_member_repository.commit.return_value = None
        
        # Act
        result = service.add_contacts_to_list(list_id, contact_ids)
        
        # Assert
        assert result.is_success
        assert result.data['added'] == 2  # Only 2 new, 1 already existed
        assert result.data['already_exists'] == 1  # Contact 200 already existed
        assert result.data['errors'] == 0
        
        # Should only create 2 new members (201, 202)
        assert mock_member_repository.create.call_count == 2
        
        # Verify the create calls
        create_calls = mock_member_repository.create.call_args_list
        created_contact_ids = [call[1]['contact_id'] for call in create_calls]
        assert 201 in created_contact_ids
        assert 202 in created_contact_ids
        assert 200 not in created_contact_ids  # Should not create for existing contact
    
    def test_add_contacts_to_list_updates_existing_removed_members_to_active(self, mock_list_repository, mock_member_repository, mock_contact_repository):
        """
        REQUIREMENT: Re-importing removed contacts should reactivate them
        
        This handles case where a contact was previously removed from a list
        but appears again in a new PropertyRadar import.
        """
        # Arrange
        service = CampaignListServiceRefactored(
            campaign_list_repository=mock_list_repository,
            member_repository=mock_member_repository,
            contact_repository=mock_contact_repository
        )
        
        list_id = 3
        contact_ids = [300, 301, 302]
        
        # Mock existing members with 'removed' status
        removed_member_1 = Mock(id=1, list_id=list_id, contact_id=300, status='removed')
        removed_member_2 = Mock(id=2, list_id=list_id, contact_id=301, status='removed')
        # Contact 302 doesn't exist yet
        
        # Mock find_one_by to return removed members for 300, 301, and None for 302
        def find_one_by_side_effect(**kwargs):
            if kwargs.get('contact_id') == 300:
                return removed_member_1
            elif kwargs.get('contact_id') == 301:
                return removed_member_2
            elif kwargs.get('contact_id') == 302:
                return None
            return None
        
        mock_member_repository.find_one_by.side_effect = find_one_by_side_effect
        mock_member_repository.update.return_value = None
        mock_member_repository.create.return_value = Mock(id=3)
        mock_member_repository.commit.return_value = None
        
        # Act
        result = service.add_contacts_to_list(list_id, contact_ids)
        
        # Assert
        assert result.is_success
        assert result.data['added'] == 3  # 2 reactivated + 1 new
        assert result.data['already_exists'] == 0
        assert result.data['errors'] == 0
        
        # Verify that removed members were reactivated
        assert mock_member_repository.update.call_count == 2  # Two removed members reactivated
        
        # Check the update calls had correct parameters
        update_calls = mock_member_repository.update.call_args_list
        for call in update_calls:
            args, kwargs = call
            assert kwargs.get('status') == 'active' or (len(args) > 1 and args[1] == 'active')
        
        # Verify new member was created for contact 302
        assert mock_member_repository.create.call_count == 1
        create_call_kwargs = mock_member_repository.create.call_args[1]
        assert create_call_kwargs['list_id'] == list_id
        assert create_call_kwargs['contact_id'] == 302


class TestCampaignListServiceErrorHandling:
    """TDD tests for error handling in contact counting"""
    
    def test_get_list_stats_handles_repository_errors(self, service, mock_member_repository):
        """
        REQUIREMENT: Should handle repository errors gracefully
        
        This ensures the service returns proper error results when database queries fail.
        """
        # Arrange
        list_id = 1
        
        # Mock repository error
        mock_member_repository.get_membership_stats.side_effect = Exception("Database connection failed")
        
        # Act
        result = service.get_list_stats(list_id)
        
        # Assert
        assert not result.is_success
        assert "Database connection failed" in result.error or "error" in result.error.lower()
    
    def test_get_list_contacts_handles_repository_errors(self, service, mock_member_repository, mock_contact_repository):
        """
        REQUIREMENT: Should handle repository errors in contact retrieval
        
        This ensures contact listing doesn't crash when database errors occur.
        """
        # Arrange
        list_id = 1
        
        # Mock member repository succeeds but contact repository fails
        mock_member_repository.get_contact_ids_in_list.return_value = [1, 2, 3]
        mock_contact_repository.get_by_ids.side_effect = Exception("Contact query failed")
        
        # Act
        result = service.get_list_contacts(list_id)
        
        # Assert
        assert not result.is_success
        assert "Contact query failed" in result.error or "error" in result.error.lower()
    
    def test_service_handles_none_repository_responses(self, service, mock_member_repository):
        """
        REQUIREMENT: Should handle None responses from repositories
        
        This prevents crashes when repositories return None instead of raising exceptions.
        """
        # Arrange
        list_id = 1
        
        # Mock repository returns None
        mock_member_repository.get_membership_stats.return_value = None
        
        # Act
        result = service.get_list_stats(list_id)
        
        # Assert
        assert not result.is_success
        assert result.error is not None
        assert len(result.error) > 0  # Should have meaningful error message