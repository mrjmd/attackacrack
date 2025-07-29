# tests/test_api_integrations.py
import pytest
import os
import pickle # Import pickle directly for patching
from datetime import datetime, timedelta, UTC
from unittest.mock import patch, MagicMock, call
import json
import logging

# Corrected: Import the module itself for patching, and specific functions if needed for direct calls
import api_integrations
# Corrected: Import necessary Google modules for type hinting and specific patching
import google.oauth2.credentials
import google_auth_oauthlib.flow
import googleapiclient.discovery
import requests # For patching requests.get/post

# Import ContactService for type hinting in mocks
from services.contact_service import ContactService

# Fixture to provide a Flask app context for tests that need current_app
@pytest.fixture
def app_context(app):
    """Provides an application context for tests."""
    with app.app_context():
        yield app

# Fixture to suppress print statements from api_integrations for cleaner test output
@pytest.fixture(autouse=True)
def suppress_prints(mocker):
    mocker.patch('builtins.print')

# Fixture to suppress logging from api_integrations for cleaner test output
@pytest.fixture(autouse=True)
def suppress_api_logging(caplog):
    # Disable logging for the api_integrations module specifically
    logging.getLogger('api_integrations').setLevel(logging.CRITICAL)
    yield
    logging.getLogger('api_integrations').setLevel(logging.NOTSET)
    caplog.clear()


# --- Tests for get_upcoming_calendar_events ---

def test_get_upcoming_calendar_events_success(app_context, mocker):
    """
    Test successful fetching of upcoming calendar events.
    """
    # 1. Setup
    mock_creds = MagicMock()
    mock_creds.valid = True
    mocker.patch('api_integrations.get_google_creds', return_value=mock_creds)

    mock_events_list_result = {'items': [{'summary': 'Event 1'}, {'summary': 'Event 2'}]}
    mock_service = MagicMock()
    mock_service.events.return_value.list.return_value.execute.return_value = mock_events_list_result
    # Corrected: Patch googleapiclient.discovery.build where it's used in api_integrations
    mocker.patch('api_integrations.build', return_value=mock_service)

    # Mock datetime.datetime.now(UTC) for consistent timeMin
    mock_datetime_now = mocker.patch('api_integrations.datetime')
    # Set the return value for datetime.now() specifically, without microseconds
    mock_datetime_now.now.return_value = datetime(2025, 7, 27, 10, 0, 0, tzinfo=UTC) 
    # Ensure that other datetime operations (like timedelta) still work by having a side_effect
    mock_datetime_now.side_effect = lambda *args, **kw: datetime(*args, **kw)


    # 2. Execution
    events = api_integrations.get_upcoming_calendar_events(count=2)

    # 3. Assertions
    assert events == mock_events_list_result['items']
    api_integrations.get_google_creds.assert_called_once()
    api_integrations.build.assert_called_once_with('calendar', 'v3', credentials=mock_creds)
    # Corrected: The timeMin string should NOT include microseconds, as the mocked datetime has 0.
    mock_service.events().list.assert_called_once_with(
        calendarId='primary', timeMin="2025-07-27T10:00:00+00:00", maxResults=2, singleEvents=True, orderBy='startTime'
    )

def test_get_upcoming_calendar_events_no_creds(app_context, mocker):
    """
    Test fetching calendar events when no Google credentials are available.
    """
    # 1. Setup
    mocker.patch('api_integrations.get_google_creds', return_value=None)
    # Corrected: Patch googleapiclient.discovery.build where it's used in api_integrations
    mock_build = mocker.patch('api_integrations.build') # Store the mock object

    # 2. Execution
    events = api_integrations.get_upcoming_calendar_events()

    # 3. Assertions
    assert events == []
    api_integrations.get_google_creds.assert_called_once()
    mock_build.assert_not_called() # Corrected: Assert on the mock object

