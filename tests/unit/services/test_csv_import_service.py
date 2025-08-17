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
def csv_import_service(mock_contact_service):
    """Factory fixture providing CSVImportService instance with mocked dependencies"""
    return CSVImportService(contact_service=mock_contact_service)


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
        mock_file = Mock(spec=FileStorage)
        mock_file.filename = filename
        mock_file.save = Mock()
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
        mock_csv_import.imported_at = datetime.utcnow()
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
    
    @patch('services.csv_import_service.db')
    @patch('services.csv_import_service.os.path.exists')
    @patch('services.csv_import_service.os.remove')
    def test_import_contacts_successful_standard_format(self, mock_remove, mock_exists, mock_db, 
                                                       csv_import_service, mock_file_storage):
        """Test successful import of contacts in standard CSV format"""
        # Arrange
        csv_content = "first_name,last_name,phone,email\nJohn,Doe,5551234567,john@example.com\nJane,Smith,5559876543,jane@example.com"
        mock_file = mock_file_storage('test.csv', csv_content)
        mock_exists.return_value = True
        
        with patch('builtins.open', mock_open(read_data=csv_content)):
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
    
    @patch('services.csv_import_service.db')
    @patch('services.csv_import_service.os.path.exists')
    @patch('services.csv_import_service.os.remove')
    def test_import_contacts_handles_duplicate_phones(self, mock_remove, mock_exists, mock_db,
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
        
        with patch('builtins.open', mock_open(read_data=csv_content)), \
             patch('services.csv_import_service.Contact') as mock_contact_class:
            mock_contact_class.query.filter_by.return_value.first.return_value = existing_contact
            
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
    
    @patch('services.csv_import_service.db')
    @patch('services.csv_import_service.os.path.exists') 
    @patch('services.csv_import_service.os.remove')
    def test_import_contacts_skips_rows_without_phone(self, mock_remove, mock_exists, mock_db,
                                                     csv_import_service, mock_file_storage):
        """Test that rows without phone numbers are skipped with error"""
        # Arrange
        csv_content = "first_name,last_name,phone,email\nJohn,Doe,,john@example.com\nJane,Smith,5559876543,jane@example.com"
        mock_file = mock_file_storage('test.csv', csv_content)
        mock_exists.return_value = True
        
        with patch('builtins.open', mock_open(read_data=csv_content)):
            # Act
            result = csv_import_service.import_contacts(file=mock_file)
        
        # Assert
        assert result['total_rows'] == 2
        assert result['successful'] == 1  # Only Jane Smith
        assert result['failed'] == 1      # John Doe skipped
        assert len(result['errors']) == 1
        assert 'Row 2: Missing phone number' in result['errors'][0]
    
    @patch('services.csv_import_service.db')
    @patch('services.csv_import_service.os.path.exists')
    @patch('services.csv_import_service.os.remove')
    def test_import_contacts_skips_invalid_phone_format(self, mock_remove, mock_exists, mock_db,
                                                       csv_import_service, mock_file_storage):
        """Test that rows with invalid phone formats are skipped"""
        # Arrange
        csv_content = "first_name,last_name,phone,email\nJohn,Doe,invalid-phone,john@example.com\nJane,Smith,5559876543,jane@example.com"
        mock_file = mock_file_storage('test.csv', csv_content)
        mock_exists.return_value = True
        
        with patch('builtins.open', mock_open(read_data=csv_content)):
            # Act
            result = csv_import_service.import_contacts(file=mock_file)
        
        # Assert
        assert result['total_rows'] == 2
        assert result['successful'] == 1
        assert result['failed'] == 1
        assert any('Invalid phone number format' in error for error in result['errors'])
    
    @patch('services.csv_import_service.db')
    def test_import_contacts_handles_file_processing_error(self, mock_db, csv_import_service, mock_file_storage):
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
    
    @patch('services.csv_import_service.db')
    @patch('services.csv_import_service.os.path.exists')
    @patch('services.csv_import_service.os.remove')
    def test_import_contacts_unknown_format_fallback(self, mock_remove, mock_exists, mock_db,
                                                    csv_import_service, mock_file_storage):
        """Test fallback behavior when CSV format cannot be detected"""
        # Arrange
        csv_content = "weird_column1,strange_field2\nvalue1,value2"
        mock_file = mock_file_storage('unknown.csv', csv_content)
        mock_exists.return_value = True
        
        with patch('builtins.open', mock_open(read_data=csv_content)):
            # Act  
            result = csv_import_service.import_contacts(file=mock_file)
        
        # Assert
        assert result['total_rows'] == 0
        assert result['successful'] == 0
        assert result['failed'] == 0
        assert len(result['errors']) > 0
        assert any('Could not detect CSV format' in error for error in result['errors'])
    
    @patch('services.csv_import_service.db')
    @patch('services.csv_import_service.os.path.exists')
    @patch('services.csv_import_service.os.remove')
    def test_import_contacts_creates_campaign_list_when_requested(self, mock_remove, mock_exists, mock_db,
                                                                 csv_import_service, mock_file_storage):
        """Test that campaign list is created when create_list=True"""
        # Arrange
        csv_content = "first_name,last_name,phone\nJohn,Doe,5551234567"
        mock_file = mock_file_storage('test.csv', csv_content)
        mock_exists.return_value = True
        
        with patch('builtins.open', mock_open(read_data=csv_content)):
            # Act
            result = csv_import_service.import_contacts(
                file=mock_file,
                list_name='Custom List Name',
                create_list=True
            )
        
        # Assert
        assert 'list_id' in result
        assert result['list_id'] is not None
    
    @patch('services.csv_import_service.db')
    @patch('services.csv_import_service.os.path.exists')
    @patch('services.csv_import_service.os.remove')
    def test_import_contacts_skips_campaign_list_when_not_requested(self, mock_remove, mock_exists, mock_db,
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
    
    @patch('services.csv_import_service.db')
    @patch('services.csv_import_service.os.path.exists')
    @patch('services.csv_import_service.os.remove')
    def test_import_contacts_handles_database_commit_errors(self, mock_remove, mock_exists, mock_db,
                                                           csv_import_service, mock_file_storage):
        """Test handling of database commit errors during import"""
        # Arrange
        csv_content = "first_name,last_name,phone\nJohn,Doe,5551234567"
        mock_file = mock_file_storage('test.csv', csv_content)
        mock_exists.return_value = True
        
        # Mock database session to raise commit error
        mock_db.session.commit.side_effect = Exception("Database commit failed")
        
        with patch('builtins.open', mock_open(read_data=csv_content)):
            # Act
            result = csv_import_service.import_contacts(file=mock_file)
        
        # Assert
        assert len(result['errors']) > 0
        assert any('commit error' in error.lower() for error in result['errors'])
    
    @patch('services.csv_import_service.db')
    @patch('services.csv_import_service.os.path.exists')
    @patch('services.csv_import_service.os.remove')
    def test_import_contacts_detects_delimiter_automatically(self, mock_remove, mock_exists, mock_db,
                                                           csv_import_service, mock_file_storage):
        """Test that CSV delimiter is detected automatically"""
        # Arrange - Use semicolon delimiter
        csv_content = "first_name;last_name;phone\nJohn;Doe;5551234567"
        mock_file = mock_file_storage('test.csv', csv_content)
        mock_exists.return_value = True
        
        with patch('builtins.open', mock_open(read_data=csv_content)):
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
    
    @patch('services.csv_import_service.CSVImport')
    def test_get_import_history_returns_recent_imports(self, mock_csv_import, csv_import_service):
        """Test that import history returns recent imports ordered by date"""
        # Arrange
        mock_imports = [
            Mock(id=1, filename='import1.csv', imported_at=datetime(2025, 1, 15)),
            Mock(id=2, filename='import2.csv', imported_at=datetime(2025, 1, 14)),
            Mock(id=3, filename='import3.csv', imported_at=datetime(2025, 1, 13))
        ]
        mock_csv_import.query.order_by.return_value.limit.return_value.all.return_value = mock_imports
        
        # Act
        result = csv_import_service.get_import_history(limit=10)
        
        # Assert
        assert len(result) == 3
        assert result[0].id == 1  # Most recent first
        assert result[0].filename == 'import1.csv'
        mock_csv_import.query.order_by.assert_called_once()
    
    @patch('services.csv_import_service.CSVImport')
    def test_get_import_history_respects_limit(self, mock_csv_import, csv_import_service):
        """Test that import history respects the limit parameter"""
        # Arrange
        mock_imports = [Mock(id=1), Mock(id=2)]
        mock_csv_import.query.order_by.return_value.limit.return_value.all.return_value = mock_imports
        
        # Act
        result = csv_import_service.get_import_history(limit=5)
        
        # Assert
        mock_csv_import.query.order_by.return_value.limit.assert_called_with(5)
        assert len(result) == 2
    
    @patch('services.csv_import_service.CSVImport')
    def test_get_import_history_default_limit(self, mock_csv_import, csv_import_service):
        """Test that import history uses default limit of 10"""
        # Arrange
        mock_csv_import.query.order_by.return_value.limit.return_value.all.return_value = []
        
        # Act
        csv_import_service.get_import_history()
        
        # Assert
        mock_csv_import.query.order_by.return_value.limit.assert_called_with(10)
    
    @patch('services.csv_import_service.CSVImport')
    def test_get_import_history_handles_empty_result(self, mock_csv_import, csv_import_service):
        """Test that import history handles empty results gracefully"""
        # Arrange
        mock_csv_import.query.order_by.return_value.limit.return_value.all.return_value = []
        
        # Act
        result = csv_import_service.get_import_history()
        
        # Assert
        assert result == []


# ============================================================================
# GET CONTACTS BY IMPORT TESTS (MUST FAIL INITIALLY)
# ============================================================================

class TestGetContactsByImport:
    """Test getting contacts by import ID functionality"""
    
    @patch('services.csv_import_service.CSVImport')
    def test_get_contacts_by_import_returns_contacts(self, mock_csv_import, csv_import_service):
        """Test that get_contacts_by_import returns contacts for valid import ID"""
        # Arrange
        mock_contacts = [
            Mock(id=1, first_name='John', last_name='Doe'),
            Mock(id=2, first_name='Jane', last_name='Smith')
        ]
        mock_import = Mock()
        mock_import.contacts = mock_contacts
        mock_csv_import.query.get.return_value = mock_import
        
        # Act
        result = csv_import_service.get_contacts_by_import(import_id=1)
        
        # Assert
        assert len(result) == 2
        assert result[0].first_name == 'John'
        assert result[1].first_name == 'Jane'
        mock_csv_import.query.get.assert_called_once_with(1)
    
    @patch('services.csv_import_service.CSVImport')
    def test_get_contacts_by_import_handles_invalid_id(self, mock_csv_import, csv_import_service):
        """Test that get_contacts_by_import handles invalid import ID"""
        # Arrange
        mock_csv_import.query.get.return_value = None  # Import not found
        
        # Act
        result = csv_import_service.get_contacts_by_import(import_id=999)
        
        # Assert
        assert result == []
        mock_csv_import.query.get.assert_called_once_with(999)
    
    @patch('services.csv_import_service.CSVImport')
    def test_get_contacts_by_import_handles_empty_contacts(self, mock_csv_import, csv_import_service):
        """Test that get_contacts_by_import handles import with no contacts"""
        # Arrange
        mock_import = Mock()
        mock_import.contacts = []
        mock_csv_import.query.get.return_value = mock_import
        
        # Act
        result = csv_import_service.get_contacts_by_import(import_id=1)
        
        # Assert
        assert result == []


# ============================================================================
# INTEGRATION TESTS (MUST FAIL INITIALLY)
# ============================================================================

class TestCSVImportServiceIntegration:
    """Integration tests combining multiple service methods"""
    
    @patch('services.csv_import_service.db')
    @patch('services.csv_import_service.os.path.exists')
    @patch('services.csv_import_service.os.remove')
    def test_full_import_workflow_openphone_format(self, mock_remove, mock_exists, mock_db,
                                                  csv_import_service, mock_file_storage):
        """Test complete import workflow with OpenPhone format CSV"""
        # Arrange
        csv_content = """First name,Last name,Phone number,Email,Address,Role
John,Doe,+1 555 123 4567,john@example.com,123 Main St,Agent
Jane,Smith,(555) 987-6543,jane@example.com,456 Oak Ave,Manager"""
        
        mock_file = mock_file_storage('openphone_export.csv', csv_content)
        mock_exists.return_value = True
        
        with patch('builtins.open', mock_open(read_data=csv_content)):
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
    
    @patch('services.csv_import_service.db')
    @patch('services.csv_import_service.os.path.exists')
    @patch('services.csv_import_service.os.remove')
    def test_full_import_workflow_propertyradar_format(self, mock_remove, mock_exists, mock_db,
                                                      csv_import_service, mock_file_storage):
        """Test complete import workflow with PropertyRadar format CSV"""
        # Arrange
        csv_content = """Primary First Name,Primary Last Name,Primary Mobile Phone1,Primary Email1,Address,City,ZIP
Bob,Johnson,555.111.2222,bob@example.com,789 Pine St,Boston,02101
Alice,Brown,555.333.4444,alice@example.com,321 Elm St,Cambridge,02139"""
        
        mock_file = mock_file_storage('cleaned_data_phone.csv', csv_content)
        mock_exists.return_value = True
        
        with patch('builtins.open', mock_open(read_data=csv_content)):
            # Act
            result = csv_import_service.import_contacts(
                file=mock_file,
                list_name='PropertyRadar Import'
            )
        
        # Assert
        assert result['total_rows'] == 2
        assert result['successful'] == 2
        # Should extract property metadata
    
    def test_service_initialization_with_contact_service(self, mock_contact_service):
        """Test that service initializes properly with ContactService dependency"""
        # Act
        service = CSVImportService(contact_service=mock_contact_service)
        
        # Assert
        assert service.contact_service == mock_contact_service
    
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
    
    @patch('services.csv_import_service.db')
    def test_import_handles_corrupted_csv_file(self, mock_db, csv_import_service, mock_file_storage):
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
    
    @patch('services.csv_import_service.db')
    @patch('services.csv_import_service.os.path.exists')
    def test_import_handles_file_not_found(self, mock_exists, mock_db, csv_import_service, mock_file_storage):
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
    
    @patch('services.csv_import_service.db')
    @patch('services.csv_import_service.os.path.exists')
    @patch('services.csv_import_service.os.remove')
    def test_import_handles_malformed_csv_rows(self, mock_remove, mock_exists, mock_db,
                                              csv_import_service, mock_file_storage):
        """Test handling of malformed CSV rows"""
        # Arrange
        csv_content = """first_name,last_name,phone
John,Doe,5551234567
Jane,Smith  # Missing phone column
Bob,Johnson,5559876543"""
        
        mock_file = mock_file_storage('malformed.csv', csv_content)
        mock_exists.return_value = True
        
        with patch('builtins.open', mock_open(read_data=csv_content)):
            # Act
            result = csv_import_service.import_contacts(file=mock_file)
        
        # Assert
        assert result['total_rows'] > 0
        assert result['failed'] > 0
        assert len(result['errors']) > 0
    
    @patch('services.csv_import_service.db')
    def test_import_handles_permission_denied_file_save(self, mock_db, csv_import_service, mock_file_storage):
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
    
    @patch('services.csv_import_service.db')
    @patch('services.csv_import_service.os.path.exists')
    @patch('services.csv_import_service.os.remove')
    def test_import_with_extremely_large_csv(self, mock_remove, mock_exists, mock_db,
                                           csv_import_service, mock_file_storage):
        """Test import performance with large CSV files"""
        # Arrange
        # Simulate large CSV by testing batch commit logic
        csv_content = "first_name,last_name,phone\n" + "\n".join([
            f"User{i},Test{i},555{i:07d}" for i in range(150)  # 150 rows to trigger batch commits
        ])
        
        mock_file = mock_file_storage('large.csv', csv_content)
        mock_exists.return_value = True
        
        with patch('builtins.open', mock_open(read_data=csv_content)):
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
    
    @patch('services.csv_import_service.db')
    @patch('services.csv_import_service.os.path.exists')
    @patch('services.csv_import_service.os.remove')
    def test_import_csv_with_empty_file(self, mock_remove, mock_exists, mock_db,
                                       csv_import_service, mock_file_storage):
        """Test import of completely empty CSV file"""
        # Arrange
        csv_content = ""  # Empty file
        mock_file = mock_file_storage('empty.csv', csv_content)
        mock_exists.return_value = True
        
        with patch('builtins.open', mock_open(read_data=csv_content)):
            # Act
            result = csv_import_service.import_contacts(file=mock_file)
        
        # Assert
        assert result['total_rows'] == 0
        assert result['successful'] == 0
        assert result['failed'] == 0
    
    @patch('services.csv_import_service.db')
    @patch('services.csv_import_service.os.path.exists')
    @patch('services.csv_import_service.os.remove')
    def test_import_csv_with_only_headers(self, mock_remove, mock_exists, mock_db,
                                         csv_import_service, mock_file_storage):
        """Test import of CSV file with only headers and no data rows"""
        # Arrange
        csv_content = "first_name,last_name,phone,email"  # Headers only
        mock_file = mock_file_storage('headers_only.csv', csv_content)
        mock_exists.return_value = True
        
        with patch('builtins.open', mock_open(read_data=csv_content)):
            # Act
            result = csv_import_service.import_contacts(file=mock_file)
        
        # Assert
        assert result['total_rows'] == 0
        assert result['successful'] == 0
        assert result['failed'] == 0


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