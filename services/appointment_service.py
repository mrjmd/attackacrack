from extensions import db
from crm_database import Appointment
from api_integrations import create_google_calendar_event, delete_google_calendar_event
from datetime import datetime, timedelta

class AppointmentService:
    def __init__(self):
        self.session = db.session

    def add_appointment(self, **kwargs):
        # Create the appointment in our local database first
        new_appointment = Appointment(
            title=kwargs.get('title'),
            description=kwargs.get('description'),
            date=kwargs.get('date'),
            time=kwargs.get('time'),
            contact_id=kwargs.get('contact_id')
        )
        self.session.add(new_appointment)
        # We commit here to make sure the appointment has an ID before we proceed
        self.session.commit()

        # Now, create the corresponding event in Google Calendar
        try:
            start_datetime = datetime.combine(new_appointment.date, new_appointment.time)
            appt_type = kwargs.get('appt_type', 'Assessment')
            duration_hours = 4 if appt_type in ['Repair', 'Callback'] else 0.5
            end_datetime = start_datetime + timedelta(hours=duration_hours)
            
            attendees = ['mike.harrington.email@example.com'] # Replace with real email
            if new_appointment.contact.email:
                attendees.append(new_appointment.contact.email)

            contact_info = f"Customer: {new_appointment.contact.first_name} {new_appointment.contact.last_name}\nPhone: {new_appointment.contact.phone}"
            full_description = f"{new_appointment.description}\n\n{contact_info}"
            location = new_appointment.contact.properties[0].address if new_appointment.contact.properties else None

            created_event = create_google_calendar_event(
                title=new_appointment.title,
                description=full_description,
                start_time=start_datetime,
                end_time=end_datetime,
                attendees=attendees,
                location=location
            )

            # --- SAVE THE EVENT ID ---
            if created_event:
                new_appointment.google_calendar_event_id = created_event.get('id')
                self.session.commit()
            # --- END SAVE ---

        except Exception as e:
            print(f"Failed to create Google Calendar event after saving appointment: {e}")

        return new_appointment

    def get_all_appointments(self):
        return self.session.query(Appointment).all()

    def get_appointment_by_id(self, appointment_id):
        # --- THIS IS THE FIX ---
        return self.session.get(Appointment, appointment_id)
        # --- END FIX ---

    def delete_appointment(self, appointment):
        """
        Deletes an appointment from the local DB and the corresponding
        event from Google Calendar.
        """
        # --- DELETE GOOGLE EVENT FIRST ---
        if appointment.google_calendar_event_id:
            print(f"Deleting corresponding Google Calendar event: {appointment.google_calendar_event_id}")
            delete_google_calendar_event(appointment.google_calendar_event_id)
        # --- END DELETE ---
        
        self.session.delete(appointment)
        self.session.commit()

    def update_appointment(self, appointment, **kwargs):
        for key, value in kwargs.items():
            setattr(appointment, key, value)
        self.session.commit()
        return appointment
