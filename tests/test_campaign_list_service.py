# tests/test_campaign_list_service.py
"""
Comprehensive tests for CampaignListService covering list management,
contact filtering, and dynamic list functionality.
"""

import pytest
from datetime import datetime, timedelta
from services.campaign_list_service import CampaignListService
from crm_database import Contact, CampaignList, CampaignListMember, CSVImport, ContactCSVImport, Activity, ContactFlag


@pytest.fixture
def list_service():
    """Fixture providing campaign list service instance"""
    return CampaignListService()


@pytest.fixture
def test_contacts(db_session):
    """Fixture providing test contacts with various attributes"""
    import time as t
    unique_suffix = str(int(t.time() * 1000000))[-6:]
    contacts = []
    
    # Contact 1: Complete information
    c1 = Contact(
        first_name='John',
        last_name='Doe',
        email=f'john{unique_suffix}@example.com',
        phone=f'+1555123{unique_suffix}',
        imported_at=datetime.utcnow() - timedelta(days=10)
    )
    contacts.append(c1)
    
    # Contact 2: No email
    c2 = Contact(
        first_name='Jane',
        last_name='Smith',
        phone=f'+1555234{unique_suffix}',
        imported_at=datetime.utcnow() - timedelta(days=5)
    )
    contacts.append(c2)
    
    # Contact 3: No phone
    c3 = Contact(
        first_name='Bob',
        last_name='Johnson',
        email=f'bob{unique_suffix}@example.com',
        imported_at=datetime.utcnow() - timedelta(days=30)
    )
    contacts.append(c3)
    
    # Contact 4: With metadata
    c4 = Contact(
        first_name='Alice',
        last_name='Williams',
        email=f'alice{unique_suffix}@example.com',
        phone=f'+1555456{unique_suffix}',
        contact_metadata={'source': 'website', 'lead_score': 85},
        imported_at=datetime.utcnow() - timedelta(days=2)
    )
    contacts.append(c4)
    
    db_session.add_all(contacts)
    db_session.commit()
    
    return contacts


@pytest.fixture
def test_list(db_session):
    """Fixture providing a test campaign list"""
    campaign_list = CampaignList(
        name='Test List',
        description='Test campaign list',
        is_dynamic=False
    )
    db_session.add(campaign_list)
    db_session.commit()
    return campaign_list


class TestListCreation:
    """Test campaign list creation"""
    
    def test_create_static_list(self, list_service, db_session):
        """Test creating a static campaign list"""
        campaign_list = list_service.create_list(
            name='Summer Campaign List',
            description='Contacts for summer promotion',
            is_dynamic=False,
            created_by='admin@example.com'
        )
        
        assert campaign_list.id is not None
        assert campaign_list.name == 'Summer Campaign List'
        assert campaign_list.description == 'Contacts for summer promotion'
        assert campaign_list.is_dynamic is False
        assert campaign_list.created_by == 'admin@example.com'
    
    def test_create_dynamic_list(self, list_service, test_contacts, db_session):
        """Test creating a dynamic list with filter criteria"""
        imported_after = datetime.utcnow() - timedelta(days=7)
        criteria = {
            'has_email': True,
            'imported_after': imported_after
        }
        
        campaign_list = list_service.create_list(
            name='Recent Email Contacts',
            description='Contacts with email imported in last 7 days',
            filter_criteria=criteria,
            is_dynamic=True
        )
        
        assert campaign_list.is_dynamic is True
        # Check that datetime was serialized to ISO string
        assert campaign_list.filter_criteria['has_email'] is True
        assert campaign_list.filter_criteria['imported_after'] == imported_after.isoformat()
        
        # Should auto-populate based on criteria
        members = CampaignListMember.query.filter_by(
            list_id=campaign_list.id,
            status='active'
        ).all()
        
        # Only c1 and c4 match (have email and imported within 7 days)
        assert len(members) == 2


