"""Comprehensive Unit Tests for CampaignService

TDD RED PHASE: These tests define expected behavior before implementation.
All tests MUST fail initially to validate TDD workflow.

Test Coverage:
- Campaign creation with validation
- Message template personalization  
- A/B variant assignment logic
- Daily limit enforcement
- Campaign status transitions
- Error handling and rollback
"""

import pytest
from unittest.mock import Mock, patch, MagicMock, call
from datetime import datetime, timedelta, time
from typing import Dict, Any, List

from services.campaign_service_refactored import CampaignService
from services.common.result import Result
from repositories.campaign_repository import CampaignRepository
from repositories.contact_repository import ContactRepository
from repositories.contact_flag_repository import ContactFlagRepository
from repositories.activity_repository import ActivityRepository
from crm_database import Campaign, Contact, CampaignMembership


class TestCampaignServiceCreation:
    """Test campaign creation functionality"""
    
    @pytest.fixture
    def campaign_service(self):
        """Create campaign service with mocked dependencies"""
        campaign_repo = Mock(spec=CampaignRepository)
        contact_repo = Mock(spec=ContactRepository)
        flag_repo = Mock(spec=ContactFlagRepository)
        activity_repo = Mock(spec=ActivityRepository)
        openphone_service = Mock()
        list_service = Mock()
        
        return CampaignService(
            campaign_repository=campaign_repo,
            contact_repository=contact_repo,
            contact_flag_repository=flag_repo,
            activity_repository=activity_repo,
            openphone_service=openphone_service,
            list_service=list_service
        )
    
    def test_create_blast_campaign_success(self, campaign_service):
        """Test successful creation of blast campaign"""
        # Arrange
        campaign_data = {
            'name': 'New Customer Blast',
            'campaign_type': 'blast',
            'audience_type': 'customer',
            'channel': 'sms',
            'template_a': 'Hi {first_name}, thanks for being a customer!',
            'daily_limit': 100,
            'business_hours_only': True
        }
        
        mock_campaign = {'id': 1, 'name': 'New Customer Blast', 'status': 'draft'}
        campaign_service.campaign_repository.create.return_value = mock_campaign
        campaign_service.campaign_repository.commit.return_value = None
        
        # Act
        result = campaign_service.create_campaign(**campaign_data)
        
        # Assert
        assert result.is_success, f"Expected success but got failure: {result.error}"
        assert result.data == mock_campaign
        
        # Verify repository calls
        campaign_service.campaign_repository.create.assert_called_once()
        create_call = campaign_service.campaign_repository.create.call_args
        assert create_call.kwargs['name'] == 'New Customer Blast'
        assert create_call.kwargs['campaign_type'] == 'blast'
        assert create_call.kwargs['audience_type'] == 'customer'
        assert create_call.kwargs['channel'] == 'sms'
        assert create_call.kwargs['template_a'] == 'Hi {first_name}, thanks for being a customer!'
        assert create_call.kwargs['daily_limit'] == 100
        assert create_call.kwargs['business_hours_only'] is True
        assert create_call.kwargs['status'] == 'draft'
        assert create_call.kwargs['ab_config'] is None  # No A/B test
        
        campaign_service.campaign_repository.commit.assert_called_once()
    
    def test_create_ab_test_campaign_success(self, campaign_service):
        """Test successful creation of A/B test campaign"""
        # Arrange
        campaign_data = {
            'name': 'A/B Test Campaign',
            'campaign_type': 'ab_test',
            'audience_type': 'cold',
            'channel': 'sms',
            'template_a': 'Hi {first_name}, option A message',
            'template_b': 'Hi {first_name}, option B message',
            'daily_limit': 125
        }
        
        mock_campaign = {'id': 2, 'name': 'A/B Test Campaign', 'status': 'draft'}
        campaign_service.campaign_repository.create.return_value = mock_campaign
        
        # Act
        result = campaign_service.create_campaign(**campaign_data)
        
        # Assert
        assert result.is_success
        assert result.data == mock_campaign
        
        # Verify A/B configuration was created
        create_call = campaign_service.campaign_repository.create.call_args
        ab_config = create_call.kwargs['ab_config']
        assert ab_config is not None
        assert ab_config['min_sample_size'] == 100
        assert ab_config['significance_threshold'] == 0.95
        assert ab_config['current_split'] == 50
        assert ab_config['winner_declared'] is False
        assert ab_config['winner_variant'] is None
    
    def test_create_campaign_invalid_type_fails(self, campaign_service):
        """Test campaign creation fails with invalid type"""
        # Arrange
        campaign_data = {
            'name': 'Invalid Campaign',
            'campaign_type': 'invalid_type',  # Invalid type
            'template_a': 'Test message'
        }
        
        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            campaign_service.create_campaign(**campaign_data)
        
        assert "Campaign type must be 'blast', 'automated', or 'ab_test'" in str(exc_info.value)
        
        # Verify no repository calls were made
        campaign_service.campaign_repository.create.assert_not_called()
    
    def test_create_campaign_invalid_audience_fails(self, campaign_service):
        """Test campaign creation fails with invalid audience type"""
        # Arrange
        campaign_data = {
            'name': 'Invalid Audience Campaign',
            'campaign_type': 'blast',
            'audience_type': 'invalid_audience',  # Invalid audience
            'template_a': 'Test message'
        }
        
        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            campaign_service.create_campaign(**campaign_data)
        
        assert "Audience type must be 'cold', 'customer', or 'mixed'" in str(exc_info.value)
    
    def test_create_campaign_invalid_channel_fails(self, campaign_service):
        """Test campaign creation fails with invalid channel"""
        # Arrange
        campaign_data = {
            'name': 'Invalid Channel Campaign',
            'campaign_type': 'blast',
            'channel': 'invalid_channel',  # Invalid channel
            'template_a': 'Test message'
        }
        
        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            campaign_service.create_campaign(**campaign_data)
        
        assert "Channel must be 'sms' or 'email'" in str(exc_info.value)
    
    def test_create_campaign_email_not_supported_fails(self, campaign_service):
        """Test campaign creation fails for email channel (not yet supported)"""
        # Arrange
        campaign_data = {
            'name': 'Email Campaign',
            'campaign_type': 'blast',
            'channel': 'email',  # Not yet supported
            'template_a': 'Test email message'
        }
        
        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            campaign_service.create_campaign(**campaign_data)
        
        assert "Email campaigns coming soon with SmartLead integration" in str(exc_info.value)
    
    def test_create_ab_test_without_template_b_fails(self, campaign_service):
        """Test A/B test campaign creation fails without template_b"""
        # Arrange
        campaign_data = {
            'name': 'AB Test No B Template',
            'campaign_type': 'ab_test',
            'template_a': 'Template A message'
            # Missing template_b
        }
        
        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            campaign_service.create_campaign(**campaign_data)
        
        assert "A/B test campaigns require both template_a and template_b" in str(exc_info.value)
    
    def test_create_campaign_repository_error_returns_failure(self, campaign_service):
        """Test campaign creation handles repository errors gracefully"""
        # Arrange
        campaign_data = {
            'name': 'Error Campaign',
            'campaign_type': 'blast',
            'template_a': 'Test message'
        }
        
        campaign_service.campaign_repository.create.side_effect = Exception("Database error")
        
        # Act
        result = campaign_service.create_campaign(**campaign_data)
        
        # Assert
        assert result.is_failure
        assert "Failed to create campaign: Database error" in result.error
        assert result.code == "CREATE_ERROR"


