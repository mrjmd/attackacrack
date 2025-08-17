#!/usr/bin/env python3
"""
Diagnostic script to test Redis connection and SSL configuration
"""
import os
import sys
import ssl
import redis
from urllib.parse import urlparse
import socket

def test_redis_connection():
    """Test Redis connection with detailed debugging"""
    redis_url = os.environ.get('REDIS_URL', '')
    
    print(f"Redis URL: {redis_url}")
    print(f"URL starts with rediss://: {redis_url.startswith('rediss://')}")
    
    if not redis_url:
        print("ERROR: REDIS_URL environment variable not set")
        return False
    
    # Parse the URL
    parsed = urlparse(redis_url)
    print(f"\nParsed URL:")
    print(f"  Scheme: {parsed.scheme}")
    print(f"  Host: {parsed.hostname}")
    print(f"  Port: {parsed.port}")
    print(f"  Path: {parsed.path}")
    
    # First, test basic network connectivity
    print(f"\nTesting network connectivity to {parsed.hostname}:{parsed.port}...")
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex((parsed.hostname, parsed.port or 6379))
        sock.close()
        
        if result == 0:
            print("✓ Network connection successful")
        else:
            print(f"✗ Network connection failed with error code: {result}")
            return False
    except Exception as e:
        print(f"✗ Network connection failed: {e}")
        return False
    
    # Now test Redis connection
    print("\nTesting Redis connection...")
    
    try:
        if redis_url.startswith('rediss://'):
            # SSL connection
            print("Using SSL connection...")
            
            # Add SSL parameters to URL if not present
            if 'ssl_cert_reqs' not in redis_url:
                separator = '&' if '?' in redis_url else '?'
                redis_url_with_ssl = redis_url + f"{separator}ssl_cert_reqs=CERT_NONE"
            else:
                redis_url_with_ssl = redis_url
            
            print(f"Connection URL: {redis_url_with_ssl}")
            
            # Create connection with explicit SSL settings
            r = redis.from_url(
                redis_url_with_ssl,
                socket_connect_timeout=10,
                socket_timeout=10,
                ssl_cert_reqs=ssl.CERT_NONE,
                ssl_check_hostname=False,
                decode_responses=True
            )
        else:
            # Non-SSL connection
            print("Using non-SSL connection...")
            r = redis.from_url(
                redis_url,
                socket_connect_timeout=10,
                socket_timeout=10,
                decode_responses=True
            )
        
        # Test the connection
        print("\nPinging Redis...")
        response = r.ping()
        print(f"✓ Ping response: {response}")
        
        # Test setting and getting a value
        print("\nTesting set/get operations...")
        test_key = "diagnostic_test_key"
        test_value = "diagnostic_test_value"
        
        r.set(test_key, test_value, ex=60)  # Expire after 60 seconds
        retrieved = r.get(test_key)
        
        if retrieved == test_value:
            print(f"✓ Set/Get successful: {retrieved}")
        else:
            print(f"✗ Set/Get failed. Expected: {test_value}, Got: {retrieved}")
        
        # Get Redis info
        print("\nRedis server info:")
        info = r.info('server')
        print(f"  Version: {info.get('redis_version', 'Unknown')}")
        print(f"  Mode: {info.get('redis_mode', 'Unknown')}")
        
        return True
        
    except redis.exceptions.TimeoutError as e:
        print(f"✗ Redis connection timeout: {e}")
        print("\nPossible causes:")
        print("- Firewall blocking the connection")
        print("- Wrong host/port")
        print("- Redis server not running")
        print("- Network issues")
        return False
    except redis.exceptions.ConnectionError as e:
        print(f"✗ Redis connection error: {e}")
        print("\nPossible causes:")
        print("- SSL certificate issues")
        print("- Authentication required but not provided")
        print("- Wrong protocol (redis:// vs rediss://)")
        return False
    except Exception as e:
        print(f"✗ Unexpected error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_celery_connection():
    """Test Celery connection"""
    print("\n" + "="*50)
    print("Testing Celery connection...")
    
    try:
        from celery_config import create_celery_app
        
        celery = create_celery_app('diagnostic')
        
        # Try to inspect the broker
        print("\nInspecting Celery broker...")
        inspect = celery.control.inspect()
        
        # This will timeout if broker is not accessible
        stats = inspect.stats()
        
        if stats:
            print("✓ Celery broker is accessible")
            print(f"  Active workers: {list(stats.keys())}")
        else:
            print("✗ No Celery workers found (broker might be accessible but no workers running)")
        
        return True
        
    except Exception as e:
        print(f"✗ Celery connection failed: {type(e).__name__}: {e}")
        return False

if __name__ == "__main__":
    print("Redis Connection Diagnostic Tool")
    print("="*50)
    
    # Test Redis first
    redis_ok = test_redis_connection()
    
    # Only test Celery if Redis is working
    if redis_ok:
        celery_ok = test_celery_connection()
    else:
        print("\nSkipping Celery test since Redis connection failed")
        celery_ok = False
    
    print("\n" + "="*50)
    print("Summary:")
    print(f"  Redis connection: {'✓ OK' if redis_ok else '✗ FAILED'}")
    print(f"  Celery connection: {'✓ OK' if celery_ok else '✗ FAILED' if redis_ok else '⚠ SKIPPED'}")
    
    sys.exit(0 if redis_ok else 1)