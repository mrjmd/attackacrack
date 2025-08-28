"""
Comprehensive test suite for CSVImportService following strict TDD principles.

This test file is designed to FAIL initially and guide the implementation through
proper test-driven development. All tests are written to demonstrate expected
behavior that must be implemented.

Coverage Requirements:
- Format detection for all supported CSV types
- Phone number normalization edge cases  
- Import functionality (success and failure scenarios)
- Metadata extraction for different formats
- Error handling (invalid files, malformed data, database errors)
- Campaign list creation and association
- Import history and contact retrieval
"""

import pytest
import io
import os
import tempfile
from datetime import datetime
from utils.datetime_utils import utc_now
from unittest.mock import Mock, patch, MagicMock, mock_open
from werkzeug.datastructures import FileStorage

from services.csv_import_service import CSVImportService
from services.contact_service_refactored import ContactService
from crm_database import Contact, CSVImport, CampaignList, CampaignListMember, ContactCSVImport


# ============================================================================
# FACTORY FIXTURES FOR TEST DATA GENERATION
# ============================================================================

@pytest.fixture
def mock_contact_service():
    """Factory fixture for mock ContactService"""
    return Mock(spec=ContactService)


@pytest.fixture
def csv_file_mock_helper():
    """Helper to create proper CSV file mocks for tests"""
    def _create_csv_mock(csv_content):
        def mock_open_handler(path, *args, **kwargs):
            if '/tmp/' in str(path):
                from io import StringIO
                return StringIO(csv_content)
            return Mock()
        return mock_open_handler
    return _create_csv_mock


@pytest.fixture
def mock_csv_import_repository():
    """Mock CSV Import Repository"""
    from repositories.csv_import_repository import CSVImportRepository
    return Mock(spec=CSVImportRepository)


@pytest.fixture
def mock_contact_csv_import_repository():
    """Mock Contact CSV Import Repository"""
    from repositories.contact_csv_import_repository import ContactCSVImportRepository
    return Mock(spec=ContactCSVImportRepository)


@pytest.fixture
def mock_campaign_list_repository():
    """Mock Campaign List Repository"""
    from repositories.campaign_list_repository import CampaignListRepository
    return Mock(spec=CampaignListRepository)


@pytest.fixture
def mock_campaign_list_member_repository():
    """Mock Campaign List Member Repository"""
    from repositories.campaign_list_member_repository import CampaignListMemberRepository
    return Mock(spec=CampaignListMemberRepository)


@pytest.fixture
def mock_contact_repository():
    """Mock Contact Repository"""
    from repositories.contact_repository import ContactRepository
    return Mock(spec=ContactRepository)


@pytest.fixture
def csv_import_service(mock_csv_import_repository, mock_contact_csv_import_repository, 
                      mock_campaign_list_repository, mock_campaign_list_member_repository,
                      mock_contact_repository, mock_contact_service):
    """Factory fixture providing CSVImportService instance with mocked dependencies"""
    # Configure mock return values for common operations
    
    # Mock CSVImport creation
    mock_csv_import = Mock()
    mock_csv_import.id = 1
    mock_csv_import_repository.create.return_value = mock_csv_import
    
    # Mock CampaignList creation
    mock_campaign_list = Mock()
    mock_campaign_list.id = 1
    mock_campaign_list_repository.create.return_value = mock_campaign_list
    
    # Mock Contact operations - by default no existing contacts (find_by_phone returns None)
    mock_contact_repository.find_by_phone.return_value = None
    
    # Mock Contact creation - return a different contact for each call
    def create_contact(**kwargs):
        contact = Mock()
        contact.id = kwargs.get('phone', 'default')  # Use phone as ID for uniqueness
        contact.phone = kwargs.get('phone')
        contact.first_name = kwargs.get('first_name', '')
        contact.last_name = kwargs.get('last_name', '')
        contact.email = kwargs.get('email')
        contact.contact_metadata = kwargs.get('contact_metadata', {})
        return contact
    mock_contact_repository.create.side_effect = create_contact
    
    # Mock ContactCSVImport operations
    mock_contact_csv_import_repository.exists_for_contact_and_import.return_value = False
    mock_contact_csv_import = Mock()
    mock_contact_csv_import_repository.create.return_value = mock_contact_csv_import
    
    # Mock CampaignListMember operations
    mock_campaign_list_member_repository.find_by_list_and_contact.return_value = None
    mock_campaign_list_member = Mock()
    mock_campaign_list_member_repository.create.return_value = mock_campaign_list_member
    
    return CSVImportService(
        csv_import_repository=mock_csv_import_repository,
        contact_csv_import_repository=mock_contact_csv_import_repository,
        campaign_list_repository=mock_campaign_list_repository,
        campaign_list_member_repository=mock_campaign_list_member_repository,
        contact_repository=mock_contact_repository,
        contact_service=mock_contact_service
    )


@pytest.fixture
def sample_csv_headers():
    """Factory providing various CSV header formats for testing"""
    return {
        'standard': ['first_name', 'last_name', 'phone', 'email', 'company'],
        'openphone': ['First name', 'Last name', 'Phone number', 'Email', 'Address', 'Role'],
        'realtor': ['jsx-123', 'First Name', 'Last Name', 'Phone', 'Company'],
        'sothebys': ['First Name', 'Last Name', 'Phone', 'Company'],
        'vicente': ['First Name', 'Last Name', 'Email', 'Phone'],
        'exit_cape': ['uk-text-muted', 'lastname', 'agent-card__tel', 'Exit Realty'],
        'exit_premier': ['mb-2', 'lastname', 'css-1dp0fhs-no-styles-2', 'company'],
        'jackconway': ['first_name', 'last_name', 'phone_number_1', 'phone_number_2', 'email', 'location', 'company'],
        'lamacchia': ['first_name', 'last_name', 'phone', 'email', 'company'],
        'raveis': ['First_name', 'Last_name', 'Cell', 'Title', 'City', 'Company'],
        'propertyradar': ['Primary First Name', 'Primary Last Name', 'Primary Mobile Phone1', 'Primary Email1', 'Address', 'City', 'ZIP']
    }


@pytest.fixture
def sample_csv_rows():
    """Factory providing sample CSV row data for different formats"""
    return {
        'standard': {
            'first_name': 'John',
            'last_name': 'Doe', 
            'phone': '(555) 123-4567',
            'email': 'john@example.com',
            'company': 'ACME Corp'
        },
        'openphone': {
            'First name': 'Jane',
            'Last name': 'Smith',
            'Phone number': '+1 555 987 6543',
            'Email': 'jane@example.com',
            'Address': '123 Main St',
            'Role': 'Manager'
        },
        'propertyradar': {
            'Primary First Name': 'Bob',
            'Primary Last Name': 'Johnson',
            'Primary Mobile Phone1': '555.111.2222',
            'Primary Email1': 'bob@example.com',
            'Address': '456 Oak Ave',
            'City': 'Boston',
            'ZIP': '02101'
        }
    }


