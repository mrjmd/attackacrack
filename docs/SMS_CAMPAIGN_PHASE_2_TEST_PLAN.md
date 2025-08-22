# SMS Campaign System - Phase 2 Test Plan
**Compliance & Safety Implementation**

## Overview
Phase 2 implements critical compliance and safety features for the SMS campaign system, focusing on opt-out processing and phone number validation to ensure TCPA compliance and reduce bounce rates.

## Test Environment Setup

### Prerequisites
```bash
# Start Docker services
docker-compose up -d

# Set environment variables
export NUMVERIFY_API_KEY=your_api_key_here
export OPENPHONE_API_KEY=your_api_key
export OPENPHONE_WEBHOOK_SECRET=your_webhook_secret

# Run database migrations
docker-compose exec web flask db upgrade
```

## Feature 1: Opt-Out Processing Pipeline

### 1.1 STOP Keyword Detection
**Test Scenario:** Receive STOP message via webhook
```bash
# Simulate webhook with STOP message
curl -X POST http://localhost:5001/api/webhooks/openphone \
  -H "Content-Type: application/json" \
  -H "X-OpenPhone-Signature: valid_signature" \
  -d '{
    "type": "message.received",
    "data": {
      "object": {
        "from": "+1234567890",
        "text": "STOP",
        "conversationId": "conv_123"
      }
    }
  }'
```

**Expected Results:**
- ✅ Contact flagged as opted_out in database
- ✅ Confirmation SMS sent: "You have been unsubscribed from our SMS list"
- ✅ Audit log created in OptOutAudit table
- ✅ Contact excluded from all future campaigns

### 1.2 START Keyword Re-subscription
**Test Scenario:** Receive START message from opted-out contact
```bash
# First opt-out a contact, then send START
curl -X POST http://localhost:5001/api/webhooks/openphone \
  -H "Content-Type: application/json" \
  -d '{"type": "message.received", "data": {"object": {"from": "+1234567890", "text": "START"}}}'
```

**Expected Results:**
- ✅ Opt-out flag expired (not deleted)
- ✅ Confirmation SMS sent: "You have been resubscribed to our SMS list"
- ✅ Audit log shows opt-in event
- ✅ Contact eligible for campaigns again

### 1.3 Campaign Opt-Out Filtering
**Test Scenario:** Create campaign with opted-out contacts
```python
# In Flask shell
from app import create_app
app = create_app()
with app.app_context():
    campaign_service = app.services.get('campaign')
    
    # Create campaign
    campaign_id = 1  # Existing campaign
    result = campaign_service.generate_campaign_membership(campaign_id)
    
    print(f"Total contacts: {result.data['total_contacts']}")
    print(f"Opted out excluded: {result.data['opted_out_excluded']}")
    print(f"Eligible recipients: {result.data['eligible_recipients']}")
```

**Expected Results:**
- ✅ Opted-out contacts automatically excluded
- ✅ Statistics show exclusion counts
- ✅ No messages sent to opted-out contacts

### 1.4 Opt-Out Report Dashboard
**Test Scenario:** View opt-out analytics
```bash
# Navigate to dashboard
open http://localhost:5001/campaigns/opt-out-report
```

**Expected Results:**
- ✅ Total opted-out count displayed
- ✅ Last 30 days opt-out trend
- ✅ Keyword usage breakdown (STOP, UNSUBSCRIBE, etc.)
- ✅ Recent opt-out events table
- ✅ CSV export functionality

### 1.5 Compliance Verification
**Test Commands:**
```bash
# Run opt-out integration tests
docker-compose exec web pytest tests/integration/test_campaign_opt_out_filtering.py -v
docker-compose exec web pytest tests/integration/test_opt_out_webhook_integration.py -v

# Verify audit trail
docker-compose exec web flask shell
>>> from crm_database import OptOutAudit
>>> audits = OptOutAudit.query.all()
>>> for audit in audits:
...     print(f"{audit.phone_number}: {audit.keyword_used} at {audit.created_at}")
```

## Feature 2: Phone Number Validation

