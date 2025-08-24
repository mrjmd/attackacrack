"""
Unit tests for Opt-Out Service - TDD Approach

Tests the complete opt-out processing pipeline:
1. STOP keyword detection
2. Opt-out flag management
3. Confirmation message sending
4. Audit logging
5. Campaign filtering
"""

import pytest
from datetime import datetime, timedelta
from utils.datetime_utils import utc_now
from unittest.mock import Mock, patch, MagicMock
from services.opt_out_service import OptOutService
from services.common.result import Result


class TestOptOutKeywordDetection:
    """Test detection of opt-out keywords in messages"""
    
    @pytest.fixture
    def opt_out_service(self):
        """Create service with mocked dependencies"""
        contact_flag_repo = Mock()
        opt_out_audit_repo = Mock()
        sms_service = Mock()
        contact_repo = Mock()
        
        service = OptOutService(
            contact_flag_repository=contact_flag_repo,
            opt_out_audit_repository=opt_out_audit_repo,
            sms_service=sms_service,
            contact_repository=contact_repo
        )
        return service
    
    @pytest.mark.parametrize("message,expected", [
        ("STOP", True),
        ("stop", True),
        ("Stop", True),
        ("STOP ALL", True),
        ("UNSUBSCRIBE", True),
        ("unsubscribe", True),
        ("END", True),
        ("end", True),
        ("QUIT", True),
        ("quit", True),
        ("CANCEL", True),
        ("cancel", True),
        ("OPTOUT", True),
        ("opt out", True),
        ("opt-out", True),
        ("REMOVE", True),
        ("remove me", True),
        ("DELETE", True),
        ("delete me", True),
        # Messages that should NOT trigger opt-out
        ("I want to stop by tomorrow", False),
        ("The project will end next week", False),
        ("Don't quit now", False),
        ("Cancel the meeting", False),
        ("Yes, I'm interested", False),
        ("Thanks for the info", False),
        ("", False),
        (None, False),
    ])
    def test_detects_opt_out_keywords(self, opt_out_service, message, expected):
        """Test that opt-out keywords are correctly detected"""
        result = opt_out_service.contains_opt_out_keyword(message)
        assert result == expected
    
    def test_detects_opt_out_phrases_with_extra_text(self, opt_out_service):
        """Test detection when opt-out keyword is part of larger message"""
        assert opt_out_service.contains_opt_out_keyword("STOP texting me") == True
        assert opt_out_service.contains_opt_out_keyword("Please UNSUBSCRIBE me") == True
        assert opt_out_service.contains_opt_out_keyword("I want to opt out") == True
        assert opt_out_service.contains_opt_out_keyword("REMOVE from list") == True


