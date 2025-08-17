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
    registry.register('db_session', service=db.session)
    
    # Register services with lazy loading factories
    # These won't be instantiated until first use
    
    # Basic services without dependencies
    registry.register_singleton('contact', lambda: _create_contact_service())
    registry.register_singleton('message', lambda: _create_message_service())
    registry.register_singleton('todo', lambda: _create_todo_service())
    registry.register_singleton('auth', lambda: _create_auth_service())
    registry.register_singleton('job', lambda: _create_job_service())
    registry.register_singleton('quote', lambda: _create_quote_service())
    registry.register_singleton('invoice', lambda: _create_invoice_service())
    
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
    
    registry.register_factory(
        'dashboard',
        lambda db_session: _create_dashboard_service(db_session),
        dependencies=['db_session']
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
    
    # Services with multiple dependencies
    registry.register_factory(
        'campaign',
        lambda openphone, campaign_list: _create_campaign_service(openphone, campaign_list),
        dependencies=['openphone', 'campaign_list']
    )
    
    registry.register_factory(
        'csv_import',
        lambda contact: _create_csv_import_service(contact),
        dependencies=['contact']
    )
    
    registry.register_factory(
        'openphone_sync',
        lambda openphone, db_session: _create_openphone_sync_service(openphone, db_session),
        dependencies=['openphone', 'db_session']
    )
    
    registry.register_factory(
        'openphone_webhook',
        lambda contact, sms_metrics: _create_openphone_webhook_service(contact, sms_metrics),
        dependencies=['contact', 'sms_metrics']
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
    
    # --- REMOVED APScheduler ---
    # The background task scheduling is now handled by Celery Beat.
    
    # Register CLI commands
    from scripts import commands
    commands.init_app(app)
    
    return app


# Service Factory Functions
# These are only called when the service is first requested

def _create_contact_service():
    """Create ContactService instance"""
    from services.contact_service_refactored import ContactService
    logger.info("Initializing ContactService")
    return ContactService()

def _create_message_service():
    """Create MessageService instance"""
    from services.message_service import MessageService
    logger.info("Initializing MessageService")
    return MessageService()

def _create_todo_service():
    """Create TodoService instance"""
    from services.todo_service import TodoService
    logger.info("Initializing TodoService")
    return TodoService()

def _create_auth_service():
    """Create AuthService instance"""
    from services.auth_service import AuthService
    logger.info("Initializing AuthService")
    return AuthService()

def _create_job_service():
    """Create JobService instance"""
    from services.job_service import JobService
    logger.info("Initializing JobService")
    return JobService()

def _create_quote_service():
    """Create QuoteService instance"""
    from services.quote_service import QuoteService
    logger.info("Initializing QuoteService")
    return QuoteService()

def _create_invoice_service():
    """Create InvoiceService instance"""
    from services.invoice_service import InvoiceService
    logger.info("Initializing InvoiceService")
    return InvoiceService()

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
    """Create QuickBooksService instance"""
    from services.quickbooks_service import QuickBooksService
    logger.info("Initializing QuickBooksService")
    if not os.environ.get('QUICKBOOKS_CLIENT_ID'):
        logger.warning("QuickBooks not configured")
        return None
    return QuickBooksService()

def _create_campaign_list_service(db_session):
    """Create CampaignListService with dependencies"""
    from services.campaign_list_service import CampaignListService
    logger.info("Initializing CampaignListService")
    return CampaignListService()

def _create_dashboard_service(db_session):
    """Create DashboardService with dependencies"""
    from services.dashboard_service import DashboardService
    logger.info("Initializing DashboardService")
    return DashboardService()

def _create_conversation_service(db_session):
    """Create ConversationService with dependencies"""
    from services.conversation_service import ConversationService
    logger.info("Initializing ConversationService")
    return ConversationService()

def _create_task_service(db_session):
    """Create TaskService with dependencies"""
    from services.task_service import TaskService
    logger.info("Initializing TaskService")
    return TaskService()

def _create_diagnostics_service(db_session):
    """Create DiagnosticsService with dependencies"""
    from services.diagnostics_service import DiagnosticsService
    logger.info("Initializing DiagnosticsService")
    return DiagnosticsService()

def _create_sync_health_service(db_session):
    """Create SyncHealthService with dependencies"""
    from services.sync_health_service import SyncHealthService
    logger.info("Initializing SyncHealthService")
    return SyncHealthService()

def _create_campaign_service(openphone, campaign_list):
    """Create CampaignService with dependencies"""
    from services.campaign_service import CampaignService
    logger.info("Initializing CampaignService")
    return CampaignService(
        openphone_service=openphone,
        list_service=campaign_list
    )

def _create_csv_import_service(contact):
    """Create CSVImportService with dependencies"""
    from services.csv_import_service import CSVImportService
    logger.info("Initializing CSVImportService")
    return CSVImportService(contact_service=contact)

def _create_openphone_sync_service(openphone, db_session):
    """Create OpenPhoneSyncService with dependencies"""
    from services.openphone_sync_service import OpenPhoneSyncService
    logger.info("Initializing OpenPhoneSyncService")
    return OpenPhoneSyncService()

def _create_openphone_webhook_service(contact, sms_metrics):
    """Create OpenPhoneWebhookService with dependencies"""
    from services.openphone_webhook_service import OpenPhoneWebhookService
    logger.info("Initializing OpenPhoneWebhookService")
    return OpenPhoneWebhookService(contact_service=contact, metrics_service=sms_metrics)

def _create_quickbooks_sync_service(quickbooks, db_session):
    """Create QuickBooksSyncService with dependencies"""
    from services.quickbooks_sync_service import QuickBooksSyncService
    logger.info("Initializing QuickBooksSyncService")
    return QuickBooksSyncService()

def _create_appointment_service(google_calendar, db_session):
    """Create AppointmentService with dependencies"""
    from services.appointment_service_refactored import AppointmentService
    logger.info("Initializing AppointmentService")
    return AppointmentService(calendar_service=google_calendar, session=db_session)


if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, ssl_context='adhoc')
