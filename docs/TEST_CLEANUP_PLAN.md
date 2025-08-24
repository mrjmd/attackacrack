# Test Suite Cleanup & Coverage Improvement Plan

## Executive Summary
Current State: 1999 tests passing, 11 skipped, 474 warnings, ~18% coverage
Target State: 0 skipped (where appropriate), <50 warnings, 85% coverage

---

## Phase 1: Enable Skipped Tests (1-2 days)

### Immediate Enables (8 tests)
These tests can be enabled RIGHT NOW as functionality exists:

1. **A/B Testing Variant Assignment** (`test_campaign_service.py:422`)
   - Enable and verify test passes
   
2. **A/B Testing Stats** (2 tests at lines 443, 504)
   - Update to use `get_variant_metrics` method
   
3. **Daily Limit Enforcement** (2 tests at lines 586, 616)
   - Enable - functionality fully implemented
   
4. **Context Personalization** (`test_campaign_service.py:649`)
   - Enable - `_personalize_message` exists
   
5. **Campaign Bounce Info** (`test_campaign_repository_sms_metrics_enhancement.py:167`)
   - Enable - `update_membership_with_bounce_info` exists

### Tests Needing Updates (3 tests)
1. **Service File Path** - Update to point to `campaign_service_refactored.py`
2. **Personalization Context** - Update test to match method signature
3. **A/B get_remaining_recipients** - Update to use existing methods

### Tests to Remove (3 tests)
1. **Auth Service init_app tests** (2) - Method doesn't exist in refactored service
2. **Job Service backward compatibility** - Intentionally removed

### Keep Skipped (2 tests)
1. **min_days_since_contact filter** - Feature not implemented
2. **Repository pattern migration** - Part of Phase 2

---

## Phase 2: Eliminate Warnings (2-3 days)

### Priority 1: datetime.utcnow() Warnings (399 occurrences - 84% of all warnings)

**Solution**: Global find/replace with timezone-aware datetime
```python
# OLD
from datetime import datetime
timestamp = datetime.utcnow()

# NEW  
from datetime import datetime, timezone
timestamp = datetime.now(timezone.utc)
```

**Files to Update** (Top Priority):
- `repositories/*.py` - 87 occurrences
- `services/*.py` - 62 occurrences
- `tests/**/*.py` - 250+ occurrences

**Implementation Steps**:
1. Create utility function in `utils/datetime_utils.py`
2. Run automated replacement script
3. Test thoroughly (no functional changes expected)

### Priority 2: SQLAlchemy Query.get() (35 occurrences - 7% of warnings)

**Solution**: Replace with session.get()
```python
# OLD
user = User.query.get(user_id)

# NEW
user = db.session.get(User, user_id)
```

**Key Files**:
- `app.py:466` - User loader
- Test files with direct query usage
- Documentation examples

### Priority 3: Flask-Session Config (4 occurrences - 1% of warnings)

**Solution**: Update config.py to use new Flask-Session patterns
- Review Flask-Session 0.8.0 migration guide
- Update SESSION_FILE_DIR to SESSION_CACHELIB
- Test session functionality thoroughly

---

## Phase 3: Achieve 85% Test Coverage (4-6 weeks)

### Current Coverage Baseline
- **Overall**: ~18% (2,285/12,488 lines)
- **Critical Gap**: Campaign system (0%), OpenPhone webhooks (13%)

### Week 1-2: Critical Business Paths (Target: 45% coverage)

#### Campaign System (0% → 95%)
**Files**: 
- `services/campaign_service_refactored.py`
- `routes/campaigns.py`

**Tests Needed**:
- Campaign creation validation
- Message generation and personalization
- A/B test variant assignment
- Daily limit enforcement
- Error handling and rollback

#### OpenPhone Integration (29% → 90%)
**Files**:
- `services/openphone_webhook_service_refactored.py`
- `services/openphone_service.py`

**Tests Needed**:
- Webhook signature verification
- Message receipt processing
- SMS sending with retries
- Error scenarios

### Week 3-4: Core Services (Target: 65% coverage)

#### Contact Management (14% → 85%)
**Files**:
- `services/contact_service_refactored.py`
- `routes/contact_routes.py`

**Tests Needed**:
- CRUD operations
- Phone validation
- Duplicate detection
- CSV import

