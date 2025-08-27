"""
Import Progress Tracking TDD Tests - RED PHASE
TDD CRITICAL: These tests MUST fail initially - implementation comes AFTER tests

PROBLEM IDENTIFIED:
- Progress callback may use inflated contact counts instead of row numbers
- Progress can exceed 100% when dual-contact rows inflate the numerator
- Progress calculation is inconsistent between numerator and denominator sources

TESTING STRATEGY:
1. Test that progress uses ROW numbers for both numerator and denominator
2. Test that progress never exceeds 100%
3. Test that dual-contact rows don't inflate progress
4. Test progress accuracy with different CSV structures

These tests enforce that progress tracking must be based on CSV row processing,
not on the number of entities (contacts/properties) created from those rows.
"""

import pytest
from unittest.mock import Mock, patch, call
from datetime import datetime

from services.propertyradar_import_service import PropertyRadarImportService
from repositories.property_repository import PropertyRepository
from repositories.contact_repository import ContactRepository
from repositories.csv_import_repository import CSVImportRepository
from crm_database import Property, Contact, CSVImport
from services.common.result import Result


class TestImportProgressTracking:
    """TDD RED Phase: Test that progress tracking uses row numbers correctly"""
    
    @pytest.fixture
    def mock_repositories(self):
        """Create mock repositories for testing"""
        property_repo = Mock(spec=PropertyRepository)
        contact_repo = Mock(spec=ContactRepository)
        csv_import_repo = Mock(spec=CSVImportRepository)
        
        # Mock successful operations by default
        property_repo.find_by_apn.return_value = None
        property_repo.find_by_address_and_zip.return_value = None
        property_repo.create.return_value = Mock(spec=Property, id=1)
        
        contact_repo.find_by_phone.return_value = None
        contact_repo.create.return_value = Mock(spec=Contact, id=1)
        
        mock_csv_import = Mock(spec=CSVImport, id=1, contacts=[])
        csv_import_repo.create.return_value = mock_csv_import
        
        return {
            'property': property_repo,
            'contact': contact_repo,
            'csv_import': csv_import_repo
        }
    
    @pytest.fixture
    def service(self, mock_repositories):
        """Create service instance with mocked dependencies"""
        return PropertyRadarImportService(
            property_repository=mock_repositories['property'],
            contact_repository=mock_repositories['contact'],
            csv_import_repository=mock_repositories['csv_import']
        )
    
    @pytest.fixture
    def single_contact_csv(self):
        """CSV with 3 rows, each with only primary contact (3 rows = 3 contacts)"""
        return """Type,Address,City,ZIP,Primary Name,Primary Mobile Phone1,Secondary Name,Secondary Mobile Phone1
SFR,123 Main St,City,12345,John Smith,555-0001,,
SFR,456 Oak Ave,City,67890,Jane Doe,555-0002,,
SFR,789 Pine Rd,City,11111,Bob Johnson,555-0003,,"""

    @pytest.fixture 
    def dual_contact_csv(self):
        """CSV with 3 rows, each with both primary and secondary contacts (3 rows = 6 contacts)"""
        return """Type,Address,City,ZIP,Primary Name,Primary Mobile Phone1,Secondary Name,Secondary Mobile Phone1
SFR,123 Main St,City,12345,John Smith,555-0001,Jane Smith,555-0002
SFR,456 Oak Ave,City,67890,Bob Johnson,555-0003,Alice Johnson,555-0004
SFR,789 Pine Rd,City,11111,Charlie Wilson,555-0005,Diana Wilson,555-0006"""

    @pytest.fixture
    def mixed_contact_csv(self):
        """CSV with 4 rows, mixed contact patterns (4 rows = 6 contacts total)"""
        return """Type,Address,City,ZIP,Primary Name,Primary Mobile Phone1,Secondary Name,Secondary Mobile Phone1
SFR,123 Main St,City,12345,John Smith,555-0001,Jane Smith,555-0002
SFR,456 Oak Ave,City,67890,Bob Johnson,555-0003,,
SFR,789 Pine Rd,City,11111,,Charlie Wilson,555-0004
SFR,321 Elm St,City,22222,Diana Wilson,555-0005,Frank Wilson,555-0006"""

    def test_progress_uses_row_numbers_not_contact_counts_single_contacts(self, service, single_contact_csv):
        """Test progress tracking with single contacts per row (1:1 ratio)
        
        CRITICAL: This test WILL FAIL if progress uses contact counts instead of row numbers.
        """
        # Arrange
        progress_calls = []
        
        def capture_progress(processed, total):
            progress_calls.append((processed, total))
            
        # Act
        result = service.import_csv(
            single_contact_csv,
            'single_contact_test.csv',
            'test_user',
            progress_callback=capture_progress
        )
        
        # Assert
        assert result.is_success
        assert len(progress_calls) > 0, "Progress callback should be called"
        
        # CRITICAL: Total should always be number of CSV rows (3), not contacts (3)
        for processed, total in progress_calls:
            assert total == 3, f"Total should be 3 CSV rows, got {total}"
            assert processed <= total, f"Processed {processed} should not exceed total {total}"
            
        # Final progress should show all rows processed
        final_processed, final_total = progress_calls[-1]
        assert final_processed == 3, "Should process all 3 rows"
        assert final_total == 3, "Total should remain 3 rows"

    def test_progress_uses_row_numbers_not_contact_counts_dual_contacts(self, service, dual_contact_csv):
        """Test progress tracking with dual contacts per row (1:2 ratio)
        
        CRITICAL: This test WILL FAIL if progress uses contact counts (6) instead of row numbers (3).
        """
        # Arrange
        progress_calls = []
        
        def capture_progress(processed, total):
            progress_calls.append((processed, total))
            
        # Act
        result = service.import_csv(
            dual_contact_csv,
            'dual_contact_test.csv', 
            'test_user',
            progress_callback=capture_progress
        )
        
        # Assert
        assert result.is_success
        assert len(progress_calls) > 0, "Progress callback should be called"
        
        # CRITICAL: Total must be CSV rows (3), NOT contact count (6)
        for processed, total in progress_calls:
            assert total == 3, f"Total should be 3 CSV rows, NOT 6 contacts. Got {total}"
            assert processed <= 3, f"Processed should be ≤ 3 rows, got {processed}"
            
        # Final progress should show row-based completion
        final_processed, final_total = progress_calls[-1]
        assert final_processed == 3, "Should process all 3 rows"
        assert final_total == 3, "Total should be 3 rows, not 6 contacts"

    def test_progress_never_exceeds_100_percent_with_dual_contacts(self, service, dual_contact_csv):
        """Test that progress percentage never exceeds 100% even with dual contacts
        
        CRITICAL: This test WILL FAIL if dual contacts inflate progress beyond 100%.
        """
        # Arrange
        progress_calls = []
        max_percentage = 0
        
        def capture_and_calculate_progress(processed, total):
            progress_calls.append((processed, total))
            nonlocal max_percentage
            percentage = (processed / total) * 100 if total > 0 else 0
            max_percentage = max(max_percentage, percentage)
            
        # Act
        result = service.import_csv(
            dual_contact_csv,
            'progress_limit_test.csv',
            'test_user', 
            progress_callback=capture_and_calculate_progress
        )
        
        # Assert
        assert result.is_success
        
        # CRITICAL: Progress percentage must never exceed 100%
        assert max_percentage <= 100.0, f"Progress reached {max_percentage}%, which exceeds 100%"
        
        # Verify all individual progress calls are valid
        for processed, total in progress_calls:
            percentage = (processed / total) * 100 if total > 0 else 0
            assert percentage <= 100.0, f"Progress call ({processed}/{total}) = {percentage}% exceeds 100%"

    def test_progress_consistency_with_mixed_contact_patterns(self, service, mixed_contact_csv):
        """Test progress consistency with mixed contact patterns per row
        
        CRITICAL: This test WILL FAIL if progress calculation is inconsistent.
        """
        # Arrange
        progress_calls = []
        
        def capture_progress(processed, total):
            progress_calls.append((processed, total))
            
        # Act
        result = service.import_csv(
            mixed_contact_csv,
            'mixed_progress_test.csv',
            'test_user',
            progress_callback=capture_progress
        )
        
        # Assert
        assert result.is_success
        
        # CRITICAL: Total must remain consistent throughout (4 rows)
        total_values = [total for _, total in progress_calls]
        assert all(total == 4 for total in total_values), \
            f"Total should be consistently 4 rows, got varying values: {set(total_values)}"
        
        # Processed values should increase monotonically (never decrease)
        processed_values = [processed for processed, _ in progress_calls]
        for i in range(1, len(processed_values)):
            assert processed_values[i] >= processed_values[i-1], \
                f"Processed count should never decrease: {processed_values[i-1]} → {processed_values[i]}"
        
        # Final progress should show all rows processed
        final_processed, final_total = progress_calls[-1]
        assert final_processed == 4, "Should process all 4 rows"
        assert final_total == 4, "Total should be 4 rows"

    def test_progress_callback_called_at_appropriate_intervals(self, service, dual_contact_csv):
        """Test that progress callback is called at reasonable intervals
        
        CRITICAL: This test verifies callback frequency is based on row processing.
        """
        # Arrange
        progress_calls = []
        
        def capture_progress_with_timestamp(processed, total):
            progress_calls.append({
                'processed': processed,
                'total': total,
                'timestamp': datetime.now()
            })
            
        # Act
        result = service.import_csv(
            dual_contact_csv,
            'callback_interval_test.csv',
            'test_user',
            progress_callback=capture_progress_with_timestamp
        )
        
        # Assert
        assert result.is_success
        assert len(progress_calls) > 0, "Progress callback should be called"
        
        # Should have reasonable number of calls (not one per contact created)
        assert len(progress_calls) <= 10, f"Too many progress calls ({len(progress_calls)}) for 3 rows"
        
        # Progress values should be based on row processing
        for call in progress_calls:
            assert call['total'] == 3, f"Each call should show 3 total rows, got {call['total']}"
            assert call['processed'] <= 3, f"Processed should be ≤ 3 rows, got {call['processed']}"

    def test_progress_with_batch_processing_uses_row_numbers(self, service):
        """Test that batch processing progress still uses row numbers correctly
        
        CRITICAL: This test WILL FAIL if batch processing inflates progress with contact counts.
        """
        # Arrange - Create larger CSV for batch processing
        large_csv_lines = ['Type,Address,City,ZIP,Primary Name,Primary Mobile Phone1,Secondary Name,Secondary Mobile Phone1']
        for i in range(10):  # 10 rows
            large_csv_lines.append(f'SFR,{i} Test St,City,12345,User {i},555-{i:04d},Spouse {i},555-{i+100:04d}')
        large_csv = '\n'.join(large_csv_lines)
        
        progress_calls = []
        
        def capture_progress(processed, total):
            progress_calls.append((processed, total))
            
        # Act - Use small batch size to trigger multiple batch operations
        result = service.import_csv(
            large_csv,
            'batch_progress_test.csv',
            'test_user',
            batch_size=3,  # Process in batches of 3
            progress_callback=capture_progress
        )
        
        # Assert
        assert result.is_success
        
        # CRITICAL: All progress calls should show 10 total rows, NOT 20 contacts
        for processed, total in progress_calls:
            assert total == 10, f"Batch processing should show 10 total rows, got {total}"
            assert processed <= 10, f"Processed should be ≤ 10 rows, got {processed}"
        
        # Final progress should complete all rows
        if progress_calls:
            final_processed, final_total = progress_calls[-1]
            assert final_processed == 10, "Should complete all 10 rows"
            assert final_total == 10, "Total should remain 10 rows"

    def test_progress_accuracy_with_failed_rows(self, service, dual_contact_csv, mock_repositories):
        """Test that progress remains accurate even when some rows fail
        
        CRITICAL: This test verifies progress is based on row attempts, not successful operations.
        """
        # Arrange - Make second row fail
        def mock_create_contact(**kwargs):
            if kwargs.get('phone') == '+15550003':  # Bob Johnson's phone
                raise Exception("Simulated contact creation failure")
            return Mock(spec=Contact, id=1)
            
        mock_repositories['contact'].create.side_effect = mock_create_contact
        
        progress_calls = []
        
        def capture_progress(processed, total):
            progress_calls.append((processed, total))
            
        # Act
        result = service.import_csv(
            dual_contact_csv,
            'failed_row_progress_test.csv',
            'test_user',
            progress_callback=capture_progress
        )
        
        # Assert - Import may succeed or fail, but progress should be consistent
        if result.is_success and len(result.value.get('errors', [])) > 0:
            # Partial success scenario
            pass
        elif result.is_failure:
            # Complete failure scenario
            pass
        
        # CRITICAL: Progress should still be based on row attempts, not success count
        if progress_calls:
            for processed, total in progress_calls:
                assert total == 3, f"Total should remain 3 rows even with failures, got {total}"
                assert processed <= 3, f"Processed should be ≤ 3 rows, got {processed}"

    def test_progress_with_zero_rows_handles_gracefully(self, service):
        """Test that progress handles empty CSV gracefully
        
        CRITICAL: This test verifies edge case handling.
        """
        # Arrange
        empty_csv = "Type,Address,City,ZIP,Primary Name,Primary Mobile Phone1,Secondary Name,Secondary Mobile Phone1"
        
        progress_calls = []
        
        def capture_progress(processed, total):
            progress_calls.append((processed, total))
            
        # Act
        result = service.import_csv(
            empty_csv,
            'empty_progress_test.csv',
            'test_user',
            progress_callback=capture_progress
        )
        
        # Assert - May succeed with zero operations or fail
        # Progress should handle zero total gracefully
        for processed, total in progress_calls:
            assert processed >= 0, "Processed should not be negative"
            assert total >= 0, "Total should not be negative"
            if total > 0:
                percentage = (processed / total) * 100
                assert percentage <= 100.0, "Percentage should not exceed 100%"

    def test_progress_callback_receives_correct_data_types(self, service, single_contact_csv):
        """Test that progress callback receives integer values
        
        CRITICAL: This test verifies callback parameter data types.
        """
        # Arrange
        progress_calls = []
        
        def capture_and_validate_progress(processed, total):
            # Validate data types
            assert isinstance(processed, int), f"Processed should be int, got {type(processed)}"
            assert isinstance(total, int), f"Total should be int, got {type(total)}"
            progress_calls.append((processed, total))
            
        # Act
        result = service.import_csv(
            single_contact_csv,
            'data_type_test.csv',
            'test_user',
            progress_callback=capture_and_validate_progress
        )
        
        # Assert
        assert result.is_success
        assert len(progress_calls) > 0, "Progress callback should be called with valid data types"

    def test_progress_without_callback_still_works(self, service, single_contact_csv):
        """Test that import works normally without progress callback
        
        CRITICAL: This test verifies callback is optional.
        """
        # Act - No progress_callback parameter
        result = service.import_csv(
            single_contact_csv,
            'no_callback_test.csv',
            'test_user'
            # No progress_callback
        )
        
        # Assert
        assert result.is_success, "Import should work without progress callback"
        stats = result.value
        assert 'total_rows' in stats
        assert stats['total_rows'] == 3


