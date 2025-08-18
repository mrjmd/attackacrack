"""
TodoServiceRefactored - Refactored Todo service with repository pattern and Result pattern
"""

from typing import List, Dict, Optional, Any
from datetime import datetime
# Model and db imports removed - using repositories only
from repositories.todo_repository import TodoRepository
from services.common.result import Result


class TodoServiceRefactored:
    """Refactored service for managing user todos with Result pattern"""
    
    def __init__(self, todo_repository: Optional[TodoRepository] = None):
        """
        Initialize with optional repository.
        
        Args:
            todo_repository: TodoRepository for data access
        """
        if not todo_repository:
            raise ValueError("TodoRepository must be provided via dependency injection")
        self.todo_repository = todo_repository
    
    def get_user_todos(self, user_id: int, include_completed: bool = True):
        """
        Get all todos for a user.
        
        Args:
            user_id: The user's ID
            include_completed: Whether to include completed todos
            
        Returns:
            List of Todo objects (for backward compatibility)
        """
        # For backward compatibility, return the data directly
        result = self.get_user_todos_result(user_id, include_completed)
        if result.success:
            return result.data
        return []  # Return empty list on error for compatibility
    
    def get_user_todos_result(self, user_id: int, include_completed: bool = True) -> Result[List[Dict]]:
        """
        Get all todos for a user with Result pattern.
        
        Args:
            user_id: The user's ID
            include_completed: Whether to include completed todos
            
        Returns:
            Result containing list of Todo objects or error
        """
        # Validate input
        if not user_id:
            return Result.failure("User ID is required", code="VALIDATION_ERROR")
        
        try:
            # Use repository method (needs to be added to TodoRepository)
            todos = self.todo_repository.find_by_user_id(user_id, include_completed=include_completed)
            return Result.success(todos)
        except Exception as e:
            return Result.failure(
                f"Failed to retrieve todos: {str(e)}",
                code="REPOSITORY_ERROR"
            )
    
    def get_dashboard_todos(self, user_id: int, limit: int = 5) -> Dict[str, Any]:
        """
        Get todos for dashboard widget with priority sorting.
        
        Args:
            user_id: The user's ID
            limit: Maximum number of todos to return
            
        Returns:
            Dict with todos list and pending count (for backward compatibility)
        """
        # For backward compatibility, return the data directly
        result = self.get_dashboard_todos_result(user_id, limit)
        if result.success:
            return result.data
        return {'todos': [], 'pending_count': 0}  # Return safe defaults on error
    
    def get_dashboard_todos_result(self, user_id: int, limit: int = 5) -> Result[Dict[str, Any]]:
        """
        Get todos for dashboard widget with priority sorting (Result pattern).
        
        Args:
            user_id: The user's ID
            limit: Maximum number of todos to return
            
        Returns:
            Result containing dict with todos list and pending count
        """
        if not user_id:
            return Result.failure("User ID is required", code="VALIDATION_ERROR")
        
        try:
            # Get incomplete todos ordered by priority
            todos = self.todo_repository.find_by_user_id_with_priority(user_id, limit=limit)
            
            # Get total pending count
            pending_count = self.todo_repository.count_pending_by_user_id(user_id)
            
            dashboard_data = {
                'todos': todos,
                'pending_count': pending_count
            }
            
            return Result.success(dashboard_data)
        except Exception as e:
            return Result.failure(
                f"Failed to retrieve dashboard todos: {str(e)}",
                code="REPOSITORY_ERROR"
            )
    
    def create_todo(self, user_id: int, todo_data: Dict[str, Any]) -> Result[Dict]:
        """
        Create a new todo.
        
        Args:
            user_id: The user's ID
            todo_data: Dictionary containing todo data
            
        Returns:
            Result containing created Todo object or error
        """
        # Validate required fields
        if not todo_data.get('title'):
            return Result.failure('Title is required', code="VALIDATION_ERROR")
        
        if not user_id:
            return Result.failure('User ID is required', code="VALIDATION_ERROR")
        
        # Validate priority if provided
        valid_priorities = ['low', 'medium', 'high']
        priority = todo_data.get('priority', 'medium')
        if priority not in valid_priorities:
            return Result.failure(
                f"Invalid priority: {priority}. Must be one of {valid_priorities}",
                code="VALIDATION_ERROR"
            )
        
        # Handle due date parsing
        due_date = None
        if todo_data.get('due_date'):
            try:
                if isinstance(todo_data['due_date'], str):
                    due_date = datetime.fromisoformat(todo_data['due_date'])
                else:
                    due_date = todo_data['due_date']
            except (ValueError, TypeError) as e:
                return Result.failure(
                    f'Invalid due date format: {str(e)}',
                    code="VALIDATION_ERROR"
                )
        
        # Prepare data for repository
        create_data = {
            'title': todo_data['title'],
            'description': todo_data.get('description', ''),
            'priority': priority,
            'user_id': user_id,
            'due_date': due_date
        }
        
        try:
            todo = self.todo_repository.create(create_data)
            return Result.success(todo)
        except Exception as e:
            return Result.failure(
                f"Failed to create todo: {str(e)}",
                code="TODO_CREATION_ERROR"
            )
    
    def update_todo(self, todo_id: int, user_id: int, updates: Dict[str, Any]) -> Result[Dict]:
        """
        Update an existing todo.
        
        Args:
            todo_id: The todo's ID
            user_id: The user's ID (for ownership verification)
            updates: Dictionary containing fields to update
            
        Returns:
            Result containing updated Todo object or error
        """
        if not todo_id or not user_id:
            return Result.failure("Todo ID and User ID are required", code="VALIDATION_ERROR")
        
        try:
            # Check if todo exists and belongs to user
            todo = self.todo_repository.find_by_id_and_user(todo_id, user_id)
            if not todo:
                return Result.failure(
                    f"Todo with ID {todo_id} not found for user",
                    code="TODO_NOT_FOUND"
                )
            
            # Process updates
            update_data = {}
            
            if 'title' in updates:
                update_data['title'] = updates['title']
            
            if 'description' in updates:
                update_data['description'] = updates['description']
            
            if 'priority' in updates:
                valid_priorities = ['low', 'medium', 'high']
                if updates['priority'] not in valid_priorities:
                    return Result.failure(
                        f"Invalid priority: {updates['priority']}",
                        code="VALIDATION_ERROR"
                    )
                update_data['priority'] = updates['priority']
            
            # Handle due date
            if 'due_date' in updates:
                if updates['due_date']:
                    try:
                        if isinstance(updates['due_date'], str):
                            update_data['due_date'] = datetime.fromisoformat(updates['due_date'])
                        else:
                            update_data['due_date'] = updates['due_date']
                    except (ValueError, TypeError) as e:
                        return Result.failure(
                            f'Invalid due date format: {str(e)}',
                            code="VALIDATION_ERROR"
                        )
                else:
                    update_data['due_date'] = None
            
            # Always update the updated_at timestamp
            update_data['updated_at'] = datetime.utcnow()
            
            # Perform update
            updated_todo = self.todo_repository.update(todo_id, update_data)
            return Result.success(updated_todo)
            
        except Exception as e:
            return Result.failure(
                f"Failed to update todo: {str(e)}",
                code="TODO_UPDATE_ERROR"
            )
    
    def toggle_todo_completion(self, todo_id: int, user_id: int) -> Result[Dict]:
        """
        Toggle the completion status of a todo.
        
        Args:
            todo_id: The todo's ID
            user_id: The user's ID (for ownership verification)
            
        Returns:
            Result containing updated Todo object or error
        """
        if not todo_id or not user_id:
            return Result.failure("Todo ID and User ID are required", code="VALIDATION_ERROR")
        
        try:
            # Get the todo
            todo = self.todo_repository.find_by_id_and_user(todo_id, user_id)
            if not todo:
                return Result.failure(
                    f"Todo with ID {todo_id} not found for user",
                    code="TODO_NOT_FOUND"
                )
            
            # Toggle completion status
            if todo.is_completed:
                todo.mark_incomplete()
                update_data = {
                    'is_completed': False,
                    'completed_at': None
                }
            else:
                todo.mark_complete()
                update_data = {
                    'is_completed': True,
                    'completed_at': todo.completed_at
                }
            
            # Update in repository
            updated_todo = self.todo_repository.update(todo_id, update_data)
            return Result.success(updated_todo)
            
        except Exception as e:
            return Result.failure(
                f"Failed to toggle todo completion: {str(e)}",
                code="TODO_UPDATE_ERROR"
            )
    
    def delete_todo(self, todo_id: int, user_id: int) -> Result[bool]:
        """
        Delete a todo.
        
        Args:
            todo_id: The todo's ID
            user_id: The user's ID (for ownership verification)
            
        Returns:
            Result containing True if deleted or error
        """
        if not todo_id or not user_id:
            return Result.failure("Todo ID and User ID are required", code="VALIDATION_ERROR")
        
        try:
            # Check if todo exists and belongs to user
            todo = self.todo_repository.find_by_id_and_user(todo_id, user_id)
            if not todo:
                return Result.failure(
                    f"Todo with ID {todo_id} not found for user",
                    code="TODO_NOT_FOUND"
                )
            
            # Delete the todo
            success = self.todo_repository.delete(todo_id)
            return Result.success(success)
            
        except Exception as e:
            return Result.failure(
                f"Failed to delete todo: {str(e)}",
                code="TODO_DELETION_ERROR"
            )
    
    def get_todo_by_id(self, todo_id: int, user_id: int) -> Result[Dict]:
        """
        Get a single todo by ID.
        
        Args:
            todo_id: The todo's ID
            user_id: The user's ID (for ownership verification)
            
        Returns:
            Result containing Todo object or error
        """
        if not todo_id or not user_id:
            return Result.failure("Todo ID and User ID are required", code="VALIDATION_ERROR")
        
        try:
            todo = self.todo_repository.find_by_id_and_user(todo_id, user_id)
            if not todo:
                return Result.failure(
                    f"Todo with ID {todo_id} not found for user",
                    code="TODO_NOT_FOUND"
                )
            
            return Result.success(todo)
            
        except Exception as e:
            return Result.failure(
                f"Failed to retrieve todo: {str(e)}",
                code="REPOSITORY_ERROR"
            )
    
    def get_todo_stats(self, user_id: int) -> Result[Dict[str, int]]:
        """
        Get statistics about user's todos.
        
        Args:
            user_id: The user's ID
            
        Returns:
            Result containing dictionary with todo statistics
        """
        if not user_id:
            return Result.failure("User ID is required", code="VALIDATION_ERROR")
        
        try:
            stats = {
                'total': self.todo_repository.count_by_user_id(user_id),
                'completed': self.todo_repository.count_completed_by_user_id(user_id),
                'pending': self.todo_repository.count_pending_by_user_id(user_id),
                'high_priority': self.todo_repository.count_high_priority_pending(user_id),
                'overdue': self.todo_repository.count_overdue_by_user_id(user_id)
            }
            
            return Result.success(stats)
            
        except Exception as e:
            return Result.failure(
                f"Failed to retrieve todo statistics: {str(e)}",
                code="REPOSITORY_ERROR"
            )
    
    def serialize_todo(self, todo) -> Dict[str, Any]:
        """
        Serialize a Todo object to dictionary for API responses.
        
        Args:
            todo: Todo object to serialize
            
        Returns:
            Dictionary representation of the todo (for backward compatibility)
        """
        # For backward compatibility, return the data directly
        result = self.serialize_todo_result(todo)
        if result.success:
            return result.data
        # Return a minimal representation on error
        return {'id': getattr(todo, 'id', None), 'title': getattr(todo, 'title', 'Unknown')}
    
    def serialize_todo_result(self, todo) -> Result[Dict[str, Any]]:
        """
        Serialize a Todo object to dictionary for API responses (Result pattern).
        
        Args:
            todo: Todo object to serialize
            
        Returns:
            Result containing dictionary representation of the todo
        """
        if not todo:
            return Result.failure("Todo object is required", code="VALIDATION_ERROR")
        
        try:
            serialized = {
                'id': todo.id,
                'title': todo.title,
                'description': todo.description,
                'is_completed': todo.is_completed,
                'priority': todo.priority,
                'due_date': todo.due_date.isoformat() if todo.due_date else None,
                'created_at': todo.created_at.isoformat(),
                'updated_at': todo.updated_at.isoformat() if todo.updated_at else None,
                'completed_at': todo.completed_at.isoformat() if todo.completed_at else None
            }
            
            return Result.success(serialized)
            
        except Exception as e:
            return Result.failure(
                f"Failed to serialize todo: {str(e)}",
                code="SERIALIZATION_ERROR"
            )

# Alias for compatibility
TodoService = TodoServiceRefactored