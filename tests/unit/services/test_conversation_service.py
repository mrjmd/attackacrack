"""
Tests for ConversationService - TDD for Repository Pattern Refactoring
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime, timedelta
from utils.datetime_utils import utc_now
from services.conversation_service import ConversationService
from crm_database import Conversation, Contact, Activity, Campaign


class TestConversationService:
    """Test suite for ConversationService with repository pattern"""
    
    @pytest.fixture
    def mock_conversation_repository(self):
        """Mock ConversationRepository"""
        return Mock()
    
    @pytest.fixture
    def mock_campaign_repository(self):
        """Mock CampaignRepository"""
        return Mock()
    
    @pytest.fixture
    def service(self, mock_conversation_repository, mock_campaign_repository):
        """Create ConversationService with mocked repositories"""
        return ConversationService(
            conversation_repository=mock_conversation_repository,
            campaign_repository=mock_campaign_repository
        )
    
    def test_get_conversations_page_with_search_query(self, service, mock_conversation_repository):
        """Test getting conversations page with search query"""
        # Arrange
        search_query = "john"
        expected_result = {
            'conversations': [Mock(id=1)],
            'total_count': 10,
            'page': 1,
            'per_page': 20,
            'total_pages': 1,
            'has_prev': False,
            'has_next': False
        }
        
        mock_repo_result = {
            'conversations': [Mock(id=1)],
            'total_count': 10
        }
        mock_conversation_repository.find_conversations_with_filters.return_value = mock_repo_result
        
        # Mock enhancement
        enhanced_conversations = [{'conversation': Mock(id=1), 'is_unread': False}]
        with patch.object(service, '_enhance_conversations', return_value=enhanced_conversations):
            # Act
            result = service.get_conversations_page(search_query=search_query)
        
        # Assert
        mock_conversation_repository.find_conversations_with_filters.assert_called_once_with(
            search_query=search_query,
            filter_type='all',
            date_filter='all',
            page=1,
            per_page=20
        )
        assert result['conversations'] == enhanced_conversations
        assert result['total_count'] == 10
    
    def test_get_conversations_page_with_unread_filter(self, service, mock_conversation_repository):
        """Test getting conversations page with unread filter"""
        # Arrange
        filter_type = "unread"
        mock_repo_result = {
            'conversations': [Mock(id=1)],
            'total_count': 5
        }
        mock_conversation_repository.find_conversations_with_filters.return_value = mock_repo_result
        
        # Mock enhancement
        enhanced_conversations = [{'conversation': Mock(id=1), 'is_unread': True}]
        with patch.object(service, '_enhance_conversations', return_value=enhanced_conversations):
            # Act
            result = service.get_conversations_page(filter_type=filter_type)
        
        # Assert
        mock_conversation_repository.find_conversations_with_filters.assert_called_once_with(
            search_query='',
            filter_type=filter_type,
            date_filter='all',
            page=1,
            per_page=20
        )
        assert result['conversations'] == enhanced_conversations
        assert result['total_count'] == 5
    
    def test_get_conversations_page_with_date_filter(self, service, mock_conversation_repository):
        """Test getting conversations page with date filter"""
        # Arrange
        date_filter = "today"
        mock_repo_result = {
            'conversations': [Mock(id=1)],
            'total_count': 8
        }
        mock_conversation_repository.find_conversations_with_filters.return_value = mock_repo_result
        
        # Mock enhancement
        enhanced_conversations = [{'conversation': Mock(id=1), 'is_unread': False}]
        with patch.object(service, '_enhance_conversations', return_value=enhanced_conversations):
            # Act
            result = service.get_conversations_page(date_filter=date_filter)
        
        # Assert
        mock_conversation_repository.find_conversations_with_filters.assert_called_once_with(
            search_query='',
            filter_type='all',
            date_filter=date_filter,
            page=1,
            per_page=20
        )
        assert result['conversations'] == enhanced_conversations
        assert result['total_count'] == 8
    
    def test_get_conversations_page_pagination_calculation(self, service, mock_conversation_repository):
        """Test pagination calculation in conversations page"""
        # Arrange
        mock_repo_result = {
            'conversations': [Mock(id=i) for i in range(1, 21)],  # 20 conversations
            'total_count': 250  # Total of 250 conversations
        }
        mock_conversation_repository.find_conversations_with_filters.return_value = mock_repo_result
        
        # Mock enhancement
        enhanced_conversations = [{'conversation': Mock(id=i)} for i in range(1, 21)]
        with patch.object(service, '_enhance_conversations', return_value=enhanced_conversations):
            # Act
            result = service.get_conversations_page(page=3, per_page=20)
        
        # Assert
        assert result['page'] == 3
        assert result['per_page'] == 20
        assert result['total_pages'] == 13  # ceil(250/20)
        assert result['has_prev'] is True  # page 3 has previous
        assert result['has_next'] is True  # page 3 has next (not last page)
    
    def test_enhance_conversations_uses_batch_office_flag_lookup(self, service, mock_conversation_repository):
        """Test that enhancement uses batch office flag lookup from repository"""
        # Arrange
        conversations = [
            Mock(id=1, contact_id=101, activities=[]),
            Mock(id=2, contact_id=102, activities=[]),
            Mock(id=3, contact_id=103, activities=[])
        ]
        contact_ids = [101, 102, 103]
        office_flags = {101, 103}  # Contact 101 and 103 are office numbers
        
        mock_conversation_repository.get_office_flags_batch.return_value = office_flags
        
        # Act
        result = service._enhance_conversations(conversations)
        
        # Assert
        mock_conversation_repository.get_office_flags_batch.assert_called_once_with(contact_ids)
        # Verify office flags are applied correctly
        assert result[0]['is_office_number'] is True   # contact_id 101
        assert result[1]['is_office_number'] is False  # contact_id 102
        assert result[2]['is_office_number'] is True   # contact_id 103
    
    def test_enhance_conversations_calculates_unread_status(self, service, mock_conversation_repository):
        """Test that enhancement correctly calculates unread status"""
        # Arrange
        # Conversation with latest incoming message (unread)
        incoming_activity = Mock(direction='incoming', created_at=datetime(2023, 8, 18, 12, 0))
        outgoing_activity = Mock(direction='outgoing', created_at=datetime(2023, 8, 18, 11, 0))
        unread_conv = Mock(id=1, contact_id=101, activities=[incoming_activity, outgoing_activity])
        
        # Conversation with latest outgoing message (read)
        incoming_activity2 = Mock(direction='incoming', created_at=datetime(2023, 8, 18, 10, 0))
        outgoing_activity2 = Mock(direction='outgoing', created_at=datetime(2023, 8, 18, 11, 0))
        read_conv = Mock(id=2, contact_id=102, activities=[incoming_activity2, outgoing_activity2])
        
        conversations = [unread_conv, read_conv]
        mock_conversation_repository.get_office_flags_batch.return_value = set()
        
        # Act
        result = service._enhance_conversations(conversations)
        
        # Assert
        assert result[0]['is_unread'] is True   # Latest activity is incoming
        assert result[1]['is_unread'] is False  # Latest activity is outgoing
    
    def test_enhance_conversations_detects_attachments(self, service, mock_conversation_repository):
        """Test that enhancement correctly detects attachments"""
        # Arrange
        # Activity with real attachments
        activity_with_media = Mock(
            direction='incoming', 
            created_at=utc_now(),
            media_urls=['http://example.com/image.jpg'],
            ai_summary=None
        )
        
        # Activity without attachments
        activity_no_media = Mock(
            direction='incoming', 
            created_at=utc_now(),
            media_urls=[],
            ai_summary=None
        )
        
        conv_with_attachments = Mock(id=1, contact_id=101, activities=[activity_with_media])
        conv_no_attachments = Mock(id=2, contact_id=102, activities=[activity_no_media])
        
        conversations = [conv_with_attachments, conv_no_attachments]
        mock_conversation_repository.get_office_flags_batch.return_value = set()
        
        # Act
        result = service._enhance_conversations(conversations)
        
        # Assert
        assert result[0]['has_attachments'] is True
        assert result[1]['has_attachments'] is False
    
    def test_get_available_campaigns_uses_repository(self, service, mock_campaign_repository):
        """Test that getting available campaigns uses repository"""
        # Arrange
        expected_campaigns = [Mock(id=1, status='draft'), Mock(id=2, status='running')]
        mock_campaign_repository.find_by_statuses.return_value = expected_campaigns
        
        # Act
        result = service.get_available_campaigns()
        
        # Assert
        mock_campaign_repository.find_by_statuses.assert_called_once_with(['draft', 'running'])
        assert result == expected_campaigns
    
    def test_mark_conversations_read_uses_repository(self, service, mock_conversation_repository):
        """Test that marking conversations read uses repository"""
        # Arrange
        conversation_ids = [1, 2, 3]
        mock_conversation_repository.bulk_update_last_activity.return_value = True
        
        # Act
        success, message = service.mark_conversations_read(conversation_ids)
        
        # Assert
        mock_conversation_repository.bulk_update_last_activity.assert_called_once()
        call_args = mock_conversation_repository.bulk_update_last_activity.call_args
        assert call_args[0][0] == conversation_ids  # conversation_ids argument
        assert isinstance(call_args[0][1], datetime)  # datetime argument
        assert success is True
        assert "3 conversations" in message
    
    def test_mark_conversations_read_empty_list(self, service, mock_conversation_repository):
        """Test marking conversations read with empty list"""
        # Act
        success, message = service.mark_conversations_read([])
        
        # Assert
        mock_conversation_repository.bulk_update_last_activity.assert_not_called()
        assert success is False
        assert "No conversations selected" in message
    
    def test_mark_conversations_read_handles_repository_error(self, service, mock_conversation_repository):
        """Test that marking conversations read handles repository errors"""
        # Arrange
        conversation_ids = [1, 2, 3]
        mock_conversation_repository.bulk_update_last_activity.return_value = False
        
        # Act
        success, message = service.mark_conversations_read(conversation_ids)
        
        # Assert
        assert success is False
        assert "Error" in message
    
    def test_get_contact_ids_from_conversations_uses_repository(self, service, mock_conversation_repository):
        """Test that getting contact IDs uses repository"""
        # Arrange
        conversation_ids = [1, 2, 3]
        mock_conversations = [
            Mock(id=1, contact_id=101),
            Mock(id=2, contact_id=102),
            Mock(id=3, contact_id=101)  # Duplicate contact_id
        ]
        mock_conversation_repository.find_conversations_by_ids_with_contact_info.return_value = mock_conversations
        
        # Act
        result = service.get_contact_ids_from_conversations(conversation_ids)
        
        # Assert
        mock_conversation_repository.find_conversations_by_ids_with_contact_info.assert_called_once_with(conversation_ids)
        # Should return unique contact IDs
        assert set(result) == {101, 102}
    
    def test_export_conversations_with_contacts_uses_repository(self, service, mock_conversation_repository):
        """Test that exporting conversations uses repository methods"""
        # Arrange
        conversation_ids = [1, 2, 3]
        mock_conversations = [
            Mock(
                id=1, 
                contact=Mock(first_name="John", last_name="Doe", phone="+11234567890", email="john@example.com"),
                last_activity_at=datetime(2023, 8, 18, 12, 0)
            ),
            Mock(
                id=2,
                contact=Mock(first_name="Jane", last_name="Smith", phone="+19876543210", email="jane@example.com"),
                last_activity_at=datetime(2023, 8, 18, 11, 0)
            )
        ]
        activity_counts = {1: 5, 2: 3}
        
        mock_conversation_repository.find_conversations_by_ids_with_contact_info.return_value = mock_conversations
        mock_conversation_repository.get_activity_counts_for_conversations.return_value = activity_counts
        
        # Act
        result = service.export_conversations_with_contacts(conversation_ids)
        
        # Assert
        mock_conversation_repository.find_conversations_by_ids_with_contact_info.assert_called_once_with(conversation_ids)
        mock_conversation_repository.get_activity_counts_for_conversations.assert_called_once_with(conversation_ids)
        
        # Verify CSV content
        assert "John Doe" in result
        assert "Jane Smith" in result
        assert "+11234567890" in result
        assert "+19876543210" in result
        assert "john@example.com" in result
        assert "jane@example.com" in result
    
    def test_bulk_action_mark_read(self, service, mock_conversation_repository):
        """Test bulk action for marking conversations read"""
        # Arrange
        conversation_ids = [1, 2, 3]
        mock_conversation_repository.bulk_update_last_activity.return_value = True
        
        # Act
        success, message = service.bulk_action('mark_read', conversation_ids)
        
        # Assert
        assert success is True
        assert "3 conversations" in message
    
    def test_bulk_action_export(self, service, mock_conversation_repository):
        """Test bulk action for exporting conversations"""
        # Arrange
        conversation_ids = [1, 2]
        mock_conversations = [
            Mock(
                id=1,
                contact=Mock(first_name="Test", last_name="User", phone="+11111111111", email="test@example.com"),
                last_activity_at=utc_now()
            )
        ]
        activity_counts = {1: 2}
        
        mock_conversation_repository.find_conversations_by_ids_with_contact_info.return_value = mock_conversations
        mock_conversation_repository.get_activity_counts_for_conversations.return_value = activity_counts
        
        # Act
        success, csv_data = service.bulk_action('export', conversation_ids)
        
        # Assert
        assert success is True
        assert "Test User" in csv_data
    
    def test_bulk_action_unknown_action(self, service, mock_conversation_repository):
        """Test bulk action with unknown action type"""
        # Act
        success, message = service.bulk_action('unknown_action', [1, 2, 3])
        
        # Assert
        assert success is False
        assert "Unknown action" in message
    
    def test_bulk_action_empty_conversation_list(self, service, mock_conversation_repository):
        """Test bulk action with empty conversation list"""
        # Act
        success, message = service.bulk_action('mark_read', [])
        
        # Assert
        assert success is False
        assert "No conversations selected" in message