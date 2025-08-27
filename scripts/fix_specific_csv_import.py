#!/usr/bin/env python
"""
Specific CSV Import Fix Script
Fixes incomplete CSV import records with production-safe, idempotent operations.
"""

import click
from flask import current_app
from flask.cli import with_appcontext
from datetime import datetime
from extensions import db
from crm_database import CSVImport
from repositories.csv_import_repository import CSVImportRepository
import logging

logger = logging.getLogger(__name__)


def register_commands(app):
    """Register specific CSV import fix commands with Flask app"""
    app.cli.add_command(fix_propertyradar_import)
    app.cli.add_command(verify_csv_import_integrity)


@click.command()
@click.option('--import-id', type=int, help='Specific import ID to fix (default: looks for PropertyRadar imports)')
@click.option('--dry-run', is_flag=True, help='Show what would be changed without making changes')
@click.option('--force', is_flag=True, help='Force update even if values already set')
@with_appcontext
def fix_propertyradar_import(import_id, dry_run, force):
    """
    Fix PropertyRadar CSV import with 826 records.
    
    This command:
    - Finds PropertyRadar import (by ID or filename)
    - Sets total_rows=826, successful_imports=826, failed_imports=0
    - Is idempotent (safe to run multiple times)
    - Creates audit log of changes
    
    Examples:
        flask fix-propertyradar-import --dry-run
        flask fix-propertyradar-import --import-id 9
        flask fix-propertyradar-import --force
    """
    try:
        # Initialize repository
        db_session = current_app.services.get('db_session')
        csv_import_repo = CSVImportRepository(session=db_session)
        
        # Expected values for PropertyRadar import
        EXPECTED_TOTAL = 826
        EXPECTED_SUCCESS = 826
        EXPECTED_FAILED = 0
        
        # Find the import record
        csv_import = None
        
        if import_id:
            # Use specific ID if provided
            csv_import = csv_import_repo.get_by_id(import_id)
            if not csv_import:
                click.echo(f"❌ CSV Import record with ID {import_id} not found")
                return
        else:
            # Find PropertyRadar imports
            pr_imports = db_session.query(CSVImport).filter(
                CSVImport.filename.like('%propertyradar%826%')
            ).order_by(CSVImport.imported_at.desc()).all()
            
            if not pr_imports:
                click.echo("❌ No PropertyRadar import with 826 records found")
                click.echo("\nAvailable imports:")
                all_imports = csv_import_repo.get_recent_imports(10)
                for imp in all_imports:
                    click.echo(f"  ID {imp.id}: {imp.filename} ({imp.total_rows or 'NULL'} rows)")
                return
            
            # Use the most recent PropertyRadar import
            csv_import = pr_imports[0]
            
            if len(pr_imports) > 1:
                click.echo(f"⚠️  Found {len(pr_imports)} PropertyRadar imports, using most recent (ID {csv_import.id})")
        
        # Display current state
        click.echo(f"\n📋 CSV Import Record #{csv_import.id}")
        click.echo(f"   Filename: {csv_import.filename}")
        click.echo(f"   Imported At: {csv_import.imported_at}")
        click.echo(f"   Import Type: {csv_import.import_type or 'N/A'}")
        
        click.echo(f"\n   Current Values:")
        click.echo(f"   - Total Rows: {csv_import.total_rows or 'NULL'}")
        click.echo(f"   - Successful: {csv_import.successful_imports or 'NULL'}")
        click.echo(f"   - Failed: {'NULL' if csv_import.failed_imports is None else csv_import.failed_imports}")
        
        # Check if update is needed
        needs_update = (
            csv_import.total_rows != EXPECTED_TOTAL or
            csv_import.successful_imports != EXPECTED_SUCCESS or
            csv_import.failed_imports != EXPECTED_FAILED
        )
        
        if not needs_update and not force:
            click.echo("\n✅ Record already has the correct values")
            if csv_import.import_metadata and 'audit_log' in csv_import.import_metadata:
                audit_log = csv_import.import_metadata['audit_log']
                if audit_log:
                    last_fix = audit_log[-1]
                    click.echo(f"   Last fixed: {last_fix.get('timestamp', 'Unknown')}")
            return
        
        # Prepare updates
        updates = {}
        audit_changes = []
        
        if csv_import.total_rows != EXPECTED_TOTAL or force:
            updates['total_rows'] = EXPECTED_TOTAL
            audit_changes.append(f"total_rows: {csv_import.total_rows or 'NULL'} → {EXPECTED_TOTAL}")
        
        if csv_import.successful_imports != EXPECTED_SUCCESS or force:
            updates['successful_imports'] = EXPECTED_SUCCESS
            audit_changes.append(f"successful_imports: {csv_import.successful_imports or 'NULL'} → {EXPECTED_SUCCESS}")
        
        if csv_import.failed_imports != EXPECTED_FAILED or force:
            updates['failed_imports'] = EXPECTED_FAILED
            audit_changes.append(f"failed_imports: {csv_import.failed_imports or 'NULL'} → {EXPECTED_FAILED}")
        
        # Show proposed changes
        click.echo(f"\n   Proposed Changes:")
        for change in audit_changes:
            click.echo(f"   - {change}")
        
        if dry_run:
            click.echo("\n🔍 DRY RUN MODE - No changes made")
            return
        
        # Apply updates
        click.echo("\n⚙️  Applying updates...")
        
        # Add audit information
        metadata = csv_import.import_metadata or {}
        if 'audit_log' not in metadata:
            metadata['audit_log'] = []
        
        metadata['audit_log'].append({
            'timestamp': datetime.utcnow().isoformat(),
            'action': 'fix_propertyradar_import',
            'changes': audit_changes,
            'forced': force,
            'expected_values': {
                'total_rows': EXPECTED_TOTAL,
                'successful_imports': EXPECTED_SUCCESS,
                'failed_imports': EXPECTED_FAILED
            }
        })
        
        updates['import_metadata'] = metadata
        
        # Update the record
        updated_record = csv_import_repo.update(csv_import, **updates)
        
        if updated_record:
            db_session.commit()
            
            click.echo("✅ Successfully fixed PropertyRadar import")
            click.echo(f"\n   Updated Values:")
            click.echo(f"   - Total Rows: {updated_record.total_rows}")
            click.echo(f"   - Successful: {updated_record.successful_imports}")
            click.echo(f"   - Failed: {updated_record.failed_imports}")
            
            logger.info(f"Fixed PropertyRadar CSV Import #{csv_import.id}: {', '.join(audit_changes)}")
        else:
            click.echo("❌ Failed to update record")
            db_session.rollback()
            
    except Exception as e:
        click.echo(f"❌ Error: {str(e)}")
        logger.error(f"Error fixing PropertyRadar import: {str(e)}", exc_info=True)
        if 'db_session' in locals():
            db_session.rollback()
        raise


