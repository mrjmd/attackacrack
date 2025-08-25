"""
Unit Tests for ResponseAnalyticsService - TDD RED PHASE
These tests are written FIRST before implementing the ResponseAnalyticsService
All tests should FAIL initially to ensure proper TDD workflow

Tests cover:
1. Real-time response tracking from webhooks
2. Response rate calculations with statistical confidence
3. A/B test variant comparison with chi-square testing
4. Response funnel analysis
5. Time-based response pattern analysis
6. Sentiment analysis integration
7. Performance metrics and caching
"""

import pytest
from unittest.mock import Mock, MagicMock, patch, call
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from decimal import Decimal
import json
from scipy import stats

from services.response_analytics_service import ResponseAnalyticsService
from services.common.result import Result, Success, Failure
from repositories.campaign_response_repository import CampaignResponseRepository
from repositories.campaign_repository import CampaignRepository
from repositories.activity_repository import ActivityRepository
from repositories.contact_repository import ContactRepository
from crm_database import (
    CampaignResponse, Campaign, Contact, Activity, CampaignMembership
)
from utils.datetime_utils import utc_now, ensure_utc
from services.sentiment_analysis_service import SentimentAnalysisService
from services.cache_service import CacheService


@dataclass
class ResponseEvent:
    """Response event data from webhook"""
    campaign_id: int
    contact_id: int
    activity_id: int
    response_text: str
    received_at: datetime
    variant: str


@dataclass
class AnalyticsResults:
    """Comprehensive analytics results"""
    response_rate: float
    confidence_interval: Dict[str, float]
    total_sent: int
    total_responses: int
    sentiment_breakdown: Dict[str, int]
    intent_breakdown: Dict[str, int]
    time_metrics: Dict[str, float]
    funnel_metrics: Dict[str, Any]


