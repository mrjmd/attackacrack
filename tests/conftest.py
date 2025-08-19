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

# Import repository fixtures
from tests.fixtures.repository_fixtures import (
    repository_factory,
    mock_repositories,
    contact_repository,
    todo_repository,
    campaign_repository,
    activity_repository,
    conversation_repository
)

def create_test_contact(**kwargs):
    """
    Helper function to create test contacts with default values.
    Used across multiple test files.
    """
    defaults = {
        'first_name': 'Test',
        'last_name': 'User',
        'phone': '+15551234567',
        'email': None
    }
    defaults.update(kwargs)
    return Contact(**defaults)

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
    Uses nested transactions (savepoints) for proper isolation.
    """
    with app.app_context():
        # Start a database connection and transaction
        connection = db.engine.connect()
        transaction = connection.begin()
        
        # Configure the session to use this specific connection
        # This ensures all database operations in the test use the same transaction
        from sqlalchemy.orm import scoped_session, sessionmaker
        
        # Create a new session factory bound to our connection
        session_factory = sessionmaker(bind=connection)
        session = scoped_session(session_factory)
        
        # Save the original session to restore later
        old_session = db.session
        db.session = session
        
        # For SQLite, we need simpler transaction handling
        if 'sqlite' in str(db.engine.url):
            # SQLite has issues with nested transactions
            # We'll use a simpler approach: just flush instead of commit
            original_commit = session.commit
            
            def fake_commit():
                """Replace commit with flush to keep changes in transaction"""
                session.flush()
            
            session.commit = fake_commit
            nested = None  # No nested transactions for SQLite
        else:
            # For PostgreSQL and other databases with proper savepoint support
            nested = connection.begin_nested()
            
            # Listen for session events to restart savepoints after commits
            @db.event.listens_for(session, "after_transaction_end")
            def restart_savepoint(sess, trans):
                nonlocal nested
                if trans.nested and not trans._parent.nested:
                    # Application code committed/rolled back the savepoint
                    # Start a new savepoint to maintain isolation
                    if connection.in_transaction():
                        nested = connection.begin_nested()
        
        try:
            yield session
        finally:
            # Clean up: rollback all changes
            try:
                session.close()
            except Exception:
                pass  # Ignore close errors
            
            # Rollback the savepoint if it exists and is active
            if nested:
                try:
                    if nested.is_active:
                        nested.rollback()
                except Exception:
                    pass  # Ignore savepoint errors
            
            # Rollback the main transaction
            try:
                if transaction.is_active:
                    transaction.rollback()
            except Exception:
                pass  # Ignore rollback errors
            
            # Close the connection
            try:
                connection.close()
            except Exception:
                pass  # Ignore close errors
            
            # Restore the original session
            db.session = old_session
            
            # Clear the session registry
            try:
                session.remove()
            except Exception:
                pass  # Ignore removal errors

@pytest.fixture(autouse=True)
def clean_campaign_data(db_session):
    """
    Automatically clean up campaign-related data after each test.
    This ensures tests don't interfere with each other.
    Note: With proper transaction isolation, this cleanup is often unnecessary
    as all changes are rolled back automatically. This is kept for extra safety.
    """
    yield
    # Clean up after test - be selective about what we delete
    # This only runs if the test doesn't use transaction isolation
    from crm_database import Campaign, CampaignMembership, CampaignList, CampaignListMember, ContactFlag
    try:
        # Check if we need to clean up (only if not using transaction isolation)
        if db_session.get_bind().in_transaction():
            # We're in a transaction that will be rolled back, no need to clean
            return
            
        # Only delete campaign-specific data, not all activities/conversations
        db_session.query(ContactFlag).filter_by(flag_type='recently_texted').delete(synchronize_session=False)
        db_session.query(CampaignListMember).delete(synchronize_session=False)
        db_session.query(CampaignMembership).delete(synchronize_session=False)
        db_session.query(CampaignList).delete(synchronize_session=False)
        db_session.query(Campaign).delete(synchronize_session=False)
        db_session.commit()
    except Exception as e:
        # Silently ignore cleanup errors in transaction-isolated tests
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

# Re-export repository fixtures so they're available globally
__all__ = [
    'repository_factory',
    'mock_repositories', 
    'contact_repository',
    'todo_repository',
    'campaign_repository',
    'activity_repository',
    'conversation_repository'
]
