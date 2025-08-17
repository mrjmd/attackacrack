#!/usr/bin/env python3
"""
Test if sessions are properly maintained across requests
"""
import requests

def test_real_session():
    base_url = "https://attackacrack-prod-5ce6f.ondigitalocean.app"
    
    print("Testing session persistence with multiple requests...")
    print("=" * 60)
    
    # Create a session
    session = requests.Session()
    
    # Make multiple requests to see if we get the same worker
    results = []
    for i in range(10):
        # Just access the login page - this should create/maintain a session
        response = session.get(f"{base_url}/auth/login", allow_redirects=False)
        
        # Check cookies
        has_session = any(c.name == 'attackacrack_session' for c in session.cookies)
        
        results.append({
            'attempt': i+1,
            'status': response.status_code,
            'has_session': has_session,
            'cookie_count': len(session.cookies)
        })
        
        print(f"Attempt {i+1}: Status={response.status_code}, Session={'YES' if has_session else 'NO'}, Cookies={len(session.cookies)}")
    
    # Count how many times we got a session
    session_count = sum(1 for r in results if r['has_session'])
    
    print("=" * 60)
    print(f"Results: {session_count}/10 requests had session cookies")
    
    if session_count == 0:
        print("❌ No sessions are being created")
    elif session_count < 10:
        print("⚠️  Inconsistent session behavior")
    else:
        print("✅ Sessions are working correctly!")

if __name__ == "__main__":
    test_real_session()