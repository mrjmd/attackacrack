"""
TDD RED Phase: Tests for SMSMetricsService Repository Refactoring
These tests MUST FAIL initially - testing that service uses repositories instead of direct DB queries
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from services.sms_metrics_service import SMSMetricsService


class TestSMSMetricsServiceRepositoryRefactor:
    """Test that SMSMetricsService uses repositories instead of direct database queries"""
    
    @pytest.fixture
    def mock_activity_repository(self):
        """Mock ActivityRepository"""
        return Mock()
    
    @pytest.fixture  
    def mock_contact_repository(self):
        """Mock ContactRepository"""
        return Mock()
    
    @pytest.fixture
    def mock_campaign_repository(self):
        """Mock CampaignRepository"""
        return Mock()
    
    @pytest.fixture
    def service(self, mock_activity_repository, mock_contact_repository, mock_campaign_repository):
        """Create SMSMetricsService with mocked repositories - MUST FAIL initially"""
        # This should fail because the service doesn't accept repositories yet
        return SMSMetricsService(
            activity_repository=mock_activity_repository,
            contact_repository=mock_contact_repository,
            campaign_repository=mock_campaign_repository
        )
    
    def test_track_message_status_uses_repositories(self, service, mock_activity_repository, mock_contact_repository):
        """Test that track_message_status uses repositories instead of direct DB queries - MUST FAIL"""
        # Setup mocks
        mock_activity = Mock()
        mock_activity.id = 123
        mock_activity.status = 'sent'
        mock_activity.contact_id = 456
        mock_activity.activity_metadata = {}
        mock_activity_repository.get_by_id.return_value = mock_activity
        
        mock_contact = Mock()
        mock_contact.id = 456
        mock_contact.contact_metadata = {}
        mock_contact_repository.get_by_id.return_value = mock_contact
        
        # Test the method
        result = service.track_message_status(
            activity_id=123,
            status='failed',
            status_details='Invalid number'
        )
        
        # Verify repositories were used instead of direct DB queries
        mock_activity_repository.get_by_id.assert_called_once_with(123)
        mock_activity_repository.update_activity_status_with_metadata.assert_called_once()
        mock_contact_repository.update_contact_bounce_status.assert_called_once()
        
        # Verify result
        assert result['status'] == 'tracked'
        assert result['activity_id'] == 123
        assert result['message_status'] == 'failed'
    
    def test_get_campaign_metrics_uses_campaign_repository(self, service, mock_campaign_repository):
        """Test that get_campaign_metrics uses campaign repository - MUST FAIL"""
        # Setup mock
        mock_campaign_repository.get_campaign_metrics_with_bounce_analysis.return_value = {
            'total_contacts': 100,
            'sent': 95,
            'delivered': 90,
            'bounced': 5,
            'bounce_rate': 5.26,
            'delivery_rate': 94.74,
            'response_rate': 15.0,
            'status': 'healthy'
        }
        
        # Test the method
        result = service.get_campaign_metrics(campaign_id=123)
        
        # Verify repository was used
        mock_campaign_repository.get_campaign_metrics_with_bounce_analysis.assert_called_once_with(123)
        
        # Verify result structure
        assert 'total_contacts' in result
        assert 'bounce_rate' in result
        assert 'delivery_rate' in result
        assert result['total_contacts'] == 100
    
    def test_get_global_metrics_uses_activity_repository(self, service, mock_activity_repository):
        """Test that get_global_metrics uses activity repository - MUST FAIL"""
        # Setup mock
        mock_activity_repository.get_daily_message_stats.return_value = [
            {'date': datetime.utcnow().date(), 'sent': 10, 'bounced': 1, 'bounce_rate': 10.0}
        ]
        
        mock_activity_repository.find_messages_by_date_range_and_direction.return_value = []
        
        # Test the method
        result = service.get_global_metrics(days=7)
        
        # Verify repository methods were used
        mock_activity_repository.get_daily_message_stats.assert_called_once_with(days=7)
        
        # Verify result structure  
        assert 'period_days' in result
        assert 'total_sent' in result
        assert 'bounce_rate' in result
    
    def test_get_contact_sms_history_uses_repositories(self, service, mock_contact_repository, mock_activity_repository):
        """Test that get_contact_sms_history uses repositories - MUST FAIL"""
        # Setup mocks
        mock_contact = Mock()
        mock_contact.id = 123
        mock_contact.phone = '+1234567890'
        mock_contact.contact_metadata = {'bounce_info': {'total_bounces': 1}}
        mock_contact_repository.get_by_id.return_value = mock_contact
        
        mock_activity_repository.get_contact_message_summary.return_value = {
            'total_messages': 5,
            'sent_count': 3,
            'received_count': 2,
            'delivered_count': 2,
            'bounced_count': 1,
            'recent_messages': []
        }
        
        # Test the method
        result = service.get_contact_sms_history(contact_id=123)
        
        # Verify repositories were used
        mock_contact_repository.get_by_id.assert_called_once_with(123)
        mock_activity_repository.get_contact_message_summary.assert_called_once_with(123)
        
        # Verify result structure
        assert 'contact_id' in result
        assert 'phone' in result
        assert 'total_messages' in result
        assert 'bounce_info' in result
        assert result['contact_id'] == 123
    
    def test_identify_problematic_numbers_uses_contact_repository(self, service, mock_contact_repository):
        """Test that identify_problematic_numbers uses contact repository - MUST FAIL"""
        # Setup mock
        mock_contact_repository.find_problematic_numbers.return_value = [
            {
                'contact_id': 123,
                'phone': '+1234567890',
                'total_bounces': 3,
                'bounce_types': {'hard': 2, 'soft': 1},
                'sms_invalid': True
            }
        ]
        
        # Test the method
        result = service.identify_problematic_numbers(bounce_threshold=2)
        
        # Verify repository was used
        mock_contact_repository.find_problematic_numbers.assert_called_once_with(bounce_threshold=2)
        
        # Verify result
        assert len(result) == 1
        assert result[0]['contact_id'] == 123
        assert result[0]['total_bounces'] == 3
    
    def test_service_no_direct_db_imports(self):
        """Test that service doesn't import database models directly - MUST FAIL"""
        # Import the service module and check for direct DB imports
        import services.sms_metrics_service as sms_module
        
        # Get the module's source code
        import inspect
        source = inspect.getsource(sms_module)
        
        # These should not be found in the refactored service
        forbidden_imports = [
            'from crm_database import',
            'import crm_database',
            'from extensions import db',
            'import db',
            'Activity.query',
            'Contact.query',
            'Campaign.query',
            'CampaignMembership.query',
            'db.session'
        ]
        
        for forbidden in forbidden_imports:
            assert forbidden not in source, f"Service still contains direct DB access: {forbidden}"
    
    def test_private_update_contact_bounce_status_uses_repository(self, service, mock_contact_repository):
        """Test that _update_contact_bounce_status uses repository - MUST FAIL"""
        # Setup mock
        mock_contact_repository.update_contact_bounce_status.return_value = Mock()
        
        # Test the private method (should be refactored to use repository)
        bounce_info = {
            'bounce_type': 'hard',
            'bounce_details': 'Invalid number',
            'bounced_at': datetime.utcnow().isoformat()
        }
        
        # This should call the repository instead of direct DB query
        service._update_contact_bounce_status(contact_id=123, bounce_type='hard')
        
        # Verify repository was used
        mock_contact_repository.update_contact_bounce_status.assert_called_once()
    
    def test_classify_bounce_is_pure_function(self, service):
        """Test that _classify_bounce remains a pure function - Should PASS"""
        # This method should remain unchanged as it's pure logic
        result = service._classify_bounce('invalid_number detected')
        assert result == 'hard'
        
        result = service._classify_bounce('temporary_failure')  
        assert result == 'soft'
        
        result = service._classify_bounce('unknown_error')
        assert result == 'unknown'
    
    def test_service_initialization_requires_repositories(self):
        """Test that service requires repositories for initialization - MUST FAIL"""
        # This should fail because current service doesn't accept repositories
        with pytest.raises((TypeError, AttributeError)):
            SMSMetricsService()  # Should require repositories
    
    def test_no_sqlalchemy_session_usage(self):
        """Test that service doesn't use SQLAlchemy session directly - MUST FAIL"""
        # Import and inspect the service
        from services.sms_metrics_service import SMSMetricsService
        import inspect
        
        # Get all methods of the service
        methods = inspect.getmembers(SMSMetricsService, predicate=inspect.isfunction)
        
        for method_name, method in methods:
            if method_name.startswith('_'):
                continue  # Skip private methods for now
                
            source = inspect.getsource(method)
            
            # These patterns indicate direct database usage
            forbidden_patterns = [
                '.query.',
                'db.session',
                '.commit()',
                '.rollback()',
                '.flush()',
                '.add(',
                '.delete('
            ]
            
            for pattern in forbidden_patterns:
                assert pattern not in source, f"Method {method_name} contains direct DB usage: {pattern}"