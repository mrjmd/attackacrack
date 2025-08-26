"""
Extended tests for new ContactService methods following TDD principles
"""

import pytest
from unittest.mock import MagicMock, patch, Mock
from services.contact_service_refactored import ContactService
from crm_database import Contact, ContactFlag, CampaignMembership, Campaign, Property, Job, db
from datetime import datetime
import time


@pytest.fixture
def contact_service(db_session):
    """Fixture to provide ContactService instance with repositories"""
    from repositories.contact_repository import ContactRepository
    from repositories.campaign_repository import CampaignRepository
    from repositories.contact_flag_repository import ContactFlagRepository
    
    return ContactService(
        contact_repository=ContactRepository(db_session),
        campaign_repository=CampaignRepository(db_session),
        contact_flag_repository=ContactFlagRepository(db_session)
    )


@pytest.fixture
def test_contact(db_session):
    """Create a test contact"""
    timestamp = str(int(time.time() * 1000000))[-6:]
    contact = Contact(
        first_name=f'Test{timestamp}',
        last_name=f'User{timestamp}',
        phone=f'+155500{timestamp}',
        email=f'test{timestamp}@example.com'
    )
    db_session.add(contact)
    db_session.commit()
    return contact


@pytest.fixture
def test_campaign(db_session):
    """Create a test campaign"""
    timestamp = str(int(time.time() * 1000000))[-6:]
    campaign = Campaign(
        name=f'Test Campaign {timestamp}',
        campaign_type='blast',
        template_a='Test message',
        status='draft'
    )
    db_session.add(campaign)
    db_session.commit()
    return campaign


class TestContactRelations:
    """Test methods for handling contact relations"""
    
    def test_get_contact_with_relations(self, contact_service, test_contact, db_session):
        """Test getting contact with eager loaded properties and jobs"""
        from crm_database import PropertyContact
        
        # Add a property and associate with contact
        prop = Property(address=f'123 Test St')
        db_session.add(prop)
        db_session.commit()
        
        # Create the association
        association = PropertyContact(
            contact_id=test_contact.id,
            property_id=prop.id,
            relationship_type='owner',
            is_primary=True
        )
        db_session.add(association)
        db_session.commit()
        
        job = Job(
            property_id=prop.id,
            description='Roof repair job',
            status='Completed'
        )
        db_session.add(job)
        db_session.commit()
        
        # Get contact with relations
        result = contact_service.get_contact_with_relations(test_contact.id)
        
        assert result is not None
        assert result.id == test_contact.id
        # Use the property associations (many-to-many relationship)
        property_associations = result.property_associations.all()
        assert len(property_associations) == 1
        property_obj = property_associations[0].property
        assert len(property_obj.jobs) == 1
        assert property_obj.jobs[0].description == 'Roof repair job'
    
    def test_get_contact_with_relations_not_found(self, contact_service):
        """Test getting non-existent contact returns None"""
        result = contact_service.get_contact_with_relations(99999)
        assert result is None