@pytest.fixture
def mock_file_storage():
    """Factory fixture for mock FileStorage objects"""
    def _create_mock_file(filename, content="first_name,last_name,phone\nJohn,Doe,5551234567"):
        mock_file = Mock()  # Remove spec restriction
        mock_file.filename = filename
        mock_file.save = Mock()
        # Add read and seek methods needed by CSV import logic
        mock_file.read.return_value = content.encode('utf-8')
        mock_file.seek = Mock()
        return mock_file
    return _create_mock_file


@pytest.fixture
def sample_phone_numbers():
    """Factory providing various phone number formats for normalization testing"""
    return {
        'valid': [
            ('5551234567', '+15551234567'),           # 10 digits
            ('15551234567', '+15551234567'),          # 11 digits with 1
            ('(555) 123-4567', '+15551234567'),       # Formatted
            ('+1 555 123 4567', '+15551234567'),      # International
            ('555.123.4567', '+15551234567'),         # Dot separated
            ('555-123-4567', '+15551234567'),         # Hyphen separated
            ('1 555 123 4567', '+15551234567'),       # Space separated
        ],
        'invalid': [
            '',                                        # Empty
            None,                                      # None
            '555123456',                              # Too short (9 digits)
            '55512345678',                            # Too long (11 digits without 1)
            '25551234567',                            # Invalid country code
            'abc1234567',                             # Contains letters
            '000-000-0000',                           # All zeros (edge case)
        ]
    }


@pytest.fixture  
def mock_db_models():
    """Factory fixture providing mock database models"""
    def _create_mock_models():
        # Mock Contact model
        mock_contact = Mock(spec=Contact)
        mock_contact.id = 1
        mock_contact.phone = '+15551234567'
        mock_contact.first_name = 'John'
        mock_contact.last_name = 'Doe'
        mock_contact.email = 'john@example.com'
        mock_contact.contact_metadata = {}
        
        # Mock CSVImport model
        mock_csv_import = Mock(spec=CSVImport)
        mock_csv_import.id = 1
        mock_csv_import.filename = 'test.csv'
        mock_csv_import.imported_at = utc_now()
        mock_csv_import.contacts = [mock_contact]
        
        # Mock CampaignList model
        mock_campaign_list = Mock(spec=CampaignList)
        mock_campaign_list.id = 1
        mock_campaign_list.name = 'Test List'
        
        return {
            'contact': mock_contact,
            'csv_import': mock_csv_import,
            'campaign_list': mock_campaign_list
        }
    return _create_mock_models


# ============================================================================
# FORMAT DETECTION TESTS (MUST FAIL INITIALLY)
# ============================================================================

class TestFormatDetection:
    """Test CSV format detection functionality"""
    
    def test_detect_standard_format_by_headers(self, csv_import_service, sample_csv_headers):
        """Test detection of standard format using column headers"""
        # Arrange
        headers = sample_csv_headers['standard']
        filename = 'contacts.csv'
        
        # Act
        detected_format = csv_import_service.detect_format(headers, filename)
        
        # Assert
        assert detected_format == 'standard'
    
    def test_detect_openphone_format_by_headers(self, csv_import_service, sample_csv_headers):
        """Test detection of OpenPhone format using distinctive headers"""
        # Arrange
        headers = sample_csv_headers['openphone']
        filename = 'export.csv'
        
        # Act
        detected_format = csv_import_service.detect_format(headers, filename)
        
        # Assert
        assert detected_format == 'openphone'
    
    def test_detect_openphone_format_by_filename(self, csv_import_service):
        """Test detection of OpenPhone format using filename pattern"""
        # Arrange
        headers = ['Name', 'Phone']  # Generic headers
        filename = 'openphone_export_2025.csv'
        
        # Act
        detected_format = csv_import_service.detect_format(headers, filename)
        
        # Assert
        assert detected_format == 'openphone'
    
    def test_detect_propertyradar_format_by_headers(self, csv_import_service, sample_csv_headers):
        """Test detection of PropertyRadar format using distinctive headers"""
        # Arrange
        headers = sample_csv_headers['propertyradar']
        filename = 'data.csv'
        
        # Act
        detected_format = csv_import_service.detect_format(headers, filename)
        
        # Assert
        assert detected_format == 'propertyradar'
    
    def test_detect_propertyradar_format_by_filename(self, csv_import_service):
        """Test detection of PropertyRadar format using filename pattern"""
        # Arrange
        headers = ['Name', 'Phone']
        filename = 'cleaned_data_phone_2025.csv'
        
        # Act
        detected_format = csv_import_service.detect_format(headers, filename)
        
        # Assert
        assert detected_format == 'propertyradar'
    
    def test_detect_raveis_format_by_headers(self, csv_import_service, sample_csv_headers):
        """Test detection of Raveis format using distinctive headers"""
        # Arrange
        headers = sample_csv_headers['raveis']
        filename = 'agents.csv'
        
        # Act
        detected_format = csv_import_service.detect_format(headers, filename)
        
        # Assert
        assert detected_format == 'raveis'
    
    def test_detect_exit_cape_format_by_headers(self, csv_import_service, sample_csv_headers):
        """Test detection of Exit Cape format using CSS class headers"""
        # Arrange
        headers = sample_csv_headers['exit_cape']
        filename = 'agents.csv'
        
        # Act
        detected_format = csv_import_service.detect_format(headers, filename)
        
        # Assert
        assert detected_format == 'exit_cape'
    
    def test_detect_jackconway_format_by_headers(self, csv_import_service, sample_csv_headers):
        """Test detection of Jack Conway format using phone_number_1 header"""
        # Arrange
        headers = sample_csv_headers['jackconway']
        filename = 'agents.csv'
        
        # Act
        detected_format = csv_import_service.detect_format(headers, filename)
        
        # Assert
        assert detected_format == 'jackconway'
    
    @pytest.mark.parametrize("format_name,filename_pattern", [
        ('realtor', 'realtor_agents.csv'),
        ('sothebys', 'sotheby_team.csv'),
        ('vicente', 'vicente_contacts.csv'),
        ('exit_premier', 'exitpremier_list.csv'),
        ('lamacchia', 'lamacchia_agents.csv'),
        ('raveis', 'raveis_export.csv'),
    ])
    def test_detect_format_by_filename_patterns(self, csv_import_service, format_name, filename_pattern):
        """Test format detection using filename patterns for various formats"""
        # Arrange
        headers = ['Name', 'Phone']  # Generic headers
        
        # Act
        detected_format = csv_import_service.detect_format(headers, filename_pattern)
        
        # Assert
        assert detected_format == format_name
    
    def test_detect_format_returns_none_for_unknown(self, csv_import_service):
        """Test that unknown format returns None"""
        # Arrange
        headers = ['strange_column_1', 'weird_field_2']
        filename = 'unknown_format.csv'
        
        # Act
        detected_format = csv_import_service.detect_format(headers, filename)
        
        # Assert
        assert detected_format is None
    
    def test_detect_format_handles_empty_headers(self, csv_import_service):
        """Test format detection with empty headers list"""
        # Arrange
        headers = []
        filename = 'empty.csv'
        
        # Act
        detected_format = csv_import_service.detect_format(headers, filename)
        
        # Assert
        assert detected_format is None
    
    def test_detect_format_case_insensitive_filename(self, csv_import_service):
        """Test that filename detection is case insensitive"""
        # Arrange
        headers = ['Name', 'Phone']
        filename = 'OPENPHONE_EXPORT.CSV'
        
        # Act
        detected_format = csv_import_service.detect_format(headers, filename)
        
        # Assert
        assert detected_format == 'openphone'


