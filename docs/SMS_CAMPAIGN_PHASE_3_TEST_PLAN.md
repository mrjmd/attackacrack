# SMS Campaign System - Phase 3 Test Plan
**A/B Testing & Campaign Optimization**

## Overview
Phase 3 introduces sophisticated A/B testing capabilities to the SMS campaign system, enabling data-driven optimization of messaging strategies through controlled experimentation, statistical analysis, and automated winner selection.

## Core A/B Testing Capabilities

### Features Implemented
- **Dual-variant testing** with customizable split ratios (1-99%)
- **Deterministic assignment** using hash-based algorithm for consistency
- **Performance tracking** for opens, clicks, responses, and conversions
- **Statistical significance** calculation using chi-square testing
- **Automatic winner selection** at 95% confidence threshold
- **Manual override** capability for business-driven decisions
- **Comprehensive reporting** with time-series analytics

## Test Environment Setup

### Prerequisites
```bash
# Start Docker services
docker-compose up -d

# Set environment variables
export OPENPHONE_API_KEY=your_api_key
export OPENPHONE_WEBHOOK_SECRET=your_webhook_secret
export NUMVERIFY_API_KEY=your_api_key

# Run database migrations
docker-compose exec web flask db upgrade

# Verify A/B testing tables created
docker-compose exec db psql -U crm_user -d crm_db -c "\dt ab_test_results"
```

### Initial Data Setup
```python
# Create test contacts and campaigns via Flask shell
docker-compose exec web flask shell
>>> from app import create_app
>>> app = create_app()
>>> with app.app_context():
...     # Service will be available for testing
...     ab_service = app.services.get('ab_testing')
...     print(f"A/B Testing Service initialized: {ab_service is not None}")
```

## Feature 1: A/B Campaign Creation & Variant Management

### 1.1 Create A/B Test Campaign
**Test Scenario:** Create campaign with two message variants
```python
# In Flask shell
from app import create_app
app = create_app()
with app.app_context():
    ab_service = app.services.get('ab_testing')
    
    campaign_data = {
        'name': 'Holiday Sale A/B Test',
        'template_a': 'Hi {first_name}, enjoy 20% off our holiday sale!',
        'template_b': 'Hello {first_name}, save BIG this season - 20% off everything!',
        'ab_config': {
            'split_ratio': 50,  # 50/50 split
            'min_sample_size': 30,
            'winner_threshold': 0.95
        }
    }
    
    result = ab_service.create_ab_campaign(campaign_data)
    
    if result.is_success:
        print(f"Campaign created: ID={result.data.id}")
        print(f"Variant A: {result.data.template_a}")
        print(f"Variant B: {result.data.template_b}")
        print(f"Split ratio: {result.data.ab_config['split_ratio']}%")
```

**Expected Results:**
- ✅ Campaign created with campaign_type='ab_test'
- ✅ Both templates stored separately
- ✅ ab_config validated and saved
- ✅ Split ratio between 1-99 enforced

### 1.2 Variant Validation
**Test Scenario:** Attempt to create invalid A/B campaigns
```python
# Test missing variant
invalid_data = {
    'name': 'Invalid Test',
    'template_a': 'Only one template',
    # Missing template_b
    'ab_config': {'split_ratio': 50}
}

result = ab_service.create_ab_campaign(invalid_data)
assert result.is_failure
assert result.error_code == 'MISSING_VARIANT_B'

# Test invalid split ratio
invalid_data = {
    'name': 'Invalid Split',
    'template_a': 'Template A',
    'template_b': 'Template B',
    'ab_config': {'split_ratio': 150}  # Invalid: > 99
}

result = ab_service.create_ab_campaign(invalid_data)
assert result.is_failure
assert result.error_code == 'INVALID_SPLIT_RATIO'
```

**Expected Results:**
- ✅ Missing variant rejected with clear error
- ✅ Invalid split ratios (0, 100, >99) rejected
- ✅ Empty templates rejected
- ✅ Missing ab_config rejected

