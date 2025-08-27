"""
CLI Commands for fixing CSV Import database records
Safe, auditable, and idempotent operations
"""

import click
from flask import current_app
from flask.cli import with_appcontext
from extensions import db
from crm_database import CSVImport
from repositories.csv_import_repository import CSVImportRepository
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


def register_commands(app):
    """Register CSV import fix commands with Flask app"""
    app.cli.add_command(fix_csv_import_record)
    app.cli.add_command(audit_csv_imports)
    app.cli.add_command(fix_incomplete_imports)


@click.command()
@click.option('--id', 'import_id', required=True, type=int, help='CSV Import record ID to fix')
@click.option('--total-rows', type=int, help='Total rows in the import')
@click.option('--successful', type=int, help='Number of successful imports')
@click.option('--failed', type=int, help='Number of failed imports')
@click.option('--dry-run', is_flag=True, help='Show what would be changed without making changes')
@with_appcontext
def fix_csv_import_record(import_id, total_rows, successful, failed, dry_run):
    """
    Fix a specific CSV import record with missing or incorrect data.
    
    This command is idempotent - safe to run multiple times.
    All changes are logged for audit purposes.
    
    Example:
        flask fix-csv-import-record --id 15 --total-rows 826 --successful 826 --failed 0
        flask fix-csv-import-record --id 15 --total-rows 826 --successful 826 --failed 0 --dry-run
    """
    try:
        # Initialize repository using the service registry pattern
        db_session = current_app.services.get('db_session')
        csv_import_repo = CSVImportRepository(session=db_session)
        
        # Verify the record exists
        csv_import = csv_import_repo.get_by_id(import_id)
        
        if not csv_import:
            click.echo(f"❌ CSV Import record with ID {import_id} not found")
            return
        
        # Show current state
        click.echo(f"\n📋 CSV Import Record #{import_id}")
        click.echo(f"   Filename: {csv_import.filename}")
        click.echo(f"   Imported At: {csv_import.imported_at}")
        click.echo(f"   Import Type: {csv_import.import_type or 'N/A'}")
        click.echo(f"\n   Current Values:")
        click.echo(f"   - Total Rows: {csv_import.total_rows or 'NULL'}")
        click.echo(f"   - Successful: {csv_import.successful_imports or 'NULL'}")
        click.echo(f"   - Failed: {'NULL' if csv_import.failed_imports is None else csv_import.failed_imports}")
        
        # Check what needs to be updated
        updates = {}
        audit_log = []
        
        if total_rows is not None and csv_import.total_rows != total_rows:
            updates['total_rows'] = total_rows
            audit_log.append(f"total_rows: {csv_import.total_rows or 'NULL'} → {total_rows}")
        
        if successful is not None and csv_import.successful_imports != successful:
            updates['successful_imports'] = successful
            audit_log.append(f"successful_imports: {csv_import.successful_imports or 'NULL'} → {successful}")
        
        if failed is not None and csv_import.failed_imports != failed:
            updates['failed_imports'] = failed
            audit_log.append(f"failed_imports: {csv_import.failed_imports or 'NULL'} → {failed}")
        
        if not updates:
            click.echo("\n✅ No changes needed - record already has the specified values")
            return
        
        # Show proposed changes
        click.echo(f"\n   Proposed Changes:")
        for change in audit_log:
            click.echo(f"   - {change}")
        
        if dry_run:
            click.echo("\n🔍 DRY RUN MODE - No changes made")
            return
        
        # Apply the updates
        click.echo("\n⚙️  Applying updates...")
        
        # Add audit information to metadata
        metadata = csv_import.import_metadata or {}
        if 'audit_log' not in metadata:
            metadata['audit_log'] = []
        
        metadata['audit_log'].append({
            'timestamp': datetime.utcnow().isoformat(),
            'action': 'manual_fix',
            'changes': audit_log,
            'command': f"fix-csv-import-record --id {import_id} --total-rows {total_rows} --successful {successful} --failed {failed}"
        })
        
        updates['import_metadata'] = metadata
        
        # Perform the update using repository pattern
        updated_record = csv_import_repo.update(csv_import, **updates)
        
        if updated_record:
            # Commit the transaction
            db_session.commit()
            
            click.echo("✅ Successfully updated CSV Import record")
            click.echo(f"\n   New Values:")
            click.echo(f"   - Total Rows: {updated_record.total_rows}")
            click.echo(f"   - Successful: {updated_record.successful_imports}")
            click.echo(f"   - Failed: {updated_record.failed_imports}")
            
            # Log the change
            logger.info(f"Fixed CSV Import #{import_id}: {', '.join(audit_log)}")
        else:
            click.echo("❌ Failed to update record")
            db_session.rollback()
            
    except Exception as e:
        click.echo(f"❌ Error: {str(e)}")
        logger.error(f"Error fixing CSV import record {import_id}: {str(e)}")
        if 'db_session' in locals():
            db_session.rollback()
        raise