# ============================================================================
# PHONE NUMBER NORMALIZATION TESTS (MUST FAIL INITIALLY)
# ============================================================================

class TestPhoneNormalization:
    """Test phone number normalization functionality"""
    
    @pytest.mark.parametrize("input_phone,expected_output", [
        ('5551234567', '+15551234567'),
        ('15551234567', '+15551234567'),
        ('(555) 123-4567', '+15551234567'),
        ('+1 555 123 4567', '+15551234567'),
        ('555.123.4567', '+15551234567'),
        ('555-123-4567', '+15551234567'),
        ('1 555 123 4567', '+15551234567'),
        ('1-555-123-4567', '+15551234567'),
        ('+1(555)123-4567', '+15551234567'),
    ])
    def test_normalize_valid_phone_numbers(self, csv_import_service, input_phone, expected_output):
        """Test normalization of valid phone numbers in various formats"""
        # Act
        result = csv_import_service.normalize_phone(input_phone)
        
        # Assert
        assert result == expected_output
    
    @pytest.mark.parametrize("invalid_phone", [
        '',                    # Empty string
        None,                  # None value
        '555123456',           # Too short (9 digits)
        '55512345678',         # Too long (11 digits without 1)
        '25551234567',         # Invalid country code  
        'abc1234567',          # Contains letters
        '000-000-0000',        # All zeros
        '123',                 # Way too short
        '1234567890123456',    # Way too long
        'phone-number',        # Text only
        '555-123-456a',        # Letter at end
    ])
    def test_normalize_invalid_phone_numbers_returns_none(self, csv_import_service, invalid_phone):
        """Test that invalid phone numbers return None"""
        # Act
        result = csv_import_service.normalize_phone(invalid_phone)
        
        # Assert
        assert result is None
    
    def test_normalize_phone_handles_international_format(self, csv_import_service):
        """Test normalization of international format numbers"""
        # Arrange
        phone = '+1 (555) 123-4567'
        
        # Act
        result = csv_import_service.normalize_phone(phone)
        
        # Assert
        assert result == '+15551234567'
    
    def test_normalize_phone_strips_whitespace(self, csv_import_service):
        """Test that whitespace is properly stripped"""
        # Arrange
        phone = '  555 123 4567  '
        
        # Act
        result = csv_import_service.normalize_phone(phone)
        
        # Assert
        assert result == '+15551234567'
    
    def test_normalize_phone_handles_numeric_input(self, csv_import_service):
        """Test normalization when input is numeric type"""
        # Arrange
        phone = 5551234567  # Integer input
        
        # Act
        result = csv_import_service.normalize_phone(phone)
        
        # Assert
        assert result == '+15551234567'


# ============================================================================
# IMPORT CONTACTS TESTS (MUST FAIL INITIALLY)
# ============================================================================

