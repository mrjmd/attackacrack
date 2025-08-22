"""
Unit Tests for AB Test Result Repository - TDD RED PHASE
These tests are written FIRST before implementing the ABTestResultRepository
All tests should FAIL initially to ensure proper TDD workflow
"""

import pytest
from datetime import datetime, timedelta
from typing import Dict, List, Any
from unittest.mock import Mock, patch

from repositories.ab_test_result_repository import ABTestResultRepository
from repositories.base_repository import PaginationParams, PaginatedResult
from services.common.result import Result
from crm_database import ABTestResult, Campaign, Contact
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError


class TestABTestResultRepository:
    """Unit tests for AB Test Result Repository"""
    
    @pytest.fixture
    def mock_session(self):
        """Mock SQLAlchemy session"""
        return Mock(spec=Session)
    
    @pytest.fixture
    def repository(self, mock_session):
        """Create ABTestResultRepository with mocked session"""
        return ABTestResultRepository(session=mock_session, model_class=ABTestResult)
    
    @pytest.fixture
    def sample_ab_result(self):
        """Sample AB test result record"""
        return ABTestResult(
            id=1,
            campaign_id=1,
            contact_id=1,
            variant='A',
            assigned_at=datetime.now(),
            message_sent=True,
            message_opened=False,
            link_clicked=False,
            response_received=False,
            sent_activity_id=101,
            sent_at=datetime.now()
        )


class TestVariantAssignment:
    """Test variant assignment operations"""
    
    def test_assign_variant_to_contact(self, repository, mock_session):
        """Test assigning variant to contact"""
        # Arrange
        campaign_id, contact_id, variant = 1, 1, 'A'
        mock_session.query.return_value.filter_by.return_value.first.return_value = None  # No existing assignment
        mock_session.add = Mock()
        mock_session.commit = Mock()
        
        # Act
        result = repository.assign_variant(campaign_id, contact_id, variant)
        
        # Assert
        assert result.is_success
        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()
        
        # Verify the assignment was created with correct data
        added_assignment = mock_session.add.call_args[0][0]
        assert added_assignment.campaign_id == campaign_id
        assert added_assignment.contact_id == contact_id
        assert added_assignment.variant == variant
        assert added_assignment.assigned_at is not None
    
    def test_assign_variant_duplicate_assignment(self, repository, mock_session, sample_ab_result):
        """Test handling duplicate variant assignment"""
        # Arrange - Existing assignment
        campaign_id, contact_id, variant = 1, 1, 'B'
        mock_session.query.return_value.filter_by.return_value.first.return_value = sample_ab_result
        
        # Act
        result = repository.assign_variant(campaign_id, contact_id, variant)
        
        # Assert - Should succeed but not create duplicate
        assert result.is_success
        assert result.data.variant == 'A'  # Existing variant returned
        
        # Should not add new assignment
        mock_session.add.assert_not_called()
    
    def test_assign_variant_database_error(self, repository, mock_session):
        """Test handling database error during assignment"""
        # Arrange
        campaign_id, contact_id, variant = 1, 1, 'A'
        mock_session.query.return_value.filter_by.return_value.first.return_value = None
        mock_session.add = Mock()
        mock_session.commit.side_effect = SQLAlchemyError("Database connection error")
        mock_session.rollback = Mock()
        
        # Act
        result = repository.assign_variant(campaign_id, contact_id, variant)
        
        # Assert
        assert result.is_failure
        assert "Database connection error" in result.error
        assert result.error_code == "DB_ERROR"
        mock_session.rollback.assert_called_once()
    
    def test_get_contact_variant_existing(self, repository, mock_session, sample_ab_result):
        """Test retrieving existing contact variant assignment"""
        # Arrange
        campaign_id, contact_id = 1, 1
        mock_session.query.return_value.filter_by.return_value.first.return_value = sample_ab_result
        
        # Act
        result = repository.get_contact_variant(campaign_id, contact_id)
        
        # Assert
        assert result.is_success
        assert result.data == 'A'
        
        # Verify query was called correctly
        mock_session.query.assert_called_with(ABTestResult)
        mock_session.query.return_value.filter_by.assert_called_with(
            campaign_id=campaign_id, contact_id=contact_id
        )
    
    def test_get_contact_variant_not_assigned(self, repository, mock_session):
        """Test retrieving variant for unassigned contact"""
        # Arrange
        campaign_id, contact_id = 1, 999
        mock_session.query.return_value.filter_by.return_value.first.return_value = None
        
        # Act
        result = repository.get_contact_variant(campaign_id, contact_id)
        
        # Assert
        assert result.is_failure
        assert result.error_code == "VARIANT_NOT_ASSIGNED"
        assert "Contact not assigned to any variant" in result.error
    
    def test_get_campaign_assignments(self, repository, mock_session):
        """Test retrieving all assignments for a campaign"""
        # Arrange
        campaign_id = 1
        mock_assignments = [
            ABTestResult(id=1, campaign_id=1, contact_id=1, variant='A'),
            ABTestResult(id=2, campaign_id=1, contact_id=2, variant='B'),
            ABTestResult(id=3, campaign_id=1, contact_id=3, variant='A'),
        ]
        mock_session.query.return_value.filter_by.return_value.all.return_value = mock_assignments
        
        # Act
        result = repository.get_campaign_assignments(campaign_id)
        
        # Assert
        assert result.is_success
        assignments = result.data
        assert len(assignments) == 3
        assert assignments[0].variant == 'A'
        assert assignments[1].variant == 'B'
        
        mock_session.query.return_value.filter_by.assert_called_with(campaign_id=campaign_id)
    
    def test_get_variant_assignments(self, repository, mock_session):
        """Test retrieving assignments for specific variant"""
        # Arrange
        campaign_id, variant = 1, 'A'
        mock_assignments = [
            ABTestResult(id=1, campaign_id=1, contact_id=1, variant='A'),
            ABTestResult(id=3, campaign_id=1, contact_id=3, variant='A'),
        ]
        mock_session.query.return_value.filter_by.return_value.all.return_value = mock_assignments
        
        # Act
        result = repository.get_variant_assignments(campaign_id, variant)
        
        # Assert
        assert result.is_success
        assignments = result.data
        assert len(assignments) == 2
        assert all(a.variant == 'A' for a in assignments)
        
        mock_session.query.return_value.filter_by.assert_called_with(
            campaign_id=campaign_id, variant=variant
        )


