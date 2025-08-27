"""
Campaign routes for creating and managing text campaigns
Refactored to use service registry pattern
"""

from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash, current_app, abort, Response
from auth_utils import login_required
from datetime import datetime, timedelta
from utils.datetime_utils import utc_now
from services.common.result import Result
from extensions import db
import csv
import io
import json
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
            
            # Handle async response (large files)
            if result.get('async'):
                task_id = result.get('task_id')
                flash(f"Large file detected. Import is processing in the background. Track progress: Task ID {task_id}", 'info')
                return render_template('campaigns/import_progress.html', 
                                     task_id=task_id, 
                                     list_name=list_name,
                                     message=result.get('message', 'Import in progress...'))
            
            # Handle sync response (small files)
            if result.get('success'):
                imported_count = result.get('imported', 0)
                updated_count = result.get('updated', 0)
                error_count = len(result.get('errors', []))
                
                flash(f"Successfully imported {imported_count} contacts. {updated_count} updated, {error_count} errors.", 'success')
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


@campaigns_bp.route("/campaigns/import-progress/<task_id>")
@login_required
def import_progress(task_id):
    """Get progress of async CSV import task"""
    csv_service = current_app.services.get('csv_import')
    if not csv_service:
        return jsonify({'error': 'CSV import service not available'}), 500
    
    try:
        progress = csv_service.get_import_progress(task_id)
        return jsonify(progress)
    except Exception as e:
        return jsonify({'error': f'Error getting progress: {str(e)}'}), 500


@campaigns_bp.route("/campaigns/import-status/<task_id>")
@login_required
def import_status_page(task_id):
    """Display import progress page"""
    return render_template('campaigns/import_progress.html', task_id=task_id)


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
        since_date = utc_now() - timedelta(days=30)
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
        since_date = utc_now() - timedelta(days=365)
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


# Phase 3C: Campaign Scheduling Routes

