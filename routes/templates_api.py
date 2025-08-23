"""Template API endpoints.

Provides RESTful API for managing campaign templates.
Follows existing API patterns from api_routes.py.
"""

from flask import Blueprint, jsonify, request, current_app
from flask_login import login_required, current_user
from services.enums import TemplateCategory, TemplateStatus
from services.campaign_template_service import (
    TemplateValidationError,
    TemplateNotFoundError,
    TemplateDuplicateError
)

templates_api_bp = Blueprint('templates_api', __name__, url_prefix='/api/templates')


@templates_api_bp.route('', methods=['POST'])
@login_required
def create_template():
    """Create a new campaign template.
    
    Expected JSON payload:
    {
        "name": "Template Name",
        "content": "Template content with {variables}",
        "category": "promotional|follow_up|reminder|notification|custom",
        "description": "Optional description",
        "variables": ["optional", "list", "of", "variables"]
    }
    
    Returns:
        201: Template created successfully with template data
        400: Validation error or bad request
        500: Internal server error
    """
    try:
        template_service = current_app.services.get('campaign_template')
        if not template_service:
            return jsonify({'error': 'Template service not available'}), 500
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Validate required fields
        if not data.get('name'):
            return jsonify({'error': 'Name is required'}), 400
        if not data.get('content'):
            return jsonify({'error': 'Content is required'}), 400
        if not data.get('category'):
            return jsonify({'error': 'Category is required'}), 400
        
        # Convert category string to enum
        try:
            category = TemplateCategory[data['category'].upper()]
        except KeyError:
            return jsonify({'error': f"Invalid category: {data['category']}"}), 400
        
        # Create template
        template = template_service.create_template(
            name=data['name'],
            content=data['content'],
            category=category,
            description=data.get('description'),
            variables=data.get('variables')
        )
        
        # Template is already a dictionary from the service
        # Ensure category and status are lowercase strings for API response
        if isinstance(template['category'], str):
            template['category'] = template['category'].lower()
        if isinstance(template['status'], str):
            template['status'] = template['status'].lower()
        
        return jsonify(template), 201
        
    except TemplateValidationError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        current_app.logger.error(f"Error creating template: {e}", exc_info=True)
        return jsonify({'error': 'Internal server error'}), 500


@templates_api_bp.route('', methods=['GET'])
@login_required
def list_templates():
    """List campaign templates with optional filtering.
    
    Query parameters:
    - page: Page number (default: 1)
    - per_page: Items per page (default: 20)
    - category: Filter by category (promotional|follow_up|reminder|notification|custom)
    - status: Filter by status (draft|approved|active|archived)
    - search: Search in name and content
    
    Returns:
        200: List of templates with pagination metadata
        500: Internal server error
    """
    try:
        template_service = current_app.services.get('campaign_template')
        if not template_service:
            return jsonify({'error': 'Template service not available'}), 500
        
        # Get query parameters
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        category_str = request.args.get('category')
        status_str = request.args.get('status')
        search = request.args.get('search')
        
        # Convert category string to enum if provided
        category = None
        if category_str:
            try:
                category = TemplateCategory[category_str.upper()]
            except KeyError:
                return jsonify({'error': f"Invalid category: {category_str}"}), 400
        
        # Convert status string to enum if provided
        status = None
        if status_str:
            try:
                status = TemplateStatus[status_str.upper()]
            except KeyError:
                return jsonify({'error': f"Invalid status: {status_str}"}), 400
        
        # Get templates
        if search:
            # Use search method if search term provided
            templates = template_service.search_templates(search)
            # Manual pagination for search results
            total = len(templates)
            start = (page - 1) * per_page
            end = start + per_page
            templates_page = templates[start:end]
            
            # Ensure category and status are lowercase
            for item in templates_page:
                if isinstance(item.get('category'), str):
                    item['category'] = item['category'].lower()
                if isinstance(item.get('status'), str):
                    item['status'] = item['status'].lower()
            
            items = templates_page
            
            return jsonify({
                'items': items,
                'total': total,
                'page': page,
                'per_page': per_page,
                'total_pages': (total + per_page - 1) // per_page
            }), 200
        else:
            # Use list_templates with pagination
            result = template_service.list_templates(
                category=category,
                status=status,
                page=page,
                per_page=per_page
            )
            
            # Result is already a dictionary with the correct structure
            # Calculate total_pages
            total_pages = (result['total'] + per_page - 1) // per_page if result['total'] > 0 else 0
            
            # Ensure category and status are lowercase in items
            for item in result['items']:
                if isinstance(item.get('category'), str):
                    item['category'] = item['category'].lower()
                if isinstance(item.get('status'), str):
                    item['status'] = item['status'].lower()
            
            return jsonify({
                'items': result['items'],
                'total': result['total'],
                'page': result['page'],
                'per_page': result['per_page'],
                'total_pages': total_pages
            }), 200
            
    except Exception as e:
        current_app.logger.error(f"Error listing templates: {e}", exc_info=True)
        return jsonify({'error': 'Internal server error'}), 500


