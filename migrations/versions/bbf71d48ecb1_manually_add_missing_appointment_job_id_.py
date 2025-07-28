"""Manually add missing Appointment job_id, Conversation, and Activity schema

Revision ID: bbf71d48ecb1
Revises: 0a8914f5fe62
Create Date: 2025-07-27 18:58:47.841887

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'bbf71d48ecb1'
down_revision = '83d517a98249'
branch_labels = None
depends_on = None

def upgrade():
    # ### Start manual commands ###
    conn = op.get_bind() # Get connection object once at the beginning

    # 1. Attempt to create the foreign key for appointment.job_id
    # This column is confirmed to exist, but the FK might not if previous transactions aborted.
    try:
        with op.batch_alter_table('appointment', schema=None) as batch_op:
            batch_op.create_foreign_key('fk_appointment_job_id', 'job', ['job_id'], ['id'])
        print("Attempted to create foreign key for appointment.job_id.")
    except Exception as e:
        print(f"Warning: Could not create foreign key 'fk_appointment_job_id' on appointment. It might already exist or conflict. Error: {e}")


    # 2. Create Conversation table (only if it doesn't exist)
    # This block is now correctly conditional
    if not conn.dialect.has_table(conn, 'conversation'):
        op.create_table('conversation',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('openphone_id', sa.String(length=100), nullable=True, unique=True),
            sa.Column('contact_id', sa.Integer(), nullable=False),
            sa.Column('participants', sa.String(length=500), nullable=True),
            sa.Column('last_activity_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['contact_id'], ['contact.id'], ),
            sa.PrimaryKeyConstraint('id')
        )
        print("Created 'conversation' table.")
    else:
        print("'conversation' table already exists. Skipping creation.")


    # 3. Rename 'message' table to 'activity' and add new columns to 'activity'
    # Check if 'message' table exists to rename it
    if conn.dialect.has_table(conn, 'message'):
        op.rename_table('message', 'activity')
        print("Renamed 'message' table to 'activity'.")
    else:
        print("'message' table does not exist. Proceeding to ensure 'activity' table structure.")
        # If 'message' table doesn't exist, but 'activity' also doesn't, create 'activity'.
        if not conn.dialect.has_table(conn, 'activity'):
            op.create_table('activity',
                sa.Column('id', sa.Integer(), nullable=False),
                sa.Column('conversation_id', sa.Integer(), nullable=False),
                sa.Column('openphone_id', sa.String(length=100), nullable=False, unique=True),
                sa.Column('direction', sa.String(length=10), nullable=False),
                sa.Column('body', sa.Text(), nullable=True),
                sa.Column('created_at', sa.DateTime(), nullable=True),
                sa.ForeignKeyConstraint(['conversation_id'], ['conversation.id'], ),
                sa.PrimaryKeyConstraint('id')
            )
            print("Created 'activity' table (as 'message' was not found for rename).")

    # Add new columns to 'activity' table using batch_alter_table
    # Reflect the 'activity' table to check for existing columns
    from sqlalchemy import Table, Column
    activity_table_reflected = Table('activity', sa.MetaData(), autoload_with=conn)

    with op.batch_alter_table('activity', schema=None) as batch_op:
        # Add 'type' column
        if 'type' not in activity_table_reflected.columns:
            batch_op.add_column(sa.Column('type', sa.String(length=20), nullable=False, server_default='message'))
            print("Added 'type' column to 'activity'.")
        else:
            print("'type' column already exists in 'activity'.")

        # Add 'status' column
        if 'status' not in activity_table_reflected.columns:
            batch_op.add_column(sa.Column('status', sa.String(length=50), nullable=True))
            print("Added 'status' column to 'activity'.")
        else:
            print("'status' column already exists in 'activity'.")

        # Add 'duration' column
        if 'duration' not in activity_table_reflected.columns:
            batch_op.add_column(sa.Column('duration', sa.Integer(), nullable=True))
            print("Added 'duration' column to 'activity'.")
        else:
            print("'duration' column already exists in 'activity'.")

        # Add 'recording_url' column
        if 'recording_url' not in activity_table_reflected.columns:
            batch_op.add_column(sa.Column('recording_url', sa.String(length=500), nullable=True))
            print("Added 'recording_url' column to 'activity'.")
        else:
            print("'recording_url' column already exists in 'activity'.")

        # Add 'voicemail_url' column
        if 'voicemail_url' not in activity_table_reflected.columns:
            batch_op.add_column(sa.Column('voicemail_url', sa.String(length=500), nullable=True))
            print("Added 'voicemail_url' column to 'activity'.")
        else:
            print("'voicemail_url' column already exists in 'activity'.")
        
        # Handle timestamp to created_at migration
        # Add 'created_at' if it doesn't exist
        if 'created_at' not in activity_table_reflected.columns:
            batch_op.add_column(sa.Column('created_at', sa.DateTime(), nullable=True))
            print("Attempted to add 'created_at' column to 'activity'.")
        else:
            print("'created_at' column already exists in 'activity'.")

    # Perform data migration for timestamp to created_at and drop timestamp
    activity_table_final_check = Table('activity', sa.MetaData(), autoload_with=conn)

    if 'timestamp' in activity_table_final_check.columns and 'created_at' in activity_table_final_check.columns:
        print("Migrating 'timestamp' to 'created_at' in 'activity' table...")
        op.execute(text("UPDATE activity SET created_at = timestamp WHERE created_at IS NULL"))
        with op.batch_alter_table('activity', schema=None) as batch_op:
            batch_op.drop_column('timestamp')
        print("Migrated 'timestamp' to 'created_at' and dropped 'timestamp'.")
    elif 'timestamp' in activity_table_final_check.columns and 'created_at' not in activity_table_final_check.columns:
        print("Warning: 'timestamp' exists but 'created_at' does not. Adding 'created_at' as fallback.")
        with op.batch_alter_table('activity', schema=None) as batch_op:
            batch_op.add_column(sa.Column('created_at', sa.DateTime(), nullable=True))
        op.execute(text("UPDATE activity SET created_at = timestamp WHERE created_at IS NULL"))
        with op.batch_alter_table('activity', schema=None) as batch_op:
            batch_op.drop_column('timestamp')
        print("Added 'created_at', migrated data, and dropped 'timestamp'.")
    else:
        print("Timestamp to created_at migration not needed or already done.")


    # 4. Update foreign key on 'media_attachment'
    media_attachment_table_reflected = sa.Table('media_attachment', sa.MetaData(), autoload_with=conn)

    # Rename 'message_id' to 'activity_id' if 'message_id' exists
    if 'message_id' in media_attachment_table_reflected.columns:
        op.alter_column('media_attachment', 'message_id', new_column_name='activity_id', existing_type=sa.Integer(), nullable=False)
        print("Renamed 'media_attachment.message_id' to 'activity_id'.")
    else:
        print("'media_attachment.message_id' column does not exist. Assuming 'activity_id' is already present.")
    
    # Add the foreign key constraint to activity.id if it doesn't exist
    try:
        with op.batch_alter_table('media_attachment', schema=None) as batch_op:
            batch_op.create_foreign_key('fk_media_attachment_activity_id', 'activity', ['activity_id'], ['id'])
        print("Added foreign key to 'media_attachment.activity_id'.")
    except Exception as e:
        print(f"Warning: Could not create foreign key on media_attachment. It might already exist or conflict. Error: {e}")


    # ### End manual commands ###


def downgrade():
    # ### Start manual commands for downgrade ###

    # 1. Drop foreign key from Appointment
    try:
        with op.batch_alter_table('appointment', schema=None) as batch_op:
            batch_op.drop_constraint('fk_appointment_job_id', type_='foreignkey')
    except Exception as e:
        print(f"Warning: Could not drop FK 'fk_appointment_job_id' from appointment during downgrade. Error: {e}")


    # 2. Drop Conversation table
    op.drop_table('conversation')

    # 3. Revert 'activity' to 'message' and drop new columns
    with op.batch_alter_table('activity', schema=None) as batch_op:
        batch_op.drop_column('voicemail_url')
        batch_op.drop_column('recording_url')
        batch_op.drop_column('duration')
        batch_op.drop_column('status')
        batch_op.drop_column('type')
        # Re-add timestamp and drop created_at
        batch_op.add_column(sa.Column('timestamp', sa.DateTime(), nullable=True))
        batch_op.drop_column('created_at')

    op.rename_table('activity', 'message')

    # 4. Revert foreign key on 'media_attachment'
    try:
        with op.batch_alter_table('media_attachment', schema=None) as batch_op:
            batch_op.drop_constraint('fk_media_attachment_activity_id', type_='foreignkey')
    except Exception as e:
        print(f"Warning: Could not drop FK on media_attachment during downgrade. Error: {e}")
    
    op.alter_column('media_attachment', 'activity_id', new_column_name='message_id', existing_type=sa.Integer(), nullable=False)
