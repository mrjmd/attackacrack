"""PropertyService - Business logic for property management using Repository Pattern

Refactored to use PropertyRepository instead of direct database access.
Follows dependency injection and clean architecture principles.
"""

from typing import List, Optional
from sqlalchemy.exc import SQLAlchemyError

from crm_database import Property
from repositories.property_repository import PropertyRepository
from services.common.result import Result
import logging

logger = logging.getLogger(__name__)


class PropertyService:
    """Service layer for property management operations
    
    Provides business logic for property operations while delegating
    data access to PropertyRepository. Includes error handling and
    result patterns for robust operation.
    """

    def __init__(self, repository: PropertyRepository):
        """Initialize PropertyService with repository dependency
        
        Args:
            repository: PropertyRepository instance for data access
        """
        self.repository = repository
        logger.info("PropertyService initialized with repository pattern")

    # ============================================
    # CREATE OPERATIONS
    # ============================================

    def add_property(self, **kwargs) -> Property:
        """Add a new property
        
        Args:
            **kwargs: Property attributes including address, contact_id, property_type
            
        Returns:
            Created Property instance
            
        Raises:
            ValueError: If required fields are missing
            SQLAlchemyError: If database operation fails
        """
        logger.info(f"Adding new property at {kwargs.get('address', 'unknown address')}")
        return self.repository.create(**kwargs)
    
    def add_property_safe(self, **kwargs) -> Result[Property]:
        """Safely add a new property with error handling
        
        Args:
            **kwargs: Property attributes
            
        Returns:
            Result object containing either success data or error
        """
        try:
            property_instance = self.add_property(**kwargs)
            logger.info(f"Successfully added property {property_instance.id}")
            return Result.success(property_instance)
        except (ValueError, SQLAlchemyError) as e:
            logger.error(f"Failed to add property: {str(e)}")
            return Result.failure(str(e))

    # ============================================
    # READ OPERATIONS
    # ============================================

    def get_all_properties(self) -> List[Property]:
        """Get all properties
        
        Returns:
            List of all Property instances
        """
        logger.info("Retrieving all properties")
        return self.repository.get_all()

    def get_property_by_id(self, property_id: int) -> Optional[Property]:
        """Get property by ID
        
        Args:
            property_id: ID of the property to retrieve
            
        Returns:
            Property instance if found, None otherwise
        """
        logger.info(f"Retrieving property with ID {property_id}")
        return self.repository.get_by_id(property_id)
    
    def get_properties_by_contact(self, contact_id: int) -> List[Property]:
        """Get all properties for a specific contact
        
        Args:
            contact_id: ID of the contact
            
        Returns:
            List of Property instances for the contact
        """
        logger.info(f"Retrieving properties for contact {contact_id}")
        return self.repository.find_by_contact_id(contact_id)
    
    def search_properties_by_address(self, address_query: str) -> List[Property]:
        """Search properties by address
        
        Args:
            address_query: Part of the address to search for
            
        Returns:
            List of Property instances with matching addresses
        """
        logger.info(f"Searching properties by address: {address_query}")
        return self.repository.find_by_address_contains(address_query)
    
    def get_properties_by_type(self, property_type: str) -> List[Property]:
        """Get properties by type
        
        Args:
            property_type: Type of property to filter by
            
        Returns:
            List of Property instances of the specified type
        """
        logger.info(f"Retrieving properties of type: {property_type}")
        return self.repository.find_by_type(property_type)

    # ============================================
    # UPDATE OPERATIONS
    # ============================================

    def update_property(self, property_obj: Property, **kwargs) -> Property:
        """Update an existing property
        
        Args:
            property_obj: Property instance to update
            **kwargs: Fields to update
            
        Returns:
            Updated Property instance
            
        Raises:
            SQLAlchemyError: If database operation fails
        """
        logger.info(f"Updating property {property_obj.id}")
        return self.repository.update(property_obj, **kwargs)
    
    def update_property_by_id(self, property_id: int, **kwargs) -> Optional[Property]:
        """Update property by ID
        
        Args:
            property_id: ID of property to update
            **kwargs: Fields to update
            
        Returns:
            Updated Property instance or None if not found
        """
        logger.info(f"Updating property {property_id} by ID")
        return self.repository.update_by_id(property_id, **kwargs)

    # ============================================
    # DELETE OPERATIONS
    # ============================================

    def delete_property(self, property_obj: Property) -> bool:
        """Delete a property
        
        Args:
            property_obj: Property instance to delete
            
        Returns:
            True if deletion successful
            
        Raises:
            SQLAlchemyError: If database operation fails
        """
        logger.info(f"Deleting property {property_obj.id}")
        return self.repository.delete(property_obj)
    
    def delete_property_by_id(self, property_id: int) -> bool:
        """Delete property by ID
        
        Args:
            property_id: ID of property to delete
            
        Returns:
            True if deletion successful, False if property not found
        """
        logger.info(f"Deleting property {property_id} by ID")
        return self.repository.delete_by_id(property_id)

    # ============================================
    # BUSINESS LOGIC OPERATIONS
    # ============================================

    def get_properties_with_jobs(self) -> List[Property]:
        """Get properties that have associated jobs
        
        Returns:
            List of Property instances that have at least one job
        """
        logger.info("Retrieving properties with jobs")
        return self.repository.get_properties_with_jobs()
    
    def get_property_statistics(self) -> List[tuple]:
        """Get property statistics grouped by type
        
        Returns:
            List of tuples (property_type, count)
        """
        logger.info("Retrieving property statistics")
        return self.repository.count_by_property_type()
    
    def search_properties(self, **search_params) -> List[Property]:
        """Advanced property search with multiple criteria
        
        Args:
            **search_params: Search criteria (address_query, property_type, etc.)
            
        Returns:
            List of Property instances matching the criteria
        """
        logger.info(f"Advanced property search with params: {search_params}")
        return self.repository.search_properties(**search_params)
