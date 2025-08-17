import pytest
from flask import url_for

def test_dashboard_route_with_mocking(authenticated_client, mocker, app):
    """
    GIVEN a test client and the pytest mocker
    WHEN the dashboard route is requested
    THEN check that the page loads correctly with faked external data.
    
    This test now uses the 'client' fixture from conftest.py.
    """
    # We use mocker.patch to replace the real functions with mocks.
    # Mock external API calls
    mocker.patch('routes.main_routes.get_upcoming_calendar_events', return_value=[])
    mocker.patch('routes.main_routes.get_recent_gmail_messages', return_value=[])
    
    # Mock database calls that populate the dashboard
    # This is the crucial mock to ensure no internal appointments are found
    mocker.patch('services.appointment_service.AppointmentService.get_all_appointments', return_value=[])
    
    # Mock the database call for latest conversations
    mocker.patch('services.message_service.MessageService.get_latest_conversations_from_db', return_value=[])
    
    with app.test_request_context():
        response = authenticated_client.get(url_for('main.dashboard'))
    
    assert response.status_code == 200
    assert b'<h1 class="text-3xl font-bold text-white">Dashboard</h1>' in response.data
    
    # Check for the expected "no data" message for appointments.
    # With both internal appointments and Google events mocked to be empty,
    # this text should now correctly appear.
    assert b"No appointments scheduled for today." in response.data
