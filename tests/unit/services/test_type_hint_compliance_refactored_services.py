"""
TDD Tests for Type Hint Compliance in Refactored Services

These tests verify that refactored services work with dictionary returns
instead of model objects, ensuring type hints match actual behavior.

CRITICAL: These tests should FAIL initially (RED phase) because the services
currently have incorrect type hints for model classes that no longer exist.
"""

import pytest
from unittest.mock import Mock, MagicMock
from datetime import datetime, timedelta
from utils.datetime_utils import utc_now
from typing import List, Dict, Any

from services.campaign_list_service_refactored import CampaignListServiceRefactored
from services.campaign_service_refactored import CampaignService
from services.common.result import Result
from repositories.campaign_list_repository import CampaignListRepository
from repositories.campaign_list_member_repository import CampaignListMemberRepository
from repositories.contact_repository import ContactRepository
from repositories.campaign_repository import CampaignRepository
from repositories.contact_flag_repository import ContactFlagRepository


class TestCampaignListServiceTypeHints:
    """Test that CampaignListService works with dictionary returns, not model objects"""
    
    @pytest.fixture
    def mock_campaign_list_repository(self):
        """Mock CampaignListRepository returning dictionaries"""
        repo = Mock(spec=CampaignListRepository)
        # Repository should return dictionaries, not model objects
        repo.create.return_value = {
            'id': 1,
            'name': 'Test List',
            'description': 'Test Description',
            'is_dynamic': False,
            'filter_criteria': None,
            'created_by': 'test-user',
            'created_at': utc_now(),
            'updated_at': utc_now()
        }
        return repo
    
    @pytest.fixture
    def mock_member_repository(self):
        """Mock CampaignListMemberRepository"""
        return Mock(spec=CampaignListMemberRepository)
    
    @pytest.fixture
    def mock_contact_repository(self):
        """Mock ContactRepository returning dictionaries"""
        repo = Mock(spec=ContactRepository)
        # Repository should return list of contact dictionaries
        repo.get_by_ids.return_value = [
            {
                'id': 1,
                'phone': '+11234567890',
                'first_name': 'John',
                'last_name': 'Doe',
                'email': 'john@example.com'
            },
            {
                'id': 2,
                'phone': '+10987654321',
                'first_name': 'Jane',
                'last_name': 'Smith',
                'email': None
            }
        ]
        return repo
    
    @pytest.fixture
    def service(self, mock_campaign_list_repository, mock_member_repository, mock_contact_repository):
        """Create service instance with mocked repositories"""
        return CampaignListServiceRefactored(
            campaign_list_repository=mock_campaign_list_repository,
            member_repository=mock_member_repository,
            contact_repository=mock_contact_repository
        )
    
    def test_create_list_returns_dict_not_model(self, service, mock_campaign_list_repository):
        """Test that create_list returns Result[Dict] not Result[CampaignList]"""
        # Arrange
        mock_campaign_list_repository.commit.return_value = None
        
        # Act
        result = service.create_list('Test List', 'Description')
        
        # Assert - should return Result[Dict[str, Any]], not Result[CampaignList]
        assert result.is_success
        assert isinstance(result.data, dict), f"Expected dict, got {type(result.data)}"
        assert 'id' in result.data
        assert 'name' in result.data
        assert result.data['name'] == 'Test List'
        
        # Verify the data structure matches expected dictionary format
        expected_keys = {'id', 'name', 'description', 'is_dynamic', 'filter_criteria', 'created_by', 'created_at', 'updated_at'}
        actual_keys = set(result.data.keys())
        assert expected_keys.issubset(actual_keys), f"Missing keys: {expected_keys - actual_keys}"
    
    def test_get_list_contacts_returns_list_of_dicts(self, service, mock_member_repository, mock_contact_repository):
        """Test that get_list_contacts returns Result[List[Dict]] not Result[List[Contact]]"""
        # Arrange
        list_id = 1
        contact_ids = [1, 2]
        mock_member_repository.get_contact_ids_in_list.return_value = contact_ids
        
        # Act
        result = service.get_list_contacts(list_id)
        
        # Assert - should return Result[List[Dict[str, Any]]], not Result[List[Contact]]
        assert result.is_success
        assert isinstance(result.data, list), f"Expected list, got {type(result.data)}"
        
        for contact in result.data:
            assert isinstance(contact, dict), f"Expected dict, got {type(contact)}"
            assert 'id' in contact
            assert 'phone' in contact
            assert 'first_name' in contact
    
    def test_get_all_lists_returns_list_of_dicts(self, service, mock_campaign_list_repository):
        """Test that get_all_lists returns Result[List[Dict]] not Result[List[CampaignList]]"""
        # Arrange
        mock_lists = [
            {'id': 1, 'name': 'List 1', 'is_dynamic': False},
            {'id': 2, 'name': 'List 2', 'is_dynamic': True}
        ]
        mock_campaign_list_repository.get_lists_ordered_by_created_desc.return_value = mock_lists
        
        # Act  
        result = service.get_all_lists()
        
        # Assert - should return Result[List[Dict[str, Any]]], not Result[List[CampaignList]]
        assert result.is_success
        assert isinstance(result.data, list), f"Expected list, got {type(result.data)}"
        
        for campaign_list in result.data:
            assert isinstance(campaign_list, dict), f"Expected dict, got {type(campaign_list)}"
            assert 'id' in campaign_list
            assert 'name' in campaign_list
    
    def test_get_campaign_list_by_id_returns_dict(self, service, mock_campaign_list_repository):
        """Test that get_campaign_list_by_id returns Result[Dict] not Result[CampaignList]"""
        # Arrange
        list_id = 1
        mock_list = {'id': list_id, 'name': 'Test List', 'is_dynamic': False}
        mock_campaign_list_repository.get_by_id.return_value = mock_list
        
        # Act
        result = service.get_campaign_list_by_id(list_id)
        
        # Assert - should return Result[Dict[str, Any]], not Result[CampaignList]
        assert result.is_success
        assert isinstance(result.data, dict), f"Expected dict, got {type(result.data)}"
        assert result.data['id'] == list_id
        assert result.data['name'] == 'Test List'
    
    def test_duplicate_list_returns_dict(self, service, mock_campaign_list_repository, mock_member_repository):
        """Test that duplicate_list returns Result[Dict] not Result[CampaignList]"""
        # Arrange
        source_list_id = 1
        new_name = 'Duplicated List'
        
        source_list = {'id': source_list_id, 'name': 'Original', 'filter_criteria': None}
        new_list = {'id': 2, 'name': new_name, 'description': 'Copy of Original'}
        
        mock_campaign_list_repository.get_by_id.return_value = source_list
        mock_campaign_list_repository.create.return_value = new_list
        mock_campaign_list_repository.flush.return_value = None
        mock_campaign_list_repository.commit.return_value = None
        mock_member_repository.get_contact_ids_in_list.return_value = []
        
        # Act
        result = service.duplicate_list(source_list_id, new_name)
        
        # Assert - should return Result[Dict[str, Any]], not Result[CampaignList]
        assert result.is_success
        assert isinstance(result.data, dict), f"Expected dict, got {type(result.data)}"
        assert result.data['name'] == new_name


