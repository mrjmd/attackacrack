import pytest
from app import create_app
from extensions import db
from crm_database import Contact

@pytest.fixture
def client():
    """A test client for the app."""
    app = create_app(test_config={
        'TESTING': True,
        'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
        'WTF_CSRF_ENABLED': False  # Disable CSRF security for testing forms
    })

    with app.test_client() as client:
        with app.app_context():
            db.create_all()
            # You can seed the database with initial data here if needed
            new_contact = Contact(first_name="Initial", last_name="Contact", email="initial@test.com", phone="999")
            db.session.add(new_contact)
            db.session.commit()
        yield client

def test_contact_list_page(client):
    """Test that the contact list page loads and shows existing contacts."""
    response = client.get('/contacts/')
    assert response.status_code == 200
    # --- THIS IS THE FIX ---
    assert b'<h2 class="text-3xl font-bold">Contacts</h2>' in response.data
    # --- END FIX ---
    assert b"Initial Contact" in response.data # Check for seeded contact

def test_add_contact_route(client):
    """Test that submitting the 'add contact' form creates a new contact."""
    # First, make a POST request with the form data to the add route
    response = client.post('/contacts/add', data={
        'first_name': 'Jane',
        'last_name': 'Doe',
        'email': 'jane.doe@example.com',
        'phone': '0987654321'
    }, follow_redirects=True) # follow_redirects=True is important to follow the redirect to the contact list

    # After a successful POST, the route should redirect to the contact list
    assert response.status_code == 200
    
    # Check that the new contact's name is now on the contact list page
    assert b"Jane Doe" in response.data
    # --- THIS IS THE FIX ---
    assert b'<h2 class="text-3xl font-bold">Contacts</h2>' in response.data
    # --- END FIX ---