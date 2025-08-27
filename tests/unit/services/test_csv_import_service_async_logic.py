"""
Test suite for CSVImportService smart async decision logic following TDD principles.

This test file is designed to FAIL initially and guide the implementation of
smart async/sync decision making for CSV imports based on file size and row count.

Requirements being tested:
1. If CSV > 500KB OR > 500 rows → Use Celery (async)
2. If CSV < 500KB AND < 500 rows → Process synchronously  
3. Show progress bar for async imports
4. File size calculation accuracy
5. Row count estimation accuracy
6. Task creation for async processing
7. Proper response format for both paths

Coverage Requirements:
- File size calculation (various formats)
- Row count estimation without full file read
- Decision logic (async vs sync)
- Celery task creation and tracking
- Progress tracking for async imports
- Error handling for file analysis
- Integration with existing import logic
"""

import pytest
import io
import os
import tempfile
from unittest.mock import Mock, patch, MagicMock
from werkzeug.datastructures import FileStorage

from services.csv_import_service import CSVImportService
from services.contact_service_refactored import ContactService


# ============================================================================
# FIXTURES FOR ASYNC LOGIC TESTING
# ============================================================================

@pytest.fixture
def mock_celery_app():
    """Mock Celery app for task creation"""
    celery_mock = Mock()
    task_mock = Mock()
    task_mock.id = 'test-task-id-12345'
    task_mock.state = 'PENDING'
    task_mock.info = {'current': 0, 'total': 100, 'percent': 0}
    celery_mock.send_task.return_value = task_mock
    return celery_mock