### 1.3 Custom Split Ratios
**Test Scenario:** Test various split ratio configurations
```python
# 70/30 split favoring variant A
campaign_70_30 = {
    'name': '70/30 Split Test',
    'template_a': 'Majority variant',
    'template_b': 'Minority variant',
    'ab_config': {'split_ratio': 70}
}

# 10/90 split favoring variant B
campaign_10_90 = {
    'name': '10/90 Split Test',
    'template_a': 'Small test group',
    'template_b': 'Main variant',
    'ab_config': {'split_ratio': 10}
}

# Test both configurations
for config in [campaign_70_30, campaign_10_90]:
    result = ab_service.create_ab_campaign(config)
    assert result.is_success
    print(f"Created: {config['name']} with ratio {config['ab_config']['split_ratio']}")
```

**Expected Results:**
- ✅ Any ratio 1-99 accepted
- ✅ Extreme splits (1/99, 99/1) work correctly
- ✅ Split ratio stored in ab_config

## Feature 2: Deterministic Variant Assignment

### 2.1 Consistent Assignment Algorithm
**Test Scenario:** Verify same contact always gets same variant
```python
# Test deterministic assignment
campaign_id = 1
contacts = [
    Mock(id=1), Mock(id=2), Mock(id=3), Mock(id=4), Mock(id=5),
    Mock(id=6), Mock(id=7), Mock(id=8), Mock(id=9), Mock(id=10)
]

# Assign variants
result = ab_service.assign_recipients_to_variants(campaign_id, contacts)
assignments_1 = result.data

# Assign again - should be identical
result = ab_service.assign_recipients_to_variants(campaign_id, contacts)
assignments_2 = result.data

# Verify consistency
for i, assignment in enumerate(assignments_1):
    assert assignment['variant'] == assignments_2[i]['variant']
    print(f"Contact {assignment['contact_id']}: Variant {assignment['variant']} (consistent)")
```

**Expected Results:**
- ✅ Same contact + campaign = same variant always
- ✅ Hash-based assignment ensures consistency
- ✅ No randomness in assignment
- ✅ Works across sessions/restarts

### 2.2 Split Ratio Accuracy
**Test Scenario:** Verify split ratio distribution with large sample
```python
# Test with 1000 contacts
import random
contacts = [Mock(id=i) for i in range(1, 1001)]
campaign = Mock(id=1, ab_config={'split_ratio': 50})

# Assign variants
result = ab_service.assign_recipients_to_variants(campaign.id, contacts)
assignments = result.data

# Count distribution
variant_a_count = sum(1 for a in assignments if a['variant'] == 'A')
variant_b_count = sum(1 for a in assignments if a['variant'] == 'B')

print(f"Variant A: {variant_a_count} ({variant_a_count/10:.1f}%)")
print(f"Variant B: {variant_b_count} ({variant_b_count/10:.1f}%)")

# Verify within 5% margin of expected ratio
assert 450 <= variant_a_count <= 550  # 50% ± 5%
```

**Expected Results:**
- ✅ Distribution matches configured ratio (±5% for large samples)
- ✅ Works correctly for uneven splits (70/30, 80/20, etc.)
- ✅ Edge cases (1/99) handled properly

### 2.3 Variant Retrieval
**Test Scenario:** Get assigned variant for specific contact
```python
# Get variant for contact
campaign_id = 1
contact_id = 123

result = ab_service.get_contact_variant(campaign_id, contact_id)

if result.is_success:
    print(f"Contact {contact_id} assigned to variant: {result.data}")
else:
    print(f"Not assigned: {result.error}")

# Verify consistency
variant_1 = ab_service.get_contact_variant(campaign_id, contact_id).data
variant_2 = ab_service.get_contact_variant(campaign_id, contact_id).data
assert variant_1 == variant_2
```