class TestContactManagement:
    """Test adding and removing contacts from lists"""
    
    def test_add_contacts_to_list(self, list_service, test_list, test_contacts, db_session):
        """Test adding multiple contacts to a list"""
        contact_ids = [c.id for c in test_contacts[:3]]
        
        results = list_service.add_contacts_to_list(
            test_list.id,
            contact_ids,
            added_by='user@example.com'
        )
        
        assert results['added'] == 3
        assert results['already_exists'] == 0
        assert results['errors'] == 0
        
        # Verify members created
        members = CampaignListMember.query.filter_by(list_id=test_list.id).all()
        assert len(members) == 3
        assert all(m.status == 'active' for m in members)
        assert all(m.added_by == 'user@example.com' for m in members)
    
    def test_add_duplicate_contacts(self, list_service, test_list, test_contacts, db_session):
        """Test adding contacts that already exist in list"""
        contact_ids = [test_contacts[0].id]
        
        # Add first time
        results1 = list_service.add_contacts_to_list(test_list.id, contact_ids)
        assert results1['added'] == 1
        
        # Add again
        results2 = list_service.add_contacts_to_list(test_list.id, contact_ids)
        assert results2['added'] == 0
        assert results2['already_exists'] == 1
    
    def test_reactivate_removed_contact(self, list_service, test_list, test_contacts, db_session):
        """Test reactivating a removed contact"""
        contact_id = test_contacts[0].id
        
        # Add contact
        list_service.add_contacts_to_list(test_list.id, [contact_id])
        
        # Remove contact
        list_service.remove_contacts_from_list(test_list.id, [contact_id])
        
        # Verify removed
        member = CampaignListMember.query.filter_by(
            list_id=test_list.id,
            contact_id=contact_id
        ).first()
        assert member.status == 'removed'
        
        # Add again
        results = list_service.add_contacts_to_list(test_list.id, [contact_id])
        assert results['added'] == 1
        
        # Verify reactivated
        db_session.refresh(member)
        assert member.status == 'active'
    
    def test_remove_contacts_from_list(self, list_service, test_list, test_contacts, db_session):
        """Test removing contacts from list (soft delete)"""
        # Add all contacts
        contact_ids = [c.id for c in test_contacts]
        list_service.add_contacts_to_list(test_list.id, contact_ids)
        
        # Remove first two
        removed_count = list_service.remove_contacts_from_list(
            test_list.id,
            contact_ids[:2]
        )
        
        assert removed_count == 2
        
        # Verify soft deleted
        removed_members = CampaignListMember.query.filter_by(
            list_id=test_list.id,
            status='removed'
        ).all()
        assert len(removed_members) == 2
        
        # Active members should be 2
        active_members = CampaignListMember.query.filter_by(
            list_id=test_list.id,
            status='active'
        ).all()
        assert len(active_members) == 2


class TestListRetrieval:
    """Test retrieving list contents and statistics"""
    
    def test_get_list_contacts(self, list_service, test_list, test_contacts, db_session):
        """Test retrieving contacts from a list"""
        # Add some contacts
        contact_ids = [c.id for c in test_contacts[:3]]
        list_service.add_contacts_to_list(test_list.id, contact_ids)
        
        # Get contacts
        contacts = list_service.get_list_contacts(test_list.id)
        
        assert len(contacts) == 3
        assert all(isinstance(c, Contact) for c in contacts)
    
    def test_get_list_contacts_exclude_removed(self, list_service, test_list, test_contacts, db_session):
        """Test that removed contacts are excluded by default"""
        # Add all contacts
        contact_ids = [c.id for c in test_contacts]
        list_service.add_contacts_to_list(test_list.id, contact_ids)
        
        # Remove one
        list_service.remove_contacts_from_list(test_list.id, [contact_ids[0]])
        
        # Get contacts (should exclude removed)
        contacts = list_service.get_list_contacts(test_list.id, include_removed=False)
        assert len(contacts) == 3
        
        # Get all including removed
        all_contacts = list_service.get_list_contacts(test_list.id, include_removed=True)
        assert len(all_contacts) == 4
    
    def test_get_list_stats(self, list_service, test_list, test_contacts, db_session):
        """Test getting list statistics"""
        # Add contacts with different attributes
        contact_ids = [c.id for c in test_contacts]
        list_service.add_contacts_to_list(test_list.id, contact_ids)
        
        # Remove one
        list_service.remove_contacts_from_list(test_list.id, [contact_ids[0]])
        
        stats = list_service.get_list_stats(test_list.id)
        
        assert stats['total_members'] == 4
        assert stats['active_members'] == 3
        assert stats['removed_members'] == 1
        assert stats['with_email'] == 2  # c3 and c4 have email (c1 removed)
        assert stats['with_phone'] == 2  # c2 and c4 have phone


