import pytest
from app import create_app
from extensions import db

@pytest.fixture
def client():
    """A test client for the app, similar to the one in contact routes test."""
    app = create_app(test_config={
        'TESTING': True,
        'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
        'WTF_CSRF_ENABLED': False
    })

    with app.test_client() as client:
        with app.app_context():
            db.create_all()
        yield client

def test_dashboard_route_with_mocking(client, mocker):
    """
    GIVEN a test client and the pytest mocker
    WHEN the dashboard route is requested
    THEN check that the page loads correctly with faked external data.
    """
    # We use mocker.patch to replace the real functions with mocks.
    # The string is the full path to the function from the test's perspective.
    # We tell the mock to return an empty list or a tuple with no error.
    mocker.patch('routes.main_routes.get_upcoming_calendar_events', return_value=[])
    mocker.patch('routes.main_routes.get_recent_gmail_messages', return_value=[])
    mocker.patch('routes.main_routes.get_recent_openphone_texts', return_value=([], None))

    # Now when we make this GET request, the real API calls inside the
    # dashboard route will be intercepted by our mocks.
    response = client.get('/dashboard')

    assert response.status_code == 200
    assert b'<h2 class="text-3xl font-bold mb-6">Dashboard</h2>' in response.data
    # We can also check for sections that should be empty because of our mocks
    assert b"No upcoming appointments or events." in response.data
    assert b"No unread emails found." in response.data