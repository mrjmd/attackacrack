from flask import Blueprint, render_template, request, redirect, url_for
from services.property_service import PropertyService
from services.contact_service import ContactService

property_bp = Blueprint('property', __name__)
property_service = PropertyService()
contact_service = ContactService()

@property_bp.route('/')
def list_all():
    all_properties = property_service.get_all_properties()
    return render_template('property_list.html', properties=all_properties)

@property_bp.route('/<int:property_id>')
def property_detail(property_id):
    prop = property_service.get_property_by_id(property_id)
    return render_template('property_detail.html', property=prop)

@property_bp.route('/add', methods=['GET', 'POST'])
def add_property():
    if request.method == 'POST':
        property_service.add_property(
            address=request.form['address'],
            contact_id=request.form['contact_id']
        )
        return redirect(url_for('property.list_all'))
    contacts = contact_service.get_all_contacts()
    return render_template('add_edit_property_form.html', contacts=contacts)

@property_bp.route('/<int:property_id>/edit', methods=['GET', 'POST'])
def edit_property(property_id):
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
def delete_property(property_id):
    prop = property_service.get_property_by_id(property_id)
    property_service.delete_property(prop)
    return redirect(url_for('property.list_all'))
