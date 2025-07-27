# tests/conftest.py
"""
This file contains shared fixtures for the pytest test suite.
Fixtures defined here are automatically available to all tests.
"""
import pytest
from app import create_app
from extensions import db
from crm_database import Contact, Property, Job, Quote, Invoice, Appointment
from datetime import date, time

@pytest.fixture(scope='module')
def app():
    """
    A fixture that creates a new Flask application instance for a test module.
    This ensures that tests within a module run against a clean, consistent
    application and database state.
    """
    # Create a new app instance with a test-specific configuration
    app = create_app(test_config={
        'TESTING': True,
        'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:', # Use an in-memory SQLite database for tests
        'SQLALCHEMY_TRACK_MODIFICATIONS': False,
        'WTF_CSRF_ENABLED': False, # Disable CSRF for easier form testing
        'SERVER_NAME': 'localhost.localdomain' # ADDED THIS LINE: Required for url_for in tests
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
        quote = Quote(id=1, amount=100.0, job=job, status='Sent')
        invoice = Invoice(id=1, amount=100.0, due_date=date(2025, 1, 1), job=job, status='Unpaid')
        appointment = Appointment(id=1, title="Test Appt", date=date(2025, 1, 1), time=time(12, 0), contact=contact)
        
        # Add all the created objects to the database session
        db.session.add_all([contact, prop, job, quote, invoice, appointment])
        
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
def db_session(app):
    """
    A fixture that provides a clean database session for each test function.
    This ensures that tests are isolated from each other.
    """
    with app.app_context():
        yield db.session
        db.session.rollback() # Rollback any changes after each test