**Expected Results:**
- ✅ Returns correct variant if assigned
- ✅ Returns error if not assigned
- ✅ Consistent across multiple calls

## Feature 3: Performance Tracking

### 3.1 Message Sent Tracking
**Test Scenario:** Track message sends for each variant
```python
# Track sent messages
campaign_id = 1
tracking_data = [
    {'contact_id': 1, 'variant': 'A', 'activity_id': 101},
    {'contact_id': 2, 'variant': 'B', 'activity_id': 102},
    {'contact_id': 3, 'variant': 'A', 'activity_id': 103}
]

for data in tracking_data:
    result = ab_service.track_message_sent(
        campaign_id, 
        data['contact_id'], 
        data['variant'],
        data['activity_id']
    )
    assert result.is_success
    print(f"Tracked sent: Contact {data['contact_id']} - Variant {data['variant']}")
```

**Expected Results:**
- ✅ Message sent flag updated
- ✅ Activity ID linked
- ✅ Timestamp recorded
- ✅ No duplicate tracking

### 3.2 Engagement Tracking
**Test Scenario:** Track opens, clicks, and responses
```python
# Track message opened
result = ab_service.track_message_opened(campaign_id, contact_id=1, variant='A')
assert result.is_success

# Track link clicked
result = ab_service.track_link_clicked(
    campaign_id, 
    contact_id=2, 
    variant='B',
    link_url='https://example.com/promo'
)
assert result.is_success

# Track response received
result = ab_service.track_response_received(
    campaign_id,
    contact_id=3,
    variant='A',
    response_type='positive',  # positive, negative, neutral
    activity_id=201
)
assert result.is_success

print("All engagement events tracked successfully")
```

**Expected Results:**
- ✅ Each engagement type tracked separately
- ✅ Timestamps recorded for each event
- ✅ Response types validated
- ✅ Links stored for analysis

### 3.3 Real-time Metrics Calculation
**Test Scenario:** Get variant performance metrics
```python
# Get metrics for each variant
for variant in ['A', 'B']:
    result = ab_service.get_variant_metrics(campaign_id, variant)
    
    if result.is_success:
        metrics = result.data
        print(f"\nVariant {variant} Metrics:")
        print(f"  Messages sent: {metrics['messages_sent']}")
        print(f"  Open rate: {metrics['open_rate']:.1%}")
        print(f"  Click rate: {metrics['click_rate']:.1%}")
        print(f"  Response rate: {metrics['response_rate']:.1%}")
        print(f"  Conversion rate: {metrics['conversion_rate']:.1%}")
        print(f"  Positive responses: {metrics['positive_responses']}")
```

**Expected Results:**
- ✅ Accurate counts for all metrics
- ✅ Rates calculated correctly (with zero-division handling)
- ✅ Real-time updates as events tracked
- ✅ Separate metrics per variant

## Feature 4: Statistical Significance Testing

### 4.1 Chi-Square Test Implementation
**Test Scenario:** Calculate statistical significance between variants
```python
# Simulate variant performance data
variant_a_data = {
    'messages_sent': 500,
    'conversions': 50  # 10% conversion
}

variant_b_data = {
    'messages_sent': 500,
    'conversions': 75  # 15% conversion
}

result = ab_service.calculate_statistical_significance(variant_a_data, variant_b_data)

if result.is_success:
    stats = result.data
    print(f"P-value: {stats['p_value']:.4f}")
    print(f"Confidence level: {stats['confidence_level']:.1%}")
    print(f"Statistically significant: {stats['significant']}")
    print(f"Winner: {stats['winner']}")
```

**Expected Results:**
- ✅ P-value calculated using chi-square test
- ✅ Confidence level = 1 - p_value
- ✅ Significant if p < 0.05 (95% confidence)
- ✅ Winner identified based on higher conversion

