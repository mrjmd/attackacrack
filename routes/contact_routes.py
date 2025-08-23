from flask import Blueprint, render_template, request, redirect, url_for, current_app, jsonify, flash, make_response
from auth_utils import login_required, current_user
from datetime import datetime
from services.contact_service_refactored import ContactService
from services.message_service_refactored import MessageService
from services.conversation_service import ConversationService 

contact_bp = Blueprint('contact', __name__)

@contact_bp.route('/')
@login_required
def list_all():
    """Display paginated list of contacts with filters"""
    contact_service = current_app.services.get('contact')
    
    # Get parameters
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    search_query = request.args.get('search', '').strip()
    filter_type = request.args.get('filter', 'all')
    sort_by = request.args.get('sort', 'name')
    
    # Get paginated contacts
    result = contact_service.get_contacts_page(
        search_query=search_query,
        filter_type=filter_type,
        sort_by=sort_by,
        page=page,
        per_page=per_page
    )
    
    return render_template('contact_list.html', 
                         contacts=result['contacts'],
                         total_count=result['total_count'],
                         page=result['page'],
                         total_pages=result['total_pages'],
                         has_prev=result['has_prev'],
                         has_next=result['has_next'],
                         search_query=search_query,
                         filter_type=filter_type,
                         sort_by=sort_by)

@contact_bp.route('/conversations')
@login_required
def conversation_list():
    """Display paginated list of conversations with filters"""
    conversation_service = current_app.services.get('conversation')
    
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
    contact_service = current_app.services.get('contact')
    conversation_service = current_app.services.get('conversation')
    
    action = request.form.get('action')
    conversation_ids = [int(id) for id in request.form.getlist('conversation_ids')]
    
    if not conversation_ids:
        flash('No conversations selected', 'warning')
        return redirect(url_for('contact.conversation_list'))
    
    try:
        if action == 'mark_read':
            # Use conversation service to mark as read
            success, message = conversation_service.mark_conversations_read(conversation_ids)
            flash(message, 'success' if success else 'error')
            
        elif action == 'add_to_campaign':
            campaign_id = request.form.get('campaign_id')
            if not campaign_id:
                flash('No campaign selected', 'warning')
                return redirect(url_for('contact.conversation_list'))
            
            # Get contact IDs from conversations
            contact_ids = conversation_service.get_contact_ids_from_conversations(conversation_ids)
            
            # Use ContactService to bulk add to campaign
            added_count, message = contact_service.bulk_add_to_campaign(contact_ids, int(campaign_id))
            flash(message, 'success' if added_count > 0 else 'warning')
            
        elif action == 'flag_office':
            # Get contact IDs from conversations
            contact_ids = conversation_service.get_contact_ids_from_conversations(conversation_ids)
            
            # Flag contacts as office numbers
            flagged = 0
            for contact_id in contact_ids:
                if contact_service.add_contact_flag(contact_id, 'office_number', 'Bulk flagged as office number', 'bulk_action'):
                    flagged += 1
            
            flash(f'Flagged {flagged} contacts as office numbers', 'success')
            
        elif action == 'export':
            # Get contact IDs from conversations
            contact_ids = conversation_service.get_contact_ids_from_conversations(conversation_ids)
            
            # Export conversation data
            csv_data = conversation_service.export_conversations_with_contacts(conversation_ids)
            
            response = make_response(csv_data)
            response.headers['Content-Disposition'] = 'attachment; filename=conversations_export.csv'
            response.headers['Content-Type'] = 'text/csv'
            return response
            
        else:
            flash('Invalid action selected', 'warning')
            
    except Exception as e:
        flash(f'Error performing bulk action: {str(e)}', 'error')
    
    return redirect(url_for('contact.conversation_list'))

