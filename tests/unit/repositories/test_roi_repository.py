"""
Tests for ROIRepository - P4-04 Advanced ROI Calculation Data Layer
TDD RED PHASE - These tests are written FIRST before implementation
All tests should FAIL initially to ensure proper TDD workflow

Test Coverage:
- Cost tracking and management
- Customer Acquisition Cost (CAC) calculations
- Lifetime Value (LTV) calculations
- Cost per conversion analytics
- Cost allocation and attribution
- Advanced ROI metrics
- LTV:CAC ratio analysis
- Payback period calculations
- Break-even analysis
- Profit margin analysis
- ROI by cohort analysis
- Predictive ROI calculations
- ROI forecasting and trend analysis
- Seasonal adjustments
- Confidence intervals for predictions
- What-if scenario analysis
- Comparative ROI analysis
- ROI optimization recommendations
- Performance threshold alerts
- Edge cases and error handling
"""

import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock, MagicMock, patch
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from typing import List, Dict, Any, Optional

from repositories.roi_repository import ROIRepository
from repositories.base_repository import PaginationParams, PaginatedResult, SortOrder
from crm_database import (
    ConversionEvent, Campaign, Contact, CampaignMembership, CampaignResponse,
    Activity, Invoice, Quote
)
from utils.datetime_utils import utc_now, ensure_utc


