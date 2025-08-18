"""Comprehensive test fixtures for the service registry and all services.

Provides mock implementations for:
- Service Registry
- All 24+ registered services
- Repository mocks
- Factory methods for creating mocks
- Integration helpers
"""

import threading
from typing import Any, Dict, List, Optional, Set, Callable
from unittest.mock import Mock, MagicMock, create_autospec
from contextlib import contextmanager
from services.service_registry_enhanced import ServiceLifecycle, ServiceDescriptor


class MockServiceRegistry:
    """Mock implementation of ServiceRegistryEnhanced for testing.
    
    Provides the same interface as the real registry but returns mock services.
    Thread-safe and supports all registry operations.
    """
    
    def __init__(self):
        self._services: Dict[str, Any] = {}
        self._factories: Dict[str, Callable] = {}
        self._lock = threading.Lock()
        self._default_services = self._initialize_default_services()
    
    def _initialize_default_services(self) -> List[str]:
        """Initialize list of default service names."""
        return [
            # Core services
            'db_session', 'contact', 'activity', 'conversation', 'appointment',
            'invoice', 'quote', 'todo', 'webhook_event', 'message', 'auth',
            'product', 'job', 'property', 'setting', 'user', 'invite_token',
            
            # Repository services
            'contact_repository', 'campaign_repository', 'activity_repository',
            'conversation_repository', 'setting_repository', 'todo_repository',
            'appointment_repository', 'job_repository',
            
            # Campaign services
            'campaign', 'campaign_list', 'campaign_membership',
            
            # External integrations
            'openphone', 'openphone_webhook', 'openphone_sync',
            'google_calendar', 'quickbooks', 'quickbooks_sync',
            'email', 'ai',
            
            # Utility services
            'csv_import', 'dashboard', 'scheduler', 'sms_metrics',
            'task', 'diagnostics', 'sync_health'
        ]
    
    def get(self, name: str) -> Any:
        """Get a service by name, creating a mock if it doesn't exist."""
        with self._lock:
            if name not in self._services:
                # Check if there's a factory
                if name in self._factories:
                    self._services[name] = self._factories[name]()
                else:
                    # Create a default mock for this service
                    factory = ServiceMockFactory()
                    self._services[name] = factory.create_mock(name)
            
            return self._services[name]
    
    def register(
        self,
        name: str,
        service: Any = None,
        factory: Callable = None,
        lifecycle: ServiceLifecycle = ServiceLifecycle.SINGLETON,
        dependencies: Optional[List[str]] = None,
        tags: Optional[Set[str]] = None
    ) -> None:
        """Register a service or factory."""
        with self._lock:
            if service:
                self._services[name] = service
            elif factory:
                self._factories[name] = factory
    
    def register_factory(
        self,
        name: str,
        factory: Callable,
        dependencies: Optional[List[str]] = None,
        lifecycle: ServiceLifecycle = ServiceLifecycle.SINGLETON,
        tags: Optional[Set[str]] = None
    ) -> None:
        """Register a factory function."""
        with self._lock:
            self._factories[name] = factory
    
    def register_singleton(
        self,
        name: str,
        factory: Callable,
        tags: Optional[Set[str]] = None
    ) -> None:
        """Register a singleton factory."""
        self.register_factory(name, factory, lifecycle=ServiceLifecycle.SINGLETON, tags=tags)
    
    def validate_dependencies(self) -> List[str]:
        """Mock validation - always returns empty list (no errors)."""
        return []
    
    def warmup(self, service_names: List[str]) -> None:
        """Mock warmup - ensures services are created."""
        for name in service_names:
            self.get(name)
    
    def get_initialization_order(self) -> List[str]:
        """Return a mock initialization order."""
        return self._default_services
    
    def clear(self) -> None:
        """Clear all registered services."""
        with self._lock:
            self._services.clear()
            self._factories.clear()