class TestMetricsTracking:
    """Test metrics tracking operations"""
    
    def test_track_message_sent(self, repository, mock_session, sample_ab_result):
        """Test tracking message sent event"""
        # Arrange
        campaign_id, contact_id, variant, activity_id = 1, 1, 'A', 101
        mock_session.query.return_value.filter_by.return_value.first.return_value = sample_ab_result
        mock_session.commit = Mock()
        
        # Act
        result = repository.track_message_sent(campaign_id, contact_id, variant, activity_id)
        
        # Assert
        assert result.is_success
        assert sample_ab_result.message_sent is True
        assert sample_ab_result.sent_activity_id == activity_id
        assert sample_ab_result.sent_at is not None
        mock_session.commit.assert_called_once()
    
    def test_track_message_sent_no_assignment(self, repository, mock_session):
        """Test tracking message sent when no assignment exists"""
        # Arrange
        campaign_id, contact_id, variant, activity_id = 1, 999, 'A', 101
        mock_session.query.return_value.filter_by.return_value.first.return_value = None
        
        # Act
        result = repository.track_message_sent(campaign_id, contact_id, variant, activity_id)
        
        # Assert
        assert result.is_failure
        assert result.error_code == "ASSIGNMENT_NOT_FOUND"
        assert "Assignment not found" in result.error
    
    def test_track_message_opened(self, repository, mock_session, sample_ab_result):
        """Test tracking message opened event"""
        # Arrange
        campaign_id, contact_id, variant = 1, 1, 'A'
        sample_ab_result.message_opened = False
        mock_session.query.return_value.filter_by.return_value.first.return_value = sample_ab_result
        mock_session.commit = Mock()
        
        # Act
        result = repository.track_message_opened(campaign_id, contact_id, variant)
        
        # Assert
        assert result.is_success
        assert sample_ab_result.message_opened is True
        assert sample_ab_result.opened_at is not None
        mock_session.commit.assert_called_once()
    
    def test_track_link_clicked(self, repository, mock_session, sample_ab_result):
        """Test tracking link clicked event"""
        # Arrange
        campaign_id, contact_id, variant = 1, 1, 'A'
        link_url = "https://example.com/product"
        sample_ab_result.link_clicked = False
        mock_session.query.return_value.filter_by.return_value.first.return_value = sample_ab_result
        mock_session.commit = Mock()
        
        # Act
        result = repository.track_link_clicked(campaign_id, contact_id, variant, link_url)
        
        # Assert
        assert result.is_success
        assert sample_ab_result.link_clicked is True
        assert sample_ab_result.clicked_link_url == link_url
        assert sample_ab_result.clicked_at is not None
        mock_session.commit.assert_called_once()
    
    def test_track_response_received(self, repository, mock_session, sample_ab_result):
        """Test tracking response received event"""
        # Arrange
        campaign_id, contact_id, variant = 1, 1, 'A'
        response_type, activity_id = 'positive', 201
        sample_ab_result.response_received = False
        mock_session.query.return_value.filter_by.return_value.first.return_value = sample_ab_result
        mock_session.commit = Mock()
        
        # Act
        result = repository.track_response_received(
            campaign_id, contact_id, variant, response_type, activity_id
        )
        
        # Assert
        assert result.is_success
        assert sample_ab_result.response_received is True
        assert sample_ab_result.response_type == response_type
        assert sample_ab_result.response_activity_id == activity_id
        assert sample_ab_result.responded_at is not None
        mock_session.commit.assert_called_once()
    
    def test_track_multiple_events_same_contact(self, repository, mock_session, sample_ab_result):
        """Test tracking multiple events for same contact"""
        # Arrange
        campaign_id, contact_id, variant = 1, 1, 'A'
        mock_session.query.return_value.filter_by.return_value.first.return_value = sample_ab_result
        mock_session.commit = Mock()
        
        # Act - Track multiple events
        sent_result = repository.track_message_sent(campaign_id, contact_id, variant, 101)
        opened_result = repository.track_message_opened(campaign_id, contact_id, variant)
        clicked_result = repository.track_link_clicked(campaign_id, contact_id, variant, "https://example.com")
        response_result = repository.track_response_received(campaign_id, contact_id, variant, "positive", 201)
        
        # Assert - All should succeed
        assert all(r.is_success for r in [sent_result, opened_result, clicked_result, response_result])
        
        # Verify all events tracked
        assert sample_ab_result.message_sent is True
        assert sample_ab_result.message_opened is True
        assert sample_ab_result.link_clicked is True
        assert sample_ab_result.response_received is True
        assert sample_ab_result.response_type == "positive"
        
        # Should have committed 4 times (once per event)
        assert mock_session.commit.call_count == 4


