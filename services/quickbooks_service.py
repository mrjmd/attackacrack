"""
QuickBooks Online API Service
Handles OAuth 2.0 authentication and API requests
"""

import os
import json
import base64
import requests
from datetime import datetime, timedelta
from typing import Dict, Optional, List, Any
from urllib.parse import urlencode
from cryptography.fernet import Fernet
from flask import current_app
from crm_database import db, QuickBooksAuth, QuickBooksSync


class QuickBooksService:
    def __init__(self):
        self.client_id = os.getenv('QUICKBOOKS_CLIENT_ID')
        self.client_secret = os.getenv('QUICKBOOKS_CLIENT_SECRET')
        self.redirect_uri = os.getenv('QUICKBOOKS_REDIRECT_URI', 'http://localhost:5000/auth/quickbooks/callback')
        sandbox_value = os.getenv('QUICKBOOKS_SANDBOX', 'True')
        self.sandbox = sandbox_value.lower() in ['true', '1', 'yes', 'on']
        
        # Base URLs
        self.auth_base_url = "https://appcenter.intuit.com/connect/oauth2"
        self.api_base_url = "https://sandbox-quickbooks.api.intuit.com" if self.sandbox else "https://quickbooks.api.intuit.com"
        
        # Initialize encryption for tokens (using a simple key for now - should be in env)
        encryption_key = os.getenv('ENCRYPTION_KEY', Fernet.generate_key().decode())
        self.cipher = Fernet(encryption_key.encode() if isinstance(encryption_key, str) else encryption_key)
        
        # OAuth scopes
        self.scopes = [
            "com.intuit.quickbooks.accounting",
            "com.intuit.quickbooks.payment"
        ]
    
    def get_authorization_url(self, state: str = None) -> str:
        """Generate OAuth authorization URL"""
        params = {
            'client_id': self.client_id,
            'scope': ' '.join(self.scopes),
            'redirect_uri': self.redirect_uri,
            'response_type': 'code',
            'state': state or base64.urlsafe_b64encode(os.urandom(32)).decode()
        }
        return f"{self.auth_base_url}?{urlencode(params)}"
    
    def exchange_code_for_tokens(self, code: str) -> Dict[str, Any]:
        """Exchange authorization code for access/refresh tokens"""
        token_url = "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer"
        
        headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/x-www-form-urlencoded',
            'Authorization': 'Basic ' + base64.b64encode(
                f"{self.client_id}:{self.client_secret}".encode()
            ).decode()
        }
        
        data = {
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': self.redirect_uri
        }
        
        response = requests.post(token_url, headers=headers, data=data)
        response.raise_for_status()
        
        token_data = response.json()
        
        # Save encrypted tokens
        self._save_auth(token_data)
        
        return token_data
    
    def refresh_access_token(self) -> bool:
        """Refresh expired access token"""
        auth = self._get_auth()
        if not auth:
            return False
        
        token_url = "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer"
        
        headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/x-www-form-urlencoded',
            'Authorization': 'Basic ' + base64.b64encode(
                f"{self.client_id}:{self.client_secret}".encode()
            ).decode()
        }
        
        data = {
            'grant_type': 'refresh_token',
            'refresh_token': self.cipher.decrypt(auth.refresh_token.encode()).decode()
        }
        
        try:
            response = requests.post(token_url, headers=headers, data=data)
            response.raise_for_status()
            
            token_data = response.json()
            
            # Update tokens
            auth.access_token = self.cipher.encrypt(token_data['access_token'].encode()).decode()
            auth.refresh_token = self.cipher.encrypt(token_data['refresh_token'].encode()).decode()
            auth.expires_at = datetime.utcnow() + timedelta(seconds=token_data['expires_in'])
            auth.updated_at = datetime.utcnow()
            
            db.session.commit()
            return True
            
        except Exception as e:
            current_app.logger.error(f"Token refresh failed: {str(e)}")
            return False
    
    def make_api_request(self, endpoint: str, method: str = 'GET', 
                        data: Dict = None, params: Dict = None) -> Dict[str, Any]:
        """Make authenticated API request to QuickBooks"""
        auth = self._get_auth()
        if not auth:
            raise Exception("No QuickBooks authentication found")
        
        # Check if token needs refresh
        if datetime.utcnow() >= auth.expires_at:
            if not self.refresh_access_token():
                raise Exception("Failed to refresh access token")
            auth = self._get_auth()
        
        # Decrypt access token
        access_token = self.cipher.decrypt(auth.access_token.encode()).decode()
        
        # Build request
        url = f"{self.api_base_url}/v3/company/{auth.company_id}/{endpoint}"
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        }
        
        # Make request
        response = requests.request(
            method=method,
            url=url,
            headers=headers,
            json=data,
            params=params
        )
        
        response.raise_for_status()
        return response.json()
    
    def _save_auth(self, token_data: Dict[str, Any]) -> QuickBooksAuth:
        """Save authentication tokens (encrypted)"""
        # Extract company ID from access token (JWT)
        import jwt
        decoded = jwt.decode(token_data['access_token'], options={"verify_signature": False})
        company_id = decoded.get('realmid')
        
        # Check if auth already exists
        auth = QuickBooksAuth.query.filter_by(company_id=company_id).first()
        if not auth:
            auth = QuickBooksAuth(company_id=company_id)
            db.session.add(auth)
        
        # Encrypt and save tokens
        auth.access_token = self.cipher.encrypt(token_data['access_token'].encode()).decode()
        auth.refresh_token = self.cipher.encrypt(token_data['refresh_token'].encode()).decode()
        auth.expires_at = datetime.utcnow() + timedelta(seconds=token_data['expires_in'])
        auth.updated_at = datetime.utcnow()
        
        db.session.commit()
        return auth
    
    def _get_auth(self) -> Optional[QuickBooksAuth]:
        """Get current authentication record"""
        # For now, just get the first one (single company support)
        return QuickBooksAuth.query.first()
    
    # Convenience methods for common operations
    
    def get_company_info(self) -> Dict[str, Any]:
        """Get QuickBooks company information"""
        auth = self._get_auth()
        if not auth:
            return None
        return self.make_api_request(f"companyinfo/{auth.company_id}")
    
    def list_customers(self, max_results: int = 1000) -> List[Dict[str, Any]]:
        """List all customers"""
        query = f"select * from Customer maxresults {max_results}"
        response = self.make_api_request("query", params={'query': query})
        return response.get('QueryResponse', {}).get('Customer', [])
    
    def list_items(self, max_results: int = 1000) -> List[Dict[str, Any]]:
        """List all items (products/services)"""
        query = f"select * from Item maxresults {max_results}"
        response = self.make_api_request("query", params={'query': query})
        return response.get('QueryResponse', {}).get('Item', [])
    
    def list_estimates(self, max_results: int = 1000) -> List[Dict[str, Any]]:
        """List all estimates"""
        query = f"select * from Estimate maxresults {max_results}"
        response = self.make_api_request("query", params={'query': query})
        return response.get('QueryResponse', {}).get('Estimate', [])
    
    def list_invoices(self, max_results: int = 1000) -> List[Dict[str, Any]]:
        """List all invoices"""
        query = f"select * from Invoice maxresults {max_results}"
        response = self.make_api_request("query", params={'query': query})
        return response.get('QueryResponse', {}).get('Invoice', [])
    
    def get_customer(self, customer_id: str) -> Dict[str, Any]:
        """Get a specific customer"""
        return self.make_api_request(f"customer/{customer_id}")
    
    def get_item(self, item_id: str) -> Dict[str, Any]:
        """Get a specific item"""
        return self.make_api_request(f"item/{item_id}")
    
    def get_estimate(self, estimate_id: str) -> Dict[str, Any]:
        """Get a specific estimate"""
        return self.make_api_request(f"estimate/{estimate_id}")
    
    def get_invoice(self, invoice_id: str) -> Dict[str, Any]:
        """Get a specific invoice"""
        return self.make_api_request(f"invoice/{invoice_id}")
    
    def is_authenticated(self) -> bool:
        """Check if we have valid authentication"""
        auth = self._get_auth()
        return auth is not None