def test_get_upcoming_calendar_events_api_error(app_context, mocker):
    """
    Test fetching calendar events when the Google Calendar API call fails.
    """
    # 1. Setup
    mock_creds = MagicMock()
    mock_creds.valid = True
    mocker.patch('api_integrations.get_google_creds', return_value=mock_creds)

    mock_service = MagicMock()
    mock_service.events.return_value.list.return_value.execute.side_effect = Exception("API error")
    # Corrected: Patch googleapiclient.discovery.build where it's used in api_integrations
    mocker.patch('api_integrations.build', return_value=mock_service)

    # Mock datetime.now(UTC)
    mocker.patch('api_integrations.datetime') # Patch the datetime module within api_integrations

    # 2. Execution
    events = api_integrations.get_upcoming_calendar_events()

    # 3. Assertions
    assert events == []
    api_integrations.get_google_creds.assert_called_once()
    api_integrations.build.assert_called_once() # Build should be called
    mock_service.events().list().execute.assert_called_once()

# --- Tests for get_recent_gmail_messages ---

def test_get_recent_gmail_messages_success(app_context, mocker):
    """
    Test successful fetching of recent Gmail messages.
    """
    # 1. Setup
    mock_creds = MagicMock()
    mock_creds.valid = True
    mocker.patch('api_integrations.get_google_creds', return_value=mock_creds)

    mock_messages_list_result = {'messages': [{'id': 'msg1_id', 'threadId': 'thrd1_id'}]}
    mock_message_get_result = {
        'id': 'msg1_id',
        'threadId': 'thrd1_id',
        'payload': {'headers': [
            {'name': 'From', 'value': 'Sender One <sender1@example.com>'},
            {'name': 'Subject', 'value': 'Subject One'}
        ]}
    }
    mock_service = MagicMock()
    mock_service.users.return_value.messages.return_value.list.return_value.execute.return_value = mock_messages_list_result
    mock_service.users.return_value.messages.return_value.get.return_value.execute.return_value = mock_message_get_result
    # Corrected: Patch googleapiclient.discovery.build where it's used in api_integrations
    mocker.patch('api_integrations.build', return_value=mock_service)

    # 2. Execution
    emails = api_integrations.get_recent_gmail_messages(count=1)

    # 3. Assertions
    expected_emails = [{'id': 'msg1_id', 'threadId': 'thrd1_id', 'subject': 'Subject One', 'sender': 'Sender One <sender1@example.com>'}]
    assert emails == expected_emails
    api_integrations.get_google_creds.assert_called_once()
    api_integrations.build.assert_called_once_with('gmail', 'v1', credentials=mock_creds)
    mock_service.users().messages().list.assert_called_once_with(userId='me', labelIds=['INBOX', 'UNREAD'], maxResults=1)
    mock_service.users().messages().get.assert_called_once_with(userId='me', id='msg1_id', format='metadata', metadataHeaders=['From', 'Subject'])


def test_get_recent_gmail_messages_no_creds(app_context, mocker):
    """
    Test fetching Gmail messages when no Google credentials are available.
    """
    mocker.patch('api_integrations.get_google_creds', return_value=None)
    # Corrected: Patch googleapiclient.discovery.build where it's used in api_integrations
    mock_build = mocker.patch('api_integrations.build')

    emails = api_integrations.get_recent_gmail_messages()

    assert emails == []
    api_integrations.get_google_creds.assert_called_once()
    mock_build.assert_not_called()


def test_get_recent_gmail_messages_api_error_list(app_context, mocker):
    """
    Test fetching Gmail messages when the list API call fails.
    """
    mock_creds = MagicMock()
    mock_creds.valid = True
    mocker.patch('api_integrations.get_google_creds', return_value=mock_creds)

    mock_service = MagicMock()
    mock_service.users.return_value.messages.return_value.list.return_value.execute.side_effect = Exception("List API error")
    # Corrected: Patch googleapiclient.discovery.build where it's used in api_integrations
    mocker.patch('api_integrations.build', return_value=mock_service)

    emails = api_integrations.get_recent_gmail_messages()

    assert emails == []
    api_integrations.get_google_creds.assert_called_once()
    api_integrations.build.assert_called_once()
    mock_service.users().messages().list().execute.assert_called_once()