class TestMetricsAggregation:
    """Test metrics aggregation and reporting"""
    
    def test_get_variant_metrics(self, repository, mock_session):
        """Test getting aggregated metrics for a variant"""
        # Arrange
        campaign_id, variant = 1, 'A'
        
        # Mock query results for metrics calculation
        mock_assignments = [
            ABTestResult(id=1, variant='A', message_sent=True, message_opened=True, link_clicked=False, response_received=True, response_type='positive'),
            ABTestResult(id=2, variant='A', message_sent=True, message_opened=False, link_clicked=False, response_received=False),
            ABTestResult(id=3, variant='A', message_sent=True, message_opened=True, link_clicked=True, response_received=True, response_type='positive'),
            ABTestResult(id=4, variant='A', message_sent=True, message_opened=True, link_clicked=True, response_received=True, response_type='negative'),
        ]
        
        mock_session.query.return_value.filter_by.return_value.all.return_value = mock_assignments
        
        # Act
        result = repository.get_variant_metrics(campaign_id, variant)
        
        # Assert
        assert result.is_success
        metrics = result.data
        
        # Check raw counts
        assert metrics['messages_sent'] == 4
        assert metrics['messages_opened'] == 3
        assert metrics['links_clicked'] == 2
        assert metrics['responses_received'] == 3
        assert metrics['positive_responses'] == 2
        assert metrics['negative_responses'] == 1
        
        # Check calculated rates
        assert metrics['open_rate'] == 0.75  # 3/4
        assert metrics['click_rate'] == 0.5   # 2/4
        assert metrics['response_rate'] == 0.75  # 3/4
        assert metrics['conversion_rate'] == 0.5  # 2/4 positive responses
    
    def test_get_variant_metrics_no_data(self, repository, mock_session):
        """Test getting metrics when no data exists for variant"""
        # Arrange
        campaign_id, variant = 1, 'A'
        mock_session.query.return_value.filter_by.return_value.all.return_value = []
        
        # Act
        result = repository.get_variant_metrics(campaign_id, variant)
        
        # Assert
        assert result.is_success
        metrics = result.data
        
        # All metrics should be zero
        assert all(metrics[key] == 0 for key in [
            'messages_sent', 'messages_opened', 'links_clicked', 'responses_received',
            'positive_responses', 'negative_responses', 'open_rate', 'click_rate',
            'response_rate', 'conversion_rate'
        ])
    
    def test_get_campaign_ab_summary(self, repository, mock_session):
        """Test getting complete A/B test summary for campaign"""
        # Arrange
        campaign_id = 1
        
        # Mock data for both variants
        variant_a_assignments = [
            ABTestResult(id=1, variant='A', message_sent=True, message_opened=True, response_received=True, response_type='positive'),
            ABTestResult(id=2, variant='A', message_sent=True, message_opened=False, response_received=False),
            ABTestResult(id=3, variant='A', message_sent=True, message_opened=True, response_received=True, response_type='negative'),
        ]
        
        variant_b_assignments = [
            ABTestResult(id=4, variant='B', message_sent=True, message_opened=True, response_received=True, response_type='positive'),
            ABTestResult(id=5, variant='B', message_sent=True, message_opened=True, response_received=True, response_type='positive'),
            ABTestResult(id=6, variant='B', message_sent=True, message_opened=False, response_received=False),
        ]
        
        # Mock the query calls for both variants
        def mock_filter_by(**kwargs):
            if kwargs.get('variant') == 'A':
                mock_query = Mock()
                mock_query.all.return_value = variant_a_assignments
                return mock_query
            elif kwargs.get('variant') == 'B':
                mock_query = Mock()
                mock_query.all.return_value = variant_b_assignments
                return mock_query
            else:  # All assignments
                mock_query = Mock()
                mock_query.all.return_value = variant_a_assignments + variant_b_assignments
                return mock_query
        
        mock_session.query.return_value.filter_by.side_effect = mock_filter_by
        
        # Act
        result = repository.get_campaign_ab_summary(campaign_id)
        
        # Assert
        assert result.is_success
        summary = result.data
        
        # Check variant A metrics
        variant_a = summary['variant_a']
        assert variant_a['messages_sent'] == 3
        assert variant_a['conversion_rate'] == 1/3  # 1 positive out of 3
        assert variant_a['open_rate'] == 2/3  # 2 opened out of 3
        
        # Check variant B metrics
        variant_b = summary['variant_b']
        assert variant_b['messages_sent'] == 3
        assert variant_b['conversion_rate'] == 2/3  # 2 positive out of 3
        assert variant_b['open_rate'] == 2/3  # 2 opened out of 3
        
        # Check winner determination
        assert summary['winner'] == 'B'  # Higher conversion rate
        assert summary['significant_difference'] is True  # Should calculate statistical significance
        assert 'confidence_level' in summary
    
    @patch('repositories.ab_test_result_repository.stats.chi2_contingency')
    def test_statistical_significance_calculation(self, mock_chi2, repository, mock_session):
        """Test statistical significance calculation"""
        # Arrange
        campaign_id = 1
        mock_chi2.return_value = (10.828, 0.001, 1, None)  # chi2, p-value, dof, expected
        
        # Mock assignments with clear difference
        variant_a_assignments = [Mock(variant='A', response_received=True, response_type='positive')] * 10
        variant_b_assignments = [Mock(variant='B', response_received=True, response_type='positive')] * 20
        
        mock_session.query.return_value.filter_by.return_value.all.return_value = (
            variant_a_assignments + variant_b_assignments
        )
        
        # Act
        result = repository.get_campaign_ab_summary(campaign_id)
        
        # Assert
        assert result.is_success
        summary = result.data
        
        assert summary['significant_difference'] is True
        assert summary['confidence_level'] > 0.95  # p=0.001 means >99% confidence
        mock_chi2.assert_called_once()
    
    def test_get_time_series_metrics(self, repository, mock_session):
        """Test getting time series metrics for variant performance over time"""
        # Arrange
        campaign_id, variant = 1, 'A'
        start_date = datetime.now() - timedelta(days=7)
        end_date = datetime.now()
        
        # Mock assignments with timestamps
        mock_assignments = [
            Mock(variant='A', sent_at=start_date + timedelta(days=1), response_received=True),
            Mock(variant='A', sent_at=start_date + timedelta(days=2), response_received=False),
            Mock(variant='A', sent_at=start_date + timedelta(days=3), response_received=True),
        ]
        
        mock_session.query.return_value.filter_by.return_value.filter.return_value.order_by.return_value.all.return_value = mock_assignments
        
        # Act
        result = repository.get_time_series_metrics(campaign_id, variant, start_date, end_date)
        
        # Assert
        assert result.is_success
        time_series = result.data
        
        assert 'daily_metrics' in time_series
        assert 'cumulative_metrics' in time_series
        assert len(time_series['daily_metrics']) > 0


