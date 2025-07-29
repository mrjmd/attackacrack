import requests
import logging
from flask import current_app
from typing import Tuple, Optional, Dict, Any

# Configure structured logging
logger = logging.getLogger(__name__)

class OpenPhoneAPIError(Exception):
    """Custom exception for OpenPhone API errors"""
    def __init__(self, message: str, status_code: Optional[int] = None, response_body: Optional[str] = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body

class OpenPhoneService:
    def __init__(self):
        self.base_url = "https://api.openphone.com/v1"
        # Production-safe request configuration
        self.timeout = (5, 30)  # Connection timeout, read timeout
        self.max_retries = 3

    def send_sms(self, to_number: str, from_number_id: str, body: str) -> Tuple[Optional[Dict[Any, Any]], Optional[str]]:
        """
        Sends an SMS message using the OpenPhone API with proper error handling and security.
        
        Args:
            to_number: Recipient phone number
            from_number_id: OpenPhone number ID to send from
            body: Message content
            
        Returns:
            Tuple of (response_data, error_message)
        """
        api_key = current_app.config.get('OPENPHONE_API_KEY')
        
        if not api_key:
            logger.error("OpenPhone API key not configured")
            return None, "API Key not configured"

        url = f"{self.base_url}/messages"
        headers = {"Authorization": api_key}
        
        payload = {
            "from": from_number_id,
            "to": [to_number],
            "content": body
        }
        
        try:
            logger.info("Sending SMS via OpenPhone", extra={
                "to_number": to_number[-4:],  # Log only last 4 digits for privacy
                "from_number_id": from_number_id,
                "message_length": len(body)
            })
            
            response = requests.post(
                url, 
                headers=headers, 
                json=payload,
                timeout=self.timeout,
                verify=True  # SECURITY FIX: Always verify SSL certificates
            )
            response.raise_for_status()
            
            logger.info("SMS sent successfully via OpenPhone", extra={
                "to_number": to_number[-4:],
                "status_code": response.status_code
            })
            
            return response.json(), None
            
        except requests.exceptions.Timeout as e:
            logger.error("OpenPhone API request timeout", extra={
                "to_number": to_number[-4:],
                "timeout": self.timeout,
                "error": str(e)
            })
            return None, "Request timeout"
            
        except requests.exceptions.SSLError as e:
            logger.error("SSL verification failed for OpenPhone API", extra={
                "error": str(e)
            })
            return None, "SSL verification failed"
            
        except requests.exceptions.RequestException as e:
            status_code = getattr(e.response, 'status_code', None) if e.response else None
            response_body = e.response.text if e.response else None
            
            logger.error("OpenPhone API request failed", extra={
                "to_number": to_number[-4:],
                "status_code": status_code,
                "error": str(e),
                "response_body": response_body[:500] if response_body else None  # Truncate for logs
            })
            
            return None, f"OpenPhone API request failed: {str(e)}"
