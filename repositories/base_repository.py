"""
Base Repository - Abstract base class for all repositories
Implements common database operations following the Repository Pattern
"""

from abc import ABC, abstractmethod
from typing import TypeVar, Generic, List, Optional, Dict, Any, Tuple, Type
from sqlalchemy.orm import Session, Query
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import and_, or_, desc, asc
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)

# Type variable for model classes
T = TypeVar('T')


class SortOrder(Enum):
    """Sort order options"""
    ASC = "asc"
    DESC = "desc"


@dataclass
class PaginationParams:
    """Parameters for pagination"""
    page: int = 1
    per_page: int = 20
    
    @property
    def offset(self) -> int:
        """Calculate offset for query"""
        return (self.page - 1) * self.per_page
    
    @property
    def limit(self) -> int:
        """Get limit for query"""
        return self.per_page


@dataclass
class PaginatedResult(Generic[T]):
    """Result of a paginated query"""
    items: List[T]
    total: int
    page: int
    per_page: int
    
    @property
    def pages(self) -> int:
        """Calculate total number of pages"""
        return (self.total + self.per_page - 1) // self.per_page if self.per_page > 0 else 0
    
    @property
    def has_prev(self) -> bool:
        """Check if there's a previous page"""
        return self.page > 1
    
    @property
    def has_next(self) -> bool:
        """Check if there's a next page"""
        return self.page < self.pages
    
    @property
    def prev_page(self) -> Optional[int]:
        """Get previous page number"""
        return self.page - 1 if self.has_prev else None
    
    @property
    def next_page(self) -> Optional[int]:
        """Get next page number"""
        return self.page + 1 if self.has_next else None


