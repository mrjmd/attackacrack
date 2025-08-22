"""
Integration test for campaign opt-out filtering

Tests that opted-out contacts are properly excluded from campaigns.
"""

import pytest
from datetime import datetime
from app import create_app
from crm_database import db, Contact, ContactFlag, Campaign, CampaignList, CampaignMembership


class TestCampaignOptOutFiltering:
    """Test that campaigns properly filter opted-out contacts"""
    
    @pytest.fixture
    def contacts(self, db_session):
        """Create test contacts using test session"""
        contacts = []
        for i in range(5):
            contact = Contact(
                first_name=f'Contact{i}',
                last_name='Test',
                phone=f'+123456789{i}',
                email=f'contact{i}@example.com'
            )
            contacts.append(contact)
            db_session.add(contact)
        db_session.commit()
        return contacts
    
    @pytest.fixture
    def campaign_list(self, db_session, contacts):
        """Create campaign list with all contacts"""
        campaign_list = CampaignList(
            name='Test List',
            description='All contacts for testing',
            is_dynamic=False
        )
        db_session.add(campaign_list)
        db_session.commit()
        
        # Add all contacts to the campaign list
        from crm_database import CampaignListMember
        for contact in contacts:
            member = CampaignListMember(
                list_id=campaign_list.id,
                contact_id=contact.id,
                status='active'
            )
            db_session.add(member)
        db_session.commit()
        
        return campaign_list
    
    @pytest.fixture
    def campaign(self, db_session, campaign_list):
        """Create test campaign"""
        campaign = Campaign(
            name='Test Campaign',
            campaign_type='blast',
            template_a='Hello {first_name}, this is a test message.',
            status='draft',
            list_id=campaign_list.id
        )
        db_session.add(campaign)
        db_session.commit()
        return campaign
    
    
    def test_campaign_excludes_opted_out_contacts(self, app, db_session, contacts, campaign):
        """Test that opted-out contacts are excluded from campaign membership"""
        with app.app_context():
            # Mark contacts 1 and 3 as opted out
            for idx in [1, 3]:
                flag = ContactFlag(
                    contact_id=contacts[idx].id,
                    flag_type='opted_out',
                    flag_reason='Test opt-out',
                    applies_to='sms',
                    created_by='test'
                )
                db_session.add(flag)
            db_session.commit()
            
            # Get campaign service
            campaign_service = app.services.get('campaign')
            
            # Generate campaign membership
            result = campaign_service.add_recipients_from_list(campaign.id, campaign.list_id)
            
            assert result.is_success
            
            # Check membership was created
            memberships = CampaignMembership.query.filter_by(
                campaign_id=campaign.id
            ).all()
            
            # Should only have 3 members (5 total - 2 opted out)
            assert len(memberships) == 3
            
            # Check that opted-out contacts are not included
            member_contact_ids = [m.contact_id for m in memberships]
            assert contacts[1].id not in member_contact_ids  # Opted out
            assert contacts[3].id not in member_contact_ids  # Opted out
            
            # Check that non-opted-out contacts are included
            assert contacts[0].id in member_contact_ids
            assert contacts[2].id in member_contact_ids
            assert contacts[4].id in member_contact_ids
    
    def test_campaign_respects_temporary_opt_out(self, app, db_session, contacts, campaign):
        """Test that temporarily opted-out contacts are excluded"""
        with app.app_context():
            # Create a temporary opt-out that expires in the future
            flag = ContactFlag(
                contact_id=contacts[0].id,
                flag_type='opted_out',
                flag_reason='Temporary opt-out',
                applies_to='sms',
                expires_at=datetime(2030, 1, 1),  # Future date
                created_by='test'
            )
            db_session.add(flag)
            db_session.commit()
            
            # Get campaign service
            campaign_service = app.services.get('campaign')
            
            # Generate campaign membership
            result = campaign_service.add_recipients_from_list(campaign.id, campaign.list_id)
            
            assert result.is_success
            
            # Check membership
            memberships = CampaignMembership.query.filter_by(
                campaign_id=campaign.id
            ).all()
            
            # Should have 4 members (5 total - 1 temporarily opted out)
            assert len(memberships) == 4
            
            # Check that temporarily opted-out contact is excluded
            member_contact_ids = [m.contact_id for m in memberships]
            assert contacts[0].id not in member_contact_ids
    
    def test_campaign_includes_expired_opt_out(self, app, db_session, contacts, campaign):
        """Test that contacts with expired opt-outs are included"""
        with app.app_context():
            # Create an expired opt-out
            flag = ContactFlag(
                contact_id=contacts[0].id,
                flag_type='opted_out',
                flag_reason='Expired opt-out',
                applies_to='sms',
                expires_at=datetime(2020, 1, 1),  # Past date
                created_by='test'
            )
            db_session.add(flag)
            db_session.commit()
            
            # Get campaign service
            campaign_service = app.services.get('campaign')
            
            # Generate campaign membership
            result = campaign_service.add_recipients_from_list(campaign.id, campaign.list_id)
            
            assert result.is_success
            
            # Check membership
            memberships = CampaignMembership.query.filter_by(
                campaign_id=campaign.id
            ).all()
            
            # Should have all 5 members (expired opt-out doesn't count)
            assert len(memberships) == 5
            
            # Check that contact with expired opt-out is included
            member_contact_ids = [m.contact_id for m in memberships]
            assert contacts[0].id in member_contact_ids
    
    def test_campaign_respects_other_flags(self, app, db_session, contacts, campaign):
        """Test that other exclusion flags also work"""
        with app.app_context():
            # Create different types of exclusion flags
            flags = [
                ContactFlag(
                    contact_id=contacts[0].id,
                    flag_type='office_number',
                    flag_reason='Business phone',
                    applies_to='sms',
                    created_by='test'
                ),
                ContactFlag(
                    contact_id=contacts[1].id,
                    flag_type='do_not_contact',
                    flag_reason='Legal request',
                    applies_to='both',
                    created_by='test'
                ),
                ContactFlag(
                    contact_id=contacts[2].id,
                    flag_type='recently_texted',
                    flag_reason='Texted 2 days ago',
                    applies_to='sms',
                    expires_at=datetime(2030, 1, 1),
                    created_by='test'
                )
            ]
            
            for flag in flags:
                db_session.add(flag)
            db_session.commit()
            
            # Get campaign service
            campaign_service = app.services.get('campaign')
            
            # Generate campaign membership
            result = campaign_service.add_recipients_from_list(campaign.id, campaign.list_id)
            
            assert result.is_success
            
            # Check membership
            memberships = CampaignMembership.query.filter_by(
                campaign_id=campaign.id
            ).all()
            
            # Should have 2 members (5 total - 3 with exclusion flags)
            assert len(memberships) == 2
            
            # Check that flagged contacts are excluded
            member_contact_ids = [m.contact_id for m in memberships]
            assert contacts[0].id not in member_contact_ids  # office_number
            assert contacts[1].id not in member_contact_ids  # do_not_contact
            assert contacts[2].id not in member_contact_ids  # recently_texted
            
            # Only contacts 3 and 4 should be included
            assert contacts[3].id in member_contact_ids
            assert contacts[4].id in member_contact_ids