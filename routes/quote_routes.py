from flask import Blueprint, render_template, request, redirect, url_for
from services.quote_service import QuoteService
from services.job_service import JobService

quote_bp = Blueprint('quote', __name__)
quote_service = QuoteService()
job_service = JobService()

@quote_bp.route('/')
def list_all():
    all_quotes = quote_service.get_all_quotes()
    return render_template('quote_list.html', quotes=all_quotes)

@quote_bp.route('/<int:quote_id>')
def quote_detail(quote_id):
    quote = quote_service.get_quote_by_id(quote_id)
    return render_template('quote_detail.html', quote=quote)

@quote_bp.route('/add', methods=['GET', 'POST'])
def add_quote():
    if request.method == 'POST':
        quote_service.add_quote(
            amount=float(request.form['amount']),
            status=request.form['status'],
            job_id=request.form['job_id']
        )
        return redirect(url_for('quote.list_all'))
    jobs = job_service.get_all_jobs()
    return render_template('add_edit_quote_form.html', jobs=jobs)

@quote_bp.route('/<int:quote_id>/edit', methods=['GET', 'POST'])
def edit_quote(quote_id):
    quote = quote_service.get_quote_by_id(quote_id)
    if request.method == 'POST':
        quote_service.update_quote(
            quote,
            amount=float(request.form['amount']),
            status=request.form['status'],
            job_id=request.form['job_id']
        )
        return redirect(url_for('quote.quote_detail', quote_id=quote.id))
    jobs = job_service.get_all_jobs()
    return render_template('add_edit_quote_form.html', quote=quote, jobs=jobs)

@quote_bp.route('/<int:quote_id>/delete', methods=['POST'])
def delete_quote(quote_id):
    quote = quote_service.get_quote_by_id(quote_id)
    quote_service.delete_quote(quote)
    return redirect(url_for('quote.list_all'))
