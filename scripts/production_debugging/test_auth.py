#!/usr/bin/env python3
"""
Test authentication and environment variables in the deployed app
"""
import requests
from bs4 import BeautifulSoup

def test_auth():
    base_url = "https://attackacrack-prod-5ce6f.ondigitalocean.app"
    
    # Create session to maintain cookies
    session = requests.Session()
    
    # 1. Test if login page loads
    print("1. Testing login page...")
    response = session.get(f"{base_url}/auth/login")
    print(f"   Status: {response.status_code}")
    
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, 'html.parser')
        # Check for CSRF token or form
        form = soup.find('form')
        if form:
            print("   ✓ Login form found")
        else:
            print("   ✗ No login form found")
            
        # Check for flash messages
        flashes = soup.find_all(class_=['alert', 'flash', 'message'])
        if flashes:
            print(f"   Flash messages: {[f.text.strip() for f in flashes]}")
    
    # 2. Test session cookie
    print("\n2. Testing session management...")
    if 'attackacrack_session' in session.cookies:
        print(f"   ✓ Session cookie present: {session.cookies['attackacrack_session'][:20]}...")
    else:
        print("   ✗ No session cookie")
    
    # 3. Test authentication attempt
    print("\n3. Testing authentication...")
    login_data = {
        'email': 'test@example.com',
        'password': 'wrongpassword'
    }
    
    response = session.post(f"{base_url}/auth/login", data=login_data, allow_redirects=False)
    print(f"   Status: {response.status_code}")
    
    if response.status_code == 302:
        print(f"   Redirect to: {response.headers.get('Location')}")
    elif response.status_code == 200:
        # Parse for error messages
        soup = BeautifulSoup(response.text, 'html.parser')
        errors = soup.find_all(class_=['error', 'alert-danger', 'flash-error'])
        if errors:
            print(f"   Error messages: {[e.text.strip() for e in errors]}")
        else:
            print("   No error messages found (might be a problem)")
    
    # 4. Test Google OAuth endpoint
    print("\n4. Testing Google OAuth...")
    response = session.get(f"{base_url}/auth/google", allow_redirects=False)
    print(f"   Status: {response.status_code}")
    if response.status_code == 302:
        location = response.headers.get('Location', '')
        if 'accounts.google.com' in location:
            print("   ✓ Redirects to Google OAuth")
        else:
            print(f"   Redirect to: {location[:100]}...")
    
    # 5. Test health endpoint again to ensure app is responsive
    print("\n5. Testing health endpoint...")
    response = session.get(f"{base_url}/health")
    if response.status_code == 200:
        print(f"   ✓ Health check: {response.json()}")
    else:
        print(f"   ✗ Health check failed: {response.status_code}")

if __name__ == "__main__":
    test_auth()