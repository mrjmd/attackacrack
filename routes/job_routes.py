from flask import Blueprint, render_template, request, redirect, url_for, flash
from services.job_service import JobService
from services.property_service import PropertyService

job_bp = Blueprint('job', __name__)
job_service = JobService()
property_service = PropertyService()

@job_bp.route('/')
def list_all():
    jobs = job_service.get_all_jobs()
    return render_template('job_list.html', jobs=jobs)

@job_bp.route('/job/<int:job_id>')
def view(job_id):
    job = job_service.get_job_by_id(job_id)
    return render_template('job_detail.html', job=job)

@job_bp.route('/job/add', methods=['GET', 'POST'])
@job_bp.route('/job/<int:job_id>/edit', methods=['GET', 'POST'])
def add_edit(job_id=None):
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

    properties = property_service.get_all_properties()
    return render_template('add_edit_job_form.html', job=job, properties=properties)

@job_bp.route('/job/<int:job_id>/delete', methods=['POST'])
def delete(job_id):
    job_service.delete_job(job_id)
    flash('Job deleted successfully!', 'success')
    return redirect(url_for('job.list_all'))
