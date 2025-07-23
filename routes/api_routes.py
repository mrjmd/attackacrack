# routes/api_routes.py

from flask import Blueprint, jsonify, g, session, redirect, url_for, request, flash, current_app
from extensions import db
from crm_database import Contact, Quote, Job, Invoice
from sqlalchemy import func
from datetime import datetime
import os

api_bp = Blueprint('api', __name__, url_prefix='/api')

@api_bp.route('/metrics')
def get_metrics():
    """Fetches real metrics from the database."""
    try:
        new_leads = g.session.query(Contact).filter(Contact.contact_status == 'new_lead').count()
        deals_won = g.session.query(Job).filter(Job.job_status == 'completed').count()
        
        current_month = datetime.now().month
        current_year = datetime.now().year
        revenue_this_month = g.session.query(func.sum(Invoice.amount)).filter(
            func.extract('month', Invoice.paid_date) == current_month,
            func.extract('year', Invoice.paid_date) == current_year,
            Invoice.status == 'paid'
        ).scalar() or 0

        total_quotes_sent = g.session.query(Quote).filter(Quote.status.in_(['sent', 'accepted', 'rejected', 'invoiced'])).count()
        conversion_rate = (deals_won / total_quotes_sent * 100) if total_quotes_sent > 0 else 0

        return jsonify({
            "new_leads": new_leads, 
            "deals_won": deals_won, 
            "revenue": round(revenue_this_month, 2), 
            "conversion_rate": round(conversion_rate, 1)
        })
    except Exception as e:
        print(f"--- ERROR fetching metrics: {e} ---")
        return jsonify({"error": "Could not fetch metrics"}), 500

@api_bp.route('/pipeline')
def get_pipeline():
    """Fetches real sales pipeline data from the database."""
    try:
        pipeline_data = [
            { "name": "New Leads", "value": g.session.query(Contact).filter(Contact.contact_status == 'new_lead').count(), "color": "bg-gray-500" },
            { "name": "Quoted", "value": g.session.query(Quote).filter(Quote.status.in_(['draft', 'sent'])).count(), "color": "bg-blue-500" },
            { "name": "Accepted", "value": g.session.query(Quote).filter(Quote.status == 'accepted').count(), "color": "bg-indigo-500" },
            { "name": "Jobs In Progress", "value": g.session.query(Job).filter(Job.job_status == 'in_progress').count(), "color": "bg-purple-500" },
            { "name": "Jobs Completed", "value": g.session.query(Job).filter(Job.job_status == 'completed').count(), "color": "bg-green-500" },
        ]
        return jsonify(pipeline_data)
    except Exception as e:
        print(f"--- ERROR fetching pipeline data: {e} ---")
        return jsonify({"error": "Could not fetch pipeline data"}), 500

@api_bp.route('/tasks')
def get_tasks():
    # This remains a placeholder as the Task model doesn't exist yet.
    return jsonify([
        { "text": "Follow up with Acme Corp", "due": "Today", "completed": False },
        { "text": "Prepare presentation for Globex", "due": "Tomorrow", "completed": False }
    ])

@api_bp.route('/calendar-events')
def get_calendar_events():
    if not current_app.integration_manager.is_google_authenticated():
        return jsonify({"error": "Google account not authenticated"}), 401
    events = current_app.integration_manager.get_calendar_events()
    return jsonify(events)

@api_bp.route('/emails')
def get_emails():
    if not current_app.integration_manager.is_google_authenticated():
        return jsonify({"error": "Google account not authenticated"}), 401
    emails = current_app.integration_manager.get_recent_emails()
    return jsonify(emails)

@api_bp.route('/texts')
def get_texts():
    if not current_app.integration_manager.is_openphone_configured():
        return jsonify({"error": "OpenPhone API key not configured"}), 401
    texts = current_app.integration_manager.get_recent_texts()
    return jsonify(texts)

@api_bp.route('/settings', methods=['GET', 'POST'])
def manage_settings():
    if request.method == 'POST':
        print("--- DEBUG: Received POST request to /api/settings ---")
        try:
            data = request.get_json()
            if data is None:
                print("--- DEBUG: FAILED to parse JSON. Request body might be empty or not JSON.")
                return jsonify({"error": "Invalid JSON in request"}), 400

            print(f"--- DEBUG: Received JSON data: {data} ---")
            openphone_key = data.get('openphone_api_key')

            if openphone_key:
                print(f"--- DEBUG: API key found. Saving key: '{openphone_key[:4]}...****' ---")
                current_app.integration_manager.save_openphone_key(openphone_key)
                print("--- DEBUG: Key saved successfully. ---")
                return jsonify({"message": "Settings saved successfully"}), 200
            else:
                print("--- DEBUG: 'openphone_api_key' is missing or empty in the JSON payload. ---")
                return jsonify({"error": "Invalid data: API key is missing"}), 400
        except Exception as e:
            print(f"--- ERROR in /api/settings: {e} ---")
            return jsonify({"error": "An internal server error occurred"}), 500
            
    else: # GET
        return jsonify({
            "openphone_api_key": current_app.integration_manager.openphone_api_key
        })
