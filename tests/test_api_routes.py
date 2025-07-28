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
    # --- FIXED: This test now simulates a valid signed request ---
    # Set a dummy signing key in the app's test config
    signing_key = "test_signing_key"
    app.config['OPENPHONE_WEBHOOK_SIGNING_KEY'] = signing_key

    webhook_data = {'type': 'token.validated'}
    payload = json.dumps(webhook_data).encode('utf-8')

    # Calculate the expected signature
    expected_signature = hmac.new(
        key=signing_key.encode('utf-8'),
        msg=payload,
        digestmod=hashlib.sha256
    ).hexdigest()

    headers = {
        'x-openphone-signature-v1': expected_signature,
        'Content-Type': 'application/json'
    }

    response = client.post('/api/webhooks/openphone', data=payload, headers=headers)
    
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['success'] is True

# TODO: Add test for incoming message webhook ('message.new')
# TODO: Add test for generate_appointment_summary API endpoint
# TODO: Add test for get_contact_messages API endpoint
