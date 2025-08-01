# tests/test_campaign_integration.py
"""
Integration tests for the full campaign lifecycle:
create list -> create campaign -> add recipients -> process queue -> verify sent messages
"""

import pytest
from unittest.mock import MagicMock, patch, call
from datetime import datetime, timedelta
from services.campaign_service import CampaignService
from services.campaign_list_service import CampaignListService
from crm_database import Campaign, CampaignMembership, Contact, CampaignList, CampaignListMember, Activity, ContactFlag


@pytest.fixture
def campaign_service():
    """Fixture providing campaign service instance"""
    return CampaignService()


@pytest.fixture
def list_service():
    """Fixture providing campaign list service instance"""
    return CampaignListService()


@pytest.fixture
def test_contacts_batch(db_session):
    """Fixture providing a batch of test contacts"""
    import time
    unique_suffix = str(int(time.time() * 1000000))[-6:]
    contacts = []
    for i in range(20):
        contact = Contact(
            first_name=f'Contact{i}',
            last_name=f'Test{i}',
            phone=f'+155{unique_suffix}{i:04d}',
            email=f'contact{i}@example.com' if i % 2 == 0 else None
        )
        contacts.append(contact)
    db_session.add_all(contacts)
    db_session.commit()
    return contacts


class TestFullCampaignLifecycle:
    """Test complete campaign workflow from creation to completion"""
    
    @patch('services.campaign_service.OpenPhoneService')
    def test_blast_campaign_full_lifecycle(self, mock_openphone, campaign_service, list_service, 
                                         test_contacts_batch, db_session):
        """Test a complete blast campaign lifecycle"""
        # Step 1: Create a campaign list
        campaign_list = list_service.create_list(
            name='Summer Sale List',
            description='Contacts for summer sale campaign'
        )
        
        # Step 2: Add contacts to the list
        contact_ids = [c.id for c in test_contacts_batch[:10]]
        results = list_service.add_contacts_to_list(
            campaign_list.id,
            contact_ids,
            added_by='admin@example.com'
        )
        assert results['added'] == 10
        
        # Step 3: Create the campaign
        campaign = campaign_service.create_campaign(
            name='Summer Sale Campaign',
            campaign_type='blast',
            audience_type='mixed',
            template_a='Hi {first_name}, summer sale is here! 20% off all services. Reply STOP to opt out.',
            daily_limit=50,
            business_hours_only=False  # Allow sending anytime for test
        )
        assert campaign.status == 'draft'
        
        # Step 4: Add recipients from the list
        added_count = campaign_service.add_recipients_from_list(campaign.id, campaign_list.id)
        assert added_count == 10
        
        # Step 5: Start the campaign
        campaign_service.start_campaign(campaign.id)
        db_session.refresh(campaign)
        assert campaign.status == 'running'
        
        # Step 6: Mock OpenPhone service
        mock_openphone_instance = MagicMock()
        mock_openphone.return_value = mock_openphone_instance
        mock_openphone_instance.send_message.return_value = (True, 'MSG123')
        
        # Step 7: Process the campaign queue
        stats = campaign_service.process_campaign_queue()
        
        # Verify results
        assert stats['messages_sent'] == 10
        assert stats['messages_skipped'] == 0
        assert len(stats['errors']) == 0
        
        # Verify OpenPhone was called for each recipient
        assert mock_openphone_instance.send_message.call_count == 10
        
        # Verify campaign memberships updated
        sent_members = CampaignMembership.query.filter_by(
            campaign_id=campaign.id,
            status='sent'
        ).count()
        assert sent_members == 10
        
        # Step 8: Check campaign completion
        pending_members = CampaignMembership.query.filter_by(
            campaign_id=campaign.id,
            status='pending'
        ).count()
        assert pending_members == 0
        
        # Campaign should still be running (can be manually stopped)
        db_session.refresh(campaign)
        assert campaign.status == 'running'
    
    @patch('services.campaign_service.OpenPhoneService')
    def test_ab_test_campaign_lifecycle(self, mock_openphone, campaign_service, list_service,
                                       test_contacts_batch, db_session):
        """Test A/B test campaign with winner declaration"""
        # Create campaign list with all contacts
        campaign_list = list_service.create_list(
            name='A/B Test List',
            description='Contacts for A/B testing'
        )
        
        contact_ids = [c.id for c in test_contacts_batch]
        list_service.add_contacts_to_list(campaign_list.id, contact_ids)
        
        # Create A/B test campaign
        campaign = campaign_service.create_campaign(
            name='A/B Test Campaign',
            campaign_type='ab_test',
            template_a='Special offer! Get 20% off today. Reply STOP to opt out.',
            template_b='Limited time: Save 20% on all services! Text STOP to unsubscribe.',
            daily_limit=100,
            business_hours_only=False
        )
        
        # Add recipients and start
        campaign_service.add_recipients_from_list(campaign.id, campaign_list.id)
        campaign_service.start_campaign(campaign.id)
        
        # Mock OpenPhone
        mock_openphone_instance = MagicMock()
        mock_openphone.return_value = mock_openphone_instance
        mock_openphone_instance.send_message.return_value = (True, 'MSG123')
        
        # Process first batch
        stats = campaign_service.process_campaign_queue()
        assert stats['messages_sent'] == 20
        
        # Verify roughly 50/50 split
        variant_a_count = CampaignMembership.query.filter_by(
            campaign_id=campaign.id,
            variant_sent='A'
        ).count()
        variant_b_count = CampaignMembership.query.filter_by(
            campaign_id=campaign.id,
            variant_sent='B'
        ).count()
        
        # Should be roughly equal (allow for randomness)
        assert 5 <= variant_a_count <= 15
        assert 5 <= variant_b_count <= 15
        assert variant_a_count + variant_b_count == 20
    
    @patch('services.campaign_service.OpenPhoneService')
    def test_campaign_with_opt_outs(self, mock_openphone, campaign_service, list_service,
                                   test_contacts_batch, db_session):
        """Test campaign respects opt-outs"""
        # Add opt-out flags for some contacts
        for i in range(0, 5):
            opt_out = ContactFlag(
                contact_id=test_contacts_batch[i].id,
                flag_type='opted_out',
                flag_reason='STOP received',
                applies_to='sms'
            )
            db_session.add(opt_out)
        db_session.commit()
        
        # Create campaign
        campaign = campaign_service.create_campaign(
            name='Opt-out Test Campaign',
            template_a='Test message. Reply STOP to opt out.'
        )
        
        # Add recipients with opt-out filter
        filters = {'exclude_opted_out': True}
        added = campaign_service.add_recipients(campaign.id, filters)
        
        # Should exclude the 5 opted-out contacts
        assert added == 15
        
        # Start and process
        campaign_service.start_campaign(campaign.id)
        
        mock_openphone_instance = MagicMock()
        mock_openphone.return_value = mock_openphone_instance
        mock_openphone_instance.send_message.return_value = (True, 'MSG123')
        
        stats = campaign_service.process_campaign_queue()
        assert stats['messages_sent'] == 15
    
    @patch('services.campaign_service.OpenPhoneService')
    def test_campaign_daily_limit_enforcement(self, mock_openphone, campaign_service,
                                            test_contacts_batch, db_session):
        """Test that daily limits are enforced"""
        # Create campaign with low daily limit
        campaign = campaign_service.create_campaign(
            name='Limited Campaign',
            template_a='Test message',
            daily_limit=5,
            business_hours_only=False
        )
        
        # Add all contacts
        contact_ids = [c.id for c in test_contacts_batch]
        for contact_id in contact_ids:
            membership = CampaignMembership(
                campaign_id=campaign.id,
                contact_id=contact_id,
                status='pending'
            )
            db_session.add(membership)
        db_session.commit()
        
        # Start campaign
        campaign_service.start_campaign(campaign.id)
        
        # Mock OpenPhone
        mock_openphone_instance = MagicMock()
        mock_openphone.return_value = mock_openphone_instance
        mock_openphone_instance.send_message.return_value = (True, 'MSG123')
        
        # First process - should send 5
        stats1 = campaign_service.process_campaign_queue()
        assert stats1['messages_sent'] == 5
        
        # Second process same day - should hit limit
        stats2 = campaign_service.process_campaign_queue()
        assert stats2['messages_sent'] == 0
        assert campaign.name in stats2['daily_limits_reached']
    
    @patch('services.campaign_service.OpenPhoneService')
    def test_campaign_business_hours_enforcement(self, mock_openphone, campaign_service,
                                               test_contacts_batch, db_session):
        """Test that business hours are enforced"""
        # Create campaign with business hours only
        campaign = campaign_service.create_campaign(
            name='Business Hours Campaign',
            template_a='Business hours test',
            business_hours_only=True
        )
        
        # Add recipients
        contact_ids = [c.id for c in test_contacts_batch[:5]]
        for contact_id in contact_ids:
            membership = CampaignMembership(
                campaign_id=campaign.id,
                contact_id=contact_id,
                status='pending'
            )
            db_session.add(membership)
        db_session.commit()
        
        campaign_service.start_campaign(campaign.id)
        
        # Mock OpenPhone
        mock_openphone_instance = MagicMock()
        mock_openphone.return_value = mock_openphone_instance
        mock_openphone_instance.send_message.return_value = (True, 'MSG123')
        
        # Mock current time as outside business hours (8 PM)
        with patch('services.campaign_service.datetime') as mock_datetime:
            mock_datetime.utcnow.return_value = datetime(2025, 7, 29, 20, 0, 0)  # 8 PM
            mock_datetime.strptime = datetime.strptime
            
            stats = campaign_service.process_campaign_queue()
            
            # Should skip all due to business hours
            assert stats['messages_sent'] == 0
            assert stats['messages_skipped'] >= 5


