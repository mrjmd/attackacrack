# tests/test_scheduler_service.py
import pytest
from services.scheduler_service import SchedulerService
from crm_database import Appointment, Contact, Job, Property, Quote, Setting, db
from services.invoice_service import InvoiceService
from sms_sender import send_sms
from datetime import date, time, timedelta, datetime
import logging
from unittest.mock import patch, MagicMock

# Fixture to provide a SchedulerService instance
@pytest.fixture
def scheduler_service(app):
    """Provides a SchedulerService instance within an app context."""
    return SchedulerService(app)

# Fixture to set up common mocks for external services
@pytest.fixture(autouse=True)
def common_mocks(mocker):
    """Mocks external dependencies like sms_sender.send_sms and InvoiceService.create_invoice_from_quote."""
    # Patch send_sms where it's imported in scheduler_service
    mocker.patch('services.scheduler_service.send_sms', return_value=True) 
    mocker.patch('services.invoice_service.InvoiceService.create_invoice_from_quote', return_value=MagicMock()) 

# Fixture to suppress logging for cleaner test output
@pytest.fixture(autouse=True)
def suppress_logging(caplog):
    # Set default logging level for the root logger to CRITICAL to suppress most output
    logging.getLogger().setLevel(logging.CRITICAL) 
    yield
    logging.getLogger().setLevel(logging.NOTSET) # Re-enable logging after test
    caplog.clear() # Clear records after each test

# --- Tests for _format_message ---

def test_format_message_template_found(app, db_session, scheduler_service):
    """Test _format_message when the template exists."""
    with app.app_context():
        # Template 'test_template' is not seeded by conftest, so it needs to be added here
        template = Setting.query.filter_by(key='test_template').first()
        if not template: 
            template = Setting(key='test_template', value='Hello {name}, your date is {event_date}.')
            db_session.add(template)
            db_session.commit()

        message = scheduler_service._format_message(
            'test_template',
            name='Alice',
            event_date='tomorrow'
        )
        assert message == 'Hello Alice, your date is tomorrow.'

def test_format_message_template_not_found(app, db_session, scheduler_service):
    """Test _format_message when the template does not exist."""
    with app.app_context():
        # Ensure template does not exist (it won't if not seeded by conftest or this test)
        assert Setting.query.filter_by(key='non_existent_template').first() is None
        
        message = scheduler_service._format_message(
            'non_existent_template',
            name='Bob'
        )
        assert message is None

# --- Tests for send_appointment_reminders ---

def test_send_appointment_reminders_success(app, db_session, scheduler_service, mocker, caplog):
    """Test successful sending of appointment reminders."""
    mock_send_sms = mocker.patch('services.scheduler_service.send_sms', return_value=True) # Patch where it's imported
    
    with app.app_context():
        # Template is now seeded in conftest.py, so just query it
        reminder_template = Setting.query.filter_by(key='appointment_reminder_template').first()
        assert reminder_template is not None

        # Seed data for an appointment tomorrow
        contact = Contact(first_name='Reminder', last_name='Contact', phone='+11234567890', email='reminder@example.com')
        db_session.add(contact)
        db_session.commit()

        prop = Property(address='456 Reminder Ln', contact=contact)
        db_session.add(prop)
        db_session.commit()

        job = Job(description='Reminder Job', property=prop, status='Active')
        db_session.add(job)
        db_session.commit()

        tomorrow = date.today() + timedelta(days=1)
        appointment_time = time(9, 0)
        # Corrected: Pass job_id, as Appointment model now has job_id
        appointment = Appointment(title='Tomorrow Appt', date=tomorrow, time=appointment_time, contact=contact, job_id=job.id)
        db_session.add(appointment)
        db_session.commit()

        # Execute the method
        with patch('datetime.date') as mock_date:
            mock_date.today.return_value = date.today()
            mock_date.side_effect = lambda *args, **kw: date(*args, **kw) # Allow normal date creation
            with caplog.at_level(logging.INFO): # Temporarily enable INFO logging for this block
                scheduler_service.send_appointment_reminders()

        # Assertions
        expected_message = f"Hi Reminder, reminder for {tomorrow.strftime('%B %d, %Y')} at {appointment_time.strftime('%I:%M %P')}."
        mock_send_sms.assert_called_once_with('+11234567890', expected_message)
        
        # Verify logging
        assert f"Sent appointment reminder to Reminder Contact for appointment {appointment.id}" in caplog.text

