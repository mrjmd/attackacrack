# app.py

from flask import Flask
from flask_migrate import Migrate
from config import Config
from extensions import db
from datetime import datetime
import os
from apscheduler.schedulers.background import BackgroundScheduler

# The 'commands' import is removed as the file no longer exists.

def create_app(config_class=Config):
    """Create and configure an instance of the Flask application."""
    app = Flask(__name__)
    
    # Load configuration from the Config object
    app.config.from_object(config_class)

    # Initialize extensions with the app
    db.init_app(app)
    migrate = Migrate(app, db)

    # --- CUSTOM TEMPLATE FILTER ---
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
    # --- END CUSTOM FILTER ---

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
    
    # --- INITIALIZE SCHEDULER ---
    from services.scheduler_service import SchedulerService
    
    scheduler = BackgroundScheduler(daemon=True)
    
    def job_wrapper():
        with app.app_context():
            service = SchedulerService()
            service.send_appointment_reminders()

    scheduler.add_job(job_wrapper, 'cron', hour=8, minute=0)
    
    if os.environ.get('WERKZEUG_RUN_MAIN') or app.config.get('FLASK_ENV') == 'production':
        scheduler.start()
        print("--- Background scheduler started. ---")
    # --- END SCHEDULER ---

    return app

# This part is for running directly (e.g., python app.py)
if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, ssl_context='adhoc')
