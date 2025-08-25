"""
Integration Tests for ROI Calculation System - P4-04 Advanced ROI Calculation
TDD RED PHASE - These tests are written FIRST before implementation
All tests should FAIL initially to ensure proper TDD workflow

Test Coverage:
- Full ROI calculation workflow end-to-end
- Integration between service layers and repositories
- Database operations with real data
- Cache integration and performance
- Complex ROI scenarios with real calculations
- Multi-campaign analysis workflows
- Performance under load
- Data consistency across operations
- Transaction management
- Error recovery and rollback scenarios
"""

import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Dict, Any
from unittest.mock import Mock, patch

# Integration tests for ROI calculation system - now enabled

from services.roi_calculation_service import ROICalculationService
from repositories.roi_repository import ROIRepository
from repositories.conversion_repository import ConversionRepository
from repositories.campaign_repository import CampaignRepository
from repositories.contact_repository import ContactRepository
from services.cache_service import CacheService
from crm_database import (
    Campaign, Contact, CampaignMembership, ConversionEvent,
    CampaignResponse, Activity, Invoice, Quote
)
from utils.datetime_utils import utc_now, ensure_utc
from tests.conftest import create_test_contact, create_test_campaign


class TestROICalculationIntegration:
    """Integration tests for complete ROI calculation system"""
    
    @pytest.fixture
    def roi_repository(self, db_session):
        """Create ROI repository with real database session"""
        return ROIRepository(session=db_session)
    
    @pytest.fixture
    def conversion_repository(self, db_session):
        """Create conversion repository with real database session"""
        return ConversionRepository(session=db_session)
    
    @pytest.fixture
    def campaign_repository(self, db_session):
        """Create campaign repository with real database session"""
        return CampaignRepository(session=db_session)
    
    @pytest.fixture
    def contact_repository(self, db_session):
        """Create contact repository with real database session"""
        return ContactRepository(session=db_session)
    
    @pytest.fixture
    def cache_service(self):
        """Create mock cache service for testing"""
        mock_cache = Mock(spec=CacheService)
        mock_cache.delete_pattern = Mock(return_value=True)
        return mock_cache
    
    @pytest.fixture
    def roi_service(
        self, 
        roi_repository,
        conversion_repository, 
        campaign_repository,
        contact_repository,
        cache_service
    ):
        """Create ROI calculation service with real repositories"""
        return ROICalculationService(
            roi_repository=roi_repository,
            conversion_repository=conversion_repository,
            campaign_repository=campaign_repository,
            contact_repository=contact_repository,
            cache_service=cache_service
        )
    
    @pytest.fixture
    def sample_campaign(self, db_session):
        """Create a sample campaign in the database"""
        campaign = Campaign(
            name="ROI Test Campaign",
            campaign_type="blast",
            status="complete",
            template_a="Test ROI message",
            created_at=utc_now() - timedelta(days=30)
        )
        db_session.add(campaign)
        db_session.commit()
        return campaign
    
    @pytest.fixture
    def sample_contacts(self, db_session):
        """Create sample contacts in the database"""
        contacts = []
        for i in range(10):
            contact = Contact(
                first_name=f"Test{i}",
                last_name="User",
                phone=f"+1234567{i:03d}",
                email=f"test{i}@example.com",
                customer_type="prospect",
                total_sales=Decimal(str(100 * (i + 1)))
            )
            contacts.append(contact)
            db_session.add(contact)
        
        db_session.commit()
        return contacts
    
    @pytest.fixture
    def campaign_with_full_data(self, db_session, sample_campaign, sample_contacts):
        """Create campaign with complete ROI data structure"""
        # Create campaign memberships
        memberships = []
        for i, contact in enumerate(sample_contacts):
            membership = CampaignMembership(
                campaign_id=sample_campaign.id,
                contact_id=contact.id,
                status="sent",
                sent_at=utc_now() - timedelta(days=25),
                message_sent=f"ROI test message to {contact.first_name}"
            )
            memberships.append(membership)
            db_session.add(membership)
        
        # Create conversion events for some contacts
        conversions = []
        for i in range(0, 6):  # 60% conversion rate
            conversion = ConversionEvent(
                contact_id=sample_contacts[i].id,
                campaign_id=sample_campaign.id,
                conversion_type="purchase",
                conversion_value=Decimal(str(150 + i * 25)),
                converted_at=utc_now() - timedelta(days=20 - i),
                attribution_model="last_touch"
            )
            conversions.append(conversion)
            db_session.add(conversion)
        
        # Create campaign responses
        responses = []
        for i in range(0, 8):  # 80% response rate
            response = CampaignResponse(
                campaign_id=sample_campaign.id,
                contact_id=sample_contacts[i].id,
                message_sent_at=utc_now() - timedelta(days=25),
                first_response_at=utc_now() - timedelta(days=24 - i),
                response_sentiment="positive" if i < 6 else "negative",
                response_text=f"Response from contact {i}"
            )
            responses.append(response)
            db_session.add(response)
        
        db_session.commit()
        
        return {
            'campaign': sample_campaign,
            'contacts': sample_contacts,
            'memberships': memberships,
            'conversions': conversions,
            'responses': responses
        }
    
    # ===== End-to-End ROI Calculation Workflows =====
    
    def test_complete_roi_calculation_workflow(
        self, 
        roi_service, 
        db_session, 
        campaign_with_full_data
    ):
        """Test complete ROI calculation from cost recording to final analysis"""
        # Arrange
        campaign = campaign_with_full_data['campaign']
        
        # Record campaign costs
        cost_data = {
            'campaign_id': campaign.id,
            'cost_type': 'sms_cost',
            'amount': Decimal('85.50'),
            'cost_date': utc_now() - timedelta(days=30),
            'description': 'SMS messaging costs',
            'cost_category': 'marketing'
        }
        
        # Act - Test should FAIL initially (RED phase)
        # Step 1: Record costs
        cost_result = roi_service.record_campaign_cost(cost_data)
        
        # Step 2: Calculate CAC
        cac_result = roi_service.calculate_customer_acquisition_cost(campaign.id)
        
        # Step 3: Calculate ROAS
        roas_result = roi_service.calculate_enhanced_roas(campaign.id)
        
        # Step 4: Generate comprehensive analysis
        dashboard_result = roi_service.generate_comprehensive_roi_dashboard(campaign.id)
        
        # Assert
        assert cost_result.is_success
        assert cac_result.is_success
        assert roas_result.is_success
        assert dashboard_result.is_success
        
        # Verify calculated values make sense
        assert cac_result.data['cac'] > 0
        assert roas_result.data['roas'] > 1  # Should be profitable
        assert dashboard_result.data['overall_health_score'] > 50
    
    def test_multi_campaign_comparative_analysis(
        self, 
        roi_service, 
        db_session, 
        sample_contacts
    ):
        """Test comparative ROI analysis across multiple campaigns"""
        # Arrange - Create multiple campaigns with different performance
        campaigns = []
        for i in range(3):
            campaign = Campaign(
                name=f"ROI Campaign {i+1}",
                campaign_type=["blast", "automated", "ab_test"][i],
                status="complete",
                template_a=f"Campaign {i+1} message",
                created_at=utc_now() - timedelta(days=60 - i*10)
            )
            db_session.add(campaign)
            campaigns.append(campaign)
        
        db_session.commit()
        
        # Create different performance data for each campaign
        for i, campaign in enumerate(campaigns):
            # Record costs
            cost_data = {
                'campaign_id': campaign.id,
                'cost_type': 'total_cost',
                'amount': Decimal(str(100 + i * 50)),
                'cost_date': utc_now() - timedelta(days=50 - i*10)
            }
            
            # Create conversions with different values
            for j in range(2 + i * 2):  # Different conversion counts
                conversion = ConversionEvent(
                    contact_id=sample_contacts[j].id,
                    campaign_id=campaign.id,
                    conversion_type="purchase",
                    conversion_value=Decimal(str(200 + i * 100)),
                    converted_at=utc_now() - timedelta(days=45 - i*10)
                )
                db_session.add(conversion)
        
        db_session.commit()
        
        # Act - Test should FAIL initially (RED phase)
        comparison_result = roi_service.compare_campaign_roi_performance()
        
        # Assert
        assert comparison_result.is_success
        assert len(comparison_result.data['comparisons']) == 3
        assert 'best_performing_type' in comparison_result.data
        assert comparison_result.data['performance_gap'] >= 0
    
    def test_ltv_cac_analysis_integration(
        self, 
        roi_service, 
        db_session, 
        campaign_with_full_data
    ):
        """Test integrated LTV:CAC analysis with historical customer data"""
        # Arrange
        campaign = campaign_with_full_data['campaign']
        contacts = campaign_with_full_data['contacts']
        
        # Add historical purchase data for LTV calculation
        for i, contact in enumerate(contacts[:5]):
            # Add multiple historical conversions
            for month in range(1, 7):  # 6 months of history
                conversion = ConversionEvent(
                    contact_id=contact.id,
                    campaign_id=None,  # Historical, not from this campaign
                    conversion_type="purchase",
                    conversion_value=Decimal(str(75 + month * 10)),
                    converted_at=utc_now() - timedelta(days=180 - month*30),
                    attribution_model="organic"
                )
                db_session.add(conversion)
        
        # Record campaign costs for CAC calculation
        cost_data = {
            'campaign_id': campaign.id,
            'cost_type': 'acquisition_cost',
            'amount': Decimal('240.00'),
            'cost_date': utc_now() - timedelta(days=30)
        }
        
        db_session.commit()
        
        # Act - Test should FAIL initially (RED phase)
        # Calculate LTV for a specific contact
        ltv_result = roi_service.calculate_lifetime_value(contacts[0].id)
        
        # Calculate CAC for the campaign
        cac_result = roi_service.calculate_customer_acquisition_cost(campaign.id)
        
        # Calculate LTV:CAC ratio
        ratio_result = roi_service.calculate_ltv_cac_ratio_analysis(campaign.id)
        
        # Assert
        assert ltv_result.is_success
        assert cac_result.is_success
        assert ratio_result.is_success
        
        # Verify business logic
        assert ltv_result.data['net_value'] > 0
        assert cac_result.data['cac'] > 0
        assert ratio_result.data['ltv_cac_ratio'] > 0
        assert ratio_result.data['health_score'] > 0
    
    def test_predictive_roi_modeling_workflow(
        self, 
        roi_service, 
        db_session, 
        campaign_with_full_data
    ):
        """Test complete predictive ROI modeling workflow"""
        # Arrange
        campaign = campaign_with_full_data['campaign']
        
        # Create historical trend data
        for week in range(12):  # 12 weeks of historical data
            cost_data = {
                'campaign_id': campaign.id,
                'cost_type': 'weekly_spend',
                'amount': Decimal(str(20 + week * 2.5)),
                'cost_date': utc_now() - timedelta(weeks=12-week)
            }
            
            # Create corresponding conversions with trend
            for conv in range(int(2 + week * 0.3)):  # Growing conversion trend
                conversion = ConversionEvent(
                    contact_id=campaign_with_full_data['contacts'][conv % 10].id,
                    campaign_id=campaign.id,
                    conversion_type="purchase",
                    conversion_value=Decimal(str(100 + week * 5)),
                    converted_at=utc_now() - timedelta(weeks=12-week, days=conv)
                )
                db_session.add(conversion)
        
        db_session.commit()
        
        # Act - Test should FAIL initially (RED phase)
        # Generate ROI forecast
        forecast_result = roi_service.generate_roi_forecast(campaign.id, forecast_days=30)
        
        # Apply seasonal adjustments
        seasonal_result = roi_service.apply_seasonal_adjustments(campaign.id, target_month=12)
        
        # Calculate prediction confidence
        confidence_result = roi_service.calculate_prediction_confidence(campaign.id, 0.95)
        
        # What-if scenario analysis
        scenarios = {
            'increase_budget': {'budget_multiplier': 1.3},
            'improve_conversion': {'conversion_rate_increase': 0.01}
        }
        scenario_result = roi_service.what_if_scenario_modeling(campaign.id, scenarios)
        
        # Assert
        assert forecast_result.is_success
        assert seasonal_result.is_success
        assert confidence_result.is_success
        assert scenario_result.is_success
        
        # Verify forecast makes sense
        assert forecast_result.data['predicted_roi'] > 0
        assert forecast_result.data['confidence_interval']['lower'] < forecast_result.data['confidence_interval']['upper']
        
        # Verify scenarios show different outcomes
        baseline_roi = scenario_result.data['baseline']['current_roi']
        assert any(
            scenario['projected_roi'] != baseline_roi 
            for scenario in scenario_result.data['scenarios'].values()
        )
    
    # ===== Performance and Scalability Tests =====
    
    def test_large_dataset_roi_calculation_performance(
        self, 
        roi_service, 
        db_session
    ):
        """Test ROI calculation performance with large datasets"""
        # Arrange - Create large campaign with many contacts
        campaign = Campaign(
            name="Large ROI Test Campaign",
            campaign_type="blast",
            status="complete",
            created_at=utc_now() - timedelta(days=90)
        )
        db_session.add(campaign)
        db_session.commit()
        
        # Create many contacts and conversions (simulate real scale)
        contacts = []
        for i in range(100):  # 100 contacts
            contact = Contact(
                first_name=f"Contact{i}",
                last_name="User",
                phone=f"+1555000{i:03d}",
                email=f"contact{i}@example.com"
            )
            contacts.append(contact)
            db_session.add(contact)
        
        db_session.commit()
        
        # Create conversions for 30% of contacts
        for i in range(0, 30):
            conversion = ConversionEvent(
                contact_id=contacts[i].id,
                campaign_id=campaign.id,
                conversion_type="purchase",
                conversion_value=Decimal(str(100 + i * 10)),
                converted_at=utc_now() - timedelta(days=80 - i)
            )
            db_session.add(conversion)
        
        # Add costs
        cost_data = {
            'campaign_id': campaign.id,
            'cost_type': 'total_campaign_cost',
            'amount': Decimal('1500.00'),
            'cost_date': utc_now() - timedelta(days=90)
        }
        
        db_session.commit()
        
        # Act - Test should FAIL initially (RED phase)
        start_time = datetime.now()
        
        # Perform comprehensive ROI analysis
        dashboard_result = roi_service.generate_comprehensive_roi_dashboard(campaign.id)
        
        end_time = datetime.now()
        execution_time = (end_time - start_time).total_seconds()
        
        # Assert
        assert dashboard_result.is_success
        assert execution_time < 5.0  # Should complete within 5 seconds
        assert dashboard_result.data['roi_metrics']['total_conversions'] == 30
    
    def test_batch_roi_processing(
        self, 
        roi_service, 
        db_session, 
        sample_contacts
    ):
        """Test batch processing of ROI calculations for multiple campaigns"""
        # Arrange - Create multiple campaigns
        campaigns = []
        for i in range(5):
            campaign = Campaign(
                name=f"Batch Campaign {i+1}",
                campaign_type="automated",
                status="complete",
                created_at=utc_now() - timedelta(days=60 - i*10)
            )
            db_session.add(campaign)
            campaigns.append(campaign)
        
        db_session.commit()
        
        # Add data to each campaign
        for campaign in campaigns:
            # Add costs
            cost_data = {
                'campaign_id': campaign.id,
                'cost_type': 'campaign_cost',
                'amount': Decimal('200.00'),
                'cost_date': utc_now() - timedelta(days=50)
            }
            
            # Add conversions
            for j in range(3):
                conversion = ConversionEvent(
                    contact_id=sample_contacts[j].id,
                    campaign_id=campaign.id,
                    conversion_type="purchase",
                    conversion_value=Decimal('150.00'),
                    converted_at=utc_now() - timedelta(days=45)
                )
                db_session.add(conversion)
        
        db_session.commit()
        
        campaign_ids = [c.id for c in campaigns]
        
        # Act - Test should FAIL initially (RED phase)
        batch_result = roi_service.batch_calculate_roi_metrics(campaign_ids)
        
        # Assert
        assert batch_result.is_success
        assert len(batch_result.data['results']) == 5
        assert batch_result.data['processing_summary']['successful'] == 5
        assert batch_result.data['processing_summary']['failed'] == 0
    
    # ===== Cache Integration Tests =====
    
    def test_roi_calculation_with_caching(
        self, 
        roi_service, 
        db_session, 
        campaign_with_full_data,
        cache_service
    ):
        """Test ROI calculation with cache integration"""
        # Arrange
        campaign = campaign_with_full_data['campaign']
        cache_service.get.return_value = None  # Cache miss initially
        cache_service.set.return_value = True
        
        # Act - Test should FAIL initially (RED phase)
        # First call should hit database and cache result
        result1 = roi_service.calculate_customer_acquisition_cost(campaign.id)
        
        # Second call should hit cache
        cache_service.get.return_value = {'cac': Decimal('42.50'), 'from_cache': True}
        result2 = roi_service.calculate_customer_acquisition_cost(campaign.id)
        
        # Assert
        assert result1.is_success
        assert result2.is_success
        assert result2.data['from_cache'] == True
        cache_service.set.assert_called_once()  # Called after first calculation
        assert cache_service.get.call_count == 2  # Called for both requests
    
    def test_cache_invalidation_on_data_change(
        self, 
        roi_service, 
        db_session, 
        campaign_with_full_data,
        cache_service
    ):
        """Test cache invalidation when underlying data changes"""
        # Arrange
        campaign = campaign_with_full_data['campaign']
        cache_service.delete_pattern = Mock(return_value=True)
        
        # Act - Test should FAIL initially (RED phase)
        # Add new cost data, which should invalidate cache
        new_cost_data = {
            'campaign_id': campaign.id,
            'cost_type': 'additional_cost',
            'amount': Decimal('75.00'),
            'cost_date': utc_now()
        }
        
        result = roi_service.record_campaign_cost(new_cost_data)
        
        # Assert
        assert result.is_success
        cache_service.delete_pattern.assert_called_with(f"roi_*_{campaign.id}")
    
    # ===== Error Handling and Recovery Tests =====
    
    def test_transaction_rollback_on_error(
        self, 
        roi_service, 
        db_session, 
        campaign_with_full_data
    ):
        """Test transaction rollback when ROI calculation fails"""
        # Arrange
        campaign = campaign_with_full_data['campaign']
        
        # Create invalid cost data that will cause constraint violation
        invalid_cost_data = {
            'campaign_id': campaign.id,
            'cost_type': None,  # This should cause a database constraint error
            'amount': Decimal('100.00')
        }
        
        # Get initial count of cost records
        initial_count = db_session.query(Campaign).count()
        
        # Act - Test should FAIL initially (RED phase)
        result = roi_service.record_campaign_cost(invalid_cost_data)
        
        # Assert
        assert result.is_failure
        # Verify database state wasn't corrupted
        final_count = db_session.query(Campaign).count()
        assert final_count == initial_count
    
    def test_partial_failure_handling(
        self, 
        roi_service, 
        db_session, 
        sample_contacts
    ):
        """Test handling of partial failures in batch operations"""
        # Arrange - Create campaigns, some with invalid data
        valid_campaign = Campaign(
            name="Valid Campaign",
            campaign_type="blast",
            status="complete",
            created_at=utc_now() - timedelta(days=30)
        )
        db_session.add(valid_campaign)
        db_session.commit()
        
        campaign_ids = [valid_campaign.id, 999]  # Valid and invalid ID
        
        # Act - Test should FAIL initially (RED phase)
        batch_result = roi_service.batch_calculate_roi_metrics(campaign_ids)
        
        # Assert
        assert batch_result.is_success  # Overall operation succeeds
        assert batch_result.data['processing_summary']['successful'] == 1
        assert batch_result.data['processing_summary']['failed'] == 1
        assert len(batch_result.data['errors']) == 1
    
    # ===== Data Consistency Tests =====
    
    def test_roi_consistency_across_calculations(
        self, 
        roi_service, 
        db_session, 
        campaign_with_full_data
    ):
        """Test that ROI calculations are consistent across different methods"""
        # Arrange
        campaign = campaign_with_full_data['campaign']
        
        # Record campaign costs
        cost_data = {
            'campaign_id': campaign.id,
            'cost_type': 'total_cost',
            'amount': Decimal('300.00'),
            'cost_date': utc_now() - timedelta(days=30)
        }
        
        db_session.commit()
        
        # Act - Test should FAIL initially (RED phase)
        # Calculate ROI through different methods
        roas_result = roi_service.calculate_enhanced_roas(campaign.id)
        dashboard_result = roi_service.generate_comprehensive_roi_dashboard(campaign.id)
        
        # Assert
        assert roas_result.is_success
        assert dashboard_result.is_success
        
        # Verify consistency between different calculation methods
        roas_from_direct = roas_result.data['roas']
        roas_from_dashboard = dashboard_result.data['roi_metrics']['roas']
        
        # Allow for small rounding differences
        assert abs(roas_from_direct - roas_from_dashboard) < Decimal('0.01')
    
    def test_cross_campaign_data_isolation(
        self, 
        roi_service, 
        db_session, 
        sample_contacts
    ):
        """Test that ROI calculations don't leak data between campaigns"""
        # Arrange - Create two separate campaigns
        campaign1 = Campaign(
            name="Isolated Campaign 1",
            campaign_type="blast",
            status="complete",
            created_at=utc_now() - timedelta(days=30)
        )
        campaign2 = Campaign(
            name="Isolated Campaign 2",
            campaign_type="automated",
            status="complete",
            created_at=utc_now() - timedelta(days=25)
        )
        db_session.add_all([campaign1, campaign2])
        db_session.commit()
        
        # Add different data to each campaign
        # Campaign 1: High cost, low conversions
        conversion1 = ConversionEvent(
            contact_id=sample_contacts[0].id,
            campaign_id=campaign1.id,
            conversion_type="purchase",
            conversion_value=Decimal('100.00'),
            converted_at=utc_now() - timedelta(days=28)
        )
        
        # Campaign 2: Low cost, high conversions
        for i in range(3):
            conversion = ConversionEvent(
                contact_id=sample_contacts[i+1].id,
                campaign_id=campaign2.id,
                conversion_type="purchase",
                conversion_value=Decimal('200.00'),
                converted_at=utc_now() - timedelta(days=23)
            )
            db_session.add(conversion)
        
        db_session.add(conversion1)
        db_session.commit()
        
        # Act - Test should FAIL initially (RED phase)
        roas1_result = roi_service.calculate_enhanced_roas(campaign1.id)
        roas2_result = roi_service.calculate_enhanced_roas(campaign2.id)
        
        # Assert
        assert roas1_result.is_success
        assert roas2_result.is_success
        
        # Verify campaigns have different ROI profiles
        assert roas1_result.data['total_revenue'] != roas2_result.data['total_revenue']
        assert roas1_result.data['roas'] != roas2_result.data['roas']
        
        # Campaign 2 should have better ROAS (more conversions, same cost assumption)
        assert roas2_result.data['total_revenue'] > roas1_result.data['total_revenue']
    
    # ===== Business Logic Integration Tests =====
    
    def test_roi_optimization_workflow_integration(
        self, 
        roi_service, 
        db_session, 
        campaign_with_full_data
    ):
        """Test complete ROI optimization workflow with real data"""
        # Arrange
        campaign = campaign_with_full_data['campaign']
        
        # Create underperforming scenario
        high_cost_data = {
            'campaign_id': campaign.id,
            'cost_type': 'expensive_channel',
            'amount': Decimal('500.00'),  # High cost for few conversions
            'cost_date': utc_now() - timedelta(days=30)
        }
        
        # Act - Test should FAIL initially (RED phase)
        # Step 1: Record high costs
        cost_result = roi_service.record_campaign_cost(high_cost_data)
        
        # Step 2: Identify optimization opportunities
        optimization_result = roi_service.identify_optimization_opportunities(Decimal('3.0'))
        
        # Step 3: Generate strategies
        strategy_result = roi_service.generate_optimization_strategies(campaign.id)
        
        # Step 4: Monitor thresholds
        thresholds = {
            'min_roi': Decimal('3.0'),
            'max_cac': Decimal('60.00')
        }
        alert_result = roi_service.monitor_performance_thresholds(thresholds)
        
        # Assert
        assert cost_result.is_success
        assert optimization_result.is_success
        assert strategy_result.is_success
        assert alert_result.is_success
        
        # Verify optimization workflow detected the issue
        assert len(optimization_result.data['opportunities']) > 0
        assert optimization_result.data['total_potential_improvement'] > 0
        assert len(strategy_result.data['strategies']) > 0
    
    def test_comprehensive_roi_reporting_integration(
        self, 
        roi_service, 
        db_session, 
        campaign_with_full_data
    ):
        """Test comprehensive ROI reporting with all integrated data"""
        # Arrange
        campaign = campaign_with_full_data['campaign']
        
        # Add comprehensive cost data
        cost_types = ['sms_cost', 'labor_cost', 'tool_cost', 'overhead']
        for i, cost_type in enumerate(cost_types):
            cost_data = {
                'campaign_id': campaign.id,
                'cost_type': cost_type,
                'amount': Decimal(str(50 + i * 25)),
                'cost_date': utc_now() - timedelta(days=30 - i)
            }
        
        db_session.commit()
        
        # Act - Test should FAIL initially (RED phase)
        # Generate comprehensive dashboard
        dashboard_result = roi_service.generate_comprehensive_roi_dashboard(campaign.id)
        
        # Export ROI data
        export_result = roi_service.export_roi_data(campaign.id, 'csv')
        
        # Assert
        assert dashboard_result.is_success
        assert export_result.is_success
        
        # Verify comprehensive metrics are included
        roi_metrics = dashboard_result.data['roi_metrics']
        assert 'roas' in roi_metrics
        assert 'cac' in roi_metrics
        assert 'ltv_cac_ratio' in roi_metrics
        assert 'payback_period' in roi_metrics
        
        # Verify export contains data
        assert len(export_result.data['data']) > 0
        assert export_result.data['export_format'] == 'csv'
        assert 'download_url' in export_result.data
