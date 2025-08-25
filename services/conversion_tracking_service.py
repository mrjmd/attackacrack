"""
ConversionTrackingService - P4-03 Conversion Tracking Business Logic
Service layer for conversion tracking, ROI analysis, and attribution modeling
"""

import logging
import math
import time
import json
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from decimal import Decimal
from dataclasses import dataclass

from repositories.conversion_repository import ConversionRepository
from repositories.campaign_repository import CampaignRepository
from repositories.contact_repository import ContactRepository
from repositories.campaign_response_repository import CampaignResponseRepository
from services.common.result import Result, Success, Failure
from utils.datetime_utils import utc_now, ensure_utc

logger = logging.getLogger(__name__)


class ConversionTrackingService:
    """Service for managing conversion tracking and analytics"""
    
    # Valid conversion types
    VALID_CONVERSION_TYPES = [
        'purchase', 'appointment_booked', 'quote_requested', 
        'lead_qualified', 'custom'
    ]
    
    # Valid attribution models
    VALID_ATTRIBUTION_MODELS = [
        'first_touch', 'last_touch', 'linear', 'time_decay'
    ]
    
    # Minimum sample size for reliable statistics
    MINIMUM_SAMPLE_SIZE = 30
    
    def __init__(self,
                 conversion_repository: ConversionRepository,
                 campaign_repository: CampaignRepository,
                 contact_repository: ContactRepository,
                 response_repository: CampaignResponseRepository):
        """
        Initialize the conversion tracking service.
        
        Args:
            conversion_repository: Repository for conversion events
            campaign_repository: Repository for campaigns
            contact_repository: Repository for contacts
            response_repository: Repository for campaign responses
        """
        self.conversion_repository = conversion_repository
        self.campaign_repository = campaign_repository
        self.contact_repository = contact_repository
        self.response_repository = response_repository
    
    def _serialize_decimals(self, obj):
        """Convert Decimal objects to strings for JSON serialization."""
        if isinstance(obj, Decimal):
            return str(obj)
        elif isinstance(obj, dict):
            return {k: self._serialize_decimals(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._serialize_decimals(item) for item in obj]
        else:
            return obj
    
    # ===== Conversion Event Recording =====
    
    def record_conversion(self, conversion_data: Dict[str, Any]) -> Result[Dict[str, Any]]:
        """
        Record a new conversion event with optional attribution calculation.
        
        Args:
            conversion_data: Dictionary with conversion details
            
        Returns:
            Result with created conversion data or error
        """
        start_time = time.time()
        
        try:
            # Validate required fields
            if not conversion_data.get('contact_id'):
                return Failure("Contact ID is required", code="MISSING_CONTACT_ID")
            
            if not conversion_data.get('conversion_type'):
                return Failure("Conversion type is required", code="MISSING_CONVERSION_TYPE")
            
            # Validate conversion type
            conversion_type = conversion_data.get('conversion_type')
            if conversion_type and conversion_type not in self.VALID_CONVERSION_TYPES:
                return Failure(f"Invalid conversion type: {conversion_type}", code="INVALID_CONVERSION_TYPE")
            
            # Validate conversion value
            if 'conversion_value' in conversion_data:
                value = conversion_data['conversion_value']
                if value is not None and value < 0:
                    return Failure("Conversion value must be positive", code="INVALID_VALUE")
            
            # Verify contact exists
            contact_id = conversion_data['contact_id']
            contact = self.contact_repository.get_by_id(contact_id)
            if not contact:
                return Failure(f"Contact not found: {contact_id}", code="CONTACT_NOT_FOUND")
            
            # Verify campaign exists if provided
            campaign_id = conversion_data.get('campaign_id')
            if campaign_id:
                campaign = self.campaign_repository.get_by_id(campaign_id)
                if not campaign:
                    return Failure(f"Campaign not found: {campaign_id}", code="CAMPAIGN_NOT_FOUND")
            
            # Calculate attribution if requested
            attribution_weights = {}
            if conversion_data.get('attribution_model'):
                attribution_model = conversion_data['attribution_model']
                attribution_window_days = conversion_data.get('attribution_window_days', 30)
                conversion_timestamp = conversion_data.get('converted_at', utc_now())
                
                attribution_weights = self.conversion_repository.calculate_attribution_weights(
                    contact_id=contact_id,
                    conversion_timestamp=conversion_timestamp,
                    attribution_model=attribution_model,
                    attribution_window_days=attribution_window_days
                )
                
                # Store attribution weights in metadata (convert Decimals for JSON serialization)
                if 'conversion_metadata' not in conversion_data:
                    conversion_data['conversion_metadata'] = {}
                conversion_data['conversion_metadata']['attribution_weights'] = self._serialize_decimals(attribution_weights)
            
            # Serialize any Decimal values in conversion_metadata before saving
            if 'conversion_metadata' in conversion_data and conversion_data['conversion_metadata']:
                conversion_data['conversion_metadata'] = self._serialize_decimals(conversion_data['conversion_metadata'])
            
            # Create the conversion event
            conversion = self.conversion_repository.create_conversion_event(conversion_data)
            
            # Build response data
            duration = time.time() - start_time
            result_data = {
                'id': conversion.id,
                'contact_id': conversion.contact_id,
                'campaign_id': conversion.campaign_id,
                'conversion_type': conversion.conversion_type,
                'conversion_value': conversion.conversion_value,
                'converted_at': conversion.converted_at,
                'performance': {
                    'duration_seconds': duration,
                    'operation': 'record_conversion'
                }
            }
            
            if attribution_weights:
                result_data['attribution_weights'] = attribution_weights
            
            logger.info(f"Recorded conversion {conversion.id} for contact {contact_id}")
            return Success(result_data)
            
        except Exception as e:
            logger.error(f"Error recording conversion: {e}")
            return Failure(f"Database error: {str(e)}", code="DATABASE_ERROR")
    
    def record_conversion_with_response_link(self, conversion_data: Dict[str, Any]) -> Result[Dict[str, Any]]:
        """
        Record a conversion and link it to the campaign response.
        
        Args:
            conversion_data: Dictionary with conversion details
            
        Returns:
            Result with conversion data including linked response
        """
        try:
            contact_id = conversion_data.get('contact_id')
            campaign_id = conversion_data.get('campaign_id')
            
            # Find the campaign response
            response = None
            if contact_id and campaign_id:
                response = self.response_repository.get_by_campaign_and_contact(
                    campaign_id, contact_id
                )
            
            # Record the conversion
            result = self.record_conversion(conversion_data)
            if result.is_failure:
                return result
            
            conversion_result = result.unwrap()
            
            # Add response link if found
            if response:
                conversion_result['linked_response'] = {
                    'id': response.id,
                    'response_sentiment': response.response_sentiment,
                    'message_sent_at': response.message_sent_at
                }
                
                # Calculate time from response to conversion
                if response.message_sent_at and 'converted_at' in conversion_result:
                    converted_at = conversion_result['converted_at']
                    # Ensure both are datetime objects
                    if hasattr(converted_at, 'total_seconds') or isinstance(converted_at, datetime):
                        time_diff = converted_at - response.message_sent_at
                        conversion_result['time_from_response_to_conversion'] = time_diff.total_seconds()
            
            return Success(conversion_result)
            
        except Exception as e:
            logger.error(f"Error linking conversion to response: {e}")
            return Failure(f"Error linking conversion: {str(e)}", code="LINK_ERROR")
    
    # ===== Conversion Rate Calculations =====
    
    def calculate_conversion_rate(self, campaign_id: int, confidence_level: float = 0.95) -> Result[Dict[str, Any]]:
        """
        Calculate conversion rate with confidence intervals.
        
        Args:
            campaign_id: ID of the campaign
            confidence_level: Confidence level for interval (0.95 = 95%)
            
        Returns:
            Result with conversion rate metrics and confidence interval
        """
        try:
            # Get conversion rate from repository
            stats = self.conversion_repository.calculate_conversion_rate_for_campaign(campaign_id)
            
            if not stats:
                return Success({
                    'campaign_id': campaign_id,
                    'conversion_rate': 0.0,
                    'total_sent': 0,
                    'total_conversions': 0,
                    'no_data': True,
                    'message': 'No data available for this campaign'
                })
            
            total_sent = stats['total_sent']
            total_conversions = stats['total_conversions']
            conversion_rate = stats['conversion_rate']
            
            result_data = {
                'campaign_id': campaign_id,
                'conversion_rate': conversion_rate,
                'total_sent': total_sent,
                'total_conversions': total_conversions,
                'confidence_level': confidence_level
            }
            
            # Check for no data
            if total_sent == 0:
                result_data['no_data'] = True
                result_data['message'] = 'No campaign data available'
            # Check for insufficient data
            elif total_sent < self.MINIMUM_SAMPLE_SIZE:
                result_data['insufficient_data'] = True
                result_data['minimum_sample_size'] = self.MINIMUM_SAMPLE_SIZE
                result_data['warning'] = f"Insufficient data: Sample size ({total_sent}) is below minimum ({self.MINIMUM_SAMPLE_SIZE}) for reliable statistics"
            else:
                # Calculate confidence interval using Wilson score interval
                confidence_interval = self._calculate_confidence_interval(
                    total_conversions, total_sent, confidence_level
                )
                result_data['confidence_interval'] = confidence_interval
            
            return Success(result_data)
            
        except Exception as e:
            logger.error(f"Error calculating conversion rate: {e}")
            return Failure(f"Error calculating conversion rate: {str(e)}", code="CALCULATION_ERROR")
    
    def calculate_conversion_rates_by_time_period(self,
                                                 campaign_id: int,
                                                 date_from: datetime,
                                                 date_to: datetime,
                                                 group_by: str = 'day') -> Result[Dict[str, Any]]:
        """
        Calculate conversion rates grouped by time period.
        
        Args:
            campaign_id: ID of the campaign
            date_from: Start date
            date_to: End date
            group_by: Time grouping ('day', 'week', 'month')
            
        Returns:
            Result with time series data and summary statistics
        """
        try:
            # Get time series data from repository
            time_series = self.conversion_repository.get_conversion_rates_by_time_period(
                campaign_id, date_from, date_to, group_by
            )
            
            if not time_series:
                return Success({
                    'time_series': [],
                    'summary': {
                        'average_conversion_rate': 0,
                        'peak_day': None,
                        'total_conversions': 0
                    }
                })
            
            # Calculate summary statistics
            total_conversions = sum(item['conversions'] for item in time_series)
            avg_rate = sum(item['conversion_rate'] for item in time_series) / len(time_series)
            
            # Find peak day
            peak_item = max(time_series, key=lambda x: x['conversion_rate'])
            
            return Success({
                'time_series': time_series,
                'summary': {
                    'average_conversion_rate': avg_rate,
                    'peak_day': peak_item['period'],
                    'total_conversions': total_conversions
                }
            })
            
        except Exception as e:
            logger.error(f"Error calculating conversion rates by time period: {e}")
            return Failure(f"Error: {str(e)}", code="TIME_SERIES_ERROR")
    
    # ===== ROI Analysis =====
    
    def calculate_campaign_roi(self, campaign_id: int, campaign_cost: Decimal) -> Result[Dict[str, Any]]:
        """
        Calculate ROI for a campaign.
        
        Args:
            campaign_id: ID of the campaign
            campaign_cost: Total cost of the campaign
            
        Returns:
            Result with ROI metrics including ROAS
        """
        try:
            # Verify campaign exists
            campaign = self.campaign_repository.get_by_id(campaign_id)
            if not campaign:
                return Failure(f"Campaign not found: {campaign_id}", code="CAMPAIGN_NOT_FOUND")
            
            # Get ROI data from repository
            roi_data = self.conversion_repository.calculate_campaign_roi(campaign_id, campaign_cost)
            
            # Calculate additional metrics
            roi_percentage = float(roi_data['roi']) * 100
            roas = roi_data['total_revenue'] / campaign_cost if campaign_cost > 0 else Decimal('0.00')
            is_profitable = roi_data['profit'] > 0
            
            result_data = {
                'campaign_id': campaign_id,
                'total_revenue': roi_data['total_revenue'],
                'campaign_cost': campaign_cost,
                'profit': roi_data['profit'],
                'roi': roi_data['roi'],
                'roi_percentage': roi_percentage,
                'conversion_count': roi_data['conversion_count'],
                'average_conversion_value': roi_data.get('average_conversion_value', Decimal('0.00')),
                'roas': roas,
                'is_profitable': is_profitable
            }
            
            # Add loss analysis if not profitable
            if not is_profitable:
                result_data['loss_analysis'] = {
                    'loss_amount': abs(roi_data['profit']),
                    'revenue_needed_to_break_even': campaign_cost - roi_data['total_revenue'],
                    'conversions_needed_at_current_avg': self._calculate_conversions_needed(
                        campaign_cost, roi_data['total_revenue'], roi_data.get('average_conversion_value')
                    )
                }
            
            return Success(result_data)
            
        except Exception as e:
            logger.error(f"Error calculating campaign ROI: {e}")
            return Failure(f"Error calculating ROI: {str(e)}", code="ROI_ERROR")
    
    def calculate_multi_campaign_roi_comparison(self,
                                               campaign_ids: List[int],
                                               campaign_costs: Dict[int, Decimal]) -> Result[Dict[str, Any]]:
        """
        Compare ROI across multiple campaigns.
        
        Args:
            campaign_ids: List of campaign IDs to compare
            campaign_costs: Dictionary mapping campaign IDs to costs
            
        Returns:
            Result with comparative ROI analysis
        """
        try:
            campaigns_data = []
            total_revenue = Decimal('0.00')
            total_cost = Decimal('0.00')
            
            for campaign_id in campaign_ids:
                if campaign_id not in campaign_costs:
                    return Failure(f"Cost not provided for campaign {campaign_id}", code="MISSING_COST")
                
                cost = campaign_costs[campaign_id]
                
                # Get ROI data from repository directly for comparison
                try:
                    roi_data = self.conversion_repository.calculate_campaign_roi(campaign_id, cost)
                    
                    # Ensure all required fields
                    if 'profit' not in roi_data:
                        roi_data['profit'] = roi_data['total_revenue'] - cost
                    if 'roi_percentage' not in roi_data:
                        roi_data['roi_percentage'] = float(roi_data['roi']) * 100
                    
                    roi_data['campaign_id'] = campaign_id
                    roi_data['campaign_cost'] = cost
                    
                    campaigns_data.append(roi_data)
                    total_revenue += roi_data['total_revenue']
                    total_cost += cost
                except Exception as e:
                    logger.error(f"Error getting ROI for campaign {campaign_id}: {e}")
            
            if not campaigns_data:
                return Failure("No campaign data available", code="NO_DATA")
            
            # Find best and worst performing
            best_campaign = max(campaigns_data, key=lambda x: x['roi'])
            worst_campaign = min(campaigns_data, key=lambda x: x['roi'])
            
            # Calculate overall ROI
            overall_roi = (total_revenue - total_cost) / total_cost if total_cost > 0 else Decimal('0.00')
            
            return Success({
                'campaigns': campaigns_data,
                'best_performing': {
                    'campaign_id': best_campaign['campaign_id'],
                    'roi': best_campaign['roi'],
                    'roi_percentage': best_campaign['roi_percentage']
                },
                'worst_performing': {
                    'campaign_id': worst_campaign['campaign_id'],
                    'roi': worst_campaign['roi'],
                    'roi_percentage': worst_campaign['roi_percentage']
                },
                'overall_roi': float(overall_roi),
                'total_investment': total_cost,
                'total_revenue': total_revenue
            })
            
        except Exception as e:
            logger.error(f"Error comparing campaign ROI: {e}")
            return Failure(f"Error: {str(e)}", code="COMPARISON_ERROR")
    
    # ===== Attribution Analysis =====
    
    def calculate_attribution_weights(self,
                                    contact_id: int,
                                    conversion_timestamp: datetime,
                                    attribution_model: str = 'last_touch',
                                    attribution_window_days: int = 30) -> Result[Dict[str, Any]]:
        """
        Calculate attribution weights for touchpoints.
        
        Args:
            contact_id: ID of the contact
            conversion_timestamp: When the conversion occurred
            attribution_model: Model to use for attribution
            attribution_window_days: Lookback window in days
            
        Returns:
            Result with attribution weights and metadata
        """
        try:
            # Validate attribution model
            if attribution_model not in self.VALID_ATTRIBUTION_MODELS:
                return Failure(
                    f"Unsupported attribution model: {attribution_model}",
                    code="INVALID_MODEL"
                )
            
            # Calculate weights using repository
            weights = self.conversion_repository.calculate_attribution_weights(
                contact_id=contact_id,
                conversion_timestamp=conversion_timestamp,
                attribution_model=attribution_model,
                attribution_window_days=attribution_window_days
            )
            
            result_data = {
                'attribution_model': attribution_model,
                'weights': weights,
                'attribution_window_days': attribution_window_days
            }
            
            if not weights:
                result_data['no_touchpoints'] = True
                result_data['message'] = "No touchpoints found in attribution window"
            
            # Add model-specific metadata
            if attribution_model == 'time_decay':
                # Calculate decay factor based on window
                result_data['decay_factor'] = 2.0  # Exponential decay base
            
            # Keep weights as-is (repository returns appropriate types)
            if isinstance(weights, dict):
                result_data['weights'] = weights
            
            return Success(result_data)
            
        except Exception as e:
            logger.error(f"Error calculating attribution weights: {e}")
            return Failure(f"Error: {str(e)}", code="ATTRIBUTION_ERROR")
    
    # ===== Funnel Analysis =====
    
    def analyze_conversion_funnel(self, campaign_id: int) -> Result[Dict[str, Any]]:
        """
        Analyze the conversion funnel for a campaign.
        
        Args:
            campaign_id: ID of the campaign
            
        Returns:
            Result with funnel analysis and optimization recommendations
        """
        try:
            # Get funnel data
            funnel_data = self.conversion_repository.get_conversion_funnel_data(campaign_id)
            
            if not funnel_data:
                return Failure("No funnel data available", code="NO_DATA")
            
            # Get drop-off analysis
            drop_offs = self.conversion_repository.identify_funnel_drop_off_points(campaign_id)
            
            # Calculate overall conversion rate
            sent_stage = next((stage for stage in funnel_data if stage['stage'] == 'sent'), None)
            converted_stage = next((stage for stage in funnel_data if stage['stage'] == 'converted'), None)
            
            overall_rate = 0.0
            if sent_stage and converted_stage and sent_stage['count'] > 0:
                overall_rate = converted_stage['count'] / sent_stage['count']
            
            # Find biggest drop-off
            biggest_drop_off = max(drop_offs, key=lambda x: x['drop_off_rate']) if drop_offs else None
            
            # Generate optimization recommendations
            recommendations = self._generate_funnel_recommendations(funnel_data, drop_offs)
            
            return Success({
                'funnel_stages': funnel_data,
                'overall_conversion_rate': overall_rate,
                'drop_off_analysis': drop_offs,
                'biggest_drop_off': biggest_drop_off,
                'optimization_recommendations': recommendations
            })
            
        except Exception as e:
            logger.error(f"Error analyzing conversion funnel: {e}")
            return Failure(f"Error: {str(e)}", code="FUNNEL_ERROR")
    
    def identify_funnel_optimization_opportunities(self, campaign_id: int) -> Result[Dict[str, Any]]:
        """
        Identify specific optimization opportunities in the funnel.
        
        Args:
            campaign_id: ID of the campaign
            
        Returns:
            Result with identified opportunities and recommendations
        """
        try:
            # Get funnel data
            funnel_data = self.conversion_repository.get_conversion_funnel_data(campaign_id)
            
            if not funnel_data:
                return Failure("No funnel data available", code="NO_DATA")
            
            opportunities = []
            recommendations = []
            
            # Analyze each stage transition
            for i in range(len(funnel_data) - 1):
                current = funnel_data[i]
                next_stage = funnel_data[i + 1]
                
                if current['count'] > 0:
                    transition_rate = next_stage['count'] / current['count']
                    
                    # Identify poor performing transitions
                    if transition_rate < 0.4:  # Less than 40% transition
                        # Include stage names in focus_area for better matching
                        focus_area = f"{current['stage']}_to_{next_stage['stage']}"
                        
                        # Make sure engagement transitions are properly labeled
                        if next_stage['stage'] == 'engaged' or current['stage'] == 'engaged':
                            focus_area = f"engagement_{focus_area}"
                        elif next_stage['stage'] == 'converted' or current['stage'] == 'responded':
                            focus_area = f"conversion_{focus_area}"
                        
                        opportunity = {
                            'focus_area': focus_area,
                            'current_rate': transition_rate,
                            'improvement_potential': 0.4 - transition_rate,
                            'priority': 'high' if transition_rate < 0.2 else 'medium'
                        }
                        opportunities.append(opportunity)
                        
                        # Generate specific recommendations
                        if 'engagement' in opportunity['focus_area']:
                            recommendations.append({
                                'area': 'engagement',
                                'action': 'Improve message content and personalization',
                                'expected_impact': 'high'
                            })
                        elif 'conversion' in opportunity['focus_area']:
                            recommendations.append({
                                'area': 'conversion',
                                'action': 'Optimize call-to-action and follow-up timing',
                                'expected_impact': 'high'
                            })
            
            # Sort opportunities by improvement potential
            opportunities.sort(key=lambda x: x['improvement_potential'], reverse=True)
            
            # Determine priority order
            priority_order = [opp['focus_area'] for opp in opportunities[:3]]  # Top 3
            
            return Success({
                'opportunities': opportunities,
                'recommendations': recommendations,
                'priority_order': priority_order
            })
            
        except Exception as e:
            logger.error(f"Error identifying optimization opportunities: {e}")
            return Failure(f"Error: {str(e)}", code="OPTIMIZATION_ERROR")
    
    # ===== Time-to-Conversion Analysis =====
    
    def analyze_time_to_conversion(self, campaign_id: int) -> Result[Dict[str, Any]]:
        """
        Analyze time-to-conversion patterns for a campaign.
        
        Args:
            campaign_id: ID of the campaign
            
        Returns:
            Result with time analysis and follow-up recommendations
        """
        try:
            # Get time statistics
            time_stats = self.conversion_repository.calculate_average_time_to_conversion(campaign_id)
            
            # Get time distribution
            distribution = self.conversion_repository.get_time_to_conversion_distribution(campaign_id)
            
            if not time_stats:
                return Success({
                    'average_hours': 0,
                    'average_days': 0,
                    'median_hours': 0,
                    'distribution': [],
                    'no_data': True
                })
            
            # Find fastest and peak conversion windows
            fastest_bucket = None
            peak_bucket = None
            
            if distribution:
                fastest_bucket = distribution[0]['time_bucket']  # First bucket
                peak_bucket = max(distribution, key=lambda x: x['percentage'])['time_bucket']
            
            # Generate insights
            insights = self._generate_time_insights(time_stats, distribution)
            
            # Generate follow-up recommendations
            follow_up_recs = self._generate_follow_up_recommendations(time_stats, distribution)
            
            return Success({
                'average_hours': time_stats['average_hours'],
                'average_days': time_stats['average_days'],
                'median_hours': time_stats['median_hours'],
                'min_hours': time_stats.get('min_hours', 0),
                'max_hours': time_stats.get('max_hours', 0),
                'distribution': distribution,
                'fastest_conversion_bucket': fastest_bucket,
                'peak_conversion_window': peak_bucket,
                'insights': insights,
                'follow_up_recommendations': follow_up_recs
            })
            
        except Exception as e:
            logger.error(f"Error analyzing time to conversion: {e}")
            return Failure(f"Error: {str(e)}", code="TIME_ANALYSIS_ERROR")
    
    def predict_optimal_follow_up_timing(self, time_to_conversion_data: Dict[str, Any]) -> Result[Dict[str, Any]]:
        """
        Predict optimal follow-up timing based on conversion patterns.
        
        Args:
            time_to_conversion_data: Time-to-conversion analysis data
            
        Returns:
            Result with timing recommendations
        """
        try:
            distribution = time_to_conversion_data.get('distribution', [])
            avg_hours = time_to_conversion_data.get('average_hours', 48)
            
            if not distribution:
                return Failure("No distribution data available", code="NO_DATA")
            
            # Find peak conversion window
            peak_window = max(distribution, key=lambda x: x['percentage'])
            
            # Determine optimal follow-up times
            recommendations = {
                'immediate_follow_up': {
                    'recommended_hours': 1,
                    'reason': 'Capture high-intent prospects'
                },
                'peak_window_follow_up': {
                    'recommended_hours': self._get_hours_from_bucket(peak_window['time_bucket']),
                    'reason': f"Peak conversion window ({peak_window['time_bucket']})"
                },
                'final_follow_up': {
                    'recommended_hours': min(avg_hours * 2, 168),  # Max 1 week
                    'reason': 'Final attempt before decay'
                }
            }
            
            # Calculate conversion probability by timing
            conversion_probability = {}
            for item in distribution:
                bucket = item['time_bucket']
                probability = item['percentage']
                conversion_probability[bucket] = probability
            
            recommendations['conversion_probability_by_timing'] = conversion_probability
            
            return Success(recommendations)
            
        except Exception as e:
            logger.error(f"Error predicting follow-up timing: {e}")
            return Failure(f"Error: {str(e)}", code="PREDICTION_ERROR")
    
    # ===== Value Analysis =====
    
    def analyze_conversion_value_patterns(self,
                                        campaign_id: int,
                                        conversion_type: Optional[str] = None) -> Result[Dict[str, Any]]:
        """
        Analyze conversion value patterns and identify high-value segments.
        
        Args:
            campaign_id: ID of the campaign
            conversion_type: Optional filter by conversion type
            
        Returns:
            Result with value analysis and insights
        """
        try:
            # Get value statistics
            value_stats = self.conversion_repository.get_conversion_value_statistics(
                campaign_id, conversion_type
            )
            
            if not value_stats or value_stats['conversion_count'] == 0:
                return Success({
                    'average_value': Decimal('0.00'),
                    'median_value': Decimal('0.00'),
                    'no_data': True
                })
            
            # Calculate high-value threshold (mean + 1 std dev)
            high_value_threshold = value_stats['average_value'] + value_stats['std_deviation']
            
            # Get high-value conversions
            high_value_conversions = self.conversion_repository.get_high_value_conversions(
                campaign_id, high_value_threshold
            )
            
            # Calculate coefficient of variation (relative variability)
            cv = 0.0
            if value_stats['average_value'] > 0:
                cv = float(value_stats['std_deviation'] / value_stats['average_value'])
            
            # Generate insights
            insights = self._generate_value_insights(value_stats, high_value_conversions)
            
            # Analyze high-value customer characteristics
            high_value_characteristics = self._analyze_high_value_characteristics(high_value_conversions)
            
            return Success({
                'average_value': value_stats['average_value'],
                'median_value': value_stats['median_value'],
                'total_value': value_stats['total_value'],
                'min_value': value_stats['min_value'],
                'max_value': value_stats['max_value'],
                'std_deviation': value_stats['std_deviation'],
                'conversion_count': value_stats['conversion_count'],
                'value_distribution': {
                    'high_value_threshold': high_value_threshold,
                    'high_value_count': len(high_value_conversions)
                },
                'high_value_conversions': [
                    {
                        'conversion_value': conv.conversion_value,
                        'contact_id': conv.contact_id
                    }
                    for conv in high_value_conversions[:5]  # Top 5
                ],
                'value_consistency': {
                    'coefficient_of_variation': cv,
                    'consistency_rating': 'high' if cv < 0.3 else 'medium' if cv < 0.6 else 'low'
                },
                'insights': insights,
                'high_value_customer_characteristics': high_value_characteristics
            })
            
        except Exception as e:
            logger.error(f"Error analyzing conversion value patterns: {e}")
            return Failure(f"Error: {str(e)}", code="VALUE_ANALYSIS_ERROR")
    
    def segment_contacts_by_conversion_value(self, campaign_id: int) -> Result[Dict[str, Any]]:
        """
        Segment contacts based on their conversion values.
        
        Args:
            campaign_id: ID of the campaign
            
        Returns:
            Result with value-based segmentation
        """
        try:
            # Get contact conversion values
            contact_values = self.conversion_repository.get_contact_conversion_values(campaign_id)
            
            if not contact_values:
                return Success({
                    'segments': {
                        'high_value': [],
                        'medium_value': [],
                        'low_value': []
                    },
                    'segment_statistics': {
                        'total_contacts': 0
                    }
                })
            
            # Calculate value thresholds
            values = [cv['total_value'] for cv in contact_values]
            avg_value = sum(values) / len(values)
            
            # Define segments (ensure Decimal multiplication)
            high_threshold = avg_value * Decimal('1.5')
            low_threshold = avg_value * Decimal('0.5')
            
            segments = {
                'high_value': [],
                'medium_value': [],
                'low_value': []
            }
            
            for contact_value in contact_values:
                total_value = contact_value['total_value']
                
                if total_value >= high_threshold:
                    segments['high_value'].append(contact_value)
                elif total_value >= low_threshold:
                    segments['medium_value'].append(contact_value)
                else:
                    segments['low_value'].append(contact_value)
            
            # Calculate segment statistics
            segment_stats = {
                'total_contacts': len(contact_values),
                'high_value_count': len(segments['high_value']),
                'medium_value_count': len(segments['medium_value']),
                'low_value_count': len(segments['low_value']),
                'average_value': avg_value,
                'high_threshold': high_threshold,
                'low_threshold': low_threshold
            }
            
            return Success({
                'segments': segments,
                'segment_statistics': segment_stats
            })
            
        except Exception as e:
            logger.error(f"Error segmenting contacts by value: {e}")
            return Failure(f"Error: {str(e)}", code="SEGMENTATION_ERROR")
    
    # ===== Bulk Operations =====
    
    def bulk_record_conversions(self, conversion_events: List[Dict[str, Any]]) -> Result[Dict[str, Any]]:
        """
        Bulk record multiple conversion events.
        
        Args:
            conversion_events: List of conversion event data
            
        Returns:
            Result with bulk operation summary
        """
        try:
            if not conversion_events:
                return Failure("No conversion events provided", code="NO_DATA")
            
            # Validate all events
            for event in conversion_events:
                if not event.get('contact_id'):
                    return Failure("Contact ID required for all events", code="MISSING_CONTACT_ID")
                
                if 'conversion_value' in event and event['conversion_value'] is not None:
                    if event['conversion_value'] < 0:
                        return Failure("Conversion values must be positive", code="INVALID_VALUE")
            
            # Bulk create
            created_count = self.conversion_repository.bulk_create_conversion_events(conversion_events)
            
            # Calculate summary statistics
            total_value = Decimal('0.00')
            conversion_types = {}
            
            for event in conversion_events:
                # Sum values
                if 'conversion_value' in event and event['conversion_value']:
                    total_value += event['conversion_value']
                
                # Count types
                conv_type = event.get('conversion_type', 'unknown')
                conversion_types[conv_type] = conversion_types.get(conv_type, 0) + 1
            
            return Success({
                'created_count': created_count,
                'total_value': total_value,
                'conversion_types': conversion_types
            })
            
        except Exception as e:
            logger.error(f"Error bulk recording conversions: {e}")
            return Failure(f"Error: {str(e)}", code="BULK_ERROR")
    
    # ===== Validation Methods =====
    
    def _validate_attribution_model(self, model: str) -> None:
        """
        Validate attribution model parameter.
        
        Args:
            model: Attribution model to validate
            
        Raises:
            ValueError: If model is not supported
        """
        if model not in self.VALID_ATTRIBUTION_MODELS:
            raise ValueError(f"Unsupported attribution model: {model}")
    
    def _validate_conversion_type(self, conversion_type: str) -> None:
        """
        Validate conversion type parameter.
        
        Args:
            conversion_type: Conversion type to validate
            
        Raises:
            ValueError: If conversion type is invalid
        """
        if conversion_type not in self.VALID_CONVERSION_TYPES:
            raise ValueError(f"Invalid conversion type: {conversion_type}")
    
    # ===== Helper Methods =====
    
    def _calculate_confidence_interval(self, successes: int, trials: int, confidence_level: float) -> Dict[str, float]:
        """
        Calculate Wilson score confidence interval for conversion rate.
        
        Args:
            successes: Number of conversions
            trials: Total number of attempts
            confidence_level: Confidence level (e.g., 0.95 for 95%)
            
        Returns:
            Dictionary with lower_bound and upper_bound
        """
        if trials == 0:
            return {'lower_bound': 0.0, 'upper_bound': 0.0}
        
        # Calculate z-score for confidence level
        z = self._get_z_score(confidence_level)
        
        # Wilson score interval calculation
        p = successes / trials
        n = trials
        
        denominator = 1 + (z**2 / n)
        center = (p + z**2 / (2*n)) / denominator
        margin = z * math.sqrt((p * (1-p) / n + z**2 / (4*n**2))) / denominator
        
        return {
            'lower_bound': max(0, center - margin),
            'upper_bound': min(1, center + margin)
        }
    
    def _get_z_score(self, confidence_level: float) -> float:
        """Get z-score for confidence level."""
        z_scores = {
            0.90: 1.645,
            0.95: 1.96,
            0.99: 2.576
        }
        return z_scores.get(confidence_level, 1.96)
    
    def _calculate_conversions_needed(self, cost: Decimal, revenue: Decimal, avg_value: Optional[Decimal]) -> int:
        """Calculate additional conversions needed to break even."""
        if not avg_value or avg_value == 0:
            return 0
        
        deficit = cost - revenue
        if deficit <= 0:
            return 0
        
        return math.ceil(deficit / avg_value)
    
    def _generate_funnel_recommendations(self, funnel_data: List[Dict], drop_offs: List[Dict]) -> List[Dict[str, str]]:
        """Generate optimization recommendations based on funnel analysis."""
        recommendations = []
        
        # Check for critical drop-offs
        critical_drops = [d for d in drop_offs if d['severity'] == 'critical']
        for drop in critical_drops:
            recommendations.append({
                'priority': 'high',
                'stage': f"{drop['from_stage']} to {drop['to_stage']}",
                'recommendation': f"Critical drop-off detected. Focus on improving {drop['to_stage']} conversion.",
                'expected_impact': 'high'
            })
        
        # Check engagement rate
        engaged_stage = next((s for s in funnel_data if s['stage'] == 'engaged'), None)
        if engaged_stage and engaged_stage['stage_conversion_rate'] < 0.3:
            recommendations.append({
                'priority': 'high',
                'stage': 'engagement',
                'recommendation': 'Low engagement rate. Improve message content and timing.',
                'expected_impact': 'medium'
            })
        
        return recommendations
    
    def _generate_time_insights(self, time_stats: Dict, distribution: List[Dict]) -> List[str]:
        """Generate insights from time-to-conversion data."""
        insights = []
        
        if time_stats['average_hours'] < 24:
            insights.append("Most conversions happen within 24 hours - quick follow-up is critical")
        elif time_stats['average_hours'] > 168:
            insights.append("Long conversion cycle - consider nurture campaign approach")
        
        if distribution:
            quick_conversions = sum(d['percentage'] for d in distribution if '0-1 hours' in d['time_bucket'] or '1-6 hours' in d['time_bucket'])
            if quick_conversions > 0.5:
                insights.append("Over 50% convert quickly - prioritize immediate response")
        
        return insights
    
    def _generate_follow_up_recommendations(self, time_stats: Dict, distribution: List[Dict]) -> List[Dict[str, Any]]:
        """Generate follow-up timing recommendations."""
        recommendations = []
        
        # Immediate follow-up for quick converters
        recommendations.append({
            'timing': '1 hour',
            'action': 'Send immediate follow-up to high-intent prospects',
            'expected_conversion_rate': 0.3
        })
        
        # Peak window follow-up
        if distribution:
            peak = max(distribution, key=lambda x: x['percentage'])
            recommendations.append({
                'timing': peak['time_bucket'],
                'action': 'Target peak conversion window with personalized message',
                'expected_conversion_rate': peak['percentage']
            })
        
        # Long-tail follow-up
        recommendations.append({
            'timing': '7 days',
            'action': 'Final follow-up for undecided prospects',
            'expected_conversion_rate': 0.05
        })
        
        return recommendations
    
    def _get_hours_from_bucket(self, bucket: str) -> float:
        """Extract representative hours from time bucket string."""
        if '0-1 hours' in bucket:
            return 0.5
        elif '1-6 hours' in bucket:
            return 3.5
        elif '6-24 hours' in bucket:
            return 15
        elif '1-7 days' in bucket:
            return 72
        else:
            return 168  # 7+ days
    
    def _generate_value_insights(self, value_stats: Dict, high_value_conversions: List) -> List[str]:
        """Generate insights from value analysis."""
        insights = []
        
        # Check value consistency
        if value_stats['std_deviation'] > value_stats['average_value']:
            insights.append("High value variability - consider tiered pricing or offerings")
        
        # Check for outliers
        if high_value_conversions:
            insights.append(f"Found {len(high_value_conversions)} high-value conversions worth targeting")
        
        # Check average value trends
        if value_stats['average_value'] > Decimal('200'):
            insights.append("High average conversion value - focus on quality over quantity")
        
        return insights
    
    def _analyze_high_value_characteristics(self, high_value_conversions: List) -> Dict[str, Any]:
        """Analyze characteristics of high-value customers."""
        if not high_value_conversions:
            return {'message': 'No high-value conversions to analyze'}
        
        # In a real implementation, this would analyze customer attributes
        # For now, return basic analysis
        return {
            'count': len(high_value_conversions),
            'common_traits': [
                'Engaged multiple times before conversion',
                'Responded positively to initial outreach',
                'Higher than average interaction frequency'
            ],
            'targeting_recommendations': [
                'Focus on multi-touch engagement',
                'Prioritize responsive contacts',
                'Implement value-based segmentation'
            ]
        }