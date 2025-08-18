"""
CampaignListService (Refactored with Repository Pattern)
Manages campaign lists and contact selection using repository pattern
"""

from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
from services.common.result import Result
from repositories.campaign_list_repository import CampaignListRepository
from repositories.campaign_list_member_repository import CampaignListMemberRepository
from repositories.contact_repository import ContactRepository
# Model imports removed - using repositories only
import logging

logger = logging.getLogger(__name__)


class CampaignListServiceRefactored:
    """
    Campaign List Service using Repository Pattern.
    
    Manages campaign lists and their members through repository abstraction.
    All database operations are delegated to specialized repositories.
    """
    
    def __init__(self, campaign_list_repository: CampaignListRepository,
                 member_repository: CampaignListMemberRepository,
                 contact_repository: ContactRepository):
        """
        Initialize service with repository dependencies.
        
        Args:
            campaign_list_repository: Repository for campaign list operations
            member_repository: Repository for campaign list member operations
            contact_repository: Repository for contact operations
        """
        self.campaign_list_repository = campaign_list_repository
        self.member_repository = member_repository
        self.contact_repository = contact_repository
    
    def create_list(self, name: str, description: str = None, 
                   filter_criteria: Dict = None, is_dynamic: bool = False,
                   created_by: str = None) -> Result[Dict[str, Any]]:
        """
        Create a new campaign list.
        
        Args:
            name: Campaign list name
            description: Optional description
            filter_criteria: Filter criteria for dynamic lists
            is_dynamic: Whether this is a dynamic list
            created_by: User who created the list
            
        Returns:
            Result[CampaignList]: Success with created list or failure with error
        """
        try:
            # Convert datetime objects to ISO strings for JSON serialization
            if filter_criteria:
                serializable_criteria = {}
                for key, value in filter_criteria.items():
                    if isinstance(value, datetime):
                        serializable_criteria[key] = value.isoformat()
                    else:
                        serializable_criteria[key] = value
            else:
                serializable_criteria = filter_criteria
            
            # Create the campaign list
            campaign_list = self.campaign_list_repository.create(
                name=name,
                description=description,
                filter_criteria=serializable_criteria,
                is_dynamic=is_dynamic,
                created_by=created_by
            )
            
            self.campaign_list_repository.commit()
            
            # If dynamic, populate it based on criteria
            if is_dynamic and filter_criteria:
                refresh_result = self.refresh_dynamic_list(campaign_list.id)
                if refresh_result.is_failure:
                    logger.warning(f"Failed to refresh dynamic list {campaign_list.id}: {refresh_result.error}")
            
            return Result.success(campaign_list)
            
        except Exception as e:
            logger.error(f"Failed to create campaign list: {e}")
            self.campaign_list_repository.rollback()
            return Result.failure(f"Failed to create campaign list: {str(e)}")
    
    def add_contacts_to_list(self, list_id: int, contact_ids: List[int], 
                            added_by: str = None) -> Result[Dict[str, int]]:
        """
        Add multiple contacts to a list.
        
        Args:
            list_id: Campaign list ID
            contact_ids: List of contact IDs to add
            added_by: User who added the contacts
            
        Returns:
            Result[Dict]: Success with statistics or failure with error
        """
        try:
            results = {'added': 0, 'already_exists': 0, 'errors': 0}
            
            for contact_id in contact_ids:
                try:
                    # Check if already in list
                    existing = self.member_repository.find_one_by(
                        list_id=list_id, 
                        contact_id=contact_id
                    )
                    
                    if existing:
                        if existing.status == 'removed':
                            # Reactivate removed member
                            self.member_repository.update(
                                existing,
                                status='active',
                                added_at=datetime.utcnow()
                            )
                            results['added'] += 1
                        else:
                            results['already_exists'] += 1
                    else:
                        # Add new member
                        self.member_repository.create(
                            list_id=list_id,
                            contact_id=contact_id,
                            added_by=added_by
                        )
                        results['added'] += 1
                        
                except Exception as e:
                    logger.error(f"Error adding contact {contact_id} to list {list_id}: {e}")
                    results['errors'] += 1
            
            self.member_repository.commit()
            return Result.success(results)
            
        except Exception as e:
            logger.error(f"Failed to add contacts to list {list_id}: {e}")
            self.member_repository.rollback()
            return Result.failure(f"Failed to add contacts to list: {str(e)}")
    
    def remove_contacts_from_list(self, list_id: int, contact_ids: List[int]) -> Result[int]:
        """
        Remove contacts from a list (soft delete).
        
        Args:
            list_id: Campaign list ID
            contact_ids: List of contact IDs to remove
            
        Returns:
            Result[int]: Success with count of removed contacts or failure
        """
        try:
            count = self.member_repository.remove_contacts_from_list(list_id, contact_ids)
            self.member_repository.commit()
            return Result.success(count)
            
        except Exception as e:
            logger.error(f"Failed to remove contacts from list {list_id}: {e}")
            self.member_repository.rollback()
            return Result.failure(f"Failed to remove contacts from list: {str(e)}")
    
    def get_list_contacts(self, list_id: int, include_removed: bool = False) -> Result[List[Dict[str, Any]]]:
        """
        Get all contacts in a list.
        
        Args:
            list_id: Campaign list ID
            include_removed: Whether to include removed contacts
            
        Returns:
            Result[List[Contact]]: Success with contacts or failure
        """
        try:
            contact_ids = self.member_repository.get_contact_ids_in_list(
                list_id, include_removed=include_removed
            )
            contacts = self.contact_repository.get_by_ids(contact_ids)
            return Result.success(contacts)
            
        except Exception as e:
            logger.error(f"Failed to get contacts for list {list_id}: {e}")
            return Result.failure(f"Failed to get list contacts: {str(e)}")
    
    def get_list_stats(self, list_id: int) -> Result[Dict[str, int]]:
        """
        Get statistics for a campaign list.
        
        Args:
            list_id: Campaign list ID
            
        Returns:
            Result[Dict]: Success with statistics or failure
        """
        try:
            # Get membership stats
            member_stats = self.member_repository.get_membership_stats(list_id)
            
            # Get contact stats
            contacts_result = self.get_list_contacts(list_id)
            if contacts_result.is_failure:
                return contacts_result
            
            contacts = contacts_result.data
            
            stats = {
                'total_members': member_stats['total'],
                'active_members': member_stats['active'],
                'removed_members': member_stats['removed'],
                'with_email': sum(1 for c in contacts if c.email),
                'with_phone': sum(1 for c in contacts if c.phone)
            }
            
            return Result.success(stats)
            
        except Exception as e:
            logger.error(f"Failed to get stats for list {list_id}: {e}")
            return Result.failure(f"Failed to get list statistics: {str(e)}")
    
    def find_contacts_by_criteria(self, criteria: Dict) -> Result[List[Dict[str, Any]]]:
        """
        Find contacts based on filter criteria.
        
        Args:
            criteria: Filter criteria dictionary
            
        Returns:
            Result[List[Contact]]: Success with matching contacts or failure
        """
        try:
            # CSV Import filter
            if 'csv_import_id' in criteria:
                contacts = self.contact_repository.find_by_csv_import(criteria['csv_import_id'])
                return Result.success(contacts)
            
            # Date range filters
            if 'imported_after' in criteria or 'imported_before' in criteria:
                imported_after = None
                imported_before = None
                
                if 'imported_after' in criteria:
                    date_value = criteria['imported_after']
                    if isinstance(date_value, str):
                        imported_after = datetime.fromisoformat(date_value)
                    else:
                        imported_after = date_value
                
                if 'imported_before' in criteria:
                    date_value = criteria['imported_before']
                    if isinstance(date_value, str):
                        imported_before = datetime.fromisoformat(date_value)
                    else:
                        imported_before = date_value
                
                contacts = self.contact_repository.find_by_date_range(
                    imported_after=imported_after,
                    imported_before=imported_before
                )
                return Result.success(contacts)
            
            # No recent contact filter
            if 'no_recent_contact' in criteria:
                days = criteria.get('days_since_contact', 30)
                contacts = self.contact_repository.find_without_recent_activity(days)
                return Result.success(contacts)
            
            # Exclude opted out filter
            if 'exclude_opted_out' in criteria and criteria['exclude_opted_out']:
                contacts = self.contact_repository.find_not_opted_out()
                return Result.success(contacts)
            
            # Metadata filters
            if 'has_metadata' in criteria:
                contacts = self.contact_repository.find_by_metadata_keys(criteria['has_metadata'])
                return Result.success(contacts)
            
            # If no specific criteria, return empty list
            return Result.success([])
            
        except Exception as e:
            logger.error(f"Failed to find contacts by criteria: {e}")
            return Result.failure(f"Failed to find contacts by criteria: {str(e)}")
    
    def refresh_dynamic_list(self, list_id: int) -> Result[Dict[str, int]]:
        """
        Refresh a dynamic list based on its filter criteria.
        
        Args:
            list_id: Campaign list ID
            
        Returns:
            Result[Dict]: Success with refresh statistics or failure
        """
        try:
            # Get the campaign list
            campaign_list = self.campaign_list_repository.get_by_id(list_id)
            if not campaign_list:
                return Result.failure("Campaign list not found")
            
            if not campaign_list.is_dynamic:
                return Result.failure("Campaign list is not dynamic")
            
            # Get current members
            current_contact_ids = set(
                self.member_repository.get_contact_ids_in_list(list_id, include_removed=False)
            )
            
            # Find contacts matching criteria
            matching_result = self.find_contacts_by_criteria(campaign_list.filter_criteria or {})
            if matching_result.is_failure:
                return matching_result
            
            matching_contacts = matching_result.data
            matching_ids = set(c.id for c in matching_contacts)
            
            # Add new matches
            to_add = matching_ids - current_contact_ids
            for contact_id in to_add:
                self.member_repository.create(
                    list_id=list_id,
                    contact_id=contact_id,
                    added_by='system_dynamic'
                )
            
            # Remove non-matches
            to_remove = current_contact_ids - matching_ids
            if to_remove:
                self.member_repository.remove_contacts_from_list(list_id, list(to_remove))
            
            # Update list timestamp
            self.campaign_list_repository.update(campaign_list, updated_at=datetime.utcnow())
            self.campaign_list_repository.commit()
            
            stats = {
                'added': len(to_add),
                'removed': len(to_remove),
                'total': len(matching_ids)
            }
            
            return Result.success(stats)
            
        except Exception as e:
            logger.error(f"Failed to refresh dynamic list {list_id}: {e}")
            self.campaign_list_repository.rollback()
            return Result.failure(f"Failed to refresh dynamic list: {str(e)}")
    
    def get_all_lists(self) -> Result[List[Dict[str, Any]]]:
        """
        Get all campaign lists.
        
        Returns:
            Result[List[CampaignList]]: Success with all lists or failure
        """
        try:
            lists = self.campaign_list_repository.get_lists_ordered_by_created_desc()
            return Result.success(lists)
            
        except Exception as e:
            logger.error(f"Failed to get all campaign lists: {e}")
            return Result.failure(f"Failed to get campaign lists: {str(e)}")
    
    def duplicate_list(self, list_id: int, new_name: str, created_by: str = None) -> Result[Dict[str, Any]]:
        """
        Create a copy of an existing list.
        
        Args:
            list_id: Source list ID
            new_name: Name for the new list
            created_by: User who created the duplicate
            
        Returns:
            Result[CampaignList]: Success with new list or failure
        """
        try:
            # Get source list
            source_list = self.campaign_list_repository.get_by_id(list_id)
            if not source_list:
                return Result.failure("Source campaign list not found")
            
            # Create new list
            new_list = self.campaign_list_repository.create(
                name=new_name,
                description=f"Copy of {source_list.name}",
                filter_criteria=source_list.filter_criteria,
                is_dynamic=False,  # Copies are static by default
                created_by=created_by
            )
            
            self.campaign_list_repository.flush()
            
            # Copy active members
            active_contact_ids = self.member_repository.get_contact_ids_in_list(
                list_id, include_removed=False
            )
            
            for contact_id in active_contact_ids:
                self.member_repository.create(
                    list_id=new_list.id,
                    contact_id=contact_id,
                    added_by=created_by or 'system_duplicate'
                )
            
            self.campaign_list_repository.commit()
            return Result.success(new_list)
            
        except Exception as e:
            logger.error(f"Failed to duplicate list {list_id}: {e}")
            self.campaign_list_repository.rollback()
            return Result.failure(f"Failed to duplicate list: {str(e)}")
    
    def get_campaign_list_by_id(self, list_id: int) -> Result[Dict[str, Any]]:
        """
        Get a campaign list by ID.
        
        Args:
            list_id: Campaign list ID
            
        Returns:
            Result[CampaignList]: Success with list or failure
        """
        try:
            campaign_list = self.campaign_list_repository.get_by_id(list_id)
            if campaign_list:
                return Result.success(campaign_list)
            else:
                return Result.failure("Campaign list not found")
                
        except Exception as e:
            logger.error(f"Failed to get campaign list {list_id}: {e}")
            return Result.failure(f"Failed to get campaign list: {str(e)}")
