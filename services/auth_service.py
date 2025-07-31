# services/auth_service.py

from flask_bcrypt import Bcrypt
from flask_login import LoginManager, login_user, logout_user
from extensions import db
from crm_database import User, InviteToken
from datetime import datetime, timedelta
import secrets
import string
from flask_mail import Mail, Message
from flask import current_app
import re

bcrypt = Bcrypt()
login_manager = LoginManager()
mail = Mail()


class AuthService:
    """Service for handling authentication and user management"""
    
    @staticmethod
    def init_app(app):
        """Initialize authentication services with app"""
        bcrypt.init_app(app)
        login_manager.init_app(app)
        login_manager.login_view = 'auth.login'
        login_manager.login_message = 'Please log in to access this page.'
        
        # Initialize mail if configured
        if app.config.get('MAIL_SERVER'):
            mail.init_app(app)
    
    @staticmethod
    @login_manager.user_loader
    def load_user(user_id):
        """Load user for Flask-Login"""
        return User.query.get(int(user_id))
    
    @staticmethod
    def validate_password(password):
        """Validate password meets security requirements"""
        if len(password) < 8:
            return False, "Password must be at least 8 characters long"
        
        if not re.search(r'[A-Z]', password):
            return False, "Password must contain at least one uppercase letter"
        
        if not re.search(r'[a-z]', password):
            return False, "Password must contain at least one lowercase letter"
        
        if not re.search(r'[0-9]', password):
            return False, "Password must contain at least one number"
        
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            return False, "Password must contain at least one special character"
        
        return True, "Password is valid"
    
    @staticmethod
    def create_user(email, password, first_name, last_name, role='marketer'):
        """Create a new user with hashed password"""
        # Validate password
        is_valid, message = AuthService.validate_password(password)
        if not is_valid:
            return None, message
        
        # Check if user already exists
        if User.query.filter_by(email=email).first():
            return None, "User with this email already exists"
        
        # Hash password and create user
        password_hash = bcrypt.generate_password_hash(password).decode('utf-8')
        user = User(
            email=email,
            password_hash=password_hash,
            first_name=first_name,
            last_name=last_name,
            role=role
        )
        
        db.session.add(user)
        db.session.commit()
        
        return user, "User created successfully"
    
    @staticmethod
    def authenticate_user(email, password):
        """Authenticate user with email and password"""
        user = User.query.filter_by(email=email).first()
        
        if not user:
            return None, "Invalid email or password"
        
        if not user.is_active:
            return None, "Account is deactivated"
        
        if not bcrypt.check_password_hash(user.password_hash, password):
            return None, "Invalid email or password"
        
        # Update last login
        user.last_login = datetime.utcnow()
        db.session.commit()
        
        return user, "Authentication successful"
    
    @staticmethod
    def login_user_session(user, remember=False):
        """Log in user and create session"""
        return login_user(user, remember=remember)
    
    @staticmethod
    def logout_user_session():
        """Log out current user"""
        logout_user()
    
    @staticmethod
    def generate_invite_token():
        """Generate a secure random token"""
        alphabet = string.ascii_letters + string.digits
        return ''.join(secrets.choice(alphabet) for _ in range(32))
    
    @staticmethod
    def create_invite(email, role, created_by_user):
        """Create an invite token for a new user"""
        # Check if user already exists
        if User.query.filter_by(email=email).first():
            return None, "User with this email already exists"
        
        # Check for existing unused invite
        existing_invite = InviteToken.query.filter_by(
            email=email,
            used=False
        ).filter(InviteToken.expires_at > datetime.utcnow()).first()
        
        if existing_invite:
            return existing_invite, "Invite already sent to this email"
        
        # Create new invite
        token = AuthService.generate_invite_token()
        expires_at = datetime.utcnow() + timedelta(days=7)  # 7 day expiry
        
        invite = InviteToken(
            email=email,
            token=token,
            role=role,
            expires_at=expires_at,
            created_by_id=created_by_user.id
        )
        
        db.session.add(invite)
        db.session.commit()
        
        return invite, "Invite created successfully"
    
    @staticmethod
    def send_invite_email(invite, base_url):
        """Send invite email to user"""
        if not mail:
            return False, "Email service not configured"
        
        invite_url = f"{base_url}/auth/accept-invite/{invite.token}"
        
        msg = Message(
            'Invitation to Attack-a-Crack CRM',
            sender=current_app.config.get('MAIL_DEFAULT_SENDER', 'noreply@attackacrack.com'),
            recipients=[invite.email]
        )
        
        msg.html = f"""
        <h2>You've been invited to Attack-a-Crack CRM</h2>
        <p>You've been invited to join as a {invite.role}.</p>
        <p>Click the link below to create your account:</p>
        <p><a href="{invite_url}" style="background-color: #4CAF50; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; display: inline-block;">Accept Invitation</a></p>
        <p>This invitation will expire in 7 days.</p>
        <p>If you didn't expect this invitation, please ignore this email.</p>
        """
        
        msg.body = f"""
        You've been invited to Attack-a-Crack CRM
        
        You've been invited to join as a {invite.role}.
        
        Click the link below to create your account:
        {invite_url}
        
        This invitation will expire in 7 days.
        
        If you didn't expect this invitation, please ignore this email.
        """
        
        try:
            mail.send(msg)
            return True, "Invite email sent successfully"
        except Exception as e:
            return False, f"Failed to send email: {str(e)}"
    
    @staticmethod
    def validate_invite_token(token):
        """Validate an invite token"""
        invite = InviteToken.query.filter_by(token=token).first()
        
        if not invite:
            return None, "Invalid invitation token"
        
        if invite.used:
            return None, "This invitation has already been used"
        
        if invite.expires_at < datetime.utcnow():
            return None, "This invitation has expired"
        
        return invite, "Valid invitation"
    
    @staticmethod
    def use_invite_token(token, password, first_name, last_name):
        """Use an invite token to create a new user"""
        invite, message = AuthService.validate_invite_token(token)
        
        if not invite:
            return None, message
        
        # Create user
        user, message = AuthService.create_user(
            email=invite.email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            role=invite.role
        )
        
        if not user:
            return None, message
        
        # Mark invite as used
        invite.used = True
        invite.used_at = datetime.utcnow()
        db.session.commit()
        
        return user, "Account created successfully"
    
    @staticmethod
    def change_password(user, current_password, new_password):
        """Change user's password"""
        # Verify current password
        if not bcrypt.check_password_hash(user.password_hash, current_password):
            return False, "Current password is incorrect"
        
        # Validate new password
        is_valid, message = AuthService.validate_password(new_password)
        if not is_valid:
            return False, message
        
        # Update password
        user.password_hash = bcrypt.generate_password_hash(new_password).decode('utf-8')
        db.session.commit()
        
        return True, "Password changed successfully"
    
    @staticmethod
    def toggle_user_status(user_id):
        """Toggle user active status (admin only)"""
        user = User.query.get(user_id)
        if not user:
            return False, "User not found"
        
        user.is_active = not user.is_active
        db.session.commit()
        
        status = "activated" if user.is_active else "deactivated"
        return True, f"User {status} successfully"