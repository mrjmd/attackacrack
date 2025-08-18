# Model and db imports removed - using repositories only
from logging_config import get_logger
from repositories.job_repository import JobRepository

logger = get_logger(__name__)

class JobService:
    def __init__(self, job_repository: JobRepository = None):
        """Initialize JobService with optional repository dependency injection"""
        if job_repository is not None:
            self.repository = job_repository
        else:
            # Repository must be injected - no fallback
            raise ValueError("JobRepository must be provided via dependency injection")

    def get_or_create_active_job(self, property_id: int):
        """
        Finds the active job for a given property, or creates a new one.
        For now, we'll assume only one "Active" job per property.
        """
        # Use repository to find existing active job
        active_job = self.repository.find_active_job_by_property_id(property_id)

        if active_job:
            logger.info("Found existing active job", job_id=active_job.id, property_id=property_id)
            return active_job
        else:
            # If no active job exists, create a new one.
            logger.info("No active job found for property, creating new job", property_id=property_id)
            
            # Create job without property lookup - repository handles this
            new_job = self.repository.create(
                description=f"New job for property {property_id}",
                property_id=property_id,
                status='Active'
            )
            return new_job

    def add_job(self, **kwargs):
        """Create a new job using repository pattern"""
        return self.repository.create(**kwargs)

    def get_all_jobs(self):
        """Get all jobs using repository pattern"""
        return self.repository.get_all()

    def get_job_by_id(self, job_id):
        """Get job by ID using repository pattern"""
        return self.repository.get_by_id(job_id)

    def update_job(self, job, **kwargs):
        """Update job using repository pattern"""
        return self.repository.update(job, **kwargs)

    def delete_job(self, job):
        """Delete job using repository pattern"""
        if job is None:
            # Maintain backward compatibility - raise same error as direct session.delete(None)
            from sqlalchemy.orm.exc import UnmappedInstanceError
            raise UnmappedInstanceError("Class 'builtins.NoneType' is not mapped")
        return self.repository.delete(job)