class TestCampaignServiceTemplatePersonalization:
    """Test message template personalization functionality"""
    
    @pytest.fixture
    def campaign_service(self):
        """Create campaign service for template tests"""
        return CampaignService(
            campaign_repository=Mock(),
            contact_repository=Mock(),
            contact_flag_repository=Mock(),
            activity_repository=Mock(),
            openphone_service=Mock(),
            list_service=Mock()
        )
    
    def test_personalize_message_with_first_name(self, campaign_service):
        """Test message personalization with first name"""
        # Arrange
        template = "Hi {first_name}, how are you today?"
        mock_contact = Mock()
        mock_contact.first_name = "John"
        mock_contact.last_name = "Doe"
        mock_contact.name = "John Doe"
        mock_contact.company_name = "Acme Corp"
        
        # Act
        result = campaign_service._personalize_message(template, mock_contact)
        
        # Assert
        assert result == "Hi John, how are you today?"
    
    def test_personalize_message_with_multiple_placeholders(self, campaign_service):
        """Test message personalization with multiple placeholders"""
        # Arrange
        template = "Hi {first_name} {last_name} from {company}, we have an offer for you!"
        mock_contact = Mock()
        mock_contact.first_name = "Jane"
        mock_contact.last_name = "Smith"
        mock_contact.company_name = "Tech Solutions"
        mock_contact.name = "Jane Smith"
        
        # Act
        result = campaign_service._personalize_message(template, mock_contact)
        
        # Assert
        assert result == "Hi Jane Smith from Tech Solutions, we have an offer for you!"
    
    def test_personalize_message_skips_phone_number_as_name(self, campaign_service):
        """Test that phone numbers are not used as names in personalization"""
        # Arrange
        template = "Hi {first_name}, thanks for your interest!"
        mock_contact = Mock()
        mock_contact.first_name = "+15551234567"  # Phone number as name
        mock_contact.last_name = "(from OpenPhone)"
        
        # Act
        result = campaign_service._personalize_message(template, mock_contact)
        
        # Assert
        assert result == "Hi , thanks for your interest!"  # Empty replacement
    
    def test_personalize_message_skips_openphone_artifacts(self, campaign_service):
        """Test that OpenPhone artifacts like '(from OpenPhone)' are filtered out"""
        # Arrange
        template = "Hello {first_name} {last_name}!"
        mock_contact = Mock()
        mock_contact.first_name = "John"
        mock_contact.last_name = "(from OpenPhone)"  # OpenPhone artifact
        
        # Act
        result = campaign_service._personalize_message(template, mock_contact)
        
        # Assert
        assert result == "Hello John !"  # Last name filtered out
    
    def test_personalize_message_handles_missing_attributes(self, campaign_service):
        """Test personalization handles contacts with missing attributes gracefully"""
        # Arrange
        template = "Hi {first_name}, your company {company} is great!"
        mock_contact = Mock(spec=[])  # No attributes
        
        # Act
        result = campaign_service._personalize_message(template, mock_contact)
        
        # Assert
        assert result == "Hi {first_name}, your company {company} is great!"  # Unchanged
    
    def test_personalize_message_handles_none_template(self, campaign_service):
        """Test personalization handles None template gracefully"""
        # Arrange
        template = None
        mock_contact = Mock()
        
        # Act
        result = campaign_service._personalize_message(template, mock_contact)
        
        # Assert
        assert result == ""
    
    def test_personalize_message_handles_empty_template(self, campaign_service):
        """Test personalization handles empty template"""
        # Arrange
        template = ""
        mock_contact = Mock()
        
        # Act
        result = campaign_service._personalize_message(template, mock_contact)
        
        # Assert
        assert result == ""


