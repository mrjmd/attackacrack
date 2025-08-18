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
# Model and Session imports removed - using repositories only
from services.common.result import Result, PagedResult
from repositories.contact_repository import ContactRepository
from repositories.campaign_repository import CampaignRepository
from repositories.contact_flag_repository import ContactFlagRepository

logger = logging.getLogger(__name__)


class ContactService:
    """Service for managing contacts using Result pattern and Repository"""
    
    def __init__(self, contact_repository: Optional[ContactRepository] = None, 
                 campaign_repository: Optional[CampaignRepository] = None,
                 contact_flag_repository: Optional[ContactFlagRepository] = None):
        """
        Initialize with optional repository and session.
        
        Args:
            contact_repository: ContactRepository for data access
            campaign_repository: CampaignRepository for campaign data access
            contact_flag_repository: ContactFlagRepository for flag data access
        """
        # Repositories must be injected - no fallback to direct instantiation
        self.contact_repository = contact_repository
        self.campaign_repository = campaign_repository
        self.contact_flag_repository = contact_flag_repository
    
    def add_contact(self, first_name: str, last_name: str, 
                   email: Optional[str] = None, 
                   phone: Optional[str] = None,
                   **kwargs) -> Result[Dict]:
        """
        Add a new contact.
        
        Args:
            first_name: Contact's first name
            last_name: Contact's last name
            email: Optional email address
            phone: Optional phone number
            **kwargs: Additional contact fields
            
        Returns:
            Result[Dict]: Success with contact data or failure with error
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
            logger.info(f"Created contact: {contact.id} - {contact.first_name} {contact.last_name}")
            
            return Result.success(contact, metadata={"created_at": datetime.utcnow()})
            
        except Exception as e:
            logger.error(f"Failed to create contact: {str(e)}")
            return Result.failure(f"Failed to create contact: {str(e)}", code="CREATE_ERROR")
    
    def get_contact_by_id(self, contact_id: int) -> Result[Dict]:
        """
        Get contact by ID.
        
        Args:
            contact_id: Contact ID
            
        Returns:
            Result[Dict]: Success with contact data or failure
        """
        contact = self.contact_repository.get_by_id(contact_id)
        if contact:
            return Result.success(contact)
        return Result.failure(f"Contact not found: {contact_id}", code="NOT_FOUND")
    
    def get_contact_by_phone(self, phone_number: str) -> Result[Dict]:
        """
        Get contact by phone number.
        
        Args:
            phone_number: Phone number to search
            
        Returns:
            Result[Dict]: Success with contact data or failure
        """
        contact = self.contact_repository.find_by_phone(phone_number)
        if contact:
            return Result.success(contact)
        return Result.failure(f"Contact not found with phone: {phone_number}", code="NOT_FOUND")
    
    def get_all_contacts(self, page: int = 1, per_page: int = 100) -> PagedResult[List[Dict]]:
        """
        Get all contacts with pagination.
        
        Args:
            page: Page number
            per_page: Items per page
            
        Returns:
            PagedResult[List[Dict]]: Paginated contact data
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
    
    def search_contacts(self, query: str, limit: int = 20) -> Result[List[Dict]]:
        """
        Search contacts by name, email, or phone.
        
        Args:
            query: Search query
            limit: Maximum results
            
        Returns:
            Result[List[Dict]]: Success with contact data or failure
        """
        try:
            if not query:
                return Result.success([])
            
            # Use repository search method
            contacts = self.contact_repository.search(
                query,
                fields=['first_name', 'last_name', 'email', 'phone'],
                limit=limit
            )
            
            return Result.success(contacts)
            
        except Exception as e:
            logger.error(f"Search failed: {str(e)}")
            return Result.failure(f"Search failed: {str(e)}", code="SEARCH_ERROR")
    
    def get_by_ids(self, contact_ids: List[int]) -> Result[List[Dict]]:
        """
        Get multiple contacts by their IDs.
        
        Args:
            contact_ids: List of contact IDs
            
        Returns:
            Result[List[Dict]]: Success with contact data or failure
        """
        try:
            if not contact_ids:
                return Result.success([])
            
            contacts = self.contact_repository.get_by_ids(contact_ids)
            return Result.success(contacts)
            
        except Exception as e:
            logger.error(f"Failed to get contacts by IDs: {str(e)}")
            return Result.failure(f"Failed to get contacts by IDs: {str(e)}", code="FETCH_ERROR")
    
    def update_contact(self, contact_id: int, **kwargs) -> Result[Dict]:
        """
        Update contact attributes.
        
        Args:
            contact_id: Contact ID
            **kwargs: Fields to update
            
        Returns:
            Result[Dict]: Success with updated contact data or failure
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
            # Repository handles commit
            
            logger.info(f"Updated contact: {contact_id}")
            return Result.success(contact)
            
        except Exception as e:
            # Repository handles rollback
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
                            # Repository handles commit
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
    
    def add_to_campaign(self, contact_id: int, campaign_id: int) -> Result[Dict]:
        """
        Add contact to a campaign.
        
        Args:
            contact_id: Contact ID
            campaign_id: Campaign ID
            
        Returns:
            Result[Dict]: Success with membership data or failure
        """
        try:
            # Verify contact exists
            contact = self.contact_repository.get_by_id(contact_id)
            if not contact:
                return Result.failure(f"Contact not found: {contact_id}", code="CONTACT_NOT_FOUND")
            
            # Verify campaign exists
            campaign = self.campaign_repository.get_by_id(campaign_id)
            if not campaign:
                return Result.failure(f"Campaign not found: {campaign_id}", code="CAMPAIGN_NOT_FOUND")
            
            # Check for existing membership
            existing = self.campaign_repository.get_member_by_contact(campaign_id, contact_id)
            
            if existing:
                return Result.failure(
                    "Contact already in campaign",
                    code="ALREADY_MEMBER",
                    metadata={"membership_id": existing.id}
                )
            
            # Create membership using repository
            membership = self.campaign_repository.add_member(
                campaign_id=campaign_id,
                contact_id=contact_id,
                status='pending'
            )
            
            # Repository handles commit
            
            logger.info(f"Added contact {contact_id} to campaign {campaign_id}")
            return Result.success(membership)
            
        except Exception as e:
            # Repository handles rollback
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
        campaign = self.campaign_repository.get_by_id(campaign_id)
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
            contacts = self.contact_repository.get_by_ids(contact_ids)
            
            if not contacts:
                return Result.failure("No contacts found", code="NO_CONTACTS_FOUND")
            
            # Create CSV
            output = io.StringIO()
            writer = csv.DictWriter(output, fieldnames=[
                'id', 'first_name', 'last_name', 'email', 'phone', 'imported_at'
            ])
            
            writer.writeheader()
            for contact in contacts:
                writer.writerow({
                    'id': contact.id,
                    'first_name': contact.first_name,
                    'last_name': contact.last_name,
                    'email': contact.email,
                    'phone': contact.phone,
                    'imported_at': contact.imported_at.isoformat() if contact.imported_at else ''
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
            # Get contact stats from repository
            contact_stats = self.contact_repository.get_contact_stats()
            
            # Get flag stats from repository
            flag_stats = self.contact_flag_repository.get_flag_statistics()
            
            # Combine stats in expected format
            stats = {
                'total_contacts': contact_stats.get('total', 0),
                'with_phone': contact_stats.get('with_phone', 0),
                'with_email': contact_stats.get('with_email', 0),
                'with_conversations': contact_stats.get('with_conversation', 0),
                'opted_out': flag_stats.get('opted_out', 0),
                'invalid_phone': flag_stats.get('invalid_phone', 0)
            }
            
            return Result.success(stats)
            
        except Exception as e:
            logger.error(f"Failed to get statistics: {str(e)}")
            return Result.failure(f"Failed to get statistics: {str(e)}", code="STATS_ERROR")