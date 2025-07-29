"""
Campaign routes for creating and managing text campaigns
"""

from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash
from datetime import datetime
from extensions import db
from crm_database import Campaign, Contact, ContactFlag, CampaignMembership
from services.campaign_service import CampaignService

campaigns_bp = Blueprint('campaigns', __name__)
campaign_service = CampaignService()


@campaigns_bp.route('/campaigns')
def campaign_list():
    """List all campaigns with basic stats"""
    campaigns = Campaign.query.order_by(Campaign.created_at.desc()).all()
    
    campaign_data = []
    for campaign in campaigns:
        analytics = campaign_service.get_campaign_analytics(campaign.id)
        campaign_data.append({
            'campaign': campaign,
            'analytics': analytics
        })
    
    return render_template('campaigns/list.html', campaigns=campaign_data)


@campaigns_bp.route('/campaigns/new')
def new_campaign():
    """Show campaign creation form"""
    # Get contact counts for audience sizing
    total_contacts = Contact.query.count()
    
    # Contacts with real names (not phone numbers)
    named_contacts = Contact.query.filter(~Contact.first_name.like('%+1%')).count()
    
    # Contacts with emails
    email_contacts = Contact.query.filter(
        Contact.email.isnot(None),
        Contact.email != ''
    ).count()
    
    # Opted out contacts
    opted_out_count = db.session.query(Contact.id).join(ContactFlag).filter(
        ContactFlag.flag_type == 'opted_out',
        ContactFlag.applies_to.in_(['sms', 'both'])
    ).count()
    
    audience_stats = {
        'total_contacts': total_contacts,
        'named_contacts': named_contacts,
        'email_contacts': email_contacts,
        'opted_out_count': opted_out_count,
        'available_contacts': total_contacts - opted_out_count
    }
    
    return render_template('campaigns/new.html', audience_stats=audience_stats)


@campaigns_bp.route('/campaigns', methods=['POST'])
def create_campaign():
    """Create a new campaign"""
    try:
        data = request.form
        
        # Create campaign
        campaign = campaign_service.create_campaign(
            name=data['name'],
            campaign_type=data['campaign_type'],
            audience_type=data.get('audience_type', 'mixed'),
            channel=data.get('channel', 'sms'),
            template_a=data['template_a'],
            template_b=data.get('template_b') if data['campaign_type'] == 'ab_test' else None,
            daily_limit=int(data.get('daily_limit', 125)),
            business_hours_only=data.get('business_hours_only') == 'on'
        )
        
        # Add recipients based on filters
        contact_filters = {
            'has_name_only': data.get('has_name_only') == 'on',
            'has_email': data.get('has_email') == 'on',
            'exclude_office_numbers': data.get('exclude_office_numbers') == 'on',
            'exclude_opted_out': True,  # Always exclude opted out
            'min_days_since_contact': int(data.get('min_days_since_contact', 30))
        }
        
        recipients_added = campaign_service.add_recipients(campaign.id, contact_filters)
        
        flash(f'Campaign "{campaign.name}" created with {recipients_added} recipients!', 'success')
        return redirect(url_for('campaigns.campaign_detail', campaign_id=campaign.id))
        
    except Exception as e:
        flash(f'Error creating campaign: {str(e)}', 'error')
        return redirect(url_for('campaigns.new_campaign'))


@campaigns_bp.route('/campaigns/<int:campaign_id>')
def campaign_detail(campaign_id):
    """Show campaign details and analytics"""
    campaign = Campaign.query.get_or_404(campaign_id)
    analytics = campaign_service.get_campaign_analytics(campaign_id)
    
    # Get recent sends for activity feed
    recent_sends = CampaignMembership.query.filter_by(
        campaign_id=campaign_id,
        status='sent'
    ).order_by(CampaignMembership.sent_at.desc()).limit(10).all()
    
    return render_template('campaigns/detail.html', 
                         campaign=campaign,
                         analytics=analytics,
                         recent_sends=recent_sends)


