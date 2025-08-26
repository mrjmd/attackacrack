"""
PropertyRadar Full Import Integration Tests - Large scale import with real data
TDD RED Phase: Write comprehensive integration tests BEFORE implementation

These tests cover:
1. Full end-to-end import using actual CSV data
2. Large scale import performance (3000+ rows)
3. Memory usage and performance optimization
4. Transaction integrity and error recovery
5. Data integrity verification
6. Real CSV data processing from csvs/short-csv.csv
"""

import pytest
import csv
import os
from decimal import Decimal
from datetime import datetime, date
from sqlalchemy import text

from app import create_app
from extensions import db
from services.propertyradar_import_service import PropertyRadarImportService
from repositories.property_repository import PropertyRepository
from repositories.contact_repository import ContactRepository
from repositories.csv_import_repository import CSVImportRepository
from crm_database import Property, Contact, PropertyContact, CSVImport


class TestPropertyRadarFullImport:
    """Integration tests for full PropertyRadar import process"""
    
    @pytest.fixture(scope='function')
    def app(self):
        """Create test application with separate database"""
        # Should fail - integration test setup doesn't exist yet
        app = create_app('testing')
        with app.app_context():
            db.create_all()
            yield app
            db.session.rollback()
            db.drop_all()
    
    @pytest.fixture
    def db_session(self, app):
        """Create database session for testing"""
        with app.app_context():
            yield db.session
    
    @pytest.fixture
    def repositories(self, db_session):
        """Create repository instances with real database"""
        return {
            'property': PropertyRepository(session=db_session),
            'contact': ContactRepository(session=db_session),
            'csv_import': CSVImportRepository(session=db_session)
        }
    
    @pytest.fixture
    def import_service(self, repositories):
        """Create import service with real repositories"""
        # Should fail - service doesn't exist yet
        return PropertyRadarImportService(
            property_repository=repositories['property'],
            contact_repository=repositories['contact'],
            csv_import_repository=repositories['csv_import']
        )
    
    @pytest.fixture
    def real_csv_data(self):
        """Load real CSV data from csvs/short-csv.csv"""
        csv_path = '/app/csvs/short-csv.csv'
        
        if not os.path.exists(csv_path):
            pytest.skip(f"CSV file not found: {csv_path}")
        
        with open(csv_path, 'r', encoding='utf-8') as file:
            return file.read()
    
    @pytest.fixture
    def large_csv_data(self, real_csv_data):
        """Generate large CSV data for performance testing"""
        lines = real_csv_data.strip().split('\n')
        header = lines[0]
        sample_row = lines[1] if len(lines) > 1 else None
        
        if not sample_row:
            pytest.skip("No sample data in CSV file")
        
        # Generate 3000+ rows based on sample data
        large_rows = [header]
        for i in range(3000):
            # Modify sample row to create unique data
            row_data = sample_row.split(',')
            row_data[1] = f'{i+1} TEST STREET'  # Unique address
            row_data[3] = f'{i+10000:05d}'  # Unique ZIP
            row_data[7] = f'APN-{i:06d}'  # Unique APN
            row_data[27] = f'TEST USER {i}'  # Unique primary name
            row_data[28] = f'555-{i+1000:04d}'  # Unique phone
            row_data[30] = f'test{i}@example.com'  # Unique email
            
            large_rows.append(','.join(row_data))
        
        return '\n'.join(large_rows)
    
    def test_import_real_csv_data(self, import_service, real_csv_data, db_session):
        """Test importing real PropertyRadar CSV data"""
        # Should fail - import functionality doesn't exist yet
        result = import_service.import_csv(
            csv_content=real_csv_data,
            filename='short-csv.csv',
            imported_by='test_user'
        )
        
        assert result.is_success, f"Import failed: {result.error if result.is_failure else 'Unknown error'}"
        
        stats = result.data
        assert stats['total_rows'] > 0
        assert stats['properties_created'] > 0
        assert stats['contacts_created'] > 0
        
        # Verify data was actually saved
        property_count = db_session.query(Property).count()
        contact_count = db_session.query(Contact).count()
        
        assert property_count > 0
        assert contact_count > 0
    
    def test_verify_property_data_integrity(self, import_service, real_csv_data, db_session):
        """Test that imported property data matches CSV exactly"""
        # Should fail - data integrity verification doesn't exist yet
        result = import_service.import_csv(real_csv_data, 'test.csv', 'test_user')
        assert result.is_success
        
        # Get first property from database
        first_property = db_session.query(Property).first()
        assert first_property is not None
        
        # Parse CSV to get expected data
        csv_reader = csv.DictReader(real_csv_data.strip().split('\n'))
        first_csv_row = next(csv_reader)
        
        # Verify critical fields match (accounting for normalization)
        assert first_property.address.upper() == first_csv_row['Address'].upper()
        assert first_property.city.upper() == first_csv_row['City'].upper()
        assert first_property.zip_code == first_csv_row['ZIP']
        assert first_property.property_type == first_csv_row['Type']
        
        # Verify numeric fields are converted correctly
        if first_csv_row['Est Value']:
            expected_value = Decimal(first_csv_row['Est Value'])
            assert first_property.estimated_value == expected_value
        
        if first_csv_row['Longitude']:
            expected_longitude = float(first_csv_row['Longitude'])
            assert abs(first_property.longitude - expected_longitude) < 0.000001
    
    def test_verify_dual_contact_creation(self, import_service, real_csv_data, db_session):
        """Test that both primary and secondary contacts are created"""
        # Should fail - dual contact verification doesn't exist yet
        result = import_service.import_csv(real_csv_data, 'test.csv', 'test_user')
        assert result.is_success
        
        # Parse CSV to identify rows with secondary contacts
        csv_reader = csv.DictReader(real_csv_data.strip().split('\n'))
        rows_with_secondary = []
        rows_without_secondary = []
        
        for row in csv_reader:
            if row['Secondary Name'].strip():
                rows_with_secondary.append(row)
            else:
                rows_without_secondary.append(row)
        
        if rows_with_secondary:
            # Find property that should have secondary contact
            test_row = rows_with_secondary[0]
            property_obj = db_session.query(Property).filter_by(
                address=test_row['Address'],
                zip_code=test_row['ZIP']
            ).first()
            
            assert property_obj is not None
            
            # Should have 2 contacts associated
            assert len(property_obj.contacts) == 2
            
            # Check relationship types
            primary_association = db_session.query(PropertyContact).filter_by(
                property_id=property_obj.id,
                relationship_type='PRIMARY'
            ).first()
            
            secondary_association = db_session.query(PropertyContact).filter_by(
                property_id=property_obj.id,
                relationship_type='SECONDARY'
            ).first()
            
            assert primary_association is not None
            assert secondary_association is not None
    
    def test_large_scale_import_performance(self, import_service, large_csv_data, db_session):
        """Test importing 3000+ rows efficiently"""
        # Should fail - large scale import doesn't exist yet
        start_time = datetime.now()
        
        result = import_service.import_csv(
            csv_content=large_csv_data,
            filename='large_test.csv',
            imported_by='test_user',
            batch_size=100  # Process in batches
        )
        
        end_time = datetime.now()
        processing_time = (end_time - start_time).total_seconds()
        
        assert result.is_success, f"Large import failed: {result.error if result.is_failure else 'Unknown'}"
        
        stats = result.data
        assert stats['total_rows'] >= 3000
        assert stats['properties_created'] >= 3000
        
        # Performance requirements
        assert processing_time < 300, f"Import too slow: {processing_time}s for {stats['total_rows']} rows"
        
        # Verify all data was saved
        property_count = db_session.query(Property).count()
        contact_count = db_session.query(Contact).count()
        
        assert property_count >= 3000
        assert contact_count >= 3000  # At least one contact per property
    
    def test_memory_usage_large_import(self, import_service, large_csv_data):
        """Test memory usage stays reasonable during large import"""
        # Should fail - memory monitoring doesn't exist yet
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        memory_before = process.memory_info().rss / 1024 / 1024  # MB
        
        result = import_service.import_csv(
            csv_content=large_csv_data,
            filename='memory_test.csv',
            imported_by='test_user',
            batch_size=50  # Small batches to test memory efficiency
        )
        
        memory_after = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = memory_after - memory_before
        
        assert result.is_success
        
        # Memory increase should be reasonable (less than 500MB for 3000 rows)
        assert memory_increase < 500, f"Memory usage too high: {memory_increase}MB increase"
    
    def test_transaction_integrity_with_errors(self, import_service, db_session):
        """Test transaction rollback when errors occur"""
        # Should fail - transaction integrity doesn't exist yet
        # Create CSV with some invalid data
        invalid_csv = '''Type,Address,City,ZIP,Subdivision,Longitude,Latitude,APN,Yr Built,Purchase Date,Purchase Mos Since,Sq Ft,Beds,Baths,Est Value,Est Equity $,Owner,Mail Address,Mail City,Mail State,Mail ZIP,Owner Occ?,Listed for Sale?,Listing Status,Foreclosure?,Est Equity %,High Equity?,Primary Name,Primary Mobile Phone1,Primary Mobile 1 Status,Primary Email1,Primary Email 1 Status,Primary Email1 Hash,Secondary Name,Secondary Mobile Phone1,Secondary Mobile 1 Status,Secondary Email1,Secondary Email 1 Status,Secondary Email1 Hash
SFR,123 Valid St,City,12345,,,,,,,,,,,100000,50000,Owner,123 Valid St,City,ST,12345,1,0,,0,50,1,Valid User,555-1234,Active,valid@example.com,Active,hash1,,,,,,
SFR,456 Invalid St,City,INVALID_ZIP,,,,,,,,,,,INVALID_VALUE,0,Owner,456 Invalid St,City,ST,12345,1,0,,0,50,1,Invalid User,INVALID_PHONE,Active,invalid_email,Active,hash2,,,,,,
SFR,789 Another Valid St,City,67890,,,,,,,,,,,200000,100000,Owner,789 Another Valid St,City,ST,67890,1,0,,0,50,1,Another User,555-5678,Active,another@example.com,Active,hash3,,,,,,'''
        
        # Count records before import
        initial_property_count = db_session.query(Property).count()
        initial_contact_count = db_session.query(Contact).count()
        
        result = import_service.import_csv(
            csv_content=invalid_csv,
            filename='invalid_test.csv',
            imported_by='test_user'
        )
        
        # Import might succeed with error handling, or fail completely
        if result.is_failure:
            # If it fails, no data should be saved
            final_property_count = db_session.query(Property).count()
            final_contact_count = db_session.query(Contact).count()
            
            assert final_property_count == initial_property_count
            assert final_contact_count == initial_contact_count
        else:
            # If it succeeds, check error handling
            stats = result.data
            assert 'errors' in stats
            assert len(stats['errors']) > 0
    
    def test_duplicate_detection_across_batches(self, import_service, db_session):
        """Test duplicate detection works across batch boundaries"""
        # Should fail - cross-batch duplicate detection doesn't exist yet
        # Create CSV with duplicates in different batches
        duplicate_csv = '''Type,Address,City,ZIP,Subdivision,Longitude,Latitude,APN,Yr Built,Purchase Date,Purchase Mos Since,Sq Ft,Beds,Baths,Est Value,Est Equity $,Owner,Mail Address,Mail City,Mail State,Mail ZIP,Owner Occ?,Listed for Sale?,Listing Status,Foreclosure?,Est Equity %,High Equity?,Primary Name,Primary Mobile Phone1,Primary Mobile 1 Status,Primary Email1,Primary Email 1 Status,Primary Email1 Hash,Secondary Name,Secondary Mobile Phone1,Secondary Mobile 1 Status,Secondary Email1,Secondary Email 1 Status,Secondary Email1 Hash'''
        
        # Add same property multiple times
        base_row = 'SFR,123 Duplicate St,City,12345,,,APN-DUPLICATE,,,,,,,,100000,50000,Owner,123 Duplicate St,City,ST,12345,1,0,,0,50,1,Duplicate User,555-1234,Active,duplicate@example.com,Active,hash1,,,,,,'
        
        rows = [duplicate_csv]
        for i in range(10):
            rows.append(base_row)  # Same property 10 times
        
        duplicate_data = '\n'.join(rows)
        
        result = import_service.import_csv(
            csv_content=duplicate_data,
            filename='duplicate_test.csv',
            imported_by='test_user',
            batch_size=3  # Small batches to test cross-batch detection
        )
        
        assert result.is_success
        
        # Should only create one property despite 10 identical rows
        property_count = db_session.query(Property).filter_by(
            address='123 Duplicate St',
            zip_code='12345'
        ).count()
        
        assert property_count == 1
    
    def test_contact_deduplication_by_phone(self, import_service, db_session):
        """Test that contacts are deduplicated by phone number"""
        # Should fail - contact deduplication doesn't exist yet
        # Create CSV with same phone number for different properties
        csv_with_duplicate_phones = '''Type,Address,City,ZIP,Subdivision,Longitude,Latitude,APN,Yr Built,Purchase Date,Purchase Mos Since,Sq Ft,Beds,Baths,Est Value,Est Equity $,Owner,Mail Address,Mail City,Mail State,Mail ZIP,Owner Occ?,Listed for Sale?,Listing Status,Foreclosure?,Est Equity %,High Equity?,Primary Name,Primary Mobile Phone1,Primary Mobile 1 Status,Primary Email1,Primary Email 1 Status,Primary Email1 Hash,Secondary Name,Secondary Mobile Phone1,Secondary Mobile 1 Status,Secondary Email1,Secondary Email 1 Status,Secondary Email1 Hash
SFR,123 First St,City,12345,,,APN-001,,,,,,,,100000,50000,Owner,123 First St,City,ST,12345,1,0,,0,50,1,John Smith,555-1234,Active,john@example.com,Active,hash1,,,,,,
SFR,456 Second St,City,67890,,,APN-002,,,,,,,,200000,100000,Owner,456 Second St,City,ST,67890,1,0,,0,50,1,John Smith,555-1234,Active,john@example.com,Active,hash1,,,,,,'''
        
        result = import_service.import_csv(
            csv_content=csv_with_duplicate_phones,
            filename='phone_dedup_test.csv',
            imported_by='test_user'
        )
        
        assert result.is_success
        
        # Should create 2 properties but only 1 contact
        property_count = db_session.query(Property).count()
        contact_count = db_session.query(Contact).filter_by(
            phone='+15555551234'  # Normalized phone (555-1234 -> +15555551234)
        ).count()
        
        assert property_count == 2
        assert contact_count == 1
        
        # Both properties should be associated with the same contact
        contact = db_session.query(Contact).filter_by(
            phone='+15555551234'
        ).first()
        
        assert contact.properties.count() == 2
    
    def test_csv_import_tracking_and_audit(self, import_service, real_csv_data, db_session):
        """Test that CSV import is properly tracked in database"""
        # Should fail - import tracking doesn't exist yet
        result = import_service.import_csv(
            csv_content=real_csv_data,
            filename='audit_test.csv',
            imported_by='test_user'
        )
        
        assert result.is_success
        
        # Verify CSV import record was created
        csv_import = db_session.query(CSVImport).filter_by(
            filename='audit_test.csv'
        ).first()
        
        assert csv_import is not None
        assert csv_import.imported_by == 'test_user'
        assert csv_import.import_type == 'propertyradar'
        assert csv_import.total_rows > 0
        assert csv_import.successful_imports is not None
        assert csv_import.failed_imports is not None
        
        # Verify contacts are linked to import
        contacts_from_import = csv_import.contacts
        assert len(contacts_from_import) > 0
    
    def test_error_recovery_and_partial_success(self, import_service, db_session):
        """Test that import continues after individual row errors"""
        # Should fail - error recovery doesn't exist yet
        mixed_csv = '''Type,Address,City,ZIP,Subdivision,Longitude,Latitude,APN,Yr Built,Purchase Date,Purchase Mos Since,Sq Ft,Beds,Baths,Est Value,Est Equity $,Owner,Mail Address,Mail City,Mail State,Mail ZIP,Owner Occ?,Listed for Sale?,Listing Status,Foreclosure?,Est Equity %,High Equity?,Primary Name,Primary Mobile Phone1,Primary Mobile 1 Status,Primary Email1,Primary Email 1 Status,Primary Email1 Hash,Secondary Name,Secondary Mobile Phone1,Secondary Mobile 1 Status,Secondary Email1,Secondary Email 1 Status,Secondary Email1 Hash
SFR,123 Good St,City,12345,,,APN-GOOD,,,,,,,,100000,50000,Owner,123 Good St,City,ST,12345,1,0,,0,50,1,Good User,555-1111,Active,good@example.com,Active,hash1,,,,,,
SFR,,City,BAD,,,,,,,,,,,INVALID,0,Owner,,City,ST,,1,0,,0,50,1,,INVALID_PHONE,Active,bad_email,Active,hash2,,,,,,
SFR,789 Another Good St,City,67890,,,APN-GOOD2,,,,,,,,200000,100000,Owner,789 Another Good St,City,ST,67890,1,0,,0,50,1,Another Good User,555-2222,Active,good2@example.com,Active,hash3,,,,,,'''
        
        result = import_service.import_csv(
            csv_content=mixed_csv,
            filename='mixed_test.csv',
            imported_by='test_user'
        )
        
        assert result.is_success
        
        stats = result.data
        assert stats['total_rows'] == 3
        assert stats['properties_created'] == 2  # 2 good rows
        assert stats['errors'] is not None
        assert len(stats['errors']) >= 1  # At least 1 error from bad row
        
        # Verify good data was still saved
        good_property = db_session.query(Property).filter_by(
            address='123 Good St'
        ).first()
        assert good_property is not None
    
    def test_data_consistency_verification(self, import_service, real_csv_data, db_session):
        """Test comprehensive data consistency after import"""
        # Should fail - consistency verification doesn't exist yet
        result = import_service.import_csv(
            csv_content=real_csv_data,
            filename='consistency_test.csv',
            imported_by='test_user'
        )
        
        assert result.is_success
        
        # Run comprehensive consistency checks
        consistency_report = import_service.verify_import_consistency(
            csv_content=real_csv_data,
            import_result=result.data
        )
        
        assert consistency_report['is_consistent'] is True
        assert consistency_report['property_count_matches'] is True
        assert consistency_report['contact_count_matches'] is True
        assert consistency_report['association_integrity'] is True
        
        # Check referential integrity
        orphaned_associations = db_session.query(PropertyContact).filter(
            ~PropertyContact.property_id.in_(db_session.query(Property.id))
        ).count()
        assert orphaned_associations == 0
        
        orphaned_contacts = db_session.query(PropertyContact).filter(
            ~PropertyContact.contact_id.in_(db_session.query(Contact.id))
        ).count()
        assert orphaned_contacts == 0
    
    def test_concurrent_import_safety(self, import_service, real_csv_data):
        """Test that concurrent imports don't cause data corruption"""
        # Should fail - concurrent import safety doesn't exist yet
        import threading
        import time
        
        results = []
        errors = []
        
        def import_worker(worker_id):
            try:
                result = import_service.import_csv(
                    csv_content=real_csv_data,
                    filename=f'concurrent_test_{worker_id}.csv',
                    imported_by=f'worker_{worker_id}'
                )
                results.append((worker_id, result))
            except Exception as e:
                errors.append((worker_id, str(e)))
        
        # Start multiple concurrent imports
        threads = []
        for i in range(3):
            thread = threading.Thread(target=import_worker, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for all to complete
        for thread in threads:
            thread.join()
        
        # Verify no errors occurred
        assert len(errors) == 0, f"Concurrent import errors: {errors}"
        assert len(results) == 3
        
        # All imports should succeed
        for worker_id, result in results:
            assert result.is_success, f"Worker {worker_id} failed: {result.error if result.is_failure else 'Unknown'}"
