"""
Service Registry - Central management of all application services
Implements dependency injection and lazy loading patterns
"""
from typing import Dict, Any, Callable, Optional


class ServiceRegistry:
    """
    Centralized registry for all application services.
    Supports dependency injection and lazy loading.
    """
    
    def __init__(self):
        self._services: Dict[str, Any] = {}
        self._factories: Dict[str, Callable] = {}
    
    def register(self, name: str, service: Any) -> None:
        """
        Register a service instance directly.
        
        Args:
            name: Service identifier
            service: Service instance
        """
        self._services[name] = service
    
    def register_factory(self, name: str, factory: Callable) -> None:
        """
        Register a factory function for lazy service instantiation.
        
        Args:
            name: Service identifier
            factory: Callable that returns a service instance
        """
        self._factories[name] = factory
    
    def get(self, name: str) -> Any:
        """
        Get a service by name. Lazy loads if factory is registered.
        
        Args:
            name: Service identifier
            
        Returns:
            Service instance
            
        Raises:
            ValueError: If service is not registered
        """
        # Return existing service if already instantiated
        if name in self._services:
            return self._services[name]
        
        # Lazy load from factory if available
        if name in self._factories:
            self._services[name] = self._factories[name]()
            return self._services[name]
        
        raise ValueError(f"Service '{name}' is not registered")
    
    def has(self, name: str) -> bool:
        """
        Check if a service is registered.
        
        Args:
            name: Service identifier
            
        Returns:
            True if service is registered
        """
        return name in self._services or name in self._factories
    
    def reset(self) -> None:
        """
        Clear all registered services and factories.
        Useful for testing.
        """
        self._services.clear()
        self._factories.clear()
    
    def reset_service(self, name: str) -> None:
        """
        Reset a specific service, forcing re-instantiation on next get.
        
        Args:
            name: Service identifier
        """
        if name in self._services:
            del self._services[name]
    
    def list_services(self) -> list:
        """
        List all registered service names.
        
        Returns:
            List of service names
        """
        all_services = set(self._services.keys()) | set(self._factories.keys())
        return sorted(list(all_services))


def create_service_registry() -> ServiceRegistry:
    """
    Factory function to create and configure the service registry.
    This will be called from app.py during application initialization.
    
    Returns:
        Configured ServiceRegistry instance
    """
    registry = ServiceRegistry()
    
    # Register service factories for lazy loading
    # These will be populated in app.py with actual service instances
    # Example structure (actual implementation in app.py):
    #
    # registry.register_factory('contact', lambda: ContactService())
    # registry.register_factory('openphone', lambda: OpenPhoneService())
    # registry.register_factory('campaign', 
    #     lambda: CampaignService(
    #         openphone_service=registry.get('openphone'),
    #         list_service=registry.get('campaign_list')
    #     ))
    
    return registry