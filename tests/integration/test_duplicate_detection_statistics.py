"""
Duplicate Detection Statistics Integration Tests - RED PHASE  
TDD CRITICAL: These tests MUST fail initially - implementation comes AFTER tests

PROBLEM IDENTIFIED:
- Statistics don't distinguish between new creations and duplicate detections
- Duplicate import shows same statistics as original import
- No tracking of 'skipped', 'updated', or 'existing' operations
- Progress and statistics are based on CSV parsing, not actual database operations

TESTING STRATEGY:
1. Test first import vs duplicate import statistics using real database
2. Test different duplicate handling strategies affect statistics
3. Test cross-import duplicate detection with real data persistence
4. Test large-scale duplicate detection performance

These integration tests use actual database operations to verify that statistics
accurately reflect what happens to real data, not what's found in CSV files.
"""

import pytest
import os
from decimal import Decimal
from datetime import datetime

from app import create_app
from extensions import db
from services.propertyradar_import_service import PropertyRadarImportService
from repositories.property_repository import PropertyRepository
from repositories.contact_repository import ContactRepository
from repositories.csv_import_repository import CSVImportRepository
from repositories.campaign_list_repository import CampaignListRepository
from repositories.campaign_list_member_repository import CampaignListMemberRepository
from crm_database import Property, Contact, PropertyContact, CSVImport, CampaignList, CampaignListMember


