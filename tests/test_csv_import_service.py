"""
Tests for CSV Import Service
"""
import pytest
from unittest.mock import Mock, patch, mock_open
import pandas as pd
from io import StringIO
from services.csv_import_service import CSVImportService
from crm_database import db, Contact, CSVImport, ContactCSVImport, CampaignListMember, CampaignList


class TestCSVImportService:
    """Test cases for CSV Import service"""
    
    @pytest.fixture
    def csv_service(self, app):
        """Create a CSV import service instance"""
        with app.app_context():
            service = CSVImportService()
            yield service
            # Clean up
            ContactCSVImport.query.delete()
            CampaignListMember.query.delete()
            CSVImport.query.delete()
            CampaignList.query.delete()
            Contact.query.filter(Contact.id > 1).delete()  # Keep the seeded contact
            db.session.commit()
    
    @pytest.fixture
    def sample_csv_data(self):
        """Sample CSV data for testing"""
        csv_content = """first_name,last_name,phone,email,address,tag
John,Doe,+15551234567,john@example.com,123 Main St,customer
Jane,Smith,+15551234568,jane@example.com,456 Oak Ave,lead
Bob,Johnson,+15551234569,bob@example.com,789 Pine Rd,prospect"""
        return StringIO(csv_content)
    
    @pytest.fixture
    def sample_dataframe(self):
        """Sample DataFrame for testing"""
        return pd.DataFrame({
            'first_name': ['John', 'Jane', 'Bob'],
            'last_name': ['Doe', 'Smith', 'Johnson'],
            'phone': ['+15551234567', '+15551234568', '+15551234569'],
            'email': ['john@example.com', 'jane@example.com', 'bob@example.com'],
            'address': ['123 Main St', '456 Oak Ave', '789 Pine Rd'],
            'tag': ['customer', 'lead', 'prospect']
        })
    
    def test_import_csv_new_contacts(self, csv_service, sample_csv_data, app):
        """Test importing CSV with all new contacts"""
        with app.app_context():
            # Create campaign list
            campaign_list = CampaignList(name='Import List')
            db.session.add(campaign_list)
            db.session.commit()
            
            result = csv_service.import_csv(
                sample_csv_data,
                'test_import.csv',
                campaign_list.id
            )
            
            assert result['success'] is True
            assert result['imported'] == 3
            assert result['errors'] == 0
            assert result['new_contacts'] == 3
            assert result['enriched_contacts'] == 0
            
            # Verify contacts were created
            contacts = Contact.query.filter(Contact.phone.like('+155512345%')).all()
            assert len(contacts) == 3
            
            # Verify CSV import record
            csv_import = CSVImport.query.filter_by(filename='test_import.csv').first()
            assert csv_import is not None
            assert csv_import.total_rows == 3
            assert csv_import.successful_imports == 3
            
            # Verify list memberships
            memberships = CampaignListMember.query.filter_by(list_id=campaign_list.id).all()
            assert len(memberships) == 3
    
    def test_import_csv_with_existing_contacts(self, csv_service, sample_csv_data, app):
        """Test importing CSV with some existing contacts"""
        with app.app_context():
            # Create existing contact
            existing = Contact(
                first_name='John',
                last_name='OldLastName',
                phone='+15551234567',
                email='old@example.com'
            )
            db.session.add(existing)
            db.session.commit()
            
            # Create campaign list
            campaign_list = CampaignList(name='Import List')
            db.session.add(campaign_list)
            db.session.commit()
            
            result = csv_service.import_csv(
                sample_csv_data,
                'test_import.csv',
                campaign_list.id
            )
            
            assert result['imported'] == 3
            assert result['new_contacts'] == 2
            assert result['enriched_contacts'] == 1
            
            # Verify existing contact was enriched
            db.session.refresh(existing)
            assert existing.last_name == 'Doe'  # Updated
            assert existing.email == 'john@example.com'  # Updated
            assert existing.address == '123 Main St'  # Added
            
            # Verify contact-CSV association
            association = ContactCSVImport.query.filter_by(contact_id=existing.id).first()
            assert association is not None
            assert association.is_new is False
            assert association.data_updated is not None
            assert 'last_name' in association.data_updated
    
    def test_import_csv_with_invalid_phone(self, csv_service, app):
        """Test importing CSV with invalid phone numbers"""
        with app.app_context():
            csv_data = StringIO("""first_name,last_name,phone,email
John,Doe,invalid-phone,john@example.com
Jane,Smith,+15551234568,jane@example.com""")
            
            campaign_list = CampaignList(name='Import List')
            db.session.add(campaign_list)
            db.session.commit()
            
            result = csv_service.import_csv(csv_data, 'test.csv', campaign_list.id)
            
            assert result['imported'] == 1  # Only valid contact
            assert result['errors'] == 1
            assert result['skipped'] == 1
            
            # Check error details
            csv_import = CSVImport.query.filter_by(filename='test.csv').first()
            assert csv_import.failed_imports == 1
    
    def test_import_csv_duplicate_phones(self, csv_service, app):
        """Test importing CSV with duplicate phone numbers"""
        with app.app_context():
            csv_data = StringIO("""first_name,last_name,phone,email
John,Doe,+15551234567,john@example.com
Jane,Doe,+15551234567,jane@example.com""")
            
            campaign_list = CampaignList(name='Import List')
            db.session.add(campaign_list)
            db.session.commit()
            
            result = csv_service.import_csv(csv_data, 'test.csv', campaign_list.id)
            
            # Should only import first occurrence
            assert result['imported'] == 1
            assert result['skipped'] == 1
            
            contacts = Contact.query.filter_by(phone='+15551234567').all()
            assert len(contacts) == 1
            assert contacts[0].first_name == 'John'
    
    def test_import_csv_missing_required_fields(self, csv_service, app):
        """Test importing CSV missing required fields"""
        with app.app_context():
            # CSV without phone column
            csv_data = StringIO("""first_name,last_name,email
John,Doe,john@example.com
Jane,Smith,jane@example.com""")
            
            campaign_list = CampaignList(name='Import List')
            db.session.add(campaign_list)
            db.session.commit()
            
            result = csv_service.import_csv(csv_data, 'test.csv', campaign_list.id)
            
            assert result['success'] is False
            assert 'phone' in result['message']
    
    def test_import_csv_empty_file(self, csv_service, app):
        """Test importing empty CSV file"""
        with app.app_context():
            csv_data = StringIO("")
            
            campaign_list = CampaignList(name='Import List')
            db.session.add(campaign_list)
            db.session.commit()
            
            result = csv_service.import_csv(csv_data, 'empty.csv', campaign_list.id)
            
            assert result['success'] is False
            assert result['imported'] == 0
    
    def test_import_csv_with_extra_columns(self, csv_service, app):
        """Test importing CSV with extra columns"""
        with app.app_context():
            csv_data = StringIO("""first_name,last_name,phone,email,extra_field,another_field
John,Doe,+15551234567,john@example.com,value1,value2
Jane,Smith,+15551234568,jane@example.com,value3,value4""")
            
            campaign_list = CampaignList(name='Import List')
            db.session.add(campaign_list)
            db.session.commit()
            
            result = csv_service.import_csv(csv_data, 'test.csv', campaign_list.id)
            
            # Should import successfully, ignoring extra columns
            assert result['success'] is True
            assert result['imported'] == 2
    
    def test_import_csv_phone_normalization(self, csv_service, app):
        """Test phone number normalization during import"""
        with app.app_context():
            csv_data = StringIO("""first_name,last_name,phone,email
John,Doe,5551234567,john@example.com
Jane,Smith,(555) 123-4568,jane@example.com
Bob,Johnson,1-555-123-4569,bob@example.com""")
            
            campaign_list = CampaignList(name='Import List')
            db.session.add(campaign_list)
            db.session.commit()
            
            result = csv_service.import_csv(csv_data, 'test.csv', campaign_list.id)
            
            assert result['imported'] == 3
            
            # Verify phones were normalized
            contacts = Contact.query.filter(Contact.phone.like('%555123456%')).all()
            assert len(contacts) == 3
            assert all(c.phone.startswith('+1') for c in contacts)
    
    def test_import_csv_with_custom_tags(self, csv_service, app):
        """Test importing with custom tag handling"""
        with app.app_context():
            csv_data = StringIO("""first_name,last_name,phone,email,custom_tag
John,Doe,+15551234567,john@example.com,VIP
Jane,Smith,+15551234568,jane@example.com,Premium""")
            
            campaign_list = CampaignList(name='Import List')
            db.session.add(campaign_list)
            db.session.commit()
            
            # Mock custom field mapping
            with patch.object(csv_service, '_map_csv_to_contact_fields') as mock_map:
                def custom_mapping(row):
                    fields = {
                        'first_name': row.get('first_name'),
                        'last_name': row.get('last_name'),
                        'phone': row.get('phone'),
                        'email': row.get('email'),
                        'tag': row.get('custom_tag')  # Map custom_tag to tag field
                    }
                    return fields
                
                mock_map.side_effect = custom_mapping
                
                result = csv_service.import_csv(csv_data, 'test.csv', campaign_list.id)
            
            assert result['imported'] == 2
            
            # Verify tags were set
            john = Contact.query.filter_by(phone='+15551234567').first()
            jane = Contact.query.filter_by(phone='+15551234568').first()
            assert john.tag == 'VIP'
            assert jane.tag == 'Premium'
    
    def test_import_csv_transaction_rollback(self, csv_service, app):
        """Test that failed imports rollback properly"""
        with app.app_context():
            csv_data = StringIO("""first_name,last_name,phone,email
John,Doe,+15551234567,john@example.com""")
            
            campaign_list = CampaignList(name='Import List')
            db.session.add(campaign_list)
            db.session.commit()
            
            # Mock database error during import
            with patch.object(db.session, 'commit', side_effect=Exception('DB Error')):
                result = csv_service.import_csv(csv_data, 'test.csv', campaign_list.id)
            
            assert result['success'] is False
            assert 'error' in result['message'].lower()
            
            # Verify no contacts were created
            contacts = Contact.query.filter_by(phone='+15551234567').all()
            assert len(contacts) == 0
    
    def test_validate_csv_structure_valid(self, csv_service):
        """Test CSV structure validation with valid data"""
        df = pd.DataFrame({
            'first_name': ['John'],
            'phone': ['+15551234567']
        })
        
        is_valid, message = csv_service._validate_csv_structure(df)
        assert is_valid is True
        assert message == ''
    
    def test_validate_csv_structure_missing_phone(self, csv_service):
        """Test CSV structure validation missing phone column"""
        df = pd.DataFrame({
            'first_name': ['John'],
            'last_name': ['Doe']
        })
        
        is_valid, message = csv_service._validate_csv_structure(df)
        assert is_valid is False
        assert 'phone' in message
    
    def test_validate_csv_structure_empty(self, csv_service):
        """Test CSV structure validation with empty DataFrame"""
        df = pd.DataFrame()
        
        is_valid, message = csv_service._validate_csv_structure(df)
        assert is_valid is False
        assert 'empty' in message.lower()
    
    def test_normalize_phone_number(self, csv_service):
        """Test phone number normalization"""
        test_cases = [
            ('5551234567', '+15551234567'),
            ('(555) 123-4567', '+15551234567'),
            ('1-555-123-4567', '+15551234567'),
            ('+1 555 123 4567', '+15551234567'),
            ('555.123.4567', '+15551234567'),
            ('+15551234567', '+15551234567'),  # Already normalized
        ]
        
        for input_phone, expected in test_cases:
            result = csv_service._normalize_phone_number(input_phone)
            assert result == expected
    
    def test_normalize_phone_number_invalid(self, csv_service):
        """Test phone normalization with invalid numbers"""
        invalid_phones = ['123', 'abc', '', None, '555-CALL-NOW']
        
        for phone in invalid_phones:
            result = csv_service._normalize_phone_number(phone)
            assert result is None
    
    def test_enrich_existing_contact(self, csv_service):
        """Test enriching existing contact data"""
        existing = Contact(
            first_name='John',
            phone='+15551234567'
        )
        
        new_data = {
            'first_name': 'John',
            'last_name': 'Doe',
            'email': 'john@example.com',
            'address': '123 Main St'
        }
        
        updated_fields = csv_service._enrich_existing_contact(existing, new_data)
        
        assert existing.last_name == 'Doe'
        assert existing.email == 'john@example.com'
        assert existing.address == '123 Main St'
        assert 'last_name' in updated_fields
        assert 'email' in updated_fields
        assert 'address' in updated_fields
        assert 'first_name' not in updated_fields  # Not updated since it's the same
    
    def test_get_import_history(self, csv_service, app):
        """Test getting import history"""
        with app.app_context():
            # Create sample imports
            imports = [
                CSVImport(
                    filename=f'import_{i}.csv',
                    total_rows=10 * i,
                    successful_imports=8 * i,
                    failed_imports=2 * i
                )
                for i in range(1, 4)
            ]
            db.session.add_all(imports)
            db.session.commit()
            
            history = csv_service.get_import_history()
            
            assert len(history) == 3
            # Should be ordered by newest first
            assert history[0].filename == 'import_3.csv'
            assert history[-1].filename == 'import_1.csv'
    
    def test_import_csv_with_list_membership_inactive(self, csv_service, app):
        """Test that existing contacts added to new list maintain their data"""
        with app.app_context():
            # Create existing contact in another list
            existing = Contact(
                first_name='John',
                last_name='Doe',
                phone='+15551234567',
                email='john@example.com'
            )
            db.session.add(existing)
            
            old_list = CampaignList(name='Old List')
            db.session.add(old_list)
            db.session.commit()
            
            # Add to old list
            old_membership = CampaignListMember(
                contact_id=existing.id,
                list_id=old_list.id,
                status='active'
            )
            db.session.add(old_membership)
            db.session.commit()
            
            # Import CSV with same contact to new list
            csv_data = StringIO("""first_name,last_name,phone,email
John,Doe,+15551234567,john@example.com""")
            
            new_list = CampaignList(name='New List')
            db.session.add(new_list)
            db.session.commit()
            
            result = csv_service.import_csv(csv_data, 'test.csv', new_list.id)
            
            # Verify contact is in both lists
            memberships = CampaignListMember.query.filter_by(contact_id=existing.id).all()
            assert len(memberships) == 2
            assert all(m.status == 'active' for m in memberships)