def test_send_appointment_reminders_no_appointments(app, db_session, scheduler_service, mocker):
    """Test send_appointment_reminders when no appointments are scheduled for tomorrow."""
    mock_send_sms = mocker.patch('services.scheduler_service.send_sms') # Patch where it's imported
    
    with app.app_context():
        # Ensure no appointments for tomorrow
        tomorrow = date.today() + timedelta(days=1)
        # Delete any existing appointments for tomorrow from conftest.py seeding
        db_session.query(Appointment).filter(Appointment.date == tomorrow).delete()
        db_session.commit()
        assert Appointment.query.filter(Appointment.date == tomorrow).first() is None

        # Execute the method
        with patch('datetime.date') as mock_date:
            mock_date.today.return_value = date.today()
            mock_date.side_effect = lambda *args, **kw: date(*args, **kw)
            scheduler_service.send_appointment_reminders()

        # Assertions
        mock_send_sms.assert_not_called()
        # No specific log for "no appointments" in current code, so no caplog assertion here

def test_send_appointment_reminders_missing_phone(app, db_session, scheduler_service, mocker):
    """Test send_appointment_reminders when contact has no phone number."""
    mock_send_sms = mocker.patch('services.scheduler_service.send_sms') # Patch where it's imported
    
    with app.app_context():
        # Template is now seeded in conftest.py, so just query it
        reminder_template = Setting.query.filter_by(key='appointment_reminder_template').first()
        assert reminder_template is not None

        contact = Contact(first_name='NoPhone', last_name='Contact', phone=None) # Set phone to None
        db_session.add(contact)
        db_session.commit()

        prop = Property(address='789 NoPhone Ave', contact=contact)
        db_session.add(prop)
        db_session.commit()

        job = Job(description='NoPhone Job', property=prop, status='Active')
        db_session.add(job)
        db_session.commit()

        tomorrow = date.today() + timedelta(days=1)
        # Corrected: Pass job_id, as Appointment model now has job_id
        appointment = Appointment(title='NoPhone Appt', date=tomorrow, time=time(10,0), contact=contact, job_id=job.id)
        db_session.add(appointment)
        db_session.commit()

        # Execute the method
        with patch('datetime.date') as mock_date:
            mock_date.today.return_value = date.today()
            mock_date.side_effect = lambda *args, **kw: date(*args, **kw)
            scheduler_service.send_appointment_reminders()

        # Assertions
        mock_send_sms.assert_not_called()

def test_send_appointment_reminders_send_sms_failure(app, db_session, scheduler_service, mocker, caplog):
    """Test send_appointment_reminders when send_sms fails."""
    mocker.patch('services.scheduler_service.send_sms', side_effect=Exception("SMS sending failed")) # Patch where it's imported
    
    with app.app_context():
        # Template is now seeded in conftest.py, so just query it
        reminder_template = Setting.query.filter_by(key='appointment_reminder_template').first()
        assert reminder_template is not None

        contact = Contact(first_name='FailSMS', last_name='Contact', phone='+19998887777')
        db_session.add(contact)
        db_session.commit()

        prop = Property(address='101 Fail St', contact=contact)
        db_session.add(prop)
        db_session.commit()

        job = Job(description='FailSMS Job', property=prop, status='Active')
        db_session.add(job)
        db_session.commit()

        tomorrow = date.today() + timedelta(days=1)
        # Corrected: Pass job_id, as Appointment model now has job_id
        appointment = Appointment(title='FailSMS Appt', date=tomorrow, time=time(11,0), contact=contact, job_id=job.id)
        db_session.add(appointment)
        db_session.commit()

        # Execute the method
        with caplog.at_level(logging.ERROR):
            with patch('datetime.date') as mock_date:
                mock_date.today.return_value = date.today()
                mock_date.side_effect = lambda *args, **kw: date(*args, **kw)
                scheduler_service.send_appointment_reminders()

        # Assertions
        assert "Failed to send SMS reminder" in caplog.text
        assert f"Error: SMS sending failed" in caplog.text

