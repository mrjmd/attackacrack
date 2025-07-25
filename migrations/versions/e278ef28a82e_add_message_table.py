"""Add message table

Revision ID: e278ef28a82e
Revises: cb74241e1dea
Create Date: 2025-07-24 09:33:39.647797

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e278ef28a82e'
down_revision = 'cb74241e1dea'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('message',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('openphone_id', sa.String(length=100), nullable=False),
    sa.Column('contact_id', sa.Integer(), nullable=False),
    sa.Column('body', sa.Text(), nullable=True),
    sa.Column('direction', sa.String(length=10), nullable=False),
    sa.Column('timestamp', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['contact_id'], ['contact.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('openphone_id')
    )
    with op.batch_alter_table('contact', schema=None) as batch_op:
        batch_op.create_unique_constraint(None, ['phone'])

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('contact', schema=None) as batch_op:
        batch_op.drop_constraint(None, type_='unique')

    op.drop_table('message')
    # ### end Alembic commands ###
