"""
EmailService - Abstraction for email functionality
Provides a clean interface for sending emails with proper dependency injection
"""

from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass
from flask_mail import Mail, Message
from logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class EmailConfig:
    """Email configuration container"""
    server: str
    port: int = 587
    use_tls: bool = True
    use_ssl: bool = False
    username: Optional[str] = None
    password: Optional[str] = None
    default_sender: str = "noreply@example.com"
    max_emails: Optional[int] = None


@dataclass
class EmailMessage:
    """Email message data structure"""
    subject: str
    recipients: List[str]
    body_text: str
    body_html: Optional[str] = None
    sender: Optional[str] = None
    cc: Optional[List[str]] = None
    bcc: Optional[List[str]] = None
    reply_to: Optional[str] = None
    attachments: Optional[List[Dict[str, Any]]] = None


class EmailService:
    """Service for handling email operations"""
    
    def __init__(self, mail_client: Optional[Mail] = None, config: Optional[EmailConfig] = None):
        """
        Initialize Email Service
        
        Args:
            mail_client: Flask-Mail instance (optional, for testing)
            config: Email configuration
        """
        self.mail_client = mail_client
        self.config = config
        self._initialized = False
        
        if mail_client:
            self._initialized = True
    
    def init_app(self, app):
        """
        Initialize with Flask app (for backward compatibility)
        
        Args:
            app: Flask application instance
        """
        if not self.mail_client:
            self.mail_client = Mail()
        
        # Configure from app config if not already configured
        if not self.config:
            self.config = EmailConfig(
                server=app.config.get('MAIL_SERVER'),
                port=app.config.get('MAIL_PORT', 587),
                use_tls=app.config.get('MAIL_USE_TLS', True),
                use_ssl=app.config.get('MAIL_USE_SSL', False),
                username=app.config.get('MAIL_USERNAME'),
                password=app.config.get('MAIL_PASSWORD'),
                default_sender=app.config.get('MAIL_DEFAULT_SENDER', 'noreply@example.com')
            )
        
        if self.config.server:
            self.mail_client.init_app(app)
            self._initialized = True
            logger.info("Email service initialized", server=self.config.server)
        else:
            logger.warning("Email service not configured - MAIL_SERVER not set")
    
    def is_configured(self) -> bool:
        """
        Check if email service is properly configured
        
        Returns:
            True if configured and ready to send emails
        """
        return self._initialized and self.config and self.config.server is not None
    
    def send_email(self, message: EmailMessage) -> Tuple[bool, str]:
        """
        Send an email message
        
        Args:
            message: EmailMessage object containing email details
            
        Returns:
            Tuple of (success: bool, message: str)
        """
        if not self.is_configured():
            logger.warning("Attempted to send email but service not configured")
            return False, "Email service not configured"
        
        try:
            # Create Flask-Mail Message
            msg = Message(
                subject=message.subject,
                recipients=message.recipients,
                body=message.body_text,
                html=message.body_html,
                sender=message.sender or self.config.default_sender
            )
            
            # Add optional fields
            if message.cc:
                msg.cc = message.cc
            if message.bcc:
                msg.bcc = message.bcc
            if message.reply_to:
                msg.reply_to = message.reply_to
            
            # Add attachments if any
            if message.attachments:
                for attachment in message.attachments:
                    msg.attach(
                        filename=attachment.get('filename'),
                        content_type=attachment.get('content_type', 'application/octet-stream'),
                        data=attachment.get('data')
                    )
            
            # Send the email
            self.mail_client.send(msg)
            
            logger.info(
                "Email sent successfully",
                subject=message.subject,
                recipients=message.recipients
            )
            return True, "Email sent successfully"
            
        except Exception as e:
            logger.error(
                "Failed to send email",
                error=str(e),
                subject=message.subject,
                recipients=message.recipients
            )
            return False, f"Failed to send email: {str(e)}"
    
    def send_bulk_emails(self, messages: List[EmailMessage]) -> List[Tuple[bool, str]]:
        """
        Send multiple emails
        
        Args:
            messages: List of EmailMessage objects
            
        Returns:
            List of (success, message) tuples for each email
        """
        results = []
        
        for message in messages:
            result = self.send_email(message)
            results.append(result)
            
            # Optional: Add delay between emails to avoid rate limiting
            # import time
            # time.sleep(0.1)
        
        successful = sum(1 for success, _ in results if success)
        logger.info(
            f"Bulk email send completed",
            total=len(messages),
            successful=successful,
            failed=len(messages) - successful
        )
        
        return results
    
    def send_template_email(self,
                          template_name: str,
                          recipients: List[str],
                          context: Dict[str, Any],
                          subject: str) -> Tuple[bool, str]:
        """
        Send an email using a template
        
        Args:
            template_name: Name of the email template
            recipients: List of recipient email addresses
            context: Template context variables
            subject: Email subject
            
        Returns:
            Tuple of (success: bool, message: str)
        """
        try:
            # This would integrate with a template engine like Jinja2
            # For now, we'll use a simple placeholder system
            html_template = self._load_template(template_name, 'html')
            text_template = self._load_template(template_name, 'text')
            
            # Render templates with context
            html_body = self._render_template(html_template, context) if html_template else None
            text_body = self._render_template(text_template, context)
            
            message = EmailMessage(
                subject=subject,
                recipients=recipients,
                body_text=text_body,
                body_html=html_body
            )
            
            return self.send_email(message)
            
        except Exception as e:
            logger.error(f"Failed to send template email: {e}")
            return False, f"Failed to send template email: {str(e)}"
    
    def send_invitation_email(self,
                            email: str,
                            invite_url: str,
                            role: str,
                            expires_days: int = 7) -> Tuple[bool, str]:
        """
        Send an invitation email (specific use case)
        
        Args:
            email: Recipient email address
            invite_url: URL for accepting the invitation
            role: Role being invited to
            expires_days: Days until invitation expires
            
        Returns:
            Tuple of (success: bool, message: str)
        """
        html_body = f"""
        <h2>You've been invited to Attack-a-Crack CRM</h2>
        <p>You've been invited to join as a {role}.</p>
        <p>Click the link below to create your account:</p>
        <p><a href="{invite_url}" style="background-color: #4CAF50; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; display: inline-block;">Accept Invitation</a></p>
        <p>This invitation will expire in {expires_days} days.</p>
        <p>If you didn't expect this invitation, please ignore this email.</p>
        """
        
        text_body = f"""
        You've been invited to Attack-a-Crack CRM
        
        You've been invited to join as a {role}.
        
        Click the link below to create your account:
        {invite_url}
        
        This invitation will expire in {expires_days} days.
        
        If you didn't expect this invitation, please ignore this email.
        """
        
        message = EmailMessage(
            subject="Invitation to Attack-a-Crack CRM",
            recipients=[email],
            body_text=text_body,
            body_html=html_body
        )
        
        return self.send_email(message)
    
    def send_notification_email(self,
                               recipients: List[str],
                               subject: str,
                               message_text: str,
                               priority: str = "normal") -> Tuple[bool, str]:
        """
        Send a notification email
        
        Args:
            recipients: List of recipient email addresses
            subject: Email subject
            message_text: Notification message
            priority: Email priority (low, normal, high)
            
        Returns:
            Tuple of (success: bool, message: str)
        """
        # Add priority header if high priority
        html_body = f"<p>{message_text}</p>"
        
        if priority == "high":
            html_body = f"<p><strong>⚠️ HIGH PRIORITY</strong></p>{html_body}"
            subject = f"[HIGH PRIORITY] {subject}"
        
        message = EmailMessage(
            subject=subject,
            recipients=recipients,
            body_text=message_text,
            body_html=html_body
        )
        
        return self.send_email(message)
    
    def validate_email_address(self, email: str) -> bool:
        """
        Validate email address format
        
        Args:
            email: Email address to validate
            
        Returns:
            True if valid email format
        """
        import re
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email) is not None
    
    def _load_template(self, template_name: str, template_type: str) -> Optional[str]:
        """
        Load email template from file
        
        Args:
            template_name: Name of the template
            template_type: 'html' or 'text'
            
        Returns:
            Template content or None if not found
        """
        # This would load from templates/emails/ directory
        # For now, return None to use inline templates
        return None
    
    def _render_template(self, template: str, context: Dict[str, Any]) -> str:
        """
        Render template with context
        
        Args:
            template: Template string
            context: Context variables
            
        Returns:
            Rendered template
        """
        # Simple placeholder replacement
        # In production, use Jinja2 or similar
        for key, value in context.items():
            template = template.replace(f"{{{{{key}}}}}", str(value))
        return template