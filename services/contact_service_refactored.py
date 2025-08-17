"""
ContactService - Refactored with Result Pattern and Repository
Handles contact management operations using Result pattern for consistent error handling
"""

import csv
import io
import logging
from typing import List, Dict, Optional, Any
from datetime import datetime
from sqlalchemy import or_, and_, func
from sqlalchemy.orm import Session, joinedload

from crm_database import Contact, ContactFlag, Campaign, CampaignMembership, Conversation, Activity, db
from services.common.result import Result, PagedResult
from repositories.contact_repository import ContactRepository

logger = logging.getLogger(__name__)


class ContactService:
    """Service for managing contacts using Result pattern and Repository"""
    
    def __init__(self, contact_repository: Optional[ContactRepository] = None, 
                 session: Optional[Session] = None):
        """
        Initialize with optional repository and session.
        
        Args:
            contact_repository: ContactRepository for data access
            session: Database session
        """
        self.session = session or db.session
        self.contact_repository = contact_repository or ContactRepository(self.session, Contact)
    
    def add_contact(self, first_name: str, last_name: str, 
                   email: Optional[str] = None, 
                   phone: Optional[str] = None,
                   **kwargs) -> Result[Contact]:
        """
        Add a new contact.
        
        Args:
            first_name: Contact's first name
            last_name: Contact's last name
            email: Optional email address
            phone: Optional phone number
            **kwargs: Additional contact fields
            
        Returns:
            Result[Contact]: Success with contact or failure with error
        """
        try:
            # Check for duplicates
            if phone:
                existing = self.contact_repository.find_by_phone(phone)
                if existing:
                    return Result.failure(
                        f"Contact with phone {phone} already exists",
                        code="DUPLICATE_PHONE"
                    )
            
            if email:
                existing = self.contact_repository.find_by_email(email)
                if existing:
                    return Result.failure(
                        f"Contact with email {email} already exists",
                        code="DUPLICATE_EMAIL"
                    )
            
            # Create contact
            contact_data = {
                'first_name': first_name,
                'last_name': last_name,
                'email': email,
                'phone': phone,
                **kwargs
            }
            
            contact = self.contact_repository.create(**contact_data)
            logger.info(f"Created contact: {contact.id} - {contact.full_name}")
            
            return Result.success(contact, metadata={"created_at": datetime.utcnow()})
            
        except Exception as e:
            logger.error(f"Failed to create contact: {str(e)}")
            return Result.failure(f"Failed to create contact: {str(e)}", code="CREATE_ERROR")
    
    def get_contact_by_id(self, contact_id: int) -> Result[Contact]:
        """
        Get contact by ID.
        
        Args:
            contact_id: Contact ID
            
        Returns:
            Result[Contact]: Success with contact or failure
        """
        contact = self.contact_repository.get_by_id(contact_id)
        if contact:
            return Result.success(contact)
        return Result.failure(f"Contact not found: {contact_id}", code="NOT_FOUND")
    
    def get_contact_by_phone(self, phone_number: str) -> Result[Contact]:
        """
        Get contact by phone number.
        
        Args:
            phone_number: Phone number to search
            
        Returns:
            Result[Contact]: Success with contact or failure
        """
        contact = self.contact_repository.find_by_phone(phone_number)
        if contact:
            return Result.success(contact)
        return Result.failure(f"Contact not found with phone: {phone_number}", code="NOT_FOUND")
    
    def get_all_contacts(self, page: int = 1, per_page: int = 100) -> PagedResult[List[Contact]]:
        """
        Get all contacts with pagination.
        
        Args:
            page: Page number
            per_page: Items per page
            
        Returns:
            PagedResult[List[Contact]]: Paginated contacts
        """
        try:
            from repositories.base_repository import PaginationParams
            pagination_params = PaginationParams(page=page, per_page=per_page)
            result = self.contact_repository.get_paginated(pagination_params)
            
            return PagedResult.paginated(
                data=result.items,
                total=result.total,
                page=page,
                per_page=per_page
            )
        except Exception as e:
            logger.error(f"Failed to get contacts: {str(e)}")
            return PagedResult.failure(f"Failed to get contacts: {str(e)}", code="FETCH_ERROR")
    
    def get_contacts_page(
        self,
        search_query: str = '',
        filter_type: str = 'all',
        sort_by: str = 'name',
        page: int = 1,
        per_page: int = 50
    ) -> Dict[str, Any]:
        """
        Get paginated contacts with search and filtering for route layer.
        
        Args:
            search_query: Search query string
            filter_type: Filter type to apply ('all', 'has_email', 'has_phone', etc.)
            sort_by: Field to sort by ('name', 'created', 'recent_activity')
            page: Page number (1-based)
            per_page: Items per page
            
        Returns:
            Dictionary with pagination metadata and contacts
        """
        try:
            return self.contact_repository.get_paginated_contacts(
                search_query=search_query,
                filter_type=filter_type,
                sort_by=sort_by,
                page=page,
                per_page=per_page
            )
        except Exception as e:
            logger.error(f"Failed to get contacts page: {str(e)}")
            # Return empty result on error
            return {
                'contacts': [],
                'total_count': 0,
                'page': page,
                'total_pages': 0,
                'has_prev': False,
                'has_next': False
            }
    
    def search_contacts(self, query: str, limit: int = 20) -> Result[List[Contact]]:
        """
        Search contacts by name, email, or phone.
        
        Args:
            query: Search query
            limit: Maximum results
            
        Returns:
            Result[List[Contact]]: Success with contacts or failure
        """
        try:
            if not query:
                return Result.success([])
            
            # Search in multiple fields
            search_filter = or_(
                Contact.first_name.ilike(f'%{query}%'),
                Contact.last_name.ilike(f'%{query}%'),
                Contact.email.ilike(f'%{query}%'),
                Contact.phone.ilike(f'%{query}%'),
                Contact.company.ilike(f'%{query}%')
            )
            
            contacts = self.session.query(Contact).filter(
                search_filter
            ).limit(limit).all()
            
            return Result.success(contacts)
            
        except Exception as e:
            logger.error(f"Search failed: {str(e)}")
            return Result.failure(f"Search failed: {str(e)}", code="SEARCH_ERROR")
    
    def update_contact(self, contact_id: int, **kwargs) -> Result[Contact]:
        """
        Update contact attributes.
        
        Args:
            contact_id: Contact ID
            **kwargs: Fields to update
            
        Returns:
            Result[Contact]: Success with updated contact or failure
        """
        try:
            contact = self.contact_repository.get_by_id(contact_id)
            if not contact:
                return Result.failure(f"Contact not found: {contact_id}", code="NOT_FOUND")
            
            # Update fields
            for key, value in kwargs.items():
                if hasattr(contact, key):
                    setattr(contact, key, value)
            
            contact.updated_at = datetime.utcnow()
            self.session.commit()
            
            logger.info(f"Updated contact: {contact_id}")
            return Result.success(contact)
            
        except Exception as e:
            self.session.rollback()
            logger.error(f"Failed to update contact: {str(e)}")
            return Result.failure(f"Failed to update contact: {str(e)}", code="UPDATE_ERROR")
    
    def delete_contact(self, contact_id: int) -> Result[bool]:
        """
        Delete a contact.
        
        Args:
            contact_id: Contact ID
            
        Returns:
            Result[bool]: Success or failure
        """
        try:
            contact = self.contact_repository.get_by_id(contact_id)
            if not contact:
                return Result.failure(f"Contact not found: {contact_id}", code="NOT_FOUND")
            
            self.contact_repository.delete(contact_id)
            logger.info(f"Deleted contact: {contact_id}")
            return Result.success(True)
            
        except Exception as e:
            logger.error(f"Failed to delete contact: {str(e)}")
            return Result.failure(f"Failed to delete contact: {str(e)}", code="DELETE_ERROR")
    
    def bulk_action(self, action: str, contact_ids: List[int], **kwargs) -> Result[Dict[str, Any]]:
        """
        Perform bulk action on multiple contacts.
        
        Args:
            action: Action to perform (delete, tag, update, etc.)
            contact_ids: List of contact IDs
            **kwargs: Action-specific parameters
            
        Returns:
            Result[Dict]: Success with results or failure
        """
        if not contact_ids:
            return Result.failure("No contact IDs provided", code="NO_CONTACTS")
        
        results = {
            "successful": 0,
            "failed": 0,
            "errors": []
        }
        
        try:
            if action == "delete":
                for contact_id in contact_ids:
                    result = self.delete_contact(contact_id)
                    if result.is_success:
                        results["successful"] += 1
                    else:
                        results["failed"] += 1
                        results["errors"].append(f"Contact {contact_id}: {result.error}")
            
            elif action == "tag":
                tag = kwargs.get("tag")
                if not tag:
                    return Result.failure("Tag not provided", code="MISSING_PARAMETER")
                
                for contact_id in contact_ids:
                    contact = self.contact_repository.get_by_id(contact_id)
                    if contact:
                        current_tags = contact.tags or []
                        if tag not in current_tags:
                            current_tags.append(tag)
                            contact.tags = current_tags
                            self.session.commit()
                        results["successful"] += 1
                    else:
                        results["failed"] += 1
                        results["errors"].append(f"Contact {contact_id} not found")
            
            elif action == "update":
                update_fields = {k: v for k, v in kwargs.items() if k != "action"}
                for contact_id in contact_ids:
                    result = self.update_contact(contact_id, **update_fields)
                    if result.is_success:
                        results["successful"] += 1
                    else:
                        results["failed"] += 1
                        results["errors"].append(result.error)
            
            else:
                return Result.failure(f"Unknown action: {action}", code="INVALID_ACTION")
            
            return Result.success(results, metadata={"action": action, "total": len(contact_ids)})
            
        except Exception as e:
            logger.error(f"Bulk action failed: {str(e)}")
            return Result.failure(f"Bulk action failed: {str(e)}", code="BULK_ACTION_ERROR")
    
    def add_to_campaign(self, contact_id: int, campaign_id: int) -> Result[CampaignMembership]:
        """
        Add contact to a campaign.
        
        Args:
            contact_id: Contact ID
            campaign_id: Campaign ID
            
        Returns:
            Result[CampaignMembership]: Success with membership or failure
        """
        try:
            # Verify contact exists
            contact = self.contact_repository.get_by_id(contact_id)
            if not contact:
                return Result.failure(f"Contact not found: {contact_id}", code="CONTACT_NOT_FOUND")
            
            # Verify campaign exists
            campaign = Campaign.query.get(campaign_id)
            if not campaign:
                return Result.failure(f"Campaign not found: {campaign_id}", code="CAMPAIGN_NOT_FOUND")
            
            # Check for existing membership
            existing = CampaignMembership.query.filter_by(
                contact_id=contact_id,
                campaign_id=campaign_id
            ).first()
            
            if existing:
                return Result.failure(
                    "Contact already in campaign",
                    code="ALREADY_MEMBER",
                    metadata={"membership_id": existing.id}
                )
            
            # Create membership
            membership = CampaignMembership(
                contact_id=contact_id,
                campaign_id=campaign_id,
                status='pending'
            )
            
            self.session.add(membership)
            self.session.commit()
            
            logger.info(f"Added contact {contact_id} to campaign {campaign_id}")
            return Result.success(membership)
            
        except Exception as e:
            self.session.rollback()
            logger.error(f"Failed to add to campaign: {str(e)}")
            return Result.failure(f"Failed to add to campaign: {str(e)}", code="CAMPAIGN_ERROR")
    
    def bulk_add_to_campaign(self, contact_ids: List[int], campaign_id: int) -> Result[Dict[str, Any]]:
        """
        Add multiple contacts to a campaign.
        
        Args:
            contact_ids: List of contact IDs
            campaign_id: Campaign ID
            
        Returns:
            Result[Dict]: Success with results or failure
        """
        if not contact_ids:
            return Result.failure("No contact IDs provided", code="NO_CONTACTS")
        
        # Verify campaign exists
        campaign = Campaign.query.get(campaign_id)
        if not campaign:
            return Result.failure(f"Campaign not found: {campaign_id}", code="CAMPAIGN_NOT_FOUND")
        
        results = {
            "added": 0,
            "skipped": 0,
            "errors": []
        }
        
        for contact_id in contact_ids:
            result = self.add_to_campaign(contact_id, campaign_id)
            if result.is_success:
                results["added"] += 1
            elif result.error_code == "ALREADY_MEMBER":
                results["skipped"] += 1
            else:
                results["errors"].append(f"Contact {contact_id}: {result.error}")
        
        return Result.success(results, metadata={
            "campaign_id": campaign_id,
            "total_contacts": len(contact_ids)
        })
    
    def export_contacts(self, contact_ids: List[int]) -> Result[str]:
        """
        Export contacts to CSV format.
        
        Args:
            contact_ids: List of contact IDs to export
            
        Returns:
            Result[str]: Success with CSV data or failure
        """
        if not contact_ids:
            return Result.failure("No contact IDs provided", code="NO_CONTACTS")
        
        try:
            contacts = self.session.query(Contact).filter(
                Contact.id.in_(contact_ids)
            ).all()
            
            if not contacts:
                return Result.failure("No contacts found", code="NO_CONTACTS_FOUND")
            
            # Create CSV
            output = io.StringIO()
            writer = csv.DictWriter(output, fieldnames=[
                'id', 'first_name', 'last_name', 'email', 'phone',
                'company', 'address', 'city', 'state', 'zip_code',
                'tags', 'created_at'
            ])
            
            writer.writeheader()
            for contact in contacts:
                writer.writerow({
                    'id': contact.id,
                    'first_name': contact.first_name,
                    'last_name': contact.last_name,
                    'email': contact.email,
                    'phone': contact.phone,
                    'company': contact.company,
                    'address': contact.address,
                    'city': contact.city,
                    'state': contact.state,
                    'zip_code': contact.zip_code,
                    'tags': ','.join(contact.tags) if contact.tags else '',
                    'created_at': contact.created_at.isoformat() if contact.created_at else ''
                })
            
            csv_data = output.getvalue()
            return Result.success(csv_data, metadata={"count": len(contacts)})
            
        except Exception as e:
            logger.error(f"Export failed: {str(e)}")
            return Result.failure(f"Export failed: {str(e)}", code="EXPORT_ERROR")
    
    def get_contact_statistics(self) -> Result[Dict[str, int]]:
        """
        Get overall contact statistics.
        
        Returns:
            Result[Dict]: Success with statistics or failure
        """
        try:
            stats = {
                'total_contacts': self.session.query(Contact).count(),
                'with_phone': self.session.query(Contact).filter(Contact.phone.isnot(None)).count(),
                'with_email': self.session.query(Contact).filter(Contact.email.isnot(None)).count(),
                'with_conversations': self.session.query(Contact).join(Conversation).distinct().count(),
                'opted_out': ContactFlag.query.filter_by(flag_type='opted_out').distinct(ContactFlag.contact_id).count(),
                'invalid_phone': ContactFlag.query.filter_by(flag_type='invalid_phone').distinct(ContactFlag.contact_id).count()
            }
            
            return Result.success(stats)
            
        except Exception as e:
            logger.error(f"Failed to get statistics: {str(e)}")
            return Result.failure(f"Failed to get statistics: {str(e)}", code="STATS_ERROR")