"""
Tests for ContactService refactored with Result Pattern
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime

from services.contact_service_refactored import ContactService
from services.common.result import Result, PagedResult
from repositories.contact_repository import ContactRepository
from repositories.campaign_repository import CampaignRepository
from crm_database import Contact, ContactFlag, Campaign, CampaignMembership


class TestContactServiceResult:
    """Test suite for ContactService with Result pattern"""
    
    @pytest.fixture
    def mock_contact_repo(self):
        """Mock ContactRepository"""
        repo = Mock(spec=ContactRepository)
        repo.find_by_id = Mock(return_value=None)
        repo.get_by_id = Mock(return_value=None)  # Add get_by_id method
        repo.find_by_phone = Mock(return_value=None)
        repo.find_by_email = Mock(return_value=None)
        repo.create = Mock()
        repo.delete = Mock()
        repo.find_all = Mock()
        return repo
    
    @pytest.fixture
    def mock_campaign_repo(self):
        """Mock CampaignRepository"""
        repo = Mock(spec=CampaignRepository)
        repo.get_by_id = Mock(return_value=None)
        repo.get_member_by_contact = Mock(return_value=None)
        repo.add_member = Mock()
        repo.add_members_bulk = Mock(return_value=0)
        return repo
    
    @pytest.fixture
    def mock_session(self):
        """Mock database session"""
        session = Mock()
        session.add = Mock()
        session.commit = Mock()
        session.rollback = Mock()
        session.query = Mock()
        return session
    
    @pytest.fixture
    def contact_service(self, mock_contact_repo, mock_campaign_repo, mock_session):
        """Create ContactService with mocked dependencies"""
        service = ContactService(
            contact_repository=mock_contact_repo,
            campaign_repository=mock_campaign_repo,
            session=mock_session
        )
        return service
    
    def test_add_contact_success(self, contact_service, mock_contact_repo):
        """Test successful contact creation"""
        # Arrange
        mock_contact = Mock(spec=Contact)
        mock_contact.id = 1
        mock_contact.full_name = "John Doe"
        mock_contact_repo.find_by_phone.return_value = None
        mock_contact_repo.find_by_email.return_value = None
        mock_contact_repo.create.return_value = mock_contact
        
        # Act
        result = contact_service.add_contact(
            first_name="John",
            last_name="Doe",
            email="john@example.com",
            phone="+11234567890"
        )
        
        # Assert
        assert result.is_success == True
        assert result.data == mock_contact
        mock_contact_repo.create.assert_called_once()
    
    def test_add_contact_duplicate_phone(self, contact_service, mock_contact_repo):
        """Test contact creation with duplicate phone"""
        # Arrange
        existing_contact = Mock()
        mock_contact_repo.find_by_phone.return_value = existing_contact
        
        # Act
        result = contact_service.add_contact(
            first_name="John",
            last_name="Doe",
            phone="+11234567890"
        )
        
        # Assert
        assert result.is_failure == True
        assert result.error_code == "DUPLICATE_PHONE"
        mock_contact_repo.create.assert_not_called()
    
    def test_add_contact_duplicate_email(self, contact_service, mock_contact_repo):
        """Test contact creation with duplicate email"""
        # Arrange
        existing_contact = Mock()
        mock_contact_repo.find_by_phone.return_value = None
        mock_contact_repo.find_by_email.return_value = existing_contact
        
        # Act
        result = contact_service.add_contact(
            first_name="John",
            last_name="Doe",
            email="john@example.com"
        )
        
        # Assert
        assert result.is_failure == True
        assert result.error_code == "DUPLICATE_EMAIL"
        mock_contact_repo.create.assert_not_called()
    
    def test_get_contact_by_id_found(self, contact_service, mock_contact_repo):
        """Test getting contact by ID - found"""
        # Arrange
        mock_contact = Mock()
        mock_contact_repo.find_by_id.return_value = mock_contact
        
        # Act
        result = contact_service.get_contact_by_id(1)
        
        # Assert
        assert result.is_success == True
        assert result.data == mock_contact
    
    def test_get_contact_by_id_not_found(self, contact_service, mock_contact_repo):
        """Test getting contact by ID - not found"""
        # Arrange
        mock_contact_repo.find_by_id.return_value = None
        
        # Act
        result = contact_service.get_contact_by_id(999)
        
        # Assert
        assert result.is_failure == True
        assert result.error_code == "NOT_FOUND"
    
    def test_get_contact_by_phone_found(self, contact_service, mock_contact_repo):
        """Test getting contact by phone - found"""
        # Arrange
        mock_contact = Mock()
        mock_contact_repo.find_by_phone.return_value = mock_contact
        
        # Act
        result = contact_service.get_contact_by_phone("+11234567890")
        
        # Assert
        assert result.is_success == True
        assert result.data == mock_contact
    
    def test_get_all_contacts_paginated(self, contact_service, mock_contact_repo):
        """Test getting all contacts with pagination"""
        # Arrange
        mock_contacts = [Mock(), Mock()]
        mock_contact_repo.find_all.return_value = {
            'items': mock_contacts,
            'total': 10
        }
        
        # Act
        result = contact_service.get_all_contacts(page=1, per_page=2)
        
        # Assert
        assert result.is_success == True
        assert len(result.data) == 2
        assert result.total == 10
        assert result.page == 1
        assert result.per_page == 2
    
    @patch('services.contact_service_refactored.or_')
    @patch('services.contact_service_refactored.Contact')
    def test_search_contacts(self, mock_contact_class, mock_or, contact_service, mock_session):
        """Test searching contacts"""
        # Arrange
        mock_contacts = [Mock(), Mock()]
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = mock_contacts
        mock_session.query.return_value = mock_query
        
        # Mock the or_ function to return a valid filter
        mock_or.return_value = Mock()
        
        # Act
        result = contact_service.search_contacts("john", limit=10)
        
        # Assert
        assert result.is_success == True
        assert len(result.data) == 2
    
    def test_search_contacts_empty_query(self, contact_service):
        """Test searching with empty query"""
        # Act
        result = contact_service.search_contacts("")
        
        # Assert
        assert result.is_success == True
        assert result.data == []
    
    def test_update_contact_success(self, contact_service, mock_contact_repo, mock_session):
        """Test successful contact update"""
        # Arrange
        mock_contact = Mock()
        mock_contact.first_name = "John"
        mock_contact_repo.find_by_id.return_value = mock_contact
        
        # Act
        result = contact_service.update_contact(
            contact_id=1,
            first_name="Jane",
            email="jane@example.com"
        )
        
        # Assert
        assert result.is_success == True
        assert result.data == mock_contact
        assert mock_contact.first_name == "Jane"
        assert mock_contact.email == "jane@example.com"
        mock_session.commit.assert_called_once()
    
    def test_update_contact_not_found(self, contact_service, mock_contact_repo):
        """Test updating non-existent contact"""
        # Arrange
        mock_contact_repo.find_by_id.return_value = None
        
        # Act
        result = contact_service.update_contact(999, first_name="Jane")
        
        # Assert
        assert result.is_failure == True
        assert result.error_code == "NOT_FOUND"
    
    def test_delete_contact_success(self, contact_service, mock_contact_repo):
        """Test successful contact deletion"""
        # Arrange
        mock_contact = Mock()
        mock_contact_repo.find_by_id.return_value = mock_contact
        
        # Act
        result = contact_service.delete_contact(1)
        
        # Assert
        assert result.is_success == True
        assert result.data == True
        mock_contact_repo.delete.assert_called_once_with(1)
    
    def test_bulk_action_delete(self, contact_service, mock_contact_repo):
        """Test bulk delete action"""
        # Arrange
        mock_contact = Mock()
        mock_contact_repo.find_by_id.return_value = mock_contact
        
        # Act
        result = contact_service.bulk_action("delete", [1, 2, 3])
        
        # Assert
        assert result.is_success == True
        assert result.data["successful"] == 3
        assert result.data["failed"] == 0
        assert mock_contact_repo.delete.call_count == 3
    
    def test_bulk_action_tag(self, contact_service, mock_contact_repo, mock_session):
        """Test bulk tag action"""
        # Arrange
        mock_contact = Mock()
        mock_contact.tags = []
        mock_contact_repo.find_by_id.return_value = mock_contact
        
        # Act
        result = contact_service.bulk_action("tag", [1, 2], tag="hot_lead")
        
        # Assert
        assert result.is_success == True
        assert result.data["successful"] == 2
        assert "hot_lead" in mock_contact.tags
        # Session is committed once per iteration in the loop
        assert mock_session.commit.called
    
    def test_bulk_action_no_contacts(self, contact_service):
        """Test bulk action with no contacts"""
        # Act
        result = contact_service.bulk_action("delete", [])
        
        # Assert
        assert result.is_failure == True
        assert result.error_code == "NO_CONTACTS"
    
    def test_add_to_campaign_success_with_repository_pattern(self, contact_service, mock_contact_repo, mock_session):
        """
        Test adding contact to campaign using repository pattern.
        
        THIS TEST MUST FAIL INITIALLY because current implementation uses direct DB queries:
        - Campaign.query.get(campaign_id)  # Should use campaign_repository.get_by_id()
        - CampaignMembership.query.filter_by()  # Should use campaign_repository.get_member_by_contact()
        """
        # Arrange
        mock_contact = Mock()
        mock_contact.id = 1
        mock_contact_repo.get_by_id.return_value = mock_contact
        
        mock_campaign = Mock()
        mock_campaign.id = 1
        
        # Set up the injected campaign repository mock
        contact_service.campaign_repository.get_by_id.return_value = mock_campaign
        contact_service.campaign_repository.get_member_by_contact.return_value = None  # No existing membership
        contact_service.campaign_repository.add_member.return_value = Mock()
        
        # Act
        result = contact_service.add_to_campaign(1, 1)
        
        # Assert - These assertions verify repository pattern usage
        assert result.is_success == True
        contact_service.campaign_repository.get_by_id.assert_called_once_with(1)
        contact_service.campaign_repository.get_member_by_contact.assert_called_once_with(1, 1)
        contact_service.campaign_repository.add_member.assert_called_once_with(
            campaign_id=1, 
            contact_id=1, 
            status='pending'
        )
        mock_session.commit.assert_called_once()
    
    def test_add_to_campaign_contact_not_found(self, contact_service, mock_contact_repo):
        """Test adding to campaign when contact doesn't exist"""
        # Arrange
        mock_contact_repo.get_by_id.return_value = None
        # Need to set up a valid campaign for when contact check passes
        mock_campaign = Mock()
        contact_service.campaign_repository.get_by_id.return_value = mock_campaign
        
        # Act
        result = contact_service.add_to_campaign(999, 1)
        
        # Assert
        assert result.is_failure == True
        assert result.error_code == "CONTACT_NOT_FOUND"
        assert "Contact not found: 999" in result.error
    
    def test_add_to_campaign_campaign_not_found(self, contact_service, mock_contact_repo):
        """
        Test adding to non-existent campaign using repository pattern.
        
        THIS TEST MUST FAIL because current implementation uses Campaign.query.get()
        instead of campaign_repository.get_by_id()
        """
        # Arrange
        mock_contact = Mock()
        mock_contact.id = 1
        mock_contact_repo.get_by_id.return_value = mock_contact
        
        contact_service.campaign_repository.get_by_id.return_value = None
        
        # Act
        result = contact_service.add_to_campaign(1, 999)
        
        # Assert
        assert result.is_failure == True
        assert result.error_code == "CAMPAIGN_NOT_FOUND"
        assert "Campaign not found: 999" in result.error
        contact_service.campaign_repository.get_by_id.assert_called_once_with(999)
    
    def test_add_to_campaign_already_member(self, contact_service, mock_contact_repo):
        """
        Test adding contact to campaign when already a member.
        
        THIS TEST MUST FAIL because current implementation uses:
        CampaignMembership.query.filter_by() instead of campaign_repository.get_member_by_contact()
        """
        # Arrange
        mock_contact = Mock()
        mock_contact.id = 1
        mock_contact_repo.get_by_id.return_value = mock_contact
        
        mock_campaign = Mock()
        mock_campaign.id = 1
        
        existing_membership = Mock()
        existing_membership.id = 123
        
        contact_service.campaign_repository.get_by_id.return_value = mock_campaign
        contact_service.campaign_repository.get_member_by_contact.return_value = existing_membership
        
        # Act
        result = contact_service.add_to_campaign(1, 1)
        
        # Assert
        assert result.is_failure == True
        assert result.error_code == "ALREADY_MEMBER"
        assert "Contact already in campaign" in result.error
        contact_service.campaign_repository.get_by_id.assert_called_once_with(1)
        contact_service.campaign_repository.get_member_by_contact.assert_called_once_with(1, 1)
        contact_service.campaign_repository.add_member.assert_not_called()
    
    def test_bulk_add_to_campaign_success_with_repository_pattern(self, contact_service, mock_contact_repo, mock_session):
        """
        Test bulk adding contacts to campaign using repository pattern.
        
        THIS TEST MUST FAIL because current implementation uses:
        - Campaign.query.get(campaign_id)  # Should use campaign_repository.get_by_id()
        """
        # Arrange
        contact_ids = [1, 2, 3]
        
        mock_campaign = Mock()
        mock_campaign.id = 1
        
        contact_service.campaign_repository.get_by_id.return_value = mock_campaign
        contact_service.campaign_repository.add_members_bulk.return_value = 3  # All 3 added successfully
        
        # Set up contacts to be found
        mock_contact = Mock()
        contact_service.contact_repository.get_by_id.return_value = mock_contact
        
        # Set up no existing memberships (all contacts can be added)
        contact_service.campaign_repository.get_member_by_contact.return_value = None
        contact_service.campaign_repository.add_member.return_value = Mock()
        
        # Act
        result = contact_service.bulk_add_to_campaign(contact_ids, 1)
        
        # Assert - These verify repository pattern usage
        assert result.is_success == True
        assert result.data["added"] == 3
        assert result.data["skipped"] == 0
        assert len(result.data["errors"]) == 0
        
        # Verify campaign repository was used (implementation calls it once for bulk check + once per individual add)
        assert contact_service.campaign_repository.get_by_id.call_count > 0
        contact_service.campaign_repository.get_by_id.assert_called_with(1)
        # Verify commit was called (once per successful contact addition)
        assert mock_session.commit.call_count == 3  # One per contact
        mock_session.commit.assert_called()
    
    def test_bulk_add_to_campaign_no_contacts(self, contact_service):
        """Test bulk add with empty contact list"""
        # Act
        result = contact_service.bulk_add_to_campaign([], 1)
        
        # Assert
        assert result.is_failure == True
        assert result.error_code == "NO_CONTACTS"
        assert "No contact IDs provided" in result.error
    
    def test_bulk_add_to_campaign_campaign_not_found(self, contact_service):
        """
        Test bulk add to non-existent campaign using repository pattern.
        
        THIS TEST MUST FAIL because current implementation uses Campaign.query.get()
        instead of campaign_repository.get_by_id()
        """
        # Arrange
        contact_ids = [1, 2, 3]
        
        contact_service.campaign_repository.get_by_id.return_value = None
        
        # Act
        result = contact_service.bulk_add_to_campaign(contact_ids, 999)
        
        # Assert
        assert result.is_failure == True
        assert result.error_code == "CAMPAIGN_NOT_FOUND"
        assert "Campaign not found: 999" in result.error
        contact_service.campaign_repository.get_by_id.assert_called_once_with(999)
    
    def test_bulk_add_to_campaign_partial_success(self, contact_service, mock_session):
        """
        Test bulk add with some successes and some failures.
        
        THIS TEST MUST FAIL because it requires repository pattern implementation.
        """
        # Arrange
        contact_ids = [1, 2, 3, 4, 5]
        
        mock_campaign = Mock()
        mock_campaign.id = 1
        
        contact_service.campaign_repository.get_by_id.return_value = mock_campaign
        # Set up contacts to be found
        mock_contact = Mock()
        contact_service.contact_repository.get_by_id.return_value = mock_contact
        
        # Set up some contacts to fail by making get_member_by_contact return existing membership for some
        existing_membership = Mock()
        contact_service.campaign_repository.get_member_by_contact.side_effect = [
            None, None, existing_membership, existing_membership, None  # First 2 succeed, next 2 skip, last 1 succeeds
        ]
        contact_service.campaign_repository.add_member.return_value = Mock()
        
        # Act
        result = contact_service.bulk_add_to_campaign(contact_ids, 1)
        
        # Assert
        assert result.is_success == True
        assert result.data["added"] == 3  # Contacts 1, 2, 5 succeed
        assert result.data["skipped"] == 2  # Contacts 3, 4 are already members
        
        # Note: Current implementation calls add_to_campaign individually
        # Verify campaign repository was used multiple times (bulk check + individual checks)
        assert contact_service.campaign_repository.get_by_id.call_count > 0
        contact_service.campaign_repository.get_by_id.assert_called_with(1)
    
    def test_export_contacts_success(self, contact_service, mock_session):
        """Test successful contact export"""
        # Arrange
        mock_contacts = [
            Mock(id=1, first_name="John", last_name="Doe", email="john@example.com",
                 phone="+11234567890", company="Acme", address="123 Main",
                 city="Boston", state="MA", zip_code="02101", tags=["lead"],
                 created_at=datetime.now())
        ]
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = mock_contacts
        mock_session.query.return_value = mock_query
        
        # Act
        result = contact_service.export_contacts([1])
        
        # Assert
        assert result.is_success == True
        assert "John,Doe" in result.data
        assert result.metadata["count"] == 1
    
    def test_get_contact_statistics(self, contact_service, mock_session):
        """Test getting contact statistics"""
        # Arrange
        mock_query = Mock()
        mock_query.count.return_value = 100
        mock_query.filter.return_value = mock_query
        mock_query.join.return_value = mock_query
        mock_query.distinct.return_value = mock_query
        mock_session.query.return_value = mock_query
        
        with patch('services.contact_service_refactored.ContactFlag') as mock_flag:
            mock_flag.query.filter_by.return_value.distinct.return_value.count.return_value = 5
            
            # Act
            result = contact_service.get_contact_statistics()
            
            # Assert
            assert result.is_success == True
            assert result.data["total_contacts"] == 100
            assert result.data["opted_out"] == 5