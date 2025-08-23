"""
Unit Tests for A/B Testing Service - TDD RED PHASE
These tests are written FIRST before implementing the ABTestingService
All tests should FAIL initially to ensure proper TDD workflow
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
from typing import List, Dict, Any

from services.ab_testing_service import ABTestingService
from services.common.result import Result
from crm_database import Campaign, CampaignMembership, Contact, Activity
from repositories.campaign_repository import CampaignRepository
from repositories.contact_repository import ContactRepository
from repositories.ab_test_result_repository import ABTestResultRepository


class TestABTestingService:
    """Unit tests for A/B Testing Service"""
    
    @pytest.fixture
    def mock_campaign_repo(self):
        """Mock campaign repository"""
        return Mock(spec=CampaignRepository)
    
    @pytest.fixture
    def mock_contact_repo(self):
        """Mock contact repository"""
        return Mock(spec=ContactRepository)
    
    @pytest.fixture
    def mock_ab_result_repo(self):
        """Mock A/B test result repository"""
        return Mock(spec=ABTestResultRepository)
    
    @pytest.fixture
    def service(self, mock_campaign_repo, mock_contact_repo, mock_ab_result_repo):
        """Create ABTestingService with mocked dependencies"""
        return ABTestingService(
            campaign_repository=mock_campaign_repo,
            contact_repository=mock_contact_repo,
            ab_result_repository=mock_ab_result_repo
        )
    
    @pytest.fixture
    def sample_campaign(self):
        """Sample campaign with A/B test variants"""
        return Campaign(
            id=1,
            name="Test A/B Campaign",
            campaign_type="ab_test",
            template_a="Hi {first_name}, check out our amazing product!",
            template_b="Hello {first_name}, discover our revolutionary solution!",
            ab_config={
                "split_ratio": 50,  # 50/50 split
                "winner_threshold": 0.95,  # 95% confidence
                "min_sample_size": 100
            },
            status="draft"
        )
    
    @pytest.fixture
    def sample_contacts(self):
        """Sample contacts for testing"""
        return [
            Contact(id=1, first_name="John", last_name="Doe", phone="+11234567890"),
            Contact(id=2, first_name="Jane", last_name="Smith", phone="+11234567891"),
            Contact(id=3, first_name="Bob", last_name="Johnson", phone="+11234567892"),
            Contact(id=4, first_name="Alice", last_name="Brown", phone="+11234567893"),
        ]


class TestVariantManagement(TestABTestingService):
    """Test variant creation and validation"""
    
    def test_create_ab_campaign_with_both_variants(self, service, mock_campaign_repo):
        """Test creating A/B campaign with both variants"""
        # Arrange
        campaign_data = {
            "name": "Test A/B Campaign",
            "template_a": "Hi {first_name}, check out our product!",
            "template_b": "Hello {first_name}, discover our solution!",
            "ab_config": {"split_ratio": 50}
        }
        
        expected_campaign = Campaign(id=1, **campaign_data, campaign_type="ab_test")
        mock_campaign_repo.create.return_value = expected_campaign
        
        # Act
        result = service.create_ab_campaign(campaign_data)
        
        # Assert
        assert result.is_success
        assert result.data.campaign_type == "ab_test"
        assert result.data.template_a is not None
        assert result.data.template_b is not None
        mock_campaign_repo.create.assert_called_once()
    
    def test_create_ab_campaign_fails_without_variant_a(self, service):
        """Test that A/B campaign creation fails without variant A"""
        # Arrange
        campaign_data = {
            "name": "Test Campaign",
            "template_b": "Hello {first_name}!",
            "ab_config": {"split_ratio": 50}
        }
        
        # Act
        result = service.create_ab_campaign(campaign_data)
        
        # Assert
        assert result.is_failure
        assert "template_a is required" in result.error
        assert result.error_code == "MISSING_VARIANT_A"
    
    def test_create_ab_campaign_fails_without_variant_b(self, service):
        """Test that A/B campaign creation fails without variant B"""
        # Arrange
        campaign_data = {
            "name": "Test Campaign",
            "template_a": "Hi {first_name}!",
            "ab_config": {"split_ratio": 50}
        }
        
        # Act
        result = service.create_ab_campaign(campaign_data)
        
        # Assert
        assert result.is_failure
        assert "template_b is required" in result.error
        assert result.error_code == "MISSING_VARIANT_B"
    
    def test_validate_variants_content(self, service):
        """Test that both variants have meaningful content"""
        # Arrange
        campaign_data = {
            "name": "Test Campaign",
            "template_a": "",  # Empty variant
            "template_b": "Hello {first_name}!",
            "ab_config": {"split_ratio": 50}
        }
        
        # Act
        result = service.create_ab_campaign(campaign_data)
        
        # Assert
        assert result.is_failure
        assert "Variant A cannot be empty" in result.error
        assert result.error_code == "EMPTY_VARIANT_A"
    
    def test_validate_ab_config_required(self, service):
        """Test that ab_config is required for A/B campaigns"""
        # Arrange
        campaign_data = {
            "name": "Test Campaign",
            "template_a": "Hi {first_name}!",
            "template_b": "Hello {first_name}!"
        }
        
        # Act
        result = service.create_ab_campaign(campaign_data)
        
        # Assert
        assert result.is_failure
        assert "ab_config is required" in result.error
        assert result.error_code == "MISSING_AB_CONFIG"


class TestRecipientAssignment(TestABTestingService):
    """Test recipient assignment to variants"""
    
    def test_assign_recipients_50_50_split(self, service, sample_campaign, sample_contacts, mock_campaign_repo, mock_ab_result_repo):
        """Test 50/50 split assignment of recipients"""
        # Arrange
        sample_campaign.ab_config = {"split_ratio": 50}
        mock_campaign_repo.get_by_id.return_value = Result.success(sample_campaign)
        mock_ab_result_repo.assign_variant.return_value = Result.success(True)
        
        # Act
        result = service.assign_recipients_to_variants(sample_campaign.id, sample_contacts)
        
        # Assert
        assert result.is_success
        assignments = result.data
        
        # Check that we have both variants assigned
        variant_a_count = sum(1 for a in assignments if a['variant'] == 'A')
        variant_b_count = sum(1 for a in assignments if a['variant'] == 'B')
        
        # With deterministic hashing and small sample, we should have at least 1 of each variant
        assert variant_a_count >= 1  # At least 1 in variant A
        assert variant_b_count >= 1  # At least 1 in variant B
        assert variant_a_count + variant_b_count == 4  # Total should be 4
        assert len(assignments) == 4
    
    def test_assign_recipients_70_30_split(self, service, sample_campaign, sample_contacts, mock_campaign_repo, mock_ab_result_repo):
        """Test custom 70/30 split assignment"""
        # Arrange
        sample_campaign.ab_config = {"split_ratio": 70}  # 70% A, 30% B
        mock_campaign_repo.get_by_id.return_value = Result.success(sample_campaign)
        mock_ab_result_repo.assign_variant.return_value = Result.success(True)
        
        # Create more contacts for better split testing
        contacts = sample_contacts + [
            Contact(id=5, first_name="Carol", last_name="Wilson", phone="+11234567894"),
            Contact(id=6, first_name="David", last_name="Miller", phone="+11234567895"),
            Contact(id=7, first_name="Eve", last_name="Davis", phone="+11234567896"),
            Contact(id=8, first_name="Frank", last_name="Garcia", phone="+11234567897"),
            Contact(id=9, first_name="Grace", last_name="Rodriguez", phone="+11234567898"),
            Contact(id=10, first_name="Henry", last_name="Martinez", phone="+11234567899"),
        ]
        
        # Act
        result = service.assign_recipients_to_variants(sample_campaign.id, contacts)
        
        # Assert
        assert result.is_success
        assignments = result.data
        
        variant_a_count = sum(1 for a in assignments if a['variant'] == 'A')
        variant_b_count = sum(1 for a in assignments if a['variant'] == 'B')
        
        # With 10 contacts and 70/30 split, should be approximately 7 A and 3 B
        # Allow for some variance due to deterministic hashing
        assert 5 <= variant_a_count <= 9  # Should be more A than B
        assert 1 <= variant_b_count <= 5  # Should have some B
        assert variant_a_count + variant_b_count == 10  # Total should be 10
    
    def test_assignment_is_deterministic(self, service, sample_campaign, sample_contacts, mock_campaign_repo, mock_ab_result_repo):
        """Test that same contact always gets same variant (deterministic)"""
        # Arrange
        sample_campaign.ab_config = {"split_ratio": 50}
        mock_campaign_repo.get_by_id.return_value = Result.success(sample_campaign)
        mock_ab_result_repo.assign_variant.return_value = Result.success(True)
        
        # Act - run assignment twice
        result1 = service.assign_recipients_to_variants(sample_campaign.id, sample_contacts)
        result2 = service.assign_recipients_to_variants(sample_campaign.id, sample_contacts)
        
        # Assert
        assert result1.is_success and result2.is_success
        
        # Create lookup dictionaries
        assignments1 = {a['contact_id']: a['variant'] for a in result1.data}
        assignments2 = {a['contact_id']: a['variant'] for a in result2.data}
        
        # Same contact should get same variant both times
        for contact_id in assignments1:
            assert assignments1[contact_id] == assignments2[contact_id]
    
    def test_track_variant_assignment(self, service, sample_campaign, sample_contacts, mock_campaign_repo, mock_ab_result_repo):
        """Test that variant assignments are tracked in database"""
        # Arrange
        sample_campaign.ab_config = {"split_ratio": 50}
        mock_campaign_repo.get_by_id.return_value = Result.success(sample_campaign)
        mock_ab_result_repo.assign_variant.return_value = Result.success(True)
        
        # Act
        result = service.assign_recipients_to_variants(sample_campaign.id, sample_contacts)
        
        # Assert
        assert result.is_success
        
        # Should have called assign_variant for each contact
        assert mock_ab_result_repo.assign_variant.call_count == len(sample_contacts)
        
        # Verify the calls were made with correct parameters
        calls = mock_ab_result_repo.assign_variant.call_args_list
        for i, call in enumerate(calls):
            args, kwargs = call
            assert args[0] == sample_campaign.id  # campaign_id
            assert args[1] == sample_contacts[i].id  # contact_id
            assert args[2] in ['A', 'B']  # variant
    
    def test_get_contact_variant_assignment(self, service, mock_ab_result_repo):
        """Test retrieving existing variant assignment for contact"""
        # Arrange
        campaign_id, contact_id = 1, 1
        expected_variant = 'A'
        mock_ab_result_repo.get_contact_variant.return_value = Result.success(expected_variant)
        
        # Act
        result = service.get_contact_variant(campaign_id, contact_id)
        
        # Assert
        assert result.is_success
        assert result.data == expected_variant
        mock_ab_result_repo.get_contact_variant.assert_called_once_with(campaign_id, contact_id)
    
    def test_get_contact_variant_not_assigned(self, service, mock_ab_result_repo):
        """Test retrieving variant for unassigned contact"""
        # Arrange
        campaign_id, contact_id = 1, 999
        mock_ab_result_repo.get_contact_variant.return_value = Result.failure(
            "Contact not assigned to any variant", 
            code="VARIANT_NOT_ASSIGNED"
        )
        
        # Act
        result = service.get_contact_variant(campaign_id, contact_id)
        
        # Assert
        assert result.is_failure
        assert result.error_code == "VARIANT_NOT_ASSIGNED"


class TestPerformanceTracking(TestABTestingService):
    """Test performance metrics tracking for variants"""
    
    def test_track_message_sent(self, service, mock_ab_result_repo):
        """Test tracking when message is sent to contact"""
        # Arrange
        campaign_id, contact_id, variant = 1, 1, 'A'
        activity_id = 123
        mock_ab_result_repo.track_message_sent.return_value = Result.success(True)
        
        # Act
        result = service.track_message_sent(campaign_id, contact_id, variant, activity_id)
        
        # Assert
        assert result.is_success
        mock_ab_result_repo.track_message_sent.assert_called_once_with(
            campaign_id, contact_id, variant, activity_id
        )
    
    def test_track_message_opened(self, service, mock_ab_result_repo):
        """Test tracking when message is opened by recipient"""
        # Arrange
        campaign_id, contact_id, variant = 1, 1, 'A'
        mock_ab_result_repo.track_message_opened.return_value = Result.success(True)
        
        # Act
        result = service.track_message_opened(campaign_id, contact_id, variant)
        
        # Assert
        assert result.is_success
        mock_ab_result_repo.track_message_opened.assert_called_once_with(
            campaign_id, contact_id, variant
        )
    
    def test_track_link_clicked(self, service, mock_ab_result_repo):
        """Test tracking when link in message is clicked"""
        # Arrange
        campaign_id, contact_id, variant = 1, 1, 'B'
        link_url = "https://example.com/product"
        mock_ab_result_repo.track_link_clicked.return_value = Result.success(True)
        
        # Act
        result = service.track_link_clicked(campaign_id, contact_id, variant, link_url)
        
        # Assert
        assert result.is_success
        mock_ab_result_repo.track_link_clicked.assert_called_once_with(
            campaign_id, contact_id, variant, link_url
        )
    
    def test_track_response_received(self, service, mock_ab_result_repo):
        """Test tracking when recipient responds to message"""
        # Arrange
        campaign_id, contact_id, variant = 1, 1, 'A'
        response_type = 'positive'
        activity_id = 456
        mock_ab_result_repo.track_response_received.return_value = Result.success(True)
        
        # Act
        result = service.track_response_received(
            campaign_id, contact_id, variant, response_type, activity_id
        )
        
        # Assert
        assert result.is_success
        mock_ab_result_repo.track_response_received.assert_called_once_with(
            campaign_id, contact_id, variant, response_type, activity_id
        )
    
    def test_get_variant_metrics(self, service, mock_ab_result_repo):
        """Test retrieving performance metrics for variant"""
        # Arrange
        campaign_id, variant = 1, 'A'
        expected_metrics = {
            'messages_sent': 100,
            'messages_opened': 80,
            'links_clicked': 25,
            'responses_received': 15,
            'positive_responses': 12,
            'negative_responses': 3,
            'open_rate': 0.80,
            'click_rate': 0.25,
            'response_rate': 0.15,
            'conversion_rate': 0.12
        }
        mock_ab_result_repo.get_variant_metrics.return_value = Result.success(expected_metrics)
        
        # Act
        result = service.get_variant_metrics(campaign_id, variant)
        
        # Assert
        assert result.is_success
        metrics = result.data
        assert metrics['messages_sent'] == 100
        assert metrics['open_rate'] == 0.80
        assert metrics['conversion_rate'] == 0.12
        mock_ab_result_repo.get_variant_metrics.assert_called_once_with(campaign_id, variant)
    
    def test_get_campaign_ab_summary(self, service, mock_ab_result_repo):
        """Test retrieving A/B test summary for entire campaign"""
        # Arrange
        campaign_id = 1
        expected_summary = {
            'variant_a': {
                'messages_sent': 100,
                'conversion_rate': 0.12,
                'statistical_confidence': 0.85
            },
            'variant_b': {
                'messages_sent': 100,
                'conversion_rate': 0.18,
                'statistical_confidence': 0.95
            },
            'winner': 'B',
            'confidence_level': 0.95,
            'significant_difference': True
        }
        mock_ab_result_repo.get_campaign_ab_summary.return_value = Result.success(expected_summary)
        
        # Act
        result = service.get_campaign_ab_summary(campaign_id)
        
        # Assert
        assert result.is_success
        summary = result.data
        assert summary['winner'] == 'B'
        assert summary['significant_difference'] is True
        assert summary['variant_b']['conversion_rate'] > summary['variant_a']['conversion_rate']


class TestStatisticalSignificance(TestABTestingService):
    """Test statistical significance calculations"""
    
    def test_calculate_statistical_significance(self, service):
        """Test statistical significance calculation between variants"""
        # Arrange
        variant_a_data = {
            'messages_sent': 100,
            'conversions': 12  # 12% conversion rate
        }
        variant_b_data = {
            'messages_sent': 100,
            'conversions': 18  # 18% conversion rate
        }
        
        # Act
        result = service.calculate_statistical_significance(variant_a_data, variant_b_data)
        
        # Assert
        assert result.is_success
        significance_data = result.data
        assert 'p_value' in significance_data
        assert 'confidence_level' in significance_data
        assert 'significant' in significance_data
        assert 'winner' in significance_data
        
        # With this data, B should be the winner
        assert significance_data['winner'] == 'B'
    
    def test_insufficient_sample_size(self, service):
        """Test handling of insufficient sample size for significance"""
        # Arrange
        variant_a_data = {
            'messages_sent': 10,  # Too small sample
            'conversions': 1
        }
        variant_b_data = {
            'messages_sent': 10,  # Too small sample
            'conversions': 3
        }
        
        # Act
        result = service.calculate_statistical_significance(variant_a_data, variant_b_data)
        
        # Assert
        assert result.is_success
        significance_data = result.data
        assert significance_data['significant'] == False
        assert 'insufficient_sample_size' in significance_data
        assert significance_data['insufficient_sample_size'] is True
    
    def test_no_significant_difference(self, service):
        """Test when there's no statistically significant difference"""
        # Arrange
        variant_a_data = {
            'messages_sent': 1000,
            'conversions': 120  # 12% conversion rate
        }
        variant_b_data = {
            'messages_sent': 1000,
            'conversions': 125  # 12.5% conversion rate - small difference
        }
        
        # Act
        result = service.calculate_statistical_significance(variant_a_data, variant_b_data)
        
        # Assert
        assert result.is_success
        significance_data = result.data
        # Small difference shouldn't be significant
        assert significance_data['significant'] == False