def test_get_recent_gmail_messages_api_error_get_message(app_context, mocker):
    """
    Test fetching Gmail messages when getting individual message fails.
    """
    mock_creds = MagicMock()
    mock_creds.valid = True
    mocker.patch('api_integrations.get_google_creds', return_value=mock_creds)

    mock_messages_list_result = {'messages': [{'id': 'msg1_id', 'threadId': 'thrd1_id'}]}
    mock_service = MagicMock()
    mock_service.users.return_value.messages.return_value.list.return_value.execute.return_value = mock_messages_list_result
    mock_service.users.return_value.messages.return_value.get.return_value.execute.side_effect = Exception("Get message API error")
    # Corrected: Patch googleapiclient.discovery.build where it's used in api_integrations
    mocker.patch('api_integrations.build', return_value=mock_service)

    emails = api_integrations.get_recent_gmail_messages()

    assert emails == []
    api_integrations.get_google_creds.assert_called_once()
    api_integrations.build.assert_called_once()
    mock_service.users().messages().list().execute.assert_called_once()
    mock_service.users().messages().get.assert_called_once()


def test_get_recent_gmail_messages_missing_headers(app_context, mocker):
    """
    Test fetching Gmail messages when headers are missing.
    """
    mock_creds = MagicMock()
    mock_creds.valid = True
    mocker.patch('api_integrations.get_google_creds', return_value=mock_creds)

    mock_messages_list_result = {'messages': [{'id': 'msg1_id', 'threadId': 'thrd1_id'}]}
    mock_message_get_result = {
        'id': 'msg1_id',
        'threadId': 'thrd1_id',
        'payload': {'headers': [
            {'name': 'SomeOtherHeader', 'value': 'Value'} # Missing From and Subject
        ]}
    }
    mock_service = MagicMock()
    mock_service.users.return_value.messages.return_value.list.return_value.execute.return_value = mock_messages_list_result
    mock_service.users.return_value.messages.return_value.get.return_value.execute.return_value = mock_message_get_result
    # Corrected: Patch googleapiclient.discovery.build where it's used in api_integrations
    mocker.patch('api_integrations.build', return_value=mock_service)

    emails = api_integrations.get_recent_gmail_messages(count=1)

    expected_emails = [{'id': 'msg1_id', 'threadId': 'thrd1_id', 'subject': 'No Subject', 'sender': 'Unknown Sender'}]
    assert emails == expected_emails


# --- Tests for get_emails_for_contact ---

def test_get_emails_for_contact_success(app_context, mocker):
    """
    Test successful fetching of emails for a specific contact email address.
    """
    # 1. Setup
    mock_creds = MagicMock()
    mock_creds.valid = True
    mocker.patch('api_integrations.get_google_creds', return_value=mock_creds)

    mock_messages_list_result = {'messages': [{'id': 'msg1_id', 'threadId': 'thrd1_id'}]}
    mock_message_get_result = {
        'id': 'msg1_id',
        'threadId': 'thrd1_id',
        'payload': {'headers': [
            {'name': 'From', 'value': 'Contact Email <contact@example.com>'},
            {'name': 'Subject', 'value': 'Contact Subject'},
            {'name': 'Date', 'value': 'Sat, 27 Jul 2025 10:00:00 -0400'}
        ]}
    }
    mock_service = MagicMock()
    mock_service.users.return_value.messages.return_value.list.return_value.execute.return_value = mock_messages_list_result
    mock_service.users.return_value.messages.return_value.get.return_value.execute.return_value = mock_message_get_result
    # Corrected: Patch googleapiclient.discovery.build where it's used in api_integrations
    mocker.patch('api_integrations.build', return_value=mock_service)

    email_address = "test@example.com"

    # 2. Execution
    emails = api_integrations.get_emails_for_contact(email_address, count=1)

    # 3. Assertions
    expected_emails = [{'subject': 'Contact Subject', 'sender': 'Contact Email <contact@example.com>', 'date': 'Sat, 27 Jul 2025 10:00:00 -0400'}]
    assert emails == expected_emails
    api_integrations.get_google_creds.assert_called_once()
    api_integrations.build.assert_called_once_with('gmail', 'v1', credentials=mock_creds)
    mock_service.users().messages().list.assert_called_once_with(userId='me', q=f"from:{email_address} OR to:{email_address}", maxResults=1)
    mock_service.users().messages().get.assert_called_once_with(userId='me', id='msg1_id', format='metadata', metadataHeaders=['From', 'Subject', 'Date'])


