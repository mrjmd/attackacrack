"""
Integration tests for campaign routes
Tests the full request/response cycle with real database
"""
import pytest
from flask import url_for
from crm_database import Campaign, CampaignMembership, Contact, CampaignList
from unittest.mock import patch, Mock


class TestCampaignRoutesIntegration:
    """Integration tests for campaign routes"""
    
    def test_campaign_list_page(self, authenticated_client, db_session):
        """Test campaign list page loads with campaigns"""
        # Create test campaigns
        campaign1 = Campaign(
            name="Test Campaign 1",
            campaign_type="blast",
            template_a="Test message",
            status="draft"
        )
        campaign2 = Campaign(
            name="Test Campaign 2",
            campaign_type="ab_test",
            template_a="Version A",
            template_b="Version B",
            status="running"
        )
        db_session.add_all([campaign1, campaign2])
        db_session.commit()
        
        # Request the page
        response = authenticated_client.get('/campaigns')
        
        # Assert
        assert response.status_code == 200
        assert b'Test Campaign 1' in response.data
        assert b'Test Campaign 2' in response.data
    
    def test_new_campaign_page(self, authenticated_client, db_session):
        """Test new campaign form page loads"""
        # Create a test list for the form
        test_list = CampaignList(
            name="Test List",
            description="Test list for campaign"
        )
        db_session.add(test_list)
        db_session.commit()
        
        # Request the page
        response = authenticated_client.get('/campaigns/new')
        
        # Assert
        assert response.status_code == 200
        assert b'Create New Campaign' in response.data
        assert b'Test List' in response.data
    
    def test_create_campaign_flow(self, authenticated_client, db_session):
        """Test creating a campaign through the form"""
        # Mock only the external SMS service
        with patch('services.openphone_service.OpenPhoneService.send_message') as mock_send:
            mock_send.return_value = {'success': True}
            
            # Create test contacts
            contacts = []
            for i in range(3):
                contact = Contact(
                    first_name=f"Test{i}",
                    last_name="User",
                    phone=f"+155500000{i}"
                )
                contacts.append(contact)
                db_session.add(contact)
            db_session.commit()
            
            # Submit campaign creation form
            response = authenticated_client.post('/campaigns', data={
                'name': 'Integration Test Campaign',
                'campaign_type': 'blast',
                'audience_type': 'mixed',
                'template_a': 'Hello {first_name}!',
                'daily_limit': '50',
                'business_hours_only': 'on',
                'has_name_only': 'on'
            }, follow_redirects=True)
            
            # Assert campaign was created
            assert response.status_code == 200
            campaign = Campaign.query.filter_by(name='Integration Test Campaign').first()
            assert campaign is not None
            assert campaign.campaign_type == 'blast'
            assert campaign.template_a == 'Hello {first_name}!'
            assert campaign.daily_limit == 50
            assert campaign.business_hours_only is True
    
    def test_campaign_detail_page(self, authenticated_client, db_session):
        """Test campaign detail page with analytics"""
        import time
        unique_id = str(int(time.time() * 1000000))[-6:]
        
        # Create campaign with recipients
        campaign = Campaign(
            name=f"Detail Test Campaign {unique_id}",
            campaign_type="blast",
            template_a="Test message",
            status="running"
        )
        db_session.add(campaign)
        db_session.commit()
        
        # Add some recipients with unique phone numbers
        for i in range(5):
            contact = Contact(
                first_name=f"Contact{i}",
                last_name="Test",
                phone=f"+1555{unique_id}{i:02d}"
            )
            db_session.add(contact)
            db_session.commit()
            
            membership = CampaignMembership(
                campaign_id=campaign.id,
                contact_id=contact.id,
                status='sent' if i < 3 else 'pending'
            )
            db_session.add(membership)
        db_session.commit()
        
        # Request the detail page
        response = authenticated_client.get(f'/campaigns/{campaign.id}')
        
        # Assert
        assert response.status_code == 200
        assert b'Detail Test Campaign' in response.data
        assert b'running' in response.data
    
    def test_start_campaign(self, authenticated_client, db_session):
        """Test starting a campaign"""
        # Create campaign with recipients
        campaign = Campaign(
            name="Start Test Campaign",
            campaign_type="blast",
            template_a="Test message",
            status="draft"
        )
        db_session.add(campaign)
        db_session.commit()
        
        # Add a recipient
        contact = Contact(first_name="Test", phone="+15550001234")
        db_session.add(contact)
        db_session.commit()
        
        membership = CampaignMembership(
            campaign_id=campaign.id,
            contact_id=contact.id,
            status='pending'
        )
        db_session.add(membership)
        db_session.commit()
        
        # Start the campaign
        response = authenticated_client.post(
            f'/campaigns/{campaign.id}/start',
            follow_redirects=True
        )
        
        # Assert
        assert response.status_code == 200
        campaign = Campaign.query.get(campaign.id)
        assert campaign.status == 'running'
        assert b'Campaign started successfully!' in response.data
    
    def test_pause_campaign(self, authenticated_client, db_session):
        """Test pausing a running campaign"""
        # Create running campaign
        campaign = Campaign(
            name="Pause Test Campaign",
            campaign_type="blast",
            template_a="Test message",
            status="running"
        )
        db_session.add(campaign)
        db_session.commit()
        
        # Pause the campaign
        response = authenticated_client.post(
            f'/campaigns/{campaign.id}/pause',
            follow_redirects=True
        )
        
        # Assert
        assert response.status_code == 200
        campaign = Campaign.query.get(campaign.id)
        assert campaign.status == 'paused'
        assert b'Campaign paused' in response.data
    
    def test_api_campaign_analytics(self, authenticated_client, db_session):
        """Test API endpoint for campaign analytics"""
        # Create campaign
        campaign = Campaign(
            name="API Test Campaign",
            campaign_type="blast",
            template_a="Test",
            status="running"
        )
        db_session.add(campaign)
        db_session.commit()
        
        # Request analytics via API
        response = authenticated_client.get(f'/api/campaigns/{campaign.id}/analytics')
        
        # Assert
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert 'analytics' in data
    
    def test_campaign_lists_page(self, authenticated_client, db_session):
        """Test campaign lists management page"""
        # Create test lists
        list1 = CampaignList(name="Static List", is_dynamic=False)
        list2 = CampaignList(
            name="Dynamic List",
            is_dynamic=True,
            filter_criteria={"has_phone": True}
        )
        db_session.add_all([list1, list2])
        db_session.commit()
        
        # Request the page
        response = authenticated_client.get('/campaigns/lists')
        
        # Assert
        assert response.status_code == 200
        assert b'Static List' in response.data
        assert b'Dynamic List' in response.data
    
    def test_create_campaign_list(self, authenticated_client, db_session):
        """Test creating a new campaign list"""
        import time
        unique_id = str(int(time.time() * 1000000))[-6:]
        
        # Submit list creation form
        response = authenticated_client.post('/campaigns/lists/new', data={
            'name': f'New Test List {unique_id}',
            'description': 'Test list description',
            'is_dynamic': ''
        }, follow_redirects=True)
        
        # Assert
        assert response.status_code == 200
        new_list = CampaignList.query.filter_by(name=f'New Test List {unique_id}').first()
        assert new_list is not None
        assert new_list.description == 'Test list description'
        assert new_list.is_dynamic == False
    
    def test_refresh_dynamic_list(self, authenticated_client, db_session):
        """Test refreshing a dynamic campaign list"""
        import time
        unique_id = str(int(time.time() * 1000000))[-6:]
        
        # Create dynamic list
        dynamic_list = CampaignList(
            name=f"Dynamic Test {unique_id}",
            is_dynamic=True,
            filter_criteria={"has_phone": True}
        )
        db_session.add(dynamic_list)
        db_session.commit()
        
        # Add contacts that match criteria with unique phones
        for i in range(3):
            contact = Contact(
                first_name=f"Dynamic{i}",
                last_name="Test",
                phone=f"+1555{unique_id}{i:02d}"
            )
            db_session.add(contact)
        db_session.commit()
        
        # Refresh the list
        response = authenticated_client.post(
            f'/campaigns/lists/{dynamic_list.id}/refresh',
            follow_redirects=True
        )
        
        # Assert
        assert response.status_code == 200
        assert b'List refreshed' in response.data