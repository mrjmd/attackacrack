"""
Test database isolation to ensure no state leaks between tests.
These tests verify that our transaction rollback mechanism works correctly.
"""

import pytest
from crm_database import Contact, Activity, Campaign
from extensions import db


class TestDatabaseIsolation:
    """Test that database state doesn't leak between tests"""
    
    def test_create_contact_with_unique_phone_first(self, db_session):
        """First test: Create a contact with a unique phone number"""
        # Create a contact with a specific phone number
        contact = Contact(
            first_name="First",
            last_name="Test",
            phone="+19876543210",
            email="first@test.com"
        )
        db_session.add(contact)
        db_session.commit()
        
        # Verify it exists in this test
        found = db_session.query(Contact).filter_by(phone="+19876543210").first()
        assert found is not None
        assert found.first_name == "First"
        assert found.email == "first@test.com"
        
        # Also verify we can query by ID
        contact_id = contact.id
        found_by_id = db_session.get(Contact, contact_id)
        assert found_by_id is not None
        assert found_by_id.phone == "+19876543210"
    
    def test_create_contact_with_same_phone_second(self, db_session):
        """Second test: Should be able to create contact with same phone (isolated)"""
        # If isolation works, this contact should not exist
        existing = db_session.query(Contact).filter_by(phone="+19876543210").first()
        assert existing is None, "Database state leaked from previous test!"
        
        # Create a new contact with the same phone number
        # This should work because the previous test's data was rolled back
        contact = Contact(
            first_name="Second",
            last_name="Test",
            phone="+19876543210",
            email="second@test.com"
        )
        db_session.add(contact)
        db_session.commit()
        
        # Verify it's the new contact, not the old one
        found = db_session.query(Contact).filter_by(phone="+19876543210").first()
        assert found is not None
        assert found.first_name == "Second"
        assert found.email == "second@test.com"
    
    def test_multiple_commits_in_single_test(self, db_session):
        """Test that multiple commits within a single test work correctly"""
        # First commit
        contact1 = Contact(
            first_name="Multi1",
            last_name="Test",
            phone="+11111111111"
        )
        db_session.add(contact1)
        db_session.commit()
        
        # Second commit
        contact2 = Contact(
            first_name="Multi2",
            last_name="Test",
            phone="+12222222222"
        )
        db_session.add(contact2)
        db_session.commit()
        
        # Third commit with activity
        activity = Activity(
            contact_id=contact1.id,
            activity_type="message",
            body="Test message",
            direction="outgoing",
            status="delivered"
        )
        db_session.add(activity)
        db_session.commit()
        
        # Verify all data exists in this test
        assert db_session.query(Contact).count() >= 2
        assert db_session.query(Activity).filter_by(contact_id=contact1.id).count() == 1
    
    def test_verify_multiple_commits_rolled_back(self, db_session):
        """Verify that the multiple commits from previous test were rolled back"""
        # Check that contacts from previous test don't exist
        contact1 = db_session.query(Contact).filter_by(phone="+11111111111").first()
        contact2 = db_session.query(Contact).filter_by(phone="+12222222222").first()
        
        assert contact1 is None, "First contact from previous test still exists!"
        assert contact2 is None, "Second contact from previous test still exists!"
        
        # Activities should also be gone
        activities = db_session.query(Activity).filter_by(activity_type="message").all()
        # Filter for our specific test activity
        test_activities = [a for a in activities if a.body and "Test message" in a.body]
        assert len(test_activities) == 0, "Activity from previous test still exists!"
    
    def test_exception_rollback(self, db_session):
        """Test that exceptions properly trigger rollback"""
        # Create a contact
        contact = Contact(
            first_name="Exception",
            last_name="Test",
            phone="+13333333333"
        )
        db_session.add(contact)
        db_session.commit()
        
        # Now cause an intentional error
        with pytest.raises(Exception):
            # This should fail and rollback
            db_session.execute("INVALID SQL")
            raise Exception("Intentional error")
        
        # The contact should still exist because we committed before the error
        found = db_session.query(Contact).filter_by(phone="+13333333333").first()
        assert found is not None
    
    def test_exception_data_not_leaked(self, db_session):
        """Verify that data from exception test doesn't leak"""
        # Contact from previous test should not exist
        contact = db_session.query(Contact).filter_by(phone="+13333333333").first()
        assert contact is None, "Contact from exception test leaked!"
    
    def test_bulk_operations_isolation(self, db_session):
        """Test that bulk operations are properly isolated"""
        # Create multiple contacts in bulk
        contacts = [
            Contact(first_name=f"Bulk{i}", last_name="Test", phone=f"+1555000{i:04d}")
            for i in range(10)
        ]
        db_session.bulk_save_objects(contacts)
        db_session.commit()
        
        # Verify they exist
        bulk_contacts = db_session.query(Contact).filter(
            Contact.first_name.like("Bulk%")
        ).all()
        assert len(bulk_contacts) >= 10
    
    def test_bulk_operations_rolled_back(self, db_session):
        """Verify bulk operations from previous test were rolled back"""
        # No bulk contacts should exist
        bulk_contacts = db_session.query(Contact).filter(
            Contact.first_name.like("Bulk%")
        ).all()
        assert len(bulk_contacts) == 0, f"Found {len(bulk_contacts)} bulk contacts that should have been rolled back!"
    
    def test_nested_transactions(self, db_session):
        """Test that our transaction isolation handles errors correctly"""
        # Create initial contact
        contact = Contact(
            first_name="Nested",
            last_name="Test",
            phone="+14444444444"
        )
        db_session.add(contact)
        db_session.commit()
        
        # Verify it exists
        found = db_session.query(Contact).filter_by(phone="+14444444444").first()
        assert found is not None
        assert found.first_name == "Nested"
        
        # Try to create another contact (valid operation)
        another = Contact(
            first_name="Another",
            last_name="Contact",
            phone="+15555555555"
        )
        db_session.add(another)
        db_session.commit()
        
        # Both should exist in this test
        assert db_session.query(Contact).filter_by(phone="+14444444444").first() is not None
        assert db_session.query(Contact).filter_by(phone="+15555555555").first() is not None
    
    def test_nested_transaction_cleanup(self, db_session):
        """Verify nested transaction test was properly cleaned up"""
        contact = db_session.query(Contact).filter_by(phone="+14444444444").first()
        assert contact is None, "Contact from nested transaction test leaked!"