class TestOptOutProcessing:
    """Test the complete opt-out processing workflow"""
    
    @pytest.fixture
    def opt_out_service(self):
        """Create service with mocked dependencies"""
        contact_flag_repo = Mock()
        opt_out_audit_repo = Mock()
        sms_service = Mock()
        contact_repo = Mock()
        
        # Set up default mock returns
        contact_flag_repo.create.return_value = Mock(id=1)
        opt_out_audit_repo.create.return_value = Mock(id=1)
        sms_service.send_sms.return_value = Result.success({"message_id": "123"})
        
        service = OptOutService(
            contact_flag_repository=contact_flag_repo,
            opt_out_audit_repository=opt_out_audit_repo,
            sms_service=sms_service,
            contact_repository=contact_repo
        )
        return service
    
    def test_process_opt_out_creates_flag(self, opt_out_service):
        """Test that processing opt-out creates a contact flag"""
        contact = Mock(id=1, phone="+1234567890")
        
        # Mock that no existing flags exist
        opt_out_service.contact_flag_repository.find_active_flags.return_value = []
        
        result = opt_out_service.process_opt_out(
            contact=contact,
            message="STOP",
            source="sms_webhook"
        )
        
        assert result.is_success
        
        # Verify flag was created
        opt_out_service.contact_flag_repository.create.assert_called_once()
        call_args = opt_out_service.contact_flag_repository.create.call_args[1]
        assert call_args['contact_id'] == 1
        assert call_args['flag_type'] == 'opted_out'
        assert call_args['flag_reason'] == 'Received opt-out message: STOP'
        assert call_args['applies_to'] == 'sms'
        assert call_args['created_by'] == 'sms_webhook'
    
    def test_process_opt_out_creates_audit_log(self, opt_out_service):
        """Test that processing opt-out creates an audit log entry"""
        contact = Mock(id=1, phone="+1234567890", first_name="John", last_name="Doe")
        
        # Mock that no existing flags exist
        opt_out_service.contact_flag_repository.find_active_flags.return_value = []
        
        result = opt_out_service.process_opt_out(
            contact=contact,
            message="UNSUBSCRIBE",
            source="sms_webhook"
        )
        
        assert result.is_success
        
        # Verify audit log was created
        opt_out_service.opt_out_audit_repository.create.assert_called_once()
        call_args = opt_out_service.opt_out_audit_repository.create.call_args[1]
        assert call_args['contact_id'] == 1
        assert call_args['phone_number'] == "+1234567890"
        assert call_args['opt_out_method'] == 'sms_keyword'
        assert call_args['keyword_used'] == 'UNSUBSCRIBE'
        assert call_args['source'] == 'sms_webhook'
        assert 'contact_name' in call_args
    
    def test_process_opt_out_sends_confirmation(self, opt_out_service):
        """Test that processing opt-out sends confirmation message"""
        contact = Mock(id=1, phone="+1234567890")
        
        # Mock that no existing flags exist
        opt_out_service.contact_flag_repository.find_active_flags.return_value = []
        
        result = opt_out_service.process_opt_out(
            contact=contact,
            message="STOP",
            source="sms_webhook"
        )
        
        assert result.is_success
        
        # Verify confirmation was sent
        opt_out_service.sms_service.send_sms.assert_called_once_with(
            to_phone="+1234567890",
            message="You've been unsubscribed. Reply START to resubscribe.",
            is_system_message=True
        )
    
    def test_process_opt_out_handles_existing_opt_out(self, opt_out_service):
        """Test that duplicate opt-outs are handled gracefully"""
        contact = Mock(id=1, phone="+1234567890")
        
        # Mock that flag already exists
        existing_flag = Mock(id=1, flag_type='opted_out', created_at=utc_now())
        opt_out_service.contact_flag_repository.find_active_flags.return_value = [existing_flag]
        
        result = opt_out_service.process_opt_out(
            contact=contact,
            message="STOP",
            source="sms_webhook"
        )
        
        assert result.is_success
        assert result.data['status'] == 'already_opted_out'
        
        # Should not create new flag
        opt_out_service.contact_flag_repository.create.assert_not_called()
        # Should still send confirmation
        opt_out_service.sms_service.send_sms.assert_called_once()
    
    def test_process_opt_out_handles_sms_failure(self, opt_out_service):
        """Test that opt-out is still recorded even if confirmation SMS fails"""
        contact = Mock(id=1, phone="+1234567890")
        
        # Mock that no existing flags exist
        opt_out_service.contact_flag_repository.find_active_flags.return_value = []
        
        # Mock SMS failure
        opt_out_service.sms_service.send_sms.return_value = Result.failure(
            "SMS service unavailable"
        )
        
        result = opt_out_service.process_opt_out(
            contact=contact,
            message="STOP",
            source="sms_webhook"
        )
        
        # Should still succeed
        assert result.is_success
        assert result.data['confirmation_sent'] == False
        
        # Flag and audit should still be created
        opt_out_service.contact_flag_repository.create.assert_called_once()
        opt_out_service.opt_out_audit_repository.create.assert_called_once()