#### Authentication (15% → 85%)
**Files**:
- `services/auth_service_refactored.py`
- `routes/auth.py`

**Tests Needed**:
- Login/logout flow
- Session management
- Permission checks
- Password validation

### Week 5-6: Repository Layer & Integration (Target: 85% coverage)

#### Repository Pattern (varies → 80%)
**Focus**: All repositories with <50% coverage

**Tests Needed**:
- CRUD operations
- Complex queries
- Transaction handling
- Constraint validation

#### End-to-End Workflows
**Critical Paths**:
1. Campaign creation → sending → tracking
2. Contact import → campaign assignment → message delivery
3. Webhook receipt → contact update → response

---

## CI/CD Coverage Enforcement

### Update pytest.ini
```ini
[pytest]
addopts = 
    --cov
    --cov-report=term-missing
    --cov-report=html
    --cov-fail-under=85
```

### Update GitHub Actions
```yaml
- name: Run tests with coverage
  run: |
    docker-compose exec -T web python -m pytest \
      --cov --cov-fail-under=85 --cov-report=xml
    
- name: Upload coverage
  uses: codecov/codecov-action@v3
```

### Coverage Exclusions (.coveragerc)
```ini
[run]
omit = 
    */tests/*
    */migrations/*
    */venv/*
    scripts/*
    */__pycache__/*

[report]
fail_under = 85
exclude_lines =
    pragma: no cover
    raise NotImplementedError
    if TYPE_CHECKING:
```

---

## Success Metrics & Timeline

### Phase 1 (Days 1-2)
- [ ] 8 skipped tests enabled
- [ ] 3 obsolete tests removed
- [ ] 3 tests updated to match implementation

### Phase 2 (Days 3-5)
- [ ] datetime warnings reduced from 399 to 0
- [ ] SQLAlchemy warnings reduced from 35 to 0
- [ ] Total warnings <50 (90% reduction)

### Phase 3 (Weeks 2-6)
- [ ] Week 2: 45% coverage (critical paths)
- [ ] Week 4: 65% coverage (core services)
- [ ] Week 6: 85% coverage (full suite)

### Final State
- **Tests**: 2000+ passing, 0-2 appropriately skipped
- **Warnings**: <50 (from 474)
- **Coverage**: 85% enforced in CI/CD
- **Quality Gates**: No PR merged that reduces coverage

---

## Risk Mitigation

### Low Risk Changes
- datetime.utcnow() replacement (no functional change)
- Enabling tests for existing functionality
- Removing obsolete tests

### Medium Risk Changes
- SQLAlchemy query updates (minimal functional change)
- Flask-Session config updates (affects session handling)

### Testing Strategy
1. Make changes in small batches
2. Run full test suite after each batch
3. Deploy to staging before production
4. Monitor error rates post-deployment

---

## Resource Requirements

### Development Effort
- **Phase 1**: 1 developer, 2 days
- **Phase 2**: 1 developer, 3 days
- **Phase 3**: 1-2 developers, 4-6 weeks

### Total Timeline
- **Quick Wins** (Phase 1-2): 1 week
- **Full Coverage** (Phase 3): 6 weeks
- **Total**: 7 weeks to achieve all goals

### Tools Needed
- Coverage.py for reporting
- pytest-cov for integration
- Factory Boy for test data
- Codecov for tracking (optional)

---

## Appendix: Detailed File Lists

### Files with Most datetime.utcnow() Warnings
1. `repositories/activity_repository.py` - 15 occurrences
2. `services/auth_service_refactored.py` - 8 occurrences
3. `repositories/ab_test_result_repository.py` - 7 occurrences
4. `services/campaign_template_service.py` - 6 occurrences
5. `repositories/invite_token_repository.py` - 5 occurrences

### Critical Untested Services
1. `services/campaign_service_refactored.py` - 0% coverage
2. `services/ab_testing_service.py` - 0% coverage
3. `services/csv_import_service.py` - 0% coverage
4. `services/quickbooks_service.py` - 0% coverage
5. `services/ai_service.py` - 0% coverage

### Test Files to Re-enable
1. `tests/test_webhook_integrity.py.disabled`
2. `tests/test_campaign_integration.py.disabled`