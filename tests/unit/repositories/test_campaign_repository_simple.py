"""
Simple test for CampaignRepository to verify it works
"""

from repositories.campaign_repository import CampaignRepository
from repositories.base_repository import PaginationParams, PaginatedResult
from crm_database import Campaign, CampaignMembership
from sqlalchemy.orm import Session
from unittest.mock import MagicMock


def test_campaign_repository_creation():
    """Test that repository can be created"""
    session = MagicMock(spec=Session)
    repo = CampaignRepository(session)
    assert repo.session == session


def test_search_campaigns():
    """Test search functionality"""
    session = MagicMock(spec=Session)
    repo = CampaignRepository(session)
    
    # Mock query
    mock_query = MagicMock()
    session.query.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.all.return_value = []
    
    # Test search
    results = repo.search("test")
    assert results == []
    session.query.assert_called()


def test_get_campaign_stats():
    """Test getting campaign statistics"""
    session = MagicMock(spec=Session)
    repo = CampaignRepository(session)
    
    # Mock query results
    mock_query = MagicMock()
    session.query.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.group_by.return_value = mock_query
    mock_query.all.return_value = [
        ('sent', 100),
        ('delivered', 95),
        ('responded', 10),
        ('opted_out', 2)
    ]
    
    # Get stats
    stats = repo.get_campaign_stats(1)
    
    # Verify stats structure
    assert 'total_recipients' in stats
    assert 'sent' in stats
    assert 'delivered' in stats
    assert 'responded' in stats
    assert 'response_rate' in stats
    assert stats['sent'] == 100
    assert stats['delivered'] == 95