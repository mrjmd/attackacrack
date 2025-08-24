"""
TDD Tests for PhoneValidationRepository - REPOSITORY LAYER TESTS

TEST-DRIVEN DEVELOPMENT: These tests are written BEFORE implementation
Purpose: Test the repository layer for phone validation cache persistence

Features tested:
- CRUD operations for phone validation records
- Cache expiration queries
- Bulk insertion for CSV imports
- Search and filtering capabilities
- Database constraint validation
"""

import pytest
from datetime import datetime, timedelta
from utils.datetime_utils import utc_now, ensure_utc
from repositories.phone_validation_repository import PhoneValidationRepository
from crm_database import PhoneValidation
from repositories.base_repository import PaginationParams, SortOrder


@pytest.fixture
def phone_validation_repository(db_session):
    """Create PhoneValidationRepository with test database session"""
    return PhoneValidationRepository(session=db_session)


@pytest.fixture
def sample_validation_data():
    """Sample validation data for testing"""
    return {
        'phone_number': '+14158586273',
        'is_valid': True,
        'line_type': 'mobile',
        'carrier': 'Verizon Wireless',
        'country_code': 'US',
        'country_name': 'United States',
        'location': 'California',
        'api_response': '{"valid": true, "line_type": "mobile"}',
        'created_at': utc_now()
    }


class TestPhoneValidationRepositoryCRUD:
    """Test basic CRUD operations for PhoneValidationRepository"""
    
    def test_create_phone_validation(self, phone_validation_repository, sample_validation_data, db_session):
        """Test creating a new phone validation record"""
        # Act
        validation = phone_validation_repository.create(**sample_validation_data)
        db_session.flush()
        
        # Assert
        assert validation.id is not None
        assert validation.phone_number == sample_validation_data['phone_number']
        assert validation.is_valid is True
        assert validation.line_type == 'mobile'
        assert validation.carrier == 'Verizon Wireless'
        assert validation.country_code == 'US'
        assert validation.created_at is not None
    
    def test_find_by_phone_number(self, phone_validation_repository, sample_validation_data, db_session):
        """Test finding validation by phone number"""
        # Arrange
        created_validation = phone_validation_repository.create(**sample_validation_data)
        db_session.flush()
        
        # Act
        found_validation = phone_validation_repository.find_one_by(
            phone_number=sample_validation_data['phone_number']
        )
        
        # Assert
        assert found_validation is not None
        assert found_validation.id == created_validation.id
        assert found_validation.phone_number == sample_validation_data['phone_number']
        assert found_validation.is_valid is True
    
    def test_find_by_phone_number_not_found(self, phone_validation_repository):
        """Test finding validation for non-existent phone number"""
        # Act
        found_validation = phone_validation_repository.find_one_by(
            phone_number='+19999999999'
        )
        
        # Assert
        assert found_validation is None
    
    def test_update_validation_record(self, phone_validation_repository, sample_validation_data, db_session):
        """Test updating an existing validation record"""
        # Arrange
        validation = phone_validation_repository.create(**sample_validation_data)
        db_session.flush()
        
        # Act
        updated_validation = phone_validation_repository.update(
            validation,
            carrier='Updated Carrier',
            location='Updated Location'
        )
        db_session.flush()
        
        # Assert
        assert updated_validation.carrier == 'Updated Carrier'
        assert updated_validation.location == 'Updated Location'
        assert updated_validation.phone_number == sample_validation_data['phone_number']  # Unchanged
    
    def test_delete_validation_record(self, phone_validation_repository, sample_validation_data, db_session):
        """Test deleting a validation record"""
        # Arrange
        validation = phone_validation_repository.create(**sample_validation_data)
        db_session.flush()
        validation_id = validation.id
        
        # Act
        success = phone_validation_repository.delete(validation)
        db_session.flush()
        
        # Assert
        assert success is True
        
        # Verify record is deleted
        deleted_validation = phone_validation_repository.get_by_id(validation_id)
        assert deleted_validation is None