class TestCampaignServiceABVariantAssignment:
    """Test A/B variant assignment logic"""
    
    @pytest.fixture
    def campaign_service(self):
        """Create campaign service for A/B testing"""
        campaign_repo = Mock(spec=CampaignRepository)
        return CampaignService(
            campaign_repository=campaign_repo,
            contact_repository=Mock(),
            contact_flag_repository=Mock(),
            activity_repository=Mock(),
            openphone_service=Mock(),
            list_service=Mock()
        )
    
    def test_assign_ab_variant_for_ab_test_campaign(self, campaign_service):
        """Test A/B variant assignment for A/B test campaign"""
        # Arrange
        campaign_id = 1
        contact_id = 100
        
        mock_campaign = Mock()
        mock_campaign.campaign_type = 'ab_test'
        mock_campaign.ab_config = {
            'current_split': 50,  # 50/50 split
            'min_sample_size': 100
        }
        
        mock_member = Mock()
        mock_member.variant = None
        
        campaign_service.campaign_repository.get_by_id.return_value = mock_campaign
        campaign_service.campaign_repository.get_member_by_contact.return_value = mock_member
        
        # Mock random to always return A variant
        with patch('services.campaign_service_refactored.random.randint', return_value=30):  # 30 <= 50, so A
            # Act
            result = campaign_service.assign_ab_variant(campaign_id, contact_id)
        
        # Assert
        assert result == 'A'
        assert mock_member.variant == 'A'
        campaign_service.campaign_repository.commit.assert_called_once()
    
    def test_assign_ab_variant_returns_b_for_high_random(self, campaign_service):
        """Test A/B variant assignment returns B for high random values"""
        # Arrange
        campaign_id = 1
        contact_id = 100
        
        mock_campaign = Mock()
        mock_campaign.campaign_type = 'ab_test'
        mock_campaign.ab_config = {'current_split': 50}
        
        mock_member = Mock()
        campaign_service.campaign_repository.get_by_id.return_value = mock_campaign
        campaign_service.campaign_repository.get_member_by_contact.return_value = mock_member
        
        # Mock random to return B variant
        with patch('services.campaign_service_refactored.random.randint', return_value=70):  # 70 > 50, so B
            # Act
            result = campaign_service.assign_ab_variant(campaign_id, contact_id)
        
        # Assert
        assert result == 'B'
        assert mock_member.variant == 'B'
    
    def test_assign_ab_variant_respects_custom_split(self, campaign_service):
        """Test A/B variant assignment respects custom split percentages"""
        # Arrange
        campaign_id = 1
        contact_id = 100
        
        mock_campaign = Mock()
        mock_campaign.campaign_type = 'ab_test'
        mock_campaign.ab_config = {'current_split': 70}  # 70/30 split favoring A
        
        mock_member = Mock()
        campaign_service.campaign_repository.get_by_id.return_value = mock_campaign
        campaign_service.campaign_repository.get_member_by_contact.return_value = mock_member
        
        # Mock random to return A variant (within 70%)
        with patch('services.campaign_service_refactored.random.randint', return_value=60):  # 60 <= 70, so A
            # Act
            result = campaign_service.assign_ab_variant(campaign_id, contact_id)
        
        # Assert
        assert result == 'A'
    
    def test_assign_ab_variant_non_ab_campaign_returns_a(self, campaign_service):
        """Test A/B variant assignment for non-A/B campaign defaults to A"""
        # Arrange
        campaign_id = 1
        contact_id = 100
        
        mock_campaign = Mock()
        mock_campaign.campaign_type = 'blast'  # Not A/B test
        
        campaign_service.campaign_repository.get_by_id.return_value = mock_campaign
        
        # Act
        result = campaign_service.assign_ab_variant(campaign_id, contact_id)
        
        # Assert
        assert result == 'A'
        # Should not attempt to get member or commit
        campaign_service.campaign_repository.get_member_by_contact.assert_not_called()
        campaign_service.campaign_repository.commit.assert_not_called()
    
    def test_assign_ab_variant_campaign_not_found_returns_a(self, campaign_service):
        """Test A/B variant assignment when campaign not found defaults to A"""
        # Arrange
        campaign_id = 999  # Non-existent
        contact_id = 100
        
        campaign_service.campaign_repository.get_by_id.return_value = None
        
        # Act
        result = campaign_service.assign_ab_variant(campaign_id, contact_id)
        
        # Assert
        assert result == 'A'
    
    def test_assign_ab_variant_handles_missing_ab_config(self, campaign_service):
        """Test A/B variant assignment handles missing ab_config"""
        # Arrange
        campaign_id = 1
        contact_id = 100
        
        mock_campaign = Mock()
        mock_campaign.campaign_type = 'ab_test'
        mock_campaign.ab_config = None  # Missing config
        
        mock_member = Mock()
        campaign_service.campaign_repository.get_by_id.return_value = mock_campaign
        campaign_service.campaign_repository.get_member_by_contact.return_value = mock_member
        
        # Act
        result = campaign_service.assign_ab_variant(campaign_id, contact_id)
        
        # Assert
        assert result in ['A', 'B']  # Should still assign something


