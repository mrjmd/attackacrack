"""Tests for service registry fixtures - TDD Red Phase"""
import pytest
from unittest.mock import Mock, MagicMock, patch
import threading
from typing import Any, Dict

# Import the fixtures we're about to create
from tests.fixtures.service_fixtures import (
    MockServiceRegistry,
    ServiceMockFactory,
    create_mock_service,
    create_mock_repository,
    mock_service_registry,
    mock_contact_service,
    mock_campaign_service,
    mock_openphone_service,
    mock_dashboard_service,
    mock_csv_import_service,
    mock_all_services,
    isolated_service_registry
)


class TestMockServiceRegistry:
    """Test the MockServiceRegistry fixture"""
    
    def test_mock_registry_creation(self):
        """Test that MockServiceRegistry can be instantiated"""
        registry = MockServiceRegistry()
        assert registry is not None
        assert hasattr(registry, 'get')
        assert hasattr(registry, 'register')
        assert hasattr(registry, 'register_factory')
        assert hasattr(registry, 'register_singleton')
    
    def test_mock_registry_get_returns_mock(self):
        """Test that get() returns a mock service"""
        registry = MockServiceRegistry()
        service = registry.get('contact')
        assert service is not None
        assert isinstance(service, Mock)
    
    def test_mock_registry_get_caches_service(self):
        """Test that get() returns the same mock on repeated calls"""
        registry = MockServiceRegistry()
        service1 = registry.get('contact')
        service2 = registry.get('contact')
        assert service1 is service2
    
    def test_mock_registry_register_service(self):
        """Test that register() stores a service"""
        registry = MockServiceRegistry()
        mock_service = Mock()
        registry.register('custom_service', service=mock_service)
        
        retrieved = registry.get('custom_service')
        assert retrieved is mock_service
    
    def test_mock_registry_thread_safe(self):
        """Test that MockServiceRegistry is thread-safe"""
        registry = MockServiceRegistry()
        results = []
        
        def get_service():
            service = registry.get('contact')
            results.append(service)
        
        threads = [threading.Thread(target=get_service) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # All threads should get the same instance
        assert all(s is results[0] for s in results)
    
    def test_mock_registry_with_factory(self):
        """Test that register_factory() works with mock services"""
        registry = MockServiceRegistry()
        factory_called = []
        
        def factory():
            factory_called.append(True)
            return Mock()
        
        registry.register_factory('lazy_service', factory)
        service = registry.get('lazy_service')
        
        assert service is not None
        assert len(factory_called) == 1
        
        # Second call should not invoke factory again
        service2 = registry.get('lazy_service')
        assert service2 is service
        assert len(factory_called) == 1
    
    def test_mock_registry_validate_dependencies(self):
        """Test that validate_dependencies() returns no errors"""
        registry = MockServiceRegistry()
        errors = registry.validate_dependencies()
        assert errors == []
    
    def test_mock_registry_warmup(self):
        """Test that warmup() can be called without errors"""
        registry = MockServiceRegistry()
        registry.warmup(['contact', 'campaign', 'openphone'])
        # Should not raise any exceptions
    
    def test_mock_registry_get_initialization_order(self):
        """Test that get_initialization_order() returns expected services"""
        registry = MockServiceRegistry()
        order = registry.get_initialization_order()
        assert isinstance(order, list)
        # Should return the default service list
        assert 'contact' in order
        assert 'campaign' in order


class TestServiceMockFactory:
    """Test the ServiceMockFactory class"""
    
    def test_factory_creation(self):
        """Test that ServiceMockFactory can be instantiated"""
        factory = ServiceMockFactory()
        assert factory is not None
        assert hasattr(factory, 'create_mock')
        assert hasattr(factory, 'create_repository_mock')
        assert hasattr(factory, 'create_service_mock')
    
    def test_factory_create_contact_service_mock(self):
        """Test creating a mock ContactService"""
        factory = ServiceMockFactory()
        mock_service = factory.create_mock('contact')
        
        assert mock_service is not None
        assert hasattr(mock_service, 'get_all_contacts')
        assert hasattr(mock_service, 'create_contact')
        assert hasattr(mock_service, 'normalize_phone')
        
        # Test that methods can be called
        mock_service.get_all_contacts.return_value = []
        result = mock_service.get_all_contacts()
        assert result == []
    
    def test_factory_create_campaign_service_mock(self):
        """Test creating a mock CampaignService"""
        factory = ServiceMockFactory()
        mock_service = factory.create_mock('campaign')
        
        assert hasattr(mock_service, 'create_campaign')
        assert hasattr(mock_service, 'execute_campaign')
        assert hasattr(mock_service, 'get_campaign_stats')
    
    def test_factory_create_openphone_service_mock(self):
        """Test creating a mock OpenPhoneService"""
        factory = ServiceMockFactory()
        mock_service = factory.create_mock('openphone')
        
        assert hasattr(mock_service, 'send_message')
        assert hasattr(mock_service, 'get_messages')
        assert hasattr(mock_service, 'get_contacts')
        
        # Test with return values
        mock_service.send_message.return_value = {'id': '123', 'status': 'sent'}
        result = mock_service.send_message('+15551234567', 'Test message')
        assert result['id'] == '123'
    
    def test_factory_create_repository_mock(self):
        """Test creating a mock repository"""
        factory = ServiceMockFactory()
        mock_repo = factory.create_repository_mock('contact')
        
        assert hasattr(mock_repo, 'get_all')
        assert hasattr(mock_repo, 'get_by_id')
        assert hasattr(mock_repo, 'create')
        assert hasattr(mock_repo, 'update')
        assert hasattr(mock_repo, 'delete')
        assert hasattr(mock_repo, 'find_by')
    
    def test_factory_create_unknown_service(self):
        """Test that unknown service names return a generic mock"""
        factory = ServiceMockFactory()
        mock_service = factory.create_mock('unknown_service')
        
        assert mock_service is not None
        assert isinstance(mock_service, Mock)
    
    def test_factory_with_custom_attributes(self):
        """Test creating mocks with custom attributes"""
        factory = ServiceMockFactory()
        custom_attrs = {
            'custom_method': Mock(return_value='custom_result'),
            'custom_property': 'test_value'
        }
        
        mock_service = factory.create_service_mock('test', custom_attrs=custom_attrs)
        assert mock_service.custom_method() == 'custom_result'
        assert mock_service.custom_property == 'test_value'


class TestServiceFixtureFunctions:
    """Test individual fixture functions"""
    
    def test_create_mock_service(self):
        """Test the create_mock_service helper function"""
        mock_service = create_mock_service('contact')
        assert mock_service is not None
        assert hasattr(mock_service, 'get_all_contacts')
    
    def test_create_mock_repository(self):
        """Test the create_mock_repository helper function"""
        mock_repo = create_mock_repository('contact')
        assert mock_repo is not None
        assert hasattr(mock_repo, 'get_all')
        assert hasattr(mock_repo, 'create')
    
    def test_mock_service_registry_fixture(self):
        """Test the mock_service_registry fixture function"""
        registry = mock_service_registry()
        assert isinstance(registry, MockServiceRegistry)
        
        # Test that it has pre-registered services
        contact_service = registry.get('contact')
        assert contact_service is not None
    
    def test_mock_contact_service_fixture(self):
        """Test the mock_contact_service fixture"""
        service = mock_contact_service()
        
        # Test default return values
        assert hasattr(service, 'get_all_contacts')
        assert hasattr(service, 'create_contact')
        
        # Should have some default behaviors
        service.normalize_phone.return_value = '+15551234567'
        normalized = service.normalize_phone('555-123-4567')
        assert normalized == '+15551234567'
    
    def test_mock_campaign_service_fixture(self):
        """Test the mock_campaign_service fixture"""
        service = mock_campaign_service()
        
        assert hasattr(service, 'create_campaign')
        assert hasattr(service, 'execute_campaign')
        
        # Test with dependencies
        assert hasattr(service, 'campaign_repository')
        assert hasattr(service, 'openphone_service')
    
    def test_mock_all_services_fixture(self):
        """Test the mock_all_services fixture that returns all mocked services"""
        services = mock_all_services()
        
        assert isinstance(services, dict)
        assert 'contact' in services
        assert 'campaign' in services
        assert 'openphone' in services
        assert 'dashboard' in services
        
        # All services should be mocks
        for name, service in services.items():
            assert isinstance(service, Mock), f"{name} is not a Mock"
    
    def test_isolated_service_registry_fixture(self):
        """Test the isolated_service_registry context manager"""
        with isolated_service_registry() as registry:
            assert registry is not None
            
            # Should be able to register and retrieve services
            mock_service = Mock()
            registry.register('test_service', service=mock_service)
            
            retrieved = registry.get('test_service')
            assert retrieved is mock_service
        
        # After context, registry should be cleaned up
        # (can't test this directly but context manager should handle it)


class TestServiceMockIntegration:
    """Test integration between mock services"""
    
    def test_mock_services_can_interact(self):
        """Test that mock services can be wired together"""
        registry = MockServiceRegistry()
        
        # Create interdependent services
        contact_service = registry.get('contact')
        campaign_service = registry.get('campaign')
        
        # Set up interaction
        contact_service.get_all_contacts.return_value = [
            {'id': 1, 'phone': '+15551234567'}
        ]
        
        campaign_service.create_campaign.return_value = {
            'id': 1,
            'name': 'Test Campaign',
            'contacts': contact_service.get_all_contacts()
        }
        
        result = campaign_service.create_campaign('Test Campaign')
        assert len(result['contacts']) == 1
    
    def test_mock_registry_with_repositories(self):
        """Test that registry can handle both services and repositories"""
        registry = MockServiceRegistry()
        
        # Register repository mocks
        contact_repo = create_mock_repository('contact')
        campaign_repo = create_mock_repository('campaign')
        
        registry.register('contact_repository', service=contact_repo)
        registry.register('campaign_repository', service=campaign_repo)
        
        # Create service with repository dependencies
        factory = ServiceMockFactory()
        dashboard_service = factory.create_mock('dashboard')
        dashboard_service.contact_repository = contact_repo
        dashboard_service.campaign_repository = campaign_repo
        
        registry.register('dashboard', service=dashboard_service)
        
        # Verify wiring
        service = registry.get('dashboard')
        assert service.contact_repository is contact_repo
        assert service.campaign_repository is campaign_repo
    
    def test_mock_services_thread_safety(self):
        """Test that mock services are thread-safe"""
        registry = MockServiceRegistry()
        results = []
        errors = []
        
        def worker(service_name):
            try:
                service = registry.get(service_name)
                # Simulate some work
                if hasattr(service, 'get_all'):
                    service.get_all()
                results.append((service_name, service))
            except Exception as e:
                errors.append(e)
        
        # Create multiple threads accessing different services
        services = ['contact', 'campaign', 'openphone', 'dashboard']
        threads = []
        
        for _ in range(5):  # 5 rounds
            for service_name in services:
                t = threading.Thread(target=worker, args=(service_name,))
                threads.append(t)
                t.start()
        
        for t in threads:
            t.join()
        
        assert len(errors) == 0
        assert len(results) == 20  # 5 rounds * 4 services


class TestFixtureUsagePatterns:
    """Test common usage patterns for the fixtures"""
    
    def test_pattern_unit_test_with_mock_registry(self):
        """Example pattern: Unit testing a route with mock registry"""
        # Simulate a route test
        from flask import Flask
        app = Flask(__name__)
        
        with app.app_context():
            # Replace app.services with mock
            app.services = MockServiceRegistry()
            
            # Configure specific mock behavior
            contact_service = app.services.get('contact')
            contact_service.get_all_contacts.return_value = [
                {'id': 1, 'name': 'Test Contact'}
            ]
            
            # Test route logic would go here
            contacts = contact_service.get_all_contacts()
            assert len(contacts) == 1
    
    def test_pattern_integration_test_with_partial_mocks(self):
        """Example pattern: Integration test with some services mocked"""
        registry = MockServiceRegistry()
        
        # Use real service for some, mocks for others
        real_contact_service = Mock()  # Would be real service
        mock_openphone = mock_openphone_service()
        
        registry.register('contact', service=real_contact_service)
        registry.register('openphone', service=mock_openphone)
        
        # Test with mixed real/mock services
        campaign_service = registry.get('campaign')
        campaign_service.openphone_service = mock_openphone
        
        # Verify we can test without external API calls
        mock_openphone.send_message.return_value = {'status': 'sent'}
        result = mock_openphone.send_message('+15551234567', 'Test')
        assert result['status'] == 'sent'
    
    def test_pattern_fixture_composition(self):
        """Example pattern: Composing multiple fixtures"""
        # Get all services as a dict
        services = mock_all_services()
        
        # Create registry and register all services
        registry = MockServiceRegistry()
        for name, service in services.items():
            registry.register(name, service=service)
        
        # Now registry has all services pre-configured
        assert registry.get('contact') is services['contact']
        assert registry.get('campaign') is services['campaign']
