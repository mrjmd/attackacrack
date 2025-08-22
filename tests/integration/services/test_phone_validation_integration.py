"""
TDD Integration Tests for PhoneValidationService

TEST-DRIVEN DEVELOPMENT: These tests are written BEFORE implementation
Purpose: Test PhoneValidationService integration with database and repository layer

Integration features tested:
- Database persistence of validation results
- Repository layer integration
- Service registry dependency injection
- Real database transactions and rollback
- Cache expiration with database queries
- Bulk validation with database batching
"""

import pytest
from unittest.mock import patch, Mock
from datetime import datetime, timedelta
from services.phone_validation_service import PhoneValidationService
from repositories.phone_validation_repository import PhoneValidationRepository
from crm_database import PhoneValidation
from services.common.result import Result
import time


@pytest.fixture
def phone_validation_repository(db_session):
    """Create real PhoneValidationRepository with test database"""
    return PhoneValidationRepository(session=db_session, model_class=PhoneValidation)


@pytest.fixture
def phone_validation_service(phone_validation_repository):
    """Create PhoneValidationService with real repository"""
    with patch('os.environ.get') as mock_env:
        mock_env.side_effect = lambda key, default=None: {
            'NUMVERIFY_API_KEY': 'test_api_key',
            'NUMVERIFY_BASE_URL': 'http://apilayer.net/api/validate'
        }.get(key, default)
        
        return PhoneValidationService(
            validation_repository=phone_validation_repository
        )


@pytest.fixture
def mock_numverify_api():
    """Mock NumVerify API responses for integration tests"""
    def _mock_response(phone_number):
        """Generate mock response based on phone number"""
        mock_response = Mock()
        mock_response.status_code = 200
        
        # Define different responses for test numbers
        if phone_number == '+14158586273':
            mock_response.json.return_value = {
                'valid': True,
                'number': '14158586273',
                'local_format': '4158586273',
                'international_format': '+14158586273',
                'country_code': 'US',
                'country_name': 'United States of America',
                'location': 'California',
                'carrier': 'Verizon Wireless',
                'line_type': 'mobile'
            }
        elif phone_number == '+14155551234':
            mock_response.json.return_value = {
                'valid': True,
                'number': '14155551234',
                'local_format': '4155551234',
                'international_format': '+14155551234',
                'country_code': 'US',
                'location': 'California',
                'carrier': 'Pacific Bell',
                'line_type': 'landline'
            }
        elif 'invalid' in phone_number or phone_number == '+11234567890':
            mock_response.json.return_value = {
                'valid': False,
                'number': phone_number[1:] if phone_number.startswith('+') else phone_number,
                'line_type': ''
            }
        else:
            # Default valid mobile response
            mock_response.json.return_value = {
                'valid': True,
                'number': phone_number[1:] if phone_number.startswith('+') else phone_number,
                'country_code': 'US',
                'carrier': 'Test Carrier',
                'line_type': 'mobile'
            }
        
        return mock_response
    
    def _api_call(url, **kwargs):
        phone = kwargs.get('params', {}).get('number', '')
        return _mock_response(phone)
    
    with patch('requests.get', side_effect=_api_call) as mock_get:
        yield mock_get


