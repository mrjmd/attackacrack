from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from auth_utils import login_required

job_bp = Blueprint('job', __name__)

@job_bp.route('/')
@login_required
def list_all():
    job_service = current_app.services.get('job')
    jobs = job_service.get_all_jobs()
    return render_template('job_list.html', jobs=jobs)

@job_bp.route('/job/<int:job_id>')
@login_required
def view(job_id):
    job_service = current_app.services.get('job')
    job = job_service.get_job_by_id(job_id)
    return render_template('job_detail.html', job=job)

@job_bp.route('/job/add', methods=['GET', 'POST'])
@job_bp.route('/job/<int:job_id>/edit', methods=['GET', 'POST'])
@login_required
def add_edit(job_id=None):
    job_service = current_app.services.get('job')
    
    job = None
    if job_id:
        job = job_service.get_job_by_id(job_id)

    if request.method == 'POST':
        data = {
            'property_id': request.form['property_id'],
            'description': request.form['description']
        }
        if job_id:
            job_service.update_job(job_id, data)
            flash('Job updated successfully!', 'success')
        else:
            job = job_service.create_job(data)
            flash('Job created successfully!', 'success')
        return redirect(url_for('job.view', job_id=job.id))

    property_service = current_app.services.get('property')
    properties = property_service.get_all_properties()
    return render_template('add_edit_job_form.html', job=job, properties=properties)

@job_bp.route('/job/<int:job_id>/delete', methods=['POST'])
@login_required
def delete(job_id):
    job_service = current_app.services.get('job')
    job_service.delete_job(job_id)
    flash('Job deleted successfully!', 'success')
    return redirect(url_for('job.list_all'))
