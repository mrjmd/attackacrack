"""
Growth routes for financials and business development
"""

from flask import Blueprint, render_template

growth_bp = Blueprint('growth', __name__)


@growth_bp.route('/financials')
def financials():
    """Financial dashboard showing revenue, expenses, and profitability"""
    # Placeholder for now - will implement financial reporting
    return render_template('growth/financials.html')


@growth_bp.route('/reports')
def reports():
    """Business reports and analytics"""
    return render_template('growth/reports.html')