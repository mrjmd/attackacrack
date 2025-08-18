"""
DiagnosticsService Tests - Test business logic layer for system diagnostics
TDD RED Phase: Write comprehensive tests BEFORE implementation

This service handles:
- System health status checks
- Database connectivity verification
- Redis connectivity testing
- System metrics aggregation

Tests ensure repository pattern is used (NO direct database access)
"""

import pytest
import os
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any, Tuple

from services.diagnostics_service import DiagnosticsService
from repositories.diagnostics_repository import DiagnosticsRepository


class TestDiagnosticsService:
    """Test DiagnosticsService functionality with repository pattern"""
    
    @pytest.fixture
    def mock_repository(self):
        """Create mock diagnostics repository"""
        return Mock(spec=DiagnosticsRepository)
    
    @pytest.fixture
    def service(self, mock_repository):
        """Create service instance with mocked repository"""
        return DiagnosticsService(repository=mock_repository)
    
    # Health Status Tests
    
    def test_get_health_status_all_healthy(self, service, mock_repository):
        """Test health status when all systems are healthy"""
        # Arrange
        mock_repository.check_database_connection.return_value = True
        
        with patch.object(service, 'test_redis_connection', return_value='connected'):
            # Act
            health_status, status_code = service.get_health_status()
            
            # Assert
            assert status_code == 200
            assert health_status['status'] == 'healthy'
            assert health_status['service'] == 'attackacrack-crm'
            assert health_status['database'] == 'connected'
            assert health_status['redis'] == 'connected'
            
            # Verify repository was called
            mock_repository.check_database_connection.assert_called_once()
    
    def test_get_health_status_database_down(self, service, mock_repository):
        """Test health status when database is down"""
        # Arrange
        mock_repository.check_database_connection.return_value = False
        mock_repository.get_connection_error_details.return_value = "Connection timeout"
        
        with patch.object(service, 'test_redis_connection', return_value='connected'):
            # Act
            health_status, status_code = service.get_health_status()
            
            # Assert
            assert status_code == 503  # Service unavailable
            assert health_status['status'] == 'degraded'
            assert health_status['database'] == 'error: Connection timeout'
            assert health_status['redis'] == 'connected'
    
    def test_get_health_status_uses_repository_for_database_check(self, service, mock_repository):
        """Test that service uses repository for database connectivity (NO direct DB access)"""
        # Arrange
        mock_repository.check_database_connection.return_value = True
        
        # Act
        service.get_health_status()
        
        # Assert - CRITICAL: Must use repository, not direct DB access
        mock_repository.check_database_connection.assert_called_once()
    
    # Database Connection Tests
    
    def test_test_database_connection_success(self, service, mock_repository):
        """Test successful database connection through repository"""
        # Arrange
        mock_repository.check_database_connection.return_value = True
        
        # Act
        result = service.test_database_connection()
        
        # Assert
        assert result == 'connected'
        mock_repository.check_database_connection.assert_called_once()
    
    def test_test_database_connection_failure(self, service, mock_repository):
        """Test failed database connection through repository"""
        # Arrange
        mock_repository.check_database_connection.return_value = False
        mock_repository.get_connection_error_details.return_value = "Connection refused"
        
        # Act
        result = service.test_database_connection()
        
        # Assert
        assert result == 'error: Connection refused'
        mock_repository.check_database_connection.assert_called_once()
        mock_repository.get_connection_error_details.assert_called_once()
    
    # Redis Connection Tests (these remain in service as they don't involve DB)
    
    def test_test_redis_connection_not_configured(self, service):
        """Test Redis connection when not configured"""
        with patch.dict(os.environ, {}, clear=True):
            # Act
            result = service.test_redis_connection()
            
            # Assert
            assert result == 'not configured'
    
    def test_test_redis_connection_success(self, service):
        """Test successful Redis connection"""
        with patch.dict(os.environ, {'REDIS_URL': 'redis://localhost:6379'}):
            with patch('services.diagnostics_service.create_celery_app') as mock_celery_factory:
                mock_celery = Mock()
                mock_celery.backend.get.return_value = None
                mock_celery_factory.return_value = mock_celery
                
                # Act
                result = service.test_redis_connection()
                
                # Assert
                assert result == 'connected'
    
    def test_test_redis_connection_error(self, service):
        """Test Redis connection error handling"""
        with patch.dict(os.environ, {'REDIS_URL': 'redis://localhost:6379'}):
            with patch('services.diagnostics_service.create_celery_app', side_effect=Exception("Redis down")):
                # Act
                result = service.test_redis_connection()
                
                # Assert
                assert 'error: Redis down' in result
    
    # System Metrics Tests
    
    def test_get_system_metrics_success(self, service, mock_repository):
        """Test getting system metrics through repository"""
        # Arrange
        expected_counts = {
            'contacts': 150,
            'conversations': 75,
            'activities': 300,
            'campaigns': 25,
            'todos': 45
        }
        mock_repository.get_all_model_counts.return_value = expected_counts
        
        import sys
        mock_psutil = Mock()
        mock_proc = Mock()
        mock_proc.memory_info.return_value.rss = 104857600  # 100MB
        mock_proc.memory_percent.return_value = 5.2
        mock_psutil.Process.return_value = mock_proc
        
        with patch.dict('sys.modules', {'psutil': mock_psutil}):
            # Act
            result = service.get_system_metrics()
            
            # Assert
            assert result['database'] == expected_counts
            assert result['memory']['rss_mb'] == 100.0
            assert result['memory']['percent'] == 5.2
            
            # Verify repository was used instead of direct model queries
            mock_repository.get_all_model_counts.assert_called_once()
    
    def test_get_system_metrics_database_error(self, service, mock_repository):
        """Test system metrics when database queries fail"""
        # Arrange
        mock_repository.get_all_model_counts.side_effect = Exception("Database error")
        
        # Act
        result = service.get_system_metrics()
        
        # Assert
        assert 'error' in result['database']
        assert 'Database error' in result['database']['error']
        mock_repository.get_all_model_counts.assert_called_once()
    
    def test_get_system_metrics_psutil_not_available(self, service, mock_repository):
        """Test system metrics when psutil is not available"""
        # Arrange
        mock_repository.get_all_model_counts.return_value = {'contacts': 10}
        
        import sys
        # Remove psutil from sys.modules if it exists
        original_psutil = sys.modules.pop('psutil', None)
        
        # Patch __import__ to raise ImportError for psutil
        def mock_import(name, *args, **kwargs):
            if name == 'psutil':
                raise ImportError("No module named 'psutil'")
            return __import__(name, *args, **kwargs)
        
        with patch('builtins.__import__', side_effect=mock_import):
            try:
                # Act
                result = service.get_system_metrics()
                
                # Assert
                assert result['memory']['status'] == 'psutil not available'
            finally:
                # Restore psutil module if it existed
                if original_psutil is not None:
                    sys.modules['psutil'] = original_psutil
    
    # Redis Diagnostics Tests
    
    def test_get_redis_diagnostics_not_configured(self, service):
        """Test Redis diagnostics when not configured"""
        with patch.dict(os.environ, {}, clear=True):
            # Act
            diagnostics, status_code = service.get_redis_diagnostics()
            
            # Assert
            assert status_code == 503
            assert diagnostics['status'] == 'not_configured'
            assert not diagnostics['redis_url_configured']
            assert 'REDIS_URL environment variable not set' in diagnostics['errors']
    
    def test_get_redis_diagnostics_network_unreachable(self, service):
        """Test Redis diagnostics when network is unreachable"""
        with patch.dict(os.environ, {'REDIS_URL': 'redis://unreachable:6379'}):
            with patch.object(service, '_test_network_connectivity', return_value=False):
                with patch.object(service, '_test_celery_configuration'):
                    # Act
                    diagnostics, status_code = service.get_redis_diagnostics()
                    
                    # Assert
                    assert status_code == 503
                    assert diagnostics['status'] == 'network_unreachable'
                    assert not diagnostics['network_reachable']
    
    def test_get_redis_diagnostics_healthy(self, service):
        """Test Redis diagnostics when all systems healthy"""
        with patch.dict(os.environ, {'REDIS_URL': 'redis://localhost:6379'}):
            with patch.object(service, '_test_network_connectivity', return_value=True):
                with patch.object(service, '_test_redis_connection') as mock_redis_test:
                    with patch.object(service, '_test_celery_configuration'):
                        # Arrange
                        def mock_redis_test_side_effect(url, diag):
                            diag['redis_ping'] = True
                            diag['redis_version'] = '6.2.0'
                        
                        mock_redis_test.side_effect = mock_redis_test_side_effect
                        
                        # Act
                        diagnostics, status_code = service.get_redis_diagnostics()
                        
                        # Assert
                        assert status_code == 200
                        assert diagnostics['status'] == 'healthy'
                        assert diagnostics['redis_ping'] is True
    
    # Network Connectivity Tests
    
    def test_test_network_connectivity_success(self, service):
        """Test successful network connectivity"""
        diagnostics = {'errors': []}
        
        with patch('socket.socket') as mock_socket:
            mock_sock = Mock()
            mock_sock.connect_ex.return_value = 0  # Success
            mock_socket.return_value = mock_sock
            
            # Act
            result = service._test_network_connectivity('localhost', 6379, diagnostics)
            
            # Assert
            assert result is True
            mock_sock.connect_ex.assert_called_once_with(('localhost', 6379))
            mock_sock.close.assert_called_once()
    
    def test_test_network_connectivity_failure(self, service):
        """Test failed network connectivity"""
        diagnostics = {'errors': []}
        
        with patch('socket.socket') as mock_socket:
            mock_sock = Mock()
            mock_sock.connect_ex.return_value = 1  # Connection refused
            mock_socket.return_value = mock_sock
            
            # Act
            result = service._test_network_connectivity('localhost', 6379, diagnostics)
            
            # Assert
            assert result is False
            assert 'Network connection failed with error code: 1' in diagnostics['errors']
    
    def test_test_network_connectivity_exception(self, service):
        """Test network connectivity with exception"""
        diagnostics = {'errors': []}
        
        with patch('socket.socket', side_effect=Exception("Socket error")):
            # Act
            result = service._test_network_connectivity('localhost', 6379, diagnostics)
            
            # Assert
            assert result is False
            assert 'Network test error: Socket error' in diagnostics['errors']
    
    # Redis Connection Tests
    
    def test_test_redis_connection_success(self, service):
        """Test successful Redis connection"""
        diagnostics = {'errors': []}
        
        with patch('redis.from_url') as mock_from_url:
            mock_redis = Mock()
            mock_redis.ping.return_value = True
            mock_redis.info.return_value = {'redis_version': '6.2.0'}
            mock_from_url.return_value = mock_redis
            
            # Act
            service._test_redis_connection('redis://localhost:6379', diagnostics)
            
            # Assert
            assert diagnostics['redis_ping'] is True
            assert diagnostics['redis_version'] == '6.2.0'
    
    def test_test_redis_connection_ssl(self, service):
        """Test Redis connection with SSL"""
        diagnostics = {'errors': []}
        
        with patch('redis.from_url') as mock_from_url:
            with patch('ssl.CERT_NONE') as mock_cert_none:
                mock_redis = Mock()
                mock_redis.ping.return_value = True
                mock_redis.info.return_value = {'redis_version': '6.2.0'}
                mock_from_url.return_value = mock_redis
                
                # Act
                service._test_redis_connection('rediss://secure.redis:6379', diagnostics)
                
                # Assert
                assert diagnostics['redis_ping'] is True
                mock_from_url.assert_called_once()
    
    def test_test_redis_connection_error(self, service):
        """Test Redis connection error handling"""
        diagnostics = {'errors': []}
        
        with patch('redis.from_url', side_effect=Exception("Connection error")):
            # Act
            service._test_redis_connection('redis://localhost:6379', diagnostics)
            
            # Assert
            assert 'Redis connection error: Exception: Connection error' in diagnostics['errors']
    
    # Celery Configuration Tests
    
    def test_test_celery_configuration_success(self, service):
        """Test successful Celery configuration"""
        diagnostics = {'errors': []}
        
        with patch('celery_config.create_celery_app') as mock_create:
            mock_celery = Mock()
            mock_create.return_value = mock_celery
            
            # Act
            service._test_celery_configuration(diagnostics)
            
            # Assert
            assert diagnostics['celery_configured'] is True
    
    def test_test_celery_configuration_error(self, service):
        """Test Celery configuration error"""
        diagnostics = {'errors': []}
        
        with patch('celery_config.create_celery_app', side_effect=Exception("Celery error")):
            # Act
            service._test_celery_configuration(diagnostics)
            
            # Assert
            assert 'Celery configuration error: Celery error' in diagnostics['errors']
    
    # Service Initialization Tests
    
    def test_service_requires_repository(self):
        """Test that service requires repository dependency injection"""
        # This test ensures we can't instantiate without repository
        with pytest.raises(TypeError):
            DiagnosticsService()  # Should require repository parameter
    
    def test_service_stores_repository(self, mock_repository):
        """Test that service properly stores repository dependency"""
        # Act
        service = DiagnosticsService(repository=mock_repository)
        
        # Assert
        assert service.repository == mock_repository
    
    # Integration Pattern Tests
    
    def test_no_direct_database_access(self, service, mock_repository):
        """CRITICAL: Test that service never accesses database directly"""
        # Arrange
        mock_repository.check_database_connection.return_value = True
        mock_repository.get_all_model_counts.return_value = {'contacts': 10}
        
        # Act - call all methods that previously had direct DB access
        service.get_health_status()
        service.test_database_connection()
        service.get_system_metrics()
        
        # Assert - all database operations should go through repository
        mock_repository.check_database_connection.assert_called()
        mock_repository.get_all_model_counts.assert_called()
        
        # Verify no direct imports of db or models (this would be runtime check)
        # The fact that service works with mocked repository proves no direct access
    
    def test_error_handling_preserves_functionality(self, service, mock_repository):
        """Test that error handling doesn't break core functionality"""
        # Arrange - repository throws exceptions
        mock_repository.check_database_connection.side_effect = Exception("DB Error")
        mock_repository.get_all_model_counts.side_effect = Exception("Count Error")
        
        # Act & Assert - should not raise exceptions
        health_status, status_code = service.get_health_status()
        assert status_code in [200, 503]  # Valid status codes
        
        metrics = service.get_system_metrics()
        assert 'database' in metrics  # Should have database key even on error
        assert 'error' in metrics['database']  # Should indicate error
