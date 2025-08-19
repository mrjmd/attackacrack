"""
TDD RED Phase: Tests for CampaignRepository SMS Metrics Enhancement  
These tests MUST FAIL initially - testing new methods needed for SMSMetricsService refactoring
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
from repositories.campaign_repository import CampaignRepository
from crm_database import Campaign, CampaignMembership, Contact


class TestCampaignRepositorySMSMetricsEnhancement:
    """Test SMS metrics-specific methods for CampaignRepository"""
    
    @pytest.fixture
    def repository(self, db_session):
        """Create CampaignRepository instance"""
        return CampaignRepository(session=db_session, model_class=Campaign)
    
    @pytest.fixture
    def sample_campaign_with_memberships(self, db_session):
        """Create sample campaign with memberships for testing"""
        # Create campaign
        campaign = Campaign(
            name='Test SMS Campaign',
            campaign_type='blast',
            channel='sms',
            status='active'
        )
        db_session.add(campaign)
        db_session.flush()
        
        # Create contacts
        contacts = []
        for i in range(5):
            contact = Contact(
                phone=f'+1555000{i:04d}',
                first_name=f'Contact{i}',
                last_name='User'
            )
            contacts.append(contact)
            db_session.add(contact)
        
        db_session.flush()
        
        # Create memberships with different statuses
        memberships = []
        statuses = ['sent', 'delivered', 'failed', 'replied_positive', 'opted_out']
        
        for i, (contact, status) in enumerate(zip(contacts, statuses)):
            membership = CampaignMembership(
                campaign_id=campaign.id,
                contact_id=contact.id,
                status=status,
                sent_at=datetime.utcnow() - timedelta(hours=i) if status != 'pending' else None,
                variant_sent='A' if i % 2 == 0 else 'B'
            )
            memberships.append(membership)
            db_session.add(membership)
        
        db_session.flush()
        return campaign, memberships, contacts
    
    def test_get_campaign_metrics_with_bounce_analysis(self, repository, sample_campaign_with_memberships):
        """Test getting comprehensive campaign metrics with bounce analysis - MUST FAIL initially"""
        campaign, memberships, contacts = sample_campaign_with_memberships
        
        # This method should exist to get detailed metrics including bounce analysis
        metrics = repository.get_campaign_metrics_with_bounce_analysis(campaign_id=campaign.id)
        
        # Should return comprehensive metrics
        assert metrics is not None
        assert 'total_contacts' in metrics
        assert 'sent' in metrics
        assert 'delivered' in metrics
        assert 'bounced' in metrics
        assert 'replied' in metrics
        assert 'opted_out' in metrics
        assert 'bounce_rate' in metrics
        assert 'delivery_rate' in metrics
        assert 'response_rate' in metrics
        assert 'bounce_breakdown' in metrics
        assert 'status_indicator' in metrics
        
        # Verify counts match test data
        assert metrics['total_contacts'] == 5
        assert metrics['sent'] >= 1  # At least 1 with status 'sent'
        assert metrics['delivered'] >= 1  # At least 1 with status 'delivered' 
        assert metrics['bounced'] >= 1   # At least 1 with status 'failed'
        
        # Bounce breakdown should have categories
        breakdown = metrics['bounce_breakdown']
        assert isinstance(breakdown, dict)
        assert 'hard' in breakdown or 'soft' in breakdown or 'unknown' in breakdown
    
    def test_get_membership_status_distribution(self, repository, sample_campaign_with_memberships):
        """Test getting membership status distribution - MUST FAIL initially"""
        campaign, memberships, contacts = sample_campaign_with_memberships
        
        # This method should exist to get detailed status distribution
        distribution = repository.get_membership_status_distribution(campaign_id=campaign.id)
        
        # Should return status counts and percentages
        assert distribution is not None
        assert 'status_counts' in distribution
        assert 'status_percentages' in distribution
        assert 'total_members' in distribution
        
        status_counts = distribution['status_counts']
        assert 'sent' in status_counts
        assert 'delivered' in status_counts
        assert 'failed' in status_counts
        assert 'replied_positive' in status_counts
        assert 'opted_out' in status_counts
        
        # Verify percentages add up to 100 (or close due to rounding)
        percentages = distribution['status_percentages']
        total_percentage = sum(percentages.values())
        assert 95 <= total_percentage <= 105  # Allow for rounding errors
    
    def test_find_memberships_with_activity_ids(self, repository, sample_campaign_with_memberships):
        """Test finding memberships that have sent activity IDs - MUST FAIL initially"""
        campaign, memberships, contacts = sample_campaign_with_memberships
        
        # This method should exist to find memberships with activity references
        memberships_with_activities = repository.find_memberships_with_activity_ids(
            campaign_id=campaign.id
        )
        
        # Should return memberships that have sent_activity_id populated
        assert isinstance(memberships_with_activities, list)
        
        # All returned memberships should have sent_activity_id
        for membership in memberships_with_activities:
            assert membership.sent_activity_id is not None
    
    def test_get_campaign_bounce_analysis(self, repository, sample_campaign_with_memberships):
        """Test getting detailed bounce analysis for campaign - MUST FAIL initially"""
        campaign, memberships, contacts = sample_campaign_with_memberships
        
        # This method should exist to analyze bounces in detail
        bounce_analysis = repository.get_campaign_bounce_analysis(campaign_id=campaign.id)
        
        # Should return detailed bounce analysis
        assert bounce_analysis is not None
        assert 'total_bounces' in bounce_analysis
        assert 'bounce_types' in bounce_analysis
        assert 'bounce_reasons' in bounce_analysis
        assert 'problematic_contacts' in bounce_analysis
        assert 'recommendations' in bounce_analysis
        
        # Bounce types should be categorized
        bounce_types = bounce_analysis['bounce_types']
        assert isinstance(bounce_types, dict)
        # Should have keys like 'hard', 'soft', 'carrier_rejection', 'capability', 'unknown'
        expected_types = ['hard', 'soft', 'carrier_rejection', 'capability', 'unknown']
        for bounce_type in expected_types:
            assert bounce_type in bounce_types
    
    def test_update_membership_with_bounce_info(self, repository, sample_campaign_with_memberships):
        """Test updating membership with bounce information - MUST FAIL initially"""
        campaign, memberships, contacts = sample_campaign_with_memberships
        failed_membership = next((m for m in memberships if m.status == 'failed'), None)
        
        if failed_membership is None:
            pytest.skip("No failed membership found in test data")
        
        # This method should exist to update membership with detailed bounce info
        bounce_info = {
            'bounce_type': 'hard',
            'bounce_reason': 'invalid_number',
            'bounce_details': 'Number disconnected',
            'bounced_at': datetime.utcnow().isoformat(),
            'carrier': 'verizon'
        }
        
        result = repository.update_membership_with_bounce_info(
            membership_id=failed_membership.id,
            bounce_info=bounce_info
        )
        
        # Should update membership with bounce information
        assert result is not None
        assert result.status == 'failed'
        assert result.membership_metadata is not None
        assert 'bounce_info' in result.membership_metadata
        
        stored_bounce = result.membership_metadata['bounce_info']
        assert stored_bounce['bounce_type'] == 'hard'
        assert stored_bounce['bounce_reason'] == 'invalid_number'
    
    def test_get_campaign_performance_over_time(self, repository, sample_campaign_with_memberships):
        """Test getting campaign performance metrics over time - MUST FAIL initially"""
        campaign, memberships, contacts = sample_campaign_with_memberships
        
        # This method should exist to track performance over time
        performance = repository.get_campaign_performance_over_time(
            campaign_id=campaign.id,
            days=7
        )
        
        # Should return time-series performance data
        assert performance is not None
        assert 'daily_stats' in performance
        assert 'trends' in performance
        assert 'summary' in performance
        
        daily_stats = performance['daily_stats']
        assert isinstance(daily_stats, list)
        assert len(daily_stats) == 7  # 7 days of data
        
        # Each day should have required metrics
        for day_stat in daily_stats:
            assert 'date' in day_stat
            assert 'sent' in day_stat
            assert 'delivered' in day_stat
            assert 'bounced' in day_stat
            assert 'bounce_rate' in day_stat
    
    def test_find_campaigns_with_high_bounce_rates(self, repository, sample_campaign_with_memberships):
        """Test finding campaigns with high bounce rates - MUST FAIL initially"""
        campaign, memberships, contacts = sample_campaign_with_memberships
        
        # This method should exist to identify problematic campaigns
        high_bounce_campaigns = repository.find_campaigns_with_high_bounce_rates(
            bounce_threshold=10.0,  # 10% bounce rate threshold
            min_sent_count=1  # At least 1 message sent
        )
        
        # Should return list of campaigns with details
        assert isinstance(high_bounce_campaigns, list)
        
        # Each campaign should have bounce metrics
        for campaign_info in high_bounce_campaigns:
            assert 'campaign' in campaign_info
            assert 'bounce_rate' in campaign_info
            assert 'sent_count' in campaign_info
            assert 'bounce_count' in campaign_info
            assert campaign_info['bounce_rate'] >= 10.0
    
    def test_get_membership_timeline(self, repository, sample_campaign_with_memberships):
        """Test getting timeline of membership status changes - MUST FAIL initially"""
        campaign, memberships, contacts = sample_campaign_with_memberships
        
        # This method should exist to track status change timeline
        timeline = repository.get_membership_timeline(
            campaign_id=campaign.id,
            hours=24
        )
        
        # Should return chronological timeline of status changes
        assert timeline is not None
        assert isinstance(timeline, list)
        
        # Timeline entries should have required fields
        for entry in timeline:
            assert 'timestamp' in entry
            assert 'status' in entry
            assert 'contact_id' in entry
            assert 'event_type' in entry  # 'sent', 'delivered', 'bounced', 'replied', etc.
    
    def test_bulk_update_membership_statuses(self, repository, sample_campaign_with_memberships):
        """Test bulk updating membership statuses - MUST FAIL initially"""
        campaign, memberships, contacts = sample_campaign_with_memberships
        
        # Get membership IDs to update
        membership_ids = [m.id for m in memberships[:2]]
        
        # This method should exist to bulk update statuses
        updated_count = repository.bulk_update_membership_statuses(
            membership_ids=membership_ids,
            status='processed',
            metadata={'processed_at': datetime.utcnow().isoformat()}
        )
        
        # Should return count of updated memberships
        assert updated_count == 2
        
        # Verify memberships were updated
        for membership_id in membership_ids:
            # Use a separate query to avoid session cache
            membership = repository.session.query(CampaignMembership).get(membership_id)
            assert membership.status == 'processed'
            assert membership.membership_metadata is not None
            assert 'processed_at' in membership.membership_metadata
    
    def test_calculate_campaign_roi_metrics(self, repository, sample_campaign_with_memberships):
        """Test calculating campaign ROI and effectiveness metrics - MUST FAIL initially"""
        campaign, memberships, contacts = sample_campaign_with_memberships
        
        # This method should exist to calculate ROI and effectiveness
        roi_metrics = repository.calculate_campaign_roi_metrics(campaign_id=campaign.id)
        
        # Should return comprehensive ROI analysis
        assert roi_metrics is not None
        assert 'cost_per_message' in roi_metrics
        assert 'cost_per_response' in roi_metrics
        assert 'response_value' in roi_metrics
        assert 'roi_percentage' in roi_metrics
        assert 'effectiveness_score' in roi_metrics
        
        # Values should be reasonable
        assert roi_metrics['cost_per_message'] >= 0
        assert roi_metrics['effectiveness_score'] >= 0
        assert roi_metrics['effectiveness_score'] <= 100