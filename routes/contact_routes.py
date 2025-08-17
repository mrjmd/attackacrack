from flask import Blueprint, render_template, request, redirect, url_for, current_app, jsonify, flash
from flask_login import login_required
from datetime import datetime, timedelta
from sqlalchemy import or_, and_, func
from sqlalchemy.orm import joinedload, selectinload
from services.contact_service import ContactService
from services.message_service import MessageService
from services.conversation_service import ConversationService 
from extensions import db
from crm_database import Activity, Conversation, Contact, ContactFlag

contact_bp = Blueprint('contact', __name__)

@contact_bp.route('/')
@login_required
def list_all():
    contact_service = ContactService()
    
    # Get pagination parameters
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 100, type=int)
    search = request.args.get('search', '').strip()
    
    # Get paginated contacts
    if search:
        contacts_paginated = Contact.query.filter(
            db.or_(
                Contact.first_name.ilike(f'%{search}%'),
                Contact.last_name.ilike(f'%{search}%'),
                Contact.phone.ilike(f'%{search}%'),
                Contact.email.ilike(f'%{search}%')
            )
        ).order_by(Contact.last_name, Contact.first_name).paginate(
            page=page, per_page=per_page, error_out=False
        )
    else:
        contacts_paginated = Contact.query.order_by(
            Contact.last_name, Contact.first_name
        ).paginate(page=page, per_page=per_page, error_out=False)
    
    return render_template('contact_list.html', 
                         contacts=contacts_paginated.items,
                         pagination=contacts_paginated,
                         search=search)

@contact_bp.route('/conversations')
@login_required
def conversation_list():
    """Display paginated list of conversations with filters"""
    conversation_service = ConversationService()
    
    # Get search and filter parameters
    search_query = request.args.get('search', '').strip()
    filter_type = request.args.get('filter', 'all')
    date_filter = request.args.get('date', 'all')
    page = int(request.args.get('page', 1))
    
    # Get paginated conversations with filters
    result = conversation_service.get_conversations_page(
        search_query=search_query,
        filter_type=filter_type,
        date_filter=date_filter,
        page=page,
        per_page=20
    )
    
    # Get available campaigns for bulk actions
    available_campaigns = conversation_service.get_available_campaigns()
    
    return render_template('conversation_list.html', 
                         conversations=result['conversations'],
                         search_query=search_query,
                         filter_type=filter_type,
                         date_filter=date_filter,
                         page=result['page'],
                         total_pages=result['total_pages'],
                         has_prev=result['has_prev'],
                         has_next=result['has_next'],
                         total_conversations=result['total_count'],
                         available_campaigns=available_campaigns)

@contact_bp.route('/conversations/bulk-action', methods=['POST'])
@login_required
def bulk_conversation_action():
    """Handle bulk actions on conversations"""
    conversation_service = ConversationService()
    
    action = request.form.get('action')
    conversation_ids = [int(id) for id in request.form.getlist('conversation_ids')]
    
    if not conversation_ids:
        flash('No conversations selected', 'warning')
        return redirect(url_for('contact.conversation_list'))
    
    try:
        if action == 'mark_read':
            # Mark conversations as read by creating outgoing activities
            for conv_id in conversation_ids:
                conv = Conversation.query.get(conv_id)
                if conv:
                    # Update last activity to indicate read status
                    conv.last_activity_at = datetime.utcnow()
            
            db.session.commit()
            flash(f'Marked {len(conversation_ids)} conversations as read', 'success')
            
        elif action == 'add_to_campaign':
            campaign_id = request.form.get('campaign_id')
            if not campaign_id:
                flash('No campaign selected', 'warning')
                return redirect(url_for('contact.conversation_list'))
            
            # Add contacts to campaign
            from crm_database import Campaign, CampaignMembership
            campaign = Campaign.query.get(campaign_id)
            if not campaign:
                flash('Campaign not found', 'error')
                return redirect(url_for('contact.conversation_list'))
            
            added_count = 0
            for conv_id in conversation_ids:
                conv = Conversation.query.get(conv_id)
                if conv:
                    # Check if already in campaign
                    existing = CampaignMembership.query.filter_by(
                        campaign_id=campaign_id,
                        contact_id=conv.contact_id
                    ).first()
                    
                    if not existing:
                        membership = CampaignMembership(
                            campaign_id=campaign_id,
                            contact_id=conv.contact_id,
                            status='pending'
                        )
                        db.session.add(membership)
                        added_count += 1
            
            db.session.commit()
            flash(f'Added {added_count} contacts to campaign "{campaign.name}"', 'success')
            
        elif action == 'flag_office':
            # Flag selected contacts as office numbers
            for conv_id in conversation_ids:
                conv = Conversation.query.get(conv_id)
                if conv:
                    # Check if already flagged
                    existing_flag = ContactFlag.query.filter_by(
                        contact_id=conv.contact_id,
                        flag_type='office_number'
                    ).first()
                    
                    if not existing_flag:
                        flag = ContactFlag(
                            contact_id=conv.contact_id,
                            flag_type='office_number',
                            flag_reason='Bulk flagged as office number',
                            applies_to='both',
                            created_by='bulk_action'
                        )
                        db.session.add(flag)
            
            db.session.commit()
            flash(f'Flagged {len(conversation_ids)} contacts as office numbers', 'success')
            
        elif action == 'export':
            # Export conversation data
            conversations = Conversation.query.filter(Conversation.id.in_(conversation_ids)).all()
            
            import csv
            import io
            from flask import make_response
            
            output = io.StringIO()
            writer = csv.writer(output)
            
            # Write headers
            writer.writerow(['Contact Name', 'Phone', 'Email', 'Last Activity', 'Message Count'])
            
            # Write data
            for conv in conversations:
                writer.writerow([
                    f"{conv.contact.first_name} {conv.contact.last_name}",
                    conv.contact.phone,
                    conv.contact.email or '',
                    conv.last_activity_at.strftime('%Y-%m-%d %H:%M:%S') if conv.last_activity_at else '',
                    Activity.query.filter_by(conversation_id=conv.id).count()
                ])
            
            output.seek(0)
            response = make_response(output.getvalue())
            response.headers['Content-Disposition'] = 'attachment; filename=conversations_export.csv'
            response.headers['Content-Type'] = 'text/csv'
            return response
            
        else:
            flash('Invalid action selected', 'warning')
            
    except Exception as e:
        flash(f'Error performing bulk action: {str(e)}', 'error')
        db.session.rollback()
    
    return redirect(url_for('contact.conversation_list'))

