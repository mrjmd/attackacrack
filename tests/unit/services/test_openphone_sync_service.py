"""
Tests for OpenPhoneSyncService with Repository Pattern
TDD RED Phase - These tests are written FIRST before refactoring
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
from sqlalchemy.orm import Session

from services.openphone_sync_service import OpenPhoneSyncService
from repositories.contact_repository import ContactRepository
from repositories.activity_repository import ActivityRepository
from crm_database import Contact, Activity


class TestOpenPhoneSyncServiceWithRepositories:
    """Test OpenPhoneSyncService with repository pattern integration"""
    
    @pytest.fixture
    def mock_contact_repository(self):
        """Mock ContactRepository"""
        return Mock(spec=ContactRepository)
    
    @pytest.fixture
    def mock_activity_repository(self):
        """Mock ActivityRepository"""
        return Mock(spec=ActivityRepository)
    
    @pytest.fixture
    def service(self, mock_contact_repository, mock_activity_repository):
        """Create OpenPhoneSyncService with mocked repositories"""
        # This will fail initially because service doesn't accept repositories yet
        return OpenPhoneSyncService(
            contact_repository=mock_contact_repository,
            activity_repository=mock_activity_repository
        )
    
    def test_get_sync_statistics_with_repositories(self, service, mock_contact_repository, mock_activity_repository):
        """Test get_sync_statistics uses repositories instead of direct queries"""
        # Arrange
        expected_contact_count = 150
        expected_message_count = 500
        mock_latest_activity = Mock(
            id=1,
            activity_type='sms',
            created_at=datetime(2025, 8, 18, 10, 30, 0)
        )
        
        mock_contact_repository.count_with_phone.return_value = expected_contact_count
        mock_activity_repository.count_by_type.return_value = expected_message_count
        mock_activity_repository.find_latest_by_type.return_value = mock_latest_activity
        
        # Act
        result = service.get_sync_statistics()
        
        # Assert
        assert result['total_contacts'] == expected_contact_count
        assert result['total_messages'] == expected_message_count
        assert result['last_sync'] == datetime(2025, 8, 18, 10, 30, 0)
        
        # Verify repository methods were called
        mock_contact_repository.count_with_phone.assert_called_once()
        mock_activity_repository.count_by_type.assert_called_once_with('sms')
        mock_activity_repository.find_latest_by_type.assert_called_once_with('sms')
    
    def test_get_sync_statistics_no_last_sync(self, service, mock_contact_repository, mock_activity_repository):
        """Test get_sync_statistics when no previous sync exists"""
        # Arrange
        mock_contact_repository.count_with_phone.return_value = 0
        mock_activity_repository.count_by_type.return_value = 0
        mock_activity_repository.find_latest_by_type.return_value = None
        
        # Act
        result = service.get_sync_statistics()
        
        # Assert
        assert result['total_contacts'] == 0
        assert result['total_messages'] == 0
        assert result['last_sync'] is None
        
        # Verify repository methods were called
        mock_contact_repository.count_with_phone.assert_called_once()
        mock_activity_repository.count_by_type.assert_called_once_with('sms')
        mock_activity_repository.find_latest_by_type.assert_called_once_with('sms')
    
    def test_get_recent_sync_activity_with_repositories(self, service, mock_activity_repository):
        """Test get_recent_sync_activity uses repository instead of direct query"""
        # Arrange
        mock_contact = Mock()
        mock_contact.get_full_name.return_value = 'John Doe'
        
        mock_activity1 = Mock(
            id=1,
            contact=mock_contact,
            direction='inbound',
            created_at=datetime.now(),
            body='Hello, this is a test message with enough content to test truncation'
        )
        mock_activity2 = Mock(
            id=2,
            contact=mock_contact,
            direction='outbound', 
            created_at=datetime.now() - timedelta(minutes=5),
            body='Short reply'
        )
        
        mock_activity_repository.find_recent_by_type_with_contact.return_value = [
            mock_activity1, mock_activity2
        ]
        
        # Act
        result = service.get_recent_sync_activity(limit=5)
        
        # Assert
        assert len(result) == 2
        
        # Check first activity
        assert result[0]['id'] == 1
        assert result[0]['contact_name'] == 'John Doe'
        assert result[0]['direction'] == 'inbound'
        assert result[0]['body_preview'] == 'Hello, this is a test message with enough content '  # Truncated at 50 chars
        
        # Check second activity
        assert result[1]['id'] == 2
        assert result[1]['contact_name'] == 'John Doe'
        assert result[1]['direction'] == 'outbound'
        assert result[1]['body_preview'] == 'Short reply'
        
        # Verify repository method was called with correct parameters
        mock_activity_repository.find_recent_by_type_with_contact.assert_called_once_with('sms', limit=5)
    
    def test_get_recent_sync_activity_default_limit(self, service, mock_activity_repository):
        """Test get_recent_sync_activity uses default limit when not specified"""
        # Arrange
        mock_activity_repository.find_recent_by_type_with_contact.return_value = []
        
        # Act
        service.get_recent_sync_activity()
        
        # Assert
        mock_activity_repository.find_recent_by_type_with_contact.assert_called_once_with('sms', limit=10)
    
    def test_get_recent_sync_activity_handles_contact_none(self, service, mock_activity_repository):
        """Test get_recent_sync_activity handles activities with no associated contact"""
        # Arrange
        mock_activity = Mock(
            id=1,
            contact=None,  # No associated contact
            direction='inbound',
            created_at=datetime.now(),
            body='Orphaned message'
        )
        
        mock_activity_repository.find_recent_by_type_with_contact.return_value = [mock_activity]
        
        # Act
        result = service.get_recent_sync_activity()
        
        # Assert
        assert len(result) == 1
        assert result[0]['contact_name'] == 'Unknown'
        assert result[0]['body_preview'] == 'Orphaned message'
    
    def test_get_recent_sync_activity_handles_empty_body(self, service, mock_activity_repository):
        """Test get_recent_sync_activity handles activities with no body content"""
        # Arrange
        mock_contact = Mock()
        mock_contact.get_full_name.return_value = 'Jane Smith'
        
        mock_activity = Mock(
            id=1,
            contact=mock_contact,
            direction='outbound',
            created_at=datetime.now(),
            body=None  # No body content
        )
        
        mock_activity_repository.find_recent_by_type_with_contact.return_value = [mock_activity]
        
        # Act
        result = service.get_recent_sync_activity()
        
        # Assert
        assert len(result) == 1
        assert result[0]['body_preview'] == ''
