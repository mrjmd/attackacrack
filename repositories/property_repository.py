"""PropertyRepository - Repository pattern implementation for Property entity

This module implements the Repository pattern for Property entities,
providing a clean abstraction layer over database operations.

Follows the existing repository patterns established in the codebase.
"""

from typing import List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError

from crm_database import Property, Job
from repositories.base_repository import BaseRepository, PaginationParams, PaginatedResult
import logging

logger = logging.getLogger(__name__)


class PropertyRepository(BaseRepository[Property]):
    """Repository for Property entity operations
    
    Provides specialized methods for property management including:
    - Standard CRUD operations
    - Property search and filtering
    - Contact association queries
    - Business logic operations (properties with jobs, type counts)
    """

    def __init__(self, session: Session):
        """Initialize PropertyRepository with database session
        
        Args:
            session: SQLAlchemy database session
        """
        super().__init__(session, Property)
    
    def create(self, **kwargs) -> Property:
        """Create a new property with validation
        
        Args:
            **kwargs: Property attributes including address, contact_id, property_type
            
        Returns:
            Created Property instance
            
        Raises:
            ValueError: If required fields are missing
            SQLAlchemyError: If database operation fails
        """
        # Validate required fields
        if not kwargs.get('contact_id'):
            raise ValueError("contact_id is required")
        
        if not kwargs.get('address'):
            raise ValueError("address is required")
        
        try:
            property_instance = Property(**kwargs)
            self.session.add(property_instance)
            self.session.commit()
            self.session.refresh(property_instance)
            
            logger.info(f"Created property {property_instance.id} at {property_instance.address}")
            return property_instance
            
        except SQLAlchemyError as e:
            self.session.rollback()
            logger.error(f"Failed to create property: {str(e)}")
            raise
    
    def get_all(self) -> List[Property]:
        """Get all properties
        
        Returns:
            List of all Property instances
        """
        return self.session.query(Property).all()
    
    def find_by_contact_id(self, contact_id: int) -> List[Property]:
        """Find all properties belonging to a specific contact
        
        Args:
            contact_id: ID of the contact
            
        Returns:
            List of Property instances for the contact
        """
        return self.session.query(Property).filter_by(contact_id=contact_id).all()
    
    def find_by_address_contains(self, address_part: str) -> List[Property]:
        """Find properties with addresses containing the given text
        
        Args:
            address_part: Part of the address to search for
            
        Returns:
            List of Property instances with matching addresses
        """
        return self.session.query(Property).filter(
            Property.address.ilike(f'%{address_part}%')
        ).all()
    
    def find_by_type(self, property_type: str) -> List[Property]:
        """Find properties by property type
        
        Args:
            property_type: Type of property (e.g., 'residential', 'commercial')
            
        Returns:
            List of Property instances of the specified type
        """
        return self.session.query(Property).filter_by(property_type=property_type).all()
    
    def get_properties_with_jobs(self) -> List[Property]:
        """Get all properties that have associated jobs
        
        Returns:
            List of Property instances that have at least one job
        """
        return self.session.query(Property).join(Job).distinct().all()
    
    def count_by_property_type(self) -> List[Tuple[str, int]]:
        """Count properties grouped by property type
        
        Returns:
            List of tuples (property_type, count)
        """
        return self.session.query(
            Property.property_type,
            func.count(Property.id)
        ).group_by(Property.property_type).all()
    
    def search_properties(self, address_query: Optional[str] = None, 
                         property_type: Optional[str] = None) -> List[Property]:
        """Search properties with multiple criteria
        
        Args:
            address_query: Part of address to search for (optional)
            property_type: Property type to filter by (optional)
            
        Returns:
            List of Property instances matching the criteria
        """
        query = self.session.query(Property)
        
        if address_query:
            query = query.filter(Property.address.ilike(f'%{address_query}%'))
        
        if property_type:
            query = query.filter_by(property_type=property_type)
        
        return query.all()
    
    def get_paginated(self, pagination: PaginationParams) -> PaginatedResult[Property]:
        """Get paginated list of properties
        
        Args:
            pagination: Pagination parameters
            
        Returns:
            PaginatedResult containing properties and pagination info
        """
        query = self.session.query(Property)
        
        total = query.count()
        properties = query.offset(pagination.offset).limit(pagination.limit).all()
        
        return PaginatedResult(
            items=properties,
            total=total,
            page=pagination.page,
            per_page=pagination.per_page
        )
    
    def update(self, property_instance: Property, **updates) -> Property:
        """Update a property with new values
        
        Args:
            property_instance: Property instance to update
            **updates: Fields to update
            
        Returns:
            Updated Property instance
            
        Raises:
            SQLAlchemyError: If database operation fails
        """
        try:
            for key, value in updates.items():
                setattr(property_instance, key, value)
            
            self.session.commit()
            logger.info(f"Updated property {property_instance.id}")
            return property_instance
            
        except SQLAlchemyError as e:
            self.session.rollback()
            logger.error(f"Failed to update property {property_instance.id}: {str(e)}")
            raise
    
    def update_by_id(self, property_id: int, **updates) -> Optional[Property]:
        """Update a property by ID
        
        Args:
            property_id: ID of property to update
            **updates: Fields to update
            
        Returns:
            Updated Property instance or None if not found
        """
        property_instance = self.get_by_id(property_id)
        if property_instance:
            return self.update(property_instance, **updates)
        return None
    
    def delete(self, property_instance: Property) -> bool:
        """Delete a property
        
        Args:
            property_instance: Property instance to delete
            
        Returns:
            True if deletion successful
            
        Raises:
            SQLAlchemyError: If database operation fails
        """
        try:
            self.session.delete(property_instance)
            self.session.commit()
            logger.info(f"Deleted property {property_instance.id}")
            return True
            
        except SQLAlchemyError as e:
            self.session.rollback()
            logger.error(f"Failed to delete property {property_instance.id}: {str(e)}")
            raise
    
    def delete_by_id(self, property_id: int) -> bool:
        """Delete a property by ID
        
        Args:
            property_id: ID of property to delete
            
        Returns:
            True if deletion successful, False if property not found
        """
        property_instance = self.get_by_id(property_id)
        if property_instance:
            return self.delete(property_instance)
        return False
    
    def search(self, query: str, fields: Optional[List[str]] = None) -> List[Property]:
        """Search properties by text query
        
        Args:
            query: Text to search for
            fields: List of fields to search in (defaults to ['address', 'property_type'])
            
        Returns:
            List of Property instances matching the search query
        """
        if not fields:
            fields = ['address', 'property_type']
        
        db_query = self.session.query(Property)
        
        # Build search conditions for each field
        conditions = []
        for field in fields:
            if hasattr(Property, field):
                field_attr = getattr(Property, field)
                conditions.append(field_attr.ilike(f'%{query}%'))
        
        if conditions:
            from sqlalchemy import or_
            db_query = db_query.filter(or_(*conditions))
        
        return db_query.all()
