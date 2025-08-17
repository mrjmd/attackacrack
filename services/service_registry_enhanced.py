"""
Enhanced Service Registry with Advanced Lazy Loading
Implements factory pattern with dependency resolution and lifecycle management
"""
from typing import Dict, Any, Callable, Optional, Set, List, TypeVar, Generic
from enum import Enum
import threading
from functools import wraps
import logging

logger = logging.getLogger(__name__)

T = TypeVar('T')


class ServiceLifecycle(Enum):
    """Service lifecycle management options"""
    SINGLETON = "singleton"  # Single instance per application
    TRANSIENT = "transient"  # New instance per request
    SCOPED = "scoped"       # Single instance per request/scope


class ServiceDescriptor:
    """Describes a service registration"""
    
    def __init__(
        self,
        name: str,
        factory: Optional[Callable] = None,
        instance: Optional[Any] = None,
        lifecycle: ServiceLifecycle = ServiceLifecycle.SINGLETON,
        dependencies: Optional[List[str]] = None,
        tags: Optional[Set[str]] = None
    ):
        self.name = name
        self.factory = factory
        self.instance = instance
        self.lifecycle = lifecycle
        self.dependencies = dependencies or []
        self.tags = tags or set()
        self.is_initializing = False
        self.lock = threading.Lock()


