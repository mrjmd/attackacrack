"""Add campaign_templates and ab_test_result tables

Revision ID: add_campaign_templates
Revises: bc1952ff7326
Create Date: 2025-08-23 10:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_campaign_templates'
down_revision = 'bc1952ff7326'
branch_labels = None
depends_on = None


def upgrade():
    # Check if campaign_templates table exists
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()
    
    if 'campaign_templates' not in existing_tables:
        # Create campaign_templates table
        op.create_table('campaign_templates',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('name', sa.String(length=200), nullable=False),
            sa.Column('content', sa.Text(), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('category', sa.String(length=50), nullable=False),
            sa.Column('variables', sa.JSON(), nullable=True),
            sa.Column('status', sa.String(length=20), nullable=False),
            sa.Column('version', sa.Integer(), nullable=False, default=1),
            sa.Column('parent_id', sa.Integer(), nullable=True),
            sa.Column('is_active', sa.Boolean(), nullable=True, default=True),
            sa.Column('usage_count', sa.Integer(), nullable=True, default=0),
            sa.Column('last_used_at', sa.DateTime(), nullable=True),
            sa.Column('approved_by', sa.String(length=100), nullable=True),
            sa.Column('approved_at', sa.DateTime(), nullable=True),
            sa.Column('archived_at', sa.DateTime(), nullable=True),
            sa.Column('activated_at', sa.DateTime(), nullable=True),
            sa.Column('created_by', sa.String(length=100), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['parent_id'], ['campaign_templates.id'], ),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('name')
        )
        
        # Create indexes for campaign_templates
        op.create_index('ix_campaign_templates_category', 'campaign_templates', ['category'], unique=False)
        op.create_index('ix_campaign_templates_status', 'campaign_templates', ['status'], unique=False)
        op.create_index('ix_campaign_templates_is_active', 'campaign_templates', ['is_active'], unique=False)
        op.create_index('ix_campaign_templates_parent_id', 'campaign_templates', ['parent_id'], unique=False)
    
    # Create ab_test_result table if it doesn't exist
    if 'ab_test_result' not in existing_tables:
        op.create_table('ab_test_result',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('campaign_id', sa.Integer(), nullable=False),
            sa.Column('contact_id', sa.Integer(), nullable=False),
            sa.Column('variant', sa.String(length=10), nullable=False),
            sa.Column('template_content', sa.Text(), nullable=True),
            sa.Column('assigned_at', sa.DateTime(), nullable=False),
            sa.Column('message_sent', sa.Boolean(), nullable=True, default=False),
            sa.Column('sent_at', sa.DateTime(), nullable=True),
            sa.Column('message_opened', sa.Boolean(), nullable=True, default=False),
            sa.Column('opened_at', sa.DateTime(), nullable=True),
            sa.Column('link_clicked', sa.Boolean(), nullable=True, default=False),
            sa.Column('clicked_at', sa.DateTime(), nullable=True),
            sa.Column('response_received', sa.Boolean(), nullable=True, default=False),
            sa.Column('responded_at', sa.DateTime(), nullable=True),
            sa.Column('response_sentiment', sa.String(length=20), nullable=True),
            sa.Column('conversion_value', sa.Numeric(10, 2), nullable=True),
            sa.Column('error_message', sa.Text(), nullable=True),
            sa.Column('metadata', sa.JSON(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['campaign_id'], ['campaign.id'], ),
            sa.ForeignKeyConstraint(['contact_id'], ['contact.id'], ),
            sa.PrimaryKeyConstraint('id')
        )
        
        # Create indexes for ab_test_result
        op.create_index('idx_ab_test_assigned_at', 'ab_test_result', ['assigned_at'], unique=False)
        op.create_index('idx_ab_test_campaign_variant', 'ab_test_result', ['campaign_id', 'variant'], unique=False)
        op.create_index('idx_ab_test_performance', 'ab_test_result', ['campaign_id', 'variant', 'message_sent', 'response_received'], unique=False)
        op.create_index('ix_ab_test_result_assigned_at', 'ab_test_result', ['assigned_at'], unique=False)
        op.create_index('ix_ab_test_result_campaign_id', 'ab_test_result', ['campaign_id'], unique=False)
        op.create_index('ix_ab_test_result_contact_id', 'ab_test_result', ['contact_id'], unique=False)
        op.create_index('ix_ab_test_result_link_clicked', 'ab_test_result', ['link_clicked'], unique=False)
        op.create_index('ix_ab_test_result_message_opened', 'ab_test_result', ['message_opened'], unique=False)
        op.create_index('ix_ab_test_result_message_sent', 'ab_test_result', ['message_sent'], unique=False)
        op.create_index('ix_ab_test_result_response_received', 'ab_test_result', ['response_received'], unique=False)
        op.create_index('ix_ab_test_result_variant', 'ab_test_result', ['variant'], unique=False)


def downgrade():
    # Get current table list
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()
    
    # Drop ab_test_result table and indexes if it exists
    if 'ab_test_result' in existing_tables:
        # Get existing indexes for the table
        existing_indexes = [idx['name'] for idx in inspector.get_indexes('ab_test_result')]
        
        # Drop indexes that exist
        for index_name in ['ix_ab_test_result_variant', 'ix_ab_test_result_response_received',
                          'ix_ab_test_result_message_sent', 'ix_ab_test_result_message_opened',
                          'ix_ab_test_result_link_clicked', 'ix_ab_test_result_contact_id',
                          'ix_ab_test_result_campaign_id', 'ix_ab_test_result_assigned_at',
                          'idx_ab_test_performance', 'idx_ab_test_campaign_variant',
                          'idx_ab_test_assigned_at']:
            if index_name in existing_indexes:
                op.drop_index(index_name, table_name='ab_test_result')
        
        op.drop_table('ab_test_result')
    
    # Drop campaign_templates table and indexes if it exists
    if 'campaign_templates' in existing_tables:
        # Get existing indexes for the table
        existing_indexes = [idx['name'] for idx in inspector.get_indexes('campaign_templates')]
        
        # Drop indexes that exist
        for index_name in ['ix_campaign_templates_parent_id', 'ix_campaign_templates_is_active',
                          'ix_campaign_templates_status', 'ix_campaign_templates_category']:
            if index_name in existing_indexes:
                op.drop_index(index_name, table_name='campaign_templates')
        
        op.drop_table('campaign_templates')