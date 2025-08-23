"""
Campaign Template Service
Business logic for managing campaign templates
"""

import re
from typing import List, Optional, Dict, Any
from datetime import datetime

from repositories.campaign_template_repository import CampaignTemplateRepository
from repositories.contact_repository import ContactRepository
from repositories.base_repository import PaginationParams, PaginatedResult, SortOrder
from services.enums import TemplateCategory, TemplateStatus
import logging

logger = logging.getLogger(__name__)


# Custom exceptions for template operations
class TemplateValidationError(Exception):
    """Raised when template validation fails"""
    pass


class TemplateNotFoundError(Exception):
    """Raised when template is not found"""
    pass


class TemplateDuplicateError(Exception):
    """Raised when attempting to create duplicate template"""
    pass


class TemplateVariable:
    """Represents a template variable with metadata"""
    def __init__(self, name: str, description: str = "", default_value: str = ""):
        self.name = name
        self.description = description
        self.default_value = default_value
    
    def to_dict(self):
        return {
            'name': self.name,
            'description': self.description,
            'default_value': self.default_value
        }


class CampaignTemplateService:
    """Service for managing campaign templates"""
    
    # Standard variables available in templates
    AVAILABLE_VARIABLES = {
        'first_name': TemplateVariable('first_name', 'Contact first name'),
        'last_name': TemplateVariable('last_name', 'Contact last name'),
        'phone': TemplateVariable('phone', 'Contact phone number'),
        'email': TemplateVariable('email', 'Contact email address'),
        'company': TemplateVariable('company', 'Contact company name'),
        'property_address': TemplateVariable('property_address', 'Property street address'),
        'property_type': TemplateVariable('property_type', 'Type of property'),
        'property_value': TemplateVariable('property_value', 'Estimated property value'),
        'city': TemplateVariable('city', 'Property city'),
        'state': TemplateVariable('state', 'Property state'),
        'zip': TemplateVariable('zip', 'Property ZIP code')
    }
    
    def __init__(self, template_repository: CampaignTemplateRepository,
                 contact_repository: Optional[ContactRepository] = None):
        """
        Initialize service with repositories.
        
        Args:
            template_repository: Repository for template operations
            contact_repository: Repository for contact operations (optional)
        """
        self.template_repository = template_repository
        self.contact_repository = contact_repository
    
    def create_template(self, name: str, content: str, category: TemplateCategory,
                       description: Optional[str] = None,
                       variables: Optional[List[str]] = None,
                       status: TemplateStatus = TemplateStatus.DRAFT,
                       created_by: Optional[str] = None) -> Dict[str, Any]:
        """
        Create a new campaign template.
        
        Args:
            name: Template name (must be unique)
            content: Template content with variables
            category: Template category
            description: Optional description
            variables: Optional list of variables (auto-extracted if not provided)
            status: Initial status (defaults to DRAFT)
            created_by: User who created the template
            
        Returns:
            Dictionary with created template data
            
        Raises:
            TemplateValidationError: If validation fails
            TemplateDuplicateError: If name already exists
        """
        # Validate content first (before checking duplicates)
        if not content or not content.strip():
            raise TemplateValidationError("Content cannot be empty")
        
        # Check for duplicate name
        existing = self.template_repository.find_one_by(name=name)
        if existing:
            raise TemplateDuplicateError(f"Template with name '{name}' already exists")
        
        # Extract or validate variables
        if variables:
            # Validate that all specified variables exist in content
            content_variables = self.extract_variables(content)
            for var in variables:
                if var not in content_variables:
                    raise TemplateValidationError(f"Variable '{var}' not found in content")
            extracted_variables = variables
        else:
            # Auto-extract variables from content
            extracted_variables = self.extract_variables(content)
        
        # Create template
        template = self.template_repository.create(
            name=name,
            content=content,
            category=category,
            description=description,
            variables=extracted_variables,
            status=status,
            version=1,
            created_by=created_by
        )
        
        self.template_repository.commit()
        
        # Convert to dictionary to avoid exposing database model
        return self._template_to_dict(template)
    
    def get_template(self, template_id: int) -> Dict[str, Any]:
        """
        Get a template by ID.
        
        Args:
            template_id: Template ID
            
        Returns:
            Dictionary with template data
            
        Raises:
            TemplateNotFoundError: If template not found
        """
        template = self.template_repository.get_by_id(template_id)
        if not template:
            raise TemplateNotFoundError(f"Template {template_id} not found")
        return self._template_to_dict(template)
    
    def list_templates(self, category: Optional[TemplateCategory] = None,
                      status: Optional[TemplateStatus] = None,
                      page: int = 1, per_page: int = 20) -> Dict[str, Any]:
        """
        List templates with optional filters and pagination.
        
        Args:
            category: Filter by category
            status: Filter by status
            page: Page number
            per_page: Items per page
            
        Returns:
            Dictionary with paginated template data
        """
        filters = {}
        if category:
            filters['category'] = category
        if status:
            filters['status'] = status
        
        pagination = PaginationParams(page=page, per_page=per_page)
        result = self.template_repository.get_paginated(
            pagination=pagination,
            filters=filters,
            order_by='created_at',
            order=SortOrder.DESC
        )
        
        # Convert to dictionary format
        return {
            'items': [self._template_to_dict(t) for t in result.items],
            'total': result.total,
            'page': result.page,
            'per_page': result.per_page
        }
    
    def search_templates(self, query: str) -> List[Dict[str, Any]]:
        """
        Search templates by text query.
        
        Args:
            query: Search query
            
        Returns:
            List of dictionaries with template data
        """
        templates = self.template_repository.search(
            query=query,
            fields=['name', 'content', 'description']
        )
        return [self._template_to_dict(t) for t in templates]
    
    def get_templates_by_category(self, category: TemplateCategory) -> List[Dict[str, Any]]:
        """
        Get active templates by category.
        
        Args:
            category: Template category
            
        Returns:
            List of dictionaries with template data
        """
        templates = self.template_repository.find_by(
            category=category,
            status=TemplateStatus.ACTIVE
        )
        return [self._template_to_dict(t) for t in templates]
    
    def update_template(self, template_id: int, content: Optional[str] = None,
                       description: Optional[str] = None,
                       category: Optional[TemplateCategory] = None,
                       create_version: bool = False,
                       **kwargs) -> Dict[str, Any]:
        """
        Update a template.
        
        Args:
            template_id: Template ID
            content: New content
            description: New description
            category: New category
            create_version: If True and template is approved, create new version
            **kwargs: Additional fields to update
            
        Returns:
            Dictionary with updated template data
            
        Raises:
            TemplateNotFoundError: If template not found
        """
        # Get the actual template object from repository
        template = self.template_repository.get_by_id(template_id)
        if not template:
            raise TemplateNotFoundError(f"Template {template_id} not found")
        
        # If template is approved/active and content changes, might need new version
        if template.status in [TemplateStatus.APPROVED, TemplateStatus.ACTIVE] and content and create_version:
            # Create new version instead of updating
            new_version = template.version + 1
            # Append version to name to avoid unique constraint violation
            versioned_name = f"{template.name} v{new_version}"
            new_template = self.template_repository.create(
                name=versioned_name,
                content=content or template.content,
                description=description or template.description,
                category=category or template.category,
                variables=self.extract_variables(content) if content else template.variables,
                status=TemplateStatus.DRAFT,
                version=new_version,
                parent_id=template.id
            )
            self.template_repository.commit()
            return self._template_to_dict(new_template)
        
        # Regular update
        updates = {}
        if content:
            updates['content'] = content
            updates['variables'] = self.extract_variables(content)
        if description is not None:
            updates['description'] = description
        if category:
            updates['category'] = category
            
        # Add version increment for any update
        updates['version'] = template.version + 1
        
        # Add any additional kwargs
        updates.update(kwargs)
        
        updated = self.template_repository.update(template, **updates)
        self.template_repository.commit()
        return self._template_to_dict(updated)
    
    def delete_template(self, template_id: int) -> bool:
        """
        Delete a template.
        
        Args:
            template_id: Template ID
            
        Returns:
            True if deleted successfully
            
        Raises:
            TemplateValidationError: If template is in use
        """
        # Get the actual template object from repository
        template = self.template_repository.get_by_id(template_id)
        if not template:
            raise TemplateNotFoundError(f"Template {template_id} not found")
        
        # Check if template is in use
        if template.usage_count > 0:
            raise TemplateValidationError(
                f"Template cannot be deleted because it is in use (used {template.usage_count} times)"
            )
        
        return self.template_repository.delete(template)
    
    def soft_delete_template(self, template_id: int) -> Dict[str, Any]:
        """
        Soft delete (archive) a template.
        
        Args:
            template_id: Template ID
            
        Returns:
            Dictionary with archived template data
        """
        # Get the actual template object from repository
        template = self.template_repository.get_by_id(template_id)
        if not template:
            raise TemplateNotFoundError(f"Template {template_id} not found")
        
        updates = {
            'status': TemplateStatus.ARCHIVED,
            'archived_at': datetime.utcnow(),
            'is_active': False
        }
        
        updated = self.template_repository.update(template, **updates)
        self.template_repository.commit()
        return self._template_to_dict(updated)
    
    def extract_variables(self, content: str) -> List[str]:
        """
        Extract variable names from template content.
        
        Args:
            content: Template content
            
        Returns:
            List of variable names found in content
        """
        # Find all {variable_name} patterns
        pattern = r'\{([a-zA-Z_][a-zA-Z0-9_]*)\}'
        matches = re.findall(pattern, content)
        # Return unique variable names in order of appearance
        seen = set()
        result = []
        for var in matches:
            if var not in seen:
                seen.add(var)
                result.append(var)
        return result
    
    def substitute_variables(self, content: str, data: Dict[str, Any],
                           use_defaults: bool = False) -> str:
        """
        Substitute variables in template content with actual values.
        
        Args:
            content: Template content with variables
            data: Dictionary of variable values
            use_defaults: If True, use default values for missing variables
            
        Returns:
            Content with substituted values
        """
        result = content
        
        # Handle variables with defaults (e.g., {name|default})
        if use_defaults:
            pattern = r'\{([a-zA-Z_][a-zA-Z0-9_]*)\|([^}]*)\}'
            
            def replace_with_default(match):
                var_name = match.group(1)
                default_value = match.group(2)
                return str(data.get(var_name, default_value))
            
            result = re.sub(pattern, replace_with_default, result)
        
        # Handle regular variables
        pattern = r'\{([a-zA-Z_][a-zA-Z0-9_]*)\}'
        
        def replace_variable(match):
            var_name = match.group(1)
            if var_name in data:
                return str(data[var_name])
            return match.group(0)  # Keep original if no value
        
        result = re.sub(pattern, replace_variable, result)
        return result
    
    def preview_template(self, template_id: int, contact_id: Optional[int] = None,
                        custom_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Preview a template with substituted variables.
        
        Args:
            template_id: Template ID
            contact_id: Optional contact ID to pull data from
            custom_data: Optional custom data for variables
            
        Returns:
            Dictionary with preview and metadata
        """
        # Get the actual template object from repository for template data
        template_obj = self.template_repository.get_by_id(template_id)
        if not template_obj:
            raise TemplateNotFoundError(f"Template {template_id} not found")
        
        # Gather variable data
        data = {}
        if contact_id and self.contact_repository:
            contact = self.contact_repository.get_by_id(contact_id)
            if contact:
                # Map contact fields to variables
                data['first_name'] = contact.first_name
                data['last_name'] = contact.last_name
                data['phone'] = contact.phone
                data['email'] = contact.email
                data['company'] = getattr(contact, 'company', '')
                
                # Property fields (if available in contact metadata)
                if hasattr(contact, 'property_address'):
                    data['property_address'] = contact.property_address
                if hasattr(contact, 'property_type'):
                    data['property_type'] = contact.property_type
                if hasattr(contact, 'property_value'):
                    data['property_value'] = contact.property_value
        
        # Override with custom data
        if custom_data:
            data.update(custom_data)
        
        # Substitute variables
        preview = self.substitute_variables(template_obj.content, data)
        
        # Find missing variables
        variables_in_template = template_obj.variables or []
        variables_provided_set = set(data.keys())
        variables_used = [v for v in variables_in_template if v in variables_provided_set]
        missing_variables = [v for v in variables_in_template if v not in variables_provided_set]
        
        return {
            'preview': preview,
            'template_id': template_id,
            'contact_id': contact_id,
            'variables_used': variables_used,
            'missing_variables': missing_variables
        }
    
    def approve_template(self, template_id: int, approved_by: str) -> Dict[str, Any]:
        """
        Approve a template for use.
        
        Args:
            template_id: Template ID
            approved_by: User approving the template
            
        Returns:
            Dictionary with approved template data
            
        Raises:
            TemplateValidationError: If template cannot be approved
        """
        # Get the actual template object from repository
        template = self.template_repository.get_by_id(template_id)
        if not template:
            raise TemplateNotFoundError(f"Template {template_id} not found")
        
        if template.status == TemplateStatus.APPROVED:
            raise TemplateValidationError("Template is already approved")
        
        if template.status == TemplateStatus.ARCHIVED:
            raise TemplateValidationError("Cannot approve archived template")
        
        updates = {
            'status': TemplateStatus.APPROVED,
            'approved_by': approved_by,
            'approved_at': datetime.utcnow()
        }
        
        updated = self.template_repository.update(template, **updates)
        self.template_repository.commit()
        return self._template_to_dict(updated)
    
    def activate_template(self, template_id: int) -> Dict[str, Any]:
        """
        Activate an approved template.
        
        Args:
            template_id: Template ID
            
        Returns:
            Dictionary with activated template data
            
        Raises:
            TemplateValidationError: If template cannot be activated
        """
        # Get the actual template object from repository
        template = self.template_repository.get_by_id(template_id)
        if not template:
            raise TemplateNotFoundError(f"Template {template_id} not found")
        
        if template.status != TemplateStatus.APPROVED:
            raise TemplateValidationError("Template must be approved before activation")
        
        updates = {
            'status': TemplateStatus.ACTIVE,
            'activated_at': datetime.utcnow(),
            'is_active': True
        }
        
        updated = self.template_repository.update(template, **updates)
        self.template_repository.commit()
        return self._template_to_dict(updated)
    
    def archive_template(self, template_id: int) -> Dict[str, Any]:
        """
        Archive a template.
        
        Args:
            template_id: Template ID
            
        Returns:
            Dictionary with archived template data
        """
        return self.soft_delete_template(template_id)
    
    def track_usage(self, template_id: int, campaign_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Track template usage.
        
        Args:
            template_id: Template ID
            campaign_id: Optional campaign ID using the template
            
        Returns:
            Dictionary with updated template data
        """
        # Get the actual template object from repository
        template = self.template_repository.get_by_id(template_id)
        if not template:
            raise TemplateNotFoundError(f"Template {template_id} not found")
        
        updates = {
            'usage_count': template.usage_count + 1,
            'last_used_at': datetime.utcnow()
        }
        
        updated = self.template_repository.update(template, **updates)
        self.template_repository.commit()
        return self._template_to_dict(updated)
    
    def get_template_statistics(self, template_id: int) -> Dict[str, Any]:
        """
        Get usage statistics for a template.
        
        Args:
            template_id: Template ID
            
        Returns:
            Dictionary with statistics
        """
        # Get the actual template object from repository
        template = self.template_repository.get_by_id(template_id)
        if not template:
            raise TemplateNotFoundError(f"Template {template_id} not found")
        
        # Get usage stats from repository
        usage_stats = self.template_repository.get_usage_stats(template_id)
        
        # Calculate time-based stats
        now = datetime.utcnow()
        days_since_created = (now - template.created_at).days if template.created_at else 0
        days_since_last_used = (now - template.last_used_at).days if template.last_used_at else None
        
        return {
            'template_id': template_id,
            'usage_count': template.usage_count,
            'total_campaigns': usage_stats.get('total_campaigns', 0),
            'total_messages_sent': usage_stats.get('total_messages_sent', 0),
            'success_rate': usage_stats.get('success_rate', 0),
            'days_since_created': days_since_created,
            'days_since_last_used': days_since_last_used
        }
    
    def get_template_versions(self, template_id: int) -> List[Dict[str, Any]]:
        """
        Get all versions of a template.
        
        Args:
            template_id: Template ID
            
        Returns:
            List of dictionaries with template version data
        """
        templates = self.template_repository.get_versions(template_id)
        return [self._template_to_dict(t) for t in templates]
    
    def revert_to_version(self, template_id: int, version: int) -> Dict[str, Any]:
        """
        Revert to a previous version of a template.
        
        Args:
            template_id: Template ID
            version: Version number to revert to
            
        Returns:
            Dictionary with new template created from old version
        """
        # Get the actual template objects from repository
        current_template = self.template_repository.get_by_id(template_id)
        if not current_template:
            raise TemplateNotFoundError(f"Template {template_id} not found")
        old_version = self.template_repository.get_version(template_id, version)
        
        if not old_version:
            raise TemplateNotFoundError(f"Version {version} not found for template {template_id}")
        
        # Create new version based on old one
        new_version = current_template.version + 1
        new_template = self.template_repository.create(
            name=current_template.name,
            content=old_version.content,
            description=old_version.description,
            category=old_version.category,
            variables=old_version.variables,
            status=TemplateStatus.DRAFT,
            version=new_version,
            parent_id=template_id
        )
        
        self.template_repository.commit()
        return self._template_to_dict(new_template)
    
    def bulk_update_status(self, template_ids: List[int], 
                          new_status: TemplateStatus) -> Dict[str, Any]:
        """
        Update status for multiple templates.
        
        Args:
            template_ids: List of template IDs
            new_status: New status to set
            
        Returns:
            Dictionary with update results
        """
        updated = 0
        failed = 0
        
        for template_id in template_ids:
            try:
                template = self.template_repository.get_by_id(template_id)
                if template and template.status == TemplateStatus.DRAFT:
                    self.template_repository.update(template, status=new_status)
                    updated += 1
                else:
                    failed += 1
            except Exception as e:
                logger.error(f"Failed to update template {template_id}: {e}")
                failed += 1
        
        self.template_repository.commit()
        
        return {
            'updated': updated,
            'failed': failed
        }
    
    def clone_template(self, template_id: int, new_name: str) -> Dict[str, Any]:
        """
        Clone a template with a new name.
        
        Args:
            template_id: Template ID to clone
            new_name: Name for the cloned template
            
        Returns:
            Dictionary with cloned template data
        """
        # Get the actual template object from repository
        original = self.template_repository.get_by_id(template_id)
        if not original:
            raise TemplateNotFoundError(f"Template {template_id} not found")
        
        # Check for duplicate name
        if self.template_repository.find_one_by(name=new_name):
            raise TemplateDuplicateError(f"Template with name '{new_name}' already exists")
        
        # Create clone
        cloned = self.template_repository.create(
            name=new_name,
            content=original.content,
            description=original.description,
            category=original.category,
            variables=original.variables,
            status=TemplateStatus.DRAFT,
            version=1,
            parent_id=template_id
        )
        
        self.template_repository.commit()
        return self._template_to_dict(cloned)
    
    def validate_template_content(self, content: str) -> bool:
        """
        Validate template content syntax.
        
        Args:
            content: Template content to validate
            
        Returns:
            True if valid
            
        Raises:
            TemplateValidationError: If validation fails
        """
        if not content:
            raise TemplateValidationError("Content cannot be empty")
        
        # Check for unclosed brackets
        open_count = content.count('{')
        close_count = content.count('}')
        if open_count != close_count:
            raise TemplateValidationError("Invalid variable syntax: mismatched brackets")
        
        # Check for invalid variable names
        pattern = r'\{([^}]+)\}'
        matches = re.findall(pattern, content)
        for match in matches:
            # Split on | for default values
            var_name = match.split('|')[0]
            if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', var_name):
                raise TemplateValidationError(f"Invalid variable name: {var_name}")
        
        return True
    
    def validate_variable_names(self, variables: List[str]) -> bool:
        """
        Validate variable names.
        
        Args:
            variables: List of variable names
            
        Returns:
            True if all valid
            
        Raises:
            TemplateValidationError: If validation fails
        """
        for var in variables:
            if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', var):
                raise TemplateValidationError(f"Invalid variable name: {var}")
        return True
    
    def get_available_variables(self) -> Dict[str, Dict[str, str]]:
        """
        Get list of available template variables.
        
        Returns:
            Dictionary of available variables with metadata
        """
        return {
            name: var.to_dict()
            for name, var in self.AVAILABLE_VARIABLES.items()
        }
    
    def _template_to_dict(self, template) -> Dict[str, Any]:
        """
        Convert a template model object to a dictionary.
        
        Args:
            template: Template model object
            
        Returns:
            Dictionary representation of template
        """
        if not template:
            return None
        
        return {
            'id': template.id,
            'name': template.name,
            'content': template.content,
            'category': template.category.value if hasattr(template.category, 'value') else template.category,
            'description': template.description,
            'variables': template.variables,
            'status': template.status.value if hasattr(template.status, 'value') else template.status,
            'version': template.version,
            'usage_count': template.usage_count,
            'is_active': template.is_active,
            'parent_id': template.parent_id,
            'created_by': template.created_by,
            'approved_by': getattr(template, 'approved_by', None),
            'created_at': template.created_at.isoformat() if template.created_at else None,
            'updated_at': template.updated_at.isoformat() if template.updated_at else None,
            'approved_at': template.approved_at.isoformat() if hasattr(template, 'approved_at') and template.approved_at else None,
            'activated_at': template.activated_at.isoformat() if hasattr(template, 'activated_at') and template.activated_at else None,
            'archived_at': template.archived_at.isoformat() if hasattr(template, 'archived_at') and template.archived_at else None,
            'last_used_at': template.last_used_at.isoformat() if template.last_used_at else None
        }