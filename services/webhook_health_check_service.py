"""
WebhookHealthCheckService - Monitor OpenPhone webhook health
Sends test messages and verifies webhook receipt within timeout period
"""

import time
import uuid
from datetime import datetime, timedelta
from utils.datetime_utils import utc_now
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from enum import Enum
from sqlalchemy import and_, desc

from repositories.webhook_event_repository import WebhookEventRepository
from services.openphone_service import OpenPhoneService
from services.email_service import EmailService, EmailMessage
from logging_config import get_logger

logger = get_logger(__name__)


class HealthCheckStatus(Enum):
    """Health check status enumeration"""
    SENT = "sent"
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"


@dataclass
class HealthCheckResult:
    """Result of a health check operation"""
    status: HealthCheckStatus
    message_id: Optional[str] = None
    sent_at: Optional[datetime] = None
    received_at: Optional[datetime] = None
    response_time: Optional[float] = None
    error_message: Optional[str] = None
    check_message: Optional[str] = None


class WebhookHealthCheckService:
    """Service for monitoring OpenPhone webhook health"""
    
    def __init__(
        self,
        webhook_repository: WebhookEventRepository,
        openphone_service: OpenPhoneService,
        email_service: EmailService,
        test_phone_number: str,
        alert_email: str,
        health_check_timeout: int = 120  # 2 minutes default
    ):
        """
        Initialize WebhookHealthCheckService
        
        Args:
            webhook_repository: Repository for webhook events
            openphone_service: Service for sending SMS via OpenPhone
            email_service: Service for sending alert emails
            test_phone_number: Phone number to send test messages to
            alert_email: Email address for health check alerts
            health_check_timeout: Timeout in seconds for webhook receipt
        """
        self.webhook_repository = webhook_repository
        self.openphone_service = openphone_service
        self.email_service = email_service
        self.test_phone_number = test_phone_number
        self.alert_email = alert_email
        self.health_check_timeout = health_check_timeout
        self.health_check_prefix = "[HEALTH_CHECK]"
    
    def run_health_check(self) -> HealthCheckResult:
        """
        Run a complete health check cycle
        
        Returns:
            HealthCheckResult with status and details
        """
        logger.info("Starting webhook health check")
        
        # Step 1: Send health check message
        send_result = self.send_health_check()
        
        if send_result.status == HealthCheckStatus.FAILED:
            logger.error("Health check failed to send", error=send_result.error_message)
            self._send_alert_email(send_result)
            self._store_health_check_result(send_result)
            return send_result
        
        # Step 2: Verify webhook receipt
        verify_result = self.verify_webhook_receipt(
            send_result.check_message,
            send_result.sent_at,
            timeout=self.health_check_timeout
        )
        
        # Combine results
        final_result = HealthCheckResult(
            status=verify_result.status,
            message_id=send_result.message_id,
            sent_at=send_result.sent_at,
            received_at=verify_result.received_at,
            response_time=verify_result.response_time,
            error_message=verify_result.error_message,
            check_message=send_result.check_message
        )
        
        # Step 3: Send alert if needed
        if final_result.status in [HealthCheckStatus.TIMEOUT, HealthCheckStatus.FAILED]:
            logger.warning("Health check failed", status=final_result.status.value, error=final_result.error_message)
            self._send_alert_email(final_result)
        else:
            logger.info("Health check successful", response_time=final_result.response_time)
        
        # Step 4: Store result for history
        self._store_health_check_result(final_result)
        
        return final_result
    
    def send_health_check(self) -> HealthCheckResult:
        """
        Send a health check message via OpenPhone
        
        Returns:
            HealthCheckResult with send status
        """
        check_message = self._generate_health_check_message()
        sent_at = utc_now()
        
        try:
            response = self.openphone_service.send_message(
                self.test_phone_number,
                check_message
            )
            
            if response.get('success'):
                message_data = response.get('data', {})
                return HealthCheckResult(
                    status=HealthCheckStatus.SENT,
                    message_id=message_data.get('id'),
                    sent_at=sent_at,
                    check_message=check_message
                )
            else:
                return HealthCheckResult(
                    status=HealthCheckStatus.FAILED,
                    sent_at=sent_at,
                    error_message=f"Failed to send health check: {response.get('error')}",
                    check_message=check_message
                )
                
        except Exception as e:
            logger.exception("Exception sending health check")
            return HealthCheckResult(
                status=HealthCheckStatus.FAILED,
                sent_at=sent_at,
                error_message=f"Exception sending health check: {str(e)}",
                check_message=check_message
            )
    
    def verify_webhook_receipt(
        self,
        check_message: str,
        sent_at: datetime,
        timeout: Optional[int] = None
    ) -> HealthCheckResult:
        """
        Verify that webhook was received for the health check message
        
        Args:
            check_message: The health check message that was sent
            sent_at: When the message was sent
            timeout: Timeout in seconds (uses default if not specified)
            
        Returns:
            HealthCheckResult with verification status
        """
        timeout = timeout or self.health_check_timeout
        start_time = time.time()
        
        while (time.time() - start_time) < timeout:
            # Check for webhook event with matching message
            webhook_event = self._find_matching_webhook(check_message, sent_at)
            
            if webhook_event:
                received_at = webhook_event.created_at
                response_time = (received_at - sent_at).total_seconds()
                
                return HealthCheckResult(
                    status=HealthCheckStatus.SUCCESS,
                    received_at=received_at,
                    response_time=response_time
                )
            
            # Wait before checking again
            time.sleep(5)
        
        # Timeout reached
        return HealthCheckResult(
            status=HealthCheckStatus.TIMEOUT,
            error_message="Webhook not received within timeout period"
        )
    
    def _find_matching_webhook(self, check_message: str, sent_at: datetime):
        """
        Find webhook event matching the health check message
        
        Args:
            check_message: The health check message to match
            sent_at: When the message was sent
            
        Returns:
            WebhookEvent or None
        """
        # This method is easier to mock in tests
        return self.webhook_repository.session.query(self.webhook_repository.model_class).filter(
            and_(
                self.webhook_repository.model_class.event_type == 'message.received',
                self.webhook_repository.model_class.created_at >= sent_at
            )
        ).filter(
            self.webhook_repository.model_class.payload['text'].astext == check_message
        ).first()
    
    def get_health_check_status(self, hours: int = 24) -> Dict[str, Any]:
        """
        Get health check status summary for the specified period
        
        Args:
            hours: Number of hours to look back
            
        Returns:
            Dictionary with health check statistics
        """
        since = utc_now() - timedelta(hours=hours)
        
        # Query health check events using a more testable approach
        events = self._get_health_check_events(since)
        
        # Calculate statistics
        total_checks = len(events)
        successful_checks = sum(1 for e in events if e.event_type == 'health_check.success')
        failed_checks = total_checks - successful_checks
        
        response_times = [
            e.payload.get('response_time')
            for e in events
            if e.event_type == 'health_check.success' and e.payload.get('response_time')
        ]
        
        avg_response_time = sum(response_times) / len(response_times) if response_times else None
        
        return {
            'total_checks': total_checks,
            'successful_checks': successful_checks,
            'failed_checks': failed_checks,
            'success_rate': (successful_checks / total_checks * 100) if total_checks > 0 else 0,
            'average_response_time': avg_response_time,
            'last_check': events[0].created_at if events else None,
            'period_hours': hours
        }
    
    def _get_health_check_events(self, since: datetime) -> List:
        """
        Get health check events since the specified time
        
        Args:
            since: Start time for events
            
        Returns:
            List of webhook events
        """
        # This method is easier to mock in tests
        return self.webhook_repository.session.query(self.webhook_repository.model_class).filter(
            and_(
                self.webhook_repository.model_class.event_type.like('health_check.%'),
                self.webhook_repository.model_class.created_at >= since
            )
        ).order_by(desc(self.webhook_repository.model_class.created_at)).limit(100).all()
    
    def _generate_health_check_message(self) -> str:
        """
        Generate a unique health check message
        
        Returns:
            Unique health check message with timestamp and ID
        """
        timestamp = utc_now().isoformat()
        unique_id = str(uuid.uuid4())[:8]
        return f"{self.health_check_prefix} Test at {timestamp}-{unique_id}"
    
    def _send_alert_email(self, result: HealthCheckResult) -> None:
        """
        Send an alert email for failed health check
        
        Args:
            result: Health check result to alert about
        """
        if not self.email_service.is_configured():
            logger.warning("Email service not configured, cannot send alert")
            return
        
        subject, body = self._format_alert_email(result)
        
        email_message = EmailMessage(
            subject=subject,
            recipients=[self.alert_email],
            body_text=body,
            body_html=f"<pre>{body}</pre>"
        )
        
        try:
            success, message = self.email_service.send_email(email_message)
            if success:
                logger.info("Alert email sent", recipient=self.alert_email)
            else:
                logger.error("Failed to send alert email", error=message)
        except Exception as e:
            logger.exception("Exception sending alert email", error=str(e))
    
    def _format_alert_email(self, result: HealthCheckResult) -> tuple[str, str]:
        """
        Format alert email content
        
        Args:
            result: Health check result to format
            
        Returns:
            Tuple of (subject, body)
        """
        if result.status == HealthCheckStatus.TIMEOUT:
            subject = "ALERT: OpenPhone Webhook Not Received"
        elif result.status == HealthCheckStatus.FAILED:
            subject = "ALERT: OpenPhone Webhook Health Check Failed"
        else:
            subject = f"ALERT: OpenPhone Webhook Health Check - {result.status.value}"
        
        body = f"""
OpenPhone Webhook Health Check Alert
=====================================

Status: {result.status.value.upper()}
Time: {utc_now().strftime('%Y-%m-%d %H:%M:%S UTC')}

Details:
--------
Message ID: {result.message_id or 'N/A'}
Sent At: {result.sent_at.strftime('%Y-%m-%d %H:%M:%S UTC') if result.sent_at else 'N/A'}
Received At: {result.received_at.strftime('%Y-%m-%d %H:%M:%S UTC') if result.received_at else 'Not Received'}
Response Time: {f'{result.response_time:.2f} seconds' if result.response_time else 'N/A'}

Error: {result.error_message or 'None'}

Action Required:
----------------
1. Check OpenPhone webhook configuration
2. Verify API keys are valid
3. Check network connectivity
4. Review recent webhook logs

This is an automated alert from the Attack-a-Crack CRM system.
        """
        
        return subject, body.strip()
    
    def _store_health_check_result(self, result: HealthCheckResult) -> None:
        """
        Store health check result in webhook event repository
        
        Args:
            result: Health check result to store
        """
        event_type = f"health_check.{result.status.value}"
        event_id = f"health_check_{uuid.uuid4()}"
        
        payload = {
            'status': result.status.value,
            'message_id': result.message_id,
            'sent_at': result.sent_at.isoformat() if result.sent_at else None,
            'received_at': result.received_at.isoformat() if result.received_at else None,
            'response_time': result.response_time,
            'error_message': result.error_message,
            'check_message': result.check_message
        }
        
        try:
            self.webhook_repository.create({
                'event_id': event_id,
                'event_type': event_type,
                'payload': payload,
                'processed': True,
                'processed_at': utc_now()
            })
            logger.debug("Stored health check result", event_id=event_id, status=result.status.value)
        except Exception as e:
            logger.error("Failed to store health check result", error=str(e))