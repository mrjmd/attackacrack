"""
Test DashboardService dependency injection
Ensures SMSMetricsService is properly injected
"""
import pytest
from unittest.mock import Mock, MagicMock
from services.dashboard_service import DashboardService


class TestDashboardServiceDependencyInjection:
    """Test proper dependency injection for DashboardService"""
    
    def test_dashboard_service_accepts_sms_metrics_service(self):
        """Test that DashboardService accepts sms_metrics_service as a dependency"""
        # Arrange
        mock_contact_repo = Mock()
        mock_campaign_repo = Mock()
        mock_activity_repo = Mock()
        mock_conversation_repo = Mock()
        mock_sms_metrics = Mock()
        
        # Act
        dashboard_service = DashboardService(
            contact_repository=mock_contact_repo,
            campaign_repository=mock_campaign_repo,
            activity_repository=mock_activity_repo,
            conversation_repository=mock_conversation_repo,
            sms_metrics_service=mock_sms_metrics
        )
        
        # Assert
        assert dashboard_service.sms_metrics_service == mock_sms_metrics
        assert dashboard_service.contact_repository == mock_contact_repo
        assert dashboard_service.campaign_repository == mock_campaign_repo
        assert dashboard_service.activity_repository == mock_activity_repo
        assert dashboard_service.conversation_repository == mock_conversation_repo
    
    def test_dashboard_service_lazy_loads_sms_metrics(self, app):
        """Test that DashboardService can lazy load sms_metrics_service from registry"""
        with app.app_context():
            # Arrange
            mock_sms_metrics = Mock()
            app.services.register_singleton('sms_metrics', lambda: mock_sms_metrics)
            
            # Create DashboardService without sms_metrics_service
            dashboard_service = DashboardService()
            
            # Act
            metrics_service = dashboard_service._get_sms_metrics_service()
            
            # Assert
            assert metrics_service == mock_sms_metrics
            assert dashboard_service.sms_metrics_service == mock_sms_metrics
    
    def test_dashboard_stats_uses_injected_sms_metrics(self):
        """Test that get_dashboard_stats uses the injected sms_metrics_service"""
        # Arrange
        mock_contact_repo = Mock()
        mock_contact_repo.get_total_contacts_count.return_value = 100
        mock_contact_repo.get_contacts_added_this_week_count.return_value = 10
        
        mock_campaign_repo = Mock()
        mock_campaign_repo.get_active_campaigns_count.return_value = 5
        mock_campaign_repo.calculate_average_campaign_response_rate.return_value = 15.5
        
        mock_activity_repo = Mock()
        mock_activity_repo.get_messages_sent_today_count.return_value = 50
        mock_activity_repo.calculate_overall_response_rate.return_value = 12.3
        
        mock_sms_metrics = Mock()
        mock_sms_metrics.get_global_metrics.return_value = {
            'bounce_rate': 2.5,
            'delivery_rate': 97.5,
            'total_sent': 1000,
            'bounced': 25
        }
        
        dashboard_service = DashboardService(
            contact_repository=mock_contact_repo,
            campaign_repository=mock_campaign_repo,
            activity_repository=mock_activity_repo,
            sms_metrics_service=mock_sms_metrics
        )
        
        # Act
        stats = dashboard_service.get_dashboard_stats()
        
        # Assert
        mock_sms_metrics.get_global_metrics.assert_called_once_with(days=30)
        assert stats['bounce_rate'] == 2.5
        assert stats['delivery_rate'] == 97.5
        assert stats['total_messages_30d'] == 1000
        assert stats['bounced_messages_30d'] == 25
    
    def test_service_registry_integration(self, app):
        """Test that DashboardService is properly registered with all dependencies"""
        with app.app_context():
            # Act
            dashboard_service = app.services.get('dashboard')
            
            # Assert
            assert dashboard_service is not None
            assert hasattr(dashboard_service, 'sms_metrics_service')
            assert hasattr(dashboard_service, 'contact_repository')
            assert hasattr(dashboard_service, 'campaign_repository')
            assert hasattr(dashboard_service, 'activity_repository')
            assert hasattr(dashboard_service, 'conversation_repository')
            
            # Verify lazy loading works
            metrics_service = dashboard_service._get_sms_metrics_service()
            assert metrics_service is not None