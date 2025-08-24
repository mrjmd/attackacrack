"""
Tests for CampaignRepository dashboard-specific methods  
These tests are written FIRST (TDD RED phase) before implementing the methods
"""

import pytest
from datetime import datetime, timedelta
from utils.datetime_utils import utc_now
from repositories.campaign_repository import CampaignRepository
from crm_database import Campaign, CampaignMembership, Contact
from tests.conftest import create_test_contact


class TestCampaignRepositoryDashboardEnhancements:
    """Test dashboard-specific methods for CampaignRepository"""
    
    @pytest.fixture
    def repository(self, db_session):
        """Create CampaignRepository instance"""
        return CampaignRepository(session=db_session)
    
    def test_get_active_campaigns_count(self, repository, db_session):
        """Test getting count of running/active campaigns"""
        # Arrange - create campaigns with different statuses
        running_campaign1 = Campaign(
            name='Campaign 1',
            status='running',
            campaign_type='blast',
            channel='sms'
        )
        running_campaign2 = Campaign(
            name='Campaign 2', 
            status='running',
            campaign_type='blast',
            channel='sms'
        )
        draft_campaign = Campaign(
            name='Draft Campaign',
            status='draft',
            campaign_type='blast', 
            channel='sms'
        )
        completed_campaign = Campaign(
            name='Completed Campaign',
            status='completed',
            campaign_type='blast',
            channel='sms'
        )
        
        db_session.add_all([
            running_campaign1, running_campaign2, 
            draft_campaign, completed_campaign
        ])
        db_session.commit()
        
        # Act
        result = repository.get_active_campaigns_count()
        
        # Assert
        assert result == 2
    
    def test_get_recent_campaigns_with_limit(self, repository, db_session):
        """Test getting recent campaigns with limit"""
        # Arrange - create campaigns with different creation dates
        old_date = utc_now() - timedelta(days=10)
        recent_date = utc_now() - timedelta(days=1)
        
        old_campaign = Campaign(
            name='Old Campaign',
            status='completed',
            campaign_type='blast',
            channel='sms', 
            created_at=old_date
        )
        recent_campaign1 = Campaign(
            name='Recent Campaign 1',
            status='running',
            campaign_type='blast',
            channel='sms',
            created_at=recent_date
        )
        recent_campaign2 = Campaign(
            name='Recent Campaign 2', 
            status='draft',
            campaign_type='blast',
            channel='sms',
            created_at=recent_date
        )
        
        db_session.add_all([old_campaign, recent_campaign1, recent_campaign2])
        db_session.commit()
        
        # Act
        result = repository.get_recent_campaigns_with_limit(limit=2)
        
        # Assert
        assert len(result) == 2
        # Should be ordered by created_at desc
        assert result[0].created_at >= result[1].created_at
        
    def test_calculate_average_campaign_response_rate(self, repository, db_session):
        """Test calculating average response rate across all campaigns"""
        # Arrange - create campaigns with memberships 
        campaign1 = Campaign(
            name='Campaign 1',
            status='completed',
            campaign_type='blast',
            channel='sms'
        )
        campaign2 = Campaign(
            name='Campaign 2',
            status='completed', 
            campaign_type='blast',
            channel='sms'
        )
        db_session.add_all([campaign1, campaign2])
        db_session.commit()
        
        # Create contacts
        contact1 = create_test_contact(phone='+11234567890')
        contact2 = create_test_contact(phone='+11234567891')
        contact3 = create_test_contact(phone='+11234567892')
        contact4 = create_test_contact(phone='+11234567893')
        db_session.add_all([contact1, contact2, contact3, contact4])
        db_session.commit()
        
        # Campaign 1: 2 sent, 1 replied = 50% response rate
        membership1 = CampaignMembership(
            campaign_id=campaign1.id,
            contact_id=contact1.id,
            status='sent'
        )
        membership2 = CampaignMembership(
            campaign_id=campaign1.id,
            contact_id=contact2.id, 
            status='replied_positive'
        )
        
        # Campaign 2: 2 sent, 0 replied = 0% response rate  
        membership3 = CampaignMembership(
            campaign_id=campaign2.id,
            contact_id=contact3.id,
            status='sent'
        )
        membership4 = CampaignMembership(
            campaign_id=campaign2.id,
            contact_id=contact4.id,
            status='sent'
        )
        
        db_session.add_all([membership1, membership2, membership3, membership4])
        db_session.commit()
        
        # Act
        result = repository.calculate_average_campaign_response_rate()
        
        # Assert - (50% + 0%) / 2 = 25%
        assert result == 25.0
        
    def test_calculate_average_campaign_response_rate_no_campaigns(self, repository):
        """Test average response rate with no campaigns"""
        # Act
        result = repository.calculate_average_campaign_response_rate()
        
        # Assert
        assert result == 0
        
    def test_calculate_average_campaign_response_rate_no_sent_messages(self, repository, db_session):
        """Test average response rate with campaigns but no sent messages"""
        # Arrange
        campaign = Campaign(
            name='Draft Campaign',
            status='draft',
            campaign_type='blast',
            channel='sms'
        )
        db_session.add(campaign)
        db_session.commit()
        
        contact = create_test_contact(phone='+11234567890')
        db_session.add(contact)
        db_session.commit()
        
        # Membership in pending status (not sent)
        membership = CampaignMembership(
            campaign_id=campaign.id,
            contact_id=contact.id,
            status='pending'
        )
        db_session.add(membership)
        db_session.commit()
        
        # Act
        result = repository.calculate_average_campaign_response_rate()
        
        # Assert
        assert result == 0
        
    def test_get_pending_campaign_queue_size(self, repository, db_session):
        """Test getting count of pending campaign messages"""
        # Arrange
        campaign = Campaign(
            name='Active Campaign',
            status='running',
            campaign_type='blast', 
            channel='sms'
        )
        db_session.add(campaign)
        db_session.commit()
        
        contact1 = create_test_contact(phone='+11234567890')
        contact2 = create_test_contact(phone='+11234567891')
        contact3 = create_test_contact(phone='+11234567892')
        db_session.add_all([contact1, contact2, contact3])
        db_session.commit()
        
        # Create memberships with different statuses
        pending1 = CampaignMembership(
            campaign_id=campaign.id,
            contact_id=contact1.id,
            status='pending'
        )
        pending2 = CampaignMembership(
            campaign_id=campaign.id,
            contact_id=contact2.id,
            status='pending'
        )
        sent = CampaignMembership(
            campaign_id=campaign.id,
            contact_id=contact3.id,
            status='sent'
        )
        
        db_session.add_all([pending1, pending2, sent])
        db_session.commit()
        
        # Act
        result = repository.get_pending_campaign_queue_size()
        
        # Assert
        assert result == 2  # Only pending messages