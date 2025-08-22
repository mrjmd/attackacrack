"""
Campaign routes for creating and managing text campaigns
Refactored to use service registry pattern
"""

from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash, current_app, abort, Response
from flask_login import login_required
from datetime import datetime, timedelta
from extensions import db
import csv
import io
import logging

logger = logging.getLogger(__name__)
# Direct model imports removed - use services only

campaigns_bp = Blueprint('campaigns', __name__)


@campaigns_bp.route('/campaigns')
@login_required
def campaign_list():
    """List all campaigns with basic stats"""
    campaign_service = current_app.services.get('campaign')
    campaign_data = campaign_service.get_all_campaigns_with_analytics()
    return render_template('campaigns/list.html', campaigns=campaign_data)


@campaigns_bp.route('/campaigns/new')
@login_required
def new_campaign():
    """Show campaign creation form"""
    campaign_service = current_app.services.get('campaign')
    list_service = current_app.services.get('campaign_list')
    
    # Get audience statistics from service
    audience_stats = campaign_service.get_audience_stats()
    
    # Get available campaign lists with stats
    campaign_lists = []
    lists_result = list_service.get_all_lists()
    if lists_result.is_success and lists_result.data:
        for lst in lists_result.data:
            stats_result = list_service.get_list_stats(lst.id)
            if stats_result.is_success:
                # Add active members count as a property for the template
                lst.active_members_count = stats_result.data.get('active_members', 0)
            else:
                lst.active_members_count = 0
            campaign_lists.append(lst)
    
    return render_template('campaigns/new.html', 
                         audience_stats=audience_stats,
                         campaign_lists=campaign_lists)


@campaigns_bp.route('/campaigns', methods=['POST'])
@login_required
def create_campaign():
    """Create a new campaign"""
    try:
        campaign_service = current_app.services.get('campaign')
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
        
        # Add recipients based on list or filters
        if data.get('use_list') == 'on' and data.get('list_id'):
            # Use existing campaign list
            recipients_added = campaign_service.add_recipients_from_list(
                campaign.id, 
                int(data['list_id'])
            )
        else:
            # Use filters
            contact_filters = {
                'has_name_only': data.get('has_name_only') == 'on',
                'has_email': data.get('has_email') == 'on',
                'exclude_office_numbers': data.get('exclude_office_numbers') == 'on',
                'exclude_opted_out': data.get('exclude_opted_out') == 'on'
            }
            recipients_added = campaign_service.add_recipients(campaign.id, contact_filters)
        
        flash(f'Campaign created with {recipients_added} recipients!', 'success')
        return redirect(url_for('campaigns.campaign_detail', campaign_id=campaign.id))
    
    except Exception as e:
        flash(f'Error creating campaign: {str(e)}', 'error')
        return redirect(url_for('campaigns.new_campaign'))


@campaigns_bp.route('/campaigns/<int:campaign_id>')
@login_required
def campaign_detail(campaign_id):
    """Show campaign details and analytics"""
    campaign_service = current_app.services.get('campaign')
    campaign = campaign_service.get_by_id(campaign_id)
    if not campaign:
        abort(404)
    analytics = campaign_service.get_campaign_analytics(campaign_id)
    
    # Get bounce metrics for this campaign
    metrics_service = current_app.services.get('sms_metrics')
    bounce_metrics = metrics_service.get_campaign_metrics(campaign_id)
    
    # Get recent sends for activity feed
    recent_sends = campaign_service.get_recent_sends(campaign_id, limit=10)
    
    return render_template('campaigns/detail.html', 
                         campaign=campaign,
                         analytics=analytics,
                         bounce_metrics=bounce_metrics,
                         recent_sends=recent_sends)


@campaigns_bp.route('/campaigns/<int:campaign_id>/edit')
@login_required
def edit_campaign(campaign_id):
    """Show campaign edit form"""
    campaign_service = current_app.services.get('campaign')
    campaign = campaign_service.get_by_id(campaign_id)
    if not campaign:
        abort(404)
    
    return render_template('campaigns/edit.html', campaign=campaign)


@campaigns_bp.route('/campaigns/<int:campaign_id>/members')
@login_required
def campaign_members(campaign_id):
    """Show campaign members"""
    campaign_service = current_app.services.get('campaign')
    campaign = campaign_service.get_by_id(campaign_id)
    if not campaign:
        abort(404)
    
    members = campaign_service.get_campaign_members(campaign_id)
    
    return render_template('campaigns/members.html', 
                         campaign=campaign,
                         members=members)


