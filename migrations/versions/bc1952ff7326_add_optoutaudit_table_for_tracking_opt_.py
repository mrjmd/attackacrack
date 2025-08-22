"""Add OptOutAudit table for tracking opt-out events

Revision ID: bc1952ff7326
Revises: 5bf30755a98d
Create Date: 2025-08-21 19:31:01.123456

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'bc1952ff7326'
down_revision = '5bf30755a98d'
branch_labels = None
depends_on = None


def upgrade():
    # Create OptOutAudit table
    op.create_table('opt_out_audit',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('contact_id', sa.Integer(), nullable=False),
    sa.Column('phone_number', sa.String(length=50), nullable=False),
    sa.Column('opt_out_type', sa.String(length=10), nullable=False),
    sa.Column('keyword_used', sa.String(length=50), nullable=True),
    sa.Column('opt_out_method', sa.String(length=20), nullable=False),
    sa.Column('confirmation_sent', sa.Boolean(), nullable=False),
    sa.Column('campaign_id', sa.Integer(), nullable=True),
    sa.Column('message_id', sa.String(length=100), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['campaign_id'], ['campaign.id'], ),
    sa.ForeignKeyConstraint(['contact_id'], ['contact.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for OptOutAudit table
    op.create_index('idx_opt_out_audit_contact', 'opt_out_audit', ['contact_id'], unique=False)
    op.create_index('idx_opt_out_audit_created', 'opt_out_audit', ['created_at'], unique=False)
    op.create_index('idx_opt_out_audit_method', 'opt_out_audit', ['opt_out_method'], unique=False)
    op.create_index('idx_opt_out_audit_phone', 'opt_out_audit', ['phone_number'], unique=False)
    
    # Get the database connection to check dialect
    connection = op.get_bind()
    is_postgresql = connection.dialect.name == 'postgresql'
    
    # Drop all potentially existing indexes using PostgreSQL-specific syntax
    # This avoids transaction aborts on non-existent indexes
    if is_postgresql:
        # Execute all drops in a single batch to avoid transaction issues
        drop_index_commands = [
            # Activity table indexes
            "DROP INDEX IF EXISTS idx_activity_contact",
            "DROP INDEX IF EXISTS idx_activity_conversation_created",
            "DROP INDEX IF EXISTS idx_activity_openphone_id",
            "DROP INDEX IF EXISTS idx_activity_type_created",
            "DROP INDEX IF EXISTS idx_activity_user",
            "DROP INDEX IF EXISTS ix_activity_conversation_created",
            "DROP INDEX IF EXISTS ix_activity_openphone_id",
            "DROP INDEX IF EXISTS ix_activity_type",
            
            # Appointment table indexes
            "DROP INDEX IF EXISTS idx_appointment_date",
            "DROP INDEX IF EXISTS idx_appointment_status",
            
            # Campaign membership indexes
            "DROP INDEX IF EXISTS idx_campaign_membership_sent",
            "DROP INDEX IF EXISTS idx_campaign_membership_status",
            "DROP INDEX IF EXISTS ix_campaign_membership_campaign_status",
            "DROP INDEX IF EXISTS ix_campaign_membership_contact_id",
            
            # Contact table indexes
            "DROP INDEX IF EXISTS idx_contact_email",
            "DROP INDEX IF EXISTS idx_contact_first_name",
            "DROP INDEX IF EXISTS idx_contact_last_name",
            "DROP INDEX IF EXISTS idx_contact_phone_hash",
            "DROP INDEX IF EXISTS ix_contact_phone_hash",
            
            # Contact flag indexes
            "DROP INDEX IF EXISTS idx_contact_flag_type_phone",
            "DROP INDEX IF EXISTS ix_contact_flag_opted_out",
            
            # Conversation indexes
            "DROP INDEX IF EXISTS idx_conversation_contact",
            "DROP INDEX IF EXISTS idx_conversation_phone_number_id",
            "DROP INDEX IF EXISTS ix_conversation_contact_id",
            
            # Failed webhook queue indexes
            "DROP INDEX IF EXISTS idx_failed_webhook_queue_created_at",
            "DROP INDEX IF EXISTS idx_failed_webhook_queue_event_id",
            "DROP INDEX IF EXISTS idx_failed_webhook_queue_event_type",
            "DROP INDEX IF EXISTS idx_failed_webhook_queue_next_retry",
            "DROP INDEX IF EXISTS idx_failed_webhook_queue_resolved",
            
            # Invoice indexes
            "DROP INDEX IF EXISTS idx_invoice_status_due",
            
            # Webhook event indexes
            "DROP INDEX IF EXISTS idx_webhook_event_id",
            "DROP INDEX IF EXISTS idx_webhook_event_contact",
            "DROP INDEX IF EXISTS idx_webhook_event_conversation",
            "DROP INDEX IF EXISTS idx_webhook_event_created",
            "DROP INDEX IF EXISTS idx_webhook_event_processed"
        ]
        
        for cmd in drop_index_commands:
            op.execute(cmd)
    
    # Note: The failed_webhook_queue indexes are already created in migration 5bf30755a98d
    # They use idx_ prefix not ix_ prefix, so we don't need to recreate them
    
    print("✅ Performance indexes created successfully")


def downgrade():
    # Drop OptOutAudit indexes
    op.drop_index('idx_opt_out_audit_phone', table_name='opt_out_audit')
    op.drop_index('idx_opt_out_audit_method', table_name='opt_out_audit')
    op.drop_index('idx_opt_out_audit_created', table_name='opt_out_audit')
    op.drop_index('idx_opt_out_audit_contact', table_name='opt_out_audit')
    
    # Drop OptOutAudit table
    op.drop_table('opt_out_audit')
    
    # Note: Don't drop failed_webhook_queue indexes as they belong to migration 5bf30755a98d