@contact_bp.route('/<int:contact_id>')
@login_required
def contact_detail(contact_id):
    """Display contact details"""
    contact_service = current_app.services.get('contact')
    message_service = current_app.services.get('message')
    
    result = contact_service.get_contact_by_id(contact_id)
    if not result.is_success or not result.data:
        flash('Contact not found', 'error')
        return redirect(url_for('contact.list_all'))
    
    contact = result.data
    activities = message_service.get_activities_for_contact(contact_id)
    
    # Get emails if contact has email
    recent_emails = []
    if contact.email:
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
    """Display contact conversation with enhanced details"""
    contact_service = current_app.services.get('contact')
    message_service = current_app.services.get('message')
    
    # Get contact with eager loading for properties and jobs
    contact = contact_service.get_contact_with_relations(contact_id)
    
    if not contact:
        flash('Contact not found', 'error')
        return redirect(url_for('contact.list_all'))
    
    activities_result = message_service.get_activities_for_contact(contact_id)
    activities = activities_result.data if activities_result.is_success else []
    
    # Get recent jobs from pre-loaded properties
    recent_jobs = []
    if hasattr(contact, 'properties') and contact.properties:
        for prop in contact.properties:
            if hasattr(prop, 'jobs'):
                recent_jobs.extend(prop.jobs)
    recent_jobs = sorted(recent_jobs, key=lambda x: x.completed_at if x.completed_at else datetime.min, reverse=True)[:3]
    
    # Get contact flags
    flags_result = contact_service.get_contact_flags(contact_id)
    if flags_result.is_success:
        flags = flags_result.data
        has_office_flag = flags.get('has_office_flag', False)
        has_opted_out = flags.get('has_opted_out', False)
    else:
        has_office_flag = False
        has_opted_out = False
    
    # Get campaign memberships
    campaign_memberships = contact_service.get_campaign_memberships(contact_id)
    # Limit to 3 most recent
    if campaign_memberships:
        campaign_memberships = campaign_memberships[:3]
    
    # Calculate statistics
    call_count = sum(1 for a in activities if hasattr(a, 'activity_type') and a.activity_type == 'call')
    last_activity = max(activities, key=lambda a: a.created_at) if activities else None
    last_activity_date = last_activity.created_at.strftime('%b %d, %Y') if last_activity else None
    
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
    contact_service = current_app.services.get('contact')
    openphone_service = current_app.services.get('openphone')
    
    contact_result = contact_service.get_contact_by_id(contact_id)
    
    if not contact_result.is_success or not contact_result.data:
        flash('Contact not found', 'error')
        return redirect(url_for('contact.conversation_list'))
    
    contact = contact_result.data
    
    message_body = request.form.get('body', '').strip()
    
    if not message_body:
        flash('Message cannot be empty', 'warning')
        return redirect(url_for('contact.conversation', contact_id=contact_id))
    
    if not contact.phone:
        flash('Contact has no phone number', 'error')
        return redirect(url_for('contact.conversation', contact_id=contact_id))
    
    # Send message via OpenPhone
    try:
        result = openphone_service.send_message(
            to_number=contact.phone,
            body=message_body
        )
        
        if result.get('success'):
            flash('Message sent successfully!', 'success')
        else:
            flash(f'Failed to send message: {result.get("error", "Unknown error")}', 'error')
    except Exception as e:
        flash(f'Error sending message: {str(e)}', 'error')
    
    return redirect(url_for('contact.conversation', contact_id=contact_id))

@contact_bp.route('/<int:contact_id>/flag', methods=['POST'])
@login_required
def flag_contact(contact_id):
    """Add a flag to a contact"""
    contact_service = current_app.services.get('contact')
    
    flag_type = request.form.get('flag_type')
    reason = request.form.get('reason', '')
    
    if not flag_type:
        flash('Flag type is required', 'error')
        return redirect(url_for('contact.conversation', contact_id=contact_id))
    
    result = contact_service.add_contact_flag(
        contact_id=contact_id,
        flag_type=flag_type,
        flag_reason=reason,
        created_by=str(current_user.id) if current_user.is_authenticated else 'system'
    )
    success = result.is_success
    
    if success:
        flash(f'Contact flagged as {flag_type}', 'success')
    else:
        flash(f'Failed to flag contact: {result.error_message}', 'warning')
    
    return redirect(url_for('contact.conversation', contact_id=contact_id))

