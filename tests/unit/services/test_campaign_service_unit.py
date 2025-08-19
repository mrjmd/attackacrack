"""
Comprehensive unit tests for CampaignService - Repository Pattern with TDD
Tests all business logic in isolation with mocked repository dependencies

This test suite follows TDD principles:
1. Tests are written BEFORE implementation
2. Repository dependencies are mocked 
3. Tests verify business logic without database
4. Error handling and edge cases are tested
5. Result pattern usage is validated
"""

import pytest
from unittest.mock import Mock, MagicMock, patch, call
from datetime import datetime, time, timedelta
from typing import List, Dict, Optional

# Import the service and dependencies
from services.campaign_service_refactored import CampaignService
from repositories.campaign_repository import CampaignRepository
from repositories.contact_repository import ContactRepository
from repositories.contact_flag_repository import ContactFlagRepository
from repositories.base_repository import PaginationParams, PaginatedResult
from crm_database import Campaign, CampaignMembership, Contact, ContactFlag


class TestCampaignServiceUnit:
    """Unit tests for CampaignService with repository pattern"""
    
    @pytest.fixture
    def mock_campaign_repository(self):
        """Mock CampaignRepository for dependency injection"""
        mock_repo = Mock(spec=CampaignRepository)
        mock_repo.create.return_value = Mock(spec=Campaign)
        mock_repo.get_by_id.return_value = Mock(spec=Campaign)
        mock_repo.commit.return_value = None
        return mock_repo
    
    @pytest.fixture
    def mock_contact_repository(self):
        """Mock ContactRepository for dependency injection"""
        mock_repo = Mock(spec=ContactRepository)
        mock_repo.get_all.return_value = []
        mock_repo.get_opted_out_contacts.return_value = []
        return mock_repo
    
    @pytest.fixture
    def mock_contact_flag_repository(self):
        """Mock ContactFlagRepository for dependency injection"""
        mock_repo = Mock(spec=ContactFlagRepository)
        mock_repo.get_contact_ids_with_flag_type.return_value = set()
        mock_repo.bulk_create_flags.return_value = []
        mock_repo.cleanup_expired_flags.return_value = 0
        mock_repo.commit.return_value = None
        return mock_repo
    
    @pytest.fixture
    def mock_openphone_service(self):
        """Mock OpenPhoneService for SMS sending"""
        mock_service = Mock()
        mock_service.send_message.return_value = {'success': True, 'id': 'msg_123'}
        return mock_service
    
    @pytest.fixture
    def mock_list_service(self):
        """Mock CampaignListService for list management"""
        mock_service = Mock()
        mock_service.get_list_contacts.return_value = []
        return mock_service
    
    @pytest.fixture
    def campaign_service(self, mock_campaign_repository, mock_contact_repository, 
                        mock_contact_flag_repository, mock_openphone_service, mock_list_service):
        """Create CampaignService instance with mocked dependencies"""
        return CampaignService(
            campaign_repository=mock_campaign_repository,
            contact_repository=mock_contact_repository,
            contact_flag_repository=mock_contact_flag_repository,
            openphone_service=mock_openphone_service,
            list_service=mock_list_service
        )
    
    @pytest.fixture
    def sample_campaign_data(self):
        """Sample campaign data for testing"""
        return {
            'name': 'Test Campaign',
            'campaign_type': 'blast',
            'audience_type': 'mixed',
            'channel': 'sms',
            'template_a': 'Hi {first_name}, this is a test message!',
            'daily_limit': 100,
            'business_hours_only': True
        }
    
    @pytest.fixture
    def sample_contact(self):
        """Sample contact for testing"""
        contact = Mock(spec=Contact)
        contact.id = 1
        contact.first_name = 'John'
        contact.last_name = 'Doe'
        contact.phone = '+15551234567'
        contact.email = 'john@example.com'
        return contact
    
    # ========== CAMPAIGN CREATION TESTS ==========
    
    def test_create_campaign_success(self, campaign_service, mock_campaign_repository, sample_campaign_data):
        """Test successful campaign creation with valid data"""
        # Arrange
        created_campaign = Mock(spec=Campaign)
        created_campaign.id = 1
        created_campaign.name = sample_campaign_data['name']
        created_campaign.status = 'draft'
        mock_campaign_repository.create.return_value = created_campaign
        
        # Act
        result = campaign_service.create_campaign(**sample_campaign_data)
        
        # Assert
        assert result.is_success
        assert result.data == created_campaign
        mock_campaign_repository.create.assert_called_once_with(
            name=sample_campaign_data['name'],
            campaign_type=sample_campaign_data['campaign_type'],
            audience_type=sample_campaign_data['audience_type'],
            channel=sample_campaign_data['channel'],
            template_a=sample_campaign_data['template_a'],
            template_b=None,
            daily_limit=sample_campaign_data['daily_limit'],
            business_hours_only=sample_campaign_data['business_hours_only'],
            ab_config=None,
            status='draft'
        )
        mock_campaign_repository.commit.assert_called_once()
    
    def test_create_campaign_invalid_type(self, campaign_service, sample_campaign_data):
        """Test campaign creation with invalid campaign type"""
        # Arrange
        sample_campaign_data['campaign_type'] = 'invalid_type'
        
        # Act & Assert
        with pytest.raises(ValueError, match="Campaign type must be 'blast', 'automated', or 'ab_test'"):
            campaign_service.create_campaign(**sample_campaign_data)
    
    def test_create_campaign_invalid_audience_type(self, campaign_service, sample_campaign_data):
        """Test campaign creation with invalid audience type"""
        # Arrange
        sample_campaign_data['audience_type'] = 'invalid_audience'
        
        # Act & Assert
        with pytest.raises(ValueError, match="Audience type must be 'cold', 'customer', or 'mixed'"):
            campaign_service.create_campaign(**sample_campaign_data)
    
    def test_create_campaign_invalid_channel(self, campaign_service, sample_campaign_data):
        """Test campaign creation with invalid channel"""
        # Arrange
        sample_campaign_data['channel'] = 'invalid_channel'
        
        # Act & Assert
        with pytest.raises(ValueError, match="Channel must be 'sms' or 'email'"):
            campaign_service.create_campaign(**sample_campaign_data)
    
    def test_create_campaign_email_not_supported(self, campaign_service, sample_campaign_data):
        """Test that email campaigns are not yet supported"""
        # Arrange
        sample_campaign_data['channel'] = 'email'
        
        # Act & Assert
        with pytest.raises(ValueError, match="Email campaigns coming soon with SmartLead integration"):
            campaign_service.create_campaign(**sample_campaign_data)
    
    def test_create_ab_test_campaign_success(self, campaign_service, mock_campaign_repository, sample_campaign_data):
        """Test successful A/B test campaign creation"""
        # Arrange
        sample_campaign_data['campaign_type'] = 'ab_test'
        sample_campaign_data['template_b'] = 'Hi {first_name}, this is variant B!'
        
        created_campaign = Mock(spec=Campaign)
        created_campaign.id = 1
        mock_campaign_repository.create.return_value = created_campaign
        
        # Act
        result = campaign_service.create_campaign(**sample_campaign_data)
        
        # Assert
        assert result.is_success
        assert result.data == created_campaign
        
        # Verify A/B config was created
        call_args = mock_campaign_repository.create.call_args
        ab_config = call_args.kwargs['ab_config']
        assert ab_config is not None
        assert ab_config['min_sample_size'] == 100
        assert ab_config['significance_threshold'] == 0.95
        assert ab_config['current_split'] == 50
        assert ab_config['winner_declared'] is False
        assert ab_config['winner_variant'] is None
    
    def test_create_ab_test_campaign_missing_template_b(self, campaign_service, sample_campaign_data):
        """Test A/B test campaign creation fails without template_b"""
        # Arrange
        sample_campaign_data['campaign_type'] = 'ab_test'
        # template_b is None by default
        
        # Act & Assert
        with pytest.raises(ValueError, match="A/B test campaigns require both template_a and template_b"):
            campaign_service.create_campaign(**sample_campaign_data)
    
    # ========== RECIPIENT MANAGEMENT TESTS ==========
    
    def test_add_recipients_from_list_success(self, campaign_service, mock_campaign_repository, 
                                            mock_list_service, sample_contact):
        """Test successfully adding recipients from a campaign list"""
        # Arrange
        campaign_id = 1
        list_id = 1
        contacts = [sample_contact]
        contact_ids = [sample_contact.id]
        
        # Mock the list service to return a Result.success
        from services.common.result import Result
        mock_list_service.get_list_contacts.return_value = Result.success(contacts)
        mock_campaign_repository.add_members_bulk.return_value = 1
        mock_campaign_repository.get_by_id.return_value = Mock(spec=Campaign)
        
        # Act
        result = campaign_service.add_recipients_from_list(campaign_id, list_id)
        
        # Assert
        assert result.is_success
        assert result.data == 1
        mock_list_service.get_list_contacts.assert_called_once_with(list_id)
        mock_campaign_repository.add_members_bulk.assert_called_once_with(campaign_id, contact_ids)
        mock_campaign_repository.get_by_id.assert_called_once_with(campaign_id)
        mock_campaign_repository.commit.assert_called_once()
    
    def test_add_recipients_from_list_no_list_service(self, campaign_service):
        """Test adding recipients fails when list service is not provided"""
        # Arrange
        campaign_service.list_service = None
        
        # Act
        result = campaign_service.add_recipients_from_list(1, 1)
        
        # Assert
        assert result.is_failure
        assert "CampaignListService not provided" in result.error
    
    def test_add_recipients_with_filters_success(self, campaign_service, mock_campaign_repository, 
                                               mock_contact_repository, sample_contact):
        """Test adding recipients based on contact filters"""
        # Arrange
        campaign_id = 1
        filters = {'has_name_only': True, 'exclude_opted_out': True}
        contacts = [sample_contact]
        contact_ids = [sample_contact.id]
        
        mock_campaign_repository.get_by_id.return_value = Mock(spec=Campaign)
        mock_contact_repository.get_all.return_value = contacts
        mock_contact_repository.get_opted_out_contacts.return_value = []
        mock_campaign_repository.add_members_bulk.return_value = 1
        
        # Act
        result = campaign_service.add_recipients(campaign_id, filters)
        
        # Assert
        assert result == 1
        mock_campaign_repository.get_by_id.assert_called_once_with(campaign_id)
        mock_campaign_repository.add_members_bulk.assert_called_once_with(campaign_id, contact_ids)
        mock_campaign_repository.commit.assert_called_once()
    
    def test_add_recipients_campaign_not_found(self, campaign_service, mock_campaign_repository):
        """Test adding recipients fails when campaign doesn't exist"""
        # Arrange
        campaign_id = 999
        filters = {}
        mock_campaign_repository.get_by_id.return_value = None
        
        # Act & Assert
        with pytest.raises(ValueError, match="Campaign 999 not found"):
            campaign_service.add_recipients(campaign_id, filters)
    
    def test_get_filtered_contacts_has_name_only(self, campaign_service, mock_contact_repository):
        """Test filtering contacts with real names only"""
        # Arrange
        contact_with_name = Mock(spec=Contact)
        contact_with_name.id = 1
        contact_with_name.first_name = 'John'
        
        contact_with_phone = Mock(spec=Contact)
        contact_with_phone.id = 2
        contact_with_phone.first_name = '+15551234567'
        
        mock_contact_repository.get_all.return_value = [contact_with_name, contact_with_phone]
        filters = {'has_name_only': True}
        
        # Act
        result = campaign_service._get_filtered_contacts(filters)
        
        # Assert
        assert len(result) == 1
        assert result[0] == contact_with_name
    
    def test_get_filtered_contacts_has_email(self, campaign_service, mock_contact_repository):
        """Test filtering contacts with email addresses"""
        # Arrange
        contact_with_email = Mock(spec=Contact)
        contact_with_email.id = 1
        contact_with_email.email = 'john@example.com'
        
        contact_no_email = Mock(spec=Contact)
        contact_no_email.id = 2
        contact_no_email.email = None
        
        mock_contact_repository.get_all.return_value = [contact_with_email, contact_no_email]
        filters = {'has_email': True}
        
        # Act
        result = campaign_service._get_filtered_contacts(filters)
        
        # Assert
        assert len(result) == 1
        assert result[0] == contact_with_email
    
    def test_get_filtered_contacts_exclude_opted_out(self, campaign_service, mock_contact_repository, mock_contact_flag_repository):
        """Test filtering out opted-out contacts using ContactFlagRepository"""
        # Arrange
        good_contact = Mock(spec=Contact)
        good_contact.id = 1
        
        opted_out_contact = Mock(spec=Contact)
        opted_out_contact.id = 2
        
        mock_contact_repository.get_all.return_value = [good_contact, opted_out_contact]
        # Mock that contact 2 is opted out via ContactFlagRepository
        mock_contact_flag_repository.get_contact_ids_with_flag_type.return_value = {2}
        filters = {'exclude_opted_out': True}
        
        # Act
        result = campaign_service._get_filtered_contacts(filters)
        
        # Assert
        assert len(result) == 1
        assert result[0] == good_contact
        mock_contact_flag_repository.get_contact_ids_with_flag_type.assert_called_once_with('opted_out')
    
    # ========== TESTS FOR OFFICE NUMBER FILTERING (TDD - REPOSITORY PATTERN ENFORCEMENT) ==========
    # These tests MUST FAIL initially (RED phase) to prove repository pattern violation exists
    
    def test_get_filtered_contacts_exclude_office_numbers_uses_repository_pattern(self, campaign_service, mock_contact_repository, mock_contact_flag_repository):
        """Test that exclude_office_numbers filter now uses ContactFlagRepository correctly
        
        This test was updated after fixing the repository pattern violation.
        FIXED: Now uses ContactFlagRepository.get_contact_ids_with_flag_type('office_number')
        instead of direct session.query(ContactFlag)
        """
        # Arrange
        contact1 = Mock(spec=Contact)
        contact1.id = 1
        contact1.first_name = 'John'
        contact1.phone = '+15551234567'
        
        contact2 = Mock(spec=Contact)  # Office number contact
        contact2.id = 2
        contact2.first_name = 'Business'
        contact2.phone = '+15559876543'
        
        contact3 = Mock(spec=Contact)
        contact3.id = 3
        contact3.first_name = 'Jane'
        contact3.phone = '+15555555555'
        
        all_contacts = [contact1, contact2, contact3]
        mock_contact_repository.get_all.return_value = all_contacts
        
        # Mock that contact 2 is flagged as office number via ContactFlagRepository
        mock_contact_flag_repository.get_contact_ids_with_flag_type.return_value = {2}
        
        filters = {'exclude_office_numbers': True}
        
        # Act
        result = campaign_service._get_filtered_contacts(filters)
        
        # Assert
        # Should exclude contact2 (office number)
        assert len(result) == 2
        result_ids = {contact.id for contact in result}
        assert 1 in result_ids
        assert 3 in result_ids
        assert 2 not in result_ids  # Office number excluded
        
        # Verify that ContactFlagRepository was used correctly (FIXED VIOLATION)
        mock_contact_flag_repository.get_contact_ids_with_flag_type.assert_called_once_with('office_number')
    
    def test_get_filtered_contacts_exclude_office_numbers_expected_repository_interface(self, campaign_service, mock_contact_repository, mock_contact_flag_repository):
        """Test office number filtering using the actual repository pattern implementation"""
        # Arrange
        regular_contact = Mock(spec=Contact)
        regular_contact.id = 1
        regular_contact.first_name = 'John'
        regular_contact.phone = '+15551234567'
        
        office_contact = Mock(spec=Contact)
        office_contact.id = 2
        office_contact.first_name = 'Main Office'
        office_contact.phone = '+15559876543'
        
        another_regular = Mock(spec=Contact)
        another_regular.id = 3
        another_regular.first_name = 'Jane'
        another_regular.phone = '+15555555555'
        
        all_contacts = [regular_contact, office_contact, another_regular]
        mock_contact_repository.get_all.return_value = all_contacts
        
        # Set up flag repository to return office contact ID
        mock_contact_flag_repository.get_contact_ids_with_flag_type.return_value = {2}  # office_contact ID
        
        filters = {'exclude_office_numbers': True}
        
        # Act
        result = campaign_service._get_filtered_contacts(filters)
        
        # Assert
        assert len(result) == 2, "Should exclude office_contact and return 2 contacts"
        assert regular_contact in result, "Should include regular_contact"
        assert another_regular in result, "Should include another_regular"
        assert office_contact not in result, "Should exclude office_contact"
        
        # Verify repository method is called correctly
        mock_contact_flag_repository.get_contact_ids_with_flag_type.assert_called_once_with('office_number')
    
    def test_get_filtered_contacts_exclude_office_numbers_no_office_numbers_flagged(self, campaign_service, mock_contact_repository, mock_contact_flag_repository):
        """Test exclude_office_numbers filter when no contacts are flagged as office numbers"""
        # Arrange
        contact1 = Mock(spec=Contact)
        contact1.id = 1
        contact1.first_name = 'Alice'
        
        contact2 = Mock(spec=Contact)
        contact2.id = 2
        contact2.first_name = 'Bob'
        
        contact3 = Mock(spec=Contact)
        contact3.id = 3
        contact3.first_name = 'Charlie'
        
        all_contacts = [contact1, contact2, contact3]
        mock_contact_repository.get_all.return_value = all_contacts
        
        # No office numbers flagged - empty set
        mock_contact_flag_repository.get_contact_ids_with_flag_type.return_value = set()
        
        filters = {'exclude_office_numbers': True}
        
        # Act
        result = campaign_service._get_filtered_contacts(filters)
        
        # Assert - should return all contacts since none are flagged
        assert len(result) == 3, "Should return all contacts when none are flagged"
        assert all(contact in result for contact in all_contacts), \
               "All contacts should be included when no office numbers exist"
        
        # Repository method should be called
        mock_contact_flag_repository.get_contact_ids_with_flag_type.assert_called_once_with('office_number')
    
    def test_get_filtered_contacts_exclude_office_numbers_all_contacts_are_flagged(self, campaign_service, mock_contact_repository, mock_contact_flag_repository):
        """Test exclude_office_numbers filter when all contacts are flagged as office numbers"""
        # Arrange
        office1 = Mock(spec=Contact)
        office1.id = 1
        office1.first_name = 'Main Office'
        
        office2 = Mock(spec=Contact)
        office2.id = 2
        office2.first_name = 'Branch Office'
        
        office3 = Mock(spec=Contact)
        office3.id = 3
        office3.first_name = 'Corporate Line'
        
        all_contacts = [office1, office2, office3]
        mock_contact_repository.get_all.return_value = all_contacts
        
        # All contacts are flagged as office numbers
        mock_contact_flag_repository.get_contact_ids_with_flag_type.return_value = {1, 2, 3}
        
        filters = {'exclude_office_numbers': True}
        
        # Act
        result = campaign_service._get_filtered_contacts(filters)
        
        # Assert - should return empty list since all contacts are excluded
        assert len(result) == 0, "Should return empty list when all contacts are office numbers"
        assert result == [], "Result should be empty list"
        
        # Repository method should be called
        mock_contact_flag_repository.get_contact_ids_with_flag_type.assert_called_once_with('office_number')
    
    def test_get_filtered_contacts_exclude_office_numbers_combined_with_other_filters(self, campaign_service, mock_contact_repository, mock_contact_flag_repository):
        """Test exclude_office_numbers filter combined with other filters
        
        This comprehensive test ensures the office number filtering works correctly
        when combined with other filter types in a realistic campaign scenario.
        """
        # Arrange
        good_contact = Mock(spec=Contact)
        good_contact.id = 1
        good_contact.first_name = 'John'
        good_contact.email = 'john@example.com'
        
        office_contact = Mock(spec=Contact)
        office_contact.id = 2
        office_contact.first_name = 'Main Office'
        office_contact.email = 'office@business.com'
        
        no_email_contact = Mock(spec=Contact)
        no_email_contact.id = 3
        no_email_contact.first_name = 'NoEmail'
        no_email_contact.email = None
        
        opted_out_contact = Mock(spec=Contact)
        opted_out_contact.id = 4
        opted_out_contact.first_name = 'OptedOut'
        opted_out_contact.email = 'opted@example.com'
        
        office_with_no_email = Mock(spec=Contact)
        office_with_no_email.id = 5
        office_with_no_email.first_name = 'Branch Office'
        office_with_no_email.email = None
        
        all_contacts = [good_contact, office_contact, no_email_contact, opted_out_contact, office_with_no_email]
        mock_contact_repository.get_all.return_value = all_contacts
        
        # Set up flag repository to return flagged contact IDs
        mock_contact_flag_repository.get_contact_ids_with_flag_type.side_effect = lambda flag_type: {
            'office_number': {2, 5},  # office_contact and office_with_no_email
            'opted_out': {4}  # opted_out_contact
        }.get(flag_type, set())
        
        filters = {
            'exclude_office_numbers': True,
            'has_email': True,
            'exclude_opted_out': True
        }
        
        # Act
        result = campaign_service._get_filtered_contacts(filters)
        
        # Assert
        # Expected result analysis:
        # - good_contact: ✓ has email, ✓ not opted out, ✓ not office number = INCLUDED
        # - office_contact: ✓ has email, ✓ not opted out, ✗ is office number = EXCLUDED
        # - no_email_contact: ✗ no email, ✓ not opted out, ✓ not office number = EXCLUDED
        # - opted_out_contact: ✓ has email, ✗ is opted out, ✓ not office number = EXCLUDED
        # - office_with_no_email: ✗ no email, ✓ not opted out, ✗ is office number = EXCLUDED
        
        assert len(result) == 1, f"Expected 1 contact, got {len(result)}"
        assert result[0] == good_contact, "Only good_contact should meet all criteria"
        
        # Verify repository methods were called correctly
        mock_contact_flag_repository.get_contact_ids_with_flag_type.assert_any_call('office_number')
        mock_contact_flag_repository.get_contact_ids_with_flag_type.assert_any_call('opted_out')
    
    def test_get_filtered_contacts_exclude_office_numbers_uses_correct_repository_interface(self, campaign_service, mock_contact_repository, mock_contact_flag_repository):
        """Test that the service correctly uses ContactFlagRepository for office number filtering
        
        This test verifies the service properly uses the repository pattern
        and calls the correct repository methods.
        """
        # Arrange
        contact1 = Mock(spec=Contact)
        contact1.id = 1
        contact1.first_name = 'Regular'
        
        contact2 = Mock(spec=Contact)
        contact2.id = 2
        contact2.first_name = 'Office'
        
        all_contacts = [contact1, contact2]
        mock_contact_repository.get_all.return_value = all_contacts
        
        # Set up the correct repository interface
        mock_contact_flag_repository.get_contact_ids_with_flag_type.return_value = {2}  # office contact ID
        
        filters = {'exclude_office_numbers': True}
        
        # Act
        result = campaign_service._get_filtered_contacts(filters)
        
        # Assert - Verify correct repository usage
        mock_contact_flag_repository.get_contact_ids_with_flag_type.assert_called_once_with('office_number')
        
        # Verify the filtering worked correctly
        assert len(result) == 1, "Should exclude office contact"
        assert result[0] == contact1, "Should return non-office contact"
    
    
    def test_get_filtered_contacts_exclude_office_numbers_edge_cases(self, campaign_service, mock_contact_repository, mock_contact_flag_repository):
        """Test edge cases for office number filtering"""
        # Test case 1: Empty contact list
        mock_contact_repository.get_all.return_value = []
        mock_contact_flag_repository.get_contact_ids_with_flag_type.return_value = set()
        
        result = campaign_service._get_filtered_contacts({'exclude_office_numbers': True})
        assert result == [], "Should handle empty contact list"
        
        # Test case 2: No office numbers flagged
        contact1 = Mock(spec=Contact)
        contact1.id = 1
        contact1.first_name = 'Regular'
        
        mock_contact_repository.get_all.return_value = [contact1]
        mock_contact_flag_repository.get_contact_ids_with_flag_type.return_value = set()
        
        result = campaign_service._get_filtered_contacts({'exclude_office_numbers': True})
        assert len(result) == 1, "Should return all contacts when none flagged"
        assert result[0] == contact1
        
        # Test case 3: All contacts flagged
        mock_contact_flag_repository.get_contact_ids_with_flag_type.return_value = {1}
        
        result = campaign_service._get_filtered_contacts({'exclude_office_numbers': True})
        assert result == [], "Should return empty list when all contacts flagged"

    def test_get_filtered_contacts_exclude_office_numbers_performance_with_large_dataset(self, campaign_service, mock_contact_repository, mock_contact_flag_repository):
        """Test filtering performance with large contact dataset"""
        # Create 1000 test contacts
        contacts = []
        for i in range(1000):
            contact = Mock(spec=Contact)
            contact.id = i + 1
            contact.first_name = f'Contact{i + 1}'
            contacts.append(contact)
        
        mock_contact_repository.get_all.return_value = contacts
        # First 100 are office numbers
        office_ids = set(range(1, 101))
        mock_contact_flag_repository.get_contact_ids_with_flag_type.return_value = office_ids
        
        result = campaign_service._get_filtered_contacts({'exclude_office_numbers': True})
        
        # Should exclude 100 office contacts, return 900 regular contacts
        assert len(result) == 900, f"Expected 900 contacts, got {len(result)}"
        
        # Verify repository was called correctly
        mock_contact_flag_repository.get_contact_ids_with_flag_type.assert_called_once_with('office_number')
    # ========== CAMPAIGN STATUS MANAGEMENT TESTS ==========
    
    def test_activate_campaign_success(self, campaign_service, mock_campaign_repository):
        """Test successfully activating a draft campaign"""
        # Arrange
        campaign_id = 1
        campaign = Mock(spec=Campaign)
        campaign.status = 'draft'
        mock_campaign_repository.get_by_id.return_value = campaign
        
        # Act
        result = campaign_service.activate_campaign(campaign_id)
        
        # Assert
        assert result is True
        assert campaign.status == 'running'  # Updated to match system-wide 'running' status
        mock_campaign_repository.commit.assert_called_once()
    
    def test_start_campaign_success(self, campaign_service, mock_campaign_repository):
        """Test start_campaign method as alias for activate_campaign"""
        # Arrange
        campaign_id = 1
        campaign = Mock(spec=Campaign)
        campaign.status = 'draft'
        mock_campaign_repository.get_by_id.return_value = campaign
        
        # Act
        result = campaign_service.start_campaign(campaign_id)
        
        # Assert
        assert result is True
        assert campaign.status == 'running'
        mock_campaign_repository.commit.assert_called_once()
    
    def test_activate_campaign_not_found(self, campaign_service, mock_campaign_repository):
        """Test activating non-existent campaign returns False"""
        # Arrange
        campaign_id = 999
        mock_campaign_repository.get_by_id.return_value = None
        
        # Act
        result = campaign_service.activate_campaign(campaign_id)
        
        # Assert
        assert result is False
        mock_campaign_repository.commit.assert_not_called()
    
    def test_activate_campaign_already_active(self, campaign_service, mock_campaign_repository):
        """Test activating already active campaign returns False"""
        # Arrange
        campaign_id = 1
        campaign = Mock(spec=Campaign)
        campaign.status = 'active'
        mock_campaign_repository.get_by_id.return_value = campaign
        
        # Act
        result = campaign_service.activate_campaign(campaign_id)
        
        # Assert
        assert result is False
        mock_campaign_repository.commit.assert_not_called()
    
    def test_pause_campaign_success(self, campaign_service, mock_campaign_repository):
        """Test successfully pausing a running campaign"""
        # Arrange
        campaign_id = 1
        campaign = Mock(spec=Campaign)
        campaign.status = 'running'  # Updated to use 'running' status
        mock_campaign_repository.get_by_id.return_value = campaign
        
        # Act
        result = campaign_service.pause_campaign(campaign_id)
        
        # Assert
        assert result is True
        assert campaign.status == 'paused'
        mock_campaign_repository.commit.assert_called_once()
    
    def test_pause_campaign_not_active(self, campaign_service, mock_campaign_repository):
        """Test pausing non-active campaign returns False"""
        # Arrange
        campaign_id = 1
        campaign = Mock(spec=Campaign)
        campaign.status = 'draft'
        mock_campaign_repository.get_by_id.return_value = campaign
        
        # Act
        result = campaign_service.pause_campaign(campaign_id)
        
        # Assert
        assert result is False
        mock_campaign_repository.commit.assert_not_called()
    
    def test_complete_campaign_success(self, campaign_service, mock_campaign_repository):
        """Test successfully completing a campaign"""
        # Arrange
        campaign_id = 1
        campaign = Mock(spec=Campaign)
        campaign.status = 'running'  # Updated to use 'running' status
        mock_campaign_repository.get_by_id.return_value = campaign
        
        # Act
        result = campaign_service.complete_campaign(campaign_id)
        
        # Assert
        assert result is True
        assert campaign.status == 'completed'
        mock_campaign_repository.commit.assert_called_once()
    
    # ========== DAILY LIMIT AND BUSINESS HOURS TESTS ==========
    
    def test_can_send_today_with_quota_remaining(self, campaign_service, mock_campaign_repository):
        """Test checking send quota when messages can still be sent"""
        # Arrange
        campaign_id = 1
        campaign = Mock(spec=Campaign)
        campaign.daily_limit = 100
        mock_campaign_repository.get_by_id.return_value = campaign
        mock_campaign_repository.get_today_send_count.return_value = 25
        
        # Act
        can_send, remaining = campaign_service.can_send_today(campaign_id)
        
        # Assert
        assert can_send is True
        assert remaining == 75
        mock_campaign_repository.get_today_send_count.assert_called_once_with(campaign_id)
    
    def test_can_send_today_quota_exceeded(self, campaign_service, mock_campaign_repository):
        """Test checking send quota when daily limit is reached"""
        # Arrange
        campaign_id = 1
        campaign = Mock(spec=Campaign)
        campaign.daily_limit = 100
        mock_campaign_repository.get_by_id.return_value = campaign
        mock_campaign_repository.get_today_send_count.return_value = 100
        
        # Act
        can_send, remaining = campaign_service.can_send_today(campaign_id)
        
        # Assert
        assert can_send is False
        assert remaining == 0
    
    def test_can_send_today_campaign_not_found(self, campaign_service, mock_campaign_repository):
        """Test checking send quota for non-existent campaign"""
        # Arrange
        campaign_id = 999
        mock_campaign_repository.get_by_id.return_value = None
        
        # Act
        can_send, remaining = campaign_service.can_send_today(campaign_id)
        
        # Assert
        assert can_send is False
        assert remaining == 0
    
    @patch('services.campaign_service_refactored.datetime')
    def test_is_business_hours_weekday_within_hours(self, mock_datetime, campaign_service):
        """Test business hours check during weekday business hours"""
        # Arrange - Tuesday 2 PM
        mock_now = Mock()
        mock_now.weekday.return_value = 1  # Tuesday (0=Monday)
        mock_now.time.return_value = time(14, 0)  # 2:00 PM
        mock_datetime.now.return_value = mock_now
        
        # Act
        result = campaign_service.is_business_hours()
        
        # Assert
        assert result is True
    
    @patch('services.campaign_service_refactored.datetime')
    def test_is_business_hours_weekend(self, mock_datetime, campaign_service):
        """Test business hours check during weekend"""
        # Arrange - Saturday 2 PM
        mock_now = Mock()
        mock_now.weekday.return_value = 5  # Saturday
        mock_now.time.return_value = time(14, 0)  # 2:00 PM
        mock_datetime.now.return_value = mock_now
        
        # Act
        result = campaign_service.is_business_hours()
        
        # Assert
        assert result is False
    
    @patch('services.campaign_service_refactored.datetime')
    def test_is_business_hours_weekday_outside_hours(self, mock_datetime, campaign_service):
        """Test business hours check during weekday but outside business hours"""
        # Arrange - Tuesday 8 PM
        mock_now = Mock()
        mock_now.weekday.return_value = 1  # Tuesday
        mock_now.time.return_value = time(20, 0)  # 8:00 PM
        mock_datetime.now.return_value = mock_now
        
        # Act
        result = campaign_service.is_business_hours()
        
        # Assert
        assert result is False
    
    # ========== A/B TESTING TESTS ==========
    
    @patch('services.campaign_service_refactored.random')
    def test_assign_ab_variant_50_50_split_variant_a(self, mock_random, campaign_service, mock_campaign_repository):
        """Test A/B variant assignment with 50/50 split returning A"""
        # Arrange
        campaign_id = 1
        contact_id = 1
        campaign = Mock(spec=Campaign)
        campaign.campaign_type = 'ab_test'
        campaign.ab_config = {'current_split': 50}
        
        member = Mock(spec=CampaignMembership)
        mock_campaign_repository.get_by_id.return_value = campaign
        mock_campaign_repository.get_member_by_contact.return_value = member
        mock_random.randint.return_value = 25  # <= 50, should return A
        
        # Act
        result = campaign_service.assign_ab_variant(campaign_id, contact_id)
        
        # Assert
        assert result == 'A'
        assert member.variant == 'A'
        mock_campaign_repository.commit.assert_called_once()
    
    @patch('services.campaign_service_refactored.random')
    def test_assign_ab_variant_50_50_split_variant_b(self, mock_random, campaign_service, mock_campaign_repository):
        """Test A/B variant assignment with 50/50 split returning B"""
        # Arrange
        campaign_id = 1
        contact_id = 1
        campaign = Mock(spec=Campaign)
        campaign.campaign_type = 'ab_test'
        campaign.ab_config = {'current_split': 50}
        
        member = Mock(spec=CampaignMembership)
        mock_campaign_repository.get_by_id.return_value = campaign
        mock_campaign_repository.get_member_by_contact.return_value = member
        mock_random.randint.return_value = 75  # > 50, should return B
        
        # Act
        result = campaign_service.assign_ab_variant(campaign_id, contact_id)
        
        # Assert
        assert result == 'B'
        assert member.variant == 'B'
        mock_campaign_repository.commit.assert_called_once()
    
    def test_assign_ab_variant_non_ab_test(self, campaign_service, mock_campaign_repository):
        """Test A/B variant assignment for non-A/B test campaign returns A"""
        # Arrange
        campaign_id = 1
        contact_id = 1
        campaign = Mock(spec=Campaign)
        campaign.campaign_type = 'blast'
        mock_campaign_repository.get_by_id.return_value = campaign
        
        # Act
        result = campaign_service.assign_ab_variant(campaign_id, contact_id)
        
        # Assert
        assert result == 'A'
        mock_campaign_repository.get_member_by_contact.assert_not_called()
    
    def test_assign_ab_variant_campaign_not_found(self, campaign_service, mock_campaign_repository):
        """Test A/B variant assignment for non-existent campaign returns A"""
        # Arrange
        campaign_id = 999
        contact_id = 1
        mock_campaign_repository.get_by_id.return_value = None
        
        # Act
        result = campaign_service.assign_ab_variant(campaign_id, contact_id)
        
        # Assert
        assert result == 'A'
    
    @patch('services.campaign_service_refactored.stats')
    def test_analyze_ab_test_success_with_winner(self, mock_stats, campaign_service, mock_campaign_repository):
        """Test A/B test analysis declaring a winner"""
        # Arrange
        campaign_id = 1
        campaign = Mock(spec=Campaign)
        campaign.campaign_type = 'ab_test'
        campaign.ab_config = {'min_sample_size': 100, 'significance_threshold': 0.95}
        
        mock_campaign_repository.get_by_id.return_value = campaign
        mock_campaign_repository.get_ab_test_results.return_value = {
            'A': {'sent': 150, 'responded': 30, 'response_rate': 0.2},
            'B': {'sent': 150, 'responded': 45, 'response_rate': 0.3}
        }
        
        # Mock chi-square test
        mock_stats.chi2_contingency.return_value = (10.5, 0.001, 1, None)  # Significant p-value
        
        # Act
        result = campaign_service.analyze_ab_test(campaign_id)
        
        # Assert
        assert result['status'] == 'complete'
        assert result['winner'] == 'B'  # B has higher response rate
        assert result['confidence'] > 99  # 1 - 0.001 = 99.9%
        assert campaign.ab_config['winner_declared'] is True
        assert campaign.ab_config['winner_variant'] == 'B'
        mock_campaign_repository.commit.assert_called_once()
    
    @patch('services.campaign_service_refactored.stats')
    def test_analyze_ab_test_insufficient_data(self, mock_stats, campaign_service, mock_campaign_repository):
        """Test A/B test analysis with insufficient sample size"""
        # Arrange
        campaign_id = 1
        campaign = Mock(spec=Campaign)
        campaign.campaign_type = 'ab_test'
        campaign.ab_config = {'min_sample_size': 100, 'significance_threshold': 0.95}
        
        mock_campaign_repository.get_by_id.return_value = campaign
        mock_campaign_repository.get_ab_test_results.return_value = {
            'A': {'sent': 50, 'responded': 10, 'response_rate': 0.2},  # Below min sample
            'B': {'sent': 50, 'responded': 15, 'response_rate': 0.3}   # Below min sample
        }
        
        # Act
        result = campaign_service.analyze_ab_test(campaign_id)
        
        # Assert
        assert result['status'] == 'insufficient_data'
        assert 'Need at least 100 sends per variant' in result['message']
        mock_stats.chi2_contingency.assert_not_called()
        mock_campaign_repository.commit.assert_not_called()
    
    def test_analyze_ab_test_not_ab_campaign(self, campaign_service, mock_campaign_repository):
        """Test A/B test analysis on non-A/B test campaign"""
        # Arrange
        campaign_id = 1
        campaign = Mock(spec=Campaign)
        campaign.campaign_type = 'blast'
        mock_campaign_repository.get_by_id.return_value = campaign
        
        # Act
        result = campaign_service.analyze_ab_test(campaign_id)
        
        # Assert
        assert result['error'] == 'Not an A/B test campaign'
    
    # ========== CAMPAIGN ANALYTICS TESTS ==========
    
    def test_get_campaign_stats_success(self, campaign_service, mock_campaign_repository):
        """Test retrieving campaign statistics"""
        # Arrange
        campaign_id = 1
        expected_stats = {
            'total_recipients': 100,
            'sent': 75,
            'delivered': 70,
            'responded': 15,
            'response_rate': 0.2
        }
        mock_campaign_repository.get_campaign_stats.return_value = expected_stats
        
        # Act
        result = campaign_service.get_campaign_stats(campaign_id)
        
        # Assert
        assert result == expected_stats
        mock_campaign_repository.get_campaign_stats.assert_called_once_with(campaign_id)
    
    def test_get_campaign_members_with_pagination(self, campaign_service, mock_campaign_repository):
        """Test retrieving campaign members with pagination"""
        # Arrange
        campaign_id = 1
        page = 2
        per_page = 25
        
        mock_paginated_result = Mock(spec=PaginatedResult)
        mock_paginated_result.items = []
        mock_paginated_result.total = 100
        mock_paginated_result.page = 2
        mock_paginated_result.per_page = 25
        mock_paginated_result.pages = 4
        mock_paginated_result.has_prev = True
        mock_paginated_result.has_next = True
        
        mock_campaign_repository.get_campaign_members.return_value = mock_paginated_result
        
        # Act
        result = campaign_service.get_campaign_members(campaign_id, page=page, per_page=per_page)
        
        # Assert
        assert result['total'] == 100
        assert result['page'] == 2
        assert result['per_page'] == 25
        assert result['total_pages'] == 4
        assert result['has_prev'] is True
        assert result['has_next'] is True
        
        # Verify repository was called with correct pagination
        expected_pagination = PaginationParams(page=page, per_page=per_page)
        mock_campaign_repository.get_campaign_members.assert_called_once_with(
            campaign_id, None, expected_pagination
        )
    
    def test_get_campaign_members_with_status_filter(self, campaign_service, mock_campaign_repository):
        """Test retrieving campaign members with status filter"""
        # Arrange
        campaign_id = 1
        status = 'sent'
        
        mock_paginated_result = Mock(spec=PaginatedResult)
        mock_paginated_result.items = []
        mock_paginated_result.total = 50
        mock_paginated_result.page = 1
        mock_paginated_result.per_page = 50
        mock_paginated_result.pages = 1
        mock_paginated_result.has_prev = False
        mock_paginated_result.has_next = False
        
        mock_campaign_repository.get_campaign_members.return_value = mock_paginated_result
        
        # Act
        result = campaign_service.get_campaign_members(campaign_id, status=status)
        
        # Assert
        assert result['total'] == 50
        
        # Verify repository was called with status filter
        expected_pagination = PaginationParams(page=1, per_page=50)
        mock_campaign_repository.get_campaign_members.assert_called_once_with(
            campaign_id, status, expected_pagination
        )
    
    # ========== MEMBER STATUS UPDATE TESTS ==========
    
    def test_update_member_status_success(self, campaign_service, mock_campaign_repository):
        """Test successfully updating campaign member status"""
        # Arrange
        campaign_id = 1
        contact_id = 1
        status = 'sent'
        additional_data = {'sent_at': datetime.utcnow(), 'variant': 'A'}
        
        mock_campaign_repository.update_member_status.return_value = True
        
        # Act
        result = campaign_service.update_member_status(
            campaign_id, contact_id, status, **additional_data
        )
        
        # Assert
        assert result is True
        mock_campaign_repository.update_member_status.assert_called_once_with(
            campaign_id, contact_id, status, **additional_data
        )
        mock_campaign_repository.commit.assert_called_once()
    
    def test_update_member_status_failure(self, campaign_service, mock_campaign_repository):
        """Test member status update failure"""
        # Arrange
        campaign_id = 1
        contact_id = 999  # Non-existent contact
        status = 'sent'
        
        mock_campaign_repository.update_member_status.return_value = False
        
        # Act
        result = campaign_service.update_member_status(campaign_id, contact_id, status)
        
        # Assert
        assert result is False
        mock_campaign_repository.commit.assert_not_called()
    
    # ========== CAMPAIGN CLONING TESTS ==========
    
    def test_clone_campaign_success(self, campaign_service, mock_campaign_repository):
        """Test successfully cloning a campaign"""
        # Arrange
        campaign_id = 1
        new_name = 'Cloned Campaign'
        cloned_campaign = Mock(spec=Campaign)
        cloned_campaign.id = 2
        cloned_campaign.name = new_name
        
        mock_campaign_repository.clone_campaign.return_value = cloned_campaign
        
        # Act
        result = campaign_service.clone_campaign(campaign_id, new_name)
        
        # Assert
        assert result == cloned_campaign
        mock_campaign_repository.clone_campaign.assert_called_once_with(campaign_id, new_name)
        mock_campaign_repository.commit.assert_called_once()
    
    # ========== CAMPAIGN TIMELINE TESTS ==========
    
    def test_get_campaign_timeline(self, campaign_service, mock_campaign_repository):
        """Test retrieving campaign timeline events"""
        # Arrange
        campaign_id = 1
        expected_timeline = [
            {'event': 'created', 'timestamp': datetime.utcnow()},
            {'event': 'activated', 'timestamp': datetime.utcnow()},
            {'event': 'first_send', 'timestamp': datetime.utcnow()}
        ]
        
        mock_campaign_repository.get_campaign_timeline.return_value = expected_timeline
        
        # Act
        result = campaign_service.get_campaign_timeline(campaign_id)
        
        # Assert
        assert result == expected_timeline
        mock_campaign_repository.get_campaign_timeline.assert_called_once_with(campaign_id)
    
    # ========== CAMPAIGNS NEEDING SEND TESTS ==========
    
    def test_get_campaigns_needing_send(self, campaign_service, mock_campaign_repository):
        """Test retrieving campaigns that need messages sent"""
        # Arrange
        campaigns = [Mock(spec=Campaign), Mock(spec=Campaign)]
        mock_campaign_repository.get_campaigns_needing_send.return_value = campaigns
        
        # Act
        result = campaign_service.get_campaigns_needing_send()
        
        # Assert
        assert result == campaigns
        mock_campaign_repository.get_campaigns_needing_send.assert_called_once()


