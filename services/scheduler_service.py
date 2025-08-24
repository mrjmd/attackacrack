# services/scheduler_service.py

from datetime import date, timedelta, datetime
from utils.datetime_utils import utc_now
import logging
from celery_worker import celery
from flask import current_app
from repositories.setting_repository import SettingRepository
from repositories.job_repository import JobRepository
from repositories.quote_repository import QuoteRepository
from repositories.appointment_repository import AppointmentRepository

logger = logging.getLogger(__name__)


class SchedulerService:
    """Service for managing scheduled tasks using repository pattern"""
    
    def __init__(self, setting_repository: SettingRepository,
                 job_repository: JobRepository,
                 quote_repository: QuoteRepository,
                 appointment_repository: AppointmentRepository,
                 openphone_service,
                 invoice_service):
        """Initialize SchedulerService with repository dependencies"""
        self.setting_repository = setting_repository
        self.job_repository = job_repository
        self.quote_repository = quote_repository
        self.appointment_repository = appointment_repository
        self.openphone_service = openphone_service
        self.invoice_service = invoice_service
    
    def send_appointment_reminders(self):
        """Send SMS reminders for appointments scheduled for the next day"""
        tomorrow = date.today() + timedelta(days=1)
        
        # Get template from repository
        template_setting = self.setting_repository.find_one_by(key='appointment_reminder_template')
        if not template_setting:
            logger.warning("Appointment reminder template not found in settings. Aborting task.")
            return
        template = template_setting.value

        # Get appointments for tomorrow
        appointments_to_remind = self.appointment_repository.find_by_date(tomorrow)

        if not appointments_to_remind:
            logger.info("No appointments for tomorrow requiring reminders. Task complete.")
            return
        
        for appt in appointments_to_remind:
            if appt.contact and appt.contact.phone:
                contact = appt.contact
                message = template.format(
                    first_name=contact.first_name,
                    appointment_date=tomorrow.strftime('%B %d, %Y'),
                    appointment_time=appt.time.strftime('%I:%M %p').lower()
                )
                try:
                    result = self.openphone_service.send_message(contact.phone, message)
                    if result.get('success'):
                        logger.info(f"Sent appointment reminder to {contact.first_name} for appointment {appt.id}")
                    else:
                        logger.error(f"Failed to send SMS reminder for appointment {appt.id}. Error: {result.get('error')}")
                except Exception as e:
                    logger.error(f"Failed to send SMS reminder for appointment {appt.id}. Error: {e}")
            else:
                logger.warning(f"Skipping reminder for appointment {appt.id}: contact or phone number missing.")
    
    def send_review_requests(self):
        """Send SMS review requests for jobs completed yesterday"""
        yesterday = utc_now().date() - timedelta(days=1)

        # Get template from repository
        template_setting = self.setting_repository.find_one_by(key='review_request_template')
        if not template_setting:
            logger.warning("Review request template not found in settings. Aborting task.")
            return
        template = template_setting.value

        # Get completed jobs from yesterday
        completed_jobs = self.job_repository.find_completed_jobs_by_date(yesterday)

        if not completed_jobs:
            logger.info("No jobs completed yesterday requiring review requests. Task complete.")
            return

        for job in completed_jobs:
            if job.property and job.property.contact and job.property.contact.phone:
                contact = job.property.contact
                message = template.format(first_name=contact.first_name)
                try:
                    result = self.openphone_service.send_message(contact.phone, message)
                    if result.get('success'):
                        logger.info(f"Sent review request to {contact.first_name} for job {job.id}")
                    else:
                        logger.error(f"Failed to send review request for job {job.id}. Error: {result.get('error')}")
                except Exception as e:
                    logger.error(f"Failed to send review request for job {job.id}. Error: {e}")
            else:
                logger.warning(f"Skipping review request for job {job.id}: property, contact, or phone missing.")
    
    def convert_quotes_for_today_appointments(self):
        """Find appointments for the current day and convert draft quotes"""
        today = date.today()

        # Get appointments for today
        appointments_today = self.appointment_repository.find_by_date(today)

        if not appointments_today:
            logger.info("No appointments for today with draft quotes to convert. Task complete.")
            return

        for appt in appointments_today:
            if not appt.job:
                continue

            # Get draft quotes for the appointment's job
            draft_quotes = self.quote_repository.find_draft_quotes_by_job_id(appt.job.id)
            
            for quote in draft_quotes:
                try:
                    self.invoice_service.create_invoice_from_quote(quote.id)
                    logger.info(f"Successfully converted quote {quote.id} to a new invoice.")
                except Exception as e:
                    logger.error(f"Failed to convert quote {quote.id} to invoice. Error: {e}")
    
    def run_daily_tasks(self):
        """Run all daily scheduled tasks"""
        logger.info("Starting daily scheduled tasks...")
        self.send_appointment_reminders()
        self.send_review_requests()
        self.convert_quotes_for_today_appointments()
        logger.info("All daily tasks completed.")

# Celery task wrappers that use the service with dependency injection

@celery.task
def send_appointment_reminders():
    """
    Celery task to send SMS reminders for appointments scheduled for the next day.
    """
    with current_app.app_context():
        scheduler_service = current_app.services.get('scheduler')
        scheduler_service.send_appointment_reminders()


@celery.task
def send_review_requests():
    """
    Celery task to send SMS review requests for jobs completed yesterday.
    """
    with current_app.app_context():
        scheduler_service = current_app.services.get('scheduler')
        scheduler_service.send_review_requests()


@celery.task
def convert_quotes_for_today_appointments():
    """
    Celery task to find appointments for the current day and convert draft quotes.
    """
    with current_app.app_context():
        scheduler_service = current_app.services.get('scheduler')
        scheduler_service.convert_quotes_for_today_appointments()


@celery.task
def run_daily_tasks():
    """
    A single task to run all daily scheduled tasks.
    """
    with current_app.app_context():
        scheduler_service = current_app.services.get('scheduler')
        scheduler_service.run_daily_tasks()
