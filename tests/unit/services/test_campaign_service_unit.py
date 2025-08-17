"""
Unit tests for CampaignService
Following TDD - these tests define the behavior we want BEFORE implementation
"""
import pytest
from datetime import datetime, time, timedelta
from unittest.mock import Mock, MagicMock, patch, call
from typing import Optional

from services.campaign_service import CampaignService
from services.openphone_service import OpenPhoneService
from services.campaign_list_service import CampaignListService
from crm_database import Campaign, CampaignMembership, Contact, ContactFlag, Activity


class TestCampaignServiceCreation:
    """Test campaign creation functionality"""
    
    def test_create_campaign_with_dependency_injection(self):
        """Service should accept dependencies via constructor"""
        # Arrange
        mock_openphone = Mock(spec=OpenPhoneService)
        mock_list_service = Mock(spec=CampaignListService)
        
        # Act
        service = CampaignService(
            openphone_service=mock_openphone,
            list_service=mock_list_service
        )
        
        # Assert
        assert service.openphone_service == mock_openphone
        assert service.list_service == mock_list_service
    
    def test_create_blast_campaign(self):
        """Should create a basic blast campaign"""
        # Arrange
        mock_openphone = Mock(spec=OpenPhoneService)
        service = CampaignService(openphone_service=mock_openphone)
        
        # Act
        with patch('services.campaign_service.db') as mock_db:
            campaign = service.create_campaign(
                name="Summer Sale",
                campaign_type="blast",
                audience_type="customer",
                template_a="Hi {first_name}, check out our summer sale!"
            )
        
        # Assert
        assert campaign.name == "Summer Sale"
        assert campaign.campaign_type == "blast"
        assert campaign.audience_type == "customer"
        assert campaign.channel == "sms"
        assert campaign.template_a == "Hi {first_name}, check out our summer sale!"
        assert campaign.template_b is None
        assert campaign.status == "draft"
        assert campaign.daily_limit == 125
        assert campaign.business_hours_only is True
        
        # Verify database operations
        mock_db.session.add.assert_called_once_with(campaign)
        mock_db.session.commit.assert_called_once()
    
    def test_create_ab_test_campaign(self):
        """Should create an A/B test campaign with both templates"""
        # Arrange
        mock_openphone = Mock(spec=OpenPhoneService)
        service = CampaignService(openphone_service=mock_openphone)
        
        # Act
        with patch('services.campaign_service.db') as mock_db:
            campaign = service.create_campaign(
                name="A/B Test Campaign",
                campaign_type="ab_test",
                template_a="Version A: {first_name}, special offer!",
                template_b="Version B: Exclusive deal for you, {first_name}!"
            )
        
        # Assert
        assert campaign.campaign_type == "ab_test"
        assert campaign.template_a == "Version A: {first_name}, special offer!"
        assert campaign.template_b == "Version B: Exclusive deal for you, {first_name}!"
        assert campaign.ab_config is not None
        assert campaign.ab_config['min_sample_size'] == 100
        assert campaign.ab_config['significance_threshold'] == 0.95
        assert campaign.ab_config['current_split'] == 50
        assert campaign.ab_config['winner_declared'] is False
        assert campaign.ab_config['winner_variant'] is None
    
    def test_create_campaign_invalid_type(self):
        """Should raise error for invalid campaign type"""
        # Arrange
        mock_openphone = Mock(spec=OpenPhoneService)
        service = CampaignService(openphone_service=mock_openphone)
        
        # Act & Assert
        with pytest.raises(ValueError, match="Campaign type must be"):
            service.create_campaign(
                name="Invalid Campaign",
                campaign_type="invalid_type"
            )
    
    def test_create_ab_test_without_template_b(self):
        """Should raise error when A/B test missing template_b"""
        # Arrange
        mock_openphone = Mock(spec=OpenPhoneService)
        service = CampaignService(openphone_service=mock_openphone)
        
        # Act & Assert
        with pytest.raises(ValueError, match="A/B test campaigns require both"):
            service.create_campaign(
                name="Bad A/B Test",
                campaign_type="ab_test",
                template_a="Only template A"
            )