class TestPhoneValidationRepositorySearch:
    """Test search and filtering capabilities"""
    
    def test_find_valid_mobile_numbers(self, phone_validation_repository, db_session):
        """Test finding all valid mobile numbers"""
        # Arrange - Create mix of validation records
        test_data = [
            {
                'phone_number': '+14158586273',
                'is_valid': True,
                'line_type': 'mobile',
                'carrier': 'Verizon'
            },
            {
                'phone_number': '+14155551234', 
                'is_valid': True,
                'line_type': 'landline',
                'carrier': 'Pacific Bell'
            },
            {
                'phone_number': '+11234567890',
                'is_valid': False,
                'line_type': '',
                'carrier': ''
            },
            {
                'phone_number': '+12125559999',
                'is_valid': True,
                'line_type': 'mobile',
                'carrier': 'T-Mobile'
            }
        ]
        
        for data in test_data:
            phone_validation_repository.create(**data)
        db_session.flush()
        
        # Act
        mobile_validations = phone_validation_repository.find_by(
            is_valid=True,
            line_type='mobile'
        )
        
        # Assert
        assert len(mobile_validations) == 2
        phone_numbers = [v.phone_number for v in mobile_validations]
        assert '+14158586273' in phone_numbers
        assert '+12125559999' in phone_numbers
    
    def test_find_expired_validations(self, phone_validation_repository, db_session):
        """Test finding validations older than specified date"""
        # Arrange
        now = utc_now()
        
        # Recent validation
        phone_validation_repository.create(
            phone_number='+14158586273',
            is_valid=True,
            line_type='mobile',
            created_at=now
        )
        
        # Expired validation
        phone_validation_repository.create(
            phone_number='+14155551234',
            is_valid=True,
            line_type='mobile',
            created_at=now - timedelta(days=31)
        )
        
        db_session.flush()
        
        # Act
        expired_validations = phone_validation_repository.find_expired(days=30)
        
        # Assert
        assert len(expired_validations) == 1
        assert expired_validations[0].phone_number == '+14155551234'
    
    def test_count_validations_by_criteria(self, phone_validation_repository, db_session):
        """Test counting validations by various criteria"""
        # Arrange
        test_data = [
            {'phone_number': '+14158586273', 'is_valid': True, 'line_type': 'mobile'},
            {'phone_number': '+14155551234', 'is_valid': True, 'line_type': 'landline'},
            {'phone_number': '+11234567890', 'is_valid': False, 'line_type': ''},
            {'phone_number': '+12125559999', 'is_valid': True, 'line_type': 'mobile'}
        ]
        
        for data in test_data:
            phone_validation_repository.create(**data)
        db_session.flush()
        
        # Act & Assert
        total_count = phone_validation_repository.count()
        assert total_count == 4
        
        valid_count = phone_validation_repository.count(is_valid=True)
        assert valid_count == 3
        
        mobile_count = phone_validation_repository.count(is_valid=True, line_type='mobile')
        assert mobile_count == 2
        
        invalid_count = phone_validation_repository.count(is_valid=False)
        assert invalid_count == 1
    
    def test_search_by_carrier(self, phone_validation_repository, db_session):
        """Test searching validations by carrier"""
        # Arrange
        carriers_data = [
            {'phone_number': '+14158586273', 'carrier': 'Verizon Wireless', 'is_valid': True},
            {'phone_number': '+14155551234', 'carrier': 'AT&T', 'is_valid': True},
            {'phone_number': '+12125559999', 'carrier': 'Verizon Wireless', 'is_valid': True}
        ]
        
        for data in carriers_data:
            phone_validation_repository.create(**data)
        db_session.flush()
        
        # Act
        verizon_validations = phone_validation_repository.search(
            'Verizon', 
            fields=['carrier']
        )
        
        # Assert
        assert len(verizon_validations) == 2
        for validation in verizon_validations:
            assert 'Verizon' in validation.carrier


