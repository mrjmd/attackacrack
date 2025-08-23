"""
Service layer enums
These enums are used by services and should match the database enums
but allow services to work without importing database models
"""

from enum import Enum


class TemplateCategory(str, Enum):
    """Categories for campaign templates"""
    PROMOTIONAL = 'promotional'
    REMINDER = 'reminder'
    FOLLOW_UP = 'follow_up'
    NOTIFICATION = 'notification'
    CUSTOM = 'custom'


class TemplateStatus(str, Enum):
    """Status options for campaign templates"""
    DRAFT = 'draft'
    APPROVED = 'approved'
    ACTIVE = 'active'
    ARCHIVED = 'archived'