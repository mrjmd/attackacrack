"""
Practical examples of using the enhanced service registry
Shows real-world patterns for dependency injection and lazy loading
"""

from typing import Optional
from services.service_registry_enhanced import (
    ServiceRegistryEnhanced,
    ServiceLifecycle,
    create_enhanced_registry
)
from services.google_calendar_service import GoogleCalendarService
from services.email_service import EmailService, EmailConfig
from services.appointment_service_refactored import AppointmentService
from services.contact_service import ContactService
from services.openphone_service import OpenPhoneService
from services.campaign_service_refactored import CampaignService
from services.campaign_list_service import CampaignListService
from extensions import db
import os


def setup_registry_with_lazy_loading() -> ServiceRegistryEnhanced:
    """
    Example 1: Setting up registry with lazy loading for expensive services
    """
    registry = create_enhanced_registry()
    
    # Register simple services that are always needed
    registry.register('db_session', service=db.session)
    
    # Register expensive services with lazy loading
    # These won't be created until first use
    
    # Google Calendar - expensive due to OAuth
    def create_google_calendar():
        from api_integrations import get_google_credentials
        credentials = get_google_credentials()
        return GoogleCalendarService(credentials=credentials)
    
    registry.register_singleton(
        'google_calendar',
        create_google_calendar,
        tags={'external', 'google', 'calendar'}
    )
    
    # Email service - may require SMTP connection
    def create_email_service():
        config = EmailConfig(
            server=os.getenv('SMTP_SERVER', 'localhost'),
            port=int(os.getenv('SMTP_PORT', '587')),
            use_tls=os.getenv('SMTP_USE_TLS', 'true').lower() == 'true',
            username=os.getenv('SMTP_USERNAME'),
            password=os.getenv('SMTP_PASSWORD'),
            default_sender=os.getenv('DEFAULT_EMAIL_SENDER', 'noreply@example.com')
        )
        return EmailService(config)
    
    registry.register_singleton(
        'email',
        create_email_service,
        tags={'external', 'email', 'smtp'}
    )
    
    # OpenPhone - requires API key validation
    def create_openphone_service():
        api_key = os.getenv('OPENPHONE_API_KEY')
        phone_number = os.getenv('OPENPHONE_PHONE_NUMBER')
        return OpenPhoneService(api_key=api_key, phone_number=phone_number)
    
    registry.register_singleton(
        'openphone',
        create_openphone_service,
        tags={'external', 'sms', 'api'}
    )
    
    return registry


def setup_registry_with_dependencies() -> ServiceRegistryEnhanced:
    """
    Example 2: Setting up services with complex dependencies
    """
    registry = create_enhanced_registry()
    
    # Base services (no dependencies)
    registry.register('db_session', service=db.session)
    
    registry.register_factory(
        'contact',
        lambda db_session: ContactService(session=db_session),
        dependencies=['db_session']
    )
    
    # Services with single dependency
    registry.register_factory(
        'campaign_list',
        lambda db_session: CampaignListService(session=db_session),
        dependencies=['db_session']
    )
    
    # Services with multiple dependencies
    registry.register_factory(
        'campaign',
        lambda openphone, campaign_list, db_session: CampaignService(
            openphone_service=openphone,
            list_service=campaign_list,
            session=db_session
        ),
        dependencies=['openphone', 'campaign_list', 'db_session']
    )
    
    # Appointment service with optional dependency
    registry.register_factory(
        'appointment',
        lambda google_calendar, db_session: AppointmentService(
            calendar_service=google_calendar,
            session=db_session
        ),
        dependencies=['google_calendar', 'db_session']
    )
    
    # Register the external services
    registry.register_singleton('openphone', lambda: OpenPhoneService())
    registry.register_singleton('google_calendar', lambda: GoogleCalendarService())
    
    return registry


def setup_registry_with_lifecycles() -> ServiceRegistryEnhanced:
    """
    Example 3: Different lifecycle patterns
    """
    registry = create_enhanced_registry()
    
    # Singleton - shared across entire application
    registry.register_singleton(
        'config',
        lambda: {
            'app_name': 'Attack-a-Crack CRM',
            'version': '2.0',
            'environment': os.getenv('ENVIRONMENT', 'development')
        }
    )
    
    # Transient - new instance every time
    # Useful for services that maintain state per operation
    registry.register_transient(
        'email_builder',
        lambda: EmailMessageBuilder()
    )
    
    # Scoped - one instance per request/context
    # Useful for request-specific services
    registry.register(
        'request_context',
        factory=lambda: RequestContext(),
        lifecycle=ServiceLifecycle.SCOPED
    )
    
    return registry