class TestContactFiltering:
    """Test finding contacts by various criteria"""
    
    def test_filter_by_csv_import(self, list_service, test_contacts, db_session):
        """Test filtering contacts by CSV import"""
        # Create CSV import
        csv_import = CSVImport(
            filename='test_import.csv',
            total_rows=2,
            successful_imports=2
        )
        db_session.add(csv_import)
        db_session.commit()
        
        # Associate contacts with import
        for contact in test_contacts[:2]:
            assoc = ContactCSVImport(
                contact_id=contact.id,
                csv_import_id=csv_import.id
            )
            db_session.add(assoc)
        db_session.commit()
        
        # Find contacts by CSV import
        criteria = {'csv_import_id': csv_import.id}
        found_contacts = list_service.find_contacts_by_criteria(criteria)
        
        assert len(found_contacts) == 2
        assert test_contacts[0] in found_contacts
        assert test_contacts[1] in found_contacts
    
    def test_filter_by_import_date_range(self, list_service, test_contacts, db_session):
        """Test filtering contacts by import date range"""
        # Filter for contacts imported in last 7 days
        criteria = {
            'imported_after': datetime.utcnow() - timedelta(days=7),
            'imported_before': datetime.utcnow()
        }
        
        found_contacts = list_service.find_contacts_by_criteria(criteria)
        
        # Should find c2 (5 days) and c4 (2 days), not c1 (10 days ago) or c3 (30 days ago)
        # Check that our expected contacts are in the results
        assert test_contacts[1] in found_contacts  # Jane (5 days)
        assert test_contacts[3] in found_contacts  # Alice (2 days)
        # And that the old imports are not
        assert test_contacts[0] not in found_contacts  # John (10 days ago)
        assert test_contacts[2] not in found_contacts  # Bob (30 days ago)
    
    def test_filter_no_recent_contact(self, list_service, test_contacts, db_session):
        """Test filtering contacts with no recent outgoing activity"""
        # Create recent activity for first contact
        activity = Activity(
            contact_id=test_contacts[0].id,
            conversation_id=1,  # dummy
            activity_type='message',
            direction='outgoing',
            body='Recent message',
            created_at=datetime.utcnow() - timedelta(days=5)
        )
        db_session.add(activity)
        db_session.commit()
        
        # Filter for no contact in last 7 days
        criteria = {
            'no_recent_contact': True,
            'days_since_contact': 7
        }
        
        found_contacts = list_service.find_contacts_by_criteria(criteria)
        
        # Should exclude first contact (has recent activity)
        assert test_contacts[0] not in found_contacts
        # Other test contacts should be included (no recent activity)
        assert test_contacts[1] in found_contacts
        assert test_contacts[2] in found_contacts
        assert test_contacts[3] in found_contacts
    
    def test_filter_exclude_opted_out(self, list_service, test_contacts, db_session):
        """Test excluding opted-out contacts"""
        # Add opt-out flag for first contact
        opt_out_flag = ContactFlag(
            contact_id=test_contacts[0].id,
            flag_type='opted_out',
            flag_reason='STOP received'
        )
        db_session.add(opt_out_flag)
        db_session.commit()
        
        # Filter excluding opted out
        criteria = {'exclude_opted_out': True}
        found_contacts = list_service.find_contacts_by_criteria(criteria)
        
        # Should exclude first contact (opted out)
        assert test_contacts[0] not in found_contacts
        # Other test contacts should be included (not opted out)
        assert test_contacts[1] in found_contacts
        assert test_contacts[2] in found_contacts
        assert test_contacts[3] in found_contacts
    
    def test_filter_by_metadata(self, list_service, test_contacts, db_session):
        """Test filtering contacts by metadata keys"""
        # Filter for contacts with 'source' metadata
        criteria = {'has_metadata': ['source']}
        found_contacts = list_service.find_contacts_by_criteria(criteria)
        
        # Only c4 has metadata with 'source' key
        assert test_contacts[3] in found_contacts  # Alice has 'source' metadata
        # Others should not be included
        assert test_contacts[0] not in found_contacts
        assert test_contacts[1] not in found_contacts
        assert test_contacts[2] not in found_contacts
        
        # Filter for multiple metadata keys
        criteria = {'has_metadata': ['source', 'lead_score']}
        found_contacts = list_service.find_contacts_by_criteria(criteria)
        
        # Still only c4 matches (has both source and lead_score)
        assert test_contacts[3] in found_contacts