class ServiceMockFactory:
    """Factory for creating mock services with appropriate methods and attributes."""
    
    def __init__(self):
        self._service_specs = self._initialize_service_specs()
    
    def _initialize_service_specs(self) -> Dict[str, Dict[str, Any]]:
        """Define specifications for each service type."""
        return {
            # Contact Service
            'contact': {
                'methods': [
                    'get_all_contacts', 'create_contact', 'update_contact',
                    'delete_contact', 'get_contact', 'normalize_phone',
                    'search_contacts', 'import_contacts', 'export_contacts'
                ],
                'properties': ['repository']
            },
            
            # Campaign Service
            'campaign': {
                'methods': [
                    'create_campaign', 'execute_campaign', 'pause_campaign',
                    'resume_campaign', 'get_campaign_stats', 'get_campaign',
                    'list_campaigns', 'update_campaign', 'delete_campaign',
                    'add_recipients', 'remove_recipients', 'get_campaign_messages'
                ],
                'properties': [
                    'campaign_repository', 'contact_repository',
                    'openphone_service', 'list_service'
                ]
            },
            
            # OpenPhone Service
            'openphone': {
                'methods': [
                    'send_message', 'get_messages', 'get_message',
                    'get_contacts', 'get_contact', 'create_contact',
                    'update_contact', 'get_conversations', 'get_phone_numbers',
                    'validate_phone_number', 'get_webhooks', 'create_webhook'
                ],
                'properties': ['api_key', 'phone_number_id']
            },
            
            # Dashboard Service
            'dashboard': {
                'methods': [
                    'get_stats', 'get_recent_activity', 'get_campaign_summary',
                    'get_contact_growth', 'get_message_metrics', 'get_revenue_metrics',
                    'get_upcoming_appointments', 'get_pending_tasks'
                ],
                'properties': [
                    'contact_repository', 'campaign_repository',
                    'activity_repository', 'conversation_repository',
                    'sms_metrics_service'
                ]
            },
            
            # CSV Import Service
            'csv_import': {
                'methods': [
                    'import_csv', 'validate_csv', 'map_columns',
                    'preview_import', 'get_import_status', 'cancel_import',
                    'get_import_history', 'export_errors'
                ],
                'properties': [
                    'csv_import_repository', 'contact_repository',
                    'campaign_list_repository', 'contact_service'
                ]
            },
            
            # OpenPhone Webhook Service
            'openphone_webhook': {
                'methods': [
                    'process_webhook', 'validate_webhook', 'handle_message',
                    'handle_call', 'handle_contact_update', 'get_webhook_history'
                ],
                'properties': [
                    'activity_repository', 'conversation_repository',
                    'webhook_event_repository', 'contact_service'
                ]
            },
            
            # Campaign List Service
            'campaign_list': {
                'methods': [
                    'create_list', 'update_list', 'delete_list',
                    'add_members', 'remove_members', 'get_list',
                    'get_members', 'import_list', 'export_list'
                ],
                'properties': [
                    'campaign_list_repository', 'member_repository',
                    'contact_repository'
                ]
            },
            
            # Authentication Service
            'auth': {
                'methods': [
                    'login', 'logout', 'register', 'verify_email',
                    'reset_password', 'change_password', 'get_user',
                    'update_user', 'create_invite', 'accept_invite'
                ],
                'properties': ['user_repository', 'invite_repository']
            },
            
            # Todo Service
            'todo': {
                'methods': [
                    'create_todo', 'update_todo', 'delete_todo',
                    'get_todo', 'list_todos', 'mark_complete',
                    'mark_incomplete', 'assign_todo', 'get_overdue_todos'
                ],
                'properties': ['todo_repository']
            },
            
            # Invoice Service
            'invoice': {
                'methods': [
                    'create_invoice', 'update_invoice', 'delete_invoice',
                    'send_invoice', 'mark_paid', 'mark_unpaid',
                    'get_invoice', 'list_invoices', 'generate_pdf'
                ],
                'properties': ['invoice_repository', 'quote_repository']
            },
            
            # Quote Service
            'quote': {
                'methods': [
                    'create_quote', 'update_quote', 'delete_quote',
                    'send_quote', 'accept_quote', 'reject_quote',
                    'convert_to_invoice', 'get_quote', 'list_quotes'
                ],
                'properties': ['quote_repository', 'line_item_repository']
            },
            
            # Property Service
            'property': {
                'methods': [
                    'create_property', 'update_property', 'delete_property',
                    'get_property', 'list_properties', 'search_properties',
                    'assign_contact', 'get_property_history'
                ],
                'properties': ['repository']
            },
            
            # Job Service
            'job': {
                'methods': [
                    'create_job', 'update_job', 'delete_job',
                    'get_job', 'list_jobs', 'update_status',
                    'assign_team', 'get_job_history', 'calculate_totals'
                ],
                'properties': ['job_repository']
            },
            
            # Appointment Service
            'appointment': {
                'methods': [
                    'create_appointment', 'update_appointment', 'delete_appointment',
                    'get_appointment', 'list_appointments', 'reschedule',
                    'cancel_appointment', 'confirm_appointment', 'send_reminder'
                ],
                'properties': ['calendar_service', 'repository']
            },
            
            # SMS Metrics Service
            'sms_metrics': {
                'methods': [
                    'get_metrics', 'get_daily_stats', 'get_campaign_metrics',
                    'get_contact_metrics', 'get_response_rates', 'export_metrics'
                ],
                'properties': [
                    'activity_repository', 'contact_repository',
                    'campaign_repository'
                ]
            },
            
            # Scheduler Service
            'scheduler': {
                'methods': [
                    'schedule_task', 'cancel_task', 'reschedule_task',
                    'get_scheduled_tasks', 'run_scheduled_tasks',
                    'schedule_campaign', 'schedule_reminder'
                ],
                'properties': [
                    'setting_repository', 'job_repository',
                    'openphone_service', 'invoice_service'
                ]
            },
            
            # QuickBooks Service
            'quickbooks': {
                'methods': [
                    'sync_customers', 'sync_invoices', 'sync_products',
                    'create_customer', 'create_invoice', 'get_company_info',
                    'refresh_token', 'disconnect'
                ],
                'properties': ['auth_repository', 'sync_repository']
            },
            
            # Google Calendar Service
            'google_calendar': {
                'methods': [
                    'list_events', 'create_event', 'update_event',
                    'delete_event', 'get_event', 'get_calendars',
                    'sync_events', 'get_availability'
                ],
                'properties': ['credentials']
            },
            
            # Email Service
            'email': {
                'methods': [
                    'send_email', 'send_bulk', 'create_template',
                    'render_template', 'validate_email', 'get_bounces'
                ],
                'properties': ['mail', 'config']
            },
            
            # AI Service
            'ai': {
                'methods': [
                    'generate_message', 'analyze_sentiment', 'extract_entities',
                    'classify_intent', 'summarize_conversation', 'generate_response'
                ],
                'properties': ['api_key', 'model']
            }
        }
    
    def create_mock(self, service_name: str) -> Mock:
        """Create a mock service with appropriate methods and properties."""
        spec = self._service_specs.get(service_name, {})
        
        # Handle repository names
        if service_name.endswith('_repository'):
            return self.create_repository_mock(service_name.replace('_repository', ''))
        
        return self.create_service_mock(service_name, spec)
    
    def create_service_mock(
        self,
        name: str,
        spec: Optional[Dict[str, Any]] = None,
        custom_attrs: Optional[Dict[str, Any]] = None
    ) -> Mock:
        """Create a mock service with specified methods and properties."""
        mock_service = MagicMock()
        mock_service._mock_name = f"Mock{name.title()}Service"
        
        if spec is None:
            spec = self._service_specs.get(name, {})
        
        # Add methods
        for method_name in spec.get('methods', []):
            setattr(mock_service, method_name, MagicMock())
        
        # Add properties
        for prop_name in spec.get('properties', []):
            if prop_name.endswith('_repository'):
                # Create a mock repository for repository properties
                base_name = prop_name.replace('_repository', '')
                setattr(mock_service, prop_name, self.create_repository_mock(base_name))
            elif prop_name.endswith('_service'):
                # Create a mock service for service properties
                base_name = prop_name.replace('_service', '')
                setattr(mock_service, prop_name, self.create_mock(base_name))
            else:
                # Create a simple mock for other properties
                setattr(mock_service, prop_name, MagicMock())
        
        # Add custom attributes if provided
        if custom_attrs:
            for attr_name, attr_value in custom_attrs.items():
                setattr(mock_service, attr_name, attr_value)
        
        return mock_service
    
    def create_repository_mock(self, entity_name: str) -> Mock:
        """Create a mock repository with standard CRUD operations."""
        mock_repo = MagicMock()
        mock_repo._mock_name = f"Mock{entity_name.title()}Repository"
        
        # Standard repository methods
        repository_methods = [
            'get_all', 'get_by_id', 'create', 'update', 'delete',
            'find_by', 'find_one_by', 'count', 'exists', 'paginate',
            'bulk_create', 'bulk_update', 'bulk_delete', 'query',
            'filter', 'order_by', 'limit', 'offset', 'first', 'last'
        ]
        
        for method_name in repository_methods:
            setattr(mock_repo, method_name, MagicMock())
        
        # Add common properties
        mock_repo.session = MagicMock()
        mock_repo.model_class = MagicMock()
        
        return mock_repo


