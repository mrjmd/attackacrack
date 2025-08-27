"""
PropertyRadar Import Statistics TDD Tests - RED PHASE
TDD CRITICAL: These tests MUST fail initially - implementation comes AFTER tests

PROBLEM IDENTIFIED:
- Current system counts CSV data extraction, NOT actual database operations
- contacts_created is incremented based on CSV data presence, not whether contact was actually created or found existing
- contacts_updated is initialized but NEVER incremented anywhere
- Same CSV imported multiple times shows identical numbers because it's not tracking actual operations

TESTING STRATEGY:
1. Test that statistics reflect ACTUAL database operations, not CSV data parsing
2. Test duplicate detection affects statistics correctly
3. Test different duplicate handling strategies (skip, replace, merge)
4. Test that progress tracking uses row numbers, not inflated contact counts

These tests enforce the requirement that statistics must track what ACTUALLY happened to the data,
not what was found in the CSV file.
"""

import pytest
import csv
import io
from unittest.mock import Mock, patch, call
from datetime import datetime

from services.propertyradar_import_service import PropertyRadarImportService
from repositories.property_repository import PropertyRepository
from repositories.contact_repository import ContactRepository
from repositories.csv_import_repository import CSVImportRepository
from crm_database import Property, Contact, CSVImport
from services.common.result import Result


