"""
DiagnosticsService - Handles system health checks and diagnostics

Refactored to use Repository Pattern - NO direct database access allowed.
All database operations go through DiagnosticsRepository.
"""
import os
import socket
from typing import Dict, Any, Tuple
from urllib.parse import urlparse

from repositories.diagnostics_repository import DiagnosticsRepository


class DiagnosticsService:
    """Service for system health checks and diagnostics with repository pattern"""
    
    def __init__(self, repository: DiagnosticsRepository):
        """
        Initialize service with repository dependency injection.
        
        Args:
            repository: DiagnosticsRepository instance for database operations
        """
        self.repository = repository
    
    def get_health_status(self) -> Tuple[Dict[str, Any], int]:
        """
        Get overall system health status
        
        Returns:
            Tuple of (health status dict, HTTP status code)
        """
        health_status = {
            'status': 'healthy',
            'service': 'attackacrack-crm',
            'database': 'unknown',
            'redis': 'unknown'
        }
        
        # Check database connection
        health_status['database'] = self.test_database_connection()
        if health_status['database'] != 'connected':
            health_status['status'] = 'degraded'
        
        # Check Redis connection
        health_status['redis'] = self.test_redis_connection()
        # Redis is optional, so don't degrade status if it's not available
        
        # Return appropriate status code
        if health_status['database'] == 'connected':
            return health_status, 200
        else:
            return health_status, 503
    
    def test_database_connection(self) -> str:
        """
        Test database connectivity through repository.
        
        Returns:
            Status string: 'connected' or error message
        """
        try:
            if self.repository.check_database_connection():
                return 'connected'
            else:
                error = self.repository.get_connection_error_details()
                return f'error: {error}' if error else 'error: Unknown connection error'
        except Exception as e:
            return f'error: {str(e)}'
    
    def test_redis_connection(self) -> str:
        """
        Test Redis connectivity
        
        Returns:
            Status string: 'connected', 'not configured', or error message
        """
        redis_url = os.environ.get('REDIS_URL')
        if not redis_url:
            return 'not configured'
        
        try:
            # Get appropriate Celery instance based on Redis configuration
            if redis_url.startswith('rediss://'):
                from celery_config import create_celery_app
                celery = create_celery_app('attackacrack')
            else:
                from celery_worker import celery
            
            celery.backend.get('health_check_test')
            return 'connected'
        except ImportError:
            return 'celery not available'
        except Exception as e:
            return f'error: {str(e)}'
    
    def get_redis_diagnostics(self) -> Tuple[Dict[str, Any], int]:
        """
        Get detailed Redis connectivity diagnostics
        
        Returns:
            Tuple of (diagnostics dict, HTTP status code)
        """
        diagnostics = {
            'redis_url_configured': False,
            'redis_url_scheme': None,
            'network_reachable': False,
            'redis_ping': False,
            'celery_configured': False,
            'errors': []
        }
        
        redis_url = os.environ.get('REDIS_URL', '')
        
        if not redis_url:
            diagnostics['errors'].append("REDIS_URL environment variable not set")
            diagnostics['status'] = 'not_configured'
            return diagnostics, 503
        
        diagnostics['redis_url_configured'] = True
        parsed = urlparse(redis_url)
        diagnostics['redis_url_scheme'] = parsed.scheme
        diagnostics['redis_host'] = parsed.hostname
        diagnostics['redis_port'] = parsed.port or 6379
        
        # Test network connectivity
        diagnostics['network_reachable'] = self._test_network_connectivity(
            parsed.hostname, 
            parsed.port or 6379,
            diagnostics
        )
        
        # Test Redis connection if network is reachable
        if diagnostics['network_reachable']:
            self._test_redis_connection(redis_url, diagnostics)
        
        # Test Celery configuration
        self._test_celery_configuration(diagnostics)
        
        # Determine overall status
        if diagnostics['redis_ping']:
            status_code = 200
            diagnostics['status'] = 'healthy'
        elif diagnostics['network_reachable']:
            status_code = 503
            diagnostics['status'] = 'redis_connection_failed'
        else:
            status_code = 503
            diagnostics['status'] = 'network_unreachable'
        
        return diagnostics, status_code
    
    def _test_network_connectivity(self, hostname: str, port: int, diagnostics: Dict) -> bool:
        """
        Test network connectivity to a host and port
        
        Args:
            hostname: Host to connect to
            port: Port to connect to
            diagnostics: Dictionary to add error messages to
            
        Returns:
            True if network is reachable, False otherwise
        """
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            result = sock.connect_ex((hostname, port))
            sock.close()
            
            if result == 0:
                return True
            else:
                diagnostics['errors'].append(f"Network connection failed with error code: {result}")
                return False
        except Exception as e:
            diagnostics['errors'].append(f"Network test error: {str(e)}")
            return False
    
    def _test_redis_connection(self, redis_url: str, diagnostics: Dict) -> None:
        """
        Test Redis connection and populate diagnostics
        
        Args:
            redis_url: Redis connection URL
            diagnostics: Dictionary to populate with results
        """
        try:
            import redis
            import ssl
            
            if redis_url.startswith('rediss://'):
                # SSL connection
                if 'ssl_cert_reqs' not in redis_url:
                    separator = '&' if '?' in redis_url else '?'
                    redis_url_test = redis_url + f"{separator}ssl_cert_reqs=CERT_NONE"
                else:
                    redis_url_test = redis_url
                
                r = redis.from_url(
                    redis_url_test,
                    socket_connect_timeout=5,
                    socket_timeout=5,
                    ssl_cert_reqs=ssl.CERT_NONE,
                    ssl_check_hostname=False
                )
            else:
                r = redis.from_url(
                    redis_url,
                    socket_connect_timeout=5,
                    socket_timeout=5
                )
            
            # Test ping
            r.ping()
            diagnostics['redis_ping'] = True
            
            # Get Redis info
            info = r.info('server')
            diagnostics['redis_version'] = info.get('redis_version', 'Unknown')
            
        except Exception as e:
            diagnostics['errors'].append(f"Redis connection error: {type(e).__name__}: {str(e)}")
    
    def _test_celery_configuration(self, diagnostics: Dict) -> None:
        """
        Test Celery configuration
        
        Args:
            diagnostics: Dictionary to populate with results
        """
        try:
            from celery_config import create_celery_app
            celery = create_celery_app('diagnostic')
            diagnostics['celery_configured'] = True
        except Exception as e:
            diagnostics['errors'].append(f"Celery configuration error: {str(e)}")
    
    def get_system_metrics(self) -> Dict[str, Any]:
        """
        Get system metrics and statistics through repository.
        
        Returns:
            Dictionary of system metrics
        """
        metrics = {}
        
        try:
            # Database statistics through repository (NO direct model access)
            metrics['database'] = self.repository.get_all_model_counts()
        except Exception as e:
            metrics['database'] = {'error': str(e)}
        
        try:
            # Memory usage (if available)
            import psutil
            process = psutil.Process()
            metrics['memory'] = {
                'rss_mb': process.memory_info().rss / 1024 / 1024,
                'percent': process.memory_percent()
            }
        except ImportError:
            metrics['memory'] = {'status': 'psutil not available'}
        except Exception as e:
            metrics['memory'] = {'error': str(e)}
        
        return metrics