# Fixture Functions

def create_mock_service(service_name: str, **kwargs) -> Mock:
    """Create a mock service by name.
    
    Args:
        service_name: Name of the service to mock
        **kwargs: Additional attributes to add to the mock
    
    Returns:
        Mock service with appropriate methods and properties
    """
    factory = ServiceMockFactory()
    mock_service = factory.create_mock(service_name)
    
    # Add any additional attributes
    for key, value in kwargs.items():
        setattr(mock_service, key, value)
    
    return mock_service


def create_mock_repository(entity_name: str, **kwargs) -> Mock:
    """Create a mock repository for an entity.
    
    Args:
        entity_name: Name of the entity (e.g., 'contact', 'campaign')
        **kwargs: Additional attributes to add to the mock
    
    Returns:
        Mock repository with standard CRUD operations
    """
    factory = ServiceMockFactory()
    mock_repo = factory.create_repository_mock(entity_name)
    
    # Add any additional attributes
    for key, value in kwargs.items():
        setattr(mock_repo, key, value)
    
    return mock_repo


def mock_service_registry() -> MockServiceRegistry:
    """Create a mock service registry with pre-configured services.
    
    Returns:
        MockServiceRegistry with default services registered
    """
    registry = MockServiceRegistry()
    
    # Pre-register commonly used services
    factory = ServiceMockFactory()
    
    # Register core services
    for service_name in ['contact', 'campaign', 'openphone', 'dashboard']:
        registry.register(service_name, service=factory.create_mock(service_name))
    
    return registry


