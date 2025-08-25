"""Add campaign_id to Activity table for campaign attribution

Revision ID: bdeba4e238ad
Revises: 52ef9943e841
Create Date: 2025-08-25 22:50:29.979228

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'bdeba4e238ad'
down_revision = '52ef9943e841'
branch_labels = None
depends_on = None


def upgrade():
    """Add campaign_id column to Activity table for campaign attribution.
    
    This migration adds a foreign key reference from Activity to Campaign,
    allowing activities (calls, messages, etc.) to be linked to specific
    campaigns for attribution and analytics.
    """
    
    # Add campaign_id column as nullable foreign key
    # Using batch operations for compatibility
    with op.batch_alter_table('activity', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('campaign_id', sa.Integer(), nullable=True)
        )
        batch_op.create_foreign_key(
            'fk_activity_campaign_id',
            'campaign',
            ['campaign_id'],
            ['id'],
            ondelete='SET NULL'
        )
        
        # Create index for query performance
        batch_op.create_index(
            'ix_activity_campaign_id',
            ['campaign_id'],
            unique=False
        )
    
    # For PostgreSQL-specific optimizations
    connection = op.get_bind()
    if connection.dialect.name == 'postgresql':
        # Create composite index for campaign activities
        # This index helps with queries filtering by campaign_id and sorting by created_at
        op.execute("""
            CREATE INDEX IF NOT EXISTS 
            ix_activity_campaign_created
            ON activity(campaign_id, created_at DESC)
            WHERE campaign_id IS NOT NULL
        """)
        
        # Analyze the table after adding the column
        op.execute("ANALYZE activity")


def downgrade():
    """Remove campaign_id column from Activity table."""
    
    # Drop PostgreSQL-specific index if it exists
    connection = op.get_bind()
    if connection.dialect.name == 'postgresql':
        op.execute("DROP INDEX IF EXISTS ix_activity_campaign_created")
    
    # Remove column and constraints using batch operations
    with op.batch_alter_table('activity', schema=None) as batch_op:
        batch_op.drop_index('ix_activity_campaign_id')
        batch_op.drop_constraint('fk_activity_campaign_id', type_='foreignkey')
        batch_op.drop_column('campaign_id')
