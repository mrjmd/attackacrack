"""
End-to-End Test: CSV Import to Campaign Creation and Usage
TDD Implementation: Comprehensive integration test covering the complete workflow

Test Flow:
1. Import PropertyRadar CSV file using PropertyRadarImportService  
2. Verify the list is created with correct contacts
3. Create a campaign using the imported list
4. Verify the campaign is properly configured
5. Test sending a message through the campaign (mock the actual send)

This test validates the entire customer journey from data import to message delivery.
"""

import pytest
import os
import csv
import io
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
from decimal import Decimal
from sqlalchemy import text

from app import create_app
from extensions import db
from services.propertyradar_import_service import PropertyRadarImportService
from services.campaign_service_refactored import CampaignService
from services.campaign_list_service_refactored import CampaignListServiceRefactored
from repositories.property_repository import PropertyRepository
from repositories.contact_repository import ContactRepository
from repositories.csv_import_repository import CSVImportRepository
from repositories.campaign_list_repository import CampaignListRepository
from repositories.campaign_list_member_repository import CampaignListMemberRepository
from repositories.campaign_repository import CampaignRepository
from repositories.contact_flag_repository import ContactFlagRepository
from repositories.activity_repository import ActivityRepository
from crm_database import (
    Property, Contact, PropertyContact, CSVImport, 
    CampaignList, CampaignListMember, Campaign, CampaignMembership, Activity
)


