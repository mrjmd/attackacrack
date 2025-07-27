# tests/test_sms_scheduler.py
import pytest
import requests
import pandas as pd
import os
import time
from datetime import datetime
import logging
from unittest.mock import patch, MagicMock

# Import the functions and constants from the script
import sms_scheduler
from sms_scheduler import (
    send_openphone_message,
    get_message_status,
    run_scheduler,
    MESSAGE_TEMPLATE,
    MAX_MESSAGES_PER_RUN,
    CSV_FILE
)

# Suppress logging output during tests for cleaner results
@pytest.fixture(autouse=True)
def suppress_logging(caplog):
    # Set default logging level to CRITICAL to suppress most output
    logging.disable(logging.CRITICAL) 
    yield
    logging.disable(logging.NOTSET) # Re-enable logging after test
    caplog.clear() # Clear records after each test

@pytest.fixture
def mock_env_vars(mocker):
    """Fixture to mock environment variables for OpenPhone API."""
    mocker.patch('os.getenv', side_effect=lambda key: {
        "OPENPHONE_API_KEY": "mock_api_key",
        "OPENPHONE_PHONE_NUMBER": "+15550001111"
    }.get(key))
    # Crucially, also patch the global variables in sms_scheduler module
    # as they are loaded at module import time
    mocker.patch('sms_scheduler.OPENPHONE_API_KEY', "mock_api_key")
    mocker.patch('sms_scheduler.OPENPHONE_PHONE_NUMBER', "+15550001111")


@pytest.fixture(autouse=True) # Make this autouse to ensure os.path.exists is always mocked
def mock_os_path_exists(mocker):
    """Fixture to mock os.path.exists within sms_scheduler."""
    mocker.patch('sms_scheduler.os.path.exists', return_value=True) # Assume CSV exists by default


@pytest.fixture
def mock_sleep(mocker):
    """Fixture to mock time.sleep."""
    mocker.patch('time.sleep')

# --- Tests for send_openphone_message ---

def test_send_openphone_message_success(mock_env_vars, mocker):
    """Test successful message sending."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"data": {"id": "msg_123", "status": "sent"}}
    mock_response.raise_for_status.return_value = None
    mocker.patch('requests.post', return_value=mock_response)

    message_id, status = send_openphone_message("+1234567890", "Test message")
    assert message_id == "msg_123"
    assert status == "sent"
    requests.post.assert_called_once()

def test_send_openphone_message_config_missing(mocker):
    """Test message sending with missing API key or phone number."""
    # Patch the global variables in the sms_scheduler module directly
    mocker.patch('sms_scheduler.OPENPHONE_API_KEY', None)
    mocker.patch('sms_scheduler.OPENPHONE_PHONE_NUMBER', None)
    mock_post = mocker.patch('requests.post')

    message_id, status = send_openphone_message("+1234567890", "Test message")
    assert message_id is None
    assert status == "error: config_missing"
    mock_post.assert_not_called()

def test_send_openphone_message_http_error(mock_env_vars, mocker):
    """Test message sending with HTTP error from API."""
    mock_response = MagicMock()
    mock_response.status_code = 400
    mock_response.text = "Bad Request"
    mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(response=mock_response)
    mocker.patch('requests.post', return_value=mock_response)

    message_id, status = send_openphone_message("+1234567890", "Test message")
    assert message_id is None
    assert status == "error: http_error_400"
    requests.post.assert_called_once()

def test_send_openphone_message_connection_error(mock_env_vars, mocker):
    """Test message sending with connection error."""
    mocker.patch('requests.post', side_effect=requests.exceptions.ConnectionError("Connection refused"))

    message_id, status = send_openphone_message("+1234567890", "Test message")
    assert message_id is None
    assert status == "error: connection_error"
    requests.post.assert_called_once()

def test_send_openphone_message_timeout_error(mock_env_vars, mocker):
    """Test message sending with timeout error."""
    mocker.patch('requests.post', side_effect=requests.exceptions.Timeout("Request timed out"))

    message_id, status = send_openphone_message("+1234567890", "Test message")
    assert message_id is None
    assert status == "error: timeout_error"
    requests.post.assert_called_once()

def test_send_openphone_message_unexpected_response_format(mock_env_vars, mocker):
    """Test message sending when API response is missing expected fields."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"unexpected_field": "value"} # Missing 'data' or 'id'/'status'
    mock_response.raise_for_status.return_value = None
    mocker.patch('requests.post', return_value=mock_response)

    message_id, status = send_openphone_message("+1234567890", "Test message")
    assert message_id is None
    assert "error: 200" in status # Checks for the status code in the error string
    requests.post.assert_called_once()

