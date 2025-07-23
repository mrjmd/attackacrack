# app.py

from flask import Flask
from config import Config
from extensions import db
from datetime import datetime

def create_app(config_class=Config):
    """Create and configure an instance of the Flask application."""
    app = Flask(__name__)
    
    # Load configuration from the Config object
    app.config.from_object(config_class)

    # Initialize extensions with the app
    db.init_app(app)

    # --- CUSTOM TEMPLATE FILTER ---
    # This filter will be available in all Jinja2 templates.
    @app.template_filter('format_google_date')
    def format_google_date(date_string):
        """
        Parses Google API's date or dateTime string and formats it nicely.
        """
        if not date_string:
            return ""
        try:
            # Handle dateTime with timezone offset (e.g., -04:00 or Z)
            if 'T' in date_string:
                # The googleapiclient can return offsets with ':', which some Python versions dislike.
                if ":" == date_string[-3:-2]:
                     date_string = date_string[:-3]+date_string[-2:]
                # Handle 'Z' for UTC
                if date_string.endswith('Z'):
                    dt_obj = datetime.fromisoformat(date_string.replace('Z', '+00:00'))
                else:
                    dt_obj = datetime.fromisoformat(date_string)
                return dt_obj.strftime('%A, %b %d at %I:%M %p')
            # Handle all-day date
            else:
                dt_obj = datetime.fromisoformat(date_string)
                return dt_obj.strftime('%A, %B %d (All-day)')
        except (ValueError, TypeError):
            return date_string # Return original string if parsing fails
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

    with app.app_context():
        # Create database tables if they do not exist
        db.create_all()

    return app

# This part is for running directly (e.g., python app.py)
if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, ssl_context='adhoc')
