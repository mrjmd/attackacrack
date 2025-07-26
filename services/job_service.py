from extensions import db
from crm_database import Job

class JobService:
    def __init__(self):
        self.session = db.session

    # --- NEW METHOD ---
    def get_or_create_active_job(self, property_id: int):
        """
        Finds the active job for a given property, or creates a new one.
        For now, we'll assume only one "Active" job per property.
        """
        # Look for an existing job for this property that is still 'Active'
        active_job = self.session.query(Job).filter_by(
            property_id=property_id,
            status='Active'
        ).first()

        if active_job:
            print(f"Found existing active job (ID: {active_job.id}) for property {property_id}.")
            return active_job
        else:
            # If no active job exists, create a new one.
            print(f"No active job found for property {property_id}. Creating a new one.")
            # We need the Property model to get the address for the description
            from crm_database import Property
            prop = self.session.query(Property).get(property_id)
            
            new_job = self.add_job(
                description=f"New job for {prop.address}",
                property_id=property_id,
                status='Active'
            )
            return new_job
    # --- END NEW METHOD ---

    def add_job(self, **kwargs):
        new_job = Job(**kwargs)
        self.session.add(new_job)
        self.session.commit()
        return new_job

    def get_all_jobs(self):
        return self.session.query(Job).all()

    def get_job_by_id(self, job_id):
        # --- THIS IS THE FIX ---
        return self.session.get(Job, job_id)
        # --- END FIX ---

    def update_job(self, job, **kwargs):
        for key, value in kwargs.items():
            setattr(job, key, value)
        self.session.commit()
        return job

    def delete_job(self, job):
        self.session.delete(job)
        self.session.commit()