class TestPhoneValidationRepositoryBulkOperations:
    """Test bulk operations for large datasets"""
    
    def test_create_many_validations(self, phone_validation_repository, db_session):
        """Test bulk creation of validation records"""
        # Arrange
        bulk_data = []
        for i in range(10):
            bulk_data.append({
                'phone_number': f'+1415555{i:04d}',
                'is_valid': True,
                'line_type': 'mobile',
                'carrier': f'Carrier {i}',
                'country_code': 'US'
            })
        
        # Act
        created_validations = phone_validation_repository.create_many(bulk_data)
        db_session.flush()
        
        # Assert
        assert len(created_validations) == 10
        
        for i, validation in enumerate(created_validations):
            assert validation.phone_number == f'+1415555{i:04d}'
            assert validation.carrier == f'Carrier {i}'
            assert validation.is_valid is True
        
        # Verify in database
        total_count = phone_validation_repository.count()
        assert total_count == 10
    
    def test_delete_many_expired(self, phone_validation_repository, db_session):
        """Test bulk deletion of expired validation records"""
        # Arrange
        now = utc_now()
        
        # Create fresh validations
        for i in range(3):
            phone_validation_repository.create(
                phone_number=f'+1415555{i:04d}',
                is_valid=True,
                line_type='mobile',
                created_at=now
            )
        
        # Create expired validations
        for i in range(5):
            phone_validation_repository.create(
                phone_number=f'+1415666{i:04d}',
                is_valid=True,
                line_type='mobile',
                created_at=now - timedelta(days=31)
            )
        
        db_session.flush()
        
        # Verify initial state
        initial_count = phone_validation_repository.count()
        assert initial_count == 8
        
        # Act
        cutoff_date = now - timedelta(days=30)
        deleted_count = phone_validation_repository.delete_many_expired(cutoff_date)
        db_session.flush()
        
        # Assert
        assert deleted_count == 5
        
        # Verify remaining records
        remaining_count = phone_validation_repository.count()
        assert remaining_count == 3
    
    def test_update_many_carrier_info(self, phone_validation_repository, db_session):
        """Test bulk update of carrier information"""
        # Arrange
        for i in range(5):
            phone_validation_repository.create(
                phone_number=f'+1415555{i:04d}',
                is_valid=True,
                line_type='mobile',
                carrier='Old Carrier',
                country_code='US'
            )
        
        db_session.flush()
        
        # Act
        updated_count = phone_validation_repository.update_many(
            filters={'carrier': 'Old Carrier'},
            updates={'carrier': 'Updated Carrier'}
        )
        db_session.flush()
        
        # Assert
        assert updated_count == 5
        
        # Verify updates
        updated_validations = phone_validation_repository.find_by(carrier='Updated Carrier')
        assert len(updated_validations) == 5
        
        old_validations = phone_validation_repository.find_by(carrier='Old Carrier')
        assert len(old_validations) == 0


class TestPhoneValidationRepositoryPagination:
    """Test pagination for large result sets"""
    
    def test_get_paginated_validations(self, phone_validation_repository, db_session):
        """Test paginated retrieval of validation records"""
        # Arrange
        for i in range(25):
            phone_validation_repository.create(
                phone_number=f'+1415555{i:04d}',
                is_valid=True,
                line_type='mobile',
                carrier=f'Carrier {i}',
                created_at=utc_now() - timedelta(minutes=i)
            )
        
        db_session.flush()
        
        # Act
        pagination = PaginationParams(page=1, per_page=10)
        result = phone_validation_repository.get_paginated(
            pagination=pagination,
            order_by='created_at',
            order=SortOrder.DESC
        )
        
        # Assert
        assert result.total == 25
        assert result.page == 1
        assert result.per_page == 10
        assert result.pages == 3
        assert len(result.items) == 10
        assert result.has_next is True
        assert result.has_prev is False
        
        # Verify ordering (most recent first)
        first_item = result.items[0]
        last_item = result.items[-1]
        assert first_item.created_at > last_item.created_at
    
    def test_get_paginated_with_filters(self, phone_validation_repository, db_session):
        """Test paginated retrieval with filtering"""
        # Arrange
        for i in range(20):
            line_type = 'mobile' if i % 2 == 0 else 'landline'
            phone_validation_repository.create(
                phone_number=f'+1415555{i:04d}',
                is_valid=True,
                line_type=line_type,
                carrier='Test Carrier'
            )
        
        db_session.flush()
        
        # Act
        pagination = PaginationParams(page=1, per_page=5)
        result = phone_validation_repository.get_paginated(
            pagination=pagination,
            filters={'line_type': 'mobile'}
        )
        
        # Assert
        assert result.total == 10  # Only mobile numbers
        assert len(result.items) == 5
        assert result.pages == 2
        
        # Verify all items are mobile
        for item in result.items:
            assert item.line_type == 'mobile'


