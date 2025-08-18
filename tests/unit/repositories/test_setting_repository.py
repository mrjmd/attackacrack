"""
Test Suite for SettingRepository - Repository Pattern Implementation

Tests for data access operations on Setting model, focusing on
configuration and template management functionality.
"""

import pytest
from datetime import date, datetime, timedelta
from repositories.setting_repository import SettingRepository
from crm_database import Setting


class TestSettingRepository:
    """Test cases for SettingRepository"""
    
    @pytest.fixture
    def setting_repository(self, db_session):
        """Create SettingRepository instance with test database session"""
        return SettingRepository(session=db_session, model_class=Setting)
    
    @pytest.fixture
    def sample_settings(self, db_session):
        """Create sample settings for testing"""
        # Clean any existing settings with these keys first
        existing_keys = ['test_appointment_reminder_template', 'test_review_request_template', 'test_business_hours', 'test_max_daily_sms']
        for key in existing_keys:
            existing = db_session.query(Setting).filter_by(key=key).first()
            if existing:
                db_session.delete(existing)
        db_session.commit()
        
        settings = [
            Setting(key='test_appointment_reminder_template', value='Hi {first_name}, reminder for {appointment_date} at {appointment_time}'),
            Setting(key='test_review_request_template', value='Hi {first_name}, please review our recent work'),
            Setting(key='test_business_hours', value='9am-5pm'),
            Setting(key='test_max_daily_sms', value='125')
        ]
        
        for setting in settings:
            db_session.add(setting)
        db_session.commit()
        return settings
    
    def test_create_setting(self, setting_repository, db_session):
        """Test creating a new setting"""
        # Arrange
        key = 'test_setting'
        value = 'test value'
        
        # Act
        setting = setting_repository.create(key=key, value=value)
        
        # Assert
        assert setting.key == key
        assert setting.value == value
        assert setting.id is not None
        
        # Verify in database
        db_setting = db_session.query(Setting).filter_by(key=key).first()
        assert db_setting is not None
        assert db_setting.value == value
    
    def test_get_by_id(self, setting_repository, sample_settings):
        """Test retrieving setting by ID"""
        # Arrange
        expected_setting = sample_settings[0]
        
        # Act
        setting = setting_repository.get_by_id(expected_setting.id)
        
        # Assert
        assert setting is not None
        assert setting.key == expected_setting.key
        assert setting.value == expected_setting.value
    
    def test_get_by_nonexistent_id(self, setting_repository):
        """Test retrieving setting with non-existent ID"""
        # Act
        setting = setting_repository.get_by_id(99999)
        
        # Assert
        assert setting is None
    
    def test_find_by_key(self, setting_repository, sample_settings):
        """Test finding setting by key"""
        # Arrange
        expected_key = 'test_appointment_reminder_template'
        
        # Act
        settings = setting_repository.find_by(key=expected_key)
        
        # Assert
        assert len(settings) == 1
        assert settings[0].key == expected_key
        assert 'Hi {first_name}' in settings[0].value
    
    def test_find_by_key_not_found(self, setting_repository, sample_settings):
        """Test finding setting by non-existent key"""
        # Act
        settings = setting_repository.find_by(key='nonexistent_key')
        
        # Assert
        assert len(settings) == 0
    
    def test_find_one_by_key(self, setting_repository, sample_settings):
        """Test finding single setting by key"""
        # Arrange
        expected_key = 'test_review_request_template'
        
        # Act
        setting = setting_repository.find_one_by(key=expected_key)
        
        # Assert
        assert setting is not None
        assert setting.key == expected_key
        assert 'please review' in setting.value
    
    def test_find_one_by_nonexistent_key(self, setting_repository):
        """Test finding single setting by non-existent key"""
        # Act
        setting = setting_repository.find_one_by(key='nonexistent')
        
        # Assert
        assert setting is None
    
    def test_get_all_settings(self, setting_repository, sample_settings):
        """Test retrieving all settings"""
        # Act
        all_settings = setting_repository.get_all()
        
        # Assert - Check that our test settings are included
        keys = [s.key for s in all_settings]
        assert 'test_appointment_reminder_template' in keys
        assert 'test_review_request_template' in keys
        assert 'test_business_hours' in keys
        assert 'test_max_daily_sms' in keys
        
        # Verify we have at least our 4 test settings
        assert len(all_settings) >= 4
    
    def test_exists_by_key(self, setting_repository, sample_settings):
        """Test checking if setting exists by key"""
        # Act & Assert
        assert setting_repository.exists(key='test_appointment_reminder_template') is True
        assert setting_repository.exists(key='nonexistent_key') is False
    
    def test_update_setting(self, setting_repository, sample_settings):
        """Test updating a setting"""
        # Arrange
        setting = sample_settings[0]
        new_value = 'Updated template: Hi {first_name}, your appointment is on {appointment_date}'
        
        # Act
        updated_setting = setting_repository.update(setting, value=new_value)
        
        # Assert
        assert updated_setting.value == new_value
        assert updated_setting.key == setting.key  # Key unchanged
    
    def test_update_by_id(self, setting_repository, sample_settings):
        """Test updating setting by ID"""
        # Arrange
        setting = sample_settings[1]
        new_value = 'Updated review template'
        
        # Act
        updated_setting = setting_repository.update_by_id(setting.id, value=new_value)
        
        # Assert
        assert updated_setting is not None
        assert updated_setting.value == new_value
        assert updated_setting.key == setting.key
    
    def test_delete_setting(self, setting_repository, sample_settings, db_session):
        """Test deleting a setting"""
        # Arrange
        setting_to_delete = sample_settings[0]
        setting_id = setting_to_delete.id
        
        # Act
        result = setting_repository.delete(setting_to_delete)
        
        # Assert
        assert result is True
        
        # Verify deletion
        deleted_setting = db_session.query(Setting).get(setting_id)
        assert deleted_setting is None
    
    def test_delete_by_id(self, setting_repository, sample_settings, db_session):
        """Test deleting setting by ID"""
        # Arrange
        setting_id = sample_settings[1].id
        
        # Act
        result = setting_repository.delete_by_id(setting_id)
        
        # Assert
        assert result is True
        
        # Verify deletion
        deleted_setting = db_session.query(Setting).get(setting_id)
        assert deleted_setting is None
    
    def test_count_all_settings(self, setting_repository, sample_settings):
        """Test counting all settings"""
        # Act
        count = setting_repository.count()
        
        # Assert - Should have at least our 4 test settings
        assert count >= 4
    
    def test_search_settings(self, setting_repository, sample_settings):
        """Test searching settings (implementation-specific method)"""
        # Act
        results = setting_repository.search('template')
        
        # Assert - Should find at least our 2 template settings
        keys = [r.key for r in results]
        assert 'test_appointment_reminder_template' in keys
        assert 'test_review_request_template' in keys
        assert len(results) >= 2


