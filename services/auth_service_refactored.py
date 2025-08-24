"""
AuthService - Refactored with Result Pattern
Handles user authentication, authorization, and invite management
"""

import re
import uuid
import logging
from datetime import datetime, timedelta
from utils.datetime_utils import utc_now
from typing import Optional, List, Dict, Any
from flask_login import login_user as flask_login_user, logout_user as flask_logout_user
from flask_bcrypt import generate_password_hash, check_password_hash
# Model and Session imports removed - using repositories only
from services.common.result import Result, PagedResult
from repositories.user_repository import UserRepository
from repositories.invite_token_repository import InviteTokenRepository
from repositories.base_repository import PaginationParams

logger = logging.getLogger(__name__)


class AuthService:
    """Service for authentication and authorization using Result pattern"""
    
    def __init__(self, email_service=None,
                 user_repository: Optional[UserRepository] = None,
                 invite_repository: Optional[InviteTokenRepository] = None):
        """
        Initialize with optional dependencies.
        
        Args:
            email_service: Email service for sending invites
            user_repository: User repository for data access
            invite_repository: Invite token repository for data access
        """
        self.email_service = email_service
        
        # Repositories must be injected
        self.user_repository = user_repository
        self.invite_repository = invite_repository
        
        if not self.user_repository or not self.invite_repository:
            raise ValueError("User and Invite repositories must be provided via dependency injection")
    
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
    
    def create_user(self, email: str, password: str, first_name: str, last_name: str,
                   role: str = 'marketer', is_active: bool = True) -> Result[Dict[str, Any]]:
        """
        Create a new user.
        
        Args:
            email: User email
            password: User password
            first_name: User first name
            last_name: User last name
            role: User role (admin/marketer)
            is_active: Whether user is active
            
        Returns:
            Result[Dict[str, Any]]: Success with user or failure with error
        """
        # Validate password
        password_result = self.validate_password(password)
        if password_result.is_failure:
            return Result.failure(password_result.error, code=password_result.error_code)
        
        # Check if user exists using repository
        existing_user = self.user_repository.find_by_email(email)
        if existing_user:
            return Result.failure("User with this email already exists", code="USER_EXISTS")
        
        try:
            # Create user using repository  
            password_hash = generate_password_hash(password)
            if hasattr(password_hash, 'decode'):
                password_hash = password_hash.decode('utf-8')
            user = self.user_repository.create(
                email=email,
                password_hash=password_hash,
                first_name=first_name,
                last_name=last_name,
                role=role,
                is_active=is_active,
                created_at=utc_now()
            )
            
            self.user_repository.commit()
            logger.info(f"Created user: {email}")
            return Result.success(user, metadata={"created_at": utc_now()})
        except Exception as e:
            self.user_repository.rollback()
            logger.error(f"Failed to create user: {str(e)}")
            return Result.failure(f"Failed to create user: {str(e)}", code="DATABASE_ERROR")
    
    def authenticate_user(self, email: str, password: str) -> Result[Dict[str, Any]]:
        """
        Authenticate a user.
        
        Args:
            email: User email
            password: User password
            
        Returns:
            Result[Dict[str, Any]]: Success with user or failure with error
        """
        # Find user using repository
        user = self.user_repository.find_by_email(email)
        
        if not user:
            return Result.failure("Invalid email or password", code="INVALID_CREDENTIALS")
        
        if not user.is_active:
            return Result.failure("Account is deactivated", code="ACCOUNT_DEACTIVATED")
        
        if not check_password_hash(user.password_hash, password):
            return Result.failure("Invalid email or password", code="INVALID_CREDENTIALS")
        
        # Update last login using repository
        login_time = utc_now()
        self.user_repository.update_last_login(user.id, login_time)
        self.user_repository.commit()
        
        return Result.success(user, metadata={"last_login": login_time})
    
    def login_user(self, user: Dict[str, Any], remember: bool = False) -> Result[bool]:
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
    
    def get_user_by_id(self, user_id: int) -> Result[Dict[str, Any]]:
        """
        Get user by ID.
        
        Args:
            user_id: User ID
            
        Returns:
            Result[Dict[str, Any]]: Success with user or failure
        """
        user = self.user_repository.get_by_id(user_id)
        if user:
            return Result.success(user)
        return Result.failure(f"User not found: {user_id}", code="USER_NOT_FOUND")
    
    def get_user_by_email(self, email: str) -> Result[Dict[str, Any]]:
        """
        Get user by email.
        
        Args:
            email: User email
            
        Returns:
            Result[Dict[str, Any]]: Success with user or failure
        """
        user = self.user_repository.find_by_email(email)
        if user:
            return Result.success(user)
        return Result.failure(f"User not found: {email}", code="USER_NOT_FOUND")
    
    def get_all_users(self, page: int = 1, per_page: int = 50) -> PagedResult[List[Dict[str, Any]]]:
        """
        Get all users with pagination.
        
        Args:
            page: Page number
            per_page: Items per page
            
        Returns:
            PagedResult[List[Dict[str, Any]]]: Paginated users
        """
        try:
            pagination_params = PaginationParams(page=page, per_page=per_page)
            paginated = self.user_repository.get_paginated(pagination_params)
            
            return PagedResult.paginated(
                data=paginated.items,
                total=paginated.total,
                page=page,
                per_page=per_page
            )
        except Exception as e:
            return PagedResult.failure(f"Failed to get users: {str(e)}", code="DATABASE_ERROR")
    
    def update_user(self, user_id: int, **kwargs) -> Result[Dict[str, Any]]:
        """
        Update user attributes.
        
        Args:
            user_id: User ID
            **kwargs: Attributes to update
            
        Returns:
            Result[Dict[str, Any]]: Success with updated user or failure
        """
        user_result = self.get_user_by_id(user_id)
        if user_result.is_failure:
            return user_result
        
        user = user_result.data
        
        # Update allowed fields
        allowed_fields = ['first_name', 'last_name', 'email', 'role', 'is_active']
        update_data = {}
        for field, value in kwargs.items():
            if field in allowed_fields:
                update_data[field] = value
        
        if not update_data:
            return Result.failure("No valid fields to update", code="NO_UPDATES")
        
        try:
            # Use repository to update user
            updated_user = self.user_repository.update(user_id, **update_data)
            self.user_repository.commit()
            return Result.success(updated_user)
        except Exception as e:
            self.user_repository.rollback()
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
        
        # Update password using repository
        new_password_hash = generate_password_hash(new_password)
        if hasattr(new_password_hash, 'decode'):
            new_password_hash = new_password_hash.decode('utf-8')
        
        try:
            self.user_repository.update_by_id(user_id, password_hash=new_password_hash)
            self.user_repository.commit()
            return Result.success(True)
        except Exception as e:
            self.user_repository.rollback()
            return Result.failure(f"Failed to change password: {str(e)}", code="UPDATE_FAILED")
    
    def create_invite(self, email: str, role: str = 'marketer', 
                     invited_by_id: Optional[int] = None) -> Result[Dict[str, Any]]:
        """
        Create an invite token.
        
        Args:
            email: Email to invite
            role: Role for invited user
            invited_by_id: ID of user creating invite
            
        Returns:
            Result[Dict[str, Any]]: Success with token or failure
        """
        # Check if user already exists using repository
        existing_user = self.user_repository.find_by_email(email)
        if existing_user:
            return Result.failure("User with this email already exists", code="USER_EXISTS")
        
        # Check for existing valid invite using repository
        existing_invite = self.invite_repository.find_valid_invite_by_email(email)
        
        if existing_invite:
            return Result.failure(
                "Invite already sent to this email",
                code="INVITE_EXISTS",
                metadata={"expires_at": existing_invite.expires_at}
            )
        
        try:
            # Generate unique token
            token = str(uuid.uuid4())
            
            # Create new invite using repository
            invite = self.invite_repository.create(
                email=email,
                token=token,
                role=role,
                created_by_id=invited_by_id,
                expires_at=utc_now() + timedelta(days=7)
            )
            
            self.invite_repository.commit()
            logger.info(f"Created invite for: {email}")
            return Result.success(invite, metadata={"expires_at": invite.expires_at})
        except Exception as e:
            self.invite_repository.rollback()
            logger.error(f"Failed to create invite: {str(e)}")
            return Result.failure(f"Failed to create invite: {str(e)}", code="DATABASE_ERROR")
    
    def send_invite_email(self, invite: Dict[str, Any], base_url: str) -> Result[bool]:
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
    
    def validate_invite(self, token: str) -> Result[Dict[str, Any]]:
        """
        Validate an invite token.
        
        Args:
            token: Invite token
            
        Returns:
            Result[Dict[str, Any]]: Success with token or failure
        """
        invite = self.invite_repository.find_by_token(token)
        
        if not invite:
            return Result.failure("Invalid invite token", code="INVALID_TOKEN")
        
        if invite.used:
            return Result.failure("Invite has already been used", code="TOKEN_USED")
        
        if invite.expires_at < utc_now():
            return Result.failure("Invite has expired", code="TOKEN_EXPIRED")
        
        return Result.success(invite)
    
    def use_invite(self, token: str, password: str, first_name: str, last_name: str) -> Result[Dict[str, Any]]:
        """
        Use an invite to create a user.
        
        Args:
            token: Invite token
            password: User password
            first_name: User first name
            last_name: User last name
            
        Returns:
            Result[Dict[str, Any]]: Success with created user or failure
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
            first_name=first_name,
            last_name=last_name,
            role=invite.role
        )
        
        if user_result.is_success:
            # Mark invite as used using repository
            self.invite_repository.mark_as_used(
                invite.id,
                utc_now()
            )
            self.invite_repository.commit()
        
        return user_result
    
    def toggle_user_status(self, user_id: int) -> Result[Dict[str, Any]]:
        """
        Toggle user active status.
        
        Args:
            user_id: User ID
            
        Returns:
            Result[Dict[str, Any]]: Success with updated user or failure
        """
        user_result = self.get_user_by_id(user_id)
        if user_result.is_failure:
            return user_result
        
        user = user_result.data
        new_status = not user.is_active
        
        try:
            # Use repository to update status
            updated_user = self.user_repository.update_by_id(user_id, is_active=new_status)
            self.user_repository.commit()
            logger.info(f"Toggled user status for {user.email}: is_active={new_status}")
            return Result.success(updated_user, metadata={"is_active": new_status})
        except Exception as e:
            self.user_repository.rollback()
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
            # Use repository to delete user
            self.user_repository.delete(user_id)
            self.user_repository.commit()
            logger.info(f"Deleted user: {user.email}")
            return Result.success(True)
        except Exception as e:
            self.user_repository.rollback()
            logger.error(f"Failed to delete user: {str(e)}")
            return Result.failure(f"Failed to delete user: {str(e)}", code="DELETE_FAILED")
    
    def get_pending_invites(self, page: int = 1, per_page: int = 50) -> PagedResult[List[Dict[str, Any]]]:
        """
        Get all pending invites with pagination.
        
        Args:
            page: Page number
            per_page: Items per page
            
        Returns:
            PagedResult[List[Dict[str, Any]]]: Paginated pending invites
        """
        try:
            # Get invites that are not used and not expired
            current_time = utc_now()
            pagination_params = PaginationParams(page=page, per_page=per_page)
            
            # Use repository to get pending invites
            paginated = self.invite_repository.get_pending_invites(pagination_params, current_time)
            
            return PagedResult.paginated(
                data=paginated.items,
                total=paginated.total,
                page=page,
                per_page=per_page
            )
        except Exception as e:
            return PagedResult.failure(f"Failed to get pending invites: {str(e)}", code="DATABASE_ERROR")