def mock_contact_service() -> Mock:
    """Create a mock ContactService with common default behaviors.
    
    Returns:
        Mock ContactService with pre-configured methods
    """
    service = create_mock_service('contact')
    
    # Set up common return values
    service.get_all_contacts.return_value = []
    service.normalize_phone.side_effect = lambda phone: f"+1{''.join(filter(str.isdigit, phone))}"
    service.create_contact.return_value = MagicMock(id=1, phone='+15551234567')
    
    return service


def mock_campaign_service() -> Mock:
    """Create a mock CampaignService with dependencies.
    
    Returns:
        Mock CampaignService with repository and service dependencies
    """
    service = create_mock_service('campaign')
    
    # Set up default return values
    service.create_campaign.return_value = MagicMock(
        id=1,
        name='Test Campaign',
        status='draft'
    )
    service.get_campaign_stats.return_value = {
        'total_recipients': 0,
        'messages_sent': 0,
        'messages_delivered': 0,
        'responses_received': 0
    }
    
    return service


def mock_openphone_service() -> Mock:
    """Create a mock OpenPhoneService.
    
    Returns:
        Mock OpenPhoneService with API method mocks
    """
    service = create_mock_service('openphone')
    
    # Set up default API responses
    service.send_message.return_value = {
        'id': 'msg_123',
        'status': 'sent',
        'created_at': '2025-01-01T00:00:00Z'
    }
    service.get_messages.return_value = []
    service.validate_phone_number.return_value = True
    
    return service


