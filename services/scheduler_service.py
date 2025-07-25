# services/scheduler_service.py

from extensions import db
from crm_database import Appointment, Job, Quote, Setting
from services.invoice_service import InvoiceService
from sms_sender import send_sms
from datetime import date, timedelta, datetime
import logging

class SchedulerService:
    def __init__(self, app):
        """
        Initializes the service with the Flask app context.
        """
        self.app = app

    def _format_message(self, template_key, **kwargs):
        """
        Helper method to format a message from a template stored in the database.
        """
        template = Setting.query.filter_by(key=template_key).first()
        if template:
            return template.value.format(**kwargs)
        return None

    def send_appointment_reminders(self):
        """
        Sends SMS reminders for appointments scheduled for the next day.
        """
        with self.app.app_context():
            tomorrow = date.today() + timedelta(days=1)
            appointments = Appointment.query.filter(Appointment.date == tomorrow).all()
            
            for appt in appointments:
                if appt.job and appt.job.property and appt.job.property.contact:
                    contact = appt.job.property.contact
                    if contact.phone:
                        message = self._format_message(
                            'appointment_reminder_template',
                            first_name=contact.first_name,
                            appointment_date=tomorrow.strftime('%B %d, %Y'),
                            appointment_time=appt.time.strftime('%I:%M %P')
                        )
                        if message:
                            try:
                                send_sms(contact.phone, message)
                                logging.info(f"Sent appointment reminder to {contact.first_name} {contact.last_name} for appointment {appt.id}")
                            except Exception as e:
                                logging.error(f"Failed to send SMS reminder for appointment {appt.id}. Error: {e}")

    def send_review_requests(self):
        """
        Sends SMS review requests for jobs completed yesterday.
        """
        with self.app.app_context():
            yesterday = datetime.utcnow() - timedelta(days=1)
            completed_jobs = Job.query.filter(
                Job.status == 'Completed',
                db.func.date(Job.completed_at) == yesterday.date()
            ).all()

            for job in completed_jobs:
                contact = job.property.contact
                if contact.phone:
                    message = self._format_message('review_request_template', first_name=contact.first_name)
                    if message:
                        try:
                            send_sms(contact.phone, message)
                            logging.info(f"Sent review request to {contact.first_name} {contact.last_name} for job {job.id}")
                        except Exception as e:
                            logging.error(f"Failed to send review request for job {job.id}. Error: {e}")

    # --- CHANGE 1 of 2: NEW METHOD ADDED ---
    # This is the new function to handle the automated conversion of quotes to invoices.
    def convert_quotes_for_today_appointments(self):
        """
        Finds all appointments for the current day and converts any associated
        'Draft' quotes into invoices. Runs within the app context.
        """
        with self.app.app_context():
            today = date.today()
            logging.info(f"Running quote-to-invoice conversion job for appointments on {today.strftime('%Y-%m-%d')}")
            
            appointments_today = Appointment.query.filter(Appointment.date == today).all()

            if not appointments_today:
                logging.info("No appointments scheduled for today. Exiting job.")
                return

            for appt in appointments_today:
                job = appt.job
                if not job:
                    continue

                draft_quotes = Quote.query.filter_by(job_id=job.id, status='Draft').all()
                
                for quote in draft_quotes:
                    try:
                        logging.info(f"Found draft quote {quote.id} for job {job.id} associated with today's appointment {appt.id}. Attempting conversion.")
                        InvoiceService.create_invoice_from_quote(quote.id)
                        logging.info(f"Successfully converted quote {quote.id} to a new invoice.")
                    except Exception as e:
                        logging.error(f"Failed to convert quote {quote.id} to invoice. Error: {e}")

    def run_daily_tasks(self):
        """
        A single method to run all daily scheduled tasks.
        """
        logging.info("Starting daily scheduled tasks...")
        self.send_appointment_reminders()
        self.send_review_requests()
        # --- CHANGE 2 of 2: ESSENTIAL ADDITION ---
        # Added a call to the new method so it runs as part of the daily tasks.
        self.convert_quotes_for_today_appointments()
        logging.info("Daily scheduled tasks completed.")
