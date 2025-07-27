# tests/test_message_service.py
"""
Tests for the MessageService, focusing on processing webhooks and retrieving
conversation data from the database.
"""

import pytest
from services.message_service import MessageService
from crm_database import Contact, Conversation, Activity
from datetime import datetime

def test_process_incoming_message_webhook_new_contact(app, db_session):
    """
    GIVEN a webhook payload for a new message from an unknown phone number
    WHEN the process_incoming_webhook method is called
    THEN it should create a new Contact, a new Conversation, and a new Activity record.
    """
    # 1. Setup
    message_service = MessageService()
    webhook_data = {
        "type": "message.new",
        "data": {
            "object": {
                "id": "msg_new_contact_123",
                "conversationId": "convo_new_contact_456",
                "direction": "incoming",
                "from": "+15559876543",
                "body": "Hi, I'm a new customer."
            }
        }
    }

    # 2. Execution
    new_activity = message_service.process_incoming_webhook(webhook_data)

    # 3. Assertions
    # Check that an activity was created
    assert new_activity is not None
    assert new_activity.openphone_id == "msg_new_contact_123"
    assert new_activity.body == "Hi, I'm a new customer."

    # Check that a new contact was created
    new_contact = db_session.query(Contact).filter_by(phone="+15559876543").one_or_none()
    assert new_contact is not None
    assert new_contact.first_name == "+15559876543" # Defaults to phone number

    # Check that a conversation was created and linked
    assert new_activity.conversation_id is not None
    assert new_activity.conversation.contact_id == new_contact.id

# TODO: Add a test for an incoming message from an existing contact.
# TODO: Add a test for get_latest_conversations_from_db to ensure it returns data in the correct order.
# TODO: Add a test to ensure webhooks with outbound messages are ignored.
