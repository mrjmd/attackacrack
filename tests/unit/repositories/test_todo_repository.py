"""
Tests for TodoRepository
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime, date
from utils.datetime_utils import utc_now
from repositories.todo_repository import TodoRepository
from repositories.base_repository import PaginatedResult
from crm_database import Todo


class TestTodoRepository:
    """Test suite for TodoRepository"""
    
    @pytest.fixture
    def mock_session(self):
        """Mock database session"""
        session = MagicMock()
        return session
    
    @pytest.fixture
    def repository(self, mock_session):
        """Create TodoRepository with mocked session"""
        return TodoRepository(mock_session)
    
    def test_find_by_priority(self, repository, mock_session):
        """Test finding todos by priority"""
        # Arrange
        mock_todos = [Mock(id=1, priority="high")]
        mock_query = Mock()
        mock_query.filter_by.return_value.all.return_value = mock_todos
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.find_by_priority("high")
        
        # Assert
        assert result == mock_todos
        mock_query.filter_by.assert_called_once_with(priority="high")
    
    def test_find_completed_todos(self, repository, mock_session):
        """Test finding completed todos"""
        # Arrange
        mock_todos = [Mock(id=1, is_completed=True)]
        mock_query = Mock()
        mock_query.filter_by.return_value.all.return_value = mock_todos
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.find_completed_todos()
        
        # Assert
        assert result == mock_todos
        mock_query.filter_by.assert_called_once_with(is_completed=True)
    
    def test_find_pending_todos(self, repository, mock_session):
        """Test finding pending todos"""
        # Arrange
        mock_todos = [Mock(id=1, is_completed=False)]
        mock_query = Mock()
        mock_query.filter_by.return_value.all.return_value = mock_todos
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.find_pending_todos()
        
        # Assert
        assert result == mock_todos
        mock_query.filter_by.assert_called_once_with(is_completed=False)
    
    def test_find_overdue_todos(self, repository, mock_session):
        """Test finding overdue todos"""
        # Arrange
        mock_todos = [Mock(id=1)]
        mock_query = Mock()
        # Chain the filter calls
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = mock_todos
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.find_overdue_todos()
        
        # Assert
        assert result == mock_todos
        assert mock_query.filter.call_count == 2
    
    def test_mark_as_completed(self, repository, mock_session):
        """Test marking todo as completed"""
        # Arrange
        mock_todo = Mock(id=1, is_completed=False, completed_at=None)
        mock_query = Mock()
        mock_query.get.return_value = mock_todo
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.mark_as_completed(1)
        
        # Assert
        assert result == mock_todo
        assert mock_todo.is_completed is True
        assert mock_todo.completed_at is not None
        mock_session.commit.assert_called_once()
    
    def test_mark_as_pending(self, repository, mock_session):
        """Test marking todo as pending"""
        # Arrange
        mock_todo = Mock(id=1, is_completed=True, completed_at=utc_now())
        mock_query = Mock()
        mock_query.get.return_value = mock_todo
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.mark_as_pending(1)
        
        # Assert
        assert result == mock_todo
        assert mock_todo.is_completed is False
        assert mock_todo.completed_at is None
        mock_session.commit.assert_called_once()
    
    def test_update_priority(self, repository, mock_session):
        """Test updating todo priority"""
        # Arrange
        mock_todo = Mock(id=1, priority="medium")
        mock_query = Mock()
        mock_query.get.return_value = mock_todo
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.update_priority(1, "high")
        
        # Assert
        assert result == mock_todo
        assert mock_todo.priority == "high"
        mock_session.commit.assert_called_once()
    
    def test_search(self, repository, mock_session):
        """Test searching todos"""
        # Arrange
        mock_todos = [Mock(id=1)]
        mock_query = Mock()
        mock_query.filter.return_value.limit.return_value.all.return_value = mock_todos
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.search("urgent")
        
        # Assert
        assert result == mock_todos
        mock_query.filter.assert_called_once()