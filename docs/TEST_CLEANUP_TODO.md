# Test Cleanup & Coverage TODO Tracker

## 🎯 Current Status
- **Tests**: 1999 passing, 11 skipped
- **Warnings**: 474 total
- **Coverage**: ~18%
- **Target**: 85% coverage, <50 warnings, 0 unnecessary skips

---

## 📋 Phase 1: Enable Skipped Tests (Priority: HIGH)
**Timeline**: 1-2 days | **Risk**: LOW | **Impact**: HIGH

### ✅ Tests to Enable Immediately
- [ ] Enable A/B variant assignment test (`test_campaign_service.py:422`)
- [ ] Enable A/B variant stats test 1 (`test_campaign_service.py:443`)
- [ ] Enable A/B variant stats test 2 (`test_campaign_service.py:504`)
- [ ] Enable daily limit test 1 (`test_campaign_service.py:586`)
- [ ] Enable daily limit test 2 (`test_campaign_service.py:616`)
- [ ] Enable context personalization test (`test_campaign_service.py:649`)
- [ ] Enable campaign bounce info test (`test_campaign_repository_sms_metrics_enhancement.py:167`)
- [ ] Enable A/B testing service tests (multiple in `test_ab_testing_service.py`)

### 🔧 Tests to Update
- [ ] Fix service file path in `test_campaign_service_contact_flag_repository.py:285`
  - Change path to `campaign_service_refactored.py`
- [ ] Update personalization test context parameter (`test_campaign_service.py:649`)
  - Remove third parameter or update method
- [ ] Update get_remaining_recipients test (`test_ab_testing_service.py:599`)
  - Use existing `send_winner_to_remaining` method

### 🗑️ Tests to Remove
- [ ] Remove auth service init_app test 1 (`test_auth_service.py:363`)
- [ ] Remove auth service init_app test 2 (`test_auth_service.py:369`)
- [ ] Remove job service backward compatibility test (`test_job_service_repository_pattern.py:154`)

### ⏸️ Tests to Keep Skipped (Document Reason)
- [ ] Document why min_days_since_contact test stays skipped (`test_campaign_service.py:300`)
- [ ] Document why repository migration test stays skipped (`test_service_model_import_violations.py:409`)

---

## 🚨 Phase 2: Eliminate Warnings (Priority: HIGH)
**Timeline**: 2-3 days | **Risk**: LOW | **Impact**: VERY HIGH

### 📅 datetime.utcnow() Replacement (399 warnings)
**Automated Replacement Script Needed**

#### Step 1: Create Utility Function
- [ ] Create `utils/datetime_utils.py` with timezone-aware helpers
- [ ] Add `utcnow()` function returning `datetime.now(timezone.utc)`
- [ ] Add `utcnow_naive()` for cases needing naive datetime

#### Step 2: Update Repository Files (87 occurrences)
- [ ] `repositories/activity_repository.py` (15)
- [ ] `repositories/ab_test_result_repository.py` (7)
- [ ] `repositories/invite_token_repository.py` (5)
- [ ] `repositories/campaign_repository.py` (4)
- [ ] `repositories/contact_repository.py` (3)
- [ ] All other repository files

#### Step 3: Update Service Files (62 occurrences)
- [ ] `services/auth_service_refactored.py` (8)
- [ ] `services/campaign_template_service.py` (6)
- [ ] `services/contact_service_refactored.py` (4)
- [ ] `services/campaign_service_refactored.py` (3)
- [ ] All other service files

#### Step 4: Update Test Files (250+ occurrences)
- [ ] Create and run automated replacement script
- [ ] Verify all tests still pass
- [ ] Check for any timezone-related issues

### 🗄️ SQLAlchemy Query.get() Updates (35 warnings)
- [ ] Update `app.py:466` User loader
- [ ] Update all test files using `Model.query.get()`
- [ ] Update documentation examples
- [ ] Search and replace pattern: `Model.query.get(id)` → `db.session.get(Model, id)`

