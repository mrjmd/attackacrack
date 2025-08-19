"""
TDD Tests for JobService Repository Pattern Refactoring

These tests verify that JobService properly uses JobRepository and PropertyRepository
instead of direct database queries. Tests MUST fail initially (RED phase).
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
from services.job_service import JobService
from repositories.job_repository import JobRepository
from crm_database import Job


class TestJobServiceRepositoryPattern:
    """Test JobService uses repository pattern instead of direct database queries"""
    
    @pytest.fixture
    def mock_job_repository(self):
        """Mock JobRepository"""
        return Mock(spec=JobRepository)
    
    
    @pytest.fixture
    def job_service(self, mock_job_repository):
        """JobService with injected repository dependencies"""
        # This will fail initially - JobService doesn't take repository parameters yet
        return JobService(job_repository=mock_job_repository)
    
    def test_get_or_create_active_job_uses_repository_to_find_existing(self, job_service, mock_job_repository):
        """Test get_or_create_active_job uses repository to find existing active job"""
        # Arrange
        property_id = 123
        existing_job = Job(id=1, description="Existing job", status="Active", property_id=property_id)
        mock_job_repository.find_active_job_by_property_id.return_value = existing_job
        
        # Act
        result = job_service.get_or_create_active_job(property_id)
        
        # Assert
        mock_job_repository.find_active_job_by_property_id.assert_called_once_with(property_id)
        assert result == existing_job
    
    def test_get_or_create_active_job_creates_new_when_none_exists(self, job_service, mock_job_repository):
        """Test get_or_create_active_job creates new job when no active job exists"""
        # Arrange
        property_id = 123
        mock_job_repository.find_active_job_by_property_id.return_value = None
        
        new_job = Job(id=2, description=f"New job for property {property_id}", status="Active", property_id=property_id)
        mock_job_repository.create.return_value = new_job
        
        # Act  
        result = job_service.get_or_create_active_job(property_id)
        
        # Assert
        mock_job_repository.find_active_job_by_property_id.assert_called_once_with(property_id)
        mock_job_repository.create.assert_called_once_with(
            description=f"New job for property {property_id}",
            property_id=property_id,
            status='Active'
        )
        assert result == new_job
    
    def test_add_job_uses_repository_create(self, job_service, mock_job_repository):
        """Test add_job uses repository.create instead of direct session operations"""
        # Arrange
        job_data = {
            'description': 'Test job',
            'property_id': 123,
            'status': 'Active'
        }
        created_job = Job(id=1, **job_data)
        mock_job_repository.create.return_value = created_job
        
        # Act
        result = job_service.add_job(**job_data)
        
        # Assert
        mock_job_repository.create.assert_called_once_with(**job_data)
        assert result == created_job
    
    def test_get_all_jobs_uses_repository(self, job_service, mock_job_repository):
        """Test get_all_jobs uses repository.get_all instead of direct query"""
        # Arrange
        jobs = [
            Job(id=1, description="Job 1"),
            Job(id=2, description="Job 2")
        ]
        mock_job_repository.get_all.return_value = jobs
        
        # Act
        result = job_service.get_all_jobs()
        
        # Assert
        mock_job_repository.get_all.assert_called_once()
        assert result == jobs
    
    def test_get_job_by_id_uses_repository(self, job_service, mock_job_repository):
        """Test get_job_by_id uses repository.get_by_id instead of session.get"""
        # Arrange
        job_id = 123
        job = Job(id=job_id, description="Test job")
        mock_job_repository.get_by_id.return_value = job
        
        # Act
        result = job_service.get_job_by_id(job_id)
        
        # Assert
        mock_job_repository.get_by_id.assert_called_once_with(job_id)
        assert result == job
    
    def test_update_job_uses_repository(self, job_service, mock_job_repository):
        """Test update_job uses repository.update instead of direct session commit"""
        # Arrange
        job = Job(id=1, description="Original")
        updates = {'description': 'Updated', 'status': 'In Progress'}
        updated_job = Job(id=1, description="Updated", status="In Progress")
        mock_job_repository.update.return_value = updated_job
        
        # Act
        result = job_service.update_job(job, **updates)
        
        # Assert
        mock_job_repository.update.assert_called_once_with(job, **updates)
        assert result == updated_job
    
    def test_delete_job_uses_repository(self, job_service, mock_job_repository):
        """Test delete_job uses repository.delete instead of direct session operations"""
        # Arrange
        job = Job(id=1, description="To be deleted")
        mock_job_repository.delete.return_value = True
        
        # Act
        result = job_service.delete_job(job)
        
        # Assert
        mock_job_repository.delete.assert_called_once_with(job)
        assert result is True


class TestJobServiceBackwardCompatibility:
    """Test that JobService maintains backward compatibility"""
    
    def test_job_service_constructor_accepts_repositories(self):
        """Test that JobService constructor now accepts repository parameters"""
        from services.job_service import JobService
        
        # Should successfully create with repository
        service = JobService(job_repository=Mock())
        assert service.repository is not None
    
    @pytest.mark.skip(reason="Backward compatibility removed - dependency injection is now required")
    def test_job_service_constructor_works_without_parameters(self):
        """Test that JobService still works without parameters (backward compatibility)"""
        from services.job_service import JobService
        
        # Should still work without parameters
        service = JobService()
        assert service.repository is not None
        # Should have created default repository
        assert hasattr(service, 'repository')
        assert service.repository.__class__.__name__ == 'JobRepository'