class TestBulkOperations:
    """Test bulk operations for performance"""
    
    def test_bulk_assign_variants(self, repository, mock_session):
        """Test bulk assignment of variants to contacts"""
        # Arrange
        assignments = [
            {'campaign_id': 1, 'contact_id': 1, 'variant': 'A'},
            {'campaign_id': 1, 'contact_id': 2, 'variant': 'B'},
            {'campaign_id': 1, 'contact_id': 3, 'variant': 'A'},
        ]
        
        mock_session.bulk_insert_mappings = Mock()
        mock_session.commit = Mock()
        
        # Act
        result = repository.bulk_assign_variants(assignments)
        
        # Assert
        assert result.is_success
        assert result.data == 3  # Number of assignments created
        
        mock_session.bulk_insert_mappings.assert_called_once_with(ABTestResult, assignments)
        mock_session.commit.assert_called_once()
    
    def test_bulk_update_metrics(self, repository, mock_session):
        """Test bulk update of metrics"""
        # Arrange
        updates = [
            {'id': 1, 'message_opened': True, 'opened_at': datetime.now()},
            {'id': 2, 'link_clicked': True, 'clicked_at': datetime.now()},
            {'id': 3, 'response_received': True, 'response_type': 'positive', 'responded_at': datetime.now()},
        ]
        
        mock_session.bulk_update_mappings = Mock()
        mock_session.commit = Mock()
        
        # Act
        result = repository.bulk_update_metrics(updates)
        
        # Assert
        assert result.is_success
        assert result.data == 3  # Number of records updated
        
        mock_session.bulk_update_mappings.assert_called_once_with(ABTestResult, updates)
        mock_session.commit.assert_called_once()
    
    def test_bulk_operation_database_error(self, repository, mock_session):
        """Test handling of database error in bulk operations"""
        # Arrange
        assignments = [{'campaign_id': 1, 'contact_id': 1, 'variant': 'A'}]
        mock_session.bulk_insert_mappings = Mock()
        mock_session.commit.side_effect = SQLAlchemyError("Bulk insert failed")
        mock_session.rollback = Mock()
        
        # Act
        result = repository.bulk_assign_variants(assignments)
        
        # Assert
        assert result.is_failure
        assert "Bulk insert failed" in result.error
        assert result.error_code == "BULK_OPERATION_ERROR"
        mock_session.rollback.assert_called_once()