def test_get_emails_for_contact_no_email_address(app_context, mocker):
    """
    Test fetching emails for contact when no email address is provided.
    """
    # Corrected: Patch get_google_creds and build directly as they are used in api_integrations
    mock_get_google_creds = mocker.patch('api_integrations.get_google_creds') 
    mock_build = mocker.patch('api_integrations.build') 

    emails = api_integrations.get_emails_for_contact(None)
    assert emails == []
    emails = api_integrations.get_emails_for_contact("")
    assert emails == []
    mock_get_google_creds.assert_not_called()
    mock_build.assert_not_called()


def test_get_emails_for_contact_no_creds(app_context, mocker):
    """
    Test fetching emails for contact when no Google credentials are available.
    """
    mocker.patch('api_integrations.get_google_creds', return_value=None)
    mock_build = mocker.patch('api_integrations.build')

    emails = api_integrations.get_emails_for_contact("test@example.com")

    assert emails == []
    api_integrations.get_google_creds.assert_called_once()
    mock_build.assert_not_called()


def test_get_emails_for_contact_api_error(app_context, mocker):
    """
    Test fetching emails for contact when the Gmail API call fails.
    """
    mock_creds = MagicMock()
    mock_creds.valid = True
    mocker.patch('api_integrations.get_google_creds', return_value=mock_creds)

    mock_service = MagicMock()
    mock_service.users.return_value.messages.return_value.list.return_value.execute.side_effect = Exception("API error")
    mocker.patch('api_integrations.build', return_value=mock_service)

    emails = api_integrations.get_emails_for_contact("test@example.com")

    assert emails == []
    api_integrations.get_google_creds.assert_called_once()
    api_integrations.build.assert_called_once()
    mock_service.users().messages().list().execute.assert_called_once()


# --- Tests for get_recent_openphone_texts ---