def test_send_appointment_reminders_missing_template(app, db_session, scheduler_service, mocker):
    """Test send_appointment_reminders when the reminder template is missing."""
    mock_send_sms = mocker.patch('services.scheduler_service.send_sms') # Patch where it's imported
    
    with app.app_context():
        # Delete the template seeded by conftest for this specific test
        template_to_delete = Setting.query.filter_by(key='appointment_reminder_template').first()
        if template_to_delete:
            db_session.delete(template_to_delete)
            db_session.commit()
        assert Setting.query.filter_by(key='appointment_reminder_template').first() is None

        contact = Contact(first_name='NoTemplate', last_name='Contact', phone='+1234567892') # Unique phone
        db_session.add(contact)
        db_session.commit()

        prop = Property(address='202 NoTemplate Rd', contact=contact)
        db_session.add(prop)
        db.session.commit()

        job = Job(description='NoTemplate Job', property=prop, status='Active')
        db_session.add(job)
        db_session.commit()

        tomorrow = date.today() + timedelta(days=1)
        # Corrected: Pass job_id, as Appointment model now has job_id
        appointment = Appointment(title='NoTemplate Appt', date=tomorrow, time=time(12,0), contact=contact, job_id=job.id)
        db_session.add(appointment)
        db_session.commit()

        # Execute the method
        with patch('datetime.date') as mock_date:
            mock_date.today.return_value = date.today()
            mock_date.side_effect = lambda *args, **kw: date(*args, **kw)
            scheduler_service.send_appointment_reminders()

        # Assertions
        mock_send_sms.assert_not_called()

# --- Tests for send_review_requests ---

def test_send_review_requests_success(app, db_session, scheduler_service, mocker, caplog):
    """Test successful sending of review requests."""
    mock_send_sms = mocker.patch('services.scheduler_service.send_sms', return_value=True) # Patch where it's imported
    
    with app.app_context():
        # Template is now seeded in conftest.py, so just query it
        review_template = Setting.query.filter_by(key='review_request_template').first()
        assert review_template is not None

        # Seed data for a completed job yesterday
        contact = Contact(first_name='Review', last_name='Contact', phone='+11112223333', email='review@example.com')
        db_session.add(contact)
        db_session.commit()

        prop = Property(address='303 Review St', contact=contact)
        db_session.add(prop)
        db_session.commit()

        yesterday_dt = datetime.utcnow() - timedelta(days=1)
        job = Job(description='Review Job', property=prop, status='Completed', completed_at=yesterday_dt)
        db_session.add(job)
        db_session.commit()

        # Execute the method
        with patch('datetime.datetime') as mock_dt:
            mock_dt.utcnow.return_value = datetime.utcnow() # Mock utcnow for consistency
            mock_dt.side_effect = lambda *args, **kw: datetime(*args, **kw) # Allow normal datetime creation
            with caplog.at_level(logging.INFO): # Temporarily enable INFO logging for this block
                scheduler_service.send_review_requests()

        # Assertions
        expected_message = f"Hi Review, please leave a review!"
        mock_send_sms.assert_called_once_with('+11112223333', expected_message)
        
        # Verify logging
        assert f"Sent review request to Review Contact for job {job.id}" in caplog.text

