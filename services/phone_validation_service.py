"""
PhoneValidationService - Service for validating phone numbers via NumVerify API
Provides caching, bulk validation, and CSV import support
"""

import os
import re
import time
import requests
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from services.common.result import Result
from repositories.phone_validation_repository import PhoneValidationRepository

logger = logging.getLogger(__name__)


class RateLimitError(Exception):
    """Custom exception for rate limit errors"""
    pass


class PhoneValidationService:
    """Service for phone number validation with NumVerify API integration"""
    
    CACHE_DURATION_DAYS = 30
    DEFAULT_BATCH_SIZE = 100
    API_TIMEOUT = 10  # seconds
    
    def __init__(self, validation_repository: PhoneValidationRepository):
        """
        Initialize PhoneValidationService with repository dependency.
        
        Args:
            validation_repository: Repository for cached validation results
            
        Raises:
            ValueError: If NumVerify API key is not configured
        """
        self.validation_repository = validation_repository
        
        # Get API configuration from environment
        self.api_key = os.environ.get('NUMVERIFY_API_KEY')
        if not self.api_key:
            raise ValueError('NumVerify API key not configured')
        
        self.base_url = os.environ.get('NUMVERIFY_BASE_URL', 'http://apilayer.net/api/validate')
    
    def validate_phone(self, phone_number: str) -> Result:
        """
        Validate a single phone number using NumVerify API with caching.
        
        Args:
            phone_number: Phone number to validate
            
        Returns:
            Result object with validation data or error
        """
        # Validate phone format
        if not self._is_valid_format(phone_number):
            return Result.failure(
                'Invalid phone number format',
                code='INVALID_FORMAT'
            )
        
        # Check cache first
        cached_result = self._get_cached_validation(phone_number)
        if cached_result:
            return Result.success(cached_result)
        
        # Call NumVerify API
        response = None
        try:
            response = self._call_numverify_api(phone_number)
            
            # Process and cache the result
            validation_data = self._process_api_response(phone_number, response)
            self._cache_validation_result(phone_number, validation_data, response)
            
            return Result.success(validation_data)
            
        except requests.exceptions.Timeout:
            return Result.failure(
                'API request timeout',
                code='TIMEOUT_ERROR'
            )
        except requests.exceptions.ConnectionError as e:
            return Result.failure(
                f'Network error: {str(e)}',
                code='NETWORK_ERROR'
            )
        except RateLimitError as e:
            return Result.failure(
                'Rate limit exceeded',
                code='RATE_LIMIT_EXCEEDED'
            )
        except Exception as e:
            # Check for specific API errors
            if 'Rate limit' in str(e):
                return Result.failure(
                    'Rate limit exceeded',
                    code='RATE_LIMIT_EXCEEDED'
                )
            elif 'API error: 500' in str(e):
                return Result.failure(
                    f'API error: 500 - Internal Server Error',
                    code='API_ERROR'
                )
            else:
                logger.error(f"Unexpected error validating phone {phone_number}: {e}")
                return Result.failure(
                    f'Validation failed: {str(e)}',
                    code='VALIDATION_ERROR'
                )
    
    def validate_bulk(self, phone_numbers: List[str], batch_size: int = None, max_retries: int = 3) -> Result:
        """
        Validate multiple phone numbers with batching and rate limit handling.
        
        Args:
            phone_numbers: List of phone numbers to validate
            batch_size: Number of phones to process per batch
            max_retries: Maximum retries for rate-limited requests
            
        Returns:
            Result object with bulk validation results
        """
        if not phone_numbers:
            return Result.success({
                'results': [],
                'total_processed': 0,
                'valid_count': 0,
                'invalid_count': 0,
                'error_count': 0
            })
        
        batch_size = batch_size or self.DEFAULT_BATCH_SIZE
        results = []
        valid_count = 0
        invalid_count = 0
        error_count = 0
        
        for phone in phone_numbers[:batch_size]:  # Process in batches
            result = self._validate_with_retry(phone, max_retries)
            
            if result.success:
                results.append(result.data)
                if result.data.get('valid'):
                    valid_count += 1
                else:
                    invalid_count += 1
            else:
                error_count += 1
                results.append({
                    'phone_number': phone,
                    'valid': False,
                    'error': result.error,
                    'from_cache': False
                })
        
        return Result.success({
            'results': results,
            'total_processed': len(results),
            'valid_count': valid_count,
            'invalid_count': invalid_count,
            'error_count': error_count
        })
    
    def validate_csv_import(self, csv_data: List[Dict], phone_field: str = 'phone', batch_size: int = None) -> Result:
        """
        Validate phone numbers from CSV import data.
        
        Args:
            csv_data: List of dictionaries from CSV import
            phone_field: Name of the field containing phone numbers
            batch_size: Number of phones to process per batch
            
        Returns:
            Result object with CSV validation results
        """
        if not csv_data:
            return Result.success({
                'total_rows': 0,
                'valid_phones': 0,
                'invalid_phones': 0,
                'invalid_rows': [],
                'error_count': 0
            })
        
        total_rows = len(csv_data)
        valid_phones = 0
        invalid_phones = 0
        invalid_rows = []
        
        for i, row in enumerate(csv_data):
            phone = row.get(phone_field)
            
            if not phone:
                invalid_rows.append({
                    'row_index': i,
                    'error': 'Missing phone number',
                    **row
                })
                invalid_phones += 1
                continue
            
            # Try to normalize the phone number first
            try:
                normalized_phone = self.normalize_phone_number(phone)
                result = self.validate_phone(normalized_phone)
                
                if result.success and result.data.get('valid'):
                    valid_phones += 1
                else:
                    invalid_phones += 1
                    invalid_rows.append({
                        'row_index': i,
                        'error': result.error or 'Invalid phone number',
                        **row
                    })
            except Exception as e:
                invalid_phones += 1
                invalid_rows.append({
                    'row_index': i,
                    'error': f'Invalid format: {str(e)}',
                    **row
                })
        
        return Result.success({
            'total_rows': total_rows,
            'valid_phones': valid_phones,
            'invalid_phones': invalid_phones,
            'invalid_rows': invalid_rows,
            'error_count': len(invalid_rows)
        })
    
    def normalize_phone_number(self, phone: str) -> str:
        """
        Normalize phone number to E.164 format (+1XXXXXXXXXX).
        
        Args:
            phone: Phone number in various formats
            
        Returns:
            Normalized phone number
        """
        if not phone:
            return ''
        
        # Remove all non-digit characters
        digits = re.sub(r'\D', '', str(phone))
        
        # Add US country code if needed
        if len(digits) == 10:
            return f'+1{digits}'
        elif len(digits) == 11 and digits.startswith('1'):
            return f'+{digits}'
        elif digits.startswith('1') and len(digits) == 11:
            return f'+{digits}'
        else:
            # Already in correct format or international
            if phone.startswith('+'):
                return phone
            return f'+{digits}'
    
    def is_mobile_phone(self, line_type: str) -> bool:
        """
        Check if a line type indicates a mobile phone.
        
        Args:
            line_type: Line type from validation result
            
        Returns:
            True if mobile, False otherwise
        """
        if not line_type:
            return False
        
        mobile_types = ['mobile', 'wireless', 'cellular']
        return line_type.lower() in mobile_types
    
    def get_validation_stats(self, recent_days: int = None) -> Result:
        """
        Get validation statistics from the repository.
        
        Args:
            recent_days: Limit stats to recent days (optional)
            
        Returns:
            Result object with validation statistics
        """
        try:
            total_validations = self.validation_repository.count()
            valid_numbers = self.validation_repository.count(is_valid=True)
            mobile_numbers = self.validation_repository.count(is_valid=True, line_type='mobile')
            landline_numbers = self.validation_repository.count(is_valid=True, line_type='landline')
            invalid_numbers = self.validation_repository.count(is_valid=False)
            
            validation_rate = 0.0
            mobile_rate = 0.0
            
            if total_validations > 0:
                validation_rate = round((valid_numbers / total_validations) * 100, 1)
            
            if valid_numbers > 0:
                mobile_rate = round((mobile_numbers / valid_numbers) * 100, 1)
            
            stats = {
                'total_validations': total_validations,
                'valid_numbers': valid_numbers,
                'mobile_numbers': mobile_numbers,
                'landline_numbers': landline_numbers,
                'invalid_numbers': invalid_numbers,
                'validation_rate': validation_rate,
                'mobile_rate': mobile_rate
            }
            
            # Add recent stats if requested
            if recent_days:
                recent_validations = len(self.validation_repository.find_recent(days=recent_days))
                stats['recent_validations'] = recent_validations
            
            return Result.success(stats)
            
        except Exception as e:
            logger.error(f"Error getting validation stats: {e}")
            return Result.failure(f"Failed to get statistics: {str(e)}")
    
    def clear_expired_cache(self, days: int = 30) -> Result:
        """
        Clear expired validation cache entries.
        
        Args:
            days: Consider entries older than this as expired
            
        Returns:
            Result object with deletion count
        """
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            # Use the repository's bulk_delete_expired method
            deleted_count = self.validation_repository.bulk_delete_expired(cutoff_date)
            
            return Result.success({
                'deleted_count': deleted_count
            })
            
        except Exception as e:
            logger.error(f"Error clearing expired cache: {e}")
            return Result.failure(f"Failed to clear cache: {str(e)}")
    
    # Private helper methods
    
    def _is_valid_format(self, phone: str) -> bool:
        """Check if phone number has valid format"""
        if not phone:
            return False
        
        # Must have at least some digits
        digits = re.sub(r'\D', '', str(phone))
        return len(digits) >= 10 and len(digits) <= 15
    
    def _get_cached_validation(self, phone_number: str) -> Optional[Dict]:
        """Get cached validation result if not expired"""
        cached = self.validation_repository.find_one_by(phone_number=phone_number)
        
        if not cached:
            return None
        
        # Check if cache is expired
        cache_age = datetime.utcnow() - cached.created_at
        if cache_age.days > self.CACHE_DURATION_DAYS:
            return None
        
        # Return cached data
        return {
            'phone_number': cached.phone_number,
            'valid': cached.is_valid,
            'line_type': cached.line_type or '',
            'is_mobile': self.is_mobile_phone(cached.line_type),
            'carrier': cached.carrier or '',
            'country_code': cached.country_code or '',
            'country_name': cached.country_name or '',
            'location': cached.location or '',
            'from_cache': True
        }
    
    def _call_numverify_api(self, phone_number: str) -> Dict:
        """Make API call to NumVerify"""
        params = {
            'access_key': self.api_key,
            'number': phone_number,
            'country_code': '',
            'format': 1
        }
        
        response = requests.get(
            self.base_url,
            params=params,
            timeout=self.API_TIMEOUT
        )
        
        # Check for rate limiting
        if response.status_code == 429:
            error_data = response.json() if response.text else {}
            raise RateLimitError(f"Rate limit exceeded")
        
        # Check for other errors
        if response.status_code != 200:
            raise Exception(f"API error: {response.status_code} - {response.text}")
        
        return response.json()
    
    def _process_api_response(self, phone_number: str, response: Dict) -> Dict:
        """Process NumVerify API response into standard format"""
        return {
            'phone_number': phone_number,
            'valid': response.get('valid', False),
            'line_type': response.get('line_type', ''),
            'is_mobile': self.is_mobile_phone(response.get('line_type', '')),
            'carrier': response.get('carrier', ''),
            'country_code': response.get('country_code', ''),
            'country_name': response.get('country_name', ''),
            'location': response.get('location', ''),
            'from_cache': False
        }
    
    def _cache_validation_result(self, phone_number: str, validation_data: Dict, raw_response: Dict):
        """Save validation result to cache"""
        try:
            cache_until = datetime.utcnow() + timedelta(days=self.CACHE_DURATION_DAYS)
            
            self.validation_repository.create(
                phone_number=phone_number,
                is_valid=validation_data['valid'],
                line_type=validation_data['line_type'],
                carrier=validation_data['carrier'],
                country_code=validation_data['country_code'],
                country_name=validation_data['country_name'],
                location=validation_data['location'],
                cached_until=cache_until,
                raw_response=raw_response,
                api_response=raw_response,  # Legacy field support
                created_at=datetime.utcnow()
            )
        except Exception as e:
            # Log but don't fail if caching fails
            logger.warning(f"Failed to cache validation result for {phone_number}: {e}")
    
    def _validate_with_retry(self, phone: str, max_retries: int) -> Result:
        """Validate with exponential backoff for rate limiting"""
        for attempt in range(max_retries):
            result = self.validate_phone(phone)
            
            # Success or non-retryable error
            if result.success or result.code != 'RATE_LIMIT_EXCEEDED':
                return result
            
            # Exponential backoff for rate limiting
            if attempt < max_retries - 1:
                sleep_time = 2 ** attempt  # 1, 2, 4 seconds
                time.sleep(sleep_time)
        
        return result