@templates_api_bp.route('/<int:template_id>/preview', methods=['POST'])
@login_required
def preview_template(template_id):
    """Preview a template with optional contact substitution.
    
    Expected JSON payload:
    {
        "contact_id": 123,  # Optional contact ID for variable substitution
        "custom_values": {  # Optional custom values for variables
            "first_name": "John",
            "property_address": "123 Main St"
        }
    }
    
    Returns:
        200: Preview data with substituted content
        404: Template not found
        500: Internal server error
    """
    try:
        template_service = current_app.services.get('campaign_template')
        if not template_service:
            return jsonify({'error': 'Template service not available'}), 500
        
        data = request.get_json() or {}
        contact_id = data.get('contact_id')
        custom_data = data.get('custom_values', {})  # Map API field to service parameter
        
        # Get preview
        preview_data = template_service.preview_template(
            template_id=template_id,
            contact_id=contact_id,
            custom_data=custom_data
        )
        
        # Return preview data
        return jsonify({
            'template_id': template_id,
            'contact_id': contact_id,
            'preview': preview_data['preview'],
            'variables_used': preview_data.get('variables_used', []),
            'missing_variables': preview_data.get('missing_variables', [])
        }), 200
        
    except TemplateNotFoundError as e:
        return jsonify({'error': str(e)}), 404
    except Exception as e:
        current_app.logger.error(f"Error previewing template: {e}", exc_info=True)
        return jsonify({'error': 'Internal server error'}), 500


@templates_api_bp.route('/<int:template_id>/approve', methods=['POST'])
@login_required
def approve_template(template_id):
    """Approve a template for use.
    
    Returns:
        200: Template approved successfully
        404: Template not found
        400: Template cannot be approved (already approved/active)
        500: Internal server error
    """
    try:
        template_service = current_app.services.get('campaign_template')
        if not template_service:
            return jsonify({'error': 'Template service not available'}), 500
        
        # Approve template (use current user's ID or email as approver)
        approved_by = str(current_user.id) if hasattr(current_user, 'id') else 'admin'
        
        template = template_service.approve_template(
            template_id=template_id,
            approved_by=approved_by
        )
        
        # Template is already a dictionary from the service
        if isinstance(template.get('status'), str):
            template['status'] = template['status'].lower()
        
        return jsonify(template), 200
        
    except TemplateNotFoundError as e:
        return jsonify({'error': str(e)}), 404
    except (TemplateValidationError, TemplateDuplicateError) as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        current_app.logger.error(f"Error approving template: {e}", exc_info=True)
        return jsonify({'error': 'Internal server error'}), 500


@templates_api_bp.route('/<int:template_id>/clone', methods=['POST'])
@login_required
def clone_template(template_id):
    """Clone an existing template.
    
    Expected JSON payload:
    {
        "name": "New Template Name"  # Required: Name for the cloned template
    }
    
    Returns:
        201: Template cloned successfully
        404: Template not found
        400: Bad request (missing name)
        500: Internal server error
    """
    try:
        template_service = current_app.services.get('campaign_template')
        if not template_service:
            return jsonify({'error': 'Template service not available'}), 500
        
        data = request.get_json() or {}
        new_name = data.get('name')
        
        if not new_name:
            return jsonify({'error': 'Name is required for cloned template'}), 400
        
        # Clone template
        cloned = template_service.clone_template(
            template_id=template_id,
            new_name=new_name
        )
        
        # Template is already a dictionary from the service
        if isinstance(cloned.get('category'), str):
            cloned['category'] = cloned['category'].lower()
        if isinstance(cloned.get('status'), str):
            cloned['status'] = cloned['status'].lower()
        
        return jsonify(cloned), 201
        
    except TemplateNotFoundError as e:
        return jsonify({'error': str(e)}), 404
    except TemplateValidationError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        current_app.logger.error(f"Error cloning template: {e}", exc_info=True)
        return jsonify({'error': 'Internal server error'}), 500


@templates_api_bp.route('/<int:template_id>', methods=['GET'])
@login_required
def get_template(template_id):
    """Get a specific template by ID.
    
    Returns:
        200: Template data
        404: Template not found
        500: Internal server error
    """
    try:
        template_service = current_app.services.get('campaign_template')
        if not template_service:
            return jsonify({'error': 'Template service not available'}), 500
        
        template = template_service.get_template(template_id)
        
        if not template:
            return jsonify({'error': 'Template not found'}), 404
        
        # Template is already a dictionary from the service
        if isinstance(template.get('category'), str):
            template['category'] = template['category'].lower()
        if isinstance(template.get('status'), str):
            template['status'] = template['status'].lower()
        
        return jsonify(template), 200
        
    except TemplateNotFoundError as e:
        return jsonify({'error': str(e)}), 404
    except Exception as e:
        current_app.logger.error(f"Error getting template: {e}", exc_info=True)
        return jsonify({'error': 'Internal server error'}), 500


