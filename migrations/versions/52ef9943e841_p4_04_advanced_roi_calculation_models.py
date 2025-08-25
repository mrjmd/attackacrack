"""P4-04: Add Advanced ROI Calculation System models

Revision ID: p4_04_roi_calc
Revises: 5b09c0e43fe9
Create Date: 2025-08-25 16:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '52ef9943e841'
down_revision = '93b5f0c0c48d'
branch_labels = None
depends_on = None


def upgrade():
    # Check if we're using PostgreSQL for specific features
    connection = op.get_bind()
    is_postgresql = connection.dialect.name == 'postgresql'
    
    # Create CampaignCost table
    op.create_table('campaign_costs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('campaign_id', sa.Integer(), nullable=False),
        sa.Column('cost_type', sa.String(length=20), nullable=False),
        sa.Column('amount', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('currency', sa.String(length=3), nullable=False, server_default='USD'),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('cost_date', sa.Date(), nullable=False),
        sa.Column('is_shared', sa.Boolean(), nullable=True, server_default='false'),
        sa.Column('allocation_method', sa.String(length=20), nullable=True),
        sa.Column('allocation_details', sa.JSON(), nullable=True),
        sa.Column('created_by', sa.String(length=100), nullable=True),
        sa.Column('approved_by', sa.String(length=100), nullable=True),
        sa.Column('approval_date', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['campaign_id'], ['campaign.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for CampaignCost
    op.create_index('idx_campaign_costs_campaign_id', 'campaign_costs', ['campaign_id'])
    op.create_index('idx_campaign_costs_cost_type', 'campaign_costs', ['cost_type'])
    op.create_index('idx_campaign_costs_cost_date', 'campaign_costs', ['cost_date'])
    op.create_index('idx_campaign_costs_campaign_type', 'campaign_costs', ['campaign_id', 'cost_type'])
    op.create_index('idx_campaign_costs_date_range', 'campaign_costs', ['campaign_id', 'cost_date'])
    op.create_index('idx_campaign_costs_created_at', 'campaign_costs', ['created_at'])
    
    # Add check constraint for positive amounts
    if is_postgresql:
        op.execute("ALTER TABLE campaign_costs ADD CONSTRAINT ck_campaign_costs_amount_positive CHECK (amount >= 0)")
    
    # Create CustomerLifetimeValue table
    op.create_table('customer_lifetime_values',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('contact_id', sa.Integer(), nullable=False),
        sa.Column('calculation_date', sa.Date(), nullable=False),
        sa.Column('total_revenue', sa.Numeric(precision=12, scale=2), nullable=False, server_default='0'),
        sa.Column('total_purchases', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('average_order_value', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('purchase_frequency', sa.Numeric(precision=6, scale=3), nullable=True),
        sa.Column('customer_lifespan_days', sa.Integer(), nullable=True),
        sa.Column('predicted_ltv', sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column('confidence_score', sa.Numeric(precision=4, scale=3), nullable=True),
        sa.Column('prediction_method', sa.String(length=50), nullable=True),
        sa.Column('prediction_horizon_months', sa.Integer(), nullable=True, server_default='24'),
        sa.Column('cohort_month', sa.Date(), nullable=True),
        sa.Column('cohort_segment', sa.String(length=50), nullable=True),
        sa.Column('retention_probability', sa.Numeric(precision=4, scale=3), nullable=True),
        sa.Column('churn_probability', sa.Numeric(precision=4, scale=3), nullable=True),
        sa.Column('last_purchase_date', sa.Date(), nullable=True),
        sa.Column('days_since_last_purchase', sa.Integer(), nullable=True),
        sa.Column('value_tier', sa.String(length=20), nullable=True),
        sa.Column('percentile_rank', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column('calculation_metadata', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['contact_id'], ['contact.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('contact_id', 'calculation_date', name='unique_contact_ltv_date')
    )
    
    # Create indexes for CustomerLifetimeValue
    op.create_index('idx_customer_ltv_contact_id', 'customer_lifetime_values', ['contact_id'])
    op.create_index('idx_customer_ltv_calculation_date', 'customer_lifetime_values', ['calculation_date'])
    op.create_index('idx_customer_ltv_cohort_month', 'customer_lifetime_values', ['cohort_month'])
    op.create_index('idx_customer_ltv_contact_date', 'customer_lifetime_values', ['contact_id', 'calculation_date'])
    op.create_index('idx_customer_ltv_cohort', 'customer_lifetime_values', ['cohort_month', 'value_tier'])
    op.create_index('idx_customer_ltv_value', 'customer_lifetime_values', ['predicted_ltv', 'total_revenue'])
    op.create_index('idx_customer_ltv_created_at', 'customer_lifetime_values', ['created_at'])
    
    # Add check constraints for CustomerLifetimeValue
    if is_postgresql:
        op.execute("ALTER TABLE customer_lifetime_values ADD CONSTRAINT ck_ltv_revenue_positive CHECK (total_revenue >= 0)")
        op.execute("ALTER TABLE customer_lifetime_values ADD CONSTRAINT ck_ltv_purchases_positive CHECK (total_purchases >= 0)")
        op.execute("ALTER TABLE customer_lifetime_values ADD CONSTRAINT ck_ltv_confidence_range CHECK (confidence_score >= 0 AND confidence_score <= 1)")
    
    # Create ROIAnalysis table
    op.create_table('roi_analyses',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('campaign_id', sa.Integer(), nullable=True),
        sa.Column('analysis_date', sa.Date(), nullable=False),
        sa.Column('analysis_type', sa.String(length=20), nullable=False),
        sa.Column('analysis_period_start', sa.Date(), nullable=True),
        sa.Column('analysis_period_end', sa.Date(), nullable=True),
        sa.Column('total_cost', sa.Numeric(precision=12, scale=2), nullable=False, server_default='0'),
        sa.Column('total_revenue', sa.Numeric(precision=12, scale=2), nullable=False, server_default='0'),
        sa.Column('gross_profit', sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column('net_profit', sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column('roi_percentage', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('roas', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('profit_margin', sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column('cac', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('new_customers_acquired', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('ltv_cac_ratio', sa.Numeric(precision=8, scale=2), nullable=True),
        sa.Column('payback_period_days', sa.Integer(), nullable=True),
        sa.Column('break_even_date', sa.Date(), nullable=True),
        sa.Column('break_even_customers', sa.Integer(), nullable=True),
        sa.Column('conversion_rate', sa.Numeric(precision=6, scale=3), nullable=True),
        sa.Column('average_order_value', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('customer_retention_rate', sa.Numeric(precision=6, scale=3), nullable=True),
        sa.Column('segment_criteria', sa.JSON(), nullable=True),
        sa.Column('segment_size', sa.Integer(), nullable=True),
        sa.Column('analysis_metadata', sa.JSON(), nullable=True),
        sa.Column('data_completeness', sa.Numeric(precision=4, scale=3), nullable=True),
        sa.Column('confidence_level', sa.Numeric(precision=4, scale=3), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['campaign_id'], ['campaign.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for ROIAnalysis
    op.create_index('idx_roi_analysis_campaign_id', 'roi_analyses', ['campaign_id'])
    op.create_index('idx_roi_analysis_analysis_date', 'roi_analyses', ['analysis_date'])
    op.create_index('idx_roi_analysis_analysis_type', 'roi_analyses', ['analysis_type'])
    op.create_index('idx_roi_analysis_campaign_date', 'roi_analyses', ['campaign_id', 'analysis_date'])
    op.create_index('idx_roi_analysis_type_date', 'roi_analyses', ['analysis_type', 'analysis_date'])
    op.create_index('idx_roi_analysis_roi', 'roi_analyses', ['roi_percentage', 'roas'])
    op.create_index('idx_roi_analysis_performance', 'roi_analyses', ['campaign_id', 'roi_percentage', 'total_revenue'])
    op.create_index('idx_roi_analysis_created_at', 'roi_analyses', ['created_at'])
    
    # Add check constraints for ROIAnalysis
    if is_postgresql:
        op.execute("ALTER TABLE roi_analyses ADD CONSTRAINT ck_roi_cost_positive CHECK (total_cost >= 0)")
        op.execute("ALTER TABLE roi_analyses ADD CONSTRAINT ck_roi_revenue_positive CHECK (total_revenue >= 0)")
        op.execute("ALTER TABLE roi_analyses ADD CONSTRAINT ck_roi_percentage_min CHECK (roi_percentage IS NULL OR roi_percentage >= -100)")
        op.execute("ALTER TABLE roi_analyses ADD CONSTRAINT ck_roi_roas_positive CHECK (roas IS NULL OR roas >= 0)")
    
    # Note: Removed partial indexes that used CURRENT_DATE as PostgreSQL requires 
    # functions in index predicates to be immutable, and CURRENT_DATE is not immutable.
    # The regular indexes created above provide sufficient query optimization.


def downgrade():
    # Drop tables in reverse order due to foreign key dependencies
    op.drop_table('roi_analyses')
    op.drop_table('customer_lifetime_values')
    op.drop_table('campaign_costs')