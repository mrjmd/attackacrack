import pytest
# No need to import db or Contact, as fixtures handle setup.

def test_contact_list_page(authenticated_client):
    """
    Test that the contact list page loads and shows existing contacts.
    This test now uses the 'authenticated_client' fixture from conftest.py.
    """
    response = authenticated_client.get('/contacts/')
    assert response.status_code == 200
    assert b'<h1 class="text-3xl font-bold text-white">Contacts</h1>' in response.data
    # Check for the seeded contact from conftest.py
    assert b"Test User" in response.data

def test_add_contact_route(authenticated_client):
    """
    Test that submitting the 'add contact' form creates a new contact.
    This test also uses the 'authenticated_client' fixture from conftest.py.
    """
    # Make a POST request with the form data to the add route
    response = authenticated_client.post('/contacts/add', data={
        'first_name': 'Jane',
        'last_name': 'Doe',
        'email': 'jane.doe@example.com',
        'phone': '0987654321'
    }, follow_redirects=True) # follow_redirects is important

    # After a successful POST, the route should redirect to the contact list
    assert response.status_code == 200
    
    # Check that the new contact's name is now on the contact list page
    assert b"Jane" in response.data and b"Doe" in response.data
    assert b'<h1 class="text-3xl font-bold text-white">Contacts</h1>' in response.data