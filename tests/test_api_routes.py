# tests/test_api_routes.py
"""
Tests for the main API endpoints to ensure they return the correct data and status codes.
"""

import json
import hmac
import hashlib

def test_get_contacts_api(client):
    """
    GIVEN a test client
    WHEN the '/api/contacts' endpoint is requested
    THEN check that the response is successful and contains the seeded contact data.
    """
    response = client.get('/api/contacts')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert isinstance(data, list)
    assert len(data) >= 1
    assert data[0]['first_name'] == 'Test'
    assert data[0]['email'] == 'test@user.com'

def test_openphone_webhook_validation(client, app):
    """
    GIVEN a test client and a valid signature
    WHEN a 'token.validated' event is POSTed to the OpenPhone webhook
    THEN the response should be a 200 OK.
    """
    import base64
    import time
    
    # Set a dummy signing key in the app's test config (base64 encoded)
    signing_key = base64.b64encode(b"test_signing_key").decode('utf-8')
    app.config['OPENPHONE_WEBHOOK_SIGNING_KEY'] = signing_key

    webhook_data = {'type': 'token.validated'}
    payload = json.dumps(webhook_data).encode('utf-8')
    
    # Generate timestamp
    timestamp = str(int(time.time() * 1000))  # milliseconds
    
    # Create signed data: timestamp.payload
    signed_data = timestamp.encode() + b'.' + payload
    
    # Calculate the expected signature
    signing_key_bytes = base64.b64decode(signing_key)
    expected_signature = base64.b64encode(
        hmac.new(
            key=signing_key_bytes,
            msg=signed_data,
            digestmod=hashlib.sha256
        ).digest()
    ).decode('utf-8')
    
    # Create OpenPhone signature header format: hmac;version;timestamp;signature
    signature_header = f"hmac;1;{timestamp};{expected_signature}"

    headers = {
        'openphone-signature': signature_header,
        'Content-Type': 'application/json'
    }

    response = client.post('/api/webhooks/openphone', data=payload, headers=headers)
    
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['status'] == 'success'

# TODO: Add test for incoming message webhook ('message.new')
# TODO: Add test for generate_appointment_summary API endpoint
# TODO: Add test for get_contact_messages API endpoint
