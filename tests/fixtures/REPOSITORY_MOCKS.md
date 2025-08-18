# Repository Mock Factory Documentation

## Overview
The Repository Mock Factory provides comprehensive mocking for all repository classes in the Attack-a-Crack CRM. It enables testing without database dependencies through in-memory storage and full BaseRepository interface support.

## Key Features
- ✅ Mock implementations of all repository methods
- ✅ BaseRepository interface support (get, create, update, delete, search, etc.)
- ✅ In-memory data storage for testing
- ✅ Seamless integration with service fixtures
- ✅ No database dependencies required
- ✅ Thread-safe operations
- ✅ Auto-incrementing IDs
- ✅ Pagination support

## Usage

### Basic Repository Mock Creation

```python
from tests.fixtures.repository_fixtures import RepositoryMockFactory

# Create factory
factory = RepositoryMockFactory()

# Create mock with in-memory storage
contact_repo = factory.create_with_data('contact')

# Create pure mock (no storage)
mock_repo = factory.create_mock('contact')
```

### Using Helper Functions

```python
from tests.fixtures.repository_fixtures import (
    create_contact_repository_mock,
    create_todo_repository_mock,
    create_campaign_repository_mock,
    create_all_repository_mocks
)

# Create specific repository mocks
contact_repo = create_contact_repository_mock(with_data=True)
todo_repo = create_todo_repository_mock(with_data=True)

# Create all repository mocks at once
all_repos = create_all_repository_mocks(with_data=True)
```

### Integration with Services

```python
from tests.fixtures.repository_fixtures import create_todo_repository_mock
from services.todo_service_refactored import TodoService

# Create repository mock
todo_repo = create_todo_repository_mock(with_data=True)

# Inject into service
todo_service = TodoService(todo_repository=todo_repo)

# Use service normally
result = todo_service.create_todo(1, {
    'title': 'Test Todo',
    'priority': 'high'
})

# Data is stored in mock repository
todos = todo_repo.find_by_user_id(1)
assert len(todos) == 1
```

### Pytest Fixtures

```python
# These fixtures are available globally via conftest.py

def test_with_repository_fixtures(
    repository_factory,    # Factory instance
    mock_repositories,     # All repositories dict
    contact_repository,    # Contact repository mock
    todo_repository,       # Todo repository mock
    campaign_repository    # Campaign repository mock
):
    # Use repositories in tests
    contact = contact_repository.create(
        name='Test User',
        phone='+15551234567'
    )
    assert contact['id'] is not None
```

## Repository Methods

### Standard CRUD Operations
All repository mocks support these BaseRepository methods:

- `create(**kwargs)` - Create single entity
- `create_many(entities_data)` - Create multiple entities
- `get_by_id(entity_id)` - Get by ID
- `get_all(order_by=None, order=SortOrder.ASC)` - Get all entities
- `update(entity, **updates)` - Update entity
- `update_by_id(entity_id, **updates)` - Update by ID
- `update_many(filters, updates)` - Bulk update
- `delete(entity)` - Delete entity
- `delete_by_id(entity_id)` - Delete by ID
- `delete_many(filters)` - Bulk delete

### Query Methods
- `find_by(**filters)` - Find entities by filters
- `find_one_by(**filters)` - Find single entity
- `exists(**filters)` - Check existence
- `count(**filters)` - Count entities
- `search(query, fields=None)` - Text search

### Pagination
- `get_paginated(pagination, filters=None, order_by=None, order=SortOrder.ASC)`

### Transaction Methods
- `commit()` - Commit transaction (mocked)
- `rollback()` - Rollback transaction (mocked)
- `flush()` - Flush changes (mocked)

## Repository-Specific Methods

### TodoRepository
- `find_by_priority(priority)`
- `find_completed_todos()`
- `find_pending_todos()`
- `find_overdue_todos()`
- `mark_as_completed(todo_id)`
- `mark_as_pending(todo_id)`
- `find_by_user_id(user_id, include_completed=True)`
- `find_by_user_id_with_priority(user_id, limit=5)`
- `count_by_user_id(user_id)`
- `count_completed_by_user_id(user_id)`
- `count_pending_by_user_id(user_id)`
- `count_high_priority_pending(user_id)`

### ContactRepository
- `find_by_phone(phone)`
- `find_by_tag(tag)`
- `get_recent_contacts(limit=10)`
- `search(query, fields=None)`

### CampaignRepository
- `find_active_campaigns()`
- `find_by_status(status)`
- `update_status(campaign_id, status)`
- `get_campaign_with_stats(campaign_id)`

### ActivityRepository
- `find_by_contact_id(contact_id)`
- `find_recent_activities(limit=10)`

### ConversationRepository
- `find_by_contact_id(contact_id)`
- `find_active_conversations()`

## Examples

### Test with In-Memory Storage

```python
def test_todo_crud():
    repo = create_todo_repository_mock(with_data=True)
    
    # Create
    todo = repo.create(
        title='Test Todo',
        priority='high',
        user_id=1
    )
    
    # Read
    retrieved = repo.get_by_id(todo['id'])
    assert retrieved['title'] == 'Test Todo'
    
    # Update
    updated = repo.update(todo, priority='low')
    assert updated['priority'] == 'low'
    
    # Delete
    deleted = repo.delete(todo)
    assert deleted is True
```

### Test with Pagination

```python
def test_pagination():
    repo = create_contact_repository_mock(with_data=True)
    
    # Create 25 contacts
    for i in range(1, 26):
        repo.create(name=f'Contact {i}')
    
    # Get page 1
    page1 = repo.get_paginated(
        PaginationParams(page=1, per_page=10)
    )
    assert len(page1.items) == 10
    assert page1.total == 25
    assert page1.pages == 3
```

### Test Service Integration

```python
@pytest.fixture
def todo_service():
    # Create repository with data storage
    mock_repo = create_todo_repository_mock(with_data=True)
    # Inject into service
    return TodoService(todo_repository=mock_repo)

def test_todo_service(todo_service):
    result = todo_service.create_todo(1, {
        'title': 'Test',
        'priority': 'high'
    })
    assert result.success is True
```

## Migration Guide

### From Database Tests to Repository Mocks

Before (with database):
```python
def test_with_database(db_session):
    todo = Todo(title='Test', user_id=1)
    db_session.add(todo)
    db_session.commit()
    
    retrieved = Todo.query.get(todo.id)
    assert retrieved.title == 'Test'
```

After (with repository mocks):
```python
def test_with_repository_mock(todo_repository):
    todo = todo_repository.create(
        title='Test',
        user_id=1
    )
    
    retrieved = todo_repository.get_by_id(todo['id'])
    assert retrieved['title'] == 'Test'
```

## Benefits
1. **Fast Tests** - No database overhead
2. **Isolated Tests** - Each test gets fresh repository
3. **Predictable** - In-memory storage is deterministic
4. **Easy Setup** - No database migrations or fixtures
5. **Thread-Safe** - Safe for parallel testing

## Available Repositories
The factory supports all 24+ repositories:
- contact, activity, conversation, appointment
- invoice, quote, webhook_event, todo
- quickbooks_sync, campaign, campaign_list
- campaign_list_member, csv_import, contact_csv_import
- contact_flag, user, invite_token, product
- job, property, setting, quote_line_item
- invoice_line_item, quickbooks_auth

## Tips
1. Use `with_data=True` for integration tests that need storage
2. Use `with_data=False` for unit tests with pure mocks
3. Repository data is dictionaries, not ORM objects
4. Each test gets isolated repository instances
5. Mock repositories are thread-safe for parallel testing