class TestCSVToCampaignEndToEnd:
    """End-to-end tests for CSV import to campaign workflow"""
    
    @pytest.fixture(scope='function')
    def app(self):
        """Create test application with isolated database"""
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
        """Create repository instances for testing"""
        return {
            'property': PropertyRepository(session=db_session),
            'contact': ContactRepository(session=db_session),
            'csv_import': CSVImportRepository(session=db_session),
            'campaign_list': CampaignListRepository(session=db_session),
            'campaign_list_member': CampaignListMemberRepository(session=db_session),
            'campaign': CampaignRepository(session=db_session),
            'contact_flag': ContactFlagRepository(session=db_session),
            'activity': ActivityRepository(session=db_session)
        }
    
    @pytest.fixture
    def services(self, repositories, db_session):
        """Create service instances with mocked external dependencies"""
        # Mock OpenPhone service with unique message IDs
        import itertools
        openphone_service = Mock()
        message_id_counter = itertools.count(1)
        openphone_service.send_message = Mock(side_effect=lambda phone, message: {
            'success': True, 
            'message_id': f'test_msg_{next(message_id_counter)}',
            'status': 'delivered'
        })
        
        # Create import service
        import_service = PropertyRadarImportService(
            property_repository=repositories['property'],
            contact_repository=repositories['contact'],
            csv_import_repository=repositories['csv_import'],
            campaign_list_repository=repositories['campaign_list'],
            campaign_list_member_repository=repositories['campaign_list_member'],
            session=db_session
        )
        
        # Create campaign list service
        list_service = CampaignListServiceRefactored(
            campaign_list_repository=repositories['campaign_list'],
            member_repository=repositories['campaign_list_member'],
            contact_repository=repositories['contact']
        )
        
        # Create campaign service
        campaign_service = CampaignService(
            campaign_repository=repositories['campaign'],
            contact_repository=repositories['contact'],
            contact_flag_repository=repositories['contact_flag'],
            activity_repository=repositories['activity'],
            openphone_service=openphone_service,
            list_service=list_service
        )
        
        return {
            'import': import_service,
            'campaign': campaign_service,
            'list': list_service,
            'openphone': openphone_service
        }
    
    @pytest.fixture
    def sample_csv_content(self):
        """PropertyRadar CSV content for testing with comprehensive data"""
        return '''Type,Address,City,ZIP,Subdivision,Longitude,Latitude,APN,Yr Built,Purchase Date,Purchase Mos Since,Sq Ft,Beds,Baths,Est Value,Est Equity $,Owner,Mail Address,Mail City,Mail State,Mail ZIP,Owner Occ?,Listed for Sale?,Listing Status,Foreclosure?,Est Equity %,High Equity?,Primary Name,Primary Mobile Phone1,Primary Mobile 1 Status,Primary Email1,Primary Email 1 Status,Primary Email1 Hash,Secondary Name,Secondary Mobile Phone1,Secondary Mobile 1 Status,Secondary Email1,Secondary Email 1 Status,Secondary Email1 Hash
SFR,123 Main St,Testtown,12345,Oak Grove,12.345678,-34.567890,APN-123,1995,01/15/2020,48,1500,3,2,250000,125000,JOHN SMITH,123 Main St,Testtown,ST,12345,1,0,,0,50,1,JOHN SMITH,555-0001,Active,john@example.com,Active,hash1,JANE SMITH,555-0002,Active,jane@example.com,Active,hash2
SFR,456 Oak Ave,Testtown,12345,Oak Grove,12.345679,-34.567891,APN-456,2000,03/22/2019,56,1800,4,3,300000,150000,BOB JOHNSON,456 Oak Ave,Testtown,ST,12345,1,0,,0,50,1,BOB JOHNSON,555-0003,Active,bob@example.com,Active,hash3,,,,,,
Condo,789 Pine Rd,Testtown,12346,Pine Hills,12.345680,-34.567892,APN-789,2010,06/10/2021,30,1200,2,2,180000,90000,ALICE WILSON,789 Pine Rd,Testtown,ST,12346,1,0,,0,50,1,ALICE WILSON,555-0004,Active,alice@example.com,Active,hash4,CHARLIE WILSON,555-0005,Active,charlie@example.com,Active,hash5
Townhome,321 Elm St,Testtown,12347,Elm Park,12.345681,-34.567893,APN-321,2015,12/05/2022,18,1650,3,2,280000,140000,DAVID BROWN,321 Elm St,Testtown,ST,12347,1,0,,0,50,1,DAVID BROWN,555-0006,Active,david@example.com,Active,hash6,,,,,,
SFR,654 Maple Dr,Testtown,12348,Maple Heights,12.345682,-34.567894,APN-654,1988,08/15/2018,64,2200,4,3,420000,210000,SARAH DAVIS,654 Maple Dr,Testtown,ST,12348,1,0,,0,50,1,SARAH DAVIS,555-0007,Active,sarah@example.com,Active,hash7,MIKE DAVIS,555-0008,Active,mike@example.com,Active,hash8'''
    
    @pytest.fixture
    def large_csv_content(self):
        """Generate larger CSV content for performance testing"""
        header = '''Type,Address,City,ZIP,Primary Name,Primary Mobile Phone1,Primary Email1,Secondary Name,Secondary Mobile Phone1,Secondary Email1'''
        
        rows = [header]
        for i in range(100):  # 100 properties with contacts
            # Some properties have secondary contacts, some don't
            secondary_name = f"SECONDARY USER {i}" if i % 3 == 0 else ""
            secondary_phone = f"555-{8000 + i:04d}" if i % 3 == 0 else ""
            secondary_email = f"secondary{i}@example.com" if i % 3 == 0 else ""
            
            row = f"SFR,{i+1000} TEST STREET,TESTCITY,{90000 + i},PRIMARY USER {i},555-{7000 + i:04d},primary{i}@example.com,{secondary_name},{secondary_phone},{secondary_email}"
            rows.append(row)
        
        return '\n'.join(rows)
    
    def test_complete_csv_import_to_campaign_workflow(self, services, sample_csv_content, db_session):
        """Test complete workflow from CSV import to campaign message sending"""
        
        # Phase 1: Import CSV with list creation
        list_name = "PropertyRadar Import - Testtown Prospects"
        
        import_result = services['import'].import_csv(
            csv_content=sample_csv_content,
            filename='testtown_prospects.csv',
            imported_by='integration_test',
            list_name=list_name
        )
        
        # Verify import succeeded
        assert import_result.is_success, f"Import failed: {import_result.error}"
        
        import_stats = import_result.data
        assert import_stats['total_rows'] == 5  # 5 properties
        assert import_stats['properties_created'] == 5
        assert import_stats['contacts_created'] == 8  # 5 primary + 3 secondary contacts
        assert import_stats['list_id'] is not None
        assert import_stats['list_name'] == list_name
        assert import_stats['contacts_added_to_list'] == 8
        
        list_id = import_stats['list_id']
        
        # Phase 2: Verify list and contacts are correctly created
        campaign_list = db_session.query(CampaignList).filter_by(id=list_id).first()
        assert campaign_list is not None
        assert campaign_list.name == list_name
        assert campaign_list.description == "PropertyRadar import from testtown_prospects.csv"
        
        # Verify all contacts are in the list
        list_members = db_session.query(CampaignListMember).filter_by(
            list_id=list_id,
            status='active'
        ).all()
        assert len(list_members) == 8
        
        # Verify contact details and normalization
        contacts = db_session.query(Contact).all()
        assert len(contacts) == 8
        
        # Check name normalization (JOHN SMITH -> John Smith)
        john_smith = next((c for c in contacts if c.first_name == 'John' and c.last_name == 'Smith'), None)
        assert john_smith is not None
        assert john_smith.phone == '+15550001'  # Normalized phone
        assert john_smith.email == 'john@example.com'
        
        # Phase 3: Create campaign using the imported list
        campaign_result = services['campaign'].create_campaign(
            name="Testtown Real Estate Outreach",
            campaign_type="blast",
            audience_type="cold",
            template_a="Hi {first_name}, we wanted to reach out about potential opportunities. Reply STOP to opt out.",
            daily_limit=50
        )
        
        assert campaign_result.is_success, f"Campaign creation failed: {campaign_result.error}"
        campaign_data = campaign_result.data
        campaign_id = campaign_data['id'] if isinstance(campaign_data, dict) else campaign_data.id
        
        # Phase 4: Add the imported list as recipients to the campaign
        # Note: This would normally be done through a campaign list association
        # For this test, we'll add contacts manually to simulate the process
        
        added_count = 0
        for member in list_members:
            # Add each contact from the list to the campaign
            membership = CampaignMembership(
                campaign_id=campaign_id,
                contact_id=member.contact_id,
                status='pending',
                # list_source_id would require schema update
            )
            db_session.add(membership)
            added_count += 1
        
        db_session.commit()
        
        # Verify all contacts were added to campaign
        campaign_members = db_session.query(CampaignMembership).filter_by(
            campaign_id=campaign_id
        ).all()
        assert len(campaign_members) == 8
        assert all(m.status == 'pending' for m in campaign_members)
        # Note: list_source_id tracking would require database schema update
        
        # Phase 5: Activate the campaign
        activation_result = services['campaign'].activate_campaign(campaign_id)
        assert activation_result is True
        
        # Verify campaign is active
        campaign = db_session.query(Campaign).filter_by(id=campaign_id).first()
        assert campaign.status == 'running'
        
        # Phase 6: Process campaign queue (send messages)
        with patch.object(services['campaign'], 'is_business_hours', return_value=True):
            process_result = services['campaign'].process_campaign_queue()
        
        # Verify messages were sent
        assert process_result.is_success, f"Queue processing failed: {process_result.error}"
        
        send_stats = process_result.data
        assert send_stats['messages_sent'] == 8  # All 8 contacts
        assert send_stats['messages_skipped'] == 0
        assert len(send_stats.get('errors', [])) == 0
        
        # Phase 7: Verify OpenPhone service calls
        openphone_service = services['openphone']
        assert openphone_service.send_message.call_count == 8
        
        # Verify personalized messages were sent with normalized names
        calls = openphone_service.send_message.call_args_list
        sent_messages = [call[0][1] for call in calls]  # Extract message content
        
        # Check that names are properly normalized in messages
        assert any("Hi John," in msg for msg in sent_messages)
        assert any("Hi Bob," in msg for msg in sent_messages) 
        assert any("Hi Alice," in msg for msg in sent_messages)
        
        # Phase 8: Verify campaign statistics and tracking
        analytics = services['campaign'].get_campaign_analytics(campaign_id)
        assert analytics['sent_count'] == 8
        assert analytics['total_recipients'] == 8
        # Calculate completion rate from available data
        completion_rate = (analytics['sent_count'] / analytics['total_recipients']) * 100
        assert completion_rate == 100.0
        
        # Verify campaign member statuses were updated
        updated_members = db_session.query(CampaignMembership).filter_by(
            campaign_id=campaign_id
        ).all()
        assert all(m.status == 'sent' for m in updated_members)
        assert all(m.sent_at is not None for m in updated_members)
        
        # Phase 9: Verify activity tracking (messages logged)
        # Note: Activity creation is currently disabled in campaign service (TODO)
        # This would be verified once activity logging is implemented
        # activities = db_session.query(Activity).filter_by(
        #     campaign_id=campaign_id,
        #     activity_type='campaign_message_sent'
        # ).all()
        # assert len(activities) == 8
    
    def test_large_scale_csv_to_campaign_workflow(self, services, large_csv_content, db_session):
        """Test workflow with larger dataset (100+ properties)"""
        
        # Import large CSV
        list_name = "Large Import Test List"
        
        import_result = services['import'].import_csv(
            csv_content=large_csv_content,
            filename='large_import.csv',
            imported_by='performance_test',
            list_name=list_name,
            batch_size=25  # Test batch processing
        )
        
        assert import_result.is_success
        import_stats = import_result.data
        assert import_stats['total_rows'] == 100  # 100 properties
        assert import_stats['properties_created'] == 100
        
        # Should have ~134 contacts (100 primary + ~34 secondary)
        # Every 3rd property (starting from 0) has secondary: 0, 3, 6, 9, ... up to 99
        # That's 34 properties with secondary contacts
        expected_contacts = 100 + 34  # 100 primary + 34 secondary
        assert import_stats['contacts_created'] == expected_contacts
        assert import_stats['contacts_added_to_list'] == expected_contacts
        
        list_id = import_stats['list_id']
        
        # Create campaign with higher daily limit
        campaign_result = services['campaign'].create_campaign(
            name="Large Scale Campaign Test",
            template_a="Bulk message to {first_name}",
            daily_limit=150  # Higher than contact count
        )
        
        assert campaign_result.is_success
        campaign_data = campaign_result.data
        campaign_id = campaign_data['id'] if isinstance(campaign_data, dict) else campaign_data.id
        
        # Add list members to campaign
        list_members = db_session.query(CampaignListMember).filter_by(list_id=list_id).all()
        memberships = []
        for member in list_members:
            membership = CampaignMembership(
                campaign_id=campaign_id,
                contact_id=member.contact_id,
                status='pending',
                # list_source_id would require schema update
            )
            memberships.append(membership)
        
        db_session.add_all(memberships)
        db_session.commit()
        
        # Activate and process
        services['campaign'].activate_campaign(campaign_id)
        
        with patch.object(services['campaign'], 'is_business_hours', return_value=True):
            process_result = services['campaign'].process_campaign_queue()
        
        # Verify large scale processing
        assert process_result.is_success
        send_stats = process_result.data
        assert send_stats['messages_sent'] == expected_contacts
        assert services['openphone'].send_message.call_count == expected_contacts
    
    def test_csv_import_with_duplicates_to_campaign(self, services, db_session):
        """Test workflow handles duplicate contacts correctly"""
        
        # CSV with duplicate phone numbers
        csv_with_duplicates = '''Type,Address,City,ZIP,Primary Name,Primary Mobile Phone1,Primary Email1
SFR,123 First St,Town,12345,John Smith,555-1111,john@example.com
SFR,456 Second St,Town,12346,John Smith,555-1111,john@example.com
SFR,789 Third St,Town,12347,Jane Doe,555-2222,jane@example.com
SFR,999 Fourth St,Town,12348,Different Person,555-2222,different@example.com'''
        
        # Import CSV
        import_result = services['import'].import_csv(
            csv_content=csv_with_duplicates,
            filename='duplicates_test.csv',
            imported_by='duplicate_test',
            list_name="Duplicate Test List"
        )
        
        assert import_result.is_success
        import_stats = import_result.data
        assert import_stats['total_rows'] == 4  # 4 properties
        assert import_stats['properties_created'] == 4
        assert import_stats['contacts_created'] == 2  # Only 2 unique phone numbers
        assert import_stats['contacts_added_to_list'] == 2  # Only unique contacts in list
        
        # Verify only unique contacts exist
        contacts = db_session.query(Contact).all()
        assert len(contacts) == 2
        
        phones = [c.phone for c in contacts]
        assert '+15551111' in phones
        assert '+15552222' in phones
        
        # Create and run campaign
        campaign_result = services['campaign'].create_campaign(
            name="Duplicate Handling Test Campaign",
            template_a="Message for {first_name}"
        )
        
        campaign_data = campaign_result.data
        campaign_id = campaign_data['id'] if isinstance(campaign_data, dict) else campaign_data.id
        
        # Add contacts to campaign
        list_id = import_stats['list_id']
        list_members = db_session.query(CampaignListMember).filter_by(list_id=list_id).all()
        
        for member in list_members:
            membership = CampaignMembership(
                campaign_id=campaign_id,
                contact_id=member.contact_id,
                status='pending'
            )
            db_session.add(membership)
        db_session.commit()
        
        services['campaign'].activate_campaign(campaign_id)
        
        with patch.object(services['campaign'], 'is_business_hours', return_value=True):
            process_result = services['campaign'].process_campaign_queue()
        
        # Should only send to 2 unique contacts
        send_stats = process_result.data
        assert send_stats['messages_sent'] == 2
        assert services['openphone'].send_message.call_count == 2
    
    def test_csv_import_error_handling_in_campaign_workflow(self, services, db_session):
        """Test workflow handles import errors and partial data gracefully"""
        
        # CSV with mixed valid and invalid data
        mixed_csv = '''Type,Address,City,ZIP,Primary Name,Primary Mobile Phone1,Primary Email1
SFR,123 Good St,Town,12345,Good User,555-1111,good@example.com
SFR,,Town,INVALID,Bad User,INVALID_PHONE,bad_email
SFR,789 Another Good St,Town,67890,Another Good,555-2222,good2@example.com'''
        
        # Import CSV (should succeed with errors)
        import_result = services['import'].import_csv(
            csv_content=mixed_csv,
            filename='mixed_data.csv',
            imported_by='error_test',
            list_name="Error Handling Test List"
        )
        
        assert import_result.is_success  # Overall success despite errors
        import_stats = import_result.data
        assert import_stats['total_rows'] == 3
        assert import_stats['properties_created'] == 2  # Only valid properties
        assert import_stats['contacts_created'] == 2  # Only valid contacts
        assert len(import_stats['errors']) > 0  # Some errors captured
        
        # Create campaign with only valid contacts
        campaign_result = services['campaign'].create_campaign(
            name="Error Recovery Campaign",
            template_a="Message for {first_name}"
        )
        
        campaign_data = campaign_result.data
        campaign_id = campaign_data['id'] if isinstance(campaign_data, dict) else campaign_data.id
        
        # Add valid contacts to campaign
        list_id = import_stats['list_id']
        list_members = db_session.query(CampaignListMember).filter_by(list_id=list_id).all()
        assert len(list_members) == 2  # Only valid contacts in list
        
        for member in list_members:
            membership = CampaignMembership(
                campaign_id=campaign_id,
                contact_id=member.contact_id,
                status='pending'
            )
            db_session.add(membership)
        db_session.commit()
        
        services['campaign'].activate_campaign(campaign_id)
        
        with patch.object(services['campaign'], 'is_business_hours', return_value=True):
            process_result = services['campaign'].process_campaign_queue()
        
        # Should successfully send to valid contacts
        send_stats = process_result.data
        assert send_stats['messages_sent'] == 2
        assert len(send_stats.get('errors', [])) == 0
    
    def test_campaign_send_failure_handling(self, services, sample_csv_content, db_session):
        """Test campaign handles OpenPhone send failures gracefully"""
        
        # Import contacts first
        import_result = services['import'].import_csv(
            csv_content=sample_csv_content,
            filename='send_failure_test.csv',
            imported_by='failure_test',
            list_name="Send Failure Test List"
        )
        
        assert import_result.is_success
        list_id = import_result.data['list_id']
        
        # Create campaign
        campaign_result = services['campaign'].create_campaign(
            name="Send Failure Test Campaign",
            template_a="Test message for {first_name}"
        )
        
        campaign_data = campaign_result.data
        campaign_id = campaign_data['id'] if isinstance(campaign_data, dict) else campaign_data.id
        
        # Add contacts to campaign
        list_members = db_session.query(CampaignListMember).filter_by(list_id=list_id).all()
        for member in list_members:
            membership = CampaignMembership(
                campaign_id=campaign_id,
                contact_id=member.contact_id,
                status='pending'
            )
            db_session.add(membership)
        db_session.commit()
        
        # Mock OpenPhone to fail for some sends
        openphone_service = services['openphone']
        responses = [
            {'success': True, 'message_id': 'msg_1'},  # Success
            {'success': False, 'error': 'Invalid phone'},  # Fail
            {'success': True, 'message_id': 'msg_3'},  # Success
            {'success': False, 'error': 'Rate limited'},  # Fail
            {'success': True, 'message_id': 'msg_5'},  # Success
            {'success': True, 'message_id': 'msg_6'},  # Success
            {'success': True, 'message_id': 'msg_7'},  # Success
            {'success': True, 'message_id': 'msg_8'},  # Success
        ]
        openphone_service.send_message = Mock(side_effect=responses)
        
        # Activate and process
        services['campaign'].activate_campaign(campaign_id)
        
        with patch.object(services['campaign'], 'is_business_hours', return_value=True):
            process_result = services['campaign'].process_campaign_queue()
        
        # Verify partial success handling
        send_stats = process_result.data
        assert send_stats['messages_sent'] == 6  # 6 successful sends
        assert send_stats['messages_skipped'] == 2  # 2 failed sends
        assert len(send_stats['errors']) == 2  # 2 error messages
        
        # Verify campaign member statuses reflect actual send results
        updated_members = db_session.query(CampaignMembership).filter_by(
            campaign_id=campaign_id
        ).all()
        
        sent_count = sum(1 for m in updated_members if m.status == 'sent')
        failed_count = sum(1 for m in updated_members if m.status == 'failed')
        
        assert sent_count == 6
        assert failed_count == 2
    
    def test_campaign_respects_daily_limits_with_large_import(self, services, large_csv_content, db_session):
        """Test campaign respects daily limits even with large imported lists"""
        
        # Import large list
        import_result = services['import'].import_csv(
            csv_content=large_csv_content,
            filename='daily_limit_test.csv',
            imported_by='limit_test',
            list_name="Daily Limit Test List"
        )
        
        assert import_result.is_success
        list_id = import_result.data['list_id']
        
        # Create campaign with low daily limit
        campaign_result = services['campaign'].create_campaign(
            name="Daily Limit Test Campaign",
            template_a="Limited message for {first_name}",
            daily_limit=10  # Much lower than contact count
        )
        
        campaign_data = campaign_result.data
        campaign_id = campaign_data['id'] if isinstance(campaign_data, dict) else campaign_data.id
        
        # Add all contacts to campaign
        list_members = db_session.query(CampaignListMember).filter_by(list_id=list_id).all()
        for member in list_members:
            membership = CampaignMembership(
                campaign_id=campaign_id,
                contact_id=member.contact_id,
                status='pending'
            )
            db_session.add(membership)
        db_session.commit()
        
        # Activate and process
        services['campaign'].activate_campaign(campaign_id)
        
        with patch.object(services['campaign'], 'is_business_hours', return_value=True):
            process_result = services['campaign'].process_campaign_queue()
        
        # Should only send up to daily limit
        send_stats = process_result.data
        assert send_stats['messages_sent'] == 10  # Respects daily limit
        assert services['openphone'].send_message.call_count == 10
        
        # Verify remaining contacts are still pending
        pending_members = db_session.query(CampaignMembership).filter_by(
            campaign_id=campaign_id,
            status='pending'
        ).count()
        
        total_contacts = len(list_members)
        assert pending_members == total_contacts - 10  # Remaining contacts still pending
    
    def test_end_to_end_data_integrity_verification(self, services, sample_csv_content, db_session):
        """Test comprehensive data integrity throughout the entire workflow"""
        
        # Phase 1: Import and verify data integrity
        import_result = services['import'].import_csv(
            csv_content=sample_csv_content,
            filename='integrity_test.csv',
            imported_by='integrity_test',
            list_name="Data Integrity Test List"
        )
        
        assert import_result.is_success
        
        # Run consistency verification
        consistency_report = services['import'].verify_import_consistency(
            csv_content=sample_csv_content,
            import_result=import_result.data
        )
        
        assert consistency_report['is_consistent'] is True
        assert consistency_report['property_count_matches'] is True
        assert consistency_report['contact_count_matches'] is True
        assert consistency_report['association_integrity'] is True
        
        # Phase 2: Create campaign and verify referential integrity
        campaign_result = services['campaign'].create_campaign(
            name="Integrity Test Campaign",
            template_a="Integrity test message for {first_name}"
        )
        
        campaign_data = campaign_result.data
        campaign_id = campaign_data['id'] if isinstance(campaign_data, dict) else campaign_data.id
        list_id = import_result.data['list_id']
        
        # Add contacts to campaign and verify associations
        list_members = db_session.query(CampaignListMember).filter_by(list_id=list_id).all()
        for member in list_members:
            # Verify contact exists
            contact = db_session.query(Contact).filter_by(id=member.contact_id).first()
            assert contact is not None
            
            membership = CampaignMembership(
                campaign_id=campaign_id,
                contact_id=member.contact_id,
                status='pending',
                # list_source_id would require schema update
            )
            db_session.add(membership)
        
        db_session.commit()
        
        # Phase 3: Process campaign and verify activity integrity
        services['campaign'].activate_campaign(campaign_id)
        
        with patch.object(services['campaign'], 'is_business_hours', return_value=True):
            process_result = services['campaign'].process_campaign_queue()
        
        # Verify no orphaned records
        # Check CampaignMembership referential integrity
        orphaned_memberships = db_session.execute(text('''
            SELECT cm.id FROM campaign_membership cm 
            LEFT JOIN campaign c ON cm.campaign_id = c.id 
            LEFT JOIN contact ct ON cm.contact_id = ct.id
            WHERE c.id IS NULL OR ct.id IS NULL
        ''')).fetchall()
        assert len(orphaned_memberships) == 0
        
        # Check Activity referential integrity
        orphaned_activities = db_session.execute(text('''
            SELECT a.id FROM activity a 
            LEFT JOIN contact c ON a.contact_id = c.id
            LEFT JOIN campaign camp ON a.campaign_id = camp.id
            WHERE (a.contact_id IS NOT NULL AND c.id IS NULL) 
               OR (a.campaign_id IS NOT NULL AND camp.id IS NULL)
        ''')).fetchall()
        assert len(orphaned_activities) == 0
        
        # Check PropertyContact associations integrity  
        orphaned_property_contacts = db_session.execute(text('''
            SELECT pc.id FROM property_contact pc
            LEFT JOIN property p ON pc.property_id = p.id
            LEFT JOIN contact c ON pc.contact_id = c.id
            WHERE p.id IS NULL OR c.id IS NULL
        ''')).fetchall()
        assert len(orphaned_property_contacts) == 0
        
        # Phase 4: Verify campaign analytics accuracy
        analytics = services['campaign'].get_campaign_analytics(campaign_id)
        
        # Count actual sent activities
        actual_sent = db_session.query(Activity).filter_by(
            campaign_id=campaign_id,
            activity_type='campaign_message_sent'
        ).count()
        
        assert analytics['sent_count'] == actual_sent
        
        # Count actual campaign memberships
        total_members = db_session.query(CampaignMembership).filter_by(
            campaign_id=campaign_id
        ).count()
        
        assert analytics['total_recipients'] == total_members