@campaigns_bp.route('/api/campaigns/<int:campaign_id>/schedule', methods=['GET'])
@login_required
def api_get_campaign_schedule(campaign_id):
    """Get campaign schedule information"""
    try:
        scheduling_service = current_app.services.get('campaign_scheduling')
        if not scheduling_service:
            return jsonify({
                'success': False,
                'error': 'Scheduling service not available'
            }), 503
        
        result = scheduling_service.get_campaign_schedule_info(campaign_id)
        
        if result.is_success:
            info = result.data
            # Check if campaign is scheduled
            is_scheduled = info['status'] == 'scheduled'
            
            return jsonify({
                'success': True,
                'campaign_id': campaign_id,
                'is_scheduled': is_scheduled,
                'scheduled_at': info['scheduled_at'].isoformat() if info['scheduled_at'] else None,
                'timezone': info['timezone'],
                'is_recurring': info['is_recurring'],
                'recurrence_pattern': info['recurrence_pattern'],
                'next_run_at': info['next_run_at'].isoformat() if info['next_run_at'] else None
            })
        else:
            return jsonify({
                'success': False,
                'error': result.error
            }), 404
            
    except Exception as e:
        logger.error(f"Error getting campaign schedule: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@campaigns_bp.route('/api/campaigns/<int:campaign_id>/schedule', methods=['POST'])
@login_required
def api_schedule_campaign(campaign_id):
    """Schedule a campaign for future execution"""
    try:
        scheduling_service = current_app.services.get('campaign_scheduling')
        if not scheduling_service:
            return jsonify({
                'success': False,
                'error': 'Scheduling service not available'
            }), 503
        
        # Handle malformed JSON
        try:
            data = request.get_json(force=True)
        except Exception:
            return jsonify({
                'success': False,
                'error': 'Invalid JSON format'
            }), 400
            
        if data is None:
            return jsonify({
                'success': False,
                'error': 'No data provided'
            }), 400
        
        # Parse scheduled time
        scheduled_at_str = data.get('scheduled_at')
        if not scheduled_at_str:
            return jsonify({
                'success': False,
                'error': 'scheduled_at is required'
            }), 400
        
        scheduled_at = datetime.fromisoformat(scheduled_at_str.replace('Z', '+00:00'))
        timezone = data.get('timezone', 'UTC')
        
        # Validate not in the past
        if scheduled_at < utc_now():
            return jsonify({
                'success': False,
                'error': 'Cannot schedule campaign in the past'
            }), 400
        
        # Schedule the campaign
        result = scheduling_service.schedule_campaign(
            campaign_id=campaign_id,
            scheduled_at=scheduled_at,
            timezone=timezone
        )
        
        if result.is_success:
            return jsonify({
                'success': True,
                'campaign_id': campaign_id,
                'scheduled_at': scheduled_at.isoformat(),
                'timezone': timezone
            })
        else:
            return jsonify({
                'success': False,
                'error': result.error
            }), 400
            
    except Exception as e:
        logger.error(f"Error scheduling campaign {campaign_id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@campaigns_bp.route('/api/campaigns/<int:campaign_id>/recurring', methods=['POST'])
@login_required
def api_create_recurring_campaign(campaign_id):
    """Create a recurring campaign"""
    try:
        scheduling_service = current_app.services.get('campaign_scheduling')
        if not scheduling_service:
            return jsonify({
                'success': False,
                'error': 'Scheduling service not available'
            }), 503
        
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'error': 'No data provided'
            }), 400
        
        # Parse start time
        start_at_str = data.get('start_at')
        if not start_at_str:
            return jsonify({
                'success': False,
                'error': 'start_at is required'
            }), 400
        
        start_at = datetime.fromisoformat(start_at_str.replace('Z', '+00:00'))
        recurrence_pattern = data.get('recurrence_pattern')
        timezone = data.get('timezone', 'UTC')
        
        if not recurrence_pattern:
            return jsonify({
                'success': False,
                'error': 'recurrence_pattern is required'
            }), 400
        
        # Create recurring campaign
        result = scheduling_service.create_recurring_campaign(
            campaign_id=campaign_id,
            start_at=start_at,
            recurrence_pattern=recurrence_pattern,
            timezone=timezone
        )
        
        if result.is_success:
            campaign = result.data
            return jsonify({
                'success': True,
                'campaign_id': campaign_id,
                'is_recurring': True,
                'recurrence_pattern': recurrence_pattern,
                'next_run_at': campaign.next_run_at.isoformat() if campaign.next_run_at else None
            })
        else:
            return jsonify({
                'success': False,
                'error': result.error
            }), 400
            
    except Exception as e:
        logger.error(f"Error creating recurring campaign {campaign_id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@campaigns_bp.route('/api/campaigns/<int:campaign_id>/schedule', methods=['DELETE'])
@login_required
def api_cancel_schedule(campaign_id):
    """Cancel a scheduled campaign"""
    try:
        scheduling_service = current_app.services.get('campaign_scheduling')
        if not scheduling_service:
            return jsonify({
                'success': False,
                'error': 'Scheduling service not available'
            }), 503
        
        result = scheduling_service.cancel_schedule(campaign_id)
        
        if result.is_success:
            return jsonify({
                'success': True,
                'campaign_id': campaign_id,
                'message': 'Schedule cancelled'
            })
        else:
            return jsonify({
                'success': False,
                'error': result.error
            }), 400
            
    except Exception as e:
        logger.error(f"Error cancelling schedule for campaign {campaign_id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@campaigns_bp.route('/api/campaigns/<int:campaign_id>/schedule', methods=['PUT'])
@login_required
def api_update_schedule(campaign_id):
    """Update schedule for a campaign"""
    try:
        scheduling_service = current_app.services.get('campaign_scheduling')
        if not scheduling_service:
            return jsonify({
                'success': False,
                'error': 'Scheduling service not available'
            }), 503
        
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'error': 'No data provided'
            }), 400
        
        scheduled_at_str = data.get('scheduled_at')
        if not scheduled_at_str:
            return jsonify({
                'success': False,
                'error': 'scheduled_at is required'
            }), 400
        
        scheduled_at = datetime.fromisoformat(scheduled_at_str.replace('Z', '+00:00'))
        timezone = data.get('timezone')
        
        result = scheduling_service.update_schedule(
            campaign_id=campaign_id,
            scheduled_at=scheduled_at,
            timezone=timezone
        )
        
        if result.is_success:
            return jsonify({
                'success': True,
                'campaign_id': campaign_id,
                'scheduled_at': scheduled_at.isoformat()
            })
        else:
            return jsonify({
                'success': False,
                'error': result.error
            }), 400
            
    except Exception as e:
        logger.error(f"Error updating schedule for campaign {campaign_id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@campaigns_bp.route('/api/campaigns/<int:campaign_id>/unarchive', methods=['POST'])
@login_required
def api_unarchive_campaign(campaign_id):
    """Unarchive a campaign"""
    try:
        scheduling_service = current_app.services.get('campaign_scheduling')
        if not scheduling_service:
            return jsonify({
                'success': False,
                'error': 'Scheduling service not available'
            }), 503
        
        result = scheduling_service.unarchive_campaign(campaign_id)
        
        if result.is_success:
            return jsonify({
                'success': True,
                'campaign_id': campaign_id,
                'archived': False
            })
        else:
            return jsonify({
                'success': False,
                'error': result.error
            }), 400
            
    except Exception as e:
        logger.error(f"Error unarchiving campaign {campaign_id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@campaigns_bp.route('/api/campaigns/scheduled')
@login_required
def api_get_scheduled_campaigns():
    """Get all scheduled campaigns"""
    try:
        scheduling_service = current_app.services.get('campaign_scheduling')
        if not scheduling_service:
            return jsonify({
                'success': False,
                'error': 'Scheduling service not available'
            }), 503
        
        include_archived = request.args.get('include_archived', 'false').lower() == 'true'
        campaigns = scheduling_service.get_scheduled_campaigns(include_archived=include_archived)
        
        campaign_data = []
        for campaign in campaigns:
            # Ensure consistent datetime formatting
            scheduled_at = None
            if campaign.scheduled_at:
                # If timezone-aware, use as-is, otherwise treat as UTC
                dt = campaign.scheduled_at
                if dt.tzinfo is None:
                    from zoneinfo import ZoneInfo
                    dt = dt.replace(tzinfo=ZoneInfo('UTC'))
                scheduled_at = dt.isoformat()
            
            next_run_at = None
            if campaign.next_run_at:
                # If timezone-aware, use as-is, otherwise treat as UTC
                dt = campaign.next_run_at
                if dt.tzinfo is None:
                    from zoneinfo import ZoneInfo
                    dt = dt.replace(tzinfo=ZoneInfo('UTC'))
                next_run_at = dt.isoformat()
            
            campaign_data.append({
                'id': campaign.id,
                'name': campaign.name,
                'scheduled_at': scheduled_at,
                'timezone': campaign.timezone,
                'is_recurring': campaign.is_recurring,
                'recurrence_pattern': campaign.recurrence_pattern,
                'next_run_at': next_run_at,
                'archived': campaign.archived
            })
        
        return jsonify({
            'success': True,
            'campaigns': campaign_data,
            'count': len(campaign_data)
        })
        
    except Exception as e:
        logger.error(f"Error getting scheduled campaigns: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@campaigns_bp.route('/campaigns/<int:campaign_id>/schedule')
@login_required
def campaign_schedule_page(campaign_id):
    """Show campaign scheduling page"""
    campaign_service = current_app.services.get('campaign')
    scheduling_service = current_app.services.get('campaign_scheduling')
    
    campaign = campaign_service.get_by_id(campaign_id)
    if not campaign:
        abort(404)
    
    # Check if already scheduled
    is_scheduled = campaign.status == 'scheduled'
    scheduled_info = None
    if is_scheduled:
        scheduled_info = {
            'scheduled_at': campaign.scheduled_at,
            'timezone': campaign.timezone,
            'is_recurring': campaign.is_recurring,
            'recurrence_pattern': campaign.recurrence_pattern
        }
    
    return render_template('campaigns/schedule.html',
                         campaign=campaign,
                         is_scheduled=is_scheduled,
                         scheduled_info=scheduled_info)


@campaigns_bp.route('/campaigns/scheduled')
@login_required
def scheduled_campaigns():
    """Show all scheduled campaigns"""
    scheduling_service = current_app.services.get('campaign_scheduling')
    
    if not scheduling_service:
        flash('Scheduling service not available', 'error')
        return redirect(url_for('campaigns.campaign_list'))
    
    scheduled = scheduling_service.get_scheduled_campaigns()
    
    return render_template('campaigns/scheduled.html',
                         scheduled_campaigns=scheduled)


@campaigns_bp.route('/api/campaigns/<int:campaign_id>/cancel-schedule', methods=['POST'])
@login_required
def api_cancel_campaign_schedule(campaign_id):
    """Cancel a scheduled campaign"""
    try:
        scheduling_service = current_app.services.get('campaign_scheduling')
        if not scheduling_service:
            return jsonify({
                'success': False,
                'error': 'Scheduling service not available'
            }), 503
        
        result = scheduling_service.cancel_schedule(campaign_id)
        
        if result.is_success:
            campaign = result.data
            return jsonify({
                'success': True,
                'status': campaign.status,
                'message': 'Campaign schedule cancelled'
            })
        else:
            return jsonify({
                'success': False,
                'error': result.error
            }), 400
            
    except Exception as e:
        logger.error(f"Error cancelling campaign schedule: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@campaigns_bp.route('/api/campaigns/<int:campaign_id>/duplicate', methods=['POST'])
@login_required
def api_duplicate_campaign(campaign_id):
    """Duplicate a campaign with optional scheduling"""
    try:
        data = request.get_json() or {}
        scheduling_service = current_app.services.get('campaign_scheduling')
        
        if not scheduling_service:
            return jsonify({
                'success': False,
                'error': 'Scheduling service not available'
            }), 503
        
        # Extract parameters
        new_name = data.get('name', f"Copy of Campaign {campaign_id}")
        scheduled_at = data.get('scheduled_at')
        timezone = data.get('timezone', 'UTC')
        
        if scheduled_at:
            # Parse and schedule the duplicate
            from datetime import datetime
            scheduled_datetime = datetime.fromisoformat(scheduled_at.replace('Z', '+00:00'))
            result = scheduling_service.duplicate_campaign_with_schedule(
                campaign_id, new_name, scheduled_datetime, timezone
            )
        else:
            # Just duplicate without scheduling
            campaign_service = current_app.services.get('campaign')
            original = campaign_service.get_by_id(campaign_id)
            if not original:
                return jsonify({
                    'success': False,
                    'error': f'Campaign {campaign_id} not found'
                }), 404
                
            duplicate = campaign_service.create_campaign(
                name=new_name,
                campaign_type=original.campaign_type,
                template_a=original.template_a,
                template_b=original.template_b,
                daily_limit=original.daily_limit,
                business_hours_only=original.business_hours_only,
                audience_type=original.audience_type,
                channel=original.channel
            )
            result = Result.success({'campaign_id': duplicate.id})
        
        if result.is_success:
            return jsonify({
                'success': True,
                'campaign_id': result.data['campaign_id'],
                'message': 'Campaign duplicated successfully'
            })
        else:
            return jsonify({
                'success': False,
                'error': result.error
            }), 400
            
    except Exception as e:
        logger.error(f"Error duplicating campaign: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@campaigns_bp.route('/api/campaigns/<int:campaign_id>/archive', methods=['POST'])
@login_required
def api_archive_campaign(campaign_id):
    """Archive a campaign"""
    try:
        data = request.get_json() or {}
        reason = data.get('reason', '')
        
        campaign_repository = current_app.services.get('campaign_repository')
        if not campaign_repository:
            return jsonify({
                'success': False,
                'error': 'Campaign repository not available'
            }), 503
        
        campaign = campaign_repository.get_by_id(campaign_id)
        if not campaign:
            return jsonify({
                'success': False,
                'error': f'Campaign {campaign_id} not found'
            }), 404
        
        # Archive the campaign
        from utils.datetime_utils import utc_now
        campaign.archived = True
        campaign.archived_at = utc_now()
        campaign.archive_reason = reason
        campaign_repository.commit()
        
        return jsonify({
            'success': True,
            'archived': True,
            'archived_at': campaign.archived_at.isoformat(),
            'message': 'Campaign archived successfully'
        })
        
    except Exception as e:
        logger.error(f"Error archiving campaign: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@campaigns_bp.route('/api/campaigns/archived')
@login_required
def api_get_archived_campaigns():
    """Get all archived campaigns"""
    try:
        scheduling_service = current_app.services.get('campaign_scheduling')
        if not scheduling_service:
            return jsonify({
                'success': False,
                'error': 'Scheduling service not available'
            }), 503
        
        # Get query parameters
        include_date_range = request.args.get('include_date_range', 'false').lower() == 'true'
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        # Parse dates if provided
        from datetime import datetime
        if start_date:
            start_date = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
        if end_date:
            end_date = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
        
        campaigns = scheduling_service.get_archived_campaigns(
            include_date_range, start_date, end_date
        )
        
        campaign_data = []
        for campaign in campaigns:
            campaign_data.append({
                'id': campaign.id,
                'name': campaign.name,
                'status': campaign.status,
                'archived': campaign.archived,
                'archived_at': campaign.archived_at.isoformat() if campaign.archived_at else None,
                'archive_reason': getattr(campaign, 'archive_reason', None),
                'created_at': campaign.created_at.isoformat() if campaign.created_at else None
            })
        
        return jsonify({
            'success': True,
            'campaigns': campaign_data,
            'count': len(campaign_data)
        })
        
    except Exception as e:
        logger.error(f"Error getting archived campaigns: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@campaigns_bp.route('/api/campaigns/bulk-schedule', methods=['POST'])
@login_required
def api_bulk_schedule_campaigns():
    """Bulk schedule multiple campaigns"""
    try:
        data = request.get_json() or {}
        
        # Validate required fields
        if not data.get('campaign_ids'):
            return jsonify({
                'success': False,
                'error': 'campaign_ids is required'
            }), 400
            
        if not data.get('scheduled_at'):
            return jsonify({
                'success': False,
                'error': 'scheduled_at is required'
            }), 400
        
        scheduling_service = current_app.services.get('campaign_scheduling')
        if not scheduling_service:
            return jsonify({
                'success': False,
                'error': 'Scheduling service not available'
            }), 503
        
        # Parse parameters
        campaign_ids = data['campaign_ids']
        scheduled_at = data['scheduled_at']
        timezone = data.get('timezone', 'UTC')
        
        # Parse datetime
        from datetime import datetime
        scheduled_datetime = datetime.fromisoformat(scheduled_at.replace('Z', '+00:00'))
        
        # Schedule campaigns
        result = scheduling_service.bulk_schedule_campaigns(
            campaign_ids, scheduled_datetime, timezone
        )
        
        if result.is_success:
            return jsonify({
                'success': True,
                'campaigns_scheduled': result.data['campaigns_scheduled'],
                'failed_campaigns': result.data.get('failed_campaigns', []),
                'message': f"Scheduled {result.data['campaigns_scheduled']} campaigns"
            })
        else:
            return jsonify({
                'success': False,
                'error': result.error
            }), 400
            
    except Exception as e:
        logger.error(f"Error bulk scheduling campaigns: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@campaigns_bp.route('/api/campaigns/calendar')
@login_required
def api_get_campaign_calendar():
    """Get campaign calendar data"""
    try:
        scheduling_service = current_app.services.get('campaign_scheduling')
        if not scheduling_service:
            return jsonify({
                'success': False,
                'error': 'Scheduling service not available'
            }), 503
        
        # Get date range from query params
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        timezone = request.args.get('timezone', 'UTC')
        
        # Parse dates
        from datetime import datetime
        if start_date:
            start_date = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
        else:
            from utils.datetime_utils import utc_now
            start_date = utc_now()
            
        if end_date:
            end_date = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
        else:
            from datetime import timedelta
            end_date = start_date + timedelta(days=30)
        
        # Get campaigns in date range
        result = scheduling_service.get_campaign_calendar(
            start_date, end_date, timezone
        )
        
        if result.is_success:
            return jsonify({
                'success': True,
                'calendar_data': result.data,
                'campaigns': result.data,  # Keep for backward compatibility
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
                'timezone': timezone
            })
        else:
            return jsonify({
                'success': False,
                'error': result.error
            }), 400
            
    except Exception as e:
        logger.error(f"Error getting campaign calendar: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@campaigns_bp.route('/api/campaigns/<int:campaign_id>/schedule-info')
@login_required
def api_get_campaign_schedule_info(campaign_id):
    """Get schedule information for a campaign"""
    try:
        scheduling_service = current_app.services.get('campaign_scheduling')
        if not scheduling_service:
            return jsonify({
                'success': False,
                'error': 'Scheduling service not available'
            }), 503
        
        result = scheduling_service.get_campaign_schedule_info(campaign_id)
        
        if result.is_success:
            info = result.data
            return jsonify({
                'success': True,
                'campaign_id': info['campaign_id'],
                'status': info['status'],
                'scheduled_at': info['scheduled_at'].isoformat() if info['scheduled_at'] else None,
                'timezone': info['timezone'],
                'is_recurring': info['is_recurring'],
                'recurrence_pattern': info['recurrence_pattern'],
                'next_run_at': info['next_run_at'].isoformat() if info['next_run_at'] else None,
                'archived': info['archived']
            })
        else:
            return jsonify({
                'success': False,
                'error': result.error
            }), 404
            
    except Exception as e:
        logger.error(f"Error getting campaign schedule info: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@campaigns_bp.route('/api/timezones')
@login_required
def api_get_timezones():
    """Get list of supported timezones"""
    try:
        # Common US timezones
        timezones = [
            {'value': 'America/New_York', 'label': 'Eastern Time (ET)'},
            {'value': 'America/Chicago', 'label': 'Central Time (CT)'},
            {'value': 'America/Denver', 'label': 'Mountain Time (MT)'},
            {'value': 'America/Phoenix', 'label': 'Arizona Time (AZ)'},
            {'value': 'America/Los_Angeles', 'label': 'Pacific Time (PT)'},
            {'value': 'America/Anchorage', 'label': 'Alaska Time (AK)'},
            {'value': 'Pacific/Honolulu', 'label': 'Hawaii Time (HI)'},
            {'value': 'UTC', 'label': 'UTC'}
        ]
        
        return jsonify({
            'success': True,
            'timezones': timezones
        })
        
    except Exception as e:
        logger.error(f"Error getting timezones: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500