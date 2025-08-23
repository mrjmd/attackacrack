"""
Tests for QuickBooksAuthRepository
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime, timedelta
from repositories.quickbooks_auth_repository import QuickBooksAuthRepository
from crm_database import QuickBooksAuth


class TestQuickBooksAuthRepository:
    """Test suite for QuickBooksAuthRepository"""
    
    @pytest.fixture
    def mock_session(self):
        """Mock database session"""
        session = MagicMock()
        return session
    
    @pytest.fixture
    def repository(self, mock_session):
        """Create QuickBooksAuthRepository with mocked session"""
        return QuickBooksAuthRepository(mock_session)
    
    def test_find_by_company_id(self, repository, mock_session):
        """Test finding auth record by company ID"""
        # Arrange
        mock_auth = Mock(id=1, company_id="123456")
        mock_query = Mock()
        mock_query.filter_by.return_value.first.return_value = mock_auth
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.find_by_company_id("123456")
        
        # Assert
        assert result == mock_auth
        mock_session.query.assert_called_once_with(QuickBooksAuth)
        mock_query.filter_by.assert_called_once_with(company_id="123456")
    
    def test_find_by_company_id_not_found(self, repository, mock_session):
        """Test finding auth record when company ID doesn't exist"""
        # Arrange
        mock_query = Mock()
        mock_query.filter_by.return_value.first.return_value = None
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.find_by_company_id("nonexistent")
        
        # Assert
        assert result is None
        mock_query.filter_by.assert_called_once_with(company_id="nonexistent")
    
    def test_get_first_auth(self, repository, mock_session):
        """Test getting the first auth record (single company support)"""
        # Arrange
        mock_auth = Mock(id=1, company_id="123456")
        mock_query = Mock()
        mock_query.first.return_value = mock_auth
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.get_first_auth()
        
        # Assert
        assert result == mock_auth
        mock_session.query.assert_called_once_with(QuickBooksAuth)
        mock_query.first.assert_called_once()
    
    def test_get_first_auth_no_records(self, repository, mock_session):
        """Test getting first auth when no records exist"""
        # Arrange
        mock_query = Mock()
        mock_query.first.return_value = None
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.get_first_auth()
        
        # Assert
        assert result is None
        mock_query.first.assert_called_once()
    
    def test_create_or_update_existing_auth(self, repository, mock_session):
        """Test creating or updating auth when record already exists"""
        # Arrange
        existing_auth = Mock(
            id=1, 
            company_id="123456", 
            access_token="old_token",
            refresh_token="old_refresh"
        )
        mock_query = Mock()
        mock_query.filter_by.return_value.first.return_value = existing_auth
        mock_session.query.return_value = mock_query
        
        auth_data = {
            'company_id': '123456',
            'access_token': 'new_encrypted_token',
            'refresh_token': 'new_encrypted_refresh',
            'expires_at': datetime.utcnow() + timedelta(hours=1)
        }
        
        # Act
        result = repository.create_or_update_auth(auth_data)
        
        # Assert
        assert result == existing_auth
        assert existing_auth.access_token == 'new_encrypted_token'
        assert existing_auth.refresh_token == 'new_encrypted_refresh'
        assert existing_auth.expires_at == auth_data['expires_at']
        assert existing_auth.updated_at is not None
        mock_session.add.assert_not_called()  # Should not add existing record
        mock_session.commit.assert_called_once()
    
    def test_create_or_update_new_auth(self, repository, mock_session):
        """Test creating new auth when record doesn't exist"""
        # Arrange
        mock_query = Mock()
        mock_query.filter_by.return_value.first.return_value = None
        mock_session.query.return_value = mock_query
        
        # Mock the QuickBooksAuth constructor
        mock_auth = Mock()
        with patch('repositories.quickbooks_auth_repository.QuickBooksAuth') as mock_auth_class:
            mock_auth_class.return_value = mock_auth
            
            auth_data = {
                'company_id': '123456',
                'access_token': 'encrypted_token',
                'refresh_token': 'encrypted_refresh',
                'expires_at': datetime.utcnow() + timedelta(hours=1)
            }
            
            # Act
            result = repository.create_or_update_auth(auth_data)
            
            # Assert
            assert result == mock_auth
            mock_auth_class.assert_called_once_with(company_id='123456')
            mock_session.add.assert_called_once_with(mock_auth)
            mock_session.commit.assert_called_once()
    
    def test_update_tokens(self, repository, mock_session):
        """Test updating access and refresh tokens"""
        # Arrange
        auth_record = Mock(id=1)
        mock_session.query.return_value.get.return_value = auth_record
        
        # Act
        result = repository.update_tokens(
            auth_id=1,
            access_token="new_access_token",
            refresh_token="new_refresh_token",
            expires_at=datetime.utcnow() + timedelta(hours=1)
        )
        
        # Assert
        assert result == auth_record
        assert auth_record.access_token == "new_access_token"
        assert auth_record.refresh_token == "new_refresh_token"
        assert auth_record.updated_at is not None
        mock_session.commit.assert_called_once()
    
    def test_update_tokens_record_not_found(self, repository, mock_session):
        """Test updating tokens when auth record doesn't exist"""
        # Arrange
        mock_session.query.return_value.get.return_value = None
        
        # Act
        result = repository.update_tokens(
            auth_id=999,
            access_token="new_access_token",
            refresh_token="new_refresh_token",
            expires_at=datetime.utcnow() + timedelta(hours=1)
        )
        
        # Assert
        assert result is None
        mock_session.commit.assert_not_called()
    
    def test_is_token_expired_true(self, repository, mock_session):
        """Test checking if token is expired when it is expired"""
        # Arrange
        expired_time = datetime.utcnow() - timedelta(hours=1)
        auth_record = Mock(expires_at=expired_time)
        mock_session.query.return_value.get.return_value = auth_record
        
        # Act
        result = repository.is_token_expired(1)
        
        # Assert
        assert result is True
    
    def test_is_token_expired_false(self, repository, mock_session):
        """Test checking if token is expired when it's still valid"""
        # Arrange
        future_time = datetime.utcnow() + timedelta(hours=1)
        auth_record = Mock(expires_at=future_time)
        mock_session.query.return_value.get.return_value = auth_record
        
        # Act
        result = repository.is_token_expired(1)
        
        # Assert
        assert result is False
    
    def test_is_token_expired_record_not_found(self, repository, mock_session):
        """Test checking token expiry when auth record doesn't exist"""
        # Arrange
        mock_session.query.return_value.get.return_value = None
        
        # Act
        result = repository.is_token_expired(999)
        
        # Assert
        assert result is True  # Treat missing record as expired
    
    def test_delete_auth(self, repository, mock_session):
        """Test deleting auth record"""
        # Arrange
        auth_record = Mock(id=1)
        mock_session.query.return_value.get.return_value = auth_record
        
        # Act
        result = repository.delete_auth(1)
        
        # Assert
        assert result is True
        mock_session.delete.assert_called_once_with(auth_record)
        mock_session.commit.assert_called_once()
    
    def test_delete_auth_record_not_found(self, repository, mock_session):
        """Test deleting auth record when it doesn't exist"""
        # Arrange
        mock_session.query.return_value.get.return_value = None
        
        # Act
        result = repository.delete_auth(999)
        
        # Assert
        assert result is False
        mock_session.delete.assert_not_called()
        mock_session.commit.assert_not_called()
    
    def test_search_with_query(self, repository, mock_session):
        """Test searching auth records by company ID"""
        # Arrange
        mock_auths = [Mock(id=1, company_id="123456")]
        mock_query = Mock()
        mock_query.filter.return_value.limit.return_value.all.return_value = mock_auths
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.search("123")
        
        # Assert
        assert result == mock_auths
        mock_query.filter.assert_called_once()
        mock_query.filter.return_value.limit.assert_called_once_with(100)
    
    def test_search_empty_query(self, repository, mock_session):
        """Test searching with empty query returns empty list"""
        # Act
        result = repository.search("")
        
        # Assert
        assert result == []
        mock_session.query.assert_not_called()