@contact_bp.route('/<int:contact_id>')
@login_required
def contact_detail(contact_id):
    contact_service = ContactService()
    message_service = MessageService()
    contact = contact_service.get_contact_by_id(contact_id)
    
    activities = message_service.get_activities_for_contact(contact_id)
    
    from api_integrations import get_emails_for_contact
    recent_emails = get_emails_for_contact(contact.email)

    return render_template(
        'contact_detail.html', 
        contact=contact,
        activities=activities,
        recent_emails=recent_emails
    )

@contact_bp.route('/<int:contact_id>/conversation')
@login_required
def conversation(contact_id):
    contact_service = ContactService()
    message_service = MessageService()
    
    # Additional data for enhanced view
    from crm_database import Job, ContactFlag, CampaignMembership, Campaign, Property
    
    # Get contact with eager loading for properties and their jobs
    contact = Contact.query.options(
        selectinload(Contact.properties).selectinload(Property.jobs)
    ).filter_by(id=contact_id).first()
    
    if not contact:
        flash('Contact not found', 'error')
        return redirect(url_for('contact.list_all'))
    
    activities = message_service.get_activities_for_contact(contact_id)
    
    # Get recent jobs from pre-loaded properties
    recent_jobs = []
    if contact.properties:
        for prop in contact.properties:
            recent_jobs.extend(prop.jobs)  # Jobs are already loaded
    recent_jobs = sorted(recent_jobs, key=lambda x: x.completed_at if x.completed_at else datetime.min, reverse=True)[:3]
    
    # Check for flags
    has_office_flag = ContactFlag.query.filter_by(
        contact_id=contact_id,
        flag_type='office_number'
    ).first() is not None
    
    has_opted_out = ContactFlag.query.filter_by(
        contact_id=contact_id,
        flag_type='opted_out'
    ).first() is not None
    
    # Get campaign memberships with eager loading
    campaign_memberships = CampaignMembership.query.options(
        joinedload(CampaignMembership.campaign)
    ).filter_by(
        contact_id=contact_id
    ).order_by(CampaignMembership.sent_at.desc()).limit(3).all()
    
    # Calculate statistics
    call_count = sum(1 for a in activities if a.activity_type == 'call')
    last_activity = max(activities, key=lambda a: a.created_at) if activities else None
    last_activity_date = last_activity.created_at.strftime('%b %d, %Y') if last_activity else None
    
    # Use the new enhanced template
    return render_template('conversation_detail_enhanced.html', 
                         contact=contact, 
                         activities=activities,
                         recent_jobs=recent_jobs,
                         has_office_flag=has_office_flag,
                         has_opted_out=has_opted_out,
                         campaign_memberships=campaign_memberships,
                         call_count=call_count,
                         last_activity_date=last_activity_date)

@contact_bp.route('/<int:contact_id>/send-message', methods=['POST'])
@login_required
def send_message(contact_id):
    """Send a message to a contact via OpenPhone"""
    from services.openphone_service import OpenPhoneService
    
    contact_service = ContactService()
    contact = contact_service.get_contact_by_id(contact_id)
    
    if not contact:
        flash('Contact not found', 'error')
        return redirect(url_for('contact.conversation_list'))
    
    message_body = request.form.get('body', '').strip()
    if not message_body:
        flash('Message cannot be empty', 'error')
        return redirect(url_for('contact.conversation', contact_id=contact_id))
    
    try:
        openphone_service = OpenPhoneService()
        result = openphone_service.send_message(contact.phone, message_body)
        
        if result.get('success'):
            flash('Message sent successfully!', 'success')
        else:
            flash('Failed to send message', 'error')
    except Exception as e:
        flash(f'Error sending message: {str(e)}', 'error')
    
    return redirect(url_for('contact.conversation', contact_id=contact_id))

@contact_bp.route('/add', methods=['GET', 'POST'])
@login_required
def add_contact():
    contact_service = ContactService()
    if request.method == 'POST':
        contact_service.add_contact(
            first_name=request.form['first_name'],
            last_name=request.form['last_name'],
            email=request.form['email'],
            phone=request.form['phone']
        )
        return redirect(url_for('contact.list_all'))
    return render_template('add_edit_contact_form.html')

@contact_bp.route('/<int:contact_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_contact(contact_id):
    contact_service = ContactService()
    contact = contact_service.get_contact_by_id(contact_id)
    if request.method == 'POST':
        contact_service.update_contact(
            contact,
            first_name=request.form['first_name'],
            last_name=request.form['last_name'],
            email=request.form['email'],
            phone=request.form['phone']
        )
        return redirect(url_for('contact.contact_detail', contact_id=contact.id))
    return render_template('add_edit_contact_form.html', contact=contact)

@contact_bp.route('/<int:contact_id>/delete', methods=['POST'])
@login_required
def delete_contact(contact_id):
    contact_service = ContactService()
    contact = contact_service.get_contact_by_id(contact_id)
    contact_service.delete_contact(contact)
    return redirect(url_for('contact.list_all'))