### 2.1 Single Phone Validation
**Test Scenario:** Validate individual phone number
```python
# In Flask shell
from app import create_app
app = create_app()
with app.app_context():
    phone_service = app.services.get('phone_validation')
    
    # Validate US mobile number
    result = phone_service.validate_phone('+14155552345')
    
    if result.is_success:
        print(f"Valid: {result.data['valid']}")
        print(f"Line Type: {result.data['line_type']}")
        print(f"Carrier: {result.data['carrier']}")
        print(f"Location: {result.data['location']}")
```

**Expected Results:**
- ✅ Valid phone returns is_valid=True
- ✅ Line type identified (mobile/landline)
- ✅ Carrier information retrieved
- ✅ Result cached for 30 days

### 2.2 Bulk Validation with Rate Limiting
**Test Scenario:** Validate multiple phones with API rate limits
```python
# Validate bulk list
phones = ['+14155552345', '+12125553456', '+13105554567', '+14085555678']
result = phone_service.validate_bulk(phones)

print(f"Validated: {result.data['validated_count']}")
print(f"Invalid: {result.data['invalid_count']}")
print(f"From cache: {result.data['cache_hits']}")
```

**Expected Results:**
- ✅ Processes in batches to respect rate limits
- ✅ Implements exponential backoff on 429 errors
- ✅ Uses cached results when available
- ✅ Returns comprehensive statistics

### 2.3 CSV Import Validation
**Test Scenario:** Validate phones during CSV import
```bash
# Upload CSV with phone numbers
curl -X POST http://localhost:5001/api/contacts/import \
  -F "file=@test_contacts.csv" \
  -F "validate_phones=true"
```

**Test CSV Content:**
```csv
first_name,last_name,phone,email
John,Doe,+14155552345,john@example.com
Jane,Smith,+1999999999,jane@example.com
Bob,Wilson,+12125553456,bob@example.com
```

**Expected Results:**
- ✅ Valid phones imported successfully
- ✅ Invalid phones flagged with warnings
- ✅ Validation results shown in UI
- ✅ Import continues despite invalid numbers

### 2.4 Cache Management
**Test Scenario:** Verify caching behavior
```python
# First validation - API call
result1 = phone_service.validate_phone('+14155552345')
print(f"From cache: {result1.data.get('from_cache', False)}")  # False

# Second validation - From cache
result2 = phone_service.validate_phone('+14155552345')
print(f"From cache: {result2.data.get('from_cache', False)}")  # True

# Clear expired cache
expired_count = phone_service.clear_expired_cache()
print(f"Cleared {expired_count} expired validations")
```

**Expected Results:**
- ✅ First call hits API
- ✅ Subsequent calls use cache
- ✅ Cache expires after 30 days
- ✅ Expired entries cleaned up

### 2.5 Error Handling
**Test Scenario:** Handle API failures gracefully
```python
# Simulate API timeout
import os
os.environ['NUMVERIFY_BASE_URL'] = 'http://invalid-url'

result = phone_service.validate_phone('+14155552345')
if not result.is_success:
    print(f"Error: {result.error}")
    print(f"Code: {result.error_code}")
```

**Expected Results:**
- ✅ Timeout after 10 seconds
- ✅ Returns Result with error details
- ✅ Doesn't crash application
- ✅ Logs error for monitoring

## Performance Testing

### Load Test: Bulk Validation
```python
# Test with 1000 phone numbers
import time
phones = [f"+1415555{i:04d}" for i in range(1000)]

start = time.time()
result = phone_service.validate_bulk(phones)
duration = time.time() - start

print(f"Processed 1000 phones in {duration:.2f} seconds")
print(f"Rate: {1000/duration:.2f} phones/second")
```

**Expected Performance:**
- ✅ < 60 seconds for 1000 phones (with rate limiting)
- ✅ Efficient cache utilization
- ✅ No memory leaks
- ✅ Database connection pooling

## Integration Testing

