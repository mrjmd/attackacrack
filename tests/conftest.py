# tests/conftest.py
"""
This file contains shared fixtures for the pytest test suite.
Fixtures defined here are automatically available to all tests.
"""
import pytest
from app import create_app
from extensions import db
from crm_database import Contact, Property, Job, Quote, Invoice, Appointment, Setting, InviteToken
from datetime import date, time
from unittest.mock import MagicMock # Import MagicMock

@pytest.fixture(scope='module')
def app():
    """
    A fixture that creates a new Flask application instance for a test module.
    This ensures that tests within a module run against a clean, consistent
    application and database state.
    """
    # Create a new app instance with testing configuration
    app = create_app(config_name='testing', test_config={
        'SERVER_NAME': 'localhost.localdomain' # Required for url_for in tests
    })

    # The 'with app.app_context()' block makes the application context available,
    # which is necessary for database operations.
    with app.app_context():
        # Create all database tables based on the models
        db.create_all()
        
        # --- Seeding the database with test data ---
        # This provides consistent data for tests to run against.
        contact = Contact(id=1, first_name="Test", last_name="User", email="test@user.com", phone="+15551234567")
        prop = Property(id=1, address="123 Test St", contact=contact)
        job = Job(id=1, description="Test Job", property=prop, status='Active')
        quote = Quote(id=1, subtotal=100.0, tax_amount=0.0, total_amount=100.0, job=job, status='Sent')
        invoice = Invoice(id=1, subtotal=100.0, tax_amount=0.0, total_amount=100.0, due_date=date(2025, 1, 1), job=job, status='Unpaid')
        appointment = Appointment(id=1, title="Test Appt", date=date(2025, 1, 1), time=time(12, 0), contact=contact, job_id=job.id) # Use job_id
        
        # Seed common settings templates here
        reminder_template = Setting(key='appointment_reminder_template', value='Hi {first_name}, reminder for {appointment_date} at {appointment_time}.')
        review_template = Setting(key='review_request_template', value='Hi {first_name}, please leave a review!')
        
        # Create test user for authentication
        from crm_database import User
        from flask_bcrypt import generate_password_hash
        test_user = User(
            email='test@example.com',
            password_hash=generate_password_hash('testpassword').decode('utf-8'),
            first_name='Test',
            last_name='User',
            role='admin',
            is_active=True
        )
        
        # Add all the created objects to the database session
        db.session.add_all([contact, prop, job, quote, invoice, appointment, reminder_template, review_template, test_user])
        
        # Commit the changes to the database
        db.session.commit()

        # 'yield' passes the app object to the test function
        yield app

        # --- Teardown ---
        # After the tests in the module have run, this code will execute.
        db.session.close()
        db.drop_all()

@pytest.fixture(scope='module')
def client(app):
    """
    A fixture that provides a test client for the Flask application.
    This client can be used to make requests to the application's endpoints.
    It depends on the 'app' fixture.
    """
    return app.test_client()

@pytest.fixture(scope='function')
def authenticated_client(app, client):
    """
    A fixture that provides an authenticated test client.
    Logs in the test user before each test.
    """
    with app.app_context():
        # Login the test user
        response = client.post('/auth/login', data={
            'email': 'test@example.com',
            'password': 'testpassword'
        }, follow_redirects=True)
        
        yield client
        
        # Logout after test
        client.get('/auth/logout')

@pytest.fixture(scope='function')
def db_session(app):
    """
    A fixture that provides a clean database session for each test function.
    This ensures that tests are isolated from each other by rolling back any changes.
    """
    with app.app_context():
        # For SQLite (used in CI), we need different transaction handling
        if 'sqlite' in str(db.engine.url):
            # SQLite doesn't support nested transactions well
            # Just use the session directly and clean up after
            yield db.session
            db.session.rollback()
            db.session.remove()
        else:
            # For PostgreSQL, use nested transactions
            connection = db.engine.connect()
            transaction = connection.begin()
            
            # Configure session to use this connection
            session = db.session
            session.configure(bind=connection)
            
            yield session
            
            # Rollback the transaction to ensure clean state
            session.close()
            transaction.rollback()
            connection.close()

@pytest.fixture(autouse=True)
def clean_campaign_data(db_session):
    """
    Automatically clean up campaign-related data after each test.
    This ensures tests don't interfere with each other.
    """
    yield
    # Clean up after test - be selective about what we delete
    from crm_database import Campaign, CampaignMembership, CampaignList, CampaignListMember, ContactFlag
    try:
        # Only delete campaign-specific data, not all activities/conversations
        db_session.query(ContactFlag).filter_by(flag_type='recently_texted').delete()
        db_session.query(CampaignListMember).delete()
        db_session.query(CampaignMembership).delete()
        db_session.query(CampaignList).delete()
        db_session.query(Campaign).delete()
        db_session.commit()
    except Exception as e:
        print(f"Error cleaning campaign data: {e}")
        db_session.rollback()

# ADDED THIS FIXTURE: To globally mock get_google_creds for application_pages tests
@pytest.fixture(autouse=True)
def mock_get_google_creds_globally(mocker):
    """
    Globally mocks api_integrations.get_google_creds to prevent actual Google API calls
    and token.pickle issues in application_pages tests.
    """
    mock_creds = MagicMock()
    mock_creds.valid = True
    mocker.patch('api_integrations.get_google_creds', return_value=mock_creds)
