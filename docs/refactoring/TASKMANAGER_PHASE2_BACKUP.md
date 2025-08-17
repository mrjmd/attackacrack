# Task Manager - Phase 2: Codebase Hardening & TDD

## Overview
This document tracks all tasks for Phase 2 of the refactoring project. Each task has an ID, status, estimated hours, and dependencies.

## Task Status Legend
- 🔵 TODO - Not started
- 🟡 IN_PROGRESS - Currently being worked on
- ✅ DONE - Completed
- 🔴 BLOCKED - Waiting on dependencies
- ⏸️ PAUSED - Temporarily on hold

## Week 1: Foundation (40 hours total)

### Monday-Tuesday: Complete Dependency Injection
| ID | Task | Status | Est. Hours | Assignee | Dependencies | Notes |
|----|------|--------|------------|----------|--------------|-------|
| W1-01 | Audit all services for internal dependencies | ✅ DONE | 2h | Claude | None | Created SERVICE_DEPENDENCY_AUDIT.md |
| W1-02 | Create GoogleCalendarService | ✅ DONE | 3h | Claude | W1-01 | Extracted with 8 methods, 18 tests |
| W1-03 | Create EmailService abstraction | ✅ DONE | 2h | Claude | W1-01 | Created with 11 methods, 24 tests |
| W1-04 | Refactor AppointmentService to accept GoogleCalendarService | ✅ DONE | 2h | Claude | W1-02 | Expanded to 19 methods, 24 tests |
| W1-05 | Implement lazy loading in ServiceRegistry | ✅ DONE | 3h | Claude | None | Enhanced registry with 25 tests |
| W1-06 | Update app.py with proper service initialization order | ✅ DONE | 4h | Claude | W1-01 to W1-05 | Created app_enhanced.py |

### Wednesday-Thursday: Repository Pattern Implementation
| ID | Task | Status | Est. Hours | Assignee | Dependencies | Notes |
|----|------|--------|------------|----------|--------------|-------|
| W1-07 | Create BaseRepository interface | ✅ DONE | 2h | Claude | None | Abstract base class |
| W1-08 | Implement ContactRepository | ✅ DONE | 4h | Claude | W1-07 | All Contact queries |
| W1-09 | Implement CampaignRepository | ✅ DONE | 4h | Claude | W1-07 | All Campaign queries |
| W1-10 | Refactor ContactService to use ContactRepository | ✅ DONE | 3h | Claude | W1-08 | Update all methods |
| W1-11 | Refactor CampaignService to use CampaignRepository | ✅ DONE | 3h | Claude | W1-09 | Tests written, 10 tests passing |

### Friday: Standardization
| ID | Task | Status | Est. Hours | Assignee | Dependencies | Notes |
|----|------|--------|------------|----------|--------------|-------|
| W1-12 | Implement Result pattern class | ✅ DONE | 2h | Claude | None | Created with 16 tests |
| W1-13 | Update AuthService to use Result pattern | ✅ DONE | 2h | Claude | W1-12 | Refactored with 18 tests |
| W1-14 | Update ContactService to use Result pattern | ✅ DONE | 2h | Claude | W1-12 | Created with 19 tests |
| W1-15 | Archive obsolete scripts | ✅ DONE | 1h | Claude | None | Archived 11 scripts |
| W1-16 | Consolidate documentation | ✅ DONE | 1h | Claude | None | Organized into categories |

## Week 2: Complex Services & Infrastructure (40 hours total)

### Monday: Create Missing Repositories
| ID | Task | Status | Est. Hours | Assignee | Dependencies | Notes |
|----|------|--------|------------|----------|--------------|-------|
| W2-01 | Create ActivityRepository | 🔵 TODO | 2h | - | None | For Activity model |
| W2-02 | Create ConversationRepository | 🔵 TODO | 2h | - | None | For Conversation model |
| W2-03 | Create AppointmentRepository | 🔵 TODO | 1h | - | None | For Appointment model |
| W2-04 | Create InvoiceRepository | 🔵 TODO | 1h | - | None | For Invoice model |
| W2-05 | Create QuoteRepository | 🔵 TODO | 1h | - | None | For Quote model |
| W2-06 | Create QuickBooksCustomerRepository | 🔵 TODO | 1h | - | None | For QB Customer |
| W2-07 | Create WebhookEventRepository | 🔵 TODO | 1h | - | None | For WebhookEvent |
| W2-08 | Create TodoRepository | 🔵 TODO | 1h | - | None | For Todo model |

