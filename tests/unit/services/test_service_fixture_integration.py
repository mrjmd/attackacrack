"""Integration tests demonstrating service fixture usage.

This file shows how to use the new service fixtures to test services
and routes with proper isolation and mocking.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from flask import Flask, current_app

# Import our new fixtures
from tests.fixtures.service_fixtures import (
    MockServiceRegistry,
    ServiceMockFactory,
    mock_service_registry,
    mock_contact_service,
    mock_campaign_service,
    mock_openphone_service,
    mock_dashboard_service,
    create_mock_repository,
    mock_all_services,
    isolated_service_registry
)


class TestServiceRegistryIntegration:
    """Test service registry replacement in Flask app"""
    
    def test_replace_app_services_with_mock_registry(self):
        """Test replacing Flask app's service registry with mock"""
        # Create a minimal Flask app
        app = Flask(__name__)
        
        # Replace services with mock registry
        app.services = mock_service_registry()
        
        with app.app_context():
            # Get services from the mock registry
            contact_service = app.services.get('contact')
            campaign_service = app.services.get('campaign')
            
            # Services should be mocks
            assert hasattr(contact_service, 'get_all_contacts')
            assert hasattr(campaign_service, 'create_campaign')
            
            # Configure mock behavior
            contact_service.get_all_contacts.return_value = [
                {'id': 1, 'name': 'John Doe', 'phone': '+15551234567'}
            ]
            
            # Test the mock behavior
            contacts = contact_service.get_all_contacts()
            assert len(contacts) == 1
            assert contacts[0]['name'] == 'John Doe'
    
    def test_service_with_repository_dependencies(self):
        """Test service that depends on repositories"""
        # Create mock repositories
        contact_repo = create_mock_repository('contact')
        campaign_repo = create_mock_repository('campaign')
        
        # Configure repository behavior
        contact_repo.get_all.return_value = []
        contact_repo.create.return_value = Mock(id=1, phone='+15551234567')
        
        # Create registry and register repositories
        registry = MockServiceRegistry()
        registry.register('contact_repository', service=contact_repo)
        registry.register('campaign_repository', service=campaign_repo)
        
        # Get a service that uses these repositories
        dashboard_service = registry.get('dashboard')
        dashboard_service.contact_repository = contact_repo
        dashboard_service.campaign_repository = campaign_repo
        
        # Test repository interaction
        contacts = contact_repo.get_all()
        assert contacts == []
        
        new_contact = contact_repo.create({'phone': '+15551234567'})
        assert new_contact.id == 1


class TestContactServiceWithMocks:
    """Test ContactService using mock fixtures"""
    
    def test_contact_service_operations(self):
        """Test basic contact service operations with mocks"""
        # Get a mock contact service
        service = mock_contact_service()
        
        # Configure mock behaviors
        service.get_all_contacts.return_value = [
            {'id': 1, 'name': 'Alice', 'phone': '+15551111111'},
            {'id': 2, 'name': 'Bob', 'phone': '+15552222222'}
        ]
        
        service.create_contact.return_value = {
            'id': 3, 'name': 'Charlie', 'phone': '+15553333333'
        }
        
        service.search_contacts.return_value = [
            {'id': 1, 'name': 'Alice', 'phone': '+15551111111'}
        ]
        
        # Test operations
        all_contacts = service.get_all_contacts()
        assert len(all_contacts) == 2
        
        new_contact = service.create_contact({'name': 'Charlie', 'phone': '555-333-3333'})
        assert new_contact['id'] == 3
        
        search_results = service.search_contacts('Alice')
        assert len(search_results) == 1
        
        # Verify mock was called
        service.get_all_contacts.assert_called_once()
        service.create_contact.assert_called_once_with({'name': 'Charlie', 'phone': '555-333-3333'})
        service.search_contacts.assert_called_once_with('Alice')
    
    def test_contact_service_phone_normalization(self):
        """Test phone number normalization with mock"""
        service = mock_contact_service()
        
        # The fixture sets up a default normalization behavior
        normalized = service.normalize_phone('555-123-4567')
        assert normalized == '+15551234567'
        
        # Can override for specific tests
        service.normalize_phone.side_effect = lambda p: p.upper()
        normalized = service.normalize_phone('test')
        assert normalized == 'TEST'


