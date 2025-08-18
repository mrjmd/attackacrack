"""
Tests for DashboardService refactored to use repository pattern
These tests verify the service uses repositories instead of direct DB queries
"""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timedelta
from services.dashboard_service import DashboardService
from crm_database import Contact, Campaign, CampaignMembership, Activity, Conversation


class TestDashboardServiceRepositoryRefactor:
    """Test DashboardService uses repository pattern correctly"""
    
    @pytest.fixture
    def mock_contact_repository(self):
        """Mock ContactRepository"""
        return Mock()
    
    @pytest.fixture  
    def mock_campaign_repository(self):
        """Mock CampaignRepository"""
        return Mock()
        
    @pytest.fixture
    def mock_activity_repository(self):
        """Mock ActivityRepository"""
        return Mock()
        
    @pytest.fixture
    def mock_conversation_repository(self):
        """Mock ConversationRepository"""
        return Mock()
    
    @pytest.fixture
    def dashboard_service(self, mock_contact_repository, mock_campaign_repository, 
                         mock_activity_repository, mock_conversation_repository):
        """Create DashboardService with mocked repositories"""
        service = DashboardService()
        
        # Inject the mocked repositories
        service.contact_repository = mock_contact_repository
        service.campaign_repository = mock_campaign_repository
        service.activity_repository = mock_activity_repository
        service.conversation_repository = mock_conversation_repository
        
        return service
    
    def test_get_dashboard_stats_uses_repositories(self, dashboard_service, 
                                                 mock_contact_repository, 
                                                 mock_campaign_repository,
                                                 mock_activity_repository):
        """Test that get_dashboard_stats uses repository methods instead of direct DB queries"""
        # Arrange - setup repository method return values
        mock_contact_repository.get_total_contacts_count.return_value = 150
        mock_contact_repository.get_contacts_added_this_week_count.return_value = 12
        mock_campaign_repository.get_active_campaigns_count.return_value = 3
        mock_campaign_repository.calculate_average_campaign_response_rate.return_value = 25.5
        mock_activity_repository.get_messages_sent_today_count.return_value = 45
        mock_activity_repository.calculate_overall_response_rate.return_value = 68.2
        
        # Act
        result = dashboard_service.get_dashboard_stats()
        
        # Assert - verify repository methods were called
        mock_contact_repository.get_total_contacts_count.assert_called_once()
        mock_contact_repository.get_contacts_added_this_week_count.assert_called_once()
        mock_campaign_repository.get_active_campaigns_count.assert_called_once()
        mock_campaign_repository.calculate_average_campaign_response_rate.assert_called_once()
        mock_activity_repository.get_messages_sent_today_count.assert_called_once()
        mock_activity_repository.calculate_overall_response_rate.assert_called_once()
        
        # Assert - verify correct values are returned
        assert result['contact_count'] == 150
        assert result['contacts_added_this_week'] == 12
        assert result['active_campaigns'] == 3
        assert result['campaign_response_rate'] == 25.5
        assert result['messages_today'] == 45
        assert result['overall_response_rate'] == 68.2
    
    def test_get_activity_timeline_uses_repository(self, dashboard_service, 
                                                  mock_conversation_repository):
        """Test that get_activity_timeline uses conversation repository"""
        # Arrange - create mock conversations with activities
        mock_contact1 = Mock()
        mock_contact1.id = 1
        mock_contact1.first_name = 'John'
        mock_contact1.phone = '+11234567890'
        
        mock_activity1 = Mock()
        mock_activity1.activity_type = 'message'
        mock_activity1.direction = 'incoming'
        mock_activity1.body = 'Test message'
        mock_activity1.created_at = datetime.utcnow() - timedelta(hours=1)
        mock_activity1.duration_seconds = None
        
        mock_conversation1 = Mock()
        mock_conversation1.contact = mock_contact1
        mock_conversation1.activities = [mock_activity1]
        
        mock_conversation_repository.get_recent_conversations_with_activities.return_value = [mock_conversation1]
        
        # Act
        result = dashboard_service.get_activity_timeline(limit=20)
        
        # Assert - verify repository method was called
        mock_conversation_repository.get_recent_conversations_with_activities.assert_called_once_with(limit=20)
        
        # Assert - verify timeline is properly formatted
        assert len(result) == 1
        timeline_item = result[0]
        assert timeline_item['contact_id'] == 1
        assert timeline_item['contact_name'] == 'John'
        assert timeline_item['contact_number'] == '+11234567890'
        assert 'Test message' in timeline_item['latest_message_body']
        assert 'activity_timestamp' in timeline_item
        assert timeline_item['activity_type'] == 'message'
    
    def test_get_recent_campaigns_uses_repository(self, dashboard_service, 
                                                 mock_campaign_repository):
        """Test that get_recent_campaigns uses campaign repository"""
        # Arrange
        mock_campaign1 = Mock()
        mock_campaign1.name = 'Test Campaign 1'
        mock_campaign1.created_at = datetime.utcnow() - timedelta(days=1)
        
        mock_campaign2 = Mock()
        mock_campaign2.name = 'Test Campaign 2'
        mock_campaign2.created_at = datetime.utcnow() - timedelta(days=2)
        
        mock_campaign_repository.get_recent_campaigns_with_limit.return_value = [mock_campaign1, mock_campaign2]
        
        # Act
        result = dashboard_service.get_recent_campaigns(limit=3)
        
        # Assert
        mock_campaign_repository.get_recent_campaigns_with_limit.assert_called_once_with(limit=3)
        assert len(result) == 2
        assert result[0].name == 'Test Campaign 1'
        assert result[1].name == 'Test Campaign 2'
    
    def test_get_message_volume_data_uses_repository(self, dashboard_service, 
                                                    mock_activity_repository):
        """Test that get_message_volume_data uses activity repository"""
        # Arrange
        today = datetime.utcnow().date()
        yesterday = today - timedelta(days=1)
        
        mock_volume_data = [
            {'date': yesterday, 'count': 15},
            {'date': today, 'count': 23}
        ]
        mock_activity_repository.get_message_volume_data.return_value = mock_volume_data
        
        # Act
        result = dashboard_service.get_message_volume_data(days=2)
        
        # Assert
        mock_activity_repository.get_message_volume_data.assert_called_once_with(days=2)
        assert result == mock_volume_data
        assert len(result) == 2
        assert result[0]['count'] == 15
        assert result[1]['count'] == 23
    
    def test_get_campaign_queue_size_uses_repository(self, dashboard_service, 
                                                    mock_campaign_repository):
        """Test that get_campaign_queue_size uses campaign repository"""
        # Arrange
        mock_campaign_repository.get_pending_campaign_queue_size.return_value = 42
        
        # Act
        result = dashboard_service.get_campaign_queue_size()
        
        # Assert
        mock_campaign_repository.get_pending_campaign_queue_size.assert_called_once()
        assert result == 42
    
    def test_get_data_quality_score_uses_repository(self, dashboard_service, 
                                                   mock_contact_repository):
        """Test that get_data_quality_score uses contact repository"""
        # Arrange
        mock_quality_stats = {
            'total_contacts': 100,
            'contacts_with_names': 85,
            'contacts_with_emails': 60,
            'data_quality_score': 73
        }
        mock_contact_repository.get_data_quality_stats.return_value = mock_quality_stats
        
        # Act
        result = dashboard_service.get_data_quality_score()
        
        # Assert
        mock_contact_repository.get_data_quality_stats.assert_called_once()
        assert result == 73
    
    def test_format_activity_item_handles_different_types(self, dashboard_service):
        """Test that _format_activity_item correctly formats different activity types"""
        # Arrange - create mock conversation and contact
        mock_contact = Mock()
        mock_contact.id = 1
        mock_contact.first_name = 'John'
        mock_contact.phone = '+11234567890'
        
        mock_conversation = Mock()
        mock_conversation.contact = mock_contact
        
        # Test message activity
        mock_message_activity = Mock()
        mock_message_activity.activity_type = 'message'
        mock_message_activity.body = 'Hello world'
        mock_message_activity.created_at = datetime.utcnow()
        mock_message_activity.direction = 'incoming'
        mock_message_activity.duration_seconds = None
        
        # Act
        result = dashboard_service._format_activity_item(mock_conversation, mock_message_activity)
        
        # Assert
        assert result['contact_id'] == 1
        assert result['contact_name'] == 'John'
        assert result['contact_number'] == '+11234567890'
        assert result['latest_message_body'] == 'Hello world'
        assert result['activity_type'] == 'message'
        
        # Test call activity  
        mock_call_activity = Mock()
        mock_call_activity.activity_type = 'call'
        mock_call_activity.direction = 'incoming'
        mock_call_activity.duration_seconds = 180  # 3 minutes
        mock_call_activity.body = None
        mock_call_activity.created_at = datetime.utcnow()
        
        # Act
        result_call = dashboard_service._format_activity_item(mock_conversation, mock_call_activity)
        
        # Assert
        assert '📞 Incoming call (3m)' in result_call['latest_message_body']
        assert result_call['activity_type'] == 'call'
        
        # Test voicemail activity
        mock_voicemail_activity = Mock()
        mock_voicemail_activity.activity_type = 'voicemail'
        mock_voicemail_activity.direction = 'incoming'
        mock_voicemail_activity.duration_seconds = None
        mock_voicemail_activity.body = None
        mock_voicemail_activity.created_at = datetime.utcnow()
        
        # Act
        result_voicemail = dashboard_service._format_activity_item(mock_conversation, mock_voicemail_activity)
        
        # Assert
        assert result_voicemail['latest_message_body'] == '🎤 Voicemail received'
        assert result_voicemail['activity_type'] == 'voicemail'