### Full Campaign Flow with Validation
```bash
# 1. Import contacts with validation
curl -X POST http://localhost:5001/api/contacts/import \
  -F "file=@contacts.csv" \
  -F "validate_phones=true"

# 2. Create campaign
curl -X POST http://localhost:5001/api/campaigns \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test Campaign",
    "list_id": 1,
    "message_template": "Hi {first_name}, special offer!",
    "exclude_invalid_phones": true
  }'

# 3. Check campaign stats
curl http://localhost:5001/api/campaigns/1/stats
```

**Expected Results:**
- ✅ Invalid phones excluded from campaign
- ✅ Opted-out contacts excluded
- ✅ Campaign stats show exclusion reasons
- ✅ Only valid, opted-in contacts receive messages

## Database Verification

### Check Database State
```sql
-- Check opt-out flags
SELECT c.first_name, c.phone, cf.flag_type, cf.created_at
FROM contacts c
JOIN contact_flags cf ON c.id = cf.contact_id
WHERE cf.flag_type = 'opted_out' AND cf.expires_at IS NULL;

-- Check phone validations
SELECT phone_number, is_valid, line_type, carrier, cached_until
FROM phone_validations
ORDER BY validation_date DESC
LIMIT 10;

-- Check opt-out audit log
SELECT contact_id, phone_number, keyword_used, opt_out_method, created_at
FROM opt_out_audits
ORDER BY created_at DESC;
```

## Automated Test Suite

### Run Complete Phase 2 Tests
```bash
# All Phase 2 tests
docker-compose exec web pytest tests/ -k "opt_out or phone_validation" -v

# Unit tests only
docker-compose exec web pytest tests/unit/services/test_opt_out_service.py -v
docker-compose exec web pytest tests/unit/services/test_phone_validation_service.py -v

# Integration tests
docker-compose exec web pytest tests/integration/test_campaign_opt_out_filtering.py -v
docker-compose exec web pytest tests/integration/test_opt_out_webhook_integration.py -v
docker-compose exec web pytest tests/integration/services/test_phone_validation_integration.py -v

# Coverage report
docker-compose exec web pytest tests/ -k "opt_out or phone_validation" \
  --cov=services.opt_out_service \
  --cov=services.phone_validation_service \
  --cov-report=term-missing
```

## Success Criteria

### Opt-Out Processing
- ✅ 100% TCPA compliance with automatic opt-out handling
- ✅ < 30 seconds processing time for opt-out requests
- ✅ Confirmation messages sent for all opt-out/opt-in events
- ✅ Complete audit trail maintained
- ✅ Zero opted-out contacts receiving campaign messages

### Phone Validation
- ✅ 95%+ accuracy in phone validation
- ✅ < 100ms response time for cached validations
- ✅ Successful handling of API rate limits
- ✅ 30-day cache reducing API calls by 80%+
- ✅ Invalid phones excluded from campaigns

### Overall System
- ✅ All existing tests continue to pass
- ✅ No performance degradation
- ✅ Complete integration with existing workflows
- ✅ Comprehensive error handling
- ✅ Production-ready compliance features

## Monitoring & Alerts

### Key Metrics to Track
- Opt-out rate (target: < 2%)
- Phone validation cache hit rate (target: > 80%)
- API rate limit hits (should decrease over time)
- Campaign exclusion rates by reason
- Webhook processing time (target: < 1 second)

### Log Monitoring
```bash
# Watch for opt-out events
docker-compose logs -f web | grep "opt-out"

# Monitor validation API calls
docker-compose logs -f web | grep "NumVerify"

# Check for errors
docker-compose logs -f web | grep -E "ERROR|CRITICAL"
```

## Rollback Plan

If issues arise:
```bash
# 1. Disable opt-out processing
export DISABLE_OPT_OUT_PROCESSING=true

# 2. Disable phone validation
export DISABLE_PHONE_VALIDATION=true

# 3. Rollback database if needed
docker-compose exec web flask db downgrade -1

# 4. Revert code changes
git revert HEAD
```

---

**Document Version:** 1.0
**Created:** August 21, 2025
**Phase Status:** Implementation Complete
**Test Coverage:** 140 tests written, core functionality operational