class TestDuplicateDetectionStatisticsIntegration:
    """Integration tests for duplicate detection statistics with real database"""
    
    @pytest.fixture(scope='function')
    def app(self):
        """Create test application with separate database"""
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
            'csv_import': CSVImportRepository(session=db_session),
            'campaign_list': CampaignListRepository(session=db_session),
            'campaign_list_member': CampaignListMemberRepository(session=db_session)
        }
    
    @pytest.fixture
    def import_service(self, repositories, db_session):
        """Create import service with real repositories"""
        return PropertyRadarImportService(
            property_repository=repositories['property'],
            contact_repository=repositories['contact'],
            csv_import_repository=repositories['csv_import'],
            campaign_list_repository=repositories['campaign_list'],
            campaign_list_member_repository=repositories['campaign_list_member'],
            session=db_session
        )
    
    @pytest.fixture
    def sample_csv_data(self):
        """Sample CSV data for duplicate testing"""
        return """Type,Address,City,ZIP,Primary Name,Primary Mobile Phone1,Secondary Name,Secondary Mobile Phone1
SFR,123 Main St,Testtown,12345,John Smith,555-0001,Jane Smith,555-0002
SFR,456 Oak Ave,Testtown,67890,Bob Johnson,555-0003,Alice Johnson,555-0004
Condo,789 Pine Rd,Testtown,11111,Charlie Wilson,555-0005,Diana Wilson,555-0006"""

    def test_first_import_shows_all_new_creations(self, import_service, sample_csv_data, db_session):
        """Test that first import correctly reports all entities as newly created
        
        CRITICAL: This test WILL FAIL until statistics track actual database operations.
        """
        # Verify database is empty initially
        assert db_session.query(Property).count() == 0
        assert db_session.query(Contact).count() == 0
        
        # Act - First import
        result = import_service.import_csv(sample_csv_data, 'first_import.csv', 'test_user')
        
        # Assert - This WILL FAIL until statistics reflect actual operations
        assert result.is_success, f"First import should succeed: {result.error if result.is_failure else 'Success'}"
        
        stats = result.value
        
        # CRITICAL: Statistics must reflect actual database operations
        assert stats['total_rows'] == 3, "Should process 3 CSV rows"
        assert stats['properties_created'] == 3, "Should create 3 new properties"
        assert stats['properties_updated'] == 0, "Should update 0 properties on first import"
        assert stats['contacts_created'] == 6, "Should create 6 new contacts (2 per row)"
        assert stats['contacts_updated'] == 0, "Should update 0 contacts on first import"
        
        # Verify actual database state matches statistics
        actual_properties = db_session.query(Property).count()
        actual_contacts = db_session.query(Contact).count()
        
        assert actual_properties == stats['properties_created'], \
            f"Database has {actual_properties} properties, stats show {stats['properties_created']} created"
        assert actual_contacts == stats['contacts_created'], \
            f"Database has {actual_contacts} contacts, stats show {stats['contacts_created']} created"

    def test_duplicate_import_shows_all_existing_found(self, import_service, sample_csv_data, db_session):
        """Test that duplicate import correctly reports all entities as existing/updated
        
        CRITICAL: This test WILL FAIL until statistics distinguish between created and existing.
        """
        # Arrange - First import to create data
        first_result = import_service.import_csv(sample_csv_data, 'original.csv', 'test_user')
        assert first_result.is_success
        
        # Verify data exists
        initial_properties = db_session.query(Property).count()
        initial_contacts = db_session.query(Contact).count()
        assert initial_properties == 3
        assert initial_contacts == 6
        
        # Act - Duplicate import of same data
        result = import_service.import_csv(sample_csv_data, 'duplicate.csv', 'test_user')
        
        # Assert - This WILL FAIL until duplicate detection affects statistics
        assert result.is_success, f"Duplicate import should succeed: {result.error if result.is_failure else 'Success'}"
        
        stats = result.value
        
        # CRITICAL: Duplicate import must show different statistics
        assert stats['total_rows'] == 3, "Should still process 3 CSV rows"
        assert stats['properties_created'] == 0, "Should create 0 new properties (all exist)"
        assert stats['properties_updated'] == 3, "Should update/find 3 existing properties"
        assert stats['contacts_created'] == 0, "Should create 0 new contacts (all exist)"
        assert stats['contacts_updated'] == 6, "Should update/find 6 existing contacts"
        
        # Verify database counts haven't changed (no new records)
        final_properties = db_session.query(Property).count()
        final_contacts = db_session.query(Contact).count()
        
        assert final_properties == initial_properties, "Property count should not increase on duplicate import"
        assert final_contacts == initial_contacts, "Contact count should not increase on duplicate import"

    def test_mixed_import_counts_new_and_existing_separately(self, import_service, sample_csv_data, db_session):
        """Test import with mix of new and existing data shows accurate separate counts
        
        CRITICAL: This test WILL FAIL until statistics can distinguish operation types.
        """
        # Arrange - Import partial data first
        partial_csv = """Type,Address,City,ZIP,Primary Name,Primary Mobile Phone1,Secondary Name,Secondary Mobile Phone1
SFR,123 Main St,Testtown,12345,John Smith,555-0001,Jane Smith,555-0002"""
        
        first_result = import_service.import_csv(partial_csv, 'partial.csv', 'test_user')
        assert first_result.is_success
        
        # Verify partial data exists (1 property, 2 contacts)
        assert db_session.query(Property).count() == 1
        assert db_session.query(Contact).count() == 2
        
        # Act - Import full data (1 existing property + 2 new properties, 2 existing contacts + 4 new contacts)
        result = import_service.import_csv(sample_csv_data, 'mixed.csv', 'test_user')
        
        # Assert - This WILL FAIL until mixed operation tracking is implemented
        assert result.is_success, f"Mixed import should succeed: {result.error if result.is_failure else 'Success'}"
        
        stats = result.value
        
        # CRITICAL: Must accurately count new vs existing operations
        assert stats['total_rows'] == 3, "Should process 3 CSV rows"
        assert stats['properties_created'] == 2, "Should create 2 new properties (Oak Ave, Pine Rd)"
        assert stats['properties_updated'] == 1, "Should find 1 existing property (Main St)"
        assert stats['contacts_created'] == 4, "Should create 4 new contacts"
        assert stats['contacts_updated'] == 2, "Should find 2 existing contacts (John, Jane)"
        
        # Verify final database state
        final_properties = db_session.query(Property).count()
        final_contacts = db_session.query(Contact).count()
        
        assert final_properties == 3, "Should have 3 total properties"
        assert final_contacts == 6, "Should have 6 total contacts"

    def test_duplicate_phone_numbers_deduplicated_across_properties(self, import_service, db_session):
        """Test that duplicate phone numbers are deduplicated across different properties
        
        CRITICAL: This test WILL FAIL until phone deduplication affects contact statistics.
        """
        # Arrange - CSV with same phone numbers across different properties
        csv_with_duplicate_phones = """Type,Address,City,ZIP,Primary Name,Primary Mobile Phone1,Secondary Name,Secondary Mobile Phone1
SFR,123 Main St,City,12345,John Smith,555-0001,Jane Smith,555-0002
SFR,456 Oak Ave,City,67890,John Smith,555-0001,Bob Johnson,555-0003
SFR,789 Pine Rd,City,11111,Alice Wilson,555-0004,Jane Smith,555-0002"""
        
        # Act
        result = import_service.import_csv(csv_with_duplicate_phones, 'phone_dedup.csv', 'test_user')
        
        # Assert - This WILL FAIL until phone deduplication is tracked in statistics
        assert result.is_success
        
        stats = result.value
        
        # CRITICAL: Should create fewer contacts due to phone deduplication
        # CSV has 6 contact entries but only 4 unique phone numbers
        assert stats['total_rows'] == 3, "Should process 3 CSV rows"
        assert stats['properties_created'] == 3, "Should create 3 properties"
        assert stats['contacts_created'] == 4, "Should create 4 unique contacts (deduplicated by phone)"
        assert stats['contacts_updated'] == 2, "Should find 2 duplicate contacts by phone"
        
        # Verify actual database has deduplicated contacts
        unique_contacts = db_session.query(Contact).count()
        assert unique_contacts == 4, "Database should have 4 unique contacts (deduplicated by phone)"
        
        # Verify each property has correct associations
        properties = db_session.query(Property).all()
        assert len(properties) == 3
        
        # First property should have John and Jane
        # Second property should have John (existing) and Bob (new)
        # Third property should have Alice (new) and Jane (existing)

    def test_large_scale_duplicate_detection_performance(self, import_service, db_session):
        """Test duplicate detection performance with larger dataset
        
        CRITICAL: This test verifies performance doesn't degrade with duplicate detection.
        """
        # Arrange - Create large CSV with systematic duplicates
        csv_lines = ['Type,Address,City,ZIP,Primary Name,Primary Mobile Phone1,Secondary Name,Secondary Mobile Phone1']
        
        # Create 100 properties, but repeat contact phone numbers every 10 properties
        for i in range(100):
            phone1 = f'555-{(i % 10):04d}'  # Repeat every 10
            phone2 = f'555-{((i % 10) + 1000):04d}'  # Repeat every 10
            line = f'SFR,{i} Test St,City,{12345 + i},User {i},{phone1},Spouse {i},{phone2}'
            csv_lines.append(line)
        
        large_csv = '\n'.join(csv_lines)
        
        # Act
        start_time = datetime.now()
        result = import_service.import_csv(large_csv, 'large_dedup.csv', 'test_user', batch_size=25)
        end_time = datetime.now()
        
        processing_time = (end_time - start_time).total_seconds()
        
        # Assert
        assert result.is_success, f"Large duplicate detection should succeed: {result.error if result.is_failure else 'Success'}"
        
        stats = result.value
        
        # CRITICAL: Should create 100 properties but only 20 unique contacts (10 pairs × 2 contacts)
        assert stats['total_rows'] == 100, "Should process 100 CSV rows"
        assert stats['properties_created'] == 100, "Should create 100 unique properties"
        assert stats['contacts_created'] == 20, "Should create 20 unique contacts (deduplicated)"
        assert stats['contacts_updated'] == 180, "Should find 180 duplicate contacts (100×2 - 20)"
        
        # Performance requirement
        assert processing_time < 30, f"Large duplicate detection took {processing_time}s, should be < 30s"
        
        # Verify actual database state
        actual_properties = db_session.query(Property).count()
        actual_contacts = db_session.query(Contact).count()
        
        assert actual_properties == 100, f"Should have 100 properties, got {actual_properties}"
        assert actual_contacts == 20, f"Should have 20 unique contacts, got {actual_contacts}"

    def test_campaign_list_statistics_with_duplicates(self, import_service, sample_csv_data, db_session):
        """Test that campaign list statistics handle duplicate contacts correctly
        
        CRITICAL: This test WILL FAIL until list statistics account for deduplication.
        """
        # Arrange - Import data first time with list
        first_result = import_service.import_csv(
            sample_csv_data, 
            'first_list.csv', 
            'test_user',
            list_name='Original List'
        )
        assert first_result.is_success
        
        first_stats = first_result.value
        original_list_id = first_stats['list_id']
        
        # Verify first import list statistics
        assert first_stats['contacts_added_to_list'] == 6, "Should add all 6 contacts to list initially"
        
        # Act - Import same data again with different list (should reuse existing contacts)
        second_result = import_service.import_csv(
            sample_csv_data,
            'second_list.csv',
            'test_user', 
            list_name='Duplicate List'
        )
        
        # Assert - This WILL FAIL until list statistics handle existing contacts
        assert second_result.is_success
        
        second_stats = second_result.value
        duplicate_list_id = second_stats['list_id']
        
        # CRITICAL: Second list should add existing contacts, not create new ones
        assert second_stats['contacts_created'] == 0, "Should create 0 new contacts (all exist)"
        assert second_stats['contacts_updated'] == 6, "Should find 6 existing contacts"
        assert second_stats['contacts_added_to_list'] == 6, "Should add all 6 existing contacts to new list"
        
        # Verify database state
        total_contacts = db_session.query(Contact).count()
        assert total_contacts == 6, "Should still have only 6 unique contacts total"
        
        # Verify both lists exist with same contacts
        original_members = db_session.query(CampaignListMember).filter_by(list_id=original_list_id).count()
        duplicate_members = db_session.query(CampaignListMember).filter_by(list_id=duplicate_list_id).count()
        
        assert original_members == 6, "Original list should have 6 members"
        assert duplicate_members == 6, "Duplicate list should have 6 members (same contacts)"

    def test_cross_import_duplicate_detection_persistence(self, import_service, db_session):
        """Test that duplicate detection works across separate import sessions
        
        CRITICAL: This test verifies persistence of duplicate detection across transactions.
        """
        # Arrange - First import session
        first_csv = """Type,Address,City,ZIP,Primary Name,Primary Mobile Phone1
SFR,123 First St,City,12345,John Smith,555-0001
SFR,456 Second St,City,67890,Jane Doe,555-0002"""
        
        first_result = import_service.import_csv(first_csv, 'session1.csv', 'user1')
        assert first_result.is_success
        
        # Commit to ensure persistence
        db_session.commit()
        
        # Second import session with overlapping data
        second_csv = """Type,Address,City,ZIP,Primary Name,Primary Mobile Phone1
SFR,123 First St,City,12345,John Smith,555-0001
SFR,789 Third St,City,11111,Bob Johnson,555-0003"""
        
        # Act - Second import should detect duplicates from first import
        second_result = import_service.import_csv(second_csv, 'session2.csv', 'user2')
        
        # Assert - This WILL FAIL until cross-session duplicate detection works
        assert second_result.is_success
        
        stats = second_result.value
        
        # CRITICAL: Should detect existing data from previous import
        assert stats['properties_created'] == 1, "Should create 1 new property (789 Third St)"
        assert stats['properties_updated'] == 1, "Should find 1 existing property (123 First St)" 
        assert stats['contacts_created'] == 1, "Should create 1 new contact (Bob Johnson)"
        assert stats['contacts_updated'] == 1, "Should find 1 existing contact (John Smith)"
        
        # Verify final database state
        total_properties = db_session.query(Property).count()
        total_contacts = db_session.query(Contact).count()
        
        assert total_properties == 3, "Should have 3 total properties across both imports"
        assert total_contacts == 3, "Should have 3 total contacts across both imports"

    def test_error_handling_preserves_accurate_statistics(self, import_service, db_session):
        """Test that statistics remain accurate even when some operations fail
        
        CRITICAL: This test verifies statistics accuracy in error conditions.
        """
        # Arrange - CSV with some problematic data
        mixed_csv = """Type,Address,City,ZIP,Primary Name,Primary Mobile Phone1
SFR,123 Valid St,City,12345,John Smith,555-0001
SFR,,City,BADZIP,Invalid User,BADPHONE
SFR,456 Another Valid St,City,67890,Jane Doe,555-0002"""
        
        # Act
        result = import_service.import_csv(mixed_csv, 'error_stats.csv', 'test_user')
        
        # Assert - Import may succeed with errors or fail
        stats = result.value if result.is_success else {}
        
        if result.is_success:
            # CRITICAL: Statistics should only count successful operations
            assert stats['total_rows'] == 3, "Should attempt to process 3 rows"
            
            # Successful operations should be counted accurately
            successful_properties = stats.get('properties_created', 0)
            successful_contacts = stats.get('contacts_created', 0)
            
            # Verify actual database matches successful statistics
            actual_properties = db_session.query(Property).count()
            actual_contacts = db_session.query(Contact).count()
            
            assert actual_properties == successful_properties, \
                f"Database has {actual_properties} properties, stats show {successful_properties}"
            assert actual_contacts == successful_contacts, \
                f"Database has {actual_contacts} contacts, stats show {successful_contacts}"
            
            # Should have error information
            assert 'errors' in stats, "Should include error information"
            assert len(stats['errors']) > 0, "Should report errors for problematic rows"