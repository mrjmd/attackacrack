# routes/property_routes.py

from flask import Blueprint, render_template, g, request, redirect, url_for, flash
from crm_manager import list_properties, get_property_by_id, add_property, update_property, delete_property
from datetime import datetime

property_bp = Blueprint('property', __name__, url_prefix='/properties')

@property_bp.route('/')
def list_all():
    filters = {
        'city': request.args.get('city'),
        'zip_code': request.args.get('zip_code'),
        'min_value': request.args.get('min_value', type=int),
        'has_foreclosure': request.args.get('has_foreclosure') == 'true'
    }
    properties = list_properties(g.session, **filters)
    return render_template('property_list.html', 
                           properties=properties,
                           current_city=filters['city'],
                           current_zip_code=filters['zip_code'],
                           current_min_value=filters['min_value'],
                           current_has_foreclosure=filters['has_foreclosure'])

@property_bp.route('/<int:property_id>')
def detail(property_id):
    prop = get_property_by_id(g.session, property_id)
    if not prop:
        flash('Property not found.', 'error')
        return redirect(url_for('property.list_all'))
    return render_template('property_detail.html', property=prop)

@property_bp.route('/add', methods=['GET', 'POST'])
def add():
    if request.method == 'POST':
        new_prop = add_property(g.session,
                                apn=request.form['apn'],
                                address=request.form['address'],
                                city=request.form['city'],
                                zip_code=request.form['zip_code'],
                                year_built=request.form.get('year_built', type=int),
                                sq_ft=request.form.get('sq_ft', type=int),
                                beds=request.form.get('beds', type=int),
                                baths=request.form.get('baths', type=float),
                                est_value=request.form.get('est_value', type=int),
                                owner_occupied=request.form.get('owner_occupied') == 'true',
                                listed_for_sale=request.form.get('listed_for_sale') == 'true',
                                foreclosure=request.form.get('foreclosure') == 'true')
        if new_prop:
            flash(f'Property "{new_prop.address}" added successfully!', 'success')
            return redirect(url_for('property.list_all'))
        else:
            flash('Error adding property. APN might already exist.', 'error')
    return render_template('add_edit_property_form.html', form_title="Add New Property")

@property_bp.route('/edit/<int:property_id>', methods=['GET', 'POST'])
def edit(property_id):
    prop = get_property_by_id(g.session, property_id)
    if not prop:
        flash('Property not found.', 'error')
        return redirect(url_for('property.list_all'))
    
    if request.method == 'POST':
        update_data = {k: v for k, v in request.form.items() if v is not None}
        # Handle checkboxes
        update_data['owner_occupied'] = 'owner_occupied' in request.form
        update_data['listed_for_sale'] = 'listed_for_sale' in request.form
        update_data['foreclosure'] = 'foreclosure' in request.form
        
        if update_property(g.session, property_id, **update_data):
            flash('Property updated successfully!', 'success')
            return redirect(url_for('property.detail', property_id=property_id))
        else:
            flash('Error updating property.', 'error')
            
    return render_template('add_edit_property_form.html', property=prop, form_title="Edit Property")

@property_bp.route('/delete/<int:property_id>', methods=['POST'])
def delete(property_id):
    prop = get_property_by_id(g.session, property_id)
    if delete_property(g.session, property_id):
        flash(f'Property "{prop.address}" deleted.', 'success')
    else:
        flash('Error deleting property.', 'error')
    return redirect(url_for('property.list_all'))
