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
        health_status = {
            'status': 'healthy',
            'service': 'attackacrack-crm'
        }
        
        try:
            # Quick database check
            db.session.execute('SELECT 1')
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
    
    # --- REMOVED APScheduler ---
    # The background task scheduling is now handled by Celery Beat.
    
    # Register CLI commands
    from scripts import commands
    commands.init_app(app)
    
    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, ssl_context='adhoc')