class TestWinnerSelection(TestABTestingService):
    """Test automatic winner selection and manual override"""
    
    def test_identify_automatic_winner(self, service, mock_ab_result_repo, mock_campaign_repo):
        """Test automatic identification of winning variant"""
        # Arrange
        campaign_id = 1
        ab_summary = {
            'variant_a': {'conversion_rate': 0.12, 'statistical_confidence': 0.85, 'responses_received': 120},
            'variant_b': {'conversion_rate': 0.18, 'statistical_confidence': 0.96, 'responses_received': 180},
            'winner': 'B',
            'confidence_level': 0.96,
            'significant_difference': True
        }
        
        mock_ab_result_repo.get_campaign_ab_summary.return_value = Result.success(ab_summary)
        
        # Mock the campaign with proper ab_config
        mock_campaign = Mock()
        mock_campaign.ab_config = {'split_ratio': 50, 'winner_threshold': 0.95}
        mock_campaign_repo.get_by_id.return_value = mock_campaign
        mock_campaign_repo.update_by_id.return_value = Mock(id=campaign_id)
        
        # Act
        result = service.identify_winner(campaign_id, confidence_threshold=0.95)
        
        # Assert
        assert result.is_success
        winner_data = result.data
        assert winner_data['winner'] == 'B'
        assert winner_data['confidence_level'] >= 0.95
        assert winner_data['automatic'] is True
        
        # Check that update was called with correct arguments
        mock_campaign_repo.update_by_id.assert_called_once()
        call_args = mock_campaign_repo.update_by_id.call_args
        assert call_args[0][0] == campaign_id  # First positional arg is campaign_id
    
    def test_no_winner_below_confidence_threshold(self, service, mock_ab_result_repo):
        """Test when no winner meets confidence threshold"""
        # Arrange
        campaign_id = 1
        ab_summary = {
            'variant_a': {'conversion_rate': 0.12, 'statistical_confidence': 0.85, 'responses_received': 120},
            'variant_b': {'conversion_rate': 0.15, 'statistical_confidence': 0.88, 'responses_received': 150},
            'winner': 'B',
            'confidence_level': 0.88,
            'significant_difference': False
        }
        
        mock_ab_result_repo.get_campaign_ab_summary.return_value = Result.success(ab_summary)
        
        # Act
        result = service.identify_winner(campaign_id, confidence_threshold=0.95)
        
        # Assert
        assert result.is_success
        winner_data = result.data
        assert winner_data['winner'] is None
        assert winner_data['reason'] == 'insufficient_confidence'
        assert winner_data['confidence_level'] < 0.95
    
    def test_manual_winner_override(self, service, mock_campaign_repo):
        """Test manual override of winner selection"""
        # Arrange
        campaign_id = 1
        manual_winner = 'A'
        override_reason = "Business decision based on brand voice"
        
        # Mock the campaign with proper ab_config
        mock_campaign = Mock()
        mock_campaign.ab_config = {'split_ratio': 50, 'winner_threshold': 0.95}
        mock_campaign_repo.get_by_id.return_value = mock_campaign
        mock_campaign_repo.update_by_id.return_value = Mock(id=campaign_id)
        
        # Act
        result = service.set_manual_winner(campaign_id, manual_winner, override_reason)
        
        # Assert
        assert result.is_success
        winner_data = result.data
        assert winner_data['winner'] == 'A'
        assert winner_data['automatic'] is False
        assert winner_data['override_reason'] == override_reason
        
        mock_campaign_repo.update_by_id.assert_called_once()
    
    @pytest.mark.skip(reason="get_remaining_recipients not yet implemented")
    def test_send_winner_to_remaining_recipients(self, service, mock_campaign_repo, mock_contact_repo):
        """Test sending winning variant to remaining recipients"""
        # Arrange
        campaign_id = 1
        winning_variant = 'B'
        
        # Mock remaining recipients (those who haven't received any message yet)
        remaining_contacts = [
            Contact(id=10, first_name="New", last_name="Contact", phone="+11234567900"),
            Contact(id=11, first_name="Another", last_name="Contact", phone="+11234567901"),
        ]
        
        # Note: get_remaining_recipients is not implemented, test will need adjustment
        mock_campaign_repo.get_by_id.return_value = Campaign(
            id=campaign_id, template_b="Winning message template"
        )
        
        # Act
        result = service.send_winner_to_remaining(campaign_id, winning_variant)
        
        # Assert
        assert result.is_success
        send_data = result.data
        assert send_data['variant_sent'] == 'B'
        assert send_data['recipients_count'] == 2
        assert len(send_data['scheduled_sends']) == 2