# ========== FACTORY PATTERN FOR TEST DATA ==========

class CampaignFactory:
    """Factory for creating test campaign data"""
    
    @staticmethod
    def create_campaign_data(**overrides):
        """Create campaign data with optional overrides"""
        defaults = {
            'name': 'Test Campaign',
            'campaign_type': 'blast',
            'audience_type': 'mixed',
            'channel': 'sms',
            'template_a': 'Hi {first_name}, this is a test!',
            'daily_limit': 100,
            'business_hours_only': True
        }
        defaults.update(overrides)
        return defaults
    
    @staticmethod
    def create_ab_test_data(**overrides):
        """Create A/B test campaign data"""
        defaults = CampaignFactory.create_campaign_data()
        defaults.update({
            'campaign_type': 'ab_test',
            'template_b': 'Hey {first_name}, this is variant B!'
        })
        defaults.update(overrides)
        return defaults


class ContactFactory:
    """Factory for creating test contact data"""
    
    @staticmethod
    def create_contact(**overrides):
        """Create mock contact with optional overrides"""
        contact = Mock(spec=Contact)
        contact.id = overrides.get('id', 1)
        contact.first_name = overrides.get('first_name', 'John')
        contact.last_name = overrides.get('last_name', 'Doe')
        contact.phone = overrides.get('phone', '+15551234567')
        contact.email = overrides.get('email', 'john@example.com')
        return contact
    
    @staticmethod
    def create_contact_batch(count: int) -> List[Mock]:
        """Create a batch of mock contacts"""
        contacts = []
        for i in range(count):
            contact = ContactFactory.create_contact(
                id=i + 1,
                first_name=f'Contact{i + 1}',
                phone=f'+155512340{i:02d}'
            )
            contacts.append(contact)
        return contacts


