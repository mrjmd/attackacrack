"""
Unit tests for Opt-Out Audit Repository

Tests the repository layer for opt-out audit trail management.
"""

import pytest
from datetime import datetime, timedelta
from utils.datetime_utils import utc_now
from unittest.mock import Mock, MagicMock, patch
from repositories.opt_out_audit_repository import OptOutAuditRepository
from crm_database import OptOutAudit, db


class TestOptOutAuditRepository:
    """Test the OptOutAudit repository implementation"""
    
    @pytest.fixture
    def mock_session(self):
        """Create a mock database session"""
        session = MagicMock()
        return session
    
    @pytest.fixture
    def repository(self, mock_session):
        """Create repository with mocked session"""
        repo = OptOutAuditRepository(mock_session)
        return repo
    
    def test_create_opt_out_audit(self, repository, mock_session):
        """Test creating an opt-out audit log entry"""
        # Prepare test data
        audit_data = {
            'contact_id': 1,
            'phone_number': '+1234567890',
            'contact_name': 'John Doe',
            'opt_out_method': 'sms_keyword',
            'keyword_used': 'STOP',
            'source': 'webhook',
            'campaign_id': None,
            'message_id': 'msg123'
        }
        
        # Mock the add and commit
        mock_audit = Mock(spec=OptOutAudit)
        mock_audit.id = 1
        mock_audit.contact_id = 1
        mock_audit.created_at = utc_now()
        
        with patch('repositories.opt_out_audit_repository.OptOutAudit') as MockAudit:
            MockAudit.return_value = mock_audit
            
            result = repository.create(**audit_data)
            
            # Verify OptOutAudit was created with correct data
            MockAudit.assert_called_once_with(**audit_data)
            
            # Verify it was added to session and committed
            mock_session.add.assert_called_once_with(mock_audit)
            mock_session.commit.assert_called_once()
            mock_session.refresh.assert_called_once_with(mock_audit)
            
            assert result == mock_audit
    
    def test_find_by_contact_id(self, repository, mock_session):
        """Test finding audit logs by contact ID"""
        contact_id = 1
        
        # Mock query result
        mock_audits = [
            Mock(id=1, contact_id=1, keyword_used='STOP'),
            Mock(id=2, contact_id=1, keyword_used='UNSUBSCRIBE')
        ]
        
        mock_query = MagicMock()
        mock_query.filter_by.return_value.order_by.return_value.all.return_value = mock_audits
        mock_session.query.return_value = mock_query
        
        result = repository.find_by_contact_id(contact_id)
        
        # Verify query was built correctly
        mock_session.query.assert_called_once_with(OptOutAudit)
        mock_query.filter_by.assert_called_once_with(contact_id=contact_id)
        
        assert result == mock_audits
        assert len(result) == 2
    
    def test_find_since(self, repository, mock_session):
        """Test finding audit logs since a specific date"""
        since_date = utc_now() - timedelta(days=7)
        
        # Mock query result
        mock_audits = [
            Mock(id=1, created_at=utc_now()),
            Mock(id=2, created_at=utc_now() - timedelta(days=1))
        ]
        
        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_query.filter.return_value = mock_filter
        mock_filter.order_by.return_value.all.return_value = mock_audits
        mock_session.query.return_value = mock_query
        
        result = repository.find_since(since_date)
        
        # Verify query was built correctly
        mock_session.query.assert_called_once_with(OptOutAudit)
        # Check that filter was called (exact comparison is complex with SQLAlchemy)
        assert mock_query.filter.called
        
        assert result == mock_audits
        assert len(result) == 2
    
    def test_find_by_phone_number(self, repository, mock_session):
        """Test finding audit logs by phone number"""
        phone = '+1234567890'
        
        # Mock query result
        mock_audits = [
            Mock(id=1, phone_number=phone, keyword_used='STOP')
        ]
        
        mock_query = MagicMock()
        mock_query.filter_by.return_value.order_by.return_value.all.return_value = mock_audits
        mock_session.query.return_value = mock_query
        
        result = repository.find_by_phone_number(phone)
        
        # Verify query was built correctly
        mock_session.query.assert_called_once_with(OptOutAudit)
        mock_query.filter_by.assert_called_once_with(phone_number=phone)
        
        assert result == mock_audits
        assert len(result) == 1
    
    def test_find_by_keyword(self, repository, mock_session):
        """Test finding audit logs by keyword used"""
        keyword = 'STOP'
        
        # Mock query result
        mock_audits = [
            Mock(id=1, keyword_used='STOP'),
            Mock(id=2, keyword_used='STOP')
        ]
        
        mock_query = MagicMock()
        mock_query.filter_by.return_value.order_by.return_value.all.return_value = mock_audits
        mock_session.query.return_value = mock_query
        
        result = repository.find_by_keyword(keyword)
        
        # Verify query was built correctly
        mock_session.query.assert_called_once_with(OptOutAudit)
        mock_query.filter_by.assert_called_once_with(keyword_used=keyword)
        
        assert result == mock_audits
        assert len(result) == 2
    
    def test_find_by_method(self, repository, mock_session):
        """Test finding audit logs by opt-out method"""
        method = 'sms_keyword'
        
        # Mock query result
        mock_audits = [
            Mock(id=1, opt_out_method='sms_keyword'),
            Mock(id=2, opt_out_method='sms_keyword'),
            Mock(id=3, opt_out_method='sms_keyword')
        ]
        
        mock_query = MagicMock()
        mock_query.filter_by.return_value.order_by.return_value.all.return_value = mock_audits
        mock_session.query.return_value = mock_query
        
        result = repository.find_by_method(method)
        
        # Verify query was built correctly
        mock_session.query.assert_called_once_with(OptOutAudit)
        mock_query.filter_by.assert_called_once_with(opt_out_method=method)
        
        assert result == mock_audits
        assert len(result) == 3
    
    def test_find_all(self, repository, mock_session):
        """Test finding all audit logs"""
        # Mock query result
        mock_audits = [
            Mock(id=1, keyword_used='STOP'),
            Mock(id=2, keyword_used='UNSUBSCRIBE'),
            Mock(id=3, keyword_used='END')
        ]
        
        mock_query = MagicMock()
        mock_query.order_by.return_value.all.return_value = mock_audits
        mock_session.query.return_value = mock_query
        
        result = repository.find_all()
        
        # Verify query was built correctly
        mock_session.query.assert_called_once_with(OptOutAudit)
        mock_query.order_by.assert_called_once()
        
        assert result == mock_audits
        assert len(result) == 3
    
    def test_count_by_keyword(self, repository, mock_session):
        """Test counting audit logs by keyword"""
        # Mock query result for aggregation
        mock_results = [
            ('STOP', 25),
            ('UNSUBSCRIBE', 10),
            ('END', 5)
        ]
        
        mock_query = MagicMock()
        mock_query.group_by.return_value.all.return_value = mock_results
        mock_session.query.return_value = mock_query
        
        result = repository.count_by_keyword()
        
        # Verify the result is properly formatted
        assert result == {
            'STOP': 25,
            'UNSUBSCRIBE': 10,
            'END': 5
        }
    
    def test_count_since(self, repository, mock_session):
        """Test counting audit logs since a date"""
        since_date = utc_now() - timedelta(days=30)
        
        # Mock query result
        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_query.filter.return_value = mock_filter
        mock_filter.count.return_value = 42
        mock_session.query.return_value = mock_query
        
        result = repository.count_since(since_date)
        
        # Verify query was built correctly
        mock_session.query.assert_called_once_with(OptOutAudit)
        assert mock_query.filter.called
        
        assert result == 42
    
    def test_get_latest_for_contact(self, repository, mock_session):
        """Test getting the most recent audit log for a contact"""
        contact_id = 1
        
        # Mock query result
        mock_audit = Mock(id=5, contact_id=1, created_at=utc_now())
        
        mock_query = MagicMock()
        mock_query.filter_by.return_value.order_by.return_value.first.return_value = mock_audit
        mock_session.query.return_value = mock_query
        
        result = repository.get_latest_for_contact(contact_id)
        
        # Verify query was built correctly
        mock_session.query.assert_called_once_with(OptOutAudit)
        mock_query.filter_by.assert_called_once_with(contact_id=contact_id)
        
        assert result == mock_audit
    
    def test_delete_old_audits(self, repository, mock_session):
        """Test deleting old audit logs"""
        older_than = utc_now() - timedelta(days=365)
        
        # Mock the delete operation
        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_query.filter.return_value = mock_filter
        mock_filter.delete.return_value = 10  # Number of deleted records
        mock_session.query.return_value = mock_query
        
        result = repository.delete_old_audits(older_than)
        
        # Verify query was built correctly
        mock_session.query.assert_called_once_with(OptOutAudit)
        assert mock_query.filter.called
        mock_filter.delete.assert_called_once()
        mock_session.commit.assert_called_once()
        
        assert result == 10