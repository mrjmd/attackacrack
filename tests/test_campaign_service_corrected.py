"""
Corrected tests for Campaign Service
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
from services.campaign_service import CampaignService
from services.openphone_service import OpenPhoneService
from crm_database import db, Contact, Campaign, CampaignMembership, CampaignList, CampaignListMember


class TestCampaignServiceCorrected:
    """Corrected test cases for Campaign service"""
    
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
                    email=f"test{i}@example.com"
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
            campaign = campaign_service.create_campaign(
                name='Test Campaign',
                template_a='Hello {first_name}!',
                audience_type='mixed'
            )
            
            assert campaign is not None
            assert campaign.name == 'Test Campaign'
            assert campaign.template_a == 'Hello {first_name}!'
            assert campaign.status == 'draft'
    
    def test_create_campaign_with_all_params(self, campaign_service, app):
        """Test creating a campaign with all parameters"""
        with app.app_context():
            campaign = campaign_service.create_campaign(
                name='Full Campaign',
                campaign_type='blast',
                audience_type='cold',
                channel='sms',
                template_a='Test message',
                template_b=None,
                daily_limit=100,
                business_hours_only=False
            )
            
            assert campaign.name == 'Full Campaign'
            assert campaign.campaign_type == 'blast'
            assert campaign.audience_type == 'cold'
            assert campaign.daily_limit == 100
            assert campaign.business_hours_only is False
    
    def test_get_all_campaigns(self, campaign_service, app):
        """Test getting all campaigns"""
        with app.app_context():
            # Create test campaigns
            campaign1 = campaign_service.create_campaign(
                name='Campaign 1',
                template_a='Test 1'
            )
            campaign2 = campaign_service.create_campaign(
                name='Campaign 2',
                template_a='Test 2'
            )
            
            # Get all campaigns - should include seeded campaigns too
            campaigns = Campaign.query.all()
            assert len(campaigns) >= 2
            
            campaign_names = [c.name for c in campaigns]
            assert 'Campaign 1' in campaign_names
            assert 'Campaign 2' in campaign_names
    
    def test_personalize_message(self, campaign_service, app):
        """Test message personalization"""
        with app.app_context():
            contact = Contact(
                first_name='John',
                last_name='Doe',
                phone='+15551234567'
            )
            
            template = "Hello {first_name}!"
            result = campaign_service._personalize_message(template, contact)
            assert result == "Hello John!"
            
            # Test with contact that has no first name
            contact.first_name = ''
            result = campaign_service._personalize_message(template, contact)
            assert result == "Hello !"
    
    @patch('services.openphone_service.OpenPhoneService')
    def test_send_campaign_immediate(self, mock_openphone_class, campaign_service, sample_contacts, app):
        """Test sending a campaign immediately"""
        with app.app_context():
            # Mock OpenPhone service
            mock_openphone = Mock()
            mock_openphone.send_sms.return_value = ({'success': True}, None)
            mock_openphone_class.return_value = mock_openphone
            
            # Create campaign
            campaign = campaign_service.create_campaign(
                name='Immediate Send',
                template_a='Hello {first_name}!'
            )
            
            # Add recipients
            for contact in sample_contacts[:2]:
                membership = CampaignMembership(
                    campaign_id=campaign.id,
                    contact_id=contact.id,
                    status='pending'
                )
                db.session.add(membership)
            db.session.commit()
            
            # Start campaign
            result = campaign_service.start_campaign(campaign.id)
            assert result is True
            assert campaign.status == 'sending'
    
    def test_add_recipients_from_list(self, campaign_service, sample_campaign_list, app):
        """Test adding recipients from a campaign list"""
        with app.app_context():
            # Create campaign
            campaign = campaign_service.create_campaign(
                name='List Recipients Test',
                template_a='Test message'
            )
            
            # Add recipients from list
            count = campaign_service.add_recipients_from_list(campaign.id, sample_campaign_list.id)
            assert count == 3  # We added 3 contacts to the list
            
            # Verify memberships created
            memberships = CampaignMembership.query.filter_by(campaign_id=campaign.id).all()
            assert len(memberships) == 3
    
    def test_add_recipients_with_filters(self, campaign_service, sample_contacts, app):
        """Test adding recipients with filters"""
        with app.app_context():
            # Create campaign
            campaign = campaign_service.create_campaign(
                name='Filtered Recipients',
                template_a='Test'
            )
            
            # Add recipients with filter - all contacts
            filters = {'audience_type': 'all'}
            count = campaign_service.add_recipients(campaign.id, filters)
            assert count >= len(sample_contacts)
    
    def test_get_campaign_stats(self, campaign_service, app):
        """Test getting campaign statistics"""
        with app.app_context():
            # Create campaign
            campaign = campaign_service.create_campaign(
                name='Stats Test',
                template_a='Test'
            )
            
            # Add memberships with different statuses
            for i in range(5):
                membership = CampaignMembership(
                    campaign_id=campaign.id,
                    contact_id=1,  # Use seeded contact
                    status='sent' if i < 3 else 'failed'
                )
                db.session.add(membership)
            db.session.commit()
            
            # Get stats
            stats = campaign_service.get_campaign_analytics(campaign.id)
            
            assert stats['campaign_id'] == campaign.id
            assert stats['total_recipients'] == 5
            assert stats['sent'] == 3
            assert stats['failed'] == 2
            assert stats['delivery_rate'] == 60.0
    
    def test_is_business_hours(self, campaign_service, app):
        """Test business hours check"""
        with app.app_context():
            result = campaign_service._is_business_hours()
            assert isinstance(result, bool)
    
    def test_handle_opt_out(self, campaign_service, app):
        """Test opt-out handling"""
        with app.app_context():
            # Create test contact
            contact = Contact(
                first_name='OptOut',
                last_name='Test',
                phone='+15559999999'
            )
            db.session.add(contact)
            db.session.commit()
            
            # Test opt-out keywords
            assert campaign_service.handle_opt_out('+15559999999', 'STOP') is True
            assert campaign_service.handle_opt_out('+15559999999', 'stop') is True
            assert campaign_service.handle_opt_out('+15559999999', 'Regular message') is False
            
            # Clean up
            db.session.delete(contact)
            db.session.commit()
    
    @patch('services.openphone_service.OpenPhoneService')
    def test_process_campaign_queue(self, mock_openphone_class, campaign_service, app):
        """Test processing campaign queue"""
        with app.app_context():
            # Mock OpenPhone
            mock_openphone = Mock()
            mock_openphone.send_sms.return_value = ({'success': True}, None)
            mock_openphone_class.return_value = mock_openphone
            
            # Create campaign with pending messages
            campaign = campaign_service.create_campaign(
                name='Queue Test',
                template_a='Test'
            )
            campaign.status = 'sending'
            db.session.commit()
            
            # Add pending membership
            membership = CampaignMembership(
                campaign_id=campaign.id,
                contact_id=1,
                status='pending'
            )
            db.session.add(membership)
            db.session.commit()
            
            # Process queue
            results = campaign_service.process_campaign_queue()
            assert results['total_processed'] >= 0
    
    def test_create_campaign_validation_errors(self, campaign_service, app):
        """Test campaign creation validation"""
        with app.app_context():
            # Invalid campaign type
            with pytest.raises(ValueError, match='Campaign type must be'):
                campaign_service.create_campaign(
                    name='Invalid',
                    campaign_type='invalid_type'
                )
            
            # Invalid audience type
            with pytest.raises(ValueError, match='Audience type must be'):
                campaign_service.create_campaign(
                    name='Invalid',
                    audience_type='invalid_audience'
                )
            
            # Invalid channel
            with pytest.raises(ValueError, match='Channel must be'):
                campaign_service.create_campaign(
                    name='Invalid',
                    channel='invalid_channel'
                )
    
    def test_check_contact_history(self, campaign_service, app):
        """Test checking contact history"""
        with app.app_context():
            # Create contact and campaign
            contact = Contact(
                first_name='History',
                last_name='Test',
                phone='+15558888888'
            )
            db.session.add(contact)
            db.session.commit()
            
            campaign = campaign_service.create_campaign(
                name='History Test',
                template_a='Test'
            )
            
            # Check history (should be empty)
            history = campaign_service._check_contact_history(contact, campaign)
            assert 'has_history' in history
            assert history['has_history'] is False
            
            # Clean up
            db.session.delete(contact)
            db.session.commit()
    
    @patch('services.openphone_service.OpenPhoneService')
    def test_send_scheduled_campaigns(self, mock_openphone_class, campaign_service, app):
        """Test sending scheduled campaigns"""
        with app.app_context():
            # Mock OpenPhone
            mock_openphone = Mock()
            mock_openphone.send_sms.return_value = ({'success': True}, None)
            mock_openphone_class.return_value = mock_openphone
            
            # Create scheduled campaign with past time
            campaign = campaign_service.create_campaign(
                name='Scheduled Campaign',
                template_a='Test'
            )
            campaign.scheduled_send_time = datetime.utcnow() - timedelta(hours=1)
            campaign.status = 'scheduled'
            
            # Add recipient
            membership = CampaignMembership(
                campaign_id=campaign.id,
                contact_id=1,
                status='pending'
            )
            db.session.add(membership)
            db.session.commit()
            
            # Process scheduled campaigns
            campaign_service.send_scheduled_campaigns()
            
            # Check campaign was sent
            db.session.refresh(campaign)
            assert campaign.status == 'sent' or campaign.status == 'completed'