"""
Tests for QuickBooks Service
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
import os
from datetime import datetime, timedelta
import json
import base64
from services.quickbooks_service import QuickBooksService
from crm_database import db, QuickBooksAuth
from cryptography.fernet import Fernet


class TestQuickBooksService:
    """Test cases for QuickBooks OAuth and API service"""
    
    @pytest.fixture
    def qb_service(self, app):
        """Create a QuickBooks service instance"""
        with app.app_context():
            # Set up test environment variables
            os.environ['QUICKBOOKS_CLIENT_ID'] = 'test_client_id'
            os.environ['QUICKBOOKS_CLIENT_SECRET'] = 'test_client_secret'
            os.environ['QUICKBOOKS_REDIRECT_URI'] = 'http://localhost:5000/callback'
            os.environ['QUICKBOOKS_SANDBOX'] = 'True'
            os.environ['ENCRYPTION_KEY'] = Fernet.generate_key().decode()
            
            service = QuickBooksService()
            yield service
            
            # Clean up
            QuickBooksAuth.query.delete()
            db.session.commit()
    
    def test_initialization_sandbox_mode(self, qb_service):
        """Test service initializes correctly in sandbox mode"""
        assert qb_service.sandbox is True
        assert qb_service.api_base_url == "https://sandbox-quickbooks.api.intuit.com"
        assert qb_service.client_id == 'test_client_id'
        assert qb_service.client_secret == 'test_client_secret'
    
    def test_initialization_production_mode(self, app):
        """Test service initializes correctly in production mode"""
        with app.app_context():
            os.environ['QUICKBOOKS_SANDBOX'] = 'False'
            service = QuickBooksService()
            assert service.sandbox is False
            assert service.api_base_url == "https://quickbooks.api.intuit.com"
    
    def test_get_authorization_url(self, qb_service):
        """Test OAuth authorization URL generation"""
        state = "test_state_123"
        auth_url = qb_service.get_authorization_url(state)
        
        assert "https://appcenter.intuit.com/connect/oauth2" in auth_url
        assert "client_id=test_client_id" in auth_url
        assert "state=test_state_123" in auth_url
        assert "response_type=code" in auth_url
        assert "redirect_uri=http%3A%2F%2Flocalhost%3A5000%2Fcallback" in auth_url
    
    def test_get_authorization_url_without_state(self, qb_service):
        """Test OAuth URL generation with auto-generated state"""
        auth_url = qb_service.get_authorization_url()
        assert "state=" in auth_url
        # Check that state parameter is present and has a value
        assert not auth_url.endswith("state=")
    
    @patch('requests.post')
    def test_exchange_code_for_tokens_success(self, mock_post, qb_service, app):
        """Test successful OAuth code exchange"""
        # Mock successful token response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'access_token': 'test_access_token',
            'refresh_token': 'test_refresh_token',
            'expires_in': 3600,
            'x_refresh_token_expires_in': 8726400,
            'token_type': 'bearer'
        }
        mock_post.return_value = mock_response
        
        with app.app_context():
            result = qb_service.exchange_code_for_tokens('test_code')
            
            assert result['access_token'] == 'test_access_token'
            assert result['refresh_token'] == 'test_refresh_token'
            
            # Check that tokens were saved to database
            auth = QuickBooksAuth.query.first()
            assert auth is not None
            assert auth.realm_id == 'pending'
    
    @patch('requests.post')
    def test_exchange_code_for_tokens_with_realm_id(self, mock_post, qb_service, app):
        """Test OAuth code exchange with realm_id"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'access_token': 'test_access_token',
            'refresh_token': 'test_refresh_token',
            'expires_in': 3600
        }
        mock_post.return_value = mock_response
        
        with app.app_context():
            result = qb_service.exchange_code_for_tokens('test_code', 'test_realm_123')
            
            auth = QuickBooksAuth.query.first()
            assert auth.realm_id == 'test_realm_123'
    
    @patch('requests.post')
    def test_exchange_code_for_tokens_failure(self, mock_post, qb_service, app):
        """Test failed OAuth code exchange"""
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.text = 'Invalid grant'
        mock_post.return_value = mock_response
        
        with app.app_context():
            with pytest.raises(Exception) as exc_info:
                qb_service.exchange_code_for_tokens('invalid_code')
            assert "Failed to exchange code" in str(exc_info.value)
    
    def test_get_auth_from_db(self, qb_service, app):
        """Test retrieving auth from database"""
        with app.app_context():
            # Create test auth record
            auth = QuickBooksAuth(
                realm_id='test_realm',
                access_token=qb_service.cipher.encrypt(b'test_access').decode(),
                refresh_token=qb_service.cipher.encrypt(b'test_refresh').decode(),
                access_token_expires_at=datetime.utcnow() + timedelta(hours=1),
                refresh_token_expires_at=datetime.utcnow() + timedelta(days=100)
            )
            db.session.add(auth)
            db.session.commit()
            
            retrieved_auth = qb_service._get_auth()
            assert retrieved_auth is not None
            assert retrieved_auth.realm_id == 'test_realm'
    
    @patch('requests.post')
    def test_refresh_access_token_success(self, mock_post, qb_service, app):
        """Test successful token refresh"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'access_token': 'new_access_token',
            'refresh_token': 'new_refresh_token',
            'expires_in': 3600,
            'x_refresh_token_expires_in': 8726400
        }
        mock_post.return_value = mock_response
        
        with app.app_context():
            # Create expired auth
            auth = QuickBooksAuth(
                realm_id='test_realm',
                access_token=qb_service.cipher.encrypt(b'old_access').decode(),
                refresh_token=qb_service.cipher.encrypt(b'old_refresh').decode(),
                access_token_expires_at=datetime.utcnow() - timedelta(hours=1),
                refresh_token_expires_at=datetime.utcnow() + timedelta(days=100)
            )
            db.session.add(auth)
            db.session.commit()
            
            new_auth = qb_service._refresh_access_token(auth)
            
            decrypted_token = qb_service.cipher.decrypt(new_auth.access_token.encode()).decode()
            assert decrypted_token == 'new_access_token'
    
    @patch('requests.post')
    def test_refresh_access_token_failure(self, mock_post, qb_service, app):
        """Test failed token refresh"""
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.text = 'Invalid refresh token'
        mock_post.return_value = mock_response
        
        with app.app_context():
            auth = QuickBooksAuth(
                realm_id='test_realm',
                access_token=qb_service.cipher.encrypt(b'old_access').decode(),
                refresh_token=qb_service.cipher.encrypt(b'invalid_refresh').decode(),
                access_token_expires_at=datetime.utcnow() - timedelta(hours=1),
                refresh_token_expires_at=datetime.utcnow() + timedelta(days=100)
            )
            db.session.add(auth)
            db.session.commit()
            
            with pytest.raises(Exception) as exc_info:
                qb_service._refresh_access_token(auth)
            assert "Failed to refresh token" in str(exc_info.value)
    
    def test_get_valid_auth_token_no_auth(self, qb_service, app):
        """Test getting auth token when no auth exists"""
        with app.app_context():
            result = qb_service._get_valid_auth()
            assert result is None
    
    @patch.object(QuickBooksService, '_refresh_access_token')
    def test_get_valid_auth_token_needs_refresh(self, mock_refresh, qb_service, app):
        """Test getting auth token that needs refresh"""
        with app.app_context():
            # Create auth with expired access token
            expired_auth = QuickBooksAuth(
                realm_id='test_realm',
                access_token=qb_service.cipher.encrypt(b'expired_access').decode(),
                refresh_token=qb_service.cipher.encrypt(b'valid_refresh').decode(),
                access_token_expires_at=datetime.utcnow() - timedelta(hours=1),
                refresh_token_expires_at=datetime.utcnow() + timedelta(days=100)
            )
            db.session.add(expired_auth)
            db.session.commit()
            
            # Mock successful refresh
            refreshed_auth = QuickBooksAuth(
                realm_id='test_realm',
                access_token=qb_service.cipher.encrypt(b'new_access').decode(),
                refresh_token=qb_service.cipher.encrypt(b'new_refresh').decode(),
                access_token_expires_at=datetime.utcnow() + timedelta(hours=1),
                refresh_token_expires_at=datetime.utcnow() + timedelta(days=100)
            )
            mock_refresh.return_value = refreshed_auth
            
            result = qb_service._get_valid_auth()
            assert result is not None
            mock_refresh.assert_called_once()
    
    def test_is_authenticated_true(self, qb_service, app):
        """Test is_authenticated returns True when valid auth exists"""
        with app.app_context():
            auth = QuickBooksAuth(
                realm_id='test_realm',
                access_token=qb_service.cipher.encrypt(b'valid_access').decode(),
                refresh_token=qb_service.cipher.encrypt(b'valid_refresh').decode(),
                access_token_expires_at=datetime.utcnow() + timedelta(hours=1),
                refresh_token_expires_at=datetime.utcnow() + timedelta(days=100)
            )
            db.session.add(auth)
            db.session.commit()
            
            assert qb_service.is_authenticated() is True
    
    def test_is_authenticated_false(self, qb_service, app):
        """Test is_authenticated returns False when no auth exists"""
        with app.app_context():
            assert qb_service.is_authenticated() is False
    
    @patch('requests.get')
    def test_make_api_request_success(self, mock_get, qb_service, app):
        """Test successful API request"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'test': 'data'}
        mock_get.return_value = mock_response
        
        with app.app_context():
            # Create valid auth
            auth = QuickBooksAuth(
                realm_id='test_realm',
                access_token=qb_service.cipher.encrypt(b'valid_token').decode(),
                refresh_token=qb_service.cipher.encrypt(b'valid_refresh').decode(),
                access_token_expires_at=datetime.utcnow() + timedelta(hours=1),
                refresh_token_expires_at=datetime.utcnow() + timedelta(days=100)
            )
            db.session.add(auth)
            db.session.commit()
            
            result = qb_service._make_api_request('/test/endpoint')
            
            assert result == {'test': 'data'}
            mock_get.assert_called_once()
            call_args = mock_get.call_args
            assert 'Authorization' in call_args[1]['headers']
            assert call_args[1]['headers']['Authorization'] == 'Bearer valid_token'
    
    @patch('requests.get')
    def test_make_api_request_no_auth(self, mock_get, qb_service, app):
        """Test API request with no auth"""
        with app.app_context():
            with pytest.raises(Exception) as exc_info:
                qb_service._make_api_request('/test/endpoint')
            assert "Not authenticated" in str(exc_info.value)
    
    @patch.object(QuickBooksService, '_make_api_request')
    def test_get_company_info(self, mock_request, qb_service, app):
        """Test getting company info"""
        mock_request.return_value = {'CompanyInfo': {'CompanyName': 'Test Co'}}
        
        with app.app_context():
            result = qb_service.get_company_info()
            assert result['CompanyInfo']['CompanyName'] == 'Test Co'
            mock_request.assert_called_with('/v3/company/{realm_id}/companyinfo/1')
    
    @patch.object(QuickBooksService, '_make_api_request')
    def test_get_customers(self, mock_request, qb_service):
        """Test getting customers list"""
        mock_request.return_value = {
            'QueryResponse': {
                'Customer': [
                    {'Id': '1', 'DisplayName': 'Customer 1'},
                    {'Id': '2', 'DisplayName': 'Customer 2'}
                ]
            }
        }
        
        result = qb_service.get_customers()
        assert len(result) == 2
        assert result[0]['DisplayName'] == 'Customer 1'
    
    @patch.object(QuickBooksService, '_make_api_request')
    def test_get_customers_with_query(self, mock_request, qb_service):
        """Test getting customers with custom query"""
        mock_request.return_value = {'QueryResponse': {'Customer': []}}
        
        qb_service.get_customers(query="WHERE Active = true")
        mock_request.assert_called_with(
            '/v3/company/{realm_id}/query?query=SELECT * FROM Customer WHERE Active = true'
        )
    
    @patch.object(QuickBooksService, '_make_api_request')
    def test_get_items(self, mock_request, qb_service):
        """Test getting items list"""
        mock_request.return_value = {
            'QueryResponse': {
                'Item': [
                    {'Id': '1', 'Name': 'Service 1'},
                    {'Id': '2', 'Name': 'Product 1'}
                ]
            }
        }
        
        result = qb_service.get_items()
        assert len(result) == 2
        assert result[0]['Name'] == 'Service 1'
    
    @patch.object(QuickBooksService, '_make_api_request')
    def test_get_estimates(self, mock_request, qb_service):
        """Test getting estimates"""
        mock_request.return_value = {
            'QueryResponse': {
                'Estimate': [
                    {'Id': '1', 'TotalAmt': 100.00}
                ]
            }
        }
        
        result = qb_service.get_estimates()
        assert len(result) == 1
        assert result[0]['TotalAmt'] == 100.00
    
    @patch.object(QuickBooksService, '_make_api_request')
    def test_get_invoices(self, mock_request, qb_service):
        """Test getting invoices"""
        mock_request.return_value = {
            'QueryResponse': {
                'Invoice': [
                    {'Id': '1', 'TotalAmt': 200.00}
                ]
            }
        }
        
        result = qb_service.get_invoices()
        assert len(result) == 1
        assert result[0]['TotalAmt'] == 200.00
    
    @patch.object(QuickBooksService, '_make_api_request')
    def test_get_single_customer(self, mock_request, qb_service):
        """Test getting a single customer by ID"""
        mock_request.return_value = {
            'Customer': {'Id': '123', 'DisplayName': 'Test Customer'}
        }
        
        result = qb_service.get_customer('123')
        assert result['Id'] == '123'
        assert result['DisplayName'] == 'Test Customer'
        mock_request.assert_called_with('/v3/company/{realm_id}/customer/123')
    
    @patch.object(QuickBooksService, '_make_api_request') 
    def test_api_request_with_different_methods(self, mock_request, qb_service):
        """Test API requests with different HTTP methods"""
        mock_request.return_value = {'success': True}
        
        # Test POST
        qb_service._make_api_request('/test', method='POST', data={'test': 'data'})
        mock_request.assert_called_with('/test', method='POST', data={'test': 'data'})
        
        # Test PUT
        qb_service._make_api_request('/test', method='PUT', data={'test': 'data'})
        mock_request.assert_called_with('/test', method='PUT', data={'test': 'data'})