"""
Dependency Injection Compliance Tests

TESTS MUST FAIL INITIALLY (RED PHASE) TO ENFORCE PROPER TDD.

These tests verify that all services in our CRM system properly follow
dependency injection patterns without fallbacks or direct instantiation.

FOCUS AREAS:
1. SMSMetricsService requires and properly uses injected repositories
2. JobService requires and properly uses injected JobRepository
3. DashboardService uses injected SMSMetricsService instead of creating it
4. OpenPhoneWebhookServiceRefactored uses injected services without fallbacks
5. Service registry factories properly inject all required dependencies

TEST STRATEGY:
- Use mocks to verify constructor requirements
- Test that services fail without proper dependencies
- Verify services use injected dependencies, not create their own
- Test service registry factories create services with correct dependencies
"""

import pytest
from unittest.mock import Mock, patch, MagicMock, call
from flask import Flask

# Import the services we're testing
from services.sms_metrics_service import SMSMetricsService
from services.job_service import JobService
from services.dashboard_service import DashboardService
from services.openphone_webhook_service_refactored import OpenPhoneWebhookServiceRefactored


class TestSMSMetricsServiceDICompliance:
    """Test SMSMetricsService follows strict dependency injection patterns"""
    
    def test_sms_metrics_service_requires_all_repositories(self):
        """Test that SMSMetricsService constructor requires all repository dependencies"""
        # This test should FAIL initially because SMSMetricsService doesn't require dependencies
        
        # Arrange - Create mock repositories
        mock_activity_repo = Mock()
        mock_contact_repo = Mock()
        mock_campaign_repo = Mock()
        
        # Act & Assert - Constructor should require all dependencies
        with pytest.raises(TypeError, match="missing.*required.*argument"):
            # This should fail if constructor doesn't require dependencies
            SMSMetricsService()
    
    def test_sms_metrics_service_stores_injected_repositories(self):
        """Test that SMSMetricsService stores all injected repositories as instance variables"""
        # Arrange
        mock_activity_repo = Mock()
        mock_contact_repo = Mock()
        mock_campaign_repo = Mock()
        
        # Act
        service = SMSMetricsService(
            activity_repository=mock_activity_repo,
            contact_repository=mock_contact_repo,
            campaign_repository=mock_campaign_repo
        )
        
        # Assert - Service should store injected dependencies
        assert service.activity_repository is mock_activity_repo
        assert service.contact_repository is mock_contact_repo
        assert service.campaign_repository is mock_campaign_repo
    
    def test_track_message_status_uses_injected_activity_repository(self):
        """Test that track_message_status uses injected activity_repository, not direct queries"""
        # Arrange
        mock_activity_repo = Mock()
        mock_contact_repo = Mock()
        mock_campaign_repo = Mock()
        
        # Mock activity object
        mock_activity = Mock()
        mock_activity.contact_id = 123
        mock_activity_repo.get_by_id.return_value = mock_activity
        
        service = SMSMetricsService(
            activity_repository=mock_activity_repo,
            contact_repository=mock_contact_repo,
            campaign_repository=mock_campaign_repo
        )
        
        # Act
        result = service.track_message_status(activity_id=1, status='delivered')
        
        # Assert - Should use injected repository, not direct DB access
        mock_activity_repo.get_by_id.assert_called_once_with(1)
        mock_activity_repo.update_activity_status_with_metadata.assert_called_once()
        
        # Should NOT import or use direct SQLAlchemy queries
        assert result['status'] == 'tracked'
    
    def test_get_contact_sms_history_uses_injected_repositories(self):
        """Test that get_contact_sms_history uses injected repositories exclusively"""
        # Arrange
        mock_activity_repo = Mock()
        mock_contact_repo = Mock()
        mock_campaign_repo = Mock()
        
        # Mock contact and message summary
        mock_contact = Mock()
        mock_contact.id = 123
        mock_contact.phone = '+11234567890'
        mock_contact.contact_metadata = {}
        mock_contact_repo.get_by_id.return_value = mock_contact
        
        mock_message_summary = {
            'total_messages': 10,
            'sent_count': 8,
            'received_count': 2,
            'delivered_count': 7,
            'bounced_count': 1,
            'recent_messages': []
        }
        mock_activity_repo.get_contact_message_summary.return_value = mock_message_summary
        mock_contact_repo.get_contact_reliability_score.return_value = 85
        
        service = SMSMetricsService(
            activity_repository=mock_activity_repo,
            contact_repository=mock_contact_repo,
            campaign_repository=mock_campaign_repo
        )
        
        # Act
        result = service.get_contact_sms_history(contact_id=123)
        
        # Assert - Should use both injected repositories
        mock_contact_repo.get_by_id.assert_called_once_with(123)
        mock_activity_repo.get_contact_message_summary.assert_called_once_with(123)
        mock_contact_repo.get_contact_reliability_score.assert_called_once_with(123)
        
        assert result['contact_id'] == 123
        assert result['total_messages'] == 10
        assert result['reliability_score'] == 85
    
    def test_get_campaign_metrics_uses_injected_campaign_repository(self):
        """Test that get_campaign_metrics delegates to injected campaign_repository"""
        # Arrange
        mock_activity_repo = Mock()
        mock_contact_repo = Mock()
        mock_campaign_repo = Mock()
        
        expected_metrics = {
            'sent': 100,
            'delivered': 95,
            'bounced': 5,
            'bounce_rate': 5.0
        }
        mock_campaign_repo.get_campaign_metrics_with_bounce_analysis.return_value = expected_metrics
        
        service = SMSMetricsService(
            activity_repository=mock_activity_repo,
            contact_repository=mock_contact_repo,
            campaign_repository=mock_campaign_repo
        )
        
        # Act
        result = service.get_campaign_metrics(campaign_id=456)
        
        # Assert
        mock_campaign_repo.get_campaign_metrics_with_bounce_analysis.assert_called_once_with(456)
        assert result == expected_metrics


