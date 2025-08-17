"""
ContactService - Refactored with Repository Pattern
Business logic layer for contact management, now using ContactRepository for data access
"""

from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
import csv
import io
from sqlalchemy.orm import Session
from repositories.contact_repository import ContactRepository
from repositories.base_repository import PaginationParams, SortOrder
from crm_database import Contact, ContactFlag, Conversation, Activity, CampaignMembership, Campaign, Property, Job, db
from sqlalchemy.exc import IntegrityError
import logging

logger = logging.getLogger(__name__)


class ContactService:
    """Service for contact business logic with repository pattern"""
    
    def __init__(self, repository: Optional[ContactRepository] = None, session: Optional[Session] = None):
        """
        Initialize with injected repository.
        
        Args:
            repository: ContactRepository instance for data access
            session: Database session (will create repository if not provided)
        """
        self.session = session or db.session
        self.repository = repository or ContactRepository(self.session, Contact)
    
    def get_contacts_page(
        self,
        search_query: str = '',
        filter_type: str = 'all',
        sort_by: str = 'name',
        page: int = 1,
        per_page: int = 50
    ) -> Dict[str, Any]:
        """
        Get paginated contacts with filters and search.
        
        Args:
            search_query: Search text
            filter_type: Filter to apply
            sort_by: Sort field
            page: Page number
            per_page: Items per page
            
        Returns:
            Dictionary with contacts and pagination info
        """
        # Use repository for data access
        pagination = PaginationParams(page=page, per_page=per_page)
        sort_order = SortOrder.DESC if sort_by == 'recent_activity' else SortOrder.ASC
        
        result = self.repository.get_contacts_with_filter(
            filter_type=filter_type,
            search_query=search_query,
            sort_by=sort_by,
            sort_order=sort_order,
            pagination=pagination
        )
        
        # Enhance contacts with metadata
        enhanced_contacts = self._enhance_contacts(result.items)
        
        return {
            'contacts': enhanced_contacts,
            'total_count': result.total,
            'page': result.page,
            'per_page': result.per_page,
            'total_pages': result.pages,
            'has_prev': result.has_prev,
            'has_next': result.has_next
        }
    
    def _enhance_contacts(self, contacts: List[Contact]) -> List[Dict[str, Any]]:
        """
        Add metadata to contacts for display.
        
        Args:
            contacts: List of Contact objects
            
        Returns:
            List of enhanced contact dictionaries
        """
        if not contacts:
            return []
        
        contact_ids = [c.id for c in contacts]
        
        # Get conversation counts
        conversation_counts = {}
        if contact_ids:
            from sqlalchemy import func
            counts = self.session.query(
                Conversation.contact_id,
                func.count(Conversation.id)
            ).filter(
                Conversation.contact_id.in_(contact_ids)
            ).group_by(Conversation.contact_id).all()
            
            conversation_counts = {contact_id: count for contact_id, count in counts}
        
        # Get last activity dates
        last_activities = {}
        if contact_ids:
            activities = self.session.query(
                Conversation.contact_id,
                func.max(Conversation.last_activity_at)
            ).filter(
                Conversation.contact_id.in_(contact_ids)
            ).group_by(Conversation.contact_id).all()
            
            last_activities = {contact_id: last_activity for contact_id, last_activity in activities}
        
        # Get opt-out status
        opted_out_ids = set()
        if contact_ids:
            flags = self.session.query(ContactFlag.contact_id).filter(
                ContactFlag.contact_id.in_(contact_ids),
                ContactFlag.flag_type == 'opted_out'
            ).all()
            opted_out_ids = {flag[0] for flag in flags}
        
        # Build enhanced contact list
        enhanced = []
        for contact in contacts:
            enhanced.append({
                'contact': contact,
                'conversation_count': conversation_counts.get(contact.id, 0),
                'last_activity': last_activities.get(contact.id),
                'is_opted_out': contact.id in opted_out_ids
            })
        
        return enhanced
    
    def get_contact_by_id(self, contact_id: int) -> Optional[Contact]:
        """
        Get contact by ID.
        
        Args:
            contact_id: Contact ID
            
        Returns:
            Contact or None
        """
        return self.repository.get_by_id(contact_id)
    
    def create_contact(self, **contact_data) -> Tuple[bool, Optional[Contact], Optional[str]]:
        """
        Create a new contact.
        
        Args:
            **contact_data: Contact fields
            
        Returns:
            Tuple of (success, contact, error_message)
        """
        try:
            contact = self.repository.create(**contact_data)
            self.repository.commit()
            logger.info(f"Created contact: {contact.id}")
            return True, contact, None
        except IntegrityError as e:
            self.repository.rollback()
            if 'unique constraint' in str(e).lower():
                return False, None, "A contact with this phone number or email already exists"
            return False, None, "Database error creating contact"
        except Exception as e:
            self.repository.rollback()
            logger.error(f"Error creating contact: {e}")
            return False, None, str(e)
    
    def update_contact(self, contact_id: int, **updates) -> Tuple[bool, Optional[Contact], Optional[str]]:
        """
        Update a contact.
        
        Args:
            contact_id: Contact ID
            **updates: Fields to update
            
        Returns:
            Tuple of (success, contact, error_message)
        """
        try:
            contact = self.repository.update_by_id(contact_id, **updates)
            if contact:
                self.repository.commit()
                logger.info(f"Updated contact: {contact_id}")
                return True, contact, None
            else:
                return False, None, "Contact not found"
        except IntegrityError as e:
            self.repository.rollback()
            if 'unique constraint' in str(e).lower():
                return False, None, "A contact with this phone number or email already exists"
            return False, None, "Database error updating contact"
        except Exception as e:
            self.repository.rollback()
            logger.error(f"Error updating contact {contact_id}: {e}")
            return False, None, str(e)
    
    def delete_contact(self, contact_id: int) -> Tuple[bool, Optional[str]]:
        """
        Delete a contact.
        
        Args:
            contact_id: Contact ID
            
        Returns:
            Tuple of (success, error_message)
        """
        try:
            success = self.repository.delete_by_id(contact_id)
            if success:
                self.repository.commit()
                logger.info(f"Deleted contact: {contact_id}")
                return True, None
            else:
                return False, "Contact not found"
        except Exception as e:
            self.repository.rollback()
            logger.error(f"Error deleting contact {contact_id}: {e}")
            return False, str(e)
    
    def search_contacts(self, query: str) -> List[Contact]:
        """
        Search contacts by query.
        
        Args:
            query: Search query
            
        Returns:
            List of matching contacts
        """
        return self.repository.search(query)
    
    def find_or_create_contact(self, phone: str, **additional_data) -> Contact:
        """
        Find existing contact by phone or create new one.
        
        Args:
            phone: Phone number
            **additional_data: Additional contact fields
            
        Returns:
            Contact instance
        """
        # Try to find existing contact
        contact = self.repository.find_by_phone(phone)
        
        if not contact:
            # Create new contact
            contact_data = {'phone': phone}
            contact_data.update(additional_data)
            contact = self.repository.create(**contact_data)
            self.repository.commit()
            logger.info(f"Created new contact with phone: {phone}")
        else:
            # Update existing contact with any new data
            if additional_data:
                # Only update fields that are currently empty
                updates = {}
                for key, value in additional_data.items():
                    if value and not getattr(contact, key, None):
                        updates[key] = value
                
                if updates:
                    self.repository.update(contact, **updates)
                    self.repository.commit()
                    logger.info(f"Updated existing contact {contact.id} with new data")
        
        return contact
    
    def bulk_update_tags(self, contact_ids: List[int], tags: List[str], operation: str = 'add') -> int:
        """
        Bulk update tags for multiple contacts.
        
        Args:
            contact_ids: List of contact IDs
            tags: Tags to add/remove/replace
            operation: 'add', 'remove', or 'replace'
            
        Returns:
            Number of contacts updated
        """
        count = self.repository.bulk_update_tags(contact_ids, tags, operation)
        self.repository.commit()
        logger.info(f"Updated tags for {count} contacts")
        return count
    
    def merge_duplicate_contacts(self, primary_id: int, duplicate_id: int) -> Tuple[bool, Optional[Contact], Optional[str]]:
        """
        Merge duplicate contact into primary contact.
        
        Args:
            primary_id: ID of contact to keep
            duplicate_id: ID of contact to merge and delete
            
        Returns:
            Tuple of (success, merged_contact, error_message)
        """
        try:
            merged = self.repository.merge_contacts(primary_id, duplicate_id)
            if merged:
                self.repository.commit()
                logger.info(f"Merged contact {duplicate_id} into {primary_id}")
                return True, merged, None
            else:
                return False, None, "One or both contacts not found"
        except Exception as e:
            self.repository.rollback()
            logger.error(f"Error merging contacts: {e}")
            return False, None, str(e)
    
    def find_duplicates(self, field: str = 'phone') -> List[Tuple[str, int]]:
        """
        Find duplicate contacts by field.
        
        Args:
            field: Field to check for duplicates
            
        Returns:
            List of (field_value, count) tuples
        """
        return self.repository.find_duplicates(field)
    
    def get_contact_stats(self) -> Dict[str, int]:
        """
        Get statistics about contacts.
        
        Returns:
            Dictionary with contact statistics
        """
        return self.repository.get_contact_stats()
    
    def export_contacts_to_csv(self, contact_ids: Optional[List[int]] = None) -> str:
        """
        Export contacts to CSV format.
        
        Args:
            contact_ids: Optional list of specific contact IDs to export
            
        Returns:
            CSV string
        """
        if contact_ids:
            contacts = [self.repository.get_by_id(cid) for cid in contact_ids]
            contacts = [c for c in contacts if c]  # Filter out None values
        else:
            contacts = self.repository.get_all(order_by='last_name')
        
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=[
            'id', 'first_name', 'last_name', 'phone', 'email', 
            'company', 'address', 'city', 'state', 'zip_code',
            'tags', 'created_at', 'updated_at'
        ])
        
        writer.writeheader()
        for contact in contacts:
            writer.writerow({
                'id': contact.id,
                'first_name': contact.first_name or '',
                'last_name': contact.last_name or '',
                'phone': contact.phone or '',
                'email': contact.email or '',
                'company': contact.company or '',
                'address': contact.address or '',
                'city': contact.city or '',
                'state': contact.state or '',
                'zip_code': contact.zip_code or '',
                'tags': ','.join(contact.tags) if contact.tags else '',
                'created_at': contact.created_at.isoformat() if contact.created_at else '',
                'updated_at': contact.updated_at.isoformat() if contact.updated_at else ''
            })
        
        return output.getvalue()
    
    def import_contacts_from_csv(self, csv_content: str) -> Tuple[int, int, List[str]]:
        """
        Import contacts from CSV content.
        
        Args:
            csv_content: CSV string content
            
        Returns:
            Tuple of (created_count, updated_count, errors)
        """
        created = 0
        updated = 0
        errors = []
        
        reader = csv.DictReader(io.StringIO(csv_content))
        
        for row_num, row in enumerate(reader, start=2):  # Start at 2 (header is row 1)
            try:
                # Clean and validate phone number
                phone = row.get('phone', '').strip()
                if not phone:
                    errors.append(f"Row {row_num}: Missing phone number")
                    continue
                
                # Check if contact exists
                existing = self.repository.find_by_phone(phone)
                
                contact_data = {
                    'first_name': row.get('first_name', '').strip(),
                    'last_name': row.get('last_name', '').strip(),
                    'email': row.get('email', '').strip() or None,
                    'company': row.get('company', '').strip() or None,
                    'address': row.get('address', '').strip() or None,
                    'city': row.get('city', '').strip() or None,
                    'state': row.get('state', '').strip() or None,
                    'zip_code': row.get('zip_code', '').strip() or None
                }
                
                # Handle tags
                tags_str = row.get('tags', '').strip()
                if tags_str:
                    contact_data['tags'] = [t.strip() for t in tags_str.split(',')]
                
                if existing:
                    # Update existing contact
                    self.repository.update(existing, **contact_data)
                    updated += 1
                else:
                    # Create new contact
                    contact_data['phone'] = phone
                    self.repository.create(**contact_data)
                    created += 1
                
            except Exception as e:
                errors.append(f"Row {row_num}: {str(e)}")
        
        # Commit all changes
        if created > 0 or updated > 0:
            self.repository.commit()
        
        return created, updated, errors
    
    def get_contacts_for_campaign(self, filters: Dict[str, Any]) -> List[Contact]:
        """
        Get contacts for a campaign based on filters.
        
        Args:
            filters: Dictionary of filters to apply
            
        Returns:
            List of eligible contacts
        """
        # Start with all contacts
        if filters.get('list_id'):
            # Get contacts from a specific list
            from crm_database import CampaignList, CampaignListMember
            list_members = self.session.query(CampaignListMember.contact_id).filter(
                CampaignListMember.list_id == filters['list_id'],
                CampaignListMember.status == 'active'
            ).subquery()
            
            contacts = self.session.query(Contact).filter(
                Contact.id.in_(list_members)
            ).all()
        else:
            contacts = self.repository.get_all()
        
        # Apply additional filters
        if filters.get('has_phone'):
            contacts = [c for c in contacts if c.phone]
        
        if filters.get('exclude_opted_out'):
            opted_out = self.repository.get_opted_out_contacts()
            opted_out_ids = {c.id for c in opted_out}
            contacts = [c for c in contacts if c.id not in opted_out_ids]
        
        if filters.get('has_conversation'):
            contacts_with_conv = self.repository.get_contacts_with_conversations()
            conv_ids = {c.id for c in contacts_with_conv}
            contacts = [c for c in contacts if c.id in conv_ids]
        
        if filters.get('no_conversation'):
            contacts_without_conv = self.repository.get_contacts_without_conversations()
            no_conv_ids = {c.id for c in contacts_without_conv}
            contacts = [c for c in contacts if c.id in no_conv_ids]
        
        return contacts