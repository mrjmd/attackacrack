"""
Integration test for opt-out processing through webhook pipeline

Tests the complete flow from webhook receipt to opt-out flag creation.
"""

import pytest
import json
from datetime import datetime
from utils.datetime_utils import utc_now, ensure_utc
from unittest.mock import Mock, patch

from app import create_app
from crm_database import db, Contact, ContactFlag, OptOutAudit, Activity, Conversation


class TestOptOutWebhookIntegration:
    """Test opt-out processing through the webhook pipeline"""
    
    @pytest.fixture
    def contact(self, db_session):
        """Create test contact"""
        contact = Contact(
            first_name='John',
            last_name='Doe',
            phone='+1234567890',
            email='john@example.com'
        )
        db_session.add(contact)
        db_session.commit()
        return contact
    
    @pytest.fixture
    def webhook_headers(self):
        """Create webhook headers with signature"""
        return {
            'openphone-signature': 'hmac;1;1640995200;test_signature',
            'Content-Type': 'application/json'
        }
    
    def test_opt_out_webhook_creates_flag(self, app, client, db_session, contact, webhook_headers):
        """Test that receiving STOP message creates opt-out flag"""
        # Prepare webhook payload
        webhook_data = {
            'type': 'message.received',
            'data': {
                'object': {
                    'id': 'msg_123',
                    'direction': 'incoming',
                    'from': '+1234567890',
                    'to': ['+19876543210'],
                    'text': 'STOP',
                    'conversationId': 'conv_123',
                    'status': 'received',
                    'createdAt': utc_now().isoformat()
                }
            }
        }
        
        with app.app_context():
            # Set up webhook signing key for tests (base64 encoded)
            app.config['OPENPHONE_WEBHOOK_SIGNING_KEY'] = 'dGVzdF9zaWduaW5nX2tleQ=='  # base64 of 'test_signing_key'
            
            # Mock OpenPhone signature verification
            with patch('hmac.compare_digest', return_value=True):
                # Mock SMS service to avoid actual API calls
                with patch('services.openphone_service.OpenPhoneService.send_sms') as mock_send:
                    mock_send.return_value = Mock(is_success=True)
                    
                    # Send webhook
                    response = client.post(
                        '/api/webhooks/openphone',
                        data=json.dumps(webhook_data),
                        headers=webhook_headers
                    )
                    
                    assert response.status_code == 200
                    
                    # Check that opt-out flag was created
                    flags = ContactFlag.query.filter_by(
                        contact_id=contact.id,
                        flag_type='opted_out'
                    ).all()
                    
                    assert len(flags) == 1
                    assert flags[0].flag_reason == 'Received opt-out message: STOP'
                    assert flags[0].applies_to == 'sms'
                    
                    # Check that audit log was created
                    audits = OptOutAudit.query.filter_by(
                        contact_id=contact.id
                    ).all()
                    
                    assert len(audits) == 1
                    assert audits[0].keyword_used == 'STOP'
                    assert audits[0].opt_out_method == 'sms_keyword'
                    assert audits[0].phone_number == '+1234567890'
                    
                    # Check that confirmation SMS was sent
                    mock_send.assert_called_once()
                    call_args = mock_send.call_args[1]
                    assert call_args['to_phone'] == '+1234567890'
                    assert 'unsubscribed' in call_args['message'].lower()
    
    def test_opt_in_webhook_removes_flag(self, app, client, db_session, contact, webhook_headers):
        """Test that receiving START message removes opt-out flag"""
        with app.app_context():
            # Create existing opt-out flag
            flag = ContactFlag(
                contact_id=contact.id,
                flag_type='opted_out',
                flag_reason='Previous opt-out',
                applies_to='sms',
                created_by='test'
            )
            db_session.add(flag)
            db_session.commit()
            flag_id = flag.id
        
        # Prepare webhook payload
        webhook_data = {
            'type': 'message.received',
            'data': {
                'object': {
                    'id': 'msg_124',
                    'direction': 'incoming',
                    'from': '+1234567890',
                    'to': ['+19876543210'],
                    'text': 'START',
                    'conversationId': 'conv_123',
                    'status': 'received',
                    'createdAt': utc_now().isoformat()
                }
            }
        }
        
        with app.app_context():
            # Set up webhook signing key for tests (base64 encoded)
            app.config['OPENPHONE_WEBHOOK_SIGNING_KEY'] = 'dGVzdF9zaWduaW5nX2tleQ=='  # base64 of 'test_signing_key'
            
            # Mock OpenPhone signature verification
            with patch('hmac.compare_digest', return_value=True):
                # Mock SMS service
                with patch('services.openphone_service.OpenPhoneService.send_sms') as mock_send:
                    mock_send.return_value = Mock(is_success=True)
                    
                    # Send webhook
                    response = client.post(
                        '/api/webhooks/openphone',
                        data=json.dumps(webhook_data),
                        headers=webhook_headers
                    )
                    
                    assert response.status_code == 200
                    
                    # Check that opt-out flag was expired
                    flag = db.session.get(ContactFlag, flag_id)
                    assert flag.expires_at is not None
                    assert ensure_utc(flag.expires_at) <= utc_now()
                    
                    # Check that audit log was created for opt-in
                    audits = OptOutAudit.query.filter_by(
                        contact_id=contact.id,
                        opt_out_method='sms_opt_in'
                    ).all()
                    
                    assert len(audits) == 1
                    assert audits[0].keyword_used == 'START'
                    
                    # Check that confirmation SMS was sent
                    mock_send.assert_called_once()
                    call_args = mock_send.call_args[1]
                    assert 'resubscribed' in call_args['message'].lower()
    
    def test_normal_message_no_opt_out(self, app, client, db_session, contact, webhook_headers):
        """Test that normal messages don't trigger opt-out"""
        # Prepare webhook payload
        webhook_data = {
            'type': 'message.received',
            'data': {
                'object': {
                    'id': 'msg_125',
                    'direction': 'incoming',
                    'from': '+1234567890',
                    'to': ['+19876543210'],
                    'text': 'Yes, I am interested in your services',
                    'conversationId': 'conv_123',
                    'status': 'received',
                    'createdAt': utc_now().isoformat()
                }
            }
        }
        
        with app.app_context():
            # Set up webhook signing key for tests (base64 encoded)
            app.config['OPENPHONE_WEBHOOK_SIGNING_KEY'] = 'dGVzdF9zaWduaW5nX2tleQ=='  # base64 of 'test_signing_key'
            
            # Mock OpenPhone signature verification
            with patch('hmac.compare_digest', return_value=True):
                # Mock SMS service
                with patch('services.openphone_service.OpenPhoneService.send_sms') as mock_send:
                    mock_send.return_value = Mock(is_success=True)
                    
                    # Send webhook
                    response = client.post(
                        '/api/webhooks/openphone',
                        data=json.dumps(webhook_data),
                        headers=webhook_headers
                    )
                    
                    assert response.status_code == 200
                    
                    # Check that no opt-out flag was created
                    flags = ContactFlag.query.filter_by(
                        contact_id=contact.id,
                        flag_type='opted_out'
                    ).all()
                    
                    assert len(flags) == 0
                    
                    # Check that no audit log was created
                    audits = OptOutAudit.query.filter_by(
                        contact_id=contact.id
                    ).all()
                    
                    assert len(audits) == 0
                    
                    # Check that no confirmation SMS was sent
                    mock_send.assert_not_called()
                    
                    # But activity should still be created
                    activities = Activity.query.filter_by(
                        contact_id=contact.id
                    ).all()
                    
                    assert len(activities) == 1
                    assert activities[0].body == 'Yes, I am interested in your services'