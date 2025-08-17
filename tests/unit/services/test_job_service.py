# tests/test_job_service_simple.py
"""
Tests for JobService matching the actual implementation.
"""

import pytest
from unittest.mock import MagicMock, patch
from services.job_service import JobService
from crm_database import Job, Property, Contact


@pytest.fixture
def job_service():
    """Fixture to provide JobService instance"""
    return JobService()


@pytest.fixture
def test_contact_with_property(app, db_session):
    """Fixture providing a contact with associated property"""
    import time
    unique_id = str(int(time.time() * 1000000))[-6:]  # Get unique 6-digit suffix
    
    contact = Contact(
        first_name="Alice",
        last_name="Johnson", 
        phone=f"+155578{unique_id}",
        email=f"alice{unique_id}@example.com"
    )
    db_session.add(contact)
    db_session.flush()
    
    property_obj = Property(
        address=f"789 Oak St #{unique_id}",
        contact_id=contact.id
    )
    db_session.add(property_obj)
    db_session.commit()
    
    return contact, property_obj


class TestJobService:
    """Test JobService methods"""
    
    def test_add_job_success(self, job_service, test_contact_with_property):
        """Test successful job creation"""
        contact, property_obj = test_contact_with_property
        
        job_data = {
            'description': 'Foundation repair needed',
            'property_id': property_obj.id,
            'status': 'Active'
        }
        
        new_job = job_service.add_job(**job_data)
        
        assert new_job is not None
        assert new_job.id is not None
        assert new_job.description == 'Foundation repair needed'
        assert new_job.property_id == property_obj.id
        assert new_job.status == 'Active'
    
    def test_get_all_jobs(self, job_service, test_contact_with_property):
        """Test retrieving all jobs"""
        contact, property_obj = test_contact_with_property
        
        # Create a few jobs
        for i in range(3):
            job_service.add_job(
                description=f'Test job {i}',
                property_id=property_obj.id,
                status='Active'
            )
        
        all_jobs = job_service.get_all_jobs()
        
        # Should have at least the 3 jobs we created
        assert len(all_jobs) >= 3
        
        # Check our jobs are in there
        descriptions = [job.description for job in all_jobs]
        assert 'Test job 0' in descriptions
        assert 'Test job 1' in descriptions
        assert 'Test job 2' in descriptions
    
    def test_get_job_by_id_success(self, job_service, test_contact_with_property):
        """Test successful job retrieval by ID"""
        contact, property_obj = test_contact_with_property
        
        # Create a job
        job = job_service.add_job(
            description='Test job for retrieval',
            property_id=property_obj.id,
            status='Active'
        )
        
        # Retrieve it
        retrieved_job = job_service.get_job_by_id(job.id)
        
        assert retrieved_job is not None
        assert retrieved_job.id == job.id
        assert retrieved_job.description == 'Test job for retrieval'
    
    def test_get_job_by_id_not_found(self, job_service):
        """Test job retrieval with non-existent ID"""
        result = job_service.get_job_by_id(99999)
        assert result is None
    
    def test_update_job_success(self, job_service, test_contact_with_property):
        """Test successful job update"""
        contact, property_obj = test_contact_with_property
        
        # Create a job
        job = job_service.add_job(
            description='Original description',
            property_id=property_obj.id,
            status='Active'
        )
        
        # Update it
        updated_job = job_service.update_job(
            job,
            description='Updated description',
            status='In Progress'
        )
        
        assert updated_job is not None
        assert updated_job.description == 'Updated description'
        assert updated_job.status == 'In Progress'
        assert updated_job.property_id == property_obj.id  # Should remain unchanged
    
    def test_delete_job_success(self, job_service, test_contact_with_property):
        """Test successful job deletion"""
        contact, property_obj = test_contact_with_property
        
        # Create a job
        job = job_service.add_job(
            description='Job to be deleted',
            property_id=property_obj.id,
            status='Active'
        )
        job_id = job.id
        
        # Delete it
        job_service.delete_job(job)
        
        # Verify it's gone
        deleted_job = job_service.get_job_by_id(job_id)
        assert deleted_job is None
    
    def test_get_or_create_active_job_existing(self, job_service, test_contact_with_property):
        """Test get_or_create_active_job when active job exists"""
        contact, property_obj = test_contact_with_property
        
        # Create an active job first
        existing_job = job_service.add_job(
            description='Existing active job',
            property_id=property_obj.id,
            status='Active'
        )
        
        # Call get_or_create_active_job
        result_job = job_service.get_or_create_active_job(property_obj.id)
        
        # Should return the existing job
        assert result_job.id == existing_job.id
        assert result_job.description == 'Existing active job'
    
    def test_get_or_create_active_job_create_new(self, job_service, test_contact_with_property):
        """Test get_or_create_active_job when no active job exists"""
        contact, property_obj = test_contact_with_property
        
        # No active jobs exist for this property
        result_job = job_service.get_or_create_active_job(property_obj.id)
        
        # Should create a new job
        assert result_job is not None
        assert result_job.property_id == property_obj.id
        assert result_job.status == 'Active'
        assert f'New job for {property_obj.address}' in result_job.description
    
    def test_get_or_create_active_job_ignores_inactive(self, job_service, test_contact_with_property):
        """Test get_or_create_active_job ignores inactive jobs"""
        contact, property_obj = test_contact_with_property
        
        # Create a completed job (not active)
        job_service.add_job(
            description='Completed job',
            property_id=property_obj.id,
            status='Completed'
        )
        
        # Call get_or_create_active_job
        result_job = job_service.get_or_create_active_job(property_obj.id)
        
        # Should create a new active job, not return the completed one
        assert result_job.status == 'Active'
        assert 'New job for' in result_job.description
        
        # Verify we now have 2 jobs for this property
        all_jobs = job_service.get_all_jobs()
        property_jobs = [j for j in all_jobs if j.property_id == property_obj.id]
        assert len(property_jobs) == 2
    
    @patch('services.job_service.logger')  # Mock logger instead of print
    def test_get_or_create_active_job_logging(self, mock_logger, job_service, test_contact_with_property):
        """Test that get_or_create_active_job logs appropriately"""
        contact, property_obj = test_contact_with_property
        
        # Test creation scenario
        job_service.get_or_create_active_job(property_obj.id)
        
        # Should have logged about creating new job
        mock_logger.info.assert_any_call("No active job found for property, creating new job", property_id=property_obj.id)
        
        # Reset mock and test existing scenario
        mock_logger.reset_mock()
        
        # Now get the existing active job
        job_service.get_or_create_active_job(property_obj.id)
        
        # Should have logged about finding existing job
        mock_logger.info.assert_any_call("Found existing active job", job_id=mock_logger.info.call_args_list[0][1]['job_id'], property_id=property_obj.id)


class TestJobServiceErrorHandling:
    """Test error handling scenarios"""
    
    def test_add_job_with_minimal_data(self, job_service, test_contact_with_property):
        """Test add_job with minimal required data"""
        contact, property_obj = test_contact_with_property
        
        # Create job with just required fields
        job = job_service.add_job(
            description='Minimal job',
            property_id=property_obj.id
        )
        
        assert job is not None
        assert job.description == 'Minimal job'
        assert job.property_id == property_obj.id
    
    def test_update_job_with_none_object(self, job_service):
        """Test update_job handles None job object"""
        with pytest.raises(AttributeError):
            job_service.update_job(None, description='New desc')
    
    def test_delete_job_with_none_object(self, job_service):
        """Test delete_job handles None job object"""
        from sqlalchemy.orm.exc import UnmappedInstanceError
        with pytest.raises(UnmappedInstanceError):
            job_service.delete_job(None)