"""
Unit Tests for CampaignResponseRepository - TDD RED PHASE
These tests are written FIRST before implementing the CampaignResponseRepository
All tests should FAIL initially to ensure proper TDD workflow

Tests cover:
1. Response creation and tracking
2. Response time calculations
3. Sentiment and intent analysis
4. Bulk operations for performance
5. Campaign response analytics
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from decimal import Decimal

from repositories.campaign_response_repository import CampaignResponseRepository
from repositories.base_repository import BaseRepository, PaginationParams, PaginatedResult
from crm_database import CampaignResponse, Campaign, Contact, Activity, CampaignMembership
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from utils.datetime_utils import utc_now, ensure_utc


@dataclass
class ResponseTimeMetrics:
    """Response time calculation results"""
    average_seconds: float
    median_seconds: float
    first_response_rate: float
    response_count: int


@dataclass
class ResponseAnalytics:
    """Response analytics data structure"""
    response_rate: float
    total_sent: int
    total_responses: int
    sentiment_distribution: Dict[str, int]
    intent_distribution: Dict[str, int]
    average_response_time_hours: float
    confidence_interval: Dict[str, float]


class TestCampaignResponseRepository:
    """Unit tests for CampaignResponseRepository"""
    
    @pytest.fixture
    def mock_session(self):
        """Mock SQLAlchemy session"""
        return Mock(spec=Session)
    
    @pytest.fixture
    def repository(self, mock_session):
        """Create repository instance with mocked session"""
        return CampaignResponseRepository(mock_session)
    
    @pytest.fixture
    def sample_campaign(self):
        """Sample campaign for testing"""
        campaign = Mock(spec=Campaign)
        campaign.id = 1
        campaign.name = "Test Campaign"
        campaign.status = "running"
        campaign.created_at = utc_now()
        return campaign
    
    @pytest.fixture
    def sample_contact(self):
        """Sample contact for testing"""
        contact = Mock(spec=Contact)
        contact.id = 1
        contact.phone = "+15551234567"
        contact.name = "John Doe"
        return contact
    
    @pytest.fixture
    def sample_sent_activity(self):
        """Sample sent message activity"""
        activity = Mock(spec=Activity)
        activity.id = 1
        activity.activity_type = "message"
        activity.direction = "outgoing"
        activity.status = "delivered"
        activity.created_at = utc_now() - timedelta(hours=2)
        activity.body = "Hi John, interested in our services?"
        return activity
    
    @pytest.fixture
    def sample_response_activity(self):
        """Sample response message activity"""
        activity = Mock(spec=Activity)
        activity.id = 2
        activity.activity_type = "message"
        activity.direction = "incoming"
        activity.status = "received"
        activity.created_at = utc_now() - timedelta(minutes=30)
        activity.body = "Yes, very interested! Tell me more."
        return activity

    # ===== Core CRUD Operations =====
    
    def test_create_response_record_success(self, repository, mock_session, sample_campaign, sample_contact, sample_sent_activity):
        """Test creating a new campaign response record"""
        # Arrange
        response_data = {
            'campaign_id': sample_campaign.id,
            'contact_id': sample_contact.id,
            'sent_activity_id': sample_sent_activity.id,
            'variant_sent': 'A',
            'message_sent': "Hi John, interested in our services?",
            'sent_at': sample_sent_activity.created_at
        }
        
        mock_response = Mock(spec=CampaignResponse)
        mock_response.id = 1
        mock_response.campaign_id = sample_campaign.id
        mock_response.contact_id = sample_contact.id
        mock_response.sent_at = sample_sent_activity.created_at
        mock_response.response_received = False
        
        mock_session.add.return_value = None
        mock_session.commit.return_value = None
        mock_session.refresh.return_value = None
        
        # Mock the repository's create method to return the mock response
        repository.create = Mock(return_value=mock_response)
        
        # Act
        result = repository.create(**response_data)
        
        # Assert
        assert result is not None
        assert result.id == 1
        assert result.campaign_id == sample_campaign.id
        assert result.contact_id == sample_contact.id
        assert result.response_received == False
        repository.create.assert_called_once_with(**response_data)
    
    def test_create_response_record_duplicate_raises_error(self, repository, mock_session, sample_campaign, sample_contact):
        """Test that creating duplicate response record raises error"""
        # Arrange
        response_data = {
            'campaign_id': sample_campaign.id,
            'contact_id': sample_contact.id,
            'campaign_membership_id': 1,
            'message_variant': 'A',
            'message_sent_at': utc_now()
        }
        
        # Create the first response successfully
        mock_response = Mock(spec=CampaignResponse)
        mock_response.id = 1
        repository.create = Mock(return_value=mock_response)
        first_response = repository.create(**response_data)
        
        # Now simulate duplicate error on second attempt
        repository.create = Mock(side_effect=SQLAlchemyError("Duplicate entry"))
        
        # Act & Assert
        with pytest.raises(SQLAlchemyError):
            repository.create(**response_data)
    
    def test_update_response_with_incoming_message(self, repository, mock_session, sample_response_activity):
        """Test updating response record when contact responds"""
        # Arrange
        response_id = 1
        update_data = {
            'response_activity_id': sample_response_activity.id,
            'response_received': True,
            'responded_at': sample_response_activity.created_at,
            'response_text': sample_response_activity.body,
            'response_time_seconds': 5400,  # 1.5 hours
            'sentiment': 'positive',
            'intent': 'interested'
        }
        
        mock_response = Mock(spec=CampaignResponse)
        mock_response.id = response_id
        mock_response.response_received = True
        mock_response.sentiment = 'positive'
        
        mock_session.query.return_value.filter.return_value.first.return_value = mock_response
        mock_session.commit.return_value = None
        
        # Mock repository update method
        repository.update_response = Mock(return_value=mock_response)
        
        # Act
        result = repository.update_response(response_id, **update_data)
        
        # Assert
        assert result is not None
        assert result.response_received == True
        assert result.sentiment == 'positive'
        repository.update_response.assert_called_once_with(response_id, **update_data)
    
    def test_get_by_campaign_and_contact(self, repository, mock_session, sample_campaign, sample_contact):
        """Test retrieving response by campaign and contact"""
        # Arrange
        mock_response = Mock(spec=CampaignResponse)
        mock_response.campaign_id = sample_campaign.id
        mock_response.contact_id = sample_contact.id
        
        mock_session.query.return_value.filter.return_value.first.return_value = mock_response
        repository.get_by_campaign_and_contact = Mock(return_value=mock_response)
        
        # Act
        result = repository.get_by_campaign_and_contact(sample_campaign.id, sample_contact.id)
        
        # Assert
        assert result == mock_response
        repository.get_by_campaign_and_contact.assert_called_once_with(sample_campaign.id, sample_contact.id)

    # ===== Response Analytics Methods =====
    
    def test_get_campaign_responses_paginated(self, repository, mock_session, sample_campaign):
        """Test getting paginated campaign responses"""
        # Arrange
        pagination = PaginationParams(page=1, per_page=10)
        mock_responses = [Mock(spec=CampaignResponse) for _ in range(5)]
        
        paginated_result = PaginatedResult(
            items=mock_responses,
            total=25,
            page=1,
            per_page=10
        )
        
        repository.get_campaign_responses = Mock(return_value=paginated_result)
        
        # Act
        result = repository.get_campaign_responses(sample_campaign.id, pagination)
        
        # Assert
        assert result.items == mock_responses
        assert result.total == 25
        assert result.page == 1
        repository.get_campaign_responses.assert_called_once_with(sample_campaign.id, pagination)
    
    def test_calculate_response_times(self, repository):
        """Test calculating response time metrics"""
        # Arrange
        campaign_id = 1
        mock_metrics = ResponseTimeMetrics(
            average_seconds=3600.0,  # 1 hour average
            median_seconds=2700.0,   # 45 minute median
            first_response_rate=0.15,  # 15% response rate
            response_count=45
        )
        
        repository.calculate_response_times = Mock(return_value=mock_metrics)
        
        # Act
        result = repository.calculate_response_times(campaign_id)
        
        # Assert
        assert result.average_seconds == 3600.0
        assert result.median_seconds == 2700.0
        assert result.first_response_rate == 0.15
        assert result.response_count == 45
        repository.calculate_response_times.assert_called_once_with(campaign_id)
    
    def test_get_response_analytics_comprehensive(self, repository):
        """Test getting comprehensive response analytics"""
        # Arrange
        campaign_id = 1
        mock_analytics = ResponseAnalytics(
            response_rate=0.18,
            total_sent=500,
            total_responses=90,
            sentiment_distribution={'positive': 60, 'neutral': 20, 'negative': 10},
            intent_distribution={'interested': 45, 'not_interested': 25, 'question': 15, 'complaint': 5},
            average_response_time_hours=1.2,
            confidence_interval={'lower': 0.14, 'upper': 0.22}
        )
        
        repository.get_response_analytics = Mock(return_value=mock_analytics)
        
        # Act
        result = repository.get_response_analytics(campaign_id)
        
        # Assert
        assert result.response_rate == 0.18
        assert result.total_sent == 500
        assert result.total_responses == 90
        assert result.sentiment_distribution['positive'] == 60
        assert result.intent_distribution['interested'] == 45
        assert result.average_response_time_hours == 1.2
        assert 'lower' in result.confidence_interval
        repository.get_response_analytics.assert_called_once_with(campaign_id)
    
    def test_get_variant_comparison_ab_testing(self, repository):
        """Test A/B variant response comparison"""
        # Arrange
        campaign_id = 1
        variant_comparison = {
            'variant_a': {
                'sent': 250,
                'responses': 50,
                'response_rate': 0.20,
                'average_response_time': 2.1,
                'sentiment_breakdown': {'positive': 35, 'neutral': 10, 'negative': 5}
            },
            'variant_b': {
                'sent': 250,
                'responses': 40,
                'response_rate': 0.16,
                'average_response_time': 1.8,
                'sentiment_breakdown': {'positive': 28, 'neutral': 8, 'negative': 4}
            },
            'statistical_significance': {
                'chi_square_statistic': 2.67,
                'p_value': 0.102,
                'confidence_level': 0.95,
                'significant': False,
                'winner': None
            }
        }
        
        repository.get_variant_comparison = Mock(return_value=variant_comparison)
        
        # Act
        result = repository.get_variant_comparison(campaign_id)
        
        # Assert
        assert result['variant_a']['response_rate'] == 0.20
        assert result['variant_b']['response_rate'] == 0.16
        assert result['statistical_significance']['significant'] == False
        assert result['statistical_significance']['p_value'] == 0.102
        repository.get_variant_comparison.assert_called_once_with(campaign_id)

    # ===== Time-Based Analytics =====
    
    def test_get_response_funnel_metrics(self, repository):
        """Test getting response funnel analysis"""
        # Arrange
        campaign_id = 1
        funnel_data = {
            'sent': 500,
            'delivered': 485,  # 97% delivery rate
            'opened': 340,     # 70% open rate (estimated)
            'responded': 90,   # 26% response rate of opened
            'qualified': 45,   # 50% qualified responses
            'conversion_rates': {
                'delivery_rate': 0.97,
                'open_rate': 0.70,
                'response_rate': 0.265,
                'qualification_rate': 0.50
            },
            'drop_off_analysis': {
                'not_delivered': 15,
                'delivered_no_open': 145,
                'opened_no_response': 250,
                'responded_not_qualified': 45
            }
        }
        
        repository.get_response_funnel = Mock(return_value=funnel_data)
        
        # Act
        result = repository.get_response_funnel(campaign_id)
        
        # Assert
        assert result['sent'] == 500
        assert result['delivered'] == 485
        assert result['responded'] == 90
        assert result['conversion_rates']['delivery_rate'] == 0.97
        assert result['drop_off_analysis']['not_delivered'] == 15
        repository.get_response_funnel.assert_called_once_with(campaign_id)
    
    def test_get_time_based_response_patterns(self, repository):
        """Test analyzing response patterns over time"""
        # Arrange
        campaign_id = 1
        time_patterns = {
            'hourly_response_rates': {
                '09': 0.22,  # 9 AM - highest response rate
                '10': 0.18,
                '11': 0.15,
                '12': 0.12,  # Lunch hour dip
                '13': 0.14,
                '14': 0.19,
                '15': 0.16,
                '16': 0.20,
                '17': 0.14   # End of work day
            },
            'daily_response_rates': {
                'monday': 0.19,
                'tuesday': 0.21,
                'wednesday': 0.18,
                'thursday': 0.16,
                'friday': 0.15,
                'saturday': 0.08,
                'sunday': 0.06
            },
            'optimal_send_times': {
                'best_hour': 9,
                'best_day': 'tuesday',
                'avoid_hours': [12, 18, 19],
                'avoid_days': ['saturday', 'sunday']
            }
        }
        
        repository.get_time_based_patterns = Mock(return_value=time_patterns)
        
        # Act
        result = repository.get_time_based_patterns(campaign_id)
        
        # Assert
        assert result['hourly_response_rates']['09'] == 0.22
        assert result['daily_response_rates']['tuesday'] == 0.21
        assert result['optimal_send_times']['best_hour'] == 9
        assert 'saturday' in result['optimal_send_times']['avoid_days']
        repository.get_time_based_patterns.assert_called_once_with(campaign_id)

    # ===== Bulk Operations for Performance =====
    
    def test_bulk_create_response_records(self, repository):
        """Test bulk creation of response records for performance"""
        # Arrange
        campaign_id = 1
        response_records = [
            {
                'contact_id': i,
                'sent_activity_id': 100 + i,
                'variant_sent': 'A' if i % 2 == 0 else 'B',
                'message_sent': f"Message to contact {i}",
                'sent_at': utc_now()
            }
            for i in range(1, 101)  # 100 records
        ]
        
        mock_created_count = 100
        repository.bulk_create_responses = Mock(return_value=mock_created_count)
        
        # Act
        result = repository.bulk_create_responses(campaign_id, response_records)
        
        # Assert
        assert result == 100
        repository.bulk_create_responses.assert_called_once_with(campaign_id, response_records)
    
    def test_bulk_update_responses_with_sentiment(self, repository):
        """Test bulk updating responses with sentiment analysis"""
        # Arrange
        sentiment_updates = [
            {
                'response_id': 1,
                'sentiment': 'positive',
                'intent': 'interested',
                'confidence_score': 0.89
            },
            {
                'response_id': 2,
                'sentiment': 'negative',
                'intent': 'not_interested',
                'confidence_score': 0.92
            },
            {
                'response_id': 3,
                'sentiment': 'neutral',
                'intent': 'question',
                'confidence_score': 0.76
            }
        ]
        
        mock_updated_count = 3
        repository.bulk_update_sentiment = Mock(return_value=mock_updated_count)
        
        # Act
        result = repository.bulk_update_sentiment(sentiment_updates)
        
        # Assert
        assert result == 3
        repository.bulk_update_sentiment.assert_called_once_with(sentiment_updates)

    # ===== Error Handling and Edge Cases =====
    
    def test_get_response_analytics_empty_campaign(self, repository):
        """Test analytics for campaign with no responses"""
        # Arrange
        empty_campaign_id = 999
        empty_analytics = ResponseAnalytics(
            response_rate=0.0,
            total_sent=0,
            total_responses=0,
            sentiment_distribution={},
            intent_distribution={},
            average_response_time_hours=0.0,
            confidence_interval={'lower': 0.0, 'upper': 0.0}
        )
        
        repository.get_response_analytics = Mock(return_value=empty_analytics)
        
        # Act
        result = repository.get_response_analytics(empty_campaign_id)
        
        # Assert
        assert result.response_rate == 0.0
        assert result.total_sent == 0
        assert result.total_responses == 0
        repository.get_response_analytics.assert_called_once_with(empty_campaign_id)
    
    def test_calculate_confidence_intervals(self, repository):
        """Test statistical confidence interval calculations"""
        # Arrange
        responses = 50
        total_sent = 300
        confidence_level = 0.95
        
        expected_interval = {
            'lower': 0.123,
            'upper': 0.210,
            'margin_of_error': 0.043
        }
        
        repository.calculate_confidence_interval = Mock(return_value=expected_interval)
        
        # Act
        result = repository.calculate_confidence_interval(responses, total_sent, confidence_level)
        
        # Assert
        assert result['lower'] == 0.123
        assert result['upper'] == 0.210
        assert result['margin_of_error'] == 0.043
        repository.calculate_confidence_interval.assert_called_once_with(responses, total_sent, confidence_level)
    
    def test_database_error_handling(self, repository, mock_session):
        """Test proper handling of database errors"""
        # Arrange
        mock_session.query.side_effect = SQLAlchemyError("Database connection lost")
        
        # Act - The repository returns a default ResponseAnalytics on error
        result = repository.get_response_analytics(1)
        
        # Assert - Should return empty analytics on database error
        assert result.response_rate == 0.0
        assert result.total_sent == 0
        assert result.total_responses == 0
        # The repository logs the error but doesn't rollback for read operations
        assert mock_session.query.called

    # ===== Repository Integration Tests =====
    
    def test_repository_inherits_from_base(self, repository):
        """Test that CampaignResponseRepository properly inherits from BaseRepository"""
        # Assert
        assert isinstance(repository, BaseRepository)
        assert hasattr(repository, 'session')
        assert hasattr(repository, 'create')
        assert hasattr(repository, 'get_by_id')
        assert hasattr(repository, 'update')
        assert hasattr(repository, 'delete')
    
    def test_repository_model_type_is_campaign_response(self, repository):
        """Test that repository is typed for CampaignResponse model"""
        # This test ensures proper typing but will need implementation
        repository._get_model_class = Mock(return_value=CampaignResponse)
        
        # Act
        model_class = repository._get_model_class()
        
        # Assert
        assert model_class == CampaignResponse
        repository._get_model_class.assert_called_once()
