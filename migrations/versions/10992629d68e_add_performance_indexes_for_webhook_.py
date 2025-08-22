"""Add performance indexes for webhook campaign and opt_out processing

Revision ID: 10992629d68e
Revises: 2792ed2d7978
Create Date: 2025-08-21 23:04:39.463023

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = '10992629d68e'
down_revision = '2792ed2d7978'
branch_labels = None
depends_on = None


def upgrade():
    """Add critical performance indexes for campaign and webhook processing."""
    
    # Get the database connection to check dialect
    connection = op.get_bind()
    is_postgresql = connection.dialect.name == 'postgresql'
    
    # ==============================
    # WEBHOOK PROCESSING INDEXES
    # ==============================
    
    # Index for activity lookup by openphone_id (critical for webhook deduplication)
    # This helps prevent duplicate webhook processing
    op.create_index(
        'ix_activity_openphone_id',
        'activity',
        ['openphone_id'],
        unique=False,
        if_not_exists=True
    )
    
    # Partial index for webhook_event that need retry processing
    # Only index failed and retry_queued events to keep index small and efficient
    # Note: webhook_event doesn't have status or retry_count columns in current schema
    # Adding index on processed and event_type instead for query optimization
    op.create_index(
        'ix_webhook_event_processed',
        'webhook_event',
        ['processed', 'event_type'],
        unique=False,
        if_not_exists=True
    )
    
    # ==============================
    # CAMPAIGN PROCESSING INDEXES
    # ==============================
    
    # Composite index for campaign membership lookups
    # Critical for finding members by campaign and status
    op.create_index(
        'ix_campaign_membership_campaign_status',
        'campaign_membership',
        ['campaign_id', 'status'],
        unique=False,
        if_not_exists=True
    )
    
    # Phone number index for contact
    # Use hash index for PostgreSQL for exact match lookups
    if is_postgresql:
        # Hash index is perfect for exact match lookups on phone numbers
        op.execute("""
            CREATE INDEX IF NOT EXISTS ix_contact_phone_hash
            ON contact USING hash(phone)
        """)
    else:
        # Regular B-tree index for SQLite
        op.create_index(
            'ix_contact_phone',
            'contact',
            ['phone'],
            unique=False,
            if_not_exists=True
        )
    
    # Composite index for activity by conversation and time
    # Critical for loading conversation history efficiently
    op.create_index(
        'ix_activity_conversation_created',
        'activity',
        ['conversation_id', sa.text('created_at DESC')],
        unique=False,
        if_not_exists=True
    )
    
    # ==============================
    # OPT-OUT CHECKING INDEXES
    # ==============================
    
    # Partial index for opt-out flag lookups
    # Only index opted_out flags to keep index small
    if is_postgresql:
        op.execute("""
            CREATE INDEX IF NOT EXISTS ix_contact_flag_opted_out
            ON contact_flag(flag_type, contact_id)
            WHERE flag_type = 'opted_out'
        """)
    else:
        # SQLite: Create regular composite index
        op.create_index(
            'ix_contact_flag_type_contact',
            'contact_flag',
            ['flag_type', 'contact_id'],
            unique=False,
            if_not_exists=True
        )
    
    # ==============================
    # ADDITIONAL PERFORMANCE INDEXES
    # ==============================
    
    # Index for conversation by contact (for quick contact history lookup)
    op.create_index(
        'ix_conversation_contact_id',
        'conversation',
        ['contact_id'],
        unique=False,
        if_not_exists=True
    )
    
    # Index for activity by type (for filtering specific activity types)
    # Note: The column is 'activity_type' not 'type' in the Activity model
    op.create_index(
        'ix_activity_type',
        'activity',
        ['activity_type'],
        unique=False,
        if_not_exists=True
    )
    
    # Index for campaign membership by contact (to check if contact is in any campaign)
    op.create_index(
        'ix_campaign_membership_contact_id',
        'campaign_membership',
        ['contact_id'],
        unique=False,
        if_not_exists=True
    )
    
    # Index for webhook_event by event type for analytics
    op.create_index(
        'ix_webhook_event_event_type',
        'webhook_event',
        ['event_type'],
        unique=False,
        if_not_exists=True
    )
    
    print("✅ Performance indexes created successfully")


def downgrade():
    """Remove all performance indexes."""
    
    # Get the database connection to check dialect
    connection = op.get_bind()
    is_postgresql = connection.dialect.name == 'postgresql'
    
    # Drop indexes in reverse order
    
    # Additional indexes
    op.drop_index('ix_webhook_event_event_type', table_name='webhook_event', if_exists=True)
    op.drop_index('ix_campaign_membership_contact_id', table_name='campaign_membership', if_exists=True)
    op.drop_index('ix_activity_type', table_name='activity', if_exists=True)
    op.drop_index('ix_conversation_contact_id', table_name='conversation', if_exists=True)
    
    # Opt-out indexes
    if is_postgresql:
        op.execute("DROP INDEX IF EXISTS ix_contact_flag_opted_out")
    else:
        op.drop_index('ix_contact_flag_type_contact', table_name='contact_flag', if_exists=True)
    
    # Campaign indexes
    op.drop_index('ix_activity_conversation_created', table_name='activity', if_exists=True)
    
    if is_postgresql:
        op.execute("DROP INDEX IF EXISTS ix_contact_phone_hash")
    else:
        op.drop_index('ix_contact_phone', table_name='contact', if_exists=True)
    
    op.drop_index('ix_campaign_membership_campaign_status', table_name='campaign_membership', if_exists=True)
    
    # Webhook indexes
    op.drop_index('ix_webhook_event_processed', table_name='webhook_event', if_exists=True)
    
    op.drop_index('ix_activity_openphone_id', table_name='activity', if_exists=True)
    
    print("✅ Performance indexes dropped successfully")
