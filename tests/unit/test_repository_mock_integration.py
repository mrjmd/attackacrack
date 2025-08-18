"""
Integration test demonstrating repository mocks with services

This shows how the repository mock factory enables testing without database dependencies.
"""
import pytest
from tests.fixtures.repository_fixtures import (
    RepositoryMockFactory, 
    create_todo_repository_mock,
    create_contact_repository_mock,
    create_campaign_repository_mock
)
from services.todo_service_refactored import TodoService
from services.common.result import Result


class TestRepositoryMockIntegration:
    """Test that repository mocks integrate correctly with services"""
    
    def test_todo_service_with_mock_repository(self):
        """Test TodoService with mock repository"""
        # Create mock repository with in-memory storage
        mock_repo = create_todo_repository_mock(with_data=True)
        
        # Create service with mock repository
        todo_service = TodoService(todo_repository=mock_repo)
        
        # Test create
        result = todo_service.create_todo(1, {
            'title': 'Test Todo',
            'description': 'Test Description',
            'priority': 'high'
        })
        
        assert result.success is True
        assert result.data['title'] == 'Test Todo'
        
        # Test get - should retrieve from mock storage
        todos = todo_service.get_user_todos(1)
        assert len(todos) == 1
        assert todos[0]['title'] == 'Test Todo'
    
    def test_repository_mock_factory(self):
        """Test the repository mock factory"""
        factory = RepositoryMockFactory()
        
        # Test creating different repository types
        contact_repo = factory.create_with_data('contact')
        todo_repo = factory.create_with_data('todo')
        campaign_repo = factory.create_with_data('campaign')
        
        # Test that each has appropriate methods
        assert hasattr(contact_repo, 'find_by_phone')
        assert hasattr(todo_repo, 'find_by_priority')
        assert hasattr(campaign_repo, 'find_active_campaigns')
        
        # Test basic CRUD operations
        contact = contact_repo.create(
            phone='+15551234567',
            name='Test User'
        )
        assert contact['phone'] == '+15551234567'
        
        retrieved = contact_repo.get_by_id(contact['id'])
        assert retrieved == contact
    
    def test_repository_in_memory_storage(self):
        """Test that in-memory storage works correctly"""
        repo = create_todo_repository_mock(with_data=True)
        
        # Create multiple items
        todo1 = repo.create(title='Todo 1', priority='high', user_id=1)
        todo2 = repo.create(title='Todo 2', priority='low', user_id=1)
        todo3 = repo.create(title='Todo 3', priority='high', user_id=2)
        
        # Test filtering
        high_priority = repo.find_by_priority('high')
        assert len(high_priority) == 2
        
        user1_todos = repo.find_by_user_id(1)
        assert len(user1_todos) == 2
        
        # Test update
        updated = repo.update_by_id(todo1['id'], title='Updated Todo 1')
        assert updated['title'] == 'Updated Todo 1'
        
        # Test delete
        deleted = repo.delete_by_id(todo2['id'])
        assert deleted is True
        assert repo.get_by_id(todo2['id']) is None
        assert len(repo.get_all()) == 2
    
    def test_repository_pagination(self):
        """Test pagination support in repository mocks"""
        from repositories.base_repository import PaginationParams
        
        repo = create_contact_repository_mock(with_data=True)
        
        # Create 25 contacts
        for i in range(1, 26):
            repo.create(
                name=f'Contact {i}',
                phone=f'+155512345{i:02d}'
            )
        
        # Test pagination
        page1 = repo.get_paginated(PaginationParams(page=1, per_page=10))
        assert len(page1.items) == 10
        assert page1.total == 25
        assert page1.pages == 3
        assert page1.has_next is True
        assert page1.has_prev is False
        
        page2 = repo.get_paginated(PaginationParams(page=2, per_page=10))
        assert len(page2.items) == 10
        assert page2.has_next is True
        assert page2.has_prev is True
        
        page3 = repo.get_paginated(PaginationParams(page=3, per_page=10))
        assert len(page3.items) == 5
        assert page3.has_next is False
        assert page3.has_prev is True
    
    def test_campaign_repository_specific_methods(self):
        """Test campaign repository specific functionality"""
        repo = create_campaign_repository_mock(with_data=True)
        
        # Create campaigns
        campaign1 = repo.create(name='Campaign 1', status='active')
        campaign2 = repo.create(name='Campaign 2', status='paused')
        campaign3 = repo.create(name='Campaign 3', status='active')
        
        # Test find active campaigns
        active = repo.find_active_campaigns()
        assert len(active) == 2
        assert all(c['status'] == 'active' for c in active)
        
        # Test update status
        updated = repo.update_status(campaign2['id'], 'active')
        assert updated['status'] == 'active'
        
        # Now should have 3 active campaigns
        active = repo.find_active_campaigns()
        assert len(active) == 3
        
        # Test get with stats
        stats = repo.get_campaign_with_stats(campaign1['id'])
        assert stats is not None
        assert 'total_recipients' in stats
        assert 'messages_sent' in stats
    
    def test_repository_isolation_between_tests(self):
        """Test that each repository instance is isolated"""
        # Create two separate repositories
        repo1 = create_todo_repository_mock(with_data=True)
        repo2 = create_todo_repository_mock(with_data=True)
        
        # Add data to repo1
        repo1.create(title='Repo1 Todo', user_id=1)
        
        # repo2 should be empty
        assert len(repo2.get_all()) == 0
        
        # Add data to repo2
        repo2.create(title='Repo2 Todo', user_id=1)
        
        # Each should have only their own data
        assert len(repo1.get_all()) == 1
        assert len(repo2.get_all()) == 1
        assert repo1.get_all()[0]['title'] == 'Repo1 Todo'
        assert repo2.get_all()[0]['title'] == 'Repo2 Todo'
    
    def test_repository_mock_without_storage(self):
        """Test creating pure mocks without in-memory storage"""
        factory = RepositoryMockFactory()
        
        # Create pure mock (no storage)
        mock_repo = factory.create_mock('contact')
        
        # It should have all methods but they're just mocks
        assert hasattr(mock_repo, 'create')
        assert hasattr(mock_repo, 'get_by_id')
        assert hasattr(mock_repo, 'find_by_phone')
        
        # Can configure mock behavior
        mock_repo.get_by_id.return_value = {'id': 1, 'name': 'Mocked'}
        result = mock_repo.get_by_id(1)
        assert result == {'id': 1, 'name': 'Mocked'}
    
    def test_bulk_operations(self):
        """Test bulk create, update, and delete operations"""
        repo = create_contact_repository_mock(with_data=True)
        
        # Bulk create
        contacts_data = [
            {'name': 'Alice', 'phone': '+15551234567'},
            {'name': 'Bob', 'phone': '+15551234568'},
            {'name': 'Charlie', 'phone': '+15551234569'}
        ]
        created = repo.create_many(contacts_data)
        assert len(created) == 3
        
        # Bulk update
        updated_count = repo.update_many(
            {'name': 'Alice'},
            {'tag': 'vip'}
        )
        assert updated_count == 1
        
        alice = repo.find_one_by(name='Alice')
        assert alice['tag'] == 'vip'
        
        # Bulk delete
        deleted_count = repo.delete_many({'tag': 'vip'})
        assert deleted_count == 1
        assert repo.count() == 2