def test_send_review_requests_no_completed_jobs(app, db_session, scheduler_service, mocker):
    """Test send_review_requests when no jobs were completed yesterday."""
    mock_send_sms = mocker.patch('services.scheduler_service.send_sms') # Patch where it's imported
    
    with app.app_context():
        # Ensure no completed jobs for yesterday
        yesterday_dt = datetime.utcnow() - timedelta(days=1)
        # Delete any existing jobs for yesterday from conftest.py seeding
        db_session.query(Job).filter(db.func.date(Job.completed_at) == yesterday_dt.date()).delete()
        db_session.commit()
        
        assert Job.query.filter(
            Job.status == 'Completed',
            db.func.date(Job.completed_at) == yesterday_dt.date()
        ).first() is None

        # Execute the method
        with patch('datetime.datetime') as mock_dt:
            mock_dt.utcnow.return_value = datetime.utcnow()
            mock_dt.side_effect = lambda *args, **kw: datetime(*args, **kw)
            scheduler_service.send_review_requests()

        # Assertions
        mock_send_sms.assert_not_called()

def test_send_review_requests_missing_phone(app, db_session, scheduler_service, mocker):
    """Test send_review_requests when contact has no phone number."""
    mock_send_sms = mocker.patch('services.scheduler_service.send_sms') # Patch where it's imported
    
    with app.app_context():
        # Template is now seeded in conftest.py, so just query it
        review_template = Setting.query.filter_by(key='review_request_template').first()
        assert review_template is not None

        contact = Contact(first_name='NoPhoneReview', last_name='Contact', phone=None) # Set phone to None
        db_session.add(contact)
        db_session.commit()

        prop = Property(address='404 NoPhone Review', contact=contact)
        db_session.add(prop)
        db.session.commit()

        yesterday_dt = datetime.utcnow() - timedelta(days=1)
        job = Job(description='NoPhoneReview Job', property=prop, status='Completed', completed_at=yesterday_dt)
        db_session.add(job)
        db_session.commit()

        # Execute the method
        with patch('datetime.datetime') as mock_dt:
            mock_dt.utcnow.return_value = datetime.utcnow()
            mock_dt.side_effect = lambda *args, **kw: datetime(*args, **kw)
            scheduler_service.send_review_requests()

        # Assertions
        # The contact's phone is explicitly None, so send_sms should NOT be called.
        mock_send_sms.assert_not_called()

def test_send_review_requests_send_sms_failure(app, db_session, scheduler_service, mocker, caplog):
    """Test send_review_requests when send_sms fails."""
    mocker.patch('services.scheduler_service.send_sms', side_effect=Exception("SMS sending failed")) # Patch where it's imported
    
    with app.app_context():
        # Template is now seeded in conftest.py, so just query it
        review_template = Setting.query.filter_by(key='review_request_template').first()
        assert review_template is not None

        contact = Contact(first_name='FailReview', last_name='Contact', phone='+15554443333')
        db_session.add(contact)
        db_session.commit()

        prop = Property(address='505 Fail Review', contact=contact)
        db_session.add(prop)
        db.session.commit()

        yesterday_dt = datetime.utcnow() - timedelta(days=1)
        job = Job(description='FailReview Job', property=prop, status='Completed', completed_at=yesterday_dt)
        db_session.add(job)
        db_session.commit()

        # Execute the method
        with caplog.at_level(logging.ERROR):
            with patch('datetime.datetime') as mock_dt:
                mock_dt.utcnow.return_value = datetime.utcnow()
                mock_dt.side_effect = lambda *args, **kw: datetime(*args, **kw)
                scheduler_service.send_review_requests()

        # Assertions
        assert "Failed to send review request" in caplog.text
        assert "Error: SMS sending failed" in caplog.text

