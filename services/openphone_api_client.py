"""
OpenPhone API Client

Handles all direct API communication with OpenPhone, including:
- Authentication
- Rate limiting
- Pagination
- Error handling
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import requests
from flask import current_app

logger = logging.getLogger(__name__)


class OpenPhoneAPIClient:
    """Client for interacting with OpenPhone API"""
    
    def __init__(self, api_key: Optional[str] = None, base_url: str = "https://api.openphone.com/v1"):
        """
        Initialize OpenPhone API client.
        
        Args:
            api_key: OpenPhone API key (will use from config if not provided)
            base_url: Base URL for OpenPhone API
        """
        self.api_key = api_key or current_app.config.get('OPENPHONE_API_KEY')
        self.base_url = base_url
        self.timeout = (5, 30)  # Connection timeout, read timeout
        self.max_retries = 3
        self.retry_delay = 1  # Initial retry delay in seconds
        
        if not self.api_key:
            raise ValueError("OpenPhone API key not configured")
    
    def _make_request(self, method: str, endpoint: str, params: Optional[Dict] = None,
                     json_data: Optional[Dict] = None, retry_count: int = 0) -> Dict[str, Any]:
        """
        Make HTTP request to OpenPhone API with retry logic.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path
            params: Query parameters
            json_data: JSON body data
            retry_count: Current retry attempt
            
        Returns:
            Response data as dictionary
            
        Raises:
            Exception: On API errors after retries exhausted
        """
        url = f"{self.base_url}/{endpoint}"
        headers = {
            "Authorization": self.api_key,
            "Content-Type": "application/json"
        }
        
        try:
            logger.debug(f"Making {method} request to {endpoint}", extra={
                "params": params,
                "retry_count": retry_count
            })
            
            response = requests.request(
                method=method,
                url=url,
                headers=headers,
                params=params,
                json=json_data,
                timeout=self.timeout,
                verify=True
            )
            
            # Handle rate limiting
            if response.status_code == 429:
                if retry_count < self.max_retries:
                    # Exponential backoff
                    delay = self.retry_delay * (2 ** retry_count)
                    logger.warning(f"Rate limited, retrying after {delay} seconds", extra={
                        "retry_count": retry_count,
                        "delay": delay
                    })
                    time.sleep(delay)
                    return self._make_request(method, endpoint, params, json_data, retry_count + 1)
                else:
                    raise Exception(f"Rate limit exceeded after {self.max_retries} retries")
            
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.Timeout as e:
            logger.error(f"Request timeout for {endpoint}", extra={
                "error": str(e),
                "retry_count": retry_count
            })
            if retry_count < self.max_retries:
                time.sleep(self.retry_delay * (2 ** retry_count))
                return self._make_request(method, endpoint, params, json_data, retry_count + 1)
            raise Exception(f"Request timeout after {self.max_retries} retries: {str(e)}")
            
        except requests.exceptions.RequestException as e:
            logger.error(f"API request failed for {endpoint}", extra={
                "error": str(e),
                "status_code": getattr(e.response, 'status_code', None) if hasattr(e, 'response') else None
            })
            if retry_count < self.max_retries and getattr(e.response, 'status_code', 500) >= 500:
                time.sleep(self.retry_delay * (2 ** retry_count))
                return self._make_request(method, endpoint, params, json_data, retry_count + 1)
            raise Exception(f"API request failed: {str(e)}")
    
    def get_messages(self, since: Optional[str] = None, until: Optional[str] = None,
                    cursor: Optional[str] = None, limit: int = 100,
                    phone_number_id: Optional[str] = None,
                    conversation_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Fetch messages from OpenPhone API.
        
        Args:
            since: ISO 8601 timestamp to fetch messages after
            until: ISO 8601 timestamp to fetch messages before
            cursor: Pagination cursor from previous response
            limit: Number of messages per page (max 100)
            phone_number_id: Filter by phone number ID
            conversation_id: Filter by conversation ID
            
        Returns:
            Dictionary with 'data' (list of messages) and 'cursor' (for pagination)
        """
        params = {
            'limit': min(limit, 100)  # API max is 100
        }
        
        if since:
            params['since'] = since
        if until:
            params['until'] = until
        if cursor:
            params['cursor'] = cursor
        if phone_number_id:
            params['phoneNumberId'] = phone_number_id
        if conversation_id:
            params['conversationId'] = conversation_id
        
        logger.info(f"Fetching messages from OpenPhone", extra={
            "since": since,
            "until": until,
            "cursor": cursor[:10] if cursor else None,
            "limit": limit
        })
        
        response = self._make_request('GET', 'messages', params=params)
        
        # Ensure consistent response format
        if 'data' not in response:
            response['data'] = []
        if 'cursor' not in response:
            response['cursor'] = None
        
        logger.info(f"Fetched {len(response.get('data', []))} messages", extra={
            "has_more": bool(response.get('cursor'))
        })
        
        return response
    
    def get_conversations(self, cursor: Optional[str] = None, limit: int = 100,
                         phone_number_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Fetch conversations from OpenPhone API.
        
        Args:
            cursor: Pagination cursor from previous response
            limit: Number of conversations per page (max 100)
            phone_number_id: Filter by phone number ID
            
        Returns:
            Dictionary with 'data' (list of conversations) and 'cursor' (for pagination)
        """
        params = {
            'limit': min(limit, 100)
        }
        
        if cursor:
            params['cursor'] = cursor
        if phone_number_id:
            params['phoneNumberId'] = phone_number_id
        
        response = self._make_request('GET', 'conversations', params=params)
        
        # Ensure consistent response format
        if 'data' not in response:
            response['data'] = []
        if 'cursor' not in response:
            response['cursor'] = None
        
        return response
    
    def send_message(self, to_number: str, from_number_id: str, body: str,
                    media_urls: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Send a message via OpenPhone API.
        
        Args:
            to_number: Recipient phone number
            from_number_id: OpenPhone number ID to send from
            body: Message content
            media_urls: Optional list of media URLs to attach
            
        Returns:
            Response data from API
        """
        payload = {
            "from": from_number_id,
            "to": [to_number],
            "content": body
        }
        
        if media_urls:
            payload["mediaUrls"] = media_urls
        
        logger.info("Sending message via OpenPhone", extra={
            "to_number": to_number[-4:],  # Log only last 4 digits for privacy
            "from_number_id": from_number_id,
            "message_length": len(body),
            "has_media": bool(media_urls)
        })
        
        response = self._make_request('POST', 'messages', json_data=payload)
        
        logger.info("Message sent successfully", extra={
            "message_id": response.get('id'),
            "status": response.get('status')
        })
        
        return response
    
    def get_phone_numbers(self) -> List[Dict[str, Any]]:
        """
        Get all phone numbers associated with the account.
        
        Returns:
            List of phone number objects
        """
        response = self._make_request('GET', 'phoneNumbers')
        return response.get('data', [])
    
    def get_users(self) -> List[Dict[str, Any]]:
        """
        Get all users in the workspace.
        
        Returns:
            List of user objects
        """
        response = self._make_request('GET', 'users')
        return response.get('data', [])
    
    def validate_webhook_token(self, token: str) -> bool:
        """
        Validate a webhook token with OpenPhone.
        
        Args:
            token: Webhook validation token
            
        Returns:
            True if token is valid
        """
        try:
            response = self._make_request('POST', 'webhooks/validate', json_data={'token': token})
            return response.get('valid', False)
        except Exception as e:
            logger.error(f"Failed to validate webhook token: {e}")
            return False
    
    def get_message_by_id(self, message_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific message by ID.
        
        Args:
            message_id: OpenPhone message ID
            
        Returns:
            Message object or None if not found
        """
        try:
            response = self._make_request('GET', f'messages/{message_id}')
            return response
        except Exception as e:
            logger.error(f"Failed to get message {message_id}: {e}")
            return None
    
    def get_conversation_by_id(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific conversation by ID.
        
        Args:
            conversation_id: OpenPhone conversation ID
            
        Returns:
            Conversation object or None if not found
        """
        try:
            response = self._make_request('GET', f'conversations/{conversation_id}')
            return response
        except Exception as e:
            logger.error(f"Failed to get conversation {conversation_id}: {e}")
            return None