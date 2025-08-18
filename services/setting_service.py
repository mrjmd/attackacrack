"""
SettingService - Business logic for settings management
Implements template retrieval and management functionality.
"""

from typing import List, Optional
from repositories.setting_repository import SettingRepository
from crm_database import Setting
import logging

logger = logging.getLogger(__name__)


class SettingService:
    """Service for settings business logic with repository pattern"""
    
    def __init__(self, repository: SettingRepository):
        """Initialize service with repository dependency"""
        self.repository = repository
    
    def get_template_by_key(self, template_key: str) -> Optional[str]:
        """
        Get template value by key.
        
        Args:
            template_key: The setting key to retrieve
            
        Returns:
            Template value string or None if not found
            
        Raises:
            ValueError: If template_key is empty or None
        """
        if not template_key:
            raise ValueError("Template key cannot be empty")
        
        setting = self.repository.find_one_by(key=template_key)
        return setting.value if setting else None
    
    def get_appointment_reminder_template(self) -> Optional[str]:
        """Get the appointment reminder template"""
        return self.get_template_by_key('appointment_reminder_template')
    
    def get_review_request_template(self) -> Optional[str]:
        """Get the review request template"""
        return self.get_template_by_key('review_request_template')
    
    def get_all_templates(self) -> List[Setting]:
        """
        Get all settings that are templates (keys ending with '_template').
        
        Returns:
            List of Setting objects that are templates
        """
        all_settings = self.repository.get_all()
        return [setting for setting in all_settings if setting.key.endswith('_template')]
    
    def update_template(self, template_key: str, new_value: str) -> bool:
        """
        Update an existing template.
        
        Args:
            template_key: The setting key to update
            new_value: New template value
            
        Returns:
            True if updated successfully, False if template not found
        """
        setting = self.repository.find_one_by(key=template_key)
        if not setting:
            return False
        
        self.repository.update(setting, value=new_value)
        return True
    
    def create_template(self, template_key: str, template_value: str) -> Setting:
        """
        Create a new template setting.
        
        Args:
            template_key: The setting key
            template_value: The template value
            
        Returns:
            Created Setting object
            
        Raises:
            ValueError: If key/value is empty or key already exists
        """
        if not template_key:
            raise ValueError("Template key cannot be empty")
        
        if not template_value:
            raise ValueError("Template value cannot be empty")
        
        if self.repository.exists(key=template_key):
            raise ValueError(f"Setting with key '{template_key}' already exists")
        
        return self.repository.create(key=template_key, value=template_value)
    
    def delete_template(self, template_key: str) -> bool:
        """
        Delete a template setting.
        
        Args:
            template_key: The setting key to delete
            
        Returns:
            True if deleted successfully, False if template not found
        """
        setting = self.repository.find_one_by(key=template_key)
        if not setting:
            return False
        
        return self.repository.delete(setting)