class TestProgressCalculationLogic:
    """TDD RED Phase: Test internal progress calculation logic"""
    
    @pytest.fixture
    def service(self):
        """Create service for testing progress calculation logic"""
        return PropertyRadarImportService(
            property_repository=Mock(spec=PropertyRepository),
            contact_repository=Mock(spec=ContactRepository),
            csv_import_repository=Mock(spec=CSVImportRepository)
        )
    
    def test_progress_calculation_method_exists(self, service):
        """Test that progress calculation helper method exists and works correctly
        
        CRITICAL: This test WILL FAIL until progress calculation method is implemented.
        """
        # Act - This WILL FAIL until method exists
        progress_percent = service._calculate_progress(5, 10)
        
        # Assert
        assert progress_percent == 50.0, "Should calculate 50% progress"
        
        # Test edge cases
        assert service._calculate_progress(0, 10) == 0.0, "Should handle zero processed"
        assert service._calculate_progress(10, 10) == 100.0, "Should handle complete progress"
        assert service._calculate_progress(0, 0) == 0.0, "Should handle zero total gracefully"
        
    def test_progress_update_frequency_logic(self, service):
        """Test that progress updates are called at appropriate frequencies
        
        CRITICAL: This test WILL FAIL until frequency logic is implemented.
        """
        # Arrange
        callback_calls = []
        
        def mock_callback(processed, total):
            callback_calls.append((processed, total))
        
        # Act - This WILL FAIL until frequency logic exists
        # Test calling progress update logic directly
        for row_num in range(1, 21):  # Simulate 20 rows
            should_update = service._should_update_progress(row_num, 20)
            if should_update:
                mock_callback(row_num, 20)
        
        # Assert
        # Should not call callback for every single row (performance)
        assert len(callback_calls) < 20, "Should not call progress for every row"
        assert len(callback_calls) >= 2, "Should call progress at least at start and end"
        
        # Should include final progress
        final_call = callback_calls[-1]
        assert final_call == (20, 20), "Final progress should show completion"

    def test_row_counting_logic_ignores_contact_multiplicity(self, service):
        """Test that row counting logic ignores how many contacts per row
        
        CRITICAL: This test WILL FAIL until row counting is separated from entity counting.
        """
        # Mock CSV rows with different contact patterns
        rows = [
            {'Primary Name': 'John', 'Primary Mobile Phone1': '555-0001', 'Secondary Name': '', 'Secondary Mobile Phone1': ''},  # 1 contact
            {'Primary Name': 'Jane', 'Primary Mobile Phone1': '555-0002', 'Secondary Name': 'Bob', 'Secondary Mobile Phone1': '555-0003'},  # 2 contacts
            {'Primary Name': '', 'Primary Mobile Phone1': '', 'Secondary Name': 'Alice', 'Secondary Mobile Phone1': '555-0004'},  # 1 contact
        ]
        
        # Act - This WILL FAIL until row counting logic exists
        total_rows = service._count_csv_rows(rows)
        
        # Assert
        assert total_rows == 3, "Should count 3 rows regardless of contact multiplicity"
        
        # Test with parsed contacts
        contacts_per_row = [
            service._count_contacts_in_row(row) for row in rows
        ]
        assert contacts_per_row == [1, 2, 1], "Should count contacts per row correctly"
        
        # But total progress denominator should still be row count
        progress_denominator = service._get_progress_denominator(rows)
        assert progress_denominator == 3, "Progress denominator should be row count, not contact count"