def mock_dashboard_service() -> Mock:
    """Create a mock DashboardService.
    
    Returns:
        Mock DashboardService with metric methods
    """
    service = create_mock_service('dashboard')
    
    # Set up default metrics
    service.get_stats.return_value = {
        'total_contacts': 0,
        'total_campaigns': 0,
        'messages_sent_today': 0,
        'active_conversations': 0
    }
    service.get_recent_activity.return_value = []
    
    return service


def mock_csv_import_service() -> Mock:
    """Create a mock CSVImportService.
    
    Returns:
        Mock CSVImportService with import methods
    """
    service = create_mock_service('csv_import')
    
    # Set up default import behavior
    service.validate_csv.return_value = {'valid': True, 'errors': []}
    service.import_csv.return_value = {
        'imported': 0,
        'skipped': 0,
        'errors': []
    }
    
    return service


def mock_all_services() -> Dict[str, Mock]:
    """Create mocks for all registered services.
    
    Returns:
        Dictionary mapping service names to their mocks
    """
    factory = ServiceMockFactory()
    services = {}
    
    # All service names from the registry
    service_names = [
        'contact', 'campaign', 'openphone', 'dashboard', 'csv_import',
        'openphone_webhook', 'campaign_list', 'auth', 'todo', 'invoice',
        'quote', 'property', 'job', 'appointment', 'sms_metrics',
        'scheduler', 'quickbooks', 'google_calendar', 'email', 'ai',
        'message', 'setting', 'product', 'conversation', 'activity',
        'webhook_event', 'task', 'diagnostics', 'sync_health',
        'openphone_sync', 'quickbooks_sync'
    ]
    
    for name in service_names:
        services[name] = factory.create_mock(name)
    
    # Add repository mocks
    repository_names = [
        'contact_repository', 'campaign_repository', 'activity_repository',
        'conversation_repository', 'setting_repository', 'todo_repository',
        'appointment_repository', 'job_repository'
    ]
    
    for name in repository_names:
        services[name] = factory.create_mock(name)
    
    return services


@contextmanager
def isolated_service_registry():
    """Context manager for an isolated service registry.
    
    Yields:
        MockServiceRegistry that is cleaned up after use
    """
    registry = MockServiceRegistry()
    try:
        yield registry
    finally:
        registry.clear()


# Pytest Fixtures
# These can be imported and used in test files

import pytest


@pytest.fixture
def service_registry():
    """Pytest fixture for mock service registry."""
    return mock_service_registry()


@pytest.fixture
def contact_service():
    """Pytest fixture for mock contact service."""
    return mock_contact_service()


@pytest.fixture
def campaign_service():
    """Pytest fixture for mock campaign service."""
    return mock_campaign_service()


@pytest.fixture
def openphone_service():
    """Pytest fixture for mock OpenPhone service."""
    return mock_openphone_service()


@pytest.fixture
def dashboard_service():
    """Pytest fixture for mock dashboard service."""
    return mock_dashboard_service()


@pytest.fixture
def all_services():
    """Pytest fixture providing all mock services."""
    return mock_all_services()


@pytest.fixture
def mock_app(mocker):
    """Pytest fixture for Flask app with mock service registry.
    
    Args:
        mocker: pytest-mock fixture
    
    Returns:
        Flask app with services replaced by mocks
    """
    from flask import Flask
    app = Flask(__name__)
    app.services = MockServiceRegistry()
    
    # Mock current_app to return our app
    mocker.patch('flask.current_app', app)
    
    return app


@pytest.fixture
def isolated_registry():
    """Pytest fixture for isolated service registry."""
    with isolated_service_registry() as registry:
        yield registry
