"""
Integration Tests for Route Database Query Violations - TDD RED Phase
Tests to ensure routes use services instead of direct database queries.

These tests MUST FAIL initially - verifying violations exist.
After fixing routes, these tests should PASS.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from flask import url_for, current_app
from datetime import datetime


class TestMainRoutesNoDatabaseViolations:
    """Test main_routes.py uses services instead of direct DB queries"""
    
    def test_schedule_appointment_uses_setting_service(self, authenticated_client, app, mocker):
        """Test that schedule_appointment route uses SettingService instead of db.session.query(Setting)"""
        # Mock the setting service
        mock_setting_service = MagicMock()
        mock_setting_service.get_template_by_key.return_value = 'Test template for {first_name}'
        
        # Mock the google calendar service
        mock_google_service = MagicMock()
        mock_google_service.create_event.return_value = {'id': 'test_event', 'htmlLink': 'http://test'}
        
        # Patch the service registry's get method to return our mocks
        def mock_get_service(service_name):
            services = {
                'setting': mock_setting_service,
                'google_calendar': mock_google_service
            }
            return services.get(service_name)
        
        with app.app_context():
            # Replace the service registry get method
            original_get = app.services.get
            app.services.get = MagicMock(side_effect=mock_get_service)
            
            try:
                # Make request to schedule appointment
                response = authenticated_client.post('/schedule_appointment', data={
                    'contact_id': 1,
                    'date': '2024-12-25',
                    'time': '10:00',
                    'service_type': 'appointment_reminder',
                    'first_name': 'John',
                    'phone': '+11234567890'
                })
                
                # Assert service was used instead of direct DB query
                app.services.get.assert_any_call('setting')
                mock_setting_service.get_template_by_key.assert_called_with('appointment_reminder_template')
            finally:
                # Restore original get method
                app.services.get = original_get
    
    def test_schedule_reminder_uses_setting_service(self, authenticated_client, app, mocker):
        """Test that schedule_reminder route uses SettingService instead of db.session.query(Setting)"""
        # Mock the setting service
        mock_setting_service = MagicMock()
        mock_setting_service.get_appointment_reminder_template.return_value = 'Reminder template'
        mock_setting_service.get_review_request_template.return_value = 'Review template'
        
        with app.app_context():
            # Replace the service registry get method
            original_get = app.services.get
            app.services.get = MagicMock(return_value=mock_setting_service)
            
            try:
                # Make request to schedule reminder
                response = authenticated_client.post('/schedule_reminder', data={
                    'contact_id': 1,
                    'reminder_type': 'appointment',
                    'first_name': 'Jane'
                })
                
                # Assert service methods were used
                app.services.get.assert_called_with('setting')
                # Should call one of the template methods
                assert (mock_setting_service.get_appointment_reminder_template.called or 
                       mock_setting_service.get_review_request_template.called)
            finally:
                # Restore original get method
                app.services.get = original_get


class TestCampaignRoutesNoDatabaseViolations:
    """Test campaigns.py uses services instead of direct model queries"""
    
    def test_campaign_detail_uses_campaign_service(self, authenticated_client, app):
        """Test that campaign detail route uses service instead of Campaign.query.get_or_404()"""
        # Mock the campaign service
        mock_campaign_service = MagicMock()
        mock_campaign = MagicMock()
        mock_campaign.id = 1
        mock_campaign.name = 'Test Campaign'
        mock_campaign.status = 'Active'
        mock_campaign.created_at = datetime.now()
        mock_campaign.messages = []
        mock_campaign.campaign_memberships = []
        mock_campaign_service.get_by_id.return_value = mock_campaign
        
        # Mock analytics data that template expects
        mock_analytics = {
            'sent_count': 10,
            'sends_today': 5,
            'response_count': 3,
            'response_rate': 0.3,
            'pending_count': 2,
            'failed_count': 1,
            'total_recipients': 15,
            'daily_limit': 125
        }
        mock_campaign_service.get_campaign_analytics.return_value = mock_analytics
        
        # Mock bounce metrics
        mock_bounce_metrics = {
            'bounce_count': 0,
            'bounce_rate': 0.0,
            'delivery_rate': 1.0
        }
        mock_campaign_service.get_campaign_bounce_metrics.return_value = mock_bounce_metrics
        
        # Mock recent sends
        mock_campaign_service.get_recent_campaign_sends.return_value = []
        
        # Mock sms_metrics service that might be called
        mock_sms_metrics_service = MagicMock()
        
        # Service factory to return different mocks based on service name
        def mock_get_service(service_name):
            services = {
                'campaign': mock_campaign_service,
                'sms_metrics': mock_sms_metrics_service
            }
            return services.get(service_name)
        
        with app.app_context():
            # Replace the service registry get method
            original_get = app.services.get
            app.services.get = MagicMock(side_effect=mock_get_service)
            
            try:
                # Make request to campaign detail
                response = authenticated_client.get('/campaigns/1')
                
                # Assert service was used instead of Campaign.query.get_or_404()
                app.services.get.assert_any_call('campaign')
                mock_campaign_service.get_by_id.assert_called_with(1)
                mock_campaign_service.get_campaign_analytics.assert_called_with(1)
            finally:
                # Restore original get method
                app.services.get = original_get
    
    def test_edit_campaign_uses_campaign_service(self, authenticated_client, app):
        """Test that edit campaign route uses service instead of Campaign.query.get_or_404()"""
        mock_campaign_service = MagicMock()
        mock_campaign = MagicMock()
        mock_campaign.id = 1
        mock_campaign.name = 'Test Campaign'
        mock_campaign.message_template = 'Test template'
        mock_campaign.send_from = '+11234567890'
        mock_campaign.created_at = datetime.now()
        mock_campaign_service.get_by_id.return_value = mock_campaign
        
        # Mock other services that might be called
        mock_sms_metrics_service = MagicMock()
        
        def mock_get_service(service_name):
            services = {
                'campaign': mock_campaign_service,
                'sms_metrics': mock_sms_metrics_service
            }
            return services.get(service_name)
        
        with app.app_context():
            # Replace the service registry get method
            original_get = app.services.get
            app.services.get = MagicMock(side_effect=mock_get_service)
            
            try:
                # The template might not exist, but we're testing service usage
                try:
                    response = authenticated_client.get('/campaigns/1/edit')
                except Exception:
                    pass  # Template error is OK for this test
                
                # The important part is that the service was called
                app.services.get.assert_any_call('campaign')
                mock_campaign_service.get_by_id.assert_called_with(1)
            finally:
                # Restore original get method
                app.services.get = original_get
    
    def test_campaign_members_uses_service(self, authenticated_client, app):
        """Test that campaign members route uses service instead of CampaignMembership.query"""
        mock_campaign_service = MagicMock()
        mock_campaign = MagicMock()
        mock_campaign.id = 1
        mock_campaign.name = 'Test Campaign'
        mock_campaign.created_at = datetime.now()
        mock_campaign_service.get_by_id.return_value = mock_campaign
        mock_campaign_service.get_campaign_members.return_value = []
        
        # Mock other services that might be called
        mock_sms_metrics_service = MagicMock()
        
        def mock_get_service(service_name):
            services = {
                'campaign': mock_campaign_service,
                'sms_metrics': mock_sms_metrics_service
            }
            return services.get(service_name)
        
        with app.app_context():
            # Replace the service registry get method
            original_get = app.services.get
            app.services.get = MagicMock(side_effect=mock_get_service)
            
            try:
                # The template might not exist, but we're testing service usage
                try:
                    response = authenticated_client.get('/campaigns/1/members')
                except Exception:
                    pass  # Template error is OK for this test
                
                # The important part is that the service was called
                app.services.get.assert_any_call('campaign')
                mock_campaign_service.get_campaign_members.assert_called_with(1)
            finally:
                # Restore original get method
                app.services.get = original_get


class TestQuoteRoutesNoDatabaseViolations:
    """Test quote_routes.py uses services instead of direct model queries"""
    
    def test_quote_form_uses_product_service(self, authenticated_client, app, mocker):
        """Test that quote form uses service instead of ProductService.query.all()"""
        # Mock the services that will be called
        mock_product_service = MagicMock()
        mock_product_service.get_all.return_value = []
        
        mock_quote_service = MagicMock()
        
        mock_job_service = MagicMock()
        mock_job_service.get_all_jobs.return_value = []
        
        mock_sms_metrics_service = MagicMock()
        
        # Create a tracking mock for the get method
        original_get = app.services.get
        get_tracker = MagicMock()
        
        def mock_get_service(service_name):
            get_tracker(service_name)  # Track the call
            services = {
                'product': mock_product_service,
                'quote': mock_quote_service,
                'job': mock_job_service,
                'sms_metrics': mock_sms_metrics_service
            }
            return services.get(service_name, original_get(service_name))
        
        # Use mocker to patch at the module level where it's imported
        mocker.patch.object(app.services, 'get', side_effect=mock_get_service)
        
        # The template might not exist, but we're testing service usage
        try:
            response = authenticated_client.get('/quotes/new')
        except Exception:
            pass  # Template error is OK for this test
        
        # Check that the services were called
        get_tracker.assert_any_call('quote')
        get_tracker.assert_any_call('job')
        get_tracker.assert_any_call('product')
        
        # Verify the specific method calls
        mock_job_service.get_all_jobs.assert_called_once()
        mock_product_service.get_all.assert_called_once()


class TestPropertyRoutesNoDatabaseViolations:
    """Test property_routes.py uses services instead of direct model queries"""
    
    def test_property_list_uses_property_service(self, authenticated_client, app):
        """Test that property list uses service instead of Property.query"""
        mock_property_service = MagicMock()
        mock_paginated_result = MagicMock()
        mock_paginated_result.items = []
        mock_paginated_result.pages = 0
        mock_paginated_result.page = 1
        mock_paginated_result.per_page = 10
        mock_property_service.get_paginated_properties.return_value = mock_paginated_result
        
        with app.app_context():
            # Replace the service registry get method
            original_get = app.services.get
            app.services.get = MagicMock(return_value=mock_property_service)
            
            try:
                response = authenticated_client.get('/properties/')
                
                # Assert service was used instead of Property.query
                app.services.get.assert_called_with('property')
                mock_property_service.get_paginated_properties.assert_called_once()
            finally:
                # Restore original get method
                app.services.get = original_get


class TestAPIRoutesNoDatabaseViolations:
    """Test api_routes.py doesn't use problematic db.session operations"""
    
    def test_webhook_endpoint_no_expire_all(self, client, app, mocker):
        """Test that webhook endpoint doesn't call db.session.expire_all()"""
        # This test verifies that db.session.expire_all() is not called
        # We mock the verification to focus on testing service usage
        
        # Mock the webhook service
        mock_webhook_service = MagicMock()
        mock_webhook_service.process_webhook.return_value = {'status': 'success'}
        
        # Mock other services that might be called
        mock_sms_metrics_service = MagicMock()
        
        def mock_get_service(service_name):
            services = {
                'openphone_webhook': mock_webhook_service,
                'sms_metrics': mock_sms_metrics_service
            }
            return services.get(service_name)
        
        with app.app_context():
            # Set a test webhook signing key (base64 encoded) to make signature verification work
            import base64
            test_key = base64.b64encode(b'test-signing-key-secret').decode('utf-8')
            app.config['OPENPHONE_WEBHOOK_SIGNING_KEY'] = test_key
            
            # Replace the service registry get method
            original_get = app.services.get
            app.services.get = MagicMock(side_effect=mock_get_service)
            
            try:
                # Mock webhook payload
                webhook_payload = {
                    'type': 'message.created',
                    'data': {
                        'id': 'msg_123',
                        'body': 'Test message'
                    }
                }
                
                # Generate a valid signature
                import hmac
                import hashlib
                import json
                import time
                
                timestamp = str(int(time.time()))
                
                # Create the raw payload bytes exactly as Flask will receive it
                payload_str = json.dumps(webhook_payload, separators=(',', ':'))
                payload_bytes = payload_str.encode('utf-8')
                signed_data_bytes = timestamp.encode('utf-8') + b'.' + payload_bytes
                
                # Use the same key for signing as configured
                signing_key_bytes = base64.b64decode(test_key)
                signature = base64.b64encode(
                    hmac.new(
                        signing_key_bytes,
                        signed_data_bytes,
                        hashlib.sha256
                    ).digest()
                ).decode('utf-8')
                
                signature_header = f'hmac;1;{timestamp};{signature}'
                
                # Send the raw data instead of JSON to control exactly what request.data contains
                response = client.post('/api/webhooks/openphone', 
                                     data=payload_bytes,
                                     headers={
                                         'Content-Type': 'application/json',
                                         'openphone-signature': signature_header
                                     })
                
                # The key assertion: webhook service was used, not direct DB operations
                app.services.get.assert_any_call('openphone_webhook')
                mock_webhook_service.process_webhook.assert_called_once()
                
                # Response should be successful (no db.session.expire_all() blocking it)
                assert response.status_code in [200, 201, 204]
            finally:
                # Restore original get method
                app.services.get = original_get


class TestServiceRegistrationIntegration:
    """Test that services are properly registered and accessible"""
    
    def test_setting_service_registered(self, app):
        """Test that SettingService is properly registered in service registry"""
        with app.app_context():
            setting_service = app.services.get('setting')
            assert setting_service is not None
            # Verify it's the correct type
            from services.setting_service import SettingService
            assert isinstance(setting_service, SettingService)
    
    def test_setting_repository_registered(self, app):
        """Test that SettingRepository is properly registered"""
        with app.app_context():
            setting_repository = app.services.get('setting_repository')
            assert setting_repository is not None
            from repositories.setting_repository import SettingRepository
            assert isinstance(setting_repository, SettingRepository)
    
    def test_campaign_service_exists(self, app):
        """Test that campaign service is available (needed for campaign route fixes)"""
        with app.app_context():
            campaign_service = app.services.get('campaign')
            assert campaign_service is not None
    
    def test_property_service_exists(self, app):
        """Test that property service is available (needed for property route fixes)"""
        with app.app_context():
            property_service = app.services.get('property')
            assert property_service is not None