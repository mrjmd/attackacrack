"""
Tests for EngagementScoreRepository - P4-01 Engagement Scoring System
TDD RED PHASE - These tests are written FIRST before implementation
"""

import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock, patch
from utils.datetime_utils import utc_now
from repositories.engagement_score_repository import EngagementScoreRepository
from crm_database import EngagementScore, Contact, Campaign
from tests.conftest import create_test_contact
from repositories.base_repository import PaginationParams


class TestEngagementScoreRepository:
    """Test EngagementScoreRepository with comprehensive coverage"""
    
    @pytest.fixture
    def repository(self, db_session):
        """Create EngagementScoreRepository instance"""
        return EngagementScoreRepository(session=db_session)
    
    @pytest.fixture
    def sample_contact(self, db_session):
        """Create sample contact for testing"""
        import uuid
        unique_phone = f'+1555{str(uuid.uuid4())[:8].replace("-", "")[:7]}'
        contact = create_test_contact(phone=unique_phone, first_name='Test', last_name='Contact')
        db_session.add(contact)
        db_session.commit()
        return contact
    
    @pytest.fixture 
    def sample_campaign(self, db_session):
        """Create sample campaign for testing"""
        from crm_database import Campaign
        import uuid
        unique_name = f'Test Campaign {str(uuid.uuid4())[:8]}'
        campaign = Campaign(name=unique_name, status='active')
        db_session.add(campaign)
        db_session.commit()
        return campaign
    
    def test_create_engagement_score(self, repository, db_session, sample_contact, sample_campaign):
        """Test creating a new engagement score"""
        # Arrange
        score_data = {
            'contact_id': sample_contact.id,
            'campaign_id': sample_campaign.id,
            'overall_score': 85.5,
            'recency_score': 90.0,
            'frequency_score': 80.0,
            'monetary_score': 86.0,
            'engagement_probability': 0.75,
            'calculated_at': utc_now(),
            'score_version': '1.0'
        }
        
        # Act
        score = repository.create(**score_data)
        
        # Assert
        assert score.id is not None
        assert score.contact_id == sample_contact.id
        assert score.campaign_id == sample_campaign.id
        assert score.overall_score == 85.5
        assert score.recency_score == 90.0
        assert score.frequency_score == 80.0
        assert score.monetary_score == 86.0
        assert score.engagement_probability == 0.75
        assert score.score_version == '1.0'
    
    def test_update_existing_score(self, repository, db_session, sample_contact, sample_campaign):
        """Test updating an existing engagement score"""
        # Arrange - Create initial score
        initial_score = repository.create(
            contact_id=sample_contact.id,
            campaign_id=sample_campaign.id,
            overall_score=75.0,
            recency_score=80.0,
            frequency_score=70.0,
            monetary_score=75.0,
            engagement_probability=0.65,
            calculated_at=utc_now() - timedelta(hours=1),
            score_version='1.0'
        )
        
        # Act - Update the score
        updated_score = repository.update(
            initial_score,
            overall_score=82.5,
            recency_score=85.0,
            frequency_score=78.0,
            monetary_score=84.0,
            engagement_probability=0.72,
            calculated_at=utc_now(),
            score_version='1.1'
        )
        
        # Assert
        assert updated_score.id == initial_score.id
        assert updated_score.overall_score == 82.5
        assert updated_score.recency_score == 85.0
        assert updated_score.engagement_probability == 0.72
        assert updated_score.score_version == '1.1'
    
    def test_get_score_by_contact_and_campaign(self, repository, db_session, sample_contact, sample_campaign):
        """Test retrieving score by contact and campaign"""
        # Arrange
        score = repository.create(
            contact_id=sample_contact.id,
            campaign_id=sample_campaign.id,
            overall_score=88.0,
            recency_score=90.0,
            frequency_score=85.0,
            monetary_score=89.0,
            engagement_probability=0.78,
            calculated_at=utc_now(),
            score_version='1.0'
        )
        
        # Act
        retrieved_score = repository.get_by_contact_and_campaign(sample_contact.id, sample_campaign.id)
        
        # Assert
        assert retrieved_score is not None
        assert retrieved_score.id == score.id
        assert retrieved_score.overall_score == 88.0
    
    def test_get_score_by_contact_and_campaign_not_found(self, repository, db_session, sample_contact):
        """Test retrieving non-existent score returns None"""
        # Arrange - Create campaign without associated score
        from crm_database import Campaign
        other_campaign = Campaign(name='Other Campaign', status='active')
        db_session.add(other_campaign)
        db_session.commit()
        
        # Act
        result = repository.get_by_contact_and_campaign(sample_contact.id, other_campaign.id)
        
        # Assert
        assert result is None
    
    def test_get_latest_score_for_contact(self, repository, db_session, sample_contact, sample_campaign):
        """Test retrieving the latest score for a contact across all campaigns"""
        # Arrange - Create multiple scores at different times
        from crm_database import Campaign
        campaign2 = Campaign(name='Campaign 2', status='active')
        db_session.add(campaign2)
        db_session.commit()
        
        # Older score
        old_score = repository.create(
            contact_id=sample_contact.id,
            campaign_id=sample_campaign.id,
            overall_score=70.0,
            calculated_at=utc_now() - timedelta(hours=2),
            score_version='1.0'
        )
        
        # Newer score
        new_score = repository.create(
            contact_id=sample_contact.id,
            campaign_id=campaign2.id,
            overall_score=85.0,
            calculated_at=utc_now() - timedelta(minutes=30),
            score_version='1.0'
        )
        
        # Act
        latest_score = repository.get_latest_score_for_contact(sample_contact.id)
        
        # Assert
        assert latest_score is not None
        assert latest_score.id == new_score.id
        assert latest_score.overall_score == 85.0
    
    def test_get_all_scores_for_contact(self, repository, db_session, sample_contact, sample_campaign):
        """Test retrieving all scores for a contact"""
        # Arrange - Create multiple scores
        from crm_database import Campaign
        campaign2 = Campaign(name='Campaign 2', status='active')
        db_session.add(campaign2)
        db_session.commit()
        
        score1 = repository.create(
            contact_id=sample_contact.id,
            campaign_id=sample_campaign.id,
            overall_score=75.0,
            calculated_at=utc_now() - timedelta(hours=1),
            score_version='1.0'
        )
        
        score2 = repository.create(
            contact_id=sample_contact.id,
            campaign_id=campaign2.id,
            overall_score=82.0,
            calculated_at=utc_now(),
            score_version='1.0'
        )
        
        # Act
        all_scores = repository.get_all_scores_for_contact(sample_contact.id)
        
        # Assert
        assert len(all_scores) == 2
        assert score1 in all_scores
        assert score2 in all_scores
    
    def test_get_scores_for_campaign(self, repository, db_session, sample_contact, sample_campaign):
        """Test retrieving all scores for a specific campaign"""
        # Arrange - Create multiple contacts and scores
        contact2 = create_test_contact(phone='+15551234568', first_name='Test2', last_name='Contact2')
        db_session.add(contact2)
        db_session.commit()
        
        score1 = repository.create(
            contact_id=sample_contact.id,
            campaign_id=sample_campaign.id,
            overall_score=75.0,
            calculated_at=utc_now(),
            score_version='1.0'
        )
        
        score2 = repository.create(
            contact_id=contact2.id,
            campaign_id=sample_campaign.id,
            overall_score=82.0,
            calculated_at=utc_now(),
            score_version='1.0'
        )
        
        # Act
        campaign_scores = repository.get_scores_for_campaign(sample_campaign.id)
        
        # Assert
        assert len(campaign_scores) == 2
        assert score1 in campaign_scores
        assert score2 in campaign_scores
    
    def test_calculate_percentile_ranks(self, repository, db_session, sample_campaign):
        """Test calculating percentile ranks for campaign scores"""
        # Arrange - Create multiple contacts with different scores
        contacts = []
        scores = [45.0, 55.0, 65.0, 75.0, 85.0, 95.0]  # 6 contacts with varying scores
        
        for i, score_value in enumerate(scores):
            contact = create_test_contact(phone=f'+155512345{60+i}', first_name=f'Test{i}', last_name='Contact')
            db_session.add(contact)
            contacts.append(contact)
        
        db_session.commit()
        
        for contact, score_value in zip(contacts, scores):
            repository.create(
                contact_id=contact.id,
                campaign_id=sample_campaign.id,
                overall_score=score_value,
                calculated_at=utc_now(),
                score_version='1.0'
            )
        
        # Act
        percentiles = repository.calculate_percentile_ranks(sample_campaign.id)
        
        # Assert
        assert len(percentiles) == 6
        # Highest score (95.0) should be 100th percentile
        highest_score_contact = next(c for c, s in zip(contacts, scores) if s == 95.0)
        assert percentiles[highest_score_contact.id]['percentile'] == 100.0
        # Lowest score (45.0) should be approximately 0th percentile
        lowest_score_contact = next(c for c, s in zip(contacts, scores) if s == 45.0)
        assert percentiles[lowest_score_contact.id]['percentile'] <= 20.0
    
    def test_get_top_scored_contacts(self, repository, db_session, sample_campaign):
        """Test retrieving top-scored contacts for a campaign"""
        # Arrange - Create contacts with different scores
        contacts = []
        scores = [65.0, 85.0, 45.0, 92.0, 73.0]  # Unsorted scores
        
        for i, score_value in enumerate(scores):
            contact = create_test_contact(phone=f'+155512345{70+i}', first_name=f'TopTest{i}', last_name='Contact')
            db_session.add(contact)
            contacts.append(contact)
        
        db_session.commit()
        
        for contact, score_value in zip(contacts, scores):
            repository.create(
                contact_id=contact.id,
                campaign_id=sample_campaign.id,
                overall_score=score_value,
                calculated_at=utc_now(),
                score_version='1.0'
            )
        
        # Act
        top_contacts = repository.get_top_scored_contacts(sample_campaign.id, limit=3)
        
        # Assert
        assert len(top_contacts) == 3
        # Should be ordered by score descending: 92.0, 85.0, 73.0
        assert top_contacts[0].overall_score == 92.0
        assert top_contacts[1].overall_score == 85.0
        assert top_contacts[2].overall_score == 73.0
    
    def test_get_score_distribution(self, repository, db_session, sample_campaign):
        """Test getting score distribution statistics"""
        # Arrange - Create contacts with known score distribution
        contacts = []
        scores = [20.0, 40.0, 60.0, 80.0, 100.0]
        
        for i, score_value in enumerate(scores):
            contact = create_test_contact(phone=f'+155512345{80+i}', first_name=f'DistTest{i}', last_name='Contact')
            db_session.add(contact)
            contacts.append(contact)
        
        db_session.commit()
        
        for contact, score_value in zip(contacts, scores):
            repository.create(
                contact_id=contact.id,
                campaign_id=sample_campaign.id,
                overall_score=score_value,
                calculated_at=utc_now(),
                score_version='1.0'
            )
        
        # Act
        distribution = repository.get_score_distribution(sample_campaign.id)
        
        # Assert
        assert distribution['min'] == 20.0
        assert distribution['max'] == 100.0
        assert distribution['mean'] == 60.0  # (20+40+60+80+100)/5
        assert distribution['median'] == 60.0
        assert distribution['std_dev'] is not None
        assert distribution['count'] == 5
    
    def test_get_scores_needing_update(self, repository, db_session, sample_contact, sample_campaign):
        """Test finding scores that need to be recalculated"""
        # Arrange - Create scores with different ages
        from crm_database import Campaign
        campaign2 = Campaign(name='Campaign 2', status='active')
        db_session.add(campaign2)
        db_session.commit()
        
        # Fresh score (shouldn't need update)
        fresh_score = repository.create(
            contact_id=sample_contact.id,
            campaign_id=sample_campaign.id,
            overall_score=75.0,
            calculated_at=utc_now() - timedelta(hours=1),
            score_version='1.0'
        )
        
        # Stale score (should need update)
        stale_score = repository.create(
            contact_id=sample_contact.id,
            campaign_id=campaign2.id,
            overall_score=82.0,
            calculated_at=utc_now() - timedelta(days=8),
            score_version='1.0'
        )
        
        # Act
        max_age_hours = 48  # 2 days
        scores_needing_update = repository.get_scores_needing_update(max_age_hours)
        
        # Assert
        assert stale_score in scores_needing_update
        assert fresh_score not in scores_needing_update
    
    def test_bulk_update_scores(self, repository, db_session, sample_campaign):
        """Test bulk updating multiple scores"""
        # Arrange - Create multiple contacts and scores
        contacts = []
        for i in range(5):
            contact = create_test_contact(phone=f'+155512346{i}', first_name=f'BulkTest{i}', last_name='Contact')
            db_session.add(contact)
            contacts.append(contact)
        
        db_session.commit()
        
        scores = []
        for contact in contacts:
            score = repository.create(
                contact_id=contact.id,
                campaign_id=sample_campaign.id,
                overall_score=50.0,
                calculated_at=utc_now() - timedelta(hours=6),
                score_version='1.0'
            )
            scores.append(score)
        
        # Prepare bulk updates
        updates = []
        for i, score in enumerate(scores):
            updates.append({
                'score_id': score.id,
                'overall_score': 70.0 + (i * 5),  # 70, 75, 80, 85, 90
                'calculated_at': utc_now(),
                'score_version': '1.1'
            })
        
        # Act
        updated_count = repository.bulk_update_scores(updates)
        
        # Assert
        assert updated_count == 5
        
        # Verify updates
        for i, score in enumerate(scores):
            updated_score = repository.get_by_id(score.id)
            assert updated_score.overall_score == 70.0 + (i * 5)
            assert updated_score.score_version == '1.1'
    
    def test_delete_old_score_history(self, repository, db_session, sample_contact, sample_campaign):
        """Test deletion of old score records for data retention"""
        # Arrange
        now = utc_now()
        
        # Create a second campaign for the old score
        from crm_database import Campaign
        import uuid
        old_campaign = Campaign(name=f'Old Campaign {str(uuid.uuid4())[:8]}', status='active')
        db_session.add(old_campaign)
        db_session.commit()
        
        # Recent score (should be kept)
        recent_score = repository.create(
            contact_id=sample_contact.id,
            campaign_id=sample_campaign.id,
            overall_score=75.0,
            calculated_at=now - timedelta(days=30),
            score_version='1.0'
        )
        
        # Old score in different campaign (should be deleted)
        old_score = repository.create(
            contact_id=sample_contact.id,
            campaign_id=old_campaign.id,
            overall_score=68.0,
            calculated_at=now - timedelta(days=400),
            score_version='1.0'
        )
        
        # Act
        cutoff_date = now - timedelta(days=365)  # 1 year retention
        deleted_count = repository.delete_scores_older_than(cutoff_date)
        
        # Assert
        assert deleted_count == 1
        assert repository.get_by_id(recent_score.id) is not None
        assert repository.get_by_id(old_score.id) is None
    
    def test_get_average_scores_by_segment(self, repository, db_session, sample_campaign):
        """Test calculating average scores by contact segments"""
        # Arrange - Create contacts with different segments
        high_value_contacts = []
        low_value_contacts = []
        
        for i in range(3):
            # High value contacts
            contact = create_test_contact(
                phone=f'+155512347{i}', 
                first_name=f'HighValue{i}', 
                last_name='Contact',
                contact_metadata={'segment': 'high_value', 'customer_type': 'premium'}
            )
            db_session.add(contact)
            high_value_contacts.append(contact)
            
            # Low value contacts  
            contact = create_test_contact(
                phone=f'+155512348{i}',
                first_name=f'LowValue{i}', 
                last_name='Contact',
                contact_metadata={'segment': 'low_value', 'customer_type': 'basic'}
            )
            db_session.add(contact)
            low_value_contacts.append(contact)
        
        db_session.commit()
        
        # Create scores for high value contacts (higher scores)
        for contact in high_value_contacts:
            repository.create(
                contact_id=contact.id,
                campaign_id=sample_campaign.id,
                overall_score=85.0,
                calculated_at=utc_now(),
                score_version='1.0'
            )
        
        # Create scores for low value contacts (lower scores)
        for contact in low_value_contacts:
            repository.create(
                contact_id=contact.id,
                campaign_id=sample_campaign.id,
                overall_score=55.0,
                calculated_at=utc_now(),
                score_version='1.0'
            )
        
        # Act
        segment_averages = repository.get_average_scores_by_segment(sample_campaign.id, 'segment')
        
        # Assert
        assert 'high_value' in segment_averages
        assert 'low_value' in segment_averages
        assert segment_averages['high_value']['avg_overall_score'] == 85.0
        assert segment_averages['low_value']['avg_overall_score'] == 55.0
    
    def test_upsert_score(self, repository, db_session, sample_contact, sample_campaign):
        """Test upsert functionality (insert or update)"""
        # Arrange & Act 1 - First upsert (should insert)
        score1 = repository.upsert_score(
            contact_id=sample_contact.id,
            campaign_id=sample_campaign.id,
            overall_score=75.0,
            recency_score=80.0,
            frequency_score=70.0,
            monetary_score=75.0,
            engagement_probability=0.65,
            score_version='1.0'
        )
        
        # Assert 1
        assert score1.id is not None
        assert score1.overall_score == 75.0
        
        # Act 2 - Second upsert (should update)
        score2 = repository.upsert_score(
            contact_id=sample_contact.id,
            campaign_id=sample_campaign.id,
            overall_score=82.5,
            recency_score=85.0,
            frequency_score=78.0,
            monetary_score=84.0,
            engagement_probability=0.72,
            score_version='1.1'
        )
        
        # Assert 2 - Same ID, updated values
        assert score2.id == score1.id
        assert score2.overall_score == 82.5
        assert score2.score_version == '1.1'
    
    def test_search_scores(self, repository, db_session, sample_contact, sample_campaign):
        """Test searching scores by various criteria"""
        # Arrange
        score = repository.create(
            contact_id=sample_contact.id,
            campaign_id=sample_campaign.id,
            overall_score=88.5,
            calculated_at=utc_now(),
            score_version='2.0',
            score_metadata={'model_type': 'advanced_rfm', 'features_used': ['recency', 'frequency', 'monetary']}
        )
        
        # Act
        search_results = repository.search('advanced', fields=['score_metadata'])
        
        # Assert
        assert score in search_results
    
    def test_get_scores_paginated(self, repository, db_session, sample_campaign):
        """Test paginated retrieval of scores"""
        # Arrange - Create multiple contacts and scores
        for i in range(25):
            contact = create_test_contact(phone=f'+155512349{i:02d}', first_name=f'PageTest{i}', last_name='Contact')
            db_session.add(contact)
        
        db_session.commit()
        
        contacts = db_session.query(Contact).filter(Contact.first_name.like('PageTest%')).all()
        
        for contact in contacts:
            repository.create(
                contact_id=contact.id,
                campaign_id=sample_campaign.id,
                overall_score=50.0 + (contact.id % 50),  # Varying scores
                calculated_at=utc_now(),
                score_version='1.0'
            )
        
        # Act
        pagination = PaginationParams(page=1, per_page=10)
        result = repository.get_paginated(pagination, order_by='overall_score')
        
        # Assert
        assert len(result.items) == 10
        assert result.total == 25
        assert result.pages == 3
        assert result.has_next is True
        assert result.has_prev is False
    
    def test_create_score_with_invalid_data(self, repository, db_session):
        """Test that creating score with invalid data raises appropriate errors"""
        # Arrange - Missing required fields
        invalid_data = {
            'overall_score': 75.0,
            'calculated_at': utc_now()
            # Missing contact_id, campaign_id
        }
        
        # Act & Assert
        with pytest.raises(Exception):
            repository.create(**invalid_data)
    
    def test_create_score_with_invalid_probability(self, repository, db_session, sample_contact, sample_campaign):
        """Test that invalid engagement probabilities are rejected"""
        # Arrange
        invalid_data = {
            'contact_id': sample_contact.id,
            'campaign_id': sample_campaign.id,
            'overall_score': 75.0,
            'engagement_probability': 1.5,  # Invalid: > 1.0
            'calculated_at': utc_now(),
            'score_version': '1.0'
        }
        
        # Act & Assert
        with pytest.raises(ValueError, match="Engagement probability must be between 0 and 1"):
            repository.create(**invalid_data)
    
    def test_get_score_trends(self, repository, db_session, sample_contact, sample_campaign):
        """Test retrieving score trends over time"""
        # Arrange - Create score history by updating the same score over time
        # Since we have a unique constraint on contact_id + campaign_id, we track changes by updating
        base_time = utc_now() - timedelta(days=30)
        
        # Create initial score
        score = repository.create(
            contact_id=sample_contact.id,
            campaign_id=sample_campaign.id,
            overall_score=60.0,
            calculated_at=base_time,
            score_version='1.0'
        )
        
        # Create additional campaigns for historical data points
        from crm_database import Campaign
        import uuid
        campaigns = []
        scores = [score]
        
        for i in range(1, 5):
            campaign = Campaign(name=f'Trend Campaign {str(uuid.uuid4())[:8]}', status='active')
            db_session.add(campaign)
            db_session.commit()
            campaigns.append(campaign)
            
            score = repository.create(
                contact_id=sample_contact.id,
                campaign_id=campaign.id,
                overall_score=60.0 + (i * 5),  # Increasing trend: 65, 70, 75, 80
                calculated_at=base_time + timedelta(days=i*7),
                score_version='1.0'
            )
            scores.append(score)
        
        # Act - Get trends across all campaigns for this contact
        trends = repository.get_score_trends(sample_contact.id, campaign_id=None, days_back=35)  # Extend to capture all data points
        
        # Assert
        assert len(trends) == 5  # Should have exactly 5 data points
        # Verify the trend is increasing
        sorted_trends = sorted(trends, key=lambda x: x['calculated_at'])
        first_score = sorted_trends[0]['overall_score']
        last_score = sorted_trends[-1]['overall_score']
        assert last_score > first_score  # Should show upward trend
        assert first_score == 60.0
        assert last_score == 80.0