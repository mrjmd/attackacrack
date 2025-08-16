"""
Campaign routes for creating and managing text campaigns
"""

from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash
from flask_login import login_required
from datetime import datetime
from extensions import db
from crm_database import Campaign, Contact, ContactFlag, CampaignMembership, CampaignList, CSVImport
from services.campaign_service import CampaignService
from services.campaign_list_service import CampaignListService
from services.csv_import_service import CSVImportService
from services.contact_service import ContactService

campaigns_bp = Blueprint('campaigns', __name__)
campaign_service = CampaignService()
list_service = CampaignListService()
csv_service = CSVImportService(ContactService())


@campaigns_bp.route('/campaigns')
@login_required
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
@login_required
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
    
    # Get available campaign lists with stats
    campaign_lists = []
    for lst in list_service.get_all_lists():
        stats = list_service.get_list_stats(lst.id)
        # Add active members count as a property for the template
        lst.active_members_count = stats['active_members']
        campaign_lists.append(lst)
    
    return render_template('campaigns/new.html', 
                         audience_stats=audience_stats,
                         campaign_lists=campaign_lists)


@campaigns_bp.route('/campaigns', methods=['POST'])
@login_required
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
@login_required
def campaign_detail(campaign_id):
    """Show campaign details and analytics"""
    campaign = Campaign.query.get_or_404(campaign_id)
    analytics = campaign_service.get_campaign_analytics(campaign_id)
    
    # Get bounce metrics for this campaign
    from services.sms_metrics_service import SMSMetricsService
    metrics_service = SMSMetricsService()
    bounce_metrics = metrics_service.get_campaign_metrics(campaign_id)
    
    # Get recent sends for activity feed
    recent_sends = CampaignMembership.query.filter_by(
        campaign_id=campaign_id,
        status='sent'
    ).order_by(CampaignMembership.sent_at.desc()).limit(10).all()
    
    return render_template('campaigns/detail.html', 
                         campaign=campaign,
                         analytics=analytics,
                         bounce_metrics=bounce_metrics,
                         recent_sends=recent_sends)


@campaigns_bp.route('/campaigns/<int:campaign_id>/start', methods=['POST'])
@login_required
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
@login_required
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
@login_required
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
@login_required
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
@login_required
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

# Campaign List Management Routes
@campaigns_bp.route("/campaigns/lists")
@login_required
def campaign_lists():
    """Show all campaign lists"""
    lists = list_service.get_all_lists()
    
    # Get stats for each list
    list_data = []
    for lst in lists:
        stats = list_service.get_list_stats(lst.id)
        list_data.append({
            "list": lst,
            "stats": stats
        })
    
    # Get recent imports
    recent_imports = csv_service.get_import_history(limit=5)
    
    return render_template("campaigns/lists.html", 
                         lists=list_data,
                         recent_imports=recent_imports)


@campaigns_bp.route("/campaigns/lists/new", methods=["GET", "POST"])
@login_required
def new_campaign_list():
    """Create a new campaign list"""
    if request.method == "POST":
        data = request.form
        
        # Create list
        campaign_list = list_service.create_list(
            name=data["name"],
            description=data.get("description"),
            is_dynamic=data.get("is_dynamic") == "on",
            created_by="system"  # TODO: Get from session
        )
        
        # Handle different list creation methods
        if data.get("creation_method") == "csv_import":
            # Add contacts from specific CSV import
            import_id = data.get("csv_import_id")
            if import_id:
                contacts = csv_service.get_contacts_by_import(int(import_id))
                contact_ids = [c.id for c in contacts]
                list_service.add_contacts_to_list(campaign_list.id, contact_ids)
        
        elif data.get("creation_method") == "filter":
            # Build filter criteria
            criteria = {}
            
            if data.get("import_source"):
                criteria["import_source"] = data["import_source"]
            
            if data.get("no_recent_contact"):
                criteria["no_recent_contact"] = True
                criteria["days_since_contact"] = int(data.get("days_since_contact", 30))
            
            if data.get("exclude_opted_out"):
                criteria["exclude_opted_out"] = True
            
            # Save criteria and find matching contacts
            campaign_list.filter_criteria = criteria
            db.session.commit()
            
            if campaign_list.is_dynamic:
                list_service.refresh_dynamic_list(campaign_list.id)
            else:
                # Static list - add contacts now
                contacts = list_service.find_contacts_by_criteria(criteria)
                contact_ids = [c.id for c in contacts]
                list_service.add_contacts_to_list(campaign_list.id, contact_ids)
        
        flash(f"Campaign list {campaign_list.name} created successfully!", "success")
        return redirect(url_for("campaigns.campaign_lists"))
    
    # GET - show form
    csv_imports = CSVImport.query.order_by(CSVImport.imported_at.desc()).all()
    return render_template("campaigns/new_list.html", csv_imports=csv_imports)