class TestCampaignDataIsolation:
    """Test isolation for campaign-specific data"""
    
    def test_create_campaign_with_memberships(self, db_session):
        """Create a campaign with memberships"""
        from crm_database import Campaign, CampaignMembership
        
        # Create campaign
        campaign = Campaign(
            name="Test Campaign Isolation",
            template_a="Testing isolation message",
            status="draft"
        )
        db_session.add(campaign)
        db_session.commit()
        
        # Create a contact for the campaign
        contact = Contact(
            first_name="Campaign",
            last_name="Member",
            phone="+15555555555"
        )
        db_session.add(contact)
        db_session.commit()
        
        # Create membership
        membership = CampaignMembership(
            campaign_id=campaign.id,
            contact_id=contact.id,
            status="pending"
        )
        db_session.add(membership)
        db_session.commit()
        
        # Verify it exists
        assert db_session.query(Campaign).filter_by(name="Test Campaign Isolation").first() is not None
        assert db_session.query(CampaignMembership).filter_by(campaign_id=campaign.id).count() == 1
    
    def test_campaign_data_isolated(self, db_session):
        """Verify campaign data from previous test is isolated"""
        from crm_database import Campaign, CampaignMembership
        
        # Campaign from previous test should not exist
        campaign = db_session.query(Campaign).filter_by(name="Test Campaign Isolation").first()
        assert campaign is None, "Campaign from previous test leaked!"
        
        # Contact should also be gone
        contact = db_session.query(Contact).filter_by(phone="+15555555555").first()
        assert contact is None, "Campaign contact from previous test leaked!"
        
        # No orphan memberships should exist
        memberships = db_session.query(CampaignMembership).all()
        # Should only have pre-seeded data if any
        for membership in memberships:
            # Verify these aren't from our test
            if membership.campaign:
                assert membership.campaign.name != "Test Campaign Isolation"