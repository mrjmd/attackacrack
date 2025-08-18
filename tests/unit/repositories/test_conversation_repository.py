"""
Tests for ConversationRepository
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime, timedelta
from repositories.conversation_repository import ConversationRepository
from repositories.base_repository import PaginatedResult
from crm_database import Conversation, Contact, Activity, ContactFlag


class TestConversationRepository:
    """Test suite for ConversationRepository"""
    
    @pytest.fixture
    def mock_session(self):
        """Mock database session"""
        session = MagicMock()
        return session
    
    @pytest.fixture
    def repository(self, mock_session):
        """Create ConversationRepository with mocked session"""
        return ConversationRepository(mock_session, Conversation)
    
    def test_find_by_contact_id(self, repository, mock_session):
        """Test finding conversations by contact ID"""
        # Arrange
        mock_conversations = [Mock(id=1), Mock(id=2)]
        mock_query = Mock()
        mock_query.filter_by.return_value.order_by.return_value.all.return_value = mock_conversations
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.find_by_contact_id(123)
        
        # Assert
        assert result == mock_conversations
        mock_query.filter_by.assert_called_once_with(contact_id=123)
    
    def test_find_by_openphone_id(self, repository, mock_session):
        """Test finding conversation by OpenPhone ID"""
        # Arrange
        mock_conversation = Mock(id=1, openphone_conversation_id="op_conv_123")
        mock_query = Mock()
        mock_query.filter_by.return_value.first.return_value = mock_conversation
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.find_by_openphone_id("op_conv_123")
        
        # Assert
        assert result == mock_conversation
        mock_query.filter_by.assert_called_once_with(openphone_conversation_id="op_conv_123")
    
    def test_find_recent_conversations(self, repository, mock_session):
        """Test finding recent conversations"""
        # Arrange
        mock_conversations = [Mock(id=1), Mock(id=2)]
        mock_query = Mock()
        mock_query.order_by.return_value.limit.return_value.all.return_value = mock_conversations
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.find_recent_conversations(limit=25)
        
        # Assert
        assert result == mock_conversations
        mock_query.order_by.assert_called_once()
        mock_query.order_by.return_value.limit.assert_called_once_with(25)
    
    def test_find_active_conversations(self, repository, mock_session):
        """Test finding active conversations"""
        # Arrange
        mock_conversations = [Mock(id=1, last_activity_at=datetime.utcnow())]
        mock_query = Mock()
        mock_query.filter.return_value.order_by.return_value.all.return_value = mock_conversations
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.find_active_conversations()
        
        # Assert
        assert result == mock_conversations
        mock_query.filter.assert_called_once()
    
    def test_get_conversations_page(self, repository, mock_session):
        """Test getting paginated conversations"""
        # Arrange
        mock_conversations = [Mock(id=1), Mock(id=2)]
        mock_query = Mock()
        mock_session.query.return_value = mock_query
        mock_query.count.return_value = 50
        mock_query.order_by.return_value.limit.return_value.offset.return_value.all.return_value = mock_conversations
        
        # Act
        result = repository.get_conversations_page(page=2, per_page=20)
        
        # Assert
        assert isinstance(result, PaginatedResult)
        assert result.items == mock_conversations
        assert result.total == 50
        assert result.page == 2
        assert result.per_page == 20
    
    def test_update_last_activity(self, repository, mock_session):
        """Test updating conversation's last activity time"""
        # Arrange
        mock_conversation = Mock(id=1, last_activity_at=None)
        mock_query = Mock()
        mock_query.get.return_value = mock_conversation
        mock_session.query.return_value = mock_query
        new_time = datetime.utcnow()
        
        # Act
        result = repository.update_last_activity(1, new_time)
        
        # Assert
        assert result == mock_conversation
        assert mock_conversation.last_activity_at == new_time
        mock_session.commit.assert_called_once()
    
    def test_count_by_status(self, repository, mock_session):
        """Test counting conversations by status"""
        # Arrange
        mock_query = Mock()
        mock_query.filter.return_value.count.return_value = 15
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.count_by_status("active")
        
        # Assert
        assert result == 15
        mock_query.filter.assert_called_once()
    
    def test_find_or_create_for_contact(self, repository, mock_session):
        """Test finding or creating conversation for contact"""
        # Arrange
        mock_query = Mock()
        mock_query.filter_by.return_value.first.return_value = None  # No existing conversation
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.find_or_create_for_contact(123)
        
        # Assert
        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()
        # Verify the created conversation
        created_conv = mock_session.add.call_args[0][0]
        assert created_conv.contact_id == 123
    
    def test_archive_conversation(self, repository, mock_session):
        """Test archiving a conversation"""
        # Arrange
        mock_conversation = Mock(id=1)
        mock_query = Mock()
        mock_query.get.return_value = mock_conversation
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.archive_conversation(1)
        
        # Assert
        assert result is True
        mock_session.commit.assert_called_once()
    
    def test_search(self, repository, mock_session):
        """Test searching conversations"""
        # Arrange
        mock_conversations = [Mock(id=1)]
        mock_query = Mock()
        mock_query.join.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.distinct.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = mock_conversations
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.search("test query")
        
        # Assert
        assert result == mock_conversations
        mock_query.join.assert_called()
        mock_query.filter.assert_called()
        mock_query.distinct.assert_called_once()

    # New enhanced methods for service refactoring
    def test_find_conversations_with_filters_search_query(self, repository, mock_session):
        """Test finding conversations with search query filter"""
        # Arrange
        search_query = "john"
        mock_conversations = [Mock(id=1, contact=Mock(first_name="John"))]
        mock_query = Mock()
        
        # Complex mock chain for joins and filters
        mock_query.options.return_value = mock_query
        mock_query.join.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.count.return_value = 10
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = mock_conversations
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.find_conversations_with_filters(
            search_query=search_query,
            page=1,
            per_page=20
        )
        
        # Assert
        assert result['conversations'] == mock_conversations
        assert result['total_count'] == 10
        mock_query.options.assert_called_once()
        mock_query.join.assert_called()
        mock_query.filter.assert_called()
    
    def test_find_conversations_with_filters_unread_filter(self, repository, mock_session):
        """Test finding conversations with unread filter"""
        # Arrange
        mock_conversations = [Mock(id=1)]
        mock_query = Mock()
        mock_subquery = Mock()
        
        # Setup mock chain
        mock_query.options.return_value = mock_query
        mock_query.join.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.count.return_value = 5
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = mock_conversations
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.find_conversations_with_filters(
            filter_type='unread',
            page=1,
            per_page=20
        )
        
        # Assert
        assert result['conversations'] == mock_conversations
        assert result['total_count'] == 5
    
    def test_find_conversations_with_filters_has_attachments(self, repository, mock_session):
        """Test finding conversations with attachments filter"""
        # Arrange
        mock_conversations = [Mock(id=1)]
        mock_query = Mock()
        
        # Setup mock chain for attachment filtering
        mock_query.options.return_value = mock_query
        mock_query.join.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.count.return_value = 3
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = mock_conversations
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.find_conversations_with_filters(
            filter_type='has_attachments',
            page=1,
            per_page=20
        )
        
        # Assert
        assert result['conversations'] == mock_conversations
        assert result['total_count'] == 3
    
    def test_find_conversations_with_filters_office_numbers(self, repository, mock_session):
        """Test finding conversations with office numbers filter"""
        # Arrange
        mock_conversations = [Mock(id=1)]
        mock_query = Mock()
        
        # Setup mock chain
        mock_query.options.return_value = mock_query
        mock_query.join.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.count.return_value = 2
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = mock_conversations
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.find_conversations_with_filters(
            filter_type='office_numbers',
            page=1,
            per_page=20
        )
        
        # Assert
        assert result['conversations'] == mock_conversations
        assert result['total_count'] == 2
    
    def test_find_conversations_with_filters_date_filter_today(self, repository, mock_session):
        """Test finding conversations with today date filter"""
        # Arrange
        mock_conversations = [Mock(id=1)]
        mock_query = Mock()
        
        # Setup mock chain
        mock_query.options.return_value = mock_query
        mock_query.join.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.count.return_value = 8
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = mock_conversations
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.find_conversations_with_filters(
            date_filter='today',
            page=1,
            per_page=20
        )
        
        # Assert
        assert result['conversations'] == mock_conversations
        assert result['total_count'] == 8
    
    def test_find_conversations_with_filters_date_filter_week(self, repository, mock_session):
        """Test finding conversations with week date filter"""
        # Arrange
        mock_conversations = [Mock(id=1)]
        mock_query = Mock()
        
        # Setup mock chain
        mock_query.options.return_value = mock_query
        mock_query.join.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.count.return_value = 15
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = mock_conversations
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.find_conversations_with_filters(
            date_filter='week',
            page=1,
            per_page=20
        )
        
        # Assert
        assert result['conversations'] == mock_conversations
        assert result['total_count'] == 15
    
    def test_find_conversations_with_filters_date_filter_month(self, repository, mock_session):
        """Test finding conversations with month date filter"""
        # Arrange
        mock_conversations = [Mock(id=1)]
        mock_query = Mock()
        
        # Setup mock chain
        mock_query.options.return_value = mock_query
        mock_query.join.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.count.return_value = 25
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = mock_conversations
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.find_conversations_with_filters(
            date_filter='month',
            page=1,
            per_page=20
        )
        
        # Assert
        assert result['conversations'] == mock_conversations
        assert result['total_count'] == 25
    
    def test_get_office_flags_batch(self, repository, mock_session):
        """Test batch lookup of office flags for contacts"""
        # Arrange
        contact_ids = [1, 2, 3]
        mock_flags = [Mock(contact_id=1), Mock(contact_id=3)]
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = mock_flags
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.get_office_flags_batch(contact_ids)
        
        # Assert
        assert result == {1, 3}
        mock_query.filter.assert_called()
    
    def test_get_office_flags_batch_empty_list(self, repository, mock_session):
        """Test batch lookup with empty contact list"""
        # Act
        result = repository.get_office_flags_batch([])
        
        # Assert
        assert result == set()
        mock_session.query.assert_not_called()
    
    def test_bulk_update_last_activity(self, repository, mock_session):
        """Test bulk updating last activity for multiple conversations"""
        # Arrange
        conversation_ids = [1, 2, 3]
        new_time = datetime.utcnow()
        mock_conversations = [Mock(id=1), Mock(id=2), Mock(id=3)]
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = mock_conversations
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.bulk_update_last_activity(conversation_ids, new_time)
        
        # Assert
        assert result is True
        # Verify each conversation had its last_activity_at updated
        for conv in mock_conversations:
            assert conv.last_activity_at == new_time
        mock_session.commit.assert_called_once()
    
    def test_bulk_update_last_activity_empty_list(self, repository, mock_session):
        """Test bulk update with empty conversation list"""
        # Act
        result = repository.bulk_update_last_activity([], datetime.utcnow())
        
        # Assert
        assert result is False
        mock_session.query.assert_not_called()
    
    def test_bulk_update_last_activity_with_error(self, repository, mock_session):
        """Test bulk update handles database errors"""
        # Arrange
        conversation_ids = [1, 2]
        new_time = datetime.utcnow()
        mock_session.commit.side_effect = Exception("Database error")
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = [Mock(id=1), Mock(id=2)]
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.bulk_update_last_activity(conversation_ids, new_time)
        
        # Assert
        assert result is False
        mock_session.rollback.assert_called_once()
    
    def test_find_conversations_by_ids_with_contact_info(self, repository, mock_session):
        """Test finding conversations by IDs with contact information"""
        # Arrange
        conversation_ids = [1, 2, 3]
        mock_conversations = [Mock(id=1), Mock(id=2), Mock(id=3)]
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.options.return_value = mock_query
        mock_query.all.return_value = mock_conversations
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.find_conversations_by_ids_with_contact_info(conversation_ids)
        
        # Assert
        assert result == mock_conversations
        mock_query.filter.assert_called()
        mock_query.options.assert_called_once()  # joinedload for contact info
    
    def test_find_conversations_by_ids_with_contact_info_empty_list(self, repository, mock_session):
        """Test finding conversations with empty ID list"""
        # Act
        result = repository.find_conversations_by_ids_with_contact_info([])
        
        # Assert
        assert result == []
        mock_session.query.assert_not_called()
    
    def test_get_activity_counts_for_conversations(self, repository, mock_session):
        """Test getting activity counts for conversations"""
        # Arrange
        conversation_ids = [1, 2, 3]
        mock_results = [(1, 5), (2, 3), (3, 10)]  # (conversation_id, count)
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.group_by.return_value = mock_query
        mock_query.all.return_value = mock_results
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.get_activity_counts_for_conversations(conversation_ids)
        
        # Assert
        expected = {1: 5, 2: 3, 3: 10}
        assert result == expected
        mock_query.filter.assert_called()
        mock_query.group_by.assert_called()
    
    def test_get_activity_counts_for_conversations_empty_list(self, repository, mock_session):
        """Test getting activity counts with empty conversation list"""
        # Act
        result = repository.get_activity_counts_for_conversations([])
        
        # Assert
        assert result == {}
        mock_session.query.assert_not_called()