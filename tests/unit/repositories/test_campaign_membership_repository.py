"""
Unit tests for CampaignMembershipRepository
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime, timedelta
from utils.datetime_utils import utc_now

from repositories.campaign_membership_repository import CampaignMembershipRepository
from crm_database import CampaignMembership


class TestCampaignMembershipRepository:
    """Test CampaignMembershipRepository implementation"""
    
    @pytest.fixture
    def mock_session(self):
        """Create mock database session"""
        return MagicMock()
    
    @pytest.fixture
    def repository(self, mock_session):
        """Create repository with mocked session"""
        return CampaignMembershipRepository(mock_session)
    
    def test_find_by_contact_and_campaign(self, repository, mock_session):
        """Test finding membership by contact and campaign IDs"""
        # Arrange
        mock_membership = Mock(spec=CampaignMembership)
        mock_membership.id = 1
        mock_membership.contact_id = 10
        mock_membership.campaign_id = 20
        
        mock_query = Mock()
        mock_query.filter_by.return_value = mock_query
        mock_query.first.return_value = mock_membership
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.find_by_contact_and_campaign(10, 20)
        
        # Assert
        assert result == mock_membership
        mock_session.query.assert_called_once_with(CampaignMembership)
        mock_query.filter_by.assert_called_once_with(contact_id=10, campaign_id=20)
    
    def test_find_active_memberships_for_contact(self, repository, mock_session):
        """Test finding active memberships within time window"""
        # Arrange
        mock_memberships = [
            Mock(id=1, status='sent', sent_at=utc_now() - timedelta(hours=24)),
            Mock(id=2, status='sent', sent_at=utc_now() - timedelta(hours=48))
        ]
        
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.all.return_value = mock_memberships
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.find_active_memberships_for_contact(contact_id=5, hours_window=72)
        
        # Assert
        assert result == mock_memberships
        assert len(result) == 2
        mock_session.query.assert_called_once_with(CampaignMembership)
    
    def test_find_by_sent_activity_id(self, repository, mock_session):
        """Test finding membership by sent activity ID"""
        # Arrange
        mock_membership = Mock(spec=CampaignMembership)
        mock_membership.sent_activity_id = 100
        
        mock_query = Mock()
        mock_query.filter_by.return_value = mock_query
        mock_query.first.return_value = mock_membership
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.find_by_sent_activity_id(100)
        
        # Assert
        assert result == mock_membership
        mock_query.filter_by.assert_called_once_with(sent_activity_id=100)
    
    def test_find_by_campaign_id(self, repository, mock_session):
        """Test finding all memberships for a campaign"""
        # Arrange
        mock_memberships = [Mock(id=1), Mock(id=2), Mock(id=3)]
        
        mock_query = Mock()
        mock_query.filter_by.return_value = mock_query
        mock_query.all.return_value = mock_memberships
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.find_by_campaign_id(campaign_id=15)
        
        # Assert
        assert result == mock_memberships
        assert len(result) == 3
        mock_query.filter_by.assert_called_once_with(campaign_id=15)
    
    def test_find_pending_for_campaign(self, repository, mock_session):
        """Test finding pending memberships for a campaign"""
        # Arrange
        mock_memberships = [Mock(id=1, status='pending'), Mock(id=2, status='pending')]
        
        mock_query = Mock()
        mock_query.filter_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = mock_memberships
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.find_pending_for_campaign(campaign_id=10, limit=50)
        
        # Assert
        assert result == mock_memberships
        mock_query.filter_by.assert_called_once_with(campaign_id=10, status='pending')
        mock_query.limit.assert_called_once_with(50)
    
    def test_update_membership_status(self, repository, mock_session):
        """Test updating membership status and fields"""
        # Arrange
        mock_membership = Mock(spec=CampaignMembership)
        mock_membership.id = 1
        mock_membership.status = 'pending'
        
        # Mock get_by_id from base repository
        with patch.object(repository, 'get_by_id', return_value=mock_membership):
            # Act
            result = repository.update_membership_status(
                membership_id=1,
                status='sent',
                sent_at=utc_now(),
                variant_sent='A'
            )
            
            # Assert
            assert result == mock_membership
            assert mock_membership.status == 'sent'
            assert hasattr(mock_membership, 'sent_at')
            assert hasattr(mock_membership, 'variant_sent')
            mock_session.commit.assert_called_once()
    
    def test_mark_as_replied_positive(self, repository, mock_session):
        """Test marking membership as replied with positive sentiment"""
        # Arrange
        mock_membership = Mock(spec=CampaignMembership)
        mock_membership.id = 1
        mock_membership.status = 'sent'
        mock_membership.reply_activity_id = None
        mock_membership.response_sentiment = None
        
        # Mock get_by_id from base repository
        with patch.object(repository, 'get_by_id', return_value=mock_membership):
            # Act
            result = repository.mark_as_replied(
                membership_id=1,
                reply_activity_id=200,
                sentiment='positive'
            )
            
            # Assert
            assert result == mock_membership
            assert mock_membership.reply_activity_id == 200
            assert mock_membership.response_sentiment == 'positive'
            assert mock_membership.status == 'replied_positive'
            mock_session.commit.assert_called_once()
    
    def test_mark_as_replied_negative(self, repository, mock_session):
        """Test marking membership as replied with negative sentiment"""
        # Arrange
        mock_membership = Mock(spec=CampaignMembership)
        mock_membership.id = 1
        
        # Mock get_by_id from base repository
        with patch.object(repository, 'get_by_id', return_value=mock_membership):
            # Act
            result = repository.mark_as_replied(
                membership_id=1,
                reply_activity_id=201,
                sentiment='negative'
            )
            
            # Assert
            assert mock_membership.response_sentiment == 'negative'
            assert mock_membership.status == 'replied_negative'
    
    def test_mark_as_replied_neutral(self, repository, mock_session):
        """Test marking membership as replied with neutral sentiment"""
        # Arrange
        mock_membership = Mock(spec=CampaignMembership)
        mock_membership.id = 1
        
        # Mock get_by_id from base repository
        with patch.object(repository, 'get_by_id', return_value=mock_membership):
            # Act
            result = repository.mark_as_replied(
                membership_id=1,
                reply_activity_id=202,
                sentiment='neutral'
            )
            
            # Assert
            assert mock_membership.response_sentiment == 'neutral'
            assert mock_membership.status == 'replied'
    
    def test_count_by_status(self, repository, mock_session):
        """Test counting memberships by status"""
        # Arrange
        mock_results = [
            ('pending', 10),
            ('sent', 25),
            ('replied_positive', 5),
            ('failed', 2)
        ]
        
        mock_query = Mock()
        mock_query.filter_by.return_value = mock_query
        mock_query.group_by.return_value = mock_query
        mock_query.all.return_value = mock_results
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.count_by_status(campaign_id=5)
        
        # Assert
        assert result == {
            'pending': 10,
            'sent': 25,
            'replied_positive': 5,
            'failed': 2
        }
        mock_query.filter_by.assert_called_once_with(campaign_id=5)
    
    def test_find_recent_replies(self, repository, mock_session):
        """Test finding recent replies for a campaign"""
        # Arrange
        mock_memberships = [
            Mock(id=1, reply_activity_id=100),
            Mock(id=2, reply_activity_id=101)
        ]
        
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = mock_memberships
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.find_recent_replies(campaign_id=7, limit=20)
        
        # Assert
        assert result == mock_memberships
        assert len(result) == 2
        mock_query.limit.assert_called_once_with(20)