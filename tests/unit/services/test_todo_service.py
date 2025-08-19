"""
Tests for TodoService
"""
import pytest
from datetime import datetime, timedelta
from services.todo_service_refactored import TodoServiceRefactored
from tests.fixtures.repository_fixtures import create_todo_repository_mock


@pytest.fixture
def todo_service():
    """Fixture providing todo service instance with mock repository"""
    # Create a mock repository with in-memory storage
    mock_repo = create_todo_repository_mock(with_data=True)
    # Pass it to the TodoServiceRefactored
    return TodoServiceRefactored(todo_repository=mock_repo)


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


class TestTodoService:
    """Test TodoService functionality"""
    
    def test_create_todo(self, todo_service, test_user_id, sample_todo_data):
        """Test creating a new todo"""
        result = todo_service.create_todo(test_user_id, sample_todo_data)
        
        # TodoServiceRefactored returns a Result object
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
        """Test creating todo without title returns error result"""
        result = todo_service.create_todo(test_user_id, {})
        
        assert result.success is False
        assert "Title is required" in result.error
        assert result.error_code == "VALIDATION_ERROR"
    
    def test_create_todo_with_invalid_date(self, todo_service, test_user_id):
        """Test creating todo with invalid date format returns error result"""
        data = {
            'title': 'Test Todo',
            'due_date': 'invalid-date'
        }
        
        result = todo_service.create_todo(test_user_id, data)
        
        assert result.success is False
        assert "Invalid due date format" in result.error
        assert result.error_code == "VALIDATION_ERROR"
    
    def test_get_user_todos(self, todo_service, test_user_id):
        """Test retrieving user todos"""
        # Create some todos
        todo1_result = todo_service.create_todo(test_user_id, {'title': 'Todo 1'})
        todo2_result = todo_service.create_todo(test_user_id, {'title': 'Todo 2'})
        todo3_result = todo_service.create_todo(test_user_id, {'title': 'Todo 3'})
        
        # Mark one as completed by updating directly in repository
        todo3 = todo3_result.data
        todo_service.todo_repository.update_by_id(
            todo3['id'], 
            is_completed=True, 
            completed_at=datetime.utcnow()
        )
        
        # Get all todos
        todos = todo_service.get_user_todos(test_user_id)
        assert len(todos) == 3
        
        # Get only incomplete todos
        incomplete_todos = todo_service.get_user_todos(test_user_id, include_completed=False)
        assert len(incomplete_todos) == 2
    
    def test_update_todo(self, todo_service, test_user_id, sample_todo_data):
        """Test updating a todo"""
        # Create a todo
        result = todo_service.create_todo(test_user_id, sample_todo_data)
        assert result.success is True
        todo = result.data
        
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
        assert updated_todo['due_date'] is None
        assert updated_todo['updated_at'] is not None
    
    def test_update_nonexistent_todo(self, todo_service, test_user_id):
        """Test updating non-existent todo returns error result"""
        result = todo_service.update_todo(99999, test_user_id, {'title': 'New Title'})
        
        assert result.success is False
        assert "not found" in result.error
        assert result.error_code == "TODO_NOT_FOUND"
    
    def test_toggle_todo_completion(self, todo_service, test_user_id):
        """Test toggling todo completion status"""
        # Create a todo
        create_result = todo_service.create_todo(test_user_id, {'title': 'Toggle Test'})
        assert create_result.success is True
        todo = create_result.data
        assert todo['is_completed'] is False
        
        # Toggle to complete
        toggle_result = todo_service.toggle_todo_completion(todo['id'], test_user_id)
        assert toggle_result.success is True
        toggled = toggle_result.data
        assert toggled['is_completed'] is True
        assert toggled['completed_at'] is not None
        
        # Toggle back to incomplete
        toggle_result2 = todo_service.toggle_todo_completion(todo['id'], test_user_id)
        assert toggle_result2.success is True
        toggled2 = toggle_result2.data
        assert toggled2['is_completed'] is False
        assert toggled2['completed_at'] is None
    
    def test_delete_todo(self, todo_service, test_user_id):
        """Test deleting a todo"""
        # Create a todo
        create_result = todo_service.create_todo(test_user_id, {'title': 'Delete Test'})
        assert create_result.success is True
        todo = create_result.data
        todo_id = todo['id']
        
        # Delete it
        delete_result = todo_service.delete_todo(todo_id, test_user_id)
        assert delete_result.success is True
        assert delete_result.data is True
        
        # Verify it's deleted
        deleted_todo = todo_service.todo_repository.get_by_id(todo_id)
        assert deleted_todo is None
        
        # Try to delete non-existent todo
        delete_result2 = todo_service.delete_todo(99999, test_user_id)
        assert delete_result2.success is False
        assert "not found" in delete_result2.error
    
    def test_get_dashboard_todos(self, todo_service, test_user_id):
        """Test getting dashboard todos with priority sorting"""
        # Create todos with different priorities
        todo_service.create_todo(test_user_id, {'title': 'Low Priority', 'priority': 'low'})
        todo_service.create_todo(test_user_id, {'title': 'High Priority 1', 'priority': 'high'})
        todo_service.create_todo(test_user_id, {'title': 'Medium Priority', 'priority': 'medium'})
        todo_service.create_todo(test_user_id, {'title': 'High Priority 2', 'priority': 'high'})
        
        # Create a completed todo (should not appear in dashboard)
        completed_result = todo_service.create_todo(test_user_id, {'title': 'Completed', 'priority': 'high'})
        completed_todo = completed_result.data
        todo_service.todo_repository.update_by_id(
            completed_todo['id'],
            is_completed=True,
            completed_at=datetime.utcnow()
        )
        
        # Get dashboard todos
        result = todo_service.get_dashboard_todos(test_user_id, limit=3)
        
        assert len(result['todos']) == 3
        assert result['pending_count'] == 4
        
        # Check that high priority todos come first
        priorities = [todo['priority'] for todo in result['todos']]
        assert priorities[0] == 'high'
        assert priorities[1] == 'high'
        assert priorities[2] == 'medium'
    
    def test_get_todo_stats(self, todo_service, test_user_id):
        """Test getting todo statistics"""
        # Create various todos
        todo_service.create_todo(test_user_id, {'title': 'Todo 1', 'priority': 'high'})
        todo_service.create_todo(test_user_id, {'title': 'Todo 2', 'priority': 'high'})
        todo_service.create_todo(test_user_id, {'title': 'Todo 3', 'priority': 'low'})
        
        # Create overdue todo
        overdue_date = datetime.utcnow() - timedelta(days=1)
        todo_service.create_todo(test_user_id, {
            'title': 'Overdue',
            'due_date': overdue_date.isoformat()
        })
        
        # Create completed todo
        completed_result = todo_service.create_todo(test_user_id, {'title': 'Done'})
        completed_todo = completed_result.data
        todo_service.todo_repository.update_by_id(
            completed_todo['id'],
            is_completed=True,
            completed_at=datetime.utcnow()
        )
        
        # Get stats - the service returns Result pattern for get_todo_stats
        stats_result = todo_service.get_todo_stats(test_user_id)
        assert stats_result.success is True
        stats = stats_result.data
        
        assert stats['total'] == 5
        assert stats['completed'] == 1
        assert stats['pending'] == 4
        assert stats['high_priority'] == 2
        assert stats['overdue'] == 1
    
    def test_serialize_todo(self, todo_service, test_user_id, sample_todo_data):
        """Test todo serialization"""
        create_result = todo_service.create_todo(test_user_id, sample_todo_data)
        assert create_result.success is True
        todo = create_result.data
        
        # Create a mock todo object from the data (the serialize method expects an object)
        class MockTodo:
            def __init__(self, data):
                for key, value in data.items():
                    setattr(self, key, value)
                # Convert ISO string back to datetime for due_date if present
                if hasattr(self, 'due_date') and isinstance(self.due_date, str):
                    self.due_date = datetime.fromisoformat(self.due_date)
        
        todo_obj = MockTodo(todo)
        serialized = todo_service.serialize_todo(todo_obj)
        
        assert serialized['id'] == todo['id']
        assert serialized['title'] == todo['title']
        assert serialized['description'] == todo['description']
        assert serialized['priority'] == todo['priority']
        assert serialized['is_completed'] == todo['is_completed']
        assert serialized['due_date'] is not None
        assert serialized['created_at'] is not None
        assert serialized['updated_at'] is not None
        assert serialized['completed_at'] is None