class TestCampaignServiceTypeHints:
    """Test that CampaignService works with dictionary returns, not model objects"""
    
    @pytest.fixture
    def mock_campaign_repository(self):
        """Mock CampaignRepository returning dictionaries"""
        repo = Mock(spec=CampaignRepository)
        # Repository should return dictionaries, not model objects
        repo.create.return_value = {
            'id': 1,
            'name': 'Test Campaign',
            'campaign_type': 'blast',
            'status': 'draft',
            'template_a': 'Hello {first_name}',
            'template_b': None,
            'daily_limit': 125,
            'created_at': utc_now()
        }
        return repo
    
    @pytest.fixture
    def mock_contact_repository(self):
        """Mock ContactRepository"""
        return Mock(spec=ContactRepository)
    
    @pytest.fixture
    def mock_contact_flag_repository(self):
        """Mock ContactFlagRepository"""
        return Mock(spec=ContactFlagRepository)
    
    @pytest.fixture
    def service(self, mock_campaign_repository, mock_contact_repository, mock_contact_flag_repository):
        """Create service instance with mocked repositories"""
        return CampaignService(
            campaign_repository=mock_campaign_repository,
            contact_repository=mock_contact_repository,
            contact_flag_repository=mock_contact_flag_repository
        )
    
    def test_create_campaign_returns_dict_not_model(self, service, mock_campaign_repository):
        """Test that create_campaign returns Dict not Campaign model"""
        # Arrange
        mock_campaign_repository.commit.return_value = None
        
        # Act
        result = service.create_campaign(
            name='Test Campaign',
            campaign_type='blast',
            template_a='Hello {first_name}'
        )
        
        # Assert - should return Result[Dict[str, Any]], not Result[Campaign]
        assert result.is_success, f"Expected success, got: {result.error if not result.is_success else 'N/A'}"
        assert isinstance(result.data, dict), f"Expected dict, got {type(result.data)}"
        assert 'id' in result.data
        assert 'name' in result.data
        assert result.data['name'] == 'Test Campaign'
        assert result.data['campaign_type'] == 'blast'
        
        # Verify the data structure matches expected dictionary format
        expected_keys = {'id', 'name', 'campaign_type', 'status', 'template_a', 'daily_limit', 'created_at'}
        actual_keys = set(result.data.keys())
        assert expected_keys.issubset(actual_keys), f"Missing keys: {expected_keys - actual_keys}"
    
    def test_get_by_id_returns_dict_or_none(self, service, mock_campaign_repository):
        """Test that get_by_id returns Dict or None, not Campaign model"""
        # Arrange
        campaign_id = 1
        mock_campaign = {'id': campaign_id, 'name': 'Test Campaign', 'status': 'active'}
        mock_campaign_repository.get_by_id.return_value = mock_campaign
        
        # Act
        result = service.get_by_id(campaign_id)
        
        # Assert - should return Dict[str, Any] or None, not Campaign model
        assert isinstance(result, dict), f"Expected dict, got {type(result)}"
        assert result['id'] == campaign_id
        assert result['name'] == 'Test Campaign'
    
    def test_clone_campaign_returns_dict(self, service, mock_campaign_repository):
        """Test that clone_campaign returns Dict not Campaign model"""
        # Arrange
        campaign_id = 1
        new_name = 'Cloned Campaign'
        cloned_campaign = {
            'id': 2,
            'name': new_name,
            'campaign_type': 'blast',
            'status': 'draft'
        }
        
        mock_campaign_repository.clone_campaign.return_value = cloned_campaign
        mock_campaign_repository.commit.return_value = None
        
        # Act
        result = service.clone_campaign(campaign_id, new_name)
        
        # Assert - should return Dict[str, Any], not Campaign model
        assert isinstance(result, dict), f"Expected dict, got {type(result)}"
        assert result['id'] == 2
        assert result['name'] == new_name
    
    def test_get_eligible_contacts_returns_list_of_dicts(self, service, mock_contact_repository, mock_contact_flag_repository):
        """Test that get_eligible_contacts returns List[Dict] not List[Contact]"""
        # Arrange
        filters = {'has_phone': True, 'exclude_opted_out': True}
        mock_contacts = [
            {'id': 1, 'phone': '+11234567890', 'first_name': 'John'},
            {'id': 2, 'phone': '+10987654321', 'first_name': 'Jane'}
        ]
        mock_contact_repository.get_all.return_value = mock_contacts
        mock_contact_flag_repository.get_contact_ids_with_flag_type.return_value = []  # No opted out contacts
        
        # Act
        result = service.get_eligible_contacts(filters)
        
        # Assert - should return List[Dict[str, Any]], not List[Contact]
        assert isinstance(result, list), f"Expected list, got {type(result)}"
        
        for contact in result:
            assert isinstance(contact, dict), f"Expected dict, got {type(contact)}"
            assert 'id' in contact
            assert 'phone' in contact
            assert 'first_name' in contact
    
    def test_get_campaigns_needing_send_returns_list_of_dicts(self, service, mock_campaign_repository):
        """Test that get_campaigns_needing_send returns List[Dict] not List[Campaign]"""
        # Arrange
        mock_campaigns = [
            {'id': 1, 'name': 'Campaign 1', 'status': 'active'},
            {'id': 2, 'name': 'Campaign 2', 'status': 'active'}
        ]
        mock_campaign_repository.get_campaigns_needing_send.return_value = mock_campaigns
        
        # Act
        result = service.get_campaigns_needing_send()
        
        # Assert - should return List[Dict[str, Any]], not List[Campaign]
        assert isinstance(result, list), f"Expected list, got {type(result)}"
        
        for campaign in result:
            assert isinstance(campaign, dict), f"Expected dict, got {type(campaign)}"
            assert 'id' in campaign
            assert 'name' in campaign
            assert 'status' in campaign


