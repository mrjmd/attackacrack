"""
Tests for ContactRepository OpenPhone sync methods
TDD RED Phase - These tests are written FIRST and MUST fail initially
"""

import pytest
from unittest.mock import Mock, MagicMock
from repositories.contact_repository import ContactRepository
from crm_database import Contact


class TestContactRepositoryOpenPhoneSync:
    """Test OpenPhone sync methods for ContactRepository"""
    
    @pytest.fixture
    def mock_session(self):
        """Mock database session"""
        session = MagicMock()
        return session
    
    @pytest.fixture
    def repository(self, mock_session):
        """Create ContactRepository with mocked session"""
        return ContactRepository(mock_session, Contact)
    
    def test_count_with_phone(self, repository, mock_session):
        """Test counting contacts that have phone numbers"""
        # Arrange
        expected_count = 42
        mock_query = mock_session.query.return_value
        mock_query.filter.return_value = mock_query
        mock_query.count.return_value = expected_count
        
        # Act
        result = repository.count_with_phone()
        
        # Assert
        assert result == expected_count
        mock_session.query.assert_called_once_with(Contact)
        mock_query.filter.assert_called_once()
        mock_query.count.assert_called_once()
    
    def test_count_with_phone_zero_results(self, repository, mock_session):
        """Test count_with_phone when no contacts have phone numbers"""
        # Arrange
        mock_query = mock_session.query.return_value
        mock_query.filter.return_value = mock_query
        mock_query.count.return_value = 0
        
        # Act
        result = repository.count_with_phone()
        
        # Assert
        assert result == 0
        mock_session.query.assert_called_once_with(Contact)
        mock_query.filter.assert_called_once()
        mock_query.count.assert_called_once()
