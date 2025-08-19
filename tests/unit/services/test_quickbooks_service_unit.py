"""
Unit tests for QuickBooksService using repository pattern
"""

import pytest
import os
# import jwt  # Commented out - not installed
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime, timedelta
from services.quickbooks_service import QuickBooksService
from crm_database import QuickBooksAuth


class TestQuickBooksService:
    """Test suite for QuickBooksService with repository pattern"""
    
    @pytest.fixture
    def mock_auth_repository(self):
        """Mock QuickBooksAuth repository"""
        return Mock()
    
    @pytest.fixture
    def mock_sync_repository(self):
        """Mock QuickBooksSync repository"""  
        return Mock()
    
    @pytest.fixture
    def service(self, mock_auth_repository, mock_sync_repository):
        """Create QuickBooksService with mocked repositories"""
        service = QuickBooksService()
        service.auth_repository = mock_auth_repository
        service.sync_repository = mock_sync_repository
        return service
    
    @pytest.fixture
    def mock_auth_record(self):
        """Mock QuickBooksAuth record"""
        auth = Mock()
        auth.id = 1
        auth.company_id = "123456"
        auth.access_token = "encrypted_access_token"
        auth.refresh_token = "encrypted_refresh_token"
        auth.expires_at = datetime.utcnow() + timedelta(hours=1)
        return auth
    
    def test_init_sets_config_from_environment(self):
        """Test service initialization reads from environment variables"""
        # Arrange
        with patch.dict(os.environ, {
            'QUICKBOOKS_CLIENT_ID': 'test_client_id',
            'QUICKBOOKS_CLIENT_SECRET': 'test_secret',
            'QUICKBOOKS_REDIRECT_URI': 'http://test.com/callback',
            'QUICKBOOKS_SANDBOX': 'False'
        }):
            # Act
            service = QuickBooksService()
            
            # Assert
            assert service.client_id == 'test_client_id'
            assert service.client_secret == 'test_secret'
            assert service.redirect_uri == 'http://test.com/callback'
            assert service.sandbox is False
            assert "quickbooks.api.intuit.com" in service.api_base_url
    
    def test_init_defaults_sandbox_true(self):
        """Test service defaults to sandbox mode"""
        # Arrange & Act
        service = QuickBooksService()
        
        # Assert
        assert service.sandbox is True
        assert "sandbox-quickbooks.api.intuit.com" in service.api_base_url
    
    def test_get_authorization_url(self, service):
        """Test generating OAuth authorization URL"""
        # Act
        url = service.get_authorization_url(state="test_state")
        
        # Assert
        assert service.auth_base_url in url
        assert "client_id" in url
        assert "scope" in url
        assert "redirect_uri" in url
        assert "response_type=code" in url
        assert "state=test_state" in url
    
    def test_get_authorization_url_generates_state_if_none(self, service):
        """Test authorization URL generation creates state if none provided"""
        # Act
        url = service.get_authorization_url()
        
        # Assert
        assert "state=" in url
        # State should be present and not empty
        state_part = [part for part in url.split('&') if part.startswith('state=')][0]
        state_value = state_part.split('=')[1]
        assert len(state_value) > 0
    
    @patch('services.quickbooks_service.requests.post')
    @patch('jwt.decode')
    def test_exchange_code_for_tokens_success(self, mock_jwt_decode, mock_requests_post, service, mock_auth_repository):
        """Test successful token exchange"""
        # Arrange
        mock_response = Mock()
        mock_response.json.return_value = {
            'access_token': 'test_access_token',
            'refresh_token': 'test_refresh_token',
            'expires_in': 3600
        }
        mock_response.status_code = 200
        mock_requests_post.return_value = mock_response
        
        mock_jwt_decode.return_value = {'realmid': '123456'}
        
        mock_auth = Mock()
        mock_auth_repository.create_or_update_auth.return_value = mock_auth
        
        # Act
        result = service.exchange_code_for_tokens('test_code')
        
        # Assert
        assert result == mock_response.json.return_value
        mock_requests_post.assert_called_once()
        mock_auth_repository.create_or_update_auth.assert_called_once()
        
        # Verify auth data structure
        auth_call_args = mock_auth_repository.create_or_update_auth.call_args[0][0]
        assert auth_call_args['company_id'] == '123456'
        assert 'access_token' in auth_call_args
        assert 'refresh_token' in auth_call_args
        assert 'expires_at' in auth_call_args
    
    @patch('services.quickbooks_service.requests.post')
    def test_exchange_code_for_tokens_api_error(self, mock_requests_post, service):
        """Test token exchange with API error"""
        # Arrange
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = Exception("API Error")
        mock_requests_post.return_value = mock_response
        
        # Act & Assert
        with pytest.raises(Exception, match="API Error"):
            service.exchange_code_for_tokens('test_code')
    
    @patch('services.quickbooks_service.requests.post')
    def test_refresh_access_token_success(self, mock_requests_post, service, mock_auth_repository, mock_auth_record):
        """Test successful token refresh"""
        # Arrange
        mock_auth_repository.get_first_auth.return_value = mock_auth_record
        
        # Mock cipher decrypt
        with patch.object(service.cipher, 'decrypt') as mock_decrypt:
            mock_decrypt.return_value.decode.return_value = 'decrypted_refresh_token'
            
            mock_response = Mock()
            mock_response.json.return_value = {
                'access_token': 'new_access_token',
                'refresh_token': 'new_refresh_token',
                'expires_in': 3600
            }
            mock_response.status_code = 200
            mock_requests_post.return_value = mock_response
            
            # Mock cipher encrypt for new tokens
            with patch.object(service.cipher, 'encrypt') as mock_encrypt:
                mock_encrypt.side_effect = lambda x: f"encrypted_{x.decode()}".encode()
                
                # Act
                result = service.refresh_access_token()
                
                # Assert
                assert result is True
                mock_requests_post.assert_called_once()
                mock_auth_repository.update_tokens.assert_called_once()
                
                # Verify update_tokens was called with correct parameters
                call_args = mock_auth_repository.update_tokens.call_args
                assert call_args[1]['auth_id'] == mock_auth_record.id
                assert 'access_token' in call_args[1]
                assert 'refresh_token' in call_args[1]
                assert 'expires_at' in call_args[1]
    
    def test_refresh_access_token_no_auth(self, service, mock_auth_repository):
        """Test token refresh when no auth record exists"""
        # Arrange
        mock_auth_repository.get_first_auth.return_value = None
        
        # Act
        result = service.refresh_access_token()
        
        # Assert
        assert result is False
    
    @patch('services.quickbooks_service.requests.post')
    def test_refresh_access_token_api_error(self, mock_requests_post, service, mock_auth_repository, mock_auth_record):
        """Test token refresh with API error"""
        # Arrange
        mock_auth_repository.get_first_auth.return_value = mock_auth_record
        
        with patch.object(service.cipher, 'decrypt') as mock_decrypt:
            mock_decrypt.return_value.decode.return_value = 'decrypted_refresh_token'
            
            mock_response = Mock()
            mock_response.raise_for_status.side_effect = Exception("API Error")
            mock_requests_post.return_value = mock_response
            
            # Act
            result = service.refresh_access_token()
            
            # Assert
            assert result is False
    
    @patch('services.quickbooks_service.requests.request')
    def test_make_api_request_success(self, mock_requests, service, mock_auth_repository, mock_auth_record):
        """Test successful API request"""
        # Arrange
        mock_auth_repository.get_first_auth.return_value = mock_auth_record
        mock_auth_repository.is_token_expired.return_value = False
        
        with patch.object(service.cipher, 'decrypt') as mock_decrypt:
            mock_decrypt.return_value.decode.return_value = 'decrypted_access_token'
            
            mock_response = Mock()
            mock_response.json.return_value = {'data': 'test_response'}
            mock_response.status_code = 200
            mock_requests.return_value = mock_response
            
            # Act
            result = service.make_api_request('customers')
            
            # Assert
            assert result == {'data': 'test_response'}
            mock_requests.assert_called_once()
            
            # Verify request parameters
            call_args = mock_requests.call_args
            assert 'customers' in call_args[1]['url']
            assert 'Bearer decrypted_access_token' in call_args[1]['headers']['Authorization']
    
    def test_make_api_request_no_auth(self, service, mock_auth_repository):
        """Test API request when no auth record exists"""
        # Arrange
        mock_auth_repository.get_first_auth.return_value = None
        
        # Act & Assert
        with pytest.raises(Exception, match="No QuickBooks authentication found"):
            service.make_api_request('customers')
    
    @patch('services.quickbooks_service.requests.request')
    def test_make_api_request_with_token_refresh(self, mock_requests, service, mock_auth_repository, mock_auth_record):
        """Test API request that triggers token refresh"""
        # Arrange
        mock_auth_repository.get_first_auth.return_value = mock_auth_record
        mock_auth_repository.is_token_expired.return_value = True
        
        # Mock successful refresh
        with patch.object(service, 'refresh_access_token') as mock_refresh:
            mock_refresh.return_value = True
            # After refresh, get_first_auth should return updated auth
            mock_auth_repository.get_first_auth.return_value = mock_auth_record
            
            with patch.object(service.cipher, 'decrypt') as mock_decrypt:
                mock_decrypt.return_value.decode.return_value = 'refreshed_access_token'
                
                mock_response = Mock()
                mock_response.json.return_value = {'data': 'test_response'}
                mock_requests.return_value = mock_response
                
                # Act
                result = service.make_api_request('customers')
                
                # Assert
                assert result == {'data': 'test_response'}
                mock_refresh.assert_called_once()
    
    def test_make_api_request_refresh_fails(self, service, mock_auth_repository, mock_auth_record):
        """Test API request when token refresh fails"""
        # Arrange
        mock_auth_repository.get_first_auth.return_value = mock_auth_record
        mock_auth_repository.is_token_expired.return_value = True
        
        with patch.object(service, 'refresh_access_token') as mock_refresh:
            mock_refresh.return_value = False
            
            # Act & Assert
            with pytest.raises(Exception, match="Failed to refresh access token"):
                service.make_api_request('customers')
    
    def test_get_company_info_success(self, service, mock_auth_repository, mock_auth_record):
        """Test getting company info successfully"""
        # Arrange
        mock_auth_repository.get_first_auth.return_value = mock_auth_record
        
        with patch.object(service, 'make_api_request') as mock_api_request:
            mock_api_request.return_value = {'company': 'data'}
            
            # Act
            result = service.get_company_info()
            
            # Assert
            assert result == {'company': 'data'}
            mock_api_request.assert_called_once_with(f"companyinfo/{mock_auth_record.company_id}")
    
    def test_get_company_info_no_auth(self, service, mock_auth_repository):
        """Test getting company info when no auth exists"""
        # Arrange
        mock_auth_repository.get_first_auth.return_value = None
        
        # Act
        result = service.get_company_info()
        
        # Assert
        assert result is None
    
    def test_list_customers(self, service):
        """Test listing customers"""
        # Arrange
        mock_response = {
            'QueryResponse': {
                'Customer': [{'id': '1', 'name': 'Test Customer'}]
            }
        }
        
        with patch.object(service, 'make_api_request') as mock_api_request:
            mock_api_request.return_value = mock_response
            
            # Act
            result = service.list_customers(max_results=500)
            
            # Assert
            assert result == [{'id': '1', 'name': 'Test Customer'}]
            mock_api_request.assert_called_once_with(
                "query", 
                params={'query': "select * from Customer maxresults 500"}
            )
    
    def test_list_items(self, service):
        """Test listing items"""
        # Arrange
        mock_response = {
            'QueryResponse': {
                'Item': [{'id': '1', 'name': 'Test Item'}]
            }
        }
        
        with patch.object(service, 'make_api_request') as mock_api_request:
            mock_api_request.return_value = mock_response
            
            # Act
            result = service.list_items(max_results=100)
            
            # Assert
            assert result == [{'id': '1', 'name': 'Test Item'}]
            mock_api_request.assert_called_once_with(
                "query", 
                params={'query': "select * from Item maxresults 100"}
            )
    
    def test_list_estimates(self, service):
        """Test listing estimates"""
        # Arrange
        mock_response = {
            'QueryResponse': {
                'Estimate': [{'id': '1', 'total': '100.00'}]
            }
        }
        
        with patch.object(service, 'make_api_request') as mock_api_request:
            mock_api_request.return_value = mock_response
            
            # Act
            result = service.list_estimates()
            
            # Assert
            assert result == [{'id': '1', 'total': '100.00'}]
            mock_api_request.assert_called_once_with(
                "query", 
                params={'query': "select * from Estimate maxresults 1000"}
            )
    
    def test_list_invoices(self, service):
        """Test listing invoices"""
        # Arrange
        mock_response = {
            'QueryResponse': {
                'Invoice': [{'id': '1', 'total': '200.00'}]
            }
        }
        
        with patch.object(service, 'make_api_request') as mock_api_request:
            mock_api_request.return_value = mock_response
            
            # Act
            result = service.list_invoices()
            
            # Assert
            assert result == [{'id': '1', 'total': '200.00'}]
            mock_api_request.assert_called_once_with(
                "query", 
                params={'query': "select * from Invoice maxresults 1000"}
            )
    
    def test_get_customer(self, service):
        """Test getting specific customer"""
        # Arrange
        mock_response = {'customer': 'data'}
        
        with patch.object(service, 'make_api_request') as mock_api_request:
            mock_api_request.return_value = mock_response
            
            # Act
            result = service.get_customer('123')
            
            # Assert
            assert result == mock_response
            mock_api_request.assert_called_once_with("customer/123")
    
    def test_get_item(self, service):
        """Test getting specific item"""
        # Arrange
        mock_response = {'item': 'data'}
        
        with patch.object(service, 'make_api_request') as mock_api_request:
            mock_api_request.return_value = mock_response
            
            # Act
            result = service.get_item('456')
            
            # Assert
            assert result == mock_response
            mock_api_request.assert_called_once_with("item/456")
    
    def test_get_estimate(self, service):
        """Test getting specific estimate"""
        # Arrange
        mock_response = {'estimate': 'data'}
        
        with patch.object(service, 'make_api_request') as mock_api_request:
            mock_api_request.return_value = mock_response
            
            # Act
            result = service.get_estimate('789')
            
            # Assert
            assert result == mock_response
            mock_api_request.assert_called_once_with("estimate/789")
    
    def test_get_invoice(self, service):
        """Test getting specific invoice"""
        # Arrange
        mock_response = {'invoice': 'data'}
        
        with patch.object(service, 'make_api_request') as mock_api_request:
            mock_api_request.return_value = mock_response
            
            # Act
            result = service.get_invoice('101112')
            
            # Assert
            assert result == mock_response
            mock_api_request.assert_called_once_with("invoice/101112")
    
    def test_is_authenticated_true(self, service, mock_auth_repository, mock_auth_record):
        """Test authentication check when authenticated"""
        # Arrange
        mock_auth_repository.get_first_auth.return_value = mock_auth_record
        
        # Act
        result = service.is_authenticated()
        
        # Assert
        assert result is True
    
    def test_is_authenticated_false(self, service, mock_auth_repository):
        """Test authentication check when not authenticated"""
        # Arrange
        mock_auth_repository.get_first_auth.return_value = None
        
        # Act
        result = service.is_authenticated()
        
        # Assert
        assert result is False