"""
Unit tests for TodoServiceRefactored following TDD principles
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime, timedelta
from services.todo_service_refactored import TodoServiceRefactored
from services.common.result import Result
from repositories.todo_repository import TodoRepository
from crm_database import Todo


class TestTodoServiceRefactoredInitialization:
    """Test service initialization and dependency injection"""
    
    def test_service_initialization_with_repository(self):
        """Test service initializes with provided repository"""
        # Arrange
        mock_repository = Mock(spec=TodoRepository)
        
        # Act
        service = TodoServiceRefactored(todo_repository=mock_repository)
        
        # Assert
        assert service.todo_repository == mock_repository
    
    def test_service_initialization_without_repository(self):
        """Test service creates default repository if none provided"""
        # Act
        with patch('services.todo_service_refactored.TodoRepository') as MockRepo:
            with patch('services.todo_service_refactored.db'):
                service = TodoServiceRefactored()
                
        # Assert
        assert service.todo_repository is not None
        MockRepo.assert_called_once()


class TestGetUserTodos:
    """Test get_user_todos method with Result pattern"""
    
    def test_get_user_todos_success_all(self):
        """Test getting all todos for a user"""
        # Arrange
        mock_repository = Mock(spec=TodoRepository)
        service = TodoServiceRefactored(todo_repository=mock_repository)
        
        mock_todos = [
            Mock(id=1, title="Todo 1", is_completed=False),
            Mock(id=2, title="Todo 2", is_completed=True)
        ]
        mock_repository.find_by_user_id.return_value = mock_todos
        
        # Act
        result = service.get_user_todos(user_id=1, include_completed=True)
        
        # Assert
        assert result.success is True
        assert result.data == mock_todos
        mock_repository.find_by_user_id.assert_called_once_with(1, include_completed=True)
    
    def test_get_user_todos_success_pending_only(self):
        """Test getting only pending todos"""
        # Arrange
        mock_repository = Mock(spec=TodoRepository)
        service = TodoServiceRefactored(todo_repository=mock_repository)
        
        mock_todos = [Mock(id=1, title="Todo 1", is_completed=False)]
        mock_repository.find_by_user_id.return_value = mock_todos
        
        # Act
        result = service.get_user_todos(user_id=1, include_completed=False)
        
        # Assert
        assert result.success is True
        assert result.data == mock_todos
        mock_repository.find_by_user_id.assert_called_once_with(1, include_completed=False)
    
    def test_get_user_todos_invalid_user_id(self):
        """Test with invalid user ID"""
        # Arrange
        mock_repository = Mock(spec=TodoRepository)
        service = TodoServiceRefactored(todo_repository=mock_repository)
        
        # Act
        result = service.get_user_todos(user_id=None)
        
        # Assert
        assert result.success is False
        assert result.error_code == "VALIDATION_ERROR"
        assert "User ID is required" in result.error
        mock_repository.find_by_user_id.assert_not_called()
    
    def test_get_user_todos_repository_error(self):
        """Test repository error handling"""
        # Arrange
        mock_repository = Mock(spec=TodoRepository)
        service = TodoServiceRefactored(todo_repository=mock_repository)
        mock_repository.find_by_user_id.side_effect = Exception("Database error")
        
        # Act
        result = service.get_user_todos(user_id=1)
        
        # Assert
        assert result.success is False
        assert result.error_code == "REPOSITORY_ERROR"
        assert "Database error" in result.error


class TestGetDashboardTodos:
    """Test get_dashboard_todos method"""
    
    def test_get_dashboard_todos_success(self):
        """Test getting dashboard todos with stats"""
        # Arrange
        mock_repository = Mock(spec=TodoRepository)
        service = TodoServiceRefactored(todo_repository=mock_repository)
        
        mock_todos = [
            Mock(id=1, priority="high"),
            Mock(id=2, priority="medium")
        ]
        mock_repository.find_by_user_id_with_priority.return_value = mock_todos
        mock_repository.count_pending_by_user_id.return_value = 5
        
        # Act
        result = service.get_dashboard_todos(user_id=1, limit=5)
        
        # Assert
        assert result.success is True
        assert result.data['todos'] == mock_todos
        assert result.data['pending_count'] == 5
        mock_repository.find_by_user_id_with_priority.assert_called_once_with(1, limit=5)
        mock_repository.count_pending_by_user_id.assert_called_once_with(1)
    
    def test_get_dashboard_todos_empty(self):
        """Test dashboard with no todos"""
        # Arrange
        mock_repository = Mock(spec=TodoRepository)
        service = TodoServiceRefactored(todo_repository=mock_repository)
        
        mock_repository.find_by_user_id_with_priority.return_value = []
        mock_repository.count_pending_by_user_id.return_value = 0
        
        # Act
        result = service.get_dashboard_todos(user_id=1)
        
        # Assert
        assert result.success is True
        assert result.data['todos'] == []
        assert result.data['pending_count'] == 0


class TestCreateTodo:
    """Test create_todo method"""
    
    def test_create_todo_success(self):
        """Test successful todo creation"""
        # Arrange
        mock_repository = Mock(spec=TodoRepository)
        service = TodoServiceRefactored(todo_repository=mock_repository)
        
        todo_data = {
            'title': 'Test Todo',
            'description': 'Test Description',
            'priority': 'high',
            'due_date': '2024-12-31T10:00:00'
        }
        
        mock_todo = Mock(id=1, title='Test Todo')
        mock_repository.create.return_value = mock_todo
        
        # Act
        result = service.create_todo(user_id=1, todo_data=todo_data)
        
        # Assert
        assert result.success is True
        assert result.data == mock_todo
        
        # Verify repository was called with correct data
        call_args = mock_repository.create.call_args[0][0]
        assert call_args['title'] == 'Test Todo'
        assert call_args['user_id'] == 1
    
    def test_create_todo_missing_title(self):
        """Test validation error when title is missing"""
        # Arrange
        mock_repository = Mock(spec=TodoRepository)
        service = TodoServiceRefactored(todo_repository=mock_repository)
        
        todo_data = {'description': 'No title'}
        
        # Act
        result = service.create_todo(user_id=1, todo_data=todo_data)
        
        # Assert
        assert result.success is False
        assert result.error_code == "VALIDATION_ERROR"
        assert "Title is required" in result.error
        mock_repository.create.assert_not_called()
    
    def test_create_todo_invalid_due_date(self):
        """Test validation error with invalid due date"""
        # Arrange
        mock_repository = Mock(spec=TodoRepository)
        service = TodoServiceRefactored(todo_repository=mock_repository)
        
        todo_data = {
            'title': 'Test Todo',
            'due_date': 'invalid-date'
        }
        
        # Act
        result = service.create_todo(user_id=1, todo_data=todo_data)
        
        # Assert
        assert result.success is False
        assert result.error_code == "VALIDATION_ERROR"
        assert "Invalid due date format" in result.error


class TestUpdateTodo:
    """Test update_todo method"""
    
    def test_update_todo_success(self):
        """Test successful todo update"""
        # Arrange
        mock_repository = Mock(spec=TodoRepository)
        service = TodoServiceRefactored(todo_repository=mock_repository)
        
        existing_todo = Mock(id=1, user_id=1, title="Old Title")
        mock_repository.find_by_id_and_user.return_value = existing_todo
        mock_repository.update.return_value = existing_todo
        
        updates = {'title': 'New Title', 'priority': 'high'}
        
        # Act
        result = service.update_todo(todo_id=1, user_id=1, updates=updates)
        
        # Assert
        assert result.success is True
        assert result.data == existing_todo
        mock_repository.find_by_id_and_user.assert_called_once_with(1, 1)
        mock_repository.update.assert_called_once()
    
    def test_update_todo_not_found(self):
        """Test updating non-existent todo"""
        # Arrange
        mock_repository = Mock(spec=TodoRepository)
        service = TodoServiceRefactored(todo_repository=mock_repository)
        mock_repository.find_by_id_and_user.return_value = None
        
        # Act
        result = service.update_todo(todo_id=999, user_id=1, updates={'title': 'New'})
        
        # Assert
        assert result.success is False
        assert result.error_code == "TODO_NOT_FOUND"
        mock_repository.update.assert_not_called()
    
    def test_update_todo_with_due_date(self):
        """Test updating todo with due date"""
        # Arrange
        mock_repository = Mock(spec=TodoRepository)
        service = TodoServiceRefactored(todo_repository=mock_repository)
        
        existing_todo = Mock(id=1, user_id=1)
        mock_repository.find_by_id_and_user.return_value = existing_todo
        mock_repository.update.return_value = existing_todo
        
        updates = {'due_date': '2024-12-31T10:00:00'}
        
        # Act
        result = service.update_todo(todo_id=1, user_id=1, updates=updates)
        
        # Assert
        assert result.success is True
        
        # Verify date was parsed correctly
        call_args = mock_repository.update.call_args[0][1]
        assert isinstance(call_args['due_date'], datetime)


class TestToggleTodoCompletion:
    """Test toggle_todo_completion method"""
    
    def test_toggle_todo_completion_to_complete(self):
        """Test marking todo as complete"""
        # Arrange
        mock_repository = Mock(spec=TodoRepository)
        service = TodoServiceRefactored(todo_repository=mock_repository)
        
        mock_todo = Mock(id=1, is_completed=False)
        mock_todo.mark_complete = Mock()
        mock_repository.find_by_id_and_user.return_value = mock_todo
        mock_repository.update.return_value = mock_todo
        
        # Act
        result = service.toggle_todo_completion(todo_id=1, user_id=1)
        
        # Assert
        assert result.success is True
        assert result.data == mock_todo
        mock_todo.mark_complete.assert_called_once()
        mock_repository.update.assert_called_once_with(1, {'is_completed': True, 'completed_at': mock_todo.completed_at})
    
    def test_toggle_todo_completion_to_incomplete(self):
        """Test marking todo as incomplete"""
        # Arrange
        mock_repository = Mock(spec=TodoRepository)
        service = TodoServiceRefactored(todo_repository=mock_repository)
        
        mock_todo = Mock(id=1, is_completed=True)
        mock_todo.mark_incomplete = Mock()
        mock_repository.find_by_id_and_user.return_value = mock_todo
        mock_repository.update.return_value = mock_todo
        
        # Act
        result = service.toggle_todo_completion(todo_id=1, user_id=1)
        
        # Assert
        assert result.success is True
        mock_todo.mark_incomplete.assert_called_once()
        mock_repository.update.assert_called_once_with(1, {'is_completed': False, 'completed_at': None})
    
    def test_toggle_todo_completion_not_found(self):
        """Test toggling non-existent todo"""
        # Arrange
        mock_repository = Mock(spec=TodoRepository)
        service = TodoServiceRefactored(todo_repository=mock_repository)
        mock_repository.find_by_id_and_user.return_value = None
        
        # Act
        result = service.toggle_todo_completion(todo_id=999, user_id=1)
        
        # Assert
        assert result.success is False
        assert result.error_code == "TODO_NOT_FOUND"


class TestDeleteTodo:
    """Test delete_todo method"""
    
    def test_delete_todo_success(self):
        """Test successful todo deletion"""
        # Arrange
        mock_repository = Mock(spec=TodoRepository)
        service = TodoServiceRefactored(todo_repository=mock_repository)
        
        mock_todo = Mock(id=1)
        mock_repository.find_by_id_and_user.return_value = mock_todo
        mock_repository.delete.return_value = True
        
        # Act
        result = service.delete_todo(todo_id=1, user_id=1)
        
        # Assert
        assert result.success is True
        assert result.data is True
        mock_repository.delete.assert_called_once_with(1)
    
    def test_delete_todo_not_found(self):
        """Test deleting non-existent todo"""
        # Arrange
        mock_repository = Mock(spec=TodoRepository)
        service = TodoServiceRefactored(todo_repository=mock_repository)
        mock_repository.find_by_id_and_user.return_value = None
        
        # Act
        result = service.delete_todo(todo_id=999, user_id=1)
        
        # Assert
        assert result.success is False
        assert result.error_code == "TODO_NOT_FOUND"
        mock_repository.delete.assert_not_called()


class TestGetTodoStats:
    """Test get_todo_stats method"""
    
    def test_get_todo_stats_success(self):
        """Test getting todo statistics"""
        # Arrange
        mock_repository = Mock(spec=TodoRepository)
        service = TodoServiceRefactored(todo_repository=mock_repository)
        
        mock_repository.count_by_user_id.return_value = 10
        mock_repository.count_completed_by_user_id.return_value = 3
        mock_repository.count_pending_by_user_id.return_value = 7
        mock_repository.count_high_priority_pending.return_value = 2
        mock_repository.count_overdue_by_user_id.return_value = 1
        
        # Act
        result = service.get_todo_stats(user_id=1)
        
        # Assert
        assert result.success is True
        assert result.data['total'] == 10
        assert result.data['completed'] == 3
        assert result.data['pending'] == 7
        assert result.data['high_priority'] == 2
        assert result.data['overdue'] == 1
    
    def test_get_todo_stats_empty(self):
        """Test stats for user with no todos"""
        # Arrange
        mock_repository = Mock(spec=TodoRepository)
        service = TodoServiceRefactored(todo_repository=mock_repository)
        
        mock_repository.count_by_user_id.return_value = 0
        mock_repository.count_completed_by_user_id.return_value = 0
        mock_repository.count_pending_by_user_id.return_value = 0
        mock_repository.count_high_priority_pending.return_value = 0
        mock_repository.count_overdue_by_user_id.return_value = 0
        
        # Act
        result = service.get_todo_stats(user_id=1)
        
        # Assert
        assert result.success is True
        assert all(v == 0 for v in result.data.values())


class TestSerializeTodo:
    """Test serialize_todo method (now instance method)"""
    
    def test_serialize_todo_complete(self):
        """Test serializing a complete todo"""
        # Arrange
        mock_repository = Mock(spec=TodoRepository)
        service = TodoServiceRefactored(todo_repository=mock_repository)
        
        mock_todo = Mock(
            id=1,
            title="Test Todo",
            description="Test Description",
            is_completed=True,
            priority="high",
            due_date=datetime(2024, 12, 31, 10, 0),
            created_at=datetime(2024, 1, 1, 9, 0),
            updated_at=datetime(2024, 1, 2, 10, 0),
            completed_at=datetime(2024, 1, 3, 11, 0)
        )
        
        # Act
        result = service.serialize_todo(mock_todo)
        
        # Assert
        assert result.success is True
        assert result.data['id'] == 1
        assert result.data['title'] == "Test Todo"
        assert result.data['is_completed'] is True
        assert result.data['due_date'] == "2024-12-31T10:00:00"
    
    def test_serialize_todo_with_nulls(self):
        """Test serializing todo with null fields"""
        # Arrange
        mock_repository = Mock(spec=TodoRepository)
        service = TodoServiceRefactored(todo_repository=mock_repository)
        
        mock_todo = Mock(
            id=1,
            title="Test",
            description="",
            is_completed=False,
            priority="medium",
            due_date=None,
            created_at=datetime.now(),
            updated_at=None,
            completed_at=None
        )
        
        # Act
        result = service.serialize_todo(mock_todo)
        
        # Assert
        assert result.success is True
        assert result.data['due_date'] is None
        assert result.data['updated_at'] is None
        assert result.data['completed_at'] is None
    
    def test_serialize_todo_invalid_input(self):
        """Test serializing with invalid input"""
        # Arrange
        mock_repository = Mock(spec=TodoRepository)
        service = TodoServiceRefactored(todo_repository=mock_repository)
        
        # Act
        result = service.serialize_todo(None)
        
        # Assert
        assert result.success is False
        assert result.error_code == "VALIDATION_ERROR"


class TestErrorHandling:
    """Test comprehensive error handling"""
    
    def test_repository_exception_handling(self):
        """Test that repository exceptions are caught and wrapped"""
        # Arrange
        mock_repository = Mock(spec=TodoRepository)
        service = TodoServiceRefactored(todo_repository=mock_repository)
        mock_repository.create.side_effect = Exception("Connection lost")
        
        # Act
        result = service.create_todo(user_id=1, todo_data={'title': 'Test'})
        
        # Assert
        assert result.success is False
        assert result.error_code == "TODO_CREATION_ERROR"
        assert "Connection lost" in result.error
    
    def test_invalid_priority_validation(self):
        """Test validation of priority values"""
        # Arrange
        mock_repository = Mock(spec=TodoRepository)
        service = TodoServiceRefactored(todo_repository=mock_repository)
        
        todo_data = {
            'title': 'Test',
            'priority': 'invalid'
        }
        
        # Act
        result = service.create_todo(user_id=1, todo_data=todo_data)
        
        # Assert
        assert result.success is False
        assert result.error_code == "VALIDATION_ERROR"
        assert "Invalid priority" in result.error