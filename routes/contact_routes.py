from flask import Blueprint, render_template, request, redirect, url_for, current_app, jsonify, flash
from flask_login import login_required
from datetime import datetime, timedelta
from sqlalchemy import or_, and_, func
from services.contact_service import ContactService
from services.message_service import MessageService 
from extensions import db
from crm_database import Activity, Conversation, Contact, ContactFlag

contact_bp = Blueprint('contact', __name__)

@contact_bp.route('/')
@login_required
def list_all():
    contact_service = ContactService()
    all_contacts = contact_service.get_all_contacts()
    return render_template('contact_list.html', contacts=all_contacts)

@contact_bp.route('/conversations')
@login_required
def conversation_list():
    # Refresh session to get latest data from webhooks
    db.session.expire_all()
    
    # Get search and filter parameters
    search_query = request.args.get('search', '').strip()
    filter_type = request.args.get('filter', 'all')  # all, unread, has_attachments, office_numbers
    date_filter = request.args.get('date', 'all')  # all, today, week, month
    page = int(request.args.get('page', 1))
    per_page = 20
    
    # Start with base query - only conversations with activities
    query = db.session.query(Conversation).join(Contact).filter(
        Conversation.id.in_(
            db.session.query(Activity.conversation_id).distinct()
        )
    )
    
    # Apply search filters
    if search_query:
        query = query.filter(
            or_(
                Contact.first_name.ilike(f'%{search_query}%'),
                Contact.last_name.ilike(f'%{search_query}%'),
                Contact.phone.ilike(f'%{search_query}%'),
                Contact.email.ilike(f'%{search_query}%'),
                # Search in recent message content
                Conversation.id.in_(
                    db.session.query(Activity.conversation_id).filter(
                        Activity.body.ilike(f'%{search_query}%')
                    ).subquery()
                )
            )
        )
    
    # Apply type filters
    if filter_type == 'unread':
        # Conversations with incoming messages newer than last outgoing
        query = query.filter(
            Conversation.id.in_(
                db.session.query(Activity.conversation_id).filter(
                    Activity.direction == 'incoming',
                    Activity.created_at > func.coalesce(
                        db.session.query(func.max(Activity.created_at)).filter(
                            Activity.conversation_id == Conversation.id,
                            Activity.direction == 'outgoing'
                        ).scalar_subquery(),
                        datetime(2020, 1, 1)
                    )
                ).subquery()
            )
        )
    elif filter_type == 'has_attachments':
        query = query.filter(
            Conversation.id.in_(
                db.session.query(Activity.conversation_id).filter(
                    Activity.media_urls.isnot(None)
                ).subquery()
            )
        )
    elif filter_type == 'office_numbers':
        # Conversations with contacts flagged as office numbers
        office_contact_ids = db.session.query(ContactFlag.contact_id).filter(
            ContactFlag.flag_type == 'office_number'
        ).subquery()
        query = query.filter(Contact.id.in_(office_contact_ids))
    
    # Apply date filters
    if date_filter == 'today':
        today = datetime.now().date()
        query = query.filter(func.date(Conversation.last_activity_at) == today)
    elif date_filter == 'week':
        week_ago = datetime.now() - timedelta(days=7)
        query = query.filter(Conversation.last_activity_at >= week_ago)
    elif date_filter == 'month':
        month_ago = datetime.now() - timedelta(days=30)
        query = query.filter(Conversation.last_activity_at >= month_ago)
    
    # Order by most recent activity
    query = query.order_by(Conversation.last_activity_at.desc())
    
    # Paginate results
    total_conversations = query.count()
    conversations = query.offset((page - 1) * per_page).limit(per_page).all()
    
    # Enhance conversations with metadata
    enhanced_conversations = []
    for conv in conversations:
        # Get latest activity
        latest_activity = Activity.query.filter_by(conversation_id=conv.id).order_by(Activity.created_at.desc()).first()
        
        # Check for unread status
        latest_incoming = Activity.query.filter_by(
            conversation_id=conv.id, 
            direction='incoming'
        ).order_by(Activity.created_at.desc()).first()
        
        latest_outgoing = Activity.query.filter_by(
            conversation_id=conv.id, 
            direction='outgoing'
        ).order_by(Activity.created_at.desc()).first()
        
        is_unread = (latest_incoming and 
                    (not latest_outgoing or latest_incoming.created_at > latest_outgoing.created_at))
        
        # Check for attachments
        has_attachments = Activity.query.filter(
            Activity.conversation_id == conv.id,
            Activity.media_urls.isnot(None)
        ).first() is not None
        
        # Check for AI content
        has_ai_summary = Activity.query.filter(
            Activity.conversation_id == conv.id,
            Activity.ai_summary.isnot(None)
        ).first() is not None
        
        # Check if office number
        is_office_number = ContactFlag.query.filter_by(
            contact_id=conv.contact_id,
            flag_type='office_number'
        ).first() is not None
        
        enhanced_conversations.append({
            'conversation': conv,
            'latest_activity': latest_activity,
            'is_unread': is_unread,
            'has_attachments': has_attachments,
            'has_ai_summary': has_ai_summary,
            'is_office_number': is_office_number,
            'message_count': Activity.query.filter_by(conversation_id=conv.id).count()
        })
    
    # Calculate pagination
    total_pages = (total_conversations + per_page - 1) // per_page
    has_prev = page > 1
    has_next = page < total_pages
    
    # Get available campaigns for bulk actions
    from crm_database import Campaign
    available_campaigns = Campaign.query.filter(Campaign.status.in_(['draft', 'running'])).all()
    
    return render_template('conversation_list.html', 
                         conversations=enhanced_conversations,
                         search_query=search_query,
                         filter_type=filter_type,
                         date_filter=date_filter,
                         page=page,
                         total_pages=total_pages,
                         has_prev=has_prev,
                         has_next=has_next,
                         total_conversations=total_conversations,
                         available_campaigns=available_campaigns)

@contact_bp.route('/conversations/bulk-action', methods=['POST'])
def bulk_conversation_action():
    """Handle bulk actions on conversations"""
    action = request.form.get('action')
    conversation_ids = request.form.getlist('conversation_ids')
    
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
def conversation(contact_id):
    contact_service = ContactService()
    message_service = MessageService()
    contact = contact_service.get_contact_by_id(contact_id)
    activities = message_service.get_activities_for_contact(contact_id)
    
    # Additional data for enhanced view
    from crm_database import Job, ContactFlag, CampaignMembership, Campaign
    
    # Get recent jobs
    recent_jobs = []
    if contact.properties:
        for prop in contact.properties:
            recent_jobs.extend(prop.jobs)
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
    
    # Get campaign memberships
    campaign_memberships = CampaignMembership.query.filter_by(
        contact_id=contact_id
    ).join(Campaign).order_by(CampaignMembership.sent_at.desc()).limit(3).all()
    
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
def delete_contact(contact_id):
    contact_service = ContactService()
    contact = contact_service.get_contact_by_id(contact_id)
    contact_service.delete_contact(contact)
    return redirect(url_for('contact.list_all'))