class TestRepositoryMockDocumentation:
    """Test examples that serve as documentation"""
    
    def test_basic_usage_example(self):
        """Example: Basic repository mock usage"""
        # Create a repository mock with in-memory storage
        repo = create_contact_repository_mock(with_data=True)
        
        # Create a contact
        contact = repo.create(
            name='John Doe',
            phone='+15551234567',
            email='john@example.com'
        )
        
        # Retrieve by ID
        retrieved = repo.get_by_id(contact['id'])
        assert retrieved['name'] == 'John Doe'
        
        # Find by phone
        found = repo.find_by_phone('+15551234567')
        assert found is not None
        
        # Update
        updated = repo.update(contact, email='newemail@example.com')
        assert updated['email'] == 'newemail@example.com'
        
        # Delete
        deleted = repo.delete(contact)
        assert deleted is True
    
    def test_service_with_repository_example(self):
        """Example: Using repository mock with a service"""
        # Create repository
        todo_repo = create_todo_repository_mock(with_data=True)
        
        # Create service with repository
        todo_service = TodoService(todo_repository=todo_repo)
        
        # Use service normally
        result = todo_service.create_todo(1, {
            'title': 'Learn Repository Pattern',
            'priority': 'high'
        })
        
        assert result.success is True
        
        # The data is stored in the mock repository
        todos = todo_repo.find_by_user_id(1)
        assert len(todos) == 1
        assert todos[0]['title'] == 'Learn Repository Pattern'