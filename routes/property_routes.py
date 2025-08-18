from flask import Blueprint, render_template, request, redirect, url_for, current_app
from flask_login import login_required
from crm_database import Property
from extensions import db

property_bp = Blueprint('property', __name__)

@property_bp.route('/')
@login_required
def list_all():
    # Get pagination parameters
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 100, type=int)
    search = request.args.get('search', '').strip()
    
    # Get paginated properties
    query = Property.query
    if search:
        query = query.filter(
            db.or_(
                Property.address.ilike(f'%{search}%'),
                Property.property_type.ilike(f'%{search}%')
            )
        )
    
    properties_paginated = query.order_by(Property.address).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    return render_template('property_list.html', 
                         properties=properties_paginated.items,
                         pagination=properties_paginated,
                         search=search)

@property_bp.route('/<int:property_id>')
@login_required
def property_detail(property_id):
    property_service = current_app.services.get('property')
    prop = property_service.get_property_by_id(property_id)
    return render_template('property_detail.html', property=prop)

@property_bp.route('/add', methods=['GET', 'POST'])
@login_required
def add_property():
    property_service = current_app.services.get('property')
    contact_service = current_app.services.get('contact')
    
    if request.method == 'POST':
        property_service.add_property(
            address=request.form['address'],
            contact_id=request.form['contact_id']
        )
        return redirect(url_for('property.list_all'))
    contacts = contact_service.get_all_contacts()
    return render_template('add_edit_property_form.html', contacts=contacts)

@property_bp.route('/<int:property_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_property(property_id):
    property_service = current_app.services.get('property')
    contact_service = current_app.services.get('contact')
    
    prop = property_service.get_property_by_id(property_id)
    if request.method == 'POST':
        property_service.update_property(
            prop,
            address=request.form['address'],
            contact_id=request.form['contact_id']
        )
        return redirect(url_for('property.property_detail', property_id=prop.id))
    contacts = contact_service.get_all_contacts()
    return render_template('add_edit_property_form.html', property=prop, contacts=contacts)

@property_bp.route('/<int:property_id>/delete', methods=['POST'])
@login_required
def delete_property(property_id):
    property_service = current_app.services.get('property')
    
    prop = property_service.get_property_by_id(property_id)
    property_service.delete_property(prop)
    return redirect(url_for('property.list_all'))
