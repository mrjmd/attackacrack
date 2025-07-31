"""
Fixed tests for Campaign Service
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
from services.campaign_service import CampaignService
from crm_database import db, Contact, Campaign, CampaignMembership, CampaignList, CampaignListMember


class TestCampaignServiceFixed:
    """Fixed test cases for Campaign service"""
    
    @pytest.fixture
    def campaign_service(self, app):
        """Create a campaign service instance"""
        with app.app_context():
            yield CampaignService()
    
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
            
            # Clean up
            db.session.delete(campaign)
            db.session.commit()
    
    def test_create_campaign_all_types(self, campaign_service, app):
        """Test creating campaigns of different types"""
        with app.app_context():
            # Blast campaign
            blast = campaign_service.create_campaign(
                name='Blast Campaign',
                campaign_type='blast',
                audience_type='cold'
            )
            assert blast.campaign_type == 'blast'
            
            # Automated campaign
            automated = campaign_service.create_campaign(
                name='Automated Campaign',
                campaign_type='automated',
                audience_type='customer'
            )
            assert automated.campaign_type == 'automated'
            
            # A/B test campaign
            ab_test = campaign_service.create_campaign(
                name='AB Test',
                campaign_type='ab_test',
                template_a='Version A',
                template_b='Version B'
            )
            assert ab_test.campaign_type == 'ab_test'
            assert ab_test.template_b == 'Version B'
            
            # Clean up
            db.session.query(Campaign).filter(
                Campaign.id.in_([blast.id, automated.id, ab_test.id])
            ).delete(synchronize_session=False)
            db.session.commit()
    
    def test_create_campaign_validation(self, campaign_service, app):
        """Test campaign creation validation"""
        with app.app_context():
            # Invalid campaign type
            with pytest.raises(ValueError, match='Campaign type must be'):
                campaign_service.create_campaign(
                    name='Invalid',
                    campaign_type='invalid'
                )
            
            # Invalid audience type
            with pytest.raises(ValueError, match='Audience type must be'):
                campaign_service.create_campaign(
                    name='Invalid',
                    audience_type='invalid'
                )
            
            # A/B test without template_b
            with pytest.raises(ValueError, match='A/B test campaigns require'):
                campaign_service.create_campaign(
                    name='AB Test',
                    campaign_type='ab_test',
                    template_a='Only A'
                )
    
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
            
            # Test with missing first name
            contact.first_name = None
            result = campaign_service._personalize_message(template, contact)
            assert result == "Hello !"
    
    def test_add_recipients_from_list(self, campaign_service, app):
        """Test adding recipients from a campaign list"""
        with app.app_context():
            # Create test data
            contact1 = Contact(first_name='Test1', last_name='User1', phone='+15551111111')
            contact2 = Contact(first_name='Test2', last_name='User2', phone='+15552222222')
            db.session.add_all([contact1, contact2])
            db.session.commit()
            
            # Create campaign list
            campaign_list = CampaignList(name='Test List')
            db.session.add(campaign_list)
            db.session.commit()
            
            # Add contacts to list
            member1 = CampaignListMember(list_id=campaign_list.id, contact_id=contact1.id)
            member2 = CampaignListMember(list_id=campaign_list.id, contact_id=contact2.id)
            db.session.add_all([member1, member2])
            db.session.commit()
            
            # Create campaign
            campaign = campaign_service.create_campaign(
                name='List Test',
                template_a='Test message'
            )
            
            # Add recipients
            count = campaign_service.add_recipients_from_list(campaign.id, campaign_list.id)
            assert count == 2
            
            # Verify memberships created
            memberships = CampaignMembership.query.filter_by(campaign_id=campaign.id).all()
            assert len(memberships) == 2
            
            # Clean up
            db.session.query(CampaignMembership).filter_by(campaign_id=campaign.id).delete()
            db.session.query(CampaignListMember).filter_by(list_id=campaign_list.id).delete()
            db.session.delete(campaign)
            db.session.delete(campaign_list)
            db.session.delete(contact1)
            db.session.delete(contact2)
            db.session.commit()
    
    def test_is_business_hours(self, campaign_service, app):
        """Test business hours check"""
        with app.app_context():
            # This will depend on current time
            result = campaign_service._is_business_hours()
            assert isinstance(result, bool)
    
    @patch('services.openphone_service.OpenPhoneService')
    def test_send_message(self, mock_openphone, campaign_service, app):
        """Test sending a message"""
        with app.app_context():
            # Mock OpenPhone
            mock_instance = Mock()
            mock_instance.send_sms.return_value = ({'success': True}, None)
            mock_openphone.return_value = mock_instance
            
            result = campaign_service._send_message('+15551234567', 'Test message')
            assert result is True
            
            # Test failure
            mock_instance.send_sms.return_value = (None, 'Error')
            result = campaign_service._send_message('+15551234567', 'Test message')
            assert result is False
    
    def test_get_campaign_analytics(self, campaign_service, app):
        """Test getting campaign analytics"""
        with app.app_context():
            # Create campaign
            campaign = campaign_service.create_campaign(
                name='Analytics Test',
                template_a='Test'
            )
            campaign.status = 'completed'
            db.session.commit()
            
            # Add some memberships
            for i in range(5):
                membership = CampaignMembership(
                    campaign_id=campaign.id,
                    contact_id=1,  # Use seeded contact
                    status='sent' if i < 3 else 'failed'
                )
                db.session.add(membership)
            db.session.commit()
            
            # Get analytics
            analytics = campaign_service.get_campaign_analytics(campaign.id)
            
            assert analytics['campaign_id'] == campaign.id
            assert analytics['total_recipients'] == 5
            assert analytics['sent'] == 3
            assert analytics['failed'] == 2
            assert analytics['delivery_rate'] == 60.0
            
            # Clean up
            db.session.query(CampaignMembership).filter_by(campaign_id=campaign.id).delete()
            db.session.delete(campaign)
            db.session.commit()
    
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
            assert campaign_service.handle_opt_out('+15559999999', 'unsubscribe') is True
            assert campaign_service.handle_opt_out('+15559999999', 'Regular message') is False
            
            # Clean up
            db.session.delete(contact)
            db.session.commit()