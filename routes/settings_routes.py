"""
Settings routes for system configuration and data management
"""

from flask import Blueprint, render_template, request, flash, redirect, url_for, current_app
from auth_utils import login_required
# Direct model imports removed - use services only
from extensions import db
from datetime import datetime, timedelta
import uuid
import os

settings_bp = Blueprint('settings', __name__)


@settings_bp.route('/imports')
@login_required
def imports():
    """Data imports dashboard - QuickBooks, PropertyRadar, etc."""
    return render_template('settings/imports.html')


@settings_bp.route('/automation')
@login_required
def automation():
    """Automation configuration - messages, scheduling rules, etc."""
    return render_template('settings/automation.html')


@settings_bp.route('/sync-health')
@login_required
def sync_health():
    """Sync health monitoring - webhook status, reconciliation, etc."""
    sync_health_service = current_app.services.get('sync_health')
    health_data = sync_health_service.get_sync_health_status()
    
    return render_template('settings/sync_health.html',
                         active_tasks=health_data.get('active_tasks'),
                         scheduled_tasks=health_data.get('scheduled_tasks'),
                         recent_tasks=health_data.get('recent_tasks', []),
                         celery_available=health_data.get('celery_available', False))


@settings_bp.route('/openphone')
@login_required
def openphone():
    """OpenPhone sync management"""
    openphone_sync_service = current_app.services.get('openphone_sync')
    sync_stats = openphone_sync_service.get_sync_statistics()
    
    return render_template('settings/openphone.html',
                         total_contacts=sync_stats['total_contacts'],
                         total_messages=sync_stats['total_messages'],
                         last_sync=sync_stats['last_sync'])


@settings_bp.route('/openphone/sync', methods=['POST'])
@login_required
def openphone_sync():
    """Run manual OpenPhone sync"""
    openphone_sync_service = current_app.services.get('openphone_sync')
    
    # Get parameters from form
    sync_type = request.form.get('sync_type', 'recent')
    custom_days = request.form.get('custom_days', type=int)
    track_bounces = request.form.get('track_bounces') == 'true'
    
    # Determine days to sync
    days_back = openphone_sync_service.determine_sync_days(sync_type, custom_days)
    
    # Queue the sync task
    success, message, task_id = openphone_sync_service.queue_sync_task(days_back, track_bounces)
    
    if success:
        flash(message, 'success')
    else:
        flash(message, 'error')
        if task_id:  # task_id contains the command hint in failure case
            flash(task_id, 'info')
    
    return redirect(url_for('settings.openphone'))


@settings_bp.route('/quickbooks')
@login_required
def quickbooks():
    """QuickBooks integration settings"""
    qb_service = current_app.services.get('quickbooks')
    
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
@login_required
def quickbooks_sync():
    """Manually trigger QuickBooks sync"""
    try:
        sync_service = current_app.services.get('quickbooks_sync')
        
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