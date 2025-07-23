from extensions import db
from crm_database import Appointment

class AppointmentService:
    def __init__(self):
        self.session = db.session

    def add_appointment(self, **kwargs):
        new_appointment = Appointment(**kwargs)
        self.session.add(new_appointment)
        self.session.commit()
        return new_appointment

    def get_all_appointments(self):
        return self.session.query(Appointment).all()

    def get_appointment_by_id(self, appointment_id):
        return self.session.query(Appointment).get(appointment_id)

    def update_appointment(self, appointment, **kwargs):
        for key, value in kwargs.items():
            setattr(appointment, key, value)
        self.session.commit()
        return appointment

    def delete_appointment(self, appointment):
        self.session.delete(appointment)
        self.session.commit()