# --- Tests for get_message_status ---

def test_get_message_status_success(mock_env_vars, mocker):
    """Test successful message status retrieval."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"data": {"status": "delivered"}}
    mock_response.raise_for_status.return_value = None
    mocker.patch('requests.get', return_value=mock_response)

    status = get_message_status("msg_123")
    assert status == "delivered"
    requests.get.assert_called_once()

def test_get_message_status_config_missing(mocker):
    """Test status retrieval with missing API key."""
    # Patch the global variable in the sms_scheduler module directly
    mocker.patch('sms_scheduler.OPENPHONE_API_KEY', None)
    mock_get = mocker.patch('requests.get')

    status = get_message_status("msg_123")
    assert status is None
    mock_get.assert_not_called()

def test_get_message_status_http_404(mock_env_vars, mocker):
    """Test status retrieval with HTTP 404 (message not found)."""
    mock_response = MagicMock()
    mock_response.status_code = 404
    mock_response.text = "Not Found"
    mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(response=mock_response)
    mocker.patch('requests.get', return_value=mock_response)

    status = get_message_status("msg_123")
    assert status == "error: not_found"
    requests.get.assert_called_once()

def test_get_message_status_other_http_error(mock_env_vars, mocker):
    """Test status retrieval with other HTTP error."""
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.text = "Internal Server Error"
    mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(response=mock_response)
    mocker.patch('requests.get', return_value=mock_response)

    status = get_message_status("msg_123")
    assert status == "error: http_error_500"
    requests.get.assert_called_once()

def test_get_message_status_unexpected_response_format(mock_env_vars, mocker):
    """Test status retrieval when API response is missing expected fields."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"some_other_field": "value"} # Missing 'data' or 'status'
    mock_response.raise_for_status.return_value = None
    mocker.patch('requests.get', return_value=mock_response)

    status = get_message_status("msg_123")
    assert status is None
    requests.get.assert_called_once()

# --- Tests for run_scheduler ---

def test_run_scheduler_csv_not_found(mock_env_vars, mock_sleep, mocker, caplog):
    """Test run_scheduler when CSV file does not exist."""
    # Ensure os.path.exists is mocked to return False for this specific test
    mocker.patch('sms_scheduler.os.path.exists', return_value=False)
    mocker.patch('pandas.read_csv') # Ensure read_csv is not called

    with caplog.at_level(logging.CRITICAL):
        run_scheduler()
    
    assert "CSV file not found" in caplog.text
    pd.read_csv.assert_not_called()

def test_run_scheduler_empty_csv(mock_env_vars, mock_sleep, mocker, caplog):
    """Test run_scheduler when CSV file is empty."""
    mocker.patch('pandas.read_csv', side_effect=pd.errors.EmptyDataError("Empty CSV"))
    mocker.patch('pandas.DataFrame.to_csv') # Mock to_csv as it might be called in finally

    with caplog.at_level(logging.CRITICAL):
        run_scheduler()
    
    assert "The CSV file 'test.csv' is empty" in caplog.text
    pd.read_csv.assert_called_once()

def test_run_scheduler_new_contacts_sent_successfully(mock_env_vars, mock_os_path_exists, mock_sleep, mocker, caplog):
    """Test run_scheduler sending messages to new contacts successfully."""
    # Create a mock DataFrame that run_scheduler will operate on
    mock_df = pd.DataFrame({
        'name': ['Alice', 'Bob', 'Charlie'],
        'phone_number': ['+1234567890', '+19876543210', '+15551234567'],
        'status': ['', '', ''],
        'message_sent_at': ['', '', ''],
        'openphone_message_id': ['', '', '']
    })
    mocker.patch('pandas.read_csv', return_value=mock_df)

    # Mock send_openphone_message to simulate success
    mock_send = mocker.patch('sms_scheduler.send_openphone_message', side_effect=[
        ("msg_alice", "sent"),
        ("msg_bob", "sent"),
        ("msg_charlie", "sent")
    ])
    
    # Mock to_csv on the original mock_df instance
    mocker.patch.object(mock_df, 'to_csv')

    # Temporarily enable INFO logging for this test
    with caplog.at_level(logging.INFO):
        run_scheduler()
    
    # Assertions
    assert "Starting OpenPhone SMS Scheduler." in caplog.text
    assert "Attempting to send messages to 3 contacts." in caplog.text
    assert "Finished sending messages. Sent 3 messages in this run." in caplog.text
    
    assert mock_send.call_count == 3
    mock_send.assert_has_calls([
        mocker.call('+1234567890', MESSAGE_TEMPLATE.format(name='Alice')),
        mocker.call('+19876543210', MESSAGE_TEMPLATE.format(name='Bob')),
        mocker.call('+15551234567', MESSAGE_TEMPLATE.format(name='Charlie'))
    ])
    
    # Verify time.sleep was called for throttling
    assert time.sleep.call_count == 3 # 3 messages, 3 delays

    # Verify to_csv was called on the mock_df
    mock_df.to_csv.assert_called_once_with(CSV_FILE, index=False)
    
    # Assert directly on the mock_df's state after run_scheduler modifies it
    assert mock_df.loc[0, 'status'] == 'sent'
    assert mock_df.loc[0, 'openphone_message_id'] == 'msg_alice'
    assert pd.notna(mock_df.loc[0, 'message_sent_at'])

    assert mock_df.loc[1, 'status'] == 'sent'
    assert mock_df.loc[1, 'openphone_message_id'] == 'msg_bob'

    assert mock_df.loc[2, 'status'] == 'sent'
    assert mock_df.loc[2, 'openphone_message_id'] == 'msg_charlie'