@click.command()
@click.option('--verbose', is_flag=True, help='Show detailed information')
@with_appcontext
def verify_csv_import_integrity(verbose):
    """
    Verify integrity of all CSV import records.
    
    Checks for:
    - Records with NULL statistics
    - Records where total != successful + failed
    - PropertyRadar imports with unexpected counts
    
    Examples:
        flask verify-csv-import-integrity
        flask verify-csv-import-integrity --verbose
    """
    try:
        db_session = current_app.services.get('db_session')
        csv_import_repo = CSVImportRepository(session=db_session)
        
        issues_found = False
        
        # Check for NULL values
        click.echo("\n🔍 Checking for incomplete records...")
        incomplete = db_session.query(CSVImport).filter(
            db.or_(
                CSVImport.total_rows.is_(None),
                CSVImport.successful_imports.is_(None),
                CSVImport.failed_imports.is_(None)
            )
        ).all()
        
        if incomplete:
            issues_found = True
            click.echo(f"⚠️  Found {len(incomplete)} records with NULL values:")
            for imp in incomplete:
                click.echo(f"   ID {imp.id}: {imp.filename}")
                if verbose:
                    click.echo(f"      Total: {imp.total_rows}, Success: {imp.successful_imports}, Failed: {imp.failed_imports}")
        else:
            click.echo("✅ No records with NULL values")
        
        # Check for mismatched counts
        click.echo("\n🔍 Checking for count mismatches...")
        all_imports = csv_import_repo.get_all()
        mismatched = []
        
        for imp in all_imports:
            if imp.total_rows is not None and imp.successful_imports is not None and imp.failed_imports is not None:
                if imp.total_rows != (imp.successful_imports + imp.failed_imports):
                    mismatched.append(imp)
        
        if mismatched:
            issues_found = True
            click.echo(f"⚠️  Found {len(mismatched)} records with count mismatches:")
            for imp in mismatched:
                click.echo(f"   ID {imp.id}: {imp.filename}")
                click.echo(f"      Total: {imp.total_rows}, Success: {imp.successful_imports}, Failed: {imp.failed_imports}")
                click.echo(f"      Difference: {imp.total_rows - (imp.successful_imports + imp.failed_imports)}")
        else:
            click.echo("✅ All record counts match")
        
        # Check PropertyRadar imports specifically
        click.echo("\n🔍 Checking PropertyRadar imports...")
        pr_imports = db_session.query(CSVImport).filter(
            CSVImport.filename.like('%propertyradar%')
        ).all()
        
        if pr_imports:
            click.echo(f"Found {len(pr_imports)} PropertyRadar imports:")
            for imp in pr_imports:
                expected_826 = '826' in imp.filename
                status = "✅" if imp.total_rows == 826 and expected_826 else "⚠️"
                click.echo(f"   {status} ID {imp.id}: {imp.filename}")
                click.echo(f"      Total: {imp.total_rows}, Success: {imp.successful_imports}, Failed: {imp.failed_imports}")
                
                if verbose and imp.import_metadata and 'audit_log' in imp.import_metadata:
                    audit_log = imp.import_metadata['audit_log']
                    if audit_log:
                        click.echo(f"      Last audit: {audit_log[-1].get('timestamp', 'Unknown')}")
        else:
            click.echo("No PropertyRadar imports found")
        
        # Summary
        click.echo("\n" + "=" * 60)
        if issues_found:
            click.echo("⚠️  Issues found. Run 'flask fix-csv-import-record' to fix specific records.")
        else:
            click.echo("✅ All CSV import records are valid")
        
    except Exception as e:
        click.echo(f"❌ Error during verification: {str(e)}")
        logger.error(f"Error verifying CSV import integrity: {str(e)}", exc_info=True)
        raise