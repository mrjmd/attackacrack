# app.py

from flask import Flask
from flask_migrate import Migrate
from config import Config
from extensions import db
from datetime import datetime
import os
from werkzeug.middleware.proxy_fix import ProxyFix

def create_app(config_class=Config, test_config=None):
    """Create and configure an instance of the Flask application."""
    app = Flask(__name__)
    
    app.config.from_object(config_class)
    
    if test_config:
        app.config.update(test_config)

    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

    db.init_app(app)
    migrate = Migrate(app, db)

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
    
    app.register_blueprint(main_bp)
    app.register_blueprint(contact_bp, url_prefix='/contacts')
    app.register_blueprint(property_bp, url_prefix='/properties')
    app.register_blueprint(job_bp, url_prefix='/jobs')
    app.register_blueprint(appointment_bp, url_prefix='/appointments')
    app.register_blueprint(quote_bp, url_prefix='/quotes')
    app.register_blueprint(invoice_bp, url_prefix='/invoices')
    app.register_blueprint(api_bp, url_prefix='/api')
    
    # --- REMOVED APScheduler ---
    # The background task scheduling is now handled by Celery Beat.
    
    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, ssl_context='adhoc')
