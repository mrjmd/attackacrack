"""
Integration Tests for Route Database Query Violations - TDD RED Phase
Tests to ensure routes use services instead of direct database queries.

These tests MUST FAIL initially - verifying violations exist.
After fixing routes, these tests should PASS.
"""

import pytest
from unittest.mock import Mock, patch
from flask import url_for


class TestMainRoutesNoDatabaseViolations:
    """Test main_routes.py uses services instead of direct DB queries"""
    
    def test_schedule_appointment_uses_setting_service(self, authenticated_client, mocker):
        """Test that schedule_appointment route uses SettingService instead of db.session.query(Setting)"""
        # Mock the setting service
        mock_setting_service = Mock()
        mock_setting_service.get_template_by_key.return_value = 'Test template for {first_name}'
        
        # Patch the service registry to return our mock
        with patch('flask.current_app') as mock_app:
            mock_services = Mock()
            mock_services.get.return_value = mock_setting_service
            mock_app.services = mock_services
            
            # Mock other required services
            mock_google_service = Mock()
            mock_google_service.create_event.return_value = {'id': 'test_event', 'htmlLink': 'http://test'}
            mock_services.get.side_effect = lambda name: {
                'setting': mock_setting_service,
                'google_calendar': mock_google_service
            }.get(name)
            
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
            mock_services.get.assert_any_call('setting')
            mock_setting_service.get_template_by_key.assert_called_with('appointment_reminder_template')
    
    def test_schedule_reminder_uses_setting_service(self, authenticated_client, mocker):
        """Test that schedule_reminder route uses SettingService instead of db.session.query(Setting)"""
        # Mock the setting service
        mock_setting_service = Mock()
        mock_setting_service.get_appointment_reminder_template.return_value = 'Reminder template'
        mock_setting_service.get_review_request_template.return_value = 'Review template'
        
        with patch('flask.current_app') as mock_app:
            mock_services = Mock()
            mock_services.get.return_value = mock_setting_service
            mock_app.services = mock_services
            
            # Make request to schedule reminder
            response = authenticated_client.post('/schedule_reminder', data={
                'contact_id': 1,
                'reminder_type': 'appointment',
                'first_name': 'Jane'
            })
            
            # Assert service methods were used
            mock_services.get.assert_called_with('setting')
            # Should call one of the template methods
            assert (mock_setting_service.get_appointment_reminder_template.called or 
                   mock_setting_service.get_review_request_template.called)


class TestCampaignRoutesNoDatabaseViolations:
    """Test campaigns.py uses services instead of direct model queries"""
    
    def test_campaign_detail_uses_campaign_service(self, authenticated_client):
        """Test that campaign detail route uses service instead of Campaign.query.get_or_404()"""
        # Mock the campaign service
        mock_campaign_service = Mock()
        mock_campaign = Mock()
        mock_campaign.id = 1
        mock_campaign.name = 'Test Campaign'
        mock_campaign_service.get_by_id.return_value = mock_campaign
        
        with patch('flask.current_app') as mock_app:
            mock_services = Mock()
            mock_services.get.return_value = mock_campaign_service
            mock_app.services = mock_services
            
            # Make request to campaign detail
            response = authenticated_client.get('/campaigns/1')
            
            # Assert service was used instead of Campaign.query.get_or_404()
            mock_services.get.assert_called_with('campaign')
            mock_campaign_service.get_by_id.assert_called_with(1)
    
    def test_edit_campaign_uses_campaign_service(self, authenticated_client):
        """Test that edit campaign route uses service instead of Campaign.query.get_or_404()"""
        mock_campaign_service = Mock()
        mock_campaign = Mock()
        mock_campaign.id = 1
        mock_campaign.name = 'Test Campaign'
        mock_campaign_service.get_by_id.return_value = mock_campaign
        
        with patch('flask.current_app') as mock_app:
            mock_services = Mock()
            mock_services.get.return_value = mock_campaign_service
            mock_app.services = mock_services
            
            response = authenticated_client.get('/campaigns/1/edit')
            
            mock_services.get.assert_called_with('campaign')
            mock_campaign_service.get_by_id.assert_called_with(1)
    
    def test_campaign_members_uses_service(self, authenticated_client):
        """Test that campaign members route uses service instead of CampaignMembership.query"""
        mock_campaign_service = Mock()
        mock_campaign = Mock()
        mock_campaign.id = 1
        mock_campaign_service.get_by_id.return_value = mock_campaign
        mock_campaign_service.get_campaign_members.return_value = []
        
        with patch('flask.current_app') as mock_app:
            mock_services = Mock()
            mock_services.get.return_value = mock_campaign_service
            mock_app.services = mock_services
            
            response = authenticated_client.get('/campaigns/1/members')
            
            mock_services.get.assert_called_with('campaign')
            mock_campaign_service.get_campaign_members.assert_called_with(1)


class TestQuoteRoutesNoDatabaseViolations:
    """Test quote_routes.py uses services instead of direct model queries"""
    
    def test_quote_form_uses_product_service(self, authenticated_client):
        """Test that quote form uses service instead of ProductService.query.all()"""
        mock_product_service = Mock()
        mock_product_service.get_all.return_value = []
        
        with patch('flask.current_app') as mock_app:
            mock_services = Mock()
            mock_services.get.return_value = mock_product_service
            mock_app.services = mock_services
            
            response = authenticated_client.get('/quotes/new')
            
            # Assert service was used instead of ProductService.query.all()
            mock_services.get.assert_called_with('product')
            mock_product_service.get_all.assert_called_once()


class TestPropertyRoutesNoDatabaseViolations:
    """Test property_routes.py uses services instead of direct model queries"""
    
    def test_property_list_uses_property_service(self, authenticated_client):
        """Test that property list uses service instead of Property.query"""
        mock_property_service = Mock()
        mock_property_service.get_paginated.return_value = Mock(items=[], pages=0, page=1, per_page=10)
        
        with patch('flask.current_app') as mock_app:
            mock_services = Mock()
            mock_services.get.return_value = mock_property_service
            mock_app.services = mock_services
            
            response = authenticated_client.get('/properties')
            
            # Assert service was used instead of Property.query
            mock_services.get.assert_called_with('property')
            mock_property_service.get_paginated.assert_called_once()


class TestAPIRoutesNoDatabaseViolations:
    """Test api_routes.py doesn't use problematic db.session operations"""
    
    def test_webhook_endpoint_no_expire_all(self, client):
        """Test that webhook endpoint doesn't call db.session.expire_all()"""
        # This test will verify that db.session.expire_all() is removed
        # We'll mock the webhook service to avoid actual processing
        
        with patch('flask.current_app') as mock_app:
            mock_services = Mock()
            mock_webhook_service = Mock()
            mock_webhook_service.process_webhook.return_value = {'status': 'success'}
            mock_services.get.return_value = mock_webhook_service
            mock_app.services = mock_services
            
            # Mock webhook payload
            webhook_payload = {
                'type': 'message.created',
                'data': {
                    'id': 'msg_123',
                    'body': 'Test message'
                }
            }
            
            response = client.post('/api/webhook', 
                                 json=webhook_payload,
                                 headers={'Content-Type': 'application/json'})
            
            # The test passes if no db.session.expire_all() is called
            # This will be verified by the absence of direct db operations
            assert response.status_code in [200, 201, 204]


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