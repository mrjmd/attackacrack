from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required
from werkzeug.utils import secure_filename
import os
from datetime import datetime

from services.contact_service import ContactService
from services.property_service import PropertyService
from services.job_service import JobService
from services.quote_service import QuoteService
from services.appointment_service import AppointmentService
from services.message_service import MessageService
from utils.csv_importer import CsvImporter
from utils.property_radar_importer import PropertyRadarImporter
from api_integrations import get_upcoming_calendar_events, get_recent_gmail_messages
from extensions import db
from crm_database import Setting, Activity, Conversation

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    """Root route - redirect to dashboard if logged in, else to login"""
    from flask_login import current_user
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    else:
        return redirect(url_for('auth.login'))

@main_bp.route('/dashboard')
@login_required
def dashboard():
    from datetime import datetime, timedelta
    from sqlalchemy import func
    from crm_database import Contact, Campaign, CampaignMembership, Activity, Conversation
    from services.campaign_service import CampaignService
    
    contact_service = ContactService()
    appointment_service = AppointmentService()
    message_service = MessageService()
    campaign_service = CampaignService()
    
    # Enhanced Statistics for Dashboard Cards
    total_contacts = Contact.query.count()
    
    # Contacts added this week (using Activity records as proxy since Contact doesn't have created_at)
    week_ago = datetime.utcnow() - timedelta(days=7)
    contacts_added_this_week = Activity.query.filter(
        Activity.created_at >= week_ago,
        Activity.contact_id.isnot(None)
    ).distinct(Activity.contact_id).count()
    
    # Active campaigns
    active_campaigns = Campaign.query.filter_by(status='running').count()
    
    # Campaign response rate (average across all campaigns)
    all_campaigns = Campaign.query.all()
    response_rates = []
    try:
        for campaign in all_campaigns:
            analytics = campaign_service.get_campaign_analytics(campaign.id)
            if analytics.get('sent_count', 0) > 0:
                response_rates.append(analytics['response_rate'] * 100)
    except Exception as e:
        # Handle case where campaign service fails
        pass
    
    avg_response_rate = round(sum(response_rates) / len(response_rates), 1) if response_rates else 0
    
    # Monthly revenue (placeholder - can be enhanced with actual revenue tracking)
    monthly_revenue = 12500  # Placeholder
    revenue_growth = 8.5  # Placeholder percentage
    
    # Messages sent today
    today = datetime.utcnow().date()
    messages_today = Activity.query.filter(
        Activity.activity_type == 'message',
        Activity.direction == 'outgoing',
        func.date(Activity.created_at) == today
    ).count()
    
    # Overall response rate (incoming messages vs outgoing)
    total_outgoing = Activity.query.filter(
        Activity.activity_type == 'message',
        Activity.direction == 'outgoing'
    ).count()
    
    total_incoming = Activity.query.filter(
        Activity.activity_type == 'message',
        Activity.direction == 'incoming'
    ).count()
    
    overall_response_rate = round((total_incoming / total_outgoing * 100), 1) if total_outgoing > 0 else 0
    
    stats = {
        'contact_count': total_contacts,
        'contacts_added_this_week': contacts_added_this_week,
        'active_campaigns': active_campaigns,
        'campaign_response_rate': avg_response_rate,
        'monthly_revenue': monthly_revenue,
        'revenue_growth': revenue_growth,
        'overall_response_rate': overall_response_rate,
        'messages_today': messages_today
    }
    
    # Activity Timeline Data (get more conversations and sort by most recent activity)
    latest_conversations = message_service.get_latest_conversations_from_db(limit=20)
    
    openphone_texts = []
    for conv in latest_conversations:
        # Get the most recent activity for this conversation
        last_activity = max(conv.activities, key=lambda act: act.created_at) if conv.activities else None
        if last_activity:
            # Determine content based on activity type
            if last_activity.activity_type == 'call':
                if last_activity.direction == 'incoming':
                    content = "📞 Incoming call"
                else:
                    content = "📞 Outgoing call"
                if last_activity.duration_seconds:
                    duration_min = last_activity.duration_seconds // 60
                    content += f" ({duration_min}m)"
            elif last_activity.activity_type == 'voicemail':
                content = "🎤 Voicemail received"
            else:
                # Message type
                content = last_activity.body or "📱 Message (no content)"
            
            openphone_texts.append({
                'contact_id': conv.contact.id,
                'contact_name': conv.contact.first_name or conv.contact.phone,
                'contact_number': conv.contact.phone,
                'latest_message_body': content,
                'timestamp': last_activity.created_at.strftime('%H:%M') if last_activity.created_at else 'Just now',
                'activity_timestamp': last_activity.created_at,  # For sorting
                'activity_type': last_activity.activity_type
            })
    
    # Sort by most recent activity timestamp descending
    openphone_texts.sort(key=lambda x: x['activity_timestamp'], reverse=True)
    
    # Take only the top 5 for dashboard display
    openphone_texts = openphone_texts[:5]
    
    # Campaign Events for Timeline
    recent_campaigns = Campaign.query.order_by(Campaign.created_at.desc()).limit(3).all()
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
    message_volume_data = []
    for i in range(7):
        day = datetime.utcnow().date() - timedelta(days=6-i)
        count = Activity.query.filter(
            Activity.activity_type == 'message',
            func.date(Activity.created_at) == day
        ).count()
        message_volume_data.append({'date': day, 'count': count})
    
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
    appointments = appointment_service.get_all_appointments()[:4]  # Limit to 4
    
    # System Health Data
    campaign_queue_size = CampaignMembership.query.filter_by(status='pending').count()
    
    # Data quality score (percentage of contacts with complete info)
    contacts_with_names = Contact.query.filter(~Contact.first_name.like('%+1%')).count()
    contacts_with_emails = Contact.query.filter(Contact.email.isnot(None), Contact.email != '').count()
    data_quality_score = round(((contacts_with_names + contacts_with_emails) / (total_contacts * 2)) * 100) if total_contacts > 0 else 0
    
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
        pending_tasks=3  # Placeholder
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

        setting = db.session.query(Setting).filter_by(key=template_key).first()
        if setting:
            setting.value = template_text
        else:
            setting = Setting(key=template_key, value=template_text)
            db.session.add(setting)
        
        db.session.commit()
        flash(flash_message, 'success')
        return redirect(url_for('main.automation_settings'))

    # For GET request, fetch both templates
    reminder_setting = db.session.query(Setting).filter_by(key='appointment_reminder_template').first()
    review_setting = db.session.query(Setting).filter_by(key='review_request_template').first()

    reminder_text = reminder_setting.value if reminder_setting else "Hi [contact_first_name], this is a reminder for your appointment with Attack-a-Crack on [appointment_date] at [appointment_time]."
    review_text = review_setting.value if review_setting else "Hi [contact_first_name], we hope you're happy with the work we did! If you have a moment, we'd love it if you could leave us a review on Google: [Your Google Review Link]"
    
    return render_template('automation_settings.html', reminder_template_text=reminder_text, review_template_text=review_text)

@main_bp.route('/import_csv', methods=['GET', 'POST'])
@login_required
def import_csv():
    contact_service = ContactService()
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file part')
            return redirect(request.url)
        file = request.files['file']
        if file.filename == '':
            flash('No selected file')
            return redirect(request.url)
        if file:
            filename = secure_filename(file.filename)
            filepath = os.path.join('/tmp', filename)
            file.save(filepath)
            
            importer = CsvImporter(contact_service)
            importer.import_data(filepath)
            
            flash('CSV data imported successfully!')
            return redirect(url_for('contact.list_all'))
            
    return render_template('import_csv.html')

@main_bp.route('/import_property_radar', methods=['GET', 'POST'])
@login_required
def import_property_radar():
    contact_service = ContactService()
    property_service = PropertyService()
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file part')
            return redirect(request.url)
        file = request.files['file']
        if file.filename == '':
            flash('No selected file')
            return redirect(request.url)
        if file:
            filename = secure_filename(file.filename)
            filepath = os.path.join('/tmp', filename)
            file.save(filepath)

            importer = PropertyRadarImporter(contact_service, property_service)
            importer.import_data(filepath)

            flash('Property Radar data imported successfully!')
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