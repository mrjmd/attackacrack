#!/usr/bin/env python3
"""
Data normalization utilities for existing contacts and properties.

This module provides commands to normalize and reconcile existing data
in the database, ensuring consistency with PropertyRadar import standards.
"""

import click
from flask import current_app
from flask.cli import with_appcontext
from sqlalchemy import func
from crm_database import db, Contact, Property


def normalize_phone_number(phone):
    """Normalize phone number to E.164 format."""
    if not phone:
        return None
    
    # Remove all non-digit characters
    digits = ''.join(filter(str.isdigit, phone))
    
    # Add country code if missing
    if len(digits) == 10:
        digits = '1' + digits
    elif len(digits) == 11 and digits[0] == '1':
        pass  # Already has country code
    else:
        return None  # Invalid format
    
    return '+' + digits


def normalize_address(address):
    """Normalize address string."""
    if not address:
        return None
    
    # Basic normalization
    address = ' '.join(address.split())  # Remove extra spaces
    address = address.strip()
    
    return address if address else None


@click.command('normalize-contacts')
@click.option('--dry-run', is_flag=True, help='Preview changes without saving')
@with_appcontext
def normalize_contacts_command(dry_run):
    """Normalize existing contact data."""
    click.echo("Normalizing contact data...")
    
    contacts = Contact.query.all()
    normalized_count = 0
    
    for contact in contacts:
        changed = False
        
        # Normalize phone
        if contact.phone:
            normalized = normalize_phone_number(contact.phone)
            if normalized != contact.phone:
                if not dry_run:
                    contact.phone = normalized
                changed = True
                click.echo(f"  Phone: {contact.phone} -> {normalized}")
        
        # Normalize address
        if contact.address:
            normalized = normalize_address(contact.address)
            if normalized != contact.address:
                if not dry_run:
                    contact.address = normalized
                changed = True
                click.echo(f"  Address: {contact.address} -> {normalized}")
        
        if changed:
            normalized_count += 1
    
    if not dry_run:
        db.session.commit()
        click.echo(f"Normalized {normalized_count} contacts")
    else:
        click.echo(f"Would normalize {normalized_count} contacts (dry run)")


@click.command('normalize-properties')
@click.option('--dry-run', is_flag=True, help='Preview changes without saving')
@with_appcontext
def normalize_properties_command(dry_run):
    """Normalize existing property data."""
    click.echo("Normalizing property data...")
    
    properties = Property.query.all()
    normalized_count = 0
    
    for property in properties:
        changed = False
        
        # Normalize address
        if property.address:
            normalized = normalize_address(property.address)
            if normalized != property.address:
                if not dry_run:
                    property.address = normalized
                changed = True
                click.echo(f"  Address: {property.address} -> {normalized}")
        
        if changed:
            normalized_count += 1
    
    if not dry_run:
        db.session.commit()
        click.echo(f"Normalized {normalized_count} properties")
    else:
        click.echo(f"Would normalize {normalized_count} properties (dry run)")


@click.command('reconcile-duplicates')
@click.option('--dry-run', is_flag=True, help='Preview changes without saving')
@with_appcontext
def reconcile_duplicates_command(dry_run):
    """Find and reconcile duplicate contacts."""
    click.echo("Finding duplicate contacts...")
    
    # Find contacts with duplicate phone numbers
    duplicates = db.session.query(
        Contact.phone, 
        func.count(Contact.id).label('count')
    ).group_by(Contact.phone).having(func.count(Contact.id) > 1).all()
    
    if not duplicates:
        click.echo("No duplicate contacts found")
        return
    
    click.echo(f"Found {len(duplicates)} duplicate phone numbers")
    
    for phone, count in duplicates:
        if not phone:
            continue
            
        contacts = Contact.query.filter_by(phone=phone).order_by(Contact.created_at).all()
        primary = contacts[0]  # Keep the oldest
        
        click.echo(f"  Phone {phone}: {count} duplicates, keeping contact #{primary.id}")
        
        if not dry_run:
            # Merge data from duplicates into primary
            for duplicate in contacts[1:]:
                # Update primary with any missing data
                if not primary.email and duplicate.email:
                    primary.email = duplicate.email
                if not primary.name and duplicate.name:
                    primary.name = duplicate.name
                if not primary.address and duplicate.address:
                    primary.address = duplicate.address
                
                # Delete duplicate
                db.session.delete(duplicate)
    
    if not dry_run:
        db.session.commit()
        click.echo("Duplicates reconciled")
    else:
        click.echo("Duplicates found (dry run)")


def register_commands(app):
    """Register normalization commands with Flask app."""
    app.cli.add_command(normalize_contacts_command)
    app.cli.add_command(normalize_properties_command)
    app.cli.add_command(reconcile_duplicates_command)