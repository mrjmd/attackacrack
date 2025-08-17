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
| W1-07 | Create BaseRepository interface | 🔵 TODO | 2h | - | None | Abstract base class |
| W1-08 | Implement ContactRepository | 🔵 TODO | 4h | - | W1-07 | All Contact queries |
| W1-09 | Implement CampaignRepository | 🔵 TODO | 4h | - | W1-07 | All Campaign queries |
| W1-10 | Refactor ContactService to use ContactRepository | 🔵 TODO | 3h | - | W1-08 | Update all methods |
| W1-11 | Refactor CampaignService to use CampaignRepository | 🔵 TODO | 3h | - | W1-09 | Update all methods |

### Friday: Standardization
| ID | Task | Status | Est. Hours | Assignee | Dependencies | Notes |
|----|------|--------|------------|----------|--------------|-------|
| W1-12 | Implement Result pattern class | 🔵 TODO | 2h | - | None | services/common/result.py |
| W1-13 | Update AuthService to use Result pattern | 🔵 TODO | 2h | - | W1-12 | Already uses tuples |
| W1-14 | Update ContactService to use Result pattern | 🔵 TODO | 2h | - | W1-12 | High-priority service |
| W1-15 | Archive obsolete scripts | 🔵 TODO | 1h | - | None | Create scripts/archive/ |
| W1-16 | Consolidate documentation | 🔵 TODO | 1h | - | None | Move to docs/ |

## Week 2: Test Infrastructure (40 hours total)

### Monday: Test Restructuring
| ID | Task | Status | Est. Hours | Assignee | Dependencies | Notes |
|----|------|--------|------------|----------|--------------|-------|
| W2-01 | Create new test directory structure | 🔵 TODO | 1h | - | None | unit/, integration/, e2e/ |
| W2-02 | Move existing tests to appropriate directories | 🔵 TODO | 2h | - | W2-01 | Maintain git history |
| W2-03 | Create BaseFactory class | 🔵 TODO | 2h | - | None | With Faker integration |
| W2-04 | Implement ContactFactory | 🔵 TODO | 2h | - | W2-03 | Test data generation |
| W2-05 | Implement CampaignFactory | 🔵 TODO | 1h | - | W2-03 | Test data generation |

### Tuesday-Wednesday: CSV Import Service Tests
| ID | Task | Status | Est. Hours | Assignee | Dependencies | Notes |
|----|------|--------|------------|----------|--------------|-------|
| W2-06 | Unit tests for detect_format | 🔵 TODO | 3h | - | W2-04 | All 10+ formats |
| W2-07 | Unit tests for normalize_phone | 🔵 TODO | 2h | - | None | Edge cases |
| W2-08 | Unit tests for _enrich_contact | 🔵 TODO | 3h | - | W2-04 | Merge logic |
| W2-09 | Integration test for full import flow | 🔵 TODO | 4h | - | W2-04, W2-05 | With temp CSV |
| W2-10 | Performance test for 1000+ contacts | 🔵 TODO | 2h | - | W2-09 | Benchmark |
| W2-11 | Test duplicate handling | 🔵 TODO | 2h | - | W2-04 | Various scenarios |

### Thursday-Friday: Campaign Service Tests
| ID | Task | Status | Est. Hours | Assignee | Dependencies | Notes |
|----|------|--------|------------|----------|--------------|-------|
| W2-12 | Unit tests for _should_skip_send | 🔵 TODO | 3h | - | W2-04 | All compliance rules |
| W2-13 | Unit tests for A/B test winner logic | 🔵 TODO | 3h | - | W2-05 | Statistical tests |
| W2-14 | Unit tests for audience filtering | 🔵 TODO | 3h | - | W2-04 | Complex queries |
| W2-15 | Integration test for campaign lifecycle | 🔵 TODO | 4h | - | W2-04, W2-05 | Create to send |
| W2-16 | Mock OpenPhoneService for tests | 🔵 TODO | 3h | - | None | Prevent API calls |

## Week 3: Coverage Expansion (40 hours total)

### Monday-Tuesday: Webhook Service Testing
| ID | Task | Status | Est. Hours | Assignee | Dependencies | Notes |
|----|------|--------|------------|----------|--------------|-------|
| W3-01 | Test all message event types | 🔵 TODO | 4h | - | W2-04 | message.* events |
| W3-02 | Test all call event types | 🔵 TODO | 4h | - | W2-04 | call.* events |
| W3-03 | Test idempotency handling | 🔵 TODO | 2h | - | None | Duplicate events |
| W3-04 | Test signature verification | 🔵 TODO | 2h | - | None | Security critical |
| W3-05 | Test malformed payloads | 🔵 TODO | 2h | - | None | Error handling |
| W3-06 | Test out-of-order events | 🔵 TODO | 2h | - | None | Resilience |

### Wednesday-Thursday: Auth Testing
| ID | Task | Status | Est. Hours | Assignee | Dependencies | Notes |
|----|------|--------|------------|----------|--------------|-------|
| W3-07 | Audit all routes for @login_required | 🔵 TODO | 3h | - | None | Programmatic check |
| W3-08 | Test admin-only routes | 🔵 TODO | 3h | - | None | Role enforcement |
| W3-09 | Test session management | 🔵 TODO | 3h | - | None | Multi-worker |
| W3-10 | Test token expiration | 🔵 TODO | 2h | - | None | InviteToken |
| W3-11 | Test password requirements | 🔵 TODO | 2h | - | None | Validation |
| W3-12 | Test QuickBooks OAuth flow | 🔵 TODO | 3h | - | None | Mock external |

### Friday: Critical Path E2E
| ID | Task | Status | Est. Hours | Assignee | Dependencies | Notes |
|----|------|--------|------------|----------|--------------|-------|
| W3-13 | E2E test: CSV import to campaign | 🔵 TODO | 3h | - | W2-04, W2-05 | Full flow |
| W3-14 | E2E test: Campaign create to send | 🔵 TODO | 3h | - | W2-05 | With tracking |
| W3-15 | E2E test: Webhook to data update | 🔵 TODO | 2h | - | W3-01 | Real-time sync |

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
- **Completed**: 0
- **In Progress**: 0
- **Blocked**: 0
- **Completion**: 0%

### Week Progress
- Week 1: 0/16 tasks (0%)
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