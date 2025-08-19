"""
Tests for refactored CampaignService with Repository Pattern
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime, time, timedelta
from services.campaign_service_refactored import CampaignService
from repositories.campaign_repository import CampaignRepository
from repositories.contact_repository import ContactRepository
from crm_database import Campaign, CampaignMembership, Contact


class TestCampaignServiceRefactored:
    """Test suite for refactored CampaignService"""
    
    @pytest.fixture
    def mock_campaign_repo(self):
        """Mock CampaignRepository"""
        repo = Mock()  # Remove spec to allow any method
        repo.create = Mock()
        repo.find_by_id = Mock()
        repo.get_by_id = Mock()
        repo.update = Mock()
        repo.commit = Mock()
        repo.get_stats = Mock()
        return repo
    
    @pytest.fixture
    def mock_contact_repo(self):
        """Mock ContactRepository"""
        repo = Mock()  # Remove spec to allow any method
        repo.create = Mock()
        repo.find_by_id = Mock()
        return repo
    
    @pytest.fixture
    def mock_openphone_service(self):
        """Mock OpenPhoneService"""
        service = Mock()
        service.send_message = Mock(return_value={'id': 'msg123', 'status': 'sent'})
        return service
    
    @pytest.fixture
    def mock_list_service(self):
        """Mock CampaignListService"""
        service = Mock()
        return service
    
    @pytest.fixture
    def campaign_service(self, mock_campaign_repo, mock_contact_repo, 
                        mock_openphone_service, mock_list_service):
        """Create CampaignService with mocked dependencies"""
        return CampaignService(
            campaign_repository=mock_campaign_repo,
            contact_repository=mock_contact_repo,
            openphone_service=mock_openphone_service,
            list_service=mock_list_service
        )
    
    def test_init_with_dependencies(self, mock_campaign_repo, mock_contact_repo):
        """Test CampaignService initialization with injected dependencies"""
        service = CampaignService(
            campaign_repository=mock_campaign_repo,
            contact_repository=mock_contact_repo
        )
        
        assert service.campaign_repository == mock_campaign_repo
        assert service.contact_repository == mock_contact_repo
        assert service.business_hours_start == time(9, 0)
        assert service.business_hours_end == time(18, 0)
    
    def test_init_without_dependencies(self):
        """Test CampaignService initialization without dependencies"""
        service = CampaignService()
        
        # Repositories should be None when not provided (dependency injection pattern)
        assert service.campaign_repository is None
        assert service.contact_repository is None
        assert service.contact_flag_repository is None
    
    def test_create_campaign(self, campaign_service, mock_campaign_repo):
        """Test creating a new campaign"""
        # Arrange
        mock_campaign = Mock(spec=Campaign)
        mock_campaign.id = 1
        mock_campaign.name = "Test Campaign"
        mock_campaign_repo.create.return_value = mock_campaign
        
        # Act
        result = campaign_service.create_campaign(
            name="Test Campaign",
            campaign_type="blast",
            audience_type="mixed",
            template_a="Hello {first_name}",
            template_b="Hi {first_name}",
            daily_limit=100
        )
        
        # Assert
        assert result.is_success
        assert result.data == mock_campaign
        mock_campaign_repo.create.assert_called_once()
        # Check the kwargs passed to create
        call_kwargs = mock_campaign_repo.create.call_args.kwargs
        assert call_kwargs['name'] == "Test Campaign"
        assert call_kwargs['campaign_type'] == "blast"
        assert call_kwargs['template_a'] == "Hello {first_name}"
    
    def test_is_business_hours(self, campaign_service):
        """Test business hours checking"""
        # Mock datetime to a weekday at 10am
        with patch('services.campaign_service_refactored.datetime') as mock_datetime:
            # Setup mock datetime object
            mock_now = Mock()
            mock_now.weekday.return_value = 2  # Wednesday
            mock_now.time.return_value = time(10, 0)
            mock_datetime.now.return_value = mock_now
            
            assert campaign_service.is_business_hours() == True
            
            # Test outside business hours
            mock_now.time.return_value = time(20, 0)  # 8pm
            assert campaign_service.is_business_hours() == False
            
            # Test weekend
            mock_now.weekday.return_value = 6  # Sunday
            mock_now.time.return_value = time(10, 0)  # Even during business hours
            assert campaign_service.is_business_hours() == False
    
    def test_add_recipients_from_list(self, campaign_service, mock_campaign_repo, 
                                     mock_contact_repo, mock_list_service):
        """Test adding recipients from a campaign list"""
        # Arrange
        campaign_id = 1
        list_id = 2
        mock_contacts = [
            Mock(id=1, phone="+11234567890"),
            Mock(id=2, phone="+10987654321"),
            Mock(id=3, phone=None)  # Contact without phone
        ]
        
        from services.common.result import Result
        mock_list_service.get_list_contacts.return_value = Result.success(mock_contacts)
        mock_campaign_repo.find_membership = Mock(return_value=None)  # No existing membership
        mock_campaign_repo.add_members_bulk = Mock(return_value=2)  # Returns count of added
        mock_campaign_repo.get_by_id = Mock(return_value=Mock())  # Mock campaign exists
        
        # Act
        result = campaign_service.add_recipients_from_list(campaign_id, list_id)
        
        # Assert
        assert result.is_success
        assert result.data == 2  # Only contacts with phones
        mock_campaign_repo.add_members_bulk.assert_called_once()
        mock_list_service.get_list_contacts.assert_called_once_with(list_id)
    
    def test_add_recipients_with_filters(self, campaign_service, mock_campaign_repo, 
                                        mock_contact_repo):
        """Test adding recipients with contact filters"""
        # Arrange
        campaign_id = 1
        filters = {"tags": ["hot_lead"], "city": "Boston"}
        
        mock_contacts = [
            Mock(id=1, phone="+11234567890"),
            Mock(id=2, phone="+10987654321")
        ]
        
        # Mock the _get_filtered_contacts method to return our mock contacts
        with patch.object(campaign_service, '_get_filtered_contacts', return_value=mock_contacts):
            mock_campaign_repo.find_membership = Mock(return_value=None)
            mock_campaign_repo.add_members_bulk = Mock(return_value=2)
            
            # Act
            count = campaign_service.add_recipients(campaign_id, filters)
            
            # Assert
            assert count == 2
            mock_campaign_repo.add_members_bulk.assert_called_once()
    
    def test_activate_campaign(self, campaign_service, mock_campaign_repo):
        """Test activating a campaign"""
        # Arrange
        campaign_id = 1
        mock_campaign = Mock()
        mock_campaign.status = 'draft'
        mock_campaign_repo.get_by_id.return_value = mock_campaign
        mock_campaign_repo.commit = Mock()
        
        # Act
        result = campaign_service.activate_campaign(campaign_id)
        
        # Assert
        assert result == True
        assert mock_campaign.status == 'active'
        mock_campaign_repo.commit.assert_called_once()
    
    def test_pause_campaign(self, campaign_service, mock_campaign_repo):
        """Test pausing a campaign"""
        # Arrange
        campaign_id = 1
        mock_campaign = Mock()
        mock_campaign.status = 'running'  # Campaign should be 'running' not 'active'
        mock_campaign_repo.get_by_id.return_value = mock_campaign
        mock_campaign_repo.commit = Mock()
        
        # Act
        result = campaign_service.pause_campaign(campaign_id)
        
        # Assert
        assert result == True
        assert mock_campaign.status == 'paused'
        mock_campaign_repo.commit.assert_called_once()
    
    def test_complete_campaign(self, campaign_service, mock_campaign_repo):
        """Test completing a campaign"""
        # Arrange
        campaign_id = 1
        mock_campaign = Mock()
        mock_campaign.status = 'running'  # Campaign should be 'running' not 'active'
        mock_campaign_repo.get_by_id.return_value = mock_campaign
        mock_campaign_repo.commit = Mock()
        
        # Act
        result = campaign_service.complete_campaign(campaign_id)
        
        # Assert
        assert result == True
        assert mock_campaign.status == 'completed'
        mock_campaign_repo.commit.assert_called_once()
    
    def test_get_campaign_stats(self, campaign_service, mock_campaign_repo):
        """Test getting campaign statistics"""
        # Arrange
        campaign_id = 1
        expected_stats = {
            'total_recipients': 100,
            'sent': 30,
            'pending': 50,
            'opted_out': 5,
            'failed': 2
        }
        mock_campaign_repo.get_campaign_stats.return_value = expected_stats
        
        # Act
        stats = campaign_service.get_campaign_stats(campaign_id)
        
        # Assert
        assert stats == expected_stats
        assert stats['total_recipients'] == 100
        assert stats['sent'] == 30
        assert stats['pending'] == 50
        assert stats['opted_out'] == 5
        assert stats['failed'] == 2
        mock_campaign_repo.get_campaign_stats.assert_called_once_with(campaign_id)