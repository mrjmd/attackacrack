# Service Registry Test Fixtures Documentation

## Overview

The service fixtures provide comprehensive mocking capabilities for the Attack-a-Crack CRM service registry and all 24+ registered services. These fixtures enable isolated unit testing by replacing real services with configurable mocks.

## Quick Start

### Basic Usage in Tests

```python
import pytest
from tests.fixtures.service_fixtures import (
    mock_service_registry,
    mock_contact_service,
    mock_campaign_service
)

def test_route_with_mock_registry():
    """Example: Testing a route with mocked services"""
    from flask import Flask
    app = Flask(__name__)
    
    # Replace the real service registry with a mock
    app.services = mock_service_registry()
    
    with app.app_context():
        # Get a mocked service
        contact_service = app.services.get('contact')
        
        # Configure mock behavior
        contact_service.get_all_contacts.return_value = [
            {'id': 1, 'name': 'Test Contact', 'phone': '+15551234567'}
        ]
        
        # Test your route logic
        contacts = contact_service.get_all_contacts()
        assert len(contacts) == 1
```

### Using Pytest Fixtures

```python
import pytest
from tests.fixtures.service_fixtures import service_registry, contact_service

def test_with_fixtures(service_registry, contact_service):
    """Using fixtures directly in test parameters"""
    # service_registry is a MockServiceRegistry instance
    # contact_service is a mock ContactService
    
    contact_service.create_contact.return_value = {'id': 1}
    result = contact_service.create_contact({'phone': '+15551234567'})
    assert result['id'] == 1
```

## Available Components

### 1. MockServiceRegistry

A thread-safe mock implementation of ServiceRegistryEnhanced.

```python
from tests.fixtures.service_fixtures import MockServiceRegistry

registry = MockServiceRegistry()
service = registry.get('contact')  # Returns a mock ContactService
registry.register('custom', service=my_mock)  # Register custom mock
```

**Key Methods:**
- `get(name)` - Get or create a mock service
- `register(name, service)` - Register a pre-created mock
- `register_factory(name, factory)` - Register a factory function
- `validate_dependencies()` - Always returns empty list (no errors)
- `warmup(service_names)` - Pre-create specified services
- `clear()` - Remove all registered services

### 2. ServiceMockFactory

Factory for creating service mocks with appropriate methods and properties.

```python
from tests.fixtures.service_fixtures import ServiceMockFactory

factory = ServiceMockFactory()

# Create a mock service
contact_mock = factory.create_mock('contact')
assert hasattr(contact_mock, 'get_all_contacts')

# Create a mock repository
repo_mock = factory.create_repository_mock('contact')
assert hasattr(repo_mock, 'get_all')
assert hasattr(repo_mock, 'create')
```

### 3. Helper Functions

#### create_mock_service()
```python
from tests.fixtures.service_fixtures import create_mock_service

service = create_mock_service('campaign')
service.create_campaign.return_value = {'id': 1, 'status': 'draft'}
```

#### create_mock_repository()
```python
from tests.fixtures.service_fixtures import create_mock_repository

repo = create_mock_repository('contact')
repo.get_all.return_value = []
repo.find_by.return_value = None
```

#### mock_all_services()
```python
from tests.fixtures.service_fixtures import mock_all_services

services = mock_all_services()
# Returns dict with all 24+ services as mocks
assert 'contact' in services
assert 'campaign' in services
assert 'openphone' in services
```

#### isolated_service_registry()
```python
from tests.fixtures.service_fixtures import isolated_service_registry

with isolated_service_registry() as registry:
    # Use registry in isolation
    service = registry.get('contact')
    # Registry is automatically cleaned up after context
```

## Service-Specific Mocks

Each service mock comes pre-configured with appropriate methods:

### ContactService Mock
```python
service = mock_contact_service()
# Pre-configured methods:
- get_all_contacts()
- create_contact()
- update_contact()
- delete_contact()
- normalize_phone()
- search_contacts()
```

### CampaignService Mock
```python
service = mock_campaign_service()
# Pre-configured methods:
- create_campaign()
- execute_campaign()
- get_campaign_stats()
- pause_campaign()
- resume_campaign()
# Pre-configured properties:
- campaign_repository
- contact_repository
- openphone_service
```

### OpenPhoneService Mock
```python
service = mock_openphone_service()
# Pre-configured methods:
- send_message()
- get_messages()
- get_contacts()
- validate_phone_number()
# Default return values:
service.send_message() returns {'id': 'msg_123', 'status': 'sent'}
```

## Common Testing Patterns

### Pattern 1: Unit Testing Routes