@click.command()
@click.option('--show-incomplete', is_flag=True, help='Show imports with NULL statistics')
@click.option('--show-failed', is_flag=True, help='Show imports with failures')
@click.option('--limit', type=int, default=20, help='Maximum number of records to show')
@with_appcontext
def audit_csv_imports(show_incomplete, show_failed, limit):
    """
    Audit CSV import records to find issues.
    
    Examples:
        flask audit-csv-imports --show-incomplete
        flask audit-csv-imports --show-failed
        flask audit-csv-imports --show-incomplete --limit 10
    """
    try:
        # Initialize repository
        db_session = current_app.services.get('db_session')
        csv_import_repo = CSVImportRepository(session=db_session)
        
        if show_incomplete:
            click.echo("\n📊 CSV Imports with Incomplete Statistics (NULL values):")
            click.echo("=" * 70)
            
            # Get imports with NULL statistics
            incomplete = db_session.query(CSVImport).filter(
                db.or_(
                    CSVImport.total_rows.is_(None),
                    CSVImport.successful_imports.is_(None),
                    CSVImport.failed_imports.is_(None)
                )
            ).order_by(CSVImport.imported_at.desc()).limit(limit).all()
            
            if not incomplete:
                click.echo("✅ No incomplete import records found")
            else:
                click.echo(f"\nFound {len(incomplete)} incomplete records:\n")
                for imp in incomplete:
                    click.echo(f"ID: {imp.id}")
                    click.echo(f"  Filename: {imp.filename}")
                    click.echo(f"  Imported: {imp.imported_at}")
                    click.echo(f"  Total Rows: {imp.total_rows or 'NULL'}")
                    click.echo(f"  Successful: {imp.successful_imports or 'NULL'}")
                    click.echo(f"  Failed: {imp.failed_imports or 'NULL'}")
                    click.echo("-" * 40)
        
        if show_failed:
            click.echo("\n❌ CSV Imports with Failures:")
            click.echo("=" * 70)
            
            failed_imports = csv_import_repo.get_failed_imports()[:limit]
            
            if not failed_imports:
                click.echo("✅ No failed import records found")
            else:
                click.echo(f"\nFound {len(failed_imports)} imports with failures:\n")
                for imp in failed_imports:
                    click.echo(f"ID: {imp.id}")
                    click.echo(f"  Filename: {imp.filename}")
                    click.echo(f"  Imported: {imp.imported_at}")
                    click.echo(f"  Total Rows: {imp.total_rows}")
                    click.echo(f"  Successful: {imp.successful_imports}")
                    click.echo(f"  Failed: {imp.failed_imports} ⚠️")
                    
                    # Check for error details in metadata
                    if imp.import_metadata and 'errors' in imp.import_metadata:
                        errors = imp.import_metadata['errors']
                        if isinstance(errors, list) and errors:
                            click.echo(f"  First Error: {errors[0][:100]}...")
                    click.echo("-" * 40)
        
        if not show_incomplete and not show_failed:
            click.echo("Please specify --show-incomplete or --show-failed")
            
    except Exception as e:
        click.echo(f"❌ Error during audit: {str(e)}")
        logger.error(f"Error auditing CSV imports: {str(e)}")
        raise


@click.command()
@click.option('--confirm', is_flag=True, help='Confirm the fix operation')
@click.option('--dry-run', is_flag=True, help='Show what would be fixed without making changes')
@with_appcontext
def fix_incomplete_imports(confirm, dry_run):
    """
    Fix all incomplete CSV import records by setting NULL values to 0.
    
    This is useful for cleaning up old imports that didn't properly track statistics.
    
    Examples:
        flask fix-incomplete-imports --dry-run
        flask fix-incomplete-imports --confirm
    """
    try:
        if not confirm and not dry_run:
            click.echo("⚠️  This command will update multiple records.")
            click.echo("Use --confirm to proceed or --dry-run to preview changes.")
            return
        
        # Initialize repository
        db_session = current_app.services.get('db_session')
        csv_import_repo = CSVImportRepository(session=db_session)
        
        # Find incomplete imports
        incomplete = db_session.query(CSVImport).filter(
            db.or_(
                CSVImport.total_rows.is_(None),
                CSVImport.successful_imports.is_(None),
                CSVImport.failed_imports.is_(None)
            )
        ).all()
        
        if not incomplete:
            click.echo("✅ No incomplete import records found")
            return
        
        click.echo(f"\n📋 Found {len(incomplete)} incomplete import records")
        
        if dry_run:
            click.echo("\n🔍 DRY RUN MODE - Showing what would be fixed:\n")
        else:
            click.echo("\n⚙️  Fixing incomplete records...\n")
        
        fixed_count = 0
        
        for imp in incomplete:
            changes = []
            updates = {}
            
            if imp.total_rows is None:
                updates['total_rows'] = 0
                changes.append("total_rows: NULL → 0")
            
            if imp.successful_imports is None:
                updates['successful_imports'] = 0
                changes.append("successful_imports: NULL → 0")
            
            if imp.failed_imports is None:
                updates['failed_imports'] = 0
                changes.append("failed_imports: NULL → 0")
            
            if updates:
                click.echo(f"Record #{imp.id} ({imp.filename}):")
                for change in changes:
                    click.echo(f"  - {change}")
                
                if not dry_run:
                    # Add audit log
                    metadata = imp.import_metadata or {}
                    if 'audit_log' not in metadata:
                        metadata['audit_log'] = []
                    
                    metadata['audit_log'].append({
                        'timestamp': datetime.utcnow().isoformat(),
                        'action': 'bulk_fix_incomplete',
                        'changes': changes
                    })
                    
                    updates['import_metadata'] = metadata
                    
                    # Update the record
                    csv_import_repo.update(imp, **updates)
                    fixed_count += 1
        
        if not dry_run:
            db_session.commit()
            click.echo(f"\n✅ Successfully fixed {fixed_count} records")
            logger.info(f"Fixed {fixed_count} incomplete CSV import records")
        else:
            click.echo(f"\n🔍 Would fix {len(incomplete)} records")
            
    except Exception as e:
        click.echo(f"❌ Error: {str(e)}")
        logger.error(f"Error fixing incomplete imports: {str(e)}")
        if 'db_session' in locals():
            db_session.rollback()
        raise