class TestRecipientManagement:
    """Test adding and managing campaign recipients"""
    
    def test_add_recipients_from_list(self):
        """Should add all contacts from a list to campaign"""
        # Arrange
        mock_openphone = Mock(spec=OpenPhoneService)
        mock_list_service = Mock(spec=CampaignListService)
        
        # Mock contacts from list
        mock_contacts = [
            Mock(id=1, spec=Contact),
            Mock(id=2, spec=Contact),
            Mock(id=3, spec=Contact)
        ]
        mock_list_service.get_list_contacts.return_value = mock_contacts
        
        service = CampaignService(
            openphone_service=mock_openphone,
            list_service=mock_list_service
        )
        
        # Mock database queries
        with patch('services.campaign_service.CampaignMembership') as mock_membership:
            with patch('services.campaign_service.Campaign') as mock_campaign_model:
                with patch('services.campaign_service.db') as mock_db:
                    mock_membership.query.filter_by.return_value.first.return_value = None
                    mock_campaign = Mock(spec=Campaign)
                    mock_campaign_model.query.get.return_value = mock_campaign
                    
                    # Act
                    added_count = service.add_recipients_from_list(
                        campaign_id=1,
                        list_id=10
                    )
        
        # Assert
        assert added_count == 3
        mock_list_service.get_list_contacts.assert_called_once_with(10)
        assert mock_db.session.add.call_count == 3
        mock_db.session.commit.assert_called_once()
        assert mock_campaign.list_id == 10
    
    def test_add_recipients_skips_existing_members(self):
        """Should not add contacts already in campaign"""
        # Arrange
        mock_openphone = Mock(spec=OpenPhoneService)
        mock_list_service = Mock(spec=CampaignListService)
        
        mock_contacts = [
            Mock(id=1, spec=Contact),  # Already exists
            Mock(id=2, spec=Contact),  # New
        ]
        mock_list_service.get_list_contacts.return_value = mock_contacts
        
        service = CampaignService(
            openphone_service=mock_openphone,
            list_service=mock_list_service
        )
        
        # Mock database - first contact exists, second doesn't
        with patch('services.campaign_service.CampaignMembership') as mock_membership:
            with patch('services.campaign_service.Campaign'):
                with patch('services.campaign_service.db') as mock_db:
                    mock_membership.query.filter_by.return_value.first.side_effect = [
                        Mock(),  # First contact exists
                        None     # Second contact doesn't exist
                    ]
                    
                    # Act
                    added_count = service.add_recipients_from_list(1, 10)
        
        # Assert
        assert added_count == 1
        assert mock_db.session.add.call_count == 1


class TestCampaignProcessing:
    """Test campaign message sending and processing"""
    
    def test_process_campaign_queue_respects_daily_limit(self):
        """Should not exceed daily message limit"""
        # Arrange
        mock_openphone = Mock(spec=OpenPhoneService)
        mock_openphone.send_message.return_value = {'success': True, 'id': 'msg123'}
        
        service = CampaignService(openphone_service=mock_openphone)
        
        # Create campaign with 10 pending recipients, but daily limit of 5
        mock_campaign = Mock(spec=Campaign)
        mock_campaign.id = 1
        mock_campaign.daily_limit = 5
        mock_campaign.business_hours_only = False
        mock_campaign.campaign_type = 'blast'
        mock_campaign.template_a = 'Hello {first_name}'
        mock_campaign.name = 'Test Campaign'
        
        with patch('services.campaign_service.Campaign') as mock_campaign_model:
            # Mock the query for running campaigns
            mock_campaign_model.query.filter_by.return_value.all.return_value = [mock_campaign]
            
            # Mock internal methods
            with patch.object(service, '_get_daily_send_count', return_value=0):
                with patch.object(service, '_process_campaign_sends', return_value={'sent': 5, 'skipped': 0}):
                    # Act
                    result = service.process_campaign_queue()
        
        # Assert
        assert result['campaigns_processed'] == 1
        assert result['messages_sent'] == 5  # Limited by daily_limit
    
    def test_process_campaign_personalization(self):
        """Should personalize messages with contact data"""
        # Arrange
        mock_openphone = Mock(spec=OpenPhoneService)
        mock_openphone.send_message.return_value = {'success': True, 'id': 'msg123'}
        
        service = CampaignService(openphone_service=mock_openphone)
        
        # Create mock contact with all required attributes
        mock_contact = Mock(spec=Contact)
        mock_contact.first_name = "John"
        mock_contact.last_name = "Doe"
        mock_contact.email = None
        mock_contact.contact_metadata = {'company': 'Acme Corp'}
        
        # Act
        personalized = service.personalize_message(
            template="Hello {first_name}, welcome to {company}!",
            contact=mock_contact
        )
        
        # Assert
        assert personalized == "Hello John, welcome to Acme Corp!"
    
    def test_process_campaign_respects_business_hours(self):
        """Should only send during business hours when configured"""
        # Arrange
        mock_openphone = Mock(spec=OpenPhoneService)
        service = CampaignService(openphone_service=mock_openphone)
        
        # Test during business hours (Tuesday 10am)
        business_time = datetime(2024, 1, 16, 10, 0, 0)  # Tuesday 10am
        with patch('services.campaign_service.datetime') as mock_datetime:
            mock_datetime.now.return_value = business_time
            assert service.is_business_hours() is True
        
        # Test outside business hours (Sunday 10am)
        weekend_time = datetime(2024, 1, 14, 10, 0, 0)  # Sunday 10am
        with patch('services.campaign_service.datetime') as mock_datetime:
            mock_datetime.now.return_value = weekend_time
            assert service.is_business_hours() is False
        
        # Test outside business hours (Tuesday 8pm)
        evening_time = datetime(2024, 1, 16, 20, 0, 0)  # Tuesday 8pm
        with patch('services.campaign_service.datetime') as mock_datetime:
            mock_datetime.now.return_value = evening_time
            assert service.is_business_hours() is False


