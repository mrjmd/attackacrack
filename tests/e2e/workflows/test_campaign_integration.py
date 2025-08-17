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


def mock_openphone_service(campaign_service):
    """Helper to mock OpenPhone service on a campaign service instance"""
    mock = MagicMock()
    mock.send_message.return_value = {'success': True, 'message_id': 'MSG123'}
    campaign_service.openphone_service = mock
    return mock


@pytest.fixture
def campaign_service(list_service):
    """Fixture providing campaign service instance with dependencies"""
    from services.openphone_service import OpenPhoneService
    openphone_service = OpenPhoneService()
    return CampaignService(
        openphone_service=openphone_service,
        list_service=list_service
    )


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
            email=f'contact{i}_{unique_suffix}@example.com' if i % 2 == 0 else None
        )
        contacts.append(contact)
    db_session.add_all(contacts)
    db_session.commit()
    return contacts


class TestFullCampaignLifecycle:
    """Test complete campaign workflow from creation to completion"""
    
    def test_blast_campaign_full_lifecycle(self, campaign_service, list_service, 
                                         test_contacts_batch, db_session):
        """Test a complete blast campaign lifecycle"""
        # Mock the OpenPhone service
        mock_openphone = mock_openphone_service(campaign_service)
        
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
        
        # Step 6: Process the campaign queue
        stats = campaign_service.process_campaign_queue()
        
        # Verify results
        assert stats['messages_sent'] == 10
        assert stats['messages_skipped'] == 0
        assert len(stats['errors']) == 0
        
        # Verify OpenPhone was called for each recipient
        assert mock_openphone.send_message.call_count == 10
        
        # Verify campaign memberships updated
        sent_members = CampaignMembership.query.filter_by(
            campaign_id=campaign.id,
            status='sent'
        ).count()
        assert sent_members == 10
        
        # Step 7: Check campaign completion
        pending_members = CampaignMembership.query.filter_by(
            campaign_id=campaign.id,
            status='pending'
        ).count()
        assert pending_members == 0
        
        # Campaign should still be running (can be manually stopped)
        db_session.refresh(campaign)
        assert campaign.status == 'running'
    
    def test_ab_test_campaign_lifecycle(self, campaign_service, list_service,
                                       test_contacts_batch, db_session):
        """Test A/B test campaign with winner declaration"""
        # Mock the OpenPhone service
        mock_openphone = mock_openphone_service(campaign_service)
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
    
    def test_campaign_with_opt_outs(self, campaign_service, list_service,
                                   test_contacts_batch, db_session):
        """Test campaign respects opt-outs"""
        # Mock the OpenPhone service
        mock_openphone = mock_openphone_service(campaign_service)
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
            template_a='Test message. Reply STOP to opt out.',
            business_hours_only=False  # Disable business hours check for test
        )
        
        # Create a list with all test contacts
        campaign_list = list_service.create_list(
            name='Opt-out Test List',
            description='Test list for opt-out campaign'
        )
        
        # Add all test contacts to the list
        contact_ids = [c.id for c in test_contacts_batch]
        list_service.add_contacts_to_list(campaign_list.id, contact_ids)
        
        # Add recipients from the list (will add all 20)
        added = campaign_service.add_recipients_from_list(campaign.id, campaign_list.id)
        assert added == 20  # All contacts are added to campaign
        
        # Start and process
        campaign_service.start_campaign(campaign.id)
        
        # Process campaign - should skip opted-out contacts
        stats = campaign_service.process_campaign_queue()
        assert stats['messages_sent'] == 15  # Only 15 sent (5 skipped due to opt-out)
        assert stats['messages_skipped'] == 5  # 5 skipped
    
    def test_campaign_daily_limit_enforcement(self, campaign_service,
                                            test_contacts_batch, db_session):
        """Test that daily limits are enforced"""
        # Mock the OpenPhone service
        mock_openphone = mock_openphone_service(campaign_service)
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
        
        # First process - should send 5
        stats1 = campaign_service.process_campaign_queue()
        assert stats1['messages_sent'] == 5
        
        # Second process same day - should hit limit
        stats2 = campaign_service.process_campaign_queue()
        assert stats2['messages_sent'] == 0
        assert campaign.name in stats2['daily_limits_reached']
    
    def test_campaign_business_hours_enforcement(self, campaign_service,
                                               test_contacts_batch, db_session):
        """Test that business hours are enforced"""
        # Mock the OpenPhone service
        mock_openphone = mock_openphone_service(campaign_service)
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
        
        # Mock _is_business_hours to return False
        with patch.object(campaign_service, '_is_business_hours', return_value=False):
            stats = campaign_service.process_campaign_queue()
            
            # Should skip all due to business hours
            assert stats['messages_sent'] == 0
            # Business hours check happens early, so no messages are processed/skipped
            assert stats['messages_skipped'] == 0


class TestCampaignErrorHandling:
    """Test error handling during campaign lifecycle"""
    
    def test_openphone_send_failure_handling(self, campaign_service,
                                           test_contacts_batch, db_session):
        """Test handling of OpenPhone send failures"""
        # Ensure no existing campaigns
        Campaign.query.delete()
        db_session.commit()
        
        # Mock the OpenPhone service to fail
        mock_openphone = mock_openphone_service(campaign_service)
        mock_openphone.reset_mock()  # Clear any previous calls
        mock_openphone.send_message.return_value = {'success': False, 'error': 'API Error'}
        # Create and start campaign
        campaign = campaign_service.create_campaign(
            name='Error Test Campaign',
            template_a='Test message',
            business_hours_only=False  # Ensure it processes
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
        
        # Process queue
        stats = campaign_service.process_campaign_queue()
        
        # Should mark as failed
        assert stats['messages_sent'] == 0
        assert stats['messages_skipped'] == 1
        
        # Check mock was called exactly once
        assert mock_openphone.send_message.call_count == 1, f"Expected 1 call, got {mock_openphone.send_message.call_count}"
        
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
            template_a='Test message',
            business_hours_only=False  # Ensure it processes
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
        initial_added = campaign_service.add_recipients_from_list(campaign.id, dynamic_list.id)
        
        # Should add contacts with email - at least the 10 from test_contacts_batch
        assert initial_added >= 10
        
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
        
        # Try to add from refreshed list - since we already added all members,
        # only the new contact should be added (avoids duplicates)
        memberships_before = CampaignMembership.query.filter_by(campaign_id=campaign.id).count()
        
        # Refresh and try to add again
        list_service.refresh_dynamic_list(dynamic_list.id)
        added_new = campaign_service.add_recipients_from_list(campaign.id, dynamic_list.id)
        
        memberships_after = CampaignMembership.query.filter_by(campaign_id=campaign.id).count()
        
        # Should add only the new contact (others already in campaign)
        assert memberships_after == memberships_before + 1