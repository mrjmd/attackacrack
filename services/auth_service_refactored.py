"""
AuthService - Refactored with Result Pattern
Handles user authentication, authorization, and invite management
"""

import re
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from flask_login import login_user as flask_login_user, logout_user as flask_logout_user
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.orm import Session

from crm_database import User, InviteToken, db
from services.common.result import Result, PagedResult

logger = logging.getLogger(__name__)


class AuthService:
    """Service for authentication and authorization using Result pattern"""
    
    def __init__(self, email_service=None, session: Optional[Session] = None):
        """
        Initialize with optional dependencies.
        
        Args:
            email_service: Email service for sending invites
            session: Database session
        """
        self.email_service = email_service
        self.session = session or db.session
    
    def validate_password(self, password: str) -> Result[str]:
        """
        Validate password meets requirements.
        
        Args:
            password: Password to validate
            
        Returns:
            Result[str]: Success with message or failure with error
        """
        if len(password) < 8:
            return Result.failure("Password must be at least 8 characters long", code="PASSWORD_TOO_SHORT")
        
        if not re.search(r'[A-Z]', password):
            return Result.failure("Password must contain at least one uppercase letter", code="PASSWORD_NO_UPPERCASE")
        
        if not re.search(r'[a-z]', password):
            return Result.failure("Password must contain at least one lowercase letter", code="PASSWORD_NO_LOWERCASE")
        
        if not re.search(r'\d', password):
            return Result.failure("Password must contain at least one number", code="PASSWORD_NO_NUMBER")
        
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            return Result.failure("Password must contain at least one special character", code="PASSWORD_NO_SPECIAL")
        
        return Result.success("Password is valid")
    
    def create_user(self, email: str, password: str, name: str, 
                   role: str = 'user', is_active: bool = True) -> Result[User]:
        """
        Create a new user.
        
        Args:
            email: User email
            password: User password
            name: User name
            role: User role (admin/user)
            is_active: Whether user is active
            
        Returns:
            Result[User]: Success with user or failure with error
        """
        # Validate password
        password_result = self.validate_password(password)
        if password_result.is_failure:
            return Result.failure(password_result.error, code=password_result.error_code)
        
        # Check if user exists
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            return Result.failure("User with this email already exists", code="USER_EXISTS")
        
        # Create user
        user = User(
            email=email,
            password_hash=generate_password_hash(password),
            name=name,
            role=role,
            is_active=is_active,
            created_at=datetime.utcnow()
        )
        
        try:
            self.session.add(user)
            self.session.commit()
            logger.info(f"Created user: {email}")
            return Result.success(user, metadata={"created_at": datetime.utcnow()})
        except Exception as e:
            self.session.rollback()
            logger.error(f"Failed to create user: {str(e)}")
            return Result.failure(f"Failed to create user: {str(e)}", code="DATABASE_ERROR")
    
    def authenticate_user(self, email: str, password: str) -> Result[User]:
        """
        Authenticate a user.
        
        Args:
            email: User email
            password: User password
            
        Returns:
            Result[User]: Success with user or failure with error
        """
        user = User.query.filter_by(email=email).first()
        
        if not user:
            return Result.failure("Invalid email or password", code="INVALID_CREDENTIALS")
        
        if not user.is_active:
            return Result.failure("Account is deactivated", code="ACCOUNT_DEACTIVATED")
        
        if not check_password_hash(user.password_hash, password):
            return Result.failure("Invalid email or password", code="INVALID_CREDENTIALS")
        
        # Update last login
        user.last_login = datetime.utcnow()
        self.session.commit()
        
        return Result.success(user, metadata={"last_login": user.last_login})
    
    def login_user(self, user: User, remember: bool = False) -> Result[bool]:
        """
        Log in a user using Flask-Login.
        
        Args:
            user: User to log in
            remember: Whether to remember the user
            
        Returns:
            Result[bool]: Success with True or failure
        """
        try:
            success = flask_login_user(user, remember=remember)
            if success:
                return Result.success(True)
            return Result.failure("Failed to log in user", code="LOGIN_FAILED")
        except Exception as e:
            return Result.failure(f"Login error: {str(e)}", code="LOGIN_ERROR")
    
    def logout_user(self) -> Result[bool]:
        """
        Log out the current user.
        
        Returns:
            Result[bool]: Success with True
        """
        flask_logout_user()
        return Result.success(True)
    
    def get_user_by_id(self, user_id: int) -> Result[User]:
        """
        Get user by ID.
        
        Args:
            user_id: User ID
            
        Returns:
            Result[User]: Success with user or failure
        """
        user = User.query.get(user_id)
        if user:
            return Result.success(user)
        return Result.failure(f"User not found: {user_id}", code="USER_NOT_FOUND")
    
    def get_user_by_email(self, email: str) -> Result[User]:
        """
        Get user by email.
        
        Args:
            email: User email
            
        Returns:
            Result[User]: Success with user or failure
        """
        user = User.query.filter_by(email=email).first()
        if user:
            return Result.success(user)
        return Result.failure(f"User not found: {email}", code="USER_NOT_FOUND")
    
    def get_all_users(self, page: int = 1, per_page: int = 50) -> PagedResult[List[User]]:
        """
        Get all users with pagination.
        
        Args:
            page: Page number
            per_page: Items per page
            
        Returns:
            PagedResult[List[User]]: Paginated users
        """
        try:
            paginated = User.query.paginate(page=page, per_page=per_page, error_out=False)
            
            return PagedResult.paginated(
                data=paginated.items,
                total=paginated.total,
                page=page,
                per_page=per_page
            )
        except Exception as e:
            return PagedResult.failure(f"Failed to get users: {str(e)}", code="DATABASE_ERROR")
    
    def update_user(self, user_id: int, **kwargs) -> Result[User]:
        """
        Update user attributes.
        
        Args:
            user_id: User ID
            **kwargs: Attributes to update
            
        Returns:
            Result[User]: Success with updated user or failure
        """
        user_result = self.get_user_by_id(user_id)
        if user_result.is_failure:
            return user_result
        
        user = user_result.data
        
        # Update allowed fields
        allowed_fields = ['name', 'email', 'role', 'is_active']
        for field, value in kwargs.items():
            if field in allowed_fields:
                setattr(user, field, value)
        
        try:
            self.session.commit()
            return Result.success(user)
        except Exception as e:
            self.session.rollback()
            return Result.failure(f"Failed to update user: {str(e)}", code="UPDATE_FAILED")
    
    def change_password(self, user_id: int, old_password: str, new_password: str) -> Result[bool]:
        """
        Change user password.
        
        Args:
            user_id: User ID
            old_password: Current password
            new_password: New password
            
        Returns:
            Result[bool]: Success or failure
        """
        user_result = self.get_user_by_id(user_id)
        if user_result.is_failure:
            return Result.failure(user_result.error, code=user_result.error_code)
        
        user = user_result.data
        
        # Verify old password
        if not check_password_hash(user.password_hash, old_password):
            return Result.failure("Invalid current password", code="INVALID_PASSWORD")
        
        # Validate new password
        password_result = self.validate_password(new_password)
        if password_result.is_failure:
            return Result.failure(password_result.error, code=password_result.error_code)
        
        # Update password
        user.password_hash = generate_password_hash(new_password)
        
        try:
            self.session.commit()
            return Result.success(True)
        except Exception as e:
            self.session.rollback()
            return Result.failure(f"Failed to change password: {str(e)}", code="UPDATE_FAILED")
    
    def create_invite(self, email: str, role: str = 'user', 
                     invited_by_id: Optional[int] = None) -> Result[InviteToken]:
        """
        Create an invite token.
        
        Args:
            email: Email to invite
            role: Role for invited user
            invited_by_id: ID of user creating invite
            
        Returns:
            Result[InviteToken]: Success with token or failure
        """
        # Check if user already exists
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            return Result.failure("User with this email already exists", code="USER_EXISTS")
        
        # Check for existing invite
        existing_invite = InviteToken.query.filter_by(
            email=email,
            used=False
        ).first()
        
        if existing_invite:
            if existing_invite.expires_at > datetime.utcnow():
                return Result.failure(
                    "Invite already sent to this email",
                    code="INVITE_EXISTS",
                    metadata={"expires_at": existing_invite.expires_at}
                )
            else:
                # Delete expired invite
                self.session.delete(existing_invite)
        
        # Create new invite
        invite = InviteToken(
            email=email,
            role=role,
            invited_by_id=invited_by_id,
            expires_at=datetime.utcnow() + timedelta(days=7)
        )
        
        try:
            self.session.add(invite)
            self.session.commit()
            logger.info(f"Created invite for: {email}")
            return Result.success(invite, metadata={"expires_at": invite.expires_at})
        except Exception as e:
            self.session.rollback()
            logger.error(f"Failed to create invite: {str(e)}")
            return Result.failure(f"Failed to create invite: {str(e)}", code="DATABASE_ERROR")
    
    def send_invite_email(self, invite: InviteToken, base_url: str) -> Result[bool]:
        """
        Send invite email.
        
        Args:
            invite: Invite token
            base_url: Base URL for invite link
            
        Returns:
            Result[bool]: Success or failure
        """
        if not self.email_service:
            return Result.failure("Email service not configured", code="EMAIL_NOT_CONFIGURED")
        
        invite_url = f"{base_url}/auth/register?token={invite.token}"
        
        try:
            self.email_service.send_invite(
                to_email=invite.email,
                invite_url=invite_url,
                role=invite.role
            )
            return Result.success(True)
        except Exception as e:
            logger.error(f"Failed to send invite email: {str(e)}")
            return Result.failure(f"Failed to send email: {str(e)}", code="EMAIL_SEND_FAILED")
    
    def validate_invite(self, token: str) -> Result[InviteToken]:
        """
        Validate an invite token.
        
        Args:
            token: Invite token
            
        Returns:
            Result[InviteToken]: Success with token or failure
        """
        invite = InviteToken.query.filter_by(token=token).first()
        
        if not invite:
            return Result.failure("Invalid invite token", code="INVALID_TOKEN")
        
        if invite.used:
            return Result.failure("Invite has already been used", code="TOKEN_USED")
        
        if invite.expires_at < datetime.utcnow():
            return Result.failure("Invite has expired", code="TOKEN_EXPIRED")
        
        return Result.success(invite)
    
    def use_invite(self, token: str, password: str, name: str) -> Result[User]:
        """
        Use an invite to create a user.
        
        Args:
            token: Invite token
            password: User password
            name: User name
            
        Returns:
            Result[User]: Success with created user or failure
        """
        # Validate invite
        invite_result = self.validate_invite(token)
        if invite_result.is_failure:
            return Result.failure(invite_result.error, code=invite_result.error_code)
        
        invite = invite_result.data
        
        # Create user
        user_result = self.create_user(
            email=invite.email,
            password=password,
            name=name,
            role=invite.role
        )
        
        if user_result.is_success:
            # Mark invite as used
            invite.used = True
            invite.used_at = datetime.utcnow()
            invite.used_by_id = user_result.data.id
            self.session.commit()
        
        return user_result
    
    def toggle_user_status(self, user_id: int) -> Result[User]:
        """
        Toggle user active status.
        
        Args:
            user_id: User ID
            
        Returns:
            Result[User]: Success with updated user or failure
        """
        user_result = self.get_user_by_id(user_id)
        if user_result.is_failure:
            return user_result
        
        user = user_result.data
        user.is_active = not user.is_active
        
        try:
            self.session.commit()
            logger.info(f"Toggled user status for {user.email}: is_active={user.is_active}")
            return Result.success(user, metadata={"is_active": user.is_active})
        except Exception as e:
            self.session.rollback()
            return Result.failure(f"Failed to toggle user status: {str(e)}", code="UPDATE_FAILED")
    
    def delete_user(self, user_id: int) -> Result[bool]:
        """
        Delete a user.
        
        Args:
            user_id: User ID
            
        Returns:
            Result[bool]: Success or failure
        """
        user_result = self.get_user_by_id(user_id)
        if user_result.is_failure:
            return Result.failure(user_result.error, code=user_result.error_code)
        
        user = user_result.data
        
        try:
            self.session.delete(user)
            self.session.commit()
            logger.info(f"Deleted user: {user.email}")
            return Result.success(True)
        except Exception as e:
            self.session.rollback()
            logger.error(f"Failed to delete user: {str(e)}")
            return Result.failure(f"Failed to delete user: {str(e)}", code="DELETE_FAILED")