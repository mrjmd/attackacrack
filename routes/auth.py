# routes/auth.py

from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_required, current_user, logout_user
from services.auth_service import AuthService
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
        
        user, message = AuthService.authenticate_user(email, password)
        
        if user:
            AuthService.login_user_session(user, remember=remember)
            next_page = request.args.get('next')
            if next_page:
                return redirect(next_page)
            return redirect(url_for('main.dashboard'))
        else:
            flash(message, 'error')
    
    return render_template('auth/login.html')


@auth_bp.route('/logout')
@login_required
def logout():
    """Logout current user"""
    AuthService.logout_user_session()
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
        
        # Create invite
        invite, message = AuthService.create_invite(email, role, current_user)
        
        if invite:
            # Send invite email
            base_url = request.url_root.rstrip('/')
            success, email_message = AuthService.send_invite_email(invite, base_url)
            
            if success:
                flash(f'Invitation sent to {email}', 'success')
            else:
                flash(f'Invitation created but email failed: {email_message}', 'warning')
                flash(f'Share this link: {base_url}/auth/accept-invite/{invite.token}', 'info')
        else:
            flash(message, 'error')
    
    return render_template('auth/invite.html')


@auth_bp.route('/accept-invite/<token>', methods=['GET', 'POST'])
def accept_invite(token):
    """Accept an invitation and create account"""
    if current_user.is_authenticated:
        logout_user()
    
    # Validate token
    invite, message = AuthService.validate_invite_token(token)
    
    if not invite:
        flash(message, 'error')
        return redirect(url_for('auth.login'))
    
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
            user, message = AuthService.use_invite_token(token, password, first_name, last_name)
            
            if user:
                flash('Account created successfully! Please log in.', 'success')
                return redirect(url_for('auth.login'))
            else:
                flash(message, 'error')
    
    return render_template('auth/accept_invite.html', invite=invite)


@auth_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    """User profile page"""
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'update_profile':
            # Update profile information
            first_name = request.form.get('first_name', current_user.first_name)
            last_name = request.form.get('last_name', current_user.last_name)
            success, message = AuthService.update_user_profile(current_user, first_name, last_name)
            flash(message, 'success' if success else 'error')
            
        elif action == 'change_password':
            # Change password
            current_password = request.form.get('current_password', '')
            new_password = request.form.get('new_password', '')
            confirm_password = request.form.get('confirm_password', '')
            
            if new_password != confirm_password:
                flash('New passwords do not match', 'error')
            else:
                success, message = AuthService.change_password(current_user, current_password, new_password)
                flash(message, 'success' if success else 'error')
    
    return render_template('auth/profile.html', user=current_user)


@auth_bp.route('/users')
@admin_required
def manage_users():
    """User management page (admin only)"""
    auth_service = current_app.services.get('auth')
    users = auth_service.get_all_users()
    invites = auth_service.get_pending_invites()
    return render_template('auth/manage_users.html', users=users, invites=invites)


@auth_bp.route('/users/<int:user_id>/toggle-status', methods=['POST'])
@admin_required
def toggle_user_status(user_id):
    """Toggle user active status (admin only)"""
    if user_id == current_user.id:
        flash('You cannot deactivate your own account', 'error')
    else:
        success, message = AuthService.toggle_user_status(user_id)
        flash(message, 'success' if success else 'error')
    
    return redirect(url_for('auth.manage_users'))