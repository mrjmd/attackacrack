"""
Unit tests for EmailService
Tests email functionality in complete isolation using mocks
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from services.email_service import EmailService, EmailConfig, EmailMessage


class TestEmailService:
    """Test suite for EmailService"""
    
    @pytest.fixture
    def email_config(self):
        """Create test email configuration"""
        return EmailConfig(
            server="smtp.test.com",
            port=587,
            use_tls=True,
            username="test@test.com",
            password="testpass",
            default_sender="noreply@test.com"
        )
    
    @pytest.fixture
    def mock_mail_client(self):
        """Create mock Flask-Mail client"""
        mock = MagicMock()
        mock.send = MagicMock()
        return mock
    
    @pytest.fixture
    def service(self, mock_mail_client, email_config):
        """Create EmailService with mocked dependencies"""
        service = EmailService(mail_client=mock_mail_client, config=email_config)
        return service
    
    @pytest.fixture
    def sample_message(self):
        """Create sample email message"""
        return EmailMessage(
            subject="Test Email",
            recipients=["recipient@test.com"],
            body_text="This is a test email",
            body_html="<p>This is a test email</p>"
        )
    
    def test_init_without_dependencies(self):
        """Test service initialization without dependencies"""
        service = EmailService()
        assert service.mail_client is None
        assert service.config is None
        assert service._initialized is False
    
    def test_init_with_dependencies(self, mock_mail_client, email_config):
        """Test service initialization with dependencies"""
        service = EmailService(mail_client=mock_mail_client, config=email_config)
        assert service.mail_client == mock_mail_client
        assert service.config == email_config
        assert service._initialized is True
    
    def test_is_configured_true(self, service):
        """Test is_configured returns True when properly configured"""
        assert service.is_configured() is True
    
    def test_is_configured_false_no_config(self):
        """Test is_configured returns False without config"""
        service = EmailService()
        assert service.is_configured() is False
    
    def test_is_configured_false_no_server(self, mock_mail_client):
        """Test is_configured returns False without server config"""
        config = EmailConfig(server=None)
        service = EmailService(mail_client=mock_mail_client, config=config)
        assert service.is_configured() is False
    
    @patch('services.email_service.Message')
    def test_send_email_success(self, mock_message_class, service, sample_message, mock_mail_client):
        """Test successful email sending"""
        mock_msg = MagicMock()
        mock_message_class.return_value = mock_msg
        
        success, message = service.send_email(sample_message)
        
        assert success is True
        assert message == "Email sent successfully"
        
        # Verify Message was created with correct parameters
        mock_message_class.assert_called_once_with(
            subject="Test Email",
            recipients=["recipient@test.com"],
            body="This is a test email",
            html="<p>This is a test email</p>",
            sender="noreply@test.com"
        )
        
        # Verify email was sent
        mock_mail_client.send.assert_called_once_with(mock_msg)
    
    def test_send_email_not_configured(self, sample_message):
        """Test sending email when service not configured"""
        service = EmailService()
        success, message = service.send_email(sample_message)
        
        assert success is False
        assert message == "Email service not configured"
    
    @patch('services.email_service.Message')
    def test_send_email_with_cc_bcc(self, mock_message_class, service, mock_mail_client):
        """Test sending email with CC and BCC"""
        mock_msg = MagicMock()
        mock_message_class.return_value = mock_msg
        
        message = EmailMessage(
            subject="Test",
            recipients=["to@test.com"],
            body_text="Test",
            cc=["cc@test.com"],
            bcc=["bcc@test.com"]
        )
        
        service.send_email(message)
        
        assert mock_msg.cc == ["cc@test.com"]
        assert mock_msg.bcc == ["bcc@test.com"]
    
    @patch('services.email_service.Message')
    def test_send_email_with_attachments(self, mock_message_class, service, mock_mail_client):
        """Test sending email with attachments"""
        mock_msg = MagicMock()
        mock_message_class.return_value = mock_msg
        
        message = EmailMessage(
            subject="Test",
            recipients=["to@test.com"],
            body_text="Test",
            attachments=[
                {
                    'filename': 'test.pdf',
                    'content_type': 'application/pdf',
                    'data': b'PDF content'
                }
            ]
        )
        
        service.send_email(message)
        
        mock_msg.attach.assert_called_once_with(
            filename='test.pdf',
            content_type='application/pdf',
            data=b'PDF content'
        )
    
    @patch('services.email_service.Message')
    def test_send_email_exception(self, mock_message_class, service, sample_message, mock_mail_client):
        """Test handling of email send exception"""
        mock_mail_client.send.side_effect = Exception("SMTP error")
        
        success, message = service.send_email(sample_message)
        
        assert success is False
        assert "Failed to send email: SMTP error" in message
    
    @patch('services.email_service.Message')
    def test_send_bulk_emails(self, mock_message_class, service, mock_mail_client):
        """Test sending multiple emails"""
        messages = [
            EmailMessage(subject=f"Email {i}", recipients=[f"user{i}@test.com"], body_text=f"Text {i}")
            for i in range(3)
        ]
        
        results = service.send_bulk_emails(messages)
        
        assert len(results) == 3
        assert all(success for success, _ in results)
        assert mock_mail_client.send.call_count == 3
    
    @patch('services.email_service.Message')
    def test_send_bulk_emails_partial_failure(self, mock_message_class, service, mock_mail_client):
        """Test bulk email with some failures"""
        # Make second email fail
        mock_mail_client.send.side_effect = [None, Exception("Failed"), None]
        
        messages = [
            EmailMessage(subject=f"Email {i}", recipients=[f"user{i}@test.com"], body_text=f"Text {i}")
            for i in range(3)
        ]
        
        results = service.send_bulk_emails(messages)
        
        assert len(results) == 3
        assert results[0][0] is True  # First succeeded
        assert results[1][0] is False  # Second failed
        assert results[2][0] is True  # Third succeeded
    
    @patch('services.email_service.Message')
    def test_send_invitation_email(self, mock_message_class, service, mock_mail_client):
        """Test sending invitation email"""
        mock_msg = MagicMock()
        mock_message_class.return_value = mock_msg
        
        success, message = service.send_invitation_email(
            email="newuser@test.com",
            invite_url="https://app.com/invite/abc123",
            role="admin",
            expires_days=7
        )
        
        assert success is True
        
        # Verify email details
        call_args = mock_message_class.call_args
        assert call_args[1]['subject'] == "Invitation to Attack-a-Crack CRM"
        assert call_args[1]['recipients'] == ["newuser@test.com"]
        assert "admin" in call_args[1]['body']
        assert "https://app.com/invite/abc123" in call_args[1]['body']
    
    @patch('services.email_service.Message')
    def test_send_notification_email_normal(self, mock_message_class, service, mock_mail_client):
        """Test sending normal priority notification"""
        mock_msg = MagicMock()
        mock_message_class.return_value = mock_msg
        
        success, message = service.send_notification_email(
            recipients=["user@test.com"],
            subject="System Alert",
            message_text="System maintenance scheduled",
            priority="normal"
        )
        
        assert success is True
        
        call_args = mock_message_class.call_args
        assert call_args[1]['subject'] == "System Alert"
        assert "HIGH PRIORITY" not in call_args[1]['html']
    
    @patch('services.email_service.Message')
    def test_send_notification_email_high_priority(self, mock_message_class, service, mock_mail_client):
        """Test sending high priority notification"""
        mock_msg = MagicMock()
        mock_message_class.return_value = mock_msg
        
        success, message = service.send_notification_email(
            recipients=["user@test.com"],
            subject="System Alert",
            message_text="Critical system issue",
            priority="high"
        )
        
        assert success is True
        
        call_args = mock_message_class.call_args
        assert call_args[1]['subject'] == "[HIGH PRIORITY] System Alert"
        assert "HIGH PRIORITY" in call_args[1]['html']
    
    def test_validate_email_address_valid(self, service):
        """Test email validation with valid addresses"""
        valid_emails = [
            "user@example.com",
            "user.name@example.com",
            "user+tag@example.co.uk",
            "user_name@example-domain.com"
        ]
        
        for email in valid_emails:
            assert service.validate_email_address(email) is True
    
    def test_validate_email_address_invalid(self, service):
        """Test email validation with invalid addresses"""
        invalid_emails = [
            "notanemail",
            "@example.com",
            "user@",
            "user@.com",
            "user @example.com",
            "user@example"
        ]
        
        for email in invalid_emails:
            assert service.validate_email_address(email) is False
    
    @patch('services.email_service.Mail')
    def test_init_app(self, mock_mail_class):
        """Test init_app Flask integration"""
        mock_mail = MagicMock()
        mock_mail_class.return_value = mock_mail
        
        mock_app = MagicMock()
        mock_app.config = {
            'MAIL_SERVER': 'smtp.example.com',
            'MAIL_PORT': 465,
            'MAIL_USE_SSL': True,
            'MAIL_USERNAME': 'user@example.com',
            'MAIL_PASSWORD': 'password',
            'MAIL_DEFAULT_SENDER': 'noreply@example.com'
        }
        
        service = EmailService()
        service.init_app(mock_app)
        
        assert service.config.server == 'smtp.example.com'
        assert service.config.port == 465
        assert service.config.use_ssl is True
        assert service._initialized is True
        mock_mail.init_app.assert_called_once_with(mock_app)
    
    def test_init_app_no_server(self):
        """Test init_app without mail server config"""
        mock_app = MagicMock()
        mock_app.config = {}
        
        service = EmailService()
        service.init_app(mock_app)
        
        assert service._initialized is False
    
    def test_render_template(self, service):
        """Test template rendering"""
        template = "Hello {{name}}, your role is {{role}}"
        context = {"name": "John", "role": "admin"}
        
        result = service._render_template(template, context)
        
        assert result == "Hello John, your role is admin"
    
    @patch('services.email_service.Message')
    def test_send_template_email(self, mock_message_class, service, mock_mail_client):
        """Test sending templated email"""
        mock_msg = MagicMock()
        mock_message_class.return_value = mock_msg
        
        # Mock template loading to return inline template
        service._load_template = Mock(side_effect=lambda name, type: 
            "Hello {{name}}" if type == 'text' else "<p>Hello {{name}}</p>")
        
        success, message = service.send_template_email(
            template_name="welcome",
            recipients=["user@test.com"],
            context={"name": "John"},
            subject="Welcome"
        )
        
        assert success is True
        
        call_args = mock_message_class.call_args
        assert "Hello John" in call_args[1]['body']
        assert "<p>Hello John</p>" in call_args[1]['html']