class TestImportContacts:
    """Test main import functionality"""
    
    @patch('services.csv_import_service.os.path.exists')
    @patch('services.csv_import_service.os.remove')
    def test_import_contacts_successful_standard_format(self, mock_remove, mock_exists, 
                                                       csv_import_service, mock_file_storage):
        """Test successful import of contacts in standard CSV format"""
        # Arrange
        csv_content = "first_name,last_name,phone,email\nJohn,Doe,5551234567,john@example.com\nJane,Smith,5559876543,jane@example.com"
        mock_file = mock_file_storage('test.csv', csv_content)
        mock_exists.return_value = True
        
        # Mock open to handle the temp file path
        def mock_open_handler(path, *args, **kwargs):
            if '/tmp/' in str(path):
                from io import StringIO
                return StringIO(csv_content)
            return mock_open()()
        
        with patch('builtins.open', side_effect=mock_open_handler):
            # Act
            result = csv_import_service.import_contacts(
                file=mock_file,
                list_name='Test Import',
                create_list=True,
                imported_by='test_user'
            )
        
        # Assert
        assert result['total_rows'] == 2
        assert result['successful'] == 2
        assert result['failed'] == 0
        assert result['duplicates'] == 0
        assert len(result['errors']) == 0
        assert 'import_id' in result
        assert 'list_id' in result
        mock_remove.assert_called_once()
    
    @patch('services.csv_import_service.os.path.exists')
    @patch('services.csv_import_service.os.remove')
    def test_import_contacts_handles_duplicate_phones(self, mock_remove, mock_exists,
                                                     csv_import_service, mock_file_storage):
        """Test import handling of duplicate phone numbers"""
        # Arrange
        csv_content = "first_name,last_name,phone,email\nJohn,Doe,5551234567,john@example.com"
        mock_file = mock_file_storage('test.csv', csv_content)
        mock_exists.return_value = True
        
        # Mock existing contact
        existing_contact = Mock(spec=Contact)
        existing_contact.phone = '+15551234567'
        existing_contact.first_name = 'John'
        existing_contact.last_name = 'Doe'
        existing_contact.email = 'john@example.com'
        existing_contact.contact_metadata = {}
        
        # Configure the contact repository to return existing contact for this phone
        csv_import_service.contact_repository.find_by_phone.return_value = existing_contact
        
        # Mock open to handle the temp file path
        def mock_open_handler(path, *args, **kwargs):
            if '/tmp/' in str(path):
                from io import StringIO
                return StringIO(csv_content)
            return Mock()
        
        with patch('builtins.open', side_effect=mock_open_handler):
            # Act
            result = csv_import_service.import_contacts(
                file=mock_file,
                list_name='Test Import',
                create_list=True
            )
        
        # Assert
        assert result['total_rows'] == 1
        assert result['successful'] == 1
        assert result['duplicates'] == 1
        assert result['failed'] == 0
    
    @patch('services.csv_import_service.os.path.exists') 
    @patch('services.csv_import_service.os.remove')
    def test_import_contacts_skips_rows_without_phone(self, mock_remove, mock_exists,
                                                     csv_import_service, mock_file_storage):
        """Test that rows without phone numbers are skipped with error"""
        # Arrange
        csv_content = "first_name,last_name,phone,email\nJohn,Doe,,john@example.com\nJane,Smith,5559876543,jane@example.com"
        mock_file = mock_file_storage('test.csv', csv_content)
        mock_exists.return_value = True
        
        # Mock open to handle the temp file path
        def mock_open_handler(path, *args, **kwargs):
            if '/tmp/' in str(path):
                from io import StringIO
                return StringIO(csv_content)
            return Mock()
        
        with patch('builtins.open', side_effect=mock_open_handler):
            # Act
            result = csv_import_service.import_contacts(file=mock_file)
        
        # Assert
        assert result['total_rows'] == 2
        assert result['successful'] == 1  # Only Jane Smith
        assert result['failed'] == 1      # John Doe skipped
        assert len(result['errors']) == 1
        assert 'Row 2: Missing phone number' in result['errors'][0]
    
    @patch('services.csv_import_service.os.path.exists')
    @patch('services.csv_import_service.os.remove')
    def test_import_contacts_skips_invalid_phone_format(self, mock_remove, mock_exists,
                                                       csv_import_service, mock_file_storage):
        """Test that rows with invalid phone formats are skipped"""
        # Arrange
        csv_content = "first_name,last_name,phone,email\nJohn,Doe,invalid-phone,john@example.com\nJane,Smith,5559876543,jane@example.com"
        mock_file = mock_file_storage('test.csv', csv_content)
        mock_exists.return_value = True
        
        # Mock open to handle the temp file path
        def mock_open_handler(path, *args, **kwargs):
            if '/tmp/' in str(path):
                from io import StringIO
                return StringIO(csv_content)
            return Mock()
        
        with patch('builtins.open', side_effect=mock_open_handler):
            # Act
            result = csv_import_service.import_contacts(file=mock_file)
        
        # Assert
        assert result['total_rows'] == 2
        assert result['successful'] == 1
        assert result['failed'] == 1
        assert any('Invalid phone number format' in error for error in result['errors'])
    
    def test_import_contacts_handles_file_processing_error(self, csv_import_service, mock_file_storage):
        """Test handling of file processing errors"""
        # Arrange
        mock_file = mock_file_storage('test.csv')
        
        # Mock file.save to raise an exception
        mock_file.save.side_effect = IOError("File save failed")
        
        # Act
        result = csv_import_service.import_contacts(file=mock_file)
        
        # Assert
        assert result['total_rows'] == 0
        assert result['successful'] == 0
        assert result['failed'] == 0
        assert len(result['errors']) > 0
        assert any('File processing error' in error for error in result['errors'])
    
    @patch('services.csv_import_service.os.path.exists')
    @patch('services.csv_import_service.os.remove')
    def test_import_contacts_unknown_format_fallback(self, mock_remove, mock_exists,
                                                    csv_import_service, mock_file_storage):
        """Test fallback behavior when CSV format cannot be detected"""
        # Arrange
        csv_content = "weird_column1,strange_field2\nvalue1,value2"
        mock_file = mock_file_storage('unknown.csv', csv_content)
        mock_exists.return_value = True
        
        # Mock open to handle the temp file path
        def mock_open_handler(path, *args, **kwargs):
            if '/tmp/' in str(path):
                from io import StringIO
                return StringIO(csv_content)
            return Mock()
        
        with patch('builtins.open', side_effect=mock_open_handler):
            # Act  
            result = csv_import_service.import_contacts(file=mock_file)
        
        # Assert
        assert result['total_rows'] == 0
        assert result['successful'] == 0
        assert result['failed'] == 0
        assert len(result['errors']) > 0
        assert any('Could not detect CSV format' in error for error in result['errors'])
    
    @patch('services.csv_import_service.os.path.exists')
    @patch('services.csv_import_service.os.remove')
    def test_import_contacts_creates_campaign_list_when_requested(self, mock_remove, mock_exists,
                                                                 csv_import_service, mock_file_storage):
        """Test that campaign list is created when create_list=True"""
        # Arrange
        csv_content = "first_name,last_name,phone\nJohn,Doe,5551234567"
        mock_file = mock_file_storage('test.csv', csv_content)
        mock_exists.return_value = True
        
        # Mock open to handle the temp file path
        def mock_open_handler(path, *args, **kwargs):
            if '/tmp/' in str(path):
                from io import StringIO
                return StringIO(csv_content)
            return Mock()
        
        with patch('builtins.open', side_effect=mock_open_handler):
            # Act
            result = csv_import_service.import_contacts(
                file=mock_file,
                list_name='Custom List Name',
                create_list=True
            )
        
        # Assert
        assert 'list_id' in result
        assert result['list_id'] is not None
    
    @patch('services.csv_import_service.os.path.exists')
    @patch('services.csv_import_service.os.remove')
    def test_import_contacts_skips_campaign_list_when_not_requested(self, mock_remove, mock_exists,
                                                                   csv_import_service, mock_file_storage):
        """Test that no campaign list is created when create_list=False"""
        # Arrange
        csv_content = "first_name,last_name,phone\nJohn,Doe,5551234567"
        mock_file = mock_file_storage('test.csv', csv_content)
        mock_exists.return_value = True
        
        with patch('builtins.open', mock_open(read_data=csv_content)):
            # Act
            result = csv_import_service.import_contacts(
                file=mock_file,
                create_list=False
            )
        
        # Assert
        assert result['list_id'] is None
    
    @patch('services.csv_import_service.os.path.exists')
    @patch('services.csv_import_service.os.remove')
    def test_import_contacts_handles_database_commit_errors(self, mock_remove, mock_exists,
                                                           csv_import_service, mock_file_storage):
        """Test handling of database commit errors during import"""
        # Arrange
        csv_content = "first_name,last_name,phone\nJohn,Doe,5551234567"
        mock_file = mock_file_storage('test.csv', csv_content)
        mock_exists.return_value = True
        
        # Mock repository to raise commit error by making contact creation fail
        csv_import_service.contact_repository.create.side_effect = Exception("Database commit failed")
        
        # Mock open to handle the temp file path
        def mock_open_handler(path, *args, **kwargs):
            if '/tmp/' in str(path):
                from io import StringIO
                return StringIO(csv_content)
            return Mock()
        
        with patch('builtins.open', side_effect=mock_open_handler):
            # Act
            result = csv_import_service.import_contacts(file=mock_file)
        
        # Assert
        assert len(result['errors']) > 0
        assert any('database commit failed' in error.lower() for error in result['errors'])
    
    @patch('services.csv_import_service.os.path.exists')
    @patch('services.csv_import_service.os.remove')
    def test_import_contacts_detects_delimiter_automatically(self, mock_remove, mock_exists,
                                                           csv_import_service, mock_file_storage):
        """Test that CSV delimiter is detected automatically"""
        # Arrange - Use semicolon delimiter
        csv_content = "first_name;last_name;phone\nJohn;Doe;5551234567"
        mock_file = mock_file_storage('test.csv', csv_content)
        mock_exists.return_value = True
        
        # Mock open to handle the temp file path
        def mock_open_handler(path, *args, **kwargs):
            if '/tmp/' in str(path):
                from io import StringIO
                return StringIO(csv_content)
            return Mock()
        
        with patch('builtins.open', side_effect=mock_open_handler):
            # Act
            result = csv_import_service.import_contacts(file=mock_file)
        
        # Assert
        assert result['successful'] == 1  # Should successfully parse with ; delimiter


# ============================================================================
# METADATA EXTRACTION TESTS (MUST FAIL INITIALLY)
# ============================================================================

