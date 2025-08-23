"""Add missing columns to ab_test_result table

Revision ID: 35e46443c6d5
Revises: bdd5d2ed05c7
Create Date: 2025-08-23 13:49:35.720971

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '35e46443c6d5'
down_revision = 'bdd5d2ed05c7'
branch_labels = None
depends_on = None


def upgrade():
    # Get the database connection to check dialect
    connection = op.get_bind()
    dialect_name = connection.dialect.name
    
    if dialect_name == 'sqlite':
        # SQLite doesn't support ALTER COLUMN, so we need to recreate the table
        # First, let's check if the table exists and get its current structure
        inspector = sa.inspect(connection)
        
        if 'ab_test_result' in inspector.get_table_names():
            # Get existing columns
            existing_columns = [col['name'] for col in inspector.get_columns('ab_test_result')]
            
            # Create a new temporary table with the desired schema
            # For SQLite, we need to use raw SQL for CREATE TABLE
            op.execute("""
                CREATE TABLE ab_test_result_new (
                    id INTEGER PRIMARY KEY,
                    campaign_id INTEGER NOT NULL,
                    contact_id INTEGER NOT NULL,
                    variant VARCHAR(1) NOT NULL,
                    assigned_at DATETIME NOT NULL,
                    message_sent BOOLEAN DEFAULT 0,
                    sent_activity_id INTEGER,
                    sent_at DATETIME,
                    message_opened BOOLEAN DEFAULT 0,
                    opened_at DATETIME,
                    link_clicked BOOLEAN DEFAULT 0,
                    clicked_link_url VARCHAR(500),
                    clicked_at DATETIME,
                    response_received BOOLEAN DEFAULT 0,
                    response_type VARCHAR(20),
                    response_activity_id INTEGER,
                    responded_at DATETIME,
                    conversion_tracked BOOLEAN DEFAULT 0,
                    converted_at DATETIME
                )
            """)
            
            # Define columns to copy (exclude columns being dropped)
            columns_to_drop = ['created_at', 'updated_at', 'response_sentiment', 'error_message',
                             'conversion_value', 'template_content', 'metadata']
            
            # Build list of columns to copy
            columns_to_copy = []
            for col in existing_columns:
                if col not in columns_to_drop and col != 'id':
                    columns_to_copy.append(col)
            
            # Only copy columns that exist in both old and new tables
            new_table_columns = ['campaign_id', 'contact_id', 'variant', 'assigned_at',
                               'message_sent', 'sent_at', 'message_opened', 'opened_at',
                               'link_clicked', 'clicked_at', 'response_received', 'responded_at',
                               'conversion_tracked', 'converted_at']
            
            copy_columns = [col for col in columns_to_copy if col in new_table_columns]
            
            if copy_columns:
                # Copy data from old table to new table
                columns_str = ', '.join(copy_columns)
                op.execute(f"""
                    INSERT INTO ab_test_result_new (id, {columns_str})
                    SELECT id, {columns_str}
                    FROM ab_test_result
                """)
            
            # Drop the old table
            op.drop_table('ab_test_result')
            
            # Rename the new table to the original name
            op.rename_table('ab_test_result_new', 'ab_test_result')
            
            # Create indexes
            op.create_index('ix_ab_test_result_campaign_id', 'ab_test_result', ['campaign_id'])
            op.create_index('ix_ab_test_result_contact_id', 'ab_test_result', ['contact_id'])
            op.create_index('ix_ab_test_result_variant', 'ab_test_result', ['variant'])
            op.create_index('ix_ab_test_result_assigned_at', 'ab_test_result', ['assigned_at'])
            op.create_index('ix_ab_test_result_message_sent', 'ab_test_result', ['message_sent'])
            op.create_index('ix_ab_test_result_message_opened', 'ab_test_result', ['message_opened'])
            op.create_index('ix_ab_test_result_link_clicked', 'ab_test_result', ['link_clicked'])
            op.create_index('ix_ab_test_result_response_received', 'ab_test_result', ['response_received'])
            
            # Note: SQLite doesn't support foreign keys being added after table creation
            # They would need to be included in the CREATE TABLE statement
            
    else:
        # PostgreSQL and other databases that support ALTER TABLE
        
        # Add missing columns to ab_test_result
        with op.batch_alter_table('ab_test_result') as batch_op:
            # Check if columns already exist before adding
            inspector = sa.inspect(connection)
            existing_columns = [col['name'] for col in inspector.get_columns('ab_test_result')]
            
            if 'sent_activity_id' not in existing_columns:
                batch_op.add_column(sa.Column('sent_activity_id', sa.Integer(), nullable=True))
            if 'clicked_link_url' not in existing_columns:
                batch_op.add_column(sa.Column('clicked_link_url', sa.String(length=500), nullable=True))
            if 'response_type' not in existing_columns:
                batch_op.add_column(sa.Column('response_type', sa.String(length=20), nullable=True))
            if 'response_activity_id' not in existing_columns:
                batch_op.add_column(sa.Column('response_activity_id', sa.Integer(), nullable=True))
        
        # Update variant column type to be more specific
        with op.batch_alter_table('ab_test_result') as batch_op:
            batch_op.alter_column('variant',
                                existing_type=sa.VARCHAR(length=10),
                                type_=sa.String(length=1),
                                existing_nullable=False)
        
        # Add unique constraint to prevent duplicate assignments
        try:
            op.create_unique_constraint('unique_campaign_contact_assignment', 'ab_test_result', ['campaign_id', 'contact_id'])
        except Exception:
            pass  # Constraint might already exist
        
        # Add foreign keys for activity references (PostgreSQL specific)
        if dialect_name == 'postgresql':
            try:
                op.create_foreign_key('fk_ab_test_result_response_activity', 'ab_test_result', 'activity', ['response_activity_id'], ['id'])
            except Exception:
                pass
            try:
                op.create_foreign_key('fk_ab_test_result_sent_activity', 'ab_test_result', 'activity', ['sent_activity_id'], ['id'])
            except Exception:
                pass
        
        # Drop columns that were in the initial migration but not in the model
        inspector = sa.inspect(connection)
        columns = [col['name'] for col in inspector.get_columns('ab_test_result')]
        
        # Only drop columns if they exist
        columns_to_drop = ['created_at', 'updated_at', 'response_sentiment', 'error_message',
                         'conversion_value', 'template_content', 'metadata']
        
        with op.batch_alter_table('ab_test_result') as batch_op:
            for col in columns_to_drop:
                if col in columns:
                    batch_op.drop_column(col)


def downgrade():
    # Get the database connection to check dialect
    connection = op.get_bind()
    dialect_name = connection.dialect.name
    
    if dialect_name == 'sqlite':
        # For SQLite, we need to recreate the table again
        inspector = sa.inspect(connection)
        
        if 'ab_test_result' in inspector.get_table_names():
            # Create the old table structure
            # For SQLite, we need to use raw SQL for CREATE TABLE
            op.execute("""
                CREATE TABLE ab_test_result_old (
                    id INTEGER PRIMARY KEY,
                    campaign_id INTEGER NOT NULL,
                    contact_id INTEGER NOT NULL,
                    variant VARCHAR(10) NOT NULL,
                    assigned_at DATETIME NOT NULL,
                    message_sent BOOLEAN DEFAULT 0,
                    sent_at DATETIME,
                    message_opened BOOLEAN DEFAULT 0,
                    opened_at DATETIME,
                    link_clicked BOOLEAN DEFAULT 0,
                    clicked_at DATETIME,
                    response_received BOOLEAN DEFAULT 0,
                    responded_at DATETIME,
                    conversion_tracked BOOLEAN DEFAULT 0,
                    converted_at DATETIME,
                    created_at DATETIME NOT NULL,
                    updated_at DATETIME,
                    response_sentiment VARCHAR(20),
                    error_message TEXT,
                    conversion_value NUMERIC(10, 2),
                    template_content TEXT,
                    metadata TEXT
                )
            """)
            
            # Copy data back (excluding new columns)
            columns_to_copy = ['id', 'campaign_id', 'contact_id', 'variant', 'assigned_at',
                             'message_sent', 'sent_at', 'message_opened', 'opened_at',
                             'link_clicked', 'clicked_at', 'response_received', 'responded_at',
                             'conversion_tracked', 'converted_at']
            
            columns_str = ', '.join(columns_to_copy)
            op.execute(f"""
                INSERT INTO ab_test_result_old ({columns_str})
                SELECT {columns_str}
                FROM ab_test_result
            """)
            
            # Drop the current table and rename old one
            op.drop_table('ab_test_result')
            op.rename_table('ab_test_result_old', 'ab_test_result')
            
            # Recreate indexes
            op.create_index('ix_ab_test_result_campaign_id', 'ab_test_result', ['campaign_id'])
            op.create_index('ix_ab_test_result_contact_id', 'ab_test_result', ['contact_id'])
            op.create_index('ix_ab_test_result_variant', 'ab_test_result', ['variant'])
            op.create_index('ix_ab_test_result_assigned_at', 'ab_test_result', ['assigned_at'])
            op.create_index('ix_ab_test_result_message_sent', 'ab_test_result', ['message_sent'])
            op.create_index('ix_ab_test_result_message_opened', 'ab_test_result', ['message_opened'])
            op.create_index('ix_ab_test_result_link_clicked', 'ab_test_result', ['link_clicked'])
            op.create_index('ix_ab_test_result_response_received', 'ab_test_result', ['response_received'])
            
    else:
        # PostgreSQL and other databases
        
        # Re-add removed columns
        with op.batch_alter_table('ab_test_result') as batch_op:
            # Use JSON type for PostgreSQL, TEXT for others
            if dialect_name == 'postgresql':
                batch_op.add_column(sa.Column('metadata', postgresql.JSON(astext_type=sa.Text()), nullable=True))
                batch_op.add_column(sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()))
                batch_op.add_column(sa.Column('updated_at', sa.DateTime(), nullable=True))
            else:
                batch_op.add_column(sa.Column('metadata', sa.JSON(), nullable=True))
                batch_op.add_column(sa.Column('created_at', sa.DateTime(), nullable=False, default=sa.func.now()))
                batch_op.add_column(sa.Column('updated_at', sa.DateTime(), nullable=True))
            
            batch_op.add_column(sa.Column('template_content', sa.TEXT(), nullable=True))
            batch_op.add_column(sa.Column('conversion_value', sa.NUMERIC(precision=10, scale=2), nullable=True))
            batch_op.add_column(sa.Column('error_message', sa.TEXT(), nullable=True))
            batch_op.add_column(sa.Column('response_sentiment', sa.VARCHAR(length=20), nullable=True))
        
        # Drop foreign key constraints (PostgreSQL specific)
        if dialect_name == 'postgresql':
            try:
                op.drop_constraint('fk_ab_test_result_response_activity', 'ab_test_result', type_='foreignkey')
            except Exception:
                pass
            try:
                op.drop_constraint('fk_ab_test_result_sent_activity', 'ab_test_result', type_='foreignkey')
            except Exception:
                pass
        
        # Drop unique constraint
        try:
            op.drop_constraint('unique_campaign_contact_assignment', 'ab_test_result', type_='unique')
        except Exception:
            pass
        
        # Revert variant column type
        with op.batch_alter_table('ab_test_result') as batch_op:
            batch_op.alter_column('variant',
                                existing_type=sa.String(length=1),
                                type_=sa.VARCHAR(length=10),
                                existing_nullable=False)
        
        # Drop added columns
        with op.batch_alter_table('ab_test_result') as batch_op:
            inspector = sa.inspect(connection)
            existing_columns = [col['name'] for col in inspector.get_columns('ab_test_result')]
            
            if 'response_activity_id' in existing_columns:
                batch_op.drop_column('response_activity_id')
            if 'response_type' in existing_columns:
                batch_op.drop_column('response_type')
            if 'clicked_link_url' in existing_columns:
                batch_op.drop_column('clicked_link_url')
            if 'sent_activity_id' in existing_columns:
                batch_op.drop_column('sent_activity_id')