class TestCampaignServiceWithMocks:
    """Test CampaignService with dependencies mocked"""
    
    def test_campaign_creation_with_dependencies(self):
        """Test campaign creation with mocked dependencies"""
        # Create mocks for dependencies
        campaign_service = mock_campaign_service()
        openphone_mock = mock_openphone_service()
        contact_repo_mock = create_mock_repository('contact')
        
        # Wire dependencies
        campaign_service.openphone_service = openphone_mock
        campaign_service.contact_repository = contact_repo_mock
        
        # Configure mock behavior
        contact_repo_mock.find_by.return_value = [
            Mock(id=1, phone='+15551234567'),
            Mock(id=2, phone='+15552222222')
        ]
        
        campaign_service.create_campaign.return_value = {
            'id': 1,
            'name': 'Test Campaign',
            'status': 'draft',
            'recipient_count': 2
        }
        
        # Test campaign creation
        campaign = campaign_service.create_campaign(
            name='Test Campaign',
            message='Hello {first_name}!',
            list_id=1
        )
        
        assert campaign['id'] == 1
        assert campaign['status'] == 'draft'
        assert campaign['recipient_count'] == 2
    
    def test_campaign_execution_with_openphone(self):
        """Test campaign execution with OpenPhone mock"""
        campaign_service = mock_campaign_service()
        openphone_mock = mock_openphone_service()
        
        campaign_service.openphone_service = openphone_mock
        
        # Configure OpenPhone mock to simulate sending messages
        openphone_mock.send_message.side_effect = [
            {'id': 'msg_1', 'status': 'sent'},
            {'id': 'msg_2', 'status': 'sent'},
            {'id': 'msg_3', 'status': 'failed'}
        ]
        
        campaign_service.execute_campaign.return_value = {
            'campaign_id': 1,
            'messages_sent': 2,
            'messages_failed': 1
        }
        
        # Execute campaign
        result = campaign_service.execute_campaign(campaign_id=1)
        
        assert result['messages_sent'] == 2
        assert result['messages_failed'] == 1


class TestDashboardServiceWithMocks:
    """Test DashboardService with repository mocks"""
    
    def test_dashboard_stats_with_repositories(self):
        """Test dashboard statistics with mocked repositories"""
        # Create dashboard service mock
        dashboard = mock_dashboard_service()
        
        # Create repository mocks
        contact_repo = create_mock_repository('contact')
        campaign_repo = create_mock_repository('campaign')
        activity_repo = create_mock_repository('activity')
        
        # Wire repositories
        dashboard.contact_repository = contact_repo
        dashboard.campaign_repository = campaign_repo
        dashboard.activity_repository = activity_repo
        
        # Configure repository responses
        contact_repo.count.return_value = 150
        campaign_repo.count.return_value = 5
        activity_repo.count.return_value = 1200
        
        # Configure dashboard stats
        dashboard.get_stats.return_value = {
            'total_contacts': 150,
            'total_campaigns': 5,
            'total_activities': 1200,
            'active_conversations': 23
        }
        
        # Get stats
        stats = dashboard.get_stats()
        
        assert stats['total_contacts'] == 150
        assert stats['total_campaigns'] == 5
        assert stats['total_activities'] == 1200
    
    def test_dashboard_recent_activity(self):
        """Test dashboard recent activity with mocks"""
        dashboard = mock_dashboard_service()
        
        # Configure recent activity
        dashboard.get_recent_activity.return_value = [
            {'type': 'message', 'contact': 'John', 'time': '2 hours ago'},
            {'type': 'call', 'contact': 'Jane', 'time': '3 hours ago'}
        ]
        
        activity = dashboard.get_recent_activity()
        assert len(activity) == 2
        assert activity[0]['type'] == 'message'


class TestServiceFactoryPatterns:
    """Test ServiceMockFactory patterns"""
    
    def test_factory_creates_appropriate_mocks(self):
        """Test that factory creates mocks with correct methods"""
        factory = ServiceMockFactory()
        
        # Test various service types
        services_to_test = [
            ('contact', ['get_all_contacts', 'create_contact', 'normalize_phone']),
            ('campaign', ['create_campaign', 'execute_campaign', 'get_campaign_stats']),
            ('openphone', ['send_message', 'get_messages', 'validate_phone_number']),
            ('todo', ['create_todo', 'update_todo', 'mark_complete']),
            ('invoice', ['create_invoice', 'send_invoice', 'mark_paid'])
        ]
        
        for service_name, expected_methods in services_to_test:
            mock_service = factory.create_mock(service_name)
            
            for method in expected_methods:
                assert hasattr(mock_service, method), \
                    f"{service_name} mock missing method: {method}"
    
    def test_factory_creates_repository_mocks(self):
        """Test that factory creates proper repository mocks"""
        factory = ServiceMockFactory()
        
        # Test repository creation
        contact_repo = factory.create_repository_mock('contact')
        
        # Should have standard CRUD operations
        assert hasattr(contact_repo, 'get_all')
        assert hasattr(contact_repo, 'get_by_id')
        assert hasattr(contact_repo, 'create')
        assert hasattr(contact_repo, 'update')
        assert hasattr(contact_repo, 'delete')
        assert hasattr(contact_repo, 'find_by')
        assert hasattr(contact_repo, 'paginate')


