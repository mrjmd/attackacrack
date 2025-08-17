"""
Comprehensive tests for enhanced service registry with lazy loading
"""

import pytest
from unittest.mock import Mock, MagicMock, call
import threading
import time
from services.service_registry_enhanced import (
    ServiceRegistryEnhanced,
    ServiceLifecycle,
    ServiceDescriptor,
    create_enhanced_registry,
    service
)


class TestServiceRegistryEnhanced:
    """Test suite for enhanced service registry"""
    
    @pytest.fixture
    def registry(self):
        """Create a fresh registry instance"""
        return ServiceRegistryEnhanced()
    
    def test_init(self, registry):
        """Test registry initialization"""
        assert registry._descriptors == {}
        assert registry._scoped_instances == {}
        assert registry._initialization_stack == []
        assert registry.list_services() == []
    
    def test_register_service_instance(self, registry):
        """Test registering a pre-instantiated service"""
        service_instance = Mock()
        registry.register('test_service', service=service_instance)
        
        assert registry.has('test_service')
        assert registry.get('test_service') is service_instance
    
    def test_register_factory(self, registry):
        """Test registering a service factory"""
        factory = Mock(return_value="service_instance")
        registry.register_factory('lazy_service', factory)
        
        assert registry.has('lazy_service')
        
        # Factory not called until first get
        factory.assert_not_called()
        
        # Get triggers factory
        result = registry.get('lazy_service')
        assert result == "service_instance"
        factory.assert_called_once()
        
        # Second get returns cached instance (singleton)
        result2 = registry.get('lazy_service')
        assert result2 == "service_instance"
        factory.assert_called_once()  # Still only called once
    
    def test_singleton_lifecycle(self, registry):
        """Test singleton lifecycle management"""
        counter = {'value': 0}
        
        def factory():
            counter['value'] += 1
            return f"instance_{counter['value']}"
        
        registry.register_singleton('singleton', factory)
        
        # Multiple gets return same instance
        instance1 = registry.get('singleton')
        instance2 = registry.get('singleton')
        instance3 = registry.get('singleton')
        
        assert instance1 == instance2 == instance3 == "instance_1"
        assert counter['value'] == 1
    
    def test_transient_lifecycle(self, registry):
        """Test transient lifecycle management"""
        counter = {'value': 0}
        
        def factory():
            counter['value'] += 1
            return f"instance_{counter['value']}"
        
        registry.register_transient('transient', factory)
        
        # Each get creates new instance
        instance1 = registry.get('transient')
        instance2 = registry.get('transient')
        instance3 = registry.get('transient')
        
        assert instance1 == "instance_1"
        assert instance2 == "instance_2"
        assert instance3 == "instance_3"
        assert counter['value'] == 3
    
    def test_scoped_lifecycle(self, registry):
        """Test scoped lifecycle management"""
        counter = {'value': 0}
        
        def factory():
            counter['value'] += 1
            return f"instance_{counter['value']}"
        
        registry.register('scoped', factory=factory, lifecycle=ServiceLifecycle.SCOPED)
        
        # Same scope returns same instance
        instance1 = registry.get('scoped', scope_id='scope1')
        instance2 = registry.get('scoped', scope_id='scope1')
        assert instance1 == instance2 == "instance_1"
        
        # Different scope creates new instance
        instance3 = registry.get('scoped', scope_id='scope2')
        assert instance3 == "instance_2"
        
        # Default scope
        instance4 = registry.get('scoped')
        instance5 = registry.get('scoped')
        assert instance4 == instance5 == "instance_3"
        
        assert counter['value'] == 3
    
    def test_dependency_injection(self, registry):
        """Test dependency injection in factories"""
        # Register dependencies
        db_service = Mock(name='db')
        cache_service = Mock(name='cache')
        
        registry.register('db', service=db_service)
        registry.register('cache', service=cache_service)
        
        # Register service with dependencies
        def app_factory(db, cache):
            app = Mock()
            app.db = db
            app.cache = cache
            return app
        
        registry.register_factory(
            'app',
            app_factory,
            dependencies=['db', 'cache']
        )
        
        # Get service - dependencies should be injected
        app = registry.get('app')
        
        assert app.db is db_service
        assert app.cache is cache_service
    
    def test_circular_dependency_detection(self, registry):
        """Test circular dependency detection"""
        # Create circular dependency: A -> B -> C -> A
        registry.register_factory(
            'service_a',
            lambda service_b: Mock(),
            dependencies=['service_b']
        )
        registry.register_factory(
            'service_b',
            lambda service_c: Mock(),
            dependencies=['service_c']
        )
        registry.register_factory(
            'service_c',
            lambda service_a: Mock(),
            dependencies=['service_a']
        )
        
        with pytest.raises(RuntimeError, match="Circular dependency detected"):
            registry.get('service_a')
    
    def test_missing_dependency(self, registry):
        """Test error when dependency is missing"""
        registry.register_factory(
            'service',
            lambda missing_dep: Mock(),
            dependencies=['missing_dep']
        )
        
        with pytest.raises(ValueError, match="Service 'missing_dep' is not registered"):
            registry.get('service')
    
    def test_thread_safety(self, registry):
        """Test thread-safe singleton initialization"""
        initialization_count = {'value': 0}
        initialization_delay = 0.1
        
        def slow_factory():
            initialization_count['value'] += 1
            time.sleep(initialization_delay)
            return f"instance_{initialization_count['value']}"
        
        registry.register_singleton('thread_safe', slow_factory)
        
        results = []
        
        def get_service():
            results.append(registry.get('thread_safe'))
        
        # Start multiple threads
        threads = [threading.Thread(target=get_service) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # All threads should get same instance
        assert all(r == results[0] for r in results)
        # Factory should only be called once
        assert initialization_count['value'] == 1
    
    def test_tags(self, registry):
        """Test service tagging and filtering"""
        registry.register('db_service', service=Mock(), tags={'database', 'persistence'})
        registry.register('cache_service', service=Mock(), tags={'cache', 'persistence'})
        registry.register('api_service', service=Mock(), tags={'api', 'external'})
        
        # Get all persistence services
        persistence_services = registry.get_all_by_tag('persistence')
        assert len(persistence_services) == 2
        assert 'db_service' in persistence_services
        assert 'cache_service' in persistence_services
        
        # Get all API services
        api_services = registry.get_all_by_tag('api')
        assert len(api_services) == 1
        assert 'api_service' in api_services
    
    def test_reset_service(self, registry):
        """Test resetting individual service"""
        counter = {'value': 0}
        
        def factory():
            counter['value'] += 1
            return f"instance_{counter['value']}"
        
        registry.register_singleton('resettable', factory)
        
        # Get initial instance
        instance1 = registry.get('resettable')
        assert instance1 == "instance_1"
        
        # Reset service
        registry.reset_service('resettable')
        
        # Get new instance
        instance2 = registry.get('resettable')
        assert instance2 == "instance_2"
        assert counter['value'] == 2
    
    def test_clear_scope(self, registry):
        """Test clearing scoped instances"""
        counter = {'value': 0}
        
        def factory():
            counter['value'] += 1
            return f"instance_{counter['value']}"
        
        registry.register('scoped', factory=factory, lifecycle=ServiceLifecycle.SCOPED)
        
        # Create instances in scope
        instance1 = registry.get('scoped', scope_id='test_scope')
        assert instance1 == "instance_1"
        
        # Clear scope
        registry.clear_scope('test_scope')
        
        # Get creates new instance
        instance2 = registry.get('scoped', scope_id='test_scope')
        assert instance2 == "instance_2"
    
    def test_validate_dependencies(self, registry):
        """Test dependency validation"""
        registry.register_factory('service_a', Mock, dependencies=['service_b'])
        registry.register_factory('service_b', Mock, dependencies=['service_c'])
        
        # Validate - should find missing service_c
        errors = registry.validate_dependencies()
        assert len(errors) == 1
        assert "service_b' depends on unregistered service 'service_c'" in errors[0]
        
        # Register missing dependency
        registry.register('service_c', service=Mock())
        
        # Validate again - should be clean
        errors = registry.validate_dependencies()
        assert errors == []
    
    def test_get_dependency_graph(self, registry):
        """Test getting dependency graph"""
        registry.register_factory('a', Mock, dependencies=['b', 'c'])
        registry.register_factory('b', Mock, dependencies=['c'])
        registry.register_factory('c', Mock, dependencies=[])
        
        graph = registry.get_dependency_graph()
        
        assert graph == {
            'a': ['b', 'c'],
            'b': ['c'],
            'c': []
        }
    
    def test_get_initialization_order(self, registry):
        """Test topological sort for initialization order"""
        # Create dependency chain: app -> service -> repository -> database
        registry.register('database', service=Mock())
        registry.register_factory('repository', Mock, dependencies=['database'])
        registry.register_factory('service', Mock, dependencies=['repository'])
        registry.register_factory('app', Mock, dependencies=['service'])
        
        order = registry.get_initialization_order()
        
        # Database should come before repository, repository before service, etc.
        assert order.index('database') < order.index('repository')
        assert order.index('repository') < order.index('service')
        assert order.index('service') < order.index('app')
    
    def test_warmup(self, registry):
        """Test service warmup"""
        factory_calls = []
        
        def make_factory(name):
            def factory():
                factory_calls.append(name)
                return Mock()
            return factory
        
        # Register services with dependencies
        registry.register_singleton('db', make_factory('db'))
        registry.register_singleton('cache', make_factory('cache'))
        registry.register_singleton(
            'service',
            make_factory('service'),
            dependencies=['db', 'cache']
        )
        registry.register_transient('transient', make_factory('transient'))
        
        # Warmup singletons
        registry.warmup()
        
        # Singletons should be initialized
        assert 'db' in factory_calls
        assert 'cache' in factory_calls
        assert 'service' in factory_calls
        # Transient should not be warmed up
        assert 'transient' not in factory_calls
    
    def test_warmup_specific_services(self, registry):
        """Test warming up specific services"""
        factory_calls = []
        
        def make_factory(name):
            def factory():
                factory_calls.append(name)
                return Mock()
            return factory
        
        registry.register_singleton('service1', make_factory('service1'))
        registry.register_singleton('service2', make_factory('service2'))
        registry.register_singleton('service3', make_factory('service3'))
        
        # Warmup only specific services
        registry.warmup(['service1', 'service3'])
        
        assert 'service1' in factory_calls
        assert 'service2' not in factory_calls
        assert 'service3' in factory_calls
    
    def test_get_service_info(self, registry):
        """Test getting service information"""
        registry.register_factory(
            'test_service',
            Mock,
            lifecycle=ServiceLifecycle.SINGLETON,
            dependencies=['dep1', 'dep2'],
            tags={'tag1', 'tag2'}
        )
        
        info = registry.get_service_info('test_service')
        
        assert info['name'] == 'test_service'
        assert info['lifecycle'] == 'singleton'
        assert info['dependencies'] == ['dep1', 'dep2']
        assert set(info['tags']) == {'tag1', 'tag2'}
        assert info['is_instantiated'] is False
        assert info['has_factory'] is True
        
        # Get service to instantiate it
        registry.register('dep1', service=Mock())
        registry.register('dep2', service=Mock())
        registry.get('test_service')
        
        info = registry.get_service_info('test_service')
        assert info['is_instantiated'] is True
    
    def test_service_not_registered_error(self, registry):
        """Test error when getting unregistered service"""
        with pytest.raises(ValueError, match="Service 'unknown' is not registered"):
            registry.get('unknown')
    
    def test_no_factory_or_instance_error(self, registry):
        """Test error when registering without factory or instance"""
        with pytest.raises(ValueError, match="Either service instance or factory must be provided"):
            registry.register('invalid')
    
    def test_reset_all(self, registry):
        """Test resetting entire registry"""
        registry.register('service1', service=Mock())
        registry.register_factory('service2', Mock)
        
        assert len(registry.list_services()) == 2
        
        registry.reset()
        
        assert len(registry.list_services()) == 0
        assert not registry.has('service1')
        assert not registry.has('service2')


class TestServiceDecorator:
    """Test the @service decorator"""
    
    def test_service_decorator_basic(self):
        """Test basic service decorator usage"""
        
        @service('my_service')
        class MyService:
            def __init__(self):
                self.value = 42
        
        assert MyService._service_name == 'my_service'
        assert MyService._service_lifecycle == ServiceLifecycle.SINGLETON
        assert MyService._service_dependencies == []
        assert MyService._service_tags == set()
        
        # Can still instantiate normally
        instance = MyService()
        assert instance.value == 42
    
    def test_service_decorator_with_options(self):
        """Test service decorator with all options"""
        
        @service(
            'complex_service',
            lifecycle=ServiceLifecycle.TRANSIENT,
            dependencies=['db', 'cache'],
            tags={'important', 'core'}
        )
        class ComplexService:
            def __init__(self, db, cache):
                self.db = db
                self.cache = cache
        
        assert ComplexService._service_name == 'complex_service'
        assert ComplexService._service_lifecycle == ServiceLifecycle.TRANSIENT
        assert ComplexService._service_dependencies == ['db', 'cache']
        assert ComplexService._service_tags == {'important', 'core'}


class TestFactoryFunction:
    """Test the create_enhanced_registry factory"""
    
    def test_create_enhanced_registry(self):
        """Test factory creates proper registry instance"""
        registry = create_enhanced_registry()
        
        assert isinstance(registry, ServiceRegistryEnhanced)
        assert registry.list_services() == []
        
        # Should be usable
        registry.register('test', service=Mock())
        assert registry.has('test')