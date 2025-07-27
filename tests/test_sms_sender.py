# tests/test_sms_sender.py
import pytest
import requests
from flask import current_app
from sms_sender import send_sms # Import the function directly

def test_send_sms_success(app, mocker):
    """
    GIVEN a valid phone number, message, and configured API key
    WHEN send_sms is called
    THEN it should successfully send an SMS via the OpenPhone API
    AND return the API's JSON response.
    """
    # 1. Setup
    # Configure the Flask app with a mock API key for this test
    app.config['OPENPHONE_API_KEY'] = 'mock_openphone_api_key_123'

    # Mock the requests.post method to simulate a successful API call
    mock_response = mocker.Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"status": "sent", "messageId": "sms_abc456"}
    mock_response.raise_for_status.return_value = None # Ensure no exception is raised

    mocker.patch('requests.post', return_value=mock_response)

    phone_number = "+19876543210"
    message = "Hello from Attack-a-Crack!"

    # 2. Execution
    with app.app_context(): # `send_sms` uses `current_app`, so an app context is needed
        result = send_sms(phone_number, message)

    # 3. Assertions
    assert result == {"status": "sent", "messageId": "sms_abc456"}
    
    # Verify that requests.post was called with the correct arguments
    expected_url = "https://api.openphone.co/v1/sms"
    expected_headers = {
        "Authorization": "Bearer mock_openphone_api_key_123",
        "Content-Type": "application/json"
    }
    expected_data = {
        "to": phone_number,
        "body": message
    }
    requests.post.assert_called_once_with(
        expected_url,
        json=expected_data,
        headers=expected_headers
    )

def test_send_sms_no_api_key(app, mocker):
    """
    GIVEN no OpenPhone API key is configured
    WHEN send_sms is called
    THEN it should return None
    AND not attempt to make an HTTP request.
    """
    # 1. Setup
    # Ensure the API key is not set for this test
    if 'OPENPHONE_API_KEY' in app.config:
        del app.config['OPENPHONE_API_KEY']
    
    # Mock requests.post to ensure it's not called
    mock_post = mocker.patch('requests.post')

    phone_number = "+19876543210"
    message = "Hello from Attack-a-Crack!"

    # 2. Execution
    with app.app_context():
        result = send_sms(phone_number, message)

    # 3. Assertions
    assert result is None
    # Verify that requests.post was never called
    mock_post.assert_not_called()

def test_send_sms_api_error_response(app, mocker):
    """
    GIVEN the OpenPhone API returns an error status code (e.g., 400, 500)
    WHEN send_sms is called
    THEN it should return None.
    """
    # 1. Setup
    app.config['OPENPHONE_API_KEY'] = 'mock_openphone_api_key_123'

    # Mock requests.post to simulate an API error response
    mock_response = mocker.Mock()
    mock_response.status_code = 400 # Simulate a Bad Request error
    mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("400 Client Error: Bad Request")
    
    mocker.patch('requests.post', return_value=mock_response)

    phone_number = "+19876543210"
    message = "Hello from Attack-a-Crack!"

    # 2. Execution
    with app.app_context():
        result = send_sms(phone_number, message)

    # 3. Assertions
    assert result is None
    # Verify that requests.post was called
    requests.post.assert_called_once()

def test_send_sms_network_error(app, mocker):
    """
    GIVEN a network or connection error occurs during the API call
    WHEN send_sms is called
    THEN it should return None.
    """
    # 1. Setup
    app.config['OPENPHONE_API_KEY'] = 'mock_openphone_api_key_123'

    # Mock requests.post to raise a RequestException (e.g., network issue)
    mocker.patch('requests.post', side_effect=requests.exceptions.RequestException("Connection refused"))

    phone_number = "+19876543210"
    message = "Hello from Attack-a-Crack!"

    # 2. Execution
    with app.app_context():
        result = send_sms(phone_number, message)

    # 3. Assertions
    assert result is None
    # Verify that requests.post was called
    requests.post.assert_called_once()
