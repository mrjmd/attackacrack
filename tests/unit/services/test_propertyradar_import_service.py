"""
PropertyRadar Import Service Tests - Dual contact import with complete field mapping
TDD RED Phase: Write comprehensive tests BEFORE implementation

These tests cover:
1. Dual contact import (PRIMARY and SECONDARY) from single PropertyRadar row
2. Complete field mapping for all 42+ PropertyRadar fields
3. Property-contact association with relationship types
4. Duplicate detection and handling
5. Data validation and transformation
6. Transaction handling and rollback
"""

import pytest
import csv
import io
from decimal import Decimal
from datetime import datetime, date
from unittest.mock import Mock, patch, call

from services.propertyradar_import_service import PropertyRadarImportService
from repositories.property_repository import PropertyRepository
from repositories.contact_repository import ContactRepository
from repositories.csv_import_repository import CSVImportRepository
from crm_database import Property, Contact, PropertyContact, CSVImport
from services.common.result import Result


class TestPropertyRadarImportService:
    """Test PropertyRadar CSV import service"""
    
    @pytest.fixture
    def mock_property_repository(self):
        """Mock property repository"""
        return Mock(spec=PropertyRepository)
    
    @pytest.fixture
    def mock_contact_repository(self):
        """Mock contact repository"""
        return Mock(spec=ContactRepository)
    
    @pytest.fixture
    def mock_csv_import_repository(self):
        """Mock CSV import repository"""
        return Mock(spec=CSVImportRepository)
    
    @pytest.fixture
    def service(self, mock_property_repository, mock_contact_repository, mock_csv_import_repository):
        """Create service instance with mocked dependencies"""
        # Should fail - PropertyRadarImportService doesn't exist yet
        return PropertyRadarImportService(
            property_repository=mock_property_repository,
            contact_repository=mock_contact_repository,
            csv_import_repository=mock_csv_import_repository
        )
    
    @pytest.fixture
    def sample_csv_row(self):
        """Sample PropertyRadar CSV row with all fields"""
        return {
            'Type': 'SFR',
            'Address': '455 MIDDLE ST',
            'City': 'BRAINTREE',
            'ZIP': '02184',
            'Subdivision': 'BRAINTREE',
            'Longitude': '-70.987754',
            'Latitude': '42.211216',
            'APN': 'BRAI-001001-000000-000018',
            'Yr Built': '1954',
            'Purchase Date': '2017-07-28',
            'Purchase Mos Since': '66',
            'Sq Ft': '2050',
            'Beds': '4',
            'Baths': '2',
            'Est Value': '767509',
            'Est Equity $': '402357',
            'Owner': 'LINKER,JON J & AIMEE C',
            'Mail Address': '455 MIDDLE ST',
            'Mail City': 'BRAINTREE',
            'Mail State': 'MA',
            'Mail ZIP': '02184',
            'Owner Occ?': '1',
            'Listed for Sale?': '0',
            'Listing Status': '',
            'Foreclosure?': '0',
            'Est Equity %': '52',
            'High Equity?': '1',
            'Primary Name': 'JON LINKER',
            'Primary Mobile Phone1': '339-222-4624',
            'Primary Mobile 1 Status': 'Active',
            'Primary Email1': 'linkeraimee@hotmail.com',
            'Primary Email 1 Status': 'Active',
            'Primary Email1 Hash': 'dd03ca8fe8f7c75977cde9f8bec35b0cedc0e6f918166da3ab60a3ea9d8c41c7',
            'Secondary Name': 'AIMEE LINKER',
            'Secondary Mobile Phone1': '781-316-1658',
            'Secondary Mobile 1 Status': 'Active',
            'Secondary Email1': '',
            'Secondary Email 1 Status': '',
            'Secondary Email1 Hash': ''
        }
    
    @pytest.fixture
    def sample_csv_content(self, sample_csv_row):
        """Sample CSV content with headers and data"""
        headers = list(sample_csv_row.keys())
        values = list(sample_csv_row.values())
        
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(headers)
        writer.writerow(values)
        return output.getvalue()
    
    def test_service_initialization(self, service):
        """Test service initializes with required dependencies"""
        # Should fail - service doesn't exist yet
        assert service.property_repository is not None
        assert service.contact_repository is not None
        assert service.csv_import_repository is not None
    
    def test_import_csv_creates_import_record(self, service, mock_csv_import_repository, sample_csv_content):
        """Test that CSV import creates tracking record"""
        # Should fail - import_csv method doesn't exist yet
        filename = 'test_properties.csv'
        imported_by = 'test_user'
        
        mock_csv_import = Mock(spec=CSVImport)
        mock_csv_import.id = 1
        mock_csv_import_repository.create.return_value = mock_csv_import
        
        result = service.import_csv(sample_csv_content, filename, imported_by)
        
        # Verify import record created
        mock_csv_import_repository.create.assert_called_once()
        create_args = mock_csv_import_repository.create.call_args[1]
        assert create_args['filename'] == filename
        assert create_args['imported_by'] == imported_by
        assert create_args['import_type'] == 'propertyradar'
    
    def test_parse_csv_row_creates_property_with_all_fields(self, service, sample_csv_row):
        """Test parsing CSV row creates property with all PropertyRadar fields"""
        # Should fail - parse_csv_row method doesn't exist yet
        result = service.parse_csv_row(sample_csv_row)
        
        assert result.is_success
        property_data = result.value['property']
        
        # Test all PropertyRadar property fields are mapped
        assert property_data['property_type'] == 'SFR'
        assert property_data['address'] == '455 Middle St'  # Normalized
        assert property_data['city'] == 'Braintree'  # Normalized
        assert property_data['zip_code'] == '02184'
        assert property_data['subdivision'] == 'BRAINTREE'
        assert property_data['longitude'] == -70.987754
        assert property_data['latitude'] == 42.211216
        assert property_data['apn'] == 'BRAI-001001-000000-000018'
        assert property_data['year_built'] == 1954
        assert property_data['purchase_date'] == date(2017, 7, 28)
        assert property_data['purchase_months_since'] == 66
        assert property_data['square_feet'] == 2050
        assert property_data['bedrooms'] == 4
        assert property_data['bathrooms'] == 2
        assert property_data['estimated_value'] == Decimal('767509.00')
        assert property_data['estimated_equity'] == Decimal('402357.00')
        
        # Test mail address fields
        assert property_data['mail_address'] == '455 MIDDLE ST'
        assert property_data['mail_city'] == 'BRAINTREE'
        assert property_data['mail_state'] == 'MA'
        assert property_data['mail_zip'] == '02184'
        
        # Test status flags
        assert property_data['owner_occupied'] is True
        assert property_data['listed_for_sale'] is False
        assert property_data['foreclosure'] is False
        assert property_data['estimated_equity_percent'] == 52
        assert property_data['high_equity'] is True
    
    def test_parse_csv_row_creates_primary_contact(self, service, sample_csv_row):
        """Test parsing CSV row creates primary contact"""
        # Should fail - dual contact parsing doesn't exist yet
        result = service.parse_csv_row(sample_csv_row)
        
        assert result.is_success
        primary_contact = result.value['primary_contact']
        
        assert primary_contact['first_name'] == 'Jon'  # Normalized
        assert primary_contact['last_name'] == 'Linker'  # Normalized
        assert primary_contact['phone'] == '+13392224624'  # Normalized phone
        assert primary_contact['email'] == 'linkeraimee@hotmail.com'
        assert primary_contact['contact_metadata']['phone_status'] == 'Active'
        assert primary_contact['contact_metadata']['email_status'] == 'Active'
        assert primary_contact['contact_metadata']['email_hash'] == 'dd03ca8fe8f7c75977cde9f8bec35b0cedc0e6f918166da3ab60a3ea9d8c41c7'
    
    def test_parse_csv_row_creates_secondary_contact(self, service, sample_csv_row):
        """Test parsing CSV row creates secondary contact"""
        # Should fail - secondary contact parsing doesn't exist yet
        result = service.parse_csv_row(sample_csv_row)
        
        assert result.is_success
        secondary_contact = result.value['secondary_contact']
        
        assert secondary_contact['first_name'] == 'Aimee'  # Normalized
        assert secondary_contact['last_name'] == 'Linker'  # Normalized
        assert secondary_contact['phone'] == '+17813161658'  # Normalized phone
        assert secondary_contact['email'] is None  # Empty in sample data
        assert secondary_contact['contact_metadata']['phone_status'] == 'Active'
    
    def test_parse_csv_row_handles_missing_secondary_contact(self, service, sample_csv_row):
        """Test parsing when secondary contact fields are empty"""
        # Should fail - secondary contact handling doesn't exist yet
        # Remove secondary contact data
        row_without_secondary = sample_csv_row.copy()
        row_without_secondary['Secondary Name'] = ''
        row_without_secondary['Secondary Mobile Phone1'] = ''
        row_without_secondary['Secondary Mobile 1 Status'] = ''
        
        result = service.parse_csv_row(row_without_secondary)
        
        assert result.is_success
        assert result.value['secondary_contact'] is None
    
    def test_normalize_phone_number(self, service):
        """Test phone number normalization"""
        # Should fail - phone normalization method doesn't exist yet
        # Test various phone formats
        assert service.normalize_phone('339-222-4624') == '+13392224624'
        assert service.normalize_phone('(339) 222-4624') == '+13392224624'
        assert service.normalize_phone('339.222.4624') == '+13392224624'
        assert service.normalize_phone('3392224624') == '+13392224624'
        assert service.normalize_phone('+1-339-222-4624') == '+13392224624'
        assert service.normalize_phone('') is None
        assert service.normalize_phone(None) is None
    
    def test_parse_name_splits_correctly(self, service):
        """Test name parsing splits first and last name correctly"""
        # Should fail - parse_name method doesn't exist yet
        assert service.parse_name('JON LINKER') == ('JON', 'LINKER')
        assert service.parse_name('MARY JANE SMITH') == ('MARY JANE', 'SMITH')
        assert service.parse_name('JOHNSON') == ('', 'JOHNSON')  # Single name goes to last
        assert service.parse_name('') == ('', '')
        assert service.parse_name(None) == ('', '')
    
    def test_import_row_creates_property_and_contacts(self, service, mock_property_repository, 
                                                     mock_contact_repository, sample_csv_row):
        """Test importing single row creates property and associates contacts"""
        # Should fail - import_row method doesn't exist yet
        mock_csv_import = Mock(spec=CSVImport)
        mock_csv_import.id = 1
        
        # Mock property creation
        mock_property = Mock(spec=Property)
        mock_property.id = 1
        mock_property_repository.create.return_value = mock_property
        mock_property_repository.find_duplicate.return_value = None
        
        # Mock contact creation
        mock_primary_contact = Mock(spec=Contact)
        mock_primary_contact.id = 1
        mock_secondary_contact = Mock(spec=Contact)
        mock_secondary_contact.id = 2
        mock_contact_repository.find_by_phone.side_effect = [None, None]  # No duplicates
        mock_contact_repository.create.side_effect = [mock_primary_contact, mock_secondary_contact]
        
        result = service.import_row(sample_csv_row, mock_csv_import)
        
        assert result.is_success
        
        # Verify property created
        mock_property_repository.create.assert_called_once()
        
        # Verify both contacts created
        assert mock_contact_repository.create.call_count == 2
        
        # Verify contacts associated with property
        assert mock_property_repository.associate_contact.call_count == 2
        mock_property_repository.associate_contact.assert_any_call(
            mock_property, mock_primary_contact, 'PRIMARY'
        )
        mock_property_repository.associate_contact.assert_any_call(
            mock_property, mock_secondary_contact, 'SECONDARY'
        )
    
    def test_import_row_handles_duplicate_property(self, service, mock_property_repository, sample_csv_row):
        """Test importing row with duplicate property (by address+zip)"""
        # Should fail - duplicate detection doesn't exist yet
        mock_csv_import = Mock(spec=CSVImport)
        mock_existing_property = Mock(spec=Property)
        mock_existing_property.id = 1
        
        # Mock finding existing property
        mock_property_repository.find_duplicate.return_value = mock_existing_property
        
        result = service.import_row(sample_csv_row, mock_csv_import)
        
        assert result.is_success
        
        # Should not create new property
        mock_property_repository.create.assert_not_called()
        
        # Should update existing property
        mock_property_repository.update.assert_called_once()
    
    def test_import_row_handles_duplicate_contact(self, service, mock_contact_repository, 
                                                 mock_property_repository, sample_csv_row):
        """Test importing row with duplicate contact (by phone)"""
        # Should fail - contact deduplication doesn't exist yet
        mock_csv_import = Mock(spec=CSVImport)
        mock_property = Mock(spec=Property)
        mock_property.id = 1
        mock_property_repository.create.return_value = mock_property
        mock_property_repository.find_duplicate.return_value = None
        
        # Mock existing contact
        mock_existing_contact = Mock(spec=Contact)
        mock_existing_contact.id = 1
        mock_contact_repository.find_by_phone.return_value = mock_existing_contact
        
        result = service.import_row(sample_csv_row, mock_csv_import)
        
        assert result.is_success
        
        # Should not create new contact
        mock_contact_repository.create.assert_not_called()
        
        # Should update existing contact
        mock_contact_repository.update.assert_called_once()
    
    def test_import_csv_processes_all_rows(self, service, mock_csv_import_repository, 
                                          mock_property_repository, sample_csv_content):
        """Test that import processes all CSV rows"""
        # Should fail - full CSV processing doesn't exist yet
        mock_csv_import = Mock(spec=CSVImport)
        mock_csv_import.id = 1
        mock_csv_import_repository.create.return_value = mock_csv_import
        
        # Mock successful row processing
        mock_property = Mock(spec=Property)
        mock_property_repository.create.return_value = mock_property
        mock_property_repository.find_duplicate.return_value = None
        
        with patch.object(service, 'import_row') as mock_import_row:
            mock_import_row.return_value = Result.success({'property': mock_property})
            
            result = service.import_csv(sample_csv_content, 'test.csv', 'test_user')
            
            assert result.is_success
            
            # Should process one row (excluding header)
            mock_import_row.assert_called_once()
            
            # Should update import status
            mock_csv_import_repository.update_import_status.assert_called_once_with(
                mock_csv_import.id, 1, 1, 0, None  # total=1, success=1, failed=0
            )
    
    def test_import_csv_handles_processing_errors(self, service, mock_csv_import_repository, sample_csv_content):
        """Test error handling during CSV processing"""
        # Should fail - error handling doesn't exist yet
        mock_csv_import = Mock(spec=CSVImport)
        mock_csv_import.id = 1
        mock_csv_import_repository.create.return_value = mock_csv_import
        
        with patch.object(service, 'import_row') as mock_import_row:
            mock_import_row.return_value = Result.failure('Processing error')
            
            result = service.import_csv(sample_csv_content, 'test.csv', 'test_user')
            
            assert result.is_success  # Overall import succeeds even with row failures
            
            # Should update import status with failures
            mock_csv_import_repository.update_import_status.assert_called_once_with(
                mock_csv_import.id, 1, 0, 1, {'errors': ['Processing error']}  # 0 success, 1 failed
            )
    
    def test_validate_csv_headers(self, service):
        """Test CSV header validation"""
        # Should fail - header validation doesn't exist yet
        required_headers = [
            'Type', 'Address', 'City', 'ZIP', 'Primary Name', 
            'Primary Mobile Phone1', 'Secondary Name', 'Secondary Mobile Phone1'
        ]
        
        # Valid headers
        valid_headers = required_headers + ['Extra Field']
        assert service.validate_csv_headers(valid_headers).is_success
        
        # Missing required header
        invalid_headers = required_headers[:-1]  # Remove last header
        result = service.validate_csv_headers(invalid_headers)
        assert result.is_failure
        assert 'missing required headers' in result.error.lower()
    
    def test_data_type_conversions(self, service, sample_csv_row):
        """Test data type conversions from CSV strings"""
        # Should fail - data conversion methods don't exist yet
        result = service.parse_csv_row(sample_csv_row)
        property_data = result.value['property']
        
        # Test numeric conversions
        assert isinstance(property_data['longitude'], float)
        assert isinstance(property_data['latitude'], float)
        assert isinstance(property_data['year_built'], int)
        assert isinstance(property_data['square_feet'], int)
        assert isinstance(property_data['bedrooms'], int)
        assert isinstance(property_data['bathrooms'], int)
        assert isinstance(property_data['estimated_value'], Decimal)
        assert isinstance(property_data['estimated_equity'], Decimal)
        
        # Test date conversion
        assert isinstance(property_data['purchase_date'], date)
        
        # Test boolean conversions
        assert isinstance(property_data['owner_occupied'], bool)
        assert isinstance(property_data['listed_for_sale'], bool)
        assert isinstance(property_data['foreclosure'], bool)
        assert isinstance(property_data['high_equity'], bool)
    
    def test_handles_malformed_data(self, service):
        """Test handling of malformed data in CSV"""
        # Should fail - data validation doesn't exist yet
        malformed_row = {
            'Type': 'SFR',
            'Address': '123 Test St',
            'Longitude': 'invalid',  # Invalid float
            'Yr Built': 'not_a_number',  # Invalid int
            'Est Value': 'abc',  # Invalid decimal
            'Purchase Date': '2023-99-99',  # Invalid date
            'Primary Name': 'TEST USER',
            'Primary Mobile Phone1': '123',  # Invalid phone
        }
        
        result = service.parse_csv_row(malformed_row)
        
        # Should handle errors gracefully
        if result.is_failure:
            assert 'data validation' in result.error.lower()
        else:
            # Or should provide defaults for invalid data
            property_data = result.value['property']
            assert property_data['longitude'] is None
            assert property_data['year_built'] is None
    
    def test_transaction_rollback_on_error(self, service, mock_property_repository, sample_csv_content):
        """Test that transaction is rolled back on errors"""
        # Should fail - transaction handling doesn't exist yet
        mock_csv_import = Mock(spec=CSVImport)
        mock_csv_import_repository = service.csv_import_repository
        mock_csv_import_repository.create.return_value = mock_csv_import
        
        # Mock repository to raise error
        mock_property_repository.create.side_effect = Exception('Database error')
        
        with patch.object(service, 'rollback_transaction') as mock_rollback:
            result = service.import_csv(sample_csv_content, 'test.csv', 'test_user')
            
            # Should call rollback on error
            mock_rollback.assert_called_once()
    
    def test_import_progress_tracking(self, service, mock_csv_import_repository, sample_csv_content):
        """Test import progress tracking and reporting"""
        # Should fail - progress tracking doesn't exist yet
        mock_csv_import = Mock(spec=CSVImport)
        mock_csv_import.id = 1
        mock_csv_import_repository.create.return_value = mock_csv_import
        
        progress_callback = Mock()
        
        result = service.import_csv(
            sample_csv_content, 
            'test.csv', 
            'test_user',
            progress_callback=progress_callback
        )
        
        # Should call progress callback
        progress_callback.assert_called()
    
    def test_import_statistics_collection(self, service, mock_csv_import_repository, sample_csv_content):
        """Test collection of import statistics"""
        # Should fail - statistics collection doesn't exist yet
        mock_csv_import = Mock(spec=CSVImport)
        mock_csv_import.id = 1
        mock_csv_import_repository.create.return_value = mock_csv_import
        
        result = service.import_csv(sample_csv_content, 'test.csv', 'test_user')
        
        assert result.is_success
        stats = result.value
        
        # Should return comprehensive statistics
        assert 'total_rows' in stats
        assert 'properties_created' in stats
        assert 'properties_updated' in stats
        assert 'contacts_created' in stats
        assert 'contacts_updated' in stats
        assert 'errors' in stats
        assert 'processing_time' in stats
    
    def test_batch_processing_large_csv(self, service):
        """Test batch processing for large CSV files"""
        # Should fail - batch processing doesn't exist yet
        # Create large CSV content
        large_csv_rows = []
        for i in range(1000):
            large_csv_rows.append(f'SFR,{i} Test St,Test City,0{i:04d},,,,,,,,,,,,,Test Owner,{i} Test St,Test City,MA,0{i:04d},1,0,,0,50,0,Test User {i},555-{i:04d},Active,test{i}@example.com,Active,hash{i},,,,,')
        
        headers = 'Type,Address,City,ZIP,Subdivision,Longitude,Latitude,APN,Yr Built,Purchase Date,Purchase Mos Since,Sq Ft,Beds,Baths,Est Value,Est Equity $,Owner,Mail Address,Mail City,Mail State,Mail ZIP,Owner Occ?,Listed for Sale?,Listing Status,Foreclosure?,Est Equity %,High Equity?,Primary Name,Primary Mobile Phone1,Primary Mobile 1 Status,Primary Email1,Primary Email 1 Status,Primary Email1 Hash,Secondary Name,Secondary Mobile Phone1,Secondary Mobile 1 Status,Secondary Email1,Secondary Email 1 Status,Secondary Email1 Hash'
        large_csv_content = headers + '\n' + '\n'.join(large_csv_rows)
        
        result = service.import_csv(large_csv_content, 'large_test.csv', 'test_user', batch_size=100)
        
        assert result.is_success
        assert result.value['total_rows'] == 1000
    
    def test_memory_efficient_processing(self, service):
        """Test that large files are processed memory efficiently"""
        # Should fail - memory efficient processing doesn't exist yet
        # This test would verify that large CSV files don't load entirely into memory
        
        with patch.object(service, 'process_csv_stream') as mock_stream_process:
            mock_stream_process.return_value = Result.success({'total_rows': 5000})
            
            # Simulate large file processing
            result = service.import_csv_file('/path/to/large_file.csv', 'test_user')
            
            assert result.is_success
            mock_stream_process.assert_called_once()
    
    # ==============================================================================
    # DATA NORMALIZATION TESTS - TDD RED PHASE
    # These tests should FAIL initially since normalization methods don't exist yet
    # ==============================================================================
    
    def test_normalize_name_all_caps_to_proper_case(self, service):
        """Test name normalization from ALL CAPS to proper case"""
        # Should fail - normalize_name method doesn't exist yet
        assert service.normalize_name('JOHN SMITH') == 'John Smith'
        assert service.normalize_name('MARY JANE DOE') == 'Mary Jane Doe'
        assert service.normalize_name('ELIZABETH BROWN') == 'Elizabeth Brown'
    
    def test_normalize_name_handles_hyphenated_names(self, service):
        """Test normalization of hyphenated names"""
        # Should fail - normalize_name method doesn't exist yet
        assert service.normalize_name('MARY-JANE SMITH') == 'Mary-Jane Smith'
        assert service.normalize_name('JEAN-LUC PICARD') == 'Jean-Luc Picard'
        assert service.normalize_name('ANNE-MARIE O\'CONNOR') == 'Anne-Marie O\'Connor'
    
    def test_normalize_name_handles_apostrophes(self, service):
        """Test normalization of names with apostrophes"""
        # Should fail - normalize_name method doesn't exist yet
        assert service.normalize_name('O\'BRIEN') == 'O\'Brien'
        assert service.normalize_name('D\'ANGELO') == 'D\'Angelo'
        assert service.normalize_name('MC\'DONALD') == 'Mc\'Donald'
        assert service.normalize_name('O\'NEILL-SMITH') == 'O\'Neill-Smith'
    
    def test_normalize_name_handles_multiple_spaces(self, service):
        """Test normalization removes extra spaces"""
        # Should fail - normalize_name method doesn't exist yet
        assert service.normalize_name('JOHN  SMITH') == 'John Smith'
        assert service.normalize_name('MARY   JANE    DOE') == 'Mary Jane Doe'
        assert service.normalize_name('  ELIZABETH  BROWN  ') == 'Elizabeth Brown'
    
    def test_normalize_name_preserves_proper_case(self, service):
        """Test that existing proper case is preserved"""
        # Should fail - normalize_name method doesn't exist yet
        assert service.normalize_name('McDonald') == 'McDonald'
        assert service.normalize_name('McConnell') == 'McConnell'
        assert service.normalize_name('MacArthur') == 'MacArthur'
        assert service.normalize_name('O\'Brien') == 'O\'Brien'
        assert service.normalize_name('DuBois') == 'DuBois'
    
    def test_normalize_name_handles_suffixes(self, service):
        """Test normalization of names with suffixes"""
        # Should fail - normalize_name method doesn't exist yet
        assert service.normalize_name('JOHN SMITH JR') == 'John Smith Jr'
        assert service.normalize_name('ROBERT DOE SR') == 'Robert Doe Sr'
        assert service.normalize_name('WILLIAM JONES III') == 'William Jones III'
        assert service.normalize_name('CHARLES BROWN IV') == 'Charles Brown IV'
        assert service.normalize_name('MICHAEL DAVIS JR.') == 'Michael Davis Jr.'
    
    def test_normalize_name_handles_edge_cases(self, service):
        """Test name normalization edge cases"""
        # Should fail - normalize_name method doesn't exist yet
        assert service.normalize_name('') == ''
        assert service.normalize_name('   ') == ''
        assert service.normalize_name('JOHN') == 'John'
        assert service.normalize_name('j') == 'J'
        assert service.normalize_name('a-b') == 'A-B'
    
    def test_normalize_address_basic_conversion(self, service):
        """Test basic address normalization to proper case with suffix standardization"""
        # Test standardized suffixes (abbreviated form)
        assert service.normalize_address('455 MIDDLE ST') == '455 Middle St'
        assert service.normalize_address('123 MAIN STREET') == '123 Main St'  # STREET -> St
        assert service.normalize_address('789 OAK AVENUE') == '789 Oak Ave'    # AVENUE -> Ave
    
    def test_normalize_address_standardizes_street_suffixes(self, service):
        """Test address normalization standardizes street suffixes"""
        # Should fail - normalize_address method doesn't exist yet
        assert service.normalize_address('123 MAIN STREET') == '123 Main St'
        assert service.normalize_address('456 OAK AVENUE') == '456 Oak Ave'
        assert service.normalize_address('789 PINE ROAD') == '789 Pine Rd'
        assert service.normalize_address('321 ELM DRIVE') == '321 Elm Dr'
        assert service.normalize_address('654 MAPLE LANE') == '654 Maple Ln'
        assert service.normalize_address('987 CEDAR COURT') == '987 Cedar Ct'
        assert service.normalize_address('147 BIRCH PLACE') == '147 Birch Pl'
        assert service.normalize_address('258 WILLOW CIRCLE') == '258 Willow Cir'
        assert service.normalize_address('369 POPLAR BOULEVARD') == '369 Poplar Blvd'
    
    def test_normalize_address_handles_directionals(self, service):
        """Test address normalization handles directional indicators"""
        # Should fail - normalize_address method doesn't exist yet
        assert service.normalize_address('123 N MAIN ST') == '123 N Main St'
        assert service.normalize_address('456 SOUTH OAK AVE') == '456 S Oak Ave'
        assert service.normalize_address('789 EAST PINE RD') == '789 E Pine Rd'
        assert service.normalize_address('321 WEST ELM DR') == '321 W Elm Dr'
        assert service.normalize_address('654 NORTHEAST MAPLE LN') == '654 NE Maple Ln'
        assert service.normalize_address('987 SOUTHWEST CEDAR CT') == '987 SW Cedar Ct'
    
    def test_normalize_address_preserves_apartment_units(self, service):
        """Test address normalization preserves apartment/unit numbers"""
        # Should fail - normalize_address method doesn't exist yet
        assert service.normalize_address('123 MAIN ST APT 4B') == '123 Main St Apt 4B'
        assert service.normalize_address('456 OAK AVE UNIT 12') == '456 Oak Ave Unit 12'
        assert service.normalize_address('789 PINE RD #205') == '789 Pine Rd #205'
        assert service.normalize_address('321 ELM DR SUITE 100') == '321 Elm Dr Suite 100'
    
    def test_normalize_address_handles_po_boxes(self, service):
        """Test address normalization handles PO Boxes properly"""
        # Should fail - normalize_address method doesn't exist yet
        assert service.normalize_address('PO BOX 1234') == 'PO Box 1234'
        assert service.normalize_address('P.O. BOX 5678') == 'PO Box 5678'
        assert service.normalize_address('POST OFFICE BOX 9999') == 'PO Box 9999'
    
    def test_normalize_address_handles_edge_cases(self, service):
        """Test address normalization edge cases"""
        # Should fail - normalize_address method doesn't exist yet
        assert service.normalize_address('') == ''
        assert service.normalize_address('   ') == ''
        assert service.normalize_address('123') == '123'
        assert service.normalize_address('MAIN ST') == 'Main St'
    
    def test_normalize_city_basic_conversion(self, service):
        """Test basic city normalization to proper case"""
        # Should fail - normalize_city method doesn't exist yet
        assert service.normalize_city('BRAINTREE') == 'Braintree'
        assert service.normalize_city('BOSTON') == 'Boston'
        assert service.normalize_city('CAMBRIDGE') == 'Cambridge'
    
    def test_normalize_city_handles_multi_word_cities(self, service):
        """Test normalization of multi-word city names"""
        # Should fail - normalize_city method doesn't exist yet
        assert service.normalize_city('SAN FRANCISCO') == 'San Francisco'
        assert service.normalize_city('LOS ANGELES') == 'Los Angeles'
        assert service.normalize_city('NEW YORK') == 'New York'
        assert service.normalize_city('SALT LAKE CITY') == 'Salt Lake City'
        assert service.normalize_city('BATON ROUGE') == 'Baton Rouge'
    
    def test_normalize_city_handles_hyphenated_cities(self, service):
        """Test normalization of hyphenated city names"""
        # Should fail - normalize_city method doesn't exist yet
        assert service.normalize_city('WINSTON-SALEM') == 'Winston-Salem'
        assert service.normalize_city('WILKES-BARRE') == 'Wilkes-Barre'
        assert service.normalize_city('JOHNSON-CITY') == 'Johnson-City'
    
    def test_normalize_city_preserves_proper_case(self, service):
        """Test that existing proper case in cities is preserved"""
        # Should fail - normalize_city method doesn't exist yet
        assert service.normalize_city('San Francisco') == 'San Francisco'
        assert service.normalize_city('Los Angeles') == 'Los Angeles'
        assert service.normalize_city('New York') == 'New York'
        assert service.normalize_city('McDonald Heights') == 'McDonald Heights'
    
    def test_normalize_city_handles_edge_cases(self, service):
        """Test city normalization edge cases"""
        # Should fail - normalize_city method doesn't exist yet
        assert service.normalize_city('') == ''
        assert service.normalize_city('   ') == ''
        assert service.normalize_city('A') == 'A'
        assert service.normalize_city('x-y') == 'X-Y'
    
    def test_normalization_applied_during_csv_import(self, service, mock_property_repository, 
                                                   mock_contact_repository, mock_csv_import_repository):
        """Test that normalization is applied during CSV row processing"""
        # Should fail - normalization methods don't exist yet
        mock_csv_import = Mock()
        mock_csv_import.id = 1
        mock_csv_import_repository.create.return_value = mock_csv_import
        
        # Sample row with ALL CAPS data that should be normalized
        test_row = {
            'Type': 'SFR',
            'Address': '455 MIDDLE STREET',
            'City': 'SAN FRANCISCO',
            'ZIP': '02184',
            'Primary Name': 'JOHN O\'BRIEN-SMITH JR',
            'Primary Mobile Phone1': '339-222-4624',
            'Secondary Name': 'MARY-JANE MCDONALD',
            'Secondary Mobile Phone1': '781-316-1658'
        }
        
        # Mock property and contact creation
        mock_property = Mock()
        mock_property_repository.find_duplicate.return_value = None
        mock_property_repository.create.return_value = mock_property
        
        mock_contact = Mock()
        mock_contact_repository.find_by_phone.return_value = None
        mock_contact_repository.create.return_value = mock_contact
        
        # Process the row
        result = service.import_row(test_row, mock_csv_import)
        
        # Verify result is successful
        assert result.is_success
        
        # Verify property was created with normalized address and city
        property_call_args = mock_property_repository.create.call_args[1]
        assert property_call_args['address'] == '455 Middle St'  # Normalized
        assert property_call_args['city'] == 'San Francisco'  # Normalized
        
        # Verify contacts were created with normalized names
        contact_calls = mock_contact_repository.create.call_args_list
        
        # Primary contact should have normalized name
        primary_contact_args = contact_calls[0][1]
        assert primary_contact_args['first_name'] == 'John'  # Normalized from JOHN
        assert primary_contact_args['last_name'] == 'O\'Brien-Smith Jr'  # Normalized from O'BRIEN-SMITH JR
        
        # Secondary contact should have normalized name
        secondary_contact_args = contact_calls[1][1]
        assert secondary_contact_args['first_name'] == 'Mary-Jane'  # Normalized from MARY-JANE
        assert secondary_contact_args['last_name'] == 'McDonald'  # Normalized from MCDONALD