class BaseRepository(ABC, Generic[T]):
    """
    Abstract base repository with common CRUD operations.
    
    This class provides a foundation for all repository implementations,
    ensuring consistent database access patterns across the application.
    """
    
    def __init__(self, session: Session, model_class: Type[T]):
        """
        Initialize repository with database session and model class.
        
        Args:
            session: SQLAlchemy database session
            model_class: The model class this repository manages
        """
        self.session = session
        self.model_class = model_class
    
    # CREATE Operations
    
    def create(self, **kwargs) -> T:
        """
        Create a new entity.
        
        Args:
            **kwargs: Attributes for the new entity
            
        Returns:
            Created entity instance
            
        Raises:
            SQLAlchemyError: If database operation fails
        """
        try:
            entity = self.model_class(**kwargs)
            self.session.add(entity)
            self.session.flush()  # Flush to get ID without committing
            logger.debug(f"Created {self.model_class.__name__} with id {entity.id}")
            return entity
        except SQLAlchemyError as e:
            logger.error(f"Error creating {self.model_class.__name__}: {e}")
            self.session.rollback()
            raise
    
    def create_many(self, entities_data: List[Dict[str, Any]]) -> List[T]:
        """
        Create multiple entities in a single operation.
        
        Args:
            entities_data: List of dictionaries with entity attributes
            
        Returns:
            List of created entities
            
        Raises:
            SQLAlchemyError: If database operation fails
        """
        try:
            entities = [self.model_class(**data) for data in entities_data]
            self.session.add_all(entities)
            self.session.flush()
            logger.debug(f"Created {len(entities)} {self.model_class.__name__} entities")
            return entities
        except SQLAlchemyError as e:
            logger.error(f"Error creating multiple {self.model_class.__name__}: {e}")
            self.session.rollback()
            raise
    
    # READ Operations
    
    def get_by_id(self, entity_id: int) -> Optional[T]:
        """
        Get entity by ID.
        
        Args:
            entity_id: Entity ID
            
        Returns:
            Entity instance or None if not found
        """
        try:
            return self.session.get(self.model_class, entity_id)
        except SQLAlchemyError as e:
            logger.error(f"Error getting {self.model_class.__name__} by id {entity_id}: {e}")
            return None
    
    def get_all(self, order_by: Optional[str] = None, 
                order: SortOrder = SortOrder.ASC) -> List[T]:
        """
        Get all entities with optional ordering.
        
        Args:
            order_by: Field name to order by
            order: Sort order (ASC or DESC)
            
        Returns:
            List of all entities
        """
        try:
            query = self.session.query(self.model_class)
            
            if order_by:
                order_field = getattr(self.model_class, order_by, None)
                if order_field:
                    query = query.order_by(
                        desc(order_field) if order == SortOrder.DESC else asc(order_field)
                    )
            
            return query.all()
        except SQLAlchemyError as e:
            logger.error(f"Error getting all {self.model_class.__name__}: {e}")
            return []
    
    def get_paginated(self, 
                     pagination: PaginationParams,
                     filters: Optional[Dict[str, Any]] = None,
                     order_by: Optional[str] = None,
                     order: SortOrder = SortOrder.ASC) -> PaginatedResult[T]:
        """
        Get paginated results with optional filtering and ordering.
        
        Args:
            pagination: Pagination parameters
            filters: Dictionary of filters to apply
            order_by: Field name to order by
            order: Sort order
            
        Returns:
            PaginatedResult with items and metadata
        """
        try:
            query = self._build_query(filters)
            
            # Apply ordering
            if order_by:
                order_field = getattr(self.model_class, order_by, None)
                if order_field:
                    query = query.order_by(
                        desc(order_field) if order == SortOrder.DESC else asc(order_field)
                    )
            
            # Get total count
            total = query.count()
            
            # Apply pagination
            items = query.offset(pagination.offset).limit(pagination.limit).all()
            
            return PaginatedResult(
                items=items,
                total=total,
                page=pagination.page,
                per_page=pagination.per_page
            )
        except SQLAlchemyError as e:
            logger.error(f"Error getting paginated {self.model_class.__name__}: {e}")
            return PaginatedResult(items=[], total=0, page=1, per_page=pagination.per_page)
    
    def find_by(self, **filters) -> List[T]:
        """
        Find entities by specific field values.
        
        Args:
            **filters: Field-value pairs to filter by
            
        Returns:
            List of matching entities
        """
        try:
            query = self.session.query(self.model_class)
            for field, value in filters.items():
                if hasattr(self.model_class, field):
                    query = query.filter(getattr(self.model_class, field) == value)
            return query.all()
        except SQLAlchemyError as e:
            logger.error(f"Error finding {self.model_class.__name__} by filters: {e}")
            return []
    
    def find_one_by(self, **filters) -> Optional[T]:
        """
        Find single entity by specific field values.
        
        Args:
            **filters: Field-value pairs to filter by
            
        Returns:
            First matching entity or None
        """
        results = self.find_by(**filters)
        return results[0] if results else None
    
    def exists(self, **filters) -> bool:
        """
        Check if entity exists with given filters.
        
        Args:
            **filters: Field-value pairs to check
            
        Returns:
            True if entity exists, False otherwise
        """
        try:
            query = self.session.query(self.model_class)
            for field, value in filters.items():
                if hasattr(self.model_class, field):
                    query = query.filter(getattr(self.model_class, field) == value)
            return query.first() is not None
        except SQLAlchemyError as e:
            logger.error(f"Error checking existence of {self.model_class.__name__}: {e}")
            return False
    
    def count(self, **filters) -> int:
        """
        Count entities matching filters.
        
        Args:
            **filters: Field-value pairs to filter by
            
        Returns:
            Count of matching entities
        """
        try:
            query = self.session.query(self.model_class)
            for field, value in filters.items():
                if hasattr(self.model_class, field):
                    query = query.filter(getattr(self.model_class, field) == value)
            return query.count()
        except SQLAlchemyError as e:
            logger.error(f"Error counting {self.model_class.__name__}: {e}")
            return 0
    
    # UPDATE Operations
    
    def update(self, entity: T, **updates) -> T:
        """
        Update an entity with new values.
        
        Args:
            entity: Entity to update
            **updates: Field-value pairs to update
            
        Returns:
            Updated entity
            
        Raises:
            SQLAlchemyError: If database operation fails
        """
        try:
            for field, value in updates.items():
                if hasattr(entity, field):
                    setattr(entity, field, value)
            self.session.flush()
            logger.debug(f"Updated {self.model_class.__name__} with id {entity.id}")
            return entity
        except SQLAlchemyError as e:
            logger.error(f"Error updating {self.model_class.__name__}: {e}")
            self.session.rollback()
            raise
    
    def update_by_id(self, entity_id: int, **updates) -> Optional[T]:
        """
        Update entity by ID.
        
        Args:
            entity_id: Entity ID
            **updates: Field-value pairs to update
            
        Returns:
            Updated entity or None if not found
        """
        entity = self.get_by_id(entity_id)
        if entity:
            return self.update(entity, **updates)
        return None
    
    def update_many(self, filters: Dict[str, Any], updates: Dict[str, Any]) -> int:
        """
        Update multiple entities matching filters.
        
        Args:
            filters: Conditions to match entities
            updates: Field-value pairs to update
            
        Returns:
            Number of updated entities
        """
        try:
            query = self._build_query(filters)
            count = query.update(updates, synchronize_session=False)
            self.session.flush()
            logger.debug(f"Updated {count} {self.model_class.__name__} entities")
            return count
        except SQLAlchemyError as e:
            logger.error(f"Error updating multiple {self.model_class.__name__}: {e}")
            self.session.rollback()
            return 0
    
    # DELETE Operations
    
    def delete(self, entity: T) -> bool:
        """
        Delete an entity.
        
        Args:
            entity: Entity to delete
            
        Returns:
            True if successful, False otherwise
        """
        try:
            self.session.delete(entity)
            self.session.flush()
            logger.debug(f"Deleted {self.model_class.__name__} with id {entity.id}")
            return True
        except SQLAlchemyError as e:
            logger.error(f"Error deleting {self.model_class.__name__}: {e}")
            self.session.rollback()
            return False
    
    def delete_by_id(self, entity_id: int) -> bool:
        """
        Delete entity by ID.
        
        Args:
            entity_id: Entity ID
            
        Returns:
            True if successful, False otherwise
        """
        entity = self.get_by_id(entity_id)
        if entity:
            return self.delete(entity)
        return False
    
    def delete_many(self, filters: Dict[str, Any]) -> int:
        """
        Delete multiple entities matching filters.
        
        Args:
            filters: Conditions to match entities
            
        Returns:
            Number of deleted entities
        """
        try:
            query = self._build_query(filters)
            count = query.delete(synchronize_session=False)
            self.session.flush()
            logger.debug(f"Deleted {count} {self.model_class.__name__} entities")
            return count
        except SQLAlchemyError as e:
            logger.error(f"Error deleting multiple {self.model_class.__name__}: {e}")
            self.session.rollback()
            return 0
    
    # Transaction Management
    
    def commit(self) -> None:
        """Commit the current transaction."""
        try:
            self.session.commit()
        except SQLAlchemyError as e:
            logger.error(f"Error committing transaction: {e}")
            self.session.rollback()
            raise
    
    def rollback(self) -> None:
        """Rollback the current transaction."""
        self.session.rollback()
    
    def flush(self) -> None:
        """Flush pending changes without committing."""
        self.session.flush()
    
    # Helper Methods
    
    def _build_query(self, filters: Optional[Dict[str, Any]] = None) -> Query:
        """
        Build a query with filters.
        
        Args:
            filters: Dictionary of filters to apply
            
        Returns:
            SQLAlchemy Query object
        """
        query = self.session.query(self.model_class)
        
        if filters:
            for field, value in filters.items():
                if hasattr(self.model_class, field):
                    if isinstance(value, list):
                        # Handle IN clause
                        query = query.filter(getattr(self.model_class, field).in_(value))
                    elif value is None:
                        # Handle NULL check
                        query = query.filter(getattr(self.model_class, field).is_(None))
                    else:
                        # Handle equality
                        query = query.filter(getattr(self.model_class, field) == value)
        
        return query
    
    # Abstract Methods (to be implemented by subclasses)
    
    @abstractmethod
    def search(self, query: str, fields: Optional[List[str]] = None) -> List[T]:
        """
        Search entities by text query.
        
        Args:
            query: Search query string
            fields: Fields to search in (None for default fields)
            
        Returns:
            List of matching entities
        """
        pass