@campaigns_bp.route('/campaigns/<int:campaign_id>/start', methods=['POST'])
@login_required
def start_campaign(campaign_id):
    """Start a campaign"""
    try:
        campaign_service = current_app.services.get('campaign')
        success = campaign_service.start_campaign(campaign_id)
        if success:
            flash('Campaign started successfully!', 'success')
        else:
            flash('Failed to start campaign', 'error')
    except Exception as e:
        flash(f'Error starting campaign: {str(e)}', 'error')
    
    return redirect(url_for('campaigns.campaign_detail', campaign_id=campaign_id))


@campaigns_bp.route('/campaigns/<int:campaign_id>/pause', methods=['POST'])
@login_required
def pause_campaign(campaign_id):
    """Pause a running campaign"""
    campaign_service = current_app.services.get('campaign')
    success = campaign_service.pause_campaign(campaign_id)
    
    if success:
        flash('Campaign paused', 'info')
    else:
        flash('Campaign is not running or not found', 'warning')
    
    return redirect(url_for('campaigns.campaign_detail', campaign_id=campaign_id))


@campaigns_bp.route('/campaigns/<int:campaign_id>/recipients')
@login_required
def campaign_recipients(campaign_id):
    """Show campaign recipients with filtering"""
    campaign_service = current_app.services.get('campaign')
    campaign = campaign_service.get_by_id(campaign_id)
    if not campaign:
        abort(404)
    
    # Get filter parameters
    status_filter = request.args.get('status', 'all')
    variant_filter = request.args.get('variant', 'all')
    
    # Use campaign service to get members
    status = status_filter if status_filter != 'all' else None
    
    # Get all members for now (pagination can be added later)
    members_data = campaign_service.get_campaign_members(
        campaign_id, 
        status=status,
        page=1,
        per_page=1000  # Large number to get all for now
    )
    
    recipients = members_data.get('items', [])
    
    # TODO: Add variant filtering support to campaign service
    # For now, we'll apply variant filter in memory if needed
    if variant_filter != 'all':
        recipients = [r for r in recipients if getattr(r, 'variant_sent', None) == variant_filter]
    
    return render_template('campaigns/recipients.html',
                         campaign=campaign,
                         recipients=recipients,
                         status_filter=status_filter,
                         variant_filter=variant_filter)


