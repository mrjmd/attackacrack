"""
Tests for ROICalculationService - P4-04 Advanced ROI Calculation Business Logic
TDD RED PHASE - These tests are written FIRST before implementation
All tests should FAIL initially to ensure proper TDD workflow

Test Coverage:
- Cost tracking and allocation business logic
- CAC and LTV calculation orchestration
- Advanced ROI metrics computation
- Predictive ROI modeling
- ROI optimization recommendations
- Comparative analysis coordination
- Performance monitoring and alerting
- Integration with existing repositories
- Result pattern implementation
- Error handling and validation
- Business rule enforcement
- Cache integration for performance
- Batch processing capabilities
- Data validation and sanitization
"""

import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock, MagicMock, patch, call
from typing import List, Dict, Any, Optional

from services.roi_calculation_service import ROICalculationService
from services.common.result import Result, Success, Failure
from repositories.roi_repository import ROIRepository
from repositories.conversion_repository import ConversionRepository
from repositories.campaign_repository import CampaignRepository
from repositories.contact_repository import ContactRepository
from repositories.campaign_response_repository import CampaignResponseRepository
from services.cache_service import CacheService
from crm_database import (
    ConversionEvent, Campaign, Contact, CampaignMembership, CampaignResponse
)
from utils.datetime_utils import utc_now, ensure_utc
from tests.conftest import create_test_contact, create_test_campaign