class TestABTestReporting(TestABTestingService):
    """Test A/B test report generation"""
    
    def test_generate_ab_test_report(self, service, mock_ab_result_repo, mock_campaign_repo):
        """Test comprehensive A/B test report generation"""
        # Arrange
        campaign_id = 1
        
        campaign = Campaign(
            id=campaign_id,
            name="Test A/B Campaign",
            template_a="Variant A message",
            template_b="Variant B message",
            created_at=datetime.now() - timedelta(days=7)
        )
        
        ab_summary = {
            'variant_a': {
                'messages_sent': 500,
                'messages_opened': 400,
                'links_clicked': 100,
                'responses_received': 50,
                'positive_responses': 40,
                'conversion_rate': 0.08,
                'open_rate': 0.80,
                'click_rate': 0.20,
                'response_rate': 0.10
            },
            'variant_b': {
                'messages_sent': 500,
                'messages_opened': 450,
                'links_clicked': 135,
                'responses_received': 75,
                'positive_responses': 60,
                'conversion_rate': 0.12,
                'open_rate': 0.90,
                'click_rate': 0.27,
                'response_rate': 0.15
            },
            'winner': 'B',
            'confidence_level': 0.96,
            'significant_difference': True
        }
        
        mock_campaign_repo.get_by_id.return_value = campaign
        mock_ab_result_repo.get_campaign_ab_summary.return_value = Result.success(ab_summary)
        
        # Act
        result = service.generate_ab_test_report(campaign_id)
        
        # Assert
        assert result.is_success
        report = result.data
        
        # Check report structure
        assert 'campaign_info' in report
        assert 'test_duration_days' in report
        assert 'variant_performance' in report
        assert 'statistical_analysis' in report
        assert 'recommendations' in report
        
        # Check campaign info
        assert report['campaign_info']['name'] == "Test A/B Campaign"
        assert report['campaign_info']['id'] == campaign_id
        
        # Check performance data
        assert 'variant_a' in report['variant_performance']
        assert 'variant_b' in report['variant_performance']
        
        # Check statistical analysis
        assert report['statistical_analysis']['winner'] == 'B'
        assert report['statistical_analysis']['confidence_level'] == 0.96
        
        # Check recommendations
        assert len(report['recommendations']) > 0
    
    def test_generate_report_for_ongoing_test(self, service, mock_ab_result_repo, mock_campaign_repo):
        """Test report generation for ongoing A/B test"""
        # Arrange
        campaign_id = 1
        
        # Ongoing test with no clear winner yet
        ab_summary = {
            'variant_a': {'conversion_rate': 0.10, 'messages_sent': 50, 'responses_received': 5},
            'variant_b': {'conversion_rate': 0.12, 'messages_sent': 50, 'responses_received': 6},
            'winner': None,
            'confidence_level': 0.75,
            'significant_difference': False
        }
        
        campaign = Campaign(id=campaign_id, name="Ongoing Test", status="running")
        
        mock_campaign_repo.get_by_id.return_value = campaign
        mock_ab_result_repo.get_campaign_ab_summary.return_value = Result.success(ab_summary)
        
        # Act
        result = service.generate_ab_test_report(campaign_id)
        
        # Assert
        assert result.is_success
        report = result.data
        
        assert report['statistical_analysis']['winner'] is None
        assert report['statistical_analysis']['test_status'] == 'ongoing'
        assert 'continue test' in report['recommendations'][0].lower()


