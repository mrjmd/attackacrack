# Phase 2 Revised Plan: Service Refactoring + Testing Infrastructure

## Overview
This document integrates the service refactoring needs identified in the Week 1 audit with the original Phase 2 testing infrastructure plan. We now have a 4-week plan instead of the original 3 weeks.

## Week 1 ✅ COMPLETE
- Repository Pattern implementation
- Result Pattern implementation  
- Service Registry with DI
- Refactored 4 core services
- 16/16 tasks complete

## Week 2: Service Refactoring Sprint (NEW - Based on Audit)

### Goals
- Complete refactoring of ALL remaining services
- Achieve 100% consistency across codebase
- Zero direct DB queries outside repositories

### Tasks
**Monday: Create Missing Repositories (10 hours)**
- ActivityRepository
- ConversationRepository  
- AppointmentRepository
- InvoiceRepository
- QuoteRepository
- QuickBooksCustomerRepository
- WebhookEventRepository
- TodoRepository

**Tuesday: Clean Up & External APIs (8 hours)**
- Delete duplicate service files
- Merge app_enhanced.py improvements
- Fix TODOs in refactored services
- Ensure external services are injectable

**Wednesday-Friday: Refactor Critical Services (22 hours)**
- DashboardService (most complex - 8 hours)
- QuickBooksSyncService (4 hours)
- OpenPhoneWebhookService (4 hours)
- InvoiceService (3 hours)
- MessageService (3 hours)

## Week 3: Complete Service Refactoring + Test Infrastructure (ORIGINAL Week 2)

### Monday-Tuesday: Final Service Refactoring (16 hours)
- TodoService refactoring
- Result pattern for all services
- Final audit of all services
- Update app.py registrations

### Wednesday-Friday: Test Infrastructure Setup (24 hours)
**This is from the ORIGINAL Phase 2 plan:**
- Create test directory structure (unit/, integration/, e2e/)
- Move existing tests to appropriate directories
- Create BaseFactory class with Faker
- Implement ContactFactory, CampaignFactory
- Create test data builders for all models

## Week 4: Comprehensive Testing (ORIGINAL Week 2-3 content)

### Monday-Wednesday: Service Testing (24 hours)
**CSV Import Service Tests (highest risk):**
- Unit tests for detect_format (all 10+ formats)
- Unit tests for normalize_phone
- Unit tests for _enrich_contact
- Integration test for full import flow
- Performance test for 1000+ contacts
- Test duplicate handling

**Campaign Service Tests:**
- Unit tests for _should_skip_send
- Unit tests for A/B test winner logic
- Unit tests for audience filtering
- Integration test for campaign lifecycle
- Mock OpenPhoneService

### Thursday-Friday: Critical Path Testing (16 hours)
**Webhook Service Testing:**
- Test all message event types
- Test all call event types
- Test idempotency handling
- Test signature verification

**Auth Testing:**
- Audit all routes for @login_required
- Test admin-only routes
- Test session management

## Week 5: Final Testing & Performance (ORIGINAL Week 4)

### Monday-Tuesday: E2E Testing (16 hours)
- CSV import to campaign flow
- Campaign create to send flow
- Webhook to data update flow
- User registration to first action

### Wednesday: Performance Testing (8 hours)
- Setup pytest-benchmark
- Benchmark CSV import (10k contacts)
- Benchmark campaign send (1k recipients)
- Benchmark dashboard load
- Database query optimization

### Thursday-Friday: Documentation & Deployment (16 hours)
- Create ARCHITECTURE.md
- Create TESTING.md
- Update API.md
- Code coverage report (target 95%)
- Performance baseline report
- Deploy to staging

## Success Metrics

### Service Refactoring (End of Week 2)
- ✅ Zero direct DB queries outside repositories
- ✅ All services use Repository pattern
- ✅ All services use Result pattern
- ✅ All services use Dependency Injection
- ✅ No internal service instantiation
- ✅ No static methods in services

### Testing Infrastructure (End of Week 5)
- ✅ 95% test coverage
- ✅ All critical paths have E2E tests
- ✅ Performance benchmarks established
- ✅ Test data factories for all models
- ✅ Separated unit/integration/e2e tests

## Critical Path

The most critical items that block other work:
1. **Week 2 Monday**: Create repositories (blocks all service refactoring)
2. **Week 2 Wednesday**: Refactor DashboardService (blocks dashboard functionality)
3. **Week 3 Wednesday**: Test infrastructure setup (blocks all testing work)
4. **Week 4 Monday**: CSV Import tests (highest risk feature)

## Resource Requirements

- **Total Hours**: 160 hours (4 weeks × 40 hours)
- **Original Plan**: 120 hours (3 weeks)
- **Additional Time**: 40 hours for service refactoring
- **Risk Buffer**: 10% (16 hours) included in estimates

## Notes

1. The original Phase 2 testing plan is PRESERVED and moved to Weeks 3-5
2. Week 2 is INSERT to handle the service refactoring debt discovered in audit
3. This ensures we have a clean, consistent codebase BEFORE writing tests
4. All original test coverage goals remain intact
5. Timeline extended by 1 week to maintain quality

---

*Created: January 17, 2025*
*Combines service refactoring needs with original testing plan*
*Estimated completion: End of Week 5 (instead of Week 4)*