class TestPhoneValidationDatabaseIntegration:
    """Test PhoneValidationService database integration"""
    
    def test_validate_phone_saves_to_database(self, phone_validation_service, phone_validation_repository, mock_numverify_api, db_session):
        """Test that validation results are saved to database"""
        # Arrange
        phone_number = '+14158586273'
        
        # Verify database is empty initially
        initial_count = phone_validation_repository.count()
        assert initial_count == 0
        
        # Act
        result = phone_validation_service.validate_phone(phone_number)
        db_session.commit()  # Commit to see the changes
        
        # Assert
        assert result.success is True
        
        # Verify record was saved to database
        final_count = phone_validation_repository.count()
        assert final_count == 1
        
        # Verify saved data
        saved_validation = phone_validation_repository.find_one_by(phone_number=phone_number)
        assert saved_validation is not None
        assert saved_validation.phone_number == phone_number
        assert saved_validation.is_valid is True
        assert saved_validation.line_type == 'mobile'
        assert saved_validation.carrier == 'Verizon Wireless'
        assert saved_validation.country_code == 'US'
        assert saved_validation.created_at is not None
    
    def test_validate_phone_retrieves_from_database_cache(self, phone_validation_service, phone_validation_repository, mock_numverify_api, db_session):
        """Test that cached validation results are retrieved from database"""
        # Arrange
        phone_number = '+14158586273'
        
        # First validation - should hit API and save to DB
        result1 = phone_validation_service.validate_phone(phone_number)
        db_session.commit()
        
        assert result1.success is True
        assert result1.data['from_cache'] is False
        api_call_count_1 = mock_numverify_api.call_count
        
        # Second validation - should use cache
        result2 = phone_validation_service.validate_phone(phone_number)
        
        # Assert
        assert result2.success is True
        assert result2.data['from_cache'] is True
        assert result2.data['phone_number'] == phone_number
        assert result2.data['valid'] is True
        assert result2.data['line_type'] == 'mobile'
        
        # Verify no additional API call was made
        assert mock_numverify_api.call_count == api_call_count_1
    
    def test_bulk_validation_database_persistence(self, phone_validation_service, phone_validation_repository, mock_numverify_api, db_session):
        """Test that bulk validation results are persisted to database"""
        # Arrange
        phone_numbers = ['+14158586273', '+14155551234', '+11234567890']
        
        # Verify database is empty
        initial_count = phone_validation_repository.count()
        assert initial_count == 0
        
        # Act
        result = phone_validation_service.validate_bulk(phone_numbers)
        db_session.commit()
        
        # Assert
        assert result.success is True
        assert result.data['total_processed'] == 3
        
        # Verify all results were saved to database
        final_count = phone_validation_repository.count()
        assert final_count == 3
        
        # Check individual records
        mobile_record = phone_validation_repository.find_one_by(phone_number='+14158586273')
        assert mobile_record.is_valid is True
        assert mobile_record.line_type == 'mobile'
        
        landline_record = phone_validation_repository.find_one_by(phone_number='+14155551234')
        assert landline_record.is_valid is True
        assert landline_record.line_type == 'landline'
        
        invalid_record = phone_validation_repository.find_one_by(phone_number='+11234567890')
        assert invalid_record.is_valid is False
    
    def test_cache_expiration_with_database(self, phone_validation_service, phone_validation_repository, mock_numverify_api, db_session):
        """Test that expired cache entries are updated in database"""
        # Arrange
        phone_number = '+14158586273'
        
        # Create an expired validation record
        expired_validation = PhoneValidation(
            phone_number=phone_number,
            is_valid=True,
            line_type='mobile',
            carrier='Old Carrier',
            country_code='US',
            created_at=datetime.utcnow() - timedelta(days=31)  # Expired
        )
        
        phone_validation_repository.create(
            phone_number=phone_number,
            is_valid=True,
            line_type='mobile',
            carrier='Old Carrier',
            country_code='US',
            created_at=datetime.utcnow() - timedelta(days=31)
        )
        db_session.commit()
        
        # Verify expired record exists
        initial_record = phone_validation_repository.find_one_by(phone_number=phone_number)
        assert initial_record.carrier == 'Old Carrier'
        
        # Act - Should trigger fresh validation due to expiration
        result = phone_validation_service.validate_phone(phone_number)
        db_session.commit()
        
        # Assert
        assert result.success is True
        assert result.data['from_cache'] is False  # Fresh validation
        
        # Verify new record was created (or old one updated)
        records = phone_validation_repository.find_by(phone_number=phone_number)
        
        # Should have updated record with fresh carrier
        fresh_record = records[0]  # Should be only one record now (updated)
        assert fresh_record.carrier == 'Verizon Wireless'  # From mock API
        assert fresh_record.validation_date > initial_record.created_at  # Validation was refreshed
    
    def test_database_transaction_rollback_on_error(self, phone_validation_service, phone_validation_repository, db_session):
        """Test that database transactions are rolled back on API errors"""
        # Arrange
        phone_number = '+14158586273'
        
        with patch('requests.get') as mock_get:
            # Mock API error
            mock_get.side_effect = Exception('Database connection error')
            
            # Verify database is empty
            initial_count = phone_validation_repository.count()
            assert initial_count == 0
            
            # Act
            result = phone_validation_service.validate_phone(phone_number)
            
            # Assert
            assert result.success is False
            
            # Verify no partial data was saved
            final_count = phone_validation_repository.count()
            assert final_count == 0
    
    def test_clear_expired_cache_database_integration(self, phone_validation_service, phone_validation_repository, db_session):
        """Test clearing expired cache entries from database"""
        # Arrange - Create mix of fresh and expired records
        fresh_phones = ['+14158586273', '+14155551234']
        expired_phones = ['+12125551234', '+13235551234']
        
        # Create fresh records
        for phone in fresh_phones:
            phone_validation_repository.create(
                phone_number=phone,
                is_valid=True,
                line_type='mobile',
                carrier='Test Carrier',
                country_code='US',
                created_at=datetime.utcnow()
            )
        
        # Create expired records
        for phone in expired_phones:
            phone_validation_repository.create(
                phone_number=phone,
                is_valid=True,
                line_type='mobile',
                carrier='Expired Carrier',
                country_code='US',
                created_at=datetime.utcnow() - timedelta(days=31)
            )
        
        db_session.commit()
        
        # Verify initial state
        total_count = phone_validation_repository.count()
        assert total_count == 4
        
        # Act
        result = phone_validation_service.clear_expired_cache(days=30)
        db_session.commit()
        
        # Assert
        assert result.success is True
        assert result.data['deleted_count'] == 2
        
        # Verify only expired records were deleted
        remaining_count = phone_validation_repository.count()
        assert remaining_count == 2
        
        # Verify fresh records still exist
        for phone in fresh_phones:
            record = phone_validation_repository.find_one_by(phone_number=phone)
            assert record is not None
        
        # Verify expired records were deleted
        for phone in expired_phones:
            record = phone_validation_repository.find_one_by(phone_number=phone)
            assert record is None


