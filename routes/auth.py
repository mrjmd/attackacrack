# routes/auth.py

from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_required, current_user, logout_user
from functools import wraps

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')


def admin_required(f):
    """Decorator to require admin role"""
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if not current_user.is_admin:
            flash('Admin access required', 'error')
            return redirect(url_for('main.dashboard'))
        return f(*args, **kwargs)
    return decorated_function


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Login page"""
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        remember = request.form.get('remember', False)
        
        # Get auth service from registry
        auth_service = current_app.services.get('auth')
        
        # Authenticate user and handle Result
        auth_result = auth_service.authenticate_user(email, password)
        
        if auth_result.is_success:
            user = auth_result.data
            # Login user with Flask-Login
            login_result = auth_service.login_user(user, remember=remember)
            
            if login_result.is_success:
                next_page = request.args.get('next')
                if next_page:
                    return redirect(next_page)
                return redirect(url_for('main.dashboard'))
            else:
                flash(login_result.error or 'Failed to log in', 'error')
        else:
            flash(auth_result.error or 'Invalid credentials', 'error')
    
    return render_template('auth/login.html')


@auth_bp.route('/logout')
@login_required
def logout():
    """Logout current user"""
    # Get auth service from registry
    auth_service = current_app.services.get('auth')
    auth_service.logout_user()
    flash('You have been logged out', 'success')
    return redirect(url_for('auth.login'))


@auth_bp.route('/invite', methods=['GET', 'POST'])
@admin_required
def invite_user():
    """Invite a new user (admin only)"""
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        role = request.form.get('role', 'marketer')
        
        if role not in ['admin', 'marketer']:
            flash('Invalid role selected', 'error')
            return render_template('auth/invite.html')
        
        # Get auth service from registry
        auth_service = current_app.services.get('auth')
        
        # Create invite
        invite_result = auth_service.create_invite(email, role, invited_by_id=current_user.id)
        
        if invite_result.is_success:
            invite = invite_result.data
            # Send invite email
            base_url = request.url_root.rstrip('/')
            email_result = auth_service.send_invite_email(invite, base_url)
            
            if email_result.is_success:
                flash(f'Invitation sent to {email}', 'success')
            else:
                flash(f'Invitation created but email failed: {email_result.error}', 'warning')
                flash(f'Share this link: {base_url}/auth/accept-invite/{invite.token}', 'info')
        else:
            flash(invite_result.error or 'Failed to create invite', 'error')
    
    return render_template('auth/invite.html')


@auth_bp.route('/accept-invite/<token>', methods=['GET', 'POST'])
def accept_invite(token):
    """Accept an invitation and create account"""
    if current_user.is_authenticated:
        logout_user()
    
    # Get auth service from registry
    auth_service = current_app.services.get('auth')
    
    # Validate token
    invite_result = auth_service.validate_invite(token)
    
    if not invite_result.is_success:
        flash(invite_result.error or 'Invalid or expired invite', 'error')
        return redirect(url_for('auth.login'))
    
    invite = invite_result.data
    
    if request.method == 'POST':
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        first_name = request.form.get('first_name', '').strip()
        last_name = request.form.get('last_name', '').strip()
        
        # Validate form
        if not all([password, confirm_password, first_name, last_name]):
            flash('All fields are required', 'error')
        elif password != confirm_password:
            flash('Passwords do not match', 'error')
        else:
            # Create user
            user_result = auth_service.use_invite(token, password, first_name, last_name)
            
            if user_result.is_success:
                flash('Account created successfully! Please log in.', 'success')
                return redirect(url_for('auth.login'))
            else:
                flash(user_result.error or 'Failed to create account', 'error')
    
    return render_template('auth/accept_invite.html', invite=invite)


@auth_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    """User profile page"""
    if request.method == 'POST':
        action = request.form.get('action')
        
        # Get auth service from registry
        auth_service = current_app.services.get('auth')
        
        if action == 'update_profile':
            # Update profile information
            first_name = request.form.get('first_name', current_user.first_name)
            last_name = request.form.get('last_name', current_user.last_name)
            
            # Use the generic update_user method
            update_result = auth_service.update_user(current_user.id, 
                                                   first_name=first_name, 
                                                   last_name=last_name)
            
            if update_result.is_success:
                flash('Profile updated successfully', 'success')
            else:
                flash(update_result.error or 'Failed to update profile', 'error')
            
        elif action == 'change_password':
            # Change password
            current_password = request.form.get('current_password', '')
            new_password = request.form.get('new_password', '')
            confirm_password = request.form.get('confirm_password', '')
            
            if new_password != confirm_password:
                flash('New passwords do not match', 'error')
            else:
                password_result = auth_service.change_password(current_user.id, current_password, new_password)
                
                if password_result.is_success:
                    flash('Password changed successfully', 'success')
                else:
                    flash(password_result.error or 'Failed to change password', 'error')
    
    return render_template('auth/profile.html', user=current_user)


@auth_bp.route('/users')
@admin_required
def manage_users():
    """User management page (admin only)"""
    auth_service = current_app.services.get('auth')
    
    # Get page from query params
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    
    # Get users with pagination
    users_result = auth_service.get_all_users(page=page, per_page=per_page)
    
    if users_result.is_success:
        users = users_result.data
    else:
        users = []
        flash('Failed to load users', 'error')
    
    # Get pending invites
    invites_result = auth_service.get_pending_invites()
    
    if invites_result.is_success:
        invites = invites_result.data
    else:
        invites = []
    
    # Create pagination object from PagedResult metadata
    pagination = None
    if users_result.is_success:
        pagination = {
            'total': users_result.total,
            'page': users_result.page,
            'per_page': users_result.per_page,
            'total_pages': users_result.total_pages,
            'has_prev': users_result.page > 1 if users_result.page else False,
            'has_next': users_result.page < users_result.total_pages if users_result.page and users_result.total_pages else False
        }
    
    return render_template('auth/manage_users.html', 
                         users=users, 
                         invites=invites,
                         pagination=pagination)


@auth_bp.route('/users/<int:user_id>/toggle-status', methods=['POST'])
@admin_required
def toggle_user_status(user_id):
    """Toggle user active status (admin only)"""
    if user_id == current_user.id:
        flash('You cannot deactivate your own account', 'error')
    else:
        # Get auth service from registry
        auth_service = current_app.services.get('auth')
        
        toggle_result = auth_service.toggle_user_status(user_id)
        
        if toggle_result.is_success:
            flash('User status updated successfully', 'success')
        else:
            flash(toggle_result.error or 'Failed to update user status', 'error')
    
    return redirect(url_for('auth.manage_users'))