def test_get_recent_openphone_texts_success_messages(app_context, mocker):
    """
    Test successful fetching and processing of recent OpenPhone messages.
    """
    # 1. Setup
    app_context.config['OPENPHONE_API_KEY'] = 'op_api_key'
    app_context.config['OPENPHONE_PHONE_NUMBER_ID'] = 'op_phone_id'
    app_context.config['OPENPHONE_PHONE_NUMBER'] = '+15551234567' # Your OpenPhone number

    mock_contact_service_instance = MagicMock(spec=ContactService) # Mock the instance
    mock_contact = MagicMock()
    mock_contact.id = 101
    mock_contact.first_name = "John"
    mock_contact_service_instance.get_contact_by_phone.return_value = mock_contact
    # Patch the class itself, so when it's instantiated in api_integrations, it returns our mock instance
    mocker.patch('api_integrations.ContactService', return_value=mock_contact_service_instance)

    mock_convo_response = MagicMock()
    mock_convo_response.status_code = 200
    mock_convo_response.json.return_value = {
        'data': [{
            'id': 'convo_1',
            'lastActivityType': 'message',
            'lastActivityId': 'msg_1',
            'participants': ['+15551234567', '+1234567890'], # Your number and other participant
            'name': 'Test Contact'
        }]
    }

    mock_message_response = MagicMock()
    mock_message_response.status_code = 200
    mock_message_response.json.return_value = {'data': {'text': 'Hello from customer'}}

    # Patch requests.get globally, side_effect ensures different responses for different calls
    mocker.patch('requests.get', side_effect=[mock_convo_response, mock_message_response])

    # 2. Execution
    # No need to pass mock_contact_service here, as it's patched globally
    texts, error = api_integrations.get_recent_openphone_texts(mock_contact_service_instance, count=1)

    # 3. Assertions
    assert error is None
    assert len(texts) == 1
    assert texts[0]['contact_id'] == 101
    assert texts[0]['contact_name'] == 'Test Contact'
    assert texts[0]['contact_number'] == '+1234567890'
    assert texts[0]['latest_message_body'] == 'Hello from customer'
    
    # Verify requests.get calls
    requests.get.assert_has_calls([
        call(f"https://api.openphone.com/v1/conversations?phoneNumberId=op_phone_id&limit=1", headers={"Authorization": "op_api_key"}, verify=True, timeout=(5, 30)),
        call(f"https://api.openphone.com/v1/messages/msg_1", headers={"Authorization": "op_api_key"}, verify=True, timeout=(5, 30))
    ])
    mock_contact_service_instance.get_contact_by_phone.assert_called_once_with('+1234567890')


def test_get_recent_openphone_texts_success_calls(app_context, mocker):
    """
    Test successful fetching and processing of recent OpenPhone calls.
    """
    # 1. Setup
    app_context.config['OPENPHONE_API_KEY'] = 'op_api_key'
    app_context.config['OPENPHONE_PHONE_NUMBER_ID'] = 'op_phone_id'
    app_context.config['OPENPHONE_PHONE_NUMBER'] = '+15551234567' # Your OpenPhone number

    mock_contact_service_instance = MagicMock(spec=ContactService)
    mock_contact = MagicMock()
    mock_contact.id = 102
    mock_contact.first_name = "Jane"
    mock_contact_service_instance.get_contact_by_phone.return_value = mock_contact
    mocker.patch('api_integrations.ContactService', return_value=mock_contact_service_instance)

    mock_convo_response = MagicMock()
    mock_convo_response.status_code = 200
    mock_convo_response.json.return_value = {
        'data': [{
            'id': 'convo_2',
            'lastActivityType': 'call', # Last activity is a call
            'lastActivityId': 'call_1',
            'participants': ['+15551234567', '+19876543210'],
            'name': 'Call Contact'
        }]
    }

    mocker.patch('requests.get', return_value=mock_convo_response) # Only convo response needed

    # 2. Execution
    texts, error = api_integrations.get_recent_openphone_texts(mock_contact_service_instance, count=1)

    # 3. Assertions
    assert error is None
    assert len(texts) == 1
    assert texts[0]['contact_id'] == 102
    assert texts[0]['contact_name'] == 'Call Contact'
    assert texts[0]['contact_number'] == '+19876543210'
    assert texts[0]['latest_message_body'] == '[Last activity was a phone call]'
    
    requests.get.assert_called_once_with(f"https://api.openphone.com/v1/conversations?phoneNumberId=op_phone_id&limit=1", headers={"Authorization": "op_api_key"}, verify=True, timeout=(5, 30))
    mock_contact_service_instance.get_contact_by_phone.assert_called_once_with('+19876543210')


