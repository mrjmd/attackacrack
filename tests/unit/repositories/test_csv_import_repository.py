"""
CSVImportRepository Tests - Test data access layer for CSVImport entities
TDD RED Phase: Write comprehensive tests BEFORE implementation
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock
from sqlalchemy.exc import SQLAlchemyError

from repositories.csv_import_repository import CSVImportRepository
from crm_database import CSVImport
from repositories.base_repository import PaginationParams, PaginatedResult, SortOrder


class TestCSVImportRepository:
    """Test CSVImportRepository functionality"""
    
    @pytest.fixture
    def mock_session(self):
        """Create mock database session"""
        return Mock()
    
    @pytest.fixture
    def repository(self, mock_session):
        """Create repository instance with mocked dependencies"""
        return CSVImportRepository(session=mock_session)
    
    @pytest.fixture
    def sample_import_data(self):
        """Sample CSV import data for testing"""
        return {
            'filename': 'test_contacts.csv',
            'imported_by': 'test_user',
            'import_type': 'contacts',
            'total_rows': 100,
            'successful_imports': 95,
            'failed_imports': 5,
            'import_metadata': {'format': 'standard', 'delimiter': ','}
        }
    
    def test_search_by_filename(self, repository, mock_session):
        """Test searching imports by filename"""
        # Arrange
        query_text = 'contacts'
        expected_imports = [Mock(spec=CSVImport)]
        mock_query = Mock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = expected_imports
        
        # Act
        result = repository.search(query_text, limit=10)
        
        # Assert
        assert result == expected_imports
        mock_session.query.assert_called_once_with(CSVImport)
    
    def test_search_empty_query_returns_empty_list(self, repository):
        """Test that empty search query returns empty list"""
        result = repository.search('')
        assert result == []
    
    def test_find_by_filename(self, repository):
        """Test finding import by filename"""
        # Arrange
        filename = 'test_contacts.csv'
        expected_import = Mock(spec=CSVImport)
        repository.find_one_by = Mock(return_value=expected_import)
        
        # Act
        result = repository.find_by_filename(filename)
        
        # Assert
        assert result == expected_import
        repository.find_one_by.assert_called_once_with(filename=filename)
    
    def test_find_by_import_type(self, repository):
        """Test finding imports by type"""
        # Arrange
        import_type = 'contacts'
        expected_imports = [Mock(spec=CSVImport), Mock(spec=CSVImport)]
        repository.find_by = Mock(return_value=expected_imports)
        
        # Act
        result = repository.find_by_import_type(import_type)
        
        # Assert
        assert result == expected_imports
        repository.find_by.assert_called_once_with(import_type=import_type)
    
    def test_find_by_imported_by(self, repository):
        """Test finding imports by user"""
        # Arrange
        imported_by = 'test_user'
        expected_imports = [Mock(spec=CSVImport)]
        repository.find_by = Mock(return_value=expected_imports)
        
        # Act
        result = repository.find_by_imported_by(imported_by)
        
        # Assert
        assert result == expected_imports
        repository.find_by.assert_called_once_with(imported_by=imported_by)
    
    def test_get_recent_imports(self, repository, mock_session):
        """Test getting recent imports with limit"""
        # Arrange
        limit = 5
        expected_imports = [Mock(spec=CSVImport) for _ in range(limit)]
        mock_query = Mock()
        mock_session.query.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = expected_imports
        
        # Act
        result = repository.get_recent_imports(limit=limit)
        
        # Assert
        assert result == expected_imports
        assert len(result) == limit
        mock_query.order_by.assert_called_once()
        mock_query.limit.assert_called_once_with(limit)
    
    def test_get_imports_by_date_range(self, repository, mock_session):
        """Test getting imports within date range"""
        # Arrange
        start_date = datetime(2023, 1, 1)
        end_date = datetime(2023, 12, 31)
        expected_imports = [Mock(spec=CSVImport), Mock(spec=CSVImport)]
        mock_query = Mock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = expected_imports
        
        # Act
        result = repository.get_imports_by_date_range(start_date, end_date)
        
        # Assert
        assert result == expected_imports
        # Should have two filter calls for date range
        assert mock_query.filter.call_count == 2
    
    def test_get_successful_imports(self, repository, mock_session):
        """Test getting imports with no failures"""
        # Arrange
        expected_imports = [Mock(spec=CSVImport)]
        mock_query = Mock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = expected_imports
        
        # Act
        result = repository.get_successful_imports()
        
        # Assert
        assert result == expected_imports
        # Should filter for failed_imports == 0 OR failed_imports IS NULL
        mock_query.filter.assert_called_once()
    
    def test_get_failed_imports(self, repository, mock_session):
        """Test getting imports with failures"""
        # Arrange
        expected_imports = [Mock(spec=CSVImport)]
        mock_query = Mock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = expected_imports
        
        # Act
        result = repository.get_failed_imports()
        
        # Assert
        assert result == expected_imports
        # Should filter for failed_imports > 0
        mock_query.filter.assert_called_once()
    
    def test_get_import_stats_by_type(self, repository, mock_session):
        """Test getting statistics by import type"""
        # Arrange
        mock_stats = [('contacts', 10), ('properties', 5)]
        mock_query = Mock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.group_by.return_value = mock_query
        mock_query.all.return_value = mock_stats
        
        # Act
        result = repository.get_import_stats_by_type()
        
        # Assert
        expected = {'contacts': 10, 'properties': 5, 'total': 15}
        assert result == expected
    
    def test_get_import_stats_by_user(self, repository, mock_session):
        """Test getting statistics by user"""
        # Arrange
        mock_stats = [('user1', 15), ('user2', 8)]
        mock_query = Mock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.group_by.return_value = mock_query
        mock_query.all.return_value = mock_stats
        
        # Act
        result = repository.get_import_stats_by_user()
        
        # Assert
        expected = {'user1': 15, 'user2': 8, 'total': 23}
        assert result == expected
    
    def test_update_import_status(self, repository, mock_session):
        """Test updating import status after processing"""
        # Arrange
        import_id = 1
        total_rows = 100
        successful = 95
        failed = 5
        metadata = {'errors': ['Row 10: Invalid phone']}
        
        mock_import = Mock(spec=CSVImport)
        mock_import.id = import_id
        repository.get_by_id = Mock(return_value=mock_import)
        repository.update = Mock(return_value=mock_import)
        
        # Act
        result = repository.update_import_status(
            import_id, total_rows, successful, failed, metadata
        )
        
        # Assert
        assert result == mock_import
        repository.update.assert_called_once_with(
            mock_import,
            total_rows=total_rows,
            successful_imports=successful,
            failed_imports=failed,
            import_metadata=metadata
        )
    
    def test_update_import_status_not_found(self, repository):
        """Test updating import status when import not found"""
        # Arrange
        repository.get_by_id = Mock(return_value=None)
        
        # Act
        result = repository.update_import_status(999, 100, 95, 5, {})
        
        # Assert
        assert result is None
    
    def test_mark_import_completed(self, repository, mock_session):
        """Test marking import as completed"""
        # Arrange
        import_id = 1
        mock_import = Mock(spec=CSVImport)
        mock_import.import_metadata = {}
        repository.get_by_id = Mock(return_value=mock_import)
        repository.update = Mock(return_value=mock_import)
        
        # Act
        result = repository.mark_import_completed(import_id)
        
        # Assert
        assert result == mock_import
        repository.update.assert_called_once()
        # Check that metadata was updated with completed_at
        args, kwargs = repository.update.call_args
        assert 'import_metadata' in kwargs
        assert 'completed_at' in kwargs['import_metadata']
    
    def test_get_incomplete_imports(self, repository, mock_session):
        """Test getting imports without completion timestamp"""
        # Arrange
        expected_imports = [Mock(spec=CSVImport)]
        mock_query = Mock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = expected_imports
        
        # Act
        result = repository.get_incomplete_imports()
        
        # Assert
        assert result == expected_imports
        # Should filter for completed_at IS NULL OR total_rows IS NULL
        mock_query.filter.assert_called_once()
    
    def test_find_duplicate_filename_imports(self, repository, mock_session):
        """Test finding imports with same filename"""
        # Arrange
        filename = 'contacts.csv'
        expected_imports = [Mock(spec=CSVImport), Mock(spec=CSVImport)]
        mock_query = Mock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.all.return_value = expected_imports
        
        # Act
        result = repository.find_duplicate_filename_imports(filename)
        
        # Assert
        assert result == expected_imports
        mock_query.filter.assert_called_once()
        mock_query.order_by.assert_called_once()
    
    def test_get_total_imports_count(self, repository, mock_session):
        """Test getting total count of all imports"""
        # Arrange
        expected_count = 25
        repository.count = Mock(return_value=expected_count)
        
        # Act
        result = repository.get_total_imports_count()
        
        # Assert
        assert result == expected_count
        repository.count.assert_called_once()
    
    def test_delete_old_imports(self, repository, mock_session):
        """Test deleting imports older than specified days"""
        # Arrange
        days = 90
        expected_count = 5
        mock_query = Mock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.count.return_value = expected_count
        mock_query.delete.return_value = expected_count
        
        # Act
        result = repository.delete_old_imports(days)
        
        # Assert
        assert result == expected_count
        # Should call query twice - once for count, once for delete
        assert mock_session.query.call_count == 2
        mock_query.filter.assert_called()
        mock_query.delete.assert_called_once()
    
    def test_get_imports_with_errors(self, repository, mock_session):
        """Test getting imports that had processing errors"""
        # Arrange
        expected_imports = [Mock(spec=CSVImport)]
        mock_query = Mock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = expected_imports
        
        # Act
        result = repository.get_imports_with_errors()
        
        # Assert
        assert result == expected_imports
        # Should filter twice - once for metadata not null, once for errors key
        assert mock_query.filter.call_count == 2
    
    def test_search_handles_sql_error(self, repository, mock_session):
        """Test that search handles SQLAlchemy errors gracefully"""
        # Arrange
        mock_session.query.side_effect = SQLAlchemyError("Database error")
        
        # Act
        result = repository.search('test')
        
        # Assert
        assert result == []
    
    def test_repository_inherits_from_base(self, repository):
        """Test that repository properly inherits from BaseRepository"""
        # Should have all base repository methods
        assert hasattr(repository, 'create')
        assert hasattr(repository, 'get_by_id')
        assert hasattr(repository, 'update')
        assert hasattr(repository, 'delete')
        assert hasattr(repository, 'find_by')
        assert hasattr(repository, 'count')
    
    def test_model_class_is_csv_import(self, repository):
        """Test that repository is configured with correct model class"""
        assert repository.model_class == CSVImport
