"""
Tests for TodoService
"""
import pytest
from datetime import datetime, timedelta
from services.todo_service_refactored import TodoService
from crm_database import Todo
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


class TestTodoService:
    """Test TodoService functionality"""
    
    def test_create_todo(self, todo_service, test_user_id, sample_todo_data, db_session):
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
    
    def test_create_todo_without_title(self, todo_service, test_user_id, db_session):
        """Test creating todo without title raises error"""
        with pytest.raises(ValueError, match="Title is required"):
            todo_service.create_todo(test_user_id, {})
    
    def test_create_todo_with_invalid_date(self, todo_service, test_user_id, db_session):
        """Test creating todo with invalid date format"""
        data = {
            'title': 'Test Todo',
            'due_date': 'invalid-date'
        }
        
        with pytest.raises(ValueError, match="Invalid due date format"):
            todo_service.create_todo(test_user_id, data)
    
    def test_get_user_todos(self, todo_service, test_user_id, db_session):
        """Test retrieving user todos"""
        # Clear any existing todos for this user
        Todo.query.filter_by(user_id=test_user_id).delete()
        db_session.commit()
        
        # Create some todos
        todo_service.create_todo(test_user_id, {'title': 'Todo 1'})
        todo_service.create_todo(test_user_id, {'title': 'Todo 2'})
        
        # Create a completed todo
        todo3 = todo_service.create_todo(test_user_id, {'title': 'Todo 3'})
        todo3.mark_complete()
        db_session.commit()
        
        # Get all todos
        todos = todo_service.get_user_todos(test_user_id)
        assert len(todos) == 3
        
        # Get only incomplete todos
        incomplete_todos = todo_service.get_user_todos(test_user_id, include_completed=False)
        assert len(incomplete_todos) == 2
    
    def test_update_todo(self, todo_service, test_user_id, sample_todo_data, db_session):
        """Test updating a todo"""
        # Create a todo
        todo = todo_service.create_todo(test_user_id, sample_todo_data)
        
        # Update it
        updates = {
            'title': 'Updated Title',
            'priority': 'low',
            'due_date': None
        }
        
        updated_todo = todo_service.update_todo(todo.id, test_user_id, updates)
        
        assert updated_todo.title == 'Updated Title'
        assert updated_todo.priority == 'low'
        assert updated_todo.due_date is None
        assert updated_todo.updated_at is not None
    
    def test_update_nonexistent_todo(self, todo_service, test_user_id):
        """Test updating non-existent todo returns None"""
        result = todo_service.update_todo(99999, test_user_id, {'title': 'New Title'})
        assert result is None
    
    def test_toggle_todo_completion(self, todo_service, test_user_id, db_session):
        """Test toggling todo completion status"""
        # Create a todo
        todo = todo_service.create_todo(test_user_id, {'title': 'Toggle Test'})
        assert todo.is_completed is False
        
        # Toggle to complete
        toggled = todo_service.toggle_todo_completion(todo.id, test_user_id)
        assert toggled.is_completed is True
        assert toggled.completed_at is not None
        
        # Toggle back to incomplete
        toggled = todo_service.toggle_todo_completion(todo.id, test_user_id)
        assert toggled.is_completed is False
        assert toggled.completed_at is None
    
    def test_delete_todo(self, todo_service, test_user_id, db_session):
        """Test deleting a todo"""
        # Create a todo
        todo = todo_service.create_todo(test_user_id, {'title': 'Delete Test'})
        todo_id = todo.id
        
        # Delete it
        success = todo_service.delete_todo(todo_id, test_user_id)
        assert success is True
        
        # Verify it's deleted
        deleted_todo = Todo.query.get(todo_id)
        assert deleted_todo is None
        
        # Try to delete non-existent todo
        success = todo_service.delete_todo(99999, test_user_id)
        assert success is False
    
    def test_get_dashboard_todos(self, todo_service, test_user_id, db_session):
        """Test getting dashboard todos with priority sorting"""
        # Clear any existing todos for this user
        Todo.query.filter_by(user_id=test_user_id).delete()
        db_session.commit()
        
        # Create todos with different priorities
        todo_service.create_todo(test_user_id, {'title': 'Low Priority', 'priority': 'low'})
        todo_service.create_todo(test_user_id, {'title': 'High Priority 1', 'priority': 'high'})
        todo_service.create_todo(test_user_id, {'title': 'Medium Priority', 'priority': 'medium'})
        todo_service.create_todo(test_user_id, {'title': 'High Priority 2', 'priority': 'high'})
        
        # Create a completed todo (should not appear)
        completed = todo_service.create_todo(test_user_id, {'title': 'Completed', 'priority': 'high'})
        completed.mark_complete()
        db_session.commit()
        
        # Get dashboard todos
        result = todo_service.get_dashboard_todos(test_user_id, limit=3)
        
        assert len(result['todos']) == 3
        assert result['pending_count'] == 4
        
        # Check that high priority todos come first
        priorities = [todo.priority for todo in result['todos']]
        assert priorities[0] == 'high'
        assert priorities[1] == 'high'
        assert priorities[2] == 'medium'
    
    def test_get_todo_stats(self, todo_service, test_user_id, db_session):
        """Test getting todo statistics"""
        # Clear any existing todos for this user
        Todo.query.filter_by(user_id=test_user_id).delete()
        db_session.commit()
        
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
        completed = todo_service.create_todo(test_user_id, {'title': 'Done'})
        completed.mark_complete()
        db_session.commit()
        
        # Get stats
        stats = todo_service.get_todo_stats(test_user_id)
        
        assert stats['total'] == 5
        assert stats['completed'] == 1
        assert stats['pending'] == 4
        assert stats['high_priority'] == 2
        assert stats['overdue'] == 1
    
    def test_serialize_todo(self, todo_service, test_user_id, sample_todo_data, db_session):
        """Test todo serialization"""
        todo = todo_service.create_todo(test_user_id, sample_todo_data)
        
        serialized = todo_service.serialize_todo(todo)
        
        assert serialized['id'] == todo.id
        assert serialized['title'] == todo.title
        assert serialized['description'] == todo.description
        assert serialized['priority'] == todo.priority
        assert serialized['is_completed'] == todo.is_completed
        assert serialized['due_date'] is not None
        assert serialized['created_at'] is not None
        assert serialized['updated_at'] is not None
        assert serialized['completed_at'] is None