def test_get_recent_openphone_texts_missing_api_config(app_context, mocker):
    """
    Test fetching OpenPhone texts when API key or phone number ID is missing.
    """
    # 1. Setup
    app_context.config['OPENPHONE_API_KEY'] = None # Missing API key
    app_context.config['OPENPHONE_PHONE_NUMBER_ID'] = 'op_phone_id'

    mock_contact_service_instance = MagicMock(spec=ContactService)
    mocker.patch('api_integrations.ContactService', return_value=mock_contact_service_instance)
    mocker.patch('requests.get') # Ensure no requests are made

    # 2. Execution
    texts, error = api_integrations.get_recent_openphone_texts(mock_contact_service_instance)

    # 3. Assertions
    assert texts == []
    assert "OpenPhone API Key or Phone Number ID is not configured." in error
    requests.get.assert_not_called()


def test_get_recent_openphone_texts_conversations_api_error(app_context, mocker):
    """
    Test fetching OpenPhone texts when conversations API call fails.
    """
    # 1. Setup
    app_context.config['OPENPHONE_API_KEY'] = 'op_api_key'
    app_context.config['OPENPHONE_PHONE_NUMBER_ID'] = 'op_phone_id'

    mock_contact_service_instance = MagicMock(spec=ContactService)
    mocker.patch('api_integrations.ContactService', return_value=mock_contact_service_instance)

    mock_convo_response = MagicMock()
    mock_convo_response.status_code = 500
    mock_convo_response.raise_for_status.side_effect = requests.exceptions.HTTPError("500 Server Error")
    mocker.patch('requests.get', return_value=mock_convo_response)

    # 2. Execution
    texts, error = api_integrations.get_recent_openphone_texts(mock_contact_service_instance)

    # 3. Assertions
    assert texts == []
    assert "500 Server Error" in error
    requests.get.assert_called_once()


def test_get_recent_openphone_texts_message_fetch_error(app_context, mocker):
    """
    Test fetching OpenPhone texts when fetching individual message fails.
    """
    # 1. Setup
    app_context.config['OPENPHONE_API_KEY'] = 'op_api_key'
    app_context.config['OPENPHONE_PHONE_NUMBER_ID'] = 'op_phone_id'
    app_context.config['OPENPHONE_PHONE_NUMBER'] = '+15551234567'

    mock_contact_service_instance = MagicMock(spec=ContactService)
    mock_contact_service_instance.get_contact_by_phone.return_value = MagicMock(id=103, first_name="Test")
    mocker.patch('api_integrations.ContactService', return_value=mock_contact_service_instance)

    mock_convo_response = MagicMock()
    mock_convo_response.status_code = 200
    mock_convo_response.json.return_value = {
        'data': [{
            'id': 'convo_3',
            'lastActivityType': 'message',
            'lastActivityId': 'msg_3',
            'participants': ['+15551234567', '+10000000000'],
            'name': 'Error Message Contact'
        }]
    }

    mock_message_response = MagicMock()
    mock_message_response.status_code = 404
    mock_message_response.raise_for_status.side_effect = requests.exceptions.HTTPError("404 Not Found")
    mocker.patch('requests.get', side_effect=[mock_convo_response, mock_message_response])

    # 2. Execution
    texts, error = api_integrations.get_recent_openphone_texts(mock_contact_service_instance)

    # 3. Assertions
    assert error is None # The function handles message fetch error internally, not as a top-level error
    assert len(texts) == 1
    assert texts[0]['latest_message_body'] == '[Error fetching message: 404]'
    assert requests.get.call_count == 2 # Both conversation and message get should be called

