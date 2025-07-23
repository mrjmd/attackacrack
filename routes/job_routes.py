from flask import Blueprint, render_template, request, redirect, url_for
from services.job_service import JobService
from services.property_service import PropertyService

job_bp = Blueprint('job', __name__)
job_service = JobService()
property_service = PropertyService()

@job_bp.route('/')
def list_all():
    all_jobs = job_service.get_all_jobs()
    return render_template('job_list.html', jobs=all_jobs)

@job_bp.route('/<int:job_id>')
def job_detail(job_id):
    job = job_service.get_job_by_id(job_id)
    return render_template('job_detail.html', job=job)

@job_bp.route('/add', methods=['GET', 'POST'])
def add_job():
    if request.method == 'POST':
        job_service.add_job(
            description=request.form['description'],
            property_id=request.form['property_id']
        )
        return redirect(url_for('job.list_all'))
    properties = property_service.get_all_properties()
    return render_template('add_edit_job_form.html', properties=properties)

@job_bp.route('/<int:job_id>/edit', methods=['GET', 'POST'])
def edit_job(job_id):
    job = job_service.get_job_by_id(job_id)
    if request.method == 'POST':
        job_service.update_job(
            job,
            description=request.form['description'],
            property_id=request.form['property_id']
        )
        return redirect(url_for('job.job_detail', job_id=job.id))
    properties = property_service.get_all_properties()
    return render_template('add_edit_job_form.html', job=job, properties=properties)

@job_bp.route('/<int:job_id>/delete', methods=['POST'])
def delete_job(job_id):
    job = job_service.get_job_by_id(job_id)
    job_service.delete_job(job)
    return redirect(url_for('job.list_all'))