class TestContactFlags:
    """Test contact flag management"""
    
    def test_get_contact_flags_empty(self, contact_service, test_contact):
        """Test getting flags for contact with no flags"""
        result = contact_service.get_contact_flags(test_contact.id)
        
        assert result.is_success
        assert result.data['has_office_flag'] is False
        assert result.data['has_opted_out'] is False
        assert result.data['flags'] == []
    
    def test_get_contact_flags_with_flags(self, contact_service, test_contact, db_session):
        """Test getting flags for contact with multiple flags"""
        # Add flags
        flag1 = ContactFlag(
            contact_id=test_contact.id,
            flag_type='office_number'
            # created_at is auto-set by model default
        )
        flag2 = ContactFlag(
            contact_id=test_contact.id,
            flag_type='opted_out'
            # created_at is auto-set by model default
        )
        db_session.add_all([flag1, flag2])
        db_session.commit()
        
        result = contact_service.get_contact_flags(test_contact.id)
        
        assert result.is_success
        assert result.data['has_office_flag'] is True
        assert result.data['has_opted_out'] is True
        assert 'office_number' in result.data['flags']
        assert 'opted_out' in result.data['flags']
    
    def test_add_contact_flag_success(self, contact_service, test_contact, db_session):
        """Test adding a flag to a contact"""
        result = contact_service.add_contact_flag(
            test_contact.id,
            'office_number',
            'Marked as office',
            'test_user'
        )
        
        assert result.is_success
        assert result.data is True
        
        # Verify flag was added
        flag = ContactFlag.query.filter_by(
            contact_id=test_contact.id,
            flag_type='office_number'
        ).first()
        assert flag is not None
        assert flag.flag_reason == 'Marked as office'
        assert flag.created_by == 'test_user'
    
    def test_add_contact_flag_duplicate(self, contact_service, test_contact, db_session):
        """Test adding duplicate flag returns False"""
        # Add initial flag
        initial_result = contact_service.add_contact_flag(test_contact.id, 'opted_out')
        assert initial_result.is_success
        
        # Try to add duplicate
        result = contact_service.add_contact_flag(test_contact.id, 'opted_out')
        
        assert result.is_success
        assert result.data is False
    
    def test_remove_contact_flag_success(self, contact_service, test_contact, db_session):
        """Test removing a flag from a contact"""
        # Add a flag first
        add_result = contact_service.add_contact_flag(test_contact.id, 'office_number')
        assert add_result.is_success
        
        # Remove it
        result = contact_service.remove_contact_flag(test_contact.id, 'office_number')
        
        assert result.is_success
        assert result.data is True
        
        # Verify flag was removed
        flag = ContactFlag.query.filter_by(
            contact_id=test_contact.id,
            flag_type='office_number'
        ).first()
        assert flag is None


class TestCampaignMembership:
    """Test campaign membership management"""
    
    def test_get_campaign_memberships_empty(self, contact_service, test_contact):
        """Test getting memberships for contact with no campaigns"""
        result = contact_service.get_campaign_memberships(test_contact.id)
        assert result == []
    
    def test_get_campaign_memberships_with_campaigns(self, contact_service, test_contact, test_campaign, db_session):
        """Test getting campaign memberships"""
        # Add membership
        membership = CampaignMembership(
            contact_id=test_contact.id,
            campaign_id=test_campaign.id,
            status='sent',
            sent_at=datetime.now()
        )
        db_session.add(membership)
        db_session.commit()
        
        result = contact_service.get_campaign_memberships(test_contact.id)
        
        assert len(result) == 1
        assert result[0].campaign_id == test_campaign.id
        assert result[0].campaign.name == test_campaign.name
    
    def test_add_to_campaign_success(self, contact_service, test_contact, test_campaign):
        """Test adding contact to campaign"""
        result = contact_service.add_to_campaign(test_contact.id, test_campaign.id)
        
        assert result.is_success
        membership = result.data  # Returns the CampaignMembership object
        assert membership is not None
        assert membership.contact_id == test_contact.id
        assert membership.campaign_id == test_campaign.id
        assert membership.status == 'pending'
        
        # Verify membership was created in database
        db_membership = CampaignMembership.query.filter_by(
            contact_id=test_contact.id,
            campaign_id=test_campaign.id
        ).first()
        assert db_membership is not None
        assert db_membership.id == membership.id
    
    def test_add_to_campaign_duplicate(self, contact_service, test_contact, test_campaign):
        """Test adding contact to campaign they're already in"""
        # Add initially
        initial_result = contact_service.add_to_campaign(test_contact.id, test_campaign.id)
        assert initial_result.is_success
        
        # Try to add again
        result = contact_service.add_to_campaign(test_contact.id, test_campaign.id)
        
        # Should fail with "already in campaign" error
        assert result.is_failure
        assert result.error_code == "ALREADY_MEMBER"
        assert 'already in campaign' in result.error.lower()
    
    def test_add_to_campaign_invalid_campaign(self, contact_service, test_contact):
        """Test adding contact to non-existent campaign"""
        result = contact_service.add_to_campaign(test_contact.id, 99999)
        
        # This should return a failure result due to invalid campaign
        assert result.is_failure
        assert 'campaign not found' in result.error.lower() or 'not found' in result.error.lower()
    
    def test_bulk_add_to_campaign_success(self, contact_service, test_campaign, db_session):
        """Test bulk adding contacts to campaign"""
        # Create multiple contacts
        contacts = []
        for i in range(3):
            timestamp = str(int(time.time() * 1000000))[-6:]
            contact = Contact(
                first_name=f'Bulk{i}{timestamp}',
                last_name=f'Test{i}',
                phone=f'+1555{i:02d}{timestamp}'
            )
            contacts.append(contact)
        db_session.add_all(contacts)
        db_session.commit()
        
        contact_ids = [c.id for c in contacts]
        
        # Bulk add to campaign
        result = contact_service.bulk_add_to_campaign(contact_ids, test_campaign.id)
        
        assert result.is_success
        data = result.data  # Returns a dictionary with results
        assert data['added'] == 3
        assert data['skipped'] == 0
        assert len(data['errors']) == 0
        
        # Verify all were added
        memberships = CampaignMembership.query.filter(
            CampaignMembership.contact_id.in_(contact_ids)
        ).all()
        assert len(memberships) == 3