def test_run_scheduler_status_update(mock_env_vars, mock_os_path_exists, mock_sleep, mocker, caplog):
    """Test run_scheduler updating statuses for previously sent messages."""
    mock_df = pd.DataFrame({
        'name': ['Dave', 'Eve'],
        'phone_number': ['+11112223333', '+14445556666'],
        'status': ['sent', 'queued'],
        'message_sent_at': ['2025-07-20 10:00:00', '2025-07-20 11:00:00'],
        'openphone_message_id': ['msg_dave', 'msg_eve']
    })
    mocker.patch('pandas.read_csv', return_value=mock_df)

    # Mock get_message_status to return new statuses
    mock_get_status = mocker.patch('sms_scheduler.get_message_status', side_effect=[
        "delivered", # Dave's new status
        "failed"     # Eve's new status
    ])
    
    mocker.patch.object(mock_df, 'to_csv')

    # Temporarily enable INFO logging for this test
    with caplog.at_level(logging.INFO):
        run_scheduler()

    assert "Checking status for 2 previously sent messages..." in caplog.text
    assert "Updated contact Dave (+11112223333) status to: delivered" in caplog.text
    assert "Updated contact Eve (+14445556666) status to: failed" in caplog.text
    
    assert mock_get_status.call_count == 2
    mock_get_status.assert_has_calls([
        mocker.call('msg_dave'),
        mocker.call('msg_eve')
    ])
    
    # Verify API_REQUEST_DELAY is applied
    assert time.sleep.call_count == 2 # 2 status checks, 2 delays

    mock_df.to_csv.assert_called_once_with(CSV_FILE, index=False)
    
    # Assert directly on the mock_df's state
    assert mock_df.loc[0, 'status'] == 'delivered'
    assert mock_df.loc[1, 'status'] == 'failed'

def test_run_scheduler_max_messages_limit(mock_env_vars, mock_os_path_exists, mock_sleep, mocker, caplog):
    """Test run_scheduler respects MAX_MESSAGES_PER_RUN."""
    # Create a mock DataFrame with more contacts than MAX_MESSAGES_PER_RUN
    contacts_data = {
        'name': [f'Contact {i}' for i in range(MAX_MESSAGES_PER_RUN + 5)],
        'phone_number': [f'+1555100000{i}' for i in range(MAX_MESSAGES_PER_RUN + 5)],
        'status': [''] * (MAX_MESSAGES_PER_RUN + 5),
        'message_sent_at': [''] * (MAX_MESSAGES_PER_RUN + 5),
        'openphone_message_id': [''] * (MAX_MESSAGES_PER_RUN + 5)
    }
    mock_df = pd.DataFrame(contacts_data)
    mocker.patch('pandas.read_csv', return_value=mock_df)

    mock_send = mocker.patch('sms_scheduler.send_openphone_message', side_effect=[
        (f"msg_{i}", "sent") for i in range(MAX_MESSAGES_PER_RUN + 5)
    ])
    
    mocker.patch.object(mock_df, 'to_csv')

    # Temporarily enable INFO logging for this test
    with caplog.at_level(logging.INFO):
        run_scheduler()
    
    assert f"Attempting to send messages to {MAX_MESSAGES_PER_RUN} contacts." in caplog.text
    assert f"Reached maximum messages per run ({MAX_MESSAGES_PER_RUN}). Stopping sending." in caplog.text
    assert f"Finished sending messages. Sent {MAX_MESSAGES_PER_RUN} messages in this run." in caplog.text
    
    assert mock_send.call_count == MAX_MESSAGES_PER_RUN
    assert time.sleep.call_count == MAX_MESSAGES_PER_RUN # For MESSAGE_THROTTLING_DELAY
    mock_df.to_csv.assert_called_once_with(CSV_FILE, index=False)

