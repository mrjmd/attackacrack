"""
Test CSV import service duplicate handling strategies.

This module tests the three duplicate handling strategies:
- merge: Only update missing fields (default)
- replace: Overwrite all fields with new data
- skip: Don't modify existing contacts
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from io import BytesIO
from werkzeug.datastructures import FileStorage
from services.csv_import_service import CSVImportService
from crm_database import Contact, CSVImport
from utils.datetime_utils import utc_now


class TestCSVImportDuplicateStrategies:
    """Test suite for CSV import duplicate handling strategies."""
    
    @pytest.fixture
    def mock_repositories(self):
        """Create mock repositories for testing."""
        return {
            'contact_repository': Mock(),
            'csv_import_repository': Mock(),
            'contact_csv_import_repository': Mock(),
            'campaign_list_repository': Mock(),
            'campaign_list_member_repository': Mock(),
            'contact_service': Mock()
        }
    
    @pytest.fixture
    def csv_service(self, mock_repositories):
        """Create CSVImportService with mocked dependencies."""
        return CSVImportService(
            contact_repository=mock_repositories['contact_repository'],
            csv_import_repository=mock_repositories['csv_import_repository'],
            contact_csv_import_repository=mock_repositories['contact_csv_import_repository'],
            campaign_list_repository=mock_repositories['campaign_list_repository'],
            campaign_list_member_repository=mock_repositories['campaign_list_member_repository'],
            contact_service=mock_repositories['contact_service']
        )
    
    @pytest.fixture
    def sample_csv_content(self):
        """Create sample CSV content for testing."""
        return b"""phone,first_name,last_name,email
+11234567890,John,Doe,john@example.com
+10987654321,Jane,Smith,jane@example.com
+15555555555,Bob,Johnson,bob@example.com"""
    
    @pytest.fixture
    def existing_contact(self):
        """Create a mock existing contact."""
        contact = Mock(spec=Contact)
        contact.id = 1
        contact.phone = '+11234567890'
        contact.first_name = 'Johnny'
        contact.last_name = None
        contact.email = None
        contact.contact_metadata = {}
        return contact
    
    def test_merge_strategy_only_updates_missing_fields(self, csv_service, mock_repositories, sample_csv_content, existing_contact):
        """Test that merge strategy only updates missing fields."""
        # Setup
        file = FileStorage(stream=BytesIO(sample_csv_content), filename='test.csv')
        mock_csv_import = Mock(spec=CSVImport)
        mock_csv_import.id = 1
        
        # Configure mocks
        mock_repositories['csv_import_repository'].create.return_value = mock_csv_import
        mock_repositories['contact_repository'].find_by_phone.side_effect = [
            existing_contact,  # First row - existing contact
            None,  # Second row - new contact
            None   # Third row - new contact
        ]
        mock_repositories['contact_repository'].create.return_value = Mock(id=2, phone='+10987654321')
        mock_repositories['campaign_list_repository'].create.return_value = None
        
        # Execute with merge strategy
        result = csv_service.import_contacts(
            file=file,
            create_list=False,
            duplicate_strategy='merge'
        )
        
        # Verify existing contact was updated correctly
        assert existing_contact.first_name == 'Johnny'  # Should NOT be changed (was not missing)
        assert existing_contact.last_name == 'Doe'  # Should be updated (was missing)
        assert existing_contact.email == 'john@example.com'  # Should be updated (was missing)
        
        # Verify results
        assert result['successful'] >= 1
        assert result['duplicates'] == 1  # One duplicate found and merged
    
    def test_replace_strategy_overwrites_all_fields(self, csv_service, mock_repositories, sample_csv_content, existing_contact):
        """Test that replace strategy overwrites all fields."""
        # Setup
        file = FileStorage(stream=BytesIO(sample_csv_content), filename='test.csv')
        mock_csv_import = Mock(spec=CSVImport)
        mock_csv_import.id = 1
        
        # Configure mocks
        mock_repositories['csv_import_repository'].create.return_value = mock_csv_import
        mock_repositories['contact_repository'].find_by_phone.side_effect = [
            existing_contact,  # First row - existing contact
            None,  # Second row - new contact
            None   # Third row - new contact
        ]
        mock_repositories['contact_repository'].create.return_value = Mock(id=2, phone='+10987654321')
        mock_repositories['campaign_list_repository'].create.return_value = None
        
        # Execute with replace strategy
        result = csv_service.import_contacts(
            file=file,
            create_list=False,
            duplicate_strategy='replace'
        )
        
        # Verify existing contact was replaced completely
        assert existing_contact.first_name == 'John'  # Should be changed (replaced)
        assert existing_contact.last_name == 'Doe'  # Should be updated (replaced)
        assert existing_contact.email == 'john@example.com'  # Should be updated (replaced)
        
        # Verify results
        assert result['successful'] >= 1
        assert result['duplicates'] == 1  # One duplicate found and replaced
    
    def test_skip_strategy_does_not_modify_existing(self, csv_service, mock_repositories, sample_csv_content, existing_contact):
        """Test that skip strategy does not modify existing contacts."""
        # Setup
        file = FileStorage(stream=BytesIO(sample_csv_content), filename='test.csv')
        mock_csv_import = Mock(spec=CSVImport)
        mock_csv_import.id = 1
        
        # Store original values
        original_first_name = existing_contact.first_name
        original_last_name = existing_contact.last_name
        original_email = existing_contact.email
        
        # Configure mocks
        mock_repositories['csv_import_repository'].create.return_value = mock_csv_import
        mock_repositories['contact_repository'].find_by_phone.side_effect = [
            existing_contact,  # First row - existing contact
            None,  # Second row - new contact
            None   # Third row - new contact
        ]
        mock_repositories['contact_repository'].create.return_value = Mock(id=2, phone='+10987654321')
        mock_repositories['campaign_list_repository'].create.return_value = None
        
        # Execute with skip strategy
        result = csv_service.import_contacts(
            file=file,
            create_list=False,
            duplicate_strategy='skip'
        )
        
        # Verify existing contact was NOT modified
        assert existing_contact.first_name == original_first_name  # Should NOT be changed
        assert existing_contact.last_name == original_last_name  # Should NOT be changed
        assert existing_contact.email == original_email  # Should NOT be changed
        
        # Verify results
        assert result['successful'] >= 1
        assert result['duplicates'] == 1  # One duplicate found and skipped
    
    def test_default_strategy_is_merge(self, csv_service, mock_repositories, sample_csv_content, existing_contact):
        """Test that default strategy is merge when not specified."""
        # Setup
        file = FileStorage(stream=BytesIO(sample_csv_content), filename='test.csv')
        mock_csv_import = Mock(spec=CSVImport)
        mock_csv_import.id = 1
        
        # Configure mocks
        mock_repositories['csv_import_repository'].create.return_value = mock_csv_import
        mock_repositories['contact_repository'].find_by_phone.side_effect = [
            existing_contact,  # First row - existing contact
            None,  # Second row - new contact
            None   # Third row - new contact
        ]
        mock_repositories['contact_repository'].create.return_value = Mock(id=2, phone='+10987654321')
        mock_repositories['campaign_list_repository'].create.return_value = None
        
        # Execute without specifying duplicate_strategy
        result = csv_service.import_contacts(
            file=file,
            create_list=False
            # duplicate_strategy not specified - should default to 'merge'
        )
        
        # Verify merge behavior (existing contact should be enriched)
        assert existing_contact.first_name == 'Johnny'  # Should NOT be changed (was not missing)
        assert existing_contact.last_name == 'Doe'  # Should be updated (was missing)
        assert existing_contact.email == 'john@example.com'  # Should be updated (was missing)
        
        # Verify results
        assert result['successful'] >= 1
        assert result['duplicates'] == 1  # One duplicate found and merged


class TestPropertyRadarDuplicateStrategies:
    """Test duplicate strategies for PropertyRadar imports."""
    
    @pytest.fixture
    def mock_repositories(self):
        """Create mock repositories for testing."""
        return {
            'contact_repository': Mock(),
            'csv_import_repository': Mock(),
            'contact_csv_import_repository': Mock(),
            'campaign_list_repository': Mock(),
            'campaign_list_member_repository': Mock(),
            'contact_service': Mock()
        }
    
    @pytest.fixture
    def csv_service(self, mock_repositories):
        """Create CSVImportService with mocked dependencies."""
        return CSVImportService(
            contact_repository=mock_repositories['contact_repository'],
            csv_import_repository=mock_repositories['csv_import_repository'],
            contact_csv_import_repository=mock_repositories['contact_csv_import_repository'],
            campaign_list_repository=mock_repositories['campaign_list_repository'],
            campaign_list_member_repository=mock_repositories['campaign_list_member_repository'],
            contact_service=mock_repositories['contact_service']
        )
    
    @pytest.fixture
    def propertyradar_csv_content(self):
        """Create PropertyRadar format CSV content."""
        return b"""Primary First Name,Primary Last Name,Primary Mobile Phone1,Secondary Name,Secondary Mobile Phone1,Address,City,ZIP
