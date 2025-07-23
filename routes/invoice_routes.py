from flask import Blueprint, render_template, request, redirect, url_for
from services.invoice_service import InvoiceService
from services.job_service import JobService
from datetime import datetime

invoice_bp = Blueprint('invoice', __name__)
invoice_service = InvoiceService()
job_service = JobService()

@invoice_bp.route('/')
def list_all():
    all_invoices = invoice_service.get_all_invoices()
    return render_template('invoice_list.html', invoices=all_invoices)

@invoice_bp.route('/<int:invoice_id>')
def invoice_detail(invoice_id):
    invoice = invoice_service.get_invoice_by_id(invoice_id)
    return render_template('invoice_detail.html', invoice=invoice)

@invoice_bp.route('/add', methods=['GET', 'POST'])
def add_invoice():
    if request.method == 'POST':
        invoice_service.add_invoice(
            amount=float(request.form['amount']),
            due_date=datetime.strptime(request.form['due_date'], '%Y-%m-%d').date(),
            status=request.form['status'],
            job_id=request.form['job_id']
        )
        return redirect(url_for('invoice.list_all'))
    jobs = job_service.get_all_jobs()
    return render_template('add_edit_invoice_form.html', jobs=jobs)

@invoice_bp.route('/<int:invoice_id>/edit', methods=['GET', 'POST'])
def edit_invoice(invoice_id):
    invoice = invoice_service.get_invoice_by_id(invoice_id)
    if request.method == 'POST':
        invoice_service.update_invoice(
            invoice,
            amount=float(request.form['amount']),
            due_date=datetime.strptime(request.form['due_date'], '%Y-%m-%d').date(),
            status=request.form['status'],
            job_id=request.form['job_id']
        )
        return redirect(url_for('invoice.invoice_detail', invoice_id=invoice.id))
    jobs = job_service.get_all_jobs()
    return render_template('add_edit_invoice_form.html', invoice=invoice, jobs=jobs)

@invoice_bp.route('/<int:invoice_id>/delete', methods=['POST'])
def delete_invoice(invoice_id):
    invoice = invoice_service.get_invoice_by_id(invoice_id)
    invoice_service.delete_invoice(invoice)
    return redirect(url_for('invoice.list_all'))
