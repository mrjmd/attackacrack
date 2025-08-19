"""
Tests for TodoService with Repository Mock Support

This test suite demonstrates proper testing with:
1. Repository mocks with in-memory storage
2. Result pattern handling
3. No database dependencies
"""
import pytest
from datetime import datetime, timedelta
from services.todo_service_refactored import TodoService
from tests.fixtures.repository_fixtures import create_todo_repository_mock


@pytest.fixture
def todo_service():
    """Fixture providing todo service instance with mock repository"""
    # Create a mock repository with in-memory storage
    mock_repo = create_todo_repository_mock(with_data=True)
    # Pass it to the TodoService
    return TodoService(todo_repository=mock_repo)


@pytest.fixture
def test_user_id():
    """Fixture providing a test user ID"""
    return 1


@pytest.fixture
def sample_todo_data():
    """Fixture providing sample todo data"""
    return {
        'title': 'Test Todo',
        'description': 'This is a test todo',
        'priority': 'high',
        'due_date': (datetime.utcnow() + timedelta(days=1)).isoformat()
    }


class TestTodoServiceWithMocks:
    """Test TodoService functionality with repository mocks"""
    
    def test_create_todo(self, todo_service, test_user_id, sample_todo_data):
        """Test creating a new todo"""
        result = todo_service.create_todo(test_user_id, sample_todo_data)
        
        # TodoService returns a Result object
        assert result.success is True
        todo = result.data
        
        assert todo['id'] is not None
        assert todo['title'] == sample_todo_data['title']
        assert todo['description'] == sample_todo_data['description']
        assert todo['priority'] == sample_todo_data['priority']
        assert todo['user_id'] == test_user_id
        assert todo.get('is_completed', False) is False
        assert todo.get('due_date') is not None
    
    def test_create_todo_without_title(self, todo_service, test_user_id):
        """Test creating todo without title returns failure result"""
        result = todo_service.create_todo(test_user_id, {})
        
        # Should return a failure Result, not raise an exception
        assert result.success is False
        assert 'Title is required' in result.error
        assert result.error_code == 'VALIDATION_ERROR'
    
    def test_create_todo_with_invalid_date(self, todo_service, test_user_id):
        """Test creating todo with invalid date format"""
        data = {
            'title': 'Test Todo',
            'due_date': 'invalid-date'
        }
        
        result = todo_service.create_todo(test_user_id, data)
        
        # Should return a failure Result
        assert result.success is False
        assert 'Invalid due date format' in result.error
        assert result.error_code == 'VALIDATION_ERROR'
    
    def test_get_user_todos(self, todo_service, test_user_id):
        """Test retrieving user todos"""
        # Create some todos
        todo1_result = todo_service.create_todo(test_user_id, {'title': 'Todo 1'})
        todo2_result = todo_service.create_todo(test_user_id, {'title': 'Todo 2'})
        todo3_result = todo_service.create_todo(test_user_id, {'title': 'Todo 3'})
        
        assert todo1_result.success
        assert todo2_result.success
        assert todo3_result.success
        
        # Mark one as complete
        todo_service.toggle_todo_completion(todo3_result.data['id'], test_user_id)
        
        # Get all todos (backward compatibility method)
        todos = todo_service.get_user_todos(test_user_id)
        assert len(todos) == 3
        
        # Get only incomplete todos
        incomplete_todos = todo_service.get_user_todos(test_user_id, include_completed=False)
        assert len(incomplete_todos) == 2
        
        # Test with Result pattern
        result = todo_service.get_user_todos_result(test_user_id)
        assert result.success is True
        assert len(result.data) == 3
    
    def test_update_todo(self, todo_service, test_user_id, sample_todo_data):
        """Test updating a todo"""
        # Create a todo
        create_result = todo_service.create_todo(test_user_id, sample_todo_data)
        assert create_result.success
        todo = create_result.data
        
        # Update it
        updates = {
            'title': 'Updated Title',
            'priority': 'low',
            'due_date': None
        }
        
        update_result = todo_service.update_todo(todo['id'], test_user_id, updates)
        assert update_result.success is True
        
        updated_todo = update_result.data
        assert updated_todo['title'] == 'Updated Title'
        assert updated_todo['priority'] == 'low'
        assert updated_todo.get('due_date') is None
    
    def test_mark_todo_complete(self, todo_service, test_user_id, sample_todo_data):
        """Test marking a todo as complete"""
        # Create a todo
        create_result = todo_service.create_todo(test_user_id, sample_todo_data)
        assert create_result.success
        todo = create_result.data
        
        # Mark it as complete
        result = todo_service.toggle_todo_completion(todo['id'], test_user_id)
        assert result.success is True
        
        completed_todo = result.data
        assert completed_todo['is_completed'] is True
        assert completed_todo.get('completed_at') is not None
    
    def test_mark_todo_incomplete(self, todo_service, test_user_id, sample_todo_data):
        """Test marking a todo as incomplete"""
        # Create and complete a todo
        create_result = todo_service.create_todo(test_user_id, sample_todo_data)
        assert create_result.success
        todo = create_result.data
        
        todo_service.toggle_todo_completion(todo['id'], test_user_id)
        
        # Mark it as incomplete (toggle again to make it incomplete)
        result = todo_service.toggle_todo_completion(todo['id'], test_user_id)
        assert result.success is True
        
        incomplete_todo = result.data
        assert incomplete_todo['is_completed'] is False
        assert incomplete_todo.get('completed_at') is None
    
    def test_delete_todo(self, todo_service, test_user_id, sample_todo_data):
        """Test deleting a todo"""
        # Create a todo
        create_result = todo_service.create_todo(test_user_id, sample_todo_data)
        assert create_result.success
        todo = create_result.data
        
        # Delete it
        result = todo_service.delete_todo(todo['id'], test_user_id)
        assert result.success is True
        
        # Verify it's deleted
        todos = todo_service.get_user_todos(test_user_id)
        assert len(todos) == 0
    
    def test_get_todo_stats(self, todo_service, test_user_id):
        """Test getting todo statistics"""
        # Create some todos with different states
        todo_service.create_todo(test_user_id, {'title': 'High Priority', 'priority': 'high'})
        todo_service.create_todo(test_user_id, {'title': 'Medium Priority', 'priority': 'medium'})
        todo_service.create_todo(test_user_id, {'title': 'Low Priority', 'priority': 'low'})
        
        result = todo_service.create_todo(test_user_id, {'title': 'Completed', 'priority': 'high'})
        todo_service.toggle_todo_completion(result.data['id'], test_user_id)
        
        # Get stats
        stats_result = todo_service.get_todo_stats(test_user_id)
        assert stats_result.success is True
        
        stats = stats_result.data
        assert stats['total'] == 4
        assert stats['completed'] == 1
        assert stats['pending'] == 3
        assert stats['high_priority'] == 1  # One high priority pending
    
    def test_get_dashboard_todos(self, todo_service, test_user_id):
        """Test getting todos for dashboard with priority sorting"""
        # Create todos with different priorities
        todo_service.create_todo(test_user_id, {'title': 'Low Priority', 'priority': 'low'})
        todo_service.create_todo(test_user_id, {'title': 'High Priority 1', 'priority': 'high'})
        todo_service.create_todo(test_user_id, {'title': 'Medium Priority', 'priority': 'medium'})
        todo_service.create_todo(test_user_id, {'title': 'High Priority 2', 'priority': 'high'})
        
        # Get dashboard todos (should be sorted by priority)
        dashboard_data = todo_service.get_dashboard_todos(test_user_id, limit=3)
        
        assert 'todos' in dashboard_data
        assert 'pending_count' in dashboard_data
        assert dashboard_data['pending_count'] == 4
        assert len(dashboard_data['todos']) == 3
        
        # Check priority ordering (high priority should come first)
        todos = dashboard_data['todos']
        assert todos[0]['priority'] == 'high'
        assert todos[1]['priority'] == 'high'
        assert todos[2]['priority'] == 'medium'
    
    def test_unauthorized_access(self, todo_service, test_user_id):
        """Test that users can't access other users' todos"""
        # Create a todo for user 1
        create_result = todo_service.create_todo(test_user_id, {'title': 'User 1 Todo'})
        assert create_result.success
        todo = create_result.data
        
        # Try to update it as user 2
        other_user_id = 2
        update_result = todo_service.update_todo(todo['id'], other_user_id, {'title': 'Hacked'})
        
        # Should fail
        assert update_result.success is False
        assert update_result.error_code == 'TODO_NOT_FOUND'
    
    def test_repository_isolation(self, todo_service, test_user_id):
        """Test that each test has isolated repository data"""
        # This test should start with an empty repository
        todos = todo_service.get_user_todos(test_user_id)
        assert len(todos) == 0
        
        # Create a todo
        todo_service.create_todo(test_user_id, {'title': 'Isolated Todo'})
        
        # Verify it exists
        todos = todo_service.get_user_todos(test_user_id)
        assert len(todos) == 1
        
        # The next test should start fresh with an empty repository


