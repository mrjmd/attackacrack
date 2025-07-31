"""
Settings routes for system configuration and data management
"""

from flask import Blueprint, render_template, request, flash, redirect, url_for
from services.quickbooks_service import QuickBooksService
from services.quickbooks_sync_service import QuickBooksSyncService
from crm_database import db, QuickBooksAuth

settings_bp = Blueprint('settings', __name__)


@settings_bp.route('/imports')
def imports():
    """Data imports dashboard - QuickBooks, PropertyRadar, etc."""
    return render_template('settings/imports.html')


@settings_bp.route('/automation')
def automation():
    """Automation configuration - messages, scheduling rules, etc."""
    return render_template('settings/automation.html')


@settings_bp.route('/sync-health')
def sync_health():
    """Sync health monitoring - webhook status, reconciliation, etc."""
    return render_template('settings/sync_health.html')


@settings_bp.route('/quickbooks')
def quickbooks():
    """QuickBooks integration settings"""
    qb_service = QuickBooksService()
    
    # Check if authenticated
    is_authenticated = qb_service.is_authenticated()
    company_info = None
    
    if is_authenticated:
        try:
            company_info = qb_service.get_company_info()
        except Exception as e:
            flash(f'Error fetching company info: {str(e)}', 'error')
    
    return render_template('settings/quickbooks.html', 
                         is_authenticated=is_authenticated,
                         company_info=company_info)


@settings_bp.route('/quickbooks/sync', methods=['POST'])
def quickbooks_sync():
    """Manually trigger QuickBooks sync"""
    try:
        sync_service = QuickBooksSyncService()
        
        # Get sync type from form
        sync_type = request.form.get('sync_type', 'all')
        
        if sync_type == 'all':
            results = sync_service.sync_all()
            flash(f'Sync completed: {results}', 'success')
        elif sync_type == 'customers':
            results = sync_service.sync_customers()
            flash(f'Customer sync completed: {results["updated"]} updated, {results["errors"]} errors', 'success')
        elif sync_type == 'items':
            results = sync_service.sync_items()
            flash(f'Item sync completed: {results["created"]} created, {results["updated"]} updated', 'success')
        elif sync_type == 'estimates':
            results = sync_service.sync_estimates()
            flash(f'Estimate sync completed: {results["created"]} created, {results["updated"]} updated', 'success')
        elif sync_type == 'invoices':
            results = sync_service.sync_invoices()
            flash(f'Invoice sync completed: {results["created"]} created, {results["updated"]} updated', 'success')
        
    except Exception as e:
        flash(f'Sync failed: {str(e)}', 'error')
    
    return redirect(url_for('settings.quickbooks'))