# Architecture and Testing Guidelines

## Overview

This document outlines the architectural patterns and testing strategies for the Attack-a-Crack CRM system. Our goal is to build a maintainable, testable, and scalable application using proven software engineering practices.

## Core Principles

### 1. Dependency Injection (DI)
Services should never instantiate their own dependencies. All dependencies must be passed in during initialization.

**❌ Bad:**
```python
class CampaignService:
    def __init__(self):
        self.openphone_service = OpenPhoneService()  # Creates its own dependency
```

**✅ Good:**
```python
class CampaignService:
    def __init__(self, openphone_service: OpenPhoneService):
        self.openphone_service = openphone_service  # Dependency injected
```

### 2. Separation of Concerns
Each layer has a specific responsibility:
- **Routes**: HTTP request/response handling, authentication, validation
- **Services**: Business logic, orchestration between components
- **Models**: Database schema and basic data operations
- **External Clients**: API integrations (OpenPhone, QuickBooks, etc.)

### 3. Explicit Over Implicit
Dependencies and data flow should be explicit and traceable. Avoid global state and hidden dependencies.

## Application Architecture

### Service Registry Pattern

All services are instantiated and managed centrally through a service registry attached to the Flask app.

```python
# app.py
def create_app():
    app = Flask(__name__)
    
    # Initialize services
    from services.registry import ServiceRegistry
    registry = ServiceRegistry()
    
    # Register services with their dependencies
    registry.register('contact', ContactService())
    registry.register('openphone', OpenPhoneService())
    registry.register('campaign', CampaignService(
        openphone_service=registry.get('openphone'),
        contact_service=registry.get('contact')
    ))
    
    app.services = registry
    return app
```

### Accessing Services in Routes

Routes access services through Flask's current_app context:

```python
from flask import current_app

@route_bp.route('/example')
def example_route():
    service = current_app.services.get('campaign')
    result = service.process_something()
    return jsonify(result)
```

### Service Layer Patterns

Services should follow these patterns:

1. **Data Access Methods**: Encapsulate all database queries
```python
class ContactService:
    def find_by_phone(self, phone: str) -> Optional[Contact]:
        """Data access method - encapsulates database query"""
        return Contact.query.filter_by(phone=phone).first()
    
    def create_contact(self, data: dict) -> Contact:
        """Business logic method - validates and creates contact"""
        # Validation logic here
        contact = Contact(**data)
        db.session.add(contact)
        db.session.commit()
        return contact
```

2. **External API Calls**: Isolated in dedicated service classes
```python
class OpenPhoneService:
    def send_sms(self, to: str, message: str) -> dict:
        """External API call - isolated and mockable"""
        response = requests.post(
            f"{self.base_url}/messages",
            json={"to": to, "text": message}
        )
        return response.json()
```

## Testing Strategy

### Testing Pyramid

We follow the testing pyramid approach:

```
         /\
        /E2E\        <- Minimal (5%)
       /------\
      /Integration\  <- Moderate (25%)
     /------------\
    /   Unit Tests  \ <- Extensive (70%)
   /----------------\
```

### Test Types and Conventions

#### 1. Unit Tests
**Purpose**: Test individual service methods in isolation

**Location**: `tests/unit/services/`

**Naming**: `test_<service>_unit.py`

**Characteristics**:
- Mock ALL external dependencies
- Test business logic only
- Should be extremely fast (<100ms per test)
- No database access
- No network calls

**Example**:
```python
# tests/unit/services/test_campaign_service_unit.py
def test_calculate_campaign_cost():
    # Arrange
    mock_openphone = Mock(spec=OpenPhoneService)
    service = CampaignService(openphone_service=mock_openphone)
    
    # Act
    cost = service.calculate_campaign_cost(recipient_count=100)
    
    # Assert
    assert cost == 5.00  # $0.05 per message
    mock_openphone.assert_not_called()  # Pure calculation, no API needed
```

#### 2. Integration Tests
**Purpose**: Test how components work together

**Location**: `tests/integration/`

**Naming**: `test_<feature>_integration.py`

**Characteristics**:
- Use real test database
- Test complete request flows
- Mock only external APIs
- Can be slower (1-5s per test)

**Example**:
```python
# tests/integration/test_campaign_integration.py
def test_create_campaign_flow(client, test_db):
    # Arrange - mock only external API
    with patch('services.openphone_service.OpenPhoneService.send_sms'):
        # Act - make real HTTP request
        response = client.post('/campaigns/create', json={
            'name': 'Test Campaign',
            'message': 'Hello {first_name}'
        })
        
        # Assert - verify database state
        assert response.status_code == 201
        campaign = Campaign.query.filter_by(name='Test Campaign').first()
        assert campaign is not None
        assert campaign.status == 'draft'
```

#### 3. End-to-End Tests
**Purpose**: Verify critical user journeys work completely

**Location**: `tests/e2e/`

**Naming**: `test_<journey>_e2e.py`

**Characteristics**:
- Test complete user workflows
- Use real services where possible
- Only mock unavoidable external systems
- Can be slow (5-30s per test)
- Should be minimal

### Mocking Strategy