class TestTypeHintAnnotationsCompliance:
    """Test that type annotations match actual return types"""
    
    def test_campaign_list_service_type_annotations_use_dict(self):
        """Test that CampaignListService type annotations use Dict[str, Any] instead of models"""
        import inspect
        from services.campaign_list_service_refactored import CampaignListServiceRefactored
        
        # Get method signatures
        create_list_sig = inspect.signature(CampaignListServiceRefactored.create_list)
        get_list_contacts_sig = inspect.signature(CampaignListServiceRefactored.get_list_contacts)
        get_all_lists_sig = inspect.signature(CampaignListServiceRefactored.get_all_lists)
        duplicate_list_sig = inspect.signature(CampaignListServiceRefactored.duplicate_list)
        get_campaign_list_by_id_sig = inspect.signature(CampaignListServiceRefactored.get_campaign_list_by_id)
        
        # Check return type annotations
        create_list_return = str(create_list_sig.return_annotation)
        get_list_contacts_return = str(get_list_contacts_sig.return_annotation)
        get_all_lists_return = str(get_all_lists_sig.return_annotation)
        duplicate_list_return = str(duplicate_list_sig.return_annotation)
        get_campaign_list_by_id_return = str(get_campaign_list_by_id_sig.return_annotation)
        
        # These should NOT contain model class names
        model_class_names = ['CampaignList', 'Contact', 'CampaignListMember']
        
        for method_name, return_annotation in [
            ('create_list', create_list_return),
            ('get_list_contacts', get_list_contacts_return),
            ('get_all_lists', get_all_lists_return),
            ('duplicate_list', duplicate_list_return),
            ('get_campaign_list_by_id', get_campaign_list_by_id_return)
        ]:
            for model_class in model_class_names:
                assert model_class not in return_annotation, (
                    f"Method {method_name} return type annotation '{return_annotation}' "
                    f"should not reference model class '{model_class}'. "
                    f"Use Dict[str, Any] instead."
                )
    
    def test_campaign_service_type_annotations_use_dict(self):
        """Test that CampaignService type annotations use Dict[str, Any] instead of models"""
        import inspect
        from services.campaign_service_refactored import CampaignService
        
        # Get method signatures
        create_campaign_sig = inspect.signature(CampaignService.create_campaign)
        get_by_id_sig = inspect.signature(CampaignService.get_by_id)
        clone_campaign_sig = inspect.signature(CampaignService.clone_campaign)
        get_eligible_contacts_sig = inspect.signature(CampaignService.get_eligible_contacts)
        get_campaigns_needing_send_sig = inspect.signature(CampaignService.get_campaigns_needing_send)
        
        # Check return type annotations
        create_campaign_return = str(create_campaign_sig.return_annotation)
        get_by_id_return = str(get_by_id_sig.return_annotation)
        clone_campaign_return = str(clone_campaign_sig.return_annotation)
        get_eligible_contacts_return = str(get_eligible_contacts_sig.return_annotation)
        get_campaigns_needing_send_return = str(get_campaigns_needing_send_sig.return_annotation)
        
        # These should NOT contain model class names
        model_class_names = ['Campaign', 'Contact', 'CampaignMembership']
        
        for method_name, return_annotation in [
            ('create_campaign', create_campaign_return),
            ('get_by_id', get_by_id_return),
            ('clone_campaign', clone_campaign_return),
            ('get_eligible_contacts', get_eligible_contacts_return),
            ('get_campaigns_needing_send', get_campaigns_needing_send_return)
        ]:
            for model_class in model_class_names:
                assert model_class not in return_annotation, (
                    f"Method {method_name} return type annotation '{return_annotation}' "
                    f"should not reference model class '{model_class}'. "
                    f"Use Dict[str, Any] instead."
                )


# Additional edge case tests to ensure robust type handling
class TestEdgeCaseTypeHandling:
    """Test edge cases for type handling in refactored services"""
    
    def test_none_handling_in_campaign_list_service(self):
        """Test that services handle None returns properly"""
        mock_repo = Mock(spec=CampaignListRepository)
        mock_repo.get_by_id.return_value = None
        
        service = CampaignListServiceRefactored(
            campaign_list_repository=mock_repo,
            member_repository=Mock(),
            contact_repository=Mock()
        )
        
        result = service.get_campaign_list_by_id(999)
        
        # Should return Result.failure, not try to work with a model object
        assert result.is_failure
        assert 'not found' in result.error.lower()
    
    def test_none_handling_in_campaign_service(self):
        """Test that services handle None returns properly"""
        mock_repo = Mock(spec=CampaignRepository)
        mock_repo.get_by_id.return_value = None
        
        service = CampaignService(
            campaign_repository=mock_repo,
            contact_repository=Mock(),
            contact_flag_repository=Mock()
        )
        
        result = service.get_by_id(999)
        
        # Should return None, not try to access model attributes
        assert result is None