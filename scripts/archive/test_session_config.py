#!/usr/bin/env python3
"""
Test if Flask-Session is properly configured in production
"""
import requests
import time

def test_session_persistence():
    base_url = "https://attackacrack-prod-5ce6f.ondigitalocean.app"
    
    print("Testing session persistence across multiple requests...")
    print("=" * 60)
    
    # Test 10 login attempts to see the pattern
    success_count = 0
    for i in range(10):
        session = requests.Session()
        
        # Attempt login
        login_data = {
            'email': 'test@example.com',
            'password': 'wrongpassword'
        }
        
        response = session.post(f"{base_url}/auth/login", data=login_data, allow_redirects=False)
        
        # Check if we got a session cookie
        has_cookie = 'attackacrack_session' in session.cookies
        
        print(f"Attempt {i+1}: Status={response.status_code}, Cookie={'YES' if has_cookie else 'NO'}")
        
        if has_cookie:
            # Try to access a protected page with the same session
            response2 = session.get(f"{base_url}/", allow_redirects=False)
            if response2.status_code != 302 or '/auth/login' not in response2.headers.get('Location', ''):
                success_count += 1
                print(f"  -> Session persisted! (Success #{success_count})")
            else:
                print(f"  -> Session lost on second request")
        
        time.sleep(0.5)  # Small delay between attempts
    
    print("=" * 60)
    print(f"Results: {success_count}/10 sessions persisted")
    print(f"Pattern suggests {'SINGLE' if success_count > 7 else 'MULTIPLE'} worker(s)")
    
    if success_count < 3:
        print("\n⚠️  Sessions are NOT being shared between workers!")
        print("Flask-Session may not be properly configured.")
    elif success_count < 7:
        print("\n⚠️  Intermittent session persistence detected!")
        print("This matches the 1-in-4 pattern of 4 workers with local sessions.")
    else:
        print("\n✅ Sessions appear to be properly shared!")

if __name__ == "__main__":
    test_session_persistence()