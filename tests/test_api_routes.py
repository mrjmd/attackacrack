# tests/test_api_routes.py
"""
Tests for the main API endpoints to ensure they return the correct data and status codes.
"""

import json

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

def test_openphone_webhook_validation(client):
    """
    GIVEN a test client
    WHEN a 'token.validated' event is POSTed to the OpenPhone webhook
    THEN the response should be a success JSON object.
    """
    webhook_data = {'type': 'token.validated'}
    response = client.post('/api/webhooks/openphone', json=webhook_data)
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['success'] is True

# TODO: Add test for incoming message webhook ('message.new')
# TODO: Add test for generate_appointment_summary API endpoint
# TODO: Add test for get_contact_messages API endpoint
