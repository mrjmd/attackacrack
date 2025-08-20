# tests/test_message_service.py
"""
Tests for the MessageService, focusing on processing webhooks and retrieving
conversation data from the database.
"""

import pytest
from unittest.mock import Mock
from services.openphone_webhook_service_refactored import OpenPhoneWebhookServiceRefactored
from crm_database import Contact, Conversation, Activity
from datetime import datetime

def create_webhook_service_with_mocks():
    """Helper function to create service with mocked dependencies"""
    mock_activity_repo = Mock()
    mock_conversation_repo = Mock()
    mock_webhook_repo = Mock()
    mock_contact_service = Mock()
    mock_sms_metrics_service = Mock()
    
    service = OpenPhoneWebhookServiceRefactored(
        activity_repository=mock_activity_repo,
        conversation_repository=mock_conversation_repo,
        webhook_event_repository=mock_webhook_repo,
        contact_service=mock_contact_service,
        sms_metrics_service=mock_sms_metrics_service
    )
    
    return service

def test_process_incoming_message_webhook_new_contact(app, db_session):
    """
    GIVEN a webhook payload for a new message from an unknown phone number
    WHEN the webhook service processes the message
    THEN it should create a new Contact, a new Conversation, and a new Activity record.
    """
    with app.app_context():
        # 1. Setup - Use real repositories for integration test
        activity_repo = app.services.get('activity_repository')
        conversation_repo = app.services.get('conversation_repository')
        webhook_repo = app.services.get('webhook_event_repository')
        contact_service = app.services.get('contact')
        sms_metrics_service = app.services.get('sms_metrics')
        
        webhook_service = OpenPhoneWebhookServiceRefactored(
            activity_repository=activity_repo,
            conversation_repository=conversation_repo,
            webhook_event_repository=webhook_repo,
            contact_service=contact_service,
            sms_metrics_service=sms_metrics_service
        )
        
        webhook_data = {
            "type": "message.received",  # Updated to actual webhook type
            "data": {
                "object": {
                    "id": "msg_new_contact_123",
                    "conversationId": "convo_new_contact_456",
                    "direction": "incoming",
                    "from": "+15559876543",
                    "text": "Hi, I'm a new customer.",  # Updated field name
                    "media": []  # Add media field
                }
            }
        }

        # 2. Execution
        result = webhook_service.process_webhook(webhook_data)

        # 3. Assertions
        # Check that webhook processing succeeded
        assert result.is_success
        assert 'activity_id' in result.data

        # Get the created activity
        activity_id = result.data['activity_id']
        new_activity = db_session.query(Activity).get(activity_id)
        assert new_activity is not None
        assert new_activity.openphone_id == "msg_new_contact_123"
        assert new_activity.body == "Hi, I'm a new customer."

        # Check that a new contact was created
        new_contact = db_session.query(Contact).filter_by(phone="+15559876543").one_or_none()
        assert new_contact is not None
        assert new_contact.first_name == "+15559876543"  # Defaults to phone number

        # Check that a conversation was created and linked
        assert new_activity.conversation_id is not None
        assert new_activity.conversation.contact_id == new_contact.id

# TODO: Add a test for an incoming message from an existing contact.
# TODO: Add a test for get_latest_conversations_from_db to ensure it returns data in the correct order.
# TODO: Add a test to ensure webhooks with outbound messages are ignored.