@campaigns_bp.route('/api/campaigns/<int:campaign_id>/analytics')
@login_required
def api_campaign_analytics(campaign_id):
    """API endpoint for real-time campaign analytics"""
    try:
        campaign_service = current_app.services.get('campaign')
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
@login_required
def api_preview_audience():
    """Preview campaign audience size based on filters"""
    try:
        campaign_service = current_app.services.get('campaign')
        data = request.json
        preview = campaign_service.preview_audience(data)
        
        return jsonify({
            'success': True,
            'audience_size': preview['total_count'],
            'sample_contacts': preview['sample_contacts']
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# Campaign List Management Routes
@campaigns_bp.route("/campaigns/lists")
@login_required
def campaign_lists():
    """Show all campaign lists"""
    list_service = current_app.services.get('campaign_list')
    csv_service = current_app.services.get('csv_import')
    
    lists_result = list_service.get_all_lists()
    
    # Handle Result object properly
    if not lists_result.is_success:
        flash('Failed to load campaign lists', 'error')
        lists = []
    else:
        lists = lists_result.data if lists_result.data else []
    
    # Get stats for each list
    list_data = []
    for lst in lists:
        stats_result = list_service.get_list_stats(lst.id)
        if stats_result.is_success:
            stats = stats_result.data
        else:
            stats = {'active_members': 0, 'removed_members': 0, 'total_members': 0}
        list_data.append({
            "list": lst,
            "stats": stats
        })
    
    # Get recent imports if csv_service is available
    recent_imports = []
    if csv_service:
        recent_imports = csv_service.get_import_history(limit=5)
    
    return render_template("campaigns/lists.html", 
                         lists=list_data,
                         recent_imports=recent_imports)


@campaigns_bp.route("/campaigns/lists/new", methods=["GET", "POST"])
@login_required
def new_campaign_list():
    """Create a new campaign list"""
    list_service = current_app.services.get('campaign_list')
    
    if request.method == "POST":
        data = request.form
        
        # Create the list
        try:
            # Determine if list is dynamic
            is_dynamic = False
            criteria = None
            
            if data.get("list_type") == "dynamic" or data.get("is_dynamic"):
                is_dynamic = True
                # Build criteria based on form inputs
                criteria = {}
                
                if data.get("has_phone"):
                    criteria["has_phone"] = True
                if data.get("has_email"):
                    criteria["has_email"] = True
                if data.get("exclude_opted_out"):
                    criteria["exclude_opted_out"] = True
                if data.get("exclude_office"):
                    criteria["exclude_office"] = True
                if data.get("has_name"):
                    criteria["has_name"] = True
                    
                # Activity-based criteria
                if data.get("recent_activity"):
                    criteria["recent_activity_days"] = int(data.get("recent_activity_days", 30))
                if data.get("no_recent_activity"):
                    criteria["no_recent_activity_days"] = int(data.get("no_recent_activity_days", 90))
            
            campaign_list = list_service.create_list(
                name=data["name"],
                description=data.get("description", ""),
                is_dynamic=is_dynamic,
                filter_criteria=criteria
            )
            
            # If static list and contacts provided, add them
            if not is_dynamic and data.get("contact_ids"):
                contact_ids = [int(id) for id in data.get("contact_ids", "").split(",") if id]
                list_service.add_contacts_to_list(campaign_list.id, contact_ids)
            
            flash(f"Campaign list '{campaign_list.name}' created successfully!", "success")
            return redirect(url_for("campaigns.campaign_lists"))
            
        except Exception as e:
            flash(f"Error creating list: {str(e)}", "error")
    
    # Get contact counts for filters
    contact_service = current_app.services.get('contact')
    filter_stats = contact_service.get_contact_statistics()
    
    return render_template("campaigns/new_list.html", filter_stats=filter_stats)


@campaigns_bp.route("/campaigns/lists/<int:list_id>")
@login_required
def campaign_list_detail(list_id):
    """Show campaign list details"""
    list_service = current_app.services.get('campaign_list')
    
    campaign_list = list_service.get_campaign_list_by_id(list_id)
    if not campaign_list:
        from flask import abort
        abort(404)
    stats_result = list_service.get_list_stats(list_id)
    stats = stats_result.data if stats_result.is_success else {}
    
    contacts_result = list_service.get_list_contacts(list_id)
    if contacts_result.is_success and contacts_result.data:
        contacts = contacts_result.data[:50]  # Show first 50
    else:
        contacts = []
    
    # Get campaigns using this list
    campaign_service = current_app.services.get('campaign')
    # TODO: Implement get_campaigns_using_list method in CampaignService
    campaigns_using = []  # Temporary fallback until method is implemented
    
    return render_template("campaigns/list_detail.html",
                         list=campaign_list,
                         stats=stats,
                         contacts=contacts,
                         campaigns=campaigns_using)


@campaigns_bp.route("/campaigns/lists/<int:list_id>/refresh", methods=["POST"])
@login_required
def refresh_campaign_list(list_id):
    """Refresh a dynamic campaign list"""
    list_service = current_app.services.get('campaign_list')
    
    try:
        updated_count = list_service.refresh_dynamic_list(list_id)
        flash(f"List refreshed. Updated {updated_count} contacts.", "success")
    except ValueError as e:
        flash(str(e), "warning")
    except Exception as e:
        flash(f"Error refreshing list: {str(e)}", "error")
    
    return redirect(url_for("campaigns.campaign_list_detail", list_id=list_id))


@campaigns_bp.route("/campaigns/import-csv", methods=["GET", "POST"])
@login_required
def import_csv():
    """Import CSV to create campaign list"""
    if request.method == "POST":
        csv_service = current_app.services.get('csv_import')
        if not csv_service:
            # CSV service should always be registered
            flash('CSV import service not available', 'error')
            return redirect(url_for('campaigns.import_csv'))
        
        try:
            # Check if file was uploaded
            if 'csv_file' not in request.files:
                flash('No file selected', 'error')
                return redirect(request.url)
            
            file = request.files['csv_file']
            if file.filename == '':
                flash('No file selected', 'error')
                return redirect(request.url)
            
            # Process the CSV
            list_name = request.form.get('list_name', f'Import {datetime.now().strftime("%Y-%m-%d")}')
            enrichment_mode = request.form.get('enrichment_mode', 'enrich_missing')
            
            result = csv_service.import_csv(
                file=file,
                list_name=list_name,
                enrichment_mode=enrichment_mode
            )
            
            if result['success']:
                flash(f"Successfully imported {result['imported']} contacts. {result['updated']} updated, {result['errors']} errors.", 'success')
                if result.get('list_id'):
                    return redirect(url_for('campaigns.campaign_list_detail', list_id=result['list_id']))
            else:
                flash(f"Import failed: {result.get('message', 'Unknown error')}", 'error')
                
        except Exception as e:
            flash(f'Error processing CSV: {str(e)}', 'error')
            
    # Get import history
    csv_service = current_app.services.get('csv_import')
    recent_imports = []
    if csv_service:
        recent_imports = csv_service.get_import_history(limit=10)
    
    return render_template('campaigns/import_csv.html', recent_imports=recent_imports)


@campaigns_bp.route('/opt-out-report')
@login_required
def opt_out_report():
    """Display opt-out report and statistics"""
    try:
        # Get opt-out service
        opt_out_service = current_app.services.get('opt_out')
        if not opt_out_service:
            flash('Opt-out service not available', 'warning')
            return redirect(url_for('campaigns.campaign_list'))
        
        # Get statistics
        stats = opt_out_service.get_opt_out_statistics()
        
        # Calculate opt-out rate
        contact_service = current_app.services.get('contact')
        total_contacts_result = contact_service.count_all_contacts()
        total_contacts = total_contacts_result.data if total_contacts_result.is_success else 0
        
        if total_contacts > 0:
            stats['opt_out_rate'] = (stats['total_opted_out'] / total_contacts) * 100
        else:
            stats['opt_out_rate'] = 0
        
        # Get recent opt-outs with pagination
        page = request.args.get('page', 1, type=int)
        per_page = 20
        
        # Get opt-outs from last 30 days
        since_date = datetime.utcnow() - timedelta(days=30)
        recent_opt_outs = opt_out_service.get_recent_opt_outs(since=since_date)
        
        # Manual pagination
        start = (page - 1) * per_page
        end = start + per_page
        paginated_opt_outs = recent_opt_outs[start:end]
        
        has_prev = page > 1
        has_next = end < len(recent_opt_outs)
        
        return render_template(
            'campaigns/opt_out_report.html',
            stats=stats,
            recent_opt_outs=paginated_opt_outs,
            page=page,
            has_prev=has_prev,
            has_next=has_next
        )
        
    except Exception as e:
        logger.error(f"Error generating opt-out report: {e}")
        flash('Error generating opt-out report', 'danger')
        return redirect(url_for('campaigns.campaign_list'))


@campaigns_bp.route('/opt-out-report/export')
@login_required
def export_opt_outs():
    """Export opt-out data to CSV"""
    try:
        opt_out_service = current_app.services.get('opt_out')
        if not opt_out_service:
            flash('Opt-out service not available', 'warning')
            return redirect(url_for('campaigns.opt_out_report'))
        
        # Get all opt-outs from last year
        since_date = datetime.utcnow() - timedelta(days=365)
        opt_outs = opt_out_service.get_recent_opt_outs(since=since_date)
        
        # Create CSV
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow([
            'Date/Time',
            'Contact ID',
            'Contact Name',
            'Phone Number',
            'Keyword Used',
            'Source'
        ])
        
        # Write data
        for opt_out in opt_outs:
            writer.writerow([
                opt_out.get('created_at'),
                opt_out.get('contact_id'),
                opt_out.get('contact_name', ''),
                opt_out.get('phone_number'),
                opt_out.get('keyword_used'),
                opt_out.get('source', '')
            ])
        
        # Create response
        output.seek(0)
        return Response(
            output.getvalue(),
            mimetype='text/csv',
            headers={
                'Content-Disposition': f'attachment; filename=opt_outs_{datetime.now().strftime("%Y%m%d")}.csv'
            }
        )
        
    except Exception as e:
        logger.error(f"Error exporting opt-outs: {e}")
        flash('Error exporting opt-out data', 'danger')
        return redirect(url_for('campaigns.opt_out_report'))