def test_get_recent_openphone_texts_no_contact_found(app_context, mocker):
    """
    Test fetching OpenPhone texts when no matching contact is found in CRM.
    """
    # 1. Setup
    app_context.config['OPENPHONE_API_KEY'] = 'op_api_key'
    app_context.config['OPENPHONE_PHONE_NUMBER_ID'] = 'op_phone_id'
    app_context.config['OPENPHONE_PHONE_NUMBER'] = '+15551234567'

    mock_contact_service_instance = MagicMock(spec=ContactService)
    mock_contact_service_instance.get_contact_by_phone.return_value = None # Simulate no contact found
    mocker.patch('api_integrations.ContactService', return_value=mock_contact_service_instance)

    mock_convo_response = MagicMock()
    mock_convo_response.status_code = 200
    mock_convo_response.json.return_value = {
        'data': [{
            'id': 'convo_4',
            'lastActivityType': 'message',
            'lastActivityId': 'msg_4',
            'participants': ['+15551234567', '+11111111111'],
            'name': 'Unknown Contact'
        }]
    }

    mock_message_response = MagicMock()
    mock_message_response.status_code = 200
    mock_message_response.json.return_value = {'data': {'text': 'Message from unknown'}}
    mocker.patch('requests.get', side_effect=[mock_convo_response, mock_message_response])

    # 2. Execution
    texts, error = api_integrations.get_recent_openphone_texts(mock_contact_service_instance)

    # 3. Assertions
    assert error is None
    assert len(texts) == 1
    assert texts[0]['contact_id'] is None # Should be None
    assert texts[0]['contact_name'] == 'Unknown Contact' # Should use OpenPhone name
    assert texts[0]['contact_number'] == '+11111111111'
    assert texts[0]['latest_message_body'] == 'Message from unknown'
    mock_contact_service_instance.get_contact_by_phone.assert_called_once_with('+11111111111')


def test_get_recent_openphone_texts_empty_conversations(app_context, mocker):
    """
    Test fetching OpenPhone texts when OpenPhone returns no conversations.
    """
    # 1. Setup
    app_context.config['OPENPHONE_API_KEY'] = 'op_api_key'
    app_context.config['OPENPHONE_PHONE_NUMBER_ID'] = 'op_phone_id'

    mock_contact_service_instance = MagicMock(spec=ContactService)
    mocker.patch('api_integrations.ContactService', return_value=mock_contact_service_instance)

    mock_convo_response = MagicMock()
    mock_convo_response.status_code = 200
    mock_convo_response.json.return_value = {'data': []} # Empty conversations
    mocker.patch('requests.get', return_value=mock_convo_response)

    # 2. Execution
    texts, error = api_integrations.get_recent_openphone_texts(mock_contact_service_instance)

    # 3. Assertions
    assert error is None
    assert texts == []
    requests.get.assert_called_once() # Only conversation get should be called
    mock_contact_service_instance.get_contact_by_phone.assert_not_called()


# --- Tests for create_google_calendar_event ---

def test_create_google_calendar_event_success(app_context, mocker):
    """
    Test successful creation of a Google Calendar event.
    """
    # 1. Setup
    mock_creds = MagicMock()
    mock_creds.valid = True
    mocker.patch('api_integrations.get_google_creds', return_value=mock_creds)

    mock_created_event = {'id': 'event_id_123', 'htmlLink': 'http://event.link'}
    mock_service = MagicMock()
    mock_service.events.return_value.insert.return_value.execute.return_value = mock_created_event
    # Corrected: Patch googleapiclient.discovery.build where it's used in api_integrations
    mocker.patch('api_integrations.build', return_value=mock_service)

    title = "Test Event"
    description = "Event description."
    start_time = datetime(2025, 8, 1, 10, 0, 0, tzinfo=UTC)
    end_time = datetime(2025, 8, 1, 11, 0, 0, tzinfo=UTC)
    attendees = ["attendee@example.com"]
    location = "Test Location"

    # 2. Execution
    created_event = api_integrations.create_google_calendar_event(title, description, start_time, end_time, attendees, location)

    # 3. Assertions
    assert created_event == mock_created_event
    api_integrations.get_google_creds.assert_called_once()
    api_integrations.build.assert_called_once_with('calendar', 'v3', credentials=mock_creds)
    mock_service.events().insert.assert_called_once_with(
        calendarId='primary',
        body={
            'summary': title,
            'description': description,
            'start': {'dateTime': start_time.isoformat(), 'timeZone': 'America/New_York'},
            'end': {'dateTime': end_time.isoformat(), 'timeZone': 'America/New_York'},
            'attendees': [{'email': 'attendee@example.com'}],
            'location': location
        }
    )