John,Doe,+11234567890,Jane,Doe,+10987654321,123 Main St,Boston,02101
Bob,Smith,+15555555555,Alice,Smith,+14444444444,456 Oak Ave,Cambridge,02139"""
    
    @patch('services.propertyradar_import_service.PropertyRadarImportService')
    def test_propertyradar_import_uses_duplicate_strategy(self, MockPRService, csv_service, mock_repositories, propertyradar_csv_content):
        """Test that PropertyRadar import respects duplicate strategy."""
        # Setup
        file = FileStorage(stream=BytesIO(propertyradar_csv_content), filename='propertyradar_export.csv')
        
        # Configure mock PropertyRadar service
        mock_pr_instance = Mock()
        MockPRService.return_value = mock_pr_instance
        
        # Configure successful import result
        from services.common.result import Result
        mock_pr_instance.import_propertyradar_csv.return_value = Result.success({
            'contacts_created': 2,
            'contacts_updated': 1,
            'errors': [],
            'list_id': None
        })
        
        mock_csv_import = Mock(spec=CSVImport)
        mock_csv_import.id = 1
        mock_repositories['csv_import_repository'].create.return_value = mock_csv_import
        
        # Execute with replace strategy
        result = csv_service.import_csv(
            file=file,
            duplicate_strategy='replace'
        )
        
        # Verify PropertyRadar service was called with correct duplicate_strategy
        mock_pr_instance.import_propertyradar_csv.assert_called_once()
        call_args = mock_pr_instance.import_propertyradar_csv.call_args
        # Check keyword arguments for duplicate_strategy
        assert call_args.kwargs.get('duplicate_strategy') == 'replace'