class TestPropertyRadarImportStatistics:
    """TDD RED Phase: Test accurate statistics tracking for database operations"""
    
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
        mock_repo = Mock(spec=CSVImportRepository)
        mock_csv_import = Mock(spec=CSVImport, id=1, contacts=[])
        mock_repo.create.return_value = mock_csv_import
        return mock_repo
    
    @pytest.fixture
    def service(self, mock_property_repository, mock_contact_repository, mock_csv_import_repository):
        """Create service instance with mocked dependencies"""
        return PropertyRadarImportService(
            property_repository=mock_property_repository,
            contact_repository=mock_contact_repository,
            csv_import_repository=mock_csv_import_repository
        )
    
    @pytest.fixture
    def sample_csv_dual_contacts(self):
        """CSV with 2 properties, each having primary and secondary contacts (4 total)"""
        return """Type,Address,City,ZIP,Primary Name,Primary Mobile Phone1,Secondary Name,Secondary Mobile Phone1
SFR,123 Main St,City,12345,John Smith,555-0001,Jane Smith,555-0002
SFR,456 Oak Ave,City,67890,Bob Johnson,555-0003,Alice Johnson,555-0004"""

    @pytest.fixture
    def sample_csv_mixed_contacts(self):
        """CSV with 3 properties: dual contacts, single primary, single secondary (4 total)"""
        return """Type,Address,City,ZIP,Primary Name,Primary Mobile Phone1,Secondary Name,Secondary Mobile Phone1
SFR,123 Main St,City,12345,John Smith,555-0001,Jane Smith,555-0002
SFR,456 Oak Ave,City,67890,Bob Johnson,555-0003,,
SFR,789 Pine Rd,City,11111,,,Charlie Wilson,555-0005"""

    def test_first_import_marks_all_contacts_as_created_not_found_in_csv(self, service, sample_csv_dual_contacts,
                                                                       mock_contact_repository,
                                                                       mock_property_repository):
        """Test that first import counts ACTUAL database operations, not CSV data presence
        
        CRITICAL: This test WILL FAIL until we fix statistics to track operations, not CSV data.
        Current implementation counts CSV data extraction, not actual database create/update operations.
        """
        # Arrange - First import scenario (no existing data)
        mock_contact_repository.find_by_phone.return_value = None  # No existing contacts
        mock_property_repository.find_by_apn.return_value = None
        mock_property_repository.find_by_address_and_zip.return_value = None
        
        # Mock successful contact creation
        def create_contact(**kwargs):
            mock_contact = Mock(spec=Contact, phone=kwargs['phone'])
            return mock_contact
        mock_contact_repository.create.side_effect = create_contact
        
        # Mock successful property creation
        mock_property_repository.create.return_value = Mock(spec=Property, id=1)
        
        # Act
        result = service.import_csv(sample_csv_dual_contacts, 'first_import.csv', 'test_user')
        
        # Assert - This WILL FAIL because current implementation counts CSV data, not operations
        assert result.is_success
        stats = result.value
        
        # CRITICAL TEST: Statistics must reflect ACTUAL database operations
        # Current system will incorrectly count based on CSV data presence
        assert stats['contacts_created'] == 4, "Should count 4 ACTUAL contact creations (2 rows × 2 contacts each)"
        assert stats['contacts_updated'] == 0, "No contacts should be updated on first import"
        assert stats['properties_created'] == 2, "Should count 2 ACTUAL property creations"
        assert stats['properties_updated'] == 0, "No properties should be updated on first import"
        
        # Verify repository operations match statistics
        assert mock_contact_repository.create.call_count == 4, "Should actually create 4 contacts"
        assert mock_property_repository.create.call_count == 2, "Should actually create 2 properties"

    def test_second_identical_import_marks_all_as_existing_not_created(self, service, sample_csv_dual_contacts,
                                                                     mock_contact_repository,
                                                                     mock_property_repository):
        """Test that duplicate import counts ZERO new creations, all existing found
        
        CRITICAL: This test WILL FAIL until we fix statistics to track actual operations.
        Current system will show identical statistics for duplicate imports.
        """
        # Arrange - Second import scenario (all data already exists)
        existing_contacts = [
            Mock(spec=Contact, id=1, phone='+15550001'),
            Mock(spec=Contact, id=2, phone='+15550002'), 
            Mock(spec=Contact, id=3, phone='+15550003'),
            Mock(spec=Contact, id=4, phone='+15550004')
        ]
        
        # Mock finding existing contacts by phone
        mock_contact_repository.find_by_phone.side_effect = existing_contacts
        
        # Mock finding existing properties  
        existing_properties = [
            Mock(spec=Property, id=1, address='123 Main St', zip_code='12345'),
            Mock(spec=Property, id=2, address='456 Oak Ave', zip_code='67890')
        ]
        mock_property_repository.find_by_address_and_zip.side_effect = existing_properties
        
        # Act
        result = service.import_csv(sample_csv_dual_contacts, 'duplicate_import.csv', 'test_user')
        
        # Assert - This WILL FAIL because current system doesn't track found vs created
        assert result.is_success
        stats = result.value
        
        # CRITICAL TEST: Must distinguish between created and found existing
        assert stats['contacts_created'] == 0, "No new contacts should be created (all found existing)"
        assert stats['contacts_updated'] == 4, "Should count 4 existing contacts as 'updated' or 'found'"
        assert stats['properties_created'] == 0, "No new properties should be created (all found existing)"  
        assert stats['properties_updated'] == 2, "Should count 2 existing properties as 'updated'"
        
        # Verify no creation operations occurred
        mock_contact_repository.create.assert_not_called()
        mock_property_repository.create.assert_not_called()

    def test_mixed_import_counts_created_and_existing_separately(self, service, sample_csv_mixed_contacts,
                                                               mock_contact_repository,
                                                               mock_property_repository):
        """Test import with mix of new and existing contacts shows accurate counts
        
        CRITICAL: This test WILL FAIL until we implement operation-type tracking.
        """
        # Arrange - Mixed scenario: some exist, some don't
        def mock_find_contact(phone):
            # First two contacts exist, third doesn't 
            existing_map = {
                '+15550001': Mock(spec=Contact, id=1, phone='+15550001'),
                '+15550002': Mock(spec=Contact, id=2, phone='+15550002'),
                '+15550003': None,  # Doesn't exist
                '+15550005': None   # Doesn't exist
            }
            return existing_map.get(phone)
        
        mock_contact_repository.find_by_phone.side_effect = mock_find_contact
        
        # Mock contact creation for new ones
        mock_contact_repository.create.side_effect = [
            Mock(spec=Contact, id=3, phone='+15550003'),
            Mock(spec=Contact, id=4, phone='+15550005')
        ]
        
        # All properties are new
        mock_property_repository.find_by_apn.return_value = None
        mock_property_repository.find_by_address_and_zip.return_value = None
        mock_property_repository.create.side_effect = [
            Mock(spec=Property, id=1),
            Mock(spec=Property, id=2), 
            Mock(spec=Property, id=3)
        ]
        
        # Act
        result = service.import_csv(sample_csv_mixed_contacts, 'mixed_import.csv', 'test_user')
        
        # Assert - This WILL FAIL until we track operation types
        assert result.is_success
        stats = result.value
        
        # CRITICAL: Must accurately count operations, not CSV parsing
        assert stats['contacts_created'] == 2, "Should create 2 new contacts (Bob Johnson, Charlie Wilson)"
        assert stats['contacts_updated'] == 2, "Should find 2 existing contacts (John Smith, Jane Smith)"
        assert stats['properties_created'] == 3, "Should create 3 new properties"
        assert stats['properties_updated'] == 0, "No existing properties in this test"
        
        # Verify actual operations match statistics
        assert mock_contact_repository.create.call_count == 2
        assert mock_property_repository.create.call_count == 3

    def test_process_contact_returns_operation_type_tuple(self, service):
        """Test that _process_contact returns (contact, operation_type) tuple for statistics
        
        CRITICAL: This test WILL FAIL until we modify _process_contact to return operation type.
        """
        # Arrange
        contact_data = {
            'first_name': 'John',
            'last_name': 'Smith',
            'phone': '+15550001',
            'email': 'john@example.com'
        }
        
        # Test case 1: New contact creation
        service.contact_repository.find_by_phone.return_value = None
        mock_new_contact = Mock(spec=Contact, id=1)
        service.contact_repository.create.return_value = mock_new_contact
        
        # Act - This WILL FAIL until _process_contact returns tuple
        contact, operation = service._process_contact(contact_data, None)
        
        # Assert
        assert contact == mock_new_contact
        assert operation == 'created', "Should return 'created' for new contact"
        
        # Test case 2: Existing contact found
        service.contact_repository.find_by_phone.return_value = mock_new_contact
        
        # Act
        contact, operation = service._process_contact(contact_data, None)
        
        # Assert
        assert contact == mock_new_contact
        assert operation == 'existing', "Should return 'existing' for found contact"

    def test_process_property_returns_operation_type_tuple(self, service):
        """Test that _process_property returns (property, operation_type) tuple for statistics
        
        CRITICAL: This test WILL FAIL until we modify _process_property to return operation type.
        """
        # Arrange
        property_data = {
            'address': '123 Main St',
            'city': 'Test City',
            'zip_code': '12345',
            'property_type': 'SFR'
        }
        
        # Test case 1: New property creation
        service.property_repository.find_by_apn.return_value = None
        service.property_repository.find_by_address_and_zip.return_value = None
        mock_new_property = Mock(spec=Property, id=1)
        service.property_repository.create.return_value = mock_new_property
        
        # Act - This WILL FAIL until _process_property returns tuple
        property_obj, operation = service._process_property(property_data)
        
        # Assert
        assert property_obj == mock_new_property
        assert operation == 'created', "Should return 'created' for new property"
        
        # Test case 2: Existing property found and updated
        existing_property = Mock(spec=Property, id=1)
        service.property_repository.find_by_address_and_zip.return_value = existing_property
        service.property_repository.update.return_value = existing_property
        
        # Act  
        property_obj, operation = service._process_property(property_data)
        
        # Assert
        assert property_obj == existing_property
        assert operation == 'updated', "Should return 'updated' for existing property"

    def test_batch_processor_uses_operation_types_for_statistics(self, service, mock_contact_repository,
                                                               mock_property_repository):
        """Test that batch processing uses operation types for accurate statistics
        
        CRITICAL: This test WILL FAIL until _process_batch uses operation types from helper methods.
        """
        # Arrange
        batch_rows = [
            {'Type': 'SFR', 'Address': '123 Main St', 'City': 'City', 'ZIP': '12345',
             'Primary Name': 'John Smith', 'Primary Mobile Phone1': '555-0001'},
            {'Type': 'SFR', 'Address': '456 Oak Ave', 'City': 'City', 'ZIP': '67890', 
             'Primary Name': 'Jane Doe', 'Primary Mobile Phone1': '555-0002'}
        ]
        
        mock_csv_import = Mock(spec=CSVImport, id=1, contacts=[])
        
        # Mock _process_contact and _process_property to return operation types
        with patch.object(service, '_process_contact') as mock_process_contact, \
             patch.object(service, '_process_property') as mock_process_property:
            
            # First row: new contact and property
            mock_process_contact.side_effect = [
                (Mock(spec=Contact, id=1), 'created'),  # First contact created
                (Mock(spec=Contact, id=2), 'created')   # Second contact created 
            ]
            mock_process_property.side_effect = [
                (Mock(spec=Property, id=1), 'created'),   # First property created
                (Mock(spec=Property, id=2), 'existing')   # Second property exists
            ]
            
            # Act - This WILL FAIL until _process_batch uses operation types
            stats, contacts = service._process_batch(batch_rows, mock_csv_import, return_contacts=False)
        
        # Assert - Statistics must reflect actual operations, not CSV data
        assert stats['contacts_created'] == 2, "Should count actual contact creations from operation types"
        assert stats['contacts_updated'] == 0, "No contact updates in this scenario"
        assert stats['properties_created'] == 1, "Should count actual property creations from operation types"
        assert stats['properties_updated'] == 1, "Should count actual property updates from operation types"

    def test_import_progress_uses_row_numbers_not_contact_counts(self, service, sample_csv_dual_contacts):
        """Test that progress callback uses row numbers for both numerator and denominator
        
        CRITICAL: This test WILL FAIL until progress calculation is fixed.
        Current system may use inflated contact counts instead of actual row progress.
        """
        # Arrange
        progress_calls = []
        
        def capture_progress(processed, total):
            progress_calls.append((processed, total))
        
        # Act  
        result = service.import_csv(
            sample_csv_dual_contacts, 
            'progress_test.csv', 
            'test_user',
            progress_callback=capture_progress
        )
        
        # Assert
        assert result.is_success
        
        # CRITICAL: Progress should be based on ROW processing, not contact counting
        assert len(progress_calls) > 0, "Progress callback should be called"
        
        # Final progress call should show row-based progress (2 rows processed out of 2 total)
        final_processed, final_total = progress_calls[-1]
        assert final_total == 2, "Total should be number of CSV rows (2), not number of contacts (4)"
        assert final_processed <= final_total, "Processed should never exceed total rows"
        
        # Progress percentage should never exceed 100%
        for processed, total in progress_calls:
            progress_percent = (processed / total) * 100 if total > 0 else 0
            assert progress_percent <= 100, f"Progress {progress_percent}% should never exceed 100%"

    def test_statistics_distinguish_between_contacts_and_properties(self, service, sample_csv_dual_contacts,
                                                                  mock_contact_repository,
                                                                  mock_property_repository):
        """Test that statistics properly distinguish between contact and property operations
        
        CRITICAL: This test WILL FAIL until statistics tracking is separated by entity type.
        """
        # Arrange - Mixed scenario: some contacts exist, properties don't
        mock_contact_repository.find_by_phone.side_effect = [
            Mock(spec=Contact, id=1),  # John exists
            None,                      # Jane doesn't exist
            None,                      # Bob doesn't exist  
            Mock(spec=Contact, id=2)   # Alice exists
        ]
        
        mock_contact_repository.create.side_effect = [
            Mock(spec=Contact, id=3),  # Create Jane
            Mock(spec=Contact, id=4)   # Create Bob
        ]
        
        # All properties are new
        mock_property_repository.find_by_apn.return_value = None
        mock_property_repository.find_by_address_and_zip.return_value = None
        mock_property_repository.create.side_effect = [
            Mock(spec=Property, id=1),
            Mock(spec=Property, id=2)
        ]
        
        # Act
        result = service.import_csv(sample_csv_dual_contacts, 'mixed_entities.csv', 'test_user')
        
        # Assert - This WILL FAIL until entity-specific statistics are implemented
        assert result.is_success
        stats = result.value
        
        # CRITICAL: Must track contacts and properties separately
        assert stats['contacts_created'] == 2, "Should create 2 new contacts (Jane, Bob)"
        assert stats['contacts_updated'] == 2, "Should find 2 existing contacts (John, Alice)"
        assert stats['properties_created'] == 2, "Should create 2 new properties"
        assert stats['properties_updated'] == 0, "No existing properties"
        
        # Total operations should equal actual repository calls
        total_contact_ops = stats['contacts_created'] + stats['contacts_updated']
        assert total_contact_ops == 4, "Should account for all 4 contact operations"

    def test_duplicate_handling_strategy_affects_statistics(self, service, sample_csv_dual_contacts,
                                                          mock_contact_repository,
                                                          mock_property_repository):
        """Test that different duplicate handling strategies affect statistics correctly
        
        CRITICAL: This test WILL FAIL until duplicate handling strategies are implemented.
        """
        # Arrange - All data already exists (duplicate scenario)
        existing_contacts = [
            Mock(spec=Contact, id=1, phone='+15550001'),
            Mock(spec=Contact, id=2, phone='+15550002'),
            Mock(spec=Contact, id=3, phone='+15550003'), 
            Mock(spec=Contact, id=4, phone='+15550004')
        ]
        # Use cycle to repeat the existing contacts indefinitely  
        from itertools import cycle
        mock_contact_repository.find_by_phone.side_effect = cycle(existing_contacts)
        
        existing_properties = [
            Mock(spec=Property, id=1),
            Mock(spec=Property, id=2)
        ]
        # Mock both property lookup methods - cycle through properties
        mock_property_repository.find_by_apn.return_value = None  # No APN in test data
        
        # Use cycle to repeat the existing properties indefinitely
        from itertools import cycle
        mock_property_repository.find_by_address_and_zip.side_effect = cycle(existing_properties)
        mock_property_repository.update.return_value = None  # Update doesn't return anything
        
        # Test different duplicate strategies - This WILL FAIL until strategies are implemented
        
        # Strategy 1: SKIP duplicates
        result_skip = service.import_csv(
            sample_csv_dual_contacts, 
            'skip_test.csv', 
            'test_user',
            duplicate_strategy='skip'  # New parameter
        )
        
        assert result_skip.is_success
        skip_stats = result_skip.value
        assert skip_stats['contacts_created'] == 0
        assert skip_stats['contacts_skipped'] == 4  # New statistic field
        assert skip_stats['properties_skipped'] == 2
        
        # Strategy 2: REPLACE/UPDATE duplicates  
        result_replace = service.import_csv(
            sample_csv_dual_contacts,
            'replace_test.csv',
            'test_user', 
            duplicate_strategy='replace'  # New parameter
        )
        
        assert result_replace.is_success
        replace_stats = result_replace.value
        assert replace_stats['contacts_created'] == 0
        assert replace_stats['contacts_updated'] == 4  # All existing updated
        assert replace_stats['properties_updated'] == 2

    def test_same_csv_imported_twice_shows_different_statistics(self, service, sample_csv_dual_contacts,
                                                              mock_contact_repository,
                                                              mock_property_repository):
        """Test that importing the same CSV twice shows different statistics
        
        CRITICAL: This test WILL FAIL because current system shows identical statistics for duplicate imports.
        """
        # First import - all new data
        mock_contact_repository.find_by_phone.return_value = None
        mock_property_repository.find_by_apn.return_value = None
        mock_property_repository.find_by_address_and_zip.return_value = None
        
        mock_contact_repository.create.side_effect = [
            Mock(spec=Contact, id=i) for i in range(1, 5)
        ]
        mock_property_repository.create.side_effect = [
            Mock(spec=Property, id=1),
            Mock(spec=Property, id=2)
        ]
        
        # Act - First import
        result1 = service.import_csv(sample_csv_dual_contacts, 'first.csv', 'test_user')
        
        # Reset mocks for second import
        mock_contact_repository.reset_mock()
        mock_property_repository.reset_mock()
        
        # Second import - all data now exists
        existing_contacts = [Mock(spec=Contact, id=i) for i in range(1, 5)]
        mock_contact_repository.find_by_phone.side_effect = existing_contacts
        
        existing_properties = [Mock(spec=Property, id=1), Mock(spec=Property, id=2)]
        mock_property_repository.find_by_address_and_zip.side_effect = existing_properties
        
        # Act - Second import (duplicate)
        result2 = service.import_csv(sample_csv_dual_contacts, 'second.csv', 'test_user')
        
        # Assert - This WILL FAIL because current system shows identical statistics
        assert result1.is_success and result2.is_success
        
        stats1 = result1.value
        stats2 = result2.value
        
        # CRITICAL: Statistics must be different for duplicate imports
        assert stats1['contacts_created'] == 4, "First import should create 4 contacts"
        assert stats1['contacts_updated'] == 0, "First import should update 0 contacts"
        
        assert stats2['contacts_created'] == 0, "Second import should create 0 contacts (all exist)"
        assert stats2['contacts_updated'] == 4, "Second import should find 4 existing contacts"
        
        # Statistics should NOT be identical
        assert stats1 != stats2, "Duplicate import statistics should be different from original"

    def test_contacts_updated_field_is_actually_used(self, service, sample_csv_dual_contacts,
                                                   mock_contact_repository,
                                                   mock_property_repository):
        """Test that contacts_updated field is actually incremented (currently never used)
        
        CRITICAL: This test WILL FAIL because contacts_updated is never incremented in current code.
        """
        # Arrange - All contacts exist (should trigger updates)
        existing_contacts = [
            Mock(spec=Contact, id=1, phone='+15550001', first_name='John'),
            Mock(spec=Contact, id=2, phone='+15550002', first_name='Jane'),
            Mock(spec=Contact, id=3, phone='+15550003', first_name='Bob'),
            Mock(spec=Contact, id=4, phone='+15550004', first_name='Alice')
        ]
        mock_contact_repository.find_by_phone.side_effect = existing_contacts
        
        # Properties don't exist (mixed scenario)
        mock_property_repository.find_by_apn.return_value = None
        mock_property_repository.find_by_address_and_zip.return_value = None
        mock_property_repository.create.side_effect = [Mock(spec=Property), Mock(spec=Property)]
        
        # Act
        result = service.import_csv(sample_csv_dual_contacts, 'test_updates.csv', 'test_user')
        
        # Assert - This WILL FAIL because contacts_updated is never incremented
        assert result.is_success
        stats = result.value
        
        # CRITICAL: contacts_updated MUST be used when existing contacts are found
        assert stats['contacts_created'] == 0, "No new contacts should be created"
        assert stats['contacts_updated'] == 4, "All 4 existing contacts should be counted as updated"
        assert stats['contacts_updated'] > 0, "contacts_updated field must actually be used"

    def test_properties_updated_field_is_actually_used(self, service, sample_csv_dual_contacts,
                                                     mock_contact_repository, 
                                                     mock_property_repository):
        """Test that properties_updated field is properly incremented when properties exist
        
        CRITICAL: This test verifies that existing properties are counted in properties_updated.
        """
        # Arrange - All properties exist (should trigger updates)
        existing_properties = [
            Mock(spec=Property, id=1, address='123 Main St'),
            Mock(spec=Property, id=2, address='456 Oak Ave')
        ]
        mock_property_repository.find_by_address_and_zip.side_effect = existing_properties
        mock_property_repository.update.side_effect = existing_properties
        
        # Contacts don't exist (mixed scenario)
        mock_contact_repository.find_by_phone.return_value = None
        mock_contact_repository.create.side_effect = [Mock(spec=Contact) for _ in range(4)]
        
        # Act
        result = service.import_csv(sample_csv_dual_contacts, 'test_prop_updates.csv', 'test_user')
        
        # Assert
        assert result.is_success
        stats = result.value
        
        # CRITICAL: properties_updated must be incremented for existing properties
        assert stats['properties_created'] == 0, "No new properties should be created"
        assert stats['properties_updated'] == 2, "Both existing properties should be counted as updated"
        assert stats['properties_updated'] > 0, "properties_updated field must be used"


