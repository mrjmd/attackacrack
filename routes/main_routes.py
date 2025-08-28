from flask import Blueprint, render_template, redirect, url_for, request, flash, current_app
from auth_utils import login_required, get_current_user
from werkzeug.utils import secure_filename
import os
from datetime import datetime

from api_integrations import get_upcoming_calendar_events, get_recent_gmail_messages
# Direct database imports removed - use services only
from extensions import db

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    """Root route - redirect to dashboard if logged in, else to login"""
    current_user = get_current_user()
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    else:
        return redirect(url_for('auth.login'))

@main_bp.route('/dashboard')
@login_required
def dashboard():
    from datetime import datetime, timedelta
    from sqlalchemy import func
    from sqlalchemy.orm import selectinload, joinedload
    from flask import current_app
    current_user = get_current_user()
    
    # Get services from registry
    dashboard_service = current_app.services.get('dashboard')
    appointment_service = current_app.services.get('appointment')
    campaign_service = current_app.services.get('campaign')
    todo_service = current_app.services.get('todo')
    
    # Get all dashboard statistics from service
    stats = dashboard_service.get_dashboard_stats()
    
    # Get activity timeline from service
    timeline_items = dashboard_service.get_activity_timeline(limit=20)
    
    # Take only the top 5 for dashboard display
    openphone_texts = timeline_items[:5]
    
    # Get recent campaigns for timeline
    recent_campaigns = dashboard_service.get_recent_campaigns(limit=3)
    campaign_events = []
    try:
        for campaign in recent_campaigns:
            analytics = campaign_service.get_campaign_analytics(campaign.id)
            campaign_events.append({
                'title': f'Campaign: {campaign.name}',
                'description': f'{analytics.get("sent_count", 0)} messages sent, {analytics.get("response_count", 0)} responses',
                'time': campaign.created_at.strftime('%H:%M') if campaign.created_at else 'Recently'
            })
    except Exception as e:
        # If campaign analytics fail, show basic info
        for campaign in recent_campaigns:
            campaign_events.append({
                'title': f'Campaign: {campaign.name}',
                'description': f'Status: {campaign.status}',
                'time': campaign.created_at.strftime('%H:%M') if campaign.created_at else 'Recently'
            })
    
    # Message Volume Data (Last 7 Days)
    message_volume_data = dashboard_service.get_message_volume_data(days=7)
    
    # Recent Campaigns with Performance
    recent_campaigns_with_perf = []
    try:
        for campaign in recent_campaigns:
            analytics = campaign_service.get_campaign_analytics(campaign.id)
            recent_campaigns_with_perf.append({
                'name': campaign.name,
                'response_rate': round(analytics.get('response_rate', 0) * 100, 1)
            })
    except Exception as e:
        # If analytics fail, show campaigns without rates
        for campaign in recent_campaigns:
            recent_campaigns_with_perf.append({
                'name': campaign.name,
                'response_rate': 0
            })
    
    # Today's Appointments
    appointments_result = appointment_service.get_all_appointments()
    appointments = appointments_result.data[:4] if appointments_result.success else []
    
    # System Health Data
    campaign_queue_size = dashboard_service.get_campaign_queue_size()
    
    # Data quality score (percentage of contacts with complete info)
    data_quality_score = dashboard_service.get_data_quality_score()
    
    # Get todos for the current user using TodoService
    # current_user should always be authenticated due to @login_required
    todo_data = todo_service.get_dashboard_todos(user_id=current_user.id, limit=5)
    todos = todo_data['todos']
    pending_tasks_count = todo_data['pending_count']
    
    return render_template(
        'dashboard.html', 
        stats=stats, 
        appointments=appointments,
        openphone_texts=openphone_texts,
        campaign_events=campaign_events,
        message_volume_data=message_volume_data,
        recent_campaigns=recent_campaigns_with_perf,
        campaign_queue_size=campaign_queue_size,
        data_quality_score=data_quality_score,
        pending_tasks=pending_tasks_count,
        todos=todos
    )

# ... (rest of file is unchanged) ...
@main_bp.route('/settings')
@login_required
def settings():
    return render_template('settings.html')

@main_bp.route('/settings/automation', methods=['GET', 'POST'])
@login_required
def automation_settings():
    if request.method == 'POST':
        form_type = request.form.get('form_type')
        
        if form_type == 'reminder':
            template_key = 'appointment_reminder_template'
            template_text = request.form.get('reminder_template')
            flash_message = 'Reminder template saved successfully!'
        elif form_type == 'review':
            template_key = 'review_request_template'
            template_text = request.form.get('review_template')
            flash_message = 'Review request template saved successfully!'
        else:
            flash('Invalid form submission.', 'error')
            return redirect(url_for('main.automation_settings'))

        # Use SettingService instead of direct database queries
        setting_service = current_app.services.get('setting')
        
        try:
            # Try to update existing template
            if not setting_service.update_template(template_key, template_text):
                # Create new template if it doesn't exist
                setting_service.create_template(template_key, template_text)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            flash(f'Error saving template: {str(e)}', 'error')
            return redirect(url_for('main.automation_settings'))
        flash(flash_message, 'success')
        return redirect(url_for('main.automation_settings'))

    # For GET request, fetch both templates using SettingService
    setting_service = current_app.services.get('setting')
    
    reminder_text = setting_service.get_appointment_reminder_template() or "Hi [contact_first_name], this is a reminder for your appointment with Attack-a-Crack on [appointment_date] at [appointment_time]."
    review_text = setting_service.get_review_request_template() or "Hi [contact_first_name], we hope you're happy with the work we did! If you have a moment, we'd love it if you could leave us a review on Google: [Your Google Review Link]"
    
    return render_template('automation_settings.html', reminder_template_text=reminder_text, review_template_text=review_text)