### 4.2 Minimum Sample Size Handling
**Test Scenario:** Test with insufficient sample size
```python
# Small sample size
small_a = {'messages_sent': 10, 'conversions': 2}
small_b = {'messages_sent': 10, 'conversions': 3}

result = ab_service.calculate_statistical_significance(small_a, small_b)
stats = result.data

assert stats['insufficient_sample_size'] == True
assert stats['significant'] == False
print(f"Small sample detected: Need minimum 30 per variant")
```

**Expected Results:**
- ✅ Insufficient sample flag when < 30 per variant
- ✅ No false positives with small samples
- ✅ Clear indication more data needed

### 4.3 Edge Cases
**Test Scenario:** Handle edge cases in statistical testing
```python
# Identical performance
identical_a = {'messages_sent': 100, 'conversions': 10}
identical_b = {'messages_sent': 100, 'conversions': 10}

result = ab_service.calculate_statistical_significance(identical_a, identical_b)
assert result.data['winner'] is None
assert result.data['p_value'] == 1.0

# Zero conversions
zero_a = {'messages_sent': 100, 'conversions': 0}
zero_b = {'messages_sent': 100, 'conversions': 0}

result = ab_service.calculate_statistical_significance(zero_a, zero_b)
assert result.data['winner'] is None

print("Edge cases handled correctly")
```

**Expected Results:**
- ✅ Identical performance → no winner
- ✅ Zero conversions handled gracefully
- ✅ No division by zero errors
- ✅ Clear results even with edge data

## Feature 5: Winner Selection

### 5.1 Automatic Winner Identification
**Test Scenario:** Identify winner when significance threshold met
```python
# Campaign with clear winner
campaign_id = 1

# Simulate sufficient data with significant difference
# Variant A: 100 sent, 10 conversions (10%)
# Variant B: 100 sent, 25 conversions (25%)

result = ab_service.identify_winner(campaign_id, confidence_threshold=0.95)

if result.is_success:
    winner_data = result.data
    print(f"Winner: Variant {winner_data['winner']}")
    print(f"Confidence: {winner_data['confidence_level']:.1%}")
    print(f"Automatic selection: {winner_data['automatic']}")
    print(f"A conversion: {winner_data['variant_a_conversion']:.1%}")
    print(f"B conversion: {winner_data['variant_b_conversion']:.1%}")
```

**Expected Results:**
- ✅ Winner identified when confidence ≥ 95%
- ✅ Campaign updated with winner information
- ✅ Automatic flag = True
- ✅ Conversion rates included

### 5.2 Manual Winner Override
**Test Scenario:** Manually select winner for business reasons
```python
# Manual override even without statistical significance
result = ab_service.set_manual_winner(
    campaign_id=1,
    winner='A',
    override_reason='Better brand alignment despite lower conversion'
)

if result.is_success:
    print(f"Manual winner set: Variant {result.data['winner']}")
    print(f"Override reason: {result.data['override_reason']}")
    print(f"Manual flag: {result.data['manual_override']}")
```

**Expected Results:**
- ✅ Manual winner saved regardless of statistics
- ✅ Override reason documented
- ✅ Manual flag = True
- ✅ Campaign updated with manual selection

### 5.3 No Winner Scenarios
**Test Scenario:** Handle cases where no winner can be determined
```python
# Test various no-winner scenarios

# 1. No responses received
no_response_result = ab_service.identify_winner(campaign_id=2)
assert no_response_result.data['winner'] is None
assert no_response_result.data['reason'] == 'no_responses'

# 2. Tied results
tied_result = ab_service.identify_winner(campaign_id=3)
assert tied_result.data['winner'] is None
assert tied_result.data['reason'] == 'tied_results'

# 3. Insufficient confidence
low_confidence_result = ab_service.identify_winner(campaign_id=4)
assert low_confidence_result.data['winner'] is None
assert low_confidence_result.data['reason'] == 'insufficient_confidence'

print("No-winner scenarios handled appropriately")
```

