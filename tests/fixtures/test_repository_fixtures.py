"""Tests for Repository Mock Factory - TDD RED Phase

This test suite verifies the repository mock factory provides:
1. Mock implementations of all repository methods
2. BaseRepository interface support
3. In-memory data storage for testing
4. Integration with service fixtures
5. Testing without database dependencies
"""

import pytest
from unittest.mock import Mock, MagicMock, call
from typing import List, Optional, Dict, Any
from datetime import datetime
from repositories.base_repository import PaginationParams, PaginatedResult, SortOrder


class TestRepositoryMockFactory:
    """Test the RepositoryMockFactory class"""
    
    def test_factory_initialization(self):
        """Test that factory initializes correctly"""
        from tests.fixtures.repository_fixtures import RepositoryMockFactory
        
        factory = RepositoryMockFactory()
        assert factory is not None
        assert hasattr(factory, 'create_mock')
        assert hasattr(factory, 'create_with_data')
    
    def test_create_basic_repository_mock(self):
        """Test creating a basic repository mock"""
        from tests.fixtures.repository_fixtures import RepositoryMockFactory
        
        factory = RepositoryMockFactory()
        mock_repo = factory.create_mock('contact')
        
        # Should have all BaseRepository methods
        assert hasattr(mock_repo, 'create')
        assert hasattr(mock_repo, 'get_by_id')
        assert hasattr(mock_repo, 'get_all')
        assert hasattr(mock_repo, 'update')
        assert hasattr(mock_repo, 'delete')
        assert hasattr(mock_repo, 'find_by')
        assert hasattr(mock_repo, 'find_one_by')
        assert hasattr(mock_repo, 'exists')
        assert hasattr(mock_repo, 'count')
        assert hasattr(mock_repo, 'get_paginated')
        assert hasattr(mock_repo, 'create_many')
        assert hasattr(mock_repo, 'update_many')
        assert hasattr(mock_repo, 'delete_many')
        assert hasattr(mock_repo, 'search')
        assert hasattr(mock_repo, 'commit')
        assert hasattr(mock_repo, 'rollback')
        assert hasattr(mock_repo, 'flush')
    
    def test_repository_with_in_memory_storage(self):
        """Test repository mock with in-memory storage"""
        from tests.fixtures.repository_fixtures import RepositoryMockFactory
        
        factory = RepositoryMockFactory()
        mock_repo = factory.create_with_data('contact')
        
        # Test create
        contact_data = {'id': 1, 'phone': '+15551234567', 'name': 'Test User'}
        created = mock_repo.create(**contact_data)
        assert created['id'] == 1
        assert created['phone'] == '+15551234567'
        
        # Test get_by_id
        retrieved = mock_repo.get_by_id(1)
        assert retrieved == created
        
        # Test get_all
        all_items = mock_repo.get_all()
        assert len(all_items) == 1
        assert all_items[0] == created
    
    def test_repository_crud_operations(self):
        """Test full CRUD operations with in-memory storage"""
        from tests.fixtures.repository_fixtures import RepositoryMockFactory
        
        factory = RepositoryMockFactory()
        mock_repo = factory.create_with_data('todo')
        
        # Create
        todo = mock_repo.create(
            title='Test Todo',
            description='Test Description',
            priority='high',
            user_id=1
        )
        assert todo['id'] is not None
        assert todo['title'] == 'Test Todo'
        
        # Read
        retrieved = mock_repo.get_by_id(todo['id'])
        assert retrieved == todo
        
        # Update
        updated = mock_repo.update(todo, title='Updated Todo')
        assert updated['title'] == 'Updated Todo'
        assert updated['id'] == todo['id']
        
        # Delete
        result = mock_repo.delete(todo)
        assert result is True
        assert mock_repo.get_by_id(todo['id']) is None
    
    def test_repository_find_methods(self):
        """Test find_by and find_one_by methods"""
        from tests.fixtures.repository_fixtures import RepositoryMockFactory
        
        factory = RepositoryMockFactory()
        mock_repo = factory.create_with_data('contact')
        
        # Create test data
        mock_repo.create(id=1, phone='+15551234567', name='Alice', tag='customer')
        mock_repo.create(id=2, phone='+15551234568', name='Bob', tag='lead')
        mock_repo.create(id=3, phone='+15551234569', name='Charlie', tag='customer')
        
        # Test find_by
        customers = mock_repo.find_by(tag='customer')
        assert len(customers) == 2
        assert customers[0]['name'] == 'Alice'
        assert customers[1]['name'] == 'Charlie'
        
        # Test find_one_by
        bob = mock_repo.find_one_by(name='Bob')
        assert bob is not None
        assert bob['phone'] == '+15551234568'
    
    def test_repository_pagination(self):
        """Test pagination support"""
        from tests.fixtures.repository_fixtures import RepositoryMockFactory
        
        factory = RepositoryMockFactory()
        mock_repo = factory.create_with_data('contact')
        
        # Create 25 test items
        for i in range(1, 26):
            mock_repo.create(id=i, name=f'Contact {i}', phone=f'+1555123456{i:02d}')
        
        # Test pagination
        pagination = PaginationParams(page=1, per_page=10)
        result = mock_repo.get_paginated(pagination)
        
        assert isinstance(result, PaginatedResult)
        assert len(result.items) == 10
        assert result.total == 25
        assert result.pages == 3
        assert result.has_next is True
        assert result.has_prev is False
        
        # Test page 2
        pagination = PaginationParams(page=2, per_page=10)
        result = mock_repo.get_paginated(pagination)
        assert len(result.items) == 10
        assert result.has_next is True
        assert result.has_prev is True
    
    def test_repository_with_filters(self):
        """Test repository methods with filters"""
        from tests.fixtures.repository_fixtures import RepositoryMockFactory
        
        factory = RepositoryMockFactory()
        mock_repo = factory.create_with_data('activity')
        
        # Create test data
        mock_repo.create(id=1, type='call', contact_id=1, status='completed')
        mock_repo.create(id=2, type='sms', contact_id=1, status='pending')
        mock_repo.create(id=3, type='call', contact_id=2, status='completed')
        
        # Test count with filters
        call_count = mock_repo.count(type='call')
        assert call_count == 2
        
        # Test exists
        assert mock_repo.exists(type='call', contact_id=1) is True
        assert mock_repo.exists(type='email', contact_id=1) is False
    
    def test_todo_repository_specific_methods(self):
        """Test TodoRepository specific methods"""
        from tests.fixtures.repository_fixtures import create_todo_repository_mock
        
        mock_repo = create_todo_repository_mock()
        
        # Create test todos
        todo1 = mock_repo.create(
            id=1, title='Todo 1', priority='high',
            user_id=1, is_completed=False
        )
        todo2 = mock_repo.create(
            id=2, title='Todo 2', priority='low',
            user_id=1, is_completed=True
        )
        todo3 = mock_repo.create(
            id=3, title='Todo 3', priority='high',
            user_id=2, is_completed=False
        )
        
        # Test find_by_priority
        high_priority = mock_repo.find_by_priority('high')
        assert len(high_priority) == 2
        
        # Test find_completed_todos
        completed = mock_repo.find_completed_todos()
        assert len(completed) == 1
        assert completed[0]['id'] == 2
        
        # Test find_pending_todos
        pending = mock_repo.find_pending_todos()
        assert len(pending) == 2
        
        # Test mark_as_completed
        updated = mock_repo.mark_as_completed(1)
        assert updated['is_completed'] is True
        
        # Test find_by_user_id
        user_todos = mock_repo.find_by_user_id(1)
        assert len(user_todos) == 2
        
        # Test count methods
        assert mock_repo.count_by_user_id(1) == 2
        assert mock_repo.count_completed_by_user_id(1) == 2  # After marking one complete
        assert mock_repo.count_pending_by_user_id(2) == 1
    
    def test_contact_repository_specific_methods(self):
        """Test ContactRepository specific methods"""
        from tests.fixtures.repository_fixtures import create_contact_repository_mock
        
        mock_repo = create_contact_repository_mock()
        
        # Create test contacts
        contact1 = mock_repo.create(
            id=1, phone='+15551234567', name='Alice',
            tag='customer', last_activity_at=datetime(2025, 1, 10)
        )
        contact2 = mock_repo.create(
            id=2, phone='+15551234568', name='Bob',
            tag='lead', last_activity_at=datetime(2025, 1, 15)
        )
        
        # Test find_by_phone
        contact = mock_repo.find_by_phone('+15551234567')
        assert contact is not None
        assert contact['name'] == 'Alice'
        
        # Test find_by_tag
        customers = mock_repo.find_by_tag('customer')
        assert len(customers) == 1
        
        # Test get_recent_contacts
        recent = mock_repo.get_recent_contacts(limit=10)
        assert len(recent) == 2
        assert recent[0]['name'] == 'Bob'  # More recent activity
        
        # Test search
        results = mock_repo.search('Alice')
        assert len(results) == 1
    
    def test_campaign_repository_specific_methods(self):
        """Test CampaignRepository specific methods"""
        from tests.fixtures.repository_fixtures import create_campaign_repository_mock
        
        mock_repo = create_campaign_repository_mock()
        
        # Create test campaigns
        campaign1 = mock_repo.create(
            id=1, name='Campaign 1', status='active',
            type='sms', created_at=datetime(2025, 1, 1)
        )
        campaign2 = mock_repo.create(
            id=2, name='Campaign 2', status='paused',
            type='email', created_at=datetime(2025, 1, 5)
        )
        
        # Test find_active_campaigns
        active = mock_repo.find_active_campaigns()
        assert len(active) == 1
        assert active[0]['name'] == 'Campaign 1'
        
        # Test find_by_status
        paused = mock_repo.find_by_status('paused')
        assert len(paused) == 1
        
        # Test update_status
        updated = mock_repo.update_status(2, 'active')
        assert updated['status'] == 'active'
        
        # Test get_campaign_with_stats
        stats = mock_repo.get_campaign_with_stats(1)
        assert stats is not None
        assert 'total_recipients' in stats
    
    def test_repository_mock_integration_with_services(self):
        """Test repository mocks integrate with service mocks"""
        from tests.fixtures.repository_fixtures import RepositoryMockFactory
        from tests.fixtures.service_fixtures import ServiceMockFactory
        
        repo_factory = RepositoryMockFactory()
        service_factory = ServiceMockFactory()
        
        # Create repository mock
        todo_repo = repo_factory.create_with_data('todo')
        
        # Create service mock with repository
        todo_service = service_factory.create_mock('todo')
        todo_service.repository = todo_repo
        
        # Test service can use repository
        todo_data = {
            'title': 'Test Todo',
            'description': 'Test',
            'priority': 'high',
            'user_id': 1
        }
        
        # Configure service to use repository
        def create_todo_side_effect(user_id, data):
            todo_data = {'user_id': user_id, **data}
            return todo_repo.create(**todo_data)
        
        todo_service.create_todo.side_effect = create_todo_side_effect
        
        # Create todo through service
        created = todo_service.create_todo(1, todo_data)
        assert created['title'] == 'Test Todo'
        
        # Verify it's in repository
        retrieved = todo_repo.get_by_id(created['id'])
        assert retrieved == created
    
    def test_repository_bulk_operations(self):
        """Test bulk create, update, and delete operations"""
        from tests.fixtures.repository_fixtures import RepositoryMockFactory
        
        factory = RepositoryMockFactory()
        mock_repo = factory.create_with_data('contact')
        
        # Test bulk create
        contacts_data = [
            {'name': 'Alice', 'phone': '+15551234567'},
            {'name': 'Bob', 'phone': '+15551234568'},
            {'name': 'Charlie', 'phone': '+15551234569'}
        ]
        created = mock_repo.create_many(contacts_data)
        assert len(created) == 3
        
        # Test bulk update
        updated_count = mock_repo.update_many(
            {'name': 'Alice'},
            {'tag': 'vip'}
        )
        assert updated_count == 1
        
        alice = mock_repo.find_one_by(name='Alice')
        assert alice['tag'] == 'vip'
        
        # Test bulk delete
        deleted_count = mock_repo.delete_many({'tag': 'vip'})
        assert deleted_count == 1
        assert mock_repo.count() == 2
    
    def test_repository_transaction_methods(self):
        """Test transaction management methods"""
        from tests.fixtures.repository_fixtures import RepositoryMockFactory
        
        factory = RepositoryMockFactory()
        mock_repo = factory.create_with_data('invoice')
        
        # Test commit tracking
        mock_repo.create(id=1, amount=100.0)
        mock_repo.commit()
        assert mock_repo.commit.called
        
        # Test rollback
        mock_repo.create(id=2, amount=200.0)
        mock_repo.rollback()
        assert mock_repo.rollback.called
        
        # Test flush
        mock_repo.flush()
        assert mock_repo.flush.called
    
    def test_repository_factory_helper_functions(self):
        """Test helper functions for creating repository mocks"""
        from tests.fixtures.repository_fixtures import (
            create_contact_repository_mock,
            create_todo_repository_mock,
            create_campaign_repository_mock,
            create_activity_repository_mock,
            create_conversation_repository_mock,
            create_all_repository_mocks
        )
        
        # Test individual repository creation
        contact_repo = create_contact_repository_mock()
        assert contact_repo is not None
        assert hasattr(contact_repo, 'find_by_phone')
        
        todo_repo = create_todo_repository_mock()
        assert hasattr(todo_repo, 'find_by_priority')
        
        campaign_repo = create_campaign_repository_mock()
        assert hasattr(campaign_repo, 'find_active_campaigns')
        
        # Test create all repositories
        all_repos = create_all_repository_mocks()
        assert 'contact' in all_repos
        assert 'todo' in all_repos
        assert 'campaign' in all_repos
        assert 'activity' in all_repos
        assert 'conversation' in all_repos
        assert len(all_repos) >= 20  # Should have all repositories


class TestRepositoryPytestFixtures:
    """Test pytest fixtures for repositories"""
    
    def test_mock_repositories_fixture(self, mock_repositories):
        """Test the mock_repositories fixture provides all repositories"""
        assert 'contact' in mock_repositories
        assert 'todo' in mock_repositories
        assert 'campaign' in mock_repositories
        
        # Test they have correct methods
        assert hasattr(mock_repositories['contact'], 'find_by_phone')
        assert hasattr(mock_repositories['todo'], 'find_by_priority')
    
    def test_contact_repository_fixture(self, contact_repository):
        """Test contact repository fixture"""
        # Create a contact
        contact = contact_repository.create(
            phone='+15551234567',
            name='Test User'
        )
        
        # Retrieve it
        retrieved = contact_repository.get_by_id(contact['id'])
        assert retrieved == contact
    
    def test_todo_repository_fixture(self, todo_repository):
        """Test todo repository fixture"""
        # Create a todo
        todo = todo_repository.create(
            title='Test Todo',
            priority='high',
            user_id=1
        )
        
        # Test specific methods
        high_priority = todo_repository.find_by_priority('high')
        assert len(high_priority) == 1