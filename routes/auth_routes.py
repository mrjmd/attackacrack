"""
Authentication routes for OAuth integrations
"""

from flask import Blueprint, request, redirect, url_for, flash, render_template, session
from services.quickbooks_service import QuickBooksService
from services.quickbooks_sync_service import QuickBooksSyncService

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/auth/quickbooks')
def quickbooks_auth():
    """Redirect to QuickBooks OAuth"""
    qb_service = QuickBooksService()
    
    # Generate state for CSRF protection
    import secrets
    state = secrets.token_urlsafe(32)
    session['qb_oauth_state'] = state
    
    # Get authorization URL
    auth_url = qb_service.get_authorization_url(state)
    
    # Debug logging
    import logging
    logging.info(f"QuickBooks OAuth URL: {auth_url}")
    logging.info(f"Sandbox mode: {qb_service.sandbox}")
    logging.info(f"API base URL: {qb_service.api_base_url}")
    
    return redirect(auth_url)


@auth_bp.route('/auth/quickbooks/callback')
def quickbooks_callback():
    """Handle QuickBooks OAuth callback"""
    # Verify state
    state = request.args.get('state')
    if not state or state != session.get('qb_oauth_state'):
        flash('Invalid OAuth state', 'error')
        return redirect(url_for('main.settings'))
    
    # Clear state from session
    session.pop('qb_oauth_state', None)
    
    # Check for errors
    error = request.args.get('error')
    if error:
        flash(f'QuickBooks authorization failed: {error}', 'error')
        return redirect(url_for('main.settings'))
    
    # Exchange code for tokens
    code = request.args.get('code')
    if not code:
        flash('No authorization code received', 'error')
        return redirect(url_for('main.settings'))
    
    try:
        qb_service = QuickBooksService()
        tokens = qb_service.exchange_code_for_tokens(code)
        
        flash('Successfully connected to QuickBooks!', 'success')
        
        # Optionally trigger initial sync
        # sync_service = QuickBooksSyncService()
        # sync_service.sync_all()
        
        return redirect(url_for('settings.quickbooks'))
        
    except Exception as e:
        flash(f'Failed to connect to QuickBooks: {str(e)}', 'error')
        return redirect(url_for('main.settings'))


@auth_bp.route('/auth/quickbooks/disconnect', methods=['POST'])
def quickbooks_disconnect():
    """Disconnect from QuickBooks"""
    try:
        from crm_database import db, QuickBooksAuth
        
        # Delete all auth records
        QuickBooksAuth.query.delete()
        db.session.commit()
        
        flash('Disconnected from QuickBooks', 'info')
    except Exception as e:
        flash(f'Error disconnecting: {str(e)}', 'error')
    
    return redirect(url_for('settings.quickbooks'))