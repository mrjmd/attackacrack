"""
ContactCSVImportRepository - Data access layer for ContactCSVImport entities
Isolates all database queries related to contact-CSV import associations
"""

from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
from sqlalchemy import or_, and_, func, desc, asc
from sqlalchemy.orm import Query
from sqlalchemy.exc import SQLAlchemyError
from repositories.base_repository import BaseRepository
from crm_database import ContactCSVImport, Contact, CSVImport
import logging

logger = logging.getLogger(__name__)


class ContactCSVImportRepository(BaseRepository[ContactCSVImport]):
    """Repository for ContactCSVImport association data access"""
    
    def __init__(self, session):
        """Initialize repository with database session"""
        super().__init__(session, ContactCSVImport)
    
    def search(self, query: str, fields: Optional[List[str]] = None, limit: Optional[int] = None) -> List[ContactCSVImport]:
        """
        Search contact-CSV import associations by contact information.
        
        Args:
            query: Search query string
            fields: Specific contact fields to search (default: first_name, last_name)
            limit: Maximum number of results to return
            
        Returns:
            List of matching contact-CSV import associations
        """
        if not query:
            return []
        
        try:
            search_fields = fields or ['first_name', 'last_name']
            
            # Build conditions for contact fields
            conditions = []
            for field in search_fields:
                if hasattr(Contact, field):
                    conditions.append(getattr(Contact, field).ilike(f'%{query}%'))
            
            if not conditions:
                return []
            
            query_obj = self.session.query(ContactCSVImport).join(Contact).filter(
                or_(*conditions)
            )
            
            if limit:
                query_obj = query_obj.limit(limit)
                
            return query_obj.all()
        except SQLAlchemyError as e:
            logger.error(f"Error searching contact CSV import associations: {e}")
            return []
    
    def find_by_contact_id(self, contact_id: int) -> List[ContactCSVImport]:
        """
        Find associations by contact ID.
        
        Args:
            contact_id: Contact ID
            
        Returns:
            List of associations for the contact
        """
        return self.find_by(contact_id=contact_id)
    
    def find_by_csv_import_id(self, csv_import_id: int) -> List[ContactCSVImport]:
        """
        Find associations by CSV import ID.
        
        Args:
            csv_import_id: CSV import ID
            
        Returns:
            List of associations for the import
        """
        return self.find_by(csv_import_id=csv_import_id)
    
    def find_by_contact_and_import(self, contact_id: int, csv_import_id: int) -> Optional[ContactCSVImport]:
        """
        Find specific association by contact and import IDs.
        
        Args:
            contact_id: Contact ID
            csv_import_id: CSV import ID
            
        Returns:
            Contact-CSV import association or None
        """
        return self.find_one_by(contact_id=contact_id, csv_import_id=csv_import_id)
    
    def exists_for_contact_and_import(self, contact_id: int, csv_import_id: int) -> bool:
        """
        Check if association exists for contact and import.
        
        Args:
            contact_id: Contact ID
            csv_import_id: CSV import ID
            
        Returns:
            True if association exists, False otherwise
        """
        return self.exists(contact_id=contact_id, csv_import_id=csv_import_id)
    
    def get_new_contacts_for_import(self, csv_import_id: int) -> List[ContactCSVImport]:
        """
        Get associations for new contacts created during import.
        
        Args:
            csv_import_id: CSV import ID
            
        Returns:
            List of associations for new contacts
        """
        try:
            return self.session.query(ContactCSVImport).filter(
                and_(
                    ContactCSVImport.csv_import_id == csv_import_id,
                    ContactCSVImport.is_new == True
                )
            ).all()
        except SQLAlchemyError as e:
            logger.error(f"Error getting new contacts for import: {e}")
            return []
    
    def get_updated_contacts_for_import(self, csv_import_id: int) -> List[ContactCSVImport]:
        """
        Get associations for existing contacts updated during import.
        
        Args:
            csv_import_id: CSV import ID
            
        Returns:
            List of associations for updated existing contacts
        """
        try:
            return self.session.query(ContactCSVImport).filter(
                and_(
                    ContactCSVImport.csv_import_id == csv_import_id,
                    ContactCSVImport.is_new == False
                )
            ).all()
        except SQLAlchemyError as e:
            logger.error(f"Error getting updated contacts for import: {e}")
            return []
    
    def get_contacts_with_updated_data(self, csv_import_id: int) -> List[ContactCSVImport]:
        """
        Get associations where contact data was actually updated.
        
        Args:
            csv_import_id: CSV import ID
            
        Returns:
            List of associations with data updates
        """
        try:
            return self.session.query(ContactCSVImport).filter(
                and_(
                    ContactCSVImport.csv_import_id == csv_import_id,
                    ContactCSVImport.data_updated.isnot(None)
                )
            ).all()
        except SQLAlchemyError as e:
            logger.error(f"Error getting contacts with updated data: {e}")
            return []
    
    def get_import_statistics(self, csv_import_id: int) -> Dict[str, int]:
        """
        Get statistics for a specific import.
        
        Args:
            csv_import_id: CSV import ID
            
        Returns:
            Dictionary with import statistics
        """
        try:
            stats = self.session.query(
                ContactCSVImport.is_new,
                func.count(ContactCSVImport.id).label('count')
            ).filter_by(
                csv_import_id=csv_import_id
            ).group_by(ContactCSVImport.is_new).all()
            
            result = {
                'new_contacts': 0,
                'updated_contacts': 0,
                'total_associations': 0
            }
            
            for is_new, count in stats:
                if is_new:
                    result['new_contacts'] = count
                else:
                    result['updated_contacts'] = count
                result['total_associations'] += count
            
            return result
        except SQLAlchemyError as e:
            logger.error(f"Error getting import statistics: {e}")
            return {'new_contacts': 0, 'updated_contacts': 0, 'total_associations': 0}
    
    def get_contacts_by_import_with_details(self, csv_import_id: int) -> List[Tuple[Contact, ContactCSVImport]]:
        """
        Get contacts with full association details for an import.
        
        Args:
            csv_import_id: CSV import ID
            
        Returns:
            List of (contact, association) tuples
        """
        try:
            return self.session.query(Contact, ContactCSVImport).join(
                Contact, ContactCSVImport.contact_id == Contact.id
            ).filter_by(
                csv_import_id=csv_import_id
            ).all()
        except SQLAlchemyError as e:
            logger.error(f"Error getting contacts by import with details: {e}")
            return []
    
    def bulk_create_associations(self, associations_data: List[Dict[str, Any]]) -> List[ContactCSVImport]:
        """
        Bulk create contact-import associations.
        
        Args:
            associations_data: List of association data dictionaries
            
        Returns:
            List of created associations
        """
        return self.create_many(associations_data)
    
    def delete_associations_for_import(self, csv_import_id: int) -> int:
        """
        Delete all associations for a specific import.
        
        Args:
            csv_import_id: CSV import ID
            
        Returns:
            Number of associations deleted
        """
        return self.delete_many({'csv_import_id': csv_import_id})
    
    def delete_associations_for_contact(self, contact_id: int) -> int:
        """
        Delete all associations for a specific contact.
        
        Args:
            contact_id: Contact ID
            
        Returns:
            Number of associations deleted
        """
        return self.delete_many({'contact_id': contact_id})
    
    def get_recent_associations(self, limit: int = 10) -> List[ContactCSVImport]:
        """
        Get recently created associations.
        
        Args:
            limit: Maximum number of associations to return
            
        Returns:
            List of recent associations
        """
        try:
            return self.session.query(ContactCSVImport).order_by(
                desc(ContactCSVImport.created_at)
            ).limit(limit).all()
        except SQLAlchemyError as e:
            logger.error(f"Error getting recent associations: {e}")
            return []
    
    def get_associations_by_date_range(self, start_date: datetime, end_date: datetime) -> List[ContactCSVImport]:
        """
        Get associations within a date range.
        
        Args:
            start_date: Start of date range (inclusive)
            end_date: End of date range (inclusive)
            
        Returns:
            List of associations in date range
        """
        try:
            return self.session.query(ContactCSVImport).filter(
                ContactCSVImport.created_at >= start_date
            ).filter(
                ContactCSVImport.created_at <= end_date
            ).all()
        except SQLAlchemyError as e:
            logger.error(f"Error getting associations by date range: {e}")
            return []
    
    def count_associations_for_import(self, csv_import_id: int) -> int:
        """
        Count associations for a specific import.
        
        Args:
            csv_import_id: CSV import ID
            
        Returns:
            Number of associations for the import
        """
        return self.count(csv_import_id=csv_import_id)
    
    def count_associations_for_contact(self, contact_id: int) -> int:
        """
        Count associations for a specific contact.
        
        Args:
            contact_id: Contact ID
            
        Returns:
            Number of associations for the contact
        """
        return self.count(contact_id=contact_id)
    
    def find_contacts_imported_multiple_times(self) -> List[Tuple[int, int]]:
        """
        Find contacts that were imported in multiple CSV files.
        
        Returns:
            List of (contact_id, import_count) tuples
        """
        try:
            return self.session.query(
                ContactCSVImport.contact_id,
                func.count(ContactCSVImport.csv_import_id).label('import_count')
            ).group_by(
                ContactCSVImport.contact_id
            ).having(
                func.count(ContactCSVImport.csv_import_id) > 1
            ).all()
        except SQLAlchemyError as e:
            logger.error(f"Error finding contacts imported multiple times: {e}")
            return []
    
    def get_data_updates_for_contact(self, contact_id: int) -> List[ContactCSVImport]:
        """
        Get all data updates for a specific contact.
        
        Args:
            contact_id: Contact ID
            
        Returns:
            List of associations with data updates for the contact
        """
        try:
            return self.session.query(ContactCSVImport).filter(
                and_(
                    ContactCSVImport.contact_id == contact_id,
                    ContactCSVImport.data_updated.isnot(None)
                )
            ).all()
        except SQLAlchemyError as e:
            logger.error(f"Error getting data updates for contact: {e}")
            return []