# ========== INTEGRATION POINTS FOR TESTING ==========

class TestCampaignServiceIntegrationPoints:
    """Test points where CampaignService integrates with other services"""
    
    def test_repository_dependency_injection(self):
        """Test that repositories are properly injected"""
        # Arrange
        mock_campaign_repo = Mock(spec=CampaignRepository)
        mock_contact_repo = Mock(spec=ContactRepository)
        
        # Act
        service = CampaignService(
            campaign_repository=mock_campaign_repo,
            contact_repository=mock_contact_repo
        )
        
        # Assert
        assert service.campaign_repository == mock_campaign_repo
        assert service.contact_repository == mock_contact_repo
    
    def test_service_dependency_injection(self):
        """Test that external services are properly injected"""
        # Arrange
        mock_openphone = Mock()
        mock_list_service = Mock()
        
        # Act
        service = CampaignService(
            openphone_service=mock_openphone,
            list_service=mock_list_service
        )
        
        # Assert
        assert service.openphone_service == mock_openphone
        assert service.list_service == mock_list_service
    
    def test_default_repository_creation(self):
        """Test that repositories default to None when not provided for dependency injection"""
        # Arrange & Act
        service = CampaignService()
        
        # Assert - repositories should be None when not injected (dependency injection pattern)
        assert service.campaign_repository is None
        assert service.contact_repository is None
        assert service.contact_flag_repository is None