class TestJobServiceDICompliance:
    """Test JobService follows strict dependency injection patterns"""
    
    def test_job_service_requires_job_repository_dependency(self):
        """Test that JobService constructor requires JobRepository dependency"""
        # This test should FAIL initially because JobService has fallback logic
        
        # Act & Assert - Constructor should require JobRepository
        with pytest.raises(TypeError, match="missing.*required.*argument"):
            # This should fail if constructor allows None or has fallback logic
            JobService()
    
    def test_job_service_stores_injected_repository(self):
        """Test that JobService stores injected JobRepository as instance variable"""
        # Arrange
        mock_job_repo = Mock()
        
        # Act
        service = JobService(job_repository=mock_job_repo)
        
        # Assert - Service should store injected dependency
        assert service.repository is mock_job_repo
    
    def test_job_service_no_fallback_db_session_access(self):
        """Test that JobService does NOT create fallback db.session access"""
        # Arrange
        mock_job_repo = Mock()
        service = JobService(job_repository=mock_job_repo)
        
        # Assert - Should not have direct db.session access
        assert not hasattr(service, 'session')
        # Should only have the injected repository
        assert hasattr(service, 'repository')
    
    def test_get_or_create_active_job_uses_injected_repository(self):
        """Test that get_or_create_active_job uses injected repository exclusively"""
        # Arrange
        mock_job_repo = Mock()
        
        mock_job = Mock()
        mock_job.id = 123
        mock_job_repo.find_active_job_by_property_id.return_value = mock_job
        
        service = JobService(job_repository=mock_job_repo)
        
        # Act
        result = service.get_or_create_active_job(property_id=456)
        
        # Assert - Should use injected repository
        mock_job_repo.find_active_job_by_property_id.assert_called_once_with(456)
        assert result is mock_job
        
        # Should NOT import or use db.session directly
    
    def test_all_crud_methods_use_injected_repository(self):
        """Test that all CRUD methods delegate to injected repository"""
        # Arrange
        mock_job_repo = Mock()
        mock_job = Mock()
        mock_job_repo.create.return_value = mock_job
        mock_job_repo.get_all.return_value = [mock_job]
        mock_job_repo.get_by_id.return_value = mock_job
        mock_job_repo.update.return_value = mock_job
        mock_job_repo.delete.return_value = True
        
        service = JobService(job_repository=mock_job_repo)
        
        # Act & Assert for each method
        service.add_job(description='Test Job')
        mock_job_repo.create.assert_called_once_with(description='Test Job')
        
        service.get_all_jobs()
        mock_job_repo.get_all.assert_called_once()
        
        service.get_job_by_id(123)
        mock_job_repo.get_by_id.assert_called_once_with(123)
        
        service.update_job(mock_job, status='Updated')
        mock_job_repo.update.assert_called_once_with(mock_job, status='Updated')
        
        service.delete_job(mock_job)
        mock_job_repo.delete.assert_called_once_with(mock_job)