class TestROICalculationService:
    """Test ROICalculationService business logic for advanced ROI calculations"""
    
    @pytest.fixture
    def mock_roi_repository(self):
        """Mock ROI repository"""
        return Mock(spec=ROIRepository)
    
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
    def mock_cache_service(self):
        """Mock cache service"""
        return Mock(spec=CacheService)
    
    @pytest.fixture
    def service(
        self, 
        mock_roi_repository,
        mock_conversion_repository,
        mock_campaign_repository,
        mock_contact_repository,
        mock_cache_service
    ):
        """Create service instance with mocked dependencies"""
        return ROICalculationService(
            roi_repository=mock_roi_repository,
            conversion_repository=mock_conversion_repository,
            campaign_repository=mock_campaign_repository,
            contact_repository=mock_contact_repository,
            cache_service=mock_cache_service
        )
    
    @pytest.fixture
    def sample_campaign(self):
        """Sample campaign for testing"""
        campaign = Mock(spec=Campaign)
        campaign.id = 1
        campaign.name = "Test ROI Campaign"
        campaign.campaign_type = "blast"
        campaign.created_at = utc_now() - timedelta(days=30)
        return campaign
    
    @pytest.fixture
    def sample_cost_data(self):
        """Sample cost data for testing"""
        return {
            'campaign_id': 1,
            'cost_type': 'sms_cost',
            'amount': Decimal('125.50'),
            'cost_date': utc_now(),
            'description': 'SMS campaign messaging costs',
            'cost_category': 'marketing',
            'allocation_method': 'direct'
        }
    
    # ===== Cost Tracking Business Logic =====
    
    def test_record_campaign_cost_success(self, service, mock_roi_repository, sample_cost_data):
        """Test recording campaign cost with business validation"""
        # Arrange
        mock_cost_record = Mock()
        mock_cost_record.id = 1
        mock_cost_record.amount = sample_cost_data['amount']
        mock_roi_repository.create_campaign_cost.return_value = mock_cost_record
        mock_roi_repository.get_campaign_costs.return_value = [mock_cost_record]
        
        # Act - Test should FAIL initially (RED phase)
        result = service.record_campaign_cost(sample_cost_data)
        
        # Assert
        assert result.is_success
        assert result.data['cost_id'] == 1
        assert result.data['amount'] == sample_cost_data['amount']
        mock_roi_repository.create_campaign_cost.assert_called_once_with(sample_cost_data)
        
    def test_record_campaign_cost_validation_error(self, service):
        """Test cost recording fails validation"""
        # Arrange
        invalid_data = {
            'campaign_id': None,  # Invalid
            'cost_type': 'sms_cost',
            'amount': Decimal('25.00')
        }
        
        # Act - Test should FAIL initially (RED phase)
        result = service.record_campaign_cost(invalid_data)
        
        # Assert
        assert result.is_failure
        assert "Campaign ID is required" in str(result.error)
    
    def test_record_campaign_cost_business_rules(self, service, mock_roi_repository, sample_cost_data):
        """Test cost recording applies business rules"""
        # Arrange
        # Simulate cost exceeding budget threshold
        sample_cost_data['amount'] = Decimal('10000.00')  # Very high cost
        mock_roi_repository.get_total_campaign_cost.return_value = Decimal('9500.00')
        
        # Act - Test should FAIL initially (RED phase)
        result = service.record_campaign_cost(sample_cost_data)
        
        # Assert
        assert result.is_failure
        assert "Cost exceeds budget threshold" in str(result.error)
    
    def test_allocate_shared_costs(self, service, mock_roi_repository, mock_campaign_repository):
        """Test allocation of shared costs across campaigns"""
        # Arrange
        shared_cost = Decimal('300.00')
        campaign_ids = [1, 2, 3]
        allocation_method = 'equal'
        
        mock_campaigns = [Mock(id=i) for i in campaign_ids]
        mock_campaign_repository.get_by_id.side_effect = mock_campaigns
        mock_roi_repository.create_campaign_cost.return_value = Mock(id=1)
        
        # Act - Test should FAIL initially (RED phase)
        result = service.allocate_shared_costs(shared_cost, campaign_ids, allocation_method)
        
        # Assert
        assert result.is_success
        assert len(result.data['allocations']) == 3
        assert result.data['allocations'][0]['amount'] == Decimal('100.00')  # 300/3
        assert mock_roi_repository.create_campaign_cost.call_count == 3
    
    def test_allocate_shared_costs_weighted(self, service, mock_roi_repository, mock_campaign_repository):
        """Test weighted allocation of shared costs"""
        # Arrange
        shared_cost = Decimal('1000.00')
        allocations = {
            1: {'weight': 0.5},  # 50%
            2: {'weight': 0.3},  # 30%
            3: {'weight': 0.2}   # 20%
        }
        
        mock_campaigns = [Mock(id=i) for i in allocations.keys()]
        mock_campaign_repository.get_by_id.side_effect = mock_campaigns
        mock_roi_repository.create_campaign_cost.return_value = Mock(id=1)
        
        # Act - Test should FAIL initially (RED phase)
        result = service.allocate_shared_costs_weighted(shared_cost, allocations)
        
        # Assert
        assert result.is_success
        assert result.data['allocations'][1]['amount'] == Decimal('500.00')  # 50%
        assert result.data['allocations'][2]['amount'] == Decimal('300.00')  # 30%
        assert result.data['allocations'][3]['amount'] == Decimal('200.00')  # 20%
    
    # ===== CAC and LTV Business Logic =====
    
    def test_calculate_customer_acquisition_cost(self, service, mock_roi_repository, mock_cache_service):
        """Test CAC calculation with caching"""
        # Arrange
        campaign_id = 1
        expected_cac = {
            'campaign_id': campaign_id,
            'total_cost': Decimal('500.00'),
            'new_customers': 10,
            'cac': Decimal('50.00')
        }
        
        mock_cache_service.get.return_value = None  # Cache miss
        mock_roi_repository.calculate_cac.return_value = expected_cac
        mock_cache_service.set.return_value = True
        
        # Act - Test should FAIL initially (RED phase)
        result = service.calculate_customer_acquisition_cost(campaign_id)
        
        # Assert
        assert result.is_success
        assert result.data['cac'] == Decimal('50.00')
        mock_roi_repository.calculate_cac.assert_called_once_with(campaign_id)
        mock_cache_service.set.assert_called_once()
    
    def test_calculate_cac_with_cache_hit(self, service, mock_roi_repository, mock_cache_service):
        """Test CAC calculation returns cached value"""
        # Arrange
        campaign_id = 1
        cached_cac = {
            'campaign_id': campaign_id,
            'cac': Decimal('45.00'),
            'cached_at': utc_now()
        }
        
        mock_cache_service.get.return_value = cached_cac
        
        # Act - Test should FAIL initially (RED phase)
        result = service.calculate_customer_acquisition_cost(campaign_id)
        
        # Assert
        assert result.is_success
        assert result.data['cac'] == Decimal('45.00')
        assert result.data['from_cache'] == True
        mock_roi_repository.calculate_cac.assert_not_called()
    
    def test_calculate_lifetime_value(self, service, mock_roi_repository):
        """Test LTV calculation with business logic"""
        # Arrange
        contact_id = 1
        expected_ltv = {
            'contact_id': contact_id,
            'total_revenue': Decimal('1500.00'),
            'total_cost': Decimal('200.00'),
            'net_value': Decimal('1300.00'),
            'purchase_frequency': 8,
            'customer_lifespan_days': 180
        }
        
        mock_roi_repository.calculate_ltv.return_value = expected_ltv
        
        # Act - Test should FAIL initially (RED phase)
        result = service.calculate_lifetime_value(contact_id)
        
        # Assert
        assert result.is_success
        assert result.data['net_value'] == Decimal('1300.00')
        assert result.data['ltv_score'] in ['low', 'medium', 'high', 'exceptional']
        assert 'ltv_percentile' in result.data
    
    def test_predict_ltv_with_confidence(self, service, mock_roi_repository):
        """Test LTV prediction with confidence scoring"""
        # Arrange
        contact_id = 1
        prediction_days = 365
        
        predicted_ltv = {
            'contact_id': contact_id,
            'prediction_period_days': prediction_days,
            'predicted_revenue': Decimal('2400.00'),
            'predicted_ltv': Decimal('2100.00'),
            'confidence_score': 0.78
        }
        
        mock_roi_repository.calculate_predicted_ltv.return_value = predicted_ltv
        
        # Act - Test should FAIL initially (RED phase)
        result = service.predict_lifetime_value(contact_id, prediction_days)
        
        # Assert
        assert result.is_success
        assert result.data['predicted_ltv'] == Decimal('2100.00')
        assert result.data['confidence_score'] == 0.78
        assert result.data['confidence_level'] in ['low', 'medium', 'high']
        assert 'risk_factors' in result.data
    
    # ===== Advanced ROI Metrics =====
    
    def test_calculate_enhanced_roas(self, service, mock_roi_repository, mock_conversion_repository):
        """Test enhanced ROAS calculation with additional metrics"""
        # Arrange
        campaign_id = 1
        
        roas_data = {
            'campaign_id': campaign_id,
            'total_revenue': Decimal('2500.00'),
            'total_ad_spend': Decimal('500.00'),
            'roas': Decimal('5.00'),
            'roas_percentage': 400.0
        }
        
        conversion_data = {
            'total_conversions': 25,
            'avg_conversion_value': Decimal('100.00')
        }
        
        mock_roi_repository.calculate_roas.return_value = roas_data
        mock_conversion_repository.get_conversion_value_statistics.return_value = conversion_data
        
        # Act - Test should FAIL initially (RED phase)
        result = service.calculate_enhanced_roas(campaign_id)
        
        # Assert
        assert result.is_success
        assert result.data['roas'] == Decimal('5.00')
        assert result.data['performance_grade'] in ['A', 'B', 'C', 'D', 'F']
        assert result.data['benchmark_comparison'] in ['above', 'at', 'below']
        assert 'improvement_recommendations' in result.data
    
    def test_calculate_ltv_cac_ratio_analysis(self, service, mock_roi_repository):
        """Test comprehensive LTV:CAC ratio analysis"""
        # Arrange
        campaign_id = 1
        
        ratio_data = {
            'campaign_id': campaign_id,
            'avg_ltv': Decimal('450.00'),
            'avg_cac': Decimal('75.00'),
            'ltv_cac_ratio': Decimal('6.00'),
            'ratio_quality': 'excellent'
        }
        
        mock_roi_repository.calculate_ltv_cac_ratio.return_value = ratio_data
        
        # Act - Test should FAIL initially (RED phase)
        result = service.calculate_ltv_cac_ratio_analysis(campaign_id)
        
        # Assert
        assert result.is_success
        assert result.data['ltv_cac_ratio'] == Decimal('6.00')
        assert result.data['ratio_quality'] == 'excellent'
        assert result.data['health_score'] > 80  # High health score for 6:1 ratio
        assert 'sustainability_analysis' in result.data
        assert 'optimization_opportunities' in result.data
    
    def test_calculate_payback_period_analysis(self, service, mock_roi_repository):
        """Test comprehensive payback period analysis"""
        # Arrange
        campaign_id = 1
        
        payback_data = {
            'campaign_id': campaign_id,
            'payback_months': 2.3,
            'payback_days': 69,
            'break_even_achieved': True
        }
        
        mock_roi_repository.calculate_payback_period.return_value = payback_data
        
        # Act - Test should FAIL initially (RED phase)
        result = service.calculate_payback_period_analysis(campaign_id)
        
        # Assert
        assert result.is_success
        assert result.data['payback_months'] == 2.3
        assert result.data['payback_category'] in ['fast', 'normal', 'slow']
        assert result.data['risk_assessment'] in ['low', 'medium', 'high']
        assert 'cash_flow_impact' in result.data
    
    # ===== Predictive ROI and Forecasting =====
    
    def test_generate_roi_forecast(self, service, mock_roi_repository, mock_cache_service):
        """Test ROI forecasting with multiple models"""
        # Arrange
        campaign_id = 1
        forecast_days = 90
        
        forecast_data = {
            'campaign_id': campaign_id,
            'forecast_period_days': forecast_days,
            'predicted_revenue': Decimal('1800.00'),
            'predicted_costs': Decimal('400.00'),
            'predicted_roi': Decimal('3.50'),
            'confidence_interval': {
                'lower': Decimal('2.80'),
                'upper': Decimal('4.20')
            },
            'trend_direction': 'up'
        }
        
        mock_roi_repository.calculate_roi_forecast.return_value = forecast_data
        
        # Act - Test should FAIL initially (RED phase)
        result = service.generate_roi_forecast(campaign_id, forecast_days)
        
        # Assert
        assert result.is_success
        assert result.data['predicted_roi'] == Decimal('3.50')
        assert result.data['forecast_reliability'] in ['low', 'medium', 'high']
        assert result.data['scenario_analysis']['optimistic']['roi'] > result.data['predicted_roi']
        assert result.data['scenario_analysis']['pessimistic']['roi'] < result.data['predicted_roi']
        assert 'risk_factors' in result.data
    
    def test_apply_seasonal_adjustments(self, service, mock_roi_repository):
        """Test seasonal ROI adjustments"""
        # Arrange
        campaign_id = 1
        target_month = 12  # December
        
        seasonal_data = {
            'campaign_id': campaign_id,
            'target_month': target_month,
            'seasonal_factor': 1.4,
            'adjusted_roi_prediction': Decimal('4.90'),
            'historical_monthly_factors': {
                '11': 1.1,
                '12': 1.4,
                '1': 0.8
            }
        }
        
        mock_roi_repository.calculate_seasonal_adjustments.return_value = seasonal_data
        
        # Act - Test should FAIL initially (RED phase)
        result = service.apply_seasonal_adjustments(campaign_id, target_month)
        
        # Assert
        assert result.is_success
        assert result.data['seasonal_factor'] == 1.4
        assert result.data['seasonality_strength'] in ['weak', 'moderate', 'strong']
        assert 'planning_recommendations' in result.data
    
    def test_calculate_prediction_confidence(self, service, mock_roi_repository):
        """Test prediction confidence interval calculations"""
        # Arrange
        campaign_id = 1
        confidence_level = 0.95
        
        confidence_data = {
            'campaign_id': campaign_id,
            'confidence_level': confidence_level,
            'mean_roi': Decimal('4.20'),
            'lower_bound': Decimal('3.45'),
            'upper_bound': Decimal('4.95'),
            'margin_of_error': 0.75
        }
        
        mock_roi_repository.calculate_confidence_intervals.return_value = confidence_data
        
        # Act - Test should FAIL initially (RED phase)
        result = service.calculate_prediction_confidence(campaign_id, confidence_level)
        
        # Assert
        assert result.is_success
        assert result.data['confidence_level'] == confidence_level
        assert result.data['prediction_quality'] in ['poor', 'fair', 'good', 'excellent']
        assert 'reliability_factors' in result.data
    
    def test_what_if_scenario_modeling(self, service, mock_roi_repository):
        """Test what-if scenario analysis"""
        # Arrange
        campaign_id = 1
        scenarios = {
            'budget_increase_25': {'budget_multiplier': 1.25},
            'conversion_boost': {'conversion_rate_increase': 0.015},
            'cost_reduction': {'cost_reduction_percentage': 0.10}
        }
        
        scenario_results = {
            'campaign_id': campaign_id,
            'baseline': {
                'current_budget': Decimal('200.00'),
                'current_conversion_rate': 0.04,
                'current_roi': Decimal('3.50')
            },
            'scenarios': {
                'budget_increase_25': {'projected_roi': Decimal('3.80')},
                'conversion_boost': {'projected_roi': Decimal('4.20')},
                'cost_reduction': {'projected_roi': Decimal('3.85')}
            }
        }
        
        mock_roi_repository.what_if_scenario_analysis.return_value = scenario_results
        
        # Act - Test should FAIL initially (RED phase)
        result = service.what_if_scenario_modeling(campaign_id, scenarios)
        
        # Assert
        assert result.is_success
        assert len(result.data['scenarios']) == 3
        assert result.data['best_scenario'] == 'conversion_boost'  # Highest ROI
        assert result.data['roi_improvement_potential'] > 0
        assert 'implementation_recommendations' in result.data
    
    # ===== Comparative Analysis =====
    
    def test_compare_campaign_roi_performance(self, service, mock_roi_repository):
        """Test comprehensive campaign ROI comparison"""
        # Arrange
        comparison_data = [
            {'campaign_type': 'blast', 'avg_roi': Decimal('3.2'), 'campaign_count': 8},
            {'campaign_type': 'automated', 'avg_roi': Decimal('4.5'), 'campaign_count': 5},
            {'campaign_type': 'ab_test', 'avg_roi': Decimal('5.1'), 'campaign_count': 3}
        ]
        
        mock_roi_repository.compare_roi_by_campaign_type.return_value = comparison_data
        
        # Act - Test should FAIL initially (RED phase)
        result = service.compare_campaign_roi_performance()
        
        # Assert
        assert result.is_success
        assert len(result.data['comparisons']) == 3
        assert result.data['best_performing_type'] == 'ab_test'
        assert result.data['performance_gap'] > 0  # Gap between best and worst
        assert 'strategic_recommendations' in result.data
    
    def test_analyze_roi_by_customer_segments(self, service, mock_roi_repository):
        """Test ROI analysis by customer segments"""
        # Arrange
        campaign_id = 1
        segment_data = [
            {'segment': 'high_value', 'roi': Decimal('7.2'), 'customer_count': 12},
            {'segment': 'medium_value', 'roi': Decimal('3.8'), 'customer_count': 28},
            {'segment': 'low_value', 'roi': Decimal('1.9'), 'customer_count': 45}
        ]
        
        mock_roi_repository.compare_roi_by_customer_segment.return_value = segment_data
        
        # Act - Test should FAIL initially (RED phase)
        result = service.analyze_roi_by_customer_segments(campaign_id)
        
        # Assert
        assert result.is_success
        assert len(result.data['segments']) == 3
        assert result.data['highest_roi_segment'] == 'high_value'
        assert result.data['segment_distribution']['high_value']['percentage'] < 50  # Should be minority
        assert 'targeting_recommendations' in result.data
    
    def test_channel_roi_comparison(self, service, mock_roi_repository):
        """Test ROI comparison across marketing channels"""
        # Arrange
        date_from = utc_now() - timedelta(days=90)
        date_to = utc_now()
        
        channel_data = [
            {'channel': 'sms', 'roi': Decimal('4.2'), 'cost': Decimal('350.00')},
            {'channel': 'email', 'roi': Decimal('3.6'), 'cost': Decimal('125.00')},
            {'channel': 'call', 'roi': Decimal('8.5'), 'cost': Decimal('280.00')}
        ]
        
        mock_roi_repository.compare_roi_by_channel.return_value = channel_data
        
        # Act - Test should FAIL initially (RED phase)
        result = service.channel_roi_comparison(date_from, date_to)
        
        # Assert
        assert result.is_success
        assert len(result.data['channels']) == 3
        assert result.data['most_efficient_channel'] == 'call'
        assert result.data['cost_effectiveness_ranking'][0]['channel'] == 'call'
        assert 'channel_optimization_strategy' in result.data
    
    def test_ab_test_roi_analysis(self, service, mock_roi_repository):
        """Test A/B test ROI analysis with statistical significance"""
        # Arrange
        campaign_id = 1
        
        ab_test_data = {
            'campaign_id': campaign_id,
            'variant_a': {'roi': Decimal('3.4'), 'conversions': 8},
            'variant_b': {'roi': Decimal('4.9'), 'conversions': 12},
            'statistical_significance': 0.95,
            'winner': 'B'
        }
        
        mock_roi_repository.ab_test_roi_comparison.return_value = ab_test_data
        
        # Act - Test should FAIL initially (RED phase)
        result = service.ab_test_roi_analysis(campaign_id)
        
        # Assert
        assert result.is_success
        assert result.data['winner'] == 'B'
        assert result.data['improvement_percentage'] > 0
        assert result.data['confidence_level'] >= 0.95
        assert 'rollout_recommendation' in result.data
    
    # ===== ROI Optimization =====
    
    def test_identify_optimization_opportunities(self, service, mock_roi_repository):
        """Test identification of ROI optimization opportunities"""
        # Arrange
        roi_threshold = Decimal('3.5')
        
        underperforming_campaigns = [
            {
                'campaign_id': 1,
                'roi': Decimal('2.1'),
                'improvement_suggestions': ['increase_conversion_rate', 'reduce_costs']
            },
            {
                'campaign_id': 3,
                'roi': Decimal('1.8'),
                'improvement_suggestions': ['better_targeting', 'optimize_messaging']
            }
        ]
        
        mock_roi_repository.identify_underperforming_campaigns.return_value = underperforming_campaigns
        
        # Act - Test should FAIL initially (RED phase)
        result = service.identify_optimization_opportunities(roi_threshold)
        
        # Assert
        assert result.is_success
        assert len(result.data['opportunities']) == 2
        assert result.data['total_potential_improvement'] > 0
        assert 'prioritized_actions' in result.data
        assert 'expected_impact' in result.data['opportunities'][0]
    
    def test_generate_optimization_strategies(self, service, mock_roi_repository):
        """Test generation of optimization strategies"""
        # Arrange
        campaign_id = 1
        
        strategy_data = {
            'campaign_id': campaign_id,
            'current_roi': Decimal('2.8'),
            'optimization_strategies': [
                {
                    'strategy': 'improve_targeting',
                    'priority': 'high',
                    'expected_impact': 'medium',
                    'implementation_effort': 'low'
                },
                {
                    'strategy': 'optimize_messaging',
                    'priority': 'medium',
                    'expected_impact': 'high',
                    'implementation_effort': 'medium'
                }
            ]
        }
        
        mock_roi_repository.suggest_optimization_strategies.return_value = strategy_data
        
        # Act - Test should FAIL initially (RED phase)
        result = service.generate_optimization_strategies(campaign_id)
        
        # Assert
        assert result.is_success
        assert len(result.data['strategies']) == 2
        assert result.data['roi_improvement_potential'] > 0
        assert 'implementation_roadmap' in result.data
        assert 'resource_requirements' in result.data
    
    def test_optimize_budget_allocation(self, service, mock_roi_repository):
        """Test budget allocation optimization"""
        # Arrange
        total_budget = Decimal('5000.00')
        
        allocation_data = {
            'total_budget': total_budget,
            'current_allocation': {
                1: Decimal('2000.00'),  # High ROI campaign
                2: Decimal('1500.00'),  # Medium ROI campaign
                3: Decimal('1500.00')   # Low ROI campaign
            },
            'recommended_allocation': {
                1: Decimal('2800.00'),  # Increase high performer
                2: Decimal('1600.00'),  # Slight increase
                3: Decimal('600.00')    # Decrease underperformer
            },
            'expected_roi_improvement': Decimal('1.2')
        }
        
        mock_roi_repository.budget_allocation_recommendations.return_value = allocation_data
        
        # Act - Test should FAIL initially (RED phase)
        result = service.optimize_budget_allocation(total_budget)
        
        # Assert
        assert result.is_success
        assert result.data['total_budget'] == total_budget
        assert result.data['reallocation_impact'] > 0
        assert 'implementation_plan' in result.data
        assert 'risk_assessment' in result.data
    
    def test_monitor_performance_thresholds(self, service, mock_roi_repository):
        """Test performance threshold monitoring and alerting"""
        # Arrange
        thresholds = {
            'min_roi': Decimal('3.0'),
            'max_cac': Decimal('60.00'),
            'min_conversion_rate': 0.025
        }
        
        alert_data = {
            'alerts': [
                {
                    'campaign_id': 1,
                    'campaign_name': 'Alert Campaign',
                    'violated_thresholds': ['min_roi', 'max_cac'],
                    'severity': 'high'
                }
            ]
        }
        
        mock_roi_repository.performance_threshold_alerts.return_value = alert_data
        
        # Act - Test should FAIL initially (RED phase)
        result = service.monitor_performance_thresholds(thresholds)
        
        # Assert
        assert result.is_success
        assert len(result.data['alerts']) == 1
        assert result.data['alerts'][0]['severity'] == 'high'
        assert 'recommended_actions' in result.data['alerts'][0]
        assert 'alert_summary' in result.data
    
    # ===== Integration and Orchestration =====
    
    def test_comprehensive_roi_dashboard_data(self, service, mock_roi_repository, mock_conversion_repository):
        """Test generation of comprehensive ROI dashboard data"""
        # Arrange
        campaign_id = 1
        
        # Mock multiple repository calls
        mock_roi_repository.calculate_roas.return_value = {'roas': Decimal('4.5')}
        mock_roi_repository.calculate_ltv_cac_ratio.return_value = {'ltv_cac_ratio': Decimal('5.2')}
        mock_roi_repository.calculate_payback_period.return_value = {'payback_months': 2.8}
        mock_conversion_repository.calculate_conversion_rate_for_campaign.return_value = {'conversion_rate': 0.045}
        
        # Act - Test should FAIL initially (RED phase)
        result = service.generate_comprehensive_roi_dashboard(campaign_id)
        
        # Assert
        assert result.is_success
        assert 'roi_metrics' in result.data
        assert 'performance_indicators' in result.data
        assert 'trend_analysis' in result.data
        assert 'optimization_recommendations' in result.data
        assert result.data['overall_health_score'] > 0
    
    def test_batch_roi_calculation(self, service, mock_roi_repository):
        """Test batch ROI calculations for multiple campaigns"""
        # Arrange
        campaign_ids = [1, 2, 3, 4, 5]
        
        # Mock batch processing
        mock_roi_repository.calculate_roas.side_effect = [
            {'campaign_id': i, 'roas': Decimal(str(3.0 + i * 0.5))} 
            for i in campaign_ids
        ]
        
        # Act - Test should FAIL initially (RED phase)
        result = service.batch_calculate_roi_metrics(campaign_ids)
        
        # Assert
        assert result.is_success
        assert len(result.data['results']) == 5
        assert result.data['processing_summary']['successful'] == 5
        assert result.data['processing_summary']['failed'] == 0
    
    def test_roi_data_export(self, service, mock_roi_repository):
        """Test ROI data export functionality"""
        # Arrange
        campaign_id = 1
        export_format = 'csv'
        
        export_data = {
            'campaign_id': campaign_id,
            'export_format': export_format,
            'data': [
                {'metric': 'ROAS', 'value': '4.50', 'period': '2025-01'},
                {'metric': 'CAC', 'value': '45.00', 'period': '2025-01'}
            ]
        }
        
        # Act - Test should FAIL initially (RED phase)
        result = service.export_roi_data(campaign_id, export_format)
        
        # Assert
        assert result.is_success
        assert result.data['export_format'] == export_format
        assert len(result.data['data']) > 0
        assert 'download_url' in result.data
    
    # ===== Error Handling and Edge Cases =====
    
    def test_handle_repository_errors_gracefully(self, service, mock_roi_repository):
        """Test graceful handling of repository errors"""
        # Arrange
        campaign_id = 1
        mock_roi_repository.calculate_cac.side_effect = Exception("Database connection failed")
        
        # Act - Test should FAIL initially (RED phase)
        result = service.calculate_customer_acquisition_cost(campaign_id)
        
        # Assert
        assert result.is_failure
        assert "Database connection failed" in str(result.error)
    
    def test_validate_business_rules(self, service):
        """Test business rule validation"""
        # Arrange
        invalid_campaign_id = -1
        
        # Act - Test should FAIL initially (RED phase)
        result = service.calculate_customer_acquisition_cost(invalid_campaign_id)
        
        # Assert
        assert result.is_failure
        assert "Invalid campaign ID" in str(result.error)
    
    def test_handle_missing_data_scenarios(self, service, mock_roi_repository):
        """Test handling of missing data scenarios"""
        # Arrange
        campaign_id = 999  # Non-existent campaign
        mock_roi_repository.calculate_roas.return_value = None
        
        # Act - Test should FAIL initially (RED phase)
        result = service.calculate_enhanced_roas(campaign_id)
        
        # Assert
        assert result.is_failure
        assert "No data found" in str(result.error)
    
    def test_cache_invalidation(self, service, mock_cache_service, mock_roi_repository):
        """Test cache invalidation when data changes"""
        # Arrange
        campaign_id = 1
        cost_data = {'campaign_id': 1, 'amount': Decimal('50.00'), 'cost_type': 'sms_cost'}
        
        mock_roi_repository.create_campaign_cost.return_value = Mock(id=1)
        mock_cache_service.delete_pattern.return_value = True
        
        # Act - Test should FAIL initially (RED phase)
        result = service.record_campaign_cost(cost_data)
        
        # Assert
        assert result.is_success
        mock_cache_service.delete_pattern.assert_called_with(f"roi_*_{campaign_id}")
    
    def test_concurrent_calculation_handling(self, service, mock_roi_repository):
        """Test handling of concurrent ROI calculations"""
        # Arrange
        campaign_id = 1
        
        # Simulate concurrent access with locking
        mock_roi_repository.calculate_cac.side_effect = [
            Exception("Resource locked"),  # First call fails
            {'cac': Decimal('50.00')}       # Retry succeeds
        ]
        
        # Act - Test should FAIL initially (RED phase)
        result = service.calculate_customer_acquisition_cost(campaign_id, retry_on_lock=True)
        
        # Assert
        assert result.is_success
        assert result.data['cac'] == Decimal('50.00')
        assert mock_roi_repository.calculate_cac.call_count == 2