@contact_bp.route('/<int:contact_id>/unflag', methods=['POST'])
@login_required
def unflag_contact(contact_id):
    """Remove a flag from a contact"""
    contact_service = current_app.services.get('contact')
    
    flag_type = request.form.get('flag_type')
    
    if not flag_type:
        flash('Flag type is required', 'error')
        return redirect(url_for('contact.conversation', contact_id=contact_id))
    
    result = contact_service.remove_contact_flag(contact_id, flag_type)
    success = result.is_success
    
    if success:
        flash(f'Removed {flag_type} flag', 'success')
    else:
        flash(f'Error removing flag: {result.error_message}', 'error')
    
    return redirect(url_for('contact.conversation', contact_id=contact_id))

@contact_bp.route('/bulk-action', methods=['POST'])
@login_required
def bulk_contact_action():
    """Handle bulk actions on contacts"""
    contact_service = current_app.services.get('contact')
    
    action = request.form.get('action')
    contact_ids = [int(id) for id in request.form.getlist('contact_ids')]
    
    if not contact_ids:
        flash('No contacts selected', 'warning')
        return redirect(url_for('contact.list_all'))
    
    if action == 'export':
        # Export contacts to CSV
        result = contact_service.export_contacts(contact_ids)
        
        if result.is_success:
            response = make_response(result.data)
            response.headers['Content-Disposition'] = 'attachment; filename=contacts_export.csv'
            response.headers['Content-Type'] = 'text/csv'
            return response
        else:
            flash(result.error or 'Export failed', 'error')
            return redirect(url_for('contact.list_all'))
    else:
        # Use bulk_action for other operations
        form_data = request.form.to_dict()
        # Remove duplicate action and contact_ids from form data
        form_data.pop('action', None)
        form_data.pop('contact_ids', None)
        
        result = contact_service.bulk_action(
            action=action,
            contact_ids=contact_ids,
            **form_data
        )
        
        if result.is_success:
            flash(result.data or 'Bulk action completed successfully', 'success')
        else:
            flash(result.error or 'Bulk action failed', 'error')
    
    return redirect(url_for('contact.list_all'))

@contact_bp.route('/add', methods=['GET', 'POST'])
@login_required
def add_contact():
    """Add a new contact"""
    contact_service = current_app.services.get('contact')
    
    if request.method == 'POST':
        result = contact_service.add_contact(
            first_name=request.form['first_name'],
            last_name=request.form['last_name'],
            email=request.form.get('email'),
            phone=request.form.get('phone')
        )
        if result.is_success:
            flash('Contact added successfully', 'success')
        else:
            flash(f'Error adding contact: {result.error or "possible duplicate"}', 'error')
        return redirect(url_for('contact.list_all'))
    
    return render_template('add_edit_contact_form.html')

@contact_bp.route('/<int:contact_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_contact(contact_id):
    """Edit an existing contact"""
    contact_service = current_app.services.get('contact')
    
    result = contact_service.get_contact_by_id(contact_id)
    if not result.is_success or not result.data:
        flash('Contact not found', 'error')
        return redirect(url_for('contact.list_all'))
    
    contact = result.data
    
    if request.method == 'POST':
        update_result = contact_service.update_contact(
            contact_id,
            first_name=request.form['first_name'],
            last_name=request.form['last_name'],
            email=request.form.get('email'),
            phone=request.form.get('phone')
        )
        if update_result.is_success:
            flash('Contact updated successfully', 'success')
        else:
            flash(f'Error updating contact: {update_result.error}', 'error')
        return redirect(url_for('contact.contact_detail', contact_id=contact_id))
    
    return render_template('add_edit_contact_form.html', contact=contact)


@contact_bp.route('/<int:contact_id>/delete', methods=['POST'])
@login_required
def delete_contact(contact_id):
    """Delete a contact"""
    contact_service = current_app.services.get('contact')
    
    delete_result = contact_service.delete_contact(contact_id)
    if delete_result.is_success:
        flash('Contact deleted successfully', 'success')
    else:
        flash(f'Error deleting contact: {delete_result.error}', 'error')
    
    return redirect(url_for('contact.list_all'))