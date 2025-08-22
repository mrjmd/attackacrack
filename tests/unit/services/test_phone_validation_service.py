"""
TDD Tests for PhoneValidationService - UNIT TESTS

TEST-DRIVEN DEVELOPMENT: These tests are written BEFORE implementation
Purpose: Validate phone numbers for SMS campaigns with caching and bulk processing

Features tested:
- Single phone validation with NumVerify API
- Bulk validation for CSV imports
- Caching to avoid repeated API calls
- Error handling for rate limits and network issues
- Mobile vs landline classification
- Invalid/disconnected number detection
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
from services.phone_validation_service import PhoneValidationService
from services.common.result import Result
import requests


@pytest.fixture
def mock_validation_repository():
    """Mock repository for phone validation cache"""
    mock_repo = Mock()
    mock_repo.find_one_by.return_value = None  # No cached results by default
    mock_repo.create.return_value = Mock(id=1, phone_number='+11234567890')
    return mock_repo


@pytest.fixture
def phone_validation_service(mock_validation_repository):
    """Create PhoneValidationService with mocked repository"""
    with patch('os.environ.get') as mock_env:
        mock_env.side_effect = lambda key, default=None: {
            'NUMVERIFY_API_KEY': 'test_api_key',
            'NUMVERIFY_BASE_URL': 'http://apilayer.net/api/validate'
        }.get(key, default)
        
        return PhoneValidationService(
            validation_repository=mock_validation_repository
        )


@pytest.fixture
def valid_numverify_response():
    """Mock NumVerify API response for valid mobile number"""
    return {
        'valid': True,
        'number': '14158586273',
        'local_format': '4158586273',
        'international_format': '+14158586273',
        'country_prefix': '+1',
        'country_code': 'US',
        'country_name': 'United States of America',
        'location': 'California',
        'carrier': 'Verizon Wireless',
        'line_type': 'mobile'
    }


@pytest.fixture
def invalid_numverify_response():
    """Mock NumVerify API response for invalid number"""
    return {
        'valid': False,
        'number': '1234567890',
        'local_format': '',
        'international_format': '',
        'country_prefix': '',
        'country_code': '',
        'country_name': '',
        'location': '',
        'carrier': '',
        'line_type': ''
    }


@pytest.fixture
def landline_numverify_response():
    """Mock NumVerify API response for landline number"""
    return {
        'valid': True,
        'number': '14155551234',
        'local_format': '4155551234',
        'international_format': '+14155551234',
        'country_prefix': '+1',
        'country_code': 'US',
        'country_name': 'United States of America',
        'location': 'California',
        'carrier': 'Pacific Bell',
        'line_type': 'landline'
    }


class TestPhoneValidationServiceValidation:
    """Test single phone number validation"""
    
    def test_validate_phone_success_mobile(self, phone_validation_service, valid_numverify_response, mock_validation_repository):
        """Test successful validation of mobile number"""
        # Arrange
        phone_number = '+14158586273'
        
        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.json.return_value = valid_numverify_response
            mock_response.status_code = 200
            mock_get.return_value = mock_response
            
            # Act
            result = phone_validation_service.validate_phone(phone_number)
            
            # Assert
            assert result.success is True
            assert result.data['valid'] is True
            assert result.data['phone_number'] == phone_number
            assert result.data['line_type'] == 'mobile'
            assert result.data['is_mobile'] is True
            assert result.data['carrier'] == 'Verizon Wireless'
            assert result.data['country_code'] == 'US'
            
            # Verify API was called with correct parameters
            mock_get.assert_called_once()
            call_args = mock_get.call_args
            assert call_args[1]['params']['access_key'] == 'test_api_key'
            assert call_args[1]['params']['number'] == phone_number
            
            # Verify result was cached
            mock_validation_repository.create.assert_called_once()
    
    def test_validate_phone_success_landline(self, phone_validation_service, landline_numverify_response, mock_validation_repository):
        """Test successful validation of landline number"""
        # Arrange
        phone_number = '+14155551234'
        
        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.json.return_value = landline_numverify_response
            mock_response.status_code = 200
            mock_get.return_value = mock_response
            
            # Act
            result = phone_validation_service.validate_phone(phone_number)
            
            # Assert
            assert result.success is True
            assert result.data['valid'] is True
            assert result.data['line_type'] == 'landline'
            assert result.data['is_mobile'] is False
            assert result.data['carrier'] == 'Pacific Bell'
    
    def test_validate_phone_invalid_number(self, phone_validation_service, invalid_numverify_response, mock_validation_repository):
        """Test validation of invalid phone number"""
        # Arrange
        phone_number = '+11234567890'
        
        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.json.return_value = invalid_numverify_response
            mock_response.status_code = 200
            mock_get.return_value = mock_response
            
            # Act
            result = phone_validation_service.validate_phone(phone_number)
            
            # Assert
            assert result.success is True  # API call succeeded
            assert result.data['valid'] is False
            assert result.data['phone_number'] == phone_number
            assert result.data['is_mobile'] is False
            assert result.data['line_type'] == ''
    
    def test_validate_phone_cached_result(self, phone_validation_service, mock_validation_repository):
        """Test that cached validation results are returned without API call"""
        # Arrange
        phone_number = '+14158586273'
        cached_result = Mock()
        cached_result.phone_number = phone_number
        cached_result.is_valid = True
        cached_result.line_type = 'mobile'
        cached_result.carrier = 'Verizon Wireless'
        cached_result.country_code = 'US'
        cached_result.created_at = datetime.utcnow()
        
        mock_validation_repository.find_one_by.return_value = cached_result
        
        with patch('requests.get') as mock_get:
            # Act
            result = phone_validation_service.validate_phone(phone_number)
            
            # Assert
            assert result.success is True
            assert result.data['valid'] is True
            assert result.data['phone_number'] == phone_number
            assert result.data['line_type'] == 'mobile'
            assert result.data['from_cache'] is True
            
            # Verify API was NOT called
            mock_get.assert_not_called()
            
            # Verify cache was checked
            mock_validation_repository.find_one_by.assert_called_once_with(
                phone_number=phone_number
            )
    
    def test_validate_phone_expired_cache(self, phone_validation_service, valid_numverify_response, mock_validation_repository):
        """Test that expired cache entries trigger fresh API call"""
        # Arrange
        phone_number = '+14158586273'
        expired_result = Mock()
        expired_result.phone_number = phone_number
        expired_result.created_at = datetime.utcnow() - timedelta(days=31)  # Expired
        
        mock_validation_repository.find_one_by.return_value = expired_result
        
        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.json.return_value = valid_numverify_response
            mock_response.status_code = 200
            mock_get.return_value = mock_response
            
            # Act
            result = phone_validation_service.validate_phone(phone_number)
            
            # Assert
            assert result.success is True
            assert result.data['from_cache'] is False
            
            # Verify API was called despite cache hit
            mock_get.assert_called_once()
            
            # Verify new result was cached
            mock_validation_repository.create.assert_called_once()
    
    def test_validate_phone_api_error_500(self, phone_validation_service, mock_validation_repository):
        """Test handling of NumVerify API server errors"""
        # Arrange
        phone_number = '+14158586273'
        
        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 500
            mock_response.text = 'Internal Server Error'
            mock_get.return_value = mock_response
            
            # Act
            result = phone_validation_service.validate_phone(phone_number)
            
            # Assert
            assert result.success is False
            assert 'API error' in result.error
            assert result.code == 'API_ERROR'
            assert '500' in result.error
    
    def test_validate_phone_api_rate_limit(self, phone_validation_service, mock_validation_repository):
        """Test handling of NumVerify API rate limiting"""
        # Arrange
        phone_number = '+14158586273'
        
        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 429
            mock_response.json.return_value = {
                'success': False,
                'error': {
                    'code': 104,
                    'info': 'Maximum monthly API request volume reached.'
                }
            }
            mock_get.return_value = mock_response
            
            # Act
            result = phone_validation_service.validate_phone(phone_number)
            
            # Assert
            assert result.success is False
            assert 'rate limit' in result.error.lower()
            assert result.code == 'RATE_LIMIT_EXCEEDED'
    
    def test_validate_phone_network_error(self, phone_validation_service, mock_validation_repository):
        """Test handling of network connectivity issues"""
        # Arrange
        phone_number = '+14158586273'
        
        with patch('requests.get') as mock_get:
            mock_get.side_effect = requests.ConnectionError('Network error')
            
            # Act
            result = phone_validation_service.validate_phone(phone_number)
            
            # Assert
            assert result.success is False
            assert 'network error' in result.error.lower()
            assert result.code == 'NETWORK_ERROR'
    
    def test_validate_phone_timeout(self, phone_validation_service, mock_validation_repository):
        """Test handling of API timeout"""
        # Arrange
        phone_number = '+14158586273'
        
        with patch('requests.get') as mock_get:
            mock_get.side_effect = requests.Timeout('Request timeout')
            
            # Act
            result = phone_validation_service.validate_phone(phone_number)
            
            # Assert
            assert result.success is False
            assert 'timeout' in result.error.lower()
            assert result.code == 'TIMEOUT_ERROR'
    
    def test_validate_phone_invalid_format(self, phone_validation_service, mock_validation_repository):
        """Test validation of invalid phone number format"""
        # Arrange
        invalid_formats = [
            '123',  # Too short
            'abc-def-ghij',  # Non-numeric
            '',  # Empty
            None,  # None
            '123456789012345',  # Too long
        ]
        
        for invalid_phone in invalid_formats:
            # Act
            result = phone_validation_service.validate_phone(invalid_phone)
            
            # Assert
            assert result.success is False
            assert 'invalid format' in result.error.lower()
            assert result.code == 'INVALID_FORMAT'
    
    def test_validate_phone_missing_api_key(self, mock_validation_repository):
        """Test behavior when NumVerify API key is not configured"""
        # Arrange
        with patch('os.environ.get') as mock_env:
            mock_env.return_value = None  # No API key
            
            # Act & Assert
            with pytest.raises(ValueError, match='NumVerify API key not configured'):
                PhoneValidationService(validation_repository=mock_validation_repository)


class TestPhoneValidationServiceBulkValidation:
    """Test bulk phone number validation for CSV imports"""
    
    def test_validate_bulk_success(self, phone_validation_service, valid_numverify_response, mock_validation_repository):
        """Test successful bulk validation of multiple phone numbers"""
        # Arrange
        phone_numbers = ['+14158586273', '+14155551234', '+12125551234']
        
        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.json.return_value = valid_numverify_response
            mock_response.status_code = 200
            mock_get.return_value = mock_response
            
            # Act
            result = phone_validation_service.validate_bulk(phone_numbers)
            
            # Assert
            assert result.success is True
            assert len(result.data['results']) == 3
            assert result.data['total_processed'] == 3
            assert result.data['valid_count'] == 3
            assert result.data['invalid_count'] == 0
            assert result.data['error_count'] == 0
            
            # Verify each phone number was processed
            for i, phone in enumerate(phone_numbers):
                phone_result = result.data['results'][i]
                assert phone_result['phone_number'] == phone
                assert phone_result['valid'] is True
            
            # Verify API was called for each number
            assert mock_get.call_count == 3
    
    def test_validate_bulk_mixed_results(self, phone_validation_service, mock_validation_repository):
        """Test bulk validation with mix of valid/invalid numbers"""
        # Arrange
        phone_numbers = ['+14158586273', '+11234567890', '+14155551234']
        
        def mock_api_response(url, **kwargs):
            phone = kwargs['params']['number']
            mock_response = Mock()
            mock_response.status_code = 200
            
            if phone == '+11234567890':  # Invalid number
                mock_response.json.return_value = {
                    'valid': False,
                    'number': '1234567890',
                    'line_type': ''
                }
            else:  # Valid numbers
                mock_response.json.return_value = {
                    'valid': True,
                    'number': phone[1:],  # Remove +
                    'line_type': 'mobile',
                    'carrier': 'Test Carrier',
                    'country_code': 'US'
                }
            
            return mock_response
        
        with patch('requests.get', side_effect=mock_api_response):
            # Act
            result = phone_validation_service.validate_bulk(phone_numbers)
            
            # Assert
            assert result.success is True
            assert result.data['total_processed'] == 3
            assert result.data['valid_count'] == 2
            assert result.data['invalid_count'] == 1
            assert result.data['error_count'] == 0
    
    def test_validate_bulk_with_cache_hits(self, phone_validation_service, mock_validation_repository):
        """Test bulk validation with some numbers already cached"""
        # Arrange
        phone_numbers = ['+14158586273', '+14155551234']
        
        # First number is cached
        cached_result = Mock()
        cached_result.phone_number = '+14158586273'
        cached_result.is_valid = True
        cached_result.line_type = 'mobile'
        cached_result.carrier = 'Cached Carrier'
        cached_result.country_code = 'US'
        cached_result.created_at = datetime.utcnow()
        
        def mock_find_cache(phone_number):
            if phone_number == '+14158586273':
                return cached_result
            return None
        
        mock_validation_repository.find_one_by.side_effect = mock_find_cache
        
        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.json.return_value = {
                'valid': True,
                'number': '4155551234',
                'line_type': 'mobile',
                'carrier': 'API Carrier',
                'country_code': 'US'
            }
            mock_response.status_code = 200
            mock_get.return_value = mock_response
            
            # Act
            result = phone_validation_service.validate_bulk(phone_numbers)
            
            # Assert
            assert result.success is True
            assert len(result.data['results']) == 2
            
            # First result from cache
            assert result.data['results'][0]['from_cache'] is True
            assert result.data['results'][0]['carrier'] == 'Cached Carrier'
            
            # Second result from API
            assert result.data['results'][1]['from_cache'] is False
            assert result.data['results'][1]['carrier'] == 'API Carrier'
            
            # Only one API call made
            assert mock_get.call_count == 1
    
    def test_validate_bulk_rate_limiting_with_backoff(self, phone_validation_service, mock_validation_repository):
        """Test bulk validation handles rate limiting with exponential backoff"""
        # Arrange
        phone_numbers = ['+14158586273', '+14155551234']
        
        call_count = 0
        def mock_api_response(url, **kwargs):
            nonlocal call_count
            call_count += 1
            
            mock_response = Mock()
            
            if call_count == 1:
                # First call hits rate limit
                mock_response.status_code = 429
                mock_response.json.return_value = {
                    'success': False,
                    'error': {'code': 104, 'info': 'Rate limit exceeded'}
                }
            else:
                # Subsequent calls succeed
                mock_response.status_code = 200
                mock_response.json.return_value = {
                    'valid': True,
                    'number': kwargs['params']['number'][1:],
                    'line_type': 'mobile'
                }
            
            return mock_response
        
        with patch('requests.get', side_effect=mock_api_response):
            with patch('time.sleep') as mock_sleep:  # Mock sleep to speed up test
                # Act
                result = phone_validation_service.validate_bulk(phone_numbers, max_retries=2)
                
                # Assert
                assert result.success is True
                assert result.data['total_processed'] == 2
                
                # Verify backoff was used
                assert mock_sleep.called
    
    def test_validate_bulk_empty_list(self, phone_validation_service, mock_validation_repository):
        """Test bulk validation with empty phone number list"""
        # Act
        result = phone_validation_service.validate_bulk([])
        
        # Assert
        assert result.success is True
        assert result.data['total_processed'] == 0
        assert result.data['valid_count'] == 0
        assert result.data['invalid_count'] == 0
        assert len(result.data['results']) == 0
    
    def test_validate_bulk_max_batch_size(self, phone_validation_service, mock_validation_repository):
        """Test bulk validation respects maximum batch size"""
        # Arrange - Create more numbers than max batch size
        phone_numbers = [f'+1415555{i:04d}' for i in range(150)]  # 150 numbers
        
        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.json.return_value = {'valid': True, 'line_type': 'mobile'}
            mock_response.status_code = 200
            mock_get.return_value = mock_response
            
            # Act
            result = phone_validation_service.validate_bulk(phone_numbers, batch_size=100)
            
            # Assert
            assert result.success is True
            assert result.data['total_processed'] == 150
            
            # Should process in batches of 100, so 150 API calls total
            assert mock_get.call_count == 150


class TestPhoneValidationServiceUtilities:
    """Test utility methods of PhoneValidationService"""
    
    def test_normalize_phone_number(self, phone_validation_service):
        """Test phone number normalization"""
        # Test cases: (input, expected_output)
        test_cases = [
            ('(415) 858-6273', '+14158586273'),
            ('415-858-6273', '+14158586273'),
            ('415.858.6273', '+14158586273'),
            ('415 858 6273', '+14158586273'),
            ('+1 415 858 6273', '+14158586273'),
            ('14158586273', '+14158586273'),
            ('+14158586273', '+14158586273'),  # Already normalized
        ]
        
        for input_phone, expected in test_cases:
            result = phone_validation_service.normalize_phone_number(input_phone)
            assert result == expected, f"Failed for input: {input_phone}"
    
    def test_is_mobile_phone(self, phone_validation_service):
        """Test mobile phone detection"""
        # Mobile line types
        assert phone_validation_service.is_mobile_phone('mobile') is True
        assert phone_validation_service.is_mobile_phone('wireless') is True
        assert phone_validation_service.is_mobile_phone('cellular') is True
        
        # Non-mobile line types
        assert phone_validation_service.is_mobile_phone('landline') is False
        assert phone_validation_service.is_mobile_phone('fixed_line') is False
        assert phone_validation_service.is_mobile_phone('voip') is False
        assert phone_validation_service.is_mobile_phone('') is False
        assert phone_validation_service.is_mobile_phone(None) is False
    
    def test_get_validation_stats(self, phone_validation_service, mock_validation_repository):
        """Test getting validation statistics"""
        # Arrange - Mock repository to return stats
        mock_validation_repository.count.side_effect = lambda **kwargs: {
            # Total validations
            (): 1000,
            # Valid numbers  
            ('is_valid', True): 850,
            # Mobile numbers
            ('is_valid', True, 'line_type', 'mobile'): 600,
            # Recent validations (last 24 hours)
        }.get(tuple(kwargs.values()), 0)
        
        # Mock recent validations count
        def mock_count_recent(**kwargs):
            if 'created_at__gte' in str(kwargs):
                return 50
            return mock_validation_repository.count(**kwargs)
        
        mock_validation_repository.count_recent = mock_count_recent
        
        # Act
        result = phone_validation_service.get_validation_stats()
        
        # Assert
        assert result.success is True
        stats = result.data
        assert stats['total_validations'] == 1000
        assert stats['valid_numbers'] == 850
        assert stats['mobile_numbers'] == 600
        assert stats['validation_rate'] == 85.0  # 850/1000
        assert stats['mobile_rate'] == 70.6  # 600/850
    
    def test_clear_expired_cache(self, phone_validation_service, mock_validation_repository):
        """Test clearing expired cache entries"""
        # Arrange
        mock_validation_repository.delete_many.return_value = 25
        
        # Act
        result = phone_validation_service.clear_expired_cache(days=30)
        
        # Assert
        assert result.success is True
        assert result.data['deleted_count'] == 25
        
        # Verify repository was called with correct filter
        mock_validation_repository.delete_many.assert_called_once()
        call_args = mock_validation_repository.delete_many.call_args[0][0]
        assert 'created_at__lt' in str(call_args)  # Should filter by creation date


class TestPhoneValidationServiceCSVIntegration:
    """Test integration with CSV import workflow"""
    
    def test_validate_csv_phone_list(self, phone_validation_service, mock_validation_repository):
        """Test validation of phone numbers from CSV import"""
        # Arrange - CSV-style phone data
        csv_data = [
            {'phone': '(415) 858-6273', 'name': 'John Doe'},
            {'phone': '415-555-1234', 'name': 'Jane Smith'},
            {'phone': 'invalid', 'name': 'Bad Number'},
            {'phone': '+1-212-555-1234', 'name': 'Bob Wilson'}
        ]
        
        def mock_api_response(url, **kwargs):
            phone = kwargs['params']['number']
            mock_response = Mock()
            mock_response.status_code = 200
            
            if 'invalid' in phone:
                mock_response.json.return_value = {'valid': False}
            else:
                mock_response.json.return_value = {
                    'valid': True,
                    'line_type': 'mobile',
                    'country_code': 'US'
                }
            
            return mock_response
        
        with patch('requests.get', side_effect=mock_api_response):
            # Act
            phone_numbers = [row['phone'] for row in csv_data]
            result = phone_validation_service.validate_csv_import(csv_data, phone_field='phone')
            
            # Assert
            assert result.success is True
            assert result.data['total_rows'] == 4
            assert result.data['valid_phones'] == 3
            assert result.data['invalid_phones'] == 1
            
            # Check that invalid rows are identified
            invalid_rows = result.data['invalid_rows']
            assert len(invalid_rows) == 1
            assert invalid_rows[0]['row_index'] == 2  # Third row (0-indexed)
            assert invalid_rows[0]['name'] == 'Bad Number'
            assert 'invalid format' in invalid_rows[0]['error'].lower()
    
    def test_validate_csv_with_custom_phone_field(self, phone_validation_service, mock_validation_repository):
        """Test CSV validation with custom phone field name"""
        # Arrange
        csv_data = [
            {'mobile_number': '+14158586273', 'contact_name': 'John Doe'},
            {'mobile_number': '+14155551234', 'contact_name': 'Jane Smith'}
        ]
        
        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.json.return_value = {'valid': True, 'line_type': 'mobile'}
            mock_response.status_code = 200
            mock_get.return_value = mock_response
            
            # Act
            result = phone_validation_service.validate_csv_import(
                csv_data, 
                phone_field='mobile_number'
            )
            
            # Assert
            assert result.success is True
            assert result.data['total_rows'] == 2
            assert result.data['valid_phones'] == 2