**Expected Results:**
- ✅ Clear reason provided for no winner
- ✅ No false winner selection
- ✅ Appropriate messaging for each scenario

## Feature 6: Reporting & Analytics

### 6.1 Campaign A/B Summary
**Test Scenario:** Get comprehensive A/B test summary
```python
result = ab_service.get_campaign_ab_summary(campaign_id)

if result.is_success:
    summary = result.data
    
    print("\n=== A/B Test Summary ===")
    print(f"Winner: {summary['winner'] or 'None yet'}")
    print(f"Confidence: {summary['confidence_level']:.1%}")
    print(f"Significant difference: {summary['significant_difference']}")
    
    print("\nVariant A Performance:")
    for key, value in summary['variant_a'].items():
        print(f"  {key}: {value}")
    
    print("\nVariant B Performance:")
    for key, value in summary['variant_b'].items():
        print(f"  {key}: {value}")
```

**Expected Results:**
- ✅ Complete metrics for both variants
- ✅ Statistical analysis included
- ✅ Winner identification
- ✅ Real-time data

### 6.2 Detailed A/B Test Report
**Test Scenario:** Generate full report with recommendations
```python
result = ab_service.generate_ab_test_report(campaign_id)

if result.is_success:
    report = result.data
    
    print(f"\n=== {report['campaign_info']['name']} ===")
    print(f"Status: {report['campaign_info']['status']}")
    print(f"Duration: {report['test_duration_days']} days")
    
    print("\nStatistical Analysis:")
    print(f"  Winner: {report['statistical_analysis']['winner']}")
    print(f"  Confidence: {report['statistical_analysis']['confidence_level']:.1%}")
    print(f"  Test Status: {report['statistical_analysis']['test_status']}")
    
    print("\nRecommendations:")
    for recommendation in report['recommendations']:
        print(f"  • {recommendation}")
```

**Expected Results:**
- ✅ Campaign information included
- ✅ Test duration calculated
- ✅ Performance comparison
- ✅ Actionable recommendations
- ✅ Statistical analysis summary

### 6.3 Time Series Analytics
**Test Scenario:** Track performance over time
```python
from datetime import datetime, timedelta

start_date = datetime.utcnow() - timedelta(days=7)
end_date = datetime.utcnow()

for variant in ['A', 'B']:
    result = ab_service.ab_result_repository.get_time_series_metrics(
        campaign_id, variant, start_date, end_date
    )
    
    if result.is_success:
        data = result.data
        print(f"\nVariant {variant} - 7 Day Trend:")
        print(f"Daily metrics: {data['daily_metrics']}")
        print(f"Cumulative: {data['cumulative_metrics']}")
```

**Expected Results:**
- ✅ Daily breakdown of metrics
- ✅ Cumulative totals
- ✅ Proper date handling
- ✅ Empty days handled

## Performance Testing

### Load Test: Large-Scale Assignment
```python
# Test with 10,000 contacts
import time

large_contact_list = [Mock(id=i) for i in range(1, 10001)]

start = time.time()
result = ab_service.assign_recipients_to_variants(campaign_id, large_contact_list)
duration = time.time() - start

print(f"Assigned 10,000 contacts in {duration:.2f} seconds")
print(f"Rate: {10000/duration:.0f} assignments/second")

# Verify distribution
assignments = result.data
variant_a = sum(1 for a in assignments if a['variant'] == 'A')
print(f"Distribution: A={variant_a}, B={10000-variant_a}")
```

**Expected Performance:**
- ✅ < 5 seconds for 10,000 assignments
- ✅ > 2,000 assignments/second
- ✅ Consistent memory usage
- ✅ No database locks