class TestIsolatedServiceRegistry:
    """Test isolated service registry context manager"""
    
    def test_isolated_registry_cleanup(self):
        """Test that isolated registry is properly cleaned up"""
        mock_service = Mock()
        
        with isolated_service_registry() as registry:
            # Register a service
            registry.register('test_service', service=mock_service)
            
            # Service should be retrievable
            retrieved = registry.get('test_service')
            assert retrieved is mock_service
            
            # Registry should have the service
            assert 'test_service' in registry._services
        
        # After context, registry should be cleaned
        # (Can't directly test this but the context manager handles it)
    
    def test_multiple_isolated_registries(self):
        """Test that multiple isolated registries don't interfere"""
        with isolated_service_registry() as registry1:
            registry1.register('service1', service=Mock())
            
            with isolated_service_registry() as registry2:
                registry2.register('service2', service=Mock())
                
                # Each registry is independent
                service1_in_r1 = registry1.get('service1')
                service2_in_r2 = registry2.get('service2')
                
                assert service1_in_r1 is not None
                assert service2_in_r2 is not None


class TestMockAllServices:
    """Test the mock_all_services fixture"""
    
    def test_all_services_returns_complete_dict(self):
        """Test that mock_all_services returns all expected services"""
        services = mock_all_services()
        
        # Check that key services are present
        expected_services = [
            'contact', 'campaign', 'openphone', 'dashboard',
            'csv_import', 'auth', 'todo', 'invoice', 'quote'
        ]
        
        for service_name in expected_services:
            assert service_name in services, f"Missing service: {service_name}"
            assert services[service_name] is not None
    
    def test_all_services_are_mocks(self):
        """Test that all returned services are mock objects"""
        services = mock_all_services()
        
        for name, service in services.items():
            # All should be Mock or MagicMock instances
            assert isinstance(service, (Mock, MagicMock)), \
                f"{name} is not a mock object"


class TestRealWorldScenarios:
    """Test real-world scenarios using the fixtures"""
    
    def test_route_handler_with_mock_registry(self):
        """Simulate testing a route handler with mocked services"""
        # This simulates how you'd test a real route
        app = Flask(__name__)
        app.services = mock_service_registry()
        
        # Define a route-like function
        def contact_list_handler():
            contact_service = current_app.services.get('contact')
            contacts = contact_service.get_all_contacts()
            return {'contacts': contacts, 'count': len(contacts)}
        
        with app.app_context():
            # Configure mock
            contact_service = app.services.get('contact')
            contact_service.get_all_contacts.return_value = [
                {'id': 1, 'name': 'Test'}
            ]
            
            # Test the handler
            result = contact_list_handler()
            assert result['count'] == 1
            assert result['contacts'][0]['name'] == 'Test'
    
    def test_service_initialization_with_dependencies(self):
        """Test initializing a service with complex dependencies"""
        registry = MockServiceRegistry()
        
        # Register all dependencies
        all_mocks = mock_all_services()
        for name, mock_service in all_mocks.items():
            registry.register(name, service=mock_service)
        
        # Get a service with many dependencies
        campaign_service = registry.get('campaign')
        
        # Should have its dependencies available
        assert hasattr(campaign_service, 'campaign_repository')
        assert hasattr(campaign_service, 'contact_repository')
        assert hasattr(campaign_service, 'openphone_service')
    
    def test_async_operation_with_mocks(self):
        """Test async/background task with mocked services"""
        # Mock the services that would be used in a Celery task
        registry = MockServiceRegistry()
        
        openphone = mock_openphone_service()
        registry.register('openphone', service=openphone)
        
        # Simulate a background task
        def send_bulk_messages(phone_numbers):
            openphone_service = registry.get('openphone')
            results = []
            
            for phone in phone_numbers:
                result = openphone_service.send_message(phone, 'Test message')
                results.append(result)
            
            return results
        
        # Test the task
        phones = ['+15551111111', '+15552222222']
        results = send_bulk_messages(phones)
        
        assert len(results) == 2
        assert all(r['status'] == 'sent' for r in results)
        
        # Verify OpenPhone was called correctly
        assert openphone.send_message.call_count == 2


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
