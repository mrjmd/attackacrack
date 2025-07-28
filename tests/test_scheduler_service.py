# tests/test_scheduler_service.py
import pytest
from crm_database import Appointment, Contact, Job, Property, Quote, Setting, db
from services.invoice_service import InvoiceService
from datetime import date, time, timedelta, datetime
from unittest.mock import patch

# Import the task functions to be tested
from services.scheduler_service import (
    send_appointment_reminders,
    send_review_requests,
    convert_quotes_for_today_appointments,
    run_daily_tasks
)

# --- Tests for the main daily task scheduler ---

def test_run_daily_tasks(app, mocker):
    """Test that run_daily_tasks calls all expected sub-tasks."""
    mock_send_reminders = mocker.patch('services.scheduler_service.send_appointment_reminders.delay')
    mock_send_reviews = mocker.patch('services.scheduler_service.send_review_requests.delay')
    mock_convert_quotes = mocker.patch('services.scheduler_service.convert_quotes_for_today_appointments.delay')

    with app.app_context():
        run_daily_tasks()

    mock_send_reminders.assert_called_once()
    mock_send_reviews.assert_called_once()
    mock_convert_quotes.assert_called_once()