@templates_api_bp.route('/<int:template_id>', methods=['PUT'])
@login_required
def update_template(template_id):
    """Update an existing template.
    
    Expected JSON payload:
    {
        "name": "Updated Name",
        "content": "Updated content",
        "description": "Updated description",
        "create_version": false  # Optional: Create new version instead of updating
    }
    
    Returns:
        200: Template updated successfully
        404: Template not found
        400: Validation error
        500: Internal server error
    """
    try:
        template_service = current_app.services.get('campaign_template')
        if not template_service:
            return jsonify({'error': 'Template service not available'}), 500
        
        data = request.get_json() or {}
        
        # Update template
        template = template_service.update_template(
            template_id=template_id,
            name=data.get('name'),
            content=data.get('content'),
            description=data.get('description'),
            create_version=data.get('create_version', False)
        )
        
        # Template is already a dictionary from the service
        if isinstance(template.get('category'), str):
            template['category'] = template['category'].lower()
        if isinstance(template.get('status'), str):
            template['status'] = template['status'].lower()
        
        return jsonify(template), 200
        
    except TemplateNotFoundError as e:
        return jsonify({'error': str(e)}), 404
    except TemplateValidationError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        current_app.logger.error(f"Error updating template: {e}", exc_info=True)
        return jsonify({'error': 'Internal server error'}), 500


@templates_api_bp.route('/<int:template_id>', methods=['DELETE'])
@login_required
def delete_template(template_id):
    """Soft delete a template.
    
    Returns:
        200: Template deleted successfully
        404: Template not found
        500: Internal server error
    """
    try:
        template_service = current_app.services.get('campaign_template')
        if not template_service:
            return jsonify({'error': 'Template service not available'}), 500
        
        template_service.soft_delete_template(template_id)
        
        return jsonify({'message': 'Template deleted successfully'}), 200
        
    except TemplateNotFoundError as e:
        return jsonify({'error': str(e)}), 404
    except Exception as e:
        current_app.logger.error(f"Error deleting template: {e}", exc_info=True)
        return jsonify({'error': 'Internal server error'}), 500


@templates_api_bp.route('/<int:template_id>/activate', methods=['POST'])
@login_required
def activate_template(template_id):
    """Activate an approved template.
    
    Returns:
        200: Template activated successfully
        404: Template not found
        400: Template cannot be activated (not approved)
        500: Internal server error
    """
    try:
        template_service = current_app.services.get('campaign_template')
        if not template_service:
            return jsonify({'error': 'Template service not available'}), 500
        
        template = template_service.activate_template(template_id)
        
        # Template is already a dictionary from the service
        if isinstance(template.get('status'), str):
            template['status'] = template['status'].lower()
        
        return jsonify(template), 200
        
    except TemplateNotFoundError as e:
        return jsonify({'error': str(e)}), 404
    except (TemplateValidationError, TemplateDuplicateError) as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        current_app.logger.error(f"Error activating template: {e}", exc_info=True)
        return jsonify({'error': 'Internal server error'}), 500


@templates_api_bp.route('/<int:template_id>/versions', methods=['GET'])
@login_required
def get_template_versions(template_id):
    """Get all versions of a template.
    
    Returns:
        200: List of template versions
        404: Template not found
        500: Internal server error
    """
    try:
        template_service = current_app.services.get('campaign_template')
        if not template_service:
            return jsonify({'error': 'Template service not available'}), 500
        
        versions = template_service.get_template_versions(template_id)
        
        # Versions are already dictionaries from the service
        for v in versions:
            if isinstance(v.get('status'), str):
                v['status'] = v['status'].lower()
        
        return jsonify({
            'template_id': template_id,
            'versions': versions,
            'total': len(versions)
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Error getting template versions: {e}", exc_info=True)
        return jsonify({'error': 'Internal server error'}), 500


@templates_api_bp.route('/<int:template_id>/statistics', methods=['GET'])
@login_required  
def get_template_statistics(template_id):
    """Get usage statistics for a template.
    
    Returns:
        200: Template statistics
        404: Template not found
        500: Internal server error
    """
    try:
        template_service = current_app.services.get('campaign_template')
        if not template_service:
            return jsonify({'error': 'Template service not available'}), 500
        
        stats = template_service.get_template_statistics(template_id)
        
        return jsonify(stats), 200
        
    except TemplateNotFoundError as e:
        return jsonify({'error': str(e)}), 404
    except Exception as e:
        current_app.logger.error(f"Error getting template statistics: {e}", exc_info=True)
        return jsonify({'error': 'Internal server error'}), 500
