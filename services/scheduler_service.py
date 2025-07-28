# services/scheduler_service.py

from extensions import db
from crm_database import Appointment, Job, Quote, Setting, Property, Contact
from services.invoice_service import InvoiceService
from sms_sender import send_sms
from datetime import date, timedelta, datetime
import logging
from celery_worker import celery
from sqlalchemy.orm import joinedload

@celery.task
def send_appointment_reminders():
    """
    Celery task to send SMS reminders for appointments scheduled for the next day.
    """
    tomorrow = date.today() + timedelta(days=1)
    
    template_setting = Setting.query.filter_by(key='appointment_reminder_template').first()
    if not template_setting:
        logging.warning("Appointment reminder template not found in settings. Aborting task.")
        return
    template = template_setting.value

    appointments_to_remind = db.session.query(Appointment).filter(Appointment.date == tomorrow).all()

    if not appointments_to_remind:
        logging.info("No appointments for tomorrow requiring reminders. Task complete.")
        return
    
    for appt in appointments_to_remind:
        if appt.contact and appt.contact.phone:
            contact = appt.contact
            message = template.format(
                first_name=contact.first_name,
                appointment_date=tomorrow.strftime('%B %d, %Y'),
                appointment_time=appt.time.strftime('%I:%M %P')
            )
            try:
                send_sms(contact.phone, message)
                logging.info(f"Sent appointment reminder to {contact.first_name} for appointment {appt.id}")
            except Exception as e:
                logging.error(f"Failed to send SMS reminder for appointment {appt.id}. Error: {e}")
        else:
            logging.warning(f"Skipping reminder for appointment {appt.id}: contact or phone number missing.")


@celery.task
def send_review_requests():
    """
    Celery task to send SMS review requests for jobs completed yesterday.
    """
    yesterday = datetime.utcnow().date() - timedelta(days=1)

    template_setting = Setting.query.filter_by(key='review_request_template').first()
    if not template_setting:
        logging.warning("Review request template not found in settings. Aborting task.")
        return
    template = template_setting.value

    completed_jobs = Job.query.filter(
        Job.status == 'Completed',
        db.func.date(Job.completed_at) == yesterday
    ).all()

    if not completed_jobs:
        logging.info("No jobs completed yesterday requiring review requests. Task complete.")
        return

    for job in completed_jobs:
        if job.property and job.property.contact and job.property.contact.phone:
            contact = job.property.contact
            message = template.format(first_name=contact.first_name)
            try:
                send_sms(contact.phone, message)
                logging.info(f"Sent review request to {contact.first_name} for job {job.id}")
            except Exception as e:
                logging.error(f"Failed to send review request for job {job.id}. Error: {e}")
        else:
            logging.warning(f"Skipping review request for job {job.id}: property, contact, or phone missing.")


@celery.task
def convert_quotes_for_today_appointments():
    """
    Celery task to find appointments for the current day and convert draft quotes.
    """
    today = date.today()

    appointments_today = db.session.query(Appointment).filter(Appointment.date == today).all()

    if not appointments_today:
        logging.info("No appointments for today with draft quotes to convert. Task complete.")
        return

    for appt in appointments_today:
        if not appt.job:
            continue

        draft_quotes = Quote.query.filter_by(job_id=appt.job.id, status='Draft').all()
        
        for quote in draft_quotes:
            try:
                InvoiceService.create_invoice_from_quote(quote.id)
                logging.info(f"Successfully converted quote {quote.id} to a new invoice.")
            except Exception as e:
                logging.error(f"Failed to convert quote {quote.id} to invoice. Error: {e}")


@celery.task
def run_daily_tasks():
    """
    A single task to run all daily scheduled tasks.
    """
    logging.info("Starting daily scheduled tasks...")
    send_appointment_reminders.delay()
    send_review_requests.delay()
    convert_quotes_for_today_appointments.delay()
    logging.info("All daily tasks have been queued.")
