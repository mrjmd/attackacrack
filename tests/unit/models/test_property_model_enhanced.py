"""
Property Model Enhancement Tests - Enhanced Property model with 42+ PropertyRadar fields
TDD RED Phase: Write comprehensive tests BEFORE implementation

These tests cover:
1. Enhanced Property model with all PropertyRadar fields
2. Property-Contact many-to-many relationships
3. Data type validations and constraints
4. Relationships and foreign keys
"""

import pytest
from datetime import datetime, date
from decimal import Decimal
from sqlalchemy.exc import IntegrityError, DataError

from crm_database import Property, Contact, PropertyContact, db
from extensions import db as database


class TestEnhancedPropertyModel:
    """Test enhanced Property model with PropertyRadar fields"""
    
    @pytest.fixture
    def db_session(self, app):
        """Create database session for testing"""
        with app.app_context():
            database.create_all()
            yield database.session
            database.session.rollback()
            database.drop_all()
    
    @pytest.fixture
    def sample_property_data(self):
        """Sample PropertyRadar property data"""
        return {
            'property_type': 'SFR',
            'address': '455 MIDDLE ST',
            'city': 'BRAINTREE',
            'zip_code': '02184',
            'subdivision': 'BRAINTREE',
            'longitude': -70.987754,
            'latitude': 42.211216,
            'apn': 'BRAI-001001-000000-000018',
            'year_built': 1954,
            'purchase_date': date(2017, 7, 28),
            'purchase_months_since': 66,
            'square_feet': 2050,
            'bedrooms': 4,
            'bathrooms': 2,
            'estimated_value': Decimal('767509.00'),
            'estimated_equity': Decimal('402357.00'),
            'owner_name': 'LINKER,JON J & AIMEE C',
            'mail_address': '455 MIDDLE ST',
            'mail_city': 'BRAINTREE',
            'mail_state': 'MA',
            'mail_zip': '02184',
            'owner_occupied': True,
            'listed_for_sale': False,
            'listing_status': None,
            'foreclosure': False,
            'estimated_equity_percent': 52,
            'high_equity': True
        }
    
    @pytest.fixture
    def sample_contact_data(self):
        """Sample contact data for relationships"""
        return {
            'first_name': 'Jon',
            'last_name': 'Linker',
            'phone': '+13392224624',
            'email': 'linkeraimee@hotmail.com'
        }
    
    def test_property_model_exists(self):
        """Test that enhanced Property model exists with required fields"""
        # Should fail - enhanced Property model doesn't exist yet
        assert hasattr(Property, 'property_type')
        assert hasattr(Property, 'city')
        assert hasattr(Property, 'zip_code')
        assert hasattr(Property, 'longitude')
        assert hasattr(Property, 'latitude')
        assert hasattr(Property, 'apn')
        assert hasattr(Property, 'year_built')
        assert hasattr(Property, 'purchase_date')
        assert hasattr(Property, 'square_feet')
        assert hasattr(Property, 'bedrooms')
        assert hasattr(Property, 'bathrooms')
        assert hasattr(Property, 'estimated_value')
        assert hasattr(Property, 'estimated_equity')
    
    def test_property_many_to_many_contacts(self):
        """Test that Property has many-to-many relationship with Contact"""
        # Should fail - many-to-many relationship doesn't exist yet
        assert hasattr(Property, 'contacts')  # Relationship attribute
        
    def test_property_contact_association_table_exists(self):
        """Test that PropertyContact association table exists"""
        # Should fail - PropertyContact association table doesn't exist yet
        assert PropertyContact is not None
        assert hasattr(PropertyContact, 'property_id')
        assert hasattr(PropertyContact, 'contact_id')
        assert hasattr(PropertyContact, 'relationship_type')
        assert hasattr(PropertyContact, 'created_at')
    
    def test_create_property_with_all_fields(self, db_session, sample_property_data):
        """Test creating property with all PropertyRadar fields"""
        # Should fail - enhanced model fields don't exist yet
        property_obj = Property(**sample_property_data)
        db_session.add(property_obj)
        db_session.commit()
        
        # Verify all fields are saved
        assert property_obj.id is not None
        assert property_obj.property_type == 'SFR'
        assert property_obj.city == 'BRAINTREE'
        assert property_obj.zip_code == '02184'
        assert property_obj.longitude == -70.987754
        assert property_obj.latitude == 42.211216
        assert property_obj.apn == 'BRAI-001001-000000-000018'
        assert property_obj.year_built == 1954
        assert property_obj.purchase_date == date(2017, 7, 28)
        assert property_obj.square_feet == 2050
        assert property_obj.bedrooms == 4
        assert property_obj.bathrooms == 2
        assert property_obj.estimated_value == Decimal('767509.00')
        assert property_obj.estimated_equity == Decimal('402357.00')
    
    def test_property_mail_address_fields(self, db_session, sample_property_data):
        """Test property mail address fields are stored correctly"""
        # Should fail - mail address fields don't exist yet
        property_obj = Property(**sample_property_data)
        db_session.add(property_obj)
        db_session.commit()
        
        assert property_obj.mail_address == '455 MIDDLE ST'
        assert property_obj.mail_city == 'BRAINTREE'
        assert property_obj.mail_state == 'MA'
        assert property_obj.mail_zip == '02184'
    
    def test_property_status_flags(self, db_session, sample_property_data):
        """Test property status flags (boolean fields)"""
        # Should fail - status flag fields don't exist yet
        property_obj = Property(**sample_property_data)
        db_session.add(property_obj)
        db_session.commit()
        
        assert property_obj.owner_occupied is True
        assert property_obj.listed_for_sale is False
        assert property_obj.foreclosure is False
        assert property_obj.high_equity is True
    
    def test_property_financial_fields(self, db_session, sample_property_data):
        """Test property financial fields with proper decimal precision"""
        # Should fail - financial fields don't exist yet
        property_obj = Property(**sample_property_data)
        db_session.add(property_obj)
        db_session.commit()
        
        assert isinstance(property_obj.estimated_value, Decimal)
        assert isinstance(property_obj.estimated_equity, Decimal)
        assert property_obj.estimated_equity_percent == 52
        assert property_obj.estimated_value > 0
        assert property_obj.estimated_equity > 0
    
    def test_property_associate_with_multiple_contacts(self, db_session, sample_property_data, sample_contact_data):
        """Test associating property with multiple contacts"""
        # Should fail - many-to-many relationship doesn't exist yet
        # Create property
        property_obj = Property(**sample_property_data)
        db_session.add(property_obj)
        
        # Create primary contact
        primary_contact = Contact(**sample_contact_data)
        db_session.add(primary_contact)
        
        # Create secondary contact
        secondary_contact = Contact(
            first_name='Aimee',
            last_name='Linker', 
            phone='+17813161658',
            email='aimee@example.com'
        )
        db_session.add(secondary_contact)
        
        db_session.commit()
        
        # Associate contacts with property
        property_obj.contacts.append(primary_contact)
        property_obj.contacts.append(secondary_contact)
        db_session.commit()
        
        # Verify relationships
        assert len(property_obj.contacts) == 2
        assert primary_contact in property_obj.contacts
        assert secondary_contact in property_obj.contacts
        assert property_obj in primary_contact.properties
        assert property_obj in secondary_contact.properties
    
    def test_property_contact_relationship_types(self, db_session, sample_property_data, sample_contact_data):
        """Test property-contact relationship types (PRIMARY/SECONDARY)"""
        # Should fail - relationship type field doesn't exist yet
        property_obj = Property(**sample_property_data)
        contact = Contact(**sample_contact_data)
        db_session.add(property_obj)
        db_session.add(contact)
        db_session.commit()
        
        # Create association with relationship type
        association = PropertyContact(
            property_id=property_obj.id,
            contact_id=contact.id,
            relationship_type='PRIMARY'
        )
        db_session.add(association)
        db_session.commit()
        
        # Verify relationship type
        assert association.relationship_type == 'PRIMARY'
        assert association.property_id == property_obj.id
        assert association.contact_id == contact.id
    
    def test_property_unique_constraints(self, db_session, sample_property_data):
        """Test property unique constraints (address + zip or APN)"""
        # Should fail - unique constraints don't exist yet
        # Create first property
        property1 = Property(**sample_property_data)
        db_session.add(property1)
        db_session.commit()
        
        # Try to create duplicate property with same address + zip
        property2_data = sample_property_data.copy()
        property2 = Property(**property2_data)
        db_session.add(property2)
        
        # Should raise IntegrityError due to unique constraint
        with pytest.raises(IntegrityError):
            db_session.commit()
    
    def test_property_apn_unique_constraint(self, db_session, sample_property_data):
        """Test APN unique constraint"""
        # Should fail - APN unique constraint doesn't exist yet
        property1 = Property(**sample_property_data)
        db_session.add(property1)
        db_session.commit()
        
        # Try to create property with same APN but different address
        property2_data = sample_property_data.copy()
        property2_data['address'] = '123 DIFFERENT ST'
        property2 = Property(**property2_data)
        db_session.add(property2)
        
        # Should raise IntegrityError due to APN unique constraint
        with pytest.raises(IntegrityError):
            db_session.commit()
    
    def test_property_data_type_validations(self, db_session):
        """Test property data type validations"""
        # Should fail - data type validations don't exist yet
        # Test invalid longitude (should be between -180 and 180)
        with pytest.raises((DataError, ValueError)):
            property_obj = Property(
                address='123 Test St',
                longitude=181.0,  # Invalid longitude
                latitude=42.0
            )
            db_session.add(property_obj)
            db_session.commit()
    
    def test_property_nullable_fields(self, db_session):
        """Test that optional fields can be null"""
        # Should fail - model structure doesn't exist yet
        # Create property with minimal required fields
        property_obj = Property(
            address='123 Test St',
            # Optional fields should be nullable
            city=None,
            zip_code=None,
            longitude=None,
            latitude=None,
            year_built=None,
            purchase_date=None
        )
        db_session.add(property_obj)
        db_session.commit()
        
        assert property_obj.id is not None
        assert property_obj.city is None
        assert property_obj.year_built is None
    
    def test_property_default_values(self, db_session):
        """Test default values for boolean fields"""
        # Should fail - default values not set yet
        property_obj = Property(address='123 Test St')
        db_session.add(property_obj)
        db_session.commit()
        
        # Boolean fields should default to False
        assert property_obj.owner_occupied is False
        assert property_obj.listed_for_sale is False
        assert property_obj.foreclosure is False
        assert property_obj.high_equity is False
    
    def test_property_audit_timestamps(self, db_session, sample_property_data):
        """Test that property has created_at and updated_at timestamps"""
        # Should fail - audit timestamps don't exist yet
        property_obj = Property(**sample_property_data)
        db_session.add(property_obj)
        db_session.commit()
        
        assert hasattr(property_obj, 'created_at')
        assert hasattr(property_obj, 'updated_at')
        assert property_obj.created_at is not None
        assert property_obj.updated_at is not None
        assert isinstance(property_obj.created_at, datetime)
        assert isinstance(property_obj.updated_at, datetime)
    
    def test_property_string_representation(self, db_session, sample_property_data):
        """Test property string representation (__repr__)"""
        # Should fail - custom __repr__ doesn't exist yet
        property_obj = Property(**sample_property_data)
        db_session.add(property_obj)
        db_session.commit()
        
        repr_str = repr(property_obj)
        assert '455 MIDDLE ST' in repr_str
        assert 'BRAINTREE' in repr_str
        assert '02184' in repr_str
    
    def test_property_search_methods(self, db_session, sample_property_data):
        """Test property search and query methods"""
        # Should fail - search methods don't exist yet
        property_obj = Property(**sample_property_data)
        db_session.add(property_obj)
        db_session.commit()
        
        # Test search by address
        found = Property.search_by_address('455 MIDDLE ST')
        assert property_obj in found
        
        # Test search by zip
        found = Property.search_by_zip('02184')
        assert property_obj in found
        
        # Test search by city
        found = Property.search_by_city('BRAINTREE')
        assert property_obj in found
    
    def test_property_equity_calculations(self, db_session, sample_property_data):
        """Test property equity calculation methods"""
        # Should fail - calculation methods don't exist yet
        property_obj = Property(**sample_property_data)
        db_session.add(property_obj)
        db_session.commit()
        
        # Test equity percentage calculation
        assert property_obj.calculate_equity_percentage() == 52
        
        # Test high equity determination
        assert property_obj.is_high_equity() is True
        
        # Test equity tier classification
        assert property_obj.get_equity_tier() in ['high', 'medium', 'low']
    
    def test_property_geolocation_methods(self, db_session, sample_property_data):
        """Test property geolocation utility methods"""
        # Should fail - geolocation methods don't exist yet
        property_obj = Property(**sample_property_data)
        db_session.add(property_obj)
        db_session.commit()
        
        # Test coordinate validation
        assert property_obj.has_valid_coordinates() is True
        
        # Test distance calculation (needs another property to compare)
        other_property = Property(
            address='123 Other St',
            longitude=-70.990000,
            latitude=42.210000
        )
        db_session.add(other_property)
        db_session.commit()
        
        distance = property_obj.distance_to(other_property)
        assert isinstance(distance, float)
        assert distance > 0
    
    def test_property_contact_cascade_deletion(self, db_session, sample_property_data, sample_contact_data):
        """Test that property-contact associations are properly cleaned up"""
        # Should fail - cascade rules don't exist yet
        property_obj = Property(**sample_property_data)
        contact = Contact(**sample_contact_data)
        db_session.add(property_obj)
        db_session.add(contact)
        db_session.commit()
        
        # Associate them
        association = PropertyContact(
            property_id=property_obj.id,
            contact_id=contact.id,
            relationship_type='PRIMARY'
        )
        db_session.add(association)
        db_session.commit()
        
        # Delete property
        db_session.delete(property_obj)
        db_session.commit()
        
        # Association should be deleted (cascade)
        remaining_associations = db_session.query(PropertyContact).filter_by(
            property_id=property_obj.id
        ).all()
        assert len(remaining_associations) == 0
        
        # Contact should still exist (no cascade)
        remaining_contact = db_session.query(Contact).filter_by(id=contact.id).first()
        assert remaining_contact is not None
    
    def test_property_bulk_operations(self, db_session):
        """Test bulk property operations for import performance"""
        # Should fail - bulk operation methods don't exist yet
        properties_data = []
        for i in range(100):
            properties_data.append({
                'address': f'{i} Test Street',
                'city': 'Test City',
                'zip_code': f'0{i:04d}',
                'estimated_value': Decimal('500000.00')
            })
        
        # Test bulk insert
        created_properties = Property.bulk_create(properties_data)
        assert len(created_properties) == 100
        
        # Test bulk update
        update_data = {'estimated_value': Decimal('600000.00')}
        updated_count = Property.bulk_update(created_properties, update_data)
        assert updated_count == 100
