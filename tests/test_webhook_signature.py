# tests/test_webhook_signature.py
"""
Comprehensive tests for OpenPhone webhook signature verification.
Tests both valid and invalid signatures to ensure webhook security.
"""

import pytest
import json
import hmac
import hashlib
import base64
import time
from unittest.mock import patch


@pytest.fixture
def webhook_signing_key():
    """Fixture providing a test webhook signing key"""
    return base64.b64encode(b"test_webhook_signing_key_12345").decode('utf-8')


@pytest.fixture
def webhook_payload():
    """Fixture providing a test webhook payload"""
    return {
        "type": "message.received",
        "data": {
            "object": {
                "id": "MSG123456",
                "from": "+1234567890",
                "to": ["+0987654321"],
                "text": "Test message",
                "status": "received",
                "createdAt": "2025-07-30T10:00:00.000Z"
            }
        }
    }


class TestWebhookSignatureVerification:
    """Test webhook signature verification security"""
    
    def generate_valid_signature(self, payload_str, signing_key, timestamp=None):
        """Generate a valid OpenPhone webhook signature"""
        if timestamp is None:
            timestamp = str(int(time.time() * 1000))
        
        # OpenPhone signature format: timestamp.payload
        signed_data = timestamp.encode() + b'.' + payload_str.encode()
        
        # Decode the base64 signing key
        signing_key_bytes = base64.b64decode(signing_key)
        
        # Compute HMAC-SHA256
        signature = base64.b64encode(
            hmac.new(
                key=signing_key_bytes,
                msg=signed_data,
                digestmod=hashlib.sha256
            ).digest()
        ).decode('utf-8')
        
        # Return OpenPhone format: hmac;version;timestamp;signature
        return f"hmac;1;{timestamp};{signature}"
    
    def test_valid_signature_accepted(self, client, app, webhook_signing_key, webhook_payload):
        """Test that valid signatures are accepted"""
        with app.app_context():
            app.config['OPENPHONE_WEBHOOK_SIGNING_KEY'] = webhook_signing_key
            
            payload_str = json.dumps(webhook_payload)
            valid_signature = self.generate_valid_signature(payload_str, webhook_signing_key)
            
            response = client.post(
                '/api/webhooks/openphone',
                data=payload_str,
                headers={
                    'Content-Type': 'application/json',
                    'openphone-signature': valid_signature
                }
            )
            
            # Should be accepted (200 OK)
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['status'] in ['created', 'updated', 'success']
    
    def test_missing_signature_rejected(self, client, app, webhook_signing_key, webhook_payload):
        """Test that requests without signature are rejected"""
        with app.app_context():
            app.config['OPENPHONE_WEBHOOK_SIGNING_KEY'] = webhook_signing_key
            
            response = client.post(
                '/api/webhooks/openphone',
                data=json.dumps(webhook_payload),
                headers={'Content-Type': 'application/json'}
                # No openphone-signature header
            )
            
            # Should be forbidden
            assert response.status_code == 403
    
    def test_invalid_signature_format_rejected(self, client, app, webhook_signing_key, webhook_payload):
        """Test that malformed signatures are rejected"""
        with app.app_context():
            app.config['OPENPHONE_WEBHOOK_SIGNING_KEY'] = webhook_signing_key
            
            invalid_signatures = [
                "invalid_format",  # Not in correct format
                "hmac;1;timestamp",  # Missing signature part
                "wrong;1;12345;signature",  # Wrong algorithm identifier
                ";1;12345;signature",  # Missing algorithm
                "hmac;1;12345;",  # Missing signature
            ]
            
            for invalid_sig in invalid_signatures:
                response = client.post(
                    '/api/webhooks/openphone',
                    data=json.dumps(webhook_payload),
                    headers={
                        'Content-Type': 'application/json',
                        'openphone-signature': invalid_sig
                    }
                )
                
                # Should be forbidden
                assert response.status_code == 403
    
    def test_wrong_signature_rejected(self, client, app, webhook_signing_key, webhook_payload):
        """Test that incorrect signatures are rejected"""
        with app.app_context():
            app.config['OPENPHONE_WEBHOOK_SIGNING_KEY'] = webhook_signing_key
            
            payload_str = json.dumps(webhook_payload)
            # Generate signature with wrong key
            wrong_key = base64.b64encode(b"wrong_key").decode('utf-8')
            wrong_signature = self.generate_valid_signature(payload_str, wrong_key)
            
            response = client.post(
                '/api/webhooks/openphone',
                data=payload_str,
                headers={
                    'Content-Type': 'application/json',
                    'openphone-signature': wrong_signature
                }
            )
            
            # Should be forbidden
            assert response.status_code == 403
    
    def test_tampered_payload_rejected(self, client, app, webhook_signing_key, webhook_payload):
        """Test that tampered payloads are rejected"""
        with app.app_context():
            app.config['OPENPHONE_WEBHOOK_SIGNING_KEY'] = webhook_signing_key
            
            # Generate signature for original payload
            original_payload_str = json.dumps(webhook_payload)
            valid_signature = self.generate_valid_signature(original_payload_str, webhook_signing_key)
            
            # Tamper with the payload
            tampered_payload = webhook_payload.copy()
            tampered_payload['data']['object']['text'] = "Tampered message"
            tampered_payload_str = json.dumps(tampered_payload)
            
            response = client.post(
                '/api/webhooks/openphone',
                data=tampered_payload_str,  # Send tampered payload
                headers={
                    'Content-Type': 'application/json',
                    'openphone-signature': valid_signature  # But use original signature
                }
            )
            
            # Should be forbidden
            assert response.status_code == 403
    
    def test_replay_attack_with_old_timestamp(self, client, app, webhook_signing_key, webhook_payload):
        """Test that old timestamps are handled (basic replay protection awareness)"""
        with app.app_context():
            app.config['OPENPHONE_WEBHOOK_SIGNING_KEY'] = webhook_signing_key
            
            payload_str = json.dumps(webhook_payload)
            # Generate signature with old timestamp (1 hour ago)
            old_timestamp = str(int((time.time() - 3600) * 1000))
            old_signature = self.generate_valid_signature(payload_str, webhook_signing_key, old_timestamp)
            
            response = client.post(
                '/api/webhooks/openphone',
                data=payload_str,
                headers={
                    'Content-Type': 'application/json',
                    'openphone-signature': old_signature
                }
            )
            
            # Currently the implementation doesn't check timestamp freshness
            # but signature should still be valid
            assert response.status_code == 200
    
    def test_missing_signing_key_config(self, client, app, webhook_payload):
        """Test behavior when signing key is not configured"""
        with app.app_context():
            # Remove signing key from config
            app.config['OPENPHONE_WEBHOOK_SIGNING_KEY'] = None
            
            response = client.post(
                '/api/webhooks/openphone',
                data=json.dumps(webhook_payload),
                headers={
                    'Content-Type': 'application/json',
                    'openphone-signature': 'hmac;1;12345;signature'
                }
            )
            
            # Should return 500 (server error)
            assert response.status_code == 500
    
    def test_invalid_base64_signing_key(self, client, app, webhook_payload):
        """Test behavior with invalid base64 signing key"""
        with app.app_context():
            # Set invalid base64 as signing key
            app.config['OPENPHONE_WEBHOOK_SIGNING_KEY'] = "not-valid-base64!"
            
            response = client.post(
                '/api/webhooks/openphone',
                data=json.dumps(webhook_payload),
                headers={
                    'Content-Type': 'application/json',
                    'openphone-signature': 'hmac;1;12345;signature'
                }
            )
            
            # Should return 500 (server error)
            assert response.status_code == 500
    
    def test_signature_verification_with_different_payloads(self, client, app, webhook_signing_key):
        """Test signature verification with various webhook types"""
        with app.app_context():
            app.config['OPENPHONE_WEBHOOK_SIGNING_KEY'] = webhook_signing_key
            
            test_payloads = [
                {
                    "type": "message.delivered",
                    "data": {"object": {"id": "MSG789", "status": "delivered"}}
                },
                {
                    "type": "call.completed",
                    "data": {"object": {"id": "CALL123", "duration": 300}}
                },
                {
                    "type": "call.summary.completed",
                    "data": {"object": {"callId": "CALL123", "summary": "Test summary"}}
                }
            ]
            
            for payload in test_payloads:
                payload_str = json.dumps(payload)
                valid_signature = self.generate_valid_signature(payload_str, webhook_signing_key)
                
                response = client.post(
                    '/api/webhooks/openphone',
                    data=payload_str,
                    headers={
                        'Content-Type': 'application/json',
                        'openphone-signature': valid_signature
                    }
                )
                
                # All should be accepted with valid signature
                assert response.status_code == 200
    
    def test_signature_with_unicode_content(self, client, app, webhook_signing_key):
        """Test signature verification with unicode content"""
        with app.app_context():
            app.config['OPENPHONE_WEBHOOK_SIGNING_KEY'] = webhook_signing_key
            
            unicode_payload = {
                "type": "message.received",
                "data": {
                    "object": {
                        "id": "MSG999",
                        "from": "+1234567890",
                        "to": ["+0987654321"],
                        "text": "Hello 世界 🌍 émojis",
                        "status": "received"
                    }
                }
            }
            
            payload_str = json.dumps(unicode_payload, ensure_ascii=False)
            valid_signature = self.generate_valid_signature(payload_str, webhook_signing_key)
            
            response = client.post(
                '/api/webhooks/openphone',
                data=payload_str.encode('utf-8'),
                headers={
                    'Content-Type': 'application/json; charset=utf-8',
                    'openphone-signature': valid_signature
                }
            )
            
            # Should be accepted
            assert response.status_code == 200
    
    def test_signature_case_sensitivity(self, client, app, webhook_signing_key, webhook_payload):
        """Test that signature verification is case sensitive"""
        with app.app_context():
            app.config['OPENPHONE_WEBHOOK_SIGNING_KEY'] = webhook_signing_key
            
            payload_str = json.dumps(webhook_payload)
            valid_signature = self.generate_valid_signature(payload_str, webhook_signing_key)
            
            # Modify the case of the signature
            parts = valid_signature.split(';')
            parts[3] = parts[3].upper()  # Make signature uppercase
            invalid_signature = ';'.join(parts)
            
            response = client.post(
                '/api/webhooks/openphone',
                data=payload_str,
                headers={
                    'Content-Type': 'application/json',
                    'openphone-signature': invalid_signature
                }
            )
            
            # Should be forbidden (signatures are case sensitive)
            assert response.status_code == 403


