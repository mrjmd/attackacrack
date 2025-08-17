"""
Tests for ConversationRepository
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime
from repositories.conversation_repository import ConversationRepository
from repositories.base_repository import PaginatedResult
from crm_database import Conversation


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