### Tuesday: Clean Up Duplicates & External APIs
| ID | Task | Status | Est. Hours | Assignee | Dependencies | Notes |
|----|------|--------|------------|----------|--------------|-------|
| W2-09 | Delete contact_service_refactored.py | 🔵 TODO | 0.5h | - | None | Keep contact_service_result.py |
| W2-10 | Delete old appointment_service.py | 🔵 TODO | 0.5h | - | None | Keep refactored version |
| W2-11 | Merge app_enhanced.py into app.py | 🔵 TODO | 2h | - | None | Consolidate improvements |
| W2-12 | Fix TODO in appointment_service_refactored | 🔵 TODO | 1h | - | None | Default attendee config |
| W2-13 | Ensure GoogleCalendarService complete | 🔵 TODO | 2h | - | None | Verify all methods |
| W2-14 | Ensure QuickBooksService injectable | 🔵 TODO | 2h | - | None | Remove global state |

### Wednesday-Friday: Refactor High-Priority Services
| ID | Task | Status | Est. Hours | Assignee | Dependencies | Notes |
|----|------|--------|------------|----------|--------------|-------|
| W2-15 | Refactor DashboardService | 🔵 TODO | 8h | - | W2-01, W2-02 | Most complex service |
| W2-16 | Add Result pattern to DashboardService | 🔵 TODO | 2h | - | W2-15 | Consistent returns |
| W2-17 | Refactor QuickBooksSyncService | 🔵 TODO | 4h | - | W2-06, W2-14 | Remove instantiation |
| W2-18 | Add Result pattern to QuickBooksSyncService | 🔵 TODO | 2h | - | W2-17 | Consistent returns |
| W2-19 | Write tests for DashboardService | 🔵 TODO | 4h | - | W2-15, W2-16 | Critical service |
| W2-20 | Write tests for QuickBooksSyncService | 🔵 TODO | 2h | - | W2-17, W2-18 | Integration tests |

## Week 3: Remaining Services & Final Testing (40 hours total)

### Monday-Wednesday: Refactor Medium-Priority Services
| ID | Task | Status | Est. Hours | Assignee | Dependencies | Notes |
|----|------|--------|------------|----------|--------------|-------|
| W3-01 | Refactor InvoiceService | 🔵 TODO | 3h | - | W2-04, W2-05 | Remove static methods |
| W3-02 | Add Result pattern to InvoiceService | 🔵 TODO | 2h | - | W3-01 | Consistent returns |
| W3-03 | Refactor OpenPhoneWebhookService | 🔵 TODO | 4h | - | W2-07 | Inject SMSMetricsService |
| W3-04 | Add Result pattern to WebhookService | 🔵 TODO | 2h | - | W3-03 | Consistent returns |
| W3-05 | Refactor MessageService | 🔵 TODO | 3h | - | W2-01, W2-02 | Use repositories |
| W3-06 | Add Result pattern to MessageService | 🔵 TODO | 2h | - | W3-05 | Consistent returns |
| W3-07 | Refactor TodoService | 🔵 TODO | 2h | - | W2-08 | Simple refactor |
| W3-08 | Add Result pattern to TodoService | 🔵 TODO | 1h | - | W3-07 | Consistent returns |
| W3-09 | Write tests for all refactored services | 🔵 TODO | 6h | - | W3-01 to W3-08 | Comprehensive tests |

### Thursday: Final Audit & Verification
| ID | Task | Status | Est. Hours | Assignee | Dependencies | Notes |
|----|------|--------|------------|----------|--------------|-------|
| W3-10 | Audit: Zero direct DB queries | 🔵 TODO | 2h | - | All refactors | grep verification |
| W3-11 | Audit: All services use DI | 🔵 TODO | 2h | - | All refactors | Check constructors |
| W3-12 | Update app.py service registration | 🔵 TODO | 2h | - | All refactors | Register all services |
| W3-13 | Verify all routes use refactored services | 🔵 TODO | 2h | - | W3-12 | Update imports |

### Friday: Begin Comprehensive Testing
| ID | Task | Status | Est. Hours | Assignee | Dependencies | Notes |
|----|------|--------|------------|----------|--------------|-------|
| W3-14 | Test CSVImportService (highest risk) | 🔵 TODO | 4h | - | None | Critical functionality |
| W3-15 | Create test data factories | 🔵 TODO | 2h | - | None | For all models |
| W3-16 | Run coverage report | 🔵 TODO | 2h | - | All tests | Target 95% |

