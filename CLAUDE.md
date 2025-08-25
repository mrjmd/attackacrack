# CLAUDE_ENHANCED.md - Attack-a-Crack CRM Development Guide with Advanced Sub-Agent System

## 🎉 PHASE 2 FOUNDATION COMPLETE - August 17, 2025
**MAJOR MILESTONE: 30/64 tasks completed (47% of Phase 2)**

### ✅ Enhanced Dependency Injection & Repository Pattern System
- **ServiceRegistryEnhanced**: State-of-the-art dependency injection with lazy loading, sophisticated factory pattern and lifecycle management
  - **Thread-safe initialization** with circular dependency detection and validation
  - **Service tagging** by type (external, api, sms, accounting, etc.)
  - **Production optimization** with critical service warmup capabilities
  - **Zero dependency validation errors** - complete dependency graph resolution

- **Repository Pattern Implementation**: Complete data abstraction layer
  - **BaseRepository interface** with standardized CRUD operations and advanced querying
  - **Complete database abstraction** - no direct SQLAlchemy queries in services
  - **Result pattern integration** for standardized error handling

- **Clean Architecture Achieved**: Perfect separation of concerns
  - **Routes**: Handle HTTP requests/responses only, use `current_app.services.get()`
  - **Services**: Business logic with dependency injection, use repository pattern
  - **Repositories**: Data access layer with standardized interfaces
  - **Database**: SQLAlchemy models accessed only through repositories

## 🚨 CRITICAL: Test-Driven Development with appropriate subagents is MANDATORY

**ENFORCEMENT RULES:**
1. **ALWAYS** have test subagent write tests BEFORE implementation - NO EXCEPTIONS
2. Tests MUST fail initially (Red phase) with meaningful error messages
3. Then have appropriate subagent write MINIMAL code to make tests pass (Green phase)
4. Refactor only after tests are green (Refactor phase)
5. **NEVER** modify tests to match implementation - fix the implementation instead
6. **ALWAYS** make sure ALL tests are passing before declaring a phase of work complete

**TDD WORKFLOW:**
```bash
# 1. Write the test
docker-compose exec web pytest tests/test_new_feature.py -xvs  # Should FAIL

# 2. Implement minimal code
# ... only write enough to pass the test ...

# 3. Verify test passes
docker-compose exec web pytest tests/test_new_feature.py -xvs  # Should PASS

# 4. Refactor if needed (tests stay green)
docker-compose exec web pytest tests/  # All tests should PASS
```

## 📁 Project Structure & Context Preservation

### Critical Files for Context
When starting ANY task, read these files first:
- `app.py` - Service Registry and application setup
- `config.py` - Configuration management
- `crm_database.py` - All database models
- `services/__init__.py` - Service initialization patterns
- Current route file being modified
- Related test files

### Service Registry Pattern (MUST FOLLOW)
```python
# CORRECT - Using service registry
def some_route():
    contact_service = current_app.services.get('contact')
    result = contact_service.get_all_contacts()
    
# WRONG - Direct instantiation
def some_route():
    contact_service = ContactService(db.session)  # NEVER DO THIS
```

### Repository Pattern (Phase 2 Implementation)
```python
# Future state - ALL database access through repositories
class ContactRepository(BaseRepository):
    def find_by_phone(self, phone: str) -> Optional[Contact]:
        return self.query(Contact).filter_by(phone=phone).first()

class ContactService:
    def __init__(self, repository: ContactRepository):
        self.repository = repository  # Injected, not created
```

## 🧪 Testing Standards

### Coverage Requirements
- **Target**: 95% coverage for all new code
- **Minimum**: 90% overall coverage
- **Critical paths**: 100% coverage required

### Test Organization
```python
# tests/test_services/test_contact_service.py
class TestContactService:
    def test_create_contact(self, contact_service, db_session):
        """Test contact creation with valid data"""
        # Arrange
        data = {"phone": "+11234567890", "name": "Test User"}
        
        # Act
        contact = contact_service.create_contact(data)
        
        # Assert
        assert contact.phone == "+11234567890"
        assert contact.name == "Test User"
        
    def test_create_contact_duplicate_phone(self, contact_service):
        """Test that duplicate phone numbers are handled correctly"""
        # Test the error case
```

### Testing Commands
```bash
# Run all tests with coverage
docker-compose exec web pytest --cov --cov-report=term-missing

# Run specific test file
docker-compose exec web pytest tests/test_contact_service.py -xvs

# Run tests matching pattern
docker-compose exec web pytest -k "test_create" -xvs

# Generate HTML coverage report
docker-compose exec web pytest --cov --cov-report=html
```

## 🔄 Git Workflow with Context Preservation