def test_send_review_requests_missing_template(app, db_session, scheduler_service, mocker):
    """Test send_review_requests when the review request template is missing."""
    mock_send_sms = mocker.patch('services.scheduler_service.send_sms') # Patch where it's imported
    
    with app.app_context():
        # Delete the template seeded by conftest for this specific test
        template_to_delete = Setting.query.filter_by(key='review_request_template').first()
        if template_to_delete:
            db_session.delete(template_to_delete)
            db_session.commit()
        assert Setting.query.filter_by(key='review_request_template').first() is None

        contact = Contact(first_name='NoTemplateReview', last_name='Contact', phone='+1234567894') # Unique phone
        db_session.add(contact)
        db_session.commit()

        prop = Property(address='606 NoTemplate Review', contact=contact)
        db_session.add(prop)
        db.session.commit()

        yesterday_dt = datetime.utcnow() - timedelta(days=1)
        job = Job(description='NoTemplateReview Job', property=prop, status='Completed', completed_at=yesterday_dt)
        db_session.add(job)
        db_session.commit()

        # Execute the method
        with patch('datetime.datetime') as mock_dt:
            mock_dt.utcnow.return_value = datetime.utcnow()
            mock_dt.side_effect = lambda *args, **kw: datetime(*args, **kw)
            scheduler_service.send_review_requests()

        # Assertions
        mock_send_sms.assert_not_called()

# --- Tests for convert_quotes_for_today_appointments ---

def test_convert_quotes_for_today_appointments_success(app, db_session, scheduler_service, mocker, caplog):
    """Test successful conversion of draft quotes to invoices for today's appointments."""
    mock_create_invoice = mocker.patch('services.invoice_service.InvoiceService.create_invoice_from_quote')
    
    with app.app_context():
        # Seed appointment for today with a job and a draft quote
        contact = Contact(first_name='Convert', last_name='Contact', phone='+19999999999')
        db_session.add(contact)
        db_session.commit()

        prop = Property(address='707 Convert Ave', contact=contact)
        db_session.add(prop)
        db_session.commit()

        job = Job(description='Convert Job', property=prop, status='Active')
        db_session.add(job)
        db_session.commit()

        quote = Quote(amount=100.0, job=job, status='Draft')
        db_session.add(quote)
        db_session.commit()

        today = date.today()
        # Corrected: Pass job_id, as Appointment model now has job_id
        appointment = Appointment(title='Today Appt', date=today, time=time(8,0), contact=contact, job_id=job.id)
        db_session.add(appointment)
        db_session.commit()

        # Execute the method
        with caplog.at_level(logging.INFO):
            with patch('datetime.date') as mock_date:
                mock_date.today.return_value = today
                mock_date.side_effect = lambda *args, **kw: date(*args, **kw)
                scheduler_service.convert_quotes_for_today_appointments()

        # Assertions
        mock_create_invoice.assert_called_once_with(quote.id)
        assert f"Running quote-to-invoice conversion job for appointments on {today.strftime('%Y-%m-%d')}" in caplog.text
        assert f"Found draft quote {quote.id} for job {job.id} associated with today's appointment {appointment.id}. Attempting conversion." in caplog.text
        assert f"Successfully converted quote {quote.id} to a new invoice." in caplog.text

def test_convert_quotes_for_today_appointments_no_appointments(app, db_session, scheduler_service, mocker, caplog):
    """Test conversion when no appointments are scheduled for today."""
    mock_create_invoice = mocker.patch('services.invoice_service.InvoiceService.create_invoice_from_quote')
    
    with app.app_context():
        # Ensure no appointments for today
        today = date.today()
        # Delete any existing appointments for today from conftest.py seeding
        db_session.query(Appointment).filter(Appointment.date == today).delete()
        db_session.commit()
        assert Appointment.query.filter(Appointment.date == today).first() is None

        # Execute the method
        with caplog.at_level(logging.INFO):
            with patch('datetime.date') as mock_date:
                mock_date.today.return_value = today
                mock_date.side_effect = lambda *args, **kw: date(*args, **kw)
                scheduler_service.convert_quotes_for_today_appointments()

        # Assertions
        mock_create_invoice.assert_not_called()
        assert "No appointments scheduled for today. Exiting job." in caplog.text

