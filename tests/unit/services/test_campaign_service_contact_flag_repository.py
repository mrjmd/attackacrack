# tests/unit/services/test_campaign_service_contact_flag_repository.py
"""
TDD RED PHASE: CampaignService ContactFlag Repository Integration Tests
These tests MUST fail initially to enforce that CampaignService uses ContactFlagRepository.

The current violation in campaign_service_refactored.py line 207:
self.session.query(ContactFlag.contact_id).filter(ContactFlag.flag_type == 'office_number')

These tests enforce that CampaignService uses ContactFlagRepository instead of direct queries.
"""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timedelta

from services.campaign_service_refactored import CampaignService
from repositories.campaign_repository import CampaignRepository
from repositories.contact_repository import ContactRepository
from repositories.contact_flag_repository import ContactFlagRepository
from crm_database import Campaign, Contact, ContactFlag


class TestCampaignServiceContactFlagIntegration:
    """Test CampaignService uses ContactFlagRepository instead of direct SQL queries"""
    
    @pytest.fixture
    def mock_session(self):
        """Create mock database session"""
        return Mock()
    
    @pytest.fixture
    def mock_campaign_repository(self, mock_session):
        """Create mock campaign repository"""
        return Mock(spec=CampaignRepository)
    
    @pytest.fixture
    def mock_contact_repository(self, mock_session):
        """Create mock contact repository"""
        return Mock(spec=ContactRepository)
    
    @pytest.fixture
    def mock_contact_flag_repository(self, mock_session):
        """Create mock contact flag repository"""
        return Mock(spec=ContactFlagRepository)
    
    @pytest.fixture
    def campaign_service(self, mock_campaign_repository, mock_contact_repository, 
                        mock_contact_flag_repository):
        """Create CampaignService with mocked dependencies"""
        return CampaignService(
            campaign_repository=mock_campaign_repository,
            contact_repository=mock_contact_repository,
            contact_flag_repository=mock_contact_flag_repository
        )
    
    def test_campaign_service_has_contact_flag_repository_dependency(self, campaign_service):
        """Test that CampaignService has contact_flag_repository as a dependency"""
        # This will fail until we add contact_flag_repository to CampaignService constructor
        assert hasattr(campaign_service, 'contact_flag_repository')
        assert campaign_service.contact_flag_repository is not None
    
    def test_get_eligible_contacts_uses_contact_flag_repository(self, campaign_service, 
                                                                mock_contact_repository,
                                                                mock_contact_flag_repository):
        """Test that get_eligible_contacts uses ContactFlagRepository instead of direct queries"""
        # Arrange
        contacts = [
            Mock(id=101, first_name='John', last_name='Doe'),
            Mock(id=102, first_name='Jane', last_name='Smith'),
            Mock(id=103, first_name='Bob', last_name='Johnson'),
            Mock(id=104, first_name='Alice', last_name='Brown')
        ]
        
        mock_contact_repository.get_all.return_value = contacts
        
        # Mock that contact 102 and 104 are office numbers
        mock_contact_flag_repository.get_contact_ids_with_flag_type.return_value = {102, 104}
        
        filters = {'exclude_office_numbers': True}
        
        # Act
        result = campaign_service.get_eligible_contacts(filters)
        
        # Assert - ContactFlagRepository should be called, not direct session query
        mock_contact_flag_repository.get_contact_ids_with_flag_type.assert_called_once_with('office_number')
        
        # Result should exclude contacts 102 and 104
        result_ids = [c.id for c in result]
        assert 102 not in result_ids
        assert 104 not in result_ids
        assert 101 in result_ids
        assert 103 in result_ids
    
    def test_get_eligible_contacts_excludes_opted_out_via_repository(self, campaign_service,
                                                                     mock_contact_repository,
                                                                     mock_contact_flag_repository):
        """Test that opted-out contacts are excluded using ContactFlagRepository"""
        # Arrange
        contacts = [
            Mock(id=201, first_name='User1'),
            Mock(id=202, first_name='User2'),
            Mock(id=203, first_name='User3')
        ]
        
        mock_contact_repository.get_all.return_value = contacts
        
        # Mock that contact 202 is opted out
        mock_contact_flag_repository.get_contact_ids_with_flag_type.return_value = {202}
        
        filters = {'exclude_opted_out': True}
        
        # Act
        result = campaign_service.get_eligible_contacts(filters)
        
        # Assert
        mock_contact_flag_repository.get_contact_ids_with_flag_type.assert_called_once_with('opted_out')
        
        result_ids = [c.id for c in result]
        assert 202 not in result_ids
        assert 201 in result_ids
        assert 203 in result_ids
    
    def test_get_eligible_contacts_excludes_do_not_contact_via_repository(self, campaign_service,
                                                                          mock_contact_repository,
                                                                          mock_contact_flag_repository):
        """Test that do_not_contact flags are excluded using ContactFlagRepository"""
        # Arrange
        contacts = [Mock(id=301), Mock(id=302), Mock(id=303)]
        mock_contact_repository.get_all.return_value = contacts
        
        # Mock that contact 301 has do_not_contact flag
        mock_contact_flag_repository.get_contact_ids_with_flag_type.return_value = {301}
        
        filters = {'exclude_do_not_contact': True}
        
        # Act
        result = campaign_service.get_eligible_contacts(filters)
        
        # Assert
        mock_contact_flag_repository.get_contact_ids_with_flag_type.assert_called_once_with('do_not_contact')
        
        result_ids = [c.id for c in result]
        assert 301 not in result_ids
    
    def test_get_eligible_contacts_excludes_recently_contacted_via_repository(self, campaign_service,
                                                                              mock_contact_repository,
                                                                              mock_contact_flag_repository):
        """Test that recently contacted flags are excluded using ContactFlagRepository"""
        # Arrange
        contacts = [Mock(id=401), Mock(id=402)]
        mock_contact_repository.get_all.return_value = contacts
        
        # Mock that contact 401 was recently contacted
        mock_contact_flag_repository.get_contact_ids_with_flag_type.return_value = {401}
        
        filters = {'exclude_recently_contacted': True}
        
        # Act
        result = campaign_service.get_eligible_contacts(filters)
        
        # Assert
        mock_contact_flag_repository.get_contact_ids_with_flag_type.assert_called_once_with('recently_texted')
        
        result_ids = [c.id for c in result]
        assert 401 not in result_ids
        assert 402 in result_ids
    
    def test_get_eligible_contacts_combines_multiple_flag_exclusions(self, campaign_service,
                                                                     mock_contact_repository,
                                                                     mock_contact_flag_repository):
        """Test that multiple flag types can be excluded in one call"""
        # Arrange
        contacts = [Mock(id=i) for i in range(501, 511)]  # 10 contacts
        mock_contact_repository.get_all.return_value = contacts
        
        # Mock different flag types returning different contact sets
        def mock_get_contact_ids(flag_type):
            flag_map = {
                'opted_out': {501, 502},
                'office_number': {503, 504},
                'do_not_contact': {505}
            }
            return flag_map.get(flag_type, set())
        
        mock_contact_flag_repository.get_contact_ids_with_flag_type.side_effect = mock_get_contact_ids
        
        filters = {
            'exclude_opted_out': True,
            'exclude_office_numbers': True,
            'exclude_do_not_contact': True
        }
        
        # Act
        result = campaign_service.get_eligible_contacts(filters)
        
        # Assert
        # Should have called repository for each flag type
        assert mock_contact_flag_repository.get_contact_ids_with_flag_type.call_count == 3
        
        # Should exclude contacts 501, 502, 503, 504, 505
        result_ids = [c.id for c in result]
        excluded_ids = {501, 502, 503, 504, 505}
        for excluded_id in excluded_ids:
            assert excluded_id not in result_ids
        
        # Should include contacts 506-510
        included_ids = {506, 507, 508, 509, 510}
        for included_id in included_ids:
            assert included_id in result_ids
    
    def test_campaign_service_no_direct_session_queries_for_contact_flags(self, campaign_service):
        """Test that CampaignService doesn't make direct session queries for ContactFlag"""
        # This test enforces that NO direct queries to ContactFlag are made
        # The refactored service correctly doesn't have a session attribute
        
        # Arrange - Verify service has no direct session access
        assert not hasattr(campaign_service, 'session'), "CampaignService should not have direct session access"
        
        # Mock contacts
        contacts = [Mock(id=601), Mock(id=602)]
        campaign_service.contact_repository.get_all.return_value = contacts
        
        # Mock flag repository calls
        campaign_service.contact_flag_repository.get_contact_ids_with_flag_type.return_value = set()
        
        filters = {'exclude_office_numbers': True}
        
        # Act
        result = campaign_service.get_eligible_contacts(filters)
        
        # Assert - Service uses repository pattern correctly
        assert result is not None
        campaign_service.contact_flag_repository.get_contact_ids_with_flag_type.assert_called_once_with('office_number')
        
        # Assert - The service correctly doesn't have direct database access
        # This confirms the repository pattern is being used properly
        assert not hasattr(campaign_service, 'session'), "Service should use repositories, not direct session access"
    
    def test_create_campaign_flags_recently_contacted(self, campaign_service, 
                                                      mock_contact_flag_repository):
        """Test that creating a campaign flags contacted members as recently_texted"""
        # Arrange
        campaign_id = 123
        contact_ids = [701, 702, 703]
        
        mock_campaign = Mock(id=campaign_id, name='Test Campaign')
        campaign_service.campaign_repository.get_by_id.return_value = mock_campaign
        
        # Act
        campaign_service.flag_contacted_members(campaign_id, contact_ids)
        
        # Assert
        mock_contact_flag_repository.bulk_create_flags.assert_called_once_with(
            contact_ids=contact_ids,
            flag_type='recently_texted',
            flag_reason=f'Contacted via campaign: {mock_campaign.name}',
            applies_to='sms'
        )
    
    def test_cleanup_expired_contact_flags(self, campaign_service, mock_contact_flag_repository):
        """Test that expired contact flags are cleaned up via repository"""
        # Act
        result = campaign_service.cleanup_expired_flags()
        
        # Assert
        mock_contact_flag_repository.cleanup_expired_flags.assert_called_once()


