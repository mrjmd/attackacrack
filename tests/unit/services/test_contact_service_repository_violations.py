# tests/unit/services/test_contact_service_repository_violations.py
"""
TDD RED Phase: Tests to detect and fix direct database query violations in ContactService
These tests MUST fail initially to detect violations, then pass after fixing the service.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch, call
from services.contact_service_refactored import ContactService
from repositories.contact_repository import ContactRepository
from repositories.contact_flag_repository import ContactFlagRepository
from crm_database import Contact, ContactFlag
from services.common.result import Result


class TestContactServiceRepositoryViolations:
    """Test ContactService uses repositories instead of direct database queries"""
    
    @pytest.fixture
    def mock_contact_repository(self):
        """Create mock contact repository"""
        return Mock(spec=ContactRepository)
    
    @pytest.fixture
    def mock_contact_flag_repository(self):
        """Create mock contact flag repository"""
        return Mock(spec=ContactFlagRepository)
    
    @pytest.fixture
    def mock_session(self):
        """Create mock database session"""
        return Mock()
    
    @pytest.fixture
    def contact_service(self, mock_contact_repository, mock_contact_flag_repository, mock_session):
        """Create ContactService with mocked dependencies"""
        # This will fail until we add contact_flag_repository parameter
        return ContactService(
            contact_repository=mock_contact_repository,
            contact_flag_repository=mock_contact_flag_repository,
            session=mock_session
        )
    
    def test_search_contacts_uses_repository_not_session(self, contact_service, mock_contact_repository, mock_session):
        """Test search_contacts uses repository.search() instead of session.query()"""
        # Arrange
        test_query = "john"
        expected_contacts = [
            Contact(id=1, first_name='John', last_name='Doe'),
            Contact(id=2, first_name='Johnny', last_name='Smith')
        ]
        mock_contact_repository.search.return_value = expected_contacts
        
        # Act
        result = contact_service.search_contacts(test_query, limit=20)
        
        # Assert - Should use repository, not session
        mock_contact_repository.search.assert_called_once_with(
            test_query, 
            fields=['first_name', 'last_name', 'email', 'phone'],
            limit=20
        )
        # Session.query should NEVER be called
        mock_session.query.assert_not_called()
        
        assert result.is_success
        assert result.data == expected_contacts
    
    def test_get_by_ids_uses_repository_not_session(self, contact_service, mock_contact_repository, mock_session):
        """Test get_by_ids method uses repository instead of session.query()"""
        # Arrange
        contact_ids = [1, 2, 3]
        expected_contacts = [
            Contact(id=1, first_name='John'),
            Contact(id=2, first_name='Jane'),
            Contact(id=3, first_name='Bob')
        ]
        mock_contact_repository.get_by_ids.return_value = expected_contacts
        
        # Act - This method doesn't exist yet, so test will fail
        result = contact_service.get_by_ids(contact_ids)
        
        # Assert
        mock_contact_repository.get_by_ids.assert_called_once_with(contact_ids)
        mock_session.query.assert_not_called()
        
        assert result.is_success
        assert result.data == expected_contacts
    
    def test_get_statistics_uses_repositories_not_session(self, contact_service, mock_contact_repository, 
                                                        mock_contact_flag_repository, mock_session):
        """Test get_contact_statistics uses repositories instead of session queries"""
        # Arrange
        mock_contact_repository.get_contact_stats.return_value = {
            'total': 100,
            'with_phone': 85,
            'with_email': 70,
            'with_conversation': 45
        }
        mock_contact_flag_repository.get_flag_statistics.return_value = {
            'opted_out': 5,
            'invalid_phone': 3
        }
        
        # Act
        result = contact_service.get_contact_statistics()
        
        # Assert
        mock_contact_repository.get_contact_stats.assert_called_once()
        mock_contact_flag_repository.get_flag_statistics.assert_called_once()
        # Session queries should NEVER be called
        mock_session.query.assert_not_called()
        
        assert result.is_success
        expected_stats = {
            'total_contacts': 100,
            'with_phone': 85,
            'with_email': 70,
            'with_conversations': 45,
            'opted_out': 5,
            'invalid_phone': 3
        }
        assert result.data == expected_stats
    
    def test_export_contacts_uses_repository_not_session(self, contact_service, mock_contact_repository, mock_session):
        """Test export_contacts uses repository.get_by_ids() instead of session.query()"""
        # Arrange
        contact_ids = [1, 2]
        expected_contacts = [
            Contact(id=1, first_name='John', last_name='Doe', email='john@test.com'),
            Contact(id=2, first_name='Jane', last_name='Smith', email='jane@test.com')
        ]
        mock_contact_repository.get_by_ids.return_value = expected_contacts
        
        # Act
        result = contact_service.export_contacts(contact_ids)
        
        # Assert
        mock_contact_repository.get_by_ids.assert_called_once_with(contact_ids)
        mock_session.query.assert_not_called()
        
        assert result.is_success
        assert "john@test.com" in result.data
        assert "jane@test.com" in result.data
    
    def test_search_contacts_with_limit_parameter(self, contact_service, mock_contact_repository):
        """Test search_contacts passes limit parameter to repository"""
        # Arrange
        test_query = "smith"
        test_limit = 10
        mock_contact_repository.search.return_value = []
        
        # Act
        result = contact_service.search_contacts(test_query, limit=test_limit)
        
        # Assert
        mock_contact_repository.search.assert_called_once_with(
            test_query,
            fields=['first_name', 'last_name', 'email', 'phone'],
            limit=test_limit
        )
    
    def test_search_contacts_empty_query_returns_empty(self, contact_service, mock_contact_repository):
        """Test search_contacts with empty query returns empty list without calling repository"""
        # Act
        result = contact_service.search_contacts("")
        
        # Assert
        mock_contact_repository.search.assert_not_called()
        assert result.is_success
        assert result.data == []
    
    def test_service_has_contact_flag_repository_dependency(self, mock_contact_repository, mock_contact_flag_repository):
        """Test ContactService accepts ContactFlagRepository as dependency"""
        # This test will fail until we add the dependency injection
        service = ContactService(
            contact_repository=mock_contact_repository,
            contact_flag_repository=mock_contact_flag_repository
        )
        
        assert hasattr(service, 'contact_flag_repository')
        assert service.contact_flag_repository is mock_contact_flag_repository
    
    def test_get_by_ids_method_exists(self, contact_service):
        """Test that get_by_ids method exists on ContactService"""
        # This test will fail until we implement the method
        assert hasattr(contact_service, 'get_by_ids')
        assert callable(getattr(contact_service, 'get_by_ids'))


class TestContactRepositoryEnhancements:
    """Test ContactRepository has all required methods for ContactService"""
    
    @pytest.fixture
    def mock_session(self):
        return Mock()
    
    @pytest.fixture
    def contact_repository(self, mock_session):
        return ContactRepository(mock_session, Contact)
    
    def test_search_method_accepts_limit_parameter(self, contact_repository):
        """Test ContactRepository.search() accepts limit parameter"""
        with patch.object(contact_repository, 'session') as mock_session:
            mock_query = Mock()
            mock_session.query.return_value = mock_query
            mock_query.filter.return_value = mock_query
            mock_query.limit.return_value = mock_query
            mock_query.all.return_value = []
            
            # Act - This will fail until we add limit parameter
            contact_repository.search("test", limit=5)
            
            # Assert
            mock_query.limit.assert_called_once_with(5)
    
    def test_get_by_ids_method_exists(self, contact_repository):
        """Test ContactRepository has get_by_ids method"""
        # This test will fail until we implement the method
        assert hasattr(contact_repository, 'get_by_ids')
        assert callable(getattr(contact_repository, 'get_by_ids'))


class TestContactFlagRepositoryRequiredMethods:
    """Test ContactFlagRepository has methods needed for statistics"""
    
    @pytest.fixture
    def mock_session(self):
        return Mock()
    
    @pytest.fixture
    def contact_flag_repository(self, mock_session):
        return ContactFlagRepository(mock_session, ContactFlag)
    
    def test_get_flag_statistics_method_exists(self, contact_flag_repository):
        """Test ContactFlagRepository has get_flag_statistics method"""
        # This should pass since the method exists
        assert hasattr(contact_flag_repository, 'get_flag_statistics')
        assert callable(getattr(contact_flag_repository, 'get_flag_statistics'))
    
    def test_get_flag_statistics_returns_correct_format(self, contact_flag_repository):
        """Test get_flag_statistics returns expected format"""
        with patch.object(contact_flag_repository, 'session') as mock_session:
            mock_query = Mock()
            mock_session.query.return_value = mock_query
            mock_query.group_by.return_value = mock_query
            mock_query.all.return_value = [('opted_out', 5), ('invalid_phone', 3)]
            
            # Act
            result = contact_flag_repository.get_flag_statistics()
            
            # Assert
            assert isinstance(result, dict)
            assert 'opted_out' in result
            assert 'invalid_phone' in result
            assert result['opted_out'] == 5
            assert result['invalid_phone'] == 3