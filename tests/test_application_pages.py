import pytest
from app import create_app
from extensions import db
from crm_database import Contact, Property, Job, Quote, Invoice, Appointment
from datetime import date, time

@pytest.fixture
def client():
    app = create_app(test_config={
        'TESTING': True,
        'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
        'WTF_CSRF_ENABLED': False
    })

    with app.test_client() as client:
        with app.app_context():
            db.create_all()
            contact = Contact(id=1, first_name="Test", last_name="User", email="test@user.com", phone="123")
            prop = Property(id=1, address="123 Test St", contact=contact)
            job = Job(id=1, description="Test Job", property=prop)
            quote = Quote(id=1, amount=100.0, job=job)
            invoice = Invoice(id=1, amount=100.0, due_date=date(2025, 1, 1), job=job)
            appointment = Appointment(id=1, title="Test Appt", date=date(2025, 1, 1), time=time(12, 0), contact=contact)
            db.session.add_all([contact, prop, job, quote, invoice, appointment])
            db.session.commit()
        yield client

endpoints = [
    '/',
    '/dashboard',
    '/contacts/',
    '/contacts/add',
    '/contacts/1',
    '/properties/',
    '/properties/1',
    '/appointments/',
    '/appointments/1',
    '/jobs/',
    '/jobs/job/1',
    '/quotes/',
    '/quotes/quote/1',
    '/invoices/',
    # --- THIS IS THE FIX ---
    '/invoices/1',
    # --- END FIX ---
    '/settings',
]

@pytest.mark.parametrize("endpoint", endpoints)
def test_all_pages_load_ok(client, endpoint):
    """
    GIVEN a test client with a fully seeded database
    WHEN a GET request is made to each main page and detail page
    THEN check that the response is successful (200 OK or 302 Redirect).
    """
    response = client.get(endpoint)
    
    assert response.status_code in [200, 302], f"Page {endpoint} failed to load with status {response.status_code}."