def test_convert_quotes_for_today_appointments_no_draft_quotes(app, db_session, scheduler_service, mocker, caplog):
    """Test conversion when appointments exist but no draft quotes are associated."""
    mock_create_invoice = mocker.patch('services.invoice_service.InvoiceService.create_invoice_from_quote')
    
    with app.app_context():
        # Seed appointment for today with a job but no draft quotes
        contact = Contact(first_name='NoQuote', last_name='Contact', phone='+18887776666')
        db_session.add(contact)
        db_session.commit()

        prop = Property(address='808 NoQuote Blvd', contact=contact)
        db_session.add(prop)
        db_session.commit()

        job = Job(description='NoQuote Job', property=prop, status='Active')
        db_session.add(job)
        db_session.commit()

        # Add a non-draft quote
        approved_quote = Quote(amount=50.0, job=job, status='Approved')
        db_session.add(approved_quote) 
        db_session.commit()

        today = date.today()
        # Corrected: Pass job_id, as Appointment model now has job_id
        appointment = Appointment(title='Today Appt NoQuote', date=today, time=time(9,0), contact=contact, job_id=job.id)
        db_session.add(appointment)
        db_session.commit()

        # Execute the method
        with caplog.at_level(logging.INFO):
            with patch('datetime.date') as mock_date:
                mock_date.today.return_value = today
                mock_date.side_effect = lambda *args, **kw: date(*args, **kw)
                scheduler_service.convert_quotes_for_today_appointments()

        # Assertions
        mock_create_invoice.assert_not_called()
        assert f"Running quote-to-invoice conversion job for appointments on {today.strftime('%Y-%m-%d')}" in caplog.text
        # No specific log for "no draft quotes" in current code, so no caplog assertion here

def test_convert_quotes_for_today_appointments_conversion_failure(app, db_session, scheduler_service, mocker, caplog):
    """Test conversion when create_invoice_from_quote fails."""
    mocker.patch('services.invoice_service.InvoiceService.create_invoice_from_quote', side_effect=Exception("Invoice creation failed"))
    
    with app.app_context():
        contact = Contact(first_name='FailConvert', last_name='Contact', phone='+17776665555')
        db_session.add(contact)
        db_session.commit()

        prop = Property(address='909 Fail Convert', contact=contact)
        db_session.add(prop)
        db_session.commit()

        job = Job(description='FailConvert Job', property=prop, status='Active')
        db_session.add(job)
        db_session.commit()

        quote = Quote(amount=200.0, job=job, status='Draft')
        db_session.add(quote)
        db_session.commit()

        today = date.today()
        # Corrected: Pass job_id, as Appointment model now has job_id
        appointment = Appointment(title='Today Appt FailConvert', date=today, time=time(10,0), contact=contact, job_id=job.id)
        db_session.add(appointment)
        db_session.commit()

        # Execute the method
        with caplog.at_level(logging.ERROR):
            with patch('datetime.date') as mock_date:
                mock_date.today.return_value = today
                mock_date.side_effect = lambda *args, **kw: date(*args, **kw)
                scheduler_service.convert_quotes_for_today_appointments()

        # Assertions
        assert "Failed to convert quote" in caplog.text
        assert "Error: Invoice creation failed" in caplog.text

# --- Tests for run_daily_tasks ---

def test_run_daily_tasks(app, db_session, scheduler_service, mocker, caplog):
    """Test that run_daily_tasks calls all expected sub-tasks."""
    mock_send_reminders = mocker.patch.object(scheduler_service, 'send_appointment_reminders')
    mock_send_reviews = mocker.patch.object(scheduler_service, 'send_review_requests')
    mock_convert_quotes = mocker.patch.object(scheduler_service, 'convert_quotes_for_today_appointments')

    with caplog.at_level(logging.INFO):
        scheduler_service.run_daily_tasks()
    
    mock_send_reminders.assert_called_once()
    mock_send_reviews.assert_called_once()
    mock_convert_quotes.assert_called_once()
    
    assert "Starting daily scheduled tasks..." in caplog.text
    assert "Daily scheduled tasks completed." in caplog.text
