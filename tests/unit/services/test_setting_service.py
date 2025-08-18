"""
Test Suite for SettingService - TDD RED Phase
Tests for business logic around setting management and template retrieval.

These tests MUST FAIL initially - verifying RED phase of TDD.
"""

import pytest
from unittest.mock import Mock, patch
from services.setting_service import SettingService
from repositories.setting_repository import SettingRepository
from crm_database import Setting


class TestSettingService:
    """Test cases for SettingService business logic"""
    
    @pytest.fixture
    def mock_repository(self):
        """Create mock SettingRepository for isolated testing"""
        return Mock(spec=SettingRepository)
    
    @pytest.fixture
    def setting_service(self, mock_repository):
        """Create SettingService instance with mocked repository"""
        return SettingService(repository=mock_repository)
    
    def test_get_template_by_key_success(self, setting_service, mock_repository):
        """Test successful template retrieval by key"""
        # Arrange
        template_key = 'appointment_reminder_template'
        expected_template = 'Hi {first_name}, appointment on {appointment_date} at {appointment_time}'
        mock_setting = Mock(spec=Setting)
        mock_setting.key = template_key
        mock_setting.value = expected_template
        mock_repository.find_one_by.return_value = mock_setting
        
        # Act
        result = setting_service.get_template_by_key(template_key)
        
        # Assert
        assert result == expected_template
        mock_repository.find_one_by.assert_called_once_with(key=template_key)
    
    def test_get_template_by_key_not_found(self, setting_service, mock_repository):
        """Test template retrieval when key doesn't exist returns None"""
        # Arrange
        template_key = 'nonexistent_template'
        mock_repository.find_one_by.return_value = None
        
        # Act
        result = setting_service.get_template_by_key(template_key)
        
        # Assert
        assert result is None
        mock_repository.find_one_by.assert_called_once_with(key=template_key)
    
    def test_get_all_templates_filtered(self, setting_service, mock_repository):
        """Test retrieving all template settings (keys ending with '_template')"""
        # Arrange
        mock_settings = [
            Mock(key='appointment_reminder_template', value='Template 1'),
            Mock(key='review_request_template', value='Template 2'),
            Mock(key='business_hours', value='9am-5pm'),  # Not a template
        ]
        mock_repository.get_all.return_value = mock_settings
        
        # Act
        result = setting_service.get_all_templates()
        
        # Assert
        assert len(result) == 2
        template_keys = [s.key for s in result]
        assert 'appointment_reminder_template' in template_keys
        assert 'review_request_template' in template_keys
        assert 'business_hours' not in template_keys
        mock_repository.get_all.assert_called_once()
    
    def test_update_template_success(self, setting_service, mock_repository):
        """Test successful template update"""
        # Arrange
        template_key = 'appointment_reminder_template'
        new_value = 'Updated: Hi {first_name}, appointment on {appointment_date}'
        mock_setting = Mock(spec=Setting)
        mock_setting.key = template_key
        mock_setting.value = 'Old template'
        mock_repository.find_one_by.return_value = mock_setting
        mock_repository.update.return_value = mock_setting
        
        # Act
        result = setting_service.update_template(template_key, new_value)
        
        # Assert
        assert result is True
        mock_repository.find_one_by.assert_called_once_with(key=template_key)
        mock_repository.update.assert_called_once_with(mock_setting, value=new_value)
    
    def test_update_template_not_found(self, setting_service, mock_repository):
        """Test template update when key doesn't exist"""
        # Arrange
        template_key = 'nonexistent_template'
        new_value = 'New template value'
        mock_repository.find_one_by.return_value = None
        
        # Act
        result = setting_service.update_template(template_key, new_value)
        
        # Assert
        assert result is False
        mock_repository.find_one_by.assert_called_once_with(key=template_key)
        mock_repository.update.assert_not_called()
    
    def test_create_template_success(self, setting_service, mock_repository):
        """Test successful template creation"""
        # Arrange
        template_key = 'new_template'
        template_value = 'Hi {first_name}, new message template'
        mock_setting = Mock(spec=Setting)
        mock_setting.key = template_key
        mock_setting.value = template_value
        mock_repository.exists.return_value = False
        mock_repository.create.return_value = mock_setting
        
        # Act
        result = setting_service.create_template(template_key, template_value)
        
        # Assert
        assert result == mock_setting
        mock_repository.exists.assert_called_once_with(key=template_key)
        mock_repository.create.assert_called_once_with(key=template_key, value=template_value)
    
    def test_create_template_already_exists(self, setting_service, mock_repository):
        """Test template creation when key already exists"""
        # Arrange
        template_key = 'existing_template'
        template_value = 'Template value'
        mock_repository.exists.return_value = True
        
        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            setting_service.create_template(template_key, template_value)
        
        assert f"Setting with key '{template_key}' already exists" in str(exc_info.value)
        mock_repository.exists.assert_called_once_with(key=template_key)
        mock_repository.create.assert_not_called()
    
    def test_delete_template_success(self, setting_service, mock_repository):
        """Test successful template deletion"""
        # Arrange
        template_key = 'template_to_delete'
        mock_setting = Mock(spec=Setting)
        mock_setting.key = template_key
        mock_repository.find_one_by.return_value = mock_setting
        mock_repository.delete.return_value = True
        
        # Act
        result = setting_service.delete_template(template_key)
        
        # Assert
        assert result is True
        mock_repository.find_one_by.assert_called_once_with(key=template_key)
        mock_repository.delete.assert_called_once_with(mock_setting)
    
    def test_delete_template_not_found(self, setting_service, mock_repository):
        """Test template deletion when key doesn't exist"""
        # Arrange
        template_key = 'nonexistent_template'
        mock_repository.find_one_by.return_value = None
        
        # Act
        result = setting_service.delete_template(template_key)
        
        # Assert
        assert result is False
        mock_repository.find_one_by.assert_called_once_with(key=template_key)
        mock_repository.delete.assert_not_called()