class TestOptInProcessing:
    """Test handling of opt-in (resubscribe) requests"""
    
    @pytest.fixture
    def opt_out_service(self):
        """Create service with mocked dependencies"""
        contact_flag_repo = Mock()
        opt_out_audit_repo = Mock()
        sms_service = Mock()
        contact_repo = Mock()
        
        sms_service.send_sms.return_value = Result.success({"message_id": "123"})
        
        service = OptOutService(
            contact_flag_repository=contact_flag_repo,
            opt_out_audit_repository=opt_out_audit_repo,
            sms_service=sms_service,
            contact_repository=contact_repo
        )
        return service
    
    @pytest.mark.parametrize("message,expected", [
        ("START", True),
        ("start", True),
        ("Start", True),
        ("SUBSCRIBE", True),
        ("subscribe", True),
        ("YES", True),
        ("yes", True),
        ("UNSTOP", True),
        ("unstop", True),
        ("RESUME", True),
        ("resume", True),
        # Messages that should NOT trigger opt-in
        ("Let's start the project", False),
        ("Yes, but not now", False),
        ("Resume next week", False),
        ("", False),
        (None, False),
    ])
    def test_detects_opt_in_keywords(self, opt_out_service, message, expected):
        """Test that opt-in keywords are correctly detected"""
        result = opt_out_service.contains_opt_in_keyword(message)
        assert result == expected
    
    def test_process_opt_in_removes_flag(self, opt_out_service):
        """Test that processing opt-in removes the opted_out flag"""
        contact = Mock(id=1, phone="+1234567890")
        
        # Mock existing opt-out flag
        existing_flag = Mock(id=5, flag_type='opted_out', expires_at=None)
        opt_out_service.contact_flag_repository.find_active_flags.return_value = [existing_flag]
        
        result = opt_out_service.process_opt_in(
            contact=contact,
            message="START",
            source="sms_webhook"
        )
        
        assert result.is_success
        
        # Should expire the flag
        opt_out_service.contact_flag_repository.expire_flag.assert_called_once_with(5)
        
        # Should create audit log
        opt_out_service.opt_out_audit_repository.create.assert_called_once()
        call_args = opt_out_service.opt_out_audit_repository.create.call_args[1]
        assert call_args['opt_out_method'] == 'sms_opt_in'
        assert call_args['keyword_used'] == 'START'
        
        # Should send confirmation
        opt_out_service.sms_service.send_sms.assert_called_once_with(
            to_phone="+1234567890",
            message="You've been resubscribed to messages. Reply STOP to unsubscribe.",
            is_system_message=True
        )
    
    def test_process_opt_in_when_not_opted_out(self, opt_out_service):
        """Test opt-in when contact is not opted out"""
        contact = Mock(id=1, phone="+1234567890")
        
        # No existing flags
        opt_out_service.contact_flag_repository.find_active_flags.return_value = []
        
        result = opt_out_service.process_opt_in(
            contact=contact,
            message="START",
            source="sms_webhook"
        )
        
        assert result.is_success
        assert result.data['status'] == 'already_opted_in'
        
        # Should not try to expire any flags
        opt_out_service.contact_flag_repository.expire_flag.assert_not_called()
        
        # Should still send confirmation
        opt_out_service.sms_service.send_sms.assert_called_once()


class TestCampaignFiltering:
    """Test filtering of opted-out contacts from campaigns"""
    
    @pytest.fixture
    def opt_out_service(self):
        """Create service with mocked dependencies"""
        contact_flag_repo = Mock()
        opt_out_audit_repo = Mock()
        sms_service = Mock()
        contact_repo = Mock()
        
        service = OptOutService(
            contact_flag_repository=contact_flag_repo,
            opt_out_audit_repository=opt_out_audit_repo,
            sms_service=sms_service,
            contact_repository=contact_repo
        )
        return service
    
    def test_get_opted_out_contact_ids(self, opt_out_service):
        """Test retrieving list of opted-out contact IDs"""
        # Mock opted-out flags
        flags = [
            Mock(contact_id=1),
            Mock(contact_id=3),
            Mock(contact_id=5)
        ]
        opt_out_service.contact_flag_repository.find_by_flag_type.return_value = flags
        
        opted_out_ids = opt_out_service.get_opted_out_contact_ids()
        
        assert opted_out_ids == [1, 3, 5]
        opt_out_service.contact_flag_repository.find_by_flag_type.assert_called_once_with(
            'opted_out',
            active_only=True
        )
    
    def test_filter_opted_out_contacts(self, opt_out_service):
        """Test filtering a list of contacts to remove opted-out ones"""
        # Mock contacts
        contacts = [
            Mock(id=1, phone="+1111111111"),
            Mock(id=2, phone="+2222222222"),
            Mock(id=3, phone="+3333333333"),
            Mock(id=4, phone="+4444444444"),
            Mock(id=5, phone="+5555555555")
        ]
        
        # Mock that contacts 2 and 4 are opted out
        flags = [
            Mock(contact_id=2),
            Mock(contact_id=4)
        ]
        opt_out_service.contact_flag_repository.find_by_flag_type.return_value = flags
        
        filtered_contacts = opt_out_service.filter_opted_out_contacts(contacts)
        
        assert len(filtered_contacts) == 3
        assert all(c.id not in [2, 4] for c in filtered_contacts)
        assert all(c.id in [1, 3, 5] for c in filtered_contacts)
    
    def test_is_contact_opted_out(self, opt_out_service):
        """Test checking if a specific contact is opted out"""
        contact = Mock(id=1)
        
        # Test when opted out
        opt_out_service.contact_flag_repository.find_active_flags.return_value = [
            Mock(flag_type='opted_out')
        ]
        assert opt_out_service.is_contact_opted_out(contact) == True
        
        # Verify correct call was made
        opt_out_service.contact_flag_repository.find_active_flags.assert_called_with(
            1, flag_type='opted_out'
        )
        
        # Test when not opted out
        opt_out_service.contact_flag_repository.find_active_flags.return_value = []
        assert opt_out_service.is_contact_opted_out(contact) == False
        
        # Test when has other flags but not opted_out (should return empty when filtering by type)
        opt_out_service.contact_flag_repository.find_active_flags.return_value = []
        assert opt_out_service.is_contact_opted_out(contact) == False