class TestImportOperationTracking:
    """TDD RED Phase: Test operation type tracking for accurate statistics"""
    
    @pytest.fixture
    def service(self):
        """Create service with mock repositories"""
        return PropertyRadarImportService(
            property_repository=Mock(spec=PropertyRepository),
            contact_repository=Mock(spec=ContactRepository),
            csv_import_repository=Mock(spec=CSVImportRepository)
        )
    
    def test_process_contact_returns_created_operation_type(self, service):
        """Test _process_contact returns 'created' when new contact is made
        
        CRITICAL: This test WILL FAIL until _process_contact returns operation type tuple.
        """
        # Arrange
        contact_data = {'first_name': 'John', 'last_name': 'Smith', 'phone': '+15550001'}
        service.contact_repository.find_by_phone.return_value = None  # Not found
        mock_contact = Mock(spec=Contact, id=1)
        service.contact_repository.create.return_value = mock_contact
        
        # Act - This WILL FAIL until method signature changes
        result = service._process_contact(contact_data, None)
        
        # Assert - Must return tuple (contact, operation_type)
        assert isinstance(result, tuple), "_process_contact must return tuple (contact, operation_type)"
        contact, operation_type = result
        assert contact == mock_contact
        assert operation_type == 'created'
        
    def test_process_contact_returns_existing_operation_type(self, service):
        """Test _process_contact returns 'existing' when contact is found
        
        CRITICAL: This test WILL FAIL until _process_contact returns operation type tuple.
        """
        # Arrange  
        contact_data = {'first_name': 'John', 'last_name': 'Smith', 'phone': '+15550001'}
        existing_contact = Mock(spec=Contact, id=1)
        service.contact_repository.find_by_phone.return_value = existing_contact
        
        # Act - This WILL FAIL until method signature changes
        result = service._process_contact(contact_data, None)
        
        # Assert
        assert isinstance(result, tuple)
        contact, operation_type = result
        assert contact == existing_contact  
        assert operation_type == 'existing'
        
    def test_process_property_returns_created_operation_type(self, service):
        """Test _process_property returns 'created' when new property is made
        
        CRITICAL: This test WILL FAIL until _process_property returns operation type tuple.
        """
        # Arrange
        property_data = {'address': '123 Main St', 'city': 'Test', 'zip_code': '12345'}
        service.property_repository.find_by_apn.return_value = None
        service.property_repository.find_by_address_and_zip.return_value = None  
        mock_property = Mock(spec=Property, id=1)
        service.property_repository.create.return_value = mock_property
        
        # Act - This WILL FAIL until method signature changes  
        result = service._process_property(property_data)
        
        # Assert
        assert isinstance(result, tuple), "_process_property must return tuple (property, operation_type)"
        property_obj, operation_type = result
        assert property_obj == mock_property
        assert operation_type == 'created'
        
    def test_process_property_returns_updated_operation_type(self, service):
        """Test _process_property returns 'updated' when property is found and updated
        
        CRITICAL: This test WILL FAIL until _process_property returns operation type tuple.
        """
        # Arrange
        property_data = {'address': '123 Main St', 'city': 'Test', 'zip_code': '12345'}
        existing_property = Mock(spec=Property, id=1)
        service.property_repository.find_by_address_and_zip.return_value = existing_property
        service.property_repository.update.return_value = existing_property
        
        # Act - This WILL FAIL until method signature changes
        result = service._process_property(property_data)
        
        # Assert
        assert isinstance(result, tuple)
        property_obj, operation_type = result
        assert property_obj == existing_property
        assert operation_type == 'updated'

    def test_import_row_uses_operation_types_for_counting(self, service):
        """Test that import_row method uses operation types from helper methods for accurate counting
        
        CRITICAL: This test WILL FAIL until import_row uses operation type information.
        """
        # Arrange
        sample_row = {
            'Type': 'SFR', 
            'Address': '123 Main St', 
            'City': 'Test', 
            'ZIP': '12345',
            'Primary Name': 'John Smith', 
            'Primary Mobile Phone1': '555-0001',
            'Secondary Name': 'Jane Smith',
            'Secondary Mobile Phone1': '555-0002'
        }
        
        mock_csv_import = Mock(spec=CSVImport, id=1, contacts=[])
        
        # Mock the helper methods to return operation types
        with patch.object(service, '_process_property') as mock_process_prop, \
             patch.object(service, '_process_contact') as mock_process_contact:
            
            mock_process_prop.return_value = (Mock(spec=Property, id=1), 'created')
            mock_process_contact.side_effect = [
                (Mock(spec=Contact, id=1), 'created'),    # Primary contact created
                (Mock(spec=Contact, id=2), 'existing')    # Secondary contact exists
            ]
            
            # Act - This WILL FAIL until import_row uses operation types
            result = service.import_row(sample_row, mock_csv_import)
        
        # Assert
        assert result.is_success
        result_data = result.value
        
        # CRITICAL: Result must include operation type information for statistics
        assert 'property_operation' in result_data, "Result must include property operation type"
        assert 'primary_contact_operation' in result_data, "Result must include primary contact operation type"
        assert 'secondary_contact_operation' in result_data, "Result must include secondary contact operation type"
        
        # Verify the operation types are correct based on mocks
        assert result_data['property_operation'] == 'created'
        assert result_data['primary_contact_operation'] == 'created'
        assert result_data['secondary_contact_operation'] == 'existing'