class TestWebhookEndpointSecurity:
    """Test general webhook endpoint security"""
    
    def generate_valid_signature(self, payload_str, signing_key, timestamp=None):
        """Generate a valid OpenPhone webhook signature"""
        if timestamp is None:
            timestamp = str(int(time.time() * 1000))
        
        # OpenPhone signature format: timestamp.payload
        signed_data = timestamp.encode() + b'.' + payload_str.encode()
        
        # Decode the base64 signing key
        signing_key_bytes = base64.b64decode(signing_key)
        
        # Calculate HMAC-SHA256
        signature_bytes = hmac.new(
            signing_key_bytes,
            signed_data,
            hashlib.sha256
        ).digest()
        
        # Encode to base64
        signature_base64 = base64.b64encode(signature_bytes).decode()
        
        # OpenPhone header format: t=timestamp,v1=signature
        return f't={timestamp},v1={signature_base64}'
    
    def test_webhook_endpoint_requires_post(self, client, app):
        """Test that webhook endpoint only accepts POST requests"""
        with app.app_context():
            app.config['OPENPHONE_WEBHOOK_SIGNING_KEY'] = 'test_key'
            
            # Try other HTTP methods
            for method in ['GET', 'PUT', 'DELETE', 'PATCH']:
                response = getattr(client, method.lower())('/api/webhooks/openphone')
                assert response.status_code in [403, 405]  # Forbidden or Method Not Allowed
    
    def test_webhook_endpoint_logging(self, client, app, webhook_signing_key, webhook_payload, caplog):
        """Test that webhook verification is properly logged"""
        with app.app_context():
            app.config['OPENPHONE_WEBHOOK_SIGNING_KEY'] = webhook_signing_key
            
            payload_str = json.dumps(webhook_payload)
            valid_signature = self.generate_valid_signature(payload_str, webhook_signing_key)
            
            with caplog.at_level('INFO'):
                response = client.post(
                    '/api/webhooks/openphone',
                    data=payload_str,
                    headers={
                        'Content-Type': 'application/json',
                        'openphone-signature': valid_signature
                    }
                )
            
            assert response.status_code == 200
            # Check that verification was logged
            assert any("OpenPhone signature verified successfully" in record.message 
                      for record in caplog.records)