class ServiceRegistryEnhanced:
    """
    Enhanced service registry with advanced lazy loading capabilities.
    
    Features:
    - Lazy loading with factory pattern
    - Dependency resolution
    - Lifecycle management (singleton, transient, scoped)
    - Thread-safe initialization
    - Circular dependency detection
    - Service tagging and grouping
    """
    
    def __init__(self):
        self._descriptors: Dict[str, ServiceDescriptor] = {}
        self._scoped_instances: Dict[str, Dict[str, Any]] = {}
        self._thread_local = threading.local()
        self._lock = threading.Lock()
    
    def register(
        self,
        name: str,
        service: Any = None,
        factory: Callable = None,
        lifecycle: ServiceLifecycle = ServiceLifecycle.SINGLETON,
        dependencies: Optional[List[str]] = None,
        tags: Optional[Set[str]] = None
    ) -> None:
        """
        Register a service with optional factory and lifecycle management.
        
        Args:
            name: Service identifier
            service: Pre-instantiated service (for eager loading)
            factory: Factory function for lazy loading
            lifecycle: Service lifecycle type
            dependencies: List of service names this depends on
            tags: Set of tags for categorization
        """
        if not service and not factory:
            raise ValueError(f"Either service instance or factory must be provided for '{name}'")
        
        descriptor = ServiceDescriptor(
            name=name,
            factory=factory,
            instance=service,
            lifecycle=lifecycle,
            dependencies=dependencies,
            tags=tags
        )
        
        with self._lock:
            self._descriptors[name] = descriptor
    
    def register_factory(
        self,
        name: str,
        factory: Callable,
        lifecycle: ServiceLifecycle = ServiceLifecycle.SINGLETON,
        dependencies: Optional[List[str]] = None,
        tags: Optional[Set[str]] = None
    ) -> None:
        """
        Register a factory function for lazy service instantiation.
        
        Args:
            name: Service identifier
            factory: Callable that returns a service instance
            lifecycle: Service lifecycle type
            dependencies: Services this factory depends on
            tags: Optional tags for categorization
        """
        self.register(
            name=name,
            factory=factory,
            lifecycle=lifecycle,
            dependencies=dependencies,
            tags=tags
        )
    
    def register_singleton(self, name: str, factory: Callable, **kwargs) -> None:
        """Register a singleton service factory"""
        self.register_factory(name, factory, ServiceLifecycle.SINGLETON, **kwargs)
    
    def register_transient(self, name: str, factory: Callable, **kwargs) -> None:
        """Register a transient service factory"""
        self.register_factory(name, factory, ServiceLifecycle.TRANSIENT, **kwargs)
    
    def get(self, name: str, scope_id: Optional[str] = None) -> Any:
        """
        Get a service by name with lazy loading and dependency resolution.
        
        Args:
            name: Service identifier
            scope_id: Scope identifier for scoped services
            
        Returns:
            Service instance
            
        Raises:
            ValueError: If service is not registered
            RuntimeError: If circular dependency detected
        """
        if name not in self._descriptors:
            raise ValueError(f"Service '{name}' is not registered")
        
        descriptor = self._descriptors[name]
        
        # Initialize thread-local stack if needed
        if not hasattr(self._thread_local, 'initialization_stack'):
            self._thread_local.initialization_stack = []
        
        # Check for circular dependencies
        if name in self._thread_local.initialization_stack:
            cycle = " -> ".join(self._thread_local.initialization_stack + [name])
            raise RuntimeError(f"Circular dependency detected: {cycle}")
        
        # Handle different lifecycles
        if descriptor.lifecycle == ServiceLifecycle.SINGLETON:
            return self._get_singleton(descriptor)
        elif descriptor.lifecycle == ServiceLifecycle.TRANSIENT:
            return self._create_instance(descriptor)
        elif descriptor.lifecycle == ServiceLifecycle.SCOPED:
            return self._get_scoped(descriptor, scope_id)
        
        raise ValueError(f"Unknown lifecycle: {descriptor.lifecycle}")
    
    def _get_singleton(self, descriptor: ServiceDescriptor) -> Any:
        """Get or create singleton instance"""
        if descriptor.instance is not None:
            return descriptor.instance
        
        with descriptor.lock:
            # Double-check pattern
            if descriptor.instance is not None:
                return descriptor.instance
            
            if descriptor.is_initializing:
                # Another thread is initializing, wait for it
                pass  # Lock will be released and we'll wait
            
            descriptor.is_initializing = True
            try:
                descriptor.instance = self._create_instance(descriptor)
                return descriptor.instance
            finally:
                descriptor.is_initializing = False
    
    def _get_scoped(self, descriptor: ServiceDescriptor, scope_id: Optional[str]) -> Any:
        """Get or create scoped instance"""
        if scope_id is None:
            scope_id = "default"
        
        with self._lock:
            if scope_id not in self._scoped_instances:
                self._scoped_instances[scope_id] = {}
            
            scope = self._scoped_instances[scope_id]
            
            if descriptor.name not in scope:
                scope[descriptor.name] = self._create_instance(descriptor)
            
            return scope[descriptor.name]
    
    def _create_instance(self, descriptor: ServiceDescriptor) -> Any:
        """Create a new service instance"""
        if descriptor.factory is None:
            raise ValueError(f"No factory registered for '{descriptor.name}'")
        
        # Initialize thread-local stack if needed
        if not hasattr(self._thread_local, 'initialization_stack'):
            self._thread_local.initialization_stack = []
        
        self._thread_local.initialization_stack.append(descriptor.name)
        try:
            # Resolve dependencies
            if descriptor.dependencies:
                # Create a dependency injection wrapper
                deps = {dep: self.get(dep) for dep in descriptor.dependencies}
                instance = descriptor.factory(**deps)
            else:
                instance = descriptor.factory()
            
            logger.debug(f"Created service instance: {descriptor.name}")
            return instance
            
        finally:
            self._thread_local.initialization_stack.pop()
    
    def get_all_by_tag(self, tag: str) -> Dict[str, Any]:
        """
        Get all services with a specific tag.
        
        Args:
            tag: Tag to filter by
            
        Returns:
            Dictionary of service name to instance
        """
        result = {}
        for name, descriptor in self._descriptors.items():
            if tag in descriptor.tags:
                result[name] = self.get(name)
        return result
    
    def has(self, name: str) -> bool:
        """Check if a service is registered"""
        return name in self._descriptors
    
    def reset(self) -> None:
        """Clear all registered services and factories"""
        with self._lock:
            self._descriptors.clear()
            self._scoped_instances.clear()
            # Clear thread-local data
            if hasattr(self._thread_local, 'initialization_stack'):
                self._thread_local.initialization_stack.clear()
    
    def reset_service(self, name: str) -> None:
        """Reset a specific service, forcing re-instantiation on next get"""
        if name in self._descriptors:
            descriptor = self._descriptors[name]
            with descriptor.lock:
                descriptor.instance = None
            
            # Clear from all scopes
            with self._lock:
                for scope in self._scoped_instances.values():
                    scope.pop(name, None)
    
    def clear_scope(self, scope_id: str) -> None:
        """Clear all services in a specific scope"""
        with self._lock:
            self._scoped_instances.pop(scope_id, None)
    
    def list_services(self) -> List[str]:
        """List all registered service names"""
        return sorted(self._descriptors.keys())
    
    def get_service_info(self, name: str) -> Dict[str, Any]:
        """Get detailed information about a service"""
        if name not in self._descriptors:
            raise ValueError(f"Service '{name}' is not registered")
        
        descriptor = self._descriptors[name]
        return {
            'name': descriptor.name,
            'lifecycle': descriptor.lifecycle.value,
            'dependencies': descriptor.dependencies,
            'tags': list(descriptor.tags),
            'is_instantiated': descriptor.instance is not None,
            'has_factory': descriptor.factory is not None
        }
    
    def validate_dependencies(self) -> List[str]:
        """
        Validate all service dependencies are registered.
        
        Returns:
            List of validation errors (empty if valid)
        """
        errors = []
        
        for name, descriptor in self._descriptors.items():
            for dep in descriptor.dependencies:
                if dep not in self._descriptors:
                    errors.append(f"Service '{name}' depends on unregistered service '{dep}'")
        
        return errors
    
    def get_dependency_graph(self) -> Dict[str, List[str]]:
        """
        Get the dependency graph of all services.
        
        Returns:
            Dictionary mapping service names to their dependencies
        """
        return {
            name: descriptor.dependencies.copy()
            for name, descriptor in self._descriptors.items()
        }
    
    def get_initialization_order(self) -> List[str]:
        """
        Calculate the correct initialization order based on dependencies.
        Uses topological sort.
        
        Returns:
            Ordered list of service names
            
        Raises:
            RuntimeError: If circular dependency exists
        """
        graph = self.get_dependency_graph()
        visited = set()
        stack = []
        
        def visit(node: str, path: Set[str]):
            if node in path:
                cycle = " -> ".join(path) + f" -> {node}"
                raise RuntimeError(f"Circular dependency detected: {cycle}")
            
            if node in visited:
                return
            
            path.add(node)
            for dep in graph.get(node, []):
                visit(dep, path.copy())
            
            visited.add(node)
            stack.append(node)
        
        for service in graph:
            if service not in visited:
                visit(service, set())
        
        return stack
    
    def warmup(self, services: Optional[List[str]] = None) -> None:
        """
        Pre-instantiate services to avoid lazy loading delays.
        
        Args:
            services: List of service names to warmup (None for all singletons)
        """
        if services is None:
            # Warmup all singleton services
            services = [
                name for name, desc in self._descriptors.items()
                if desc.lifecycle == ServiceLifecycle.SINGLETON
            ]
        
        # Get initialization order
        order = self.get_initialization_order()
        
        # Initialize in correct order
        for name in order:
            if name in services:
                logger.info(f"Warming up service: {name}")
                self.get(name)


def create_enhanced_registry() -> ServiceRegistryEnhanced:
    """
    Factory function to create enhanced service registry.
    
    Returns:
        Configured ServiceRegistryEnhanced instance
    """
    return ServiceRegistryEnhanced()


# Decorator for automatic service registration
def service(
    name: str,
    lifecycle: ServiceLifecycle = ServiceLifecycle.SINGLETON,
    dependencies: Optional[List[str]] = None,
    tags: Optional[Set[str]] = None
):
    """
    Decorator for automatic service registration.
    
    Usage:
        @service('my_service', dependencies=['db', 'cache'])
        class MyService:
            def __init__(self, db, cache):
                self.db = db
                self.cache = cache
    """
    def decorator(cls):
        # Store metadata on the class
        cls._service_name = name
        cls._service_lifecycle = lifecycle
        cls._service_dependencies = dependencies or []
        cls._service_tags = tags or set()
        
        # Create wrapper for automatic registration
        @wraps(cls)
        def wrapper(*args, **kwargs):
            return cls(*args, **kwargs)
        
        wrapper._service_class = cls
        return wrapper
    
    return decorator