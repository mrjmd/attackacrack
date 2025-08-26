"""PropertyRepository - Repository pattern implementation for Property entity

This module implements the Repository pattern for Property entities,
providing a clean abstraction layer over database operations.

Follows the existing repository patterns established in the codebase.
"""

from typing import List, Optional, Tuple, Dict, Any
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, and_, or_
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from sqlalchemy.dialects.postgresql import insert
from datetime import datetime

from crm_database import Property, Job, Contact, PropertyContact, db
from repositories.base_repository import BaseRepository, PaginationParams, PaginatedResult
from services.common.result import Result
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
            **kwargs: Property attributes including address, property_type
            
        Returns:
            Created Property instance
            
        Raises:
            ValueError: If required fields are missing
            SQLAlchemyError: If database operation fails
        """
        # Address is required for properties
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
    
    # ====== BULK OPERATIONS FOR PROPERTYRADAR IMPORTS ======
    
    def bulk_create_properties(self, properties_data: List[Dict[str, Any]]) -> Result[int]:
        """Bulk create properties for large PropertyRadar imports.
        
        Args:
            properties_data: List of property dictionaries
            
        Returns:
            Result with number of properties created or error
        """
        try:
            if not properties_data:
                return Result.success(0)
            
            logger.info(f"Bulk creating {len(properties_data)} properties")
            
            # Use bulk_insert_mappings for optimal performance
            self.session.bulk_insert_mappings(Property, properties_data)
            self.session.flush()
            
            created_count = len(properties_data)
            logger.info(f"Successfully bulk created {created_count} properties")
            
            return Result.success(
                created_count,
                metadata={'operation': 'bulk_create', 'count': created_count}
            )
            
        except IntegrityError as e:
            self.session.rollback()
            logger.error(f"Integrity error during bulk create: {str(e)}")
            return Result.failure(
                f"Duplicate properties found: {str(e)}",
                code="INTEGRITY_ERROR"
            )
        except SQLAlchemyError as e:
            self.session.rollback()
            logger.error(f"Database error during bulk create: {str(e)}")
            return Result.failure(
                f"Failed to bulk create properties: {str(e)}",
                code="DATABASE_ERROR"
            )
    
    def bulk_update_properties(self, properties_data: List[Dict[str, Any]]) -> Result[int]:
        """Bulk update properties.
        
        Args:
            properties_data: List of property dictionaries with 'id' field
            
        Returns:
            Result with number of properties updated or error
        """
        try:
            if not properties_data:
                return Result.success(0)
            
            # Ensure all records have an ID
            for prop in properties_data:
                if 'id' not in prop:
                    return Result.failure(
                        "All properties must have an 'id' field for bulk update",
                        code="MISSING_ID"
                    )
            
            logger.info(f"Bulk updating {len(properties_data)} properties")
            
            # Use bulk_update_mappings for optimal performance
            self.session.bulk_update_mappings(Property, properties_data)
            self.session.flush()
            
            updated_count = len(properties_data)
            logger.info(f"Successfully bulk updated {updated_count} properties")
            
            return Result.success(
                updated_count,
                metadata={'operation': 'bulk_update', 'count': updated_count}
            )
            
        except SQLAlchemyError as e:
            self.session.rollback()
            logger.error(f"Database error during bulk update: {str(e)}")
            return Result.failure(
                f"Failed to bulk update properties: {str(e)}",
                code="DATABASE_ERROR"
            )
    
    def batch_upsert(self, properties_data: List[Dict[str, Any]], batch_size: int = 1000) -> Result[Dict[str, int]]:
        """Batch upsert properties (insert or update) in chunks.
        
        Uses APN as unique identifier for upsert logic.
        
        Args:
            properties_data: List of property dictionaries
            batch_size: Size of each batch (default 1000)
            
        Returns:
            Result with counts of inserted and updated records
        """
        try:
            total_inserted = 0
            total_updated = 0
            
            logger.info(f"Starting batch upsert of {len(properties_data)} properties in batches of {batch_size}")
            
            # Process in batches
            for i in range(0, len(properties_data), batch_size):
                batch = properties_data[i:i + batch_size]
                logger.debug(f"Processing batch {i // batch_size + 1}, records {i} to {i + len(batch)}")
                
                # Separate into insert and update based on APN
                to_insert = []
                to_update = []
                
                # Get APNs from batch
                apns = [prop.get('apn') for prop in batch if prop.get('apn')]
                
                # Find existing properties by APN
                if apns:
                    existing_props = self.session.query(Property.apn, Property.id).filter(
                        Property.apn.in_(apns)
                    ).all()
                    existing_apns = {prop.apn: prop.id for prop in existing_props}
                else:
                    existing_apns = {}
                
                # Categorize properties
                for prop in batch:
                    if prop.get('apn') and prop['apn'] in existing_apns:
                        # Update existing property
                        prop['id'] = existing_apns[prop['apn']]
                        prop['updated_at'] = datetime.utcnow()
                        to_update.append(prop)
                    else:
                        # Insert new property
                        prop['created_at'] = datetime.utcnow()
                        to_insert.append(prop)
                
                # Perform bulk operations
                if to_insert:
                    self.session.bulk_insert_mappings(Property, to_insert)
                    total_inserted += len(to_insert)
                    logger.debug(f"Inserted {len(to_insert)} new properties in batch")
                
                if to_update:
                    self.session.bulk_update_mappings(Property, to_update)
                    total_updated += len(to_update)
                    logger.debug(f"Updated {len(to_update)} existing properties in batch")
                
                # Flush after each batch to avoid memory issues
                self.session.flush()
            
            logger.info(f"Batch upsert complete: {total_inserted} inserted, {total_updated} updated")
            
            return Result.success(
                {'inserted': total_inserted, 'updated': total_updated},
                metadata={
                    'operation': 'batch_upsert',
                    'batch_size': batch_size,
                    'total_processed': total_inserted + total_updated
                }
            )
            
        except SQLAlchemyError as e:
            self.session.rollback()
            logger.error(f"Database error during batch upsert: {str(e)}")
            return Result.failure(
                f"Failed to batch upsert properties: {str(e)}",
                code="DATABASE_ERROR",
                metadata={'inserted_before_error': total_inserted, 'updated_before_error': total_updated}
            )
    
    # ====== SEARCH AND DUPLICATE DETECTION ======
    
    def find_by_address_and_zip(self, address: str, zip_code: str) -> Optional[Property]:
        """Find property by address and zip code.
        
        Args:
            address: Property address
            zip_code: Zip code
            
        Returns:
            Property instance or None if not found
        """
        return self.session.query(Property).filter(
            and_(
                func.lower(Property.address) == func.lower(address),
                Property.zip_code == zip_code
            )
        ).first()
    
    def find_by_apn(self, apn: str) -> Optional[Property]:
        """Find property by Assessor Parcel Number.
        
        Args:
            apn: Assessor Parcel Number
            
        Returns:
            Property instance or None if not found
        """
        return self.session.query(Property).filter_by(apn=apn).first()
    
    def find_duplicates_in_batch(self, properties_data: List[Dict[str, Any]]) -> Dict[str, Property]:
        """Find existing properties that would be duplicates in a batch.
        
        Uses APN as primary duplicate identifier, falls back to address+zip.
        
        Args:
            properties_data: List of property dictionaries to check
            
        Returns:
            Dictionary mapping unique identifier to existing Property
        """
        duplicates = {}
        
        # Check by APN first (most reliable)
        apns = [prop.get('apn') for prop in properties_data if prop.get('apn')]
        if apns:
            existing_by_apn = self.session.query(Property).filter(
                Property.apn.in_(apns)
            ).all()
            for prop in existing_by_apn:
                duplicates[f"apn:{prop.apn}"] = prop
        
        # Check by address+zip for properties without APN
        address_zip_pairs = [
            (prop.get('address'), prop.get('zip_code'))
            for prop in properties_data
            if not prop.get('apn') and prop.get('address') and prop.get('zip_code')
        ]
        
        if address_zip_pairs:
            # Build OR conditions for all address+zip pairs
            conditions = [
                and_(
                    func.lower(Property.address) == func.lower(addr),
                    Property.zip_code == zip_code
                )
                for addr, zip_code in address_zip_pairs
            ]
            
            existing_by_address = self.session.query(Property).filter(
                or_(*conditions)
            ).all()
            
            for prop in existing_by_address:
                key = f"address:{prop.address.lower()}:{prop.zip_code}"
                duplicates[key] = prop
        
        return duplicates
    
    # ====== ASSOCIATION MANAGEMENT ======
    
    def associate_contact_by_ids(self, property_id: int, contact_id: int, 
                         relationship_type: str = 'owner', 
                         is_primary: bool = False,
                         ownership_percentage: Optional[float] = None) -> Result[PropertyContact]:
        """Associate a contact with a property.
        
        Args:
            property_id: Property ID
            contact_id: Contact ID
            relationship_type: Type of relationship (owner, tenant, agent, etc.)
            is_primary: Whether this is the primary contact
            ownership_percentage: Percentage ownership (for fractional ownership)
            
        Returns:
            Result with PropertyContact association or error
        """
        try:
            # Check if association already exists
            existing = self.session.query(PropertyContact).filter_by(
                property_id=property_id,
                contact_id=contact_id
            ).first()
            
            if existing:
                # Update existing association
                existing.relationship_type = relationship_type
                existing.is_primary = is_primary
                if ownership_percentage is not None:
                    existing.ownership_percentage = ownership_percentage
                existing.updated_at = datetime.utcnow()
                self.session.flush()
                
                logger.info(f"Updated property-contact association: property={property_id}, contact={contact_id}")
                return Result.success(existing, metadata={'operation': 'updated'})
            
            # Create new association
            association = PropertyContact(
                property_id=property_id,
                contact_id=contact_id,
                relationship_type=relationship_type,
                is_primary=is_primary,
                ownership_percentage=ownership_percentage
            )
            
            # If marking as primary, unmark other primary contacts
            if is_primary:
                self.session.query(PropertyContact).filter(
                    PropertyContact.property_id == property_id,
                    PropertyContact.id != association.id
                ).update({'is_primary': False})
            
            self.session.add(association)
            self.session.flush()
            
            logger.info(f"Created property-contact association: property={property_id}, contact={contact_id}")
            return Result.success(association, metadata={'operation': 'created'})
            
        except IntegrityError as e:
            self.session.rollback()
            logger.error(f"Integrity error creating association: {str(e)}")
            return Result.failure(
                "Property or contact does not exist",
                code="INTEGRITY_ERROR"
            )
        except SQLAlchemyError as e:
            self.session.rollback()
            logger.error(f"Database error creating association: {str(e)}")
            return Result.failure(
                f"Failed to create association: {str(e)}",
                code="DATABASE_ERROR"
            )
    
    def get_property_contacts(self, property_id: int) -> List[Contact]:
        """Get all contacts associated with a property.
        
        Args:
            property_id: Property ID
            
        Returns:
            List of Contact instances
        """
        return self.session.query(Contact).join(PropertyContact).filter(
            PropertyContact.property_id == property_id
        ).all()
    
    def get_contact_properties(self, contact_id: int) -> List[Property]:
        """Get all properties associated with a contact.
        
        Args:
            contact_id: Contact ID
            
        Returns:
            List of Property instances
        """
        return self.session.query(Property).join(PropertyContact).filter(
            PropertyContact.contact_id == contact_id
        ).all()
    
    # ====== PROPERTYRADAR SPECIFIC QUERIES ======
    
    def find_high_equity_properties(self, min_equity: float = 100000) -> List[Property]:
        """Find properties with high equity.
        
        Args:
            min_equity: Minimum equity amount (default $100,000)
            
        Returns:
            List of Property instances with equity >= min_equity
        """
        return self.session.query(Property).filter(
            Property.estimated_equity >= min_equity
        ).order_by(Property.estimated_equity.desc()).all()
    
    def find_by_city_and_equity(self, city: str, min_equity: float) -> List[Property]:
        """Find properties in a city with minimum equity.
        
        Args:
            city: City name
            min_equity: Minimum equity amount
            
        Returns:
            List of Property instances matching criteria
        """
        return self.session.query(Property).filter(
            and_(
                func.lower(Property.city) == func.lower(city),
                Property.estimated_equity >= min_equity
            )
        ).order_by(Property.estimated_equity.desc()).all()
    
    def update_property_from_radar_data(self, property_id: int, radar_data: Dict[str, Any]) -> Result[Property]:
        """Update property with latest PropertyRadar data.
        
        Args:
            property_id: Property ID to update
            radar_data: Dictionary of PropertyRadar data
            
        Returns:
            Result with updated Property or error
        """
        try:
            property_instance = self.get_by_id(property_id)
            if not property_instance:
                return Result.failure(
                    f"Property with ID {property_id} not found",
                    code="NOT_FOUND"
                )
            
            # Map PropertyRadar fields to our model
            field_mapping = {
                'estimated_value': 'estimated_value',
                'estimated_equity': 'estimated_equity',
                'ltv': 'loan_to_value',
                'last_sale_date': 'last_sale_date',
                'last_sale_amount': 'last_sale_amount',
                'owner_occupied': 'owner_occupied',
                'year_built': 'year_built',
                'bedrooms': 'bedrooms',
                'bathrooms': 'bathrooms',
                'square_feet': 'square_feet',
                'lot_size': 'lot_size_sqft',
                'property_use': 'property_use',
                'zoning': 'zoning'
            }
            
            # Update fields
            updates_made = {}
            for radar_field, model_field in field_mapping.items():
                if radar_field in radar_data and hasattr(property_instance, model_field):
                    old_value = getattr(property_instance, model_field)
                    new_value = radar_data[radar_field]
                    if old_value != new_value:
                        setattr(property_instance, model_field, new_value)
                        updates_made[model_field] = {'old': old_value, 'new': new_value}
            
            # Update metadata
            property_instance.radar_last_updated = datetime.utcnow()
            
            self.session.flush()
            
            logger.info(f"Updated property {property_id} with PropertyRadar data: {len(updates_made)} fields changed")
            
            return Result.success(
                property_instance,
                metadata={
                    'fields_updated': len(updates_made),
                    'changes': updates_made
                }
            )
            
        except SQLAlchemyError as e:
            self.session.rollback()
            logger.error(f"Database error updating property from radar data: {str(e)}")
            return Result.failure(
                f"Failed to update property: {str(e)}",
                code="DATABASE_ERROR"
            )
    
    def find_duplicate(self, address: Optional[str], zip_code: Optional[str]) -> Optional[Property]:
        """Find duplicate property by address and zip code.
        
        Args:
            address: Property address
            zip_code: Property zip code
            
        Returns:
            Property instance if duplicate found, None otherwise
        """
        if not address or not zip_code:
            return None
            
        return self.find_by_address_and_zip(address, zip_code)
    
    def associate_contact(self, property_obj: Property, contact: Contact, 
                         relationship_type: str = 'owner') -> Result[PropertyContact]:
        """Associate a contact with a property object.
        
        Convenience method that accepts property and contact objects.
        
        Args:
            property_obj: Property instance
            contact: Contact instance
            relationship_type: Type of relationship
            
        Returns:
            Result with PropertyContact association or error
        """
        is_primary = relationship_type == 'PRIMARY'
        # Map PRIMARY/SECONDARY to owner for database storage
        if relationship_type in ['PRIMARY', 'SECONDARY']:
            db_relationship_type = 'owner'
        else:
            db_relationship_type = relationship_type
            
        return self.associate_contact_by_ids(
            property_id=property_obj.id,
            contact_id=contact.id,
            relationship_type=db_relationship_type,
            is_primary=is_primary
        )
