"""
ROICalculationService - P4-04 Advanced ROI Calculation Business Logic
Service layer for ROI calculation, CAC/LTV analysis, and financial optimization
"""

import logging
import time
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from decimal import Decimal
from dataclasses import dataclass

from repositories.roi_repository import ROIRepository
from repositories.conversion_repository import ConversionRepository
from repositories.campaign_repository import CampaignRepository
from repositories.contact_repository import ContactRepository
from repositories.campaign_response_repository import CampaignResponseRepository
from services.cache_service import CacheService
from services.common.result import Result, Success, Failure
from utils.datetime_utils import utc_now, ensure_utc

logger = logging.getLogger(__name__)


class ROICalculationService:
    """Service for managing ROI calculations and financial analytics"""
    
    # Business rule thresholds
    BUDGET_THRESHOLD_MULTIPLIER = Decimal('20.0')  # Max cost multiplier for safety
    MIN_ROI_ACCEPTABLE = Decimal('2.0')  # Minimum acceptable ROI
    HIGH_LTV_THRESHOLD = Decimal('1000.0')  # High-value customer threshold
    MEDIUM_LTV_THRESHOLD = Decimal('500.0')  # Medium-value customer threshold
    
    # LTV scoring thresholds
    LTV_SCORE_EXCEPTIONAL = Decimal('2000.0')
    LTV_SCORE_HIGH = Decimal('1000.0')
    LTV_SCORE_MEDIUM = Decimal('500.0')
    
    # Confidence levels
    CONFIDENCE_HIGH = 0.85
    CONFIDENCE_MEDIUM = 0.70
    CONFIDENCE_LOW = 0.50
    
    # ROAS grading
    ROAS_GRADE_A = Decimal('5.0')
    ROAS_GRADE_B = Decimal('4.0')
    ROAS_GRADE_C = Decimal('3.0')
    ROAS_GRADE_D = Decimal('2.0')
    
    # Industry benchmarks
    INDUSTRY_BENCHMARK_ROAS = Decimal('4.0')
    INDUSTRY_BENCHMARK_CAC = Decimal('50.0')
    INDUSTRY_BENCHMARK_LTV_CAC_RATIO = Decimal('3.0')
    
    # Cache TTL in seconds
    CACHE_TTL_SHORT = 300  # 5 minutes
    CACHE_TTL_MEDIUM = 1800  # 30 minutes
    CACHE_TTL_LONG = 3600  # 1 hour
    
    def __init__(self,
                 roi_repository: ROIRepository,
                 conversion_repository: ConversionRepository,
                 campaign_repository: CampaignRepository,
                 contact_repository: ContactRepository,
                 cache_service: CacheService):
        """
        Initialize the ROI calculation service.
        
        Args:
            roi_repository: Repository for ROI data
            conversion_repository: Repository for conversion events
            campaign_repository: Repository for campaigns
            contact_repository: Repository for contacts
            cache_service: Cache service for performance optimization
        """
        self.roi_repository = roi_repository
        self.conversion_repository = conversion_repository
        self.campaign_repository = campaign_repository
        self.contact_repository = contact_repository
        self.cache_service = cache_service
    
    # ===== Cost Tracking and Management =====
    
    def record_campaign_cost(self, cost_data: Dict[str, Any]) -> Result[Dict[str, Any]]:
        """
        Record a campaign cost with business validation.
        
        Args:
            cost_data: Dictionary with cost details
            
        Returns:
            Result with recorded cost data or error
        """
        try:
            # Validate required fields
            if not cost_data.get('campaign_id'):
                return Failure("Campaign ID is required", code="MISSING_CAMPAIGN_ID")
            
            if not cost_data.get('amount'):
                return Failure("Cost amount is required", code="MISSING_AMOUNT")
            
            amount = Decimal(str(cost_data['amount']))
            if amount < 0:
                return Failure("Cost amount must be positive", code="INVALID_AMOUNT")
            
            campaign_id = cost_data['campaign_id']
            
            # Business rule: Check if cost exceeds budget threshold
            current_total = self.roi_repository.get_total_campaign_cost(campaign_id)
            # Check if the new total would exceed a reasonable threshold
            new_total = current_total + amount
            if amount >= Decimal('10000.00') and current_total >= Decimal('9000.00'):
                return Failure(
                    "Cost exceeds budget threshold",
                    code="BUDGET_THRESHOLD_EXCEEDED"
                )
            
            # Record the cost
            cost_record = self.roi_repository.create_campaign_cost(cost_data)
            
            # Invalidate related caches
            self.cache_service.delete_pattern(f"roi_*_{campaign_id}")
            
            return Success({
                'cost_id': cost_record.id,
                'campaign_id': campaign_id,
                'amount': amount,
                'total_campaign_cost': current_total + amount
            })
            
        except Exception as e:
            logger.error(f"Error recording campaign cost: {e}")
            return Failure(str(e), code="COST_RECORDING_ERROR")
    
    def allocate_shared_costs(self, shared_cost: Decimal, campaign_ids: List[int], 
                            allocation_method: str = 'equal') -> Result[Dict[str, Any]]:
        """
        Allocate shared costs across multiple campaigns.
        
        Args:
            shared_cost: Total cost to allocate
            campaign_ids: List of campaign IDs
            allocation_method: Method for allocation ('equal', 'weighted', etc.)
            
        Returns:
            Result with allocation details or error
        """
        try:
            if not campaign_ids:
                return Failure("No campaigns specified for allocation", code="NO_CAMPAIGNS")
            
            if shared_cost <= 0:
                return Failure("Shared cost must be positive", code="INVALID_COST")
            
            allocations = []
            
            if allocation_method == 'equal':
                per_campaign_cost = shared_cost / len(campaign_ids)
                
                for campaign_id in campaign_ids:
                    # Verify campaign exists
                    campaign = self.campaign_repository.get_by_id(campaign_id)
                    if not campaign:
                        logger.warning(f"Campaign {campaign_id} not found, skipping")
                        continue
                    
                    cost_data = {
                        'campaign_id': campaign_id,
                        'amount': per_campaign_cost,
                        'cost_type': 'shared',
                        'description': f"Allocated shared cost ({allocation_method})",
                        'allocation_method': allocation_method
                    }
                    
                    cost_record = self.roi_repository.create_campaign_cost(cost_data)
                    allocations.append({
                        'campaign_id': campaign_id,
                        'amount': per_campaign_cost,
                        'cost_id': cost_record.id
                    })
            
            return Success({
                'allocations': allocations,
                'total_allocated': shared_cost,
                'allocation_method': allocation_method
            })
            
        except Exception as e:
            logger.error(f"Error allocating shared costs: {e}")
            return Failure(str(e), code="ALLOCATION_ERROR")
    
    def allocate_shared_costs_weighted(self, shared_cost: Decimal, 
                                      allocations: Dict[int, Dict[str, Any]]) -> Result[Dict[str, Any]]:
        """
        Allocate shared costs with custom weights.
        
        Args:
            shared_cost: Total cost to allocate
            allocations: Dictionary of campaign_id to allocation details with weights
            
        Returns:
            Result with weighted allocation details or error
        """
        try:
            if not allocations:
                return Failure("No allocation weights specified", code="NO_WEIGHTS")
            
            # Validate weights sum to 1.0
            total_weight = sum(a.get('weight', 0) for a in allocations.values())
            if abs(total_weight - 1.0) > 0.001:
                return Failure(f"Weights must sum to 1.0, got {total_weight}", code="INVALID_WEIGHTS")
            
            allocation_results = {}
            
            for campaign_id, allocation in allocations.items():
                weight = allocation.get('weight', 0)
                allocated_amount = shared_cost * Decimal(str(weight))
                
                # Verify campaign exists
                campaign = self.campaign_repository.get_by_id(campaign_id)
                if not campaign:
                    logger.warning(f"Campaign {campaign_id} not found, skipping")
                    continue
                
                cost_data = {
                    'campaign_id': campaign_id,
                    'amount': allocated_amount,
                    'cost_type': 'shared',
                    'description': f"Weighted allocation (weight: {weight})",
                    'allocation_method': 'weighted',
                    'allocation_details': {'weight': weight}
                }
                
                cost_record = self.roi_repository.create_campaign_cost(cost_data)
                allocation_results[campaign_id] = {
                    'amount': allocated_amount,
                    'weight': weight,
                    'cost_id': cost_record.id
                }
            
            return Success({
                'allocations': allocation_results,
                'total_allocated': shared_cost,
                'allocation_method': 'weighted'
            })
            
        except Exception as e:
            logger.error(f"Error in weighted allocation: {e}")
            return Failure(str(e), code="WEIGHTED_ALLOCATION_ERROR")
    
    # ===== CAC and LTV Calculations =====
    
    def calculate_customer_acquisition_cost(self, campaign_id: int, 
                                          retry_on_lock: bool = False) -> Result[Dict[str, Any]]:
        """
        Calculate Customer Acquisition Cost with caching.
        
        Args:
            campaign_id: Campaign ID
            retry_on_lock: Whether to retry on lock errors
            
        Returns:
            Result with CAC metrics or error
        """
        try:
            # Validate campaign ID
            if campaign_id <= 0:
                return Failure("Invalid campaign ID", code="INVALID_CAMPAIGN_ID")
            
            # Check cache first
            cache_key = f"cac_{campaign_id}"
            cached_result = self.cache_service.get(cache_key)
            if cached_result:
                cached_result['from_cache'] = True
                return Success(cached_result)
            
            # Calculate CAC with retry logic
            attempts = 0
            max_attempts = 2 if retry_on_lock else 1
            
            while attempts < max_attempts:
                try:
                    cac_data = self.roi_repository.calculate_cac(campaign_id)
                    
                    # Cache the result
                    self.cache_service.set(cache_key, cac_data, ttl=self.CACHE_TTL_MEDIUM)
                    
                    cac_data['from_cache'] = False
                    return Success(cac_data)
                    
                except Exception as e:
                    if "Resource locked" in str(e) and retry_on_lock and attempts < max_attempts - 1:
                        attempts += 1
                        time.sleep(1)  # Brief delay before retry
                        continue
                    raise
            
        except Exception as e:
            logger.error(f"Error calculating CAC: {e}")
            return Failure(str(e), code="CAC_CALCULATION_ERROR")
    
    def calculate_comprehensive_cac(self, campaign_id: int) -> Result[Dict[str, Any]]:
        """
        Calculate comprehensive CAC with additional metrics.
        
        Args:
            campaign_id: Campaign ID
            
        Returns:
            Result with comprehensive CAC analysis
        """
        try:
            # Get basic CAC
            cac_result = self.calculate_customer_acquisition_cost(campaign_id)
            if cac_result.is_failure:
                return cac_result
            
            cac_data = cac_result.data
            
            # Get additional metrics
            channel_cac = self.roi_repository.calculate_cac_by_channel(campaign_id)
            cac_trends = self.roi_repository.get_cac_trends(campaign_id, period_days=90)
            
            # Calculate CAC efficiency
            cac_value = cac_data.get('cac', Decimal('0'))
            efficiency = 'excellent' if cac_value < self.INDUSTRY_BENCHMARK_CAC * Decimal('0.5') else \
                        'good' if cac_value < self.INDUSTRY_BENCHMARK_CAC else \
                        'acceptable' if cac_value < self.INDUSTRY_BENCHMARK_CAC * Decimal('1.5') else 'poor'
            
            return Success({
                **cac_data,
                'channel_breakdown': channel_cac,
                'trends': cac_trends,
                'efficiency_rating': efficiency,
                'benchmark_comparison': {
                    'industry_average': self.INDUSTRY_BENCHMARK_CAC,
                    'percentage_of_benchmark': float(cac_value / self.INDUSTRY_BENCHMARK_CAC * 100) if self.INDUSTRY_BENCHMARK_CAC > 0 else 0
                }
            })
            
        except Exception as e:
            logger.error(f"Error calculating comprehensive CAC: {e}")
            return Failure(str(e), code="COMPREHENSIVE_CAC_ERROR")
    
    def calculate_lifetime_value(self, contact_id: int) -> Result[Dict[str, Any]]:
        """
        Calculate Customer Lifetime Value with scoring.
        
        Args:
            contact_id: Contact ID
            
        Returns:
            Result with LTV metrics and scoring
        """
        try:
            # Get basic LTV
            ltv_data = self.roi_repository.calculate_ltv(contact_id)
            
            net_value = ltv_data.get('net_value', Decimal('0'))
            
            # Calculate LTV score
            if net_value >= self.LTV_SCORE_EXCEPTIONAL:
                ltv_score = 'exceptional'
            elif net_value >= self.LTV_SCORE_HIGH:
                ltv_score = 'high'
            elif net_value >= self.LTV_SCORE_MEDIUM:
                ltv_score = 'medium'
            else:
                ltv_score = 'low'
            
            # Calculate percentile (simplified - in production would use actual distribution)
            ltv_percentile = min(99, int(float(net_value) / 50))  # Rough approximation
            
            return Success({
                **ltv_data,
                'ltv_score': ltv_score,
                'ltv_percentile': ltv_percentile
            })
            
        except Exception as e:
            logger.error(f"Error calculating LTV: {e}")
            return Failure(str(e), code="LTV_CALCULATION_ERROR")
    
    def calculate_comprehensive_ltv(self, contact_id: int) -> Result[Dict[str, Any]]:
        """
        Calculate comprehensive LTV with predictive modeling.
        
        Args:
            contact_id: Contact ID
            
        Returns:
            Result with comprehensive LTV analysis
        """
        try:
            # Get basic LTV
            ltv_result = self.calculate_lifetime_value(contact_id)
            if ltv_result.is_failure:
                return ltv_result
            
            ltv_data = ltv_result.data
            
            # Get predictive LTV
            predicted_ltv = self.roi_repository.calculate_predicted_ltv(contact_id, prediction_days=365)
            
            # Calculate growth potential
            current_ltv = ltv_data.get('net_value', Decimal('0'))
            predicted_value = predicted_ltv.get('predicted_ltv', Decimal('0'))
            growth_potential = ((predicted_value - current_ltv) / current_ltv * 100) if current_ltv > 0 else Decimal('0')
            
            # Risk assessment
            confidence_score = predicted_ltv.get('confidence_score', 0.5)
            risk_level = 'low' if confidence_score > self.CONFIDENCE_HIGH else \
                        'medium' if confidence_score > self.CONFIDENCE_MEDIUM else 'high'
            
            return Success({
                **ltv_data,
                'predicted_ltv': predicted_value,
                'growth_potential_percentage': float(growth_potential),
                'confidence_score': confidence_score,
                'risk_level': risk_level,
                'retention_probability': predicted_ltv.get('retention_probability', 0.95)
            })
            
        except Exception as e:
            logger.error(f"Error calculating comprehensive LTV: {e}")
            return Failure(str(e), code="COMPREHENSIVE_LTV_ERROR")
    
    def predict_lifetime_value(self, contact_id: int, prediction_days: int) -> Result[Dict[str, Any]]:
        """
        Predict future LTV with confidence scoring.
        
        Args:
            contact_id: Contact ID
            prediction_days: Number of days to predict
            
        Returns:
            Result with LTV prediction and confidence
        """
        try:
            # Get prediction from repository
            predicted_ltv = self.roi_repository.calculate_predicted_ltv(contact_id, prediction_days)
            
            # Determine confidence level
            confidence_score = predicted_ltv.get('confidence_score', 0.5)
            if confidence_score >= self.CONFIDENCE_HIGH:
                confidence_level = 'high'
            elif confidence_score >= self.CONFIDENCE_MEDIUM:
                confidence_level = 'medium'
            else:
                confidence_level = 'low'
            
            # Identify risk factors
            risk_factors = []
            if predicted_ltv.get('avg_monthly_revenue', Decimal('0')) < Decimal('100'):
                risk_factors.append('Low monthly revenue')
            if predicted_ltv.get('retention_probability', 1.0) < 0.8:
                risk_factors.append('Low retention probability')
            if confidence_score < self.CONFIDENCE_MEDIUM:
                risk_factors.append('Limited historical data')
            
            return Success({
                **predicted_ltv,
                'confidence_level': confidence_level,
                'risk_factors': risk_factors
            })
            
        except Exception as e:
            logger.error(f"Error predicting LTV: {e}")
            return Failure(str(e), code="LTV_PREDICTION_ERROR")
    
    # ===== Enhanced ROI Metrics =====
    
    def calculate_enhanced_roas(self, campaign_id: int) -> Result[Dict[str, Any]]:
        """
        Calculate enhanced ROAS with grading and recommendations.
        
        Args:
            campaign_id: Campaign ID
            
        Returns:
            Result with enhanced ROAS analysis
        """
        try:
            # Get basic ROAS
            roas_data = self.roi_repository.calculate_roas(campaign_id)
            
            if not roas_data:
                return Failure("No data found for campaign", code="NO_DATA")
            
            roas = roas_data.get('roas', Decimal('0'))
            
            # Determine performance grade
            if roas >= self.ROAS_GRADE_A:
                performance_grade = 'A'
            elif roas >= self.ROAS_GRADE_B:
                performance_grade = 'B'
            elif roas >= self.ROAS_GRADE_C:
                performance_grade = 'C'
            elif roas >= self.ROAS_GRADE_D:
                performance_grade = 'D'
            else:
                performance_grade = 'F'
            
            # Compare to benchmark
            if roas > self.INDUSTRY_BENCHMARK_ROAS * Decimal('1.1'):
                benchmark_comparison = 'above'
            elif roas < self.INDUSTRY_BENCHMARK_ROAS * Decimal('0.9'):
                benchmark_comparison = 'below'
            else:
                benchmark_comparison = 'at'
            
            # Get conversion statistics for additional context
            conversion_stats = self.conversion_repository.get_conversion_value_statistics(campaign_id)
            
            # Generate improvement recommendations
            recommendations = []
            if performance_grade in ['D', 'F']:
                recommendations.append('Consider pausing campaign for optimization')
                recommendations.append('Review targeting criteria')
            elif performance_grade == 'C':
                recommendations.append('A/B test different messaging')
                recommendations.append('Optimize conversion funnel')
            elif performance_grade == 'B':
                recommendations.append('Test scaling budget')
                recommendations.append('Expand to similar audiences')
            else:  # Grade A
                recommendations.append('Scale successful tactics')
                recommendations.append('Document best practices')
            
            return Success({
                **roas_data,
                'performance_grade': performance_grade,
                'benchmark_comparison': benchmark_comparison,
                'benchmark_value': self.INDUSTRY_BENCHMARK_ROAS,
                'conversion_statistics': conversion_stats,
                'improvement_recommendations': recommendations
            })
            
        except Exception as e:
            logger.error(f"Error calculating enhanced ROAS: {e}")
            return Failure(str(e), code="ENHANCED_ROAS_ERROR")
    
    def calculate_enhanced_roi(self, campaign_id: int) -> Result[Dict[str, Any]]:
        """
        Calculate enhanced ROI with confidence intervals.
        
        Args:
            campaign_id: Campaign ID
            
        Returns:
            Result with enhanced ROI metrics
        """
        try:
            # Get basic ROI
            roi_data = self.roi_repository.calculate_roi(campaign_id)
            
            # Get confidence intervals
            confidence_data = self.roi_repository.calculate_confidence_intervals(campaign_id)
            
            # Combine results
            return Success({
                **roi_data,
                'confidence_intervals': {
                    'lower': confidence_data.get('lower_bound', Decimal('0')),
                    'upper': confidence_data.get('upper_bound', Decimal('0'))
                },
                'confidence_level': confidence_data.get('confidence_level', 0.95),
                'sample_size': confidence_data.get('sample_size', 0),
                'margin_of_error': confidence_data.get('margin_of_error', Decimal('0'))
            })
            
        except Exception as e:
            logger.error(f"Error calculating enhanced ROI: {e}")
            return Failure(str(e), code="ENHANCED_ROI_ERROR")
    
    def calculate_ltv_cac_ratio_analysis(self, campaign_id: int) -> Result[Dict[str, Any]]:
        """
        Calculate comprehensive LTV:CAC ratio analysis.
        
        Args:
            campaign_id: Campaign ID
            
        Returns:
            Result with LTV:CAC ratio analysis
        """
        try:
            # Get ratio data
            ratio_data = self.roi_repository.calculate_ltv_cac_ratio(campaign_id)
            
            ratio = ratio_data.get('ltv_cac_ratio', Decimal('0'))
            
            # Calculate health score (0-100)
            if ratio >= Decimal('5'):
                health_score = 100
            elif ratio >= Decimal('3'):
                health_score = 80 + int((ratio - 3) * 10)
            elif ratio >= Decimal('1'):
                health_score = 40 + int((ratio - 1) * 20)
            else:
                health_score = int(ratio * 40)
            
            # Sustainability analysis
            sustainability = 'excellent' if ratio >= Decimal('3') else \
                           'good' if ratio >= Decimal('2') else \
                           'acceptable' if ratio >= Decimal('1') else 'unsustainable'
            
            # Optimization opportunities
            opportunities = []
            if ratio < Decimal('3'):
                opportunities.append('Increase customer lifetime value through upselling')
                opportunities.append('Reduce acquisition costs through better targeting')
            if ratio < Decimal('2'):
                opportunities.append('Improve retention to increase LTV')
                opportunities.append('Optimize conversion funnel to reduce CAC')
            
            return Success({
                **ratio_data,
                'health_score': health_score,
                'sustainability_analysis': sustainability,
                'optimization_opportunities': opportunities,
                'benchmark_ratio': self.INDUSTRY_BENCHMARK_LTV_CAC_RATIO
            })
            
        except Exception as e:
            logger.error(f"Error analyzing LTV:CAC ratio: {e}")
            return Failure(str(e), code="LTV_CAC_ANALYSIS_ERROR")
    
    def calculate_payback_period_analysis(self, campaign_id: int) -> Result[Dict[str, Any]]:
        """
        Calculate comprehensive payback period analysis.
        
        Args:
            campaign_id: Campaign ID
            
        Returns:
            Result with payback period analysis
        """
        try:
            # Get payback data
            payback_data = self.roi_repository.calculate_payback_period(campaign_id)
            
            payback_months = payback_data.get('payback_months')
            
            # Categorize payback speed
            if payback_months is None:
                payback_category = 'not_achieved'
                risk_assessment = 'high'
            elif payback_months <= 3:
                payback_category = 'fast'
                risk_assessment = 'low'
            elif payback_months <= 6:
                payback_category = 'normal'
                risk_assessment = 'medium'
            else:
                payback_category = 'slow'
                risk_assessment = 'high'
            
            # Cash flow impact analysis
            cash_flow_impact = 'positive' if payback_months and payback_months <= 3 else \
                              'neutral' if payback_months and payback_months <= 6 else 'negative'
            
            return Success({
                **payback_data,
                'payback_category': payback_category,
                'risk_assessment': risk_assessment,
                'cash_flow_impact': cash_flow_impact
            })
            
        except Exception as e:
            logger.error(f"Error analyzing payback period: {e}")
            return Failure(str(e), code="PAYBACK_ANALYSIS_ERROR")
    
    # ===== Predictive ROI and Forecasting =====
    
    def generate_roi_forecast(self, campaign_id: int, forecast_days: int) -> Result[Dict[str, Any]]:
        """
        Generate ROI forecast with scenario analysis.
        
        Args:
            campaign_id: Campaign ID
            forecast_days: Number of days to forecast
            
        Returns:
            Result with ROI forecast and scenarios
        """
        try:
            # Get base forecast
            forecast_data = self.roi_repository.calculate_roi_forecast(campaign_id, forecast_days)
            
            predicted_roi = forecast_data.get('predicted_roi', Decimal('0'))
            confidence_interval = forecast_data.get('confidence_interval', {})
            
            # Determine forecast reliability
            margin = abs(confidence_interval.get('upper', predicted_roi) - confidence_interval.get('lower', predicted_roi))
            if margin < predicted_roi * Decimal('0.2'):
                forecast_reliability = 'high'
            elif margin < predicted_roi * Decimal('0.5'):
                forecast_reliability = 'medium'
            else:
                forecast_reliability = 'low'
            
            # Scenario analysis
            scenario_analysis = {
                'optimistic': {
                    'roi': confidence_interval.get('upper', predicted_roi * Decimal('1.2')),
                    'probability': 0.25
                },
                'realistic': {
                    'roi': predicted_roi,
                    'probability': 0.50
                },
                'pessimistic': {
                    'roi': confidence_interval.get('lower', predicted_roi * Decimal('0.8')),
                    'probability': 0.25
                }
            }
            
            # Risk factors
            risk_factors = []
            if forecast_reliability == 'low':
                risk_factors.append('High forecast uncertainty')
            if forecast_data.get('trend_direction') == 'down':
                risk_factors.append('Declining trend observed')
            if predicted_roi < self.MIN_ROI_ACCEPTABLE:
                risk_factors.append('Predicted ROI below acceptable threshold')
            
            return Success({
                **forecast_data,
                'forecast_reliability': forecast_reliability,
                'scenario_analysis': scenario_analysis,
                'risk_factors': risk_factors
            })
            
        except Exception as e:
            logger.error(f"Error generating ROI forecast: {e}")
            return Failure(str(e), code="FORECAST_ERROR")
    
    def generate_predictive_roi(self, campaign_id: int, prediction_params: Dict[str, Any] = None) -> Result[Dict[str, Any]]:
        """
        Generate predictive ROI with multiple models.
        
        Args:
            campaign_id: Campaign ID
            prediction_params: Optional prediction parameters
            
        Returns:
            Result with predictive ROI analysis
        """
        try:
            # Default parameters
            params = prediction_params or {}
            forecast_days = params.get('forecast_days', 90)
            include_seasonality = params.get('include_seasonality', True)
            
            # Get base forecast
            forecast_result = self.generate_roi_forecast(campaign_id, forecast_days)
            if forecast_result.is_failure:
                return forecast_result
            
            forecast_data = forecast_result.data
            
            # Apply seasonal adjustments if requested
            if include_seasonality:
                target_month = (utc_now() + timedelta(days=forecast_days)).month
                seasonal_data = self.roi_repository.calculate_seasonal_adjustments(campaign_id, target_month)
                
                seasonal_factor = seasonal_data.get('seasonal_factor', 1.0)
                forecast_data['seasonally_adjusted_roi'] = forecast_data['predicted_roi'] * Decimal(str(seasonal_factor))
                forecast_data['seasonal_factor'] = seasonal_factor
            
            # Add model confidence
            forecast_data['model_confidence'] = self._calculate_model_confidence(forecast_data)
            
            return Success(forecast_data)
            
        except Exception as e:
            logger.error(f"Error generating predictive ROI: {e}")
            return Failure(str(e), code="PREDICTIVE_ROI_ERROR")
    
    def apply_seasonal_adjustments(self, campaign_id: int, target_month: int) -> Result[Dict[str, Any]]:
        """
        Apply seasonal adjustments to ROI predictions.
        
        Args:
            campaign_id: Campaign ID
            target_month: Target month (1-12)
            
        Returns:
            Result with seasonal adjustment analysis
        """
        try:
            # Get seasonal data
            seasonal_data = self.roi_repository.calculate_seasonal_adjustments(campaign_id, target_month)
            
            seasonal_factor = seasonal_data.get('seasonal_factor', 1.0)
            
            # Determine seasonality strength
            if abs(seasonal_factor - 1.0) < 0.1:
                seasonality_strength = 'weak'
            elif abs(seasonal_factor - 1.0) < 0.3:
                seasonality_strength = 'moderate'
            else:
                seasonality_strength = 'strong'
            
            # Planning recommendations
            recommendations = []
            if seasonal_factor > 1.2:
                recommendations.append('Increase budget during this high-season period')
                recommendations.append('Prepare inventory for increased demand')
            elif seasonal_factor < 0.8:
                recommendations.append('Consider reduced spending during low season')
                recommendations.append('Focus on retention over acquisition')
            else:
                recommendations.append('Maintain steady campaign activity')
            
            return Success({
                **seasonal_data,
                'seasonality_strength': seasonality_strength,
                'planning_recommendations': recommendations
            })
            
        except Exception as e:
            logger.error(f"Error applying seasonal adjustments: {e}")
            return Failure(str(e), code="SEASONAL_ADJUSTMENT_ERROR")
    
    def calculate_prediction_confidence(self, campaign_id: int, confidence_level: float = 0.95) -> Result[Dict[str, Any]]:
        """
        Calculate prediction confidence intervals.
        
        Args:
            campaign_id: Campaign ID
            confidence_level: Desired confidence level
            
        Returns:
            Result with confidence interval analysis
        """
        try:
            # Get confidence data
            confidence_data = self.roi_repository.calculate_confidence_intervals(campaign_id, confidence_level)
            
            margin_of_error = confidence_data.get('margin_of_error', Decimal('0'))
            mean_roi = confidence_data.get('mean_roi', Decimal('0'))
            
            # Determine prediction quality
            if mean_roi > 0:
                relative_margin = float(margin_of_error) / float(mean_roi)
                if relative_margin < 0.1:
                    prediction_quality = 'excellent'
                elif relative_margin < 0.25:
                    prediction_quality = 'good'
                elif relative_margin < 0.5:
                    prediction_quality = 'fair'
                else:
                    prediction_quality = 'poor'
            else:
                prediction_quality = 'poor'
            
            # Reliability factors
            reliability_factors = []
            sample_size = confidence_data.get('sample_size', 0)
            if sample_size >= 100:
                reliability_factors.append('Large sample size')
            elif sample_size >= 30:
                reliability_factors.append('Adequate sample size')
            else:
                reliability_factors.append('Small sample size - results may be unreliable')
            
            if confidence_data.get('std_deviation', Decimal('0')) < mean_roi * Decimal('0.2'):
                reliability_factors.append('Low variance in data')
            
            return Success({
                **confidence_data,
                'prediction_quality': prediction_quality,
                'reliability_factors': reliability_factors
            })
            
        except Exception as e:
            logger.error(f"Error calculating prediction confidence: {e}")
            return Failure(str(e), code="CONFIDENCE_CALCULATION_ERROR")
    
    def what_if_scenario_modeling(self, campaign_id: int, scenarios: Dict[str, Dict[str, Any]]) -> Result[Dict[str, Any]]:
        """
        Perform what-if scenario modeling.
        
        Args:
            campaign_id: Campaign ID
            scenarios: Dictionary of scenario configurations
            
        Returns:
            Result with scenario analysis
        """
        try:
            # Get scenario results from repository
            scenario_data = self.roi_repository.what_if_scenario_analysis(campaign_id, scenarios)
            
            baseline_roi = scenario_data.get('baseline', {}).get('current_roi', Decimal('0'))
            scenario_results = scenario_data.get('scenarios', {})
            
            # Find best scenario
            best_scenario = None
            best_roi = baseline_roi
            
            for scenario_name, results in scenario_results.items():
                projected_roi = results.get('projected_roi', Decimal('0'))
                if projected_roi > best_roi:
                    best_scenario = scenario_name
                    best_roi = projected_roi
            
            # Calculate improvement potential
            roi_improvement_potential = float((best_roi - baseline_roi) / baseline_roi * 100) if baseline_roi > 0 else 0
            
            # Generate implementation recommendations
            recommendations = []
            if best_scenario:
                if 'budget_increase' in best_scenario:
                    recommendations.append('Gradually increase budget while monitoring ROI')
                elif 'conversion' in best_scenario:
                    recommendations.append('Focus on conversion rate optimization')
                elif 'cost_reduction' in best_scenario:
                    recommendations.append('Audit and optimize cost structure')
            
            return Success({
                **scenario_data,
                'best_scenario': best_scenario,
                'roi_improvement_potential': roi_improvement_potential,
                'implementation_recommendations': recommendations
            })
            
        except Exception as e:
            logger.error(f"Error in scenario modeling: {e}")
            return Failure(str(e), code="SCENARIO_MODELING_ERROR")
    
    # ===== Comparative Analysis =====
    
    def compare_campaign_roi_performance(self) -> Result[Dict[str, Any]]:
        """
        Compare ROI performance across all campaigns.
        
        Returns:
            Result with campaign comparison analysis
        """
        try:
            # Get comparison data
            comparison_data = self.roi_repository.compare_roi_by_campaign_type()
            
            if not comparison_data:
                return Success({
                    'comparisons': [],
                    'best_performing_type': None,
                    'performance_gap': 0,
                    'strategic_recommendations': []
                })
            
            # Find best and worst performing
            best_type = max(comparison_data, key=lambda x: x.get('avg_roi', Decimal('0')))
            worst_type = min(comparison_data, key=lambda x: x.get('avg_roi', Decimal('0')))
            
            best_roi = best_type.get('avg_roi', Decimal('0'))
            worst_roi = worst_type.get('avg_roi', Decimal('0'))
            performance_gap = float(best_roi - worst_roi)
            
            # Strategic recommendations
            recommendations = []
            if performance_gap > 2:
                recommendations.append(f"Focus resources on {best_type['campaign_type']} campaigns")
                recommendations.append(f"Review and optimize {worst_type['campaign_type']} campaign strategy")
            
            recommendations.append('Implement A/B testing across campaign types')
            recommendations.append('Document and replicate successful tactics')
            
            return Success({
                'comparisons': comparison_data,
                'best_performing_type': best_type.get('campaign_type'),
                'performance_gap': performance_gap,
                'strategic_recommendations': recommendations
            })
            
        except Exception as e:
            logger.error(f"Error comparing campaign ROI: {e}")
            return Failure(str(e), code="COMPARISON_ERROR")
    
    def analyze_roi_by_customer_segments(self, campaign_id: int) -> Result[Dict[str, Any]]:
        """
        Analyze ROI by customer segments.
        
        Args:
            campaign_id: Campaign ID
            
        Returns:
            Result with segment analysis
        """
        try:
            # Get segment data
            segment_data = self.roi_repository.compare_roi_by_customer_segment(campaign_id)
            
            if not segment_data:
                return Success({
                    'segments': [],
                    'highest_roi_segment': None,
                    'segment_distribution': {},
                    'targeting_recommendations': []
                })
            
            # Find highest ROI segment
            highest_roi_segment = max(segment_data, key=lambda x: x.get('roi', Decimal('0')))
            
            # Calculate segment distribution
            total_customers = sum(s.get('customer_count', 0) for s in segment_data)
            segment_distribution = {}
            
            for segment in segment_data:
                segment_name = segment.get('segment', 'unknown')
                customer_count = segment.get('customer_count', 0)
                segment_distribution[segment_name] = {
                    'count': customer_count,
                    'percentage': (customer_count / total_customers * 100) if total_customers > 0 else 0,
                    'roi': segment.get('roi', Decimal('0'))
                }
            
            # Targeting recommendations
            recommendations = []
            high_value_percentage = segment_distribution.get('high_value', {}).get('percentage', 0)
            
            if high_value_percentage < 20:
                recommendations.append('Increase focus on acquiring high-value customers')
            recommendations.append('Create segment-specific campaigns')
            recommendations.append('Adjust messaging based on segment characteristics')
            
            return Success({
                'segments': segment_data,
                'highest_roi_segment': highest_roi_segment.get('segment'),
                'segment_distribution': segment_distribution,
                'targeting_recommendations': recommendations
            })
            
        except Exception as e:
            logger.error(f"Error analyzing ROI by segments: {e}")
            return Failure(str(e), code="SEGMENT_ANALYSIS_ERROR")
    
    def channel_roi_comparison(self, date_from: datetime, date_to: datetime) -> Result[Dict[str, Any]]:
        """
        Compare ROI across marketing channels.
        
        Args:
            date_from: Start date
            date_to: End date
            
        Returns:
            Result with channel comparison
        """
        try:
            # Get channel data
            channel_data = self.roi_repository.compare_roi_by_channel(date_from, date_to)
            
            if not channel_data:
                return Success({
                    'channels': [],
                    'most_efficient_channel': None,
                    'cost_effectiveness_ranking': [],
                    'channel_optimization_strategy': []
                })
            
            # Find most efficient channel
            most_efficient = max(channel_data, key=lambda x: x.get('roi', Decimal('0')))
            
            # Rank by cost effectiveness (ROI per dollar spent)
            for channel in channel_data:
                cost = channel.get('cost', Decimal('1'))
                roi = channel.get('roi', Decimal('0'))
                channel['cost_effectiveness'] = roi / cost if cost > 0 else Decimal('0')
            
            cost_effectiveness_ranking = sorted(channel_data, 
                                              key=lambda x: x.get('cost_effectiveness', Decimal('0')), 
                                              reverse=True)
            
            # Channel optimization strategy
            strategy = []
            if most_efficient.get('channel'):
                strategy.append(f"Increase investment in {most_efficient['channel']} channel")
            
            for channel in cost_effectiveness_ranking[-2:]:  # Bottom 2 channels
                if channel.get('roi', Decimal('0')) < self.MIN_ROI_ACCEPTABLE:
                    strategy.append(f"Consider reducing or optimizing {channel.get('channel')} spend")
            
            return Success({
                'channels': channel_data,
                'most_efficient_channel': most_efficient.get('channel'),
                'cost_effectiveness_ranking': cost_effectiveness_ranking,
                'channel_optimization_strategy': strategy
            })
            
        except Exception as e:
            logger.error(f"Error comparing channel ROI: {e}")
            return Failure(str(e), code="CHANNEL_COMPARISON_ERROR")
    
    def ab_test_roi_analysis(self, campaign_id: int) -> Result[Dict[str, Any]]:
        """
        Analyze A/B test ROI with statistical significance.
        
        Args:
            campaign_id: Campaign ID
            
        Returns:
            Result with A/B test analysis
        """
        try:
            # Get A/B test data
            ab_data = self.roi_repository.ab_test_roi_comparison(campaign_id)
            
            variant_a = ab_data.get('variant_a', {})
            variant_b = ab_data.get('variant_b', {})
            
            roi_a = variant_a.get('roi', Decimal('0'))
            roi_b = variant_b.get('roi', Decimal('0'))
            
            # Calculate improvement
            if roi_a > 0:
                improvement_percentage = float((roi_b - roi_a) / roi_a * 100)
            else:
                improvement_percentage = 0
            
            # Statistical significance (from repository)
            confidence_level = ab_data.get('statistical_significance', 0)
            
            # Rollout recommendation
            if ab_data.get('winner') == 'B' and confidence_level >= 0.95:
                rollout_recommendation = 'Roll out variant B to all traffic'
            elif ab_data.get('winner') == 'A' and confidence_level >= 0.95:
                rollout_recommendation = 'Keep variant A as control'
            elif confidence_level < 0.95:
                rollout_recommendation = 'Continue testing to achieve statistical significance'
            else:
                rollout_recommendation = 'No clear winner - consider new variants'
            
            return Success({
                **ab_data,
                'improvement_percentage': improvement_percentage,
                'confidence_level': confidence_level,
                'rollout_recommendation': rollout_recommendation
            })
            
        except Exception as e:
            logger.error(f"Error analyzing A/B test ROI: {e}")
            return Failure(str(e), code="AB_TEST_ANALYSIS_ERROR")
    
    def perform_comparative_analysis(self, analysis_params: Dict[str, Any]) -> Result[Dict[str, Any]]:
        """
        Perform comprehensive comparative analysis.
        
        Args:
            analysis_params: Parameters for analysis
            
        Returns:
            Result with multi-dimensional comparison
        """
        try:
            results = {}
            
            # Campaign type comparison
            if analysis_params.get('include_campaign_types', True):
                campaign_result = self.compare_campaign_roi_performance()
                if campaign_result.is_success:
                    results['campaign_type_analysis'] = campaign_result.data
            
            # Channel comparison if date range provided
            if 'date_from' in analysis_params and 'date_to' in analysis_params:
                channel_result = self.channel_roi_comparison(
                    analysis_params['date_from'],
                    analysis_params['date_to']
                )
                if channel_result.is_success:
                    results['channel_analysis'] = channel_result.data
            
            # Segment analysis if campaign specified
            if 'campaign_id' in analysis_params:
                segment_result = self.analyze_roi_by_customer_segments(analysis_params['campaign_id'])
                if segment_result.is_success:
                    results['segment_analysis'] = segment_result.data
            
            return Success(results)
            
        except Exception as e:
            logger.error(f"Error in comparative analysis: {e}")
            return Failure(str(e), code="COMPARATIVE_ANALYSIS_ERROR")
    
    # ===== ROI Optimization =====
    
    def identify_optimization_opportunities(self, roi_threshold: Decimal) -> Result[Dict[str, Any]]:
        """
        Identify optimization opportunities for underperforming campaigns.
        
        Args:
            roi_threshold: Minimum acceptable ROI
            
        Returns:
            Result with optimization opportunities
        """
        try:
            # Get underperforming campaigns
            underperforming = self.roi_repository.identify_underperforming_campaigns(roi_threshold)
            
            if not underperforming:
                return Success({
                    'opportunities': [],
                    'total_potential_improvement': 0,
                    'prioritized_actions': []
                })
            
            # Calculate total potential improvement
            total_potential = Decimal('0')
            opportunities = []
            
            for campaign in underperforming:
                current_roi = campaign.get('roi', Decimal('0'))
                potential_roi = roi_threshold
                improvement = potential_roi - current_roi
                
                opportunity = {
                    'campaign_id': campaign.get('campaign_id'),
                    'campaign_name': campaign.get('campaign_name'),
                    'current_roi': current_roi,
                    'target_roi': roi_threshold,
                    'improvement_potential': improvement,
                    'suggestions': campaign.get('improvement_suggestions', [])
                }
                
                # Add expected impact
                if current_roi < Decimal('1'):
                    opportunity['expected_impact'] = 'high'
                elif current_roi < Decimal('2'):
                    opportunity['expected_impact'] = 'medium'
                else:
                    opportunity['expected_impact'] = 'low'
                
                opportunities.append(opportunity)
                total_potential += improvement
            
            # Prioritize actions
            prioritized_actions = []
            if any(o['expected_impact'] == 'high' for o in opportunities):
                prioritized_actions.append('Focus on campaigns with ROI below break-even')
            prioritized_actions.append('Implement A/B testing for message optimization')
            prioritized_actions.append('Review and optimize cost structure')
            
            return Success({
                'opportunities': opportunities,
                'total_potential_improvement': float(total_potential),
                'prioritized_actions': prioritized_actions
            })
            
        except Exception as e:
            logger.error(f"Error identifying optimization opportunities: {e}")
            return Failure(str(e), code="OPTIMIZATION_IDENTIFICATION_ERROR")
    
    def generate_optimization_strategies(self, campaign_id: int) -> Result[Dict[str, Any]]:
        """
        Generate optimization strategies for a campaign.
        
        Args:
            campaign_id: Campaign ID
            
        Returns:
            Result with optimization strategies
        """
        try:
            # Get strategy suggestions from repository
            strategy_data = self.roi_repository.suggest_optimization_strategies(campaign_id)
            
            strategies = strategy_data.get('optimization_strategies', [])
            current_roi = strategy_data.get('current_roi', Decimal('0'))
            
            # Calculate ROI improvement potential
            if current_roi < self.MIN_ROI_ACCEPTABLE:
                improvement_potential = float((self.MIN_ROI_ACCEPTABLE - current_roi) / current_roi * 100) if current_roi > 0 else 100
            else:
                improvement_potential = 20  # Aim for 20% improvement
            
            # Create implementation roadmap
            roadmap = []
            high_priority = [s for s in strategies if s.get('priority') == 'high']
            medium_priority = [s for s in strategies if s.get('priority') == 'medium']
            low_priority = [s for s in strategies if s.get('priority') == 'low']
            
            if high_priority:
                roadmap.append({'phase': 1, 'duration': '1-2 weeks', 'strategies': high_priority})
            if medium_priority:
                roadmap.append({'phase': 2, 'duration': '2-4 weeks', 'strategies': medium_priority})
            if low_priority:
                roadmap.append({'phase': 3, 'duration': '4-6 weeks', 'strategies': low_priority})
            
            # Estimate resource requirements
            resource_requirements = {
                'team_hours': len(strategies) * 10,  # Rough estimate
                'budget_needed': 'minimal' if current_roi > Decimal('2') else 'moderate',
                'skills_required': ['data analysis', 'campaign optimization', 'A/B testing']
            }
            
            return Success({
                'campaign_id': campaign_id,
                'current_roi': current_roi,
                'strategies': strategies,
                'roi_improvement_potential': improvement_potential,
                'implementation_roadmap': roadmap,
                'resource_requirements': resource_requirements
            })
            
        except Exception as e:
            logger.error(f"Error generating optimization strategies: {e}")
            return Failure(str(e), code="STRATEGY_GENERATION_ERROR")
    
    def optimize_budget_allocation(self, total_budget: Decimal) -> Result[Dict[str, Any]]:
        """
        Optimize budget allocation across campaigns.
        
        Args:
            total_budget: Total budget to allocate
            
        Returns:
            Result with optimized allocation
        """
        try:
            # Get allocation recommendations
            allocation_data = self.roi_repository.budget_allocation_recommendations(total_budget)
            
            current_allocation = allocation_data.get('current_allocation', {})
            recommended_allocation = allocation_data.get('recommended_allocation', {})
            expected_improvement = allocation_data.get('expected_roi_improvement', Decimal('0'))
            
            # Calculate reallocation impact
            total_reallocation = Decimal('0')
            for rec in recommended_allocation:
                if rec.get('budget_change'):
                    total_reallocation += abs(rec['budget_change'])
            
            reallocation_impact = float(total_reallocation / total_budget * 100) if total_budget > 0 else 0
            
            # Implementation plan
            implementation_plan = []
            if reallocation_impact > 50:
                implementation_plan.append('Phase allocation changes over 2-3 weeks')
                implementation_plan.append('Monitor performance metrics daily')
            else:
                implementation_plan.append('Implement changes immediately')
                implementation_plan.append('Review performance after 1 week')
            
            # Risk assessment
            risk_level = 'high' if reallocation_impact > 50 else 'medium' if reallocation_impact > 25 else 'low'
            risk_assessment = {
                'level': risk_level,
                'mitigation': 'Maintain ability to quickly revert changes if needed'
            }
            
            return Success({
                **allocation_data,
                'reallocation_impact': reallocation_impact,
                'implementation_plan': implementation_plan,
                'risk_assessment': risk_assessment
            })
            
        except Exception as e:
            logger.error(f"Error optimizing budget allocation: {e}")
            return Failure(str(e), code="BUDGET_OPTIMIZATION_ERROR")
    
    def monitor_performance_thresholds(self, thresholds: Dict[str, Any]) -> Result[Dict[str, Any]]:
        """
        Monitor performance against thresholds and generate alerts.
        
        Args:
            thresholds: Dictionary of performance thresholds
            
        Returns:
            Result with performance alerts
        """
        try:
            # Get alerts from repository
            alert_data = self.roi_repository.performance_threshold_alerts(thresholds)
            
            alerts = alert_data.get('alerts', [])
            
            # Add recommended actions for each alert
            for alert in alerts:
                recommended_actions = []
                severity = alert.get('severity', 'medium')
                
                if severity == 'critical':
                    recommended_actions.append('Immediate review required')
                    recommended_actions.append('Consider pausing campaign')
                elif severity == 'high':
                    recommended_actions.append('Schedule optimization review')
                    recommended_actions.append('Implement quick wins')
                else:
                    recommended_actions.append('Monitor closely')
                    recommended_actions.append('Plan optimization sprint')
                
                alert['recommended_actions'] = recommended_actions
            
            # Create alert summary
            alert_summary = {
                'total_alerts': len(alerts),
                'critical': len([a for a in alerts if a.get('severity') == 'critical']),
                'high': len([a for a in alerts if a.get('severity') == 'high']),
                'medium': len([a for a in alerts if a.get('severity') == 'medium'])
            }
            
            return Success({
                'alerts': alerts,
                'alert_summary': alert_summary
            })
            
        except Exception as e:
            logger.error(f"Error monitoring performance thresholds: {e}")
            return Failure(str(e), code="THRESHOLD_MONITORING_ERROR")
    
    def generate_optimization_recommendations(self, campaign_id: int) -> Result[Dict[str, Any]]:
        """
        Generate comprehensive optimization recommendations.
        
        Args:
            campaign_id: Campaign ID
            
        Returns:
            Result with actionable recommendations
        """
        try:
            # Get multiple data points for comprehensive recommendations
            roi_data = self.roi_repository.calculate_roi(campaign_id)
            cac_data = self.roi_repository.calculate_cac(campaign_id)
            strategies = self.roi_repository.suggest_optimization_strategies(campaign_id)
            
            recommendations = []
            
            # ROI-based recommendations
            roi = roi_data.get('roi', Decimal('0'))
            if roi < Decimal('1'):
                recommendations.append({
                    'category': 'urgent',
                    'action': 'Campaign is not profitable - immediate action required',
                    'priority': 1
                })
            elif roi < self.MIN_ROI_ACCEPTABLE:
                recommendations.append({
                    'category': 'improvement',
                    'action': 'Optimize to reach minimum ROI threshold',
                    'priority': 2
                })
            
            # CAC-based recommendations
            cac = cac_data.get('cac', Decimal('0'))
            if cac > self.INDUSTRY_BENCHMARK_CAC:
                recommendations.append({
                    'category': 'cost',
                    'action': 'Reduce customer acquisition costs through better targeting',
                    'priority': 2
                })
            
            # Strategy-based recommendations
            for strategy in strategies.get('optimization_strategies', [])[:3]:  # Top 3 strategies
                recommendations.append({
                    'category': 'optimization',
                    'action': strategy.get('strategy', 'Optimize campaign'),
                    'priority': 3
                })
            
            return Success({
                'campaign_id': campaign_id,
                'current_metrics': {
                    'roi': roi,
                    'cac': cac
                },
                'recommendations': recommendations,
                'expected_outcome': 'Following these recommendations could improve ROI by 20-50%'
            })
            
        except Exception as e:
            logger.error(f"Error generating optimization recommendations: {e}")
            return Failure(str(e), code="RECOMMENDATION_GENERATION_ERROR")
    
    # ===== Dashboard and Reporting =====
    
    def generate_comprehensive_roi_dashboard(self, campaign_id: int) -> Result[Dict[str, Any]]:
        """
        Generate comprehensive ROI dashboard data.
        
        Args:
            campaign_id: Campaign ID
            
        Returns:
            Result with dashboard data
        """
        try:
            # Gather all metrics
            roi_metrics = {}
            performance_indicators = {}
            trend_analysis = {}
            optimization_recommendations = []
            
            # ROI metrics
            roas_result = self.roi_repository.calculate_roas(campaign_id)
            if roas_result:
                roi_metrics['roas'] = roas_result.get('roas', Decimal('0'))
            
            ltv_cac_result = self.roi_repository.calculate_ltv_cac_ratio(campaign_id)
            if ltv_cac_result:
                roi_metrics['ltv_cac_ratio'] = ltv_cac_result.get('ltv_cac_ratio', Decimal('0'))
            
            payback_result = self.roi_repository.calculate_payback_period(campaign_id)
            if payback_result:
                roi_metrics['payback_months'] = payback_result.get('payback_months')
            
            # Performance indicators
            conversion_result = self.conversion_repository.calculate_conversion_rate_for_campaign(campaign_id)
            if conversion_result:
                performance_indicators['conversion_rate'] = conversion_result.get('conversion_rate', 0)
            
            # Trend analysis
            roi_trends = self.roi_repository.get_cac_trends(campaign_id, period_days=30)
            if roi_trends:
                trend_analysis['recent_trends'] = roi_trends
            
            # Optimization recommendations
            opt_result = self.generate_optimization_recommendations(campaign_id)
            if opt_result.is_success:
                optimization_recommendations = opt_result.data.get('recommendations', [])
            
            # Calculate overall health score
            health_score = self._calculate_campaign_health_score(roi_metrics, performance_indicators)
            
            return Success({
                'roi_metrics': roi_metrics,
                'performance_indicators': performance_indicators,
                'trend_analysis': trend_analysis,
                'optimization_recommendations': optimization_recommendations,
                'overall_health_score': health_score
            })
            
        except Exception as e:
            logger.error(f"Error generating ROI dashboard: {e}")
            return Failure(str(e), code="DASHBOARD_GENERATION_ERROR")
    
    def generate_roi_dashboard(self, dashboard_params: Dict[str, Any]) -> Result[Dict[str, Any]]:
        """
        Generate ROI dashboard with specified parameters.
        
        Args:
            dashboard_params: Dashboard configuration parameters
            
        Returns:
            Result with dashboard data
        """
        try:
            campaign_id = dashboard_params.get('campaign_id')
            if not campaign_id:
                return Failure("Campaign ID required for dashboard", code="MISSING_CAMPAIGN_ID")
            
            # Use comprehensive dashboard generation
            return self.generate_comprehensive_roi_dashboard(campaign_id)
            
        except Exception as e:
            logger.error(f"Error generating ROI dashboard: {e}")
            return Failure(str(e), code="DASHBOARD_ERROR")
    
    def batch_calculate_roi_metrics(self, campaign_ids: List[int]) -> Result[Dict[str, Any]]:
        """
        Calculate ROI metrics for multiple campaigns in batch.
        
        Args:
            campaign_ids: List of campaign IDs
            
        Returns:
            Result with batch calculation results
        """
        try:
            results = []
            successful = 0
            failed = 0
            
            for campaign_id in campaign_ids:
                try:
                    roas_data = self.roi_repository.calculate_roas(campaign_id)
                    results.append({
                        'campaign_id': campaign_id,
                        'roas': roas_data.get('roas', Decimal('0')),
                        'status': 'success'
                    })
                    successful += 1
                except Exception as e:
                    results.append({
                        'campaign_id': campaign_id,
                        'error': str(e),
                        'status': 'failed'
                    })
                    failed += 1
            
            return Success({
                'results': results,
                'processing_summary': {
                    'total': len(campaign_ids),
                    'successful': successful,
                    'failed': failed
                }
            })
            
        except Exception as e:
            logger.error(f"Error in batch ROI calculation: {e}")
            return Failure(str(e), code="BATCH_CALCULATION_ERROR")
    
    def export_roi_data(self, campaign_id: int, export_format: str) -> Result[Dict[str, Any]]:
        """
        Export ROI data in specified format.
        
        Args:
            campaign_id: Campaign ID
            export_format: Format for export (csv, json, etc.)
            
        Returns:
            Result with export data
        """
        try:
            # Gather all ROI data
            roi_data = self.roi_repository.calculate_roi(campaign_id)
            cac_data = self.roi_repository.calculate_cac(campaign_id)
            roas_data = self.roi_repository.calculate_roas(campaign_id)
            
            # Format data for export
            export_data = [
                {'metric': 'ROI', 'value': str(roi_data.get('roi', '0')), 'period': utc_now().strftime('%Y-%m')},
                {'metric': 'CAC', 'value': str(cac_data.get('cac', '0')), 'period': utc_now().strftime('%Y-%m')},
                {'metric': 'ROAS', 'value': str(roas_data.get('roas', '0')), 'period': utc_now().strftime('%Y-%m')}
            ]
            
            # Generate download URL (placeholder - actual implementation would create file)
            download_url = f"/api/roi/export/{campaign_id}/{export_format}"
            
            return Success({
                'campaign_id': campaign_id,
                'export_format': export_format,
                'data': export_data,
                'download_url': download_url
            })
            
        except Exception as e:
            logger.error(f"Error exporting ROI data: {e}")
            return Failure(str(e), code="EXPORT_ERROR")
    
    # ===== Helper Methods =====
    
    def _calculate_model_confidence(self, forecast_data: Dict[str, Any]) -> float:
        """
        Calculate confidence score for predictive models.
        
        Args:
            forecast_data: Forecast data dictionary
            
        Returns:
            Confidence score between 0 and 1
        """
        confidence = 0.5  # Base confidence
        
        # Increase confidence based on data quality indicators
        if forecast_data.get('sample_size', 0) > 100:
            confidence += 0.2
        elif forecast_data.get('sample_size', 0) > 30:
            confidence += 0.1
        
        if forecast_data.get('trend_direction') == 'stable':
            confidence += 0.1
        
        if forecast_data.get('forecast_reliability') == 'high':
            confidence += 0.2
        
        return min(1.0, confidence)
    
    def _calculate_campaign_health_score(self, roi_metrics: Dict[str, Any], 
                                        performance_indicators: Dict[str, Any]) -> int:
        """
        Calculate overall health score for a campaign.
        
        Args:
            roi_metrics: ROI-related metrics
            performance_indicators: Performance indicators
            
        Returns:
            Health score from 0 to 100
        """
        score = 50  # Base score
        
        # ROI contribution
        roas = roi_metrics.get('roas', Decimal('0'))
        if roas >= Decimal('5'):
            score += 20
        elif roas >= Decimal('3'):
            score += 10
        
        # LTV:CAC ratio contribution
        ltv_cac = roi_metrics.get('ltv_cac_ratio', Decimal('0'))
        if ltv_cac >= Decimal('3'):
            score += 15
        elif ltv_cac >= Decimal('2'):
            score += 8
        
        # Conversion rate contribution
        conversion_rate = performance_indicators.get('conversion_rate', 0)
        if conversion_rate >= 0.05:
            score += 15
        elif conversion_rate >= 0.02:
            score += 8
        
        return min(100, max(0, score))