## Week 4: Performance & Polish (40 hours total)

### Monday-Tuesday: Performance Testing
| ID | Task | Status | Est. Hours | Assignee | Dependencies | Notes |
|----|------|--------|------------|----------|--------------|-------|
| W4-01 | Setup pytest-benchmark | 🔵 TODO | 2h | - | None | Performance framework |
| W4-02 | Benchmark CSV import (10k contacts) | 🔵 TODO | 3h | - | W4-01, W2-09 | < 30 sec target |
| W4-03 | Benchmark campaign send (1k recipients) | 🔵 TODO | 3h | - | W4-01, W2-15 | < 10 sec target |
| W4-04 | Benchmark dashboard load | 🔵 TODO | 3h | - | W4-01 | < 2 sec target |
| W4-05 | Create performance regression tests | 🔵 TODO | 3h | - | W4-01 to W4-04 | CI/CD integration |
| W4-06 | Database query optimization | 🔵 TODO | 2h | - | W4-02 to W4-04 | Based on results |

### Wednesday: Documentation
| ID | Task | Status | Est. Hours | Assignee | Dependencies | Notes |
|----|------|--------|------------|----------|--------------|-------|
| W4-07 | Create docs/ARCHITECTURE.md | 🔵 TODO | 3h | - | Week 1-3 | System design |
| W4-08 | Create docs/TESTING.md | 🔵 TODO | 2h | - | Week 2-3 | Test strategy |
| W4-09 | Update docs/API.md | 🔵 TODO | 2h | - | Week 1 | Service interfaces |
| W4-10 | Archive old README files | 🔵 TODO | 1h | - | None | Consolidate |

### Thursday-Friday: Final Review
| ID | Task | Status | Est. Hours | Assignee | Dependencies | Notes |
|----|------|--------|------------|----------|--------------|-------|
| W4-11 | Code coverage report | 🔵 TODO | 2h | - | All tests | Generate report |
| W4-12 | Performance baseline report | 🔵 TODO | 2h | - | W4-01 to W4-06 | Document metrics |
| W4-13 | Update CLAUDE.md with Phase 2 completion | 🔵 TODO | 1h | - | All tasks | Victory lap! |
| W4-14 | Create Phase 3 planning document | 🔵 TODO | 3h | - | All tasks | Next steps |
| W4-15 | Team retrospective | 🔵 TODO | 2h | - | All tasks | Lessons learned |
| W4-16 | Deploy to staging for testing | 🔵 TODO | 2h | - | All tasks | Validation |

## Metrics Dashboard

### Overall Progress
- **Total Tasks**: 64
- **Completed**: 16
- **In Progress**: 0
- **Blocked**: 0
- **Paused**: 0
- **Completion**: 25%

### Week Progress
- Week 1: 16/16 tasks (100%) ✅
- Week 2: 0/16 tasks (0%)
- Week 3: 0/15 tasks (0%)
- Week 4: 0/16 tasks (0%)

### Test Coverage Progress
- Current: 75%
- Target: 95%
- Progress: 0%

### Critical Milestones
- [ ] Repository pattern implemented
- [ ] All services use DI
- [ ] Test infrastructure ready
- [ ] CSV Import Service 95% coverage
- [ ] Campaign Service 95% coverage
- [ ] All critical paths tested
- [ ] Performance benchmarks met

## Risk Register

| Risk | Probability | Impact | Mitigation | Status |
|------|------------|--------|------------|--------|
| Breaking production during refactor | Medium | High | Feature flags, gradual rollout | 🔵 OPEN |
| Test suite becomes too slow | Medium | Medium | Separate unit/integration tests | 🔵 OPEN |
| Merge conflicts with ongoing dev | High | Low | Small, frequent commits | 🔵 OPEN |
| Repository pattern adds complexity | Low | Medium | Clear documentation, examples | 🔵 OPEN |

## Notes and Decisions

### Architectural Decisions
- **2025-08-17**: Decided to implement Repository pattern for complete DB isolation
- **2025-08-17**: Chose Result pattern over exceptions for service returns
- **2025-08-17**: Will use Factory pattern with Faker for test data

### Blockers and Issues
- None yet

### Lessons Learned
- To be documented during retrospective

---

*Last Updated: August 17, 2025*
*Next Review: End of Week 1*