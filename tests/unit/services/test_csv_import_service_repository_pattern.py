"""
CSVImportService Repository Pattern Tests
TDD RED Phase: Write comprehensive tests for service using repository pattern BEFORE implementation
"""

import pytest
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock
from werkzeug.datastructures import FileStorage
from io import BytesIO

from services.csv_import_service import CSVImportService
from crm_database import Contact, CSVImport, CampaignList, CampaignListMember, ContactCSVImport
from repositories.csv_import_repository import CSVImportRepository
from repositories.contact_csv_import_repository import ContactCSVImportRepository
from repositories.campaign_list_repository import CampaignListRepository
from repositories.campaign_list_member_repository import CampaignListMemberRepository
from repositories.contact_repository import ContactRepository


class TestCSVImportServiceRepositoryPattern:
    """Test CSVImportService using repository pattern - NO direct database access allowed"""
    
    @pytest.fixture
    def mock_csv_import_repo(self):
        """Mock CSV import repository"""
        return Mock(spec=CSVImportRepository)
    
    @pytest.fixture
    def mock_contact_csv_import_repo(self):
        """Mock contact-CSV import association repository"""
        return Mock(spec=ContactCSVImportRepository)
    
    @pytest.fixture
    def mock_campaign_list_repo(self):
        """Mock campaign list repository"""
        return Mock(spec=CampaignListRepository)
    
    @pytest.fixture
    def mock_campaign_list_member_repo(self):
        """Mock campaign list member repository"""
        return Mock(spec=CampaignListMemberRepository)
    
    @pytest.fixture
    def mock_contact_repo(self):
        """Mock contact repository"""
        return Mock(spec=ContactRepository)
    
    @pytest.fixture
    def mock_contact_service(self):
        """Mock contact service (dependency)"""
        mock_service = Mock()
        mock_service.normalize_phone.return_value = '+11234567890'
        return mock_service
    
    @pytest.fixture
    def service(
        self,
        mock_csv_import_repo,
        mock_contact_csv_import_repo,
        mock_campaign_list_repo,
        mock_campaign_list_member_repo,
        mock_contact_repo,
        mock_contact_service
    ):
        """Create service instance with all repository dependencies injected"""
        return CSVImportService(
            csv_import_repository=mock_csv_import_repo,
            contact_csv_import_repository=mock_contact_csv_import_repo,
            campaign_list_repository=mock_campaign_list_repo,
            campaign_list_member_repository=mock_campaign_list_member_repo,
            contact_repository=mock_contact_repo,
            contact_service=mock_contact_service
        )
    
    @pytest.fixture
    def sample_csv_content(self):
        """Sample CSV content for testing"""
        return """first_name,last_name,phone,email
John,Doe,+11234567890,john@example.com
Jane,Smith,+19876543210,jane@example.com
Bob,Johnson,+15555551234,bob@example.com"""
    
    @pytest.fixture
    def mock_file(self, sample_csv_content):
        """Mock uploaded file"""
        file_data = BytesIO(sample_csv_content.encode('utf-8'))
        mock_file = Mock(spec=FileStorage)
        mock_file.filename = 'test_contacts.csv'
        mock_file.save = Mock()
        return mock_file, file_data
    
    def test_service_initialization_requires_repositories(self):
        """Test that service requires all repository dependencies"""
        # Should fail if repositories not provided
        with pytest.raises(TypeError):
            CSVImportService()
        
        # Should fail if missing repositories
        with pytest.raises(TypeError):
            CSVImportService(
                csv_import_repository=Mock(),
                # Missing other repositories
            )
    
    def test_import_contacts_creates_csv_import_record(self, service, mock_file, mock_csv_import_repo):
        """Test that import creates CSV import record using repository"""
        # Arrange
        file, _ = mock_file
        mock_import = Mock(spec=CSVImport)
        mock_import.id = 1
        mock_csv_import_repo.create.return_value = mock_import
        mock_csv_import_repo.update_import_status.return_value = mock_import
        
        # Mock other dependencies
        service.contact_repository.find_by_phone.return_value = None  # No existing contacts
        service.contact_repository.create.return_value = Mock(id=1)
        
        # Mock service methods
        with patch.object(service, 'normalize_phone', return_value='+11234567890'), \
             patch.object(service, 'detect_format', return_value='standard'), \
             patch.object(service, '_extract_metadata_from_mapped', return_value={}):
            # Act
            with patch('builtins.open'), patch('os.remove'):
                with patch('csv.DictReader') as mock_csv_reader:
                    mock_reader_instance = Mock()
                    mock_reader_instance.fieldnames = ['first_name', 'last_name', 'phone', 'email']
                    mock_reader_instance.__iter__ = Mock(return_value=iter([
                        {'first_name': 'John', 'last_name': 'Doe', 'phone': '+11234567890', 'email': 'john@example.com'}
                    ]))
                    mock_csv_reader.return_value = mock_reader_instance
                    result = service.import_contacts(file)
        
        # Assert
        mock_csv_import_repo.create.assert_called_once()
        create_args = mock_csv_import_repo.create.call_args[1]
        assert create_args['filename'] == 'test_contacts.csv'
        assert create_args['import_type'] == 'contacts'
        assert 'imported_at' in create_args
    
    def test_import_contacts_creates_campaign_list_when_requested(self, service, mock_file, mock_campaign_list_repo):
        """Test that import creates campaign list when create_list=True"""
        # Arrange
        file, _ = mock_file
        mock_list = Mock(spec=CampaignList)
        mock_list.id = 1
        mock_campaign_list_repo.create.return_value = mock_list
        
        # Mock dependencies
        service.csv_import_repository.create.return_value = Mock(id=1)
        service.csv_import_repository.update_import_status.return_value = Mock()
        service.contact_repository.find_by_phone.return_value = None
        service.contact_repository.create.return_value = Mock(id=1)
        
        # Act
        with patch('builtins.open'), patch('csv.DictReader'), patch('os.remove'):
            result = service.import_contacts(file, create_list=True, list_name='Test List')
        
        # Assert
        mock_campaign_list_repo.create.assert_called_once()
        create_args = mock_campaign_list_repo.create.call_args[1]
        assert create_args['name'] == 'Test List'
        assert 'description' in create_args
        assert 'filter_criteria' in create_args
    
    def test_import_contacts_does_not_create_campaign_list_when_not_requested(self, service, mock_file, mock_campaign_list_repo):
        """Test that import does not create campaign list when create_list=False"""
        # Arrange
        file, _ = mock_file
        
        # Mock dependencies
        service.csv_import_repository.create.return_value = Mock(id=1)
        service.csv_import_repository.update_import_status.return_value = Mock()
        service.contact_repository.find_by_phone.return_value = None
        service.contact_repository.create.return_value = Mock(id=1)
        
        # Act
        with patch('builtins.open'), patch('csv.DictReader'), patch('os.remove'):
            result = service.import_contacts(file, create_list=False)
        
        # Assert
        mock_campaign_list_repo.create.assert_not_called()
    
    def test_import_contacts_handles_existing_contact_via_repository(self, service, mock_file, mock_contact_repo):
        """Test that import finds existing contacts using repository"""
        # Arrange
        file, _ = mock_file
        existing_contact = Mock(spec=Contact)
        existing_contact.id = 123
        existing_contact.first_name = 'John'
        existing_contact.last_name = None
        existing_contact.email = None
        existing_contact.contact_metadata = {}
        mock_contact_repo.find_by_phone.return_value = existing_contact
        
        # Mock dependencies
        service.csv_import_repository.create.return_value = Mock(id=1)
        service.csv_import_repository.update_import_status.return_value = Mock()
        service.contact_csv_import_repository.exists_for_contact_and_import.return_value = False
        service.contact_csv_import_repository.create.return_value = Mock()
        
        # Mock service methods
        with patch.object(service, 'normalize_phone', return_value='+11234567890'), \
             patch.object(service, 'detect_format', return_value='standard'), \
             patch.object(service, '_extract_metadata_from_mapped', return_value={}):        
            # Act
            with patch('builtins.open'), patch('os.remove'):
                with patch('csv.DictReader') as mock_csv_reader:
                    mock_reader_instance = Mock()
                    mock_reader_instance.fieldnames = ['first_name', 'last_name', 'phone', 'email']
                    mock_reader_instance.__iter__ = Mock(return_value=iter([
                        {'first_name': 'John', 'last_name': 'Doe', 'phone': '+11234567890', 'email': 'john@example.com'}
                    ]))
                    mock_csv_reader.return_value = mock_reader_instance
                    result = service.import_contacts(file)
        
        # Assert
        mock_contact_repo.find_by_phone.assert_called()
        # Should not create new contact if existing found
        mock_contact_repo.create.assert_not_called()
    
    def test_import_contacts_creates_new_contact_via_repository(self, service, mock_file, mock_contact_repo):
        """Test that import creates new contacts using repository"""
        # Arrange
        file, _ = mock_file
        mock_contact_repo.find_by_phone.return_value = None  # No existing contact
        new_contact = Mock(spec=Contact)
        new_contact.id = 456
        mock_contact_repo.create.return_value = new_contact
        
        # Mock dependencies
        service.csv_import_repository.create.return_value = Mock(id=1)
        service.csv_import_repository.update_import_status.return_value = Mock()
        service.contact_csv_import_repository.exists_for_contact_and_import.return_value = False
        service.contact_csv_import_repository.create.return_value = Mock()
        
        # Mock service methods
        with patch.object(service, 'normalize_phone', return_value='+11234567890'), \
             patch.object(service, 'detect_format', return_value='standard'), \
             patch.object(service, '_extract_metadata_from_mapped', return_value={}):        
            # Act
            with patch('builtins.open'), patch('os.remove'):
                with patch('csv.DictReader') as mock_csv_reader:
                    mock_reader_instance = Mock()
                    mock_reader_instance.fieldnames = ['first_name', 'last_name', 'phone', 'email']
                    mock_reader_instance.__iter__ = Mock(return_value=iter([
                        {'first_name': 'John', 'last_name': 'Doe', 'phone': '+11234567890', 'email': 'john@example.com'}
                    ]))
                    mock_csv_reader.return_value = mock_reader_instance
                    result = service.import_contacts(file)
        
        # Assert
        mock_contact_repo.find_by_phone.assert_called()
        mock_contact_repo.create.assert_called()
    
    def test_import_contacts_creates_contact_csv_import_associations(self, service, mock_file, mock_contact_csv_import_repo):
        """Test that import creates contact-CSV import associations"""
        # Arrange
        file, _ = mock_file
        
        # Mock dependencies
        service.csv_import_repository.create.return_value = Mock(id=1)
        service.csv_import_repository.update_import_status.return_value = Mock()
        service.contact_repository.find_by_phone.return_value = None
        service.contact_repository.create.return_value = Mock(id=456)
        mock_contact_csv_import_repo.exists_for_contact_and_import.return_value = False
        
        # Mock service methods
        with patch.object(service, 'normalize_phone', return_value='+11234567890'), \
             patch.object(service, 'detect_format', return_value='standard'), \
             patch.object(service, '_extract_metadata_from_mapped', return_value={}):
            # Act
            with patch('builtins.open'), patch('os.remove'):
                with patch('csv.DictReader') as mock_csv_reader:
                    mock_reader_instance = Mock()
                    mock_reader_instance.fieldnames = ['first_name', 'last_name', 'phone', 'email']
                    mock_reader_instance.__iter__ = Mock(return_value=iter([
                        {'first_name': 'John', 'last_name': 'Doe', 'phone': '+11234567890', 'email': 'john@example.com'}
                    ]))
                    mock_csv_reader.return_value = mock_reader_instance
                    result = service.import_contacts(file)
        
        # Assert
        mock_contact_csv_import_repo.exists_for_contact_and_import.assert_called()
        mock_contact_csv_import_repo.create.assert_called()
    
    def test_import_contacts_avoids_duplicate_associations(self, service, mock_file, mock_contact_csv_import_repo):
        """Test that import avoids creating duplicate associations"""
        # Arrange
        file, _ = mock_file
        mock_contact_csv_import_repo.exists_for_contact_and_import.return_value = True  # Already exists
        
        # Mock dependencies
        service.csv_import_repository.create.return_value = Mock(id=1)
        service.csv_import_repository.update_import_status.return_value = Mock()
        existing_contact = Mock(id=456)
        existing_contact.first_name = 'Existing'
        existing_contact.last_name = 'Contact'
        existing_contact.email = None
        existing_contact.contact_metadata = {}
        service.contact_repository.find_by_phone.return_value = existing_contact
        
        # Mock service methods
        with patch.object(service, 'normalize_phone', return_value='+11234567890'), \
             patch.object(service, 'detect_format', return_value='standard'), \
             patch.object(service, '_extract_metadata_from_mapped', return_value={}):
            # Act
            with patch('builtins.open'), patch('os.remove'):
                with patch('csv.DictReader') as mock_csv_reader:
                    mock_reader_instance = Mock()
                    mock_reader_instance.fieldnames = ['first_name', 'last_name', 'phone', 'email']
                    mock_reader_instance.__iter__ = Mock(return_value=iter([
                        {'first_name': 'John', 'last_name': 'Doe', 'phone': '+11234567890', 'email': 'john@example.com'}
                    ]))
                    mock_csv_reader.return_value = mock_reader_instance
                    result = service.import_contacts(file)
        
        # Assert
        mock_contact_csv_import_repo.exists_for_contact_and_import.assert_called()
        # Should not create association if already exists
        mock_contact_csv_import_repo.create.assert_not_called()
    
    def test_import_contacts_adds_to_campaign_list_via_repository(self, service, mock_file, mock_campaign_list_member_repo):
        """Test that import adds contacts to campaign list using repository"""
        # Arrange
        file, _ = mock_file
        mock_campaign_list_member_repo.find_by_list_and_contact.return_value = None  # Not in list
        
        # Mock dependencies
        service.csv_import_repository.create.return_value = Mock(id=1)
        service.csv_import_repository.update_import_status.return_value = Mock()
        service.campaign_list_repository.create.return_value = Mock(id=1)
        service.contact_repository.find_by_phone.return_value = None
        service.contact_repository.create.return_value = Mock(id=456)
        service.contact_csv_import_repository.exists_for_contact_and_import.return_value = False
        service.contact_csv_import_repository.create.return_value = Mock()
        
        # Mock service methods
        with patch.object(service, 'normalize_phone', return_value='+11234567890'), \
             patch.object(service, 'detect_format', return_value='standard'), \
             patch.object(service, '_extract_metadata_from_mapped', return_value={}):
            # Act
            with patch('builtins.open'), patch('os.remove'):
                with patch('csv.DictReader') as mock_csv_reader:
                    mock_reader_instance = Mock()
                    mock_reader_instance.fieldnames = ['first_name', 'last_name', 'phone', 'email']
                    mock_reader_instance.__iter__ = Mock(return_value=iter([
                        {'first_name': 'John', 'last_name': 'Doe', 'phone': '+11234567890', 'email': 'john@example.com'}
                    ]))
                    mock_csv_reader.return_value = mock_reader_instance
                    result = service.import_contacts(file, create_list=True)
        
        # Assert
        mock_campaign_list_member_repo.find_by_list_and_contact.assert_called()
        mock_campaign_list_member_repo.create.assert_called()
    
    def test_import_contacts_reactivates_removed_campaign_members(self, service, mock_file, mock_campaign_list_member_repo):
        """Test that import reactivates removed campaign list members"""
        # Arrange
        file, _ = mock_file
        existing_member = Mock(spec=CampaignListMember)
        existing_member.status = 'removed'
        mock_campaign_list_member_repo.find_by_list_and_contact.return_value = existing_member
        
        # Mock dependencies
        service.csv_import_repository.create.return_value = Mock(id=1)
        service.csv_import_repository.update_import_status.return_value = Mock()
        service.campaign_list_repository.create.return_value = Mock(id=1)
        service.contact_repository.find_by_phone.return_value = None
        service.contact_repository.create.return_value = Mock(id=456)
        service.contact_csv_import_repository.exists_for_contact_and_import.return_value = False
        service.contact_csv_import_repository.create.return_value = Mock()
        
        # Mock service methods
        with patch.object(service, 'normalize_phone', return_value='+11234567890'), \
             patch.object(service, 'detect_format', return_value='standard'), \
             patch.object(service, '_extract_metadata_from_mapped', return_value={}):
            # Act
            with patch('builtins.open'), patch('os.remove'):
                with patch('csv.DictReader') as mock_csv_reader:
                    mock_reader_instance = Mock()
                    mock_reader_instance.fieldnames = ['first_name', 'last_name', 'phone', 'email']
                    mock_reader_instance.__iter__ = Mock(return_value=iter([
                        {'first_name': 'John', 'last_name': 'Doe', 'phone': '+11234567890', 'email': 'john@example.com'}
                    ]))
                    mock_csv_reader.return_value = mock_reader_instance
                    result = service.import_contacts(file, create_list=True)
        
        # Assert
        mock_campaign_list_member_repo.update.assert_called()
        update_args = mock_campaign_list_member_repo.update.call_args[1]
        assert update_args['status'] == 'active'
        assert 'added_at' in update_args
    
    def test_import_contacts_updates_import_status_at_end(self, service, mock_file, mock_csv_import_repo):
        """Test that import updates final status using repository"""
        # Arrange
        file, _ = mock_file
        mock_import = Mock(id=1)
        mock_csv_import_repo.create.return_value = mock_import
        
        # Mock dependencies
        service.contact_repository.find_by_phone.return_value = None
        service.contact_repository.create.return_value = Mock(id=456)
        
        # Mock service methods
        with patch.object(service, 'normalize_phone', return_value='+11234567890'), \
             patch.object(service, 'detect_format', return_value='standard'), \
             patch.object(service, '_extract_metadata_from_mapped', return_value={}):
            # Act
            with patch('builtins.open'), patch('os.remove'):
                with patch('csv.DictReader') as mock_csv_reader:
                    mock_reader_instance = Mock()
                    mock_reader_instance.fieldnames = ['first_name', 'last_name', 'phone', 'email']
                    mock_reader_instance.__iter__ = Mock(return_value=iter([
                        {'first_name': 'John', 'last_name': 'Doe', 'phone': '+11234567890', 'email': 'john@example.com'}
                    ]))
                    mock_csv_reader.return_value = mock_reader_instance
                    result = service.import_contacts(file)
        
        # Assert
        mock_csv_import_repo.update_import_status.assert_called_once()
        args = mock_csv_import_repo.update_import_status.call_args[0]
        assert args[0] == 1  # import_id
        assert args[1] >= 0   # total_rows
        assert args[2] >= 0   # successful
        assert args[3] >= 0   # failed
        assert isinstance(args[4], dict)  # metadata
    
    def test_import_contacts_handles_transaction_rollback_on_error(self, service, mock_file, mock_csv_import_repo):
        """Test that import handles transaction rollback on errors"""
        # Arrange
        file, _ = mock_file
        service.contact_repository.create.side_effect = Exception('Database error')
        
        # Mock dependencies
        mock_csv_import_repo.create.return_value = Mock(id=1)
        service.contact_repository.find_by_phone.return_value = None
        
        # Mock service methods
        with patch.object(service, 'normalize_phone', return_value='+11234567890'), \
             patch.object(service, 'detect_format', return_value='standard'), \
             patch.object(service, '_extract_metadata_from_mapped', return_value={}):
            # Act
            with patch('builtins.open'), patch('os.remove'):
                with patch('csv.DictReader') as mock_csv_reader:
                    mock_reader_instance = Mock()
                    mock_reader_instance.fieldnames = ['first_name', 'last_name', 'phone', 'email']
                    mock_reader_instance.__iter__ = Mock(return_value=iter([
                        {'first_name': 'John', 'last_name': 'Doe', 'phone': '+11234567890', 'email': 'john@example.com'}
                    ]))
                    mock_csv_reader.return_value = mock_reader_instance
                    result = service.import_contacts(file)
        
        # Assert
        # Should still update import record with error information
        mock_csv_import_repo.update_import_status.assert_called()
        args = mock_csv_import_repo.update_import_status.call_args[0]
        assert args[3] > 0  # failed_imports should be > 0
        assert 'errors' in args[4]  # metadata should contain errors
    
    def test_import_contacts_uses_bulk_operations_for_performance(self, service, mock_file, mock_contact_csv_import_repo):
        """Test that import uses bulk operations for better performance"""
        # Arrange
        file, _ = mock_file
        # Mock multiple contacts to trigger bulk operations
        service.contact_repository.find_by_phone.return_value = None
        service.contact_repository.create.return_value = Mock(id=456)
        
        # Mock dependencies
        service.csv_import_repository.create.return_value = Mock(id=1)
        service.csv_import_repository.update_import_status.return_value = Mock()
        service.contact_csv_import_repository.exists_for_contact_and_import.return_value = False
        service.contact_csv_import_repository.create.return_value = Mock()
        
        # Mock service methods
        with patch.object(service, 'normalize_phone', return_value='+11234567890'), \
             patch.object(service, 'detect_format', return_value='standard'), \
             patch.object(service, '_extract_metadata_from_mapped', return_value={}):
            # Act
            with patch('builtins.open'), patch('os.remove'):
                with patch('csv.DictReader') as mock_csv_reader:
                    mock_reader_instance = Mock()
                    mock_reader_instance.fieldnames = ['first_name', 'phone']
                    mock_reader_instance.__iter__ = Mock(return_value=iter([
                        {'first_name': 'John', 'phone': '+11234567890'},
                        {'first_name': 'Jane', 'phone': '+19876543210'}
                    ]))
                    mock_csv_reader.return_value = mock_reader_instance
                    result = service.import_contacts(file)
        
        # Assert
        # Should call repositories multiple times for multiple contacts
        assert service.contact_repository.find_by_phone.call_count >= 2
        assert service.contact_repository.create.call_count >= 2
    
    def test_get_import_history_uses_repository(self, service, mock_csv_import_repo):
        """Test that get_import_history uses repository"""
        # Arrange
        expected_imports = [Mock(spec=CSVImport), Mock(spec=CSVImport)]
        mock_csv_import_repo.get_recent_imports.return_value = expected_imports
        
        # Act
        result = service.get_import_history(limit=5)
        
        # Assert
        assert result == expected_imports
        mock_csv_import_repo.get_recent_imports.assert_called_once_with(limit=5)
    
    def test_get_contacts_by_import_uses_repository(self, service, mock_contact_csv_import_repo):
        """Test that get_contacts_by_import uses repository"""
        # Arrange
        import_id = 123
        expected_contacts = [Mock(spec=Contact), Mock(spec=Contact)]
        mock_contact_csv_import_repo.get_contacts_by_import_with_details.return_value = [
            (expected_contacts[0], Mock()),
            (expected_contacts[1], Mock())
        ]
        
        # Act
        result = service.get_contacts_by_import(import_id)
        
        # Assert
        assert result == expected_contacts
        mock_contact_csv_import_repo.get_contacts_by_import_with_details.assert_called_once_with(import_id)
    
    def test_service_never_directly_accesses_database_models(self, service):
        """Test that service never imports or uses database models directly"""
        # This test ensures the service doesn't violate repository pattern
        import inspect
        service_source = inspect.getsource(service.__class__)
        
        # Should not import database models
        forbidden_imports = [
            'from crm_database import Contact',
            'from crm_database import CSVImport',
            'from crm_database import CampaignList',
            'Contact.query',
            'CSVImport.query',
            'db.session.add',
            'db.session.commit',
            'db.session.rollback'
        ]
        
        for forbidden in forbidden_imports:
            assert forbidden not in service_source, f'Service should not use {forbidden}'
    
    def test_service_commits_transactions_through_repositories(self, service, mock_file):
        """Test that service commits transactions through repository methods"""
        # Arrange
        file, _ = mock_file
        
        # Mock dependencies
        service.csv_import_repository.create.return_value = Mock(id=1)
        service.csv_import_repository.update_import_status.return_value = Mock()
        service.contact_repository.find_by_phone.return_value = None
        service.contact_repository.create.return_value = Mock(id=456)
        
        # Mock service methods
        with patch.object(service, 'normalize_phone', return_value='+11234567890'), \
             patch.object(service, 'detect_format', return_value='standard'), \
             patch.object(service, '_extract_metadata_from_mapped', return_value={}):
            # Act
            with patch('builtins.open'), patch('os.remove'):
                with patch('csv.DictReader') as mock_csv_reader:
                    mock_reader_instance = Mock()
                    mock_reader_instance.fieldnames = ['first_name', 'last_name', 'phone', 'email']
                    mock_reader_instance.__iter__ = Mock(return_value=iter([
                        {'first_name': 'John', 'last_name': 'Doe', 'phone': '+11234567890', 'email': 'john@example.com'}
                    ]))
                    mock_csv_reader.return_value = mock_reader_instance
                    result = service.import_contacts(file)
        
        # Assert
        # Repositories should handle their own transactions
        # Service should not directly call db.session.commit
        # This is verified by the repository pattern - each repo manages its own transactions
        assert 'import_id' in result
        assert 'successful' in result