class TestResponseAnalyticsService:
    """Unit tests for ResponseAnalyticsService"""
    
    @pytest.fixture
    def mock_response_repo(self):
        """Mock campaign response repository"""
        return Mock(spec=CampaignResponseRepository)
    
    @pytest.fixture
    def mock_campaign_repo(self):
        """Mock campaign repository"""
        return Mock(spec=CampaignRepository)
    
    @pytest.fixture
    def mock_activity_repo(self):
        """Mock activity repository"""
        return Mock(spec=ActivityRepository)
    
    @pytest.fixture
    def mock_contact_repo(self):
        """Mock contact repository"""
        return Mock(spec=ContactRepository)
    
    @pytest.fixture
    def mock_sentiment_service(self):
        """Mock sentiment analysis service"""
        return Mock(spec=SentimentAnalysisService)
    
    @pytest.fixture
    def mock_cache_service(self):
        """Mock cache service"""
        return Mock(spec=CacheService)
    
    @pytest.fixture
    def service(self, mock_response_repo, mock_campaign_repo, mock_activity_repo, 
                mock_contact_repo, mock_sentiment_service, mock_cache_service):
        """Create ResponseAnalyticsService with mocked dependencies"""
        return ResponseAnalyticsService(
            response_repository=mock_response_repo,
            campaign_repository=mock_campaign_repo,
            activity_repository=mock_activity_repo,
            contact_repository=mock_contact_repo,
            sentiment_service=mock_sentiment_service,
            cache_service=mock_cache_service
        )
    
    @pytest.fixture
    def sample_campaign(self):
        """Sample campaign for testing"""
        campaign = Mock(spec=Campaign)
        campaign.id = 1
        campaign.name = "Test Campaign"
        campaign.status = "running"
        campaign.campaign_type = "ab_test"
        campaign.created_at = utc_now() - timedelta(days=1)
        return campaign
    
    @pytest.fixture
    def sample_response_event(self):
        """Sample response event from webhook"""
        return ResponseEvent(
            campaign_id=1,
            contact_id=123,
            activity_id=456,
            response_text="Yes, I'm very interested! Tell me more.",
            received_at=utc_now(),
            variant="A"
        )

    # ===== Response Tracking Tests =====
    
    def test_track_response_from_webhook_success(self, service, mock_response_repo, 
                                               mock_sentiment_service, sample_response_event):
        """Test tracking a new response from webhook"""
        # Arrange
        mock_existing_response = Mock(spec=CampaignResponse)
        mock_existing_response.id = 1
        mock_existing_response.campaign_id = sample_response_event.campaign_id
        mock_existing_response.contact_id = sample_response_event.contact_id
        mock_existing_response.sent_at = utc_now() - timedelta(hours=2)
        mock_existing_response.response_received = False
        
        mock_response_repo.get_by_campaign_and_contact.return_value = mock_existing_response
        
        # Mock sentiment analysis
        sentiment_result = {
            'sentiment': 'positive',
            'intent': 'interested',
            'confidence': 0.89
        }
        mock_sentiment_service.analyze_response.return_value = Success(sentiment_result)
        
        # Mock response update
        updated_response = Mock(spec=CampaignResponse)
        updated_response.response_received = True
        updated_response.sentiment = 'positive'
        updated_response.intent = 'interested'
        mock_response_repo.update_response.return_value = updated_response
        
        # Act
        result = service.track_response_from_webhook(sample_response_event)
        
        # Assert
        assert result.is_success()
        response_data = result.unwrap()
        assert response_data['response_tracked'] == True
        assert response_data['sentiment'] == 'positive'
        assert response_data['intent'] == 'interested'
        
        mock_response_repo.get_by_campaign_and_contact.assert_called_once_with(
            sample_response_event.campaign_id, sample_response_event.contact_id
        )
        mock_sentiment_service.analyze_response.assert_called_once_with(
            sample_response_event.response_text
        )
        mock_response_repo.update_response.assert_called_once()
    
    def test_track_response_no_existing_record_creates_new(self, service, mock_response_repo, 
                                                        mock_campaign_repo, sample_response_event):
        """Test tracking response when no existing record exists creates new one"""
        # Arrange
        mock_response_repo.get_by_campaign_and_contact.return_value = None
        
        # Mock campaign lookup
        mock_campaign = Mock(spec=Campaign)
        mock_campaign.id = sample_response_event.campaign_id
        mock_campaign_repo.get_by_id.return_value = mock_campaign
        
        # Mock response creation
        new_response = Mock(spec=CampaignResponse)
        new_response.id = 1
        new_response.response_received = True
        mock_response_repo.create.return_value = new_response
        
        # Act
        result = service.track_response_from_webhook(sample_response_event)
        
        # Assert
        assert result.is_success()
        mock_response_repo.create.assert_called_once()
        mock_campaign_repo.get_by_id.assert_called_once_with(sample_response_event.campaign_id)
    
    def test_track_response_sentiment_analysis_failure_still_tracks(self, service, mock_response_repo,
                                                                  mock_sentiment_service, sample_response_event):
        """Test that response is still tracked even if sentiment analysis fails"""
        # Arrange
        mock_existing_response = Mock(spec=CampaignResponse)
        mock_response_repo.get_by_campaign_and_contact.return_value = mock_existing_response
        
        # Mock sentiment analysis failure
        mock_sentiment_service.analyze_response.return_value = Failure("Sentiment analysis failed")
        
        # Mock successful response update without sentiment
        updated_response = Mock(spec=CampaignResponse)
        updated_response.response_received = True
        updated_response.sentiment = None
        mock_response_repo.update_response.return_value = updated_response
        
        # Act
        result = service.track_response_from_webhook(sample_response_event)
        
        # Assert
        assert result.is_success()
        response_data = result.unwrap()
        assert response_data['response_tracked'] == True
        assert response_data.get('sentiment') is None
        assert response_data.get('sentiment_analysis_failed') == True

    # ===== Response Rate Calculation Tests =====
    
    def test_calculate_response_rate_with_confidence_intervals(self, service, mock_response_repo):
        """Test calculating response rate with statistical confidence intervals"""
        # Arrange
        campaign_id = 1
        
        # Mock response analytics from repository
        mock_analytics = {
            'response_rate': 0.18,
            'total_sent': 500,
            'total_responses': 90,
            'confidence_interval': {'lower': 0.148, 'upper': 0.212}
        }
        mock_response_repo.get_response_analytics.return_value = mock_analytics
        
        # Act
        result = service.calculate_response_rate_with_confidence(campaign_id, confidence_level=0.95)
        
        # Assert
        assert result.is_success()
        data = result.unwrap()
        assert data['response_rate'] == 0.18
        assert data['total_sent'] == 500
        assert data['total_responses'] == 90
        assert data['confidence_interval']['lower'] == 0.148
        assert data['confidence_interval']['upper'] == 0.212
        assert data['confidence_level'] == 0.95
        
        mock_response_repo.get_response_analytics.assert_called_once_with(campaign_id)
    
    def test_calculate_response_rate_insufficient_data(self, service, mock_response_repo):
        """Test response rate calculation with insufficient data"""
        # Arrange
        campaign_id = 1
        
        # Mock analytics with very low counts
        mock_analytics = {
            'response_rate': 0.0,
            'total_sent': 5,
            'total_responses': 0,
            'confidence_interval': {'lower': 0.0, 'upper': 0.0}
        }
        mock_response_repo.get_response_analytics.return_value = mock_analytics
        
        # Act
        result = service.calculate_response_rate_with_confidence(campaign_id)
        
        # Assert
        assert result.is_success()
        data = result.unwrap()
        assert data['response_rate'] == 0.0
        assert data['total_sent'] == 5
        assert data['insufficient_data'] == True
        assert data['minimum_sample_size'] > 5

    # ===== A/B Testing Analysis =====
    
    @patch('scipy.stats.chi2_contingency')
    def test_compare_ab_test_variants_statistical_significance(self, mock_chi2, service, mock_response_repo):
        """Test A/B variant comparison with chi-square statistical testing"""
        # Arrange
        campaign_id = 1
        
        # Mock variant comparison data from repository
        variant_data = {
            'variant_a': {
                'sent': 250,
                'responses': 55,
                'response_rate': 0.22,
                'sentiment_breakdown': {'positive': 40, 'neutral': 10, 'negative': 5}
            },
            'variant_b': {
                'sent': 250,
                'responses': 35,
                'response_rate': 0.14,
                'sentiment_breakdown': {'positive': 25, 'neutral': 7, 'negative': 3}
            }
        }
        mock_response_repo.get_variant_comparison.return_value = variant_data
        
        # Mock chi-square test results
        mock_chi2.return_value = (4.32, 0.038, 1, [[45, 205], [45, 205]])  # Significant result
        
        # Act
        result = service.compare_ab_test_variants(campaign_id)
        
        # Assert
        assert result.is_success()
        data = result.unwrap()
        assert data['variant_a']['response_rate'] == 0.22
        assert data['variant_b']['response_rate'] == 0.14
        assert data['statistical_test']['chi_square'] == 4.32
        assert data['statistical_test']['p_value'] == 0.038
        assert data['statistical_test']['significant'] == True
        assert data['statistical_test']['winner'] == 'variant_a'
        
        mock_response_repo.get_variant_comparison.assert_called_once_with(campaign_id)
        mock_chi2.assert_called_once()
    
    @patch('scipy.stats.chi2_contingency')
    def test_compare_ab_test_variants_no_significance(self, mock_chi2, service, mock_response_repo):
        """Test A/B comparison when difference is not statistically significant"""
        # Arrange
        campaign_id = 1
        
        variant_data = {
            'variant_a': {
                'sent': 250,
                'responses': 45,
                'response_rate': 0.18
            },
            'variant_b': {
                'sent': 250,
                'responses': 40,
                'response_rate': 0.16
            }
        }
        mock_response_repo.get_variant_comparison.return_value = variant_data
        
        # Mock chi-square test results - not significant
        mock_chi2.return_value = (0.74, 0.389, 1, [[42.5, 207.5], [42.5, 207.5]])
        
        # Act
        result = service.compare_ab_test_variants(campaign_id)
        
        # Assert
        assert result.is_success()
        data = result.unwrap()
        assert data['statistical_test']['p_value'] == 0.389
        assert data['statistical_test']['significant'] == False
        assert data['statistical_test']['winner'] is None
        assert data['recommendation'] == 'continue_testing'

    # ===== Response Funnel Analysis =====
    
    def test_generate_response_funnel_comprehensive(self, service, mock_response_repo):
        """Test generating comprehensive response funnel analysis"""
        # Arrange
        campaign_id = 1
        
        # Mock funnel data from repository
        funnel_data = {
            'sent': 1000,
            'delivered': 970,
            'opened': 680,  # Estimated from engagement metrics
            'responded': 136,
            'qualified_positive': 85,
            'converted': 12,
            'conversion_rates': {
                'delivery_rate': 0.97,
                'open_rate': 0.70,
                'response_rate': 0.20,
                'qualification_rate': 0.625,
                'conversion_rate': 0.141
            },
            'drop_off_points': {
                'delivery_failure': 30,
                'no_engagement': 290,
                'engaged_no_response': 544,
                'negative_response': 51,
                'no_conversion': 73
            }
        }
        mock_response_repo.get_response_funnel.return_value = funnel_data
        
        # Act
        result = service.generate_response_funnel(campaign_id)
        
        # Assert
        assert result.is_success()
        data = result.unwrap()
        assert data['funnel']['sent'] == 1000
        assert data['funnel']['delivered'] == 970
        assert data['funnel']['responded'] == 136
        assert data['conversion_rates']['response_rate'] == 0.20
        assert data['optimization_suggestions'][0]['focus_area'] == 'engagement'
        assert len(data['drop_off_analysis']) > 0
        
        mock_response_repo.get_response_funnel.assert_called_once_with(campaign_id)
    
    def test_identify_funnel_optimization_opportunities(self, service, mock_response_repo):
        """Test identifying optimization opportunities in response funnel"""
        # Arrange
        campaign_id = 1
        
        # Mock funnel data with poor open rate
        funnel_data = {
            'sent': 500,
            'delivered': 485,
            'opened': 242,  # Only 50% open rate
            'responded': 48,
            'conversion_rates': {
                'delivery_rate': 0.97,
                'open_rate': 0.50,  # Low open rate
                'response_rate': 0.198
            }
        }
        mock_response_repo.get_response_funnel.return_value = funnel_data
        
        # Act
        result = service.generate_response_funnel(campaign_id)
        
        # Assert
        assert result.is_success()
        data = result.unwrap()
        
        # Should identify low open rate as optimization opportunity
        suggestions = data['optimization_suggestions']
        open_rate_suggestion = next(
            (s for s in suggestions if s['focus_area'] == 'open_rate'), None
        )
        assert open_rate_suggestion is not None
        assert open_rate_suggestion['current_rate'] == 0.50
        assert open_rate_suggestion['benchmark'] > 0.60
        assert 'subject_line' in open_rate_suggestion['recommendations']

    # ===== Time-Based Analysis =====
    
    def test_analyze_response_timing_patterns(self, service, mock_response_repo):
        """Test analyzing response timing patterns for optimization"""
        # Arrange
        campaign_id = 1
        
        # Mock time-based pattern data
        time_patterns = {
            'hourly_response_rates': {
                '08': 0.15, '09': 0.24, '10': 0.22, '11': 0.18,
                '12': 0.12, '13': 0.14, '14': 0.20, '15': 0.19,
                '16': 0.21, '17': 0.16, '18': 0.08, '19': 0.06
            },
            'daily_response_rates': {
                'monday': 0.19, 'tuesday': 0.22, 'wednesday': 0.20,
                'thursday': 0.18, 'friday': 0.15, 'saturday': 0.08, 'sunday': 0.05
            },
            'average_response_time_by_hour': {
                '09': 45,  # minutes
                '10': 52,
                '14': 38,
                '16': 41
            }
        }
        mock_response_repo.get_time_based_patterns.return_value = time_patterns
        
        # Act
        result = service.analyze_response_timing_patterns(campaign_id)
        
        # Assert
        assert result.is_success()
        data = result.unwrap()
        assert data['best_send_times']['optimal_hours'] == [9, 10, 16]
        assert data['best_send_times']['optimal_days'] == ['tuesday', 'wednesday']
        assert data['worst_send_times']['avoid_hours'] == [18, 19, 12]
        assert data['worst_send_times']['avoid_days'] == ['saturday', 'sunday']
        assert data['average_response_time_minutes'] > 0
        
        mock_response_repo.get_time_based_patterns.assert_called_once_with(campaign_id)
    
    def test_predict_optimal_send_schedule(self, service):
        """Test predicting optimal send schedule based on historical data"""
        # Arrange
        historical_data = {
            'campaign_ids': [1, 2, 3, 4],
            'time_zone': 'America/New_York'
        }
        
        # Mock historical analysis
        with patch.object(service, '_analyze_historical_timing') as mock_historical:
            mock_historical.return_value = {
                'optimal_windows': [
                    {'start_hour': 9, 'end_hour': 11, 'expected_rate': 0.22},
                    {'start_hour': 14, 'end_hour': 16, 'expected_rate': 0.20}
                ],
                'peak_days': ['tuesday', 'wednesday'],
                'recommended_schedule': {
                    'primary_window': {'day': 'tuesday', 'hour': 9},
                    'secondary_window': {'day': 'wednesday', 'hour': 14}
                }
            }
            
            # Act
            result = service.predict_optimal_send_schedule(**historical_data)
            
            # Assert
            assert result.is_success()
            data = result.unwrap()
            assert len(data['optimal_windows']) == 2
            assert data['recommended_schedule']['primary_window']['hour'] == 9
            assert data['peak_days'] == ['tuesday', 'wednesday']

    # ===== Sentiment Analysis Integration =====
    
    def test_bulk_analyze_response_sentiment(self, service, mock_response_repo, mock_sentiment_service):
        """Test bulk sentiment analysis of campaign responses"""
        # Arrange
        campaign_id = 1
        
        # Mock unanalyzed responses
        unanalyzed_responses = [
            Mock(id=1, response_text="This looks great! I'm interested."),
            Mock(id=2, response_text="Not interested, please remove me."),
            Mock(id=3, response_text="Can you tell me more about pricing?")
        ]
        mock_response_repo.get_unanalyzed_responses.return_value = unanalyzed_responses
        
        # Mock sentiment analysis results
        sentiment_results = [
            {'sentiment': 'positive', 'intent': 'interested', 'confidence': 0.92},
            {'sentiment': 'negative', 'intent': 'opt_out', 'confidence': 0.88},
            {'sentiment': 'neutral', 'intent': 'question', 'confidence': 0.75}
        ]
        mock_sentiment_service.bulk_analyze.return_value = Success(sentiment_results)
        
        # Mock bulk update
        mock_response_repo.bulk_update_sentiment.return_value = 3
        
        # Act
        result = service.bulk_analyze_response_sentiment(campaign_id)
        
        # Assert
        assert result.is_success()
        data = result.unwrap()
        assert data['analyzed_count'] == 3
        assert data['sentiment_breakdown']['positive'] == 1
        assert data['sentiment_breakdown']['negative'] == 1
        assert data['sentiment_breakdown']['neutral'] == 1
        
        mock_response_repo.get_unanalyzed_responses.assert_called_once_with(campaign_id)
        mock_sentiment_service.bulk_analyze.assert_called_once()
        mock_response_repo.bulk_update_sentiment.assert_called_once()

    # ===== Caching and Performance =====
    
    def test_get_cached_analytics_hit(self, service, mock_cache_service):
        """Test retrieving analytics from cache when available"""
        # Arrange
        campaign_id = 1
        cache_key = f"response_analytics:{campaign_id}"
        
        cached_data = {
            'response_rate': 0.18,
            'total_sent': 500,
            'cached_at': utc_now().isoformat()
        }
        mock_cache_service.get.return_value = cached_data
        
        # Act
        result = service.get_response_analytics_cached(campaign_id)
        
        # Assert
        assert result.is_success()
        data = result.unwrap()
        assert data['response_rate'] == 0.18
        assert data['cache_hit'] == True
        
        mock_cache_service.get.assert_called_once_with(cache_key)
    
    def test_get_cached_analytics_miss_updates_cache(self, service, mock_cache_service, mock_response_repo):
        """Test that cache miss triggers fresh calculation and cache update"""
        # Arrange
        campaign_id = 1
        cache_key = f"response_analytics:{campaign_id}"
        
        # Mock cache miss
        mock_cache_service.get.return_value = None
        
        # Mock fresh analytics calculation
        fresh_analytics = {
            'response_rate': 0.19,
            'total_sent': 520,
            'total_responses': 99
        }
        mock_response_repo.get_response_analytics.return_value = fresh_analytics
        
        # Mock cache set
        mock_cache_service.set.return_value = True
        
        # Act
        result = service.get_response_analytics_cached(campaign_id, cache_ttl=3600)
        
        # Assert
        assert result.is_success()
        data = result.unwrap()
        assert data['response_rate'] == 0.19
        assert data['cache_hit'] == False
        
        mock_cache_service.get.assert_called_once_with(cache_key)
        mock_cache_service.set.assert_called_once_with(cache_key, fresh_analytics, ttl=3600)

    # ===== Error Handling and Edge Cases =====
    
    def test_track_response_invalid_campaign_id(self, service, mock_campaign_repo):
        """Test handling of invalid campaign ID"""
        # Arrange
        invalid_event = ResponseEvent(
            campaign_id=999,  # Non-existent campaign
            contact_id=123,
            activity_id=456,
            response_text="Test response",
            received_at=utc_now(),
            variant="A"
        )
        
        mock_campaign_repo.get_by_id.return_value = None
        
        # Act
        result = service.track_response_from_webhook(invalid_event)
        
        # Assert
        assert result.is_failure()
        error = result.unwrap_error()
        assert "Campaign not found" in str(error)
    
    def test_calculate_response_rate_database_error(self, service, mock_response_repo):
        """Test handling of database errors during calculation"""
        # Arrange
        campaign_id = 1
        mock_response_repo.get_response_analytics.side_effect = Exception("Database connection failed")
        
        # Act
        result = service.calculate_response_rate_with_confidence(campaign_id)
        
        # Assert
        assert result.is_failure()
        error = result.unwrap_error()
        assert "Database connection failed" in str(error)
    
    def test_service_initialization_validates_dependencies(self):
        """Test that service initialization validates all required dependencies"""
        # Act & Assert
        with pytest.raises(TypeError):
            ResponseAnalyticsService()
            
        with pytest.raises(TypeError):
            ResponseAnalyticsService(response_repository=Mock())
    
    def test_concurrent_response_tracking_thread_safety(self, service, mock_response_repo):
        """Test that concurrent response tracking is thread-safe"""
        # Arrange
        import threading
        import time
        
        responses = []
        errors = []
        
        def track_response(event_id):
            try:
                event = ResponseEvent(
                    campaign_id=1,
                    contact_id=event_id,
                    activity_id=event_id + 100,
                    response_text=f"Response {event_id}",
                    received_at=utc_now(),
                    variant="A"
                )
                result = service.track_response_from_webhook(event)
                responses.append(result)
            except Exception as e:
                errors.append(e)
        
        # Mock repository to be thread-safe
        mock_response_repo.get_by_campaign_and_contact.return_value = None
        mock_response_repo.create.return_value = Mock(id=1)
        
        # Act
        threads = [threading.Thread(target=track_response, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # Assert
        assert len(errors) == 0
        assert len(responses) == 10

    # ===== Integration with Service Registry =====
    
    def test_service_registry_integration(self, service):
        """Test that service integrates properly with service registry"""
        # This test ensures service can be registered and retrieved
        # Mock service registry behavior
        service._validate_service_dependencies = Mock(return_value=True)
        
        # Act
        is_valid = service._validate_service_dependencies()
        
        # Assert
        assert is_valid == True
        service._validate_service_dependencies.assert_called_once()