```python
def test_contact_route(app):
    """Test a route with mocked services"""
    app.services = mock_service_registry()
    
    with app.test_client() as client:
        # Configure mock
        contact_service = app.services.get('contact')
        contact_service.get_all_contacts.return_value = []
        
        # Test route
        response = client.get('/contacts')
        assert response.status_code == 200
```

### Pattern 2: Testing Service Dependencies

```python
def test_service_with_dependencies():
    """Test a service that depends on other services"""
    registry = MockServiceRegistry()
    
    # Mock dependencies
    openphone = mock_openphone_service()
    registry.register('openphone', service=openphone)
    
    # Get service that uses the dependency
    campaign_service = registry.get('campaign')
    campaign_service.openphone_service = openphone
    
    # Test interaction
    openphone.send_message.return_value = {'status': 'sent'}
    # ... test campaign execution ...
```

### Pattern 3: Testing with Partial Mocks

```python
def test_mixed_real_and_mock_services():
    """Use real services for some, mocks for others"""
    registry = MockServiceRegistry()
    
    # Use real contact service
    from services.contact_service_refactored import ContactService
    real_contact = ContactService()
    registry.register('contact', service=real_contact)
    
    # Use mock for external service
    mock_openphone = mock_openphone_service()
    registry.register('openphone', service=mock_openphone)
    
    # Test without making external API calls
    campaign_service = registry.get('campaign')
    # ...
```

### Pattern 4: Testing Repository Interactions

```python
def test_service_with_repository():
    """Test service-repository interaction"""
    # Create mock repository
    contact_repo = create_mock_repository('contact')
    contact_repo.get_all.return_value = []
    contact_repo.create.return_value = Mock(id=1)
    
    # Create service with mock repository
    from services.contact_service_refactored import ContactService
    service = ContactService(repository=contact_repo)
    
    # Test repository was called correctly
    result = service.create_contact({'phone': '+15551234567'})
    contact_repo.create.assert_called_once()
```

## Thread Safety

All fixtures are thread-safe and can be used in parallel tests:

```python
import threading

def test_thread_safety():
    registry = MockServiceRegistry()
    results = []
    
    def worker():
        service = registry.get('contact')
        results.append(service)
    
    threads = [threading.Thread(target=worker) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    
    # All threads get the same mock instance
    assert all(s is results[0] for s in results)
```

## Best Practices

1. **Always use fixtures for unit tests** - Don't instantiate real services
2. **Configure mocks before use** - Set return values and side effects
3. **Use isolated_service_registry()** for complete isolation
4. **Verify mock calls** - Use assert_called_with() to verify interactions
5. **Reset mocks between tests** - Use mock.reset_mock() if reusing

## Troubleshooting

### Mock not returning expected value
```python
# Wrong - forgetting to configure return value
service = mock_contact_service()
result = service.get_all_contacts()  # Returns MagicMock object

# Right - configure return value first
service = mock_contact_service()
service.get_all_contacts.return_value = []
result = service.get_all_contacts()  # Returns []
```

### Service not found in registry
```python
# The MockServiceRegistry auto-creates unknown services
registry = MockServiceRegistry()
service = registry.get('unknown_service')  # Returns generic Mock
assert service is not None  # Always succeeds
```

### Mock verification failing
```python
# Use the correct assertion method
service.method.assert_called()  # Any call
service.method.assert_called_once()  # Exactly one call
service.method.assert_called_with(arg1, arg2)  # Specific args
service.method.assert_not_called()  # Never called
```

## Complete Example

```python
import pytest
from flask import Flask
from tests.fixtures.service_fixtures import (
    MockServiceRegistry,
    mock_contact_service,
    mock_campaign_service,
    mock_openphone_service
)

class TestCampaignRoute:
    @pytest.fixture
    def app(self):
        app = Flask(__name__)
        app.services = MockServiceRegistry()
        return app
    
    def test_create_campaign(self, app):
        # Setup mocks
        campaign_service = mock_campaign_service()
        contact_service = mock_contact_service()
        openphone_service = mock_openphone_service()
        
        app.services.register('campaign', service=campaign_service)
        app.services.register('contact', service=contact_service)
        app.services.register('openphone', service=openphone_service)
        
        # Configure behavior
        contact_service.get_all_contacts.return_value = [
            {'id': 1, 'phone': '+15551234567'}
        ]
        campaign_service.create_campaign.return_value = {
            'id': 1,
            'name': 'Test Campaign',
            'status': 'draft'
        }
        
        with app.app_context():
            # Test campaign creation
            campaign = app.services.get('campaign')
            result = campaign.create_campaign(
                name='Test Campaign',
                contact_ids=[1]
            )
            
            assert result['id'] == 1
            assert result['status'] == 'draft'
            
            # Verify interactions
            campaign.create_campaign.assert_called_once()
```