class TestCampaignServiceDailyLimitEnforcement:
    """Test daily limit enforcement functionality"""
    
    @pytest.fixture
    def campaign_service(self):
        """Create campaign service for daily limit tests"""
        campaign_repo = Mock(spec=CampaignRepository)
        return CampaignService(
            campaign_repository=campaign_repo,
            contact_repository=Mock(),
            contact_flag_repository=Mock(),
            activity_repository=Mock(),
            openphone_service=Mock(),
            list_service=Mock()
        )
    
    def test_can_send_today_within_limit(self, campaign_service):
        """Test can_send_today returns True when within daily limit"""
        # Arrange
        campaign_id = 1
        
        mock_campaign = Mock()
        mock_campaign.daily_limit = 100
        
        campaign_service.campaign_repository.get_by_id.return_value = mock_campaign
        campaign_service.campaign_repository.get_today_send_count.return_value = 50  # Within limit
        
        # Act
        can_send, remaining = campaign_service.can_send_today(campaign_id)
        
        # Assert
        assert can_send is True
        assert remaining == 50  # 100 - 50 = 50 remaining
    
    def test_can_send_today_at_limit(self, campaign_service):
        """Test can_send_today returns False when at daily limit"""
        # Arrange
        campaign_id = 1
        
        mock_campaign = Mock()
        mock_campaign.daily_limit = 100
        
        campaign_service.campaign_repository.get_by_id.return_value = mock_campaign
        campaign_service.campaign_repository.get_today_send_count.return_value = 100  # At limit
        
        # Act
        can_send, remaining = campaign_service.can_send_today(campaign_id)
        
        # Assert
        assert can_send is False
        assert remaining == 0
    
    def test_can_send_today_over_limit(self, campaign_service):
        """Test can_send_today returns False when over daily limit"""
        # Arrange
        campaign_id = 1
        
        mock_campaign = Mock()
        mock_campaign.daily_limit = 100
        
        campaign_service.campaign_repository.get_by_id.return_value = mock_campaign
        campaign_service.campaign_repository.get_today_send_count.return_value = 120  # Over limit
        
        # Act
        can_send, remaining = campaign_service.can_send_today(campaign_id)
        
        # Assert
        assert can_send is False
        assert remaining == -20  # Negative remaining
    
    def test_can_send_today_campaign_not_found(self, campaign_service):
        """Test can_send_today handles campaign not found"""
        # Arrange
        campaign_id = 999
        
        campaign_service.campaign_repository.get_by_id.return_value = None
        
        # Act
        can_send, remaining = campaign_service.can_send_today(campaign_id)
        
        # Assert
        assert can_send is False
        assert remaining == 0


