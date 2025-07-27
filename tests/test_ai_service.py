# tests/test_ai_service.py
"""
Tests for the AIService to ensure it correctly interacts with the Gemini API
and parses the responses for addresses, names, and summaries.
"""

import pytest
from services.ai_service import AIService
from unittest.mock import patch

def test_summarize_conversation_for_appointment(mocker):
    """
    GIVEN a list of message objects
    WHEN the summarize_conversation_for_appointment method is called
    THEN it should call the Gemini API with a correctly formatted prompt
         and return the text from the API's response.
    """
    # 1. Setup
    # Mock the external dependency (Gemini API)
    mock_generative_model = mocker.patch('google.generativeai.GenerativeModel').return_value
    mock_generative_model.generate_content.return_value.text = "This is a test summary."

    # We need an app context for the service to configure itself
    from app import create_app
    app = create_app({'TESTING': True, 'GEMINI_API_KEY': 'fake-key'})
    
    with app.app_context():
        ai_service = AIService()

        # Create mock message objects that look like our SQLAlchemy models
        class MockMessage:
            def __init__(self, direction, body):
                self.direction = direction
                self.body = body

        messages = [
            MockMessage(direction='inbound', body='Hi, I have a crack in my foundation.'),
            MockMessage(direction='outbound', body='We can help with that.')
        ]

        # 2. Execution
        summary = ai_service.summarize_conversation_for_appointment(messages)

        # 3. Assertion
        assert summary == "This is a test summary."
        # Verify that the API was called
        mock_generative_model.generate_content.assert_called_once()
        # You can even inspect the prompt that was sent
        prompt_sent = mock_generative_model.generate_content.call_args[0][0]
        assert "Hi, I have a crack in my foundation." in prompt_sent

# TODO: Add a test for extract_address_from_text
# TODO: Add a test for extract_name_from_text
# TODO: Add a test for handling API errors gracefully