class TestSettingServiceSpecializedMethods:
    """Test specialized methods for main_routes.py needs"""
    
    @pytest.fixture
    def mock_repository(self):
        """Create mock repository"""
        return Mock(spec=SettingRepository)
    
    @pytest.fixture
    def setting_service(self, mock_repository):
        """Create service with mock repository"""
        return SettingService(repository=mock_repository)
    
    def test_get_appointment_reminder_template(self, setting_service, mock_repository):
        """Test getting appointment reminder template specifically"""
        # Arrange
        expected_template = 'Hi {first_name}, reminder for {appointment_date} at {appointment_time}'
        mock_setting = Mock(spec=Setting)
        mock_setting.value = expected_template
        mock_repository.find_one_by.return_value = mock_setting
        
        # Act
        result = setting_service.get_appointment_reminder_template()
        
        # Assert
        assert result == expected_template
        mock_repository.find_one_by.assert_called_once_with(key='appointment_reminder_template')
    
    def test_get_review_request_template(self, setting_service, mock_repository):
        """Test getting review request template specifically"""
        # Arrange
        expected_template = 'Hi {first_name}, please review our work'
        mock_setting = Mock(spec=Setting)
        mock_setting.value = expected_template
        mock_repository.find_one_by.return_value = mock_setting
        
        # Act
        result = setting_service.get_review_request_template()
        
        # Assert
        assert result == expected_template
        mock_repository.find_one_by.assert_called_once_with(key='review_request_template')
    
    def test_get_template_by_dynamic_key(self, setting_service, mock_repository):
        """Test getting template by dynamic key construction (main_routes pattern)"""
        # Arrange
        base_key = 'appointment_reminder'
        template_key = f'{base_key}_template'
        expected_template = 'Dynamic template content'
        mock_setting = Mock(spec=Setting)
        mock_setting.value = expected_template
        mock_repository.find_one_by.return_value = mock_setting
        
        # Act
        result = setting_service.get_template_by_key(template_key)
        
        # Assert
        assert result == expected_template
        mock_repository.find_one_by.assert_called_once_with(key=template_key)


class TestSettingServiceEdgeCases:
    """Test edge cases and error conditions"""
    
    @pytest.fixture
    def mock_repository(self):
        return Mock(spec=SettingRepository)
    
    @pytest.fixture
    def setting_service(self, mock_repository):
        return SettingService(repository=mock_repository)
    
    def test_get_template_empty_key(self, setting_service, mock_repository):
        """Test getting template with empty key"""
        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            setting_service.get_template_by_key('')
        
        assert 'Template key cannot be empty' in str(exc_info.value)
        mock_repository.find_one_by.assert_not_called()
    
    def test_get_template_none_key(self, setting_service, mock_repository):
        """Test getting template with None key"""
        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            setting_service.get_template_by_key(None)
        
        assert 'Template key cannot be empty' in str(exc_info.value)
        mock_repository.find_one_by.assert_not_called()
    
    def test_create_template_empty_key(self, setting_service, mock_repository):
        """Test creating template with empty key"""
        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            setting_service.create_template('', 'Some value')
        
        assert 'Template key cannot be empty' in str(exc_info.value)
        mock_repository.exists.assert_not_called()
    
    def test_create_template_empty_value(self, setting_service, mock_repository):
        """Test creating template with empty value"""
        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            setting_service.create_template('valid_key', '')
        
        assert 'Template value cannot be empty' in str(exc_info.value)
        mock_repository.exists.assert_not_called()
    
    def test_repository_error_handling(self, setting_service, mock_repository):
        """Test handling of repository errors"""
        # Arrange
        mock_repository.find_one_by.side_effect = Exception("Database connection error")
        
        # Act & Assert
        with pytest.raises(Exception) as exc_info:
            setting_service.get_template_by_key('some_key')
        
        assert "Database connection error" in str(exc_info.value)