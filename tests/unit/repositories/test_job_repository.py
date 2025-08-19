"""
Test Suite for JobRepository - Repository Pattern Implementation

Tests for data access operations on Job model, focusing on
job status tracking and completion date filtering for scheduler tasks.
"""

import pytest
from datetime import date, datetime, timedelta
from repositories.job_repository import JobRepository
from crm_database import Job, Property, Contact


@pytest.fixture
def test_contact_and_property(db_session):
    """Create test contact and property for job relationships"""
    # Use unique identifiers to avoid conflicts
    import time
    import random
    unique_id = str(int(time.time() * 1000) + random.randint(1, 1000))
    
    # Clean existing contact if any
    unique_phone = f'+1555{unique_id[-7:]}'  # Use last 7 digits to ensure uniqueness
    existing_contact = db_session.query(Contact).filter_by(phone=unique_phone).first()
    if existing_contact:
        db_session.delete(existing_contact)
        db_session.commit()
    
    contact = Contact(
        first_name='JobTest',
        last_name='User',
        email=f'jobtest{unique_id}@example.com',
        phone=unique_phone
    )
    db_session.add(contact)
    db_session.flush()
    
    property_obj = Property(
        address=f'123 Test St #{unique_id}',
        contact_id=contact.id,
        property_type='residential'
    )
    db_session.add(property_obj)
    db_session.flush()
    
    return contact, property_obj


class TestJobRepository:
    """Test cases for JobRepository"""
    
    @pytest.fixture
    def job_repository(self, db_session):
        """Create JobRepository instance with test database session"""
        return JobRepository(session=db_session, model_class=Job)
    
    
    @pytest.fixture
    def sample_jobs(self, db_session, test_contact_and_property):
        """Create sample jobs for testing"""
        contact, property_obj = test_contact_and_property
        
        # Create jobs with different statuses and completion dates
        yesterday = datetime.utcnow() - timedelta(days=1)
        two_days_ago = datetime.utcnow() - timedelta(days=2)
        
        jobs = [
            Job(
                description='Completed job from yesterday',
                status='Completed',
                completed_at=yesterday,
                property_id=property_obj.id
            ),
            Job(
                description='Completed job from two days ago',
                status='Completed',
                completed_at=two_days_ago,
                property_id=property_obj.id
            ),
            Job(
                description='Active job',
                status='Active',
                completed_at=None,
                property_id=property_obj.id
            ),
            Job(
                description='Another completed job from yesterday',
                status='Completed',
                completed_at=yesterday,
                property_id=property_obj.id
            )
        ]
        
        for job in jobs:
            db_session.add(job)
        db_session.commit()
        return jobs
    
    def test_create_job(self, job_repository, test_contact_and_property, db_session):
        """Test creating a new job"""
        # Arrange
        contact, property_obj = test_contact_and_property
        description = 'New test job'
        
        # Act
        job = job_repository.create(
            description=description,
            status='Active',
            property_id=property_obj.id
        )
        
        # Assert
        assert job.description == description
        assert job.status == 'Active'
        assert job.property_id == property_obj.id
        assert job.id is not None
        
        # Verify in database
        db_job = db_session.query(Job).filter_by(description=description).first()
        assert db_job is not None
        assert db_job.status == 'Active'
    
    def test_get_by_id(self, job_repository, sample_jobs):
        """Test retrieving job by ID"""
        # Arrange
        expected_job = sample_jobs[0]
        
        # Act
        job = job_repository.get_by_id(expected_job.id)
        
        # Assert
        assert job is not None
        assert job.description == expected_job.description
        assert job.status == expected_job.status
    
    def test_find_by_status(self, job_repository, sample_jobs):
        """Test finding jobs by status"""
        # Act
        completed_jobs = job_repository.find_by(status='Completed')
        active_jobs = job_repository.find_by(status='Active')
        
        # Assert - Account for seed data from conftest.py
        # The app fixture creates 1 Active job ("Test Job") + sample_jobs creates 1 Active job
        assert len(completed_jobs) == 3  # Three completed jobs from sample_jobs
        assert len(active_jobs) == 2     # One from seed data + one from sample_jobs
        
        for job in completed_jobs:
            assert job.status == 'Completed'
        
        for job in active_jobs:
            assert job.status == 'Active'
    
    def test_find_by_property_id(self, job_repository, sample_jobs, test_contact_and_property):
        """Test finding jobs by property ID"""
        # Arrange
        contact, property_obj = test_contact_and_property
        
        # Act
        property_jobs = job_repository.find_by(property_id=property_obj.id)
        
        # Assert
        assert len(property_jobs) == 4  # All sample jobs belong to this property
        for job in property_jobs:
            assert job.property_id == property_obj.id
    
    def test_get_all_jobs(self, job_repository, sample_jobs):
        """Test retrieving all jobs"""
        # Act
        all_jobs = job_repository.get_all()
        
        # Assert - Account for seed data (1 job) + sample_jobs (4 jobs)
        assert len(all_jobs) == 5
        descriptions = [j.description for j in all_jobs]
        assert 'Completed job from yesterday' in descriptions
        assert 'Active job' in descriptions
    
    def test_update_job_status(self, job_repository, sample_jobs):
        """Test updating job status"""
        # Arrange
        job = sample_jobs[2]  # Active job
        assert job.status == 'Active'
        
        # Act
        updated_job = job_repository.update(
            job, 
            status='Completed',
            completed_at=datetime.utcnow()
        )
        
        # Assert
        assert updated_job.status == 'Completed'
        assert updated_job.completed_at is not None
    
    def test_delete_job(self, job_repository, sample_jobs, db_session):
        """Test deleting a job"""
        # Arrange
        job_to_delete = sample_jobs[0]
        job_id = job_to_delete.id
        
        # Act
        result = job_repository.delete(job_to_delete)
        
        # Assert
        assert result is True
        
        # Verify deletion
        deleted_job = db_session.query(Job).get(job_id)
        assert deleted_job is None
    
    def test_count_jobs_by_status(self, job_repository, sample_jobs):
        """Test counting jobs by status"""
        # Act
        completed_count = job_repository.count(status='Completed')
        active_count = job_repository.count(status='Active')
        
        # Assert - Account for seed data (1 Active job) + sample_jobs (1 Active, 3 Completed)
        assert completed_count == 3
        assert active_count == 2
    
    def test_search_jobs(self, job_repository, sample_jobs):
        """Test searching jobs by description"""
        # Act
        results = job_repository.search('yesterday')
        
        # Assert
        assert len(results) == 2  # Two jobs mention "yesterday"
        for job in results:
            assert 'yesterday' in job.description.lower()


