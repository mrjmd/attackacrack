# tests/unit/repositories/test_contact_flag_repository.py
"""
TDD RED PHASE: ContactFlagRepository Tests
These tests MUST fail initially to enforce test-driven development.

ContactFlagRepository manages contact flags for campaign filtering and compliance.
Flag types include: opted_out, invalid_phone, office_number, do_not_contact, recently_texted.
"""

import pytest
from unittest.mock import Mock
from datetime import datetime, timedelta
from typing import List, Set

from repositories.contact_flag_repository import ContactFlagRepository
from repositories.base_repository import PaginationParams, PaginatedResult, SortOrder
from crm_database import ContactFlag, Contact


class TestContactFlagRepository:
    """Comprehensive test suite for ContactFlagRepository"""
    
    @pytest.fixture
    def mock_session(self):
        """Create mock database session"""
        return Mock()
    
    @pytest.fixture
    def contact_flag_repository(self, mock_session):
        """Create ContactFlagRepository with mocked session"""
        return ContactFlagRepository(mock_session, ContactFlag)
    
    def test_repository_inherits_from_base_repository(self, contact_flag_repository):
        """Test that ContactFlagRepository inherits from BaseRepository"""
        from repositories.base_repository import BaseRepository
        assert isinstance(contact_flag_repository, BaseRepository)
        assert contact_flag_repository.model_class == ContactFlag
    
    # CREATE Operations Tests
    
    def test_create_flag_for_contact_id(self, contact_flag_repository, mock_session):
        """Test creating a flag for a specific contact ID"""
        # Arrange
        contact_id = 123
        flag_type = 'opted_out'
        flag_reason = 'User requested opt-out via SMS'
        applies_to = 'sms'
        created_by = 'system'
        
        mock_flag = Mock()
        mock_flag.id = 1
        mock_flag.contact_id = contact_id
        mock_flag.flag_type = flag_type
        
        mock_session.add.return_value = None
        mock_session.flush.return_value = None
        
        # Act
        result = contact_flag_repository.create_flag_for_contact(
            contact_id=contact_id,
            flag_type=flag_type,
            flag_reason=flag_reason,
            applies_to=applies_to,
            created_by=created_by
        )
        
        # Assert
        assert result is not None
        mock_session.add.assert_called_once()
        mock_session.flush.assert_called_once()
    
    def test_create_temporary_flag_with_expiration(self, contact_flag_repository):
        """Test creating a temporary flag with expiration date"""
        # Arrange
        contact_id = 456
        flag_type = 'recently_texted'
        expires_at = datetime.utcnow() + timedelta(days=30)
        
        # Act
        result = contact_flag_repository.create_temporary_flag(
            contact_id=contact_id,
            flag_type=flag_type,
            expires_at=expires_at,
            flag_reason='Contacted in last 30 days'
        )
        
        # Assert
        assert result is not None
    
    def test_bulk_create_flags_for_multiple_contacts(self, contact_flag_repository):
        """Test creating the same flag for multiple contacts"""
        # Arrange
        contact_ids = [101, 102, 103]
        flag_type = 'office_number'
        flag_reason = 'Business phone number detected'
        
        # Act
        results = contact_flag_repository.bulk_create_flags(
            contact_ids=contact_ids,
            flag_type=flag_type,
            flag_reason=flag_reason,
            applies_to='sms'
        )
        
        # Assert
        assert len(results) == 3
        for result in results:
            assert result.flag_type == flag_type
    
    # READ Operations Tests
    
    def test_find_flags_by_contact_id(self, contact_flag_repository, mock_session):
        """Test finding all flags for a specific contact"""
        # Arrange
        contact_id = 789
        mock_flags = [
            Mock(id=1, contact_id=contact_id, flag_type='opted_out'),
            Mock(id=2, contact_id=contact_id, flag_type='office_number')
        ]
        
        mock_query = Mock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = mock_flags
        
        # Act
        result = contact_flag_repository.find_flags_by_contact_id(contact_id)
        
        # Assert
        assert len(result) == 2
        assert all(flag.contact_id == contact_id for flag in result)
    
    def test_find_flags_by_type(self, contact_flag_repository, mock_session):
        """Test finding all flags of a specific type"""
        # Arrange
        flag_type = 'opted_out'
        mock_flags = [
            Mock(id=1, flag_type=flag_type, contact_id=101),
            Mock(id=2, flag_type=flag_type, contact_id=102)
        ]
        
        mock_query = Mock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = mock_flags
        
        # Act
        result = contact_flag_repository.find_flags_by_type(flag_type)
        
        # Assert
        assert len(result) == 2
        assert all(flag.flag_type == flag_type for flag in result)
    
    def test_get_contact_ids_with_flag_type(self, contact_flag_repository, mock_session):
        """Test getting contact IDs that have a specific flag type"""
        # Arrange
        flag_type = 'office_number'
        mock_results = [(101,), (102,), (103,)]
        
        mock_query = Mock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = mock_results
        
        # Act
        result = contact_flag_repository.get_contact_ids_with_flag_type(flag_type)
        
        # Assert
        assert isinstance(result, set)
        assert result == {101, 102, 103}
    
    def test_check_contact_has_flag_type(self, contact_flag_repository, mock_session):
        """Test checking if a specific contact has a specific flag type"""
        # Arrange
        contact_id = 456
        flag_type = 'opted_out'
        
        mock_query = Mock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = Mock()  # Flag exists
        
        # Act
        result = contact_flag_repository.check_contact_has_flag_type(contact_id, flag_type)
        
        # Assert
        assert result is True
    
    def test_check_contact_has_flag_type_returns_false_when_no_flag(self, contact_flag_repository, mock_session):
        """Test checking returns False when contact doesn't have flag"""
        # Arrange
        contact_id = 456
        flag_type = 'opted_out'
        
        mock_query = Mock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None  # No flag
        
        # Act
        result = contact_flag_repository.check_contact_has_flag_type(contact_id, flag_type)
        
        # Assert
        assert result is False
    
    def test_get_active_flags_for_contact(self, contact_flag_repository, mock_session):
        """Test getting only active (non-expired) flags for a contact"""
        # Arrange
        contact_id = 789
        now = datetime.utcnow()
        
        mock_flags = [
            Mock(id=1, contact_id=contact_id, flag_type='opted_out', expires_at=None),
            Mock(id=2, contact_id=contact_id, flag_type='recently_texted', expires_at=now + timedelta(days=1))
        ]
        
        mock_query = Mock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = mock_flags
        
        # Act
        result = contact_flag_repository.get_active_flags_for_contact(contact_id)
        
        # Assert
        assert len(result) == 2
        # Both flags should be active (one permanent, one not expired)
    
    def test_get_expired_flags(self, contact_flag_repository, mock_session):
        """Test finding flags that have expired"""
        # Arrange
        expired_time = datetime.utcnow() - timedelta(days=1)
        
        mock_flags = [
            Mock(id=1, contact_id=101, flag_type='recently_texted', expires_at=expired_time)
        ]
        
        mock_query = Mock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = mock_flags
        
        # Act
        result = contact_flag_repository.get_expired_flags()
        
        # Assert
        assert len(result) == 1
        assert result[0].expires_at < datetime.utcnow()
    
    def test_bulk_check_contacts_for_flag_type(self, contact_flag_repository, mock_session):
        """Test checking multiple contacts for a specific flag type efficiently"""
        # Arrange
        contact_ids = [101, 102, 103, 104]
        flag_type = 'opted_out'
        
        # Mock that contacts 101 and 103 have the flag
        mock_results = [(101,), (103,)]
        
        mock_query = Mock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = mock_results
        
        # Act
        result = contact_flag_repository.bulk_check_contacts_for_flag_type(contact_ids, flag_type)
        
        # Assert
        assert isinstance(result, dict)
        assert result[101] is True
        assert result[102] is False
        assert result[103] is True
        assert result[104] is False
    
    # Campaign-specific filtering methods
    
    def test_get_contacts_excluded_from_campaigns(self, contact_flag_repository, mock_session):
        """Test getting contacts that should be excluded from campaigns"""
        # Arrange
        exclusion_flags = ['opted_out', 'do_not_contact', 'office_number']
        channel = 'sms'
        
        mock_contact_ids = [(101,), (102,), (103,)]
        
        mock_query = Mock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.distinct.return_value = mock_query
        mock_query.all.return_value = mock_contact_ids
        
        # Act
        result = contact_flag_repository.get_contacts_excluded_from_campaigns(channel, exclusion_flags)
        
        # Assert
        assert isinstance(result, set)
        assert result == {101, 102, 103}
    
    def test_filter_campaign_eligible_contacts(self, contact_flag_repository, mock_session):
        """Test filtering a list of contacts to only campaign-eligible ones"""
        # Arrange
        all_contact_ids = [101, 102, 103, 104, 105]
        channel = 'sms'
        
        # Mock that contacts 102 and 104 are excluded
        excluded_contact_ids = [(102,), (104,)]
        
        mock_query = Mock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.distinct.return_value = mock_query
        mock_query.all.return_value = excluded_contact_ids
        
        # Act
        result = contact_flag_repository.filter_campaign_eligible_contacts(all_contact_ids, channel)
        
        # Assert
        assert result == [101, 103, 105]  # Excluded contacts removed
    
    # UPDATE Operations Tests
    
    def test_update_flag_reason(self, contact_flag_repository, mock_session):
        """Test updating the reason for an existing flag"""
        # Arrange
        flag_id = 123
        new_reason = 'Updated reason for opt-out'
        
        mock_flag = Mock()
        mock_flag.id = flag_id
        mock_flag.flag_reason = 'Old reason'
        
        mock_session.get.return_value = mock_flag
        mock_session.flush.return_value = None
        
        # Act
        result = contact_flag_repository.update_flag_reason(flag_id, new_reason)
        
        # Assert
        assert result is not None
        assert result.flag_reason == new_reason
    
    def test_extend_flag_expiration(self, contact_flag_repository, mock_session):
        """Test extending the expiration date of a temporary flag"""
        # Arrange
        flag_id = 456
        new_expiration = datetime.utcnow() + timedelta(days=60)
        
        mock_flag = Mock()
        mock_flag.id = flag_id
        mock_flag.expires_at = datetime.utcnow() + timedelta(days=30)
        
        mock_session.get.return_value = mock_flag
        mock_session.flush.return_value = None
        
        # Act
        result = contact_flag_repository.extend_flag_expiration(flag_id, new_expiration)
        
        # Assert
        assert result is not None
        assert result.expires_at == new_expiration
    
    # DELETE Operations Tests
    
    def test_remove_flag_by_id(self, contact_flag_repository, mock_session):
        """Test removing a specific flag by ID"""
        # Arrange
        flag_id = 789
        
        mock_flag = Mock()
        mock_flag.id = flag_id
        
        mock_session.get.return_value = mock_flag
        mock_session.delete.return_value = None
        mock_session.flush.return_value = None
        
        # Act
        result = contact_flag_repository.remove_flag_by_id(flag_id)
        
        # Assert
        assert result is True
        mock_session.delete.assert_called_once_with(mock_flag)
        mock_session.flush.assert_called_once()
    
    def test_remove_flags_by_contact_and_type(self, contact_flag_repository, mock_session):
        """Test removing all flags of a specific type for a contact"""
        # Arrange
        contact_id = 123
        flag_type = 'recently_texted'
        
        mock_query = Mock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.delete.return_value = 2  # 2 flags deleted
        
        # Act
        result = contact_flag_repository.remove_flags_by_contact_and_type(contact_id, flag_type)
        
        # Assert
        assert result == 2
    
    def test_cleanup_expired_flags(self, contact_flag_repository, mock_session):
        """Test removing all expired flags"""
        # Arrange
        mock_query = Mock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.delete.return_value = 5  # 5 expired flags deleted
        
        # Act
        result = contact_flag_repository.cleanup_expired_flags()
        
        # Assert
        assert result == 5
    
    def test_bulk_remove_flag_type_for_contacts(self, contact_flag_repository, mock_session):
        """Test removing a specific flag type from multiple contacts"""
        # Arrange
        contact_ids = [101, 102, 103]
        flag_type = 'recently_texted'
        
        mock_query = Mock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.delete.return_value = 3  # 3 flags deleted
        
        # Act
        result = contact_flag_repository.bulk_remove_flag_type_for_contacts(contact_ids, flag_type)
        
        # Assert
        assert result == 3
    
    # Search Implementation (required by BaseRepository)
    
    def test_search_flags_by_reason(self, contact_flag_repository, mock_session):
        """Test searching flags by reason text"""
        # Arrange
        search_query = 'opt-out'
        
        mock_flags = [
            Mock(id=1, flag_reason='User requested opt-out'),
            Mock(id=2, flag_reason='Automatic opt-out detected')
        ]
        
        mock_query = Mock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = mock_flags
        
        # Act
        result = contact_flag_repository.search(search_query)
        
        # Assert
        assert len(result) == 2
        assert all('opt-out' in flag.flag_reason for flag in result)
    
    # Edge Cases and Error Handling
    
    def test_create_duplicate_flag_handling(self, contact_flag_repository, mock_session):
        """Test handling when trying to create duplicate flag"""
        # Arrange
        contact_id = 123
        flag_type = 'opted_out'
        
        # Mock that flag already exists
        mock_existing_flag = Mock()
        mock_existing_flag.id = 999
        mock_existing_flag.contact_id = contact_id
        mock_existing_flag.flag_type = flag_type
        
        mock_query = Mock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = mock_existing_flag
        
        # Act
        result = contact_flag_repository.create_flag_for_contact_if_not_exists(
            contact_id=contact_id,
            flag_type=flag_type,
            flag_reason='Test reason'
        )
        
        # Assert - should return existing flag, not create new one
        assert result.id == 999
    
    def test_get_flag_statistics(self, contact_flag_repository, mock_session):
        """Test getting statistics about flag usage"""
        # Arrange
        mock_results = [
            ('opted_out', 150),
            ('office_number', 75),
            ('do_not_contact', 25)
        ]
        
        mock_query = Mock()
        mock_session.query.return_value = mock_query
        mock_query.group_by.return_value = mock_query
        mock_query.all.return_value = mock_results
        
        # Act
        result = contact_flag_repository.get_flag_statistics()
        
        # Assert
        assert isinstance(result, dict)
        assert result['opted_out'] == 150
        assert result['office_number'] == 75
        assert result['do_not_contact'] == 25


class TestContactFlagRepositoryIntegration:
    """Integration tests that require ContactFlagRepository to work with campaign filtering"""
    
    @pytest.fixture
    def contact_flag_repository(self, mock_session):
        return ContactFlagRepository(mock_session, ContactFlag)
    
    def test_campaign_filter_integration(self, contact_flag_repository, mock_session):
        """Test that repository methods support campaign service filtering needs"""
        # This test verifies the interface needed by campaign_service_refactored.py
        
        # Arrange - simulate what campaign service needs
        contact_ids = [101, 102, 103, 104]
        
        # Mock excluded contact IDs (office numbers)
        mock_office_ids = [(102,), (104,)]
        
        mock_query = Mock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = mock_office_ids
        
        # Act - This is what campaign service will call
        excluded_ids = contact_flag_repository.get_contact_ids_with_flag_type('office_number')
        
        # Assert
        assert excluded_ids == {102, 104}
        
        # Verify the campaign service can filter contacts
        eligible_contacts = [c_id for c_id in contact_ids if c_id not in excluded_ids]
        assert eligible_contacts == [101, 103]