### Commit Strategy for Continuity
```bash
# After completing a feature/fix
git add .
git commit -m "Complete: [Feature description]

Context for next session:
- Tests written: [list test files]
- Services modified: [list services]
- Next steps: [what should be done next]

🤖 Generated with Claude Code

Co-Authored-By: Claude <noreply@anthropic.com>"
```

## 📊 Dashboard & Activity Tracking

### Real-time Documentation Requirements
When implementing ANY feature:
1. Update relevant service docstrings
2. Add inline comments for complex logic
3. Update CHANGELOG.md with feature/fix
4. Ensure README reflects new capabilities

### Progress Tracking

#### Automatic Todo Persistence with Archive System
**Intelligent todo management that prevents bloat while preserving history:**

##### Archive-Based System
```
.claude/todos/
├── current.md          # Symlink to active session
├── archive/           # Historical sessions by month
│   └── 2025-08/      # Monthly organization
│       ├── session-2025-08-17-0930.md
│       └── session-2025-08-17-1445.md
└── summary.md         # Cumulative completed tasks
```

##### Three-Tier Todo System

1. **`.claude/todos/current.md`** (Active Session)
   - Auto-created at session start
   - Updated after EVERY TodoWrite
   - Includes full context for recovery
   - Symlink to actual session file in archive

2. **`.claude/todos/archive/`** (Historical Record)
   - Each session preserved separately
   - Organized by month (YYYY-MM)
   - Auto-cleanup after 3 months
   - Searchable history of all work

3. **`TODO.md`** (Project Roadmap)
   - Weekly priorities and sprints
   - Long-term goals
   - Manually updated milestones

##### Benefits
- **No Bloat**: Each session is a separate file
- **Full History**: Can review any past session
- **Auto-Cleanup**: Old sessions removed after 3 months
- **Easy Recovery**: current.md always has active session
- **Searchable**: grep through archive for past work

#### Recovery After Interruption
```bash
# If session is interrupted or context squashed:
1. Read .claude/session-todos.md
2. Check "🔍 Context for Recovery" section
3. Resume from "Working On" status
4. Continue with "In Progress" items
5. Run commands from "Commands to Resume"
```

#### Todo Workflow
```bash
# Starting a task
1. TodoWrite creates in-memory todos
2. Automatically saved to .claude/session-todos.md
3. File includes timestamp and context

# During work
- Each status change triggers auto-save
- Session notes capture decisions
- Modified files are tracked

# After interruption
- New session reads .claude/session-todos.md
- Continues exactly where left off
- No manual tracking needed
```

## 🛡️ Security & Best Practices

### Environment Variables
```python
# ALWAYS use environment variables for secrets
api_key = os.environ.get('OPENPHONE_API_KEY')
if not api_key:
    raise ValueError("OPENPHONE_API_KEY not set")

# NEVER hardcode secrets
api_key = "sk-abc123..."  # NEVER DO THIS
```

### Input Validation
```python
# ALWAYS validate user input
def create_contact(self, data: dict) -> Contact:
    # Validate required fields
    if not data.get('phone'):
        raise ValueError("Phone number is required")
    
    # Normalize phone number
    phone = self.normalize_phone(data['phone'])
    
    # Validate phone format
    if not self.is_valid_phone(phone):
        raise ValueError(f"Invalid phone number: {phone}")
```

## 🔍 Debugging & Troubleshooting

### Standard Debug Process
1. Check logs: `docker-compose logs -f web`
2. Run specific test: `docker-compose exec web pytest tests/test_failing.py -xvs`
3. Interactive debugging: `import ipdb; ipdb.set_trace()`
4. Check database state: `docker-compose exec web flask shell`

### Celery Task Monitoring
```bash
# Check active tasks
docker-compose exec celery celery -A celery_worker.celery inspect active

# Monitor task queue
docker-compose exec celery celery -A celery_worker.celery events

# Purge all tasks (emergency)
docker-compose exec celery celery -A celery_worker.celery purge -f
```

## 📝 Documentation to Maintain

### Always Update These Files
1. `docs/API.md` - New endpoints
2. `docs/ARCHITECTURE.md` - Design decisions
3. Service docstrings - Method documentation
4. Test docstrings - What's being tested

### Session Handoff Template
```markdown
## Session Summary - [Date]

### Completed
- [List completed tasks]

### In Progress  
- [Current task and status]
- [Files currently being modified]

### Next Steps
- [Immediate next task]
- [Any blockers or dependencies]

### Context for Next Session
- [Key decisions made]
- [Important code locations]
- [Any pending questions]
```

---

*Last Updated: August 25, 2025*
*Version: 2.0 - Enhanced with Sub-Agent Integration*