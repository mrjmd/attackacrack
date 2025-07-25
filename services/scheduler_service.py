from datetime import datetime, timedelta
from extensions import db
from crm_database import Appointment, Setting, Job
from services.openphone_service import OpenPhoneService
from flask import current_app

class SchedulerService:
    def __init__(self):
        self.session = db.session
        self.openphone_service = OpenPhoneService()

    def _format_message(self, template, appointment=None, job=None):
        """
        Replaces placeholders in the template with actual data.
        """
        placeholders = {}
        contact = None
        if appointment:
            contact = appointment.contact
            placeholders = {
                '[appointment_date]': appointment.date.strftime('%A, %B %d'),
                '[appointment_time]': appointment.time.strftime('%I:%M %p'),
                '[property_address]': contact.properties[0].address if contact.properties else 'the property'
            }
        elif job:
            contact = job.property.contact
        
        if contact:
            placeholders['[contact_first_name]'] = contact.first_name
            placeholders['[contact_last_name]'] = contact.last_name

        message = template
        for key, value in placeholders.items():
            message = message.replace(key, value)
        return message

    def send_appointment_reminders(self):
        """
        Finds all appointments for the next day and sends an SMS reminder.
        """
        print("--- Running daily appointment reminder task ---")
        
        reminder_template_setting = self.session.query(Setting).filter_by(key='appointment_reminder_template').first()
        if not reminder_template_setting:
            print("-> No reminder template found in settings. Aborting.")
            return

        template = reminder_template_setting.value
        
        tomorrow = datetime.utcnow().date() + timedelta(days=1)
        appointments_tomorrow = self.session.query(Appointment).filter(Appointment.date == tomorrow).all()
        
        if not appointments_tomorrow:
            print("-> No appointments scheduled for tomorrow. Task complete.")
            return
        
        print(f"-> Found {len(appointments_tomorrow)} appointments for tomorrow. Sending reminders...")
        
        from_number_id = current_app.config.get('OPENPHONE_PHONE_NUMBER_ID')
        if not from_number_id:
            print("-> ERROR: OPENPHONE_PHONE_NUMBER_ID not set. Cannot send SMS.")
            return

        for appt in appointments_tomorrow:
            message_body = self._format_message(template, appointment=appt)
            print(f"  - Sending reminder to {appt.contact.phone} for appointment {appt.id}")
            self.openphone_service.send_sms(
                to_number=appt.contact.phone,
                from_number_id=from_number_id,
                body=message_body
            )
        
        print("--- Reminder task finished ---")

    def send_review_requests(self):
        """
        Finds jobs completed recently and sends an SMS requesting a review.
        """
        print("--- Running daily review request task ---")
        
        review_template_setting = self.session.query(Setting).filter_by(key='review_request_template').first()
        if not review_template_setting:
            print("-> No review request template found in settings. Aborting.")
            return

        template = review_template_setting.value
        
        one_day_ago = datetime.utcnow() - timedelta(days=1)
        two_days_ago = datetime.utcnow() - timedelta(days=2)
        
        recent_jobs = self.session.query(Job).filter(
            Job.status == 'Complete',
            Job.completed_at.between(two_days_ago, one_day_ago)
        ).all()

        if not recent_jobs:
            print("-> No recently completed jobs found. Task complete.")
            return
        
        print(f"-> Found {len(recent_jobs)} recently completed jobs. Sending review requests...")
        
        from_number_id = current_app.config.get('OPENPHONE_PHONE_NUMBER_ID')
        if not from_number_id:
            print("-> ERROR: OPENPHONE_PHONE_NUMBER_ID not set. Cannot send SMS.")
            return

        for job in recent_jobs:
            message_body = self._format_message(template, job=job)
            
            print(f"  - Sending review request to {job.property.contact.phone} for job {job.id}")
            self.openphone_service.send_sms(
                to_number=job.property.contact.phone,
                from_number_id=from_number_id,
                body=message_body
            )
        
        print("--- Review request task finished ---")