def setup_registry_with_conditional_registration() -> ServiceRegistryEnhanced:
    """
    Example 4: Conditional service registration based on environment
    """
    registry = create_enhanced_registry()
    environment = os.getenv('ENVIRONMENT', 'development')
    
    # Always register core services
    registry.register('db_session', service=db.session)
    
    # Development-only services
    if environment == 'development':
        registry.register_singleton(
            'mock_sms',
            lambda: MockSMSService(),
            tags={'mock', 'development'}
        )
        registry.register('openphone', service=registry.get('mock_sms'))
    else:
        # Production services
        registry.register_singleton(
            'openphone',
            lambda: OpenPhoneService(
                api_key=os.getenv('OPENPHONE_API_KEY'),
                phone_number=os.getenv('OPENPHONE_PHONE_NUMBER')
            ),
            tags={'production', 'external'}
        )
    
    # Optional services based on feature flags
    if os.getenv('ENABLE_QUICKBOOKS', 'false').lower() == 'true':
        registry.register_singleton(
            'quickbooks',
            lambda: QuickBooksService(),
            tags={'accounting', 'external'}
        )
    
    return registry


def setup_registry_with_warmup() -> ServiceRegistryEnhanced:
    """
    Example 5: Registry with service warmup for production
    """
    registry = create_enhanced_registry()
    
    # Register all services
    registry.register('db_session', service=db.session)
    
    # Critical services that should be warmed up
    critical_services = []
    
    # Database connection pool
    def create_db_pool():
        # Initialize connection pool
        return DatabasePool()
    
    registry.register_singleton('db_pool', create_db_pool)
    critical_services.append('db_pool')
    
    # Cache service
    def create_cache():
        # Connect to Redis
        return CacheService()
    
    registry.register_singleton('cache', create_cache)
    critical_services.append('cache')
    
    # External API clients
    registry.register_singleton('openphone', lambda: OpenPhoneService())
    critical_services.append('openphone')
    
    # Warmup critical services during startup
    if os.getenv('ENVIRONMENT') == 'production':
        print("Warming up critical services...")
        registry.warmup(critical_services)
        print("Service warmup complete")
    
    return registry


def setup_registry_with_fallbacks() -> ServiceRegistryEnhanced:
    """
    Example 6: Registry with fallback services for resilience
    """
    registry = create_enhanced_registry()
    
    # Try to create primary service, fall back if it fails
    def create_sms_service():
        try:
            # Try OpenPhone first
            api_key = os.getenv('OPENPHONE_API_KEY')
            if api_key:
                service = OpenPhoneService(api_key=api_key)
                # Test the connection
                service.test_connection()
                return service
        except Exception as e:
            print(f"OpenPhone unavailable: {e}")
        
        try:
            # Fall back to Twilio
            return TwilioService()
        except Exception as e:
            print(f"Twilio unavailable: {e}")
        
        # Last resort - log only
        print("WARNING: No SMS service available, using mock")
        return MockSMSService()
    
    registry.register_singleton('sms', create_sms_service)
    
    return registry


def demonstrate_usage():
    """
    Example 7: Using the registry in application code
    """
    # Setup registry
    registry = setup_registry_with_dependencies()
    
    # Get services as needed (lazy loading happens here)
    contact_service = registry.get('contact')
    campaign_service = registry.get('campaign')
    
    # Services are properly initialized with dependencies
    # contact_service has db_session
    # campaign_service has openphone, campaign_list, and db_session
    
    # Use services normally
    contacts = contact_service.get_all_contacts()
    campaign_service.send_campaign(campaign_id=1)
    
    # Get all services with a specific tag
    external_services = registry.get_all_by_tag('external')
    for name, service in external_services.items():
        print(f"External service: {name}")
    
    # Check service information
    info = registry.get_service_info('campaign')
    print(f"Campaign service dependencies: {info['dependencies']}")
    
    # Validate all dependencies are satisfied
    errors = registry.validate_dependencies()
    if errors:
        print("Dependency errors:", errors)
    
    # Get initialization order for debugging
    order = registry.get_initialization_order()
    print(f"Service initialization order: {order}")


# Mock classes for examples
class EmailMessageBuilder:
    """Mock email builder"""
    pass


class RequestContext:
    """Mock request context"""
    pass


class MockSMSService:
    """Mock SMS service for development"""
    def send_sms(self, to, message):
        print(f"[MOCK] Sending SMS to {to}: {message}")
        return {"status": "mock_success"}


class QuickBooksService:
    """Mock QuickBooks service"""
    pass


class DatabasePool:
    """Mock database pool"""
    pass


class CacheService:
    """Mock cache service"""
    pass


class TwilioService:
    """Mock Twilio service"""
    pass


if __name__ == "__main__":
    # Run demonstration
    demonstrate_usage()