class TestTodoServiceEdgeCases:
    """Test edge cases and error handling"""
    
    def test_invalid_priority(self, todo_service, test_user_id):
        """Test creating todo with invalid priority"""
        result = todo_service.create_todo(test_user_id, {
            'title': 'Test',
            'priority': 'invalid'
        })
        
        assert result.success is False
        assert 'Invalid priority' in result.error
        assert result.error_code == 'VALIDATION_ERROR'
    
    def test_missing_user_id(self, todo_service):
        """Test operations without user ID"""
        result = todo_service.create_todo(None, {'title': 'Test'})
        
        assert result.success is False
        assert 'User ID is required' in result.error
    
    def test_nonexistent_todo(self, todo_service, test_user_id):
        """Test operations on non-existent todo"""
        result = todo_service.update_todo(99999, test_user_id, {'title': 'Updated'})
        
        assert result.success is False
        assert result.error_code == 'TODO_NOT_FOUND'
    
    def test_empty_title_after_trim(self, todo_service, test_user_id):
        """Test creating todo with only whitespace in title"""
        result = todo_service.create_todo(test_user_id, {
            'title': '   ',
            'description': 'Has description'
        })
        
        # Should fail validation (assuming title is trimmed)
        assert result.success is False
        assert 'Title is required' in result.error