class TestPhoneValidationServiceRegistryIntegration:
    """Test PhoneValidationService integration with service registry"""
    
    def test_service_registry_provides_validation_service(self, app, db_session):
        """Test that PhoneValidationService can be retrieved from service registry"""
        with app.app_context():
            # Act
            validation_service = app.services.get('phone_validation')
            
            # Assert
            assert validation_service is not None
            assert isinstance(validation_service, PhoneValidationService)
            assert hasattr(validation_service, 'validation_repository')
            assert validation_service.validation_repository is not None
    
    def test_service_uses_correct_repository_from_registry(self, app, db_session):
        """Test that service registry injects correct repository"""
        with app.app_context():
            # Act
            validation_service = app.services.get('phone_validation')
            repository = app.services.get('phone_validation_repository')
            
            # Assert
            assert validation_service.validation_repository is repository
            assert repository.session is db_session
    
    def test_service_registry_dependency_injection(self, app, db_session, mock_numverify_api):
        """Test that service registry properly injects dependencies"""
        with app.app_context():
            # Arrange
            validation_service = app.services.get('phone_validation')
            phone_number = '+14158586273'
            
            # Act
            result = validation_service.validate_phone(phone_number)
            
            # Assert
            assert result.success is True
            
            # Verify the injected repository was used
            repository = app.services.get('phone_validation_repository')
            saved_record = repository.find_one_by(phone_number=phone_number)
            assert saved_record is not None


