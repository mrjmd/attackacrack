"""
ContactCSVImportRepository Tests - Test data access layer for ContactCSVImport entities
TDD RED Phase: Write comprehensive tests BEFORE implementation
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock
from sqlalchemy.exc import SQLAlchemyError

from repositories.contact_csv_import_repository import ContactCSVImportRepository
from crm_database import ContactCSVImport, Contact, CSVImport
from repositories.base_repository import PaginationParams, PaginatedResult, SortOrder


class TestContactCSVImportRepository:
    """Test ContactCSVImportRepository functionality"""
    
    @pytest.fixture
    def mock_session(self):
        """Create mock database session"""
        return Mock()
    
    @pytest.fixture
    def repository(self, mock_session):
        """Create repository instance with mocked dependencies"""
        return ContactCSVImportRepository(session=mock_session, model_class=ContactCSVImport)
    
    @pytest.fixture
    def sample_association_data(self):
        """Sample contact-import association data for testing"""
        return {
            'contact_id': 123,
            'csv_import_id': 456,
            'is_new': True,
            'data_updated': {'first_name': 'John', 'last_name': 'Doe'}
        }
    
    def test_search_by_contact_info(self, repository, mock_session):
        """Test searching associations by contact information"""
        # Arrange
        query_text = 'john'
        expected_associations = [Mock(spec=ContactCSVImport)]
        mock_query = Mock()
        mock_session.query.return_value = mock_query
        mock_query.join.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = expected_associations
        
        # Act
        result = repository.search(query_text, limit=10)
        
        # Assert
        assert result == expected_associations
        mock_session.query.assert_called_once_with(ContactCSVImport)
        mock_query.join.assert_called_once_with(Contact)
    
    def test_search_empty_query_returns_empty_list(self, repository):
        """Test that empty search query returns empty list"""
        result = repository.search('')
        assert result == []
    
    def test_find_by_contact_id(self, repository):
        """Test finding associations by contact ID"""
        # Arrange
        contact_id = 123
        expected_associations = [Mock(spec=ContactCSVImport)]
        repository.find_by = Mock(return_value=expected_associations)
        
        # Act
        result = repository.find_by_contact_id(contact_id)
        
        # Assert
        assert result == expected_associations
        repository.find_by.assert_called_once_with(contact_id=contact_id)
    
    def test_find_by_csv_import_id(self, repository):
        """Test finding associations by CSV import ID"""
        # Arrange
        csv_import_id = 456
        expected_associations = [Mock(spec=ContactCSVImport)]
        repository.find_by = Mock(return_value=expected_associations)
        
        # Act
        result = repository.find_by_csv_import_id(csv_import_id)
        
        # Assert
        assert result == expected_associations
        repository.find_by.assert_called_once_with(csv_import_id=csv_import_id)
    
    def test_find_by_contact_and_import(self, repository):
        """Test finding specific association by contact and import IDs"""
        # Arrange
        contact_id = 123
        csv_import_id = 456
        expected_association = Mock(spec=ContactCSVImport)
        repository.find_one_by = Mock(return_value=expected_association)
        
        # Act
        result = repository.find_by_contact_and_import(contact_id, csv_import_id)
        
        # Assert
        assert result == expected_association
        repository.find_one_by.assert_called_once_with(
            contact_id=contact_id, csv_import_id=csv_import_id
        )
    
    def test_exists_for_contact_and_import(self, repository, mock_session):
        """Test checking if association exists for contact and import"""
        # Arrange
        contact_id = 123
        csv_import_id = 456
        repository.exists = Mock(return_value=True)
        
        # Act
        result = repository.exists_for_contact_and_import(contact_id, csv_import_id)
        
        # Assert
        assert result is True
        repository.exists.assert_called_once_with(
            contact_id=contact_id, csv_import_id=csv_import_id
        )
    
    def test_get_new_contacts_for_import(self, repository, mock_session):
        """Test getting new contacts created during import"""
        # Arrange
        csv_import_id = 456
        expected_associations = [Mock(spec=ContactCSVImport)]
        mock_query = Mock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = expected_associations
        
        # Act
        result = repository.get_new_contacts_for_import(csv_import_id)
        
        # Assert
        assert result == expected_associations
        # Should filter for specific import AND is_new=True
        mock_query.filter.assert_called_once()
    
    def test_get_updated_contacts_for_import(self, repository, mock_session):
        """Test getting existing contacts updated during import"""
        # Arrange
        csv_import_id = 456
        expected_associations = [Mock(spec=ContactCSVImport)]
        mock_query = Mock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = expected_associations
        
        # Act
        result = repository.get_updated_contacts_for_import(csv_import_id)
        
        # Assert
        assert result == expected_associations
        # Should filter for specific import AND is_new=False
        mock_query.filter.assert_called_once()
    
    def test_get_contacts_with_updated_data(self, repository, mock_session):
        """Test getting associations where data was actually updated"""
        # Arrange
        csv_import_id = 456
        expected_associations = [Mock(spec=ContactCSVImport)]
        mock_query = Mock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = expected_associations
        
        # Act
        result = repository.get_contacts_with_updated_data(csv_import_id)
        
        # Assert
        assert result == expected_associations
        # Should filter for data_updated IS NOT NULL
        mock_query.filter.assert_called_once()
    
    def test_get_import_statistics(self, repository, mock_session):
        """Test getting statistics for an import"""
        # Arrange
        csv_import_id = 456
        mock_stats = [
            (True, 85),   # new contacts
            (False, 15)   # updated contacts
        ]
        mock_query = Mock()
        mock_session.query.return_value = mock_query
        mock_query.filter_by.return_value = mock_query
        mock_query.group_by.return_value = mock_query
        mock_query.all.return_value = mock_stats
        
        # Act
        result = repository.get_import_statistics(csv_import_id)
        
        # Assert
        expected = {
            'total_associations': 100,
            'new_contacts': 85,
            'updated_contacts': 15
        }
        assert result == expected
    
    def test_get_contacts_by_import_with_details(self, repository, mock_session):
        """Test getting contacts with full association details"""
        # Arrange
        csv_import_id = 456
        expected_results = [
            (Mock(spec=Contact), Mock(spec=ContactCSVImport)),
            (Mock(spec=Contact), Mock(spec=ContactCSVImport))
        ]
        mock_query = Mock()
        mock_session.query.return_value = mock_query
        mock_query.join.return_value = mock_query
        mock_query.filter_by.return_value = mock_query
        mock_query.all.return_value = expected_results
        
        # Act
        result = repository.get_contacts_by_import_with_details(csv_import_id)
        
        # Assert
        assert result == expected_results
        # Join is called with Contact and a condition, so we just check it was called
        mock_query.join.assert_called_once()
        mock_query.filter_by.assert_called_once_with(csv_import_id=csv_import_id)
    
    def test_bulk_create_associations(self, repository, mock_session):
        """Test bulk creating contact-import associations"""
        # Arrange
        associations_data = [
            {'contact_id': 1, 'csv_import_id': 456, 'is_new': True},
            {'contact_id': 2, 'csv_import_id': 456, 'is_new': False}
        ]
        expected_associations = [Mock(spec=ContactCSVImport), Mock(spec=ContactCSVImport)]
        repository.create_many = Mock(return_value=expected_associations)
        
        # Act
        result = repository.bulk_create_associations(associations_data)
        
        # Assert
        assert result == expected_associations
        repository.create_many.assert_called_once_with(associations_data)
    
    def test_delete_associations_for_import(self, repository, mock_session):
        """Test deleting all associations for a specific import"""
        # Arrange
        csv_import_id = 456
        expected_count = 10
        repository.delete_many = Mock(return_value=expected_count)
        
        # Act
        result = repository.delete_associations_for_import(csv_import_id)
        
        # Assert
        assert result == expected_count
        repository.delete_many.assert_called_once_with({'csv_import_id': csv_import_id})
    
    def test_delete_associations_for_contact(self, repository, mock_session):
        """Test deleting all associations for a specific contact"""
        # Arrange
        contact_id = 123
        expected_count = 3
        repository.delete_many = Mock(return_value=expected_count)
        
        # Act
        result = repository.delete_associations_for_contact(contact_id)
        
        # Assert
        assert result == expected_count
        repository.delete_many.assert_called_once_with({'contact_id': contact_id})
    
    def test_get_recent_associations(self, repository, mock_session):
        """Test getting recently created associations"""
        # Arrange
        limit = 10
        expected_associations = [Mock(spec=ContactCSVImport)]
        mock_query = Mock()
        mock_session.query.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = expected_associations
        
        # Act
        result = repository.get_recent_associations(limit=limit)
        
        # Assert
        assert result == expected_associations
        mock_query.order_by.assert_called_once()
        mock_query.limit.assert_called_once_with(limit)
    
    def test_get_associations_by_date_range(self, repository, mock_session):
        """Test getting associations within date range"""
        # Arrange
        start_date = datetime(2023, 1, 1)
        end_date = datetime(2023, 12, 31)
        expected_associations = [Mock(spec=ContactCSVImport)]
        mock_query = Mock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = expected_associations
        
        # Act
        result = repository.get_associations_by_date_range(start_date, end_date)
        
        # Assert
        assert result == expected_associations
        # Should have two filter calls for date range
        assert mock_query.filter.call_count == 2
    
    def test_count_associations_for_import(self, repository, mock_session):
        """Test counting associations for a specific import"""
        # Arrange
        csv_import_id = 456
        expected_count = 95
        repository.count = Mock(return_value=expected_count)
        
        # Act
        result = repository.count_associations_for_import(csv_import_id)
        
        # Assert
        assert result == expected_count
        repository.count.assert_called_once_with(csv_import_id=csv_import_id)
    
    def test_count_associations_for_contact(self, repository, mock_session):
        """Test counting associations for a specific contact"""
        # Arrange
        contact_id = 123
        expected_count = 2
        repository.count = Mock(return_value=expected_count)
        
        # Act
        result = repository.count_associations_for_contact(contact_id)
        
        # Assert
        assert result == expected_count
        repository.count.assert_called_once_with(contact_id=contact_id)
    
    def test_find_contacts_imported_multiple_times(self, repository, mock_session):
        """Test finding contacts that were imported in multiple CSV files"""
        # Arrange
        mock_results = [(123, 3), (456, 2)]  # (contact_id, import_count)
        mock_query = Mock()
        mock_session.query.return_value = mock_query
        mock_query.group_by.return_value = mock_query
        mock_query.having.return_value = mock_query
        mock_query.all.return_value = mock_results
        
        # Act
        result = repository.find_contacts_imported_multiple_times()
        
        # Assert
        assert result == mock_results
        mock_query.group_by.assert_called_once()
        mock_query.having.assert_called_once()
    
    def test_get_data_updates_for_contact(self, repository, mock_session):
        """Test getting all data updates for a specific contact"""
        # Arrange
        contact_id = 123
        expected_associations = [Mock(spec=ContactCSVImport)]
        mock_query = Mock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = expected_associations
        
        # Act
        result = repository.get_data_updates_for_contact(contact_id)
        
        # Assert
        assert result == expected_associations
        # Should filter for contact_id AND data_updated IS NOT NULL
        mock_query.filter.assert_called_once()
    
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
    
    def test_model_class_is_contact_csv_import(self, repository):
        """Test that repository is configured with correct model class"""
        assert repository.model_class == ContactCSVImport
