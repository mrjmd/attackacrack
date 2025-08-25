"""
Tests for ConversionRepository - P4-03 Conversion Tracking Data Layer
TDD RED PHASE - These tests are written FIRST before implementation
All tests should FAIL initially to ensure proper TDD workflow

Test Coverage:
- Conversion event recording and retrieval
- Conversion rate calculations
- ROI calculations
- Multi-touch attribution queries
- Conversion funnel analysis
- Time-to-conversion analytics
- Conversion value tracking
- Edge cases and error handling
"""

import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock, MagicMock, patch
from sqlalchemy.exc import SQLAlchemyError

from repositories.conversion_repository import ConversionRepository
from repositories.base_repository import PaginationParams, PaginatedResult, SortOrder
from crm_database import (
    ConversionEvent, Contact, Campaign, CampaignMembership, CampaignResponse
)
from utils.datetime_utils import utc_now


class TestConversionRepository:
    """Test ConversionRepository data access functionality"""
    
    @pytest.fixture
    def mock_session(self):
        """Create mock database session"""
        return Mock()
    
    @pytest.fixture
    def repository(self, mock_session):
        """Create repository instance with mocked dependencies"""
        return ConversionRepository(session=mock_session)
    
    @pytest.fixture
    def sample_conversion_data(self):
        """Sample conversion event data for testing"""
        return {
            'contact_id': 1,
            'campaign_id': 1,
            'conversion_type': 'purchase',
            'conversion_value': Decimal('150.00'),
            'currency': 'USD',
            'converted_at': utc_now(),
            'attribution_model': 'last_touch',
            'conversion_metadata': {
                'product_id': 'P123',
                'channel': 'sms',
                'source_campaign_membership_id': 1
            }
        }
    
    # ===== Basic CRUD Operations =====
    
    def test_create_conversion_event_success(self, repository, mock_session, sample_conversion_data):
        """Test creating a new conversion event"""
        # Arrange
        mock_conversion = Mock(spec=ConversionEvent)
        mock_conversion.id = 1
        mock_conversion.contact_id = sample_conversion_data['contact_id']
        mock_conversion.conversion_type = sample_conversion_data['conversion_type']
        mock_conversion.conversion_value = sample_conversion_data['conversion_value']
        
        mock_session.add.return_value = None
        mock_session.commit.return_value = None
        mock_session.flush.return_value = None
        
        # Mock the constructor to return our mock object
        with patch('repositories.conversion_repository.ConversionEvent', return_value=mock_conversion):
            # Act
            result = repository.create_conversion_event(sample_conversion_data)
            
            # Assert
            assert result == mock_conversion
            mock_session.add.assert_called_once_with(mock_conversion)
            mock_session.flush.assert_called_once()
    
    def test_create_conversion_event_validation_error(self, repository):
        """Test creation fails with invalid data"""
        # Arrange
        invalid_data = {
            'contact_id': None,  # Invalid - required field
            'conversion_type': 'purchase'
        }
        
        # Act & Assert
        with pytest.raises(ValueError, match="Contact ID is required"):
            repository.create_conversion_event(invalid_data)
    
    def test_create_conversion_event_negative_value_error(self, repository):
        """Test creation fails with negative conversion value"""
        # Arrange
        invalid_data = {
            'contact_id': 1,
            'conversion_type': 'purchase',
            'conversion_value': Decimal('-50.00')  # Invalid - negative value
        }
        
        # Act & Assert
        with pytest.raises(ValueError, match="Conversion value must be positive"):
            repository.create_conversion_event(invalid_data)
    
    def test_get_by_id_found(self, repository, mock_session):
        """Test retrieving conversion by ID when found"""
        # Arrange
        conversion_id = 1
        expected_conversion = Mock(spec=ConversionEvent)
        expected_conversion.id = conversion_id
        
        mock_query = Mock()
        mock_session.query.return_value = mock_query
        mock_query.get.return_value = expected_conversion
        
        # Act
        result = repository.get_by_id(conversion_id)
        
        # Assert
        assert result == expected_conversion
        mock_session.query.assert_called_once_with(ConversionEvent)
        mock_query.get.assert_called_once_with(conversion_id)
    
    def test_get_by_id_not_found(self, repository, mock_session):
        """Test retrieving conversion by ID when not found"""
        # Arrange
        conversion_id = 999
        
        mock_query = Mock()
        mock_session.query.return_value = mock_query
        mock_query.get.return_value = None
        
        # Act
        result = repository.get_by_id(conversion_id)
        
        # Assert
        assert result is None
        mock_session.query.assert_called_once_with(ConversionEvent)
        mock_query.get.assert_called_once_with(conversion_id)
    
    # ===== Query Methods for Analytics =====
    
    def test_get_conversions_for_contact(self, repository, mock_session):
        """Test retrieving all conversions for a specific contact"""
        # Arrange
        contact_id = 1
        expected_conversions = [
            Mock(spec=ConversionEvent, contact_id=contact_id),
            Mock(spec=ConversionEvent, contact_id=contact_id)
        ]
        
        mock_query = Mock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.all.return_value = expected_conversions
        
        # Act
        result = repository.get_conversions_for_contact(contact_id)
        
        # Assert
        assert result == expected_conversions
        mock_session.query.assert_called_once_with(ConversionEvent)
        # Verify filter was called for contact_id
        mock_query.filter.assert_called()
        mock_query.order_by.assert_called()
        mock_query.all.assert_called_once()
    
    def test_get_conversions_for_campaign(self, repository, mock_session):
        """Test retrieving all conversions for a specific campaign"""
        # Arrange
        campaign_id = 1
        date_from = utc_now() - timedelta(days=30)
        date_to = utc_now()
        
        expected_conversions = [
            Mock(spec=ConversionEvent, campaign_id=campaign_id),
            Mock(spec=ConversionEvent, campaign_id=campaign_id)
        ]
        
        mock_query = Mock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.all.return_value = expected_conversions
        
        # Act
        result = repository.get_conversions_for_campaign(
            campaign_id=campaign_id,
            date_from=date_from,
            date_to=date_to
        )
        
        # Assert
        assert result == expected_conversions
        mock_session.query.assert_called_once_with(ConversionEvent)
        # Should have multiple filter calls (campaign_id, date range)
        assert mock_query.filter.call_count >= 2
        mock_query.all.assert_called_once()
    
    def test_get_conversions_by_type(self, repository, mock_session):
        """Test retrieving conversions filtered by conversion type"""
        # Arrange
        conversion_type = 'purchase'
        expected_conversions = [
            Mock(spec=ConversionEvent, conversion_type=conversion_type),
            Mock(spec=ConversionEvent, conversion_type=conversion_type)
        ]
        
        mock_query = Mock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.all.return_value = expected_conversions
        
        # Act
        result = repository.get_conversions_by_type(conversion_type)
        
        # Assert
        assert result == expected_conversions
        mock_session.query.assert_called_once_with(ConversionEvent)
        mock_query.filter.assert_called()
        mock_query.all.assert_called_once()
    
    # ===== Conversion Rate Analytics =====
    
    def test_calculate_conversion_rate_for_campaign(self, repository, mock_session):
        """Test calculating conversion rate for a campaign"""
        # Arrange
        campaign_id = 1
        
        # Mock the raw SQL query result
        mock_result = Mock()
        mock_result.fetchone.return_value = (500, 75, 0.15)  # total_sent, total_conversions, conversion_rate
        mock_session.execute.return_value = mock_result
        
        # Act
        result = repository.calculate_conversion_rate_for_campaign(campaign_id)
        
        # Assert
        assert result['campaign_id'] == campaign_id
        assert result['total_sent'] == 500
        assert result['total_conversions'] == 75
        assert result['conversion_rate'] == 0.15
        assert result['calculated_at'] is not None
        
        mock_session.execute.assert_called_once()
    
    def test_calculate_conversion_rate_no_data(self, repository, mock_session):
        """Test conversion rate calculation with no campaign data"""
        # Arrange
        campaign_id = 999  # Non-existent campaign
        
        # Mock empty result
        mock_result = Mock()
        mock_result.fetchone.return_value = (0, 0, 0.0)
        mock_session.execute.return_value = mock_result
        
        # Act
        result = repository.calculate_conversion_rate_for_campaign(campaign_id)
        
        # Assert
        assert result['campaign_id'] == campaign_id
        assert result['total_sent'] == 0
        assert result['total_conversions'] == 0
        assert result['conversion_rate'] == 0.0
    
    def test_get_conversion_rates_by_time_period(self, repository, mock_session):
        """Test getting conversion rates grouped by time period"""
        # Arrange
        campaign_id = 1
        date_from = utc_now() - timedelta(days=30)
        date_to = utc_now()
        group_by = 'day'
        
        # Mock time-series result
        mock_result = Mock()
        mock_result.fetchall.return_value = [
            ('2025-08-20', 50, 8, 0.16),
            ('2025-08-21', 45, 5, 0.11),
            ('2025-08-22', 60, 12, 0.20)
        ]
        mock_session.execute.return_value = mock_result
        
        # Act
        result = repository.get_conversion_rates_by_time_period(
            campaign_id=campaign_id,
            date_from=date_from,
            date_to=date_to,
            group_by=group_by
        )
        
        # Assert
        assert len(result) == 3
        assert result[0]['period'] == '2025-08-20'
        assert result[0]['total_sent'] == 50
        assert result[0]['conversions'] == 8
        assert result[0]['conversion_rate'] == 0.16
        
        mock_session.execute.assert_called_once()
    
    # ===== ROI Calculation =====
    
    def test_calculate_campaign_roi(self, repository, mock_session):
        """Test calculating ROI for a campaign"""
        # Arrange
        campaign_id = 1
        campaign_cost = Decimal('2000.00')
        
        # Mock ROI calculation result
        mock_result = Mock()
        mock_result.fetchone.return_value = (Decimal('3500.00'), 25, Decimal('140.00'))  # total_revenue, conversion_count, avg_conversion_value
        mock_session.execute.return_value = mock_result
        
        # Act
        result = repository.calculate_campaign_roi(campaign_id, campaign_cost)
        
        # Assert
        assert result['campaign_id'] == campaign_id
        assert result['total_revenue'] == Decimal('3500.00')
        assert result['campaign_cost'] == campaign_cost
        assert result['profit'] == Decimal('1500.00')  # 3500 - 2000
        assert result['roi'] == Decimal('0.75')  # 1500 / 2000
        assert result['conversion_count'] == 25
        assert result['average_conversion_value'] == Decimal('140.00')
        
        mock_session.execute.assert_called_once()
    
    def test_calculate_campaign_roi_no_conversions(self, repository, mock_session):
        """Test ROI calculation with no conversions"""
        # Arrange
        campaign_id = 1
        campaign_cost = Decimal('1000.00')
        
        # Mock no conversions
        mock_result = Mock()
        mock_result.fetchone.return_value = (Decimal('0.00'), 0, Decimal('0.00'))
        mock_session.execute.return_value = mock_result
        
        # Act
        result = repository.calculate_campaign_roi(campaign_id, campaign_cost)
        
        # Assert
        assert result['campaign_id'] == campaign_id
        assert result['total_revenue'] == Decimal('0.00')
        assert result['campaign_cost'] == campaign_cost
        assert result['profit'] == Decimal('-1000.00')  # Loss
        assert result['roi'] == Decimal('-1.00')  # -100% ROI
        assert result['conversion_count'] == 0
    
    # ===== Multi-Touch Attribution =====
    
    def test_get_conversions_with_attribution_path(self, repository, mock_session):
        """Test retrieving conversions with their attribution touchpoints"""
        # Arrange
        conversion_id = 1
        
        # Mock complex join query result
        mock_result = Mock()
        mock_result.fetchall.return_value = [
            {
                'conversion_id': 1,
                'contact_id': 1,
                'conversion_type': 'purchase',
                'conversion_value': Decimal('200.00'),
                'touchpoint_campaign_id': 1,
                'touchpoint_type': 'sms',
                'touchpoint_timestamp': utc_now() - timedelta(days=5),
                'attribution_weight': 0.4
            },
            {
                'conversion_id': 1,
                'contact_id': 1,
                'conversion_type': 'purchase',
                'conversion_value': Decimal('200.00'),
                'touchpoint_campaign_id': 2,
                'touchpoint_type': 'email',
                'touchpoint_timestamp': utc_now() - timedelta(days=2),
                'attribution_weight': 0.6
            }
        ]
        mock_session.execute.return_value = mock_result
        
        # Act
        result = repository.get_conversions_with_attribution_path(conversion_id)
        
        # Assert
        assert len(result) == 2
        assert result[0]['conversion_id'] == 1
        assert result[0]['touchpoint_type'] == 'sms'
        assert result[0]['attribution_weight'] == 0.4
        assert result[1]['touchpoint_type'] == 'email'
        assert result[1]['attribution_weight'] == 0.6
        
        mock_session.execute.assert_called_once()
    
    def test_calculate_attribution_weights_linear_model(self, repository, mock_session):
        """Test calculating attribution weights using linear model"""
        # Arrange
        contact_id = 1
        conversion_timestamp = utc_now()
        attribution_window_days = 30
        
        # Mock touchpoints query
        mock_result = Mock()
        mock_result.fetchall.return_value = [
            {
                'campaign_id': 1,
                'activity_timestamp': conversion_timestamp - timedelta(days=20),
                'activity_type': 'sms'
            },
            {
                'campaign_id': 2,
                'activity_timestamp': conversion_timestamp - timedelta(days=10),
                'activity_type': 'email'
            },
            {
                'campaign_id': 3,
                'activity_timestamp': conversion_timestamp - timedelta(days=2),
                'activity_type': 'call'
            }
        ]
        mock_session.execute.return_value = mock_result
        
        # Act
        result = repository.calculate_attribution_weights(
            contact_id=contact_id,
            conversion_timestamp=conversion_timestamp,
            attribution_model='linear',
            attribution_window_days=attribution_window_days
        )
        
        # Assert
        assert len(result) == 3
        # Linear attribution should give equal weight
        for weight in result.values():
            assert abs(weight - 0.333) < 0.001  # ~1/3 each
        
        mock_session.execute.assert_called_once()
    
    def test_calculate_attribution_weights_time_decay_model(self, repository, mock_session):
        """Test calculating attribution weights using time-decay model"""
        # Arrange
        contact_id = 1
        conversion_timestamp = utc_now()
        
        # Mock touchpoints - more recent should get higher weight
        mock_result = Mock()
        mock_result.fetchall.return_value = [
            {
                'campaign_id': 1,
                'activity_timestamp': conversion_timestamp - timedelta(days=20),
                'activity_type': 'sms'
            },
            {
                'campaign_id': 2,
                'activity_timestamp': conversion_timestamp - timedelta(days=2),
                'activity_type': 'email'
            }
        ]
        mock_session.execute.return_value = mock_result
        
        # Act
        result = repository.calculate_attribution_weights(
            contact_id=contact_id,
            conversion_timestamp=conversion_timestamp,
            attribution_model='time_decay',
            attribution_window_days=30
        )
        
        # Assert
        assert len(result) == 2
        # More recent touchpoint should have higher weight
        assert result[2] > result[1]  # Campaign 2 more recent than Campaign 1
        # Weights should sum to 1
        assert abs(sum(result.values()) - 1.0) < 0.001
    
    # ===== Conversion Funnel Analysis =====
    
    def test_get_conversion_funnel_data(self, repository, mock_session):
        """Test retrieving conversion funnel data for analysis"""
        # Arrange
        campaign_id = 1
        
        # Mock funnel query result
        mock_result = Mock()
        mock_result.fetchall.return_value = [
            {
                'stage': 'sent',
                'count': 1000,
                'cumulative_count': 1000,
                'stage_conversion_rate': 1.0
            },
            {
                'stage': 'delivered',
                'count': 970,
                'cumulative_count': 970,
                'stage_conversion_rate': 0.97
            },
            {
                'stage': 'engaged',
                'count': 450,
                'cumulative_count': 450,
                'stage_conversion_rate': 0.464
            },
            {
                'stage': 'responded',
                'count': 180,
                'cumulative_count': 180,
                'stage_conversion_rate': 0.4
            },
            {
                'stage': 'converted',
                'count': 25,
                'cumulative_count': 25,
                'stage_conversion_rate': 0.139
            }
        ]
        mock_session.execute.return_value = mock_result
        
        # Act
        result = repository.get_conversion_funnel_data(campaign_id)
        
        # Assert
        assert len(result) == 5
        assert result[0]['stage'] == 'sent'
        assert result[0]['count'] == 1000
        assert result[4]['stage'] == 'converted'
        assert result[4]['count'] == 25
        # Overall conversion rate should be 25/1000 = 0.025
        assert result[4]['stage_conversion_rate'] == 0.139
        
        mock_session.execute.assert_called_once()
    
    def test_identify_funnel_drop_off_points(self, repository, mock_session):
        """Test identifying major drop-off points in conversion funnel"""
        # Arrange
        campaign_id = 1
        
        # Mock the get_conversion_funnel_data method since identify_funnel_drop_off_points calls it
        with patch.object(repository, 'get_conversion_funnel_data') as mock_funnel_data:
            mock_funnel_data.return_value = [
                {
                    'stage': 'sent',
                    'count': 1000,
                    'cumulative_count': 1000,
                    'stage_conversion_rate': 1.0
                },
                {
                    'stage': 'delivered',
                    'count': 970,
                    'cumulative_count': 970,
                    'stage_conversion_rate': 0.97
                },
                {
                    'stage': 'engaged',
                    'count': 450,
                    'cumulative_count': 450,
                    'stage_conversion_rate': 0.464
                },
                {
                    'stage': 'responded',
                    'count': 180,
                    'cumulative_count': 180,
                    'stage_conversion_rate': 0.4
                },
                {
                    'stage': 'converted',
                    'count': 25,
                    'cumulative_count': 25,
                    'stage_conversion_rate': 0.139
                }
            ]
            
            # Act
            result = repository.identify_funnel_drop_off_points(campaign_id)
            
            # Assert
            assert len(result) == 4  # 4 transitions between 5 stages
            # Find the critical drop-off point (from responded to converted)
            critical_drop_off = next((item for item in result if item['from_stage'] == 'responded'), None)
            assert critical_drop_off is not None
            assert critical_drop_off['to_stage'] == 'converted'
            assert critical_drop_off['drop_off_count'] == 155  # 180 - 25
            assert critical_drop_off['severity'] == 'critical'  # > 0.8 drop-off rate
            
            mock_funnel_data.assert_called_once_with(campaign_id)
    
    # ===== Time-to-Conversion Analysis =====
    
    def test_calculate_average_time_to_conversion(self, repository, mock_session):
        """Test calculating average time from first touch to conversion"""
        # Arrange
        campaign_id = 1
        
        # Mock time-to-conversion query
        mock_result = Mock()
        mock_result.fetchone.return_value = (
            72.5,  # average_hours
            3.02,  # average_days
            120,   # median_hours
            48,    # min_hours
            240    # max_hours
        )
        mock_session.execute.return_value = mock_result
        
        # Act
        result = repository.calculate_average_time_to_conversion(campaign_id)
        
        # Assert
        assert result['campaign_id'] == campaign_id
        assert result['average_hours'] == 72.5
        assert result['average_days'] == 3.02
        assert result['median_hours'] == 120
        assert result['min_hours'] == 48
        assert result['max_hours'] == 240
        
        mock_session.execute.assert_called_once()
    
    def test_get_time_to_conversion_distribution(self, repository, mock_session):
        """Test getting distribution of conversion times"""
        # Arrange
        campaign_id = 1
        
        # Mock distribution query
        mock_result = Mock()
        mock_result.fetchall.return_value = [
            {'time_bucket': '0-1 hours', 'conversion_count': 5, 'percentage': 0.20},
            {'time_bucket': '1-6 hours', 'conversion_count': 8, 'percentage': 0.32},
            {'time_bucket': '6-24 hours', 'conversion_count': 7, 'percentage': 0.28},
            {'time_bucket': '1-7 days', 'conversion_count': 4, 'percentage': 0.16},
            {'time_bucket': '7+ days', 'conversion_count': 1, 'percentage': 0.04}
        ]
        mock_session.execute.return_value = mock_result
        
        # Act
        result = repository.get_time_to_conversion_distribution(campaign_id)
        
        # Assert
        assert len(result) == 5
        assert result[0]['time_bucket'] == '0-1 hours'
        assert result[0]['conversion_count'] == 5
        assert result[0]['percentage'] == 0.20
        # Percentages should sum to 1.0
        total_percentage = sum(item['percentage'] for item in result)
        assert abs(total_percentage - 1.0) < 0.001
        
        mock_session.execute.assert_called_once()
    
    # ===== Conversion Value Analytics =====
    
    def test_get_conversion_value_statistics(self, repository, mock_session):
        """Test calculating conversion value statistics"""
        # Arrange
        campaign_id = 1
        conversion_type = 'purchase'
        
        # Mock value statistics query
        mock_result = Mock()
        mock_result.fetchone.return_value = (
            Decimal('156.75'),  # average_value
            Decimal('125.00'),  # median_value
            Decimal('3134.00'), # total_value
            Decimal('25.00'),   # min_value
            Decimal('450.00'),  # max_value
            Decimal('87.25'),   # std_deviation
            20                  # conversion_count
        )
        mock_session.execute.return_value = mock_result
        
        # Act
        result = repository.get_conversion_value_statistics(campaign_id, conversion_type)
        
        # Assert
        assert result['campaign_id'] == campaign_id
        assert result['conversion_type'] == conversion_type
        assert result['average_value'] == Decimal('156.75')
        assert result['median_value'] == Decimal('125.00')
        assert result['total_value'] == Decimal('3134.00')
        assert result['min_value'] == Decimal('25.00')
        assert result['max_value'] == Decimal('450.00')
        assert result['std_deviation'] == Decimal('87.25')
        assert result['conversion_count'] == 20
        
        mock_session.execute.assert_called_once()
    
    def test_get_high_value_conversions(self, repository, mock_session):
        """Test retrieving high-value conversions above threshold"""
        # Arrange
        campaign_id = 1
        value_threshold = Decimal('200.00')
        
        expected_conversions = [
            Mock(spec=ConversionEvent, conversion_value=Decimal('250.00')),
            Mock(spec=ConversionEvent, conversion_value=Decimal('300.00')),
            Mock(spec=ConversionEvent, conversion_value=Decimal('450.00'))
        ]
        
        mock_query = Mock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.all.return_value = expected_conversions
        
        # Act
        result = repository.get_high_value_conversions(campaign_id, value_threshold)
        
        # Assert
        assert result == expected_conversions
        mock_session.query.assert_called_once_with(ConversionEvent)
        # Should have filters for campaign_id and value threshold
        assert mock_query.filter.call_count >= 2
        mock_query.order_by.assert_called_once()
        mock_query.all.assert_called_once()
    
    # ===== Error Handling and Edge Cases =====
    
    def test_create_conversion_event_database_error(self, repository, mock_session, sample_conversion_data):
        """Test handling database errors during conversion creation"""
        # Arrange
        mock_session.add.side_effect = SQLAlchemyError("Database connection failed")
        
        # Act & Assert
        with pytest.raises(SQLAlchemyError):
            repository.create_conversion_event(sample_conversion_data)
    
    def test_calculate_conversion_rate_query_error(self, repository, mock_session):
        """Test handling query errors during conversion rate calculation"""
        # Arrange
        campaign_id = 1
        mock_session.execute.side_effect = SQLAlchemyError("Query failed")
        
        # Act & Assert
        with pytest.raises(SQLAlchemyError):
            repository.calculate_conversion_rate_for_campaign(campaign_id)
    
    def test_get_conversions_for_campaign_invalid_date_range(self, repository):
        """Test handling invalid date range in campaign conversions query"""
        # Arrange
        campaign_id = 1
        date_from = utc_now()
        date_to = utc_now() - timedelta(days=1)  # Invalid: from > to
        
        # Act & Assert
        with pytest.raises(ValueError, match="date_from must be before date_to"):
            repository.get_conversions_for_campaign(
                campaign_id=campaign_id,
                date_from=date_from,
                date_to=date_to
            )
    
    def test_calculate_attribution_weights_invalid_model(self, repository):
        """Test handling invalid attribution model"""
        # Arrange
        contact_id = 1
        conversion_timestamp = utc_now()
        
        # Act & Assert
        with pytest.raises(ValueError, match="Unsupported attribution model"):
            repository.calculate_attribution_weights(
                contact_id=contact_id,
                conversion_timestamp=conversion_timestamp,
                attribution_model='invalid_model'
            )
    
    def test_validate_conversion_type_valid_types(self, repository):
        """Test validation of conversion types"""
        # Valid conversion types should not raise errors
        valid_types = ['purchase', 'appointment_booked', 'quote_requested', 'lead_qualified', 'custom']
        
        for conversion_type in valid_types:
            # Should not raise an exception
            repository._validate_conversion_type(conversion_type)
    
    def test_validate_conversion_type_invalid_type(self, repository):
        """Test validation rejects invalid conversion types"""
        # Act & Assert
        with pytest.raises(ValueError, match="Invalid conversion type"):
            repository._validate_conversion_type('invalid_type')
    
    # ===== Pagination and Bulk Operations =====
    
    def test_get_conversions_paginated(self, repository, mock_session):
        """Test paginated retrieval of conversions"""
        # Arrange
        campaign_id = 1
        pagination = PaginationParams(page=1, per_page=10)
        
        # Mock paginated query
        expected_conversions = [Mock(spec=ConversionEvent) for _ in range(10)]
        mock_query = Mock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = expected_conversions
        
        # Mock count separately - create a fresh query mock for count
        mock_count_query = Mock()
        mock_count_query.count.return_value = 25
        mock_query.count.return_value = 25  # Set count on the same query object
        
        # Act
        result = repository.get_conversions_paginated(campaign_id, pagination)
        
        # Assert
        assert isinstance(result, PaginatedResult)
        assert result.items == expected_conversions
        assert result.total == 25
        assert result.page == 1
        assert result.per_page == 10
        
        mock_session.query.assert_called()
        mock_query.offset.assert_called_with(0)  # page 1 offset
        mock_query.limit.assert_called_with(10)
    
    def test_bulk_create_conversion_events(self, repository, mock_session):
        """Test bulk creation of multiple conversion events"""
        # Arrange
        conversion_events_data = [
            {
                'contact_id': 1,
                'campaign_id': 1,
                'conversion_type': 'purchase',
                'conversion_value': Decimal('100.00'),
                'converted_at': utc_now()
            },
            {
                'contact_id': 2,
                'campaign_id': 1,
                'conversion_type': 'appointment_booked',
                'conversion_value': Decimal('0.00'),
                'converted_at': utc_now()
            }
        ]
        
        mock_session.bulk_insert_mappings.return_value = None
        mock_session.commit.return_value = None
        
        # Act
        result = repository.bulk_create_conversion_events(conversion_events_data)
        
        # Assert
        assert result == 2  # Number of events created
        mock_session.bulk_insert_mappings.assert_called_once()
        mock_session.commit.assert_called_once()
    
    def test_delete_conversions_for_contact(self, repository, mock_session):
        """Test deleting all conversions for a contact (GDPR compliance)"""
        # Arrange
        contact_id = 1
        
        mock_query = Mock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.delete.return_value = 3  # Number of deleted records
        mock_session.commit.return_value = None
        
        # Act
        result = repository.delete_conversions_for_contact(contact_id)
        
        # Assert
        assert result == 3
        mock_session.query.assert_called_once_with(ConversionEvent)
        mock_query.filter.assert_called_once()
        mock_query.delete.assert_called_once()
        mock_session.commit.assert_called_once()