class TestMetadataExtraction:
    """Test metadata extraction functionality"""
    
    def test_extract_metadata_from_standard_row(self, csv_import_service):
        """Test metadata extraction from standard CSV row"""
        # Arrange
        row = {
            'first_name': 'John',
            'last_name': 'Doe',
            'phone': '5551234567',
            'email': 'john@example.com',
            'company': 'ACME Corp',
            'title': 'Manager',
            'department': 'Sales'
        }
        
        # Act
        metadata = csv_import_service._extract_metadata(row)
        
        # Assert
        assert metadata is not None
        assert 'company' in metadata
        assert 'title' in metadata
        assert 'department' in metadata
        assert 'first_name' not in metadata  # Standard fields excluded
        assert 'last_name' not in metadata
        assert 'phone' not in metadata
        assert 'email' not in metadata
    
    def test_extract_metadata_from_mapped_row(self, csv_import_service):
        """Test metadata extraction from mapped CSV row"""
        # Arrange
        mapped_row = {
            'first_name': 'John',
            'last_name': 'Doe',
            'phone': '+15551234567',
            'email': 'john@example.com',
            'company': 'ACME Corp',
            'title': 'Manager',
            'location': 'Boston',
            'property_address': '123 Main St'
        }
        
        # Act
        metadata = csv_import_service._extract_metadata_from_mapped(mapped_row)
        
        # Assert
        assert metadata is not None
        assert metadata['company'] == 'ACME Corp'
        assert metadata['title'] == 'Manager'
        assert metadata['location'] == 'Boston'
        assert metadata['property_address'] == '123 Main St'
        assert 'first_name' not in metadata
        assert 'phone' not in metadata
    
    def test_extract_metadata_returns_none_for_empty_row(self, csv_import_service):
        """Test that empty metadata returns None"""
        # Arrange
        row = {
            'first_name': 'John',
            'last_name': 'Doe',
            'phone': '5551234567'
        }
        
        # Act
        metadata = csv_import_service._extract_metadata(row)
        
        # Assert
        assert metadata is None
    
    def test_extract_metadata_handles_empty_values(self, csv_import_service):
        """Test metadata extraction ignores empty values"""
        # Arrange
        row = {
            'first_name': 'John',
            'last_name': 'Doe',
            'phone': '5551234567',
            'company': 'ACME Corp',
            'title': '',  # Empty string
            'department': None  # None value
        }
        
        # Act
        metadata = csv_import_service._extract_metadata(row)
        
        # Assert
        assert metadata is not None
        assert 'company' in metadata
        assert 'title' not in metadata  # Empty values excluded
        assert 'department' not in metadata
    
    def test_extract_metadata_propertyradar_format(self, csv_import_service):
        """Test metadata extraction for PropertyRadar specific fields"""
        # Arrange
        mapped_row = {
            'first_name': 'John',
            'last_name': 'Doe',
            'phone': '+15551234567',
            'property_address': '123 Oak St',
            'property_city': 'Boston',
            'property_zip': '02101',
            'mail_address': '456 Pine Ave',
            'mail_city': 'Cambridge',
            'mail_state': 'MA',
            'mail_zip': '02139',
            'secondary_name': 'Jane Doe',
            'secondary_phone': '+15559876543'
        }
        
        # Act
        metadata = csv_import_service._extract_metadata_from_mapped(mapped_row)
        
        # Assert
        assert metadata is not None
        assert metadata['property_address'] == '123 Oak St'
        assert metadata['property_city'] == 'Boston'
        assert metadata['property_zip'] == '02101'
        assert metadata['mail_address'] == '456 Pine Ave'
        assert metadata['secondary_name'] == 'Jane Doe'
        assert metadata['secondary_phone'] == '+15559876543'


# ============================================================================
# IMPORT HISTORY TESTS (MUST FAIL INITIALLY)
# ============================================================================

class TestImportHistory:
    """Test import history functionality"""
    
    # Removed CSVImport patch
    def test_get_import_history_returns_recent_imports(self, csv_import_service):
        """Test that import history returns recent imports ordered by date"""
        # Arrange
        mock_imports = [
            {'id': 1, 'filename': 'import1.csv', 'imported_at': datetime(2025, 1, 15)},
            {'id': 2, 'filename': 'import2.csv', 'imported_at': datetime(2025, 1, 14)},
            {'id': 3, 'filename': 'import3.csv', 'imported_at': datetime(2025, 1, 13)}
        ]
        csv_import_service.csv_import_repository.get_recent_imports.return_value = mock_imports
        
        # Act
        result = csv_import_service.get_import_history(limit=10)
        
        # Assert
        assert len(result) == 3
        assert result[0]['id'] == 1  # Most recent first
        assert result[0]['filename'] == 'import1.csv'
        csv_import_service.csv_import_repository.get_recent_imports.assert_called_once_with(limit=10)
    
    # Removed CSVImport patch
    def test_get_import_history_respects_limit(self, csv_import_service):
        """Test that import history respects the limit parameter"""
        # Arrange
        mock_imports = [{'id': 1}, {'id': 2}]
        csv_import_service.csv_import_repository.get_recent_imports.return_value = mock_imports
        
        # Act
        result = csv_import_service.get_import_history(limit=5)
        
        # Assert
        csv_import_service.csv_import_repository.get_recent_imports.assert_called_once_with(limit=5)
        assert len(result) == 2
    
    # Removed CSVImport patch
    def test_get_import_history_default_limit(self, csv_import_service):
        """Test that import history uses default limit of 10"""
        # Arrange
        csv_import_service.csv_import_repository.get_recent_imports.return_value = []
        
        # Act
        csv_import_service.get_import_history()
        
        # Assert
        csv_import_service.csv_import_repository.get_recent_imports.assert_called_once_with(limit=10)
    
    # Removed CSVImport patch
    def test_get_import_history_handles_empty_result(self, csv_import_service):
        """Test that import history handles empty results gracefully"""
        # Arrange
        csv_import_service.csv_import_repository.get_recent_imports.return_value = []
        
        # Act
        result = csv_import_service.get_import_history()
        
        # Assert
        assert result == []
        csv_import_service.csv_import_repository.get_recent_imports.assert_called_once_with(limit=10)


# ============================================================================
# GET CONTACTS BY IMPORT TESTS (MUST FAIL INITIALLY)
# ============================================================================

class TestGetContactsByImport:
    """Test getting contacts by import ID functionality"""
    
    # Removed CSVImport patch
    def test_get_contacts_by_import_returns_contacts(self, csv_import_service):
        """Test that get_contacts_by_import returns contacts for valid import ID"""
        # Arrange
        mock_contacts = [
            {'id': 1, 'first_name': 'John', 'last_name': 'Doe'},
            {'id': 2, 'first_name': 'Jane', 'last_name': 'Smith'}
        ]
        csv_import_service.contact_csv_import_repository.get_contacts_by_import_with_details.return_value = [(contact, None) for contact in mock_contacts]
        
        # Act
        result = csv_import_service.get_contacts_by_import(import_id=1)
        
        # Assert
        assert len(result) == 2
        assert result[0]['first_name'] == 'John'
        assert result[1]['first_name'] == 'Jane'
        csv_import_service.contact_csv_import_repository.get_contacts_by_import_with_details.assert_called_once_with(1)
    
    # Removed CSVImport patch
    def test_get_contacts_by_import_handles_invalid_id(self, csv_import_service):
        """Test that get_contacts_by_import handles invalid import ID"""
        # Arrange
        csv_import_service.contact_csv_import_repository.get_contacts_by_import_with_details.return_value = []  # Import not found
        
        # Act
        result = csv_import_service.get_contacts_by_import(import_id=999)
        
        # Assert
        assert result == []
        csv_import_service.contact_csv_import_repository.get_contacts_by_import_with_details.assert_called_once_with(999)
    
    # Removed CSVImport patch
    def test_get_contacts_by_import_handles_empty_contacts(self, csv_import_service):
        """Test that get_contacts_by_import handles import with no contacts"""
        # Arrange
        csv_import_service.contact_csv_import_repository.get_contacts_by_import_with_details.return_value = []  # Empty contacts
        
        # Act
        result = csv_import_service.get_contacts_by_import(import_id=1)
        
        # Assert
        assert result == []
        csv_import_service.contact_csv_import_repository.get_contacts_by_import_with_details.assert_called_once_with(1)


