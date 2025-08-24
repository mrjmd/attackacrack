"""Repository Mock Factory - Comprehensive mocking system for repositories.

This module provides:
1. Mock implementations of all repository methods
2. Support for the BaseRepository interface
3. In-memory data storage for testing
4. Integration with service fixtures
5. Testing without database dependencies

Usage:
    # Create a basic mock
    factory = RepositoryMockFactory()
    mock_repo = factory.create_mock('contact')
    
    # Create with in-memory storage
    mock_repo = factory.create_with_data('contact')
    contact = mock_repo.create(phone='+15551234567', name='Test')
    retrieved = mock_repo.get_by_id(contact['id'])
"""

import threading
from typing import Any, Dict, List, Optional, Set, Callable, TypeVar
from unittest.mock import Mock, MagicMock, create_autospec
from datetime import datetime, date
from utils.datetime_utils import utc_now
from dataclasses import dataclass, field
import copy


class MockModel(dict):
    """A mock model that supports both dict access and attribute access.
    
    This allows our mock repositories to return objects that behave like
    SQLAlchemy models (with .id attributes) while still being dictionaries.
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Ensure every model has an id
        if 'id' not in self:
            self['id'] = None
    
    def __getattr__(self, name):
        """Allow attribute access like model.id"""
        if name in self:
            return self[name]
        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")  
    
    def __setattr__(self, name, value):
        """Allow attribute setting like model.id = 5"""
        self[name] = value
    
    def __delattr__(self, name):
        """Allow attribute deletion"""
        if name in self:
            del self[name]
        else:
            raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")

from repositories.base_repository import (
    BaseRepository, PaginationParams, PaginatedResult, SortOrder
)


# Type variable for generic repository operations
T = TypeVar('T')


class InMemoryStorage:
    """In-memory storage backend for repository mocks.
    
    Provides thread-safe storage with auto-incrementing IDs.
    """
    
    def __init__(self):
        self._data: Dict[int, Dict[str, Any]] = {}
        self._next_id = 1
        self._lock = threading.Lock()
    
    def create(self, **kwargs) -> MockModel:
        """Create a new entity with auto-generated ID."""
        with self._lock:
            if 'id' not in kwargs or kwargs['id'] is None:
                kwargs['id'] = self._next_id
                self._next_id += 1
            else:
                # Update next_id if manually specified ID is higher
                if kwargs['id'] >= self._next_id:
                    self._next_id = kwargs['id'] + 1
            
            # Add timestamps if not present
            now = utc_now()
            if 'created_at' not in kwargs:
                kwargs['created_at'] = now
            if 'updated_at' not in kwargs:
                kwargs['updated_at'] = now
            
            entity = MockModel(kwargs)
            self._data[entity['id']] = entity
            return MockModel(entity)
    
    def get_by_id(self, entity_id: int) -> Optional[MockModel]:
        """Get entity by ID."""
        with self._lock:
            entity = self._data.get(entity_id)
            return MockModel(entity) if entity else None
    
    def get_all(self) -> List[MockModel]:
        """Get all entities."""
        with self._lock:
            return [MockModel(entity) for entity in self._data.values()]
    
    def update(self, entity_id: int, **updates) -> Optional[MockModel]:
        """Update an entity."""
        with self._lock:
            if entity_id in self._data:
                self._data[entity_id].update(updates)
                self._data[entity_id]['updated_at'] = utc_now()
                return MockModel(self._data[entity_id])
            return None
    
    def delete(self, entity_id: int) -> bool:
        """Delete an entity."""
        with self._lock:
            if entity_id in self._data:
                del self._data[entity_id]
                return True
            return False
    
    def find_by(self, **filters) -> List[MockModel]:
        """Find entities matching filters."""
        with self._lock:
            results = []
            for entity in self._data.values():
                if all(entity.get(k) == v for k, v in filters.items()):
                    results.append(MockModel(entity))
            return results
    
    def count(self, **filters) -> int:
        """Count entities matching filters."""
        if not filters:
            return len(self._data)
        return len(self.find_by(**filters))
    
    def clear(self):
        """Clear all data."""
        with self._lock:
            self._data.clear()
            self._next_id = 1


class MockRepositoryBase:
    """Base class for mock repositories with in-memory storage."""
    
    def __init__(self, storage: Optional[InMemoryStorage] = None):
        self.storage = storage or InMemoryStorage()
        self.session = MagicMock()  # Mock session
        self.model_class = MagicMock()  # Mock model class
        
        # Track method calls
        self.commit = MagicMock()
        self.rollback = MagicMock()
        self.flush = MagicMock()
    
    def create(self, **kwargs) -> MockModel:
        """Create a new entity."""
        return self.storage.create(**kwargs)
    
    def create_many(self, entities_data: List[Dict[str, Any]]) -> List[MockModel]:
        """Create multiple entities."""
        return [self.storage.create(**data) for data in entities_data]
    
    def get_by_id(self, entity_id: int) -> Optional[MockModel]:
        """Get entity by ID."""
        return self.storage.get_by_id(entity_id)
    
    def get_all(self, order_by: Optional[str] = None, 
                order: SortOrder = SortOrder.ASC) -> List[MockModel]:
        """Get all entities with optional ordering."""
        entities = self.storage.get_all()
        
        if order_by and entities:
            reverse = (order == SortOrder.DESC)
            # Sort by the specified field if it exists
            entities.sort(
                key=lambda x: x.get(order_by, ''),
                reverse=reverse
            )
        
        return entities
    
    def get_paginated(self, 
                     pagination: PaginationParams,
                     filters: Optional[Dict[str, Any]] = None,
                     order_by: Optional[str] = None,
                     order: SortOrder = SortOrder.ASC) -> PaginatedResult:
        """Get paginated results."""
        # Get filtered results
        if filters:
            entities = self.find_by(**filters)
        else:
            entities = self.get_all(order_by=order_by, order=order)
        
        # Apply ordering if not already done
        if order_by and filters:
            reverse = (order == SortOrder.DESC)
            entities.sort(
                key=lambda x: x.get(order_by, ''),
                reverse=reverse
            )
        
        # Calculate pagination
        total = len(entities)
        start = pagination.offset
        end = start + pagination.limit
        items = entities[start:end]
        
        return PaginatedResult(
            items=items,
            total=total,
            page=pagination.page,
            per_page=pagination.per_page
        )
    
    def find_by(self, **filters) -> List[MockModel]:
        """Find entities by filters."""
        return self.storage.find_by(**filters)
    
    def find_one_by(self, **filters) -> Optional[MockModel]:
        """Find single entity by filters."""
        results = self.find_by(**filters)
        return results[0] if results else None
    
    def exists(self, **filters) -> bool:
        """Check if entity exists."""
        return len(self.find_by(**filters)) > 0
    
    def count(self, **filters) -> int:
        """Count entities."""
        return self.storage.count(**filters)
    
    def update(self, entity: MockModel, **updates) -> MockModel:
        """Update an entity."""
        entity_id = entity.get('id')
        if entity_id:
            updated = self.storage.update(entity_id, **updates)
            if updated:
                return updated
        # If not found, update the passed entity
        entity.update(updates)
        return entity
    
    def update_by_id(self, entity_id: int, **updates) -> Optional[MockModel]:
        """Update entity by ID."""
        return self.storage.update(entity_id, **updates)
    
    def update_many(self, filters: Dict[str, Any], updates: Dict[str, Any]) -> int:
        """Update multiple entities."""
        entities = self.find_by(**filters)
        for entity in entities:
            self.storage.update(entity['id'], **updates)
        return len(entities)
    
    def delete(self, entity: MockModel) -> bool:
        """Delete an entity."""
        entity_id = entity.get('id')
        if entity_id:
            return self.storage.delete(entity_id)
        return False
    
    def delete_by_id(self, entity_id: int) -> bool:
        """Delete entity by ID."""
        return self.storage.delete(entity_id)
    
    def delete_many(self, filters: Dict[str, Any]) -> int:
        """Delete multiple entities."""
        entities = self.find_by(**filters)
        count = 0
        for entity in entities:
            if self.storage.delete(entity['id']):
                count += 1
        return count
    
    def search(self, query: str, fields: Optional[List[str]] = None) -> List[MockModel]:
        """Search entities by text query."""
        if not query:
            return []
        
        query_lower = query.lower()
        results = []
        
        for entity in self.storage.get_all():
            # If fields specified, search only those
            if fields:
                for field in fields:
                    value = str(entity.get(field, '')).lower()
                    if query_lower in value:
                        results.append(entity)
                        break
            else:
                # Search all string fields
                for value in entity.values():
                    if isinstance(value, str) and query_lower in value.lower():
                        results.append(entity)
                        break
        
        return results


class MockTodoRepository(MockRepositoryBase):
    """Mock TodoRepository with specific methods."""
    
    def find_by_priority(self, priority: str) -> List[Dict[str, Any]]:
        """Find todos by priority."""
        return self.find_by(priority=priority)
    
    def find_completed_todos(self) -> List[Dict[str, Any]]:
        """Find completed todos."""
        return self.find_by(is_completed=True)
    
    def find_pending_todos(self) -> List[Dict[str, Any]]:
        """Find pending todos."""
        return self.find_by(is_completed=False)
    
    def find_overdue_todos(self) -> List[Dict[str, Any]]:
        """Find overdue todos."""
        now = utc_now()
        results = []
        for todo in self.storage.get_all():
            if (not todo.get('is_completed') and 
                todo.get('due_date') and 
                todo['due_date'] < now):
                results.append(todo)
        return results
    
    def mark_as_completed(self, todo_id: int) -> Optional[Dict[str, Any]]:
        """Mark todo as completed."""
        return self.update_by_id(
            todo_id,
            is_completed=True,
            completed_at=utc_now()
        )
    
    def mark_as_pending(self, todo_id: int) -> Optional[Dict[str, Any]]:
        """Mark todo as pending."""
        return self.update_by_id(
            todo_id,
            is_completed=False,
            completed_at=None
        )
    
    def find_by_user_id(self, user_id: int, include_completed: bool = True) -> List[Dict[str, Any]]:
        """Find todos by user ID."""
        todos = self.find_by(user_id=user_id)
        
        if not include_completed:
            todos = [t for t in todos if not t.get('is_completed')]
        
        # Sort by completion status and creation date
        todos.sort(key=lambda x: (x.get('is_completed', False), -x.get('id', 0)))
        return todos
    
    def find_by_user_id_with_priority(self, user_id: int, limit: int = 5) -> List[Dict[str, Any]]:
        """Find incomplete todos for user ordered by priority."""
        todos = self.find_by(user_id=user_id, is_completed=False)
        
        # Priority ordering
        priority_order = {'high': 1, 'medium': 2, 'low': 3}
        todos.sort(key=lambda x: (
            priority_order.get(x.get('priority', 'low'), 4),
            -x.get('id', 0)
        ))
        
        return todos[:limit]
    
    def find_by_id_and_user(self, todo_id: int, user_id: int) -> Optional[Dict[str, Any]]:
        """Find todo by ID and user ID."""
        return self.find_one_by(id=todo_id, user_id=user_id)
    
    def count_by_user_id(self, user_id: int) -> int:
        """Count todos for user."""
        return self.count(user_id=user_id)
    
    def count_completed_by_user_id(self, user_id: int) -> int:
        """Count completed todos for user."""
        return self.count(user_id=user_id, is_completed=True)
    
    def count_pending_by_user_id(self, user_id: int) -> int:
        """Count pending todos for user."""
        return self.count(user_id=user_id, is_completed=False)
    
    def count_high_priority_pending(self, user_id: int) -> int:
        """Count high priority pending todos."""
        return self.count(user_id=user_id, is_completed=False, priority='high')
    
    def count_overdue_by_user_id(self, user_id: int) -> int:
        """Count overdue todos for user."""
        overdue = [t for t in self.find_overdue_todos() if t.get('user_id') == user_id]
        return len(overdue)
    
    def update_priority(self, todo_id: int, priority: str) -> Optional[Dict[str, Any]]:
        """Update todo priority."""
        return self.update_by_id(todo_id, priority=priority)


class MockContactRepository(MockRepositoryBase):
    """Mock ContactRepository with specific methods."""
    
    def find_by_phone(self, phone: str) -> Optional[Dict[str, Any]]:
        """Find contact by phone number."""
        return self.find_one_by(phone=phone)
    
    def find_by_tag(self, tag: str) -> List[Dict[str, Any]]:
        """Find contacts by tag."""
        return self.find_by(tag=tag)
    
    def get_recent_contacts(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent contacts sorted by last activity."""
        contacts = self.get_all()
        # Sort by last_activity_at or created_at
        contacts.sort(
            key=lambda x: x.get('last_activity_at', x.get('created_at', datetime.min)),
            reverse=True
        )
        return contacts[:limit]
    
    def search(self, query: str, fields: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Search contacts."""
        if not fields:
            fields = ['name', 'phone', 'email', 'tag']
        return super().search(query, fields)


class MockCampaignRepository(MockRepositoryBase):
    """Mock CampaignRepository with specific methods."""
    
    def find_active_campaigns(self) -> List[Dict[str, Any]]:
        """Find active campaigns."""
        return self.find_by(status='active')
    
    def find_by_status(self, status: str) -> List[Dict[str, Any]]:
        """Find campaigns by status."""
        return self.find_by(status=status)
    
    def update_status(self, campaign_id: int, status: str) -> Optional[Dict[str, Any]]:
        """Update campaign status."""
        return self.update_by_id(campaign_id, status=status)
    
    def get_campaign_with_stats(self, campaign_id: int) -> Optional[Dict[str, Any]]:
        """Get campaign with statistics."""
        campaign = self.get_by_id(campaign_id)
        if campaign:
            # Add mock statistics
            campaign['total_recipients'] = 100
            campaign['messages_sent'] = 50
            campaign['messages_delivered'] = 48
            campaign['responses_received'] = 12
        return campaign


class MockActivityRepository(MockRepositoryBase):
    """Mock ActivityRepository with specific methods."""
    
    def find_by_contact_id(self, contact_id: int) -> List[Dict[str, Any]]:
        """Find activities by contact ID."""
        return self.find_by(contact_id=contact_id)
    
    def find_recent_activities(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Find recent activities."""
        activities = self.get_all()
        activities.sort(key=lambda x: x.get('created_at', datetime.min), reverse=True)
        return activities[:limit]


class MockConversationRepository(MockRepositoryBase):
    """Mock ConversationRepository with specific methods."""
    
    def find_by_contact_id(self, contact_id: int) -> List[Dict[str, Any]]:
        """Find conversations by contact ID."""
        return self.find_by(contact_id=contact_id)
    
    def find_active_conversations(self) -> List[Dict[str, Any]]:
        """Find active conversations."""
        return self.find_by(status='active')


class MockQuoteRepository(MockRepositoryBase):
    """Mock QuoteRepository with specific methods."""
    
    def find_all_ordered_by_id_desc(self) -> List[MockModel]:
        """Find all quotes ordered by ID descending."""
        quotes = self.get_all()
        quotes.sort(key=lambda x: x.get('id', 0), reverse=True)
        return quotes
    
    def find_by_job_id(self, job_id: int) -> List[MockModel]:
        """Find quotes by job ID."""
        return self.find_by(job_id=job_id)
    
    def find_by_status(self, status: str) -> List[MockModel]:
        """Find quotes by status."""
        return self.find_by(status=status)
    
    def find_draft_quotes_by_job_id(self, job_id: int) -> List[MockModel]:
        """Find draft quotes for a job."""
        return self.find_by(job_id=job_id, status='Draft')
    
    def find_by_quickbooks_id(self, quickbooks_id: str) -> Optional[MockModel]:
        """Find quote by QuickBooks ID."""
        return self.find_one_by(quickbooks_estimate_id=quickbooks_id)
    
    def update_status(self, quote_id: int, status: str) -> Optional[MockModel]:
        """Update quote status."""
        return self.update_by_id(quote_id, status=status)
    
    def calculate_totals(self, quote_id: int) -> Optional[MockModel]:
        """Calculate and update quote totals."""
        quote = self.get_by_id(quote_id)
        if quote:
            total_amount = quote.get('subtotal', 0) + quote.get('tax_amount', 0)
            return self.update_by_id(quote_id, total_amount=total_amount)
        return None


class MockQuoteLineItemRepository(MockRepositoryBase):
    """Mock QuoteLineItemRepository with specific methods."""
    
    def find_by_quote_id(self, quote_id: int) -> List[MockModel]:
        """Find line items by quote ID."""
        return self.find_by(quote_id=quote_id)
    
    def find_by_product_id(self, product_id: int) -> List[MockModel]:
        """Find line items by product ID."""
        return self.find_by(product_id=product_id)
    
    def delete_by_quote_id(self, quote_id: int) -> int:
        """Delete all line items for a quote."""
        line_items = self.find_by_quote_id(quote_id)
        count = 0
        for item in line_items:
            if self.delete(item):
                count += 1
        return count
    
    def calculate_line_total(self, line_item_data: Dict[str, Any]) -> float:
        """Calculate line total from quantity and price."""
        quantity = float(line_item_data.get('quantity', 0))
        unit_price = float(line_item_data.get('unit_price', 
                          line_item_data.get('price', 0)))
        return quantity * unit_price
    
    def bulk_create_line_items(self, quote_id: int, line_items_data: List[Dict[str, Any]]) -> List[MockModel]:
        """Create multiple line items for a quote."""
        created_items = []
        for item_data in line_items_data:
            line_total = self.calculate_line_total(item_data)
            line_item = self.create(
                quote_id=quote_id,
                product_id=item_data.get('product_id'),
                description=item_data.get('description', ''),
                quantity=float(item_data.get('quantity', 0)),
                unit_price=float(item_data.get('unit_price', 
                               item_data.get('price', 0))),
                line_total=line_total
            )
            created_items.append(line_item)
        return created_items
    
    def bulk_update_line_items(self, line_items_data: List[Dict[str, Any]]) -> List[MockModel]:
        """Update multiple line items."""
        updated_items = []
        for item_data in line_items_data:
            item_id = item_data.get('id')
            if item_id:
                existing_item = self.get_by_id(item_id)
                if existing_item:
                    line_total = self.calculate_line_total(item_data)
                    updated_item = self.update_by_id(
                        item_id,
                        product_id=item_data.get('product_id', existing_item.get('product_id')),
                        description=item_data.get('description', existing_item.get('description')),
                        quantity=float(item_data.get('quantity', existing_item.get('quantity', 0))),
                        unit_price=float(item_data.get('unit_price', 
                                       item_data.get('price', existing_item.get('unit_price', 0)))),
                        line_total=line_total
                    )
                    if updated_item:
                        updated_items.append(updated_item)
        return updated_items


class RepositoryMockFactory:
    """Factory for creating repository mocks with appropriate methods."""
    
    def __init__(self):
        self._repository_classes = {
            'todo': MockTodoRepository,
            'contact': MockContactRepository,
            'campaign': MockCampaignRepository,
            'activity': MockActivityRepository,
            'conversation': MockConversationRepository,
            'quote': MockQuoteRepository,
            'quote_line_item': MockQuoteLineItemRepository,
            # Default to base for others
        }
    
    def create_mock(self, repository_name: str) -> Mock:
        """Create a basic mock repository without storage.
        
        Args:
            repository_name: Name of the repository (e.g., 'contact', 'todo')
            
        Returns:
            Mock repository with all methods mocked
        """
        # Get the appropriate class
        repo_class = self._repository_classes.get(
            repository_name,
            MockRepositoryBase
        )
        
        # Create mock with all methods
        mock_repo = create_autospec(repo_class, instance=True)
        
        # Add base properties
        mock_repo.session = MagicMock()
        mock_repo.model_class = MagicMock()
        mock_repo.commit = MagicMock()
        mock_repo.rollback = MagicMock()
        mock_repo.flush = MagicMock()
        
        return mock_repo
    
    def create_with_data(self, repository_name: str, 
                        initial_data: Optional[List[Dict[str, Any]]] = None) -> MockRepositoryBase:
        """Create a repository mock with in-memory storage.
        
        Args:
            repository_name: Name of the repository
            initial_data: Optional initial data to populate
            
        Returns:
            Repository mock with working in-memory storage
        """
        # Get the appropriate class
        repo_class = self._repository_classes.get(
            repository_name,
            MockRepositoryBase
        )
        
        # Create instance with storage
        storage = InMemoryStorage()
        mock_repo = repo_class(storage)
        
        # Add initial data if provided
        if initial_data:
            for item in initial_data:
                mock_repo.create(**item)
        
        return mock_repo


# Helper functions for creating specific repository mocks

def create_todo_repository_mock(with_data: bool = True) -> MockTodoRepository:
    """Create a TodoRepository mock.
    
    Args:
        with_data: If True, creates with in-memory storage. If False, creates pure mock.
        
    Returns:
        MockTodoRepository instance
    """
    factory = RepositoryMockFactory()
    if with_data:
        return factory.create_with_data('todo')
    return factory.create_mock('todo')


def create_contact_repository_mock(with_data: bool = True) -> MockContactRepository:
    """Create a ContactRepository mock.
    
    Args:
        with_data: If True, creates with in-memory storage. If False, creates pure mock.
        
    Returns:
        MockContactRepository instance
    """
    factory = RepositoryMockFactory()
    if with_data:
        return factory.create_with_data('contact')
    return factory.create_mock('contact')


def create_campaign_repository_mock(with_data: bool = True) -> MockCampaignRepository:
    """Create a CampaignRepository mock.
    
    Args:
        with_data: If True, creates with in-memory storage. If False, creates pure mock.
        
    Returns:
        MockCampaignRepository instance
    """
    factory = RepositoryMockFactory()
    if with_data:
        return factory.create_with_data('campaign')
    return factory.create_mock('campaign')


def create_activity_repository_mock(with_data: bool = True) -> MockActivityRepository:
    """Create an ActivityRepository mock.
    
    Args:
        with_data: If True, creates with in-memory storage. If False, creates pure mock.
        
    Returns:
        MockActivityRepository instance
    """
    factory = RepositoryMockFactory()
    if with_data:
        return factory.create_with_data('activity')
    return factory.create_mock('activity')


def create_conversation_repository_mock(with_data: bool = True) -> MockConversationRepository:
    """Create a ConversationRepository mock.
    
    Args:
        with_data: If True, creates with in-memory storage. If False, creates pure mock.
        
    Returns:
        MockConversationRepository instance
    """
    factory = RepositoryMockFactory()
    if with_data:
        return factory.create_with_data('conversation')
    return factory.create_mock('conversation')


def create_quote_repository_mock(with_data: bool = True) -> MockQuoteRepository:
    """Create a QuoteRepository mock.
    
    Args:
        with_data: If True, creates with in-memory storage. If False, creates pure mock.
        
    Returns:
        MockQuoteRepository instance
    """
    factory = RepositoryMockFactory()
    if with_data:
        return factory.create_with_data('quote')
    return factory.create_mock('quote')


def create_quote_line_item_repository_mock(with_data: bool = True) -> MockQuoteLineItemRepository:
    """Create a QuoteLineItemRepository mock.
    
    Args:
        with_data: If True, creates with in-memory storage. If False, creates pure mock.
        
    Returns:
        MockQuoteLineItemRepository instance
    """
    factory = RepositoryMockFactory()
    if with_data:
        return factory.create_with_data('quote_line_item')
    return factory.create_mock('quote_line_item')


def create_all_repository_mocks(with_data: bool = True) -> Dict[str, MockRepositoryBase]:
    """Create all repository mocks.
    
    Args:
        with_data: If True, creates with in-memory storage. If False, creates pure mocks.
        
    Returns:
        Dictionary mapping repository names to their mocks
    """
    factory = RepositoryMockFactory()
    
    repository_names = [
        'contact', 'activity', 'conversation', 'appointment', 
        'invoice', 'quote', 'webhook_event', 'todo', 'quickbooks_sync',
        'campaign', 'campaign_list', 'campaign_list_member',
        'csv_import', 'contact_csv_import', 'contact_flag',
        'user', 'invite_token', 'product', 'job', 'property',
        'setting', 'quote_line_item', 'invoice_line_item',
        'quickbooks_auth'
    ]
    
    repositories = {}
    for name in repository_names:
        if with_data:
            repositories[name] = factory.create_with_data(name)
        else:
            repositories[name] = factory.create_mock(name)
    
    return repositories


# Pytest fixtures

import pytest


@pytest.fixture
def repository_factory():
    """Pytest fixture for repository mock factory."""
    return RepositoryMockFactory()


@pytest.fixture
def mock_repositories():
    """Pytest fixture providing all repository mocks with in-memory storage."""
    return create_all_repository_mocks(with_data=True)


@pytest.fixture
def contact_repository():
    """Pytest fixture for contact repository mock."""
    return create_contact_repository_mock(with_data=True)


@pytest.fixture
def todo_repository():
    """Pytest fixture for todo repository mock."""
    return create_todo_repository_mock(with_data=True)


@pytest.fixture
def campaign_repository():
    """Pytest fixture for campaign repository mock."""
    return create_campaign_repository_mock(with_data=True)


@pytest.fixture
def activity_repository():
    """Pytest fixture for activity repository mock."""
    return create_activity_repository_mock(with_data=True)


@pytest.fixture
def conversation_repository():
    """Pytest fixture for conversation repository mock."""
    return create_conversation_repository_mock(with_data=True)


@pytest.fixture
def quote_repository():
    """Pytest fixture for quote repository mock."""
    return create_quote_repository_mock(with_data=True)


@pytest.fixture
def quote_line_item_repository():
    """Pytest fixture for quote line item repository mock."""
    return create_quote_line_item_repository_mock(with_data=True)