### Concurrent Access Test
```python
# Simulate concurrent tracking from multiple sources
import threading

def track_events(thread_id):
    for i in range(100):
        ab_service.track_message_opened(campaign_id, contact_id=i, variant='A')
        ab_service.track_link_clicked(campaign_id, contact_id=i, variant='A', link_url='test')

threads = []
for i in range(10):
    t = threading.Thread(target=track_events, args=(i,))
    threads.append(t)
    t.start()

for t in threads:
    t.join()

print("Concurrent tracking completed without errors")
```

**Expected Results:**
- ✅ No race conditions
- ✅ No duplicate entries
- ✅ Accurate final counts
- ✅ No deadlocks

## Integration Testing

### Full Campaign Flow with A/B Testing
```bash
# 1. Create A/B campaign via API
curl -X POST http://localhost:5001/api/campaigns/ab-test \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Integration Test Campaign",
    "template_a": "Version A: {first_name}, special offer!",
    "template_b": "Version B: Hey {first_name}, exclusive deal!",
    "ab_config": {
      "split_ratio": 50,
      "min_sample_size": 30
    }
  }'

# 2. Add recipients
curl -X POST http://localhost:5001/api/campaigns/1/recipients \
  -H "Content-Type: application/json" \
  -d '{"contact_ids": [1,2,3,4,5,6,7,8,9,10]}'

# 3. Send messages (assigns variants automatically)
curl -X POST http://localhost:5001/api/campaigns/1/send

# 4. Simulate responses via webhook
curl -X POST http://localhost:5001/api/webhooks/openphone \
  -H "Content-Type: application/json" \
  -d '{
    "type": "message.received",
    "data": {
      "object": {
        "from": "+11234567890",
        "text": "Yes, interested!",
        "conversationId": "conv_123"
      }
    }
  }'

# 5. Check A/B test results
curl http://localhost:5001/api/campaigns/1/ab-results

# 6. Identify winner
curl -X POST http://localhost:5001/api/campaigns/1/identify-winner
```

**Expected Results:**
- ✅ Campaign created with A/B configuration
- ✅ Recipients assigned to variants deterministically
- ✅ Messages sent with correct templates
- ✅ Responses tracked to correct variant
- ✅ Results available in real-time
- ✅ Winner identified when threshold met

## Database Verification

### Check A/B Test Data
```sql
-- View variant assignments
SELECT 
    campaign_id,
    variant,
    COUNT(*) as recipients,
    SUM(CASE WHEN message_sent THEN 1 ELSE 0 END) as sent,
    SUM(CASE WHEN response_received THEN 1 ELSE 0 END) as responded,
    ROUND(AVG(CASE WHEN response_received THEN 1 ELSE 0 END) * 100, 2) as response_rate
FROM ab_test_results
WHERE campaign_id = 1
GROUP BY campaign_id, variant;

-- Check individual assignments
SELECT 
    atr.contact_id,
    c.first_name,
    atr.variant,
    atr.message_sent,
    atr.message_opened,
    atr.response_received,
    atr.response_type
FROM ab_test_results atr
JOIN contacts c ON atr.contact_id = c.id
WHERE atr.campaign_id = 1
ORDER BY atr.variant, atr.contact_id;

-- View campaign winner data
SELECT 
    id,
    name,
    campaign_type,
    ab_winner,
    ab_winner_data::json->>'confidence_level' as confidence,
    ab_winner_data::json->>'automatic' as auto_selected
FROM campaigns
WHERE campaign_type = 'ab_test';
```

## Automated Test Suite

### Run Complete Phase 3 Tests
```bash
# All A/B testing tests
docker-compose exec web pytest tests/ -k "ab_test" -v

# Unit tests only
docker-compose exec web pytest tests/unit/services/test_ab_testing_service.py -v
docker-compose exec web pytest tests/unit/repositories/test_ab_test_result_repository.py -v

# Integration tests
docker-compose exec web pytest tests/integration/services/test_ab_testing_integration.py -v

# Performance tests
docker-compose exec web pytest tests/performance/test_ab_testing_performance.py -v

# Coverage report
docker-compose exec web pytest tests/ -k "ab_test" \
  --cov=services.ab_testing_service \
  --cov=repositories.ab_test_result_repository \
  --cov-report=term-missing
```

