#!/usr/bin/env python
"""
Fix password hash format issues in local database.

This script converts password hashes from scrypt format (werkzeug) to bcrypt format,
or allows resetting passwords for users who cannot log in due to hash format issues.
"""

import click
from flask import Flask
from flask.cli import with_appcontext
from flask_bcrypt import generate_password_hash
from extensions import db
from crm_database import User
import sys


@click.command()
@click.option('--email', help='Email of user to fix (if not provided, fixes all users)')
@click.option('--reset-password', help='New password to set (prompts if not provided)')
@click.option('--list-users', is_flag=True, help='List all users and their hash formats')
@with_appcontext
def fix_password_hashes(email, reset_password, list_users):
    """Fix password hash format issues for local development."""
    
    if list_users:
        users = User.query.all()
        click.echo("\nCurrent users in database:")
        click.echo("-" * 60)
        for user in users:
            hash_format = "unknown"
            if user.password_hash:
                if user.password_hash.startswith('$2b$') or user.password_hash.startswith('$2a$'):
                    hash_format = "bcrypt"
                elif user.password_hash.startswith('scrypt:'):
                    hash_format = "scrypt (needs fix)"
                elif user.password_hash.startswith('pbkdf2:'):
                    hash_format = "pbkdf2 (needs fix)"
            click.echo(f"ID: {user.id:3} | Email: {user.email:30} | Role: {user.role:10} | Hash: {hash_format}")
        click.echo("-" * 60)
        return
    
    # If email provided, fix specific user
    if email:
        user = User.query.filter_by(email=email).first()
        if not user:
            click.echo(f"Error: User with email '{email}' not found.")
            sys.exit(1)
        users_to_fix = [user]
    else:
        # Fix all users with non-bcrypt hashes
        users = User.query.all()
        users_to_fix = []
        for user in users:
            if user.password_hash and not (
                user.password_hash.startswith('$2b$') or 
                user.password_hash.startswith('$2a$')
            ):
                users_to_fix.append(user)
        
        if not users_to_fix:
            click.echo("No users need password hash fixes.")
            return
    
    click.echo(f"\nFound {len(users_to_fix)} user(s) needing password hash fixes:")
    for user in users_to_fix:
        click.echo(f"  - {user.email} ({user.role})")
    
    if not reset_password:
        if not click.confirm("\nDo you want to reset passwords for these users?"):
            click.echo("Aborted.")
            return
        
        reset_password = click.prompt(
            "Enter new password for all users (or press Enter for default 'admin123!')",
            default="admin123!",
            hide_input=True,
            confirmation_prompt=True
        )
    
    # Update password hashes
    for user in users_to_fix:
        try:
            # Generate bcrypt hash
            new_hash = generate_password_hash(reset_password)
            
            # Handle both bytes and string returns from generate_password_hash
            if hasattr(new_hash, 'decode'):
                new_hash = new_hash.decode('utf-8')
            
            user.password_hash = new_hash
            click.echo(f"✓ Updated password hash for {user.email}")
            
        except Exception as e:
            click.echo(f"✗ Failed to update {user.email}: {str(e)}")
            db.session.rollback()
            sys.exit(1)
    
    try:
        db.session.commit()
        click.echo(f"\n✅ Successfully updated {len(users_to_fix)} user(s)")
        click.echo(f"\n📝 You can now log in with:")
        for user in users_to_fix:
            click.echo(f"   Email: {user.email}")
        click.echo(f"   Password: {reset_password}")
        
    except Exception as e:
        db.session.rollback()
        click.echo(f"✗ Failed to commit changes: {str(e)}")
        sys.exit(1)


@click.command()
@click.option('--email', default='admin@attackacrack.com', help='Admin email address')
@click.option('--password', help='Admin password (prompts if not provided)')
@click.option('--first-name', default='Admin', help='First name')
@click.option('--last-name', default='User', help='Last name')
@with_appcontext
def create_or_reset_admin(email, password, first_name, last_name):
    """Create or reset the admin user for local development."""
    
    # Check if admin exists
    admin = User.query.filter_by(email=email).first()
    
    if admin:
        click.echo(f"Admin user '{email}' already exists.")
        
        if not password:
            if not click.confirm("Do you want to reset the password?"):
                click.echo("Aborted.")
                return
            
            password = click.prompt(
                "Enter new password (or press Enter for default 'admin123!')",
                default="admin123!",
                hide_input=True,
                confirmation_prompt=True
            )
        
        # Update password
        try:
            new_hash = generate_password_hash(password)
            if hasattr(new_hash, 'decode'):
                new_hash = new_hash.decode('utf-8')
            
            admin.password_hash = new_hash
            admin.first_name = first_name
            admin.last_name = last_name
            admin.is_active = True
            
            db.session.commit()
            click.echo(f"✅ Password reset successfully for {email}")
            
        except Exception as e:
            db.session.rollback()
            click.echo(f"✗ Failed to reset password: {str(e)}")
            sys.exit(1)
            
    else:
        # Create new admin
        if not password:
            password = click.prompt(
                "Enter password for new admin (or press Enter for default 'admin123!')",
                default="admin123!",
                hide_input=True,
                confirmation_prompt=True
            )
        
        try:
            from app import current_app
            auth_service = current_app.services.get('auth')
            
            result = auth_service.create_user(
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
                role='admin',
                is_active=True
            )
            
            if result.is_success:
                click.echo(f"✅ Admin user created successfully: {email}")
            else:
                click.echo(f"✗ Failed to create admin: {result.error}")
                sys.exit(1)
                
        except Exception as e:
            click.echo(f"✗ Error creating admin: {str(e)}")
            sys.exit(1)
    
    click.echo(f"\n📝 You can now log in with:")
    click.echo(f"   Email: {email}")
    click.echo(f"   Password: {password}")


def register_commands(app):
    """Register password fix commands with Flask app."""
    app.cli.add_command(fix_password_hashes, name='fix-passwords')
    app.cli.add_command(create_or_reset_admin, name='reset-admin')


if __name__ == '__main__':
    # Allow running as standalone script
    from app import create_app
    app = create_app()
    
    with app.app_context():
        # List users by default if run directly
        ctx = click.Context(fix_password_hashes)
        ctx.invoke(fix_password_hashes, list_users=True)