@campaigns_bp.route("/campaigns/lists/<int:list_id>")
@login_required
def view_campaign_list(list_id):
    """View details of a campaign list"""
    campaign_list = CampaignList.query.get_or_404(list_id)
    stats = list_service.get_list_stats(list_id)
    contacts = list_service.get_list_contacts(list_id)
    
    # Get campaigns using this list
    campaigns = Campaign.query.filter_by(list_id=list_id).all()
    
    return render_template("campaigns/list_detail.html",
                         list=campaign_list,
                         stats=stats,
                         contacts=contacts[:100],  # Limit display
                         campaigns=campaigns)


@campaigns_bp.route("/campaigns/lists/<int:list_id>/refresh", methods=["POST"])
@login_required
def refresh_campaign_list(list_id):
    """Refresh a dynamic list"""
    campaign_list = CampaignList.query.get_or_404(list_id)
    
    if not campaign_list.is_dynamic:
        flash("Only dynamic lists can be refreshed", "error")
    else:
        results = list_service.refresh_dynamic_list(list_id)
        added = results["added"]
        removed = results["removed"]
        flash(f"List refreshed: {added} added, {removed} removed", "success")
    
    return redirect(url_for("campaigns.view_campaign_list", list_id=list_id))


@campaigns_bp.route("/campaigns/import-csv", methods=["GET", "POST"])
@login_required
def import_campaign_csv():
    """Import contacts from CSV and optionally create a campaign list"""
    if request.method == "POST":
        file = request.files.get("csv_file")
        if not file or not file.filename.endswith(".csv"):
            flash("Please upload a valid CSV file", "error")
            return redirect(request.url)
        
        # Import the CSV
        create_list = request.form.get("create_list") == "on"
        list_name = request.form.get("list_name")
        
        results = csv_service.import_contacts(
            file=file,
            list_name=list_name,
            create_list=create_list,
            imported_by="system"  # TODO: Get from session
        )
        
        # Show results
        if results["successful"] > 0:
            successful = results["successful"]
            new_contacts = len(results.get("contacts_created", []))
            enriched = results["duplicates"]
            
            message_parts = []
            if new_contacts > 0:
                message_parts.append(f"{new_contacts} new contacts created")
            if enriched > 0:
                message_parts.append(f"{enriched} existing contacts enriched")
            
            message = f"Successfully processed {successful} contacts"
            if message_parts:
                message += f" ({', '.join(message_parts)})"
            
            if results["list_id"]:
                message += " and added to campaign list"
            flash(message, "success")
        
        if results["failed"] > 0:
            failed = results["failed"]
            flash(f"{failed} contacts failed to import", "warning")
            if results["errors"]:
                for error in results["errors"][:3]:  # Show first 3 errors
                    flash(f"Error: {error}", "error")
        
        if results["list_id"]:
            return redirect(url_for("campaigns.view_campaign_list", list_id=results["list_id"]))
        else:
            return redirect(url_for("campaigns.campaign_lists"))
    
    return render_template("campaigns/import_csv.html")