class TestROIRepository:
    """Test ROIRepository data access functionality for advanced ROI calculations"""
    
    @pytest.fixture
    def mock_session(self):
        """Create mock database session"""
        session = Mock()
        session.query.return_value = Mock()
        session.execute.return_value = Mock()
        return session
    
    @pytest.fixture
    def repository(self, mock_session):
        """Create repository instance with mocked dependencies"""
        return ROIRepository(session=mock_session)
    
    @pytest.fixture
    def sample_cost_data(self):
        """Sample cost data for testing"""
        return {
            'campaign_id': 1,
            'cost_type': 'sms_cost',
            'amount': Decimal('25.50'),
            'currency': 'USD',
            'cost_date': utc_now(),
            'description': 'SMS campaign costs',
            'cost_category': 'marketing',
            'allocation_method': 'direct'
        }
    
    @pytest.fixture
    def sample_revenue_data(self):
        """Sample revenue data for testing"""
        return {
            'contact_id': 1,
            'campaign_id': 1,
            'revenue_amount': Decimal('500.00'),
            'revenue_date': utc_now(),
            'revenue_type': 'purchase',
            'attribution_weight': 0.8
        }
    
    # ===== Cost Tracking and Management =====
    
    def test_create_campaign_cost_success(self, repository, mock_session, sample_cost_data):
        """Test creating campaign cost record"""
        # Arrange
        mock_cost = Mock()
        mock_cost.id = 1
        mock_cost.campaign_id = sample_cost_data['campaign_id']
        mock_cost.cost_type = sample_cost_data['cost_type']
        mock_cost.amount = sample_cost_data['amount']
        
        # Act
        result = repository.create_campaign_cost(sample_cost_data)
        
        # Assert - Test should FAIL initially (RED phase)
        assert result.campaign_id == sample_cost_data['campaign_id']
        assert result.amount == sample_cost_data['amount']
        mock_session.add.assert_called_once()
        mock_session.flush.assert_called_once()
    
    def test_create_campaign_cost_validation_error(self, repository):
        """Test cost creation fails with invalid data"""
        # Arrange
        invalid_data = {
            'campaign_id': None,  # Invalid - required
            'cost_type': 'sms_cost',
            'amount': Decimal('25.50')
        }
        
        # Act & Assert - Test should FAIL initially (RED phase)
        with pytest.raises(ValueError, match="Campaign ID is required"):
            repository.create_campaign_cost(invalid_data)
    
    def test_create_campaign_cost_negative_amount_error(self, repository):
        """Test cost creation fails with negative amount"""
        # Arrange
        invalid_data = {
            'campaign_id': 1,
            'cost_type': 'sms_cost',
            'amount': Decimal('-25.50')  # Invalid - negative amount
        }
        
        # Act & Assert - Test should FAIL initially (RED phase)
        with pytest.raises(ValueError, match="Cost amount must be positive"):
            repository.create_campaign_cost(invalid_data)
    
    def test_get_campaign_costs(self, repository, mock_session):
        """Test retrieving all costs for a campaign"""
        # Arrange
        campaign_id = 1
        mock_query = Mock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.all.return_value = [Mock(), Mock()]
        
        # Act - Test should FAIL initially (RED phase)
        result = repository.get_campaign_costs(campaign_id)
        
        # Assert
        assert len(result) == 2
        mock_session.query.assert_called_once()
        mock_query.filter.assert_called_once()
    
    def test_get_total_campaign_cost(self, repository, mock_session):
        """Test calculating total cost for a campaign"""
        # Arrange
        campaign_id = 1
        mock_query = Mock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.scalar.return_value = Decimal('125.75')
        
        # Act - Test should FAIL initially (RED phase)
        result = repository.get_total_campaign_cost(campaign_id)
        
        # Assert
        assert result == Decimal('125.75')
        mock_query.scalar.assert_called_once()
    
    def test_get_costs_by_type(self, repository, mock_session):
        """Test retrieving costs grouped by type"""
        # Arrange
        campaign_id = 1
        mock_result = Mock()
        mock_session.execute.return_value = mock_result
        mock_result.fetchall.return_value = [
            ('sms_cost', Decimal('50.00')),
            ('labor_cost', Decimal('75.00'))
        ]
        
        # Act - Test should FAIL initially (RED phase)
        result = repository.get_costs_by_type(campaign_id)
        
        # Assert
        assert 'sms_cost' in result
        assert result['sms_cost'] == Decimal('50.00')
        assert 'labor_cost' in result
        assert result['labor_cost'] == Decimal('75.00')
    
    # ===== Customer Acquisition Cost (CAC) Calculations =====
    
    def test_calculate_cac_for_campaign(self, repository, mock_session):
        """Test calculating Customer Acquisition Cost for a campaign"""
        # Arrange
        campaign_id = 1
        mock_result = Mock()
        mock_session.execute.return_value = mock_result
        mock_result.fetchone.return_value = (Decimal('100.00'), 4)  # total_cost, new_customers
        
        # Act - Test should FAIL initially (RED phase)
        result = repository.calculate_cac(campaign_id)
        
        # Assert
        assert result['campaign_id'] == campaign_id
        assert result['total_cost'] == Decimal('100.00')
        assert result['new_customers'] == 4
        assert result['cac'] == Decimal('25.00')  # 100/4
    
    def test_calculate_cac_no_customers(self, repository, mock_session):
        """Test CAC calculation when no customers acquired"""
        # Arrange
        campaign_id = 1
        mock_result = Mock()
        mock_session.execute.return_value = mock_result
        mock_result.fetchone.return_value = (Decimal('100.00'), 0)  # no new customers
        
        # Act - Test should FAIL initially (RED phase)
        result = repository.calculate_cac(campaign_id)
        
        # Assert
        assert result['cac'] == Decimal('0.00')  # Avoid division by zero
        assert result['new_customers'] == 0
    
    def test_calculate_cac_by_channel(self, repository, mock_session):
        """Test CAC calculation by marketing channel"""
        # Arrange
        campaign_id = 1
        mock_result = Mock()
        mock_session.execute.return_value = mock_result
        mock_result.fetchall.return_value = [
            ('sms', Decimal('75.00'), 3),  # channel, cost, customers
            ('email', Decimal('25.00'), 1)
        ]
        
        # Act - Test should FAIL initially (RED phase)
        result = repository.calculate_cac_by_channel(campaign_id)
        
        # Assert
        assert 'sms' in result
        assert result['sms']['cac'] == Decimal('25.00')  # 75/3
        assert 'email' in result
        assert result['email']['cac'] == Decimal('25.00')  # 25/1
    
    # ===== Lifetime Value (LTV) Calculations =====
    
    def test_calculate_ltv_for_contact(self, repository, mock_session):
        """Test calculating Lifetime Value for a contact"""
        # Arrange
        contact_id = 1
        mock_result = Mock()
        mock_session.execute.return_value = mock_result
        mock_result.fetchone.return_value = (
            Decimal('750.00'),  # total_revenue
            Decimal('150.00'),  # total_cost
            6,                  # purchase_frequency
            90                  # days_as_customer
        )
        
        # Act - Test should FAIL initially (RED phase)
        result = repository.calculate_ltv(contact_id)
        
        # Assert
        assert result['contact_id'] == contact_id
        assert result['total_revenue'] == Decimal('750.00')
        assert result['total_cost'] == Decimal('150.00')
        assert result['net_value'] == Decimal('600.00')  # 750-150
        assert result['purchase_frequency'] == 6
        assert result['customer_lifespan_days'] == 90
    
    def test_calculate_predicted_ltv(self, repository, mock_session):
        """Test predicting future LTV based on historical data"""
        # Arrange
        contact_id = 1
        prediction_days = 365
        mock_result = Mock()
        mock_session.execute.return_value = mock_result
        mock_result.fetchone.return_value = (
            Decimal('125.00'),  # avg_monthly_revenue
            Decimal('25.00'),   # avg_monthly_cost
            0.95                # retention_probability
        )
        
        # Act - Test should FAIL initially (RED phase)
        result = repository.calculate_predicted_ltv(contact_id, prediction_days)
        
        # Assert
        assert result['contact_id'] == contact_id
        assert result['prediction_period_days'] == prediction_days
        assert 'predicted_revenue' in result
        assert 'predicted_ltv' in result
        assert result['confidence_score'] > 0
    
    def test_calculate_ltv_cohort_analysis(self, repository, mock_session):
        """Test LTV analysis by customer cohorts"""
        # Arrange
        cohort_month = '2025-01'
        mock_result = Mock()
        mock_session.execute.return_value = mock_result
        mock_result.fetchall.return_value = [
            ('2025-01', 10, Decimal('1250.00'), Decimal('250.00')),  # cohort, customers, revenue, cost
            ('2024-12', 8, Decimal('980.00'), Decimal('196.00'))
        ]
        
        # Act - Test should FAIL initially (RED phase)
        result = repository.calculate_ltv_cohort_analysis(cohort_month)
        
        # Assert
        assert len(result) == 2
        assert result[0]['cohort_month'] == '2025-01'
        assert result[0]['avg_ltv'] == Decimal('100.00')  # (1250-250)/10
    
    # ===== Advanced ROI Metrics =====
    
    def test_calculate_roas(self, repository, mock_session):
        """Test Return on Ad Spend calculation"""
        # Arrange
        campaign_id = 1
        mock_result = Mock()
        mock_session.execute.return_value = mock_result
        mock_result.fetchone.return_value = (
            Decimal('500.00'),  # total_revenue
            Decimal('100.00')   # total_ad_spend
        )
        
        # Act - Test should FAIL initially (RED phase)
        result = repository.calculate_roas(campaign_id)
        
        # Assert
        assert result['campaign_id'] == campaign_id
        assert result['total_revenue'] == Decimal('500.00')
        assert result['total_ad_spend'] == Decimal('100.00')
        assert result['roas'] == Decimal('5.00')  # 500/100
        assert result['roas_percentage'] == 500.0  # (500-100)/100 * 100
    
    def test_calculate_ltv_cac_ratio(self, repository, mock_session):
        """Test LTV:CAC ratio analysis"""
        # Arrange
        campaign_id = 1
        mock_result = Mock()
        mock_session.execute.return_value = mock_result
        mock_result.fetchone.return_value = (
            Decimal('300.00'),  # avg_ltv
            Decimal('50.00'),   # avg_cac
            15                  # customer_count
        )
        
        # Act - Test should FAIL initially (RED phase)
        result = repository.calculate_ltv_cac_ratio(campaign_id)
        
        # Assert
        assert result['campaign_id'] == campaign_id
        assert result['avg_ltv'] == Decimal('300.00')
        assert result['avg_cac'] == Decimal('50.00')
        assert result['ltv_cac_ratio'] == Decimal('6.00')  # 300/50
        assert result['ratio_quality'] == 'excellent'  # > 5.0
    
    def test_calculate_payback_period(self, repository, mock_session):
        """Test payback period calculation"""
        # Arrange
        campaign_id = 1
        mock_result = Mock()
        mock_session.execute.return_value = mock_result
        mock_result.fetchall.return_value = [
            (1, Decimal('50.00'), Decimal('75.00'), 30),   # month, monthly_revenue, cac, days
            (2, Decimal('75.00'), Decimal('75.00'), 60),
            (3, Decimal('100.00'), Decimal('75.00'), 90)
        ]
        
        # Act - Test should FAIL initially (RED phase)
        result = repository.calculate_payback_period(campaign_id)
        
        # Assert
        assert result['campaign_id'] == campaign_id
        assert 'payback_months' in result
        assert 'payback_days' in result
        assert result['break_even_achieved'] == True
    
    def test_calculate_break_even_analysis(self, repository, mock_session):
        """Test break-even analysis"""
        # Arrange
        campaign_id = 1
        mock_result = Mock()
        mock_session.execute.return_value = mock_result
        mock_result.fetchone.return_value = (
            Decimal('150.00'),  # total_cost
            Decimal('25.00'),   # avg_order_value
            10                  # current_conversions
        )
        
        # Act - Test should FAIL initially (RED phase)
        result = repository.calculate_break_even_analysis(campaign_id)
        
        # Assert
        assert result['campaign_id'] == campaign_id
        assert result['break_even_units'] == 6  # ceil(150/25)
        assert result['current_conversions'] == 10
        assert result['units_above_break_even'] == 4  # 10-6
        assert result['is_profitable'] == True
    
    def test_calculate_profit_margin_analysis(self, repository, mock_session):
        """Test profit margin analysis"""
        # Arrange
        campaign_id = 1
        mock_result = Mock()
        mock_session.execute.return_value = mock_result
        mock_result.fetchone.return_value = (
            Decimal('1000.00'),  # total_revenue
            Decimal('300.00'),   # total_costs
            Decimal('200.00'),   # variable_costs
            Decimal('100.00')    # fixed_costs
        )
        
        # Act - Test should FAIL initially (RED phase)
        result = repository.calculate_profit_margin_analysis(campaign_id)
        
        # Assert
        assert result['campaign_id'] == campaign_id
        assert result['gross_profit'] == Decimal('800.00')  # revenue - variable_costs
        assert result['net_profit'] == Decimal('700.00')    # revenue - total_costs
        assert result['gross_margin'] == 80.0  # (800/1000) * 100
        assert result['net_margin'] == 70.0    # (700/1000) * 100
    
    # ===== Predictive ROI and Forecasting =====
    
    def test_calculate_roi_forecast(self, repository, mock_session):
        """Test ROI forecasting based on historical trends"""
        # Arrange
        campaign_id = 1
        forecast_days = 30
        mock_result = Mock()
        mock_session.execute.return_value = mock_result
        mock_result.fetchall.return_value = [
            ('2025-01-01', Decimal('150.00'), Decimal('30.00')),  # date, revenue, cost
            ('2025-01-15', Decimal('200.00'), Decimal('40.00')),
            ('2025-01-30', Decimal('250.00'), Decimal('50.00'))
        ]
        
        # Act - Test should FAIL initially (RED phase)
        result = repository.calculate_roi_forecast(campaign_id, forecast_days)
        
        # Assert
        assert result['campaign_id'] == campaign_id
        assert result['forecast_period_days'] == forecast_days
        assert 'predicted_revenue' in result
        assert 'predicted_costs' in result
        assert 'predicted_roi' in result
        assert 'confidence_interval' in result
        assert result['trend_direction'] in ['up', 'down', 'stable']
    
    def test_calculate_seasonal_adjustments(self, repository, mock_session):
        """Test seasonal ROI adjustments"""
        # Arrange
        campaign_id = 1
        target_month = 12  # December
        mock_result = Mock()
        mock_session.execute.return_value = mock_result
        mock_result.fetchall.return_value = [
            (1, 0.8),   # month, seasonal_factor
            (12, 1.5),  # December boost
            (6, 0.9)
        ]
        
        # Act - Test should FAIL initially (RED phase)
        result = repository.calculate_seasonal_adjustments(campaign_id, target_month)
        
        # Assert
        assert result['campaign_id'] == campaign_id
        assert result['target_month'] == target_month
        assert result['seasonal_factor'] == 1.5
        assert 'adjusted_roi_prediction' in result
        assert 'historical_monthly_factors' in result
    
    def test_calculate_confidence_intervals(self, repository, mock_session):
        """Test ROI confidence interval calculations"""
        # Arrange
        campaign_id = 1
        confidence_level = 0.95
        mock_result = Mock()
        mock_session.execute.return_value = mock_result
        mock_result.fetchone.return_value = (
            Decimal('4.5'),   # mean_roi
            Decimal('1.2'),   # std_dev
            25                # sample_size
        )
        
        # Act - Test should FAIL initially (RED phase)
        result = repository.calculate_confidence_intervals(campaign_id, confidence_level)
        
        # Assert
        assert result['campaign_id'] == campaign_id
        assert result['confidence_level'] == confidence_level
        assert result['mean_roi'] == Decimal('4.5')
        assert 'lower_bound' in result
        assert 'upper_bound' in result
        assert result['margin_of_error'] > 0
    
    def test_what_if_scenario_analysis(self, repository, mock_session):
        """Test what-if scenario ROI analysis"""
        # Arrange
        campaign_id = 1
        scenarios = {
            'budget_increase': {'budget_multiplier': 1.5},
            'conversion_improvement': {'conversion_rate_increase': 0.02}
        }
        
        mock_result = Mock()
        mock_session.execute.return_value = mock_result
        mock_result.fetchone.return_value = (
            Decimal('100.00'),  # current_budget
            Decimal('0.05'),    # current_conversion_rate
            Decimal('3.5')      # current_roi
        )
        
        # Act - Test should FAIL initially (RED phase)
        result = repository.what_if_scenario_analysis(campaign_id, scenarios)
        
        # Assert
        assert result['campaign_id'] == campaign_id
        assert 'baseline' in result
        assert 'scenarios' in result
        assert 'budget_increase' in result['scenarios']
        assert 'conversion_improvement' in result['scenarios']
        assert result['scenarios']['budget_increase']['projected_roi'] != result['baseline']['current_roi']
    
    # ===== Comparative Analysis =====
    
    def test_compare_roi_by_campaign_type(self, repository, mock_session):
        """Test ROI comparison by campaign type"""
        # Arrange
        mock_result = Mock()
        mock_session.execute.return_value = mock_result
        mock_result.fetchall.return_value = [
            ('blast', Decimal('3.5'), 5),      # campaign_type, avg_roi, campaign_count
            ('automated', Decimal('4.2'), 3),
            ('ab_test', Decimal('5.1'), 2)
        ]
        
        # Act - Test should FAIL initially (RED phase)
        result = repository.compare_roi_by_campaign_type()
        
        # Assert
        assert len(result) == 3
        assert result[0]['campaign_type'] == 'blast'
        assert result[0]['avg_roi'] == Decimal('3.5')
        assert result[2]['campaign_type'] == 'ab_test'
        assert result[2]['avg_roi'] == Decimal('5.1')  # Highest ROI
    
    def test_compare_roi_by_customer_segment(self, repository, mock_session):
        """Test ROI comparison by customer segments"""
        # Arrange
        campaign_id = 1
        mock_result = Mock()
        mock_session.execute.return_value = mock_result
        mock_result.fetchall.return_value = [
            ('high_value', Decimal('6.8'), 15, Decimal('450.00')),  # segment, roi, customers, avg_ltv
            ('medium_value', Decimal('3.2'), 25, Decimal('200.00')),
            ('low_value', Decimal('1.8'), 35, Decimal('75.00'))
        ]
        
        # Act - Test should FAIL initially (RED phase)
        result = repository.compare_roi_by_customer_segment(campaign_id)
        
        # Assert
        assert len(result) == 3
        assert result[0]['segment'] == 'high_value'
        assert result[0]['roi'] == Decimal('6.8')
        assert result[0]['customer_count'] == 15
        assert result[0]['avg_ltv'] == Decimal('450.00')
    
    def test_compare_roi_by_channel(self, repository, mock_session):
        """Test ROI comparison by marketing channel"""
        # Arrange
        date_from = utc_now() - timedelta(days=30)
        date_to = utc_now()
        
        mock_result = Mock()
        mock_session.execute.return_value = mock_result
        mock_result.fetchall.return_value = [
            ('sms', Decimal('4.5'), Decimal('250.00'), Decimal('55.56')),    # channel, roi, cost, cac
            ('email', Decimal('3.8'), Decimal('125.00'), Decimal('32.89')),
            ('call', Decimal('8.2'), Decimal('180.00'), Decimal('90.00'))
        ]
        
        # Act - Test should FAIL initially (RED phase)
        result = repository.compare_roi_by_channel(date_from, date_to)
        
        # Assert
        assert len(result) == 3
        assert result[0]['channel'] == 'sms'
        assert result[2]['channel'] == 'call'
        assert result[2]['roi'] == Decimal('8.2')  # Highest ROI
    
    def test_ab_test_roi_comparison(self, repository, mock_session):
        """Test A/B test ROI comparison"""
        # Arrange
        campaign_id = 1
        mock_result = Mock()
        mock_session.execute.return_value = mock_result
        mock_result.fetchall.return_value = [
            ('A', Decimal('3.2'), 100, 5, Decimal('16.00')),  # variant, roi, sent, conversions, conversion_rate
            ('B', Decimal('4.7'), 100, 8, Decimal('24.00'))
        ]
        
        # Act - Test should FAIL initially (RED phase)
        result = repository.ab_test_roi_comparison(campaign_id)
        
        # Assert
        assert result['campaign_id'] == campaign_id
        assert 'variant_a' in result
        assert 'variant_b' in result
        assert result['variant_b']['roi'] > result['variant_a']['roi']
        assert 'statistical_significance' in result
        assert 'winner' in result
        assert result['winner'] == 'B'
    
    def test_time_based_roi_comparison(self, repository, mock_session):
        """Test ROI comparison across time periods"""
        # Arrange
        campaign_id = 1
        time_periods = ['week', 'month', 'quarter']
        
        mock_result = Mock()
        mock_session.execute.return_value = mock_result
        mock_result.fetchall.return_value = [
            ('2025-W03', Decimal('3.5')),  # period, roi
            ('2025-W04', Decimal('4.2')),
            ('2025-W05', Decimal('3.8'))
        ]
        
        # Act - Test should FAIL initially (RED phase)
        result = repository.time_based_roi_comparison(campaign_id, 'week')
        
        # Assert
        assert result['campaign_id'] == campaign_id
        assert result['time_grouping'] == 'week'
        assert len(result['periods']) == 3
        assert result['trend_analysis']['direction'] in ['up', 'down', 'stable']
        assert 'best_performing_period' in result
    
    # ===== ROI Optimization =====
    
    def test_identify_underperforming_campaigns(self, repository, mock_session):
        """Test identification of underperforming campaigns"""
        # Arrange
        roi_threshold = Decimal('3.0')
        mock_result = Mock()
        mock_session.execute.return_value = mock_result
        mock_result.fetchall.return_value = [
            (1, 'Low ROI Campaign', Decimal('1.8'), 'blast'),     # id, name, roi, type
            (3, 'Another Poor Campaign', Decimal('2.1'), 'automated')
        ]
        
        # Act - Test should FAIL initially (RED phase)
        result = repository.identify_underperforming_campaigns(roi_threshold)
        
        # Assert
        assert len(result) == 2
        assert result[0]['campaign_id'] == 1
        assert result[0]['roi'] < roi_threshold
        assert 'improvement_suggestions' in result[0]
    
    def test_suggest_optimization_strategies(self, repository, mock_session):
        """Test ROI optimization strategy suggestions"""
        # Arrange
        campaign_id = 1
        mock_result = Mock()
        mock_session.execute.return_value = mock_result
        mock_result.fetchone.return_value = (
            Decimal('2.5'),   # current_roi
            Decimal('0.03'),  # conversion_rate
            Decimal('75.00'), # avg_order_value
            Decimal('45.00')  # cac
        )
        
        # Act - Test should FAIL initially (RED phase)
        result = repository.suggest_optimization_strategies(campaign_id)
        
        # Assert
        assert result['campaign_id'] == campaign_id
        assert result['current_roi'] == Decimal('2.5')
        assert 'optimization_strategies' in result
        assert len(result['optimization_strategies']) > 0
        assert 'priority' in result['optimization_strategies'][0]
        assert 'expected_impact' in result['optimization_strategies'][0]
    
    def test_budget_allocation_recommendations(self, repository, mock_session):
        """Test budget allocation recommendations"""
        # Arrange
        total_budget = Decimal('1000.00')
        mock_result = Mock()
        mock_session.execute.return_value = mock_result
        mock_result.fetchall.return_value = [
            (1, 'High ROI Campaign', Decimal('6.5'), Decimal('200.00')),  # id, name, roi, current_budget
            (2, 'Medium ROI Campaign', Decimal('3.8'), Decimal('300.00')),
            (3, 'Low ROI Campaign', Decimal('1.9'), Decimal('500.00'))
        ]
        
        # Act - Test should FAIL initially (RED phase)
        result = repository.budget_allocation_recommendations(total_budget)
        
        # Assert
        assert result['total_budget'] == total_budget
        assert 'current_allocation' in result
        assert 'recommended_allocation' in result
        assert 'expected_roi_improvement' in result
        assert len(result['recommended_allocation']) == 3
    
    def test_performance_threshold_alerts(self, repository, mock_session):
        """Test performance threshold monitoring and alerts"""
        # Arrange
        thresholds = {
            'min_roi': Decimal('3.0'),
            'max_cac': Decimal('50.00'),
            'min_conversion_rate': 0.02
        }
        
        mock_result = Mock()
        mock_session.execute.return_value = mock_result
        mock_result.fetchall.return_value = [
            (1, 'Alert Campaign 1', Decimal('1.5'), Decimal('75.00'), 0.015),  # roi, cac, conv_rate
            (2, 'Alert Campaign 2', Decimal('2.8'), Decimal('55.00'), 0.018)
        ]
        
        # Act - Test should FAIL initially (RED phase)
        result = repository.performance_threshold_alerts(thresholds)
        
        # Assert
        assert 'alerts' in result
        assert len(result['alerts']) == 2
        assert result['alerts'][0]['campaign_id'] == 1
        assert 'violated_thresholds' in result['alerts'][0]
        assert len(result['alerts'][0]['violated_thresholds']) >= 2  # ROI and CAC thresholds
        assert result['alerts'][0]['severity'] in ['low', 'medium', 'high', 'critical']
    
    # ===== Edge Cases and Error Handling =====
    
    def test_handle_zero_division_in_calculations(self, repository, mock_session):
        """Test proper handling of zero division scenarios"""
        # Arrange
        campaign_id = 1
        mock_result = Mock()
        mock_session.execute.return_value = mock_result
        mock_result.fetchone.return_value = (Decimal('0.00'), 0)  # zero cost, zero customers
        
        # Act - Test should FAIL initially (RED phase)
        result = repository.calculate_cac(campaign_id)
        
        # Assert
        assert result['cac'] == Decimal('0.00')
        assert result['total_cost'] == Decimal('0.00')
        # Should not raise division by zero error
    
    def test_handle_missing_data_gracefully(self, repository, mock_session):
        """Test graceful handling of missing or null data"""
        # Arrange
        campaign_id = 999  # Non-existent campaign
        mock_result = Mock()
        mock_session.execute.return_value = mock_result
        mock_result.fetchone.return_value = None
        
        # Act - Test should FAIL initially (RED phase)
        result = repository.calculate_roas(campaign_id)
        
        # Assert
        assert result['campaign_id'] == campaign_id
        assert result['total_revenue'] == Decimal('0.00')
        assert result['total_ad_spend'] == Decimal('0.00')
        assert result['roas'] == Decimal('0.00')
    
    def test_database_error_handling(self, repository, mock_session):
        """Test proper error handling for database failures"""
        # Arrange
        mock_session.execute.side_effect = SQLAlchemyError("Database connection failed")
        
        # Act & Assert - Test should FAIL initially (RED phase)
        with pytest.raises(SQLAlchemyError):
            repository.calculate_cac(1)
    
    def test_invalid_date_range_handling(self, repository):
        """Test handling of invalid date ranges"""
        # Arrange
        campaign_id = 1
        date_from = utc_now()
        date_to = utc_now() - timedelta(days=1)  # Invalid: from > to
        
        # Act & Assert - Test should FAIL initially (RED phase)
        with pytest.raises(ValueError, match="date_from must be before date_to"):
            repository.time_based_roi_comparison(campaign_id, 'day', date_from, date_to)
    
    def test_performance_with_large_datasets(self, repository, mock_session):
        """Test repository performance with large datasets"""
        # Arrange
        campaign_id = 1
        mock_result = Mock()
        mock_session.execute.return_value = mock_result
        # Simulate large dataset
        mock_result.fetchall.return_value = [(i, f'Campaign {i}', Decimal('3.5'), 'blast') for i in range(1000)]
        
        # Act - Test should FAIL initially (RED phase)
        result = repository.compare_roi_by_campaign_type()
        
        # Assert
        assert len(result) == 1000  # Should handle large datasets
        # Performance assertion - should complete within reasonable time
        # (This would be measured in actual implementation)
    
    def test_concurrent_access_handling(self, repository, mock_session):
        """Test handling of concurrent database access"""
        # Arrange
        campaign_id = 1
        cost_data = {'campaign_id': 1, 'cost_type': 'sms_cost', 'amount': Decimal('25.00')}
        
        # Simulate concurrent modification
        mock_session.add.side_effect = IntegrityError("Concurrent modification", None, None)
        
        # Act & Assert - Test should FAIL initially (RED phase)
        with pytest.raises(IntegrityError):
            repository.create_campaign_cost(cost_data)
    
    # ===== Search and Query Methods =====
    
    def test_search_functionality(self, repository, mock_session):
        """Test search functionality for ROI data"""
        # Arrange
        query = "high roi"
        fields = ['campaign_name', 'notes']
        
        mock_query = Mock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = [Mock(), Mock()]
        
        # Act - Test should FAIL initially (RED phase)
        result = repository.search(query, fields)
        
        # Assert
        assert len(result) == 2
        mock_session.query.assert_called_once()