### ⚙️ Flask-Session Configuration (4 warnings)
- [ ] Review Flask-Session 0.8.0 migration guide
- [ ] Update `config.py` SESSION_FILE_DIR to SESSION_CACHELIB
- [ ] Update SESSION_USE_SIGNER configuration
- [ ] Test session functionality after changes

---

## 📊 Phase 3: Achieve 85% Coverage (Priority: CRITICAL)
**Timeline**: 4-6 weeks | **Risk**: MEDIUM | **Impact**: CRITICAL

### Week 1: Critical Business Paths (Target: 30% → 45%)

#### Campaign System Testing
- [ ] Create `tests/unit/services/test_campaign_service_comprehensive.py`
  - [ ] Test campaign creation with validation
  - [ ] Test message template personalization
  - [ ] Test A/B variant assignment logic
  - [ ] Test daily limit enforcement
  - [ ] Test campaign status transitions
  - [ ] Test error handling and rollback

- [ ] Create `tests/integration/test_campaign_workflow.py`
  - [ ] Test full campaign creation → send → track flow
  - [ ] Test campaign with A/B testing
  - [ ] Test campaign with filters
  - [ ] Test campaign pause/resume

#### OpenPhone Webhook Testing
- [ ] Re-enable `tests/test_webhook_integrity.py.disabled`
- [ ] Create comprehensive webhook tests
  - [ ] Test signature validation
  - [ ] Test message received processing
  - [ ] Test delivery status updates
  - [ ] Test error scenarios
  - [ ] Test retry logic

### Week 2: Core Services (Target: 45% → 55%)

#### Contact Management Testing
- [ ] Enhance `tests/unit/services/test_contact_service.py`
  - [ ] Test phone number validation
  - [ ] Test duplicate detection
  - [ ] Test contact search and filtering
  - [ ] Test bulk operations
  - [ ] Test flag management

#### CSV Import Testing
- [ ] Create `tests/unit/services/test_csv_import_service.py`
  - [ ] Test file validation
  - [ ] Test data parsing
  - [ ] Test error handling
  - [ ] Test batch processing
  - [ ] Test duplicate handling

### Week 3: Authentication & Security (Target: 55% → 65%)

#### Auth Service Testing
- [ ] Enhance `tests/unit/services/test_auth_service.py`
  - [ ] Test password validation rules
  - [ ] Test session management
  - [ ] Test role-based access
  - [ ] Test invite flow
  - [ ] Test password reset

#### Security Testing
- [ ] Create `tests/integration/test_security.py`
  - [ ] Test CSRF protection
  - [ ] Test SQL injection prevention
  - [ ] Test XSS prevention
  - [ ] Test rate limiting
  - [ ] Test session security

### Week 4: Repository Layer (Target: 65% → 75%)

#### Repository Testing
- [ ] Test all repositories with <50% coverage
  - [ ] `repositories/campaign_repository.py`
  - [ ] `repositories/ab_test_result_repository.py`
  - [ ] `repositories/conversation_repository.py`
  - [ ] `repositories/webhook_event_repository.py`
  - [ ] `repositories/quickbooks_sync_repository.py`

#### Database Constraint Testing
- [ ] Test foreign key constraints
- [ ] Test unique constraints
- [ ] Test cascade deletes
- [ ] Test transaction rollback

### Week 5: Integration & Routes (Target: 75% → 85%)

#### Route Testing
- [ ] Test all routes with <50% coverage
  - [ ] Campaign routes
  - [ ] Contact routes
  - [ ] Invoice routes
  - [ ] Quote routes
  - [ ] Settings routes

#### End-to-End Workflows
- [ ] Re-enable `tests/test_campaign_integration.py.disabled`
- [ ] Create comprehensive E2E tests
  - [ ] Contact import → campaign → delivery
  - [ ] Quote → invoice → payment
  - [ ] Webhook → contact update → response

### Week 6: Final Push & Enforcement (Target: 85%+)

