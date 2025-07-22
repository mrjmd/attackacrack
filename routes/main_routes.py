# routes/main_routes.py

from flask import Blueprint, render_template, session, redirect, url_for, request, flash
from integrations import IntegrationManager
import os

main_bp = Blueprint('main', __name__)

# This needs to be instantiated here or passed in, but for simplicity,
# we'll create an instance. In a larger app, you might use a factory pattern.
integration_manager = IntegrationManager()

@main_bp.route('/')
def index():
    """Renders the main dashboard page."""
    return render_template('dashboard.html')

@main_bp.route('/settings')
def settings_page():
    """Renders the settings page for API configurations."""
    return render_template('settings.html')

# --- Google Authentication Routes ---
@main_bp.route('/authorize/google')
def authorize_google():
    try:
        flow = integration_manager.get_google_auth_flow()
        authorization_url, state = flow.authorization_url(access_type='offline', include_granted_scopes='true')
        session['state'] = state
        return redirect(authorization_url)
    except FileNotFoundError as e:
        flash(str(e), 'error')
        return redirect(url_for('main.settings_page'))
    except Exception as e:
        flash(f"An error occurred during Google authorization: {e}", 'error')
        return redirect(url_for('main.settings_page'))


@main_bp.route('/oauth2callback')
def oauth2callback():
    state = session['state']
    flow = integration_manager.get_google_auth_flow()
    # Specify the absolute redirect_uri to prevent mismatch error in production
    flow.redirect_uri = url_for('main.oauth2callback', _external=True, _scheme='https')
    flow.fetch_token(authorization_response=request.url)
    
    credentials = flow.credentials
    integration_manager.save_google_credentials(credentials)
    
    flash('Google Account connected successfully!', 'success')
    return redirect(url_for('main.index'))
