"""
TodoService - Handles all todo-related business logic
"""
from typing import List, Dict, Optional, Any
from datetime import datetime
from sqlalchemy import case
from extensions import db
from crm_database import Todo


class TodoService:
    """Service for managing user todos"""
    
    def get_user_todos(self, user_id: int, include_completed: bool = True) -> List[Todo]:
        """
        Get all todos for a user
        
        Args:
            user_id: The user's ID
            include_completed: Whether to include completed todos
            
        Returns:
            List of Todo objects ordered by completion status and creation date
        """
        query = Todo.query.filter_by(user_id=user_id)
        
        if not include_completed:
            query = query.filter_by(is_completed=False)
        
        return query.order_by(
            Todo.is_completed.asc(),
            Todo.created_at.desc()
        ).all()
    
    def get_dashboard_todos(self, user_id: int, limit: int = 5) -> Dict[str, Any]:
        """
        Get todos for dashboard widget with priority sorting
        
        Args:
            user_id: The user's ID
            limit: Maximum number of todos to return
            
        Returns:
            Dict containing todos list and pending count
        """
        # Get incomplete todos ordered by priority and created date
        todos = Todo.query.filter_by(
            user_id=user_id,
            is_completed=False
        ).order_by(
            case(
                (Todo.priority == 'high', 1),
                (Todo.priority == 'medium', 2),
                (Todo.priority == 'low', 3),
                else_=4
            ),
            Todo.created_at.desc()
        ).limit(limit).all()
        
        # Get total pending count
        pending_count = Todo.query.filter_by(
            user_id=user_id,
            is_completed=False
        ).count()
        
        return {
            'todos': todos,
            'pending_count': pending_count
        }
    
    def create_todo(self, user_id: int, todo_data: Dict[str, Any]) -> Todo:
        """
        Create a new todo
        
        Args:
            user_id: The user's ID
            todo_data: Dictionary containing todo data
            
        Returns:
            Created Todo object
            
        Raises:
            ValueError: If required fields are missing or invalid
        """
        if not todo_data.get('title'):
            raise ValueError('Title is required')
        
        todo = Todo(
            title=todo_data['title'],
            description=todo_data.get('description', ''),
            priority=todo_data.get('priority', 'medium'),
            user_id=user_id
        )
        
        # Handle due date if provided
        if todo_data.get('due_date'):
            try:
                if isinstance(todo_data['due_date'], str):
                    todo.due_date = datetime.fromisoformat(todo_data['due_date'])
                else:
                    todo.due_date = todo_data['due_date']
            except (ValueError, TypeError) as e:
                raise ValueError(f'Invalid due date format: {e}')
        
        db.session.add(todo)
        db.session.commit()
        
        return todo
    
    def update_todo(self, todo_id: int, user_id: int, updates: Dict[str, Any]) -> Optional[Todo]:
        """
        Update an existing todo
        
        Args:
            todo_id: The todo's ID
            user_id: The user's ID (for ownership verification)
            updates: Dictionary containing fields to update
            
        Returns:
            Updated Todo object or None if not found
            
        Raises:
            ValueError: If due date format is invalid
        """
        todo = Todo.query.filter_by(id=todo_id, user_id=user_id).first()
        
        if not todo:
            return None
        
        # Update fields if provided
        if 'title' in updates:
            todo.title = updates['title']
        
        if 'description' in updates:
            todo.description = updates['description']
        
        if 'priority' in updates:
            todo.priority = updates['priority']
        
        if 'due_date' in updates:
            if updates['due_date']:
                try:
                    if isinstance(updates['due_date'], str):
                        todo.due_date = datetime.fromisoformat(updates['due_date'])
                    else:
                        todo.due_date = updates['due_date']
                except (ValueError, TypeError) as e:
                    raise ValueError(f'Invalid due date format: {e}')
            else:
                todo.due_date = None
        
        todo.updated_at = datetime.utcnow()
        db.session.commit()
        
        return todo
    
    def toggle_todo_completion(self, todo_id: int, user_id: int) -> Optional[Todo]:
        """
        Toggle the completion status of a todo
        
        Args:
            todo_id: The todo's ID
            user_id: The user's ID (for ownership verification)
            
        Returns:
            Updated Todo object or None if not found
        """
        todo = Todo.query.filter_by(id=todo_id, user_id=user_id).first()
        
        if not todo:
            return None
        
        if todo.is_completed:
            todo.mark_incomplete()
        else:
            todo.mark_complete()
        
        db.session.commit()
        
        return todo
    
    def delete_todo(self, todo_id: int, user_id: int) -> bool:
        """
        Delete a todo
        
        Args:
            todo_id: The todo's ID
            user_id: The user's ID (for ownership verification)
            
        Returns:
            True if deleted, False if not found
        """
        todo = Todo.query.filter_by(id=todo_id, user_id=user_id).first()
        
        if not todo:
            return False
        
        db.session.delete(todo)
        db.session.commit()
        
        return True
    
    def get_todo_by_id(self, todo_id: int, user_id: int) -> Optional[Todo]:
        """
        Get a single todo by ID
        
        Args:
            todo_id: The todo's ID
            user_id: The user's ID (for ownership verification)
            
        Returns:
            Todo object or None if not found
        """
        return Todo.query.filter_by(id=todo_id, user_id=user_id).first()
    
    def get_todo_stats(self, user_id: int) -> Dict[str, int]:
        """
        Get statistics about user's todos
        
        Args:
            user_id: The user's ID
            
        Returns:
            Dictionary with todo statistics
        """
        total = Todo.query.filter_by(user_id=user_id).count()
        completed = Todo.query.filter_by(user_id=user_id, is_completed=True).count()
        pending = Todo.query.filter_by(user_id=user_id, is_completed=False).count()
        
        high_priority = Todo.query.filter_by(
            user_id=user_id, 
            is_completed=False, 
            priority='high'
        ).count()
        
        overdue = Todo.query.filter(
            Todo.user_id == user_id,
            Todo.is_completed == False,
            Todo.due_date < datetime.utcnow()
        ).count()
        
        return {
            'total': total,
            'completed': completed,
            'pending': pending,
            'high_priority': high_priority,
            'overdue': overdue
        }
    
    @staticmethod
    def serialize_todo(todo: Todo) -> Dict[str, Any]:
        """
        Serialize a Todo object to dictionary for API responses
        
        Args:
            todo: Todo object to serialize
            
        Returns:
            Dictionary representation of the todo
        """
        return {
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