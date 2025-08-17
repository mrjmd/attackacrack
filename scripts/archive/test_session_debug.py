#!/usr/bin/env python3
"""
Debug Flask-Session configuration
"""
import requests
import json

def test_session_debug():
    base_url = "https://attackacrack-prod-5ce6f.ondigitalocean.app"
    
    print("Testing Flask-Session configuration...")
    print("=" * 60)
    
    # Create a session
    session = requests.Session()
    
    # Try to login (even with wrong credentials, should get a session)
    print("\n1. Attempting login...")
    response = session.post(
        f"{base_url}/auth/login",
        data={'email': 'test@example.com', 'password': 'wrongpassword'},
        allow_redirects=False
    )
    
    print(f"   Status: {response.status_code}")
    print(f"   Headers:")
    for key, value in response.headers.items():
        if 'cookie' in key.lower():
            print(f"     {key}: {value}")
    
    print(f"\n   Cookies in jar:")
    for cookie in session.cookies:
        print(f"     {cookie.name}: {cookie.value[:50] if len(cookie.value) > 50 else cookie.value}")
        print(f"       - Domain: {cookie.domain}")
        print(f"       - Path: {cookie.path}")
        print(f"       - Secure: {cookie.secure}")
        print(f"       - Expires: {cookie.expires}")
    
    # Try to access a page that requires auth
    print("\n2. Attempting to access dashboard...")
    response2 = session.get(f"{base_url}/", allow_redirects=False)
    print(f"   Status: {response2.status_code}")
    if response2.status_code == 302:
        print(f"   Redirecting to: {response2.headers.get('Location')}")
    
    # Check if session persists
    print("\n3. Making another request to check session persistence...")
    response3 = session.get(f"{base_url}/auth/login", allow_redirects=False)
    print(f"   Status: {response3.status_code}")
    
    print(f"\n   Final cookies in jar:")
    for cookie in session.cookies:
        print(f"     {cookie.name}: {cookie.value[:50] if len(cookie.value) > 50 else cookie.value}")

if __name__ == "__main__":
    test_session_debug()