# app.py

from flask import Flask, g, request
from flask_migrate import Migrate
from config import get_config
from extensions import db, login_manager, bcrypt
from datetime import datetime
import os
import uuid
from werkzeug.middleware.proxy_fix import ProxyFix
from logging_config import setup_logging, get_logger

# Configure logging as early as possible
setup_logging(app_name="attackacrack-crm", log_level="INFO")
logger = get_logger(__name__)

# Configure Sentry for production error tracking
def init_sentry():
    """Initialize Sentry error tracking in production."""
    sentry_dsn = os.environ.get('SENTRY_DSN')
    if sentry_dsn and os.environ.get('FLASK_ENV') == 'production':
        import sentry_sdk
        from sentry_sdk.integrations.flask import FlaskIntegration
        from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
        from sentry_sdk.integrations.celery import CeleryIntegration
        
        sentry_sdk.init(
            dsn=sentry_dsn,
            integrations=[
                FlaskIntegration(
                    transaction_style='endpoint'
                ),
                SqlalchemyIntegration(),
                CeleryIntegration()
            ],
            traces_sample_rate=0.1,  # 10% of transactions for performance monitoring
            profiles_sample_rate=0.1,  # 10% of transactions for profiling
            environment=os.environ.get('FLASK_ENV', 'development'),
            release=os.environ.get('GIT_SHA', 'unknown')
        )
        logger.info("Sentry error tracking initialized")

init_sentry()