class TestPhoneValidationCSVIntegrationWorkflow:
    """Test PhoneValidationService integration with CSV import workflow"""
    
    def test_csv_validation_with_database_persistence(self, phone_validation_service, phone_validation_repository, mock_numverify_api, db_session):
        """Test CSV phone validation with database persistence"""
        # Arrange - Simulate CSV import data
        csv_data = [
            {'phone': '+14158586273', 'name': 'John Doe', 'email': 'john@example.com'},
            {'phone': '+14155551234', 'name': 'Jane Smith', 'email': 'jane@example.com'},
            {'phone': '+11234567890', 'name': 'Invalid User', 'email': 'invalid@example.com'},
            {'phone': '+12125559999', 'name': 'Bob Wilson', 'email': 'bob@example.com'}
        ]
        
        # Act
        result = phone_validation_service.validate_csv_import(csv_data, phone_field='phone')
        db_session.commit()
        
        # Assert
        assert result.success is True
        assert result.data['total_rows'] == 4
        assert result.data['valid_phones'] >= 3  # At least 3 should be valid
        
        # Verify database persistence
        total_validations = phone_validation_repository.count()
        assert total_validations == 4  # All numbers should be validated and cached
        
        # Check specific validations
        mobile_validation = phone_validation_repository.find_one_by(phone_number='+14158586273')
        assert mobile_validation.is_valid is True
        assert mobile_validation.line_type == 'mobile'
        
        landline_validation = phone_validation_repository.find_one_by(phone_number='+14155551234')
        assert landline_validation.is_valid is True
        assert landline_validation.line_type == 'landline'
        
        invalid_validation = phone_validation_repository.find_one_by(phone_number='+11234567890')
        assert invalid_validation.is_valid is False
    
    def test_csv_validation_with_partial_cache_hits(self, phone_validation_service, phone_validation_repository, mock_numverify_api, db_session):
        """Test CSV validation where some numbers are already cached"""
        # Arrange - Pre-populate cache with some numbers
        cached_phone = '+14158586273'
        phone_validation_repository.create(
            phone_number=cached_phone,
            is_valid=True,
            line_type='mobile',
            carrier='Cached Carrier',
            country_code='US',
            created_at=datetime.utcnow()
        )
        db_session.commit()
        
        csv_data = [
            {'phone': cached_phone, 'name': 'Cached User'},  # Should use cache
            {'phone': '+14155551234', 'name': 'New User'}   # Should hit API
        ]
        
        initial_api_calls = mock_numverify_api.call_count
        
        # Act
        result = phone_validation_service.validate_csv_import(csv_data, phone_field='phone')
        
        # Assert
        assert result.success is True
        assert result.data['total_rows'] == 2
        
        # Verify cache was used for first number (fewer API calls)
        # Should only make 1 new API call for the non-cached number
        expected_new_calls = 1
        actual_new_calls = mock_numverify_api.call_count - initial_api_calls
        assert actual_new_calls == expected_new_calls
        
        # Verify both numbers are now in database
        total_validations = phone_validation_repository.count()
        assert total_validations == 2
    
    def test_csv_validation_performance_with_large_dataset(self, phone_validation_service, phone_validation_repository, mock_numverify_api, db_session):
        """Test CSV validation performance with larger dataset"""
        # Arrange - Create larger CSV dataset
        csv_data = []
        for i in range(50):
            csv_data.append({
                'phone': f'+1415555{i:04d}',
                'name': f'User {i}',
                'email': f'user{i}@example.com'
            })
        
        start_time = time.time()
        
        # Act
        result = phone_validation_service.validate_csv_import(
            csv_data, 
            phone_field='phone',
            batch_size=10  # Process in smaller batches
        )
        
        end_time = time.time()
        processing_time = end_time - start_time
        
        # Assert
        assert result.success is True
        assert result.data['total_rows'] == 50
        
        # Verify reasonable performance (should complete in under 30 seconds in tests)
        assert processing_time < 30.0
        
        # Verify all records were processed and cached
        total_validations = phone_validation_repository.count()
        assert total_validations == 50
        
        # Verify batch processing worked (all API calls made)
        assert mock_numverify_api.call_count == 50
    
    def test_csv_validation_error_handling_with_database_rollback(self, phone_validation_service, phone_validation_repository, db_session):
        """Test CSV validation error handling with proper database rollback"""
        # Arrange
        csv_data = [
            {'phone': '+14158586273', 'name': 'Valid User'},
            {'phone': '+14155551234', 'name': 'Another Valid User'}
        ]
        
        # Mock a database error during the second validation
        call_count = 0
        original_create = phone_validation_repository.create
        
        def failing_create(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise Exception('Database error during validation save')
            return original_create(*args, **kwargs)
        
        phone_validation_repository.create = failing_create
        
        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.json.return_value = {'valid': True, 'line_type': 'mobile'}
            mock_response.status_code = 200
            mock_get.return_value = mock_response
            
            # Act
            result = phone_validation_service.validate_csv_import(csv_data, phone_field='phone')
            
            # Assert
            # Should handle caching error gracefully - validation should still succeed
            assert result.success is True
            assert result.data['error_count'] == 0  # No validation errors
            assert result.data['valid_phones'] == 2  # Both phones were successfully validated
            
            # Verify database state is consistent (no partial saves)
            # Due to transaction rollback, should have no records or all successful records
            total_validations = phone_validation_repository.count()
            assert total_validations <= 1  # At most the first successful validation


class TestPhoneValidationStatisticsIntegration:
    """Test PhoneValidationService statistics with real database"""
    
    def test_validation_statistics_with_real_data(self, phone_validation_service, phone_validation_repository, db_session):
        """Test getting validation statistics from real database data"""
        # Arrange - Create various validation records
        validation_data = [
            # Mobile numbers
            ('+14158586273', True, 'mobile', 'Verizon'),
            ('+14155551234', True, 'mobile', 'AT&T'),
            ('+12125559999', True, 'mobile', 'T-Mobile'),
            # Landline numbers  
            ('+14155551111', True, 'landline', 'Pacific Bell'),
            ('+12125552222', True, 'landline', 'Verizon'),
            # Invalid numbers
            ('+11234567890', False, '', ''),
            ('+19999999999', False, '', ''),
        ]
        
        for phone, valid, line_type, carrier in validation_data:
            phone_validation_repository.create(
                phone_number=phone,
                is_valid=valid,
                line_type=line_type,
                carrier=carrier,
                country_code='US' if valid else '',
                created_at=datetime.utcnow()
            )
        
        db_session.commit()
        
        # Act
        result = phone_validation_service.get_validation_stats()
        
        # Assert
        assert result.success is True
        stats = result.data
        
        assert stats['total_validations'] == 7
        assert stats['valid_numbers'] == 5
        assert stats['mobile_numbers'] == 3
        assert stats['landline_numbers'] == 2
        assert stats['invalid_numbers'] == 2
        assert stats['validation_rate'] == 71.4  # 5/7 * 100
        assert stats['mobile_rate'] == 60.0      # 3/5 * 100
    
    def test_recent_validation_statistics(self, phone_validation_service, phone_validation_repository, db_session):
        """Test statistics for recent validations only"""
        # Arrange - Create old and recent validations
        # Old validations
        for i in range(3):
            phone_validation_repository.create(
                phone_number=f'+141555{i:04d}',
                is_valid=True,
                line_type='mobile',
                carrier='Old Carrier',
                country_code='US',
                created_at=datetime.utcnow() - timedelta(days=30)
            )
        
        # Recent validations
        for i in range(5):
            phone_validation_repository.create(
                phone_number=f'+142555{i:04d}',
                is_valid=True,
                line_type='mobile',
                carrier='Recent Carrier',
                country_code='US',
                created_at=datetime.utcnow() - timedelta(hours=1)
            )
        
        db_session.commit()
        
        # Act
        result = phone_validation_service.get_validation_stats(recent_days=7)
        
        # Assert
        assert result.success is True
        stats = result.data
        
        # Should only count recent validations
        assert stats['total_validations'] == 5
        assert stats['valid_numbers'] == 5
        assert stats['recent_validations'] == 5
