"""
Settings routes for system configuration and data management
"""

from flask import Blueprint, render_template

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