class TestDashboardServiceDICompliance:
    """Test DashboardService follows strict dependency injection patterns"""
    
    def test_dashboard_service_requires_sms_metrics_service_injection(self):
        """Test that DashboardService must be injected with SMSMetricsService"""
        # This test should FAIL initially because DashboardService creates its own SMSMetricsService
        
        # Arrange
        mock_contact_repo = Mock()
        mock_campaign_repo = Mock()
        mock_activity_repo = Mock()
        mock_conversation_repo = Mock()
        mock_sms_metrics_service = Mock()
        
        # Act & Assert - Constructor should require SMSMetricsService injection
        with pytest.raises(TypeError, match="missing.*required.*argument.*sms_metrics_service"):
            # This should fail if service creates its own SMSMetricsService
            DashboardService(
                contact_repository=mock_contact_repo,
                campaign_repository=mock_campaign_repo,
                activity_repository=mock_activity_repo,
                conversation_repository=mock_conversation_repo
                # Missing sms_metrics_service parameter!
            )
    
    def test_dashboard_service_stores_injected_sms_metrics_service(self):
        """Test that DashboardService stores injected SMSMetricsService"""
        # Arrange
        mock_contact_repo = Mock()
        mock_campaign_repo = Mock()
        mock_activity_repo = Mock()
        mock_conversation_repo = Mock()
        mock_sms_metrics_service = Mock()
        
        # Act
        service = DashboardService(
            contact_repository=mock_contact_repo,
            campaign_repository=mock_campaign_repo,
            activity_repository=mock_activity_repo,
            conversation_repository=mock_conversation_repo,
            sms_metrics_service=mock_sms_metrics_service
        )
        
        # Assert
        assert service.metrics_service is mock_sms_metrics_service
    
    def test_dashboard_service_no_direct_sms_metrics_instantiation(self):
        """Test that DashboardService does NOT create its own SMSMetricsService"""
        # This test will fail initially because DashboardService has:
        # self.metrics_service = SMSMetricsService()
        
        with patch('services.dashboard_service.SMSMetricsService') as mock_sms_metrics_class:
            # Arrange
            mock_contact_repo = Mock()
            mock_campaign_repo = Mock()
            mock_activity_repo = Mock()
            mock_conversation_repo = Mock()
            mock_sms_metrics_service = Mock()
            
            # Act
            service = DashboardService(
                contact_repository=mock_contact_repo,
                campaign_repository=mock_campaign_repo,
                activity_repository=mock_activity_repo,
                conversation_repository=mock_conversation_repo,
                sms_metrics_service=mock_sms_metrics_service
            )
            
            # Assert - SMSMetricsService class should NOT be instantiated
            mock_sms_metrics_class.assert_not_called()
    
    def test_get_dashboard_stats_uses_injected_sms_metrics_service(self):
        """Test that get_dashboard_stats uses injected SMSMetricsService"""
        # Arrange
        mock_contact_repo = Mock()
        mock_campaign_repo = Mock()
        mock_activity_repo = Mock()
        mock_conversation_repo = Mock()
        mock_sms_metrics_service = Mock()
        
        # Configure repository mocks
        mock_contact_repo.get_total_contacts_count.return_value = 100
        mock_contact_repo.get_contacts_added_this_week_count.return_value = 5
        mock_campaign_repo.get_active_campaigns_count.return_value = 3
        mock_campaign_repo.calculate_average_campaign_response_rate.return_value = 25.5
        mock_activity_repo.get_messages_sent_today_count.return_value = 50
        mock_activity_repo.calculate_overall_response_rate.return_value = 15.2
        
        # Configure SMS metrics mock
        mock_sms_metrics = {
            'bounce_rate': 2.5,
            'delivery_rate': 97.5,
            'total_sent': 1000,
            'bounced': 25
        }
        mock_sms_metrics_service.get_global_metrics.return_value = mock_sms_metrics
        
        service = DashboardService(
            contact_repository=mock_contact_repo,
            campaign_repository=mock_campaign_repo,
            activity_repository=mock_activity_repo,
            conversation_repository=mock_conversation_repo,
            sms_metrics_service=mock_sms_metrics_service
        )
        
        # Act
        stats = service.get_dashboard_stats()
        
        # Assert - Should use injected SMSMetricsService
        mock_sms_metrics_service.get_global_metrics.assert_called_once_with(days=30)
        assert stats['bounce_rate'] == 2.5
        assert stats['delivery_rate'] == 97.5
        assert stats['total_messages_30d'] == 1000
        assert stats['bounced_messages_30d'] == 25


