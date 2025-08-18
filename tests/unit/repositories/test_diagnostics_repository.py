"""
DiagnosticsRepository Tests - Test data access layer for system diagnostics
TDD RED Phase: Write comprehensive tests BEFORE implementation

This repository handles:
- Database connectivity checks
- Model count queries 
- System health metrics
- Database statistics
"""

import pytest
from datetime import datetime
from unittest.mock import Mock, patch
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import text

from repositories.diagnostics_repository import DiagnosticsRepository
from crm_database import Contact, Conversation, Activity, Campaign, Todo


class TestDiagnosticsRepository:
    """Test DiagnosticsRepository functionality"""
    
    @pytest.fixture
    def mock_session(self):
        """Create mock database session"""
        return Mock()
    
    @pytest.fixture
    def repository(self, mock_session):
        """Create repository instance with mocked dependencies"""
        # DiagnosticsRepository doesn't use a model_class like other repositories
        return DiagnosticsRepository(session=mock_session)
    
    # Database Connectivity Tests
    
    def test_check_database_connection_success(self, repository, mock_session):
        """Test successful database connectivity check"""
        # Arrange
        mock_result = Mock()
        mock_session.execute.return_value = mock_result
        
        # Act
        result = repository.check_database_connection()
        
        # Assert
        assert result is True
        mock_session.execute.assert_called_once()
        # Verify it's called with a SELECT 1 query
        call_args = mock_session.execute.call_args[0]
        assert "SELECT 1" in str(call_args[0]) or call_args[0].text == "SELECT 1"
    
    def test_check_database_connection_failure(self, repository, mock_session):
        """Test database connectivity check failure"""
        # Arrange
        mock_session.execute.side_effect = SQLAlchemyError("Connection failed")
        
        # Act
        result = repository.check_database_connection()
        
        # Assert
        assert result is False
        mock_session.execute.assert_called_once()
    
    def test_get_connection_error_details(self, repository, mock_session):
        """Test getting detailed connection error information"""
        # Arrange
        error_msg = "Connection timeout"
        mock_session.execute.side_effect = SQLAlchemyError(error_msg)
        
        # Act
        result = repository.get_connection_error_details()
        
        # Assert
        assert error_msg in result
        mock_session.execute.assert_called_once()
    
    def test_get_connection_error_details_success(self, repository, mock_session):
        """Test getting connection error details when connection is successful"""
        # Arrange
        mock_session.execute.return_value = Mock()
        
        # Act
        result = repository.get_connection_error_details()
        
        # Assert
        assert result is None  # No error when connection succeeds
    
    # Model Count Tests
    
    def test_get_contact_count(self, repository, mock_session):
        """Test getting contact count"""
        # Arrange
        expected_count = 150
        mock_query = Mock()
        mock_session.query.return_value = mock_query
        mock_query.count.return_value = expected_count
        
        # Act
        result = repository.get_contact_count()
        
        # Assert
        assert result == expected_count
        mock_session.query.assert_called_once_with(Contact)
        mock_query.count.assert_called_once()
    
    def test_get_conversation_count(self, repository, mock_session):
        """Test getting conversation count"""
        # Arrange
        expected_count = 75
        mock_query = Mock()
        mock_session.query.return_value = mock_query
        mock_query.count.return_value = expected_count
        
        # Act
        result = repository.get_conversation_count()
        
        # Assert
        assert result == expected_count
        mock_session.query.assert_called_once_with(Conversation)
        mock_query.count.assert_called_once()
    
    def test_get_activity_count(self, repository, mock_session):
        """Test getting activity count"""
        # Arrange
        expected_count = 300
        mock_query = Mock()
        mock_session.query.return_value = mock_query
        mock_query.count.return_value = expected_count
        
        # Act
        result = repository.get_activity_count()
        
        # Assert
        assert result == expected_count
        mock_session.query.assert_called_once_with(Activity)
        mock_query.count.assert_called_once()
    
    def test_get_campaign_count(self, repository, mock_session):
        """Test getting campaign count"""
        # Arrange
        expected_count = 25
        mock_query = Mock()
        mock_session.query.return_value = mock_query
        mock_query.count.return_value = expected_count
        
        # Act
        result = repository.get_campaign_count()
        
        # Assert
        assert result == expected_count
        mock_session.query.assert_called_once_with(Campaign)
        mock_query.count.assert_called_once()
    
    def test_get_todo_count(self, repository, mock_session):
        """Test getting todo count"""
        # Arrange
        expected_count = 45
        mock_query = Mock()
        mock_session.query.return_value = mock_query
        mock_query.count.return_value = expected_count
        
        # Act
        result = repository.get_todo_count()
        
        # Assert
        assert result == expected_count
        mock_session.query.assert_called_once_with(Todo)
        mock_query.count.assert_called_once()
    
    def test_get_all_model_counts(self, repository, mock_session):
        """Test getting counts for all models at once"""
        # Arrange
        expected_counts = {
            'contacts': 150,
            'conversations': 75,
            'activities': 300,
            'campaigns': 25,
            'todos': 45
        }
        
        def mock_query_count(model_class):
            mock_query = Mock()
            if model_class == Contact:
                mock_query.count.return_value = 150
            elif model_class == Conversation:
                mock_query.count.return_value = 75
            elif model_class == Activity:
                mock_query.count.return_value = 300
            elif model_class == Campaign:
                mock_query.count.return_value = 25
            elif model_class == Todo:
                mock_query.count.return_value = 45
            return mock_query
        
        mock_session.query.side_effect = mock_query_count
        
        # Act
        result = repository.get_all_model_counts()
        
        # Assert
        assert result == expected_counts
        assert mock_session.query.call_count == 5  # One for each model
    
    # Error Handling Tests
    
    def test_get_contact_count_handles_error(self, repository, mock_session):
        """Test that contact count handles SQLAlchemy errors gracefully"""
        # Arrange
        mock_session.query.side_effect = SQLAlchemyError("Query failed")
        
        # Act
        result = repository.get_contact_count()
        
        # Assert
        assert result == 0  # Should return 0 on error
    
    def test_get_all_model_counts_handles_partial_errors(self, repository, mock_session):
        """Test that model counts handle partial failures gracefully"""
        # Arrange - Contact query fails, others succeed
        def mock_query_with_error(model_class):
            if model_class == Contact:
                raise SQLAlchemyError("Contact query failed")
            mock_query = Mock()
            mock_query.count.return_value = 10
            return mock_query
        
        mock_session.query.side_effect = mock_query_with_error
        
        # Act
        result = repository.get_all_model_counts()
        
        # Assert
        assert result['contacts'] == 0  # Failed query returns 0
        assert result['conversations'] == 10  # Successful queries return actual count
        assert all(count >= 0 for count in result.values())  # No negative counts
    
    # Advanced Database Statistics
    
    def test_get_database_size_info(self, repository, mock_session):
        """Test getting database size information"""
        # Arrange
        mock_result = Mock()
        mock_result.scalar.return_value = 524288000  # 500MB in bytes
        mock_session.execute.return_value = mock_result
        
        # Act
        result = repository.get_database_size_info()
        
        # Assert
        assert result['size_bytes'] == 524288000
        assert result['size_mb'] == 500.0
        mock_session.execute.assert_called_once()
    
    def test_get_table_statistics(self, repository, mock_session):
        """Test getting table-level statistics"""
        # Arrange
        mock_results = [
            ('public', 'contacts', 150, 1048576),    # schema, table_name, row_count, size_bytes
            ('public', 'conversations', 75, 524288),
            ('public', 'activities', 300, 2097152)
        ]
        mock_result = Mock()
        mock_result.fetchall.return_value = mock_results
        mock_session.execute.return_value = mock_result
        
        # Act
        result = repository.get_table_statistics()
        
        # Assert
        expected = {
            'contacts': {'row_count': 150, 'size_bytes': 1048576},
            'conversations': {'row_count': 75, 'size_bytes': 524288},
            'activities': {'row_count': 300, 'size_bytes': 2097152}
        }
        assert result == expected
        mock_session.execute.assert_called_once()
    
    def test_get_connection_pool_stats(self, repository, mock_session):
        """Test getting database connection pool statistics"""
        # Arrange
        mock_engine = Mock()
        mock_pool = Mock()
        mock_pool.size.return_value = 5
        mock_pool.checked_in.return_value = 3
        mock_pool.checked_out.return_value = 2
        mock_pool.overflow.return_value = 0
        mock_pool.invalid.return_value = 0  # Mock the invalid method too
        mock_engine.pool = mock_pool
        mock_session.get_bind.return_value = mock_engine
        
        # Act
        result = repository.get_connection_pool_stats()
        
        # Assert
        expected = {
            'pool_size': 5,
            'checked_in': 3,
            'checked_out': 2,
            'overflow': 0,
            'invalid': 0  # Default when not available
        }
        assert result == expected
    
    def test_get_connection_pool_stats_handles_error(self, repository, mock_session):
        """Test connection pool stats when pool info unavailable"""
        # Arrange
        mock_session.get_bind.side_effect = AttributeError("No bind")
        
        # Act
        result = repository.get_connection_pool_stats()
        
        # Assert
        assert result == {}  # Empty dict when unavailable
    
    # Health Check Tests
    
    def test_perform_health_check(self, repository, mock_session):
        """Test comprehensive health check"""
        # Arrange
        mock_session.execute.return_value = Mock()  # Successful connection
        
        # Mock individual methods to avoid complex side effects
        repository.get_all_model_counts = Mock(return_value={'contacts': 10})
        repository.get_connection_pool_stats = Mock(return_value={'pool_size': 5})
        repository.get_database_size_info = Mock(return_value={'size_mb': 100})
        
        # Act
        result = repository.perform_health_check()
        
        # Assert
        assert result['database_connected'] is True
        assert result['model_counts']['contacts'] == 10
        assert 'timestamp' in result
    
    def test_perform_health_check_database_down(self, repository, mock_session):
        """Test health check when database is down"""
        # Arrange
        mock_session.execute.side_effect = SQLAlchemyError("Database down")
        
        # Act
        result = repository.perform_health_check()
        
        # Assert
        assert result['database_connected'] is False
        assert 'error' in result
        assert result['model_counts'] == {}  # Empty when DB is down
    
    def test_repository_session_management(self, repository, mock_session):
        """Test that repository properly manages database session"""
        # Verify repository stores session correctly
        assert repository.session == mock_session
    
    def test_repository_error_logging(self, repository, mock_session):
        """Test that repository logs errors appropriately"""
        # Arrange
        mock_session.execute.side_effect = SQLAlchemyError("Test error")
        
        with patch('repositories.diagnostics_repository.logger') as mock_logger:
            # Act
            repository.check_database_connection()
            
            # Assert
            mock_logger.error.assert_called_once()
            assert "Test error" in mock_logger.error.call_args[0][0]
