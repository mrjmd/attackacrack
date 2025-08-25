"""
Tests for ConversionTrackingService - P4-03 Conversion Tracking Business Logic
TDD RED PHASE - These tests are written FIRST before implementation
All tests should FAIL initially to ensure proper TDD workflow

Test Coverage:
- Recording conversion events with attribution
- Calculating conversion rates and confidence intervals
- ROI analysis and profit calculations
- Multi-touch attribution models (first-touch, last-touch, linear, time-decay)
- Conversion funnel analysis and optimization
- Time-to-conversion analytics
- Value-based conversion insights
- Integration with campaign and contact systems
- Error handling and validation
- Performance optimization
"""

import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock, MagicMock, patch, call
from typing import List, Dict, Any, Optional

from services.conversion_tracking_service import ConversionTrackingService
from services.common.result import Result, Success, Failure
from repositories.conversion_repository import ConversionRepository
from repositories.campaign_repository import CampaignRepository
from repositories.contact_repository import ContactRepository
from repositories.campaign_response_repository import CampaignResponseRepository
from crm_database import (
    ConversionEvent, Contact, Campaign, CampaignMembership, CampaignResponse
)
from utils.datetime_utils import utc_now, ensure_utc
from tests.conftest import create_test_contact


class TestConversionTrackingService:
    """Test ConversionTrackingService business logic"""
    
    @pytest.fixture
    def mock_conversion_repository(self):
        """Mock conversion repository"""
        return Mock(spec=ConversionRepository)
    
    @pytest.fixture
    def mock_campaign_repository(self):
        """Mock campaign repository"""
        return Mock(spec=CampaignRepository)
    
    @pytest.fixture
    def mock_contact_repository(self):
        """Mock contact repository"""
        return Mock(spec=ContactRepository)
    
    @pytest.fixture
    def mock_response_repository(self):
        """Mock campaign response repository"""
        return Mock(spec=CampaignResponseRepository)
    
    @pytest.fixture
    def service(self, mock_conversion_repository, mock_campaign_repository,
                mock_contact_repository, mock_response_repository):
        """Create ConversionTrackingService with mocked dependencies"""
        return ConversionTrackingService(
            conversion_repository=mock_conversion_repository,
            campaign_repository=mock_campaign_repository,
            contact_repository=mock_contact_repository,
            response_repository=mock_response_repository
        )
    
    @pytest.fixture
    def sample_contact(self):
        """Sample contact for testing"""
        contact = Mock(spec=Contact)
        contact.id = 1
        contact.first_name = "John"
        contact.last_name = "Doe"
        contact.phone = "+15551234567"
        contact.email = "john@example.com"
        return contact
    
    @pytest.fixture
    def sample_campaign(self):
        """Sample campaign for testing"""
        campaign = Mock(spec=Campaign)
        campaign.id = 1
        campaign.name = "Test Campaign"
        campaign.status = "running"
        campaign.created_at = utc_now() - timedelta(days=7)
        return campaign
    
    @pytest.fixture
    def sample_conversion_data(self):
        """Sample conversion event data"""
        return {
            'contact_id': 1,
            'campaign_id': 1,
            'conversion_type': 'purchase',
            'conversion_value': Decimal('150.00'),
            'currency': 'USD',
            'conversion_metadata': {
                'product_id': 'P123',
                'order_id': 'ORD456',
                'channel': 'sms'
            }
        }
    
    # ===== Conversion Event Recording =====
    
    def test_record_conversion_success(self, service, mock_conversion_repository,
                                     mock_contact_repository, mock_campaign_repository,
                                     sample_conversion_data, sample_contact, sample_campaign):
        """Test successful conversion event recording"""
        # Arrange
        mock_contact_repository.get_by_id.return_value = sample_contact
        mock_campaign_repository.get_by_id.return_value = sample_campaign
        
        # Mock successful conversion creation
        mock_conversion = Mock(spec=ConversionEvent)
        mock_conversion.id = 1
        mock_conversion.contact_id = sample_conversion_data['contact_id']
        mock_conversion.campaign_id = sample_conversion_data['campaign_id']
        mock_conversion.conversion_type = sample_conversion_data['conversion_type']
        mock_conversion.conversion_value = sample_conversion_data['conversion_value']
        mock_conversion.converted_at = utc_now()
        
        mock_conversion_repository.create_conversion_event.return_value = mock_conversion
        
        # Act
        result = service.record_conversion(sample_conversion_data)
        
        # Assert
        assert result.is_success
        conversion_data = result.unwrap()
        assert conversion_data['id'] == 1
        assert conversion_data['contact_id'] == 1
        assert conversion_data['campaign_id'] == 1
        assert conversion_data['conversion_type'] == 'purchase'
        assert conversion_data['conversion_value'] == Decimal('150.00')
        
        # Verify repository calls
        mock_contact_repository.get_by_id.assert_called_once_with(1)
        mock_campaign_repository.get_by_id.assert_called_once_with(1)
        mock_conversion_repository.create_conversion_event.assert_called_once()
    
    def test_record_conversion_with_attribution_calculation(self, service, mock_conversion_repository,
                                                          mock_contact_repository, sample_conversion_data):
        """Test conversion recording with automatic attribution calculation"""
        # Arrange
        mock_contact_repository.get_by_id.return_value = Mock(spec=Contact, id=1)
        
        # Mock attribution calculation
        attribution_weights = {1: 0.6, 2: 0.4}  # Campaign 1: 60%, Campaign 2: 40%
        mock_conversion_repository.calculate_attribution_weights.return_value = attribution_weights
        
        mock_conversion = Mock(spec=ConversionEvent, id=1)
        mock_conversion_repository.create_conversion_event.return_value = mock_conversion
        
        conversion_data_with_attribution = sample_conversion_data.copy()
        conversion_data_with_attribution['attribution_model'] = 'linear'
        conversion_data_with_attribution['attribution_window_days'] = 30
        
        # Act
        result = service.record_conversion(conversion_data_with_attribution)
        
        # Assert
        assert result.is_success
        conversion_result = result.unwrap()
        assert 'attribution_weights' in conversion_result
        assert conversion_result['attribution_weights'] == attribution_weights
        
        # Verify attribution calculation was called
        mock_conversion_repository.calculate_attribution_weights.assert_called_once()
    
    def test_record_conversion_invalid_contact(self, service, mock_contact_repository, sample_conversion_data):
        """Test conversion recording with invalid contact ID"""
        # Arrange
        mock_contact_repository.get_by_id.return_value = None  # Contact not found
        
        # Act
        result = service.record_conversion(sample_conversion_data)
        
        # Assert
        assert result.is_failure
        error = result.error
        assert "Contact not found" in str(error)
    
    def test_record_conversion_invalid_campaign(self, service, mock_contact_repository,
                                              mock_campaign_repository, sample_conversion_data):
        """Test conversion recording with invalid campaign ID"""
        # Arrange
        mock_contact_repository.get_by_id.return_value = Mock(spec=Contact, id=1)
        mock_campaign_repository.get_by_id.return_value = None  # Campaign not found
        
        # Act
        result = service.record_conversion(sample_conversion_data)
        
        # Assert
        assert result.is_failure
        error = result.error
        assert "Campaign not found" in str(error)
    
    def test_record_conversion_validation_errors(self, service):
        """Test conversion recording with invalid data"""
        # Test missing required fields
        invalid_data_sets = [
            {},  # Empty data
            {'contact_id': 1},  # Missing conversion_type
            {'contact_id': 1, 'conversion_type': 'purchase', 'conversion_value': Decimal('-50.00')},  # Negative value
            {'contact_id': 1, 'conversion_type': 'invalid_type'},  # Invalid conversion type
        ]
        
        for invalid_data in invalid_data_sets:
            result = service.record_conversion(invalid_data)
            assert result.is_failure, f"Expected failure for data: {invalid_data}"
    
    # ===== Conversion Rate Calculations =====
    
    def test_calculate_conversion_rate_with_confidence_interval(self, service, mock_conversion_repository):
        """Test conversion rate calculation with statistical confidence intervals"""
        # Arrange
        campaign_id = 1
        
        # Mock repository response with conversion statistics
        mock_stats = {
            'campaign_id': campaign_id,
            'total_sent': 1000,
            'total_conversions': 85,
            'conversion_rate': 0.085,
            'calculated_at': utc_now()
        }
        mock_conversion_repository.calculate_conversion_rate_for_campaign.return_value = mock_stats
        
        # Act
        result = service.calculate_conversion_rate(campaign_id, confidence_level=0.95)
        
        # Assert
        assert result.is_success
        rate_data = result.unwrap()
        assert rate_data['conversion_rate'] == 0.085
        assert rate_data['total_sent'] == 1000
        assert rate_data['total_conversions'] == 85
        assert 'confidence_interval' in rate_data
        assert 'lower_bound' in rate_data['confidence_interval']
        assert 'upper_bound' in rate_data['confidence_interval']
        assert rate_data['confidence_level'] == 0.95
        
        # Confidence interval should be around the conversion rate
        ci = rate_data['confidence_interval']
        assert ci['lower_bound'] < 0.085 < ci['upper_bound']
        
        mock_conversion_repository.calculate_conversion_rate_for_campaign.assert_called_once_with(campaign_id)
    
    def test_calculate_conversion_rate_insufficient_data(self, service, mock_conversion_repository):
        """Test conversion rate calculation with insufficient data"""
        # Arrange
        campaign_id = 1
        
        # Mock insufficient data scenario
        mock_stats = {
            'campaign_id': campaign_id,
            'total_sent': 5,  # Too few for reliable statistics
            'total_conversions': 1,
            'conversion_rate': 0.2,
            'calculated_at': utc_now()
        }
        mock_conversion_repository.calculate_conversion_rate_for_campaign.return_value = mock_stats
        
        # Act
        result = service.calculate_conversion_rate(campaign_id)
        
        # Assert
        assert result.is_success
        rate_data = result.unwrap()
        assert rate_data['conversion_rate'] == 0.2
        assert rate_data['insufficient_data'] == True
        assert rate_data['minimum_sample_size'] > 5
        assert 'warning' in rate_data
        assert "insufficient data" in rate_data['warning'].lower()
    
    def test_calculate_conversion_rates_by_time_period(self, service, mock_conversion_repository):
        """Test conversion rates grouped by time periods"""
        # Arrange
        campaign_id = 1
        date_from = utc_now() - timedelta(days=30)
        date_to = utc_now()
        group_by = 'day'
        
        # Mock time-series data
        mock_time_series = [
            {'period': '2025-08-20', 'total_sent': 50, 'conversions': 8, 'conversion_rate': 0.16},
            {'period': '2025-08-21', 'total_sent': 45, 'conversions': 5, 'conversion_rate': 0.11},
            {'period': '2025-08-22', 'total_sent': 60, 'conversions': 12, 'conversion_rate': 0.20},
        ]
        mock_conversion_repository.get_conversion_rates_by_time_period.return_value = mock_time_series
        
        # Act
        result = service.calculate_conversion_rates_by_time_period(
            campaign_id=campaign_id,
            date_from=date_from,
            date_to=date_to,
            group_by=group_by
        )
        
        # Assert
        assert result.is_success
        time_series_data = result.unwrap()
        assert len(time_series_data['time_series']) == 3
        assert time_series_data['time_series'][0]['period'] == '2025-08-20'
        assert time_series_data['time_series'][0]['conversion_rate'] == 0.16
        assert time_series_data['summary']['average_conversion_rate'] > 0
        assert time_series_data['summary']['peak_day'] is not None
        assert time_series_data['summary']['total_conversions'] == 25  # 8+5+12
        
        mock_conversion_repository.get_conversion_rates_by_time_period.assert_called_once()
    
    # ===== ROI Analysis =====
    
    def test_calculate_campaign_roi_success(self, service, mock_conversion_repository, mock_campaign_repository):
        """Test successful campaign ROI calculation"""
        # Arrange
        campaign_id = 1
        campaign_cost = Decimal('2500.00')
        
        # Mock campaign data
        mock_campaign = Mock(spec=Campaign, id=campaign_id)
        mock_campaign_repository.get_by_id.return_value = mock_campaign
        
        # Mock ROI calculation from repository
        mock_roi_data = {
            'campaign_id': campaign_id,
            'total_revenue': Decimal('4200.00'),
            'campaign_cost': campaign_cost,
            'profit': Decimal('1700.00'),
            'roi': Decimal('0.68'),
            'conversion_count': 28,
            'average_conversion_value': Decimal('150.00')
        }
        mock_conversion_repository.calculate_campaign_roi.return_value = mock_roi_data
        
        # Act
        result = service.calculate_campaign_roi(campaign_id, campaign_cost)
        
        # Assert
        assert result.is_success
        roi_data = result.unwrap()
        assert roi_data['campaign_id'] == campaign_id
        assert roi_data['total_revenue'] == Decimal('4200.00')
        assert roi_data['campaign_cost'] == campaign_cost
        assert roi_data['profit'] == Decimal('1700.00')
        assert roi_data['roi'] == Decimal('0.68')
        assert roi_data['roi_percentage'] == 68.0  # 0.68 * 100
        assert roi_data['conversion_count'] == 28
        assert roi_data['roas'] > 0  # Return on Ad Spend
        
        # Verify calculations
        expected_roas = Decimal('4200.00') / campaign_cost  # 1.68
        assert roi_data['roas'] == expected_roas
        
        mock_campaign_repository.get_by_id.assert_called_once_with(campaign_id)
        mock_conversion_repository.calculate_campaign_roi.assert_called_once_with(campaign_id, campaign_cost)
    
    def test_calculate_campaign_roi_negative_roi(self, service, mock_conversion_repository, mock_campaign_repository):
        """Test ROI calculation when campaign loses money"""
        # Arrange
        campaign_id = 1
        campaign_cost = Decimal('3000.00')
        
        mock_campaign = Mock(spec=Campaign, id=campaign_id)
        mock_campaign_repository.get_by_id.return_value = mock_campaign
        
        # Mock ROI data showing loss
        mock_roi_data = {
            'campaign_id': campaign_id,
            'total_revenue': Decimal('1200.00'),
            'campaign_cost': campaign_cost,
            'profit': Decimal('-1800.00'),
            'roi': Decimal('-0.6'),
            'conversion_count': 8,
            'average_conversion_value': Decimal('150.00')
        }
        mock_conversion_repository.calculate_campaign_roi.return_value = mock_roi_data
        
        # Act
        result = service.calculate_campaign_roi(campaign_id, campaign_cost)
        
        # Assert
        assert result.is_success
        roi_data = result.unwrap()
        assert roi_data['profit'] == Decimal('-1800.00')
        assert roi_data['roi'] == Decimal('-0.6')
        assert roi_data['roi_percentage'] == -60.0
        assert roi_data['is_profitable'] == False
        assert 'loss_analysis' in roi_data
        assert roi_data['roas'] == Decimal('0.4')  # 1200/3000
    
    def test_calculate_multi_campaign_roi_comparison(self, service, mock_conversion_repository):
        """Test comparing ROI across multiple campaigns"""
        # Arrange
        campaign_ids = [1, 2, 3]
        campaign_costs = {1: Decimal('2000.00'), 2: Decimal('1500.00'), 3: Decimal('2500.00')}
        
        # Mock ROI data for each campaign
        mock_roi_responses = [
            {'campaign_id': 1, 'total_revenue': Decimal('3500.00'), 'roi': Decimal('0.75'), 'conversion_count': 20},
            {'campaign_id': 2, 'total_revenue': Decimal('2400.00'), 'roi': Decimal('0.60'), 'conversion_count': 15},
            {'campaign_id': 3, 'total_revenue': Decimal('1800.00'), 'roi': Decimal('-0.28'), 'conversion_count': 8},
        ]
        mock_conversion_repository.calculate_campaign_roi.side_effect = mock_roi_responses
        
        # Act
        result = service.calculate_multi_campaign_roi_comparison(campaign_ids, campaign_costs)
        
        # Assert
        assert result.is_success
        comparison_data = result.unwrap()
        assert len(comparison_data['campaigns']) == 3
        assert comparison_data['best_performing']['campaign_id'] == 1
        assert comparison_data['worst_performing']['campaign_id'] == 3
        assert comparison_data['overall_roi'] > 0  # Should be positive overall
        assert comparison_data['total_investment'] == Decimal('6000.00')  # Sum of costs
        
        # Verify all campaigns were calculated
        assert mock_conversion_repository.calculate_campaign_roi.call_count == 3
    
    # ===== Multi-Touch Attribution =====
    
    def test_calculate_linear_attribution(self, service, mock_conversion_repository):
        """Test linear attribution model calculation"""
        # Arrange
        contact_id = 1
        conversion_timestamp = utc_now()
        attribution_window_days = 30
        
        # Mock touchpoints for linear attribution
        mock_attribution_weights = {
            1: Decimal('0.333'),  # Campaign 1: 33.3%
            2: Decimal('0.333'),  # Campaign 2: 33.3%
            3: Decimal('0.334')   # Campaign 3: 33.4% (rounding)
        }
        mock_conversion_repository.calculate_attribution_weights.return_value = mock_attribution_weights
        
        # Act
        result = service.calculate_attribution_weights(
            contact_id=contact_id,
            conversion_timestamp=conversion_timestamp,
            attribution_model='linear',
            attribution_window_days=attribution_window_days
        )
        
        # Assert
        assert result.is_success
        attribution_data = result.unwrap()
        assert attribution_data['attribution_model'] == 'linear'
        assert len(attribution_data['weights']) == 3
        assert attribution_data['weights'][1] == Decimal('0.333')
        assert attribution_data['weights'][2] == Decimal('0.333')
        assert attribution_data['weights'][3] == Decimal('0.334')
        
        # Weights should sum to 1
        total_weight = sum(attribution_data['weights'].values())
        assert abs(total_weight - 1) < Decimal('0.001')
        
        mock_conversion_repository.calculate_attribution_weights.assert_called_once()
    
    def test_calculate_time_decay_attribution(self, service, mock_conversion_repository):
        """Test time-decay attribution model calculation"""
        # Arrange
        contact_id = 1
        conversion_timestamp = utc_now()
        
        # Mock time-decay attribution (more recent touchpoints get more weight)
        mock_attribution_weights = {
            1: Decimal('0.2'),   # Oldest touchpoint: 20%
            2: Decimal('0.3'),   # Middle touchpoint: 30%
            3: Decimal('0.5')    # Most recent touchpoint: 50%
        }
        mock_conversion_repository.calculate_attribution_weights.return_value = mock_attribution_weights
        
        # Act
        result = service.calculate_attribution_weights(
            contact_id=contact_id,
            conversion_timestamp=conversion_timestamp,
            attribution_model='time_decay',
            attribution_window_days=30
        )
        
        # Assert
        assert result.is_success
        attribution_data = result.unwrap()
        assert attribution_data['attribution_model'] == 'time_decay'
        assert attribution_data['weights'][3] > attribution_data['weights'][2]  # More recent gets more weight
        assert attribution_data['weights'][2] > attribution_data['weights'][1]  # Time decay pattern
        
        # Should include decay factor information
        assert 'decay_factor' in attribution_data
        assert attribution_data['decay_factor'] > 0
    
    def test_calculate_first_touch_attribution(self, service, mock_conversion_repository):
        """Test first-touch attribution model"""
        # Arrange
        contact_id = 1
        conversion_timestamp = utc_now()
        
        # Mock first-touch attribution (first touchpoint gets all credit)
        mock_attribution_weights = {
            1: Decimal('1.0'),   # First touchpoint: 100%
            2: Decimal('0.0'),   # Other touchpoints: 0%
            3: Decimal('0.0')
        }
        mock_conversion_repository.calculate_attribution_weights.return_value = mock_attribution_weights
        
        # Act
        result = service.calculate_attribution_weights(
            contact_id=contact_id,
            conversion_timestamp=conversion_timestamp,
            attribution_model='first_touch',
            attribution_window_days=30
        )
        
        # Assert
        assert result.is_success
        attribution_data = result.unwrap()
        assert attribution_data['attribution_model'] == 'first_touch'
        assert attribution_data['weights'][1] == Decimal('1.0')
        assert attribution_data['weights'][2] == Decimal('0.0')
        assert attribution_data['weights'][3] == Decimal('0.0')
    
    def test_calculate_last_touch_attribution(self, service, mock_conversion_repository):
        """Test last-touch attribution model"""
        # Arrange
        contact_id = 1
        conversion_timestamp = utc_now()
        
        # Mock last-touch attribution (last touchpoint gets all credit)
        mock_attribution_weights = {
            1: Decimal('0.0'),   # Earlier touchpoints: 0%
            2: Decimal('0.0'),
            3: Decimal('1.0')    # Last touchpoint: 100%
        }
        mock_conversion_repository.calculate_attribution_weights.return_value = mock_attribution_weights
        
        # Act
        result = service.calculate_attribution_weights(
            contact_id=contact_id,
            conversion_timestamp=conversion_timestamp,
            attribution_model='last_touch',
            attribution_window_days=30
        )
        
        # Assert
        assert result.is_success
        attribution_data = result.unwrap()
        assert attribution_data['attribution_model'] == 'last_touch'
        assert attribution_data['weights'][3] == Decimal('1.0')
        assert attribution_data['weights'][1] == Decimal('0.0')
        assert attribution_data['weights'][2] == Decimal('0.0')
    
    # ===== Conversion Funnel Analysis =====
    
    def test_analyze_conversion_funnel(self, service, mock_conversion_repository):
        """Test comprehensive conversion funnel analysis"""
        # Arrange
        campaign_id = 1
        
        # Mock funnel data from repository
        mock_funnel_data = [
            {'stage': 'sent', 'count': 1000, 'cumulative_count': 1000, 'stage_conversion_rate': 1.0},
            {'stage': 'delivered', 'count': 970, 'cumulative_count': 970, 'stage_conversion_rate': 0.97},
            {'stage': 'engaged', 'count': 450, 'cumulative_count': 450, 'stage_conversion_rate': 0.464},
            {'stage': 'responded', 'count': 180, 'cumulative_count': 180, 'stage_conversion_rate': 0.4},
            {'stage': 'converted', 'count': 25, 'cumulative_count': 25, 'stage_conversion_rate': 0.139}
        ]
        mock_conversion_repository.get_conversion_funnel_data.return_value = mock_funnel_data
        
        # Mock drop-off analysis
        mock_drop_offs = [
            {'from_stage': 'delivered', 'to_stage': 'engaged', 'drop_off_count': 520, 'drop_off_rate': 0.536, 'severity': 'high'},
            {'from_stage': 'responded', 'to_stage': 'converted', 'drop_off_count': 155, 'drop_off_rate': 0.861, 'severity': 'critical'}
        ]
        mock_conversion_repository.identify_funnel_drop_off_points.return_value = mock_drop_offs
        
        # Act
        result = service.analyze_conversion_funnel(campaign_id)
        
        # Assert
        assert result.is_success
        funnel_data = result.unwrap()
        assert len(funnel_data['funnel_stages']) == 5
        assert funnel_data['overall_conversion_rate'] == 0.025  # 25/1000
        assert len(funnel_data['drop_off_analysis']) == 2
        assert funnel_data['biggest_drop_off']['from_stage'] == 'responded'
        assert funnel_data['biggest_drop_off']['to_stage'] == 'converted'
        
        # Should include optimization recommendations
        assert 'optimization_recommendations' in funnel_data
        assert len(funnel_data['optimization_recommendations']) > 0
        
        mock_conversion_repository.get_conversion_funnel_data.assert_called_once_with(campaign_id)
        mock_conversion_repository.identify_funnel_drop_off_points.assert_called_once_with(campaign_id)
    
    def test_identify_funnel_optimization_opportunities(self, service, mock_conversion_repository):
        """Test identifying specific optimization opportunities in funnel"""
        # Arrange
        campaign_id = 1
        
        # Mock funnel data with clear optimization opportunities
        mock_funnel_data = [
            {'stage': 'sent', 'count': 500, 'stage_conversion_rate': 1.0},
            {'stage': 'delivered', 'count': 485, 'stage_conversion_rate': 0.97},  # Good delivery rate
            {'stage': 'engaged', 'count': 145, 'stage_conversion_rate': 0.299},  # Poor engagement
            {'stage': 'responded', 'count': 58, 'stage_conversion_rate': 0.4},   # OK response rate
            {'stage': 'converted', 'count': 5, 'stage_conversion_rate': 0.086}   # Poor conversion
        ]
        mock_conversion_repository.get_conversion_funnel_data.return_value = mock_funnel_data
        
        # Act
        result = service.identify_funnel_optimization_opportunities(campaign_id)
        
        # Assert
        assert result.is_success
        opportunities = result.unwrap()
        
        # Should identify engagement as a major opportunity
        engagement_opportunity = next((opp for opp in opportunities['opportunities'] if 'engagement' in opp['focus_area']), None)
        assert engagement_opportunity is not None
        assert engagement_opportunity['current_rate'] < 0.4  # Poor engagement rate
        assert engagement_opportunity['improvement_potential'] > 0.1
        
        # Should identify conversion as another opportunity
        conversion_opportunity = next((opp for opp in opportunities['opportunities'] if 'conversion' in opp['focus_area']), None)
        assert conversion_opportunity is not None
        
        # Should provide specific recommendations
        assert len(opportunities['recommendations']) > 0
        assert 'priority_order' in opportunities
    
    # ===== Time-to-Conversion Analysis =====
    
    def test_analyze_time_to_conversion(self, service, mock_conversion_repository):
        """Test time-to-conversion analysis"""
        # Arrange
        campaign_id = 1
        
        # Mock time-to-conversion statistics
        mock_time_stats = {
            'campaign_id': campaign_id,
            'average_hours': 72.5,
            'average_days': 3.02,
            'median_hours': 48.0,
            'min_hours': 2.0,
            'max_hours': 168.0
        }
        mock_conversion_repository.calculate_average_time_to_conversion.return_value = mock_time_stats
        
        # Mock time distribution
        mock_distribution = [
            {'time_bucket': '0-1 hours', 'conversion_count': 8, 'percentage': 0.32},
            {'time_bucket': '1-6 hours', 'conversion_count': 5, 'percentage': 0.20},
            {'time_bucket': '6-24 hours', 'conversion_count': 7, 'percentage': 0.28},
            {'time_bucket': '1-7 days', 'conversion_count': 4, 'percentage': 0.16},
            {'time_bucket': '7+ days', 'conversion_count': 1, 'percentage': 0.04}
        ]
        mock_conversion_repository.get_time_to_conversion_distribution.return_value = mock_distribution
        
        # Act
        result = service.analyze_time_to_conversion(campaign_id)
        
        # Assert
        assert result.is_success
        time_analysis = result.unwrap()
        assert time_analysis['average_hours'] == 72.5
        assert time_analysis['average_days'] == 3.02
        assert time_analysis['median_hours'] == 48.0
        assert len(time_analysis['distribution']) == 5
        assert time_analysis['fastest_conversion_bucket'] == '0-1 hours'
        assert time_analysis['peak_conversion_window'] == '0-1 hours'  # Highest percentage
        
        # Should include insights and recommendations
        assert 'insights' in time_analysis
        assert 'follow_up_recommendations' in time_analysis
        
        mock_conversion_repository.calculate_average_time_to_conversion.assert_called_once_with(campaign_id)
        mock_conversion_repository.get_time_to_conversion_distribution.assert_called_once_with(campaign_id)
    
    def test_predict_optimal_follow_up_timing(self, service):
        """Test predicting optimal follow-up timing based on conversion patterns"""
        # Arrange
        time_to_conversion_data = {
            'average_hours': 48.0,
            'median_hours': 36.0,
            'distribution': [
                {'time_bucket': '0-1 hours', 'conversion_count': 5, 'percentage': 0.20},
                {'time_bucket': '1-6 hours', 'conversion_count': 8, 'percentage': 0.32},
                {'time_bucket': '6-24 hours', 'conversion_count': 7, 'percentage': 0.28},
                {'time_bucket': '1-7 days', 'conversion_count': 5, 'percentage': 0.20}
            ]
        }
        
        # Act
        result = service.predict_optimal_follow_up_timing(time_to_conversion_data)
        
        # Assert
        assert result.is_success
        timing_recommendations = result.unwrap()
        assert 'immediate_follow_up' in timing_recommendations
        assert 'peak_window_follow_up' in timing_recommendations
        assert 'final_follow_up' in timing_recommendations
        
        # Peak window should be based on highest conversion percentage
        assert timing_recommendations['peak_window_follow_up']['recommended_hours'] >= 1
        assert timing_recommendations['peak_window_follow_up']['recommended_hours'] <= 6
        
        # Should include conversion probability estimates
        assert 'conversion_probability_by_timing' in timing_recommendations
    
    # ===== Value-Based Analytics =====
    
    def test_analyze_conversion_value_patterns(self, service, mock_conversion_repository):
        """Test analysis of conversion value patterns and insights"""
        # Arrange
        campaign_id = 1
        conversion_type = 'purchase'
        
        # Mock value statistics
        mock_value_stats = {
            'campaign_id': campaign_id,
            'conversion_type': conversion_type,
            'average_value': Decimal('185.50'),
            'median_value': Decimal('150.00'),
            'total_value': Decimal('3710.00'),
            'min_value': Decimal('25.00'),
            'max_value': Decimal('450.00'),
            'std_deviation': Decimal('95.25'),
            'conversion_count': 20
        }
        mock_conversion_repository.get_conversion_value_statistics.return_value = mock_value_stats
        
        # Mock high-value conversions
        mock_high_value = [
            Mock(spec=ConversionEvent, conversion_value=Decimal('350.00'), contact_id=5),
            Mock(spec=ConversionEvent, conversion_value=Decimal('425.00'), contact_id=10),
            Mock(spec=ConversionEvent, conversion_value=Decimal('450.00'), contact_id=15)
        ]
        mock_conversion_repository.get_high_value_conversions.return_value = mock_high_value
        
        # Act
        result = service.analyze_conversion_value_patterns(campaign_id, conversion_type)
        
        # Assert
        assert result.is_success
        value_analysis = result.unwrap()
        assert value_analysis['average_value'] == Decimal('185.50')
        assert value_analysis['median_value'] == Decimal('150.00')
        assert value_analysis['value_distribution']['high_value_threshold'] == Decimal('280.75')  # avg + std_dev
        assert len(value_analysis['high_value_conversions']) == 3
        assert value_analysis['value_consistency']['coefficient_of_variation'] > 0  # std_dev / mean
        
        # Should include value-based insights
        assert 'insights' in value_analysis
        assert 'high_value_customer_characteristics' in value_analysis
        
        mock_conversion_repository.get_conversion_value_statistics.assert_called_once()
        mock_conversion_repository.get_high_value_conversions.assert_called_once()
    
    def test_segment_contacts_by_conversion_value(self, service, mock_conversion_repository):
        """Test segmenting contacts based on their conversion values"""
        # Arrange
        campaign_id = 1
        
        # Mock contact conversion values
        mock_contact_values = [
            {'contact_id': 1, 'total_value': Decimal('450.00'), 'conversion_count': 3},
            {'contact_id': 2, 'total_value': Decimal('200.00'), 'conversion_count': 1},
            {'contact_id': 3, 'total_value': Decimal('75.00'), 'conversion_count': 1},
            {'contact_id': 4, 'total_value': Decimal('300.00'), 'conversion_count': 2},
            {'contact_id': 5, 'total_value': Decimal('150.00'), 'conversion_count': 1}
        ]
        
        # Mock repository method
        mock_conversion_repository.get_contact_conversion_values.return_value = mock_contact_values
        
        # Act
        result = service.segment_contacts_by_conversion_value(campaign_id)
        
        # Assert
        assert result.is_success
        segmentation = result.unwrap()
        
        # Should have different value segments
        assert 'high_value' in segmentation['segments']
        assert 'medium_value' in segmentation['segments']
        assert 'low_value' in segmentation['segments']
        
        # High-value segment should include contact 1 (highest total value)
        high_value_contacts = [c['contact_id'] for c in segmentation['segments']['high_value']]
        assert 1 in high_value_contacts
        
        # Should include segment statistics
        assert 'segment_statistics' in segmentation
        assert segmentation['segment_statistics']['total_contacts'] == 5
    
    # ===== Integration with Campaign Response System =====
    
    def test_link_conversion_to_campaign_response(self, service, mock_conversion_repository,
                                                mock_response_repository, mock_contact_repository,
                                                mock_campaign_repository, sample_conversion_data):
        """Test linking conversion events to existing campaign responses"""
        # Arrange
        contact_id = sample_conversion_data['contact_id']
        campaign_id = sample_conversion_data['campaign_id']
        
        # Mock contact and campaign exist
        mock_contact_repository.get_by_id.return_value = Mock(spec=Contact, id=contact_id)
        mock_campaign_repository.get_by_id.return_value = Mock(spec=Campaign, id=campaign_id)
        
        # Mock existing campaign response
        mock_response = Mock(spec=CampaignResponse)
        mock_response.id = 1
        mock_response.contact_id = contact_id
        mock_response.campaign_id = campaign_id
        mock_response.response_sentiment = 'positive'
        mock_response.message_sent_at = utc_now() - timedelta(hours=48)
        
        mock_response_repository.get_by_campaign_and_contact.return_value = mock_response
        
        # Mock conversion creation
        mock_conversion = Mock(spec=ConversionEvent)
        mock_conversion.id = 1
        mock_conversion.contact_id = contact_id
        mock_conversion.campaign_id = campaign_id
        mock_conversion.conversion_type = sample_conversion_data['conversion_type']
        mock_conversion.conversion_value = sample_conversion_data['conversion_value']
        mock_conversion.converted_at = utc_now()  # Use real datetime
        mock_conversion_repository.create_conversion_event.return_value = mock_conversion
        
        # Act
        result = service.record_conversion_with_response_link(sample_conversion_data)
        
        # Assert
        assert result.is_success
        conversion_data = result.unwrap()
        assert 'linked_response' in conversion_data
        assert conversion_data['linked_response']['id'] == 1
        assert conversion_data['linked_response']['response_sentiment'] == 'positive'
        assert conversion_data['time_from_response_to_conversion'] > 0
        
        mock_response_repository.get_by_campaign_and_contact.assert_called_once()
    
    # ===== Error Handling and Edge Cases =====
    
    def test_record_conversion_database_error(self, service, mock_conversion_repository,
                                            mock_contact_repository, sample_conversion_data):
        """Test handling database errors during conversion recording"""
        # Arrange
        mock_contact_repository.get_by_id.return_value = Mock(spec=Contact, id=1)
        mock_conversion_repository.create_conversion_event.side_effect = Exception("Database error")
        
        # Act
        result = service.record_conversion(sample_conversion_data)
        
        # Assert
        assert result.is_failure
        error = result.error
        assert "Database error" in str(error)
    
    def test_calculate_conversion_rate_no_data(self, service, mock_conversion_repository):
        """Test conversion rate calculation when no data exists"""
        # Arrange
        campaign_id = 999  # Non-existent campaign
        
        mock_conversion_repository.calculate_conversion_rate_for_campaign.return_value = {
            'campaign_id': campaign_id,
            'total_sent': 0,
            'total_conversions': 0,
            'conversion_rate': 0.0,
            'calculated_at': utc_now()
        }
        
        # Act
        result = service.calculate_conversion_rate(campaign_id)
        
        # Assert
        assert result.is_success
        rate_data = result.unwrap()
        assert rate_data['conversion_rate'] == 0.0
        assert rate_data['no_data'] == True
        assert 'message' in rate_data
    
    def test_attribution_calculation_no_touchpoints(self, service, mock_conversion_repository):
        """Test attribution calculation when no touchpoints exist"""
        # Arrange
        contact_id = 1
        conversion_timestamp = utc_now()
        
        # Mock no touchpoints found
        mock_conversion_repository.calculate_attribution_weights.return_value = {}
        
        # Act
        result = service.calculate_attribution_weights(
            contact_id=contact_id,
            conversion_timestamp=conversion_timestamp,
            attribution_model='linear'
        )
        
        # Assert
        assert result.is_success
        attribution_data = result.unwrap()
        assert attribution_data['weights'] == {}
        assert attribution_data['no_touchpoints'] == True
        assert 'message' in attribution_data
    
    def test_service_initialization_validates_dependencies(self):
        """Test that service initialization validates all required dependencies"""
        # Act & Assert
        with pytest.raises(TypeError):
            ConversionTrackingService()
        
        with pytest.raises(TypeError):
            ConversionTrackingService(conversion_repository=Mock())
    
    def test_validate_attribution_model_parameter(self, service):
        """Test validation of attribution model parameters"""
        # Valid models should not raise errors
        valid_models = ['first_touch', 'last_touch', 'linear', 'time_decay']
        
        for model in valid_models:
            # Should not raise an exception
            service._validate_attribution_model(model)
        
        # Invalid model should raise error
        with pytest.raises(ValueError, match="Unsupported attribution model"):
            service._validate_attribution_model('invalid_model')
    
    def test_validate_conversion_type_parameter(self, service):
        """Test validation of conversion type parameters"""
        # Valid types should not raise errors
        valid_types = ['purchase', 'appointment_booked', 'quote_requested', 'lead_qualified', 'custom']
        
        for conversion_type in valid_types:
            service._validate_conversion_type(conversion_type)
        
        # Invalid type should raise error
        with pytest.raises(ValueError, match="Invalid conversion type"):
            service._validate_conversion_type('invalid_type')
    
    # ===== Performance and Caching =====
    
    def test_bulk_record_conversions(self, service, mock_conversion_repository):
        """Test bulk recording of multiple conversion events"""
        # Arrange
        conversion_events = [
            {
                'contact_id': 1,
                'campaign_id': 1,
                'conversion_type': 'purchase',
                'conversion_value': Decimal('100.00')
            },
            {
                'contact_id': 2,
                'campaign_id': 1,
                'conversion_type': 'appointment_booked',
                'conversion_value': Decimal('0.00')
            },
            {
                'contact_id': 3,
                'campaign_id': 1,
                'conversion_type': 'purchase',
                'conversion_value': Decimal('250.00')
            }
        ]
        
        mock_conversion_repository.bulk_create_conversion_events.return_value = 3
        
        # Act
        result = service.bulk_record_conversions(conversion_events)
        
        # Assert
        assert result.is_success
        bulk_result = result.unwrap()
        assert bulk_result['created_count'] == 3
        assert bulk_result['total_value'] == Decimal('350.00')
        assert bulk_result['conversion_types']['purchase'] == 2
        assert bulk_result['conversion_types']['appointment_booked'] == 1
        
        mock_conversion_repository.bulk_create_conversion_events.assert_called_once()
    
    @patch('services.conversion_tracking_service.time.time')
    def test_performance_monitoring(self, mock_time, service, mock_conversion_repository, 
                                   mock_contact_repository, sample_conversion_data):
        """Test that service monitors performance of operations"""
        # Arrange
        # Use a callable that tracks calls and returns different values
        call_count = {'count': 0}
        def time_mock():
            if call_count['count'] == 0:
                call_count['count'] += 1
                return 1000.0
            elif call_count['count'] == 1:
                call_count['count'] += 1
                return 1002.5
            else:
                # For any additional calls (e.g., from logging)
                return 1002.5
        
        mock_time.side_effect = time_mock
        
        mock_contact_repository.get_by_id.return_value = Mock(spec=Contact, id=1)
        mock_conversion_repository.create_conversion_event.return_value = Mock(spec=ConversionEvent, id=1)
        
        # Act
        result = service.record_conversion(sample_conversion_data)
        
        # Assert
        assert result.is_success
        conversion_data = result.unwrap()
        assert 'performance' in conversion_data
        assert conversion_data['performance']['duration_seconds'] == 2.5
        assert conversion_data['performance']['operation'] == 'record_conversion'