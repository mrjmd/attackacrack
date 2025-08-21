"""Add critical performance indexes for webhook and campaign processing

Revision ID: 348a94c904eb
Revises: 2792ed2d7978
Create Date: 2025-08-21 21:53:42.545831

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = '348a94c904eb'
down_revision = '2792ed2d7978'
branch_labels = None
depends_on = None


def upgrade():
    """Add critical performance indexes for webhook and campaign processing."""
    
    # Get the database dialect
    connection = op.get_bind()
    dialect_name = connection.dialect.name
    
    # Index 1: Critical for webhook processing - find activities by OpenPhone ID
    # This index speeds up webhook processing when matching OpenPhone events to local activities
    if dialect_name == 'postgresql':
        op.execute("""
            CREATE INDEX IF NOT EXISTS idx_activity_openphone_id 
            ON activity(openphone_id)
            WHERE openphone_id IS NOT NULL
        """)
    else:
        # SQLite doesn't support partial indexes with WHERE clause in the same way
        with op.batch_alter_table('activity') as batch_op:
            batch_op.create_index('idx_activity_openphone_id', ['openphone_id'])
    
    # Index 2: Webhook event processing - index on processed status
    # Note: The webhook_event table doesn't have status/retry_count columns yet
    # Instead, we'll index the processed column which exists
    with op.batch_alter_table('webhook_event') as batch_op:
        batch_op.create_index('idx_webhook_event_processed', ['processed', 'created_at'])
    
    # Also add an index for event_id lookup (common operation)
    with op.batch_alter_table('webhook_event') as batch_op:
        batch_op.create_index('idx_webhook_event_id', ['event_id'])
    
    # Index 3: Critical for campaign processing - find campaign members by status
    # This index speeds up campaign list generation and status updates
    with op.batch_alter_table('campaign_membership') as batch_op:
        batch_op.create_index('idx_campaign_membership_status', ['campaign_id', 'status'])
    
    # Index 4: Critical for phone lookups - hash index for exact phone matches
    # This index dramatically speeds up contact lookups by phone number
    if dialect_name == 'postgresql':
        op.execute("""
            CREATE INDEX IF NOT EXISTS idx_contact_phone_hash 
            ON contact USING hash(phone)
        """)
    else:
        # SQLite doesn't support hash indexes, use regular B-tree index
        with op.batch_alter_table('contact') as batch_op:
            batch_op.create_index('idx_contact_phone_hash', ['phone'])
    
    # Index 5: Critical for conversation activity tracking
    # This index speeds up finding recent activities for a conversation
    with op.batch_alter_table('activity') as batch_op:
        batch_op.create_index('idx_activity_conversation_created', 
                            ['conversation_id', 'created_at'])
    
    # Index 6: Critical for opt-out checking - quickly find opted-out contacts
    # This index enables fast verification of opt-out status during campaign sending
    if dialect_name == 'postgresql':
        op.execute("""
            CREATE INDEX IF NOT EXISTS idx_contact_flag_type_phone 
            ON contact_flag(flag_type, contact_id)
            WHERE flag_type = 'opted_out'
        """)
    else:
        # SQLite: Create a composite index without the WHERE clause
        with op.batch_alter_table('contact_flag') as batch_op:
            batch_op.create_index('idx_contact_flag_type_phone', ['flag_type', 'contact_id'])
    
    # Additional performance indexes for common query patterns
    
    # Index 7: Speed up activity listing by type
    with op.batch_alter_table('activity') as batch_op:
        batch_op.create_index('idx_activity_type_created', ['activity_type', 'created_at'])
    
    # Index 8: Speed up conversation lookups by phone_number_id (the actual column name)
    with op.batch_alter_table('conversation') as batch_op:
        batch_op.create_index('idx_conversation_phone_number_id', ['phone_number_id'])
    
    # Index 9: Speed up conversation lookups by contact
    with op.batch_alter_table('conversation') as batch_op:
        batch_op.create_index('idx_conversation_contact', ['contact_id'])
    
    # Index 10: Speed up appointment scheduling queries
    # Note: appointment table has date and time columns, not scheduled_time
    with op.batch_alter_table('appointment') as batch_op:
        batch_op.create_index('idx_appointment_date', ['date', 'time'])
    
    # Index 11: Speed up invoice queries by status
    with op.batch_alter_table('invoice') as batch_op:
        batch_op.create_index('idx_invoice_status_due', ['status', 'due_date'])
    
    # Index 12: Campaign membership sent_at for tracking recent sends
    with op.batch_alter_table('campaign_membership') as batch_op:
        batch_op.create_index('idx_campaign_membership_sent', ['sent_at', 'status'])
    
    # Index 13: Contact search by first/last name (contact table doesn't have a single 'name' column)
    with op.batch_alter_table('contact') as batch_op:
        batch_op.create_index('idx_contact_first_name', ['first_name'])
    
    with op.batch_alter_table('contact') as batch_op:
        batch_op.create_index('idx_contact_last_name', ['last_name'])
    
    # Index 14: Contact email lookup
    with op.batch_alter_table('contact') as batch_op:
        batch_op.create_index('idx_contact_email', ['email'])
    
    # Index 15: Activity by user for filtering
    with op.batch_alter_table('activity') as batch_op:
        batch_op.create_index('idx_activity_user', ['user_id', 'created_at'])
    
    # Index 16: Activity by contact for history views
    with op.batch_alter_table('activity') as batch_op:
        batch_op.create_index('idx_activity_contact', ['contact_id', 'created_at'])
    
    print("Successfully created performance indexes for:")
    print("  - Webhook processing (activity by OpenPhone ID)")
    print("  - Webhook event processing (by processed status)")
    print("  - Campaign member status tracking")
    print("  - Contact phone lookups (hash index in PostgreSQL)")
    print("  - Conversation activity tracking")
    print("  - Opt-out flag checking")
    print("  - Contact name and email search")
    print("  - Activity filtering by user and contact")
    print("  - Additional common query patterns")


def downgrade():
    """Remove the performance indexes."""
    
    # Get the database dialect
    connection = op.get_bind()
    dialect_name = connection.dialect.name
    
    # Drop indexes in reverse order of creation
    
    # Drop activity indexes
    with op.batch_alter_table('activity') as batch_op:
        batch_op.drop_index('idx_activity_contact')
    
    with op.batch_alter_table('activity') as batch_op:
        batch_op.drop_index('idx_activity_user')
    
    # Drop contact search indexes
    with op.batch_alter_table('contact') as batch_op:
        batch_op.drop_index('idx_contact_email')
    
    with op.batch_alter_table('contact') as batch_op:
        batch_op.drop_index('idx_contact_last_name')
    
    with op.batch_alter_table('contact') as batch_op:
        batch_op.drop_index('idx_contact_first_name')
    
    with op.batch_alter_table('campaign_membership') as batch_op:
        batch_op.drop_index('idx_campaign_membership_sent')
    
    # Drop additional performance indexes
    with op.batch_alter_table('invoice') as batch_op:
        batch_op.drop_index('idx_invoice_status_due')
    
    with op.batch_alter_table('appointment') as batch_op:
        batch_op.drop_index('idx_appointment_date')
    
    with op.batch_alter_table('conversation') as batch_op:
        batch_op.drop_index('idx_conversation_contact')
        
    with op.batch_alter_table('conversation') as batch_op:
        batch_op.drop_index('idx_conversation_phone_number_id')
    
    with op.batch_alter_table('activity') as batch_op:
        batch_op.drop_index('idx_activity_type_created')
    
    # Drop opt-out checking index
    with op.batch_alter_table('contact_flag') as batch_op:
        batch_op.drop_index('idx_contact_flag_type_phone')
    
    # Drop conversation activity tracking index
    with op.batch_alter_table('activity') as batch_op:
        batch_op.drop_index('idx_activity_conversation_created')
    
    # Drop phone hash index
    if dialect_name == 'postgresql':
        op.execute("DROP INDEX IF EXISTS idx_contact_phone_hash")
    else:
        with op.batch_alter_table('contact') as batch_op:
            batch_op.drop_index('idx_contact_phone_hash')
    
    # Drop campaign member status index
    with op.batch_alter_table('campaign_membership') as batch_op:
        batch_op.drop_index('idx_campaign_membership_status')
    
    # Drop webhook event indexes
    with op.batch_alter_table('webhook_event') as batch_op:
        batch_op.drop_index('idx_webhook_event_id')
    
    with op.batch_alter_table('webhook_event') as batch_op:
        batch_op.drop_index('idx_webhook_event_processed')
    
    # Drop activity OpenPhone ID index
    if dialect_name == 'postgresql':
        op.execute("DROP INDEX IF EXISTS idx_activity_openphone_id")
    else:
        with op.batch_alter_table('activity') as batch_op:
            batch_op.drop_index('idx_activity_openphone_id')
    
    print("Successfully removed all performance indexes")