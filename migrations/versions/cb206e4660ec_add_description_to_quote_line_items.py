"""Add description to quote line items

Revision ID: cb206e4660ec
Revises: adddb699905f
Create Date: 2025-07-24 14:09:44.657670

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'cb206e4660ec'
down_revision = 'adddb699905f'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('quote_line_item', schema=None) as batch_op:
        batch_op.add_column(sa.Column('description', sa.Text(), nullable=False))
        batch_op.alter_column('product_service_id',
               existing_type=sa.INTEGER(),
               nullable=True)

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('quote_line_item', schema=None) as batch_op:
        batch_op.alter_column('product_service_id',
               existing_type=sa.INTEGER(),
               nullable=False)
        batch_op.drop_column('description')

    # ### end Alembic commands ###