class TestOptOutReporting:
    """Test opt-out reporting and analytics"""
    
    @pytest.fixture
    def opt_out_service(self):
        """Create service with mocked dependencies"""
        contact_flag_repo = Mock()
        opt_out_audit_repo = Mock()
        sms_service = Mock()
        contact_repo = Mock()
        
        service = OptOutService(
            contact_flag_repository=contact_flag_repo,
            opt_out_audit_repository=opt_out_audit_repo,
            sms_service=sms_service,
            contact_repository=contact_repo
        )
        return service
    
    def test_get_opt_out_statistics(self, opt_out_service):
        """Test generating opt-out statistics"""
        # Mock audit logs
        audit_logs = [
            Mock(created_at=utc_now(), keyword_used='STOP', opt_out_method='sms_keyword'),
            Mock(created_at=utc_now(), keyword_used='UNSUBSCRIBE', opt_out_method='sms_keyword'),
            Mock(created_at=utc_now(), keyword_used='STOP', opt_out_method='sms_keyword'),
            Mock(created_at=utc_now() - timedelta(days=35), keyword_used='END', opt_out_method='sms_keyword'),
        ]
        opt_out_service.opt_out_audit_repository.find_all.return_value = audit_logs
        
        # Mock count_since for last 30 days
        opt_out_service.opt_out_audit_repository.count_since.return_value = 3
        
        # Mock keyword breakdown
        opt_out_service.opt_out_audit_repository.count_by_keyword.return_value = {
            'STOP': 2,
            'UNSUBSCRIBE': 1,
            'END': 1
        }
        
        # Mock current opted out count
        opt_out_service.contact_flag_repository.count_by_flag_type.return_value = 15
        
        stats = opt_out_service.get_opt_out_statistics()
        
        assert stats['total_opted_out'] == 15
        assert stats['opt_outs_last_30_days'] == 3
        assert stats['most_common_keyword'] == 'STOP'
        assert stats['keyword_breakdown']['STOP'] == 2
        assert stats['keyword_breakdown']['UNSUBSCRIBE'] == 1
    
    def test_get_recent_opt_outs(self, opt_out_service):
        """Test retrieving recent opt-out events"""
        since_date = utc_now() - timedelta(days=7)
        
        # Mock audit logs with contact info
        audit_logs = [
            Mock(
                id=1,
                contact_id=1, 
                phone_number="+1111111111",
                contact_name="John Doe",
                created_at=utc_now(),
                keyword_used='STOP',
                opt_out_method='sms_keyword',  # Add this field
                source='webhook'
            ),
            Mock(
                id=2,
                contact_id=2,
                phone_number="+2222222222", 
                contact_name="Jane Smith",
                created_at=utc_now() - timedelta(days=1),
                keyword_used='UNSUBSCRIBE',
                opt_out_method='sms_keyword',  # Add this field
                source='webhook'
            )
        ]
        opt_out_service.opt_out_audit_repository.find_since.return_value = audit_logs
        
        recent = opt_out_service.get_recent_opt_outs(since=since_date)
        
        assert len(recent) == 2
        assert recent[0]['contact_id'] == 1
        assert recent[0]['phone_number'] == "+1111111111"
        assert recent[0]['keyword_used'] == 'STOP'
        
        opt_out_service.opt_out_audit_repository.find_since.assert_called_once_with(since_date)