class TestEdgeCases(TestABTestingService):
    """Test edge cases and error handling"""
    
    def test_single_variant_campaign_fails(self, service):
        """Test that creating campaign with only one variant fails"""
        # Arrange
        campaign_data = {
            "name": "Single Variant",
            "template_a": "Only variant A",
            "ab_config": {"split_ratio": 50}
        }
        
        # Act
        result = service.create_ab_campaign(campaign_data)
        
        # Assert
        assert result.is_failure
        assert "template_b is required" in result.error
    
    def test_no_responses_scenario(self, service, mock_ab_result_repo):
        """Test handling when no one responds to either variant"""
        # Arrange
        campaign_id = 1
        ab_summary = {
            'variant_a': {
                'messages_sent': 100,
                'responses_received': 0,
                'conversion_rate': 0.0
            },
            'variant_b': {
                'messages_sent': 100,
                'responses_received': 0,
                'conversion_rate': 0.0
            },
            'winner': None,
            'confidence_level': 0.0,
            'significant_difference': False
        }
        
        mock_ab_result_repo.get_campaign_ab_summary.return_value = Result.success(ab_summary)
        
        # Act
        result = service.identify_winner(campaign_id)
        
        # Assert
        assert result.is_success
        winner_data = result.data
        assert winner_data['winner'] is None
        assert winner_data['reason'] == 'no_responses'
    
    def test_tied_results_scenario(self, service, mock_ab_result_repo):
        """Test handling when both variants perform identically"""
        # Arrange
        campaign_id = 1
        ab_summary = {
            'variant_a': {
                'messages_sent': 1000,
                'conversion_rate': 0.15,
                'responses_received': 150
            },
            'variant_b': {
                'messages_sent': 1000,
                'conversion_rate': 0.15,  # Exactly the same
                'responses_received': 150
            },
            'winner': None,
            'confidence_level': 0.0,
            'significant_difference': False
        }
        
        mock_ab_result_repo.get_campaign_ab_summary.return_value = Result.success(ab_summary)
        
        # Act
        result = service.identify_winner(campaign_id)
        
        # Assert
        assert result.is_success
        winner_data = result.data
        assert winner_data['winner'] is None
        assert winner_data['reason'] == 'tied_results'
    
    def test_invalid_split_ratio_fails(self, service):
        """Test that invalid split ratios are rejected"""
        # Arrange
        campaign_data = {
            "name": "Invalid Split",
            "template_a": "Variant A",
            "template_b": "Variant B",
            "ab_config": {"split_ratio": 120}  # Invalid: > 100
        }
        
        # Act
        result = service.create_ab_campaign(campaign_data)
        
        # Assert
        assert result.is_failure
        assert "split_ratio must be between 1 and 99" in result.error
        assert result.error_code == "INVALID_SPLIT_RATIO"
    
    def test_zero_contacts_assignment(self, service, sample_campaign):
        """Test assignment with empty contact list"""
        # Arrange
        empty_contacts = []
        
        # Act
        result = service.assign_recipients_to_variants(sample_campaign.id, empty_contacts)
        
        # Assert
        assert result.is_success
        assert result.data == []
    
    def test_repository_error_handling(self, service, mock_ab_result_repo):
        """Test handling of repository errors"""
        # Arrange
        campaign_id, contact_id = 1, 1
        mock_ab_result_repo.get_contact_variant.return_value = Result.failure(
            "Database connection error",
            code="DB_ERROR"
        )
        
        # Act
        result = service.get_contact_variant(campaign_id, contact_id)
        
        # Assert
        assert result.is_failure
        assert result.error_code == "DB_ERROR"
        assert "Database connection error" in result.error
