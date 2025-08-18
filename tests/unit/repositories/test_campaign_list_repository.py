"""
Unit tests for CampaignListRepository
Follows TDD methodology - these tests should FAIL initially
"""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timedelta
from typing import List, Dict, Any

from repositories.campaign_list_repository import CampaignListRepository
from repositories.base_repository import PaginationParams, PaginatedResult, SortOrder
from crm_database import CampaignList
from tests.fixtures.factories.campaign_factory import CampaignListFactory


class TestCampaignListRepository:
    """Test suite for CampaignListRepository"""
    
    @pytest.fixture
    def repository(self, db_session):
        """Create repository instance with mocked session"""
        return CampaignListRepository(session=db_session, model_class=CampaignList)
    
    @pytest.fixture
    def sample_campaign_list(self, db_session):
        """Create a sample campaign list for testing"""
        campaign_list = CampaignListFactory()
        db_session.add(campaign_list)
        db_session.flush()
        return campaign_list
    
    def test_create_campaign_list(self, repository, db_session):
        """Test creating a new campaign list"""
        # Arrange
        list_data = {
            'name': 'Test Campaign List',
            'description': 'Test description',
            'created_by': 'test-user',
            'is_dynamic': False,
            'filter_criteria': {'source': 'test'}
        }
        
        # Act
        campaign_list = repository.create(**list_data)
        
        # Assert
        assert campaign_list is not None
        assert campaign_list.name == 'Test Campaign List'
        assert campaign_list.description == 'Test description'
        assert campaign_list.created_by == 'test-user'
        assert campaign_list.is_dynamic is False
        assert campaign_list.filter_criteria == {'source': 'test'}
        assert campaign_list.id is not None
        assert campaign_list.created_at is not None
    
    def test_get_by_id(self, repository, sample_campaign_list):
        """Test retrieving campaign list by ID"""
        # Act
        found_list = repository.get_by_id(sample_campaign_list.id)
        
        # Assert
        assert found_list is not None
        assert found_list.id == sample_campaign_list.id
        assert found_list.name == sample_campaign_list.name
    
    def test_get_by_id_not_found(self, repository):
        """Test retrieving non-existent campaign list"""
        # Act
        found_list = repository.get_by_id(99999)
        
        # Assert
        assert found_list is None
    
    def test_find_by_name(self, repository, sample_campaign_list):
        """Test finding campaign list by name"""
        # Act
        found_lists = repository.find_by(name=sample_campaign_list.name)
        
        # Assert
        assert len(found_lists) == 1
        assert found_lists[0].name == sample_campaign_list.name
    
    def test_find_dynamic_lists(self, repository, db_session):
        """Test finding only dynamic campaign lists"""
        # Arrange
        static_list = CampaignListFactory(is_dynamic=False)
        dynamic_list = CampaignListFactory(is_dynamic=True)
        db_session.add_all([static_list, dynamic_list])
        db_session.flush()
        
        # Act
        dynamic_lists = repository.find_by(is_dynamic=True)
        
        # Assert
        assert len(dynamic_lists) == 1
        assert dynamic_lists[0].id == dynamic_list.id
        assert dynamic_lists[0].is_dynamic is True
    
    def test_get_all_ordered_by_created_desc(self, repository, db_session):
        """Test getting all lists ordered by creation date descending"""
        # Arrange
        # Create lists with different creation times
        older_list = CampaignListFactory(created_at=datetime.utcnow() - timedelta(days=2))
        newer_list = CampaignListFactory(created_at=datetime.utcnow() - timedelta(days=1))
        db_session.add_all([older_list, newer_list])
        db_session.flush()
        
        # Act
        all_lists = repository.get_all(order_by='created_at', order=SortOrder.DESC)
        
        # Assert
        assert len(all_lists) >= 2
        # Newer list should be first
        newer_found = False
        older_found = False
        for i, campaign_list in enumerate(all_lists):
            if campaign_list.id == newer_list.id:
                newer_found = True
                newer_index = i
            elif campaign_list.id == older_list.id:
                older_found = True
                older_index = i
        
        assert newer_found and older_found
        assert newer_index < older_index
    
    def test_update_campaign_list(self, repository, sample_campaign_list):
        """Test updating campaign list fields"""
        # Act
        updated_list = repository.update(
            sample_campaign_list,
            name='Updated Name',
            description='Updated description'
        )
        
        # Assert
        assert updated_list.name == 'Updated Name'
        assert updated_list.description == 'Updated description'
        assert updated_list.updated_at is not None
    
    def test_update_by_id(self, repository, sample_campaign_list):
        """Test updating campaign list by ID"""
        # Act
        updated_list = repository.update_by_id(
            sample_campaign_list.id,
            name='Updated via ID'
        )
        
        # Assert
        assert updated_list is not None
        assert updated_list.name == 'Updated via ID'
    
    def test_update_by_id_not_found(self, repository):
        """Test updating non-existent campaign list"""
        # Act
        result = repository.update_by_id(99999, name='Should not work')
        
        # Assert
        assert result is None
    
    def test_delete_campaign_list(self, repository, sample_campaign_list, db_session):
        """Test deleting a campaign list"""
        # Arrange
        list_id = sample_campaign_list.id
        
        # Act
        success = repository.delete(sample_campaign_list)
        
        # Assert
        assert success is True
        # Verify it's actually deleted
        found_list = repository.get_by_id(list_id)
        assert found_list is None
    
    def test_delete_by_id(self, repository, sample_campaign_list):
        """Test deleting campaign list by ID"""
        # Arrange
        list_id = sample_campaign_list.id
        
        # Act
        success = repository.delete_by_id(list_id)
        
        # Assert
        assert success is True
        # Verify it's actually deleted
        found_list = repository.get_by_id(list_id)
        assert found_list is None
    
    def test_count_all(self, repository, db_session):
        """Test counting all campaign lists"""
        # Arrange
        initial_count = repository.count()
        new_list = CampaignListFactory()
        db_session.add(new_list)
        db_session.flush()
        
        # Act
        new_count = repository.count()
        
        # Assert
        assert new_count == initial_count + 1
    
    def test_count_with_filter(self, repository, db_session):
        """Test counting campaign lists with filters"""
        # Arrange
        dynamic_count_before = repository.count(is_dynamic=True)
        new_dynamic_list = CampaignListFactory(is_dynamic=True)
        db_session.add(new_dynamic_list)
        db_session.flush()
        
        # Act
        dynamic_count_after = repository.count(is_dynamic=True)
        
        # Assert
        assert dynamic_count_after == dynamic_count_before + 1
    
    def test_exists(self, repository, sample_campaign_list):
        """Test checking if campaign list exists"""
        # Act & Assert
        assert repository.exists(id=sample_campaign_list.id) is True
        assert repository.exists(id=99999) is False
        assert repository.exists(name=sample_campaign_list.name) is True
        assert repository.exists(name='Non-existent List') is False
    
    def test_search_by_name(self, repository, db_session):
        """Test searching campaign lists by name"""
        # Arrange
        list1 = CampaignListFactory(name='Summer Campaign 2024')
        list2 = CampaignListFactory(name='Winter Sale List')
        list3 = CampaignListFactory(name='Spring Promotion Campaign')
        db_session.add_all([list1, list2, list3])
        db_session.flush()
        
        # Act
        campaign_results = repository.search('Campaign')
        sale_results = repository.search('Sale')
        winter_results = repository.search('winter')
        
        # Assert
        campaign_result_ids = [r.id for r in campaign_results]
        assert list1.id in campaign_result_ids
        assert list3.id in campaign_result_ids
        assert list2.id not in campaign_result_ids
        
        sale_result_ids = [r.id for r in sale_results]
        assert list2.id in sale_result_ids
        assert list1.id not in sale_result_ids
        
        winter_result_ids = [r.id for r in winter_results]
        assert list2.id in winter_result_ids
    
    def test_search_by_description(self, repository, db_session):
        """Test searching campaign lists by description"""
        # Arrange
        list1 = CampaignListFactory(description='Customers who bought products in Q1')
        list2 = CampaignListFactory(description='VIP members eligible for discount')
        db_session.add_all([list1, list2])
        db_session.flush()
        
        # Act
        customer_results = repository.search('customers')
        vip_results = repository.search('VIP')
        
        # Assert
        customer_result_ids = [r.id for r in customer_results]
        assert list1.id in customer_result_ids
        assert list2.id not in customer_result_ids
        
        vip_result_ids = [r.id for r in vip_results]
        assert list2.id in vip_result_ids
        assert list1.id not in vip_result_ids
    
    def test_get_paginated(self, repository, db_session):
        """Test getting paginated campaign lists"""
        # Arrange
        lists = [CampaignListFactory() for _ in range(5)]
        db_session.add_all(lists)
        db_session.flush()
        
        pagination = PaginationParams(page=1, per_page=2)
        
        # Act
        result = repository.get_paginated(
            pagination=pagination,
            order_by='created_at',
            order=SortOrder.DESC
        )
        
        # Assert
        assert isinstance(result, PaginatedResult)
        assert len(result.items) == 2
        assert result.total >= 5  # At least the 5 we created
        assert result.page == 1
        assert result.per_page == 2
        assert result.pages >= 3  # ceil(5/2) = 3
    
    def test_get_lists_by_created_by(self, repository, db_session):
        """Test finding lists by creator"""
        # Arrange
        user1_lists = [CampaignListFactory(created_by='user1') for _ in range(2)]
        user2_lists = [CampaignListFactory(created_by='user2') for _ in range(3)]
        db_session.add_all(user1_lists + user2_lists)
        db_session.flush()
        
        # Act
        user1_found = repository.find_by(created_by='user1')
        user2_found = repository.find_by(created_by='user2')
        
        # Assert
        assert len(user1_found) == 2
        assert len(user2_found) == 3
        
        user1_ids = [l.id for l in user1_lists]
        user2_ids = [l.id for l in user2_lists]
        
        found_user1_ids = [l.id for l in user1_found]
        found_user2_ids = [l.id for l in user2_found]
        
        assert set(found_user1_ids) == set(user1_ids)
        assert set(found_user2_ids) == set(user2_ids)
