# commands.py

import click
from flask.cli import with_appcontext
from extensions import db
from services.auth_service_refactored import AuthService
from crm_database import User


@click.command()
@click.option('--email', prompt=True, help='Admin email address')
@click.option('--password', prompt=True, hide_input=True, confirmation_prompt=True, help='Admin password')
@click.option('--first-name', prompt=True, help='First name')
@click.option('--last-name', prompt=True, help='Last name')
@with_appcontext
def create_admin(email, password, first_name, last_name):
    """Create an admin user"""
    # Check if any admin already exists
    existing_admin = User.query.filter_by(role='admin').first()
    if existing_admin:
        click.echo('An admin user already exists. Use the web interface to invite more admins.')
        return
    
    # Create admin user
    user, message = AuthService.create_user(
        email=email,
        password=password,
        first_name=first_name,
        last_name=last_name,
        role='admin'
    )
    
    if user:
        click.echo(f'Admin user created successfully: {user.email}')
    else:
        click.echo(f'Failed to create admin: {message}')


def init_app(app):
    """Register commands with the Flask app"""
    app.cli.add_command(create_admin)
    
    # Register password fix commands
    from scripts.fix_password_hashes import register_commands as register_password_commands
    register_password_commands(app)
    
    # Register data normalization commands
    from scripts.normalize_existing_data import register_commands as register_normalization_commands
    register_normalization_commands(app)