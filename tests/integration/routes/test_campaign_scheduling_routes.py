"""
TDD Tests for Campaign Scheduling Routes - Phase 3C
Tests for HTTP API endpoints that expose campaign scheduling functionality

These tests MUST FAIL initially following TDD Red-Green-Refactor cycle.
Tests define the REST API for campaign scheduling features.
"""

import pytest
import json
from datetime import datetime, timedelta
from unittest.mock import patch, Mock
from utils.datetime_utils import utc_now
from services.common.result import Result


class TestCampaignSchedulingRoutes:
    """TDD tests for campaign scheduling HTTP routes"""
    
    def test_schedule_campaign_endpoint(self, authenticated_client, db_session):
        """Test POST /api/campaigns/{id}/schedule endpoint"""
        # Arrange
        from crm_database import Campaign
        campaign = Campaign(name="Test Campaign", status="draft")
        db_session.add(campaign)
        db_session.commit()
        
        scheduled_time = utc_now() + timedelta(hours=2)
        request_data = {
            "scheduled_at": scheduled_time.isoformat(),
            "timezone": "America/New_York"
        }
        
        # Act - This will FAIL until route is implemented
        response = authenticated_client.post(
            f'/api/campaigns/{campaign.id}/schedule',
            data=json.dumps(request_data),
            content_type='application/json'
        )
        
        # Assert
        assert response.status_code == 200
        
        response_data = response.get_json()
        assert response_data['success'] is True
        assert response_data['campaign_id'] == campaign.id
        assert 'scheduled_at' in response_data
        
        # Verify campaign was updated in database
        db_session.refresh(campaign)
        assert campaign.status == "scheduled"
        assert campaign.timezone == "America/New_York"
        
    def test_schedule_campaign_validation_errors(self, authenticated_client, db_session):
        """Test schedule endpoint validation"""
        from crm_database import Campaign
        campaign = Campaign(name="Test Campaign", status="draft")
        db_session.add(campaign)
        db_session.commit()
        
        # Test past time
        past_time = utc_now() - timedelta(hours=1)
        request_data = {
            "scheduled_at": past_time.isoformat(),
            "timezone": "UTC"
        }
        
        # This will FAIL until validation is implemented
        response = authenticated_client.post(
            f'/api/campaigns/{campaign.id}/schedule',
            data=json.dumps(request_data),
            content_type='application/json'
        )
        
        assert response.status_code == 400
        response_data = response.get_json()
        assert response_data['success'] is False
        assert "past" in response_data['error'].lower()
        
    def test_create_recurring_campaign_endpoint(self, authenticated_client, db_session):
        """Test POST /api/campaigns/{id}/recurring endpoint"""
        from crm_database import Campaign
        campaign = Campaign(name="Test Campaign", status="draft")
        db_session.add(campaign)
        db_session.commit()
        
        start_time = utc_now() + timedelta(hours=1)
        request_data = {
            "start_at": start_time.isoformat(),
            "recurrence_pattern": {
                "type": "daily",
                "interval": 1,
                "end_date": "2025-12-31"
            },
            "timezone": "America/New_York"
        }
        
        # Act - This will FAIL until route is implemented
        response = authenticated_client.post(
            f'/api/campaigns/{campaign.id}/recurring',
            data=json.dumps(request_data),
            content_type='application/json'
        )
        
        # Assert
        assert response.status_code == 200
        
        response_data = response.get_json()
        assert response_data['success'] is True
        assert response_data['is_recurring'] is True
        assert 'next_run_at' in response_data
        
        # Verify database updates
        db_session.refresh(campaign)
        assert campaign.is_recurring is True
        assert campaign.recurrence_pattern['type'] == "daily"
        
    def test_get_campaign_schedule_info_endpoint(self, authenticated_client, db_session):
        """Test GET /api/campaigns/{id}/schedule endpoint"""
        from crm_database import Campaign
        
        scheduled_time = utc_now() + timedelta(hours=2)
        campaign = Campaign(
            name="Scheduled Campaign",
            status="scheduled",
            scheduled_at=scheduled_time,
            timezone="America/New_York",
            is_recurring=False
        )
        db_session.add(campaign)
        db_session.commit()
        
        # Act - This will FAIL until route is implemented
        response = authenticated_client.get(f'/api/campaigns/{campaign.id}/schedule')
        
        # Assert
        assert response.status_code == 200
        
        response_data = response.get_json()
        assert response_data['success'] is True
        assert response_data['campaign_id'] == campaign.id
        assert response_data['is_scheduled'] is True
        assert response_data['timezone'] == "America/New_York"
        assert response_data['is_recurring'] is False
        
    def test_cancel_scheduled_campaign_endpoint(self, authenticated_client, db_session):
        """Test POST /api/campaigns/{id}/cancel-schedule endpoint"""
        from crm_database import Campaign
        
        campaign = Campaign(
            name="Scheduled Campaign",
            status="scheduled",
            scheduled_at=utc_now() + timedelta(hours=2)
        )
        db_session.add(campaign)
        db_session.commit()
        
        # Act - This will FAIL until route is implemented
        response = authenticated_client.post(f'/api/campaigns/{campaign.id}/cancel-schedule')
        
        # Assert
        assert response.status_code == 200
        
        response_data = response.get_json()
        assert response_data['success'] is True
        assert response_data['status'] == "draft"
        
        # Verify campaign was reset
        db_session.refresh(campaign)
        assert campaign.status == "draft"
        assert campaign.scheduled_at is None
        
    def test_duplicate_campaign_endpoint(self, authenticated_client, db_session):
        """Test POST /api/campaigns/{id}/duplicate endpoint"""
        from crm_database import Campaign
        
        original = Campaign(
            name="Original Campaign",
            status="complete",
            template_a="Hello {{first_name}}",
            campaign_type="blast",
            daily_limit=125
        )
        db_session.add(original)
        db_session.commit()
        
        request_data = {
            "name": "Duplicated Campaign",
            "scheduled_at": (utc_now() + timedelta(hours=3)).isoformat(),
            "timezone": "America/Los_Angeles"
        }
        
        # Act - This will FAIL until route is implemented
        response = authenticated_client.post(
            f'/api/campaigns/{original.id}/duplicate',
            data=json.dumps(request_data),
            content_type='application/json'
        )
        
        # Assert
        assert response.status_code == 200
        
        response_data = response.get_json()
        assert response_data['success'] is True
        assert 'campaign_id' in response_data
        
        duplicate_id = response_data['campaign_id']
        duplicate = db_session.query(Campaign).get(duplicate_id)
        
        assert duplicate.name == "Duplicated Campaign"
        assert duplicate.parent_campaign_id == original.id
        assert duplicate.template_a == original.template_a
        assert duplicate.status == "scheduled"
        
    def test_archive_campaign_endpoint(self, authenticated_client, db_session):
        """Test POST /api/campaigns/{id}/archive endpoint"""
        from crm_database import Campaign
        
        campaign = Campaign(name="Completed Campaign", status="complete")
        db_session.add(campaign)
        db_session.commit()
        
        request_data = {
            "reason": "Campaign completed successfully"
        }
        
        # Act - This will FAIL until route is implemented
        response = authenticated_client.post(
            f'/api/campaigns/{campaign.id}/archive',
            data=json.dumps(request_data),
            content_type='application/json'
        )
        
        # Assert
        assert response.status_code == 200
        
        response_data = response.get_json()
        assert response_data['success'] is True
        assert response_data['archived'] is True
        
        # Verify database update
        db_session.refresh(campaign)
        assert campaign.archived is True
        assert campaign.archived_at is not None
        
    def test_get_archived_campaigns_endpoint(self, authenticated_client, db_session):
        """Test GET /api/campaigns/archived endpoint"""
        from crm_database import Campaign
        
        # Create archived campaigns
        archived_campaigns = []
        for i in range(3):
            campaign = Campaign(
                name=f"Archived Campaign {i+1}",
                status="complete",
                archived=True,
                archived_at=utc_now() - timedelta(days=i+1)
            )
            archived_campaigns.append(campaign)
            db_session.add(campaign)
            
        db_session.commit()
        
        # Act - This will FAIL until route is implemented
        response = authenticated_client.get('/api/campaigns/archived')
        
        # Assert
        assert response.status_code == 200
        
        response_data = response.get_json()
        assert response_data['success'] is True
        assert len(response_data['campaigns']) == 3
        
        # Verify campaign data structure
        for campaign_data in response_data['campaigns']:
            assert 'id' in campaign_data
            assert 'name' in campaign_data
            assert 'archived_at' in campaign_data
            assert campaign_data['archived'] is True
            
    def test_bulk_schedule_campaigns_endpoint(self, authenticated_client, db_session):
        """Test POST /api/campaigns/bulk-schedule endpoint"""
        from crm_database import Campaign
        
        # Create multiple campaigns
        campaigns = []
        for i in range(3):
            campaign = Campaign(name=f"Bulk Campaign {i+1}", status="draft")
            campaigns.append(campaign)
            db_session.add(campaign)
            
        db_session.commit()
        
        request_data = {
            "campaign_ids": [c.id for c in campaigns],
            "scheduled_at": (utc_now() + timedelta(hours=4)).isoformat(),
            "timezone": "UTC"
        }
        
        # Act - This will FAIL until route is implemented
        response = authenticated_client.post(
            '/api/campaigns/bulk-schedule',
            data=json.dumps(request_data),
            content_type='application/json'
        )
        
        # Assert
        assert response.status_code == 200
        
        response_data = response.get_json()
        assert response_data['success'] is True
        assert response_data['campaigns_scheduled'] == 3
        assert response_data['failed_campaigns'] == []
        
        # Verify all campaigns were scheduled
        for campaign in campaigns:
            db_session.refresh(campaign)
            assert campaign.status == "scheduled"
            
    def test_get_campaign_calendar_endpoint(self, authenticated_client, db_session):
        """Test GET /api/campaigns/calendar endpoint"""
        from crm_database import Campaign
        
        # Create campaigns for different dates
        base_time = utc_now().replace(hour=10, minute=0, second=0, microsecond=0)
        
        campaigns_data = [
            ("Today", base_time + timedelta(hours=2)),
            ("Tomorrow", base_time + timedelta(days=1)),
            ("Next Week", base_time + timedelta(days=7))
        ]
        
        for name, scheduled_time in campaigns_data:
            campaign = Campaign(
                name=f"{name} Campaign",
                status="scheduled",
                scheduled_at=scheduled_time,
                timezone="UTC"
            )
            db_session.add(campaign)
            
        db_session.commit()
        
        # Act - This will FAIL until route is implemented
        start_date = base_time.date().isoformat()
        end_date = (base_time + timedelta(days=10)).date().isoformat()
        
        response = authenticated_client.get(
            f'/api/campaigns/calendar?start_date={start_date}&end_date={end_date}'
        )
        
        # Assert
        assert response.status_code == 200
        
        response_data = response.get_json()
        assert response_data['success'] is True
        assert 'calendar_data' in response_data
        
        calendar_data = response_data['calendar_data']
        assert isinstance(calendar_data, list)
        
        # Verify structure
        for day_data in calendar_data:
            assert 'date' in day_data
            assert 'campaigns' in day_data
            assert isinstance(day_data['campaigns'], list)
            
    def test_get_scheduled_campaigns_endpoint(self, authenticated_client, db_session):
        """Test GET /api/campaigns/scheduled endpoint"""
        from crm_database import Campaign
        
        # Create scheduled campaigns
        for i in range(5):
            campaign = Campaign(
                name=f"Scheduled Campaign {i+1}",
                status="scheduled",
                scheduled_at=utc_now() + timedelta(hours=i+1),
                timezone="UTC"
            )
            db_session.add(campaign)
            
        db_session.commit()
        
        # Act - This will FAIL until route is implemented
        response = authenticated_client.get('/api/campaigns/scheduled')
        
        # Assert
        assert response.status_code == 200
        
        response_data = response.get_json()
        assert response_data['success'] is True
        assert len(response_data['campaigns']) == 5
        
        # Verify sorting by scheduled_at
        campaigns = response_data['campaigns']
        for i in range(1, len(campaigns)):
            prev_time = datetime.fromisoformat(campaigns[i-1]['scheduled_at'])
            curr_time = datetime.fromisoformat(campaigns[i]['scheduled_at'])
            assert prev_time <= curr_time
            
    def test_route_authentication_required(self, client, db_session):
        """Test that all scheduling routes require authentication"""
        from crm_database import Campaign
        campaign = Campaign(name="Test Campaign", status="draft")
        db_session.add(campaign)
        db_session.commit()
        
        # Test various endpoints without authentication
        endpoints_to_test = [
            ('GET', f'/api/campaigns/{campaign.id}/schedule'),
            ('POST', f'/api/campaigns/{campaign.id}/schedule'),
            ('POST', f'/api/campaigns/{campaign.id}/recurring'),
            ('POST', f'/api/campaigns/{campaign.id}/duplicate'),
            ('POST', f'/api/campaigns/{campaign.id}/archive'),
            ('GET', '/api/campaigns/scheduled'),
            ('GET', '/api/campaigns/archived'),
            ('GET', '/api/campaigns/calendar'),
            ('POST', '/api/campaigns/bulk-schedule')
        ]
        
        for method, endpoint in endpoints_to_test:
            if method == 'GET':
                response = client.get(endpoint)
            else:
                response = client.post(endpoint, data='{}', content_type='application/json')
                
            # Should redirect to login or return 401
            assert response.status_code in [302, 401]
            
    def test_route_validation_missing_campaign(self, authenticated_client):
        """Test route behavior with non-existent campaign IDs"""
        non_existent_id = 99999
        
        # This will FAIL until proper 404 handling is implemented
        response = authenticated_client.get(f'/api/campaigns/{non_existent_id}/schedule')
        
        assert response.status_code == 404
        
        response_data = response.get_json()
        assert response_data['success'] is False
        assert "not found" in response_data['error'].lower()
        
    def test_route_input_validation(self, authenticated_client, db_session):
        """Test route input validation"""
        from crm_database import Campaign
        campaign = Campaign(name="Test Campaign", status="draft")
        db_session.add(campaign)
        db_session.commit()
        
        # Test invalid JSON
        response = authenticated_client.post(
            f'/api/campaigns/{campaign.id}/schedule',
            data='invalid json',
            content_type='application/json'
        )
        
        assert response.status_code == 400
        
        # Test missing required fields
        response = authenticated_client.post(
            f'/api/campaigns/{campaign.id}/schedule',
            data=json.dumps({}),  # Empty data
            content_type='application/json'
        )
        
        assert response.status_code == 400
        response_data = response.get_json()
        assert "required" in response_data['error'].lower()
        
    def test_route_permission_checks(self, authenticated_client, db_session):
        """Test that users can only access their campaigns"""
        from crm_database import Campaign, User
        
        # This test assumes multi-tenant setup - may need adjustment
        other_user = User(
            email="other@example.com",
            first_name="Other",
            last_name="User",
            password_hash="hashed"
        )
        db_session.add(other_user)
        db_session.commit()
        
        other_campaign = Campaign(
            name="Other User's Campaign",
            status="draft",
            created_by_id=other_user.id  # If this field exists
        )
        db_session.add(other_campaign)
        db_session.commit()
        
        # Try to access other user's campaign - This will FAIL until authorization is implemented
        response = authenticated_client.get(f'/api/campaigns/{other_campaign.id}/schedule')
        
        # Should return 403 Forbidden or 404 Not Found
        assert response.status_code in [403, 404]
        
    def test_timezone_list_endpoint(self, authenticated_client):
        """Test GET /api/timezones endpoint for timezone selection"""
        # Act - This will FAIL until route is implemented
        response = authenticated_client.get('/api/timezones')
        
        # Assert
        assert response.status_code == 200
        
        response_data = response.get_json()
        assert response_data['success'] is True
        assert 'timezones' in response_data
        
        timezones = response_data['timezones']
        assert isinstance(timezones, list)
        assert len(timezones) > 0
        
        # Verify common timezones are included
        timezone_identifiers = [tz['identifier'] for tz in timezones]
        assert "America/New_York" in timezone_identifiers
        assert "America/Los_Angeles" in timezone_identifiers
        assert "UTC" in timezone_identifiers
        
        # Verify timezone data structure
        for tz in timezones:
            assert 'identifier' in tz
            assert 'display_name' in tz
            assert 'utc_offset' in tz