class TestPhoneValidationRepositoryConstraints:
    """Test database constraints and validation"""
    
    def test_phone_number_uniqueness(self, phone_validation_repository, db_session):
        """Test that phone numbers must be unique"""
        # Arrange
        phone_number = '+14158586273'
        
        # Create first validation
        validation1 = phone_validation_repository.create(
            phone_number=phone_number,
            is_valid=True,
            line_type='mobile'
        )
        db_session.flush()
        
        # Act & Assert - Should raise integrity error for duplicate
        with pytest.raises(Exception):  # SQLAlchemy will raise an integrity error
            phone_validation_repository.create(
                phone_number=phone_number,
                is_valid=False,
                line_type='landline'
            )
            db_session.flush()
    
    def test_required_fields_validation(self, phone_validation_repository, db_session):
        """Test that required fields are enforced"""
        # Act & Assert - Should raise error for missing phone_number
        with pytest.raises(Exception):
            phone_validation_repository.create(
                is_valid=True,
                line_type='mobile'
                # phone_number is missing
            )
            db_session.flush()
    
    def test_boolean_field_validation(self, phone_validation_repository, db_session):
        """Test boolean field constraints"""
        # Arrange & Act
        validation = phone_validation_repository.create(
            phone_number='+14158586273',
            is_valid=True,  # Boolean field
            line_type='mobile'
        )
        db_session.flush()
        
        # Assert
        assert validation.is_valid is True
        assert isinstance(validation.is_valid, bool)


class TestPhoneValidationRepositoryCustomMethods:
    """Test custom repository methods specific to phone validation"""
    
    def test_find_by_country_code(self, phone_validation_repository, db_session):
        """Test finding validations by country code"""
        # Arrange
        countries_data = [
            {'phone_number': '+14158586273', 'country_code': 'US', 'is_valid': True},
            {'phone_number': '+14155551234', 'country_code': 'US', 'is_valid': True},
            {'phone_number': '+447700123456', 'country_code': 'GB', 'is_valid': True}
        ]
        
        for data in countries_data:
            phone_validation_repository.create(**data)
        db_session.flush()
        
        # Act
        us_validations = phone_validation_repository.find_by_country_code('US')
        gb_validations = phone_validation_repository.find_by_country_code('GB')
        
        # Assert
        assert len(us_validations) == 2
        assert len(gb_validations) == 1
        
        for validation in us_validations:
            assert validation.country_code == 'US'
    
    def test_get_validation_summary(self, phone_validation_repository, db_session):
        """Test getting validation summary statistics"""
        # Arrange
        summary_data = [
            {'phone_number': '+14158586273', 'is_valid': True, 'line_type': 'mobile'},
            {'phone_number': '+14155551234', 'is_valid': True, 'line_type': 'landline'},
            {'phone_number': '+11234567890', 'is_valid': False, 'line_type': ''},
            {'phone_number': '+12125559999', 'is_valid': True, 'line_type': 'mobile'},
            {'phone_number': '+13235551234', 'is_valid': False, 'line_type': ''}
        ]
        
        for data in summary_data:
            phone_validation_repository.create(**data)
        db_session.flush()
        
        # Act
        summary = phone_validation_repository.get_validation_summary()
        
        # Assert
        assert summary['total'] == 5
        assert summary['valid'] == 3
        assert summary['invalid'] == 2
        assert summary['mobile'] == 2
        assert summary['landline'] == 1
        assert summary['validation_rate'] == 60.0  # 3/5 * 100
    
    def test_find_recent_validations(self, phone_validation_repository, db_session):
        """Test finding validations from recent time period"""
        # Arrange
        now = utc_now()
        
        # Recent validations
        for i in range(3):
            phone_validation_repository.create(
                phone_number=f'+1415555{i:04d}',
                is_valid=True,
                line_type='mobile',
                created_at=now - timedelta(hours=i)
            )
        
        # Old validations
        for i in range(2):
            phone_validation_repository.create(
                phone_number=f'+1415666{i:04d}',
                is_valid=True,
                line_type='mobile',
                created_at=now - timedelta(days=7 + i)
            )
        
        db_session.flush()
        
        # Act
        recent_validations = phone_validation_repository.find_recent(days=3)
        
        # Assert
        assert len(recent_validations) == 3
        
        for validation in recent_validations:
            # Ensure both datetimes are timezone-aware for comparison
            validation_created_at = ensure_utc(validation.created_at)
            cutoff_date = ensure_utc(now - timedelta(days=3))
            assert validation_created_at > cutoff_date
