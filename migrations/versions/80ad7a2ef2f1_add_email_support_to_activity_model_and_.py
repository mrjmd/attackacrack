"""Add email support to Activity model and Campaign channel

Revision ID: 80ad7a2ef2f1
Revises: 0244bf8c0fe9
Create Date: 2025-07-29 21:00:45.704598

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '80ad7a2ef2f1'
down_revision = '0244bf8c0fe9'
branch_labels = None
depends_on = None


def upgrade():
    # Add email-specific fields to Activity model
    op.add_column('activity', sa.Column('email_from', sa.String(120), nullable=True))
    op.add_column('activity', sa.Column('email_to', sa.JSON(), nullable=True))  # Array for multiple recipients
    op.add_column('activity', sa.Column('email_cc', sa.JSON(), nullable=True))
    op.add_column('activity', sa.Column('email_bcc', sa.JSON(), nullable=True))
    op.add_column('activity', sa.Column('email_subject', sa.String(200), nullable=True))
    op.add_column('activity', sa.Column('email_thread_id', sa.String(100), nullable=True))
    op.add_column('activity', sa.Column('smartlead_id', sa.String(100), nullable=True))
    
    # Add channel field to Campaign model
    op.add_column('campaign', sa.Column('channel', sa.String(10), nullable=True, server_default='sms'))


def downgrade():
    # Remove email fields from Activity model
    op.drop_column('activity', 'email_from')
    op.drop_column('activity', 'email_to')
    op.drop_column('activity', 'email_cc')
    op.drop_column('activity', 'email_bcc')
    op.drop_column('activity', 'email_subject')
    op.drop_column('activity', 'email_thread_id')
    op.drop_column('activity', 'smartlead_id')
    
    # Remove channel field from Campaign model
    op.drop_column('campaign', 'channel')