class TestCampaignServiceStatusTransitions:
    """Test campaign status transition functionality"""
    
    @pytest.fixture
    def campaign_service(self):
        """Create campaign service for status tests"""
        campaign_repo = Mock(spec=CampaignRepository)
        return CampaignService(
            campaign_repository=campaign_repo,
            contact_repository=Mock(),
            contact_flag_repository=Mock(),
            activity_repository=Mock(),
            openphone_service=Mock(),
            list_service=Mock()
        )
    
    def test_activate_campaign_from_draft_success(self, campaign_service):
        """Test successful activation of draft campaign"""
        # Arrange
        campaign_id = 1
        
        mock_campaign = Mock()
        mock_campaign.status = 'draft'
        
        campaign_service.campaign_repository.get_by_id.return_value = mock_campaign
        
        # Act
        result = campaign_service.activate_campaign(campaign_id)
        
        # Assert
        assert result is True
        assert mock_campaign.status == 'running'
        campaign_service.campaign_repository.commit.assert_called_once()
    
    def test_activate_campaign_already_running_fails(self, campaign_service):
        """Test activation of already running campaign fails"""
        # Arrange
        campaign_id = 1
        
        mock_campaign = Mock()
        mock_campaign.status = 'running'  # Already running
        
        campaign_service.campaign_repository.get_by_id.return_value = mock_campaign
        
        # Act
        result = campaign_service.activate_campaign(campaign_id)
        
        # Assert
        assert result is False
        assert mock_campaign.status == 'running'  # Unchanged
        campaign_service.campaign_repository.commit.assert_not_called()
    
    def test_pause_campaign_from_running_success(self, campaign_service):
        """Test successful pausing of running campaign"""
        # Arrange
        campaign_id = 1
        
        mock_campaign = Mock()
        mock_campaign.status = 'running'
        
        campaign_service.campaign_repository.get_by_id.return_value = mock_campaign
        
        # Act
        result = campaign_service.pause_campaign(campaign_id)
        
        # Assert
        assert result is True
        assert mock_campaign.status == 'paused'
        campaign_service.campaign_repository.commit.assert_called_once()
    
    def test_pause_campaign_not_running_fails(self, campaign_service):
        """Test pausing of non-running campaign fails"""
        # Arrange
        campaign_id = 1
        
        mock_campaign = Mock()
        mock_campaign.status = 'draft'  # Not running
        
        campaign_service.campaign_repository.get_by_id.return_value = mock_campaign
        
        # Act
        result = campaign_service.pause_campaign(campaign_id)
        
        # Assert
        assert result is False
        assert mock_campaign.status == 'draft'  # Unchanged
    
    def test_complete_campaign_success(self, campaign_service):
        """Test successful completion of campaign"""
        # Arrange
        campaign_id = 1
        
        mock_campaign = Mock()
        mock_campaign.status = 'running'
        
        campaign_service.campaign_repository.get_by_id.return_value = mock_campaign
        
        # Act
        result = campaign_service.complete_campaign(campaign_id)
        
        # Assert
        assert result is True
        assert mock_campaign.status == 'completed'
        campaign_service.campaign_repository.commit.assert_called_once()
    
    def test_status_transition_campaign_not_found_fails(self, campaign_service):
        """Test status transitions fail when campaign not found"""
        # Arrange
        campaign_id = 999
        
        campaign_service.campaign_repository.get_by_id.return_value = None
        
        # Act & Assert
        assert campaign_service.activate_campaign(campaign_id) is False
        assert campaign_service.pause_campaign(campaign_id) is False
        assert campaign_service.complete_campaign(campaign_id) is False