class TestSettingRepositorySpecializedMethods:
    """Test specialized methods for scheduler service needs"""
    
    @pytest.fixture
    def setting_repository(self, db_session):
        """Create SettingRepository instance"""
        return SettingRepository(session=db_session, model_class=Setting)
    
    @pytest.fixture
    def scheduler_settings(self, db_session):
        """Create settings specifically for scheduler testing"""
        # Clean any existing settings first
        test_keys = ['scheduler_appointment_reminder_template', 'scheduler_review_request_template', 'scheduler_other_setting']
        for key in test_keys:
            existing = db_session.query(Setting).filter_by(key=key).first()
            if existing:
                db_session.delete(existing)
        db_session.commit()
        
        settings = [
            Setting(key='scheduler_appointment_reminder_template', 
                   value='Hi {first_name}, reminder for appointment on {appointment_date} at {appointment_time}'),
            Setting(key='scheduler_review_request_template', 
                   value='Hi {first_name}, please review our work'),
            Setting(key='scheduler_other_setting', value='not a template')
        ]
        
        for setting in settings:
            db_session.add(setting)
        db_session.commit()
        return settings
    
    def test_get_template_setting(self, setting_repository, scheduler_settings):
        """Test getting template setting by key (scheduler service pattern)"""
        # Act
        template_setting = setting_repository.find_one_by(key='scheduler_appointment_reminder_template')
        
        # Assert
        assert template_setting is not None
        assert template_setting.value is not None
        assert '{first_name}' in template_setting.value
        assert '{appointment_date}' in template_setting.value
        assert '{appointment_time}' in template_setting.value
    
    def test_get_nonexistent_template_returns_none(self, setting_repository):
        """Test getting non-existent template returns None"""
        # Act
        template_setting = setting_repository.find_one_by(key='nonexistent_template')
        
        # Assert
        assert template_setting is None
    
    def test_template_contains_placeholders(self, setting_repository, scheduler_settings):
        """Test that templates contain expected placeholders for formatting"""
        # Act
        appointment_template = setting_repository.find_one_by(key='scheduler_appointment_reminder_template')
        review_template = setting_repository.find_one_by(key='scheduler_review_request_template')
        
        # Assert appointment template
        assert appointment_template is not None
        assert '{first_name}' in appointment_template.value
        
        # Assert review template  
        assert review_template is not None
        assert '{first_name}' in review_template.value