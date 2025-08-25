"""
Tests for EngagementScoringService - P4-01 Engagement Scoring System
TDD RED PHASE - These tests are written FIRST before implementation
"""

import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock, MagicMock, patch
from utils.datetime_utils import utc_now
from services.engagement_scoring_service import EngagementScoringService
from crm_database import Contact, Campaign, EngagementEvent, EngagementScore
from tests.conftest import create_test_contact


class TestEngagementScoringService:
    """Test EngagementScoringService with comprehensive coverage"""
    
    @pytest.fixture
    def mock_event_repository(self):
        """Create mock engagement event repository"""
        mock_repo = Mock()
        mock_repo.get_events_for_contact.return_value = []
        mock_repo.get_recent_events_for_scoring.return_value = []
        mock_repo.get_conversion_events_with_value.return_value = []
        mock_repo.aggregate_events_by_type.return_value = {}
        return mock_repo
    
    @pytest.fixture
    def mock_score_repository(self):
        """Create mock engagement score repository"""
        mock_repo = Mock()
        mock_repo.get_by_contact_and_campaign.return_value = None
        mock_repo.upsert_score.return_value = Mock(id=1, overall_score=75.0)
        mock_repo.get_scores_needing_update.return_value = []
        return mock_repo
    
    @pytest.fixture
    def mock_contact_repository(self):
        """Create mock contact repository"""
        mock_repo = Mock()
        mock_repo.get_all.return_value = []
        mock_repo.get_by_id.return_value = Mock(id=1, first_name='Test', last_name='Contact')
        return mock_repo
    
    @pytest.fixture
    def scoring_service(self, mock_event_repository, mock_score_repository, mock_contact_repository):
        """Create EngagementScoringService with mocked dependencies"""
        return EngagementScoringService(
            event_repository=mock_event_repository,
            score_repository=mock_score_repository,
            contact_repository=mock_contact_repository
        )
    
    def test_calculate_rfm_scores_basic(self, scoring_service, mock_event_repository):
        """Test basic RFM (Recency, Frequency, Monetary) score calculation"""
        # Arrange
        contact_id = 1
        campaign_id = 1
        now = utc_now()
        
        # Mock events for RFM calculation
        mock_events = [
            Mock(
                event_type='delivered',
                event_timestamp=now - timedelta(days=2),
                conversion_value=None
            ),
            Mock(
                event_type='opened',
                event_timestamp=now - timedelta(days=2, hours=1),
                conversion_value=None
            ),
            Mock(
                event_type='clicked',
                event_timestamp=now - timedelta(days=2, hours=2),
                conversion_value=None
            ),
            Mock(
                event_type='converted',
                event_timestamp=now - timedelta(days=1),
                conversion_value=Decimal('150.00')
            )
        ]
        
        mock_event_repository.get_events_for_contact.return_value = mock_events
        
        # Act
        rfm_scores = scoring_service.calculate_rfm_scores(contact_id, campaign_id)
        
        # Assert
        assert 'recency_score' in rfm_scores
        assert 'frequency_score' in rfm_scores
        assert 'monetary_score' in rfm_scores
        
        # Recency should be high (recent activity)
        assert rfm_scores['recency_score'] >= 80.0
        
        # Frequency should reflect 4 events
        assert rfm_scores['frequency_score'] > 0
        
        # Monetary should reflect conversion value
        assert rfm_scores['monetary_score'] > 0
    
    def test_calculate_rfm_scores_no_events(self, scoring_service, mock_event_repository):
        """Test RFM calculation with no events (new contact)"""
        # Arrange
        contact_id = 1
        campaign_id = 1
        
        mock_event_repository.get_events_for_contact.return_value = []
        
        # Act
        rfm_scores = scoring_service.calculate_rfm_scores(contact_id, campaign_id)
        
        # Assert
        assert rfm_scores['recency_score'] == 0.0
        assert rfm_scores['frequency_score'] == 0.0
        assert rfm_scores['monetary_score'] == 0.0
    
    def test_calculate_rfm_scores_old_events_only(self, scoring_service, mock_event_repository):
        """Test RFM calculation with only old events (low recency)"""
        # Arrange
        contact_id = 1
        campaign_id = 1
        now = utc_now()
        
        # Old events (90 days ago)
        mock_events = [
            Mock(
                event_type='delivered',
                event_timestamp=now - timedelta(days=90),
                conversion_value=None
            ),
            Mock(
                event_type='opened',
                event_timestamp=now - timedelta(days=89),
                conversion_value=None
            )
        ]
        
        mock_event_repository.get_events_for_contact.return_value = mock_events
        
        # Act
        rfm_scores = scoring_service.calculate_rfm_scores(contact_id, campaign_id)
        
        # Assert
        # Recency should be low (old activity)
        assert rfm_scores['recency_score'] <= 20.0
        
        # Frequency should still reflect events
        assert rfm_scores['frequency_score'] > 0
        
        # No monetary value
        assert rfm_scores['monetary_score'] == 0.0
    
    def test_calculate_time_decay_scores(self, scoring_service, mock_event_repository):
        """Test time-decay weighted scoring"""
        # Arrange
        contact_id = 1
        campaign_id = 1
        now = utc_now()
        
        # Events at different time intervals
        mock_events = [
            Mock(
                event_type='opened',
                event_timestamp=now - timedelta(days=1),
                conversion_value=None
            ),
            Mock(
                event_type='clicked',
                event_timestamp=now - timedelta(days=7),
                conversion_value=None
            ),
            Mock(
                event_type='responded',
                event_timestamp=now - timedelta(days=30),
                conversion_value=None
            )
        ]
        
        mock_event_repository.get_events_for_contact.return_value = mock_events
        
        # Act
        decay_score = scoring_service.calculate_time_decay_score(contact_id, campaign_id, decay_factor=0.95)
        
        # Assert
        assert decay_score > 0
        assert decay_score <= 100.0
        # Recent events should have more weight
        assert isinstance(decay_score, float)
    
    def test_calculate_composite_engagement_score(self, scoring_service):
        """Test composite score calculation from individual components"""
        # Arrange
        component_scores = {
            'recency_score': 85.0,
            'frequency_score': 75.0,
            'monetary_score': 90.0,
            'time_decay_score': 80.0,
            'engagement_diversity_score': 70.0
        }
        
        weights = {
            'recency_weight': 0.3,
            'frequency_weight': 0.25,
            'monetary_weight': 0.2,
            'time_decay_weight': 0.15,
            'diversity_weight': 0.1
        }
        
        # Act
        composite_score = scoring_service.calculate_composite_score(component_scores, weights)
        
        # Assert
        assert composite_score > 0
        assert composite_score <= 100.0
        # Should be weighted average, approximately 81.0
        assert 75.0 <= composite_score <= 90.0
    
    def test_calculate_predictive_engagement_probability(self, scoring_service, mock_event_repository):
        """Test predictive engagement probability calculation"""
        # Arrange
        contact_id = 1
        campaign_id = 1
        now = utc_now()
        
        # High engagement history
        mock_events = [
            Mock(event_type='delivered', event_timestamp=now - timedelta(days=1)),
            Mock(event_type='opened', event_timestamp=now - timedelta(days=1, hours=1)),
            Mock(event_type='clicked', event_timestamp=now - timedelta(days=1, hours=2)),
            Mock(event_type='responded', event_timestamp=now - timedelta(days=1, hours=3))
        ]
        
        mock_event_repository.get_events_for_contact.return_value = mock_events
        
        # Act
        probability = scoring_service.calculate_engagement_probability(contact_id, campaign_id)
        
        # Assert
        assert 0.0 <= probability <= 1.0
        # High engagement history should yield high probability
        assert probability >= 0.6
    
    def test_calculate_engagement_probability_low_engagement(self, scoring_service, mock_event_repository):
        """Test engagement probability with low engagement history"""
        # Arrange
        contact_id = 1
        campaign_id = 1
        now = utc_now()
        
        # Only delivery events, no engagement
        mock_events = [
            Mock(event_type='delivered', event_timestamp=now - timedelta(days=5)),
            Mock(event_type='delivered', event_timestamp=now - timedelta(days=10)),
            Mock(event_type='delivered', event_timestamp=now - timedelta(days=15))
        ]
        
        mock_event_repository.get_events_for_contact.return_value = mock_events
        
        # Act
        probability = scoring_service.calculate_engagement_probability(contact_id, campaign_id)
        
        # Assert
        assert 0.0 <= probability <= 1.0
        # Low engagement should yield low probability
        assert probability <= 0.4
    
    def test_normalize_score_to_percentile(self, scoring_service):
        """Test score normalization to 0-100 scale"""
        # Arrange
        raw_scores = [10.5, 25.3, 45.7, 72.1, 89.4, 95.2]
        
        # Act
        normalized_scores = scoring_service.normalize_scores_to_percentile(raw_scores)
        
        # Assert
        assert len(normalized_scores) == len(raw_scores)
        assert all(0 <= score <= 100 for score in normalized_scores)
        # Highest raw score should get 100
        assert max(normalized_scores) == 100.0
        # Lowest raw score should get 0 or close to 0
        assert min(normalized_scores) <= 20.0
    
    def test_calculate_full_engagement_score(self, scoring_service, mock_event_repository, mock_score_repository):
        """Test full engagement score calculation workflow"""
        # Arrange
        contact_id = 1
        campaign_id = 1
        now = utc_now()
        
        # Comprehensive event history
        mock_events = [
            Mock(
                event_type='delivered',
                event_timestamp=now - timedelta(days=2),
                conversion_value=None
            ),
            Mock(
                event_type='opened',
                event_timestamp=now - timedelta(days=2, hours=1),
                conversion_value=None
            ),
            Mock(
                event_type='clicked',
                event_timestamp=now - timedelta(days=1),
                conversion_value=None
            ),
            Mock(
                event_type='converted',
                event_timestamp=now - timedelta(hours=12),
                conversion_value=Decimal('200.00')
            )
        ]
        
        mock_event_repository.get_events_for_contact.return_value = mock_events
        mock_score_repository.upsert_score.return_value = Mock(
            id=1,
            overall_score=87.5,
            recency_score=90.0,
            frequency_score=85.0,
            monetary_score=88.0,
            engagement_probability=0.82
        )
        
        # Act
        score = scoring_service.calculate_engagement_score(contact_id, campaign_id)
        
        # Assert
        assert score is not None
        assert score.overall_score > 80.0
        assert score.engagement_probability > 0.7
        
        # Verify repository interactions
        mock_event_repository.get_events_for_contact.assert_called_once_with(contact_id)
        mock_score_repository.upsert_score.assert_called_once()
    
    def test_handle_edge_case_no_events(self, scoring_service, mock_event_repository, mock_score_repository):
        """Test handling edge case with no engagement events"""
        # Arrange
        contact_id = 1
        campaign_id = 1
        
        mock_event_repository.get_events_for_contact.return_value = []
        mock_score_repository.upsert_score.return_value = Mock(
            id=1,
            overall_score=0.0,
            recency_score=0.0,
            frequency_score=0.0,
            monetary_score=0.0,
            engagement_probability=0.1
        )
        
        # Act
        score = scoring_service.calculate_engagement_score(contact_id, campaign_id)
        
        # Assert
        assert score is not None
        assert score.overall_score == 0.0
        assert score.engagement_probability <= 0.2
    
    def test_handle_edge_case_all_negative_events(self, scoring_service, mock_event_repository, mock_score_repository):
        """Test handling edge case with only negative engagement events"""
        # Arrange
        contact_id = 1
        campaign_id = 1
        now = utc_now()
        
        # Only negative events
        mock_events = [
            Mock(
                event_type='opted_out',
                event_timestamp=now - timedelta(days=1),
                conversion_value=None
            ),
            Mock(
                event_type='bounced',
                event_timestamp=now - timedelta(days=2),
                conversion_value=None
            )
        ]
        
        mock_event_repository.get_events_for_contact.return_value = mock_events
        mock_score_repository.upsert_score.return_value = Mock(
            id=1,
            overall_score=5.0,  # Very low but not zero due to recent activity
            recency_score=10.0,
            frequency_score=0.0,
            monetary_score=0.0,
            engagement_probability=0.05
        )
        
        # Act
        score = scoring_service.calculate_engagement_score(contact_id, campaign_id)
        
        # Assert
        assert score is not None
        assert score.overall_score <= 10.0
        assert score.engagement_probability <= 0.1
    
    def test_batch_calculate_scores(self, scoring_service, mock_contact_repository, mock_score_repository):
        """Test batch processing of engagement scores for multiple contacts"""
        # Arrange
        campaign_id = 1
        
        mock_contacts = [
            Mock(id=1, first_name='Contact1'),
            Mock(id=2, first_name='Contact2'),
            Mock(id=3, first_name='Contact3')
        ]
        
        mock_contact_repository.get_all.return_value = mock_contacts
        mock_score_repository.upsert_score.side_effect = [
            Mock(id=1, overall_score=75.0, contact_id=1),
            Mock(id=2, overall_score=82.0, contact_id=2),
            Mock(id=3, overall_score=68.0, contact_id=3)
        ]
        
        # Act
        results = scoring_service.batch_calculate_scores(campaign_id, contact_ids=[1, 2, 3])
        
        # Assert
        assert len(results) == 3
        assert results[0].contact_id == 1
        assert results[1].contact_id == 2
        assert results[2].contact_id == 3
        
        # Verify repository calls
        assert mock_score_repository.upsert_score.call_count == 3
    
    def test_update_stale_scores(self, scoring_service, mock_score_repository):
        """Test updating scores that are considered stale"""
        # Arrange
        now = utc_now()
        
        mock_stale_scores = [
            Mock(
                id=1,
                contact_id=1,
                campaign_id=1,
                calculated_at=now - timedelta(days=8),
                overall_score=70.0
            ),
            Mock(
                id=2,
                contact_id=2,
                campaign_id=1,
                calculated_at=now - timedelta(days=10),
                overall_score=65.0
            )
        ]
        
        mock_score_repository.get_scores_needing_update.return_value = mock_stale_scores
        mock_score_repository.upsert_score.side_effect = [
            Mock(id=1, overall_score=75.0, contact_id=1),
            Mock(id=2, overall_score=68.0, contact_id=2)
        ]
        
        # Act
        updated_count = scoring_service.update_stale_scores(max_age_hours=168)  # 7 days
        
        # Assert
        assert updated_count == 2
        mock_score_repository.get_scores_needing_update.assert_called_once_with(168)
        assert mock_score_repository.upsert_score.call_count == 2
    
    def test_calculate_engagement_diversity_score(self, scoring_service, mock_event_repository):
        """Test calculation of engagement diversity (variety of event types)"""
        # Arrange
        contact_id = 1
        campaign_id = 1
        now = utc_now()
        
        # Diverse engagement events
        mock_events = [
            Mock(event_type='delivered', event_timestamp=now),
            Mock(event_type='opened', event_timestamp=now),
            Mock(event_type='clicked', event_timestamp=now),
            Mock(event_type='responded', event_timestamp=now),
            Mock(event_type='converted', event_timestamp=now)
        ]
        
        mock_event_repository.get_events_for_contact.return_value = mock_events
        
        # Act
        diversity_score = scoring_service.calculate_engagement_diversity_score(contact_id, campaign_id)
        
        # Assert
        assert diversity_score > 0
        assert diversity_score <= 100.0
        # Should be high due to 5 different event types
        assert diversity_score >= 80.0
    
    def test_calculate_engagement_diversity_score_low_diversity(self, scoring_service, mock_event_repository):
        """Test diversity score with only one type of event"""
        # Arrange
        contact_id = 1
        campaign_id = 1
        now = utc_now()
        
        # Only delivery events (low diversity)
        mock_events = [
            Mock(event_type='delivered', event_timestamp=now),
            Mock(event_type='delivered', event_timestamp=now - timedelta(hours=1)),
            Mock(event_type='delivered', event_timestamp=now - timedelta(hours=2))
        ]
        
        mock_event_repository.get_events_for_contact.return_value = mock_events
        
        # Act
        diversity_score = scoring_service.calculate_engagement_diversity_score(contact_id, campaign_id)
        
        # Assert
        assert diversity_score >= 0
        assert diversity_score <= 100.0
        # Should be low due to only 1 event type
        assert diversity_score <= 30.0
    
    def test_get_score_explanation(self, scoring_service):
        """Test generation of human-readable score explanations"""
        # Arrange
        score_components = {
            'overall_score': 85.5,
            'recency_score': 90.0,
            'frequency_score': 80.0,
            'monetary_score': 88.0,
            'engagement_probability': 0.78,
            'engagement_diversity_score': 85.0
        }
        
        # Act
        explanation = scoring_service.get_score_explanation(score_components)
        
        # Assert
        assert explanation is not None
        assert isinstance(explanation, dict)
        assert 'overall_assessment' in explanation
        assert 'key_strengths' in explanation
        assert 'improvement_areas' in explanation
        assert 'engagement_prediction' in explanation
    
    def test_validate_score_calculation_inputs(self, scoring_service):
        """Test validation of inputs to score calculation"""
        # Test valid inputs
        assert scoring_service.validate_calculation_inputs(contact_id=1, campaign_id=1) is True
        
        # Test invalid inputs
        with pytest.raises(ValueError, match="Contact ID must be positive"):
            scoring_service.validate_calculation_inputs(contact_id=0, campaign_id=1)
        
        with pytest.raises(ValueError, match="Campaign ID must be positive"):
            scoring_service.validate_calculation_inputs(contact_id=1, campaign_id=0)
        
        with pytest.raises(ValueError, match="Contact ID cannot be None"):
            scoring_service.validate_calculation_inputs(contact_id=None, campaign_id=1)
    
    def test_performance_with_large_dataset(self, scoring_service, mock_event_repository):
        """Test performance characteristics with large event datasets"""
        # Arrange - Large number of events
        contact_id = 1
        campaign_id = 1
        now = utc_now()
        
        # Generate 1000 mock events
        mock_events = []
        event_types = ['delivered', 'opened', 'clicked', 'responded']
        
        for i in range(1000):
            mock_events.append(Mock(
                event_type=event_types[i % 4],
                event_timestamp=now - timedelta(hours=i),
                conversion_value=Decimal('50.00') if i % 50 == 0 else None
            ))
        
        mock_event_repository.get_events_for_contact.return_value = mock_events
        
        # Act - Time the calculation
        import time
        start_time = time.time()
        rfm_scores = scoring_service.calculate_rfm_scores(contact_id, campaign_id)
        end_time = time.time()
        
        # Assert
        calculation_time = end_time - start_time
        assert calculation_time < 2.0  # Should complete within 2 seconds
        assert rfm_scores['recency_score'] is not None
        assert rfm_scores['frequency_score'] > 0
        assert rfm_scores['monetary_score'] > 0
    
    @patch('services.engagement_scoring_service.logger')
    def test_error_handling_and_logging(self, mock_logger, scoring_service, mock_event_repository):
        """Test error handling and logging in score calculation"""
        # Arrange - Force an error
        mock_event_repository.get_events_for_contact.side_effect = Exception("Database error")
        
        # Act & Assert
        with pytest.raises(Exception):
            scoring_service.calculate_rfm_scores(contact_id=1, campaign_id=1)
        
        # Verify logging
        mock_logger.error.assert_called()
    
    def test_score_caching_mechanism(self, scoring_service, mock_score_repository):
        """Test that scores are properly cached and reused when appropriate"""
        # Arrange
        contact_id = 1
        campaign_id = 1
        
        # Mock existing recent score
        existing_score = Mock(
            id=1,
            contact_id=contact_id,
            campaign_id=campaign_id,
            overall_score=80.0,
            calculated_at=utc_now() - timedelta(hours=2),  # Recent
            score_version='1.0'
        )
        
        mock_score_repository.get_by_contact_and_campaign.return_value = existing_score
        
        # Act - Request score calculation
        score = scoring_service.get_or_calculate_score(
            contact_id=contact_id,
            campaign_id=campaign_id,
            force_recalculate=False,
            max_age_hours=6
        )
        
        # Assert
        assert score == existing_score
        # Should not have called upsert since score is recent
        mock_score_repository.upsert_score.assert_not_called()
    
    def test_force_recalculate_score(self, scoring_service, mock_score_repository, mock_event_repository):
        """Test forcing recalculation even when recent score exists"""
        # Arrange
        contact_id = 1
        campaign_id = 1
        
        # Mock existing recent score
        existing_score = Mock(
            id=1,
            contact_id=contact_id,
            campaign_id=campaign_id,
            overall_score=80.0,
            calculated_at=utc_now() - timedelta(hours=1),  # Very recent
            score_version='1.0'
        )
        
        mock_score_repository.get_by_contact_and_campaign.return_value = existing_score
        mock_event_repository.get_events_for_contact.return_value = []
        
        new_score = Mock(id=1, overall_score=75.0, contact_id=contact_id)
        mock_score_repository.upsert_score.return_value = new_score
        
        # Act - Force recalculation
        score = scoring_service.get_or_calculate_score(
            contact_id=contact_id,
            campaign_id=campaign_id,
            force_recalculate=True,
            max_age_hours=6
        )
        
        # Assert
        assert score == new_score
        # Should have called upsert despite recent score
        mock_score_repository.upsert_score.assert_called_once()