class TestCampaignServiceBusinessHours:
    """Test business hours functionality"""
    
    @pytest.fixture
    def campaign_service(self):
        """Create campaign service for business hours tests"""
        return CampaignService(
            campaign_repository=Mock(),
            contact_repository=Mock(),
            contact_flag_repository=Mock(),
            activity_repository=Mock(),
            openphone_service=Mock(),
            list_service=Mock()
        )
    
    def test_is_business_hours_weekday_within_hours(self, campaign_service):
        """Test business hours check for weekday within hours"""
        # Arrange - Mock datetime to Tuesday 2:00 PM
        mock_datetime = Mock()
        mock_datetime.weekday.return_value = 1  # Tuesday (0=Monday)
        mock_datetime.time.return_value = time(14, 0)  # 2:00 PM
        
        with patch('services.campaign_service_refactored.datetime') as mock_dt:
            mock_dt.now.return_value = mock_datetime
            
            # Act
            result = campaign_service.is_business_hours()
        
        # Assert
        assert result is True
    
    def test_is_business_hours_weekday_before_hours(self, campaign_service):
        """Test business hours check for weekday before hours"""
        # Arrange - Mock datetime to Tuesday 7:00 AM (before 9 AM)
        mock_datetime = Mock()
        mock_datetime.weekday.return_value = 1  # Tuesday
        mock_datetime.time.return_value = time(7, 0)  # 7:00 AM
        
        with patch('services.campaign_service_refactored.datetime') as mock_dt:
            mock_dt.now.return_value = mock_datetime
            
            # Act
            result = campaign_service.is_business_hours()
        
        # Assert
        assert result is False
    
    def test_is_business_hours_weekday_after_hours(self, campaign_service):
        """Test business hours check for weekday after hours"""
        # Arrange - Mock datetime to Tuesday 7:00 PM (after 6 PM)
        mock_datetime = Mock()
        mock_datetime.weekday.return_value = 1  # Tuesday
        mock_datetime.time.return_value = time(19, 0)  # 7:00 PM
        
        with patch('services.campaign_service_refactored.datetime') as mock_dt:
            mock_dt.now.return_value = mock_datetime
            
            # Act
            result = campaign_service.is_business_hours()
        
        # Assert
        assert result is False
    
    def test_is_business_hours_weekend(self, campaign_service):
        """Test business hours check for weekend"""
        # Arrange - Mock datetime to Saturday 2:00 PM
        mock_datetime = Mock()
        mock_datetime.weekday.return_value = 5  # Saturday
        mock_datetime.time.return_value = time(14, 0)  # 2:00 PM
        
        with patch('services.campaign_service_refactored.datetime') as mock_dt:
            mock_dt.now.return_value = mock_datetime
            
            # Act
            result = campaign_service.is_business_hours()
        
        # Assert
        assert result is False