class TestCampaignErrorHandling:
    """Test error handling during campaign lifecycle"""
    
    @patch('services.campaign_service.OpenPhoneService')
    def test_openphone_send_failure_handling(self, mock_openphone, campaign_service,
                                           test_contacts_batch, db_session):
        """Test handling of OpenPhone send failures"""
        # Create and start campaign
        campaign = campaign_service.create_campaign(
            name='Error Test Campaign',
            template_a='Test message'
        )
        
        # Add one recipient
        membership = CampaignMembership(
            campaign_id=campaign.id,
            contact_id=test_contacts_batch[0].id,
            status='pending'
        )
        db_session.add(membership)
        db_session.commit()
        
        campaign_service.start_campaign(campaign.id)
        
        # Mock OpenPhone to fail
        mock_openphone_instance = MagicMock()
        mock_openphone.return_value = mock_openphone_instance
        mock_openphone_instance.send_message.return_value = (False, 'API Error')
        
        # Process queue
        stats = campaign_service.process_campaign_queue()
        
        # Should mark as failed
        assert stats['messages_sent'] == 0
        assert stats['messages_skipped'] == 1
        
        # Verify membership marked as failed
        db_session.refresh(membership)
        assert membership.status == 'failed'
        assert 'API Error' in membership.error_message
    
    def test_campaign_with_invalid_contact_data(self, campaign_service, db_session):
        """Test campaign with contacts missing required data"""
        # Create contact without phone
        contact = Contact(
            first_name='No',
            last_name='Phone',
            email='nophone@example.com'
        )
        db_session.add(contact)
        db_session.commit()
        
        # Create campaign
        campaign = campaign_service.create_campaign(
            name='Invalid Contact Campaign',
            template_a='Test message'
        )
        
        # Add contact
        membership = CampaignMembership(
            campaign_id=campaign.id,
            contact_id=contact.id,
            status='pending'
        )
        db_session.add(membership)
        db_session.commit()
        
        campaign_service.start_campaign(campaign.id)
        
        # Process should skip contact with no phone
        stats = campaign_service.process_campaign_queue()
        assert stats['messages_sent'] == 0
        assert stats['messages_skipped'] >= 1