class TestWebhookIntegration:
    """Test integration with webhook processing"""
    
    @pytest.fixture
    def opt_out_service(self):
        """Create service with mocked dependencies"""
        contact_flag_repo = Mock()
        opt_out_audit_repo = Mock()
        sms_service = Mock()
        contact_repo = Mock()
        
        # Set up default returns
        contact_flag_repo.create.return_value = Mock(id=1)
        opt_out_audit_repo.create.return_value = Mock(id=1)
        sms_service.send_sms.return_value = Result.success({"message_id": "123"})
        
        service = OptOutService(
            contact_flag_repository=contact_flag_repo,
            opt_out_audit_repository=opt_out_audit_repo,
            sms_service=sms_service,
            contact_repository=contact_repo
        )
        return service
    
    def test_process_webhook_message_with_opt_out(self, opt_out_service):
        """Test processing incoming message that contains opt-out keyword"""
        contact = Mock(id=1, phone="+1234567890")
        
        # Mock that no existing flags exist
        opt_out_service.contact_flag_repository.find_active_flags.return_value = []
        
        result = opt_out_service.process_incoming_message(
            contact=contact,
            message_body="STOP texting me",
            webhook_data={'id': 'msg123', 'direction': 'incoming'}
        )
        
        assert result.is_success
        assert result.data['action'] == 'opted_out'
        
        # Should have processed opt-out
        opt_out_service.contact_flag_repository.create.assert_called_once()
        opt_out_service.opt_out_audit_repository.create.assert_called_once()
        opt_out_service.sms_service.send_sms.assert_called_once()
    
    def test_process_webhook_message_with_opt_in(self, opt_out_service):
        """Test processing incoming message that contains opt-in keyword"""
        contact = Mock(id=1, phone="+1234567890")
        
        # Mock that contact is currently opted out
        existing_flag = Mock(id=5, flag_type='opted_out')
        opt_out_service.contact_flag_repository.find_active_flags.return_value = [existing_flag]
        
        result = opt_out_service.process_incoming_message(
            contact=contact,
            message_body="START",
            webhook_data={'id': 'msg124', 'direction': 'incoming'}
        )
        
        assert result.is_success
        assert result.data['action'] == 'opted_in'
        
        # Should have expired the flag
        opt_out_service.contact_flag_repository.expire_flag.assert_called_once_with(5)
    
    def test_process_webhook_message_normal(self, opt_out_service):
        """Test processing normal message (no opt-out/opt-in)"""
        contact = Mock(id=1, phone="+1234567890")
        
        result = opt_out_service.process_incoming_message(
            contact=contact,
            message_body="Yes, I'm interested in your services",
            webhook_data={'id': 'msg125', 'direction': 'incoming'}
        )
        
        assert result.is_success
        assert result.data['action'] == 'none'
        
        # Should not process opt-out or opt-in
        opt_out_service.contact_flag_repository.create.assert_not_called()
        opt_out_service.contact_flag_repository.expire_flag.assert_not_called()
        opt_out_service.sms_service.send_sms.assert_not_called()
    
    def test_process_webhook_within_time_limit(self, opt_out_service):
        """Test that opt-out is processed within 30 seconds"""
        import time
        start_time = time.time()
        
        contact = Mock(id=1, phone="+1234567890")
        
        # Mock that no existing flags exist
        opt_out_service.contact_flag_repository.find_active_flags.return_value = []
        
        result = opt_out_service.process_incoming_message(
            contact=contact,
            message_body="STOP",
            webhook_data={'id': 'msg126', 'direction': 'incoming'}
        )
        
        processing_time = time.time() - start_time
        
        assert result.is_success
        # Should complete within 30 seconds (with large margin for test environment)
        assert processing_time < 5.0  # Much faster in practice, but allow margin