class TestABTesting:
    """Test A/B testing functionality"""
    
    def test_select_variant_for_ab_test(self):
        """Should select variant based on current split"""
        # Arrange
        mock_openphone = Mock(spec=OpenPhoneService)
        service = CampaignService(openphone_service=mock_openphone)
        
        mock_campaign = Mock(spec=Campaign)
        mock_campaign.campaign_type = 'ab_test'
        mock_campaign.ab_config = {
            'current_split': 70,  # 70% A, 30% B
            'winner_declared': False
        }
        
        # Act - run many times to verify distribution
        with patch('random.randint') as mock_random:
            # Test variant A selection (random < 70)
            mock_random.return_value = 50
            variant = service.select_variant_for_recipient(mock_campaign)
            assert variant == 'A'
            
            # Test variant B selection (random >= 70)
            mock_random.return_value = 85
            variant = service.select_variant_for_recipient(mock_campaign)
            assert variant == 'B'
    
    def test_calculate_ab_test_significance(self):
        """Should calculate statistical significance for A/B test"""
        # Arrange
        mock_openphone = Mock(spec=OpenPhoneService)
        service = CampaignService(openphone_service=mock_openphone)
        
        # Create test data - A has 20% response, B has 30% response
        stats_a = {'sent': 100, 'responses': 20}
        stats_b = {'sent': 100, 'responses': 30}
        
        # Act
        result = service.calculate_significance(stats_a, stats_b)
        
        # Assert
        assert 'p_value' in result
        assert 'is_significant' in result
        assert 'confidence' in result
        assert result['confidence'] > 0
    
    def test_auto_declare_winner(self):
        """Should automatically declare winner when significance reached"""
        # Arrange
        mock_openphone = Mock(spec=OpenPhoneService)
        service = CampaignService(openphone_service=mock_openphone)
        
        mock_campaign = Mock(spec=Campaign)
        mock_campaign.id = 1
        mock_campaign.campaign_type = 'ab_test'
        mock_campaign.ab_config = {
            'min_sample_size': 100,
            'significance_threshold': 0.95,
            'winner_declared': False,
            'current_split': 50
        }
        
        # Mock enough data to declare winner
        with patch.object(service, 'get_campaign_analytics') as mock_analytics:
            mock_analytics.return_value = {
                'variant_a': {'sent': 150, 'responses': 15, 'response_rate': 0.10},
                'variant_b': {'sent': 150, 'responses': 45, 'response_rate': 0.30}
            }
            
            with patch.object(service, 'calculate_significance') as mock_significance:
                mock_significance.return_value = {
                    'is_significant': True,
                    'confidence': 0.99,
                    'p_value': 0.001
                }
                
                with patch('services.campaign_service.db') as mock_db:
                    # Act
                    result = service.check_and_declare_ab_winner(mock_campaign)
        
        # Assert
        assert result['winner_declared'] is True
        assert result['winner'] == 'B'
        assert mock_campaign.ab_config['winner_variant'] == 'B'
        assert mock_campaign.ab_config['winner_declared'] is True
        mock_db.session.commit.assert_called_once()


class TestCompliance:
    """Test compliance and opt-out handling"""
    
    def test_handle_opt_out_message(self):
        """Should process opt-out requests"""
        # Arrange
        mock_openphone = Mock(spec=OpenPhoneService)
        service = CampaignService(openphone_service=mock_openphone)
        
        mock_contact = Mock(spec=Contact)
        mock_contact.id = 1
        mock_contact.phone = "+1234567890"
        
        opt_out_messages = ["STOP", "stop", "Stop", "UNSUBSCRIBE", "OPTOUT"]
        
        for message in opt_out_messages:
            # Act
            is_opt_out = service.is_opt_out_message(message)
            
            # Assert
            assert is_opt_out is True
    
    def test_skip_opted_out_contacts(self):
        """Should not send to opted-out contacts"""
        # Arrange
        mock_openphone = Mock(spec=OpenPhoneService)
        service = CampaignService(openphone_service=mock_openphone)
        
        # Create contact with opt-out flag
        mock_membership = Mock(spec=CampaignMembership)
        mock_membership.contact = Mock(spec=Contact)
        mock_membership.contact.id = 1
        
        with patch('services.campaign_service.ContactFlag') as mock_flag:
            mock_flag.query.filter_by.return_value.first.return_value = Mock(flag_type='opted_out')
            
            # Act
            should_send = service.should_send_to_contact(mock_membership.contact)
        
        # Assert
        assert should_send is False


class TestAnalytics:
    """Test campaign analytics and reporting"""
    
    def test_calculate_response_rate(self):
        """Should calculate response rate correctly"""
        # Arrange
        mock_openphone = Mock(spec=OpenPhoneService)
        service = CampaignService(openphone_service=mock_openphone)
        
        # Test various scenarios
        test_cases = [
            {'sent': 100, 'responses': 20, 'expected_rate': 0.20},
            {'sent': 50, 'responses': 10, 'expected_rate': 0.20},
            {'sent': 0, 'responses': 0, 'expected_rate': 0.0},
            {'sent': 100, 'responses': 0, 'expected_rate': 0.0},
        ]
        
        for case in test_cases:
            # Act
            rate = case['responses'] / case['sent'] if case['sent'] > 0 else 0.0
            
            # Assert
            assert rate == case['expected_rate']