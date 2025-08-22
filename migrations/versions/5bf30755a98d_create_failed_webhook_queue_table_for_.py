"""Create failed_webhook_queue table for error recovery (P1-16)

Revision ID: 5bf30755a98d
Revises: 10992629d68e
Create Date: 2025-08-22 01:51:49.429334

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '5bf30755a98d'
down_revision = '10992629d68e'
branch_labels = None
depends_on = None


def upgrade():
    # Create failed_webhook_queue table for error recovery and retry management
    op.create_table('failed_webhook_queue',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('event_id', sa.String(length=100), nullable=False),
        sa.Column('event_type', sa.String(length=50), nullable=False),
        sa.Column('original_payload', sa.JSON(), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=False),
        sa.Column('retry_count', sa.Integer(), nullable=False, default=0),
        sa.Column('max_retries', sa.Integer(), nullable=False, default=5),
        sa.Column('backoff_multiplier', sa.DECIMAL(precision=3, scale=1), nullable=False, default=2.0),
        sa.Column('base_delay_seconds', sa.Integer(), nullable=False, default=60),
        sa.Column('next_retry_at', sa.DateTime(), nullable=True),
        sa.Column('last_retry_at', sa.DateTime(), nullable=True),
        sa.Column('resolved', sa.Boolean(), nullable=False, default=False),
        sa.Column('resolved_at', sa.DateTime(), nullable=True),
        sa.Column('resolution_note', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for efficient querying
    op.create_index('idx_failed_webhook_queue_event_id', 'failed_webhook_queue', ['event_id'])
    op.create_index('idx_failed_webhook_queue_next_retry', 'failed_webhook_queue', ['next_retry_at', 'resolved'])
    op.create_index('idx_failed_webhook_queue_resolved', 'failed_webhook_queue', ['resolved'])
    op.create_index('idx_failed_webhook_queue_event_type', 'failed_webhook_queue', ['event_type'])
    op.create_index('idx_failed_webhook_queue_created_at', 'failed_webhook_queue', ['created_at'])


def downgrade():
    # Drop indexes first
    op.drop_index('idx_failed_webhook_queue_created_at', table_name='failed_webhook_queue')
    op.drop_index('idx_failed_webhook_queue_event_type', table_name='failed_webhook_queue')
    op.drop_index('idx_failed_webhook_queue_resolved', table_name='failed_webhook_queue')
    op.drop_index('idx_failed_webhook_queue_next_retry', table_name='failed_webhook_queue')
    op.drop_index('idx_failed_webhook_queue_event_id', table_name='failed_webhook_queue')
    
    # Drop table
    op.drop_table('failed_webhook_queue')