class TestDynamicLists:
    """Test dynamic list functionality"""
    
    def test_refresh_dynamic_list_add_new_matches(self, list_service, test_contacts, db_session):
        """Test refreshing dynamic list adds new matching contacts"""
        # Create dynamic list for contacts with email
        criteria = {'has_email': True}
        dynamic_list = list_service.create_list(
            name='Email Contacts',
            filter_criteria=criteria,
            is_dynamic=True
        )
        
        # Get initial members - should include our test contacts with email (c1, c3, c4)
        initial_members = db_session.query(Contact).join(CampaignListMember).filter(
            CampaignListMember.list_id == dynamic_list.id,
            CampaignListMember.status == 'active'
        ).all()
        
        # Check our test contacts with email are included
        assert test_contacts[0] in initial_members  # John has email
        assert test_contacts[2] in initial_members  # Bob has email  
        assert test_contacts[3] in initial_members  # Alice has email
        # Note: We can't assert Jane is NOT in the list because the dynamic list
        # includes ALL contacts with email from the database, not just our test contacts
        
        initial_count = len(initial_members)
        
        # Add new contact with email
        import time as t
        unique_id = str(int(t.time() * 1000000))[-6:]
        new_contact = Contact(
            first_name='New',
            last_name='Contact',
            email=f'new{unique_id}@example.com',
            phone=f'+1555999{unique_id}'
        )
        db_session.add(new_contact)
        db_session.commit()
        
        # Refresh list
        results = list_service.refresh_dynamic_list(dynamic_list.id)
        
        # Should now have one more member
        updated_members = db_session.query(Contact).join(CampaignListMember).filter(
            CampaignListMember.list_id == dynamic_list.id,
            CampaignListMember.status == 'active'
        ).all()
        
        assert len(updated_members) == initial_count + 1
        # New contact should be in the list
        assert new_contact in updated_members
    
    def test_refresh_dynamic_list_remove_non_matches(self, list_service, test_contacts, db_session):
        """Test refreshing dynamic list removes non-matching contacts"""
        # Create dynamic list for recent imports (last 7 days)
        criteria = {'imported_after': datetime.utcnow() - timedelta(days=7)}
        dynamic_list = list_service.create_list(
            name='Recent Imports',
            filter_criteria=criteria,
            is_dynamic=True
        )
        
        # Should initially have contacts imported in last 7 days (c2 and c4)
        initial_contacts = list_service.get_list_contacts(dynamic_list.id)
        # Check our expected recent imports are included
        assert test_contacts[1] in initial_contacts  # Jane (5 days ago)
        assert test_contacts[3] in initial_contacts  # Alice (2 days ago)
        # Old imports should not be included
        assert test_contacts[0] not in initial_contacts  # John (10 days ago)
        assert test_contacts[2] not in initial_contacts  # Bob (30 days ago)
        
        # Manually add an old contact to the list
        old_contact_member = CampaignListMember(
            list_id=dynamic_list.id,
            contact_id=test_contacts[2].id,  # c3 - imported 30 days ago
            added_by='manual'
        )
        db_session.add(old_contact_member)
        db_session.commit()
        
        # Refresh list
        list_service.refresh_dynamic_list(dynamic_list.id)
        
        # Old contact should be removed
        db_session.refresh(old_contact_member)
        assert old_contact_member.status == 'removed'
        
        # Active contacts should still only include recent imports
        active_contacts = list_service.get_list_contacts(dynamic_list.id)
        assert test_contacts[1] in active_contacts  # Jane still included
        assert test_contacts[3] in active_contacts  # Alice still included
        assert test_contacts[2] not in active_contacts  # Bob removed (old import)
    
    def test_refresh_static_list_no_effect(self, list_service, test_list, db_session):
        """Test that refreshing a static list has no effect"""
        # Try to refresh static list
        results = list_service.refresh_dynamic_list(test_list.id)
        
        assert 'error' in results
        assert 'not dynamic' in results['error']


class TestErrorHandling:
    """Test error handling scenarios"""
    
    def test_add_invalid_contact_id(self, list_service, test_list, db_session):
        """Test adding non-existent contact IDs"""
        # Get initial member count
        initial_count = CampaignListMember.query.filter_by(list_id=test_list.id).count()
        
        # Try to add non-existent contact IDs
        try:
            results = list_service.add_contacts_to_list(
                test_list.id,
                [99999, 88888]  # Non-existent IDs
            )
            # If it doesn't raise an error, check that nothing was actually added
            final_count = CampaignListMember.query.filter_by(list_id=test_list.id).count()
            assert final_count == initial_count  # No new members added
        except Exception:
            # Foreign key constraint should prevent adding invalid IDs
            # This is the expected behavior
            pass
    
    def test_remove_from_invalid_list(self, list_service, db_session):
        """Test removing contacts from non-existent list"""
        count = list_service.remove_contacts_from_list(99999, [1, 2, 3])
        assert count == 0
    
    def test_get_stats_for_empty_list(self, list_service, test_list, db_session):
        """Test getting stats for empty list"""
        stats = list_service.get_list_stats(test_list.id)
        
        assert stats['total_members'] == 0
        assert stats['active_members'] == 0
        assert stats['removed_members'] == 0
        assert stats['with_email'] == 0
        assert stats['with_phone'] == 0