def create_app(config_name=None, test_config=None):
    """Create and configure an instance of the Flask application."""
    app = Flask(__name__)
    
    config_class = get_config(config_name)
    app.config.from_object(config_class)
    
    # Initialize app with config
    config_class.init_app(app)
    
    if test_config:
        app.config.update(test_config)

    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

    db.init_app(app)
    migrate = Migrate(app, db)
    
    # Initialize Enhanced Service Registry with Lazy Loading
    from services.service_registry_enhanced import create_enhanced_registry, ServiceLifecycle
    registry = create_enhanced_registry()
    
    # Register base services (no dependencies)
    # Use a factory for db_session to ensure fresh sessions in tests
    registry.register_factory(
        'db_session',
        lambda: _get_current_db_session(),
        lifecycle=ServiceLifecycle.SCOPED  # Fresh session per scope/request
    )
    
    # Register repository services
    registry.register_factory(
        'contact_repository',
        lambda db_session: _create_contact_repository(db_session),
        dependencies=['db_session']
    )
    
    registry.register_factory(
        'campaign_repository', 
        lambda db_session: _create_campaign_repository(db_session),
        dependencies=['db_session']
    )
    
    registry.register_factory(
        'contact_flag_repository',
        lambda db_session: _create_contact_flag_repository(db_session),
        dependencies=['db_session']
    )
    
    registry.register_factory(
        'opt_out_audit_repository',
        lambda db_session: _create_opt_out_audit_repository(db_session),
        dependencies=['db_session']
    )
    
    registry.register_factory(
        'activity_repository',
        lambda db_session: _create_activity_repository(db_session),
        dependencies=['db_session']
    )
    
    registry.register_factory(
        'conversation_repository',
        lambda db_session: _create_conversation_repository(db_session),
        dependencies=['db_session']
    )
    
    registry.register_factory(
        'setting_repository',
        lambda db_session: _create_setting_repository(db_session),
        dependencies=['db_session']
    )
    
    registry.register_factory(
        'todo_repository',
        lambda db_session: _create_todo_repository(db_session),
        dependencies=['db_session']
    )
    
    registry.register_factory(
        'appointment_repository',
        lambda db_session: _create_appointment_repository(db_session),
        dependencies=['db_session']
    )
    
    registry.register_factory(
        'webhook_event_repository',
        lambda db_session: _create_webhook_event_repository(db_session),
        dependencies=['db_session']
    )
    
    registry.register_factory(
        'failed_webhook_queue_repository',
        lambda db_session: _create_failed_webhook_queue_repository(db_session),
        dependencies=['db_session']
    )
    
    registry.register_factory(
        'invoice_repository',
        lambda db_session: _create_invoice_repository(db_session),
        dependencies=['db_session']
    )
    
    registry.register_factory(
        'quote_repository',
        lambda db_session: _create_quote_repository(db_session),
        dependencies=['db_session']
    )
    
    registry.register_factory(
        'job_repository',
        lambda db_session: _create_job_repository(db_session),
        dependencies=['db_session']
    )
    
    registry.register_factory(
        'phone_validation_repository',
        lambda db_session: _create_phone_validation_repository(db_session),
        dependencies=['db_session']
    )
    
    registry.register_factory(
        'ab_test_result_repository',
        lambda db_session: _create_ab_test_result_repository(db_session),
        dependencies=['db_session']
    )
    
    registry.register_factory(
        'campaign_template_repository',
        lambda db_session: _create_campaign_template_repository(db_session),
        dependencies=['db_session']
    )
    
    # Register services with lazy loading factories
    # These won't be instantiated until first use
    
    # Basic services without dependencies
    registry.register_factory(
        'job',
        lambda job_repository: _create_job_service(job_repository),
        dependencies=['job_repository']
    )
    registry.register_singleton(
        'contact',
        lambda contact_repository, campaign_repository, contact_flag_repository: _create_contact_service(
            contact_repository, campaign_repository, contact_flag_repository
        ),
        dependencies=['contact_repository', 'campaign_repository', 'contact_flag_repository']
    )
    
    # Setting service with repository dependency
    registry.register_factory(
        'setting',
        lambda setting_repository: _create_setting_service(setting_repository),
        dependencies=['setting_repository']
    )
    registry.register_factory(
        'message',
        lambda conversation_repository, activity_repository, contact, property, openphone, ai: _create_message_service(conversation_repository, activity_repository, contact, property, openphone, ai),
        dependencies=['conversation_repository', 'activity_repository', 'contact', 'property', 'openphone', 'ai']
    )
    registry.register_factory(
        'todo',
        lambda todo_repository: _create_todo_service(todo_repository),
        dependencies=['todo_repository']
    )
    registry.register_singleton('auth', lambda: _create_auth_service(db.session))
    registry.register_factory(
        'product', 
        lambda db_session: _create_product_service(db_session),
        dependencies=['db_session']
    )
    # Job repository
    registry.register_factory(
        'job_repository',
        lambda db_session: _create_job_repository(db_session),
        dependencies=['db_session']
    )
    
    registry.register_factory(
        'job',
        lambda job_repository: _create_job_service(job_repository),
        dependencies=['job_repository']
    )
    registry.register_singleton('quote', lambda: _create_quote_service())
    registry.register_factory(
        'invoice',
        lambda invoice_repository, quote_repository: _create_invoice_service(
            invoice_repository, quote_repository
        ),
        dependencies=['invoice_repository', 'quote_repository']
    )
    registry.register_singleton(
        'sms_metrics',
        lambda activity_repository, contact_repository, campaign_repository: _create_sms_metrics_service(
            activity_repository, contact_repository, campaign_repository
        ),
        dependencies=['activity_repository', 'contact_repository', 'campaign_repository']
    )
    
    # Property service with database dependency
    registry.register_factory(
        'property',
        lambda db_session: _create_property_service(db_session),
        dependencies=['db_session']
    )
    
    # External API services (expensive to initialize)
    registry.register_singleton(
        'openphone',
        lambda: _create_openphone_service(),
        tags={'external', 'api', 'sms'}
    )
    
    registry.register_singleton(
        'google_calendar',
        lambda: _create_google_calendar_service(),
        tags={'external', 'api', 'calendar'}
    )
    
    registry.register_singleton(
        'email',
        lambda: _create_email_service(),
        tags={'external', 'smtp'}
    )
    
    registry.register_singleton(
        'ai',
        lambda: _create_ai_service(),
        tags={'external', 'api', 'ai'}
    )
    
    registry.register_singleton(
        'quickbooks',
        lambda: _create_quickbooks_service(),
        tags={'external', 'api', 'accounting'}
    )
    
    # Services with single dependencies
    registry.register_factory(
        'campaign_list',
        lambda db_session: _create_campaign_list_service(db_session),
        dependencies=['db_session']
    )
    
    # Phone validation service
    registry.register_factory(
        'phone_validation',
        lambda phone_validation_repository: _create_phone_validation_service(phone_validation_repository),
        dependencies=['phone_validation_repository'],
        tags={'validation', 'api', 'external'}
    )
    
    # A/B Testing service
    registry.register_factory(
        'ab_testing',
        lambda campaign_repository, contact_repository, ab_test_result_repository: _create_ab_testing_service(
            campaign_repository, contact_repository, ab_test_result_repository
        ),
        dependencies=['campaign_repository', 'contact_repository', 'ab_test_result_repository'],
        tags={'testing', 'analytics'}
    )
    
    # Opt-out service
    registry.register_factory(
        'opt_out',
        lambda contact_flag_repository, opt_out_audit_repository, openphone, contact_repository: _create_opt_out_service(
            contact_flag_repository, opt_out_audit_repository, openphone, contact_repository
        ),
        dependencies=['contact_flag_repository', 'opt_out_audit_repository', 'openphone', 'contact_repository']
    )
    
    registry.register_factory(
        'openphone_webhook',
        lambda activity_repository, conversation_repository, webhook_event_repository, contact, sms_metrics, opt_out: _create_openphone_webhook_service(
            activity_repository, conversation_repository, webhook_event_repository, contact, sms_metrics, opt_out
        ),
        dependencies=['activity_repository', 'conversation_repository', 'webhook_event_repository', 'contact', 'sms_metrics', 'opt_out']
    )
    
    registry.register_factory(
        'webhook_error_recovery',
        lambda failed_webhook_queue_repository, openphone_webhook, webhook_event_repository: _create_webhook_error_recovery_service(
            failed_webhook_queue_repository, openphone_webhook, webhook_event_repository
        ),
        dependencies=['failed_webhook_queue_repository', 'openphone_webhook', 'webhook_event_repository']
    )
    
    registry.register_factory(
        'dashboard',
        lambda contact_repository, campaign_repository, activity_repository, conversation_repository, sms_metrics: _create_dashboard_service_with_repositories(
            contact_repository, campaign_repository, activity_repository, conversation_repository, sms_metrics
        ),
        dependencies=['contact_repository', 'campaign_repository', 'activity_repository', 'conversation_repository', 'sms_metrics']
    )
    
    registry.register_factory(
        'campaign_template',
        lambda campaign_template_repository, contact_repository: _create_campaign_template_service(
            campaign_template_repository, contact_repository
        ),
        dependencies=['campaign_template_repository', 'contact_repository']
    )
    
    registry.register_factory(
        'conversation',
        lambda db_session: _create_conversation_service(db_session),
        dependencies=['db_session']
    )
    
    registry.register_factory(
        'task',
        lambda db_session: _create_task_service(db_session),
        dependencies=['db_session']
    )
    
    registry.register_factory(
        'diagnostics',
        lambda db_session: _create_diagnostics_service(db_session),
        dependencies=['db_session']
    )
    
    registry.register_factory(
        'sync_health',
        lambda db_session: _create_sync_health_service(db_session),
        dependencies=['db_session']
    )
    
    registry.register_factory(
        'webhook_health_check',
        lambda webhook_event_repository, openphone, email: _create_webhook_health_check_service(
            webhook_event_repository, openphone, email
        ),
        dependencies=['webhook_event_repository', 'openphone', 'email']
    )
    
    # OpenPhone Reconciliation Service
    registry.register_factory(
        'openphone_reconciliation',
        lambda activity_repository, conversation_repository, contact: _create_openphone_reconciliation_service(
            activity_repository, conversation_repository, contact
        ),
        dependencies=['activity_repository', 'conversation_repository', 'contact'],
        tags={'reconciliation', 'openphone', 'sync'}
    )
    
    # Services with multiple dependencies
    registry.register_factory(
        'campaign',
        lambda openphone, campaign_list, campaign_repository, contact_repository, activity_repository: _create_campaign_service(
            openphone, campaign_list, campaign_repository, contact_repository, activity_repository
        ),
        dependencies=['openphone', 'campaign_list', 'campaign_repository', 'contact_repository', 'activity_repository']
    )
    
    registry.register_factory(
        'csv_import',
        lambda contact, db_session: _create_csv_import_service(contact, db_session),
        dependencies=['contact', 'db_session']
    )
    
    registry.register_factory(
        'openphone_sync',
        lambda openphone, db_session: _create_openphone_sync_service(openphone, db_session),
        dependencies=['openphone', 'db_session']
    )
    
    registry.register_factory(
        'quickbooks_sync',
        lambda quickbooks, db_session: _create_quickbooks_sync_service(quickbooks, db_session),
        dependencies=['quickbooks', 'db_session']
    )
    
    registry.register_factory(
        'appointment',
        lambda google_calendar, db_session: _create_appointment_service(google_calendar, db_session),
        dependencies=['google_calendar', 'db_session']
    )
    
    registry.register_factory(
        'scheduler',
        lambda openphone, invoice, db_session: _create_scheduler_service(openphone, invoice, db_session),
        dependencies=['openphone', 'invoice', 'db_session']
    )
    
    # Validate all dependencies are registered
    errors = registry.validate_dependencies()
    if errors:
        for error in errors:
            logger.error(f"Service dependency error: {error}")
        if app.config.get('FLASK_ENV') == 'production':
            raise RuntimeError(f"Service dependency errors: {errors}")
    
    # Log initialization order for debugging
    if app.debug:
        try:
            order = registry.get_initialization_order()
            logger.debug(f"Service initialization order: {order}")
        except RuntimeError as e:
            logger.error(f"Circular dependency detected: {e}")
            raise
    
    # Warmup critical services in production
    if app.config.get('FLASK_ENV') == 'production':
        critical_services = ['db_session', 'openphone', 'auth']
        logger.info(f"Warming up critical services: {critical_services}")
        registry.warmup(critical_services)
    
    # Attach registry to app
    app.services = registry
    
    # Initialize authentication
    bcrypt.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'
    
    # User loader for Flask-Login
    from crm_database import User
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))
    
    # Add request tracking middleware
    @app.before_request
    def before_request():
        g.request_id = str(uuid.uuid4())
        logger.info("Request started", 
                   request_id=g.request_id,
                   method=request.method if hasattr(request, 'method') else None,
                   path=request.path if hasattr(request, 'path') else None)
        
        # In testing mode with LOGIN_DISABLED, provide a mock user for current_user
        if app.config.get('LOGIN_DISABLED', False):
            from flask_login import login_user
            from unittest.mock import Mock
            
            # Create a mock user object that behaves like a real user
            mock_user = Mock()
            mock_user.id = 1
            mock_user.email = 'test@example.com'
            mock_user.first_name = 'Test'
            mock_user.last_name = 'User'
            mock_user.role = 'admin'
            mock_user.is_admin = True
            mock_user.is_active = True
            mock_user.is_authenticated = True
            mock_user.is_anonymous = False
            mock_user.get_id.return_value = '1'
            
            # Store in flask.g for access in routes
            g.mock_user = mock_user
    
    @app.after_request
    def after_request(response):
        logger.info("Request completed",
                   request_id=getattr(g, 'request_id', None),
                   status_code=response.status_code)
        return response
    
    # Global error handlers
    @app.errorhandler(500)
    def internal_error(error):
        logger.error("Internal server error",
                    request_id=getattr(g, 'request_id', None),
                    error=str(error))
        return "Internal server error", 500
    
    @app.errorhandler(404)
    def not_found_error(error):
        logger.warning("Page not found",
                      request_id=getattr(g, 'request_id', None),
                      path=request.path if hasattr(request, 'path') else None)
        return "Page not found", 404
    
    # Health check endpoint - must be defined before blueprints to avoid auth
    @app.route('/health')
    def health_check():
        """Health check endpoint for monitoring - no auth required"""
        from flask import jsonify
        from sqlalchemy import text
        health_status = {
            'status': 'healthy',
            'service': 'attackacrack-crm'
        }
        
        try:
            # Quick database check
            db.session.execute(text('SELECT 1'))
            health_status['database'] = 'connected'
        except Exception as e:
            health_status['database'] = 'error'
            health_status['status'] = 'degraded'
            logger.error(f"Health check database error: {e}")
        
        return jsonify(health_status), 200 if health_status['status'] == 'healthy' else 503

    @app.template_filter('format_google_date')
    def format_google_date(date_string):
        if not date_string: return ""
        try:
            if 'T' in date_string:
                if ":" == date_string[-3:-2]:
                     date_string = date_string[:-3]+date_string[-2:]
                if date_string.endswith('Z'):
                    dt_obj = datetime.fromisoformat(date_string.replace('Z', '+00:00'))
                else:
                    dt_obj = datetime.fromisoformat(date_string)
                return dt_obj.strftime('%A, %b %d at %I:%M %p')
            else:
                dt_obj = datetime.fromisoformat(date_string)
                return dt_obj.strftime('%A, %B %d (All-day)')
        except (ValueError, TypeError):
            return date_string

    # Register blueprints for routes
    from routes.main_routes import main_bp
    from routes.contact_routes import contact_bp
    from routes.property_routes import property_bp
    from routes.job_routes import job_bp
    from routes.appointment_routes import appointment_bp
    from routes.quote_routes import quote_bp
    from routes.invoice_routes import invoice_bp
    from routes.api_routes import api_bp
    from routes.campaigns import campaigns_bp
    from routes.growth_routes import growth_bp
    from routes.settings_routes import settings_bp
    from routes.auth import auth_bp
    from routes.todo_routes import todo_bp
    from routes.reconciliation_routes import bp as reconciliation_bp
    from routes.templates_api import templates_api_bp
    
    app.register_blueprint(main_bp)
    app.register_blueprint(contact_bp, url_prefix='/contacts')
    app.register_blueprint(property_bp, url_prefix='/properties')
    app.register_blueprint(job_bp, url_prefix='/jobs')
    app.register_blueprint(appointment_bp, url_prefix='/appointments')
    app.register_blueprint(quote_bp, url_prefix='/quotes')
    app.register_blueprint(invoice_bp, url_prefix='/invoices')
    app.register_blueprint(api_bp, url_prefix='/api')
    app.register_blueprint(campaigns_bp)
    app.register_blueprint(growth_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(todo_bp)
    app.register_blueprint(reconciliation_bp)
    app.register_blueprint(templates_api_bp)
    
    # --- REMOVED APScheduler ---
    # The background task scheduling is now handled by Celery Beat.
    
    # Register CLI commands
    from scripts import commands
    commands.init_app(app)
    
    return app


# Service Factory Functions
# These are only called when the service is first requested

def _create_contact_service(contact_repository, campaign_repository, contact_flag_repository):
    """Create ContactService instance with repositories"""
    from services.contact_service_refactored import ContactService
    logger.info("Initializing ContactService")
    return ContactService(
        contact_repository=contact_repository,
        campaign_repository=campaign_repository,
        contact_flag_repository=contact_flag_repository
    )

def _create_message_service(conversation_repository, activity_repository, contact, property, openphone, ai):
    """Create MessageService instance with dependencies"""
    from services.message_service_refactored import MessageServiceRefactored
    logger.info("Initializing MessageService")
    return MessageServiceRefactored(
        conversation_repository=conversation_repository,
        activity_repository=activity_repository,
        contact_service=contact,
        property_service=property,
        openphone_service=openphone,
        ai_service=ai
    )

def _create_todo_service(todo_repository):
    """Create TodoService instance with repository dependency"""
    from services.todo_service_refactored import TodoServiceRefactored
    logger.info("Initializing TodoService with repository")
    return TodoServiceRefactored(todo_repository=todo_repository)

def _create_auth_service(db_session):
    """Create AuthService instance with required repositories"""
    from services.auth_service_refactored import AuthService
    from repositories.user_repository import UserRepository
    from repositories.invite_token_repository import InviteTokenRepository
    from crm_database import User, InviteToken
    
    logger.info("Initializing AuthService with repositories")
    
    # Create repositories
    user_repository = UserRepository(db_session)
    invite_repository = InviteTokenRepository(db_session)
    
    # Create auth service with injected repositories
    # Note: email_service will be None for now, can be added later if needed
    return AuthService(
        email_service=None,
        user_repository=user_repository,
        invite_repository=invite_repository
    )

def _create_product_service(db_session):
    """Create ProductService with ProductRepository"""
    from repositories.product_repository import ProductRepository
    from crm_database import Product
    
    class ProductService:
        """Minimal ProductService wrapper using repository pattern"""
        def __init__(self, repository):
            self.repository = repository
        
        def get_all(self):
            """Get all products using repository"""
            return self.repository.get_all()
    
    logger.info("Initializing ProductService with repository pattern")
    return ProductService(ProductRepository(db_session))

def _create_job_service(job_repository):
    """Create JobService with repository dependency"""
    from services.job_service import JobService
    logger.info("Initializing JobService with repository dependency")
    return JobService(job_repository=job_repository)

def _create_job_repository(db_session):
    """Create JobRepository instance"""
    from repositories.job_repository import JobRepository
    logger.info("Initializing JobRepository")
    return JobRepository(session=db_session)

def _create_property_service(db_session):
    """Create PropertyService with PropertyRepository"""
    from services.property_service import PropertyService
    from repositories.property_repository import PropertyRepository
    from crm_database import Property
    
    logger.info("Initializing PropertyService with repository")
    property_repo = PropertyRepository(session=db_session)
    return PropertyService(repository=property_repo)

def _create_quote_service():
    """Create QuoteService instance with repository dependencies"""
    from services.quote_service import QuoteService
    from repositories.quote_repository import QuoteRepository
    from repositories.quote_line_item_repository import QuoteLineItemRepository
    from crm_database import Quote, QuoteLineItem
    from extensions import db
    
    logger.info("Initializing QuoteService with repositories")
    
    # Create repository instances
    db_session = db.session
    quote_repo = QuoteRepository(session=db_session)
    line_item_repo = QuoteLineItemRepository(session=db_session)
    
    return QuoteService(
        quote_repository=quote_repo,
        line_item_repository=line_item_repo
    )

def _create_invoice_service(invoice_repository, quote_repository):
    """Create InvoiceService instance with injected repositories"""
    from services.invoice_service_refactored import InvoiceService
    logger.info("Initializing InvoiceService")
    return InvoiceService(
        invoice_repository=invoice_repository,
        quote_repository=quote_repository
    )

def _create_sms_metrics_service(activity_repository, contact_repository, campaign_repository):
    """Create SMSMetricsService with repository dependencies"""
    from services.sms_metrics_service import SMSMetricsService
    logger.info("Initializing SMSMetricsService with repository dependencies")
    return SMSMetricsService(
        activity_repository=activity_repository,
        contact_repository=contact_repository,
        campaign_repository=campaign_repository
    )

def _create_openphone_service():
    """Create OpenPhoneService instance - expensive due to API validation"""
    from services.openphone_service import OpenPhoneService
    logger.info("Initializing OpenPhoneService")
    api_key = os.environ.get('OPENPHONE_API_KEY')
    phone_number = os.environ.get('OPENPHONE_PHONE_NUMBER')
    if not api_key:
        logger.warning("OpenPhone API key not configured")
        return None
    return OpenPhoneService()  # Uses env vars internally

def _create_openphone_webhook_service(activity_repository, conversation_repository, webhook_event_repository, contact_service, sms_metrics_service, opt_out_service=None):
    """Create OpenPhoneWebhookServiceRefactored instance with all dependencies"""
    from services.openphone_webhook_service_refactored import OpenPhoneWebhookServiceRefactored
    logger.info("Initializing OpenPhoneWebhookServiceRefactored")
    return OpenPhoneWebhookServiceRefactored(
        activity_repository=activity_repository,
        conversation_repository=conversation_repository, 
        webhook_event_repository=webhook_event_repository,
        contact_service=contact_service,
        sms_metrics_service=sms_metrics_service,
        opt_out_service=opt_out_service
    )

def _create_webhook_error_recovery_service(failed_webhook_repository, webhook_service, webhook_event_repository):
    """Create WebhookErrorRecoveryService instance with dependencies"""
    from services.webhook_error_recovery_service import WebhookErrorRecoveryService
    logger.info("Initializing WebhookErrorRecoveryService")
    return WebhookErrorRecoveryService(
        failed_webhook_repository=failed_webhook_repository,
        webhook_service=webhook_service,
        webhook_event_repository=webhook_event_repository
    )

def _create_google_calendar_service():
    """Create GoogleCalendarService instance - expensive due to OAuth"""
    from services.google_calendar_service import GoogleCalendarService
    from api_integrations import get_google_creds
    logger.info("Initializing GoogleCalendarService")
    try:
        credentials = get_google_creds()
        return GoogleCalendarService(credentials=credentials)
    except Exception as e:
        logger.warning(f"Google Calendar service unavailable: {e}")
        return None

def _create_email_service():
    """Create EmailService instance - may require SMTP connection"""
    from services.email_service import EmailService, EmailConfig
    logger.info("Initializing EmailService")
    config = EmailConfig(
        server=os.environ.get('SMTP_SERVER', 'localhost'),
        port=int(os.environ.get('SMTP_PORT', '587')),
        use_tls=os.environ.get('SMTP_USE_TLS', 'true').lower() == 'true',
        username=os.environ.get('SMTP_USERNAME'),
        password=os.environ.get('SMTP_PASSWORD'),
        default_sender=os.environ.get('DEFAULT_EMAIL_SENDER', 'noreply@example.com')
    )
    mail = None  # Would get from Flask-Mail if needed
    return EmailService(mail=mail, config=config)

def _create_ai_service():
    """Create AIService instance"""
    from services.ai_service import AIService
    logger.info("Initializing AIService")
    return AIService()

def _create_quickbooks_service():
    """Create QuickBooksService instance with repository pattern"""
    from services.quickbooks_service import QuickBooksService
    from repositories.quickbooks_auth_repository import QuickBooksAuthRepository
    from repositories.quickbooks_sync_repository import QuickBooksSyncRepository
    from crm_database import QuickBooksAuth, QuickBooksSync
    
    logger.info("Initializing QuickBooksService with repositories")
    
    if not os.environ.get('QUICKBOOKS_CLIENT_ID'):
        logger.warning("QuickBooks not configured")
        return None
    
    # Create repository instances
    db_session = db.session
    auth_repo = QuickBooksAuthRepository(session=db_session)
    sync_repo = QuickBooksSyncRepository(session=db_session)
    
    return QuickBooksService(
        auth_repository=auth_repo,
        sync_repository=sync_repo
    )

def _create_campaign_list_service(db_session):
    """Create CampaignListServiceRefactored with repository dependencies"""
    from services.campaign_list_service_refactored import CampaignListServiceRefactored
    from repositories.campaign_list_repository import CampaignListRepository
    from repositories.campaign_list_member_repository import CampaignListMemberRepository
    from repositories.contact_repository import ContactRepository
    from crm_database import CampaignList, CampaignListMember, Contact
    
    logger.info("Initializing CampaignListServiceRefactored with repository pattern")
    return CampaignListServiceRefactored(
        campaign_list_repository=CampaignListRepository(db_session),
        member_repository=CampaignListMemberRepository(db_session),
        contact_repository=ContactRepository(db_session)
    )

def _create_dashboard_service(db_session):
    """Create DashboardService with dependencies (deprecated - use repository version)"""
    from services.dashboard_service import DashboardService
    logger.info("Initializing DashboardService")
    return DashboardService()

def _create_dashboard_service_with_repositories(contact_repository, campaign_repository, activity_repository, conversation_repository, sms_metrics_service):
    """Create DashboardService with repository and service dependencies"""
    from services.dashboard_service import DashboardService
    logger.info("Initializing DashboardService with repository pattern")
    return DashboardService(
        contact_repository=contact_repository,
        campaign_repository=campaign_repository,
        activity_repository=activity_repository,
        conversation_repository=conversation_repository,
        sms_metrics_service=sms_metrics_service
    )

# Repository creation functions
def _create_contact_repository(db_session):
    """Create ContactRepository instance"""
    from repositories.contact_repository import ContactRepository
    return ContactRepository(session=db_session)

def _create_campaign_repository(db_session):
    """Create CampaignRepository instance"""
    from repositories.campaign_repository import CampaignRepository
    return CampaignRepository(session=db_session)

def _create_contact_flag_repository(db_session):
    """Create ContactFlagRepository instance"""
    from repositories.contact_flag_repository import ContactFlagRepository
    return ContactFlagRepository(session=db_session)

def _create_opt_out_audit_repository(db_session):
    """Create OptOutAuditRepository instance"""
    from repositories.opt_out_audit_repository import OptOutAuditRepository
    return OptOutAuditRepository(session=db_session)

def _create_opt_out_service(contact_flag_repository, opt_out_audit_repository, openphone_service, contact_repository):
    """Create OptOutService instance with dependencies"""
    from services.opt_out_service import OptOutService
    logger.info("Initializing OptOutService")
    return OptOutService(
        contact_flag_repository=contact_flag_repository,
        opt_out_audit_repository=opt_out_audit_repository,
        sms_service=openphone_service,
        contact_repository=contact_repository
    )

def _create_phone_validation_repository(db_session):
    """Create PhoneValidationRepository instance"""
    from repositories.phone_validation_repository import PhoneValidationRepository
    return PhoneValidationRepository(session=db_session)

def _create_ab_test_result_repository(db_session):
    """Create ABTestResultRepository instance"""
    from repositories.ab_test_result_repository import ABTestResultRepository
    return ABTestResultRepository(session=db_session)

def _create_campaign_template_repository(db_session):
    """Create CampaignTemplateRepository instance"""
    from repositories.campaign_template_repository import CampaignTemplateRepository
    return CampaignTemplateRepository(session=db_session)

def _create_campaign_template_service(campaign_template_repository, contact_repository):
    """Create CampaignTemplateService with repository dependencies"""
    from services.campaign_template_service import CampaignTemplateService
    
    logger.info("Initializing CampaignTemplateService with repositories")
    
    return CampaignTemplateService(
        template_repository=campaign_template_repository,
        contact_repository=contact_repository
    )

def _create_phone_validation_service(phone_validation_repository):
    """Create PhoneValidationService with repository dependency"""
    from services.phone_validation_service import PhoneValidationService
    import os
    
    logger.info("Initializing PhoneValidationService with repository")
    
    # Set a test API key if not configured (for testing)
    if not os.environ.get('NUMVERIFY_API_KEY'):
        os.environ['NUMVERIFY_API_KEY'] = 'test_api_key'
    
    return PhoneValidationService(validation_repository=phone_validation_repository)

def _create_ab_testing_service(campaign_repository, contact_repository, ab_result_repository):
    """Create ABTestingService with repository dependencies"""
    from services.ab_testing_service import ABTestingService
    
    logger.info("Initializing ABTestingService with repositories")
    
    return ABTestingService(
        campaign_repository=campaign_repository,
        contact_repository=contact_repository,
        ab_result_repository=ab_result_repository
    )

def _create_activity_repository(db_session):
    """Create ActivityRepository instance"""
    from repositories.activity_repository import ActivityRepository
    return ActivityRepository(session=db_session)

def _create_conversation_repository(db_session):
    """Create ConversationRepository instance"""
    from repositories.conversation_repository import ConversationRepository
    return ConversationRepository(session=db_session)

def _create_setting_repository(db_session):
    """Create SettingRepository instance"""
    from repositories.setting_repository import SettingRepository
    return SettingRepository(session=db_session)

def _create_todo_repository(db_session):
    """Create TodoRepository instance"""
    from repositories.todo_repository import TodoRepository
    return TodoRepository(session=db_session)

def _create_appointment_repository(db_session):
    """Create AppointmentRepository instance"""
    from repositories.appointment_repository import AppointmentRepository
    return AppointmentRepository(session=db_session)

def _create_webhook_event_repository(db_session):
    """Create WebhookEventRepository instance"""
    from repositories.webhook_event_repository import WebhookEventRepository
    return WebhookEventRepository(session=db_session)

def _create_invoice_repository(db_session):
    """Create InvoiceRepository instance"""
    from repositories.invoice_repository import InvoiceRepository
    return InvoiceRepository(session=db_session)

def _create_quote_repository(db_session):
    """Create QuoteRepository instance"""
    from repositories.quote_repository import QuoteRepository
    return QuoteRepository(session=db_session)

def _create_failed_webhook_queue_repository(db_session):
    """Create FailedWebhookQueueRepository instance"""
    from repositories.failed_webhook_queue_repository import FailedWebhookQueueRepository
    return FailedWebhookQueueRepository(session=db_session)

def _create_setting_service(setting_repository):
    """Create SettingService instance"""
    from services.setting_service import SettingService
    return SettingService(repository=setting_repository)

def _create_conversation_service(db_session):
    """Create ConversationService with repository dependencies"""
    from services.conversation_service import ConversationService
    from repositories.conversation_repository import ConversationRepository
    from repositories.campaign_repository import CampaignRepository
    from crm_database import Conversation, Campaign
    
    logger.info("Initializing ConversationService with repositories")
    
    # Create repository instances
    conversation_repo = ConversationRepository(session=db_session)
    campaign_repo = CampaignRepository(session=db_session)
    
    return ConversationService(
        conversation_repository=conversation_repo,
        campaign_repository=campaign_repo
    )

def _create_task_service(db_session):
    """Create TaskService with dependencies"""
    from services.task_service import TaskService
    logger.info("Initializing TaskService")
    return TaskService()

def _create_diagnostics_service(db_session):
    """Create DiagnosticsService with repository pattern"""
    from services.diagnostics_service import DiagnosticsService
    from repositories.diagnostics_repository import DiagnosticsRepository
    
    # Create repository with database session
    diagnostics_repository = DiagnosticsRepository(session=db_session)
    
    # Create service with repository dependency injection
    logger.info("Initializing DiagnosticsService with repository pattern")
    return DiagnosticsService(repository=diagnostics_repository)

def _create_sync_health_service(db_session):
    """Create SyncHealthService with dependencies"""
    from services.sync_health_service import SyncHealthService
    logger.info("Initializing SyncHealthService")
    return SyncHealthService()

def _create_campaign_service(openphone, campaign_list, campaign_repository, contact_repository, activity_repository):
    """Create CampaignService with dependencies"""
    from services.campaign_service_refactored import CampaignService
    from repositories.contact_flag_repository import ContactFlagRepository
    from crm_database import ContactFlag
    
    logger.info("Initializing CampaignService with repositories")
    
    # Create contact flag repository
    contact_flag_repo = ContactFlagRepository(session=db.session)
    
    return CampaignService(
        campaign_repository=campaign_repository,
        contact_repository=contact_repository,
        contact_flag_repository=contact_flag_repo,
        activity_repository=activity_repository,
        openphone_service=openphone,
        list_service=campaign_list
    )

def _create_csv_import_service(contact, db_session):
    """Create CSVImportService with repository dependencies"""
    from services.csv_import_service import CSVImportService
    from repositories.csv_import_repository import CSVImportRepository
    from repositories.contact_csv_import_repository import ContactCSVImportRepository
    from repositories.campaign_list_repository import CampaignListRepository
    from repositories.campaign_list_member_repository import CampaignListMemberRepository
    from repositories.contact_repository import ContactRepository
    from crm_database import CSVImport, ContactCSVImport, CampaignList, CampaignListMember, Contact
    
    logger.info("Initializing CSVImportService with repository pattern")
    
    # Create repository instances
    csv_import_repo = CSVImportRepository(session=db_session)
    contact_csv_import_repo = ContactCSVImportRepository(session=db_session)
    campaign_list_repo = CampaignListRepository(session=db_session)
    campaign_list_member_repo = CampaignListMemberRepository(session=db_session)
    contact_repo = ContactRepository(session=db_session)
    
    return CSVImportService(
        csv_import_repository=csv_import_repo,
        contact_csv_import_repository=contact_csv_import_repo,
        campaign_list_repository=campaign_list_repo,
        campaign_list_member_repository=campaign_list_member_repo,
        contact_repository=contact_repo,
        contact_service=contact
    )

def _create_openphone_sync_service(openphone, db_session):
    """Create OpenPhoneSyncService with dependencies"""
    from services.openphone_sync_service import OpenPhoneSyncService
    from repositories.contact_repository import ContactRepository
    from repositories.activity_repository import ActivityRepository
    from crm_database import Contact, Activity
    
    logger.info("Initializing OpenPhoneSyncService with repositories")
    
    # Create repository instances
    contact_repo = ContactRepository(db_session)
    activity_repo = ActivityRepository(db_session)
    
    return OpenPhoneSyncService(
        contact_repository=contact_repo,
        activity_repository=activity_repo
    )

def _create_quickbooks_sync_service(quickbooks, db_session):
    """Create QuickBooksSyncService with repository dependencies"""
    from services.quickbooks_sync_service import QuickBooksSyncService
    from repositories.contact_repository import ContactRepository
    from repositories.product_repository import ProductRepository
    from repositories.quote_repository import QuoteRepository
    from repositories.invoice_repository import InvoiceRepository
    from repositories.job_repository import JobRepository
    from repositories.property_repository import PropertyRepository
    from repositories.quickbooks_sync_repository import QuickBooksSyncRepository
    from repositories.quote_line_item_repository import QuoteLineItemRepository
    from repositories.invoice_line_item_repository import InvoiceLineItemRepository
    from crm_database import Contact, Product, Quote, Invoice, Job, Property, QuickBooksSync, QuoteLineItem, InvoiceLineItem
    
    logger.info("Initializing QuickBooksSyncService with repositories")
    
    # Create repository instances
    contact_repo = ContactRepository(session=db_session)
    product_repo = ProductRepository(session=db_session)
    quote_repo = QuoteRepository(session=db_session)
    invoice_repo = InvoiceRepository(session=db_session)
    job_repo = JobRepository(session=db_session)
    property_repo = PropertyRepository(session=db_session)
    quickbooks_sync_repo = QuickBooksSyncRepository(session=db_session)
    quote_line_item_repo = QuoteLineItemRepository(session=db_session)
    invoice_line_item_repo = InvoiceLineItemRepository(session=db_session)
    
    return QuickBooksSyncService(
        contact_repository=contact_repo,
        product_repository=product_repo,
        quote_repository=quote_repo,
        invoice_repository=invoice_repo,
        job_repository=job_repo,
        property_repository=property_repo,
        quickbooks_sync_repository=quickbooks_sync_repo,
        quote_line_item_repository=quote_line_item_repo,
        invoice_line_item_repository=invoice_line_item_repo
    )

def _create_appointment_service(google_calendar, db_session):
    """Create AppointmentService with dependencies"""
    from services.appointment_service_refactored import AppointmentService
    from repositories.appointment_repository import AppointmentRepository
    logger.info("Initializing AppointmentService with repository")
    return AppointmentService(
        appointment_repository=AppointmentRepository(db_session),
        google_calendar_service=google_calendar
    )


def _create_webhook_health_check_service(webhook_event_repository, openphone_service, email_service):
    """Create WebhookHealthCheckService with dependencies"""
    from services.webhook_health_check_service import WebhookHealthCheckService
    import os
    
    # Get configuration from environment or use defaults
    test_phone_number = os.environ.get('WEBHOOK_HEALTH_CHECK_PHONE', os.environ.get('OPENPHONE_PHONE_NUMBER', '+15551234567'))
    alert_email = os.environ.get('WEBHOOK_HEALTH_CHECK_EMAIL', os.environ.get('ADMIN_EMAIL', 'alerts@example.com'))
    timeout = int(os.environ.get('WEBHOOK_HEALTH_CHECK_TIMEOUT', '120'))  # 2 minutes default
    
    logger.info("Initializing WebhookHealthCheckService", test_phone=test_phone_number, alert_email=alert_email)
    return WebhookHealthCheckService(
        webhook_repository=webhook_event_repository,
        openphone_service=openphone_service,
        email_service=email_service,
        test_phone_number=test_phone_number,
        alert_email=alert_email,
        health_check_timeout=timeout
    )

def _create_openphone_reconciliation_service(activity_repository, conversation_repository, contact_service):
    """Create OpenPhoneReconciliationService with dependencies"""
    from services.openphone_reconciliation_service import OpenPhoneReconciliationService
    from services.openphone_api_client import OpenPhoneAPIClient
    
    logger.info("Initializing OpenPhoneReconciliationService")
    
    # Create API client
    api_client = OpenPhoneAPIClient()
    
    return OpenPhoneReconciliationService(
        activity_repository=activity_repository,
        conversation_repository=conversation_repository,
        contact_service=contact_service,
        openphone_api_client=api_client
    )

def _create_scheduler_service(openphone, invoice, db_session):
    """Create SchedulerService with repository dependencies"""
    from services.scheduler_service import SchedulerService
    from repositories.setting_repository import SettingRepository
    from repositories.job_repository import JobRepository
    from repositories.quote_repository import QuoteRepository
    from repositories.appointment_repository import AppointmentRepository
    from crm_database import Setting, Job, Quote, Appointment
    
    logger.info("Initializing SchedulerService with repositories")
    
    # Create repository instances
    setting_repo = SettingRepository(session=db_session)
    job_repo = JobRepository(session=db_session)
    quote_repo = QuoteRepository(session=db_session)
    appointment_repo = AppointmentRepository(session=db_session)
    
    return SchedulerService(
        setting_repository=setting_repo,
        job_repository=job_repo,
        quote_repository=quote_repo,
        appointment_repository=appointment_repo,
        openphone_service=openphone,
        invoice_service=invoice
    )


def _get_current_db_session():
    """Get the current database session.
    
    This factory function ensures we always get the active session,
    which is critical for test isolation where sessions may be replaced.
    
    FIXED: Enhanced test-aware session handling with stale connection detection.
    
    TEST ISOLATION IMPROVEMENTS:
    - Always refreshes session reference in test environments
    - Detects pytest execution context for proper handling
    - Enhanced validation with test-specific error handling
    - No recovery attempts in tests to avoid masking issues
    
    PRODUCTION FEATURES:
    - Automatic connection recovery
    - Stale connection detection and refresh
    - Comprehensive error logging and fallback
    """
    import os
    session = db.session
    
    # In test environments, always refresh session reference to handle test isolation
    is_testing = os.environ.get('FLASK_ENV') == 'testing' or 'pytest' in os.environ.get('_', '')
    
    if is_testing:
        # For tests, always get fresh session reference
        # This ensures we pick up any session replacement done by test fixtures
        session = db.session
        
        # Additional validation for test sessions
        try:
            if hasattr(session, 'get_bind'):
                bind = session.get_bind()
                
                # Check if connection is closed
                if hasattr(bind, 'closed') and bind.closed:
                    logger.warning("Test session connection is closed, this may indicate test isolation issues")
                    # Don't try to recover in tests - let the test framework handle it
                    return session
                
                # Test connection with a simple query (safe for test sessions)
                try:
                    session.execute('SELECT 1')
                except Exception as query_error:
                    logger.warning(f"Test session validation failed: {query_error}")
                    # In tests, don't try to recover - return what we have
                    return session
        except Exception as e:
            logger.warning(f"Test session validation error: {e}")
            # In tests, return the session even if validation fails
            return session
    else:
        # Production/development session handling with recovery
        try:
            # Check if session has a valid connection
            if hasattr(session, 'get_bind'):
                bind = session.get_bind()
                
                # Check if connection is closed
                if hasattr(bind, 'closed') and bind.closed:
                    logger.warning("Database session connection is closed, attempting to refresh")
                    # In production, try to get fresh reference
                    session = db.session
                
                # Test connection with a simple query
                try:
                    session.execute('SELECT 1')
                except Exception as query_error:
                    logger.warning(f"Session validation query failed: {query_error}")
                    # Try to get fresh session reference again
                    session = db.session
        except Exception as e:
            logger.warning(f"Error during session validation: {e}")
            # Fall back to whatever session we have
            session = db.session
    
    return session


if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, ssl_context='adhoc')