class TestDynamicListIntegration:
    """Test campaigns with dynamic lists"""
    
    def test_campaign_with_dynamic_list(self, campaign_service, list_service,
                                      test_contacts_batch, db_session):
        """Test campaign using a dynamic list"""
        # Create dynamic list for contacts with email
        criteria = {'has_email': True}
        dynamic_list = list_service.create_list(
            name='Email Contacts',
            filter_criteria=criteria,
            is_dynamic=True
        )
        
        # Create campaign
        campaign = campaign_service.create_campaign(
            name='Dynamic List Campaign',
            template_a='Hello {first_name}!'
        )
        
        # Add recipients from dynamic list
        added = campaign_service.add_recipients_from_list(campaign.id, dynamic_list.id)
        
        # Should add only contacts with email (every other one = 10)
        assert added == 10
        
        # Add new contact with email
        new_contact = Contact(
            first_name='New',
            last_name='Dynamic',
            email='new@example.com',
            phone='+15559999999'
        )
        db_session.add(new_contact)
        db_session.commit()
        
        # Refresh dynamic list
        list_service.refresh_dynamic_list(dynamic_list.id)
        
        # Add new members to campaign
        added_new = campaign_service.add_recipients_from_list(campaign.id, dynamic_list.id)
        
        # Should add the 1 new contact
        assert added_new == 1