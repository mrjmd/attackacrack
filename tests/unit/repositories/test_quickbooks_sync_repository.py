"""
Tests for QuickBooksSyncRepository
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime
from repositories.quickbooks_sync_repository import QuickBooksSyncRepository
from repositories.base_repository import PaginatedResult
from crm_database import QuickBooksSync


class TestQuickBooksSyncRepository:
    """Test suite for QuickBooksSyncRepository"""
    
    @pytest.fixture
    def mock_session(self):
        """Mock database session"""
        session = MagicMock()
        return session
    
    @pytest.fixture
    def repository(self, mock_session):
        """Create QuickBooksSyncRepository with mocked session"""
        return QuickBooksSyncRepository(mock_session, QuickBooksSync)
    
    def test_find_by_entity_type(self, repository, mock_session):
        """Test finding sync records by entity type"""
        # Arrange
        mock_syncs = [Mock(id=1, entity_type="customer")]
        mock_query = Mock()
        mock_query.filter_by.return_value.all.return_value = mock_syncs
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.find_by_entity_type("customer")
        
        # Assert
        assert result == mock_syncs
        mock_query.filter_by.assert_called_once_with(entity_type="customer")
    
    def test_find_by_entity_id(self, repository, mock_session):
        """Test finding sync record by QB entity ID"""
        # Arrange
        mock_sync = Mock(id=1, entity_id="QB123")
        mock_query = Mock()
        mock_query.filter_by.return_value.first.return_value = mock_sync
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.find_by_entity_id("QB123")
        
        # Assert
        assert result == mock_sync
        mock_query.filter_by.assert_called_once_with(entity_id="QB123")
    
    def test_find_by_local_id(self, repository, mock_session):
        """Test finding sync record by local ID"""
        # Arrange
        mock_sync = Mock(id=1, local_id=456)
        mock_query = Mock()
        mock_query.filter_by.return_value.first.return_value = mock_sync
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.find_by_local_id(456, "contact")
        
        # Assert
        assert result == mock_sync
        mock_query.filter_by.assert_called_once_with(local_id=456, local_table="contact")
    
    def test_find_pending_syncs(self, repository, mock_session):
        """Test finding pending sync records"""
        # Arrange
        mock_syncs = [Mock(id=1, sync_status="pending")]
        mock_query = Mock()
        mock_query.filter_by.return_value.all.return_value = mock_syncs
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.find_pending_syncs()
        
        # Assert
        assert result == mock_syncs
        mock_query.filter_by.assert_called_once_with(sync_status="pending")
    
    def test_find_failed_syncs(self, repository, mock_session):
        """Test finding failed sync records"""
        # Arrange
        mock_syncs = [Mock(id=1, sync_status="error")]
        mock_query = Mock()
        mock_query.filter_by.return_value.all.return_value = mock_syncs
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.find_failed_syncs()
        
        # Assert
        assert result == mock_syncs
        mock_query.filter_by.assert_called_once_with(sync_status="error")
    
    def test_update_sync_status(self, repository, mock_session):
        """Test updating sync status"""
        # Arrange
        mock_sync = Mock(id=1, sync_status="pending")
        mock_query = Mock()
        mock_query.get.return_value = mock_sync
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.update_sync_status(1, "synced")
        
        # Assert
        assert result == mock_sync
        assert mock_sync.sync_status == "synced"
        assert mock_sync.last_synced is not None
        mock_session.commit.assert_called_once()
    
    def test_mark_as_failed(self, repository, mock_session):
        """Test marking sync as failed"""
        # Arrange
        mock_sync = Mock(id=1, sync_status="pending", error_message=None)
        mock_query = Mock()
        mock_query.get.return_value = mock_sync
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.mark_as_failed(1, "Sync error occurred")
        
        # Assert
        assert result == mock_sync
        assert mock_sync.sync_status == "error"
        assert mock_sync.error_message == "Sync error occurred"
        mock_session.commit.assert_called_once()
    
    def test_search(self, repository, mock_session):
        """Test searching sync records"""
        # Arrange
        mock_syncs = [Mock(id=1)]
        mock_query = Mock()
        mock_query.filter.return_value.limit.return_value.all.return_value = mock_syncs
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.search("QB123")
        
        # Assert
        assert result == mock_syncs
        mock_query.filter.assert_called_once()