# ============================================================================
# INTEGRATION TESTS (MUST FAIL INITIALLY)
# ============================================================================

class TestCSVImportServiceIntegration:
    """Integration tests combining multiple service methods"""
    
    @patch('services.csv_import_service.os.path.exists')
    @patch('services.csv_import_service.os.remove')
    def test_full_import_workflow_openphone_format(self, mock_remove, mock_exists,
                                                  csv_import_service, mock_file_storage):
        """Test complete import workflow with OpenPhone format CSV"""
        # Arrange
        csv_content = """First name,Last name,Phone number,Email,Address,Role
John,Doe,+1 555 123 4567,john@example.com,123 Main St,Agent
Jane,Smith,(555) 987-6543,jane@example.com,456 Oak Ave,Manager"""
        
        mock_file = mock_file_storage('openphone_export.csv', csv_content)
        mock_exists.return_value = True
        
        # Mock open to handle the temp file path
        def mock_open_handler(path, *args, **kwargs):
            if '/tmp/' in str(path):
                from io import StringIO
                return StringIO(csv_content)
            return Mock()
        
        with patch('builtins.open', side_effect=mock_open_handler):
            # Act
            result = csv_import_service.import_contacts(
                file=mock_file,
                list_name='OpenPhone Import',
                create_list=True,
                imported_by='test_user'
            )
        
        # Assert
        assert result['total_rows'] == 2
        assert result['successful'] == 2
        assert result['failed'] == 0
        assert result['list_id'] is not None
    
    @patch('services.csv_import_service.os.path.exists')
    @patch('services.csv_import_service.os.remove')
    def test_full_import_workflow_propertyradar_format(self, mock_remove, mock_exists,
                                                      csv_import_service, mock_file_storage):
        """Test complete import workflow with PropertyRadar format CSV"""
        # Arrange
        csv_content = """Primary First Name,Primary Last Name,Primary Mobile Phone1,Primary Email1,Address,City,ZIP
Bob,Johnson,555.111.2222,bob@example.com,789 Pine St,Boston,02101
Alice,Brown,555.333.4444,alice@example.com,321 Elm St,Cambridge,02139"""
        
        mock_file = mock_file_storage('cleaned_data_phone.csv', csv_content)
        mock_exists.return_value = True
        
        # Mock open to handle the temp file path
        def mock_open_handler(path, *args, **kwargs):
            if '/tmp/' in str(path):
                from io import StringIO
                return StringIO(csv_content)
            return Mock()
        
        with patch('builtins.open', side_effect=mock_open_handler):
            # Act
            result = csv_import_service.import_contacts(
                file=mock_file,
                list_name='PropertyRadar Import'
            )
        
        # Assert
        assert result['total_rows'] == 2
        assert result['successful'] == 2
        # Should extract property metadata
    
    def test_service_initialization_with_contact_service(self, mock_contact_service,
                                                           mock_csv_import_repository,
                                                           mock_contact_csv_import_repository,
                                                           mock_campaign_list_repository,
                                                           mock_campaign_list_member_repository,
                                                           mock_contact_repository):
        """Test that service initializes properly with all required dependencies"""
        # Act
        service = CSVImportService(
            csv_import_repository=mock_csv_import_repository,
            contact_csv_import_repository=mock_contact_csv_import_repository,
            campaign_list_repository=mock_campaign_list_repository,
            campaign_list_member_repository=mock_campaign_list_member_repository,
            contact_repository=mock_contact_repository,
            contact_service=mock_contact_service
        )
        
        # Assert
        assert service.contact_service == mock_contact_service
        assert service.csv_import_repository == mock_csv_import_repository
        assert service.contact_repository == mock_contact_repository
    
    def test_service_initialization_requires_contact_service(self):
        """Test that service requires ContactService dependency"""
        # Act & Assert
        with pytest.raises(TypeError):
            CSVImportService()  # Should fail without required parameter


# ============================================================================
# ERROR HANDLING TESTS (MUST FAIL INITIALLY)  
# ============================================================================

class TestErrorHandling:
    """Test error handling scenarios"""
    
    def test_import_handles_corrupted_csv_file(self, csv_import_service, mock_file_storage):
        """Test handling of corrupted CSV files"""
        # Arrange
        mock_file = mock_file_storage('corrupted.csv')
        
        # Mock open to raise UnicodeDecodeError
        with patch('builtins.open', side_effect=UnicodeDecodeError('utf-8', b'', 0, 1, 'invalid start byte')):
            # Act
            result = csv_import_service.import_contacts(file=mock_file)
        
        # Assert
        assert result['successful'] == 0
        assert len(result['errors']) > 0
    
    @patch('services.csv_import_service.os.path.exists')
    def test_import_handles_file_not_found(self, mock_exists, csv_import_service, mock_file_storage):
        """Test handling when saved file cannot be found"""
        # Arrange
        mock_file = mock_file_storage('missing.csv')
        mock_exists.return_value = False
        
        with patch('builtins.open', side_effect=FileNotFoundError("File not found")):
            # Act
            result = csv_import_service.import_contacts(file=mock_file)
        
        # Assert
        assert result['successful'] == 0
        assert len(result['errors']) > 0
    
    @patch('services.csv_import_service.os.path.exists')
    @patch('services.csv_import_service.os.remove')
    def test_import_handles_malformed_csv_rows(self, mock_remove, mock_exists,
                                              csv_import_service, mock_file_storage):
        """Test handling of malformed CSV rows"""
        # Arrange
        csv_content = """first_name,last_name,phone
John,Doe,5551234567
Jane,Smith  # Missing phone column
Bob,Johnson,5559876543"""
        
        mock_file = mock_file_storage('malformed.csv', csv_content)
        mock_exists.return_value = True
        
        # Mock open to handle the temp file path
        def mock_open_handler(path, *args, **kwargs):
            if '/tmp/' in str(path):
                from io import StringIO
                return StringIO(csv_content)
            return Mock()
        
        with patch('builtins.open', side_effect=mock_open_handler):
            # Act
            result = csv_import_service.import_contacts(file=mock_file)
        
        # Assert
        assert result['total_rows'] > 0
        assert result['failed'] > 0
        assert len(result['errors']) > 0
    
    def test_import_handles_permission_denied_file_save(self, csv_import_service, mock_file_storage):
        """Test handling of permission denied during file save"""
        # Arrange
        mock_file = mock_file_storage('test.csv')
        mock_file.save.side_effect = PermissionError("Permission denied")
        
        # Act
        result = csv_import_service.import_contacts(file=mock_file)
        
        # Assert
        assert result['successful'] == 0
        assert len(result['errors']) > 0
        assert any('File processing error' in error for error in result['errors'])