#### Coverage Gaps
- [ ] Identify remaining coverage gaps
- [ ] Write targeted tests for uncovered code
- [ ] Add edge case testing
- [ ] Add error scenario testing

#### CI/CD Integration
- [ ] Update pytest.ini with coverage requirements
- [ ] Update GitHub Actions to enforce 85% coverage
- [ ] Add coverage badge to README
- [ ] Set up Codecov integration (optional)

---

## 🛠️ Infrastructure & Tools

### Test Data Management
- [ ] Create `tests/factories.py` with Factory Boy
  - [ ] ContactFactory
  - [ ] CampaignFactory
  - [ ] ActivityFactory
  - [ ] InvoiceFactory
  - [ ] QuoteFactory

### Coverage Configuration
- [ ] Update `.coveragerc` with proper exclusions
- [ ] Configure branch coverage tracking
- [ ] Set up HTML coverage reports
- [ ] Add coverage trending

### Development Environment
- [ ] Create test database fixtures
- [ ] Set up test data seeding scripts
- [ ] Create mock services for external APIs
- [ ] Document testing best practices

---

## 📈 Success Metrics

### Phase 1 Complete When:
- [ ] 8 tests enabled and passing
- [ ] 3 tests removed
- [ ] 3 tests updated
- [ ] Documentation updated for kept skips

### Phase 2 Complete When:
- [ ] datetime warnings: 0 (from 399)
- [ ] SQLAlchemy warnings: 0 (from 35)
- [ ] Flask-Session warnings: 0 (from 4)
- [ ] Total warnings: <50 (from 474)

### Phase 3 Complete When:
- [ ] Overall coverage: ≥85%
- [ ] Critical paths: ≥95% coverage
- [ ] CI/CD enforcing coverage
- [ ] All disabled tests re-enabled
- [ ] Coverage report in each PR

---

## 🚦 Progress Tracking

### Daily Standup Questions
1. What tests were added/enabled today?
2. What warnings were eliminated?
3. What's the current coverage %?
4. Any blockers or issues?

### Weekly Metrics
- Tests added: ___
- Tests enabled: ___
- Warnings eliminated: ___
- Coverage increase: ___%
- Remaining work: ___

### Sprint Goals
- **Sprint 1**: Phase 1 + 2 complete (warnings <50)
- **Sprint 2**: Coverage 45% (critical paths)
- **Sprint 3**: Coverage 65% (core services)
- **Sprint 4**: Coverage 85% (full suite)

---

## 🔗 Related Documents
- [TEST_CLEANUP_PLAN.md](./TEST_CLEANUP_PLAN.md) - Detailed analysis and plan
- [SMS_CAMPAIGN_TODO_TRACKER.md](./SMS_CAMPAIGN_TODO_TRACKER.md) - Phase 3 implementation
- [ARCHITECTURE.md](./ARCHITECTURE.md) - System design patterns

---

## 📝 Notes

### Quick Commands
```bash
# Check current coverage
docker-compose exec web python -m pytest --cov --cov-report=term-missing

# Run specific test file
docker-compose exec web python -m pytest tests/unit/services/test_campaign_service.py -xvs

# Generate HTML coverage report
docker-compose exec web python -m pytest --cov --cov-report=html

# Count warnings by type
docker-compose exec web python -m pytest --tb=no -q 2>&1 | grep "Warning" | sort | uniq -c

# Find skipped tests
grep -r "@pytest.mark.skip\|pytest.skip" tests/
```

### Risk Matrix
| Change | Risk | Impact | Priority |
|--------|------|--------|----------|
| Enable existing tests | LOW | HIGH | P1 |
| Fix datetime warnings | LOW | HIGH | P1 |
| Fix SQLAlchemy warnings | LOW | MEDIUM | P2 |
| Add campaign tests | MEDIUM | CRITICAL | P1 |
| Add webhook tests | MEDIUM | CRITICAL | P1 |
| Update Flask-Session | MEDIUM | LOW | P3 |

---

**Last Updated**: November 23, 2024
**Target Completion**: January 2025
**Owner**: Development Team