class TestContactExport:
    """Test contact export functionality"""
    
    def test_export_contacts_csv(self, contact_service, db_session):
        """Test exporting contacts to CSV"""
        # Create test contacts
        contacts = []
        for i in range(2):
            timestamp = str(int(time.time() * 1000000))[-6:]
            contact = Contact(
                first_name=f'Export{i}',
                last_name=f'Test{i}',
                phone=f'+1555{i:02d}{timestamp}',
                email=f'export{i}@test.com',
                import_source=f'test_import_{i}',
                customer_type='prospect' if i == 0 else 'customer'
            )
            contacts.append(contact)
        db_session.add_all(contacts)
        db_session.commit()
        
        contact_ids = [c.id for c in contacts]
        
        # Export to CSV
        result = contact_service.export_contacts(contact_ids)
        
        assert result.is_success
        csv_data = result.data
        assert csv_data is not None
        lines = csv_data.strip().split('\n')
        assert len(lines) == 3  # Header + 2 contacts
        assert 'First Name,Last Name,Phone,Email' in lines[0]
        assert 'Export0' in csv_data
        assert 'Export1' in csv_data
        assert 'export0@test.com' in csv_data
        assert 'prospect' in csv_data
        assert 'customer' in csv_data


class TestContactStatistics:
    """Test contact statistics"""
    
    def test_get_contact_statistics(self, contact_service, db_session):
        """Test getting overall contact statistics"""
        # Create test data
        timestamp = str(int(time.time() * 1000000))[-6:]
        
        # Contact with phone
        c1 = Contact(
            first_name='Stats1',
            last_name='Test',
            phone=f'+15551{timestamp}'
        )
        # Contact with email
        c2 = Contact(
            first_name='Stats2',
            last_name='Test',
            email=f'stats2{timestamp}@test.com'
        )
        # Contact with both
        c3 = Contact(
            first_name='Stats3',
            last_name='Test',
            phone=f'+15553{timestamp}',
            email=f'stats3{timestamp}@test.com'
        )
        db_session.add_all([c1, c2, c3])
        db_session.commit()
        
        # Add some flags
        flag1 = ContactFlag(
            contact_id=c1.id,
            flag_type='opted_out'
            # created_at is auto-set by model default
        )
        flag2 = ContactFlag(
            contact_id=c2.id,
            flag_type='office_number'
            # created_at is auto-set by model default
        )
        db_session.add_all([flag1, flag2])
        db_session.commit()
        
        # Get statistics
        result = contact_service.get_contact_statistics()
        
        assert result.is_success
        stats = result.data
        assert stats['total_contacts'] >= 3
        assert stats['with_phone'] >= 2
        assert stats['with_email'] >= 2
        assert stats['opted_out'] >= 1
        assert stats['office_numbers'] >= 1