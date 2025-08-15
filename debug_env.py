#!/usr/bin/env python3
"""Debug environment variables in production"""
import os

print("=== Environment Variables Debug ===")
print()

# Critical variables for Celery/Redis
critical_vars = [
    'REDIS_URL',
    'CELERY_BROKER_URL', 
    'CELERY_RESULT_BACKEND',
    'OPENPHONE_PHONE_NUMBER',
    'OPENPHONE_PHONE_NUMBER_ID',
    'ENCRYPTION_KEY',
    'CELERY_BROKER_URL',
    'CELERY_RESULT_BACKEND'
]

print("Critical Variables:")
for var in critical_vars:
    value = os.environ.get(var, 'NOT SET')
    if value == 'NOT SET':
        print(f"  ❌ {var}: NOT SET")
    elif value.startswith('${'):
        print(f"  ⚠️  {var}: PLACEHOLDER NOT REPLACED ({value[:20]}...)")
    else:
        # Show first 10 chars for security
        masked = value[:10] + '...' if len(value) > 10 else value
        print(f"  ✓ {var}: {masked}")

print()
print("All environment variables with placeholders:")
for key, value in sorted(os.environ.items()):
    if '${' in str(value):
        print(f"  {key}: {value}")