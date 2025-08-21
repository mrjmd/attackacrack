"""Test configuration to prevent real connections during testing."""
import os

# Set testing environment variables BEFORE any imports
os.environ['TESTING'] = 'true'
os.environ['CELERY_ALWAYS_EAGER'] = 'true'
os.environ['CELERY_EAGER_PROPAGATES_EXCEPTIONS'] = 'true'

# Prevent Redis connection during testing
os.environ['REDIS_URL'] = 'redis://localhost:6379/15'  # Use test database