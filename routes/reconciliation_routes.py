"""
OpenPhone Reconciliation Routes

Admin routes for managing OpenPhone data reconciliation.
"""

from flask import Blueprint, render_template, jsonify, request, flash, redirect, url_for, current_app
from auth_utils import login_required, current_user
import logging
from datetime import datetime

from tasks.reconciliation_tasks import run_manual_reconciliation

logger = logging.getLogger(__name__)

bp = Blueprint('reconciliation', __name__, url_prefix='/admin/reconciliation')


def admin_required(f):
    """Decorator to ensure user is admin"""
    from functools import wraps
    
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if not current_user.is_admin:
            flash('Admin access required', 'error')
            return redirect(url_for('main.dashboard'))
        return f(*args, **kwargs)
    return decorated_function


@bp.route('/')
@admin_required
def index():
    """Reconciliation dashboard"""
    try:
        # Get reconciliation service
        reconciliation_service = current_app.services.get('openphone_reconciliation')
        
        if not reconciliation_service:
            flash('Reconciliation service not available', 'error')
            stats = {}
        else:
            stats = reconciliation_service.get_reconciliation_stats()
        
        return render_template('admin/reconciliation.html', stats=stats)
        
    except Exception as e:
        logger.error(f"Error loading reconciliation dashboard: {e}")
        flash('Error loading reconciliation dashboard', 'error')
        return redirect(url_for('main.dashboard'))


@bp.route('/run', methods=['POST'])
@admin_required
def run_reconciliation():
    """Manually trigger reconciliation"""
    try:
        hours_back = int(request.form.get('hours_back', 24))
        
        # Queue the reconciliation task
        task = run_manual_reconciliation.delay(
            hours_back=hours_back,
            user_id=current_user.id
        )
        
        flash(f'Reconciliation task queued (ID: {task.id}). Processing last {hours_back} hours.', 'success')
        
        return jsonify({
            'success': True,
            'task_id': task.id,
            'message': f'Reconciliation started for last {hours_back} hours'
        })
        
    except Exception as e:
        logger.error(f"Error starting reconciliation: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bp.route('/status')
@admin_required
def status():
    """Get current reconciliation status"""
    try:
        reconciliation_service = current_app.services.get('openphone_reconciliation')
        
        if not reconciliation_service:
            return jsonify({
                'success': False,
                'error': 'Service not available'
            }), 503
        
        stats = reconciliation_service.get_reconciliation_stats()
        
        # Format dates for JSON
        if stats.get('last_run'):
            stats['last_run'] = stats['last_run'].isoformat()
        
        return jsonify({
            'success': True,
            'stats': stats
        })
        
    except Exception as e:
        logger.error(f"Error getting reconciliation status: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bp.route('/validate', methods=['POST'])
@admin_required
def validate_integrity():
    """Run data integrity validation"""
    try:
        from tasks.reconciliation_tasks import validate_data_integrity
        
        # Queue the validation task
        task = validate_data_integrity.delay()
        
        flash(f'Data integrity validation queued (Task ID: {task.id})', 'info')
        
        return jsonify({
            'success': True,
            'task_id': task.id,
            'message': 'Data integrity validation started'
        })
        
    except Exception as e:
        logger.error(f"Error starting validation: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500