class TestCampaignServiceErrorHandling:
    """Test error handling and rollback functionality"""
    
    @pytest.fixture
    def campaign_service(self):
        """Create campaign service for error handling tests"""
        campaign_repo = Mock(spec=CampaignRepository)
        return CampaignService(
            campaign_repository=campaign_repo,
            contact_repository=Mock(),
            contact_flag_repository=Mock(),
            activity_repository=Mock(),
            openphone_service=Mock(),
            list_service=Mock()
        )
    
    def test_add_recipients_campaign_not_found_raises_error(self, campaign_service):
        """Test add_recipients raises error when campaign not found"""
        # Arrange
        campaign_id = 999
        contact_filters = {'has_email': True}
        
        campaign_service.campaign_repository.get_by_id.return_value = None
        
        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            campaign_service.add_recipients(campaign_id, contact_filters)
        
        assert f"Campaign {campaign_id} not found" in str(exc_info.value)
    
    def test_personalize_message_handles_exception_gracefully(self, campaign_service):
        """Test message personalization handles exceptions gracefully"""
        # Arrange
        template = "Hi {first_name}!"
        mock_contact = Mock()
        mock_contact.first_name = Mock(side_effect=Exception("Attribute error"))
        
        # Act
        result = campaign_service._personalize_message(template, mock_contact)
        
        # Assert
        assert result == template  # Should return original template on error
    
    def test_get_campaign_analytics_handles_exception(self, campaign_service):
        """Test campaign analytics handles repository exceptions gracefully"""
        # Arrange
        campaign_id = 1
        
        campaign_service.campaign_repository.get_campaign_memberships.side_effect = Exception("DB error")
        
        # Act
        result = campaign_service.get_campaign_analytics(campaign_id)
        
        # Assert
        assert result['sent_count'] == 0
        assert result['response_count'] == 0
        assert result['response_rate'] == 0
        assert result['total_recipients'] == 0
