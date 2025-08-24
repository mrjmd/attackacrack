"""
TodoRepository - Data access layer for Todo model
"""

from typing import List, Optional
from datetime import datetime, date
from utils.datetime_utils import utc_now
from sqlalchemy import desc, or_, and_
from repositories.base_repository import BaseRepository, PaginatedResult
from crm_database import Todo


class TodoRepository(BaseRepository):
    """Repository for Todo data access"""
    
    def __init__(self, session):
        """Initialize repository with database session"""
        super().__init__(session, Todo)
    
    def find_by_priority(self, priority: str) -> List:
        """
        Find todos by priority level.
        
        Args:
            priority: Priority level (low, medium, high)
            
        Returns:
            List of Todo objects
        """
        return self.session.query(self.model_class)\
            .filter_by(priority=priority)\
            .all()
    
    def find_completed_todos(self) -> List:
        """
        Find all completed todos.
        
        Returns:
            List of completed Todo objects
        """
        return self.session.query(self.model_class)\
            .filter_by(is_completed=True)\
            .all()
    
    def find_pending_todos(self) -> List:
        """
        Find all pending (incomplete) todos.
        
        Returns:
            List of pending Todo objects
        """
        return self.session.query(self.model_class)\
            .filter_by(is_completed=False)\
            .all()
    
    def find_overdue_todos(self) -> List:
        """
        Find todos that are overdue.
        
        Returns:
            List of overdue Todo objects
        """
        now = utc_now()
        return self.session.query(self.model_class)\
            .filter(self.model_class.due_date < now)\
            .filter(self.model_class.is_completed == False)\
            .all()
    
    def mark_as_completed(self, todo_id: int):
        """
        Mark a todo as completed.
        
        Args:
            todo_id: ID of the todo
            
        Returns:
            Updated Todo object
        """
        todo = self.session.get(self.model_class, todo_id)
        if todo:
            todo.is_completed = True
            todo.completed_at = utc_now()
            self.session.commit()
        return todo
    
    def mark_as_pending(self, todo_id: int):
        """
        Mark a todo as pending (incomplete).
        
        Args:
            todo_id: ID of the todo
            
        Returns:
            Updated Todo object
        """
        todo = self.session.get(self.model_class, todo_id)
        if todo:
            todo.is_completed = False
            todo.completed_at = None
            self.session.commit()
        return todo
    
    def find_by_user_id(self, user_id: int, include_completed: bool = True) -> List:
        """
        Find todos by user ID.
        
        Args:
            user_id: ID of the user
            include_completed: Whether to include completed todos
            
        Returns:
            List of Todo objects
        """
        query = self.session.query(self.model_class).filter_by(user_id=user_id)
        
        if not include_completed:
            query = query.filter_by(is_completed=False)
        
        return query.order_by(
            self.model_class.is_completed.asc(),
            self.model_class.created_at.desc()
        ).all()
    
    def find_by_user_id_with_priority(self, user_id: int, limit: int = 5) -> List:
        """
        Find incomplete todos for a user ordered by priority.
        
        Args:
            user_id: ID of the user
            limit: Maximum number of results
            
        Returns:
            List of Todo objects ordered by priority
        """
        from sqlalchemy import case
        
        return self.session.query(self.model_class).filter_by(
            user_id=user_id,
            is_completed=False
        ).order_by(
            case(
                (self.model_class.priority == 'high', 1),
                (self.model_class.priority == 'medium', 2),
                (self.model_class.priority == 'low', 3),
                else_=4
            ),
            self.model_class.created_at.desc()
        ).limit(limit).all()
    
    def find_by_id_and_user(self, todo_id: int, user_id: int):
        """
        Find a todo by ID and user ID (for ownership verification).
        
        Args:
            todo_id: ID of the todo
            user_id: ID of the user
            
        Returns:
            Todo object or None
        """
        return self.session.query(self.model_class).filter_by(
            id=todo_id,
            user_id=user_id
        ).first()
    
    def count_by_user_id(self, user_id: int) -> int:
        """
        Count total todos for a user.
        
        Args:
            user_id: ID of the user
            
        Returns:
            Total count
        """
        return self.session.query(self.model_class).filter_by(user_id=user_id).count()
    
    def count_completed_by_user_id(self, user_id: int) -> int:
        """
        Count completed todos for a user.
        
        Args:
            user_id: ID of the user
            
        Returns:
            Count of completed todos
        """
        return self.session.query(self.model_class).filter_by(
            user_id=user_id,
            is_completed=True
        ).count()
    
    def count_pending_by_user_id(self, user_id: int) -> int:
        """
        Count pending todos for a user.
        
        Args:
            user_id: ID of the user
            
        Returns:
            Count of pending todos
        """
        return self.session.query(self.model_class).filter_by(
            user_id=user_id,
            is_completed=False
        ).count()
    
    def count_high_priority_pending(self, user_id: int) -> int:
        """
        Count high priority pending todos for a user.
        
        Args:
            user_id: ID of the user
            
        Returns:
            Count of high priority pending todos
        """
        return self.session.query(self.model_class).filter_by(
            user_id=user_id,
            is_completed=False,
            priority='high'
        ).count()
    
    def count_overdue_by_user_id(self, user_id: int) -> int:
        """
        Count overdue todos for a user.
        
        Args:
            user_id: ID of the user
            
        Returns:
            Count of overdue todos
        """
        now = utc_now()
        return self.session.query(self.model_class).filter(
            self.model_class.user_id == user_id,
            self.model_class.is_completed == False,
            self.model_class.due_date < now
        ).count()
    
    def update_priority(self, todo_id: int, priority: str):
        """
        Update todo priority.
        
        Args:
            todo_id: ID of the todo
            priority: New priority level
            
        Returns:
            Updated Todo object
        """
        todo = self.session.get(self.model_class, todo_id)
        if todo:
            todo.priority = priority
            self.session.commit()
        return todo
    
    def search(self, query: str) -> List:
        """
        Search todos by title or description.
        
        Args:
            query: Search query string
            
        Returns:
            List of matching Todo objects
        """
        if not query:
            return []
        
        search_filter = or_(
            self.model_class.title.ilike(f'%{query}%'),
            self.model_class.description.ilike(f'%{query}%')
        )
        
        return self.session.query(self.model_class)\
            .filter(search_filter)\
            .limit(100)\
            .all()