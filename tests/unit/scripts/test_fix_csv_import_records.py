"""
Unit tests for CSV Import record fix commands
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from click.testing import CliRunner
from scripts.fix_csv_import_records import (
    fix_csv_import_record,
    audit_csv_imports,
    fix_incomplete_imports
)
from crm_database import CSVImport
from datetime import datetime


class TestFixCSVImportRecord:
    """Test the fix_csv_import_record command"""
    
    def test_fix_record_not_found(self, app):
        """Test fixing a non-existent record"""
        runner = CliRunner()
        
        with app.app_context():
            with patch('scripts.fix_csv_import_records.current_app') as mock_app:
                mock_session = Mock()
                mock_services = Mock()
                mock_services.get.return_value = mock_session
                mock_app.services = mock_services
                
                with patch('scripts.fix_csv_import_records.CSVImportRepository') as mock_repo_class:
                    mock_repo = Mock()
                    mock_repo.get_by_id.return_value = None
                    mock_repo_class.return_value = mock_repo
                    
                    result = runner.invoke(fix_csv_import_record, [
                        '--id', '999',
                        '--total-rows', '100',
                        '--successful', '100',
                        '--failed', '0'
                    ])
                    
                    assert result.exit_code == 0
                    assert "CSV Import record with ID 999 not found" in result.output
    
    def test_fix_record_with_dry_run(self, app):
        """Test dry run mode shows changes without applying them"""
        runner = CliRunner()
        
        with app.app_context():
            with patch('scripts.fix_csv_import_records.current_app') as mock_app:
                mock_session = Mock()
                mock_services = Mock()
                mock_services.get.return_value = mock_session
                mock_app.services = mock_services
                
                # Create mock CSV import record
                mock_import = Mock(spec=CSVImport)
                mock_import.id = 15
                mock_import.filename = "test.csv"
                mock_import.imported_at = datetime.utcnow()
                mock_import.import_type = "contacts"
                mock_import.total_rows = None
                mock_import.successful_imports = None
                mock_import.failed_imports = None
                mock_import.import_metadata = {}
                
                with patch('scripts.fix_csv_import_records.CSVImportRepository') as mock_repo_class:
                    mock_repo = Mock()
                    mock_repo.get_by_id.return_value = mock_import
                    mock_repo_class.return_value = mock_repo
                    
                    result = runner.invoke(fix_csv_import_record, [
                        '--id', '15',
                        '--total-rows', '826',
                        '--successful', '826',
                        '--failed', '0',
                        '--dry-run'
                    ])
                    
                    assert result.exit_code == 0
                    assert "CSV Import Record #15" in result.output
                    assert "Proposed Changes:" in result.output
                    assert "total_rows: NULL → 826" in result.output
                    assert "successful_imports: NULL → 826" in result.output
                    assert "failed_imports: NULL → 0" in result.output
                    assert "DRY RUN MODE - No changes made" in result.output
                    
                    # Ensure update was not called
                    mock_repo.update.assert_not_called()
    
    def test_fix_record_successful(self, app):
        """Test successfully fixing a record"""
        runner = CliRunner()
        
        with app.app_context():
            with patch('scripts.fix_csv_import_records.current_app') as mock_app:
                mock_session = Mock()
                mock_services = Mock()
                mock_services.get.return_value = mock_session
                mock_app.services = mock_services
                
                # Create mock CSV import record
                mock_import = Mock(spec=CSVImport)
                mock_import.id = 15
                mock_import.filename = "test.csv"
                mock_import.imported_at = datetime.utcnow()
                mock_import.import_type = "contacts"
                mock_import.total_rows = None
                mock_import.successful_imports = None
                mock_import.failed_imports = None
                mock_import.import_metadata = {}
                
                # Mock updated record
                mock_updated = Mock(spec=CSVImport)
                mock_updated.total_rows = 826
                mock_updated.successful_imports = 826
                mock_updated.failed_imports = 0
                
                with patch('scripts.fix_csv_import_records.CSVImportRepository') as mock_repo_class:
                    mock_repo = Mock()
                    mock_repo.get_by_id.return_value = mock_import
                    mock_repo.update.return_value = mock_updated
                    mock_repo_class.return_value = mock_repo
                    
                    result = runner.invoke(fix_csv_import_record, [
                        '--id', '15',
                        '--total-rows', '826',
                        '--successful', '826',
                        '--failed', '0'
                    ])
                    
                    assert result.exit_code == 0
                    assert "Successfully updated CSV Import record" in result.output
                    assert "New Values:" in result.output
                    assert "Total Rows: 826" in result.output
                    
                    # Verify update was called with correct parameters
                    mock_repo.update.assert_called_once()
                    mock_session.commit.assert_called_once()
    
    def test_fix_record_no_changes_needed(self, app):
        """Test when record already has correct values"""
        runner = CliRunner()
        
        with app.app_context():
            with patch('scripts.fix_csv_import_records.current_app') as mock_app:
                mock_session = Mock()
                mock_services = Mock()
                mock_services.get.return_value = mock_session
                mock_app.services = mock_services
                
                # Create mock CSV import record with values already set
                mock_import = Mock(spec=CSVImport)
                mock_import.id = 15
                mock_import.filename = "test.csv"
                mock_import.imported_at = datetime.utcnow()
                mock_import.import_type = "contacts"
                mock_import.total_rows = 826
                mock_import.successful_imports = 826
                mock_import.failed_imports = 0
                mock_import.import_metadata = {}
                
                with patch('scripts.fix_csv_import_records.CSVImportRepository') as mock_repo_class:
                    mock_repo = Mock()
                    mock_repo.get_by_id.return_value = mock_import
                    mock_repo_class.return_value = mock_repo
                    
                    result = runner.invoke(fix_csv_import_record, [
                        '--id', '15',
                        '--total-rows', '826',
                        '--successful', '826',
                        '--failed', '0'
                    ])
                    
                    assert result.exit_code == 0
                    assert "No changes needed - record already has the specified values" in result.output
                    
                    # Ensure update was not called
                    mock_repo.update.assert_not_called()


class TestAuditCSVImports:
    """Test the audit_csv_imports command"""
    
    def test_audit_incomplete_imports(self, app):
        """Test showing incomplete imports"""
        runner = CliRunner()
        
        with app.app_context():
            with patch('scripts.fix_csv_import_records.current_app') as mock_app:
                mock_session = Mock()
                mock_services = Mock()
                mock_services.get.return_value = mock_session
                mock_app.services = mock_services
                
                # Create mock incomplete imports
                mock_import1 = Mock(spec=CSVImport)
                mock_import1.id = 1
                mock_import1.filename = "incomplete1.csv"
                mock_import1.imported_at = datetime.utcnow()
                mock_import1.total_rows = None
                mock_import1.successful_imports = None
                mock_import1.failed_imports = None
                
                mock_query = Mock()
                mock_query.filter.return_value = mock_query
                mock_query.order_by.return_value = mock_query
                mock_query.limit.return_value = mock_query
                mock_query.all.return_value = [mock_import1]
                mock_session.query.return_value = mock_query
                
                with patch('scripts.fix_csv_import_records.CSVImportRepository') as mock_repo_class:
                    mock_repo = Mock()
                    mock_repo_class.return_value = mock_repo
                    
                    result = runner.invoke(audit_csv_imports, ['--show-incomplete'])
                    
                    assert result.exit_code == 0
                    assert "CSV Imports with Incomplete Statistics" in result.output
                    assert "Found 1 incomplete records:" in result.output
                    assert "ID: 1" in result.output
                    assert "Total Rows: NULL" in result.output
    
    def test_audit_failed_imports(self, app):
        """Test showing failed imports"""
        runner = CliRunner()
        
        with app.app_context():
            with patch('scripts.fix_csv_import_records.current_app') as mock_app:
                mock_session = Mock()
                mock_services = Mock()
                mock_services.get.return_value = mock_session
                mock_app.services = mock_services
                
                # Create mock failed import
                mock_import1 = Mock(spec=CSVImport)
                mock_import1.id = 2
                mock_import1.filename = "failed.csv"
                mock_import1.imported_at = datetime.utcnow()
                mock_import1.total_rows = 100
                mock_import1.successful_imports = 90
                mock_import1.failed_imports = 10
                mock_import1.import_metadata = {'errors': ['Error 1', 'Error 2']}
                
                with patch('scripts.fix_csv_import_records.CSVImportRepository') as mock_repo_class:
                    mock_repo = Mock()
                    mock_repo.get_failed_imports.return_value = [mock_import1]
                    mock_repo_class.return_value = mock_repo
                    
                    result = runner.invoke(audit_csv_imports, ['--show-failed'])
                    
                    assert result.exit_code == 0
                    assert "CSV Imports with Failures" in result.output
                    assert "Found 1 imports with failures:" in result.output
                    assert "Failed: 10 ⚠️" in result.output
                    assert "First Error: Error 1" in result.output


class TestFixIncompleteImports:
    """Test the fix_incomplete_imports command"""
    
    def test_fix_incomplete_requires_confirm(self, app):
        """Test that command requires confirmation"""
        runner = CliRunner()
        
        with app.app_context():
            result = runner.invoke(fix_incomplete_imports, [])
            
            assert result.exit_code == 0
            assert "Use --confirm to proceed or --dry-run to preview changes" in result.output
    
    def test_fix_incomplete_dry_run(self, app):
        """Test dry run mode for bulk fix"""
        runner = CliRunner()
        
        with app.app_context():
            with patch('scripts.fix_csv_import_records.current_app') as mock_app:
                mock_session = Mock()
                mock_services = Mock()
                mock_services.get.return_value = mock_session
                mock_app.services = mock_services
                
                # Create mock incomplete imports
                mock_import1 = Mock(spec=CSVImport)
                mock_import1.id = 1
                mock_import1.filename = "incomplete1.csv"
                mock_import1.total_rows = None
                mock_import1.successful_imports = None
                mock_import1.failed_imports = None
                mock_import1.import_metadata = {}
                
                mock_query = Mock()
                mock_query.filter.return_value = mock_query
                mock_query.all.return_value = [mock_import1]
                mock_session.query.return_value = mock_query
                
                with patch('scripts.fix_csv_import_records.CSVImportRepository') as mock_repo_class:
                    mock_repo = Mock()
                    mock_repo_class.return_value = mock_repo
                    
                    result = runner.invoke(fix_incomplete_imports, ['--dry-run'])
                    
                    assert result.exit_code == 0
                    assert "Found 1 incomplete import records" in result.output
                    assert "DRY RUN MODE" in result.output
                    assert "Record #1 (incomplete1.csv):" in result.output
                    assert "total_rows: NULL → 0" in result.output
                    assert "Would fix 1 records" in result.output
                    
                    # Ensure no updates were made
                    mock_repo.update.assert_not_called()
                    mock_session.commit.assert_not_called()