#### What to Mock in Unit Tests:
- ✅ Database queries (mock the service's own data methods)
- ✅ Other services (injected dependencies)
- ✅ External API clients
- ✅ Time/datetime for deterministic tests
- ✅ File system operations

#### What to Mock in Integration Tests:
- ✅ External APIs (OpenPhone, QuickBooks, etc.)
- ✅ Email sending
- ✅ SMS sending
- ❌ Database (use test database)
- ❌ Our own services
- ❌ Flask routing

#### What to Mock in E2E Tests:
- ✅ Payment processing (if applicable)
- ✅ Production external APIs (use sandbox when available)
- ❌ Everything else should be real

### Test Database Strategy

Use a separate test database that's reset between test runs:

```python
# tests/conftest.py
@pytest.fixture
def test_db():
    """Provide a clean test database for each test"""
    # Create all tables
    db.create_all()
    
    yield db
    
    # Clean up
    db.session.remove()
    db.drop_all()
```

### TDD Workflow

1. **Write the test first** - It will fail (Red)
2. **Write minimal code** to make the test pass (Green)
3. **Refactor** to improve code quality (Refactor)
4. **Repeat** for next requirement

Example TDD cycle:
```python
# Step 1: Write failing test
def test_contact_merge():
    service = ContactService()
    contact1 = Contact(email="test@example.com", phone=None)
    contact2 = Contact(email=None, phone="+1234567890")
    
    merged = service.merge_contacts(contact1, contact2)
    
    assert merged.email == "test@example.com"
    assert merged.phone == "+1234567890"

# Step 2: Implement minimal solution
class ContactService:
    def merge_contacts(self, contact1: Contact, contact2: Contact) -> Contact:
        contact1.phone = contact2.phone or contact1.phone
        contact1.email = contact1.email or contact2.email
        return contact1

# Step 3: Refactor for robustness
class ContactService:
    def merge_contacts(self, primary: Contact, secondary: Contact) -> Contact:
        """Merge secondary contact into primary, preserving primary's data"""
        for field in ['phone', 'email', 'company', 'address']:
            if not getattr(primary, field) and getattr(secondary, field):
                setattr(primary, field, getattr(secondary, field))
        
        # Mark secondary as merged
        secondary.merged_into_id = primary.id
        secondary.is_active = False
        
        db.session.commit()
        return primary
```

## Migration Path

### Phase 1: Service Refactoring (Current)
1. Add dependency injection to services
2. Create service registry
3. Update routes to use registry

### Phase 2: Test Coverage (Next)
1. Write comprehensive unit tests for all services
2. Write integration tests for critical paths
3. Add E2E tests for key user journeys

### Phase 3: Continuous Improvement
1. Measure test coverage (target: >90%)
2. Add performance tests for critical operations
3. Implement contract tests for external APIs

## Code Review Checklist

Before merging any PR, ensure:

- [ ] All new code has corresponding tests
- [ ] Unit tests mock all dependencies
- [ ] Integration tests use real database
- [ ] No direct database queries in routes
- [ ] No external API calls outside dedicated services
- [ ] Dependencies are injected, not created
- [ ] Test coverage hasn't decreased
- [ ] All tests pass in CI/CD pipeline

## Performance Considerations

### Service Instantiation
Services are lightweight and can be instantiated per request without significant overhead. If performance becomes an issue, we can implement lazy loading:

```python
class ServiceRegistry:
    def __init__(self):
        self._services = {}
        self._factories = {}
    
    def register_factory(self, name: str, factory: Callable):
        self._factories[name] = factory
    
    def get(self, name: str):
        if name not in self._services:
            self._services[name] = self._factories[name]()
        return self._services[name]
```

### Database Connection Pooling
Ensure SQLAlchemy is configured with appropriate connection pooling:

```python
SQLALCHEMY_ENGINE_OPTIONS = {
    'pool_size': 10,
    'pool_recycle': 3600,
    'pool_pre_ping': True
}
```

## Anti-Patterns to Avoid

### ❌ Service Locator Pattern
Don't access services through a global singleton:
```python
# Bad
from app import service_locator
service = service_locator.get('campaign')
```

### ❌ Circular Dependencies
Services should not depend on each other circularly:
```python
# Bad
class ServiceA:
    def __init__(self, service_b: ServiceB):
        self.service_b = service_b

class ServiceB:
    def __init__(self, service_a: ServiceA):
        self.service_a = service_a
```

### ❌ Testing Implementation Details
Test behavior, not implementation:
```python
# Bad - tests implementation
def test_service_calls_private_method():
    service._validate_data.assert_called_once()

# Good - tests behavior
def test_service_rejects_invalid_data():
    with pytest.raises(ValidationError):
        service.process(invalid_data)
```

### ❌ Shared Mutable Test State
Each test should be independent:
```python
# Bad - shared state
class TestService:
    service = ContactService()  # Shared across all tests
    
# Good - isolated state
class TestService:
    def test_something(self):
        service = ContactService()  # Fresh instance per test
```

## Conclusion

By following these architectural patterns and testing strategies, we ensure:
- **Maintainability**: Clear separation of concerns
- **Testability**: Every component can be tested in isolation
- **Reliability**: Comprehensive test coverage catches bugs early
- **Velocity**: TDD and good tests enable confident refactoring

This is a living document. As our application evolves, so should our architectural patterns and testing strategies.