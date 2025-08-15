#!/usr/bin/env python3
"""Test Redis/Valkey connectivity from the production environment"""
import os
import sys
import ssl
import redis
from urllib.parse import urlparse
import socket
import time

def test_redis_connection():
    redis_url = os.environ.get('REDIS_URL') or os.environ.get('CELERY_BROKER_URL')
    
    print(f"Testing Redis connection to: {redis_url}")
    print(f"Environment variables:")
    print(f"  REDIS_URL: {os.environ.get('REDIS_URL')}")
    print(f"  CELERY_BROKER_URL: {os.environ.get('CELERY_BROKER_URL')}")
    print(f"  CELERY_RESULT_BACKEND: {os.environ.get('CELERY_RESULT_BACKEND')}")
    
    if not redis_url:
        print("ERROR: No Redis URL found in environment variables")
        return False
    
    # Parse the URL
    parsed = urlparse(redis_url)
    print(f"\nParsed URL:")
    print(f"  Scheme: {parsed.scheme}")
    print(f"  Host: {parsed.hostname}")
    print(f"  Port: {parsed.port}")
    print(f"  Password: {'***' if parsed.password else 'None'}")
    
    # Test DNS resolution
    print(f"\nTesting DNS resolution for {parsed.hostname}...")
    try:
        ip = socket.gethostbyname(parsed.hostname)
        print(f"  Resolved to: {ip}")
    except socket.gaierror as e:
        print(f"  DNS resolution failed: {e}")
        return False
    
    # Test basic socket connectivity
    print(f"\nTesting socket connectivity to {parsed.hostname}:{parsed.port}...")
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(10)
    try:
        start_time = time.time()
        result = sock.connect_ex((parsed.hostname, parsed.port))
        connect_time = time.time() - start_time
        if result == 0:
            print(f"  Socket connection successful (took {connect_time:.2f}s)")
        else:
            print(f"  Socket connection failed with error code: {result}")
            return False
    except Exception as e:
        print(f"  Socket connection failed: {e}")
        return False
    finally:
        sock.close()
    
    # Test Redis connection
    print(f"\nTesting Redis connection...")
    try:
        if redis_url.startswith('rediss://'):
            # SSL connection
            print("  Using SSL connection...")
            client = redis.from_url(
                redis_url,
                ssl_cert_reqs=ssl.CERT_NONE,
                ssl_check_hostname=False,
                socket_connect_timeout=30,
                socket_timeout=30,
                socket_keepalive=True,
                socket_keepalive_options={
                    1: 1,  # TCP_KEEPIDLE
                    2: 1,  # TCP_KEEPINTVL
                    3: 3,  # TCP_KEEPCNT
                }
            )
        else:
            # Non-SSL connection
            client = redis.from_url(
                redis_url,
                socket_connect_timeout=30,
                socket_timeout=30
            )
        
        # Test ping
        print("  Testing PING command...")
        start_time = time.time()
        response = client.ping()
        ping_time = time.time() - start_time
        print(f"  PING successful: {response} (took {ping_time:.2f}s)")
        
        # Test basic operations
        print("  Testing SET/GET operations...")
        test_key = f"test_connection_{int(time.time())}"
        client.set(test_key, "test_value", ex=60)
        value = client.get(test_key)
        print(f"  SET/GET successful: {value.decode() if value else None}")
        
        # Cleanup
        client.delete(test_key)
        
        print("\nRedis connection test PASSED!")
        return True
        
    except redis.exceptions.TimeoutError as e:
        print(f"  Redis connection timeout: {e}")
        print("  This suggests a network connectivity issue or firewall blocking the connection")
    except redis.exceptions.ConnectionError as e:
        print(f"  Redis connection error: {e}")
        print("  This could be due to incorrect credentials or SSL configuration")
    except Exception as e:
        print(f"  Unexpected error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
    
    print("\nRedis connection test FAILED!")
    return False

if __name__ == "__main__":
    success = test_redis_connection()
    sys.exit(0 if success else 1)