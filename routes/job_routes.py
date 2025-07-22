# routes/job_routes.py

from flask import Blueprint, render_template, g, request, redirect, url_for, flash
from crm_manager import list_jobs, get_job_by_id, add_job, update_job, delete_job
from crm_database import Contact, Property
from datetime import datetime

job_bp = Blueprint('job', __name__, url_prefix='/jobs')

def get_job_statuses():
    return ['All', 'pending', 'in_progress', 'completed', 'on_hold', 'cancelled']

@job_bp.route('/')
def list_all():
    jobs = list_jobs(g.session, 
                     job_status=request.args.get('job_status'),
                     search_name=request.args.get('search_name'))
    return render_template('job_list.html', 
                           jobs=jobs, 
                           job_statuses=get_job_statuses(),
                           current_job_status=request.args.get('job_status'),
                           current_search_name=request.args.get('search_name', ''))

@job_bp.route('/<int:job_id>')
def detail(job_id):
    job = get_job_by_id(g.session, job_id)
    if not job:
        flash('Job not found.', 'error')
        return redirect(url_for('job.list_all'))
    return render_template('job_detail.html', job=job)

@job_bp.route('/add', methods=['GET', 'POST'])
def add():
    contacts = g.session.query(Contact).order_by(Contact.first_name).all()
    properties = g.session.query(Property).order_by(Property.address).all()
    if request.method == 'POST':
        start_date = datetime.strptime(request.form['start_date'], '%Y-%m-%d') if request.form.get('start_date') else None
        new_job = add_job(g.session,
                          job_name=request.form['job_name'],
                          description=request.form.get('description'),
                          property_id=request.form.get('property_id', type=int),
                          contact_id=request.form.get('contact_id', type=int),
                          total_amount=request.form.get('total_amount', type=float),
                          job_status=request.form.get('job_status', 'pending'),
                          start_date=start_date)
        if new_job:
            flash('Job added successfully!', 'success')
            return redirect(url_for('job.list_all'))
        else:
            flash('Error adding job.', 'error')
            
    return render_template('add_edit_job_form.html', form_title="Add New Job", contacts=contacts, properties=properties, job_statuses=get_job_statuses())

@job_bp.route('/edit/<int:job_id>', methods=['GET', 'POST'])
def edit(job_id):
    job = get_job_by_id(g.session, job_id)
    if not job:
        flash('Job not found.', 'error')
        return redirect(url_for('job.list_all'))
    
    if request.method == 'POST':
        update_data = request.form.to_dict()
        for date_field in ['start_date', 'end_date']:
            if update_data.get(date_field):
                update_data[date_field] = datetime.strptime(update_data[date_field], '%Y-%m-%d')
            else:
                update_data[date_field] = None
        
        if update_job(g.session, job_id, **update_data):
            flash('Job updated successfully!', 'success')
            return redirect(url_for('job.detail', job_id=job_id))
        else:
            flash('Error updating job.', 'error')

    contacts = g.session.query(Contact).order_by(Contact.first_name).all()
    properties = g.session.query(Property).order_by(Property.address).all()
    return render_template('add_edit_job_form.html', job=job, form_title="Edit Job", contacts=contacts, properties=properties, job_statuses=get_job_statuses())

@job_bp.route('/delete/<int:job_id>', methods=['POST'])
def delete(job_id):
    job = get_job_by_id(g.session, job_id)
    if delete_job(g.session, job_id):
        flash(f'Job "{job.job_name}" deleted.', 'success')
    else:
        flash('Error deleting job.', 'error')
    return redirect(url_for('job.list_all'))