class TestJobRepositorySchedulerMethods:
    """Test specialized methods for scheduler service needs"""
    
    @pytest.fixture
    def job_repository(self, db_session):
        """Create JobRepository instance"""
        return JobRepository(session=db_session, model_class=Job)
    
    @pytest.fixture
    def scheduler_test_jobs(self, db_session, test_contact_and_property):
        """Create jobs specifically for scheduler testing"""
        contact, property_obj = test_contact_and_property
        
        # Create jobs with specific completion dates for testing
        yesterday = datetime.utcnow().date() - timedelta(days=1)
        two_days_ago = datetime.utcnow().date() - timedelta(days=2)
        today = datetime.utcnow().date()
        
        # Set specific times for completed_at to test date filtering
        yesterday_dt = datetime.combine(yesterday, datetime.min.time())
        two_days_ago_dt = datetime.combine(two_days_ago, datetime.min.time())
        today_dt = datetime.combine(today, datetime.min.time())
        
        jobs = [
            Job(
                description='Job completed yesterday',
                status='Completed',
                completed_at=yesterday_dt,
                property_id=property_obj.id
            ),
            Job(
                description='Another job completed yesterday',
                status='Completed', 
                completed_at=yesterday_dt,
                property_id=property_obj.id
            ),
            Job(
                description='Job completed two days ago',
                status='Completed',
                completed_at=two_days_ago_dt,
                property_id=property_obj.id
            ),
            Job(
                description='Job completed today',
                status='Completed',
                completed_at=today_dt,
                property_id=property_obj.id
            ),
            Job(
                description='Active job not completed',
                status='Active',
                completed_at=None,
                property_id=property_obj.id
            )
        ]
        
        for job in jobs:
            db_session.add(job)
        db_session.commit()
        return jobs
    
    def test_find_completed_jobs_by_date(self, job_repository, scheduler_test_jobs):
        """Test finding completed jobs by specific completion date"""
        # Arrange
        yesterday = datetime.utcnow().date() - timedelta(days=1)
        
        # Act - This tests the pattern used in scheduler_service.py line 66-69
        completed_jobs_yesterday = job_repository.find_completed_jobs_by_date(yesterday)
        
        # Assert
        assert len(completed_jobs_yesterday) == 2  # Two jobs completed yesterday
        for job in completed_jobs_yesterday:
            assert job.status == 'Completed'
            assert job.completed_at.date() == yesterday
    
    def test_find_completed_jobs_by_date_no_results(self, job_repository, scheduler_test_jobs):
        """Test finding completed jobs when no jobs match the date"""
        # Arrange
        future_date = datetime.utcnow().date() + timedelta(days=10)
        
        # Act
        completed_jobs = job_repository.find_completed_jobs_by_date(future_date)
        
        # Assert
        assert len(completed_jobs) == 0
    
    def test_find_completed_jobs_excludes_active_jobs(self, job_repository, scheduler_test_jobs):
        """Test that finding completed jobs excludes active jobs"""
        # Arrange
        today = datetime.utcnow().date()
        
        # Act
        completed_jobs_today = job_repository.find_completed_jobs_by_date(today)
        
        # Assert
        assert len(completed_jobs_today) == 1  # Only one completed today, not the active one
        assert completed_jobs_today[0].status == 'Completed'
        assert completed_jobs_today[0].description == 'Job completed today'
    
    def test_completed_jobs_have_property_relationship(self, job_repository, scheduler_test_jobs, test_contact_and_property):
        """Test that completed jobs maintain property relationship for contact access"""
        # Arrange
        contact, property_obj = test_contact_and_property
        yesterday = datetime.utcnow().date() - timedelta(days=1)
        
        # Act
        completed_jobs = job_repository.find_completed_jobs_by_date(yesterday)
        
        # Assert
        assert len(completed_jobs) > 0
        for job in completed_jobs:
            assert job.property_id == property_obj.id
            # In actual usage, job.property.contact would be accessible
    
    def test_find_completed_jobs_different_dates(self, job_repository, scheduler_test_jobs):
        """Test finding completed jobs across different dates"""
        # Arrange
        yesterday = datetime.utcnow().date() - timedelta(days=1)
        two_days_ago = datetime.utcnow().date() - timedelta(days=2)
        today = datetime.utcnow().date()
        
        # Act
        jobs_yesterday = job_repository.find_completed_jobs_by_date(yesterday)
        jobs_two_days_ago = job_repository.find_completed_jobs_by_date(two_days_ago)
        jobs_today = job_repository.find_completed_jobs_by_date(today)
        
        # Assert
        assert len(jobs_yesterday) == 2
        assert len(jobs_two_days_ago) == 1
        assert len(jobs_today) == 1
        
        # Verify they are different jobs
        yesterday_ids = {job.id for job in jobs_yesterday}
        two_days_ago_ids = {job.id for job in jobs_two_days_ago}
        today_ids = {job.id for job in jobs_today}
        
        # Should be no overlap
        assert yesterday_ids.isdisjoint(two_days_ago_ids)
        assert yesterday_ids.isdisjoint(today_ids)
        assert two_days_ago_ids.isdisjoint(today_ids)


