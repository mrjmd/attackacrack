# tests/test_appointment_service.py
"""
Tests for the AppointmentService, focusing on creating and deleting appointments
and ensuring the Google Calendar integration is called correctly.
"""

import pytest
from services.appointment_service import AppointmentService
from crm_database import Appointment, Contact
from datetime import date, time
from unittest.mock import patch

def test_add_appointment_with_google_calendar(app, db_session, mocker):
    """
    GIVEN a mock of the Google Calendar API
    WHEN a new appointment is added via the AppointmentService
    THEN it should create an appointment in the local database
    AND call the Google Calendar API to create an event
    AND save the Google Calendar event ID to the local appointment record.
    """
    # 1. Setup
    # Mock the external Google Calendar API call
    mock_create_event = mocker.patch(
        'services.appointment_service.create_google_calendar_event',
        return_value={'id': 'mock_google_event_123'}
    )

    # We need a contact to associate the appointment with
    contact = db_session.get(Contact, 1)
    assert contact is not None

    appointment_service = AppointmentService()

    # 2. Execution
    new_appointment = appointment_service.add_appointment(
        title="Foundation Check",
        description="Customer reports a new crack.",
        date=date(2025, 8, 1),
        time=time(10, 0),
        contact_id=contact.id,
        appt_type='Assessment'
    )

    # 3. Assertions
    # Check that the appointment was created in our DB
    assert new_appointment.id is not None
    assert new_appointment.title == "Foundation Check"
    
    # Check that the Google Calendar API was called
    mock_create_event.assert_called_once()
    
    # Check that the Google event ID was saved to our DB record
    assert new_appointment.google_calendar_event_id == 'mock_google_event_123'

# TODO: Add a test for deleting an appointment, ensuring it also calls the delete_google_calendar_event function.
# TODO: Add a test for what happens if the Google Calendar API call fails.
