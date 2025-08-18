"""
Unit tests for CampaignListService (Refactored with Repository Pattern)
Follows TDD methodology - these tests should FAIL initially
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
from typing import List, Dict, Any

from services.campaign_list_service_refactored import CampaignListServiceRefactored
from services.common.result import Result
from repositories.campaign_list_repository import CampaignListRepository
from repositories.campaign_list_member_repository import CampaignListMemberRepository
from repositories.contact_repository import ContactRepository
from crm_database import CampaignList, CampaignListMember, Contact
from tests.fixtures.factories.campaign_factory import CampaignListFactory, CampaignListMemberFactory
from tests.fixtures.factories.contact_factory import ContactFactory


class TestCampaignListServiceRefactored:
    """Test suite for refactored CampaignListService with repository pattern"""
    
    @pytest.fixture
    def mock_campaign_list_repository(self):
        """Mock CampaignListRepository"""
        return Mock(spec=CampaignListRepository)
    
    @pytest.fixture
    def mock_member_repository(self):
        """Mock CampaignListMemberRepository"""
        return Mock(spec=CampaignListMemberRepository)
    
    @pytest.fixture
    def mock_contact_repository(self):
        """Mock ContactRepository"""
        return Mock(spec=ContactRepository)
    
    @pytest.fixture
    def service(self, mock_campaign_list_repository, mock_member_repository, mock_contact_repository):
        """Create service instance with mocked repositories"""
        return CampaignListServiceRefactored(
            campaign_list_repository=mock_campaign_list_repository,
            member_repository=mock_member_repository,
            contact_repository=mock_contact_repository
        )
    
    def test_create_list_success(self, service, mock_campaign_list_repository):
        """Test successful list creation"""
        # Arrange
        expected_list = CampaignListFactory()
        mock_campaign_list_repository.create.return_value = expected_list
        mock_campaign_list_repository.commit.return_value = None
        
        # Act
        result = service.create_list(
            name='Test List',
            description='Test description',
            created_by='test-user'
        )
        
        # Assert
        assert result.is_success
        assert result.data == expected_list
        mock_campaign_list_repository.create.assert_called_once_with(
            name='Test List',
            description='Test description',
            filter_criteria=None,
            is_dynamic=False,
            created_by='test-user'
        )
        mock_campaign_list_repository.commit.assert_called_once()
    
    def test_create_dynamic_list_with_criteria(self, service, mock_campaign_list_repository):
        """Test creating dynamic list with filter criteria"""
        # Arrange
        expected_list = CampaignListFactory(is_dynamic=True)
        filter_criteria = {'imported_after': datetime.utcnow()}
        mock_campaign_list_repository.create.return_value = expected_list
        mock_campaign_list_repository.commit.return_value = None
        
        # Mock the refresh_dynamic_list call
        service.refresh_dynamic_list = Mock(return_value=Result.success({'added': 5, 'removed': 0}))
        
        # Act
        result = service.create_list(
            name='Dynamic List',
            filter_criteria=filter_criteria,
            is_dynamic=True
        )
        
        # Assert
        assert result.is_success
        assert result.data == expected_list
        # Verify datetime was serialized to ISO string
        expected_criteria = {'imported_after': filter_criteria['imported_after'].isoformat()}
        mock_campaign_list_repository.create.assert_called_once_with(
            name='Dynamic List',
            description=None,
            filter_criteria=expected_criteria,
            is_dynamic=True,
            created_by=None
        )
        service.refresh_dynamic_list.assert_called_once_with(expected_list.id)
    
    def test_create_list_repository_error(self, service, mock_campaign_list_repository):
        """Test list creation with repository error"""
        # Arrange
        mock_campaign_list_repository.create.side_effect = Exception('Database error')
        mock_campaign_list_repository.rollback.return_value = None
        
        # Act
        result = service.create_list(name='Test List')
        
        # Assert
        assert result.is_failure
        assert 'Failed to create campaign list' in result.error
        mock_campaign_list_repository.rollback.assert_called_once()
    
    def test_add_contacts_to_list_success(self, service, mock_member_repository):
        """Test successfully adding contacts to list"""
        # Arrange
        list_id = 1
        contact_ids = [10, 11, 12]
        added_by = 'test-user'
        
        # Mock existing member check (none exist)
        mock_member_repository.find_one_by.return_value = None
        
        # Mock member creation
        created_members = [CampaignListMemberFactory() for _ in contact_ids]
        mock_member_repository.create.side_effect = created_members
        mock_member_repository.commit.return_value = None
        
        # Act
        result = service.add_contacts_to_list(list_id, contact_ids, added_by)
        
        # Assert
        assert result.is_success
        assert result.data['added'] == 3
        assert result.data['already_exists'] == 0
        assert result.data['errors'] == 0
        
        # Verify repository calls
        assert mock_member_repository.find_one_by.call_count == 3
        assert mock_member_repository.create.call_count == 3
        mock_member_repository.commit.assert_called_once()
    
    def test_add_contacts_with_existing_active_member(self, service, mock_member_repository):
        """Test adding contacts when one already exists as active"""
        # Arrange
        list_id = 1
        contact_ids = [10, 11]
        
        # Mock first contact already exists as active
        existing_member = CampaignListMemberFactory(status='active')
        mock_member_repository.find_one_by.side_effect = [existing_member, None]
        
        # Mock creation for second contact
        new_member = CampaignListMemberFactory()
        mock_member_repository.create.return_value = new_member
        mock_member_repository.commit.return_value = None
        
        # Act
        result = service.add_contacts_to_list(list_id, contact_ids)
        
        # Assert
        assert result.is_success
        assert result.data['added'] == 1
        assert result.data['already_exists'] == 1
        assert result.data['errors'] == 0
    
    def test_add_contacts_reactivate_removed_member(self, service, mock_member_repository):
        """Test adding contacts when one exists as removed (should reactivate)"""
        # Arrange
        list_id = 1
        contact_ids = [10]
        
        # Mock existing removed member
        removed_member = CampaignListMemberFactory(status='removed')
        mock_member_repository.find_one_by.return_value = removed_member
        mock_member_repository.update.return_value = removed_member
        mock_member_repository.commit.return_value = None
        
        # Act
        result = service.add_contacts_to_list(list_id, contact_ids, 'test-user')
        
        # Assert
        assert result.is_success
        assert result.data['added'] == 1
        assert result.data['already_exists'] == 0
        
        # Verify reactivation
        from unittest.mock import ANY
        mock_member_repository.update.assert_called_once_with(
            removed_member,
            status='active',
            added_at=ANY
        )
    
    def test_remove_contacts_from_list(self, service, mock_member_repository):
        """Test removing contacts from list"""
        # Arrange
        list_id = 1
        contact_ids = [10, 11, 12]
        
        mock_member_repository.remove_contacts_from_list.return_value = 3
        mock_member_repository.commit.return_value = None
        
        # Act
        result = service.remove_contacts_from_list(list_id, contact_ids)
        
        # Assert
        assert result.is_success
        assert result.data == 3
        mock_member_repository.remove_contacts_from_list.assert_called_once_with(list_id, contact_ids)
        mock_member_repository.commit.assert_called_once()
    
    def test_get_list_contacts(self, service, mock_member_repository, mock_contact_repository):
        """Test getting contacts in a list"""
        # Arrange
        list_id = 1
        contact_ids = [10, 11, 12]
        expected_contacts = [ContactFactory() for _ in contact_ids]
        
        mock_member_repository.get_contact_ids_in_list.return_value = contact_ids
        mock_contact_repository.get_by_ids.return_value = expected_contacts
        
        # Act
        result = service.get_list_contacts(list_id, include_removed=False)
        
        # Assert
        assert result.is_success
        assert result.data == expected_contacts
        mock_member_repository.get_contact_ids_in_list.assert_called_once_with(list_id, include_removed=False)
        mock_contact_repository.get_by_ids.assert_called_once_with(contact_ids)
    
    def test_get_list_stats(self, service, mock_member_repository, mock_contact_repository):
        """Test getting list statistics"""
        # Arrange
        list_id = 1
        mock_stats = {'total': 10, 'active': 8, 'removed': 2}
        contacts = [
            ContactFactory(email='test1@example.com', phone='+1234567890'),
            ContactFactory(email=None, phone='+1234567891'),
            ContactFactory(email='test3@example.com', phone=None)
        ]
        
        mock_member_repository.get_membership_stats.return_value = mock_stats
        service.get_list_contacts = Mock(return_value=Result.success(contacts))
        
        # Act
        result = service.get_list_stats(list_id)
        
        # Assert
        assert result.is_success
        stats = result.data
        assert stats['total_members'] == 10
        assert stats['active_members'] == 8
        assert stats['removed_members'] == 2
        assert stats['with_email'] == 2  # 2 contacts have email
        assert stats['with_phone'] == 2  # 2 contacts have phone
    
    def test_find_contacts_by_criteria_csv_import(self, service, mock_contact_repository):
        """Test finding contacts by CSV import criteria"""
        # Arrange
        criteria = {'csv_import_id': 123}
        expected_contacts = [ContactFactory() for _ in range(3)]
        mock_contact_repository.find_by_csv_import.return_value = expected_contacts
        
        # Act
        result = service.find_contacts_by_criteria(criteria)
        
        # Assert
        assert result.is_success
        assert result.data == expected_contacts
        mock_contact_repository.find_by_csv_import.assert_called_once_with(123)
    
    def test_find_contacts_by_criteria_date_range(self, service, mock_contact_repository):
        """Test finding contacts by date range criteria"""
        # Arrange
        start_date = datetime.utcnow() - timedelta(days=30)
        end_date = datetime.utcnow()
        criteria = {
            'imported_after': start_date.isoformat(),
            'imported_before': end_date.isoformat()
        }
        expected_contacts = [ContactFactory() for _ in range(5)]
        mock_contact_repository.find_by_date_range.return_value = expected_contacts
        
        # Act
        result = service.find_contacts_by_criteria(criteria)
        
        # Assert
        assert result.is_success
        assert result.data == expected_contacts
        mock_contact_repository.find_by_date_range.assert_called_once_with(
            imported_after=start_date,
            imported_before=end_date
        )
    
    def test_find_contacts_by_criteria_no_recent_contact(self, service, mock_contact_repository):
        """Test finding contacts with no recent contact"""
        # Arrange
        criteria = {'no_recent_contact': True, 'days_since_contact': 60}
        expected_contacts = [ContactFactory() for _ in range(10)]
        mock_contact_repository.find_without_recent_activity.return_value = expected_contacts
        
        # Act
        result = service.find_contacts_by_criteria(criteria)
        
        # Assert
        assert result.is_success
        assert result.data == expected_contacts
        mock_contact_repository.find_without_recent_activity.assert_called_once_with(60)
    
    def test_find_contacts_by_criteria_exclude_opted_out(self, service, mock_contact_repository):
        """Test finding contacts excluding opted out"""
        # Arrange
        criteria = {'exclude_opted_out': True}
        expected_contacts = [ContactFactory() for _ in range(15)]
        mock_contact_repository.find_not_opted_out.return_value = expected_contacts
        
        # Act
        result = service.find_contacts_by_criteria(criteria)
        
        # Assert
        assert result.is_success
        assert result.data == expected_contacts
        mock_contact_repository.find_not_opted_out.assert_called_once()
    
    def test_refresh_dynamic_list(self, service, mock_campaign_list_repository, mock_member_repository, mock_contact_repository):
        """Test refreshing a dynamic list"""
        # Arrange
        list_id = 1
        dynamic_list = CampaignListFactory(
            id=list_id,
            is_dynamic=True,
            filter_criteria={'source': 'test'}
        )
        
        # Mock current members
        current_contact_ids = [10, 11, 12]
        # Mock matching contacts from criteria
        matching_contacts = [ContactFactory(id=11), ContactFactory(id=12), ContactFactory(id=13)]
        matching_ids = [11, 12, 13]
        
        mock_campaign_list_repository.get_by_id.return_value = dynamic_list
        mock_member_repository.get_contact_ids_in_list.return_value = current_contact_ids
        service.find_contacts_by_criteria = Mock(return_value=Result.success(matching_contacts))
        
        # Mock member operations
        created_member = CampaignListMemberFactory()
        mock_member_repository.create.return_value = created_member
        mock_member_repository.remove_contacts_from_list.return_value = 1
        mock_campaign_list_repository.update.return_value = dynamic_list
        mock_campaign_list_repository.commit.return_value = None
        
        # Act
        result = service.refresh_dynamic_list(list_id)
        
        # Assert
        assert result.is_success
        stats = result.data
        assert stats['added'] == 1  # Contact 13 is new
        assert stats['removed'] == 1  # Contact 10 is no longer matching
        assert stats['total'] == 3  # Total matching contacts
        
        # Verify repository calls
        mock_member_repository.create.assert_called_once_with(
            list_id=list_id,
            contact_id=13,
            added_by='system_dynamic'
        )
        mock_member_repository.remove_contacts_from_list.assert_called_once_with(list_id, [10])
    
    def test_refresh_non_dynamic_list(self, service, mock_campaign_list_repository):
        """Test refreshing a non-dynamic list (should fail)"""
        # Arrange
        list_id = 1
        static_list = CampaignListFactory(id=list_id, is_dynamic=False)
        mock_campaign_list_repository.get_by_id.return_value = static_list
        
        # Act
        result = service.refresh_dynamic_list(list_id)
        
        # Assert
        assert result.is_failure
        assert 'not dynamic' in result.error
    
    def test_get_all_lists(self, service, mock_campaign_list_repository):
        """Test getting all campaign lists"""
        # Arrange
        expected_lists = [CampaignListFactory() for _ in range(3)]
        mock_campaign_list_repository.get_all.return_value = expected_lists
        
        # Act
        result = service.get_all_lists()
        
        # Assert
        assert result.is_success
        assert result.data == expected_lists
        mock_campaign_list_repository.get_all.assert_called_once_with(
            order_by='created_at',
            order=mock_campaign_list_repository.get_all.call_args[1]['order']
        )
    
    def test_duplicate_list(self, service, mock_campaign_list_repository, mock_member_repository):
        """Test duplicating a campaign list"""
        # Arrange
        source_list_id = 1
        new_name = 'Duplicated List'
        created_by = 'test-user'
        
        source_list = CampaignListFactory(
            id=source_list_id,
            name='Original List',
            description='Original description',
            filter_criteria={'source': 'test'}
        )
        
        # Mock active members
        active_contact_ids = [10, 11, 12]
        
        # Mock new list creation
        new_list = CampaignListFactory(id=2, name=new_name)
        created_members = [CampaignListMemberFactory() for _ in active_contact_ids]
        
        mock_campaign_list_repository.get_by_id.return_value = source_list
        mock_campaign_list_repository.create.return_value = new_list
        mock_campaign_list_repository.flush.return_value = None
        mock_member_repository.get_contact_ids_in_list.return_value = active_contact_ids
        mock_member_repository.create.side_effect = created_members
        mock_campaign_list_repository.commit.return_value = None
        
        # Act
        result = service.duplicate_list(source_list_id, new_name, created_by)
        
        # Assert
        assert result.is_success
        assert result.data == new_list
        
        # Verify new list creation
        mock_campaign_list_repository.create.assert_called_once_with(
            name=new_name,
            description=f"Copy of {source_list.name}",
            filter_criteria=source_list.filter_criteria,
            is_dynamic=False,
            created_by=created_by
        )
        
        # Verify member copying
        assert mock_member_repository.create.call_count == 3
    
    def test_duplicate_nonexistent_list(self, service, mock_campaign_list_repository):
        """Test duplicating a non-existent list"""
        # Arrange
        mock_campaign_list_repository.get_by_id.return_value = None
        
        # Act
        result = service.duplicate_list(99999, 'New Name')
        
        # Assert
        assert result.is_failure
        assert 'not found' in result.error
    
    def test_get_campaign_list_by_id(self, service, mock_campaign_list_repository):
        """Test getting campaign list by ID"""
        # Arrange
        list_id = 1
        expected_list = CampaignListFactory(id=list_id)
        mock_campaign_list_repository.get_by_id.return_value = expected_list
        
        # Act
        result = service.get_campaign_list_by_id(list_id)
        
        # Assert
        assert result.is_success
        assert result.data == expected_list
        mock_campaign_list_repository.get_by_id.assert_called_once_with(list_id)
    
    def test_get_campaign_list_by_id_not_found(self, service, mock_campaign_list_repository):
        """Test getting non-existent campaign list"""
        # Arrange
        mock_campaign_list_repository.get_by_id.return_value = None
        
        # Act
        result = service.get_campaign_list_by_id(99999)
        
        # Assert
        assert result.is_failure
        assert 'not found' in result.error
