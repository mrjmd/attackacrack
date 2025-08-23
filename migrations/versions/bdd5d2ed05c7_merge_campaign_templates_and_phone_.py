"""Merge campaign templates and phone validation

Revision ID: bdd5d2ed05c7
Revises: add_campaign_templates, add_phone_validation
Create Date: 2025-08-23 02:09:55.499340

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'bdd5d2ed05c7'
down_revision = ('add_campaign_templates', 'add_phone_validation')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