class TestOpenPhoneWebhookServiceDICompliance:
    """Test OpenPhoneWebhookServiceRefactored follows strict dependency injection patterns"""
    
    def test_webhook_service_requires_both_service_dependencies(self):
        """Test that OpenPhoneWebhookServiceRefactored constructor requires both service dependencies"""
        # This test should FAIL initially because service has fallback logic
        
        # Act & Assert - Constructor should require both dependencies
        with pytest.raises(TypeError, match="missing.*required.*argument"):
            # This should fail if constructor allows None or has fallback logic
            OpenPhoneWebhookServiceRefactored()
    
    def test_webhook_service_stores_injected_services(self):
        """Test that OpenPhoneWebhookServiceRefactored stores both injected services"""
        # Arrange
        mock_contact_service = Mock()
        mock_metrics_service = Mock()
        mock_activity_repo = Mock()
        mock_conversation_repo = Mock()
        mock_webhook_repo = Mock()
        
        # Act
        service = OpenPhoneWebhookServiceRefactored(
            activity_repository=mock_activity_repo,
            conversation_repository=mock_conversation_repo,
            webhook_event_repository=mock_webhook_repo,
            contact_service=mock_contact_service,
            sms_metrics_service=mock_metrics_service
        )
        
        # Assert
        assert service.contact_service is mock_contact_service
        assert service.sms_metrics_service is mock_metrics_service
    
    def test_webhook_service_no_fallback_service_creation(self):
        """Test that OpenPhoneWebhookServiceRefactored does NOT create fallback services"""
        # This test will fail initially because service has fallback logic
        
        with patch('services.openphone_webhook_service_refactored.ContactService') as mock_contact_class:
            with patch('services.openphone_webhook_service_refactored.SMSMetricsService') as mock_metrics_class:
                # Arrange
                mock_contact_service = Mock()
                mock_metrics_service = Mock()
                mock_activity_repo = Mock()
                mock_conversation_repo = Mock()
                mock_webhook_repo = Mock()
                
                # Act
                service = OpenPhoneWebhookServiceRefactored(
                    activity_repository=mock_activity_repo,
                    conversation_repository=mock_conversation_repo,
                    webhook_event_repository=mock_webhook_repo,
                    contact_service=mock_contact_service,
                    sms_metrics_service=mock_metrics_service
                )
                
                # Assert - Neither service class should be instantiated
                mock_contact_class.assert_not_called()
                mock_metrics_class.assert_not_called()
    
    def test_process_webhook_uses_injected_services(self):
        """Test that process_webhook uses injected services exclusively"""
        # Arrange
        mock_contact_service = Mock()
        mock_metrics_service = Mock()
        mock_activity_repo = Mock()
        mock_conversation_repo = Mock()
        mock_webhook_repo = Mock()
        
        # Mock contact service responses
        mock_contact = Mock()
        mock_contact.id = 123
        mock_contact_service.get_contact_by_phone.return_value = mock_contact
        
        service = OpenPhoneWebhookServiceRefactored(
            activity_repository=mock_activity_repo,
            conversation_repository=mock_conversation_repo,
            webhook_event_repository=mock_webhook_repo,
            contact_service=mock_contact_service,
            sms_metrics_service=mock_metrics_service
        )
        
        # Prepare test webhook data
        webhook_data = {
            'type': 'message.received',
            'data': {
                'object': {
                    'id': 'msg_123',
                    'direction': 'incoming',
                    'from': '+15551234567',
                    'text': 'Hello test',
                    'conversationId': 'conv_456',
                    'status': 'received'
                }
            }
        }
        
        # Mock database operations
        with patch('services.openphone_webhook_service.db.session') as mock_db_session:
            with patch('services.openphone_webhook_service.Activity') as mock_activity_class:
                with patch('services.openphone_webhook_service.Conversation') as mock_conversation_class:
                    # Act
                    result = service.process_webhook(webhook_data)
                    
                    # Assert - Should use injected contact service
                    mock_contact_service.get_contact_by_phone.assert_called_once_with('+15551234567')


