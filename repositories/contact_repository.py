"""
ContactRepository - Data access layer for Contact entities
Isolates all database queries related to contacts
"""

from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
from utils.datetime_utils import utc_now
from sqlalchemy import or_, and_, func, exists, desc, asc
from sqlalchemy.orm import joinedload, selectinload, Query
from repositories.base_repository import BaseRepository, PaginationParams, PaginatedResult, SortOrder
from crm_database import Contact, ContactFlag, Conversation, Activity, CampaignMembership, Property, Job, PropertyContact
import logging

logger = logging.getLogger(__name__)


class ContactRepository(BaseRepository[Contact]):
    """Repository for Contact data access"""
    
    def __init__(self, session):
        """Initialize repository with database session"""
        super().__init__(session, Contact)
    
    def search(self, query: str, fields: Optional[List[str]] = None, limit: Optional[int] = None) -> List[Contact]:
        """
        Search contacts by text query across multiple fields.
        
        Args:
            query: Search query string
            fields: Specific fields to search (default: name, phone, email, company)
            limit: Maximum number of results to return
            
        Returns:
            List of matching contacts
        """
        if not query:
            return []
        
        search_fields = fields or ['first_name', 'last_name', 'phone', 'email']
        
        conditions = []
        for field in search_fields:
            if hasattr(Contact, field):
                conditions.append(getattr(Contact, field).ilike(f'%{query}%'))
        
        if not conditions:
            return []
        
        query_obj = self.session.query(Contact).filter(or_(*conditions))
        if limit:
            query_obj = query_obj.limit(limit)
            
        return query_obj.all()
    
    def find_by_phone(self, phone: str) -> Optional[Contact]:
        """
        Find contact by phone number.
        
        Args:
            phone: Phone number to search for
            
        Returns:
            Contact or None
        """
        return self.find_one_by(phone=phone)
    
    def find_by_email(self, email: str) -> Optional[Contact]:
        """
        Find contact by email address.
        
        Args:
            email: Email to search for
            
        Returns:
            Contact or None
        """
        return self.find_one_by(email=email)
    
    def find_by_openphone_id(self, openphone_contact_id: str) -> Optional[Contact]:
        """
        Find contact by OpenPhone ID.
        
        Args:
            openphone_contact_id: OpenPhone contact ID
            
        Returns:
            Contact or None
        """
        return self.find_one_by(openphone_contact_id=openphone_contact_id)
    
    def get_contact_with_relations(self, contact_id: int) -> Optional[Contact]:
        """
        Get contact with eager loaded properties and jobs.
        
        Args:
            contact_id: Contact ID
            
        Returns:
            Contact object with relations or None if not found
        """
        try:
            # For dynamic relationships, we just get the contact
            # and let the relationships be loaded on-demand
            return self.get_by_id(contact_id)
        except Exception as e:
            logger.error(f"Failed to get contact with relations: {str(e)}")
            return None
    
    def get_contacts_with_filter(
        self,
        filter_type: str = 'all',
        search_query: Optional[str] = None,
        sort_by: str = 'name',
        sort_order: SortOrder = SortOrder.ASC,
        pagination: Optional[PaginationParams] = None
    ) -> PaginatedResult[Contact]:
        """
        Get contacts with advanced filtering options.
        
        Args:
            filter_type: Type of filter to apply
            search_query: Optional search query
            sort_by: Field to sort by
            sort_order: Sort order
            pagination: Pagination parameters
            
        Returns:
            PaginatedResult with filtered contacts
        """
        query = self.session.query(Contact)
        
        # Apply search
        if search_query:
            query = self._apply_search(query, search_query)
        
        # Apply filter
        query = self._apply_filter(query, filter_type)
        
        # Apply sorting
        query = self._apply_sorting(query, sort_by, sort_order)
        
        # Get total count
        total = query.count()
        
        # Apply pagination if provided
        if pagination:
            query = query.offset(pagination.offset).limit(pagination.limit)
            items = query.all()
            return PaginatedResult(
                items=items,
                total=total,
                page=pagination.page,
                per_page=pagination.per_page
            )
        else:
            # Return all results
            items = query.all()
            return PaginatedResult(
                items=items,
                total=total,
                page=1,
                per_page=total or 1
            )
    
    def _apply_search(self, query: Query, search_query: str) -> Query:
        """Apply search filter to query"""
        return query.filter(
            or_(
                Contact.first_name.ilike(f'%{search_query}%'),
                Contact.last_name.ilike(f'%{search_query}%'),
                Contact.phone.ilike(f'%{search_query}%'),
                Contact.email.ilike(f'%{search_query}%')
            )
        )
    
    def _apply_filter(self, query: Query, filter_type: str) -> Query:
        """Apply filter type to query"""
        if filter_type == 'has_phone':
            return query.filter(Contact.phone.isnot(None))
        
        elif filter_type == 'has_email':
            return query.filter(Contact.email.isnot(None))
        
        elif filter_type == 'has_conversation':
            return query.filter(
                exists().where(Conversation.contact_id == Contact.id)
            )
        
        elif filter_type == 'no_conversation':
            return query.filter(
                ~exists().where(Conversation.contact_id == Contact.id)
            )
        
        elif filter_type == 'opted_out':
            return query.filter(
                exists().where(
                    and_(
                        ContactFlag.contact_id == Contact.id,
                        ContactFlag.flag_type == 'opted_out'
                    )
                )
            )
        
        elif filter_type == 'recent_activity':
            # Contacts with activity in last 30 days
            thirty_days_ago = datetime.now() - timedelta(days=30)
            return query.join(Conversation).filter(
                Conversation.last_activity_at >= thirty_days_ago
            )
        
        elif filter_type == 'has_property':
            return query.filter(
                exists().where(Property.contact_id == Contact.id)
            )
        
        elif filter_type == 'has_job':
            return query.filter(
                exists().where(
                    and_(
                        Job.property_id == Property.id,
                        Property.contact_id == Contact.id
                    )
                )
            )
        
        elif filter_type == 'in_campaign':
            return query.filter(
                exists().where(CampaignMembership.contact_id == Contact.id)
            )
        
        return query  # 'all' or unknown filter
    
    def _apply_sorting(self, query: Query, sort_by: str, sort_order: SortOrder) -> Query:
        """Apply sorting to query"""
        order_func = desc if sort_order == SortOrder.DESC else asc
        
        if sort_by == 'name':
            return query.order_by(
                order_func(Contact.last_name),
                order_func(Contact.first_name)
            )
        
        elif sort_by == 'created':
            return query.order_by(order_func(Contact.created_at))
        
        elif sort_by == 'updated':
            return query.order_by(order_func(Contact.updated_at))
        
        elif sort_by == 'recent_activity':
            return query.outerjoin(Conversation).group_by(Contact.id).order_by(
                func.max(Conversation.last_activity_at).desc().nullslast()
                if sort_order == SortOrder.DESC
                else func.max(Conversation.last_activity_at).asc().nullsfirst()
            )
        
        # Note: company field not available in Contact model
        
        elif sort_by == 'email':
            return query.order_by(order_func(Contact.email))
        
        elif sort_by == 'phone':
            return query.order_by(order_func(Contact.phone))
        
        # Default to name if unknown sort field
        return self._apply_sorting(query, 'name', sort_order)
    
    def get_contacts_with_conversations(self) -> List[Contact]:
        """
        Get all contacts that have at least one conversation.
        
        Returns:
            List of contacts with conversations
        """
        return self.session.query(Contact).filter(
            exists().where(Conversation.contact_id == Contact.id)
        ).all()
    
    def get_contacts_without_conversations(self) -> List[Contact]:
        """
        Get all contacts that have no conversations.
        
        Returns:
            List of contacts without conversations
        """
        return self.session.query(Contact).filter(
            ~exists().where(Conversation.contact_id == Contact.id)
        ).all()
    
    def get_opted_out_contacts(self) -> List[Contact]:
        """
        Get all contacts that have opted out.
        
        Returns:
            List of opted-out contacts
        """
        return self.session.query(Contact).filter(
            exists().where(
                and_(
                    ContactFlag.contact_id == Contact.id,
                    ContactFlag.flag_type == 'opted_out'
                )
            )
        ).all()
    
    def get_contacts_with_recent_activity(self, days: int = 30) -> List[Contact]:
        """
        Get contacts with activity in the last N days.
        
        Args:
            days: Number of days to look back
            
        Returns:
            List of contacts with recent activity
        """
        cutoff_date = datetime.now() - timedelta(days=days)
        return self.session.query(Contact).join(Conversation).filter(
            Conversation.last_activity_at >= cutoff_date
        ).distinct().all()
    
    def get_paginated_contacts(
        self,
        search_query: str = '',
        filter_type: str = 'all',
        sort_by: str = 'name',
        page: int = 1,
        per_page: int = 50
    ) -> Dict[str, Any]:
        """
        Get paginated contacts with search and filtering.
        
        Args:
            search_query: Search query string
            filter_type: Filter type to apply
            sort_by: Field to sort by
            page: Page number (1-based)
            per_page: Items per page
            
        Returns:
            Dictionary with pagination metadata and contacts
        """
        pagination_params = PaginationParams(page=page, per_page=per_page)
        result = self.get_contacts_with_filter(
            filter_type=filter_type,
            search_query=search_query,
            sort_by=sort_by,
            sort_order=SortOrder.ASC,
            pagination=pagination_params
        )
        
        # Convert PaginatedResult to dict format expected by service
        return {
            'contacts': result.items,
            'total_count': result.total,
            'page': result.page,
            'total_pages': result.pages,
            'has_prev': result.has_prev,
            'has_next': result.has_next
        }
    
    def get_contacts_by_tag(self, tag: str) -> List[Contact]:
        """
        Get contacts with a specific tag.
        
        Args:
            tag: Tag to filter by
            
        Returns:
            List of contacts with the tag
        """
        return self.session.query(Contact).filter(
            Contact.tags.contains([tag])
        ).all()
    
    def get_contacts_by_company(self, company: str) -> List[Contact]:
        """
        Get all contacts from a specific company.
        
        Args:
            company: Company name
            
        Returns:
            List of contacts from the company
        """
        return self.find_by(company=company)
    
    def get_contacts_with_properties(self) -> List[Contact]:
        """
        Get all contacts that have properties.
        
        Returns:
            List of contacts with properties
        """
        return self.session.query(Contact).filter(
            exists().where(Property.contact_id == Contact.id)
        ).all()
    
    def get_contacts_with_jobs(self) -> List[Contact]:
        """
        Get all contacts that have jobs.
        
        Returns:
            List of contacts with jobs
        """
        return self.session.query(Contact).join(Property).filter(
            exists().where(Job.property_id == Property.id)
        ).distinct().all()
    
    def get_contacts_in_campaign(self, campaign_id: int) -> List[Contact]:
        """
        Get all contacts in a specific campaign.
        
        Args:
            campaign_id: Campaign ID
            
        Returns:
            List of contacts in the campaign
        """
        return self.session.query(Contact).join(CampaignMembership).filter(
            CampaignMembership.campaign_id == campaign_id
        ).all()
    
    def get_contacts_not_in_any_campaign(self) -> List[Contact]:
        """
        Get contacts not in any campaign.
        
        Returns:
            List of contacts not in campaigns
        """
        return self.session.query(Contact).filter(
            ~exists().where(CampaignMembership.contact_id == Contact.id)
        ).all()
    
    def bulk_update_tags(self, contact_ids: List[int], tags: List[str], operation: str = 'add') -> int:
        """
        Bulk update tags for multiple contacts.
        
        Args:
            contact_ids: List of contact IDs
            tags: Tags to add/remove
            operation: 'add', 'remove', or 'replace'
            
        Returns:
            Number of contacts updated
        """
        contacts = self.session.query(Contact).filter(Contact.id.in_(contact_ids)).all()
        
        for contact in contacts:
            current_tags = contact.tags or []
            
            if operation == 'add':
                # Add new tags
                contact.tags = list(set(current_tags + tags))
            elif operation == 'remove':
                # Remove specified tags
                contact.tags = [t for t in current_tags if t not in tags]
            elif operation == 'replace':
                # Replace all tags
                contact.tags = tags
        
        self.session.flush()
        return len(contacts)
    
    def merge_contacts(self, primary_id: int, duplicate_id: int) -> Optional[Contact]:
        """
        Merge duplicate contact into primary contact.
        
        Args:
            primary_id: ID of contact to keep
            duplicate_id: ID of contact to merge and delete
            
        Returns:
            Merged contact or None if not found
        """
        primary = self.get_by_id(primary_id)
        duplicate = self.get_by_id(duplicate_id)
        
        if not primary or not duplicate:
            return None
        
        # Merge fields (primary takes precedence)
        if not primary.email and duplicate.email:
            primary.email = duplicate.email
        if not primary.phone and duplicate.phone:
            primary.phone = duplicate.phone
        if not primary.company and duplicate.company:
            primary.company = duplicate.company
        
        # Merge tags
        if duplicate.tags:
            primary.tags = list(set((primary.tags or []) + duplicate.tags))
        
        # Transfer relationships
        self.session.query(Conversation).filter_by(contact_id=duplicate_id).update(
            {'contact_id': primary_id}
        )
        self.session.query(Property).filter_by(contact_id=duplicate_id).update(
            {'contact_id': primary_id}
        )
        self.session.query(CampaignMembership).filter_by(contact_id=duplicate_id).update(
            {'contact_id': primary_id}
        )
        self.session.query(ContactFlag).filter_by(contact_id=duplicate_id).update(
            {'contact_id': primary_id}
        )
        
        # Delete duplicate
        self.delete(duplicate)
        self.session.flush()
        
        return primary
    
    def find_duplicates(self, field: str = 'phone') -> List[Tuple[str, int]]:
        """
        Find duplicate contacts by field.
        
        Args:
            field: Field to check for duplicates ('phone', 'email')
            
        Returns:
            List of (field_value, count) tuples
        """
        if field == 'phone':
            query = self.session.query(
                Contact.phone,
                func.count(Contact.id).label('count')
            ).filter(
                Contact.phone.isnot(None)
            ).group_by(Contact.phone).having(func.count(Contact.id) > 1)
        
        elif field == 'email':
            query = self.session.query(
                Contact.email,
                func.count(Contact.id).label('count')
            ).filter(
                Contact.email.isnot(None)
            ).group_by(Contact.email).having(func.count(Contact.id) > 1)
        
        else:
            return []
        
        return query.all()
    
    def get_contact_stats(self) -> Dict[str, int]:
        """
        Get statistics about contacts.
        
        Returns:
            Dictionary with various contact counts
        """
        total = self.count()
        # Count contacts with phone numbers (not null/empty)
        with_phone = self.session.query(Contact).filter(Contact.phone.isnot(None)).count()
        with_email = self.session.query(Contact).filter(Contact.email.isnot(None)).count()
        with_conversation = self.session.query(Contact).filter(
            exists().where(Conversation.contact_id == Contact.id)
        ).count()
        opted_out = len(self.get_opted_out_contacts())
        
        return {
            'total': total,
            'with_phone': with_phone,
            'with_email': with_email,
            'with_conversation': with_conversation,
            'opted_out': opted_out,
            'without_conversation': total - with_conversation
        }
    
    def get_by_ids(self, contact_ids: List[int]) -> List[Contact]:
        """
        Get multiple contacts by their IDs.
        
        Args:
            contact_ids: List of contact IDs
            
        Returns:
            List of contacts matching the IDs
        """
        if not contact_ids:
            return []
            
        return self.session.query(Contact).filter(Contact.id.in_(contact_ids)).all()
    
    def find_by_csv_import(self, csv_import_id: int) -> List[Contact]:
        """
        Find contacts by CSV import ID using the many-to-many relationship.
        
        Args:
            csv_import_id: CSV import ID
            
        Returns:
            List of contacts from the CSV import
        """
        from crm_database import ContactCSVImport
        return self.session.query(Contact).join(ContactCSVImport).filter(
            ContactCSVImport.csv_import_id == csv_import_id
        ).all()
    
    def find_by_date_range(self, imported_after: Optional[datetime] = None, 
                          imported_before: Optional[datetime] = None) -> List[Contact]:
        """
        Find contacts by import date range.
        
        Args:
            imported_after: Start date (inclusive)
            imported_before: End date (inclusive)
            
        Returns:
            List of contacts imported in the date range
        """
        query = self.session.query(Contact)
        
        if imported_after:
            query = query.filter(Contact.imported_at >= imported_after)
        
        if imported_before:
            query = query.filter(Contact.imported_at <= imported_before)
        
        return query.all()
    
    def find_without_recent_activity(self, days: int = 30) -> List[Contact]:
        """
        Find contacts with no recent outgoing activity.
        
        Args:
            days: Number of days to look back
            
        Returns:
            List of contacts without recent activity
        """
        cutoff_date = utc_now() - timedelta(days=days)
        
        # Subquery to find contacts with recent outgoing activity
        recent_contacts = self.session.query(Activity.contact_id).filter(
            Activity.created_at > cutoff_date,
            Activity.direction == 'outgoing'
        )
        
        return self.session.query(Contact).filter(
            ~Contact.id.in_(recent_contacts)
        ).all()
    
    def find_not_opted_out(self) -> List[Contact]:
        """
        Find contacts that have not opted out.
        
        Returns:
            List of contacts not opted out
        """
        opted_out = self.session.query(ContactFlag.contact_id).filter(
            ContactFlag.flag_type == 'opted_out',
            or_(ContactFlag.expires_at.is_(None), 
                ContactFlag.expires_at > utc_now())
        )
        
        return self.session.query(Contact).filter(
            ~Contact.id.in_(opted_out)
        ).all()
    
    def find_by_metadata_keys(self, metadata_keys: List[str]) -> List[Contact]:
        """
        Find contacts that have specific metadata keys.
        
        Args:
            metadata_keys: List of metadata keys to check for
            
        Returns:
            List of contacts with the metadata keys
        """
        query = self.session.query(Contact).filter(
            Contact.contact_metadata.isnot(None)
        )
        
        for key in metadata_keys:
            # For SQLite compatibility, use LIKE operator on JSON string
            query = query.filter(
                func.json_extract(Contact.contact_metadata, f'$.{key}').isnot(None)
            )
        
        return query.all()
    
    # Dashboard-specific methods
    
    def get_total_contacts_count(self) -> int:
        """
        Get total count of contacts.
        
        Returns:
            Total number of contacts
        """
        return self.session.query(Contact).count()
    
    def get_contacts_added_this_week_count(self) -> int:
        """
        Get count of contacts added in the last 7 days using Activity as proxy.
        Since Contact doesn't have created_at, we use Activity records.
        
        Returns:
            Number of distinct contacts with activity in last 7 days
        """
        week_ago = datetime.now() - timedelta(days=7)
        return self.session.query(Activity.contact_id).filter(
            Activity.created_at >= week_ago,
            Activity.contact_id.isnot(None)
        ).distinct().count()
    
    def get_contacts_with_names_count(self) -> int:
        """
        Get count of contacts with real names (excluding phone numbers as names).
        
        Returns:
            Number of contacts with non-phone-number names
        """
        return self.session.query(Contact).filter(
            ~Contact.first_name.like('%+1%')
        ).count()
    
    def get_contacts_with_emails_count(self) -> int:
        """
        Get count of contacts with valid email addresses.
        
        Returns:
            Number of contacts with non-null, non-empty emails
        """
        return self.session.query(Contact).filter(
            Contact.email.isnot(None),
            Contact.email != ''
        ).count()
    
    def get_data_quality_stats(self) -> Dict[str, int]:
        """
        Get comprehensive data quality statistics for contacts.
        
        Returns:
            Dictionary with total contacts, quality counts, and score
        """
        total_contacts = self.get_total_contacts_count()
        
        if total_contacts == 0:
            return {
                'total_contacts': 0,
                'contacts_with_names': 0,
                'contacts_with_emails': 0,
                'data_quality_score': 0
            }
        
        contacts_with_names = self.get_contacts_with_names_count()
        contacts_with_emails = self.get_contacts_with_emails_count()
        
        # Calculate score: (name_score + email_score) / (total * 2) * 100
        data_quality_score = round(
            ((contacts_with_names + contacts_with_emails) / (total_contacts * 2)) * 100
        )
        
        return {
            'total_contacts': total_contacts,
            'contacts_with_names': contacts_with_names,
            'contacts_with_emails': contacts_with_emails,
            'data_quality_score': data_quality_score
        }
    
    # SMS Metrics Enhancement Methods
    
    def update_contact_bounce_status(self, contact_id: int, bounce_info: dict):
        """
        Update contact bounce status and metadata for SMS metrics tracking.
        
        Args:
            contact_id: ID of the contact to update
            bounce_info: Bounce information to merge
            
        Returns:
            Updated Contact object or None if not found
        """
        contact = self.get_by_id(contact_id)
        if not contact:
            return None
        
        # Initialize metadata if needed
        if not contact.contact_metadata:
            contact.contact_metadata = {}
        
        # Initialize bounce info if needed
        if 'bounce_info' not in contact.contact_metadata:
            contact.contact_metadata['bounce_info'] = {
                'total_bounces': 0,
                'counts': {}
            }
        
        bounce_data = contact.contact_metadata['bounce_info']
        bounce_type = bounce_info.get('bounce_type', 'unknown')
        
        # Update bounce counts
        if 'counts' not in bounce_data:
            bounce_data['counts'] = {}
        
        bounce_data['counts'][bounce_type] = bounce_data['counts'].get(bounce_type, 0) + 1
        bounce_data['total_bounces'] = sum(bounce_data['counts'].values())
        bounce_data['last_bounce'] = bounce_info.get('bounced_at')
        bounce_data['last_bounce_type'] = bounce_type
        
        # Mark as SMS invalid if too many hard bounces
        if bounce_data['counts'].get('hard', 0) >= 2:
            contact.contact_metadata['sms_invalid'] = True
            contact.contact_metadata['sms_invalid_reason'] = 'Multiple hard bounces'
        
        self.session.flush()
        return contact
    
    def find_contacts_with_bounce_metadata(self, bounce_threshold: int = 1) -> List[Contact]:
        """
        Find contacts with bounce metadata above threshold.
        
        Args:
            bounce_threshold: Minimum number of bounces to include
            
        Returns:
            List of contacts with bounce history
        """
        contacts = self.session.query(Contact).filter(
            Contact.contact_metadata.contains('bounce_info')
        ).all()
        
        # Filter by bounce threshold
        result = []
        for contact in contacts:
            if contact.contact_metadata and 'bounce_info' in contact.contact_metadata:
                bounce_info = contact.contact_metadata['bounce_info']
                if bounce_info.get('total_bounces', 0) >= bounce_threshold:
                    result.append(contact)
        
        return result
    
    def find_contacts_by_sms_validity(self, valid: bool = True) -> List[Contact]:
        """
        Find contacts by SMS validity status.
        
        Args:
            valid: If True, find valid SMS contacts; if False, find invalid ones
            
        Returns:
            List of contacts matching validity criteria
        """
        if valid:
            # Find contacts not marked as SMS invalid
            return self.session.query(Contact).filter(
                or_(
                    Contact.contact_metadata.is_(None),
                    ~Contact.contact_metadata.contains('sms_invalid'),
                    func.json_extract(Contact.contact_metadata, '$.sms_invalid') != True
                )
            ).all()
        else:
            # Find contacts marked as SMS invalid
            return self.session.query(Contact).filter(
                func.json_extract(Contact.contact_metadata, '$.sms_invalid') == True
            ).all()
    
    def get_contacts_bounce_summary(self) -> dict:
        """
        Get comprehensive bounce summary for all contacts.
        
        Returns:
            Dictionary with bounce statistics
        """
        total_contacts = self.count()
        
        # Get contacts with bounce info
        contacts_with_bounces = self.session.query(Contact).filter(
            Contact.contact_metadata.contains('bounce_info')
        ).all()
        
        # Get SMS invalid contacts
        sms_invalid_contacts = len(self.find_contacts_by_sms_validity(valid=False))
        
        # Calculate bounce type breakdown
        bounce_type_breakdown = {'hard': 0, 'soft': 0, 'carrier_rejection': 0, 'capability': 0, 'unknown': 0}
        
        for contact in contacts_with_bounces:
            bounce_info = contact.contact_metadata.get('bounce_info', {})
            counts = bounce_info.get('counts', {})
            for bounce_type, count in counts.items():
                if bounce_type in bounce_type_breakdown:
                    bounce_type_breakdown[bounce_type] += count
        
        bounce_rate = (len(contacts_with_bounces) / total_contacts * 100) if total_contacts > 0 else 0
        
        return {
            'total_contacts': total_contacts,
            'contacts_with_bounces': len(contacts_with_bounces),
            'sms_invalid_contacts': sms_invalid_contacts,
            'bounce_rate_percentage': bounce_rate,
            'bounce_type_breakdown': bounce_type_breakdown
        }
    
    def bulk_update_contacts_metadata(self, contact_ids: List[int], metadata_update: dict, merge: bool = True) -> int:
        """
        Bulk update contact metadata.
        
        Args:
            contact_ids: List of contact IDs to update
            metadata_update: Metadata to set/merge
            merge: Whether to merge with existing metadata
            
        Returns:
            Number of contacts updated
        """
        if not contact_ids:
            return 0
        
        contacts = self.session.query(Contact).filter(Contact.id.in_(contact_ids)).all()
        
        for contact in contacts:
            if merge and contact.contact_metadata:
                contact.contact_metadata.update(metadata_update)
            else:
                contact.contact_metadata = metadata_update
        
        self.session.flush()
        return len(contacts)
    
    def find_contacts_with_metadata_keys(self, metadata_keys: List[str]) -> List[Contact]:
        """
        Find contacts that have specific metadata keys.
        
        Args:
            metadata_keys: List of metadata keys to check for
            
        Returns:
            List of contacts with the metadata keys
        """
        query = self.session.query(Contact).filter(
            Contact.contact_metadata.isnot(None)
        )
        
        for key in metadata_keys:
            query = query.filter(
                Contact.contact_metadata.contains(key)
            )
        
        return query.all()
    
    def get_contact_reliability_score(self, contact_id: int) -> float:
        """
        Calculate contact reliability score based on bounce history.
        
        Args:
            contact_id: Contact ID to calculate score for
            
        Returns:
            Reliability score as percentage (0-100)
        """
        contact = self.get_by_id(contact_id)
        if not contact or not contact.contact_metadata:
            return 100.0  # No history means perfect score
        
        bounce_info = contact.contact_metadata.get('bounce_info')
        if not bounce_info:
            return 100.0
        
        total_bounces = bounce_info.get('total_bounces', 0)
        hard_bounces = bounce_info.get('counts', {}).get('hard', 0)
        
        # Score calculation: start at 100%, deduct points for bounces
        score = 100.0
        score -= hard_bounces * 30  # Hard bounces heavily penalized
        score -= (total_bounces - hard_bounces) * 5  # Other bounces lightly penalized
        
        return max(0.0, min(100.0, score))
    
    def find_problematic_numbers(self, bounce_threshold: int = 2) -> List[dict]:
        """
        Find problematic phone numbers with delivery issues.
        
        Args:
            bounce_threshold: Minimum bounces to be considered problematic
            
        Returns:
            List of problematic contact details
        """
        contacts = self.find_contacts_with_bounce_metadata(bounce_threshold)
        
        result = []
        for contact in contacts:
            bounce_info = contact.contact_metadata.get('bounce_info', {})
            
            result.append({
                'contact_id': contact.id,
                'phone': contact.phone,
                'name': f'{contact.first_name or ""} {contact.last_name or ""}' if contact.first_name or contact.last_name else 'Unknown',
                'total_bounces': bounce_info.get('total_bounces', 0),
                'bounce_types': bounce_info.get('counts', {}),
                'last_bounce': bounce_info.get('last_bounce'),
                'sms_invalid': contact.contact_metadata.get('sms_invalid', False)
            })
        
        # Sort by total bounces descending
        result.sort(key=lambda x: x['total_bounces'], reverse=True)
        return result
    
    def merge_bounce_metadata(self, contact_id: int, new_bounce_info: dict):
        """
        Merge new bounce information with existing contact bounce metadata.
        
        Args:
            contact_id: Contact ID to update
            new_bounce_info: New bounce information to merge
            
        Returns:
            Updated Contact object or None if not found
        """
        return self.update_contact_bounce_status(contact_id, new_bounce_info)
    
    def find_contacts_by_bounce_type(self, bounce_type: str) -> List[Contact]:
        """
        Find contacts by specific bounce type.
        
        Args:
            bounce_type: Type of bounce to filter by
            
        Returns:
            List of contacts with the specified bounce type
        """
        contacts = self.session.query(Contact).filter(
            Contact.contact_metadata.contains('bounce_info')
        ).all()
        
        result = []
        for contact in contacts:
            if contact.contact_metadata and 'bounce_info' in contact.contact_metadata:
                bounce_info = contact.contact_metadata['bounce_info']
                counts = bounce_info.get('counts', {})
                if counts.get(bounce_type, 0) > 0:
                    result.append(contact)
        
        return result
    
    def count_with_phone(self) -> int:
        """
        Count contacts that have phone numbers.
        
        Returns:
            Count of contacts with non-null phone numbers
        """
        return self.session.query(Contact).filter(
            Contact.phone.isnot(None)
        ).count()
    
    # QuickBooks-specific methods
    
    def find_by_quickbooks_customer_id(self, quickbooks_customer_id: str) -> Optional[Contact]:
        """
        Find contact by QuickBooks customer ID.
        
        Args:
            quickbooks_customer_id: QuickBooks customer ID
            
        Returns:
            Contact or None
        """
        return self.session.query(Contact).filter_by(
            quickbooks_customer_id=quickbooks_customer_id
        ).first()
    
    def find_by_phone_or_email(self, phone: Optional[str], email: Optional[str]) -> Optional[Contact]:
        """
        Find contact by phone number or email address.
        Tries phone first, then email.
        
        Args:
            phone: Phone number to search for
            email: Email address to search for
            
        Returns:
            Contact or None
        """
        if not phone and not email:
            return None
        
        # Try phone first
        if phone:
            contact = self.session.query(Contact).filter_by(phone=phone).first()
            if contact:
                return contact
        
        # Then try email
        if email:
            contact = self.session.query(Contact).filter_by(email=email).first()
            if contact:
                return contact
        
        return None
    
    def find_contacts_needing_quickbooks_sync(self) -> List[Contact]:
        """
        Find contacts that need QuickBooks sync (no QB customer ID).
        
        Returns:
            List of contacts without QuickBooks sync
        """
        return self.session.query(Contact).filter(
            or_(
                Contact.quickbooks_customer_id.is_(None),
                Contact.quickbooks_customer_id == ''
            )
        ).all()
    
    def find_synced_contacts(self) -> List[Contact]:
        """
        Find contacts that are synced with QuickBooks.
        
        Returns:
            List of contacts with QuickBooks sync
        """
        return self.session.query(Contact).filter(
            and_(
                Contact.quickbooks_customer_id.isnot(None),
                Contact.quickbooks_customer_id != ''
            )
        ).all()
    
    def update_quickbooks_sync_info(self, contact_id: int, quickbooks_customer_id: str, 
                                   sync_token: str) -> Optional[Contact]:
        """
        Update QuickBooks sync information for a contact.
        
        Args:
            contact_id: ID of the contact
            quickbooks_customer_id: QuickBooks customer ID
            sync_token: QuickBooks sync token
            
        Returns:
            Updated contact or None if not found
        """
        contact = self.session.query(Contact).filter_by(id=contact_id).first()
        if contact:
            contact.quickbooks_customer_id = quickbooks_customer_id
            contact.quickbooks_sync_token = sync_token
            self.session.flush()
        return contact
    
    def find_customers_only(self) -> List[Contact]:
        """
        Find contacts that are marked as customers.
        
        Returns:
            List of customer contacts
        """
        return self.session.query(Contact).filter_by(customer_type='customer').all()
    
    def bulk_update_quickbooks_info(self, contact_updates: Dict[int, Dict[str, str]]) -> int:
        """
        Bulk update QuickBooks information for multiple contacts.
        
        Args:
            contact_updates: Dictionary of {contact_id: {'quickbooks_customer_id': '...', 'quickbooks_sync_token': '...'}}
            
        Returns:
            Number of contacts updated
        """
        if not contact_updates:
            return 0
            
        contact_ids = list(contact_updates.keys())
        contacts = self.session.query(Contact).filter(
            Contact.id.in_(contact_ids)
        ).all()
        
        updated_count = 0
        for contact in contacts:
            if contact.id in contact_updates:
                update_data = contact_updates[contact.id]
                contact.quickbooks_customer_id = update_data.get('quickbooks_customer_id')
                contact.quickbooks_sync_token = update_data.get('quickbooks_sync_token')
                updated_count += 1
        
        self.session.flush()
        return updated_count
    
    def find_with_email(self) -> List[Contact]:
        """Find all contacts that have an email address.
        
        Returns:
            List of contacts with non-empty email addresses
        """
        return self.session.query(Contact).filter(
            Contact.email.isnot(None),
            Contact.email != ''
        ).all()