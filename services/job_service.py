from extensions import db
from crm_database import Job

class JobService:
    def __init__(self):
        self.session = db.session

    def add_job(self, **kwargs):
        new_job = Job(**kwargs)
        self.session.add(new_job)
        self.session.commit()
        return new_job

    def get_all_jobs(self):
        return self.session.query(Job).all()

    def get_job_by_id(self, job_id):
        return self.session.query(Job).get(job_id)

    def update_job(self, job, **kwargs):
        for key, value in kwargs.items():
            setattr(job, key, value)
        self.session.commit()
        return job

    def delete_job(self, job):
        self.session.delete(job)
        self.session.commit()
