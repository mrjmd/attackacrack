"""
Settings routes for system configuration and data management
"""

from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_required
from services.quickbooks_service import QuickBooksService
from services.quickbooks_sync_service import QuickBooksSyncService
from crm_database import db, QuickBooksAuth
from datetime import datetime, timedelta
import uuid

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
    # Initialize with empty data
    active_tasks = None
    scheduled_tasks = None
    recent_tasks = []
    celery_available = False
    
    try:
        from celery.result import AsyncResult
        import os
        
        # Handle SSL Redis configuration
        redis_url = os.environ.get('REDIS_URL', '')
        if redis_url.startswith('rediss://'):
            # For production SSL Redis, we need to configure Celery properly
            from celery_config import create_celery_app
            celery = create_celery_app('attackacrack')
        else:
            # For local non-SSL Redis, use the regular approach
            from celery_worker import celery
        
        # Check if Celery is available
        inspect = celery.control.inspect()
        active_tasks = inspect.active()
        scheduled_tasks = inspect.scheduled()
        celery_available = True
    except Exception as e:
        # Log the error but don't crash the page
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"Celery not available for sync health: {e}")
    
    return render_template('settings/sync_health.html',
                         active_tasks=active_tasks,
                         scheduled_tasks=scheduled_tasks,
                         recent_tasks=recent_tasks,
                         celery_available=celery_available)


@settings_bp.route('/openphone')
@login_required
def openphone():
    """OpenPhone sync management"""
    from services.openphone_service import OpenPhoneService
    from crm_database import Activity, Contact
    from datetime import datetime, timedelta
    
    # Get sync statistics
    total_contacts = Contact.query.filter(Contact.phone.isnot(None)).count()
    total_messages = Activity.query.filter_by(activity_type='sms').count()
    
    # Get last sync time (most recent message)
    last_activity = Activity.query.filter_by(activity_type='sms').order_by(Activity.created_at.desc()).first()
    last_sync = last_activity.created_at if last_activity else None
    
    return render_template('settings/openphone.html',
                         total_contacts=total_contacts,
                         total_messages=total_messages,
                         last_sync=last_sync)


@settings_bp.route('/openphone/sync', methods=['POST'])
@login_required
def openphone_sync():
    """Run manual OpenPhone sync"""
    from services.openphone_service import OpenPhoneService
    from tasks.sync_tasks import sync_openphone_messages
    
    # Get parameters from form
    sync_type = request.form.get('sync_type', 'recent')
    custom_days = request.form.get('custom_days', type=int)
    
    # Determine days to sync
    if sync_type == 'last_7':
        days_back = 7
    elif sync_type == 'last_30':
        days_back = 30
    elif sync_type == 'last_90':
        days_back = 90
    elif sync_type == 'full':
        # Full sync - use a very large number of days (10 years)
        days_back = 3650
    elif sync_type == 'custom' and custom_days:
        days_back = custom_days
    else:
        days_back = 30  # default
    
    try:
        # Queue the sync task
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Attempting to queue sync task for {days_back} days")
        
        # Handle SSL Redis configuration
        import os
        redis_url = os.environ.get('REDIS_URL', '')
        if redis_url.startswith('rediss://'):
            # For production SSL Redis, we need to configure Celery properly
            from celery_config import create_celery_app
            celery = create_celery_app('attackacrack')
            # Import the task with the properly configured Celery instance
            from tasks.sync_tasks import sync_openphone_messages
            # Use fire-and-forget mode to avoid timeout
            task_id = str(uuid.uuid4())
            sync_openphone_messages.apply_async(
                args=[days_back], 
                app=celery,
                task_id=task_id,
                ignore_result=True  # Don't wait for backend connection
            )
            logger.info(f"Task queued successfully with ID: {task_id}")
            flash(f'OpenPhone sync started for last {days_back} days. Check sync health for progress.', 'success')
        else:
            # For local non-SSL Redis, use the regular approach
            task = sync_openphone_messages.delay(days_back=days_back)
            logger.info(f"Task queued successfully with ID: {task.id}")
            flash(f'OpenPhone sync started for last {days_back} days. Task ID: {task.id}', 'success')
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error queuing sync task: {str(e)}", exc_info=True)
        flash(f'Error starting sync: {str(e)}', 'error')
    
    return redirect(url_for('settings.openphone'))


@settings_bp.route('/quickbooks')
@login_required
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
@login_required
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