class TestDataIntegrity:
    """Test data integrity and validation"""
    
    def test_validate_variant_value(self, repository):
        """Test validation of variant values"""
        # Act & Assert - Valid variants
        assert repository._validate_variant('A') is True
        assert repository._validate_variant('B') is True
        
        # Invalid variants
        assert repository._validate_variant('C') is False
        assert repository._validate_variant('') is False
        assert repository._validate_variant(None) is False
        assert repository._validate_variant(123) is False
    
    def test_validate_response_type(self, repository):
        """Test validation of response types"""
        # Act & Assert - Valid response types
        assert repository._validate_response_type('positive') is True
        assert repository._validate_response_type('negative') is True
        assert repository._validate_response_type('neutral') is True
        
        # Invalid response types
        assert repository._validate_response_type('invalid') is False
        assert repository._validate_response_type('') is False
        assert repository._validate_response_type(None) is False
    
    def test_prevent_invalid_variant_assignment(self, repository, mock_session):
        """Test prevention of invalid variant assignment"""
        # Arrange
        campaign_id, contact_id, invalid_variant = 1, 1, 'X'
        
        # Act
        result = repository.assign_variant(campaign_id, contact_id, invalid_variant)
        
        # Assert
        assert result.is_failure
        assert "Invalid variant" in result.error
        assert result.error_code == "INVALID_VARIANT"
        
        # Should not attempt database operation
        mock_session.add.assert_not_called()
    
    def test_prevent_invalid_response_type_tracking(self, repository, mock_session, sample_ab_result):
        """Test prevention of invalid response type tracking"""
        # Arrange
        campaign_id, contact_id, variant = 1, 1, 'A'
        invalid_response_type = 'invalid_type'
        activity_id = 201
        
        mock_session.query.return_value.filter_by.return_value.first.return_value = sample_ab_result
        
        # Act
        result = repository.track_response_received(
            campaign_id, contact_id, variant, invalid_response_type, activity_id
        )
        
        # Assert
        assert result.is_failure
        assert "Invalid response type" in result.error
        assert result.error_code == "INVALID_RESPONSE_TYPE"
        
        # Should not commit changes
        mock_session.commit.assert_not_called()
    
    def test_cleanup_orphaned_assignments(self, repository, mock_session):
        """Test cleanup of assignments for deleted campaigns/contacts"""
        # Arrange
        mock_session.query.return_value.outerjoin.return_value.filter.return_value.delete.return_value = 5
        mock_session.commit = Mock()
        
        # Act
        result = repository.cleanup_orphaned_assignments()
        
        # Assert
        assert result.is_success
        assert result.data == 5  # Number of orphaned records cleaned up
        mock_session.commit.assert_called_once()
