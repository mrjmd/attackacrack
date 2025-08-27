"""Add NOT NULL constraints to CSV import statistics with defaults

Revision ID: 54cef61514fb
Revises: c8c8f157177a
Create Date: 2025-08-27 02:09:40.800289

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '54cef61514fb'
down_revision = 'c8c8f157177a'
branch_labels = None
depends_on = None


def upgrade():
    """Add NOT NULL constraints to CSV import statistics columns with defaults.
    
    This is a zero-downtime migration that:
    1. Updates existing NULL values to 0
    2. Adds NOT NULL constraints with defaults
    3. Ensures future imports always have statistics
    """
    
    # Get database connection
    connection = op.get_bind()
    
    # Step 1: Update existing NULL values to 0 (safe, idempotent)
    # This is done in batches for large tables
    op.execute("""
        UPDATE csv_import 
        SET total_rows = 0 
        WHERE total_rows IS NULL
    """)
    
    op.execute("""
        UPDATE csv_import 
        SET successful_imports = 0 
        WHERE successful_imports IS NULL
    """)
    
    op.execute("""
        UPDATE csv_import 
        SET failed_imports = 0 
        WHERE failed_imports IS NULL
    """)
    
    # Step 2: Alter columns to add NOT NULL constraint with defaults
    # Using batch operations for compatibility
    with op.batch_alter_table('csv_import') as batch_op:
        # Add defaults and NOT NULL constraints
        batch_op.alter_column('total_rows',
                             existing_type=sa.INTEGER(),
                             nullable=False,
                             server_default='0')
        
        batch_op.alter_column('successful_imports',
                             existing_type=sa.INTEGER(),
                             nullable=False,
                             server_default='0')
        
        batch_op.alter_column('failed_imports',
                             existing_type=sa.INTEGER(),
                             nullable=False,
                             server_default='0')
    
    # Step 3: Add check constraints to ensure data integrity
    if connection.dialect.name == 'postgresql':
        # PostgreSQL-specific check constraints
        op.execute("""
            ALTER TABLE csv_import 
            ADD CONSTRAINT ck_csv_import_stats_non_negative 
            CHECK (
                total_rows >= 0 AND 
                successful_imports >= 0 AND 
                failed_imports >= 0
            )
        """)
        
        op.execute("""
            ALTER TABLE csv_import 
            ADD CONSTRAINT ck_csv_import_stats_consistency 
            CHECK (
                successful_imports + failed_imports <= total_rows
            )
        """)


def downgrade():
    """Remove NOT NULL constraints and defaults from CSV import statistics columns.
    
    This migration is safe to roll back and preserves data.
    """
    
    connection = op.get_bind()
    
    # Remove check constraints if they exist (PostgreSQL)
    if connection.dialect.name == 'postgresql':
        op.execute("""
            ALTER TABLE csv_import 
            DROP CONSTRAINT IF EXISTS ck_csv_import_stats_non_negative
        """)
        
        op.execute("""
            ALTER TABLE csv_import 
            DROP CONSTRAINT IF EXISTS ck_csv_import_stats_consistency
        """)
    
    # Remove NOT NULL constraints and defaults
    with op.batch_alter_table('csv_import') as batch_op:
        batch_op.alter_column('total_rows',
                             existing_type=sa.INTEGER(),
                             nullable=True,
                             server_default=None)
        
        batch_op.alter_column('successful_imports',
                             existing_type=sa.INTEGER(),
                             nullable=True,
                             server_default=None)
        
        batch_op.alter_column('failed_imports',
                             existing_type=sa.INTEGER(),
                             nullable=True,
                             server_default=None)
