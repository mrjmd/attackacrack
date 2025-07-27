import pytest

def test_dashboard_route_with_mocking(client, mocker):
    """
    GIVEN a test client and the pytest mocker
    WHEN the dashboard route is requested
    THEN check that the page loads correctly with faked external data.
    
    This test now uses the 'client' fixture from conftest.py.
    """
    # We use mocker.patch to replace the real functions with mocks.
    mocker.patch('routes.main_routes.get_upcoming_calendar_events', return_value=[])
    mocker.patch('routes.main_routes.get_recent_gmail_messages', return_value=[])
    
    # We can also mock the database call if we want to isolate the route completely
    mocker.patch('services.message_service.MessageService.get_latest_conversations_from_db', return_value=[])

    # Now when we make this GET request, the real API and DB calls inside the
    # dashboard route will be intercepted by our mocks.
    response = client.get('/dashboard')

    assert response.status_code == 200
    assert b'<h2 class="text-3xl font-bold mb-6">Dashboard</h2>' in response.data
    # We can also check for sections that should be empty because of our mocks
    assert b"No upcoming appointments or events." in response.data
    assert b"No unread emails found." in response.data
    # Check that the JS variable for texts is an empty array
    assert b"const initialTexts = [];" in response.data