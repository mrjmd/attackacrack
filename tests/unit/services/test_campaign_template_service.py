"""
Unit tests for CampaignTemplateService
Tests template CRUD operations, variable substitution, and business logic
Following TDD - these tests should FAIL initially (Red phase)
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime
from typing import Dict, List, Optional

# These imports will fail initially - that's expected in TDD
from services.campaign_template_service import (
    CampaignTemplateService,
    TemplateVariable,
    TemplateValidationError,
    TemplateNotFoundError,
    TemplateDuplicateError
)
from services.enums import TemplateCategory, TemplateStatus
from repositories.campaign_template_repository import CampaignTemplateRepository
from crm_database import CampaignTemplate, Contact


class TestCampaignTemplateService:
    """Test suite for CampaignTemplateService"""
    
    @pytest.fixture
    def mock_repository(self):
        """Create a mock repository"""
        repository = Mock(spec=CampaignTemplateRepository)
        return repository
    
    @pytest.fixture
    def mock_contact_repository(self):
        """Create a mock contact repository"""
        from repositories.contact_repository import ContactRepository
        repository = Mock(spec=ContactRepository)
        return repository
    
    @pytest.fixture
    def service(self, mock_repository, mock_contact_repository):
        """Create service instance with mocked dependencies"""
        return CampaignTemplateService(
            template_repository=mock_repository,
            contact_repository=mock_contact_repository
        )
    
    @pytest.fixture
    def sample_template_data(self):
        """Sample template data for testing"""
        return {
            'name': 'Welcome Message',
            'content': 'Hi {first_name}, welcome to Attack-a-Crack! Your property at {property_address} is important to us.',
            'category': TemplateCategory.PROMOTIONAL,
            'description': 'Welcome message for new contacts',
            'variables': ['first_name', 'property_address'],
            'status': TemplateStatus.DRAFT
        }
    
    @pytest.fixture
    def sample_template(self, sample_template_data):
        """Create a sample template model"""
        template = Mock(spec=CampaignTemplate)
        template.id = 1
        template.name = sample_template_data['name']
        template.content = sample_template_data['content']
        template.category = sample_template_data['category']
        template.description = sample_template_data['description']
        template.variables = sample_template_data['variables']
        template.status = sample_template_data['status']
        template.version = 1
        template.usage_count = 0
        template.is_active = False
        template.parent_id = None
        template.created_by = None
        template.created_at = datetime.now()
        template.updated_at = datetime.now()
        return template
    
    @pytest.fixture
    def sample_contact(self):
        """Create a sample contact for testing"""
        contact = Mock(spec=Contact)
        contact.id = 1
        contact.first_name = 'John'
        contact.last_name = 'Doe'
        contact.phone = '+16175551234'
        contact.email = 'john@example.com'
        contact.company = 'Test Corp'
        # Property-specific fields
        contact.property_address = '123 Main St, Boston, MA'
        contact.property_type = 'Single Family'
        contact.property_value = 500000
        return contact
    
    # CREATE Tests
    
    def test_create_template_success(self, service, mock_repository, sample_template_data, sample_template):
        """Test successful template creation"""
        # Arrange
        mock_repository.find_one_by.return_value = None  # No duplicate
        mock_repository.create.return_value = sample_template
        
        # Act
        result = service.create_template(**sample_template_data)
        
        # Assert
        assert result['id'] == 1
        assert result['name'] == sample_template_data['name']
        assert result['content'] == sample_template_data['content']
        assert result['category'] == sample_template_data['category'].value
        assert result['status'] == TemplateStatus.DRAFT.value
        assert result['version'] == 1
        mock_repository.find_one_by.assert_called_once_with(name=sample_template_data['name'])
        mock_repository.create.assert_called_once()
    
    def test_create_template_duplicate_name(self, service, mock_repository, sample_template_data):
        """Test template creation with duplicate name"""
        # Arrange
        existing_template = Mock()
        mock_repository.find_one_by.return_value = existing_template
        
        # Act & Assert
        with pytest.raises(TemplateDuplicateError) as exc_info:
            service.create_template(**sample_template_data)
        
        assert 'already exists' in str(exc_info.value)
        mock_repository.create.assert_not_called()
    
    def test_create_template_auto_extract_variables(self, service, mock_repository):
        """Test automatic variable extraction from content"""
        # Arrange
        template_data = {
            'name': 'Test Template',
            'content': 'Hello {first_name} {last_name}, your {property_type} at {property_address} is valued at ${property_value}',
            'category': TemplateCategory.FOLLOW_UP
        }
        mock_repository.find_one_by.return_value = None
        
        # Act
        result = service.create_template(**template_data)
        
        # Assert
        mock_repository.create.assert_called_once()
        create_args = mock_repository.create.call_args[1]
        assert set(create_args['variables']) == {'first_name', 'last_name', 'property_type', 'property_address', 'property_value'}
    
    def test_create_template_invalid_content(self, service, mock_repository):
        """Test template creation with invalid content"""
        # Arrange
        template_data = {
            'name': 'Invalid Template',
            'content': '',  # Empty content
            'category': TemplateCategory.REMINDER
        }
        mock_repository.find_one_by.return_value = None  # No duplicate
        
        # Act & Assert
        with pytest.raises(TemplateValidationError) as exc_info:
            service.create_template(**template_data)
        
        assert 'Content cannot be empty' in str(exc_info.value)
        mock_repository.create.assert_not_called()
    
    def test_create_template_invalid_variables(self, service, mock_repository):
        """Test template creation with mismatched variables"""
        # Arrange
        template_data = {
            'name': 'Test Template',
            'content': 'Hello {first_name}',
            'variables': ['first_name', 'last_name'],  # last_name not in content
            'category': TemplateCategory.PROMOTIONAL
        }
        mock_repository.find_one_by.return_value = None  # No duplicate
        
        # Act & Assert
        with pytest.raises(TemplateValidationError) as exc_info:
            service.create_template(**template_data)
        
        assert 'not found in content' in str(exc_info.value)
        mock_repository.create.assert_not_called()
    
    # READ Tests
    
    def test_get_template_by_id_success(self, service, mock_repository, sample_template):
        """Test getting template by ID"""
        # Arrange
        mock_repository.get_by_id.return_value = sample_template
        
        # Act
        result = service.get_template(1)
        
        # Assert
        assert result['id'] == sample_template.id
        assert result['name'] == sample_template.name
        assert result['content'] == sample_template.content
        mock_repository.get_by_id.assert_called_once_with(1)
    
    def test_get_template_by_id_not_found(self, service, mock_repository):
        """Test getting non-existent template"""
        # Arrange
        mock_repository.get_by_id.return_value = None
        
        # Act & Assert
        with pytest.raises(TemplateNotFoundError) as exc_info:
            service.get_template(999)
        
        assert 'Template 999 not found' in str(exc_info.value)
    
    def test_list_templates_with_filters(self, service, mock_repository):
        """Test listing templates with filters"""
        # Arrange
        templates = []
        for i in range(3):
            template = Mock(spec=CampaignTemplate)
            template.id = i + 1
            template.name = f'Template {i}'
            template.content = f'Content {i}'
            template.category = TemplateCategory.PROMOTIONAL
            template.status = TemplateStatus.ACTIVE
            template.version = 1
            template.usage_count = 0
            template.is_active = True
            template.parent_id = None
            template.created_by = None
            template.created_at = datetime.now()
            template.updated_at = datetime.now()
            template.description = None
            template.variables = []
            templates.append(template)
            
        paginated_result = Mock()
        paginated_result.items = templates
        paginated_result.total = 3
        paginated_result.page = 1
        paginated_result.per_page = 20
        mock_repository.get_paginated.return_value = paginated_result
        
        # Act
        result = service.list_templates(
            category=TemplateCategory.PROMOTIONAL,
            status=TemplateStatus.ACTIVE,
            page=1,
            per_page=20
        )
        
        # Assert
        assert len(result['items']) == 3
        assert result['total'] == 3
        assert result['page'] == 1
        assert result['per_page'] == 20
        mock_repository.get_paginated.assert_called_once()
        call_args = mock_repository.get_paginated.call_args
        assert call_args[1]['filters']['category'] == TemplateCategory.PROMOTIONAL
        assert call_args[1]['filters']['status'] == TemplateStatus.ACTIVE
    
    def test_search_templates(self, service, mock_repository):
        """Test searching templates by query"""
        # Arrange
        templates = []
        for i in range(2):
            template = Mock(spec=CampaignTemplate)
            template.id = i + 1
            template.name = f'Welcome Template {i}'
            template.content = f'Welcome content {i}'
            template.category = TemplateCategory.PROMOTIONAL
            template.status = TemplateStatus.ACTIVE
            template.version = 1
            template.usage_count = 0
            template.is_active = True
            template.parent_id = None
            template.created_by = None
            template.created_at = datetime.now()
            template.updated_at = datetime.now()
            template.description = None
            template.variables = []
            templates.append(template)
            
        mock_repository.search.return_value = templates
        
        # Act
        result = service.search_templates('welcome')
        
        # Assert
        assert len(result) == 2
        assert result[0]['name'] == 'Welcome Template 0'
        assert result[1]['name'] == 'Welcome Template 1'
        mock_repository.search.assert_called_once_with(
            query='welcome',
            fields=['name', 'content', 'description']
        )
    
    def test_get_templates_by_category(self, service, mock_repository):
        """Test getting templates by category"""
        # Arrange
        templates = []
        for i in range(3):
            template = Mock(spec=CampaignTemplate)
            template.id = i + 1
            template.name = f'Reminder Template {i}'
            template.content = f'Reminder content {i}'
            template.category = TemplateCategory.REMINDER
            template.status = TemplateStatus.ACTIVE
            template.version = 1
            template.usage_count = 0
            template.is_active = True
            template.parent_id = None
            template.created_by = None
            template.created_at = datetime.now()
            template.updated_at = datetime.now()
            template.description = None
            template.variables = []
            templates.append(template)
            
        mock_repository.find_by.return_value = templates
        
        # Act
        result = service.get_templates_by_category(TemplateCategory.REMINDER)
        
        # Assert
        assert len(result) == 3
        assert all(template['category'] == TemplateCategory.REMINDER.value for template in result)
        mock_repository.find_by.assert_called_once_with(
            category=TemplateCategory.REMINDER,
            status=TemplateStatus.ACTIVE
        )
    
    # UPDATE Tests
    
    def test_update_template_success(self, service, mock_repository, sample_template):
        """Test successful template update"""
        # Arrange
        mock_repository.get_by_id.return_value = sample_template
        updated_template = Mock(spec=CampaignTemplate)
        updated_template.id = 1
        updated_template.name = sample_template.name
        updated_template.content = 'Updated content {first_name}'
        updated_template.description = 'Updated description'
        updated_template.category = sample_template.category
        updated_template.status = sample_template.status
        updated_template.variables = ['first_name']
        updated_template.version = 2
        updated_template.usage_count = 0
        updated_template.is_active = False
        updated_template.parent_id = None
        updated_template.created_by = None
        updated_template.created_at = sample_template.created_at
        updated_template.updated_at = datetime.now()
        mock_repository.update.return_value = updated_template
        
        updates = {
            'content': 'Updated content {first_name}',
            'description': 'Updated description'
        }
        
        # Act
        result = service.update_template(1, **updates)
        
        # Assert
        assert result['id'] == 1
        assert result['content'] == updates['content']
        assert result['description'] == updates['description']
        assert result['version'] == 2
        mock_repository.update.assert_called_once()
        update_args = mock_repository.update.call_args[1]
        assert update_args['content'] == updates['content']
        assert update_args['description'] == updates['description']
        assert 'version' in update_args  # Version should be incremented
    
    def test_update_template_not_found(self, service, mock_repository):
        """Test updating non-existent template"""
        # Arrange
        mock_repository.get_by_id.return_value = None
        
        # Act & Assert
        with pytest.raises(TemplateNotFoundError):
            service.update_template(999, content='New content')
    
    def test_update_template_approved_requires_new_version(self, service, mock_repository):
        """Test that updating approved template creates new version"""
        # Arrange
        approved_template = Mock(spec=CampaignTemplate)
        approved_template.id = 1
        approved_template.name = 'Test Template'
        approved_template.content = 'Old content'
        approved_template.description = 'Test description'
        approved_template.category = TemplateCategory.PROMOTIONAL
        approved_template.variables = ['test']
        approved_template.status = TemplateStatus.APPROVED
        approved_template.version = 1
        approved_template.usage_count = 0
        approved_template.is_active = True
        approved_template.parent_id = None
        approved_template.created_by = None
        approved_template.created_at = datetime.now()
        approved_template.updated_at = datetime.now()
        mock_repository.get_by_id.return_value = approved_template
        
        # Mock the new version template
        new_version_template = Mock(spec=CampaignTemplate)
        new_version_template.id = 2
        new_version_template.name = approved_template.name
        new_version_template.content = 'New content'
        new_version_template.description = approved_template.description
        new_version_template.category = approved_template.category
        new_version_template.status = TemplateStatus.DRAFT
        new_version_template.variables = ['test']
        new_version_template.version = 2
        new_version_template.usage_count = 0
        new_version_template.is_active = False
        new_version_template.parent_id = 1
        new_version_template.created_by = None
        new_version_template.created_at = datetime.now()
        new_version_template.updated_at = datetime.now()
        mock_repository.create.return_value = new_version_template
        
        # Act
        result = service.update_template(1, content='New content', create_version=True)
        
        # Assert
        assert result['id'] == 2
        assert result['version'] == 2
        assert result['parent_id'] == 1
        assert result['content'] == 'New content'
        mock_repository.create.assert_called_once()  # New version created
        create_args = mock_repository.create.call_args[1]
        assert create_args['version'] == 2
        assert create_args['parent_id'] == 1
    
    # DELETE Tests
    
    def test_delete_template_success(self, service, mock_repository, sample_template):
        """Test successful template deletion"""
        # Arrange
        sample_template.usage_count = 0
        mock_repository.get_by_id.return_value = sample_template
        mock_repository.delete.return_value = True
        
        # Act
        result = service.delete_template(1)
        
        # Assert
        assert result is True
        mock_repository.delete.assert_called_once_with(sample_template)
    
    def test_delete_template_in_use(self, service, mock_repository, sample_template):
        """Test deleting template that's in use"""
        # Arrange
        sample_template.usage_count = 5
        mock_repository.get_by_id.return_value = sample_template
        
        # Act & Assert
        with pytest.raises(TemplateValidationError) as exc_info:
            service.delete_template(1)
        
        assert 'cannot be deleted' in str(exc_info.value)
        assert 'in use' in str(exc_info.value)
        mock_repository.delete.assert_not_called()
    
    def test_soft_delete_template(self, service, mock_repository, sample_template):
        """Test soft deleting a template"""
        # Arrange
        mock_repository.get_by_id.return_value = sample_template
        
        # Mock the updated template
        archived_template = Mock(spec=CampaignTemplate)
        archived_template.id = sample_template.id
        archived_template.name = sample_template.name
        archived_template.content = sample_template.content
        archived_template.description = sample_template.description
        archived_template.category = sample_template.category
        archived_template.status = TemplateStatus.ARCHIVED
        archived_template.variables = sample_template.variables
        archived_template.version = sample_template.version
        archived_template.usage_count = sample_template.usage_count
        archived_template.is_active = False
        archived_template.parent_id = sample_template.parent_id
        archived_template.created_by = sample_template.created_by
        archived_template.created_at = sample_template.created_at
        archived_template.updated_at = datetime.now()
        mock_repository.update.return_value = archived_template
        
        # Act
        result = service.soft_delete_template(1)
        
        # Assert
        assert result['status'] == TemplateStatus.ARCHIVED.value
        assert result['is_active'] == False
        mock_repository.update.assert_called_once()
        update_args = mock_repository.update.call_args[1]
        assert update_args['status'] == TemplateStatus.ARCHIVED
        assert update_args['archived_at'] is not None
    
    # VARIABLE SUBSTITUTION Tests
    
    def test_preview_template_with_contact(self, service, mock_repository, mock_contact_repository, sample_template, sample_contact):
        """Test previewing template with contact data"""
        # Arrange
        mock_repository.get_by_id.return_value = sample_template
        mock_contact_repository.get_by_id.return_value = sample_contact
        
        # Act
        result = service.preview_template(1, contact_id=1)
        
        # Assert
        assert 'John' in result['preview']
        assert '123 Main St, Boston, MA' in result['preview']
        assert result['template_id'] == 1
        assert result['contact_id'] == 1
        assert result['variables_used'] == ['first_name', 'property_address']
    
    def test_preview_template_with_custom_data(self, service, mock_repository, sample_template):
        """Test previewing template with custom data"""
        # Arrange
        mock_repository.get_by_id.return_value = sample_template
        custom_data = {
            'first_name': 'Jane',
            'property_address': '456 Oak Ave, Cambridge, MA'
        }
        
        # Act
        result = service.preview_template(1, custom_data=custom_data)
        
        # Assert
        assert 'Jane' in result['preview']
        assert '456 Oak Ave, Cambridge, MA' in result['preview']
        assert result['template_id'] == 1
        assert result['variables_used'] == ['first_name', 'property_address']
    
    def test_preview_template_missing_variables(self, service, mock_repository, sample_template):
        """Test previewing template with missing variables"""
        # Arrange
        mock_repository.get_by_id.return_value = sample_template
        incomplete_data = {'first_name': 'Bob'}  # Missing property_address
        
        # Act
        result = service.preview_template(1, custom_data=incomplete_data)
        
        # Assert
        assert 'Bob' in result['preview']
        assert '{property_address}' in result['preview']  # Unsubstituted variable
        assert 'missing_variables' in result
        assert 'property_address' in result['missing_variables']
    
    def test_substitute_variables(self, service):
        """Test variable substitution logic"""
        # Arrange
        template_content = "Hello {first_name} {last_name}, your {property_type} is at {property_address}"
        data = {
            'first_name': 'Alice',
            'last_name': 'Smith',
            'property_type': 'Condo',
            'property_address': '789 Park St'
        }
        
        # Act
        result = service.substitute_variables(template_content, data)
        
        # Assert
        assert result == "Hello Alice Smith, your Condo is at 789 Park St"
    
    def test_substitute_variables_with_defaults(self, service):
        """Test variable substitution with default values"""
        # Arrange
        template_content = "Hi {first_name|there}, welcome to {company|Attack-a-Crack}"
        data = {'first_name': 'Bob'}
        
        # Act
        result = service.substitute_variables(template_content, data, use_defaults=True)
        
        # Assert
        assert result == "Hi Bob, welcome to Attack-a-Crack"
    
    def test_extract_variables(self, service):
        """Test extracting variables from template content"""
        # Arrange
        content = "Hello {first_name}, your {property_type} at {property_address} is worth ${property_value}"
        
        # Act
        variables = service.extract_variables(content)
        
        # Assert
        assert variables == ['first_name', 'property_type', 'property_address', 'property_value']
    
    # STATUS MANAGEMENT Tests
    
    def test_approve_template(self, service, mock_repository, sample_template):
        """Test approving a draft template"""
        # Arrange
        sample_template.status = TemplateStatus.DRAFT
        mock_repository.get_by_id.return_value = sample_template
        
        # Mock the approved template
        approved_template = Mock(spec=CampaignTemplate)
        approved_template.id = sample_template.id
        approved_template.name = sample_template.name
        approved_template.content = sample_template.content
        approved_template.description = sample_template.description
        approved_template.category = sample_template.category
        approved_template.status = TemplateStatus.APPROVED
        approved_template.variables = sample_template.variables
        approved_template.version = sample_template.version
        approved_template.usage_count = sample_template.usage_count
        approved_template.is_active = False
        approved_template.parent_id = sample_template.parent_id
        approved_template.created_by = sample_template.created_by
        approved_template.approved_by = 'admin'
        approved_template.created_at = sample_template.created_at
        approved_template.updated_at = datetime.now()
        approved_template.approved_at = datetime.now()
        mock_repository.update.return_value = approved_template
        
        # Act
        result = service.approve_template(1, approved_by='admin')
        
        # Assert
        assert result['status'] == TemplateStatus.APPROVED.value
        assert result['approved_by'] == 'admin'
        assert result['approved_at'] is not None
        mock_repository.update.assert_called_once()
        update_args = mock_repository.update.call_args[1]
        assert update_args['status'] == TemplateStatus.APPROVED
        assert update_args['approved_by'] == 'admin'
        assert update_args['approved_at'] is not None
    
    def test_approve_already_approved_template(self, service, mock_repository, sample_template):
        """Test approving an already approved template"""
        # Arrange
        sample_template.status = TemplateStatus.APPROVED
        mock_repository.get_by_id.return_value = sample_template
        
        # Act & Assert
        with pytest.raises(TemplateValidationError) as exc_info:
            service.approve_template(1, approved_by='admin')
        
        assert 'already approved' in str(exc_info.value)
    
    def test_activate_template(self, service, mock_repository, sample_template):
        """Test activating an approved template"""
        # Arrange
        sample_template.status = TemplateStatus.APPROVED
        mock_repository.get_by_id.return_value = sample_template
        
        # Mock the activated template
        activated_template = Mock(spec=CampaignTemplate)
        activated_template.id = sample_template.id
        activated_template.name = sample_template.name
        activated_template.content = sample_template.content
        activated_template.description = sample_template.description
        activated_template.category = sample_template.category
        activated_template.status = TemplateStatus.ACTIVE
        activated_template.variables = sample_template.variables
        activated_template.version = sample_template.version
        activated_template.usage_count = sample_template.usage_count
        activated_template.is_active = True
        activated_template.parent_id = sample_template.parent_id
        activated_template.created_by = sample_template.created_by
        activated_template.created_at = sample_template.created_at
        activated_template.updated_at = datetime.now()
        activated_template.activated_at = datetime.now()
        mock_repository.update.return_value = activated_template
        
        # Act
        result = service.activate_template(1)
        
        # Assert
        assert result['status'] == TemplateStatus.ACTIVE.value
        assert result['is_active'] == True
        assert result['activated_at'] is not None
        mock_repository.update.assert_called_once()
        update_args = mock_repository.update.call_args[1]
        assert update_args['status'] == TemplateStatus.ACTIVE
        assert update_args['activated_at'] is not None
    
    def test_activate_unapproved_template(self, service, mock_repository, sample_template):
        """Test activating a draft template (should fail)"""
        # Arrange
        sample_template.status = TemplateStatus.DRAFT
        mock_repository.get_by_id.return_value = sample_template
        
        # Act & Assert
        with pytest.raises(TemplateValidationError) as exc_info:
            service.activate_template(1)
        
        assert 'must be approved' in str(exc_info.value)
    
    # USAGE TRACKING Tests
    
    def test_track_template_usage(self, service, mock_repository, sample_template):
        """Test tracking template usage"""
        # Arrange
        sample_template.usage_count = 10
        mock_repository.get_by_id.return_value = sample_template
        
        # Mock the updated template
        updated_template = Mock(spec=CampaignTemplate)
        updated_template.id = sample_template.id
        updated_template.name = sample_template.name
        updated_template.content = sample_template.content
        updated_template.description = sample_template.description
        updated_template.category = sample_template.category
        updated_template.status = sample_template.status
        updated_template.variables = sample_template.variables
        updated_template.version = sample_template.version
        updated_template.usage_count = 11
        updated_template.is_active = sample_template.is_active
        updated_template.parent_id = sample_template.parent_id
        updated_template.created_by = sample_template.created_by
        updated_template.created_at = sample_template.created_at
        updated_template.updated_at = datetime.now()
        updated_template.last_used_at = datetime.now()
        mock_repository.update.return_value = updated_template
        
        # Act
        result = service.track_usage(1, campaign_id=123)
        
        # Assert
        assert result['usage_count'] == 11
        assert result['last_used_at'] is not None
        mock_repository.update.assert_called_once()
        update_args = mock_repository.update.call_args[1]
        assert update_args['usage_count'] == 11
        assert update_args['last_used_at'] is not None
    
    def test_get_template_statistics(self, service, mock_repository, sample_template):
        """Test getting template usage statistics"""
        # Arrange
        sample_template.usage_count = 50
        sample_template.created_at = datetime(2025, 1, 1)
        sample_template.last_used_at = datetime(2025, 8, 1)
        mock_repository.get_by_id.return_value = sample_template
        
        # Mocked campaign usage data
        mock_repository.get_usage_stats.return_value = {
            'total_campaigns': 10,
            'total_messages_sent': 500,
            'success_rate': 0.95
        }
        
        # Act
        result = service.get_template_statistics(1)
        
        # Assert
        assert result['template_id'] == 1
        assert result['usage_count'] == 50
        assert result['total_campaigns'] == 10
        assert result['total_messages_sent'] == 500
        assert result['success_rate'] == 0.95
        assert 'days_since_created' in result
        assert 'days_since_last_used' in result
    
    # VERSIONING Tests
    
    def test_get_template_versions(self, service, mock_repository):
        """Test getting all versions of a template"""
        # Arrange
        versions = []
        for i in range(3):
            version = Mock(spec=CampaignTemplate)
            version.id = i + 10
            version.name = f'Template Version {i + 1}'
            version.content = f'Content v{i + 1}'
            version.category = TemplateCategory.PROMOTIONAL
            version.status = TemplateStatus.DRAFT if i == 2 else TemplateStatus.ACTIVE
            version.variables = []
            version.version = i + 1
            version.usage_count = 0
            version.is_active = i < 2
            version.parent_id = 1 if i > 0 else None
            version.created_by = None
            version.created_at = datetime.now()
            version.updated_at = datetime.now()
            version.description = None
            versions.append(version)
            
        mock_repository.get_versions.return_value = versions
        
        # Act
        result = service.get_template_versions(1)
        
        # Assert
        assert len(result) == 3
        assert result[0]['version'] == 1
        assert result[2]['version'] == 3
        mock_repository.get_versions.assert_called_once_with(1)
    
    def test_revert_to_version(self, service, mock_repository):
        """Test reverting to a previous template version"""
        # Arrange
        current_template = Mock(spec=CampaignTemplate)
        current_template.id = 1
        current_template.name = 'Test Template'
        current_template.version = 3
        current_template.category = TemplateCategory.PROMOTIONAL
        current_template.status = TemplateStatus.ACTIVE
        current_template.description = 'Test description'
        
        old_version = Mock(spec=CampaignTemplate)
        old_version.id = 2
        old_version.name = 'Test Template'
        old_version.version = 1
        old_version.content = 'Old content'
        old_version.category = TemplateCategory.PROMOTIONAL
        old_version.status = TemplateStatus.ACTIVE
        old_version.description = 'Test description'
        old_version.variables = ['old_var']
        
        # Mock the new reverted template
        reverted_template = Mock(spec=CampaignTemplate)
        reverted_template.id = 3
        reverted_template.name = old_version.name
        reverted_template.content = old_version.content
        reverted_template.category = old_version.category
        reverted_template.description = old_version.description
        reverted_template.variables = old_version.variables
        reverted_template.status = TemplateStatus.DRAFT
        reverted_template.version = 4
        reverted_template.usage_count = 0
        reverted_template.is_active = False
        reverted_template.parent_id = 1
        reverted_template.created_by = None
        reverted_template.created_at = datetime.now()
        reverted_template.updated_at = datetime.now()
        
        mock_repository.get_by_id.return_value = current_template
        mock_repository.get_version.return_value = old_version
        mock_repository.create.return_value = reverted_template
        
        # Act
        result = service.revert_to_version(1, version=1)
        
        # Assert
        assert result['content'] == 'Old content'
        assert result['version'] == 4
        assert result['parent_id'] == 1
        mock_repository.create.assert_called_once()
        create_args = mock_repository.create.call_args[1]
        assert create_args['content'] == 'Old content'
        assert create_args['version'] == 4  # New version created
        assert create_args['parent_id'] == 1
    
    # BULK OPERATIONS Tests
    
    def test_bulk_update_status(self, service, mock_repository):
        """Test bulk status update for templates"""
        # Arrange
        template_ids = [1, 2, 3]
        templates = [Mock(spec=CampaignTemplate) for _ in template_ids]
        for t in templates:
            t.status = TemplateStatus.DRAFT
        
        # Set up get_by_id to return templates in order
        mock_repository.get_by_id.side_effect = templates
        
        # Act
        result = service.bulk_update_status(template_ids, TemplateStatus.APPROVED)
        
        # Assert
        assert result['updated'] == 3
        assert result['failed'] == 0
        assert mock_repository.update.call_count == 3
    
    def test_clone_template(self, service, mock_repository, sample_template):
        """Test cloning a template"""
        # Arrange
        mock_repository.get_by_id.return_value = sample_template
        mock_repository.find_one_by.return_value = None  # No duplicate name
        
        # Mock the cloned template
        cloned_template = Mock(spec=CampaignTemplate)
        cloned_template.id = 2
        cloned_template.name = 'Cloned Template'
        cloned_template.content = sample_template.content
        cloned_template.description = sample_template.description
        cloned_template.category = sample_template.category
        cloned_template.status = TemplateStatus.DRAFT
        cloned_template.variables = sample_template.variables
        cloned_template.version = 1
        cloned_template.usage_count = 0
        cloned_template.is_active = False
        cloned_template.parent_id = 1
        cloned_template.created_by = None
        cloned_template.created_at = datetime.now()
        cloned_template.updated_at = datetime.now()
        mock_repository.create.return_value = cloned_template
        
        # Act
        result = service.clone_template(1, new_name='Cloned Template')
        
        # Assert
        assert result['id'] == 2
        assert result['name'] == 'Cloned Template'
        assert result['content'] == sample_template.content
        assert result['category'] == sample_template.category.value
        assert result['status'] == TemplateStatus.DRAFT.value
        assert result['parent_id'] == 1
        mock_repository.create.assert_called_once()
        create_args = mock_repository.create.call_args[1]
        assert create_args['name'] == 'Cloned Template'
        assert create_args['content'] == sample_template.content
        assert create_args['category'] == sample_template.category
        assert create_args['status'] == TemplateStatus.DRAFT
        assert create_args['parent_id'] == 1
    
    # VALIDATION Tests
    
    def test_validate_template_content(self, service):
        """Test template content validation"""
        # Arrange
        valid_content = "Hello {first_name}, welcome!"
        invalid_content = "Hello {first_name, welcome!"  # Unclosed bracket
        
        # Act & Assert
        assert service.validate_template_content(valid_content) is True
        
        with pytest.raises(TemplateValidationError) as exc_info:
            service.validate_template_content(invalid_content)
        assert 'Invalid variable syntax' in str(exc_info.value)
    
    def test_validate_variable_names(self, service):
        """Test variable name validation"""
        # Arrange
        valid_vars = ['first_name', 'last_name', 'property_address']
        invalid_vars = ['first-name', '123invalid', 'first name']  # Invalid characters
        
        # Act & Assert
        assert service.validate_variable_names(valid_vars) is True
        
        with pytest.raises(TemplateValidationError) as exc_info:
            service.validate_variable_names(invalid_vars)
        assert 'Invalid variable name' in str(exc_info.value)
    
    def test_get_available_variables(self, service):
        """Test getting list of available variables"""
        # Act
        variables = service.get_available_variables()
        
        # Assert
        assert 'first_name' in variables
        assert 'last_name' in variables
        assert 'phone' in variables
        assert 'email' in variables
        assert 'property_address' in variables
        assert 'property_type' in variables
        assert 'property_value' in variables
        # Each variable should have a description
        assert all(isinstance(v, dict) and 'name' in v and 'description' in v for v in variables.values())