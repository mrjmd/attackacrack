"""Tests for ContactRepository QuickBooks-specific methods"""

import pytest
from unittest.mock import Mock
from repositories.contact_repository import ContactRepository
from crm_database import Contact


class TestContactRepositoryQuickBooksEnhancements:
    """Test ContactRepository QuickBooks-specific functionality"""
    
    @pytest.fixture
    def mock_session(self):
        """Create mock database session"""
        return Mock()
    
    @pytest.fixture
    def repository(self, mock_session):
        """Create ContactRepository instance with mocked session"""
        return ContactRepository(mock_session)
    
    # QuickBooks-specific methods
    
    def test_find_by_quickbooks_customer_id_exists(self, repository, mock_session):
        """Test finding contact by QuickBooks customer ID when it exists"""
        # Arrange
        expected_contact = Mock(spec=Contact)
        expected_contact.quickbooks_customer_id = 'QB_CUST_123'
        mock_query = Mock()
        mock_query.filter_by.return_value.first.return_value = expected_contact
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.find_by_quickbooks_customer_id('QB_CUST_123')
        
        # Assert
        assert result == expected_contact
        mock_session.query.assert_called_once_with(Contact)
        mock_query.filter_by.assert_called_once_with(quickbooks_customer_id='QB_CUST_123')
    
    def test_find_by_quickbooks_customer_id_not_exists(self, repository, mock_session):
        """Test finding contact by QuickBooks customer ID when it doesn't exist"""
        # Arrange
        mock_query = Mock()
        mock_query.filter_by.return_value.first.return_value = None
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.find_by_quickbooks_customer_id('NONEXISTENT_ID')
        
        # Assert
        assert result is None
        mock_session.query.assert_called_once_with(Contact)
        mock_query.filter_by.assert_called_once_with(quickbooks_customer_id='NONEXISTENT_ID')
    
    def test_find_by_phone_or_email_found_by_phone(self, repository, mock_session):
        """Test finding contact by phone when phone match exists"""
        # Arrange
        expected_contact = Mock(spec=Contact)
        expected_contact.phone = '+11234567890'
        mock_query = Mock()
        mock_query.filter_by.return_value.first.return_value = expected_contact
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.find_by_phone_or_email('+11234567890', 'test@example.com')
        
        # Assert
        assert result == expected_contact
        mock_session.query.assert_called_with(Contact)
        # Should try phone first
        assert mock_query.filter_by.call_count >= 1
    
    def test_find_by_phone_or_email_found_by_email(self, repository, mock_session):
        """Test finding contact by email when phone doesn't match but email does"""
        # Arrange
        expected_contact = Mock(spec=Contact)
        expected_contact.email = 'test@example.com'
        
        mock_query = Mock()
        # First call (phone) returns None, second call (email) returns contact
        mock_query.filter_by.return_value.first.side_effect = [None, expected_contact]
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.find_by_phone_or_email('+11234567890', 'test@example.com')
        
        # Assert
        assert result == expected_contact
        mock_session.query.assert_called_with(Contact)
        assert mock_query.filter_by.call_count == 2
    
    def test_find_by_phone_or_email_not_found(self, repository, mock_session):
        """Test finding contact when neither phone nor email match"""
        # Arrange
        mock_query = Mock()
        mock_query.filter_by.return_value.first.return_value = None
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.find_by_phone_or_email('+11234567890', 'test@example.com')
        
        # Assert
        assert result is None
        mock_session.query.assert_called_with(Contact)
        assert mock_query.filter_by.call_count == 2
    
    def test_find_by_phone_or_email_phone_only(self, repository, mock_session):
        """Test finding contact with phone only (no email)"""
        # Arrange
        expected_contact = Mock(spec=Contact)
        expected_contact.phone = '+11234567890'
        mock_query = Mock()
        mock_query.filter_by.return_value.first.return_value = expected_contact
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.find_by_phone_or_email('+11234567890', None)
        
        # Assert
        assert result == expected_contact
        mock_session.query.assert_called_with(Contact)
        # Should only try phone
        assert mock_query.filter_by.call_count == 1
    
    def test_find_by_phone_or_email_email_only(self, repository, mock_session):
        """Test finding contact with email only (no phone)"""
        # Arrange
        expected_contact = Mock(spec=Contact)
        expected_contact.email = 'test@example.com'
        mock_query = Mock()
        mock_query.filter_by.return_value.first.return_value = expected_contact
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.find_by_phone_or_email(None, 'test@example.com')
        
        # Assert
        assert result == expected_contact
        mock_session.query.assert_called_with(Contact)
        # Should only try email
        assert mock_query.filter_by.call_count == 1
    
    def test_find_by_phone_or_email_neither_provided(self, repository):
        """Test finding contact when neither phone nor email provided"""
        # Act
        result = repository.find_by_phone_or_email(None, None)
        
        # Assert
        assert result is None
    
    def test_find_contacts_needing_quickbooks_sync(self, repository, mock_session):
        """Test finding contacts that need QuickBooks sync"""
        # Arrange
        expected_contacts = [Mock(spec=Contact), Mock(spec=Contact)]
        mock_query = Mock()
        mock_filter = Mock()
        mock_query.filter.return_value = mock_filter
        mock_filter.all.return_value = expected_contacts
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.find_contacts_needing_quickbooks_sync()
        
        # Assert
        assert result == expected_contacts
        mock_session.query.assert_called_once_with(Contact)
        # Should filter for contacts without QB customer ID
        mock_query.filter.assert_called_once()
    
    def test_find_synced_contacts(self, repository, mock_session):
        """Test finding contacts synced with QuickBooks"""
        # Arrange
        expected_contacts = [Mock(spec=Contact), Mock(spec=Contact), Mock(spec=Contact)]
        mock_query = Mock()
        mock_filter = Mock()
        mock_query.filter.return_value = mock_filter
        mock_filter.all.return_value = expected_contacts
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.find_synced_contacts()
        
        # Assert
        assert result == expected_contacts
        mock_session.query.assert_called_once_with(Contact)
        # Should filter for contacts with QB customer ID
        mock_query.filter.assert_called_once()
    
    def test_update_quickbooks_sync_info(self, repository, mock_session):
        """Test updating QuickBooks sync information"""
        # Arrange
        mock_contact = Mock(spec=Contact)
        mock_contact.quickbooks_customer_id = None
        mock_contact.quickbooks_sync_token = None
        mock_query = Mock()
        mock_query.filter_by.return_value.first.return_value = mock_contact
        mock_session.query.return_value = mock_query
        mock_session.flush.return_value = None
        
        # Act
        result = repository.update_quickbooks_sync_info(1, 'QB_CUST_456', 'ST_789')
        
        # Assert
        assert result == mock_contact
        assert mock_contact.quickbooks_customer_id == 'QB_CUST_456'
        assert mock_contact.quickbooks_sync_token == 'ST_789'
        mock_session.query.assert_called_once_with(Contact)
        mock_query.filter_by.assert_called_once_with(id=1)
        mock_session.flush.assert_called_once()
    
    def test_update_quickbooks_sync_info_contact_not_found(self, repository, mock_session):
        """Test updating QuickBooks sync info when contact doesn't exist"""
        # Arrange
        mock_query = Mock()
        mock_query.filter_by.return_value.first.return_value = None
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.update_quickbooks_sync_info(999, 'QB_CUST_456', 'ST_789')
        
        # Assert
        assert result is None
        mock_session.query.assert_called_once_with(Contact)
        mock_query.filter_by.assert_called_once_with(id=999)
    
    def test_find_customers_only(self, repository, mock_session):
        """Test finding contacts that are customers"""
        # Arrange
        expected_contacts = [Mock(spec=Contact), Mock(spec=Contact)]
        mock_query = Mock()
        mock_query.filter_by.return_value.all.return_value = expected_contacts
        mock_session.query.return_value = mock_query
        
        # Act
        result = repository.find_customers_only()
        
        # Assert
        assert result == expected_contacts
        mock_session.query.assert_called_once_with(Contact)
        mock_query.filter_by.assert_called_once_with(customer_type='customer')
    
    def test_bulk_update_quickbooks_info(self, repository, mock_session):
        """Test bulk updating QuickBooks information for multiple contacts"""
        # Arrange
        contact_updates = {
            1: {'quickbooks_customer_id': 'QB_CUST_001', 'quickbooks_sync_token': 'ST_001'},
            2: {'quickbooks_customer_id': 'QB_CUST_002', 'quickbooks_sync_token': 'ST_002'}
        }
        
        mock_contacts = []
        for contact_id in contact_updates.keys():
            mock_contact = Mock(spec=Contact)
            mock_contact.id = contact_id
            mock_contact.quickbooks_customer_id = None
            mock_contact.quickbooks_sync_token = None
            mock_contacts.append(mock_contact)
        
        mock_query = Mock()
        mock_query.filter.return_value.all.return_value = mock_contacts
        mock_session.query.return_value = mock_query
        mock_session.flush.return_value = None
        
        # Act
        result = repository.bulk_update_quickbooks_info(contact_updates)
        
        # Assert
        assert result == 2  # 2 contacts updated
        for i, contact in enumerate(mock_contacts):
            expected_qb_id = f'QB_CUST_00{i+1}'
            expected_sync_token = f'ST_00{i+1}'
            assert contact.quickbooks_customer_id == expected_qb_id
            assert contact.quickbooks_sync_token == expected_sync_token
        mock_session.query.assert_called_once_with(Contact)
        mock_session.flush.assert_called_once()
    
    def test_bulk_update_quickbooks_info_empty_dict(self, repository):
        """Test bulk updating with empty updates dict"""
        # Act
        result = repository.bulk_update_quickbooks_info({})
        
        # Assert
        assert result == 0