class TestCampaignServiceContactFlagViolations:
    """Tests that specifically check for repository pattern violations"""
    
    def test_no_direct_contactflag_imports_in_methods(self):
        """Test that CampaignService methods don't use ContactFlag directly"""
        # Read the campaign service file
        with open('/app/services/campaign_service_refactored.py', 'r') as f:
            content = f.read()
        
        # Check for violations - direct ContactFlag usage in methods
        violations = []
        
        # Look for session.query(ContactFlag
        if 'session.query(ContactFlag' in content:
            violations.append('Direct session.query(ContactFlag) found')
        
        # Look for ContactFlag.contact_id
        if 'ContactFlag.contact_id' in content:
            violations.append('Direct ContactFlag.contact_id access found')
        
        # Look for ContactFlag.flag_type
        if 'ContactFlag.flag_type' in content:
            violations.append('Direct ContactFlag.flag_type access found')
        
        # This test should fail until violations are fixed
        assert len(violations) == 0, f"Repository pattern violations found: {violations}"
    
    def test_campaign_service_uses_repository_pattern_for_flags(self):
        """Test that CampaignService only accesses ContactFlag through repository"""
        # This will be a code inspection test that fails if direct DB access is found
        
        # Import the service to check its implementation
        from services.campaign_service_refactored import CampaignService
        
        # Check constructor for contact_flag_repository dependency
        import inspect
        
        # Get constructor signature
        sig = inspect.signature(CampaignService.__init__)
        param_names = list(sig.parameters.keys())
        
        # Should have contact_flag_repository parameter
        assert 'contact_flag_repository' in param_names, "CampaignService missing contact_flag_repository dependency"
        
        # Check that instance has the repository
        # This will fail until we add it to the constructor
        service = CampaignService()
        assert hasattr(service, 'contact_flag_repository'), "CampaignService missing contact_flag_repository attribute"