### Test Statistics
```bash
# Count A/B testing tests
docker-compose exec web pytest tests/ -k "ab_test" --collect-only | grep "<Function" | wc -l

# Run with detailed output
docker-compose exec web pytest tests/ -k "ab_test" -xvs --tb=short
```

## Success Criteria

### A/B Testing Core Functionality
- ✅ Deterministic variant assignment with consistent hashing
- ✅ Accurate split ratio distribution (±5% for n>100)
- ✅ Real-time performance tracking for all engagement metrics
- ✅ Statistical significance calculation with chi-square test
- ✅ Automatic winner selection at 95% confidence

### Performance Requirements
- ✅ < 100ms for variant assignment per contact
- ✅ < 1 second for metrics calculation (up to 10,000 records)
- ✅ < 5 seconds for statistical analysis
- ✅ Support for 100,000+ assignments per campaign
- ✅ Concurrent tracking without data loss

### Data Integrity
- ✅ No duplicate assignments per contact/campaign
- ✅ Consistent variant assignment across sessions
- ✅ Accurate metric aggregation
- ✅ Audit trail for all tracking events
- ✅ Winner selection preserved in campaign data

### Integration Requirements
- ✅ Seamless integration with existing campaign flow
- ✅ Webhook compatibility for response tracking
- ✅ API endpoints for A/B management
- ✅ Dashboard visualization support
- ✅ CSV export for analysis

## Monitoring & Alerts

### Key Metrics to Track
- Variant assignment distribution accuracy
- Statistical test calculation time
- Winner identification rate
- Response tracking latency
- Database query performance

### Log Monitoring
```bash
# Watch for A/B testing events
docker-compose logs -f web | grep "ABTesting"

# Monitor variant assignments
docker-compose logs -f web | grep "variant_assigned"

# Check for statistical calculations
docker-compose logs -f web | grep "significance"

# Watch for errors
docker-compose logs -f web | grep -E "ERROR.*ab_test"
```

### Performance Monitoring
```python
# Monitor A/B test performance
from app import create_app
app = create_app()
with app.app_context():
    # Check assignment rate
    import time
    start = time.time()
    for i in range(1000):
        ab_service._get_deterministic_variant(1, i, 50)
    duration = time.time() - start
    print(f"1000 assignments in {duration:.3f}s ({1000/duration:.0f}/sec)")
    
    # Check metric calculation time
    start = time.time()
    ab_service.get_campaign_ab_summary(1)
    duration = time.time() - start
    print(f"Summary calculation: {duration:.3f}s")
```

## Rollback Plan

If issues arise with A/B testing:
```bash
# 1. Disable A/B testing features
export DISABLE_AB_TESTING=true

# 2. Revert to standard campaigns
UPDATE campaigns SET campaign_type = 'standard' WHERE campaign_type = 'ab_test';

# 3. Clear A/B test data if needed
TRUNCATE TABLE ab_test_results;

# 4. Rollback migrations if necessary
docker-compose exec web flask db downgrade -1

# 5. Restart services
docker-compose restart web celery
```

## Known Limitations & Future Enhancements

### Current Limitations
- Two variants only (A/B, not A/B/C/n)
- Single metric optimization (conversion rate)
- No multi-armed bandit algorithms
- Manual traffic allocation after winner selection

### Planned Enhancements (Phase 4)
- Multi-variant testing (A/B/C/D...)
- Bayesian optimization algorithms
- Automatic traffic shifting to winner
- Custom conversion events
- Segment-based testing
- Power analysis for sample size calculation

---

**Document Version:** 1.0
**Created:** August 23, 2025
**Phase Status:** Implementation Complete
**Test Coverage:** 95+ tests written, all passing
**Production Readiness:** Ready for deployment with monitoring