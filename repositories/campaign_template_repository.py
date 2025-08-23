"""
Campaign Template Repository
Handles all database operations for campaign templates
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy import or_, and_, desc, func
from sqlalchemy.orm import joinedload
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from repositories.base_repository import BaseRepository, PaginationParams, PaginatedResult, SortOrder
from crm_database import CampaignTemplate
from services.enums import TemplateCategory, TemplateStatus
import logging

logger = logging.getLogger(__name__)


class CampaignTemplateRepository(BaseRepository[CampaignTemplate]):
    """Repository for campaign template database operations"""
    
    def __init__(self, session):
        """Initialize repository with database session"""
        super().__init__(session, CampaignTemplate)
    
    def search(self, query: str, fields: Optional[List[str]] = None) -> List[CampaignTemplate]:
        """
        Search templates by text query across multiple fields.
        
        Args:
            query: Search query string
            fields: Fields to search in (defaults to name, content, description)
            
        Returns:
            List of matching templates
        """
        try:
            if not query:
                return []
            
            # Default search fields
            if not fields:
                fields = ['name', 'content', 'description']
            
            # Build OR conditions for each field
            conditions = []
            for field in fields:
                if hasattr(CampaignTemplate, field):
                    column = getattr(CampaignTemplate, field)
                    # Case-insensitive search using ILIKE (PostgreSQL) or LIKE (SQLite)
                    conditions.append(func.lower(column).contains(query.lower()))
            
            if not conditions:
                return []
            
            # Execute search query
            return self.session.query(CampaignTemplate).filter(
                or_(*conditions)
            ).all()
            
        except SQLAlchemyError as e:
            logger.error(f"Error searching templates: {e}")
            return []
    
    def find_active_by_category(self, category: TemplateCategory) -> List[CampaignTemplate]:
        """
        Find active templates by category.
        
        Args:
            category: Template category
            
        Returns:
            List of active templates in the category
        """
        return self.find_by(category=category, status=TemplateStatus.ACTIVE, is_active=True)
    
    def get_versions(self, template_id: int) -> List[CampaignTemplate]:
        """
        Get all versions of a template.
        
        Args:
            template_id: Original template ID
            
        Returns:
            List of all versions ordered by version number
        """
        try:
            # Find all templates with matching ID or parent_id
            return self.session.query(CampaignTemplate).filter(
                or_(
                    CampaignTemplate.id == template_id,
                    CampaignTemplate.parent_id == template_id
                )
            ).order_by(CampaignTemplate.version).all()
        except SQLAlchemyError as e:
            logger.error(f"Error getting template versions: {e}")
            return []
    
    def get_version(self, template_id: int, version: int) -> Optional[CampaignTemplate]:
        """
        Get a specific version of a template.
        
        Args:
            template_id: Template ID
            version: Version number
            
        Returns:
            Template with specific version or None
        """
        return self.find_one_by(id=template_id, version=version)
    
    def get_latest_version(self, template_id: int) -> Optional[CampaignTemplate]:
        """
        Get the latest version of a template.
        
        Args:
            template_id: Original template ID
            
        Returns:
            Latest version of the template
        """
        try:
            return self.session.query(CampaignTemplate).filter(
                or_(
                    CampaignTemplate.id == template_id,
                    CampaignTemplate.parent_id == template_id
                )
            ).order_by(desc(CampaignTemplate.version)).first()
        except SQLAlchemyError as e:
            logger.error(f"Error getting latest template version: {e}")
            return None
    
    def get_usage_stats(self, template_id: int) -> Dict[str, Any]:
        """
        Get usage statistics for a template.
        
        Args:
            template_id: Template ID
            
        Returns:
            Dictionary with usage statistics
        """
        try:
            # For now, return basic stats from the template itself
            # In a full implementation, this would join with campaign tables
            template = self.get_by_id(template_id)
            if not template:
                return {}
            
            # Mock stats for now - would normally aggregate from campaigns
            return {
                'template_id': template_id,
                'total_campaigns': template.usage_count // 5 if template.usage_count else 0,  # Estimate
                'total_messages_sent': template.usage_count * 10 if template.usage_count else 0,  # Estimate
                'successful_messages': int(template.usage_count * 9.5) if template.usage_count else 0,  # 95% success
                'success_rate': 0.95 if template.usage_count else 0
            }
        except SQLAlchemyError as e:
            logger.error(f"Error getting usage stats: {e}")
            return {}
    
    def get_most_used_templates(self, limit: int = 10) -> List[CampaignTemplate]:
        """
        Get the most frequently used templates.
        
        Args:
            limit: Maximum number of templates to return
            
        Returns:
            List of most used templates
        """
        try:
            return self.session.query(CampaignTemplate).filter_by(
                is_active=True
            ).order_by(desc(CampaignTemplate.usage_count)).limit(limit).all()
        except SQLAlchemyError as e:
            logger.error(f"Error getting most used templates: {e}")
            return []
    
    def increment_usage_count(self, template_id: int) -> Optional[CampaignTemplate]:
        """
        Increment the usage count for a template.
        
        Args:
            template_id: Template ID
            
        Returns:
            Updated template or None
        """
        try:
            template = self.session.get(CampaignTemplate, template_id)
            if template:
                template.usage_count += 1
                template.last_used_at = datetime.utcnow()
                self.session.flush()
                return template
            return None
        except SQLAlchemyError as e:
            logger.error(f"Error incrementing usage count: {e}")
            self.session.rollback()
            return None
    
    def exists_except(self, name: str, exclude_id: int) -> bool:
        """
        Check if a template with the given name exists, excluding a specific ID.
        
        Args:
            name: Template name to check
            exclude_id: ID to exclude from check
            
        Returns:
            True if another template with this name exists
        """
        try:
            result = self.session.query(CampaignTemplate).filter(
                CampaignTemplate.name == name
            ).filter(
                CampaignTemplate.id != exclude_id
            ).first()
            return result is not None
        except SQLAlchemyError as e:
            logger.error(f"Error checking template existence: {e}")
            return False
    
    def find_unused_templates(self) -> List[CampaignTemplate]:
        """
        Find templates that have never been used.
        
        Returns:
            List of unused templates
        """
        return self.find_by(usage_count=0)
    
    def find_recently_used(self, days: int = 7, limit: int = 10) -> List[CampaignTemplate]:
        """
        Find recently used templates.
        
        Args:
            days: Number of days to look back
            limit: Maximum number of templates to return
            
        Returns:
            List of recently used templates
        """
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            return self.session.query(CampaignTemplate).filter(
                CampaignTemplate.last_used_at >= cutoff_date
            ).order_by(desc(CampaignTemplate.last_used_at)).limit(limit).all()
        except SQLAlchemyError as e:
            logger.error(f"Error finding recently used templates: {e}")
            return []
    
    def get_children(self, parent_id: int) -> List[CampaignTemplate]:
        """
        Get child templates (versions) of a parent template.
        
        Args:
            parent_id: Parent template ID
            
        Returns:
            List of child templates
        """
        return self.find_by(parent_id=parent_id)
    
    def get_with_campaigns(self) -> List[CampaignTemplate]:
        """
        Get templates with their campaign relationships eagerly loaded.
        
        Returns:
            List of templates with campaigns loaded
        """
        try:
            # Note: campaigns relationship would need to be defined in the model
            # For now, just return all templates
            return self.session.query(CampaignTemplate).all()
        except SQLAlchemyError as e:
            logger.error(f"Error getting templates with campaigns: {e}")
            return []
    
    def get_paginated(self, 
                     pagination: PaginationParams,
                     filters: Optional[Dict[str, Any]] = None,
                     order_by: Optional[str] = None,
                     order: SortOrder = SortOrder.ASC) -> PaginatedResult[CampaignTemplate]:
        """
        Get paginated templates with filtering and sorting.
        
        Args:
            pagination: Pagination parameters
            filters: Optional filters to apply
            order_by: Field to order by
            order: Sort order
            
        Returns:
            Paginated result with templates
        """
        try:
            # Build base query
            query = self.session.query(CampaignTemplate)
            
            # Apply filters
            if filters:
                for field, value in filters.items():
                    if hasattr(CampaignTemplate, field):
                        if field == 'status' and value:
                            query = query.filter(CampaignTemplate.status == value)
                        elif field == 'category' and value:
                            query = query.filter(CampaignTemplate.category == value)
                        elif field == 'is_active' and value is not None:
                            query = query.filter(CampaignTemplate.is_active == value)
                        elif value is not None:
                            query = query.filter(getattr(CampaignTemplate, field) == value)
            
            # Apply ordering
            if order_by:
                order_field = getattr(CampaignTemplate, order_by, None)
                if order_field:
                    query = query.order_by(
                        desc(order_field) if order == SortOrder.DESC else order_field
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
            logger.error(f"Error getting paginated templates: {e}")
            return PaginatedResult(items=[], total=0, page=1, per_page=pagination.per_page)