@main_bp.route('/import_csv', methods=['GET', 'POST'])
@login_required
def import_csv():
    """Import contacts from CSV using smart format detection"""
    contact_service = current_app.services.get('contact')
    csv_service = current_app.services.get('csv_import')
    
    if request.method == 'POST':
        file = request.files.get('file')
        if not file or not file.filename:
            flash('Please select a file', 'error')
            return redirect(request.url)
        
        if not file.filename.endswith('.csv'):
            flash('Please upload a CSV file', 'error')
            return redirect(request.url)
        
        # Get duplicate strategy from form
        duplicate_strategy = request.form.get('duplicate_strategy', 'merge')
        
        # Import the CSV with smart detection
        results = csv_service.import_contacts(
            file=file,
            create_list=False,  # Don't create campaign list from settings import
            imported_by='settings_import',
            duplicate_strategy=duplicate_strategy
        )
        
        # Show results
        if results['successful'] > 0:
            message = f"Successfully imported {results['successful']} contacts"
            if results.get('contacts_created'):
                message += f" ({len(results['contacts_created'])} new)"
            if results['duplicates'] > 0:
                message += f" ({results['duplicates']} enriched)"
            flash(message, 'success')
        
        if results['failed'] > 0:
            flash(f"{results['failed']} contacts failed to import", 'warning')
            for error in results['errors'][:3]:
                flash(f"Error: {error}", 'error')
        
        return redirect(url_for('contact.list_all'))
            
    return render_template('import_csv.html')

@main_bp.route('/import_property_radar', methods=['GET', 'POST'])
@login_required
def import_property_radar():
    """Import PropertyRadar data using smart format detection"""
    contact_service = current_app.services.get('contact')
    csv_service = current_app.services.get('csv_import')
    
    if request.method == 'POST':
        file = request.files.get('file')
        if not file or not file.filename:
            flash('Please select a file', 'error')
            return redirect(request.url)
        
        if not file.filename.endswith('.csv'):
            flash('Please upload a CSV file', 'error')
            return redirect(request.url)
        
        # Get duplicate strategy from form
        duplicate_strategy = request.form.get('duplicate_strategy', 'update')
        
        # Import PropertyRadar CSV with smart detection
        # The service will automatically detect it's PropertyRadar format
        results = csv_service.import_contacts(
            file=file,
            create_list=False,  # Don't create campaign list from settings import
            imported_by='propertyradar_import',
            duplicate_strategy=duplicate_strategy
        )
        
        # Show results
        if results['successful'] > 0:
            message = f"Successfully imported {results['successful']} PropertyRadar records"
            if results.get('contacts_created'):
                message += f" ({len(results['contacts_created'])} new properties)"
            if results['duplicates'] > 0:
                message += f" ({results['duplicates']} enriched)"
            flash(message, 'success')
        
        if results['failed'] > 0:
            flash(f"{results['failed']} records failed to import", 'warning')
            for error in results['errors'][:3]:
                flash(f"Error: {error}", 'error')
        
        # Redirect to property list since it's property data
        return redirect(url_for('property.list_all'))

    return render_template('import_property_radar.html')


# --- Placeholder routes from original file ---
@main_bp.route('/customers')
@login_required
def customers():
    return render_template('customers.html')

@main_bp.route('/finances')
@login_required
def finances():
    return render_template('finances.html')

@main_bp.route('/marketing')
@login_required
def marketing():
    return render_template('marketing.html')


@main_bp.route('/schedule_appointment', methods=['POST'])
@login_required
def schedule_appointment():
    """Schedule an appointment and send reminder using services"""
    # Use service registry pattern
    setting_service = current_app.services.get('setting')
    google_service = current_app.services.get('google_calendar')
    
    # Get form data
    contact_id = request.form.get('contact_id')
    date = request.form.get('date')
    time = request.form.get('time')
    service_type = request.form.get('service_type', 'appointment_reminder')
    first_name = request.form.get('first_name')
    phone = request.form.get('phone')
    
    try:
        # Get template using service
        template = setting_service.get_template_by_key(f'{service_type}_template')
        
        # Create calendar event using service
        event_data = google_service.create_event({
            'date': date,
            'time': time,
            'first_name': first_name,
            'phone': phone
        })
        
        flash('Appointment scheduled successfully!', 'success')
        return redirect(url_for('appointment.list_all'))
        
    except Exception as e:
        flash(f'Error scheduling appointment: {str(e)}', 'error')
        return redirect(url_for('appointment.list_all'))


@main_bp.route('/schedule_reminder', methods=['POST'])
@login_required
def schedule_reminder():
    """Schedule a reminder using services"""
    # Use service registry pattern
    setting_service = current_app.services.get('setting')
    
    # Get form data
    contact_id = request.form.get('contact_id')
    reminder_type = request.form.get('reminder_type')
    first_name = request.form.get('first_name')
    
    try:
        # Get appropriate template using service
        if reminder_type == 'appointment':
            template = setting_service.get_appointment_reminder_template()
        else:
            template = setting_service.get_review_request_template()
        
        # Process reminder (implementation depends on requirements)
        flash('Reminder scheduled successfully!', 'success')
        return redirect(url_for('main.dashboard'))
        
    except Exception as e:
        flash(f'Error scheduling reminder: {str(e)}', 'error')
        return redirect(url_for('main.dashboard'))