"""Create conversation and activity tables

Revision ID: 13618c8f8334
Revises: 5b88747384d3
Create Date: 2025-07-26 19:15:23.456789

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '13618c8f8334' # This will be different for you, but it's okay.
down_revision = '5b88747384d3' # This should match the previous migration file.
branch_labels = None
depends_on = None


def upgrade():
    # ### Manually Edited Migration ###

    # Step 1: Create the new 'conversation' table
    op.create_table('conversation',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('openphone_id', sa.String(length=100), nullable=True),
        sa.Column('contact_id', sa.Integer(), nullable=False),
        sa.Column('participants', sa.String(length=500), nullable=True),
        sa.Column('last_activity_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['contact_id'], ['contact.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('openphone_id')
    )

    # Step 2: Rename the 'message' table to 'activity'
    op.rename_table('message', 'activity')

    # Step 3: Add and modify columns on the new 'activity' table
    with op.batch_alter_table('activity', schema=None) as batch_op:
        batch_op.add_column(sa.Column('conversation_id', sa.Integer(), nullable=True)) # Allow null temporarily
        batch_op.add_column(sa.Column('type', sa.String(length=20), nullable=False, server_default='message'))
        batch_op.add_column(sa.Column('status', sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column('duration', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('recording_url', sa.String(length=500), nullable=True))
        batch_op.add_column(sa.Column('voicemail_url', sa.String(length=500), nullable=True))
        batch_op.alter_column('timestamp', new_column_name='created_at')

    # Step 4: Drop the old foreign key from 'media_attachment'
    with op.batch_alter_table('media_attachment', schema=None) as batch_op:
        batch_op.drop_constraint('media_attachment_message_id_fkey', type_='foreignkey')
        batch_op.alter_column('message_id', new_column_name='activity_id')
        
    # Step 5: Create the new foreign key from 'media_attachment' to 'activity'
    with op.batch_alter_table('media_attachment', schema=None) as batch_op:
        batch_op.create_foreign_key('fk_activity', 'activity', ['activity_id'], ['id'])
        
    # Step 6: Create the new foreign key from 'activity' to 'conversation'
    # This assumes a simple data migration where we create one conversation per contact.
    # A more complex migration would be needed to preserve threads, but this is safe for an empty DB.
    op.execute("""
        INSERT INTO conversation (contact_id, last_activity_at)
        SELECT DISTINCT contact_id, MAX(created_at)
        FROM activity
        GROUP BY contact_id;
    """)
    op.execute("""
        UPDATE activity a
        SET conversation_id = c.id
        FROM conversation c
        WHERE a.contact_id = c.contact_id;
    """)
    
    # Finally, make the conversation_id not nullable
    with op.batch_alter_table('activity', schema=None) as batch_op:
        batch_op.alter_column('conversation_id', nullable=False)
        batch_op.create_foreign_key('fk_conversation', 'conversation', ['conversation_id'], ['id'])
        batch_op.drop_constraint('message_contact_id_fkey', type_='foreignkey')
        batch_op.drop_column('contact_id')

    # ### end Alembic commands ###


def downgrade():
    # Downgrade logic would be the reverse of the above, but is complex
    # and not needed for our forward progress.
    pass