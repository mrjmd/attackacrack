"""add engagement scoring tables

Revision ID: 5c4bfb64753a
Revises: 88d16698a080
Create Date: 2025-08-24 21:44:10.996933

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = '5c4bfb64753a'
down_revision = '88d16698a080'
branch_labels = None
depends_on = None


def upgrade():
    # Check if we're in PostgreSQL or SQLite
    connection = op.get_bind()
    is_postgresql = connection.dialect.name == 'postgresql'
    
    # Create engagement_events table
    op.create_table('engagement_events',
        sa.Column('id', sa.Integer(), nullable=False),
        
        # Core relationships
        sa.Column('contact_id', sa.Integer(), nullable=False),
        sa.Column('campaign_id', sa.Integer(), nullable=True),
        sa.Column('activity_id', sa.Integer(), nullable=True),
        sa.Column('parent_event_id', sa.Integer(), nullable=True),
        sa.Column('campaign_membership_id', sa.Integer(), nullable=True),
        
        # Event details
        sa.Column('event_type', sa.String(length=20), nullable=False),
        sa.Column('event_timestamp', sa.DateTime(), nullable=False),
        sa.Column('channel', sa.String(length=10), nullable=False),
        
        # Message/Campaign context
        sa.Column('message_id', sa.String(length=100), nullable=True),
        sa.Column('campaign_message_variant', sa.String(length=1), nullable=True),
        
        # Event-specific data
        sa.Column('click_url', sa.String(length=500), nullable=True),
        sa.Column('response_text', sa.Text(), nullable=True),
        sa.Column('response_sentiment', sa.String(length=20), nullable=True),
        
        # Conversion tracking
        sa.Column('conversion_type', sa.String(length=50), nullable=True),
        sa.Column('conversion_value', sa.Numeric(precision=10, scale=2), nullable=True),
        
        # Opt-out tracking
        sa.Column('opt_out_method', sa.String(length=50), nullable=True),
        sa.Column('opt_out_keyword', sa.String(length=20), nullable=True),
        
        # Timestamps
        sa.Column('created_at', sa.DateTime(), nullable=False),
        
        # Primary key and foreign keys
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['contact_id'], ['contact.id'], ),
        sa.ForeignKeyConstraint(['campaign_id'], ['campaign.id'], ),
        sa.ForeignKeyConstraint(['activity_id'], ['activity.id'], ),
        sa.ForeignKeyConstraint(['parent_event_id'], ['engagement_events.id'], ),
        sa.ForeignKeyConstraint(['campaign_membership_id'], ['campaign_membership.id'], )
    )
    
    # Add JSON columns based on database type
    if is_postgresql:
        op.add_column('engagement_events', sa.Column('event_metadata', postgresql.JSONB(), nullable=True))
        op.add_column('engagement_events', sa.Column('device_info', postgresql.JSONB(), nullable=True))
    else:
        op.add_column('engagement_events', sa.Column('event_metadata', sa.Text(), nullable=True))
        op.add_column('engagement_events', sa.Column('device_info', sa.Text(), nullable=True))
    
    # Create indexes for engagement_events table
    op.create_index('ix_engagement_events_contact_id', 'engagement_events', ['contact_id'])
    op.create_index('ix_engagement_events_campaign_id', 'engagement_events', ['campaign_id'])
    op.create_index('ix_engagement_events_event_type', 'engagement_events', ['event_type'])
    op.create_index('ix_engagement_events_event_timestamp', 'engagement_events', ['event_timestamp'])
    op.create_index('ix_engagement_events_channel', 'engagement_events', ['channel'])
    op.create_index('ix_engagement_events_message_id', 'engagement_events', ['message_id'])
    op.create_index('ix_engagement_events_created_at', 'engagement_events', ['created_at'])
    
    # Composite indexes for performance
    op.create_index('idx_engagement_events_contact_time', 'engagement_events', ['contact_id', 'event_timestamp'])
    op.create_index('idx_engagement_events_campaign_time', 'engagement_events', ['campaign_id', 'event_timestamp'])
    op.create_index('idx_engagement_events_type_time', 'engagement_events', ['event_type', 'event_timestamp'])
    
    # Create engagement_scores table
    op.create_table('engagement_scores',
        sa.Column('id', sa.Integer(), nullable=False),
        
        # Core relationships
        sa.Column('contact_id', sa.Integer(), nullable=False),
        sa.Column('campaign_id', sa.Integer(), nullable=True),
        
        # Primary scores (0-100 scale)
        sa.Column('overall_score', sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column('recency_score', sa.Numeric(precision=5, scale=2), nullable=False, server_default='0'),
        sa.Column('frequency_score', sa.Numeric(precision=5, scale=2), nullable=False, server_default='0'),
        sa.Column('monetary_score', sa.Numeric(precision=5, scale=2), nullable=False, server_default='0'),
        
        # Advanced scoring components
        sa.Column('engagement_diversity_score', sa.Numeric(precision=5, scale=2), nullable=True, server_default='0'),
        sa.Column('time_decay_score', sa.Numeric(precision=5, scale=2), nullable=True, server_default='0'),
        sa.Column('negative_events_penalty', sa.Numeric(precision=5, scale=2), nullable=True, server_default='0'),
        
        # Predictive metrics
        sa.Column('engagement_probability', sa.Numeric(precision=4, scale=3), nullable=False, server_default='0'),
        sa.Column('conversion_probability', sa.Numeric(precision=4, scale=3), nullable=True, server_default='0'),
        sa.Column('churn_risk_score', sa.Numeric(precision=5, scale=2), nullable=True, server_default='0'),
        
        # Percentile rankings (calculated relative to campaign)
        sa.Column('overall_percentile', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column('recency_percentile', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column('frequency_percentile', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column('monetary_percentile', sa.Numeric(precision=5, scale=2), nullable=True),
        
        # Metadata
        sa.Column('score_version', sa.String(length=10), nullable=False, server_default='1.0'),
        sa.Column('calculation_method', sa.String(length=50), nullable=True),
        sa.Column('confidence_level', sa.Numeric(precision=4, scale=3), nullable=True),
        sa.Column('score_type', sa.String(length=20), nullable=True),  # 'recency', 'frequency', 'monetary', 'composite'
        
        # Event statistics (cached for performance)
        sa.Column('total_events_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('positive_events_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('negative_events_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_event_timestamp', sa.DateTime(), nullable=True),
        sa.Column('first_event_timestamp', sa.DateTime(), nullable=True),
        
        # Timestamps
        sa.Column('calculated_at', sa.DateTime(), nullable=False),
        sa.Column('calculation_date', sa.Date(), nullable=True),  # For unique constraints
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        
        # Primary key and foreign keys
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['contact_id'], ['contact.id'], ),
        sa.ForeignKeyConstraint(['campaign_id'], ['campaign.id'], )
    )
    
    # Add JSON column based on database type
    if is_postgresql:
        op.add_column('engagement_scores', sa.Column('score_metadata', postgresql.JSONB(), nullable=True))
    else:
        op.add_column('engagement_scores', sa.Column('score_metadata', sa.Text(), nullable=True))
    
    # Create indexes for engagement_scores table
    op.create_index('ix_engagement_scores_contact_id', 'engagement_scores', ['contact_id'])
    op.create_index('ix_engagement_scores_campaign_id', 'engagement_scores', ['campaign_id'])
    op.create_index('ix_engagement_scores_overall_score', 'engagement_scores', ['overall_score'])
    op.create_index('ix_engagement_scores_calculated_at', 'engagement_scores', ['calculated_at'])
    
    # Composite indexes for performance
    op.create_index('idx_engagement_scores_contact_date', 'engagement_scores', ['contact_id', 'calculated_at'])
    op.create_index('idx_engagement_scores_campaign_date', 'engagement_scores', ['campaign_id', 'calculated_at'])
    
    # Unique constraint for one score per contact-campaign-type-date combination
    # This allows multiple score types per contact-campaign but only one of each type per calculation date
    with op.batch_alter_table('engagement_scores') as batch_op:
        batch_op.create_unique_constraint(
            'uq_engagement_scores_contact_campaign_type_date',
            ['contact_id', 'campaign_id', 'score_type', 'calculation_date']
        )
    
    # PostgreSQL-specific features
    if is_postgresql:
        # Create GIN index for JSONB metadata fields for faster searching
        op.execute("""
            CREATE INDEX IF NOT EXISTS idx_engagement_events_metadata_gin 
            ON engagement_events USING gin(event_metadata)
        """)
        
        op.execute("""
            CREATE INDEX IF NOT EXISTS idx_engagement_scores_metadata_gin 
            ON engagement_scores USING gin(score_metadata)
        """)
        
        # Add check constraints for valid values
        op.execute("""
            ALTER TABLE engagement_events 
            ADD CONSTRAINT ck_engagement_events_event_type 
            CHECK (event_type IN ('delivered', 'opened', 'clicked', 'responded', 'converted', 'opted_out', 'bounced'))
        """)
        
        op.execute("""
            ALTER TABLE engagement_events 
            ADD CONSTRAINT ck_engagement_events_channel 
            CHECK (channel IN ('sms', 'email', 'call'))
        """)
        
        op.execute("""
            ALTER TABLE engagement_scores 
            ADD CONSTRAINT ck_engagement_scores_probability 
            CHECK (engagement_probability >= 0 AND engagement_probability <= 1)
        """)
        
        op.execute("""
            ALTER TABLE engagement_scores 
            ADD CONSTRAINT ck_engagement_scores_conversion_prob 
            CHECK (conversion_probability IS NULL OR (conversion_probability >= 0 AND conversion_probability <= 1))
        """)
        
        op.execute("""
            ALTER TABLE engagement_scores 
            ADD CONSTRAINT ck_engagement_scores_percentiles 
            CHECK (
                (overall_percentile IS NULL OR (overall_percentile >= 0 AND overall_percentile <= 100)) AND
                (recency_percentile IS NULL OR (recency_percentile >= 0 AND recency_percentile <= 100)) AND
                (frequency_percentile IS NULL OR (frequency_percentile >= 0 AND frequency_percentile <= 100)) AND
                (monetary_percentile IS NULL OR (monetary_percentile >= 0 AND monetary_percentile <= 100))
            )
        """)


def downgrade():
    # Drop tables in reverse order to handle foreign key dependencies
    op.drop_table('engagement_scores')
    op.drop_table('engagement_events')