"""
Integration tests for Campaign Template feature
Tests the full workflow including service, repository, and database
Following TDD - these tests should FAIL initially (Red phase)
"""

import pytest
from datetime import datetime, timedelta
from flask import Flask
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# These imports will fail initially - that's expected in TDD
from app import create_app
from crm_database import db, CampaignTemplate, Contact, Campaign
from services.campaign_template_service import (
    CampaignTemplateService,
    TemplateValidationError,
    TemplateNotFoundError
)
from services.enums import TemplateCategory, TemplateStatus
from repositories.campaign_template_repository import CampaignTemplateRepository
from repositories.contact_repository import ContactRepository


class TestCampaignTemplateIntegration:
    """Integration tests for Campaign Template feature"""
    
    @pytest.fixture
    def app(self):
        """Create test application"""
        app = create_app('testing')
        
        with app.app_context():
            db.create_all()
            yield app
            db.session.remove()
            db.drop_all()
    
    @pytest.fixture
    def client(self, app):
        """Create test client"""
        return app.test_client()
    
    @pytest.fixture
    def authenticated_client(self, client):
        """Create authenticated test client"""
        # Mock authentication
        with client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['user_role'] = 'admin'
        return client
    
    @pytest.fixture
    def db_session(self, app):
        """Create database session"""
        with app.app_context():
            yield db.session
    
    @pytest.fixture
    def template_repository(self, db_session):
        """Create template repository"""
        return CampaignTemplateRepository(session=db_session)
    
    @pytest.fixture
    def contact_repository(self, app):
        """Get contact repository from app registry"""
        with app.app_context():
            return app.services.get('contact_repository')
    
    @pytest.fixture
    def template_service(self, app):
        """Create template service from app registry"""
        with app.app_context():
            return app.services.get('campaign_template')
    
    @pytest.fixture
    def sample_contact(self, app, db_session):
        """Create a sample contact in database"""
        with app.app_context():
            contact_repo = app.services.get('contact_repository')
            contact = contact_repo.create(
                first_name='John',
                last_name='Doe',
                phone='+16175551234',
                email='john@example.com'
            )
            contact_repo.commit()
            
            # Refresh from session to ensure it's attached
            db_session.refresh(contact)
            
            # Add mock property attributes for testing
            # These would normally come from related Property model
            contact.property_address = '123 Main St, Boston, MA'
            contact.property_type = 'Single Family'
            contact.property_value = 500000
            
            # Ensure ID is accessible
            contact_id = contact.id
            
            return contact
    
    @pytest.fixture
    def sample_template(self, template_repository):
        """Create a sample template in database"""
        template = template_repository.create(
            name='Welcome Template',
            content='Hi {first_name}, welcome to Attack-a-Crack!',
            category=TemplateCategory.PROMOTIONAL,
            status=TemplateStatus.DRAFT,
            variables=['first_name']
        )
        template_repository.commit()
        return template
    
    # END-TO-END WORKFLOW Tests
    
    def test_complete_template_lifecycle(self, template_service, db_session):
        """Test complete template lifecycle from creation to usage"""
        # 1. Create template
        template = template_service.create_template(
            name='Lifecycle Test',
            content='Hello {first_name}, your {property_type} is amazing!',
            category=TemplateCategory.PROMOTIONAL,
            description='Test template for lifecycle'
        )
        assert template['id'] is not None
        assert template['status'] == TemplateStatus.DRAFT.value
        assert template['variables'] == ['first_name', 'property_type']
        
        # 2. Approve template
        approved = template_service.approve_template(template['id'], approved_by='admin')
        assert approved['status'] == TemplateStatus.APPROVED.value
        assert approved['approved_by'] == 'admin'
        assert approved['approved_at'] is not None
        
        # 3. Activate template
        activated = template_service.activate_template(template['id'])
        assert activated['status'] == TemplateStatus.ACTIVE.value
        assert activated['activated_at'] is not None
        
        # 4. Use template in campaign (track usage)
        template_service.track_usage(template['id'], campaign_id=1)
        updated = template_service.get_template(template['id'])
        assert updated['usage_count'] == 1
        assert updated['last_used_at'] is not None
        
        # 5. Create new version
        new_version = template_service.update_template(
            template['id'],
            content='Updated: Hello {first_name}, your {property_type} at {property_address} is amazing!',
            create_version=True
        )
        assert new_version['version'] == 2
        assert new_version['parent_id'] == template['id']
        
        # 6. Get all versions
        versions = template_service.get_template_versions(template['id'])
        assert len(versions) == 2
        assert versions[0]['version'] == 1
        assert versions[1]['version'] == 2
    
    def test_template_with_contact_substitution(self, template_service, app):
        """Test template variable substitution with real contact data"""
        with app.app_context():
            # Create a contact
            contact_repo = app.services.get('contact_repository')
            contact = contact_repo.create(
                first_name='John',
                last_name='Doe',
                phone='+16175551234',
                email='john@example.com'
            )
            contact_repo.commit()
            
            # Add mock property attributes
            contact.property_address = '123 Main St, Boston, MA'
            contact.property_type = 'Single Family'
            contact.property_value = 500000
            
            # Create template with multiple variables
            template = template_service.create_template(
                name='Contact Test',
                content='Dear {first_name} {last_name}, your {property_type} at {property_address} valued at ${property_value} is perfect for our services.',
                category=TemplateCategory.FOLLOW_UP
            )
            
            # Preview with contact
            preview = template_service.preview_template(template['id'], contact_id=contact.id)
            
            # Verify substitution
            assert 'John Doe' in preview['preview']
            assert '123 Main St, Boston, MA' in preview['preview']
            assert 'Single Family' in preview['preview']
            assert '500000' in preview['preview']
            assert preview['variables_used'] == ['first_name', 'last_name', 'property_type', 'property_address', 'property_value']
            assert 'missing_variables' not in preview or len(preview['missing_variables']) == 0
    
    def test_bulk_template_operations(self, template_service, db_session):
        """Test bulk operations on templates"""
        # Create multiple templates
        templates = []
        for i in range(5):
            template = template_service.create_template(
                name=f'Bulk Template {i}',
                content=f'Template {i} content: Hello {{first_name}}!',
                category=TemplateCategory.REMINDER
            )
            templates.append(template)
        
        # Bulk approve
        template_ids = [t['id'] for t in templates]
        result = template_service.bulk_update_status(template_ids[:3], TemplateStatus.APPROVED)
        assert result['updated'] == 3
        assert result['failed'] == 0
        
        # Verify status changes
        for i in range(3):
            updated = template_service.get_template(templates[i]['id'])
            assert updated['status'] == TemplateStatus.APPROVED.value
        
        # Templates 3-4 should still be draft
        for i in range(3, 5):
            unchanged = template_service.get_template(templates[i]['id'])
            assert unchanged['status'] == TemplateStatus.DRAFT.value
    
    # API ENDPOINT Tests
    
    def test_template_api_create(self, authenticated_client):
        """Test creating template via API"""
        response = authenticated_client.post('/api/templates', json={
            'name': 'API Template',
            'content': 'Hi {first_name}, this is a test.',
            'category': 'promotional',
            'description': 'Created via API'
        })
        
        assert response.status_code == 201
        data = response.get_json()
        assert data['name'] == 'API Template'
        assert data['id'] is not None
        assert data['status'] == 'draft'
        assert data['variables'] == ['first_name']
    
    def test_template_api_list(self, authenticated_client, template_service):
        """Test listing templates via API"""
        # Create test templates
        for i in range(3):
            template_service.create_template(
                name=f'List Test {i}',
                content='Test content {first_name}',
                category=TemplateCategory.PROMOTIONAL if i % 2 == 0 else TemplateCategory.REMINDER
            )
        
        # Get all templates
        response = authenticated_client.get('/api/templates')
        assert response.status_code == 200
        data = response.get_json()
        assert data['total'] >= 3
        assert len(data['items']) >= 3
        
        # Filter by category
        response = authenticated_client.get('/api/templates?category=promotional')
        assert response.status_code == 200
        data = response.get_json()
        assert all(t['category'] == 'promotional' for t in data['items'])
    
    def test_template_api_preview(self, authenticated_client, sample_template, sample_contact):
        """Test template preview via API"""
        response = authenticated_client.post(f'/api/templates/{sample_template.id}/preview', json={
            'contact_id': sample_contact.id
        })
        
        assert response.status_code == 200
        data = response.get_json()
        assert 'preview' in data
        assert 'John' in data['preview']
        assert data['template_id'] == sample_template.id
        assert data['contact_id'] == sample_contact.id
    
    def test_template_api_approve(self, authenticated_client, sample_template):
        """Test template approval via API"""
        response = authenticated_client.post(f'/api/templates/{sample_template.id}/approve')
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['status'] == 'approved'
        assert data['approved_by'] is not None
        assert data['approved_at'] is not None
    
    def test_template_api_clone(self, authenticated_client, sample_template):
        """Test template cloning via API"""
        response = authenticated_client.post(f'/api/templates/{sample_template.id}/clone', json={
            'name': 'Cloned Template'
        })
        
        assert response.status_code == 201
        data = response.get_json()
        assert data['name'] == 'Cloned Template'
        assert data['content'] == sample_template.content
        assert data['id'] != sample_template.id
        assert data['parent_id'] == sample_template.id
    
    # SEARCH AND FILTER Tests
    
    def test_search_templates(self, template_service):
        """Test template search functionality"""
        # Create templates with searchable content
        template_service.create_template(
            name='Property Reminder',
            content='Reminder about your property inspection',
            description='Send property inspection reminders',
            category=TemplateCategory.REMINDER
        )
        
        template_service.create_template(
            name='Welcome Message',
            content='Welcome to our property management service',
            description='Initial welcome for new clients',
            category=TemplateCategory.PROMOTIONAL
        )
        
        template_service.create_template(
            name='Follow Up',
            content='Following up on our previous conversation',
            description='General follow up template',
            category=TemplateCategory.FOLLOW_UP
        )
        
        # Search for "property"
        results = template_service.search_templates('property')
        assert len(results) >= 2
        assert any('property' in t['name'].lower() or 'property' in t['content'].lower() for t in results)
        
        # Search for "welcome"
        results = template_service.search_templates('welcome')
        assert len(results) >= 1
        assert any('welcome' in t['name'].lower() or 'welcome' in t['content'].lower() for t in results)
    
    def test_filter_templates_by_status(self, template_service):
        """Test filtering templates by status"""
        # Create templates with different statuses
        draft = template_service.create_template(
            name='Draft Template',
            content='Draft content',
            category=TemplateCategory.PROMOTIONAL
        )
        
        approved = template_service.create_template(
            name='Approved Template',
            content='Approved content',
            category=TemplateCategory.PROMOTIONAL
        )
        template_service.approve_template(approved['id'], approved_by='admin')
        
        active = template_service.create_template(
            name='Active Template',
            content='Active content',
            category=TemplateCategory.PROMOTIONAL
        )
        template_service.approve_template(active['id'], approved_by='admin')
        template_service.activate_template(active['id'])
        
        # Filter by status
        draft_templates = template_service.list_templates(status=TemplateStatus.DRAFT)
        assert any(t['id'] == draft['id'] for t in draft_templates['items'])
        assert not any(t['id'] == active['id'] for t in draft_templates['items'])
        
        active_templates = template_service.list_templates(status=TemplateStatus.ACTIVE)
        assert any(t['id'] == active['id'] for t in active_templates['items'])
        assert not any(t['id'] == draft['id'] for t in active_templates['items'])
    
    # VALIDATION Tests
    
    def test_template_validation_errors(self, template_service):
        """Test various validation error scenarios"""
        # Empty content
        with pytest.raises(TemplateValidationError) as exc:
            template_service.create_template(
                name='Empty',
                content='',
                category=TemplateCategory.PROMOTIONAL
            )
        assert 'Content cannot be empty' in str(exc.value)
        
        # Invalid variable syntax
        with pytest.raises(TemplateValidationError) as exc:
            template_service.create_template(
                name='Invalid Vars',
                content='Hello {first_name and {last_name}',  # Unclosed bracket
                category=TemplateCategory.PROMOTIONAL
            )
        assert 'Invalid variable syntax' in str(exc.value)
        
        # Variable name with invalid characters
        with pytest.raises(TemplateValidationError) as exc:
            template_service.create_template(
                name='Bad Var Name',
                content='Hello {first-name}',  # Hyphen not allowed
                category=TemplateCategory.PROMOTIONAL
            )
        assert 'Invalid variable name' in str(exc.value)
    
    # STATISTICS Tests
    
    def test_template_usage_statistics(self, template_service, db_session):
        """Test template usage tracking and statistics"""
        # Create and use template
        template = template_service.create_template(
            name='Stats Test',
            content='Hello {first_name}',
            category=TemplateCategory.PROMOTIONAL
        )
        
        # Activate template
        template_service.approve_template(template['id'], approved_by='admin')
        template_service.activate_template(template['id'])
        
        # Simulate usage
        for i in range(10):
            template_service.track_usage(template['id'], campaign_id=i+1)
        
        # Get statistics
        stats = template_service.get_template_statistics(template['id'])
        
        assert stats['template_id'] == template['id']
        assert stats['usage_count'] == 10
        assert 'days_since_created' in stats
        assert 'days_since_last_used' in stats
        assert stats['days_since_last_used'] == 0  # Used just now
    
    # PERFORMANCE Tests
    
    def test_bulk_template_creation_performance(self, template_service, db_session):
        """Test performance of bulk template operations"""
        import time
        
        start_time = time.time()
        
        # Create 100 templates
        templates = []
        for i in range(100):
            template = template_service.create_template(
                name=f'Perf Test {i}',
                content=f'Template {i}: Hello {{first_name}}, {{last_name}}!',
                category=TemplateCategory.PROMOTIONAL if i % 3 == 0 else TemplateCategory.REMINDER
            )
            templates.append(template)
        
        creation_time = time.time() - start_time
        
        # Should complete in reasonable time (< 5 seconds)
        assert creation_time < 5.0
        
        # Test pagination performance
        start_time = time.time()
        
        # Get paginated results
        page1 = template_service.list_templates(page=1, per_page=20)
        page2 = template_service.list_templates(page=2, per_page=20)
        page3 = template_service.list_templates(page=3, per_page=20)
        
        pagination_time = time.time() - start_time
        
        # Pagination should be fast (< 1 second)
        assert pagination_time < 1.0
        assert page1['total'] >= 100
        assert len(page1['items']) == 20
    
    # CONCURRENCY Tests
    
    def test_concurrent_template_updates(self, template_service, db_session):
        """Test handling concurrent updates to same template"""
        # Create template
        template = template_service.create_template(
            name='Concurrent Test',
            content='Original content',
            category=TemplateCategory.PROMOTIONAL
        )
        
        # Simulate concurrent updates
        # In real scenario, these would be from different sessions
        try:
            # First update
            template_service.update_template(template['id'], content='Update 1')
            
            # Second update (should succeed as it's after first)
            result = template_service.update_template(template['id'], content='Update 2')
            
            assert result['content'] == 'Update 2'
            
        except Exception as e:
            # Should handle gracefully
            assert 'concurrent' in str(e).lower() or 'conflict' in str(e).lower()
    
    # CLEANUP Tests
    
    def test_cascade_delete_template_versions(self, template_service, db_session):
        """Test that deleting parent template handles versions correctly"""
        # Create template with versions
        template = template_service.create_template(
            name='Parent Template',
            content='Version 1',
            category=TemplateCategory.PROMOTIONAL
        )
        
        # Create versions
        for i in range(2, 4):
            template_service.update_template(
                template['id'],
                content=f'Version {i}',
                create_version=True
            )
        
        # Soft delete should preserve versions
        template_service.soft_delete_template(template['id'])
        versions = template_service.get_template_versions(template['id'])
        assert len(versions) >= 1  # Versions should still exist
        
        # Hard delete (if implemented) would remove all
        # This depends on cascade rules in database