def test_run_scheduler_invalid_phone_number(mock_env_vars, mock_os_path_exists, mock_sleep, mocker, caplog):
    """Test run_scheduler handles invalid phone numbers."""
    mock_df = pd.DataFrame({
        'name': ['Frank', 'Grace'],
        'phone_number': ['12345', 'invalid_number'], # Invalid numbers
        'status': ['', ''],
        'message_sent_at': ['', ''],
        'openphone_message_id': ['', '']
    })
    mocker.patch('pandas.read_csv', return_value=mock_df)
    mocker.patch('sms_scheduler.send_openphone_message') # Should not be called for invalid numbers
    
    mocker.patch.object(mock_df, 'to_csv')

    with caplog.at_level(logging.WARNING):
        run_scheduler()
    
    assert "Skipping invalid phone number for Frank: 12345. Must be E.164 format" in caplog.text
    assert "Skipping invalid phone number for Grace: invalid_number. Must be E.164 format" in caplog.text
    
    sms_scheduler.send_openphone_message.assert_not_called() # Ensure no API call for invalid numbers
    
    mock_df.to_csv.assert_called_once_with(CSV_FILE, index=False)
    
    assert mock_df.loc[0, 'status'] == 'error: invalid_phone_number'
    assert mock_df.loc[1, 'status'] == 'error: invalid_phone_number'

def test_run_scheduler_parser_error(mock_env_vars, mock_sleep, mocker, caplog):
    """Test run_scheduler handles CSV parsing errors."""
    mocker.patch('sms_scheduler.os.path.exists', return_value=True) # Ensure exists is true
    mocker.patch('pandas.read_csv', side_effect=pd.errors.ParserError("Bad CSV format"))
    mocker.patch('pandas.DataFrame.to_csv') 

    with caplog.at_level(logging.CRITICAL):
        run_scheduler()
    
    assert "Error parsing CSV file 'test.csv': Bad CSV format" in caplog.text
    pd.read_csv.assert_called_once()
    # In this error case, df is not assigned, so to_csv is not called on a DataFrame instance.
    # The finally block's if df is not None will prevent the call.
    pd.DataFrame.to_csv.assert_not_called()

def test_run_scheduler_file_not_found_on_save(mock_env_vars, mock_os_path_exists, mock_sleep, mocker, caplog):
    """Test run_scheduler handles FileNotFoundError during CSV save."""
    mock_df = pd.DataFrame({
        'name': ['Harry'],
        'phone_number': ['+17778889999'],
        'status': [''],
        'message_sent_at': [''],
        'openphone_message_id': ['']
    })
    mocker.patch('pandas.read_csv', return_value=mock_df)
    mocker.patch('sms_scheduler.send_openphone_message', return_value=("msg_harry", "sent"))
    
    # Mock to_csv on the specific mock_df instance
    mocker.patch.object(mock_df, 'to_csv', side_effect=Exception("Disk full error"))

    with caplog.at_level(logging.CRITICAL):
        run_scheduler()
    
    assert "Failed to save updated CSV file: Disk full error" in caplog.text
    sms_scheduler.send_openphone_message.assert_called_once()
    mock_df.to_csv.assert_called_once_with(CSV_FILE, index=False) # Assert it was called before exception

def test_run_scheduler_no_new_contacts(mock_env_vars, mock_os_path_exists, mock_sleep, mocker, caplog):
    """Test run_scheduler when no new contacts need messaging."""
    mock_df = pd.DataFrame({
        'name': ['Ian'],
        'phone_number': ['+10000000000'],
        'status': ['sent'], # Already sent
        'message_sent_at': ['2025-07-20 12:00:00'],
        'openphone_message_id': ['msg_ian']
    })
    mocker.patch('pandas.read_csv', return_value=mock_df)
    mocker.patch('sms_scheduler.send_openphone_message') # Ensure not called
    mocker.patch('sms_scheduler.get_message_status', return_value="delivered") # Ensure status check runs
    
    mocker.patch.object(mock_df, 'to_csv')

    with caplog.at_level(logging.INFO):
        run_scheduler()
    
    assert "No new contacts to message or all desired messages sent for this run." in caplog.text
    sms_scheduler.send_openphone_message.assert_not_called()
    sms_scheduler.get_message_status.assert_called_once_with('msg_ian')
    mock_df.to_csv.assert_called_once_with(CSV_FILE, index=False)
