import pytest

# A list of all major endpoints that should load without errors.
# This acts as a simple smoke test for all pages.
endpoints = [
    '/',
    '/dashboard',
    '/contacts/',
    '/contacts/add',
    '/contacts/1', # Detail page for seeded contact
    '/contacts/conversations',
    '/contacts/1/conversation',
    '/properties/',
    '/properties/add',
    '/properties/1', # Detail page for seeded property
    '/appointments/',
    '/appointments/add',
    '/appointments/1', # Detail page for seeded appointment
    '/jobs/',
    '/jobs/job/add',
    '/jobs/job/1', # Detail page for seeded job
    '/quotes/',
    '/quotes/quote/add',
    '/quotes/quote/1', # Detail page for seeded quote
    '/invoices/',
    '/invoices/add',
    '/invoices/1', # Detail page for seeded invoice
    '/settings',
    '/settings/automation',
    '/import_csv',
    '/import_property_radar'
]

@pytest.mark.parametrize("endpoint", endpoints)
def test_all_pages_load_ok(client, endpoint):
    """
    GIVEN a test client with a fully seeded database
    WHEN a GET request is made to each main page and detail page
    THEN check that the response is successful (200 OK or 302 Redirect).
    
    This test uses the 'client' fixture from conftest.py.
    """
    response = client.get(endpoint)
    
    # A 302 status code (redirect) is also considered a success for root URLs.
    assert response.status_code in [200, 302], f"Page {endpoint} failed to load with status {response.status_code}."