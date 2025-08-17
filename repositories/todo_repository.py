"""
TodoRepository - Data access layer for Todo model
"""

from typing import List, Optional
from datetime import datetime, date
from sqlalchemy import desc, or_, and_
from repositories.base_repository import BaseRepository, PaginatedResult


class TodoRepository(BaseRepository):
    """Repository for Todo data access"""
    
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
        now = datetime.utcnow()
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
        todo = self.session.query(self.model_class).get(todo_id)
        if todo:
            todo.is_completed = True
            todo.completed_at = datetime.utcnow()
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
        todo = self.session.query(self.model_class).get(todo_id)
        if todo:
            todo.is_completed = False
            todo.completed_at = None
            self.session.commit()
        return todo
    
    def update_priority(self, todo_id: int, priority: str):
        """
        Update todo priority.
        
        Args:
            todo_id: ID of the todo
            priority: New priority level
            
        Returns:
            Updated Todo object
        """
        todo = self.session.query(self.model_class).get(todo_id)
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