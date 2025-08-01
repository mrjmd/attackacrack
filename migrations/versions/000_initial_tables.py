"""Create initial base tables

Revision ID: 000_initial_tables
Revises: 
Create Date: 2025-08-01

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '000_initial_tables'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Create contact table first (no foreign keys)
    op.create_table('contact',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('first_name', sa.String(length=50), nullable=False),
        sa.Column('last_name', sa.String(length=50), nullable=False),
        sa.Column('email', sa.String(length=120), nullable=True),
        sa.Column('phone', sa.String(length=20), nullable=True),
        sa.Column('contact_metadata', sa.JSON(), nullable=True),
        sa.Column('csv_import_id', sa.Integer(), nullable=True),
        sa.Column('import_source', sa.String(length=100), nullable=True),
        sa.Column('imported_at', sa.DateTime(), nullable=True),
        sa.Column('quickbooks_customer_id', sa.String(length=50), nullable=True),
        sa.Column('quickbooks_sync_token', sa.String(length=50), nullable=True),
        sa.Column('customer_type', sa.String(length=20), nullable=True),
        sa.Column('payment_terms', sa.String(length=50), nullable=True),
        sa.Column('credit_limit', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('tax_exempt', sa.Boolean(), nullable=True),
        sa.Column('total_sales', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('outstanding_balance', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('last_sync_date', sa.DateTime(), nullable=True),
        sa.Column('marketing_consent', sa.Boolean(), nullable=True),
        sa.Column('consent_date', sa.DateTime(), nullable=True),
        sa.Column('consent_method', sa.String(length=50), nullable=True),
        sa.Column('unsubscribed', sa.Boolean(), nullable=True),
        sa.Column('unsubscribe_date', sa.DateTime(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('deactivated_at', sa.DateTime(), nullable=True),
        sa.Column('reactivated_at', sa.DateTime(), nullable=True),
        sa.Column('do_not_contact', sa.Boolean(), nullable=True),
        sa.Column('bounce_count', sa.Integer(), nullable=True),
        sa.Column('last_bounce_date', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email'),
        sa.UniqueConstraint('phone'),
        sa.UniqueConstraint('quickbooks_customer_id')
    )
    
    # Create conversation table (depends on contact)
    op.create_table('conversation',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('openphone_id', sa.String(length=100), nullable=True),
        sa.Column('contact_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=True),
        sa.Column('participants', sa.String(length=500), nullable=True),
        sa.Column('phone_number_id', sa.String(length=100), nullable=True),
        sa.Column('last_activity_at', sa.DateTime(), nullable=True),
        sa.Column('last_activity_type', sa.String(length=20), nullable=True),
        sa.Column('last_activity_id', sa.String(length=100), nullable=True),
        sa.ForeignKeyConstraint(['contact_id'], ['contact.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('openphone_id')
    )
    
    # Create activity table (depends on conversation and contact)
    op.create_table('activity',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('openphone_id', sa.String(length=100), nullable=True),
        sa.Column('conversation_id', sa.Integer(), nullable=True),
        sa.Column('contact_id', sa.Integer(), nullable=True),
        sa.Column('activity_type', sa.String(length=20), nullable=True),
        sa.Column('direction', sa.String(length=10), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=True),
        sa.Column('from_number', sa.String(length=20), nullable=True),
        sa.Column('to_numbers', sa.JSON(), nullable=True),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('phone_number_id', sa.String(length=100), nullable=True),
        sa.Column('body', sa.Text(), nullable=True),
        sa.Column('media_urls', sa.JSON(), nullable=True),
        sa.Column('email_from', sa.String(length=120), nullable=True),
        sa.Column('email_to', sa.JSON(), nullable=True),
        sa.Column('email_cc', sa.JSON(), nullable=True),
        sa.Column('email_bcc', sa.JSON(), nullable=True),
        sa.Column('email_subject', sa.String(length=200), nullable=True),
        sa.Column('email_thread_id', sa.String(length=100), nullable=True),
        sa.Column('smartlead_id', sa.String(length=100), nullable=True),
        sa.Column('email_html_body', sa.Text(), nullable=True),
        sa.Column('email_attachments', sa.JSON(), nullable=True),
        sa.Column('duration_seconds', sa.Integer(), nullable=True),
        sa.Column('answered_at', sa.DateTime(), nullable=True),
        sa.Column('answered_by', sa.String(length=100), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('initiated_by', sa.String(length=100), nullable=True),
        sa.Column('forwarded_from', sa.String(length=100), nullable=True),
        sa.Column('forwarded_to', sa.String(length=100), nullable=True),
        sa.Column('ai_summary', sa.Text(), nullable=True),
        sa.Column('ai_next_steps', sa.Text(), nullable=True),
        sa.Column('ai_transcript', sa.JSON(), nullable=True),
        sa.Column('ai_content_status', sa.String(length=50), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['contact_id'], ['contact.id'], ),
        sa.ForeignKeyConstraint(['conversation_id'], ['conversation.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('openphone_id')
    )
    
    # Create csv_import table (needed for contact foreign key)
    op.create_table('csv_import',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('filename', sa.String(length=255), nullable=False),
        sa.Column('imported_at', sa.DateTime(), nullable=True),
        sa.Column('row_count', sa.Integer(), nullable=True),
        sa.Column('import_metadata', sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Add foreign key constraint to contact table
    op.create_foreign_key(None, 'contact', 'csv_import', ['csv_import_id'], ['id'])


def downgrade():
    op.drop_constraint(None, 'contact', type_='foreignkey')
    op.drop_table('csv_import')
    op.drop_table('activity')
    op.drop_table('conversation')
    op.drop_table('contact')