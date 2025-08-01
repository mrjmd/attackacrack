"""Add production constraints and fields

Revision ID: production_001
Revises: 
Create Date: 2025-07-31

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'production_001'
down_revision = '66e4d583f188'
branch_labels = None
depends_on = None


def upgrade():
    # Add new fields to contact table
    with op.batch_alter_table('contact', schema=None) as batch_op:
        batch_op.add_column(sa.Column('lead_source', sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column('customer_since', sa.Date(), nullable=True))
    
    # Add property_type to property table
    with op.batch_alter_table('property', schema=None) as batch_op:
        batch_op.add_column(sa.Column('property_type', sa.String(length=50), nullable=True))
    
    # Note: UNIQUE constraints for phone and email already exist in the model


def downgrade():
    # Remove added fields
    with op.batch_alter_table('property', schema=None) as batch_op:
        batch_op.drop_column('property_type')
    
    with op.batch_alter_table('contact', schema=None) as batch_op:
        batch_op.drop_column('customer_since')
        batch_op.drop_column('lead_source')