class TestServiceRegistryDICompliance:
    """Test that service registry factories properly inject all dependencies"""
    
    def test_sms_metrics_service_factory_injects_repositories(self, app):
        """Test that SMS metrics service factory properly injects all required repositories"""
        # This test should FAIL initially because factory doesn't inject dependencies
        
        with app.app_context():
            # Act
            sms_metrics_service = app.services.get('sms_metrics')
            
            # Assert - Service should have all required repository dependencies
            assert hasattr(sms_metrics_service, 'activity_repository')
            assert hasattr(sms_metrics_service, 'contact_repository') 
            assert hasattr(sms_metrics_service, 'campaign_repository')
            
            assert sms_metrics_service.activity_repository is not None
            assert sms_metrics_service.contact_repository is not None
            assert sms_metrics_service.campaign_repository is not None
    
    def test_job_service_factory_injects_repository(self, app):
        """Test that job service factory properly injects JobRepository"""
        # This test should FAIL initially because factory creates service without dependencies
        
        with app.app_context():
            # Act
            job_service = app.services.get('job')
            
            # Assert - Service should have injected JobRepository
            assert hasattr(job_service, 'repository')
            assert job_service.repository is not None
            
            # Should NOT have fallback session access
            assert not hasattr(job_service, 'session')
    
    def test_dashboard_service_factory_injects_sms_metrics_service(self, app):
        """Test that dashboard service factory injects SMSMetricsService"""
        # This test should FAIL initially because factory doesn't inject SMSMetricsService
        
        with app.app_context():
            # Act
            dashboard_service = app.services.get('dashboard')
            
            # Assert - Service should have injected SMSMetricsService
            assert hasattr(dashboard_service, 'metrics_service')
            assert dashboard_service.metrics_service is not None
            
            # The metrics service should be the same instance from the registry
            expected_metrics_service = app.services.get('sms_metrics')
            assert dashboard_service.metrics_service is expected_metrics_service
    
    def test_openphone_webhook_service_factory_injects_both_services(self, app):
        """Test that webhook service factory injects both required services"""
        # This test should PASS because this factory already works correctly
        
        with app.app_context():
            # Act
            webhook_service = app.services.get('openphone_webhook')
            
            # Assert - Service should have both injected services
            assert hasattr(webhook_service, 'contact_service')
            assert hasattr(webhook_service, 'metrics_service')
            
            assert webhook_service.contact_service is not None
            assert webhook_service.metrics_service is not None
    
    @patch('services.sms_metrics_service.SMSMetricsService')
    def test_service_registry_prevents_duplicate_instantiation(self, mock_sms_metrics_class, app):
        """Test that service registry uses singletons and doesn't create duplicate instances"""
        with app.app_context():
            # Act - Get the same service multiple times
            service1 = app.services.get('sms_metrics')
            service2 = app.services.get('sms_metrics')
            service3 = app.services.get('sms_metrics')
            
            # Assert - Should return the same instance (singleton pattern)
            assert service1 is service2
            assert service2 is service3
            
            # SMSMetricsService class should only be instantiated once
            assert mock_sms_metrics_class.call_count == 1


class TestDependencyValidationErrors:
    """Test that services properly validate their dependencies and fail fast"""
    
    def test_sms_metrics_service_validates_repository_types(self):
        """Test that SMSMetricsService validates that injected dependencies are repositories"""
        # Arrange - Pass invalid dependencies
        invalid_dependency = "not_a_repository"
        
        # Act & Assert
        with pytest.raises((TypeError, AttributeError)):
            service = SMSMetricsService(
                activity_repository=invalid_dependency,
                contact_repository=invalid_dependency,
                campaign_repository=invalid_dependency
            )
            # Try to use the service - should fail fast
            service.track_message_status(1, 'delivered')
    
    def test_job_service_validates_repository_type(self):
        """Test that JobService validates that injected dependency is a repository"""
        # Arrange
        invalid_repository = "not_a_repository"
        
        # Act & Assert
        with pytest.raises((TypeError, AttributeError)):
            service = JobService(job_repository=invalid_repository)
            # Try to use the service - should fail fast
            service.get_all_jobs()
    
    def test_dashboard_service_validates_service_types(self):
        """Test that DashboardService validates injected service types"""
        # Arrange
        mock_repos = [Mock(), Mock(), Mock(), Mock()]  # Valid repositories
        invalid_service = "not_a_service"
        
        # Act & Assert
        with pytest.raises((TypeError, AttributeError)):
            service = DashboardService(
                contact_repository=mock_repos[0],
                campaign_repository=mock_repos[1], 
                activity_repository=mock_repos[2],
                conversation_repository=mock_repos[3],
                sms_metrics_service=invalid_service
            )
            # Try to use the service - should fail fast
            service.get_dashboard_stats()
