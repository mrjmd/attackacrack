import pytest
from services.ai_service import AIService
from crm_database import Activity, Conversation
from datetime import datetime

# No need to import create_app here, use the 'app' fixture

def test_summarize_conversation_for_appointment(mocker, app):
    """
    GIVEN a list of activity (message) objects
    WHEN the summarize_conversation_for_appointment method is called
    THEN it should call the Gemini API with a correctly formatted prompt
         and return the text from the API's response.
    """
    # 1. Setup
    # Mock the external dependency (Gemini API)
    mock_generative_model = mocker.patch('google.generativeai.GenerativeModel').return_value
    mock_generative_model.generate_content.return_value.text = "This is a test summary."

    # Use the 'app' fixture to get an application context
    with app.app_context():
        ai_service = AIService()

        # Create dummy conversation and activity objects for the test
        # Note: In a real test, if these models rely on db.Model,
        # you might need to add them to the session and commit for them to have an ID.
        # For this unit test focusing on the AI service, creating instances directly is often sufficient
        # as long as the service doesn't try to query them from the DB by ID.
        conversation = Conversation(
            openphone_id="test_convo_id",
            contact_id=1, # Assuming contact_id 1 exists for testing due to conftest.py seeding
            participants="111-222-3333, 444-555-6666",
            last_activity_at=datetime.utcnow()
        )
        
        # Now create Activity objects instead of Message objects
        activities = [
            Activity(
                conversation_id=conversation.id, # This will be None until conversation is committed and has an ID
                openphone_id="msg1",
                created_at=datetime.now(),
                direction="in",
                type="message",
                body="Hello, I have a crack in my foundation.",
                # Removed 'media_url' as it's not a direct column on Activity
            ),
            Activity(
                conversation_id=conversation.id, # This will be None until conversation is committed and has an ID
                openphone_id="msg2",
                created_at=datetime.now(),
                direction="out",
                type="message",
                body="Can you send a picture?",
                # Removed 'media_url' as it's not a direct column on Activity
            )
        ]

        # To properly associate activities with a conversation for the test,
        # you might need to add them to the session and commit the conversation first
        # to get its ID, then assign that ID to the activities.
        # However, for a unit test mocking the AI service, if the service only
        # iterates over the provided list of `activities` and doesn't query the DB,
        # this might not be strictly necessary.
        # If the AI service needs a valid conversation_id on the activities,
        # you would do something like:
        # db.session.add(conversation)
        # db.session.commit()
        # for activity in activities:
        #     activity.conversation_id = conversation.id

        # 2. Execution
        # Ensure the AI service can handle the list of Activity objects
        summary = ai_service.summarize_conversation_for_appointment(activities)

        # 3. Assertion
        # Verify that generate_content was called
        mock_generative_model.generate_content.assert_called_once()
        # Verify the returned summary
        assert summary == "This is a test summary."

        # You can add more specific assertions about the prompt content if needed
        # For example:
        # call_args = mock_generative_model.generate_content.call_args[0][0]
        # assert "crack in my foundation" in call_args