def test_create_google_calendar_event_no_creds(app_context, mocker):
    """
    Test event creation when no Google credentials are available.
    """
    mocker.patch('api_integrations.get_google_creds', return_value=None)
    # Corrected: Patch googleapiclient.discovery.build where it's used in api_integrations
    mocker.patch('api_integrations.build')

    created_event = api_integrations.create_google_calendar_event("Title", "Desc", datetime.now(), datetime.now(), [])

    assert created_event is None
    api_integrations.get_google_creds.assert_called_once()
    api_integrations.build.assert_not_called()


def test_create_google_calendar_event_api_error(app_context, mocker):
    """
    Test event creation when Google Calendar API call fails.
    """
    mock_creds = MagicMock()
    mock_creds.valid = True
    mocker.patch('api_integrations.get_google_creds', return_value=mock_creds)

    mock_service = MagicMock()
    mock_service.events.return_value.insert.return_value.execute.side_effect = Exception("API error")
    # Corrected: Patch googleapiclient.discovery.build where it's used in api_integrations
    mocker.patch('api_integrations.build', return_value=mock_service)

    created_event = api_integrations.create_google_calendar_event("Title", "Desc", datetime.now(), datetime.now(), [])

    assert created_event is None
    api_integrations.get_google_creds.assert_called_once()
    api_integrations.build.assert_called_once()
    mock_service.events().insert().execute.assert_called_once()


# --- Tests for delete_google_calendar_event ---

def test_delete_google_calendar_event_success(app_context, mocker):
    """
    Test successful deletion of a Google Calendar event.
    """
    # 1. Setup
    mock_creds = MagicMock()
    mock_creds.valid = True
    mocker.patch('api_integrations.get_google_creds', return_value=mock_creds)

    mock_service = MagicMock()
    mock_service.events.return_value.delete.return_value.execute.return_value = None # Delete returns None on success
    # Corrected: Patch googleapiclient.discovery.build where it's used in api_integrations
    mocker.patch('api_integrations.build', return_value=mock_service)

    event_id = "event_to_delete_123"

    # 2. Execution
    result = api_integrations.delete_google_calendar_event(event_id)

    # 3. Assertions
    assert result is True
    api_integrations.get_google_creds.assert_called_once()
    api_integrations.build.assert_called_once_with('calendar', 'v3', credentials=mock_creds)
    mock_service.events().delete.assert_called_once_with(calendarId='primary', eventId=event_id)


def test_delete_google_calendar_event_no_creds(app_context, mocker):
    """
    Test event deletion when no Google credentials are available.
    """
    mocker.patch('api_integrations.get_google_creds', return_value=None)
    # Corrected: Patch googleapiclient.discovery.build where it's used in api_integrations
    mock_build = mocker.patch('api_integrations.build')

    result = api_integrations.delete_google_calendar_event("event_id")

    assert result is False
    api_integrations.get_google_creds.assert_called_once()
    mock_build.assert_not_called()


def test_delete_google_calendar_event_api_error(app_context, mocker):
    """
    Test event deletion when Google Calendar API call fails.
    """
    mock_creds = MagicMock()
    mock_creds.valid = True
    mocker.patch('api_integrations.get_google_creds', return_value=mock_creds)

    mock_service = MagicMock()
    mock_service.events.return_value.delete.return_value.execute.side_effect = Exception("API error")
    # Corrected: Patch googleapiclient.discovery.build where it's used in api_integrations
    mocker.patch('api_integrations.build', return_value=mock_service)

    result = api_integrations.delete_google_calendar_event("event_id")

    assert result is False
    api_integrations.get_google_creds.assert_called_once()
    api_integrations.build.assert_called_once()
    mock_service.events().delete().execute.assert_called_once()