@campaigns_bp.route('/campaigns/<int:campaign_id>/start', methods=['POST'])
def start_campaign(campaign_id):
    """Start a campaign"""
    try:
        success = campaign_service.start_campaign(campaign_id)
        if success:
            flash('Campaign started successfully!', 'success')
        else:
            flash('Failed to start campaign', 'error')
    except Exception as e:
        flash(f'Error starting campaign: {str(e)}', 'error')
    
    return redirect(url_for('campaigns.campaign_detail', campaign_id=campaign_id))


@campaigns_bp.route('/campaigns/<int:campaign_id>/pause', methods=['POST'])
def pause_campaign(campaign_id):
    """Pause a running campaign"""
    campaign = Campaign.query.get_or_404(campaign_id)
    
    if campaign.status == 'running':
        campaign.status = 'paused'
        db.session.commit()
        flash('Campaign paused', 'info')
    else:
        flash('Campaign is not running', 'warning')
    
    return redirect(url_for('campaigns.campaign_detail', campaign_id=campaign_id))


@campaigns_bp.route('/campaigns/<int:campaign_id>/recipients')
def campaign_recipients(campaign_id):
    """Show campaign recipients with filtering"""
    campaign = Campaign.query.get_or_404(campaign_id)
    
    # Get filter parameters
    status_filter = request.args.get('status', 'all')
    variant_filter = request.args.get('variant', 'all')
    
    # Build query
    query = CampaignMembership.query.filter_by(campaign_id=campaign_id)
    
    if status_filter != 'all':
        query = query.filter_by(status=status_filter)
    
    if variant_filter != 'all':
        query = query.filter_by(variant_sent=variant_filter)
    
    recipients = query.order_by(CampaignMembership.sent_at.desc()).all()
    
    return render_template('campaigns/recipients.html',
                         campaign=campaign,
                         recipients=recipients,
                         status_filter=status_filter,
                         variant_filter=variant_filter)


@campaigns_bp.route('/api/campaigns/<int:campaign_id>/analytics')
def api_campaign_analytics(campaign_id):
    """API endpoint for real-time campaign analytics"""
    try:
        analytics = campaign_service.get_campaign_analytics(campaign_id)
        return jsonify({
            'success': True,
            'analytics': analytics
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@campaigns_bp.route('/api/campaigns/preview-audience', methods=['POST'])
def api_preview_audience():
    """Preview campaign audience size based on filters"""
    try:
        data = request.json
        
        # Build contact query based on filters
        query = Contact.query
        
        if data.get('has_name_only'):
            query = query.filter(~Contact.first_name.like('%+1%'))
        
        if data.get('has_email'):
            query = query.filter(Contact.email.isnot(None))
            query = query.filter(Contact.email != '')
        
        if data.get('exclude_office_numbers'):
            office_contact_ids = db.session.query(ContactFlag.contact_id).filter(
                ContactFlag.flag_type == 'office_number'
            ).subquery()
            query = query.filter(~Contact.id.in_(office_contact_ids))
        
        # Always exclude opted out
        opted_out_ids = db.session.query(ContactFlag.contact_id).filter(
            ContactFlag.flag_type == 'opted_out',
            ContactFlag.applies_to.in_(['sms', 'both'])
        ).subquery()
        query = query.filter(~Contact.id.in_(opted_out_ids))
        
        if data.get('min_days_since_contact'):
            from datetime import timedelta
            days_ago = datetime.utcnow() - timedelta(days=data['min_days_since_contact'])
            recent_contact_ids = db.session.query(ContactFlag.contact_id).filter(
                ContactFlag.flag_type == 'recently_texted',
                ContactFlag.created_at > days_ago
            ).subquery()
            query = query.filter(~Contact.id.in_(recent_contact_ids))
        
        audience_size = query.count()
        
        return jsonify({
            'success': True,
            'audience_size': audience_size
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500