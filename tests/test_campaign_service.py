"""
Tests for Campaign Service
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
from services.campaign_service import CampaignService
from services.openphone_service import OpenPhoneService
from crm_database import db, Contact, Campaign, CampaignMembership, CampaignList, CampaignListMember


class TestCampaignService:
    """Test cases for Campaign service"""
    
    @pytest.fixture
    def campaign_service(self, app):
        """Create a campaign service instance"""
        with app.app_context():
            service = CampaignService()
            yield service
            # Clean up
            CampaignMembership.query.delete()
            Campaign.query.delete()
            CampaignListMember.query.delete()
            CampaignList.query.delete()
            db.session.commit()
    
    @pytest.fixture
    def sample_contacts(self, app):
        """Create sample contacts for testing"""
        with app.app_context():
            contacts = [
                Contact(
                    first_name=f"Test{i}",
                    last_name=f"Contact{i}",
                    phone=f"+1555123000{i}",
                    email=f"test{i}@example.com",
                    address=f"{i} Test St",
                    tag="active" if i % 2 == 0 else "inactive"
                )
                for i in range(5)
            ]
            db.session.add_all(contacts)
            db.session.commit()
            return contacts
    
    @pytest.fixture
    def sample_campaign_list(self, app, sample_contacts):
        """Create a sample campaign list with members"""
        with app.app_context():
            campaign_list = CampaignList(
                name="Test List",
                description="Test campaign list"
            )
            db.session.add(campaign_list)
            db.session.commit()
            
            # Add first 3 contacts to the list
            for contact in sample_contacts[:3]:
                membership = CampaignListMember(
                    contact_id=contact.id,
                    list_id=campaign_list.id,
                    status='active'
                )
                db.session.add(membership)
            db.session.commit()
            
            return campaign_list
    
    def test_create_campaign_basic(self, campaign_service, app):
        """Test creating a basic campaign"""
        with app.app_context():
            campaign_data = {
                'name': 'Test Campaign',
                'message_template': 'Hello {first_name}!',
                'target_audience': 'all'
            }
            
            campaign = campaign_service.create_campaign(campaign_data)
            
            assert campaign is not None
            assert campaign.name == 'Test Campaign'
            assert campaign.message_template == 'Hello {first_name}!'
            assert campaign.status == 'draft'
    
    def test_create_campaign_with_scheduling(self, campaign_service, app):
        """Test creating a campaign with scheduling"""
        with app.app_context():
            send_time = datetime.utcnow() + timedelta(hours=2)
            campaign_data = {
                'name': 'Scheduled Campaign',
                'message_template': 'Test message',
                'scheduled_send_time': send_time.isoformat(),
                'target_audience': 'all'
            }
            
            campaign = campaign_service.create_campaign(campaign_data)
            
            assert campaign.scheduled_send_time is not None
            assert campaign.status == 'scheduled'
    
    def test_get_target_contacts_all(self, campaign_service, sample_contacts, app):
        """Test getting all contacts as target audience"""
        with app.app_context():
            campaign = Campaign(
                name='Test',
                message_template='Test',
                target_audience='all'
            )
            
            contacts = campaign_service._get_target_contacts(campaign)
            
            assert len(contacts) == len(sample_contacts)
    
    def test_get_target_contacts_by_tag(self, campaign_service, sample_contacts, app):
        """Test getting contacts filtered by tag"""
        with app.app_context():
            campaign = Campaign(
                name='Test',
                message_template='Test',
                target_audience='tag:active'
            )
            
            contacts = campaign_service._get_target_contacts(campaign)
            
            # Should only get contacts with 'active' tag (even indices)
            assert len(contacts) == 3
            assert all(c.tag == 'active' for c in contacts)
    
    def test_get_target_contacts_by_location(self, campaign_service, sample_contacts, app):
        """Test getting contacts filtered by location"""
        with app.app_context():
            campaign = Campaign(
                name='Test',
                message_template='Test',
                target_audience='location:Test St'
            )
            
            contacts = campaign_service._get_target_contacts(campaign)
            
            assert len(contacts) == len(sample_contacts)
            assert all('Test St' in c.address for c in contacts)
    
    def test_get_target_contacts_from_list(self, campaign_service, sample_campaign_list, app):
        """Test getting contacts from a campaign list"""
        with app.app_context():
            campaign = Campaign(
                name='Test',
                message_template='Test',
                target_audience=f'list:{sample_campaign_list.id}'
            )
            
            contacts = campaign_service._get_target_contacts(campaign)
            
            # Should only get the 3 contacts in the list
            assert len(contacts) == 3
    
    def test_get_target_contacts_custom_filter(self, campaign_service, sample_contacts, app):
        """Test getting contacts with custom filter"""
        with app.app_context():
            # Add custom data to one contact
            sample_contacts[0].growth_stage = 'qualified'
            db.session.commit()
            
            campaign = Campaign(
                name='Test',
                message_template='Test',
                target_audience='custom:growth_stage=qualified'
            )
            
            contacts = campaign_service._get_target_contacts(campaign)
            
            assert len(contacts) == 1
            assert contacts[0].growth_stage == 'qualified'
    
    def test_get_target_contacts_invalid_filter(self, campaign_service, app):
        """Test handling invalid target audience filter"""
        with app.app_context():
            campaign = Campaign(
                name='Test',
                message_template='Test',
                target_audience='invalid:filter'
            )
            
            contacts = campaign_service._get_target_contacts(campaign)
            
            # Should return empty list for invalid filter
            assert len(contacts) == 0
    
    def test_personalize_message(self, campaign_service):
        """Test message personalization"""
        contact = Contact(
            first_name='John',
            last_name='Doe',
            phone='+15551234567',
            email='john@example.com'
        )
        
        template = "Hello {first_name} {last_name}! Your phone is {phone}."
        result = campaign_service._personalize_message(template, contact)
        
        assert result == "Hello John Doe! Your phone is +15551234567."
    
    def test_personalize_message_missing_fields(self, campaign_service):
        """Test message personalization with missing fields"""
        contact = Contact(
            first_name='John',
            phone='+15551234567'
        )
        
        template = "Hello {first_name} {last_name}!"
        result = campaign_service._personalize_message(template, contact)
        
        # Should handle missing last_name gracefully
        assert result == "Hello John !"
    
    @patch.object(OpenPhoneService, 'send_sms')
    def test_send_campaign_immediate(self, mock_send_sms, campaign_service, sample_contacts, app):
        """Test sending campaign immediately"""
        mock_send_sms.return_value = {'success': True}
        
        with app.app_context():
            campaign = Campaign(
                name='Test Campaign',
                message_template='Hello {first_name}!',
                target_audience='all'
            )
            db.session.add(campaign)
            db.session.commit()
            
            result = campaign_service.send_campaign(campaign.id)
            
            assert result is True
            assert campaign.status == 'sent'
            assert campaign.sent_at is not None
            
            # Check recipients were created
            recipients = CampaignMembership.query.filter_by(campaign_id=campaign.id).all()
            assert len(recipients) == len(sample_contacts)
            assert all(r.status == 'sent' for r in recipients)
            
            # Verify SMS was sent for each contact
            assert mock_send_sms.call_count == len(sample_contacts)
    
    @patch.object(OpenPhoneService, 'send_sms')
    def test_send_campaign_with_failed_messages(self, mock_send_sms, campaign_service, sample_contacts, app):
        """Test campaign with some failed messages"""
        # Mock some failures
        def send_sms_side_effect(to_number, message):
            if '0001' in to_number:  # Fail for second contact
                return {'error': 'Failed to send'}
            return {'success': True}
        
        mock_send_sms.side_effect = send_sms_side_effect
        
        with app.app_context():
            campaign = Campaign(
                name='Test Campaign',
                message_template='Hello!',
                target_audience='all'
            )
            db.session.add(campaign)
            db.session.commit()
            
            result = campaign_service.send_campaign(campaign.id)
            
            assert result is True
            assert campaign.status == 'sent'
            
            # Check recipient statuses
            recipients = CampaignMembership.query.filter_by(campaign_id=campaign.id).all()
            failed_count = sum(1 for r in recipients if r.status == 'failed')
            sent_count = sum(1 for r in recipients if r.status == 'sent')
            
            assert failed_count == 1
            assert sent_count == len(sample_contacts) - 1
    
    def test_send_campaign_scheduled(self, campaign_service, app):
        """Test that scheduled campaigns are not sent immediately"""
        with app.app_context():
            future_time = datetime.utcnow() + timedelta(hours=2)
            campaign = Campaign(
                name='Scheduled Campaign',
                message_template='Hello!',
                target_audience='all',
                scheduled_send_time=future_time,
                status='scheduled'
            )
            db.session.add(campaign)
            db.session.commit()
            
            result = campaign_service.send_campaign(campaign.id)
            
            # Should not send scheduled campaign
            assert result is False
            assert campaign.status == 'scheduled'
            assert campaign.sent_at is None
    
    def test_send_campaign_nonexistent(self, campaign_service, app):
        """Test sending non-existent campaign"""
        with app.app_context():
            result = campaign_service.send_campaign(99999)
            assert result is False
    
    @patch.object(OpenPhoneService, 'send_sms')
    def test_send_scheduled_campaigns(self, mock_send_sms, campaign_service, app):
        """Test sending due scheduled campaigns"""
        mock_send_sms.return_value = {'success': True}
        
        with app.app_context():
            # Create campaigns with different scheduled times
            past_campaign = Campaign(
                name='Past Campaign',
                message_template='Hello!',
                target_audience='all',
                scheduled_send_time=datetime.utcnow() - timedelta(hours=1),
                status='scheduled'
            )
            future_campaign = Campaign(
                name='Future Campaign',
                message_template='Hello!',
                target_audience='all',
                scheduled_send_time=datetime.utcnow() + timedelta(hours=1),
                status='scheduled'
            )
            
            db.session.add_all([past_campaign, future_campaign])
            db.session.commit()
            
            campaign_service.send_scheduled_campaigns()
            
            # Only past campaign should be sent
            db.session.refresh(past_campaign)
            db.session.refresh(future_campaign)
            
            assert past_campaign.status == 'sent'
            assert future_campaign.status == 'scheduled'
    
    def test_get_campaign_by_id(self, campaign_service, app):
        """Test getting campaign by ID"""
        with app.app_context():
            campaign = Campaign(name='Test', message_template='Test')
            db.session.add(campaign)
            db.session.commit()
            
            result = campaign_service.get_campaign_by_id(campaign.id)
            assert result is not None
            assert result.id == campaign.id
            
            # Test non-existent ID
            result = campaign_service.get_campaign_by_id(99999)
            assert result is None
    
    def test_get_all_campaigns(self, campaign_service, app):
        """Test getting all campaigns"""
        with app.app_context():
            campaigns = [
                Campaign(name=f'Campaign {i}', message_template='Test')
                for i in range(3)
            ]
            db.session.add_all(campaigns)
            db.session.commit()
            
            result = campaign_service.get_all_campaigns()
            assert len(result) == 3
            # Should be ordered by creation date (newest first)
            assert result[0].name == 'Campaign 2'
    
    def test_update_campaign(self, campaign_service, app):
        """Test updating a campaign"""
        with app.app_context():
            campaign = Campaign(
                name='Original Name',
                message_template='Original message',
                status='draft'
            )
            db.session.add(campaign)
            db.session.commit()
            
            update_data = {
                'name': 'Updated Name',
                'message_template': 'Updated message'
            }
            
            updated = campaign_service.update_campaign(campaign.id, update_data)
            
            assert updated is not None
            assert updated.name == 'Updated Name'
            assert updated.message_template == 'Updated message'
    
    def test_update_campaign_nonexistent(self, campaign_service, app):
        """Test updating non-existent campaign"""
        with app.app_context():
            result = campaign_service.update_campaign(99999, {'name': 'Test'})
            assert result is None
    
    def test_delete_campaign(self, campaign_service, app):
        """Test deleting a campaign"""
        with app.app_context():
            campaign = Campaign(name='To Delete', message_template='Test')
            db.session.add(campaign)
            db.session.commit()
            campaign_id = campaign.id
            
            result = campaign_service.delete_campaign(campaign_id)
            assert result is True
            
            # Verify it's deleted
            deleted = Campaign.query.get(campaign_id)
            assert deleted is None
    
    def test_delete_campaign_nonexistent(self, campaign_service, app):
        """Test deleting non-existent campaign"""
        with app.app_context():
            result = campaign_service.delete_campaign(99999)
            assert result is False
    
    def test_get_campaign_stats(self, campaign_service, app):
        """Test getting campaign statistics"""
        with app.app_context():
            campaign = Campaign(
                name='Test Campaign',
                message_template='Test',
                status='sent',
                sent_at=datetime.utcnow()
            )
            db.session.add(campaign)
            db.session.commit()
            
            # Add recipients with different statuses
            recipients = [
                CampaignMembership(campaign_id=campaign.id, contact_id=1, status='sent'),
                CampaignMembership(campaign_id=campaign.id, contact_id=2, status='sent'),
                CampaignMembership(campaign_id=campaign.id, contact_id=3, status='failed'),
                CampaignMembership(campaign_id=campaign.id, contact_id=4, status='pending')
            ]
            db.session.add_all(recipients)
            db.session.commit()
            
            stats = campaign_service.get_campaign_stats(campaign.id)
            
            assert stats['total_recipients'] == 4
            assert stats['sent'] == 2
            assert stats['failed'] == 1
            assert stats['pending'] == 1
            assert stats['success_rate'] == 50.0
    
    def test_get_campaign_stats_no_recipients(self, campaign_service, app):
        """Test campaign stats with no recipients"""
        with app.app_context():
            campaign = Campaign(name='Empty Campaign', message_template='Test')
            db.session.add(campaign)
            db.session.commit()
            
            stats = campaign_service.get_campaign_stats(campaign.id)
            
            assert stats['total_recipients'] == 0
            assert stats['success_rate'] == 0
    
    def test_get_campaign_recipients(self, campaign_service, sample_contacts, app):
        """Test getting campaign recipients"""
        with app.app_context():
            campaign = Campaign(name='Test', message_template='Test')
            db.session.add(campaign)
            db.session.commit()
            
            # Add recipients
            for i, contact in enumerate(sample_contacts[:3]):
                recipient = CampaignMembership(
                    campaign_id=campaign.id,
                    contact_id=contact.id,
                    status='sent' if i < 2 else 'failed'
                )
                db.session.add(recipient)
            db.session.commit()
            
            # Get all recipients
            recipients = campaign_service.get_campaign_recipients(campaign.id)
            assert len(recipients) == 3
            
            # Get only sent recipients
            sent_recipients = campaign_service.get_campaign_recipients(campaign.id, status='sent')
            assert len(sent_recipients) == 2
    
    def test_cancel_scheduled_campaign(self, campaign_service, app):
        """Test canceling a scheduled campaign"""
        with app.app_context():
            campaign = Campaign(
                name='To Cancel',
                message_template='Test',
                status='scheduled',
                scheduled_send_time=datetime.utcnow() + timedelta(hours=1)
            )
            db.session.add(campaign)
            db.session.commit()
            
            result = campaign_service.cancel_campaign(campaign.id)
            
            assert result is True
            assert campaign.status == 'cancelled'
    
    def test_cancel_already_sent_campaign(self, campaign_service, app):
        """Test that sent campaigns cannot be cancelled"""
        with app.app_context():
            campaign = Campaign(
                name='Already Sent',
                message_template='Test',
                status='sent',
                sent_at=datetime.utcnow()
            )
            db.session.add(campaign)
            db.session.commit()
            
            result = campaign_service.cancel_campaign(campaign.id)
            
            assert result is False
            assert campaign.status == 'sent'  # Status unchanged
    
    def test_duplicate_campaign(self, campaign_service, app):
        """Test duplicating a campaign"""
        with app.app_context():
            original = Campaign(
                name='Original Campaign',
                message_template='Hello {first_name}!',
                target_audience='tag:vip'
            )
            db.session.add(original)
            db.session.commit()
            
            duplicate = campaign_service.duplicate_campaign(original.id)
            
            assert duplicate is not None
            assert duplicate.id != original.id
            assert duplicate.name == 'Original Campaign (Copy)'
            assert duplicate.message_template == original.message_template
            assert duplicate.target_audience == original.target_audience
            assert duplicate.status == 'draft'
    
    @patch.object(OpenPhoneService, 'send_sms')
    def test_send_test_message(self, mock_send_sms, campaign_service, sample_contacts, app):
        """Test sending a test message"""
        mock_send_sms.return_value = {'success': True}
        
        with app.app_context():
            campaign = Campaign(
                name='Test Campaign',
                message_template='Hello {first_name}!'
            )
            db.session.add(campaign)
            db.session.commit()
            
            test_contact = sample_contacts[0]
            result = campaign_service.send_test_message(campaign.id, test_contact.id)
            
            assert result is True
            mock_send_sms.assert_called_once()
            call_args = mock_send_sms.call_args[0]
            assert test_contact.phone in call_args[0]
            assert test_contact.first_name in call_args[1]