class TestJobRepositoryServiceMethods:
    """Test methods specifically needed by JobService"""
    
    @pytest.fixture
    def job_repository(self, db_session):
        """Create JobRepository instance"""
        return JobRepository(session=db_session, model_class=Job)
    
    def test_find_active_job_by_property_id(self, job_repository, test_contact_and_property, db_session):
        """Test finding active job for a specific property - JobService line 18-21"""
        # Arrange
        contact, property_obj = test_contact_and_property
        
        # Create multiple jobs for the property
        active_job = Job(
            description='Active job for property',
            status='Active',
            property_id=property_obj.id
        )
        completed_job = Job(
            description='Completed job for property',
            status='Completed',
            completed_at=datetime.utcnow(),
            property_id=property_obj.id
        )
        
        db_session.add(active_job)
        db_session.add(completed_job)
        db_session.commit()
        
        # Act
        found_job = job_repository.find_active_job_by_property_id(property_obj.id)
        
        # Assert
        assert found_job is not None
        assert found_job.id == active_job.id
        assert found_job.status == 'Active'
        assert found_job.property_id == property_obj.id
    
    def test_find_active_job_by_property_id_none_exists(self, job_repository, test_contact_and_property, db_session):
        """Test finding active job when only completed jobs exist"""
        # Arrange
        contact, property_obj = test_contact_and_property
        
        # Create only completed job
        completed_job = Job(
            description='Completed job for property',
            status='Completed',
            completed_at=datetime.utcnow(),
            property_id=property_obj.id
        )
        db_session.add(completed_job)
        db_session.commit()
        
        # Act
        found_job = job_repository.find_active_job_by_property_id(property_obj.id)
        
        # Assert
        assert found_job is None
    
    def test_find_active_job_by_property_id_multiple_active(self, job_repository, test_contact_and_property, db_session):
        """Test finding active job when multiple active jobs exist (should return first)"""
        # Arrange
        contact, property_obj = test_contact_and_property
        
        # Create multiple active jobs (edge case)
        job1 = Job(
            description='First active job',
            status='Active',
            property_id=property_obj.id
        )
        job2 = Job(
            description='Second active job',
            status='Active',
            property_id=property_obj.id
        )
        
        db_session.add(job1)
        db_session.add(job2)
        db_session.commit()
        
        # Act
        found_job = job_repository.find_active_job_by_property_id(property_obj.id)
        
        # Assert
        assert found_job is not None
        assert found_job.status == 'Active'
        assert found_job.property_id == property_obj.id
        # Should return one of the active jobs (implementation decides which)
        assert found_job.id in [job1.id, job2.id]