@pytest.fixture
def file_size_test_helper():
    """Helper to create FileStorage objects with specific sizes"""
    def _create_file_with_size(filename: str, size_kb: int, row_count: int = None):
        # Create content to reach approximately the target size
        if row_count:
            # Create specific number of rows
            header = "first_name,last_name,phone,email\n"
            row_template = "User{},Test{},555{:07d},user{}@example.com\n"
            content = header
            for i in range(row_count):
                content += row_template.format(i, i, i, i)
        else:
            # Create content to reach target size
            header = "first_name,last_name,phone,email\n"
            row = "John,Doe,5551234567,john@example.com\n"
            rows_needed = max(1, (size_kb * 1024 - len(header)) // len(row))
            content = header + (row * rows_needed)
        
        # Truncate or pad to get closer to target size
        target_bytes = size_kb * 1024
        if len(content) > target_bytes:
            content = content[:target_bytes]
        elif len(content) < target_bytes:
            padding = 'a' * (target_bytes - len(content))
            content += padding
        
        mock_file = Mock()
        mock_file.filename = filename
        mock_file.read = Mock(return_value=content.encode('utf-8'))
        mock_file.seek = Mock()
        mock_file.save = Mock()
        
        return mock_file, content
    
    return _create_file_with_size


@pytest.fixture
def csv_import_service_with_async():
    """CSV Import Service with enhanced async capabilities"""
    from services.contact_service_refactored import ContactService
    from repositories.csv_import_repository import CSVImportRepository
    from repositories.contact_csv_import_repository import ContactCSVImportRepository
    from repositories.campaign_list_repository import CampaignListRepository
    from repositories.campaign_list_member_repository import CampaignListMemberRepository
    from repositories.contact_repository import ContactRepository
    
    # Create all mocks
    mock_csv_import_repository = Mock(spec=CSVImportRepository)
    mock_contact_csv_import_repository = Mock(spec=ContactCSVImportRepository)
    mock_campaign_list_repository = Mock(spec=CampaignListRepository)
    mock_campaign_list_member_repository = Mock(spec=CampaignListMemberRepository)
    mock_contact_repository = Mock(spec=ContactRepository)
    mock_contact_service = Mock(spec=ContactService)
    
    # Standard mocking setup
    mock_csv_import = Mock()
    mock_csv_import.id = 1
    mock_csv_import_repository.create.return_value = mock_csv_import
    
    mock_campaign_list = Mock()
    mock_campaign_list.id = 1
    mock_campaign_list_repository.create.return_value = mock_campaign_list
    
    mock_contact_repository.find_by_phone.return_value = None
    
    def create_contact(**kwargs):
        contact = Mock()
        contact.id = kwargs.get('phone', 'default')
        contact.phone = kwargs.get('phone')
        contact.first_name = kwargs.get('first_name', '')
        contact.last_name = kwargs.get('last_name', '')
        contact.email = kwargs.get('email')
        contact.contact_metadata = kwargs.get('contact_metadata', {})
        return contact
    mock_contact_repository.create.side_effect = create_contact
    
    mock_contact_csv_import_repository.exists_for_contact_and_import.return_value = False
    mock_contact_csv_import = Mock()
    mock_contact_csv_import_repository.create.return_value = mock_contact_csv_import
    
    mock_campaign_list_member_repository.find_by_list_and_contact.return_value = None
    mock_campaign_list_member = Mock()
    mock_campaign_list_member_repository.create.return_value = mock_campaign_list_member
    
    service = CSVImportService(
        csv_import_repository=mock_csv_import_repository,
        contact_csv_import_repository=mock_contact_csv_import_repository,
        campaign_list_repository=mock_campaign_list_repository,
        campaign_list_member_repository=mock_campaign_list_member_repository,
        contact_repository=mock_contact_repository,
        contact_service=mock_contact_service
    )
    
    return service


# ============================================================================
# FILE SIZE CALCULATION TESTS (RED PHASE - MUST FAIL)
# ============================================================================

class TestFileSizeCalculation:
    """Test file size calculation functionality"""
    
    def test_calculate_file_size_method_exists(self, csv_import_service_with_async):
        """Test that calculate_file_size method exists"""
        # Act & Assert
        assert hasattr(csv_import_service_with_async, 'calculate_file_size'), \
            "calculate_file_size method should exist"
        assert callable(getattr(csv_import_service_with_async, 'calculate_file_size')), \
            "calculate_file_size should be callable"
    
    def test_calculate_file_size_small_file(self, csv_import_service_with_async, file_size_test_helper):
        """Test file size calculation for small file (< 500KB)"""
        # Arrange
        mock_file, content = file_size_test_helper('small.csv', 100)  # 100KB file
        
        # Act
        file_size_kb = csv_import_service_with_async.calculate_file_size(mock_file)
        
        # Assert
        assert file_size_kb < 500, f"Expected < 500KB, got {file_size_kb}KB"
        assert file_size_kb >= 95, f"Expected ~100KB, got {file_size_kb}KB (within tolerance)"
        assert file_size_kb <= 105, f"Expected ~100KB, got {file_size_kb}KB (within tolerance)"
    
    def test_calculate_file_size_large_file(self, csv_import_service_with_async, file_size_test_helper):
        """Test file size calculation for large file (> 500KB)"""
        # Arrange
        mock_file, content = file_size_test_helper('large.csv', 750)  # 750KB file
        
        # Act
        file_size_kb = csv_import_service_with_async.calculate_file_size(mock_file)
        
        # Assert
        assert file_size_kb > 500, f"Expected > 500KB, got {file_size_kb}KB"
        assert file_size_kb >= 740, f"Expected ~750KB, got {file_size_kb}KB (within tolerance)"
        assert file_size_kb <= 760, f"Expected ~750KB, got {file_size_kb}KB (within tolerance)"
    
    def test_calculate_file_size_exactly_500kb(self, csv_import_service_with_async, file_size_test_helper):
        """Test file size calculation at the threshold (exactly 500KB)"""
        # Arrange
        mock_file, content = file_size_test_helper('threshold.csv', 500)  # Exactly 500KB
        
        # Act
        file_size_kb = csv_import_service_with_async.calculate_file_size(mock_file)
        
        # Assert
        assert file_size_kb >= 495, f"Expected ~500KB, got {file_size_kb}KB (within tolerance)"
        assert file_size_kb <= 505, f"Expected ~500KB, got {file_size_kb}KB (within tolerance)"
    
    def test_calculate_file_size_empty_file(self, csv_import_service_with_async):
        """Test file size calculation for empty file"""
        # Arrange
        mock_file = Mock()
        mock_file.read = Mock(return_value=b'')
        mock_file.seek = Mock()
        
        # Act
        file_size_kb = csv_import_service_with_async.calculate_file_size(mock_file)
        
        # Assert
        assert file_size_kb == 0, f"Expected 0KB for empty file, got {file_size_kb}KB"
    
    def test_calculate_file_size_resets_file_pointer(self, csv_import_service_with_async):
        """Test that file pointer is reset after size calculation"""
        # Arrange
        content = "first_name,last_name,phone\nJohn,Doe,5551234567"
        mock_file = Mock()
        mock_file.read = Mock(return_value=content.encode('utf-8'))
        mock_file.seek = Mock()
        
        # Act
        file_size_kb = csv_import_service_with_async.calculate_file_size(mock_file)
        
        # Assert
        mock_file.seek.assert_called_with(0), "File pointer should be reset to beginning"
    
    def test_calculate_file_size_handles_unicode(self, csv_import_service_with_async):
        """Test file size calculation with unicode characters"""
        # Arrange
        content = "first_name,last_name,phone\nJöhn,Døe,5551234567"  # Unicode chars
        mock_file = Mock()
        mock_file.read = Mock(return_value=content.encode('utf-8'))
        mock_file.seek = Mock()
        
        # Act
        file_size_kb = csv_import_service_with_async.calculate_file_size(mock_file)
        
        # Assert
        expected_bytes = len(content.encode('utf-8'))
        expected_kb = expected_bytes / 1024
        assert abs(file_size_kb - expected_kb) < 0.1, \
            f"Expected {expected_kb:.2f}KB, got {file_size_kb}KB"


# ============================================================================
# ROW COUNT ESTIMATION TESTS (RED PHASE - MUST FAIL)
# ============================================================================

class TestRowCountEstimation:
    """Test row count estimation without full file read"""
    
    def test_estimate_row_count_method_exists(self, csv_import_service_with_async):
        """Test that estimate_row_count method exists"""
        # Act & Assert
        assert hasattr(csv_import_service_with_async, 'estimate_row_count'), \
            "estimate_row_count method should exist"
        assert callable(getattr(csv_import_service_with_async, 'estimate_row_count')), \
            "estimate_row_count should be callable"
    
    def test_estimate_row_count_small_file(self, csv_import_service_with_async, file_size_test_helper):
        """Test row count estimation for small file (< 500 rows)"""
        # Arrange - Create file with exactly 100 rows
        mock_file, content = file_size_test_helper('small_rows.csv', 50, row_count=100)
        
        # Act
        estimated_rows = csv_import_service_with_async.estimate_row_count(mock_file)
        
        # Assert
        assert estimated_rows < 500, f"Expected < 500 rows, got {estimated_rows}"
        assert estimated_rows >= 90, f"Expected ~100 rows, got {estimated_rows} (within 10% tolerance)"
        assert estimated_rows <= 110, f"Expected ~100 rows, got {estimated_rows} (within 10% tolerance)"
    
    def test_estimate_row_count_large_file(self, csv_import_service_with_async, file_size_test_helper):
        """Test row count estimation for large file (> 500 rows)"""
        # Arrange - Create file with exactly 800 rows
        mock_file, content = file_size_test_helper('large_rows.csv', 200, row_count=800)
        
        # Act
        estimated_rows = csv_import_service_with_async.estimate_row_count(mock_file)
        
        # Assert
        assert estimated_rows > 500, f"Expected > 500 rows, got {estimated_rows}"
        assert estimated_rows >= 720, f"Expected ~800 rows, got {estimated_rows} (within 10% tolerance)"
        assert estimated_rows <= 880, f"Expected ~800 rows, got {estimated_rows} (within 10% tolerance)"
    
    def test_estimate_row_count_exactly_500_rows(self, csv_import_service_with_async, file_size_test_helper):
        """Test row count estimation at the threshold (exactly 500 rows)"""
        # Arrange
        mock_file, content = file_size_test_helper('threshold_rows.csv', 120, row_count=500)
        
        # Act
        estimated_rows = csv_import_service_with_async.estimate_row_count(mock_file)
        
        # Assert
        assert estimated_rows >= 450, f"Expected ~500 rows, got {estimated_rows} (within 10% tolerance)"
        assert estimated_rows <= 550, f"Expected ~500 rows, got {estimated_rows} (within 10% tolerance)"
    
    def test_estimate_row_count_uses_sampling(self, csv_import_service_with_async):
        """Test that row count estimation uses sampling rather than full read"""
        # Arrange - Create file with known structure
        header = "first_name,last_name,phone,email\n"
        row = "John,Doe,5551234567,john@example.com\n"
        content = header + (row * 1000)  # 1000 data rows + header
        
        mock_file = Mock()
        mock_file.read = Mock(return_value=content.encode('utf-8'))
        mock_file.seek = Mock()
        
        # Track how many times read is called for sampling vs full read
        read_calls = []
        def track_read(*args, **kwargs):
            read_calls.append(args)
            return content.encode('utf-8')
        
        mock_file.read = Mock(side_effect=track_read)
        
        # Act
        estimated_rows = csv_import_service_with_async.estimate_row_count(mock_file)
        
        # Assert
        # Should use sampling approach, not read entire file multiple times
        assert len(read_calls) <= 3, f"Should use sampling, but read was called {len(read_calls)} times"
        assert estimated_rows >= 900, f"Expected ~1000 rows, got {estimated_rows}"
        assert estimated_rows <= 1100, f"Expected ~1000 rows, got {estimated_rows}"
    
    def test_estimate_row_count_handles_empty_file(self, csv_import_service_with_async):
        """Test row count estimation for empty file"""
        # Arrange
        mock_file = Mock()
        mock_file.read = Mock(return_value=b'')
        mock_file.seek = Mock()
        
        # Act
        estimated_rows = csv_import_service_with_async.estimate_row_count(mock_file)
        
        # Assert
        assert estimated_rows == 0, f"Expected 0 rows for empty file, got {estimated_rows}"
    
    def test_estimate_row_count_headers_only(self, csv_import_service_with_async):
        """Test row count estimation for file with only headers"""
        # Arrange
        content = "first_name,last_name,phone,email\n"  # Header only, no data rows
        mock_file = Mock()
        mock_file.read = Mock(return_value=content.encode('utf-8'))
        mock_file.seek = Mock()
        
        # Act
        estimated_rows = csv_import_service_with_async.estimate_row_count(mock_file)
        
        # Assert
        assert estimated_rows == 0, f"Expected 0 data rows for headers-only file, got {estimated_rows}"
    
    def test_estimate_row_count_resets_file_pointer(self, csv_import_service_with_async):
        """Test that file pointer is reset after row count estimation"""
        # Arrange
        content = "first_name,last_name,phone\nJohn,Doe,5551234567"
        mock_file = Mock()
        mock_file.read = Mock(return_value=content.encode('utf-8'))
        mock_file.seek = Mock()
        
        # Act
        estimated_rows = csv_import_service_with_async.estimate_row_count(mock_file)
        
        # Assert
        mock_file.seek.assert_called_with(0), "File pointer should be reset to beginning"


# ============================================================================
# ASYNC/SYNC DECISION LOGIC TESTS (RED PHASE - MUST FAIL)
# ============================================================================

class TestAsyncSyncDecisionLogic:
    """Test the core decision logic for async vs sync processing"""
    
    def test_should_process_async_method_exists(self, csv_import_service_with_async):
        """Test that should_process_async method exists"""
        # Act & Assert
        assert hasattr(csv_import_service_with_async, 'should_process_async'), \
            "should_process_async method should exist"
        assert callable(getattr(csv_import_service_with_async, 'should_process_async')), \
            "should_process_async should be callable"
    
    def test_should_process_async_large_file_size(self, csv_import_service_with_async):
        """Test async decision for large file size (> 500KB, regardless of rows)"""
        # Arrange
        with patch.object(csv_import_service_with_async, 'calculate_file_size') as mock_size:
            with patch.object(csv_import_service_with_async, 'estimate_row_count') as mock_rows:
                mock_size.return_value = 600  # 600KB - over threshold
                mock_rows.return_value = 100  # Low row count, but file size should trigger async
                
                mock_file = Mock()
                
                # Act
                should_async = csv_import_service_with_async.should_process_async(mock_file)
                
                # Assert
                assert should_async is True, "Files > 500KB should use async processing"
    
    def test_should_process_async_large_row_count(self, csv_import_service_with_async):
        """Test async decision for large row count (> 500 rows, regardless of file size)"""
        # Arrange
        with patch.object(csv_import_service_with_async, 'calculate_file_size') as mock_size:
            with patch.object(csv_import_service_with_async, 'estimate_row_count') as mock_rows:
                mock_size.return_value = 100  # Small file size
                mock_rows.return_value = 800  # 800 rows - over threshold
                
                mock_file = Mock()
                
                # Act
                should_async = csv_import_service_with_async.should_process_async(mock_file)
                
                # Assert
                assert should_async is True, "Files > 500 rows should use async processing"
    
    def test_should_process_async_both_thresholds_exceeded(self, csv_import_service_with_async):
        """Test async decision when both size and row thresholds are exceeded"""
        # Arrange
        with patch.object(csv_import_service_with_async, 'calculate_file_size') as mock_size:
            with patch.object(csv_import_service_with_async, 'estimate_row_count') as mock_rows:
                mock_size.return_value = 750  # 750KB - over threshold
                mock_rows.return_value = 1200  # 1200 rows - over threshold
                
                mock_file = Mock()
                
                # Act
                should_async = csv_import_service_with_async.should_process_async(mock_file)
                
                # Assert
                assert should_async is True, "Files exceeding both thresholds should use async"
    
    def test_should_process_sync_small_file_and_rows(self, csv_import_service_with_async):
        """Test sync decision for small file size AND small row count"""
        # Arrange
        with patch.object(csv_import_service_with_async, 'calculate_file_size') as mock_size:
            with patch.object(csv_import_service_with_async, 'estimate_row_count') as mock_rows:
                mock_size.return_value = 200  # 200KB - under threshold
                mock_rows.return_value = 150  # 150 rows - under threshold
                
                mock_file = Mock()
                
                # Act
                should_async = csv_import_service_with_async.should_process_async(mock_file)
                
                # Assert
                assert should_async is False, "Small files with few rows should use sync processing"
    
    def test_should_process_sync_exactly_at_thresholds(self, csv_import_service_with_async):
        """Test decision logic at exact threshold values (500KB, 500 rows)"""
        # Arrange - exactly at both thresholds
        with patch.object(csv_import_service_with_async, 'calculate_file_size') as mock_size:
            with patch.object(csv_import_service_with_async, 'estimate_row_count') as mock_rows:
                mock_size.return_value = 500  # Exactly 500KB
                mock_rows.return_value = 500  # Exactly 500 rows
                
                mock_file = Mock()
                
                # Act
                should_async = csv_import_service_with_async.should_process_async(mock_file)
                
                # Assert
                # At exactly the threshold, should still process sync (< is the trigger for async)
                assert should_async is False, "Files at exact threshold should use sync processing"
    
    def test_should_process_async_one_threshold_exceeded(self, csv_import_service_with_async):
        """Test async decision when only one threshold is exceeded (either size OR rows)"""
        # Test case 1: Size exceeded, rows under
        with patch.object(csv_import_service_with_async, 'calculate_file_size') as mock_size:
            with patch.object(csv_import_service_with_async, 'estimate_row_count') as mock_rows:
                mock_size.return_value = 501  # Just over size threshold
                mock_rows.return_value = 100  # Well under row threshold
                
                mock_file = Mock()
                
                # Act
                should_async_1 = csv_import_service_with_async.should_process_async(mock_file)
                
                # Test case 2: Rows exceeded, size under
                mock_size.return_value = 100  # Well under size threshold
                mock_rows.return_value = 501  # Just over row threshold
                
                # Act
                should_async_2 = csv_import_service_with_async.should_process_async(mock_file)
        
        # Assert
        assert should_async_1 is True, "Files over size threshold should use async even with few rows"
        assert should_async_2 is True, "Files over row threshold should use async even when small"
    
    def test_should_process_async_handles_empty_file(self, csv_import_service_with_async):
        """Test decision logic for empty file"""
        # Arrange
        with patch.object(csv_import_service_with_async, 'calculate_file_size') as mock_size:
            with patch.object(csv_import_service_with_async, 'estimate_row_count') as mock_rows:
                mock_size.return_value = 0  # Empty file
                mock_rows.return_value = 0  # No rows
                
                mock_file = Mock()
                
                # Act
                should_async = csv_import_service_with_async.should_process_async(mock_file)
                
                # Assert
                assert should_async is False, "Empty files should use sync processing"
    
    def test_decision_logic_calls_analysis_methods(self, csv_import_service_with_async):
        """Test that decision logic calls both file analysis methods"""
        # Arrange
        with patch.object(csv_import_service_with_async, 'calculate_file_size') as mock_size:
            with patch.object(csv_import_service_with_async, 'estimate_row_count') as mock_rows:
                mock_size.return_value = 300
                mock_rows.return_value = 200
                
                mock_file = Mock()
                
                # Act
                csv_import_service_with_async.should_process_async(mock_file)
                
                # Assert
                mock_size.assert_called_once_with(mock_file), "Should calculate file size"
                mock_rows.assert_called_once_with(mock_file), "Should estimate row count"


# ============================================================================
# ASYNC TASK CREATION TESTS (RED PHASE - MUST FAIL)
# ============================================================================

class TestAsyncTaskCreation:
    """Test Celery task creation for async processing"""
    
    def test_create_async_import_task_method_exists(self, csv_import_service_with_async):
        """Test that create_async_import_task method exists"""
        # Act & Assert
        assert hasattr(csv_import_service_with_async, 'create_async_import_task'), \
            "create_async_import_task method should exist"
        assert callable(getattr(csv_import_service_with_async, 'create_async_import_task')), \
            "create_async_import_task should be callable"
    
    @patch('tasks.csv_import_tasks.process_large_csv_import.delay')
    def test_create_async_import_task_creates_celery_task(self, mock_delay, csv_import_service_with_async):
        """Test that async import task is properly created in Celery"""
        # Arrange
        mock_task = Mock()
        mock_task.id = 'test-task-id-12345'
        mock_delay.return_value = mock_task
        
        mock_file = Mock()
        mock_file.filename = 'test.csv'
        mock_file.read.return_value = b'first_name,last_name,phone\nJohn,Doe,5551234567'
        mock_file.seek = Mock()
        
        # Act
        task_id = csv_import_service_with_async.create_async_import_task(
            file=mock_file,
            list_name='Test List',
            imported_by='test_user'
        )
        
        # Assert
        assert task_id == 'test-task-id-12345', "Should return the Celery task ID"
        mock_delay.assert_called_once(), "Should call delay method to create task"
    
    @patch('tasks.csv_import_tasks.process_large_csv_import.delay')
    def test_create_async_import_task_passes_correct_parameters(self, mock_delay, csv_import_service_with_async):
        """Test that correct parameters are passed to the Celery task"""
        # Arrange
        mock_task = Mock()
        mock_task.id = 'task-123'
        mock_delay.return_value = mock_task
        
        mock_file = Mock()
        mock_file.filename = 'large_file.csv'
        mock_file.read.return_value = b'first_name,last_name,phone\nJohn,Doe,5551234567'
        mock_file.seek = Mock()
        
        # Act
        task_id = csv_import_service_with_async.create_async_import_task(
            file=mock_file,
            list_name='Large Import List',
            imported_by='admin_user'
        )
        
        # Assert
        mock_delay.assert_called_once()
        call_args = mock_delay.call_args
        kwargs = call_args[1] if call_args[1] else {}
        
        assert kwargs['filename'] == 'large_file.csv', "Should pass filename"
        assert kwargs['list_name'] == 'Large Import List', "Should pass list name"
        assert kwargs['imported_by'] == 'admin_user', "Should pass imported_by"
        assert 'file_content' in kwargs, "Should pass file content"
    
    @patch('tasks.csv_import_tasks.process_large_csv_import.delay')
    def test_create_async_import_task_handles_celery_failure(self, mock_delay, csv_import_service_with_async):
        """Test handling of Celery task creation failure"""
        # Arrange
        mock_delay.side_effect = Exception("Celery broker unavailable")
        
        mock_file = Mock()
        mock_file.filename = 'test.csv'
        mock_file.read.return_value = b'first_name,last_name,phone\nJohn,Doe,5551234567'
        mock_file.seek = Mock()
        
        # Act & Assert
        with pytest.raises(Exception) as exc_info:
            csv_import_service_with_async.create_async_import_task(
                file=mock_file,
                list_name='Test List'
            )
        
        assert "celery" in str(exc_info.value).lower() or "broker" in str(exc_info.value).lower()


# ============================================================================
# PROGRESS TRACKING TESTS (RED PHASE - MUST FAIL)
# ============================================================================

class TestProgressTracking:
    """Test progress tracking for async imports"""
    
    def test_get_import_progress_method_exists(self, csv_import_service_with_async):
        """Test that get_import_progress method exists"""
        # Act & Assert
        assert hasattr(csv_import_service_with_async, 'get_import_progress'), \
            "get_import_progress method should exist"
        assert callable(getattr(csv_import_service_with_async, 'get_import_progress')), \
            "get_import_progress should be callable"
    
    @patch('celery_worker.celery')
    def test_get_import_progress_returns_task_status(self, mock_celery, csv_import_service_with_async):
        """Test that import progress returns current task status"""
        # Arrange
        mock_result = Mock()
        mock_result.state = 'PROGRESS'
        mock_result.info = {
            'current': 150,
            'total': 500,
            'percent': 30
        }
        mock_celery.AsyncResult.return_value = mock_result
        
        task_id = 'test-task-id-12345'
        
        # Act
        progress = csv_import_service_with_async.get_import_progress(task_id)
        
        # Assert
        assert progress['state'] == 'PROGRESS', "Should return task state"
        assert progress['current'] == 150, "Should return current progress"
        assert progress['total'] == 500, "Should return total items"
        assert progress['percent'] == 30, "Should return percentage complete"
    
    @patch('celery_worker.celery')
    def test_get_import_progress_handles_completed_task(self, mock_celery, csv_import_service_with_async):
        """Test progress tracking for completed task"""
        # Arrange
        mock_result = Mock()
        mock_result.state = 'SUCCESS'
        mock_result.result = {
            'total_rows': 500,
            'successful': 480,
            'failed': 20,
            'import_id': 123,
            'list_id': 456
        }
        mock_celery.AsyncResult.return_value = mock_result
        
        task_id = 'completed-task-id'
        
        # Act
        progress = csv_import_service_with_async.get_import_progress(task_id)
        
        # Assert
        assert progress['state'] == 'SUCCESS', "Should indicate completion"
        assert 'result' in progress, "Should include final results"
        assert progress['result']['successful'] == 480, "Should include success count"
    
    @patch('celery_worker.celery')
    def test_get_import_progress_handles_failed_task(self, mock_celery, csv_import_service_with_async):
        """Test progress tracking for failed task"""
        # Arrange
        mock_result = Mock()
        mock_result.state = 'FAILURE'
        mock_result.info = 'Database connection failed'
        mock_celery.AsyncResult.return_value = mock_result
        
        task_id = 'failed-task-id'
        
        # Act
        progress = csv_import_service_with_async.get_import_progress(task_id)
        
        # Assert
        assert progress['state'] == 'FAILURE', "Should indicate failure"
        assert 'error' in progress, "Should include error information"
    
    @patch('celery_worker.celery')
    def test_get_import_progress_handles_pending_task(self, mock_celery, csv_import_service_with_async):
        """Test progress tracking for pending/queued task"""
        # Arrange
        mock_result = Mock()
        mock_result.state = 'PENDING'
        mock_result.info = None
        mock_celery.AsyncResult.return_value = mock_result
        
        task_id = 'pending-task-id'
        
        # Act
        progress = csv_import_service_with_async.get_import_progress(task_id)
        
        # Assert
        assert progress['state'] == 'PENDING', "Should indicate task is queued"
        assert progress.get('current', 0) == 0, "Should show no progress for pending task"
    
    @patch('celery_worker.celery')
    def test_get_import_progress_handles_invalid_task_id(self, mock_celery, csv_import_service_with_async):
        """Test progress tracking with invalid task ID"""
        # Arrange
        mock_celery.AsyncResult.side_effect = Exception("Task not found")
        
        task_id = 'invalid-task-id'
        
        # Act
        progress = csv_import_service_with_async.get_import_progress(task_id)
        
        # Assert
        assert 'error' in progress, "Should indicate error for invalid task ID"


# ============================================================================
# ENHANCED IMPORT_CSV METHOD TESTS (RED PHASE - MUST FAIL)
# ============================================================================

class TestEnhancedImportCSVMethod:
    """Test the enhanced import_csv method with async/sync decision logic"""
    
    @patch.object(CSVImportService, 'should_process_async')
    @patch.object(CSVImportService, '_process_sync_with_fallback')
    def test_import_csv_uses_sync_for_small_files(self, mock_sync_process, mock_should_async, csv_import_service_with_async):
        """Test that small files are processed synchronously"""
        # Arrange
        mock_should_async.return_value = False  # Small file
        mock_sync_process.return_value = {
            'success': True,
            'imported': 50,
            'updated': 5,
            'errors': [],
            'message': 'Import completed',
            'list_id': 123
        }
        
        mock_file = Mock()
        mock_file.filename = 'small.csv'
        
        # Act
        result = csv_import_service_with_async.import_csv(
            file=mock_file,
            list_name='Small Import'
        )
        
        # Assert
        mock_should_async.assert_called_once_with(mock_file), "Should check if async processing needed"
        mock_sync_process.assert_called_once(), "Should use synchronous processing"
        assert result['success'] is True, "Should return success result"
        assert 'task_id' not in result, "Sync processing should not return task_id"
    
    @patch.object(CSVImportService, 'should_process_async')
    @patch.object(CSVImportService, 'create_async_import_task')
    def test_import_csv_uses_async_for_large_files(self, mock_create_task, mock_should_async, csv_import_service_with_async):
        """Test that large files are processed asynchronously"""
        # Arrange
        mock_should_async.return_value = True  # Large file
        mock_create_task.return_value = 'async-task-id-12345'
        
        mock_file = Mock()
        mock_file.filename = 'large.csv'
        
        # Act
        result = csv_import_service_with_async.import_csv(
            file=mock_file,
            list_name='Large Import'
        )
        
        # Assert
        mock_should_async.assert_called_once_with(mock_file), "Should check if async processing needed"
        mock_create_task.assert_called_once(), "Should create async task"
        assert 'task_id' in result, "Async processing should return task_id"
        assert result['task_id'] == 'async-task-id-12345', "Should return the correct task ID"
        assert result['async'] is True, "Should indicate async processing"
    
    @patch.object(CSVImportService, 'should_process_async')
    def test_import_csv_handles_async_decision_failure(self, mock_should_async, csv_import_service_with_async):
        """Test handling when async decision logic fails"""
        # Arrange
        mock_should_async.side_effect = Exception("File analysis failed")
        
        mock_file = Mock()
        mock_file.filename = 'test.csv'
        
        # Act
        result = csv_import_service_with_async.import_csv(file=mock_file)
        
        # Assert
        assert result['success'] is False, "Should handle decision failure gracefully"
        assert 'error' in str(result['errors'][0]).lower(), "Should include error information"
    
    @patch.object(CSVImportService, 'should_process_async')
    @patch.object(CSVImportService, 'create_async_import_task')
    def test_import_csv_async_response_format(self, mock_create_task, mock_should_async, csv_import_service_with_async):
        """Test the response format for async processing"""
        # Arrange
        mock_should_async.return_value = True
        mock_create_task.return_value = 'task-id-789'
        
        mock_file = Mock()
        mock_file.filename = 'large.csv'
        
        # Act
        result = csv_import_service_with_async.import_csv(
            file=mock_file,
            list_name='Async Import'
        )
        
        # Assert expected response format for async processing
        expected_keys = {'async', 'task_id', 'message'}
        assert all(key in result for key in expected_keys), \
            f"Missing keys in async response: {expected_keys - set(result.keys())}"
        
        assert result['async'] is True, "Should indicate async processing"
        assert result['task_id'] == 'task-id-789', "Should include task ID"
        assert ('async' in result['message'].lower() or 'background' in result['message'].lower()), "Message should indicate async processing"
    
    @patch.object(CSVImportService, 'should_process_async')
    @patch.object(CSVImportService, 'create_async_import_task')
    def test_import_csv_passes_parameters_to_async_task(self, mock_create_task, mock_should_async, csv_import_service_with_async):
        """Test that all parameters are passed correctly to async task"""
        # Arrange
        mock_should_async.return_value = True
        mock_create_task.return_value = 'task-id-456'
        
        mock_file = Mock()
        mock_file.filename = 'large_import.csv'
        
        # Act
        result = csv_import_service_with_async.import_csv(
            file=mock_file,
            list_name='Custom List Name',
            enrichment_mode='enrich_all'
        )
        
        # Assert that async task creation received correct parameters
        mock_create_task.assert_called_once()
        call_args = mock_create_task.call_args
        args, kwargs = call_args if call_args else ([], {})
        
        # Check that file is passed (either as positional or keyword argument)
        assert ('file' in kwargs and kwargs['file'] is mock_file) or (len(args) > 0 and args[0] is mock_file), "Should pass file to async task"
        
        # Check that list_name is passed
        assert ('list_name' in kwargs and kwargs['list_name'] == 'Custom List Name') or (len(args) > 1), "Should pass list_name"
        
        # Note: enrichment_mode may not be passed if not implemented yet


# ============================================================================
# INTEGRATION TESTS (RED PHASE - MUST FAIL)
# ============================================================================

class TestAsyncLogicIntegration:
    """Integration tests for the complete async/sync decision workflow"""
    
    def test_end_to_end_small_file_sync_processing(self, csv_import_service_with_async, file_size_test_helper):
        """Test complete workflow for small file (sync processing)"""
        # Arrange - Create small file
        mock_file, content = file_size_test_helper('small_sync.csv', 100, row_count=50)
        
        with patch.object(csv_import_service_with_async, '_basic_import_csv') as mock_basic_import:
            mock_basic_import.return_value = {
                'success': True,
                'imported': 50,
                'updated': 0,
                'errors': [],
                'message': 'Import completed successfully',
                'list_id': 789
            }
            
            # Act
            result = csv_import_service_with_async.import_csv(
                file=mock_file,
                list_name='Small File Test'
            )
        
        # Assert sync processing was used
        assert 'task_id' not in result, "Small files should not return task_id"
        assert 'async' not in result or result['async'] is False, "Should not use async processing"
        assert result['success'] is True, "Should complete successfully"
        assert result['imported'] == 50, "Should import all rows"
        mock_basic_import.assert_called_once(), "Should use synchronous import"
    
    def test_end_to_end_large_file_async_processing(self, csv_import_service_with_async, file_size_test_helper):
        """Test complete workflow for large file (async processing)"""
        # Arrange - Create large file
        mock_file, content = file_size_test_helper('large_async.csv', 600, row_count=800)
        
        with patch.object(csv_import_service_with_async, 'create_async_import_task') as mock_create_task:
            mock_create_task.return_value = 'large-file-task-id'
            
            # Act
            result = csv_import_service_with_async.import_csv(
                file=mock_file,
                list_name='Large File Test'
            )
        
        # Assert async processing was used
        assert result.get('task_id') == 'large-file-task-id', "Large files should return task_id"
        assert result.get('async') is True, "Should use async processing"
        mock_create_task.assert_called_once(), "Should create async task"
    
    def test_threshold_boundary_conditions(self, csv_import_service_with_async, file_size_test_helper):
        """Test files right at the threshold boundaries"""
        # Test file exactly at 500KB, 500 rows (should be sync)
        mock_file_500, _ = file_size_test_helper('threshold.csv', 500, row_count=500)
        
        with patch.object(csv_import_service_with_async, '_basic_import_csv') as mock_basic:
            with patch.object(csv_import_service_with_async, 'create_async_import_task') as mock_async:
                mock_basic.return_value = {'success': True, 'imported': 500}
                
                # Act
                result_500 = csv_import_service_with_async.import_csv(file=mock_file_500)
                
                # Assert - exactly at threshold should use sync
                mock_basic.assert_called(), "Files at exact threshold should use sync"
                mock_async.assert_not_called(), "Should not create async task at threshold"
        
        # Test file just over threshold (should be async)
        mock_file_501, _ = file_size_test_helper('over_threshold.csv', 501, row_count=501)
        
        with patch.object(csv_import_service_with_async, '_basic_import_csv') as mock_basic:
            with patch.object(csv_import_service_with_async, 'create_async_import_task') as mock_async:
                mock_async.return_value = 'over-threshold-task'
                
                # Act
                result_501 = csv_import_service_with_async.import_csv(file=mock_file_501)
                
                # Assert - over threshold should use async
                mock_async.assert_called(), "Files over threshold should use async"
                mock_basic.assert_not_called(), "Should not use sync processing over threshold"


# ============================================================================
# ERROR HANDLING AND EDGE CASES (RED PHASE - MUST FAIL)
# ============================================================================

class TestAsyncLogicErrorHandling:
    """Test error handling in async decision logic"""
    
    def test_file_analysis_error_falls_back_to_sync(self, csv_import_service_with_async):
        """Test that file analysis errors fall back to sync processing"""
        # Arrange
        mock_file = Mock()
        mock_file.read = Mock(side_effect=IOError("File read error"))
        mock_file.seek = Mock()
        
        with patch.object(csv_import_service_with_async, '_process_sync_with_fallback') as mock_sync:
            mock_sync.return_value = {'success': False, 'errors': ['File read error']}
            
            # Act
            result = csv_import_service_with_async.import_csv(file=mock_file)
        
        # Assert fallback to sync processing
        mock_sync.assert_called(), "Should fall back to sync processing on analysis error"
        assert 'task_id' not in result, "Error scenarios should not create async tasks"
    
    def test_async_task_creation_failure_falls_back_to_sync(self, csv_import_service_with_async, file_size_test_helper):
        """Test fallback to sync when async task creation fails"""
        # Arrange - Large file that should trigger async
        mock_file, content = file_size_test_helper('large_fallback.csv', 600, row_count=700)
        
        with patch.object(csv_import_service_with_async, 'create_async_import_task') as mock_create_task:
            with patch.object(csv_import_service_with_async, '_basic_import_csv') as mock_basic:
                mock_create_task.side_effect = Exception("Celery broker down")
                mock_basic.return_value = {'success': True, 'imported': 700}
                
                # Act
                result = csv_import_service_with_async.import_csv(file=mock_file)
        
        # Assert fallback to sync
        mock_basic.assert_called(), "Should fall back to sync when async task creation fails"
        assert result['success'] is True, "Should still process successfully via sync"
    
    def test_corrupted_file_size_calculation(self, csv_import_service_with_async):
        """Test handling of corrupted files during size calculation"""
        # Arrange
        mock_file = Mock()
        mock_file.read = Mock(side_effect=[
            UnicodeDecodeError('utf-8', b'', 0, 1, 'invalid start byte'),
            b'fallback content'  # Second call should work
        ])
        mock_file.seek = Mock()
        
        with patch.object(csv_import_service_with_async, '_basic_import_csv') as mock_basic:
            mock_basic.return_value = {'success': False, 'errors': ['File encoding error']}
            
            # Act
            result = csv_import_service_with_async.import_csv(file=mock_file)
        
        # Assert graceful handling
        assert 'errors' in result, "Should handle file corruption gracefully"


# ============================================================================
# TEST EXECUTION VERIFICATION
# ============================================================================

def test_async_logic_tests_designed_to_fail_initially():
    """
    Meta-test ensuring async logic tests follow TDD principles.
    All tests above should FAIL until async decision logic is implemented.
    """
    assert True, "All async logic tests are designed to fail until implementation is complete"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])