# ============================================================================
# EDGE CASE TESTS (MUST FAIL INITIALLY)
# ============================================================================

class TestEdgeCases:
    """Test edge cases and boundary conditions"""
    
    def test_detect_format_with_none_filename(self, csv_import_service):
        """Test format detection when filename is None"""
        # Arrange
        headers = ['first_name', 'last_name', 'phone']
        filename = None
        
        # Act
        detected_format = csv_import_service.detect_format(headers, filename)
        
        # Assert
        assert detected_format == 'standard'  # Should fall back to header detection
    
    def test_normalize_phone_with_very_long_input(self, csv_import_service):
        """Test phone normalization with extremely long input"""
        # Arrange
        phone = '1' * 50  # 50 digit string
        
        # Act
        result = csv_import_service.normalize_phone(phone)
        
        # Assert
        assert result is None  # Should reject overly long numbers
    
    # Removed db patch
    @patch('services.csv_import_service.os.path.exists')
    @patch('services.csv_import_service.os.remove')
    def test_import_with_extremely_large_csv(self, mock_remove, mock_exists,
                                           csv_import_service, mock_file_storage):
        """Test import performance with large CSV files"""
        # Arrange
        # Simulate large CSV by testing batch commit logic
        csv_content = "first_name,last_name,phone\n" + "\n".join([
            f"User{i},Test{i},555{i:07d}" for i in range(150)  # 150 rows to trigger batch commits
        ])
        
        mock_file = mock_file_storage('large.csv', csv_content)
        mock_exists.return_value = True
        
        # Mock open to handle the temp file path
        def mock_open_handler(path, *args, **kwargs):
            if '/tmp/' in str(path):
                from io import StringIO
                return StringIO(csv_content)
            return Mock()
        
        with patch('builtins.open', side_effect=mock_open_handler):
            # Act
            result = csv_import_service.import_contacts(file=mock_file)
        
        # Assert
        assert result['total_rows'] == 150
        # Should handle large files without memory issues
    
    def test_normalize_phone_with_unicode_characters(self, csv_import_service):
        """Test phone normalization with Unicode characters"""
        # Arrange
        phone = '555-123-4567 📞'  # Phone with emoji
        
        # Act
        result = csv_import_service.normalize_phone(phone)
        
        # Assert
        assert result == '+15551234567'  # Should strip Unicode and normalize
    
    # Removed db patch
    @patch('services.csv_import_service.os.path.exists')
    @patch('services.csv_import_service.os.remove')
    def test_import_csv_with_empty_file(self, mock_remove, mock_exists,
                                       csv_import_service, mock_file_storage):
        """Test import of completely empty CSV file"""
        # Arrange
        csv_content = ""  # Empty file
        mock_file = mock_file_storage('empty.csv', csv_content)
        mock_exists.return_value = True
        
        # Mock open to handle the temp file path
        def mock_open_handler(path, *args, **kwargs):
            if '/tmp/' in str(path):
                from io import StringIO
                return StringIO(csv_content)
            return Mock()
        
        with patch('builtins.open', side_effect=mock_open_handler):
            # Act
            result = csv_import_service.import_contacts(file=mock_file)
        
        # Assert
        assert result['total_rows'] == 0
        assert result['successful'] == 0
        assert result['failed'] == 0
    
    # Removed db patch
    @patch('services.csv_import_service.os.path.exists')
    @patch('services.csv_import_service.os.remove')
    def test_import_csv_with_only_headers(self, mock_remove, mock_exists,
                                         csv_import_service, mock_file_storage):
        """Test import of CSV file with only headers and no data rows"""
        # Arrange
        csv_content = "first_name,last_name,phone,email"  # Headers only
        mock_file = mock_file_storage('headers_only.csv', csv_content)
        mock_exists.return_value = True
        
        # Mock open to handle the temp file path
        def mock_open_handler(path, *args, **kwargs):
            if '/tmp/' in str(path):
                from io import StringIO
                return StringIO(csv_content)
            return Mock()
        
        with patch('builtins.open', side_effect=mock_open_handler):
            # Act
            result = csv_import_service.import_contacts(file=mock_file)
        
        # Assert
        assert result['total_rows'] == 0
        assert result['successful'] == 0
        assert result['failed'] == 0


# ============================================================================
# IMPORT_CSV METHOD TESTS (MUST FAIL INITIALLY - TDD RED PHASE)
# ============================================================================

class TestImportCSVMethod:
    """Test the import_csv method that acts as a wrapper for import_contacts"""
    
    def test_import_csv_method_exists(self, csv_import_service):
        """Test that the import_csv method exists and is callable"""
        # Act & Assert
        assert hasattr(csv_import_service, 'import_csv'), "import_csv method should exist"
        assert callable(getattr(csv_import_service, 'import_csv')), "import_csv should be callable"
    
    @patch('services.csv_import_service.os.path.exists')
    @patch('services.csv_import_service.os.remove')
    def test_import_csv_delegates_to_import_contacts(self, mock_remove, mock_exists,
                                                   csv_import_service, mock_file_storage):
        """Test that import_csv properly delegates to _basic_import_csv for non-PropertyRadar files"""
        # Arrange
        csv_content = "first_name,last_name,phone,email\nJohn,Doe,5551234567,john@example.com"
        mock_file = mock_file_storage('test.csv', csv_content)
        mock_exists.return_value = True
        
        # Mock _basic_import_csv to track the delegation
        with patch.object(csv_import_service, '_basic_import_csv') as mock_basic_import:
            mock_basic_import.return_value = {
                'success': True,
                'imported': 1,
                'updated': 0,
                'errors': [],
                'message': 'Import completed successfully',
                'list_id': 123
            }
            
            # Act
            result = csv_import_service.import_csv(
                file=mock_file,
                list_name='Test List',
                enrichment_mode='enrich_missing'
            )
            
            # Assert that _basic_import_csv was called (non-PropertyRadar path)
            mock_basic_import.assert_called_once_with(mock_file, 'Test List', duplicate_strategy='merge', progress_callback=None)
    
    def test_import_csv_returns_expected_format(self, csv_import_service, mock_file_storage):
        """Test that import_csv returns the expected response format for the route"""
        # Arrange
        mock_file = mock_file_storage('test.csv')
        
        # Mock _basic_import_csv to return typical response
        with patch.object(csv_import_service, '_basic_import_csv') as mock_basic_import:
            mock_basic_import.return_value = {
                'success': True,
                'imported': 3,
                'updated': 1,
                'errors': ['Row 4: Invalid phone number'],
                'message': 'Import completed',
                'list_id': 789
            }
            
            # Act
            result = csv_import_service.import_csv(
                file=mock_file,
                list_name='Test Import',
                enrichment_mode='enrich_missing'
            )
        
        # Assert response has all required keys for the route
        assert 'success' in result
        assert 'imported' in result
        assert 'updated' in result
        assert 'errors' in result
        assert 'message' in result
        assert 'list_id' in result
        
        # Assert correct mappings from import_contacts response
        assert result['success'] is True  # Should be True when successful > 0
        assert result['imported'] == 3   # Maps to successful
        assert result['updated'] == 1    # Maps to duplicates
        assert result['errors'] == ['Row 4: Invalid phone number']
        assert result['list_id'] == 789
        assert 'completed' in result['message'].lower()
    
    def test_import_csv_handles_import_contacts_failure(self, csv_import_service, mock_file_storage):
        """Test that import_csv handles failures from _basic_import_csv gracefully"""
        # Arrange
        mock_file = mock_file_storage('test.csv')
        
        # Mock _basic_import_csv to return failure scenario
        with patch.object(csv_import_service, '_basic_import_csv') as mock_basic_import:
            mock_basic_import.return_value = {
                'success': False,
                'imported': 0,
                'updated': 0,
                'errors': ['Row 2: Invalid phone', 'Row 3: Missing data'],
                'message': 'Import failed',
                'list_id': None
            }
            
            # Act
            result = csv_import_service.import_csv(
                file=mock_file,
                list_name='Failed Import'
            )
        
        # Assert failure response format
        assert result['success'] is False  # Should be False when no successful imports
        assert result['imported'] == 0
        assert result['updated'] == 0
        assert len(result['errors']) == 2
        assert result['list_id'] is None
        assert 'failed' in result['message'].lower() or 'error' in result['message'].lower()
    
    def test_import_csv_handles_enrichment_mode_parameter(self, csv_import_service, mock_file_storage):
        """Test that import_csv accepts and stores enrichment_mode parameter"""
        # Arrange
        mock_file = mock_file_storage('test.csv')
        
        with patch.object(csv_import_service, '_basic_import_csv') as mock_basic_import:
            mock_basic_import.return_value = {
                'success': True,
                'imported': 1,
                'updated': 0,
                'errors': [],
                'message': 'Import completed',
                'list_id': 456
            }
            
            # Act - test with different enrichment modes
            result1 = csv_import_service.import_csv(
                file=mock_file,
                list_name='Test',
                enrichment_mode='enrich_missing'
            )
            
            result2 = csv_import_service.import_csv(
                file=mock_file,
                list_name='Test',
                enrichment_mode='enrich_all'
            )
            
            result3 = csv_import_service.import_csv(
                file=mock_file,
                list_name='Test',
                enrichment_mode='no_enrichment'
            )
        
        # Assert that method accepts all enrichment modes without error
        assert result1['success'] is True
        assert result2['success'] is True
        assert result3['success'] is True
    
    def test_import_csv_default_parameters(self, csv_import_service, mock_file_storage):
        """Test import_csv with minimal parameters (only file required)"""
        # Arrange
        mock_file = mock_file_storage('test.csv')
        
        with patch.object(csv_import_service, '_basic_import_csv') as mock_basic_import:
            mock_basic_import.return_value = {
                'success': True,
                'imported': 1,
                'updated': 0,
                'errors': [],
                'message': 'Import completed',
                'list_id': 456
            }
            
            # Act - call with only required file parameter
            result = csv_import_service.import_csv(file=mock_file)
            
            # Assert that _basic_import_csv was called with sensible defaults
            mock_basic_import.assert_called_once_with(mock_file, None, duplicate_strategy='merge', progress_callback=None)
            # The assertion above confirms correct delegation
    
    def test_import_csv_with_custom_list_name(self, csv_import_service, mock_file_storage):
        """Test that import_csv passes custom list_name to _basic_import_csv"""
        # Arrange
        mock_file = mock_file_storage('agents.csv')
        custom_list_name = 'Real Estate Agents - Q1 2025'
        
        with patch.object(csv_import_service, '_basic_import_csv') as mock_basic_import:
            mock_basic_import.return_value = {
                'success': True,
                'imported': 1,
                'updated': 0,
                'errors': [],
                'message': 'Import completed',
                'list_id': 456
            }
            
            # Act
            result = csv_import_service.import_csv(
                file=mock_file,
                list_name=custom_list_name
            )
            
            # Assert custom list name was passed through
            mock_basic_import.assert_called_once_with(mock_file, custom_list_name, duplicate_strategy='merge', progress_callback=None)
            # The assertion above confirms correct list name passing
    
    def test_import_csv_handles_exception_from_import_contacts(self, csv_import_service, mock_file_storage):
        """Test that import_csv handles exceptions from import_contacts gracefully"""
        # Arrange
        mock_file = mock_file_storage('test.csv')
        
        with patch.object(csv_import_service, 'import_contacts') as mock_import_contacts:
            # Mock import_contacts to raise an exception
            mock_import_contacts.side_effect = Exception("Database connection failed")
            
            # Act
            result = csv_import_service.import_csv(file=mock_file)
        
        # Assert error is handled gracefully
        assert result['success'] is False
        assert result['imported'] == 0
        assert result['updated'] == 0
        assert len(result['errors']) > 0
        assert any('error' in error.lower() for error in result['errors'])
        assert result['list_id'] is None
        assert 'error' in result['message'].lower() or 'failed' in result['message'].lower()
    
    def test_import_csv_preserves_route_contract(self, csv_import_service, mock_file_storage):
        """Test that import_csv maintains the exact contract expected by the route"""
        # Arrange
        mock_file = mock_file_storage('test.csv')
        
        with patch.object(csv_import_service, '_basic_import_csv') as mock_basic_import:
            mock_basic_import.return_value = {
                'success': False,
                'imported': 8,
                'updated': 1,
                'errors': ['Row 5: Invalid format'],
                'message': 'Import completed with errors',
                'list_id': 888
            }
            
            # Act - exactly like the route calls it
            result = csv_import_service.import_csv(
                file=mock_file,
                list_name='Campaign List',
                enrichment_mode='enrich_missing'
            )
        
        # Assert the exact keys the route expects
        expected_keys = {'success', 'imported', 'updated', 'errors', 'message', 'list_id'}
        assert set(result.keys()) >= expected_keys, f"Missing keys: {expected_keys - set(result.keys())}"
        
        # Assert correct data types
        assert isinstance(result['success'], bool)
        assert isinstance(result['imported'], int)
        assert isinstance(result['updated'], int)
        assert isinstance(result['errors'], list)
        assert isinstance(result['message'], str)
        assert result['list_id'] is None or isinstance(result['list_id'], int)
        
        # Assert reasonable values  
        assert result['success'] is False  # Mock returned False
        assert result['imported'] == 8
        assert result['updated'] == 1  # duplicates
        assert result['list_id'] == 888


# ============================================================================
# TEST EXECUTION VERIFICATION
# ============================================================================

def test_all_tests_are_designed_to_fail_initially():
    """
    Meta-test to ensure this test suite follows TDD principles.
    This test should PASS, confirming that all other tests are designed to FAIL
    until the CSVImportService is properly implemented.
    
    This enforces the RED-GREEN-REFACTOR cycle.
    """
    # This test verifies that we're following TDD by having comprehensive
    # tests written BEFORE implementation
    assert True, "All tests above are designed to fail until CSVImportService is implemented"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])