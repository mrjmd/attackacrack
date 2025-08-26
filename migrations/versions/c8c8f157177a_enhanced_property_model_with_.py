"""Enhanced Property model with PropertyRadar fields and many-to-many Contact relationship

Revision ID: c8c8f157177a
Revises: bdeba4e238ad
Create Date: 2025-08-26 11:37:10.829450

This migration enhances the Property model to support PropertyRadar imports with:
1. All PropertyRadar fields (42+ fields)
2. Many-to-many relationship with Contact via PropertyContact association
3. Proper indexes for performance
4. Zero-downtime migration approach
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'c8c8f157177a'
down_revision = 'bdeba4e238ad'
branch_labels = None
depends_on = None


def upgrade():
    """
    Enhance Property table with PropertyRadar fields and create many-to-many Contact relationship.
    This is a zero-downtime migration that preserves existing data.
    """
    
    # Phase 1: Create PropertyContact association table
    op.create_table('property_contact',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('property_id', sa.Integer(), nullable=False),
        sa.Column('contact_id', sa.Integer(), nullable=False),
        sa.Column('relationship_type', sa.String(20), nullable=True),  # 'owner', 'tenant', 'agent', etc.
        sa.Column('ownership_percentage', sa.Numeric(5, 2), nullable=True),  # For fractional ownership
        sa.Column('is_primary', sa.Boolean(), default=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=True, onupdate=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['contact_id'], ['contact.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['property_id'], ['property.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('property_id', 'contact_id', name='uq_property_contact')
    )
    
    # Create indexes for PropertyContact
    op.create_index('ix_property_contact_property_id', 'property_contact', ['property_id'])
    op.create_index('ix_property_contact_contact_id', 'property_contact', ['contact_id'])
    op.create_index('ix_property_contact_relationship', 'property_contact', ['relationship_type'])
    
    # Phase 2: Add new columns to Property table (all nullable initially for zero-downtime)
    
    # Geographic fields
    op.add_column('property', sa.Column('city', sa.String(100), nullable=True))
    op.add_column('property', sa.Column('state', sa.String(2), nullable=True))
    op.add_column('property', sa.Column('zip_code', sa.String(10), nullable=True))
    op.add_column('property', sa.Column('subdivision', sa.String(100), nullable=True))
    op.add_column('property', sa.Column('longitude', sa.Numeric(10, 7), nullable=True))
    op.add_column('property', sa.Column('latitude', sa.Numeric(10, 7), nullable=True))
    
    # Property identifiers
    op.add_column('property', sa.Column('apn', sa.String(100), nullable=True))  # Assessor Parcel Number
    
    # Property details
    op.add_column('property', sa.Column('year_built', sa.Integer(), nullable=True))
    op.add_column('property', sa.Column('square_feet', sa.Integer(), nullable=True))
    op.add_column('property', sa.Column('bedrooms', sa.Integer(), nullable=True))
    op.add_column('property', sa.Column('bathrooms', sa.Numeric(3, 1), nullable=True))
    
    # Financial fields
    op.add_column('property', sa.Column('assessed_value', sa.Numeric(12, 2), nullable=True))
    op.add_column('property', sa.Column('market_value', sa.Numeric(12, 2), nullable=True))
    op.add_column('property', sa.Column('equity_estimate', sa.Numeric(12, 2), nullable=True))
    op.add_column('property', sa.Column('last_sale_price', sa.Numeric(12, 2), nullable=True))
    op.add_column('property', sa.Column('last_sale_date', sa.Date(), nullable=True))
    op.add_column('property', sa.Column('purchase_months_since', sa.Integer(), nullable=True))
    
    # PropertyRadar specific value fields (legacy naming preserved)
    op.add_column('property', sa.Column('estimated_value', sa.Numeric(12, 2), nullable=True))
    op.add_column('property', sa.Column('estimated_equity', sa.Numeric(12, 2), nullable=True))
    op.add_column('property', sa.Column('estimated_equity_percent', sa.Integer(), nullable=True))
    
    # Purchase information
    op.add_column('property', sa.Column('purchase_date', sa.Date(), nullable=True))
    op.add_column('property', sa.Column('purchase_price', sa.Numeric(12, 2), nullable=True))
    
    # Status flags
    op.add_column('property', sa.Column('owner_occupied', sa.Boolean(), server_default='false', nullable=True))
    op.add_column('property', sa.Column('listed_for_sale', sa.Boolean(), server_default='false', nullable=True))
    op.add_column('property', sa.Column('listing_status', sa.String(50), nullable=True))
    op.add_column('property', sa.Column('foreclosure', sa.Boolean(), server_default='false', nullable=True))
    op.add_column('property', sa.Column('foreclosure_status', sa.String(50), nullable=True))
    op.add_column('property', sa.Column('high_equity', sa.Boolean(), server_default='false', nullable=True))
    
    # Owner information
    op.add_column('property', sa.Column('owner_name', sa.String(200), nullable=True))
    
    # Mailing address fields
    op.add_column('property', sa.Column('mail_address', sa.String(200), nullable=True))
    op.add_column('property', sa.Column('mail_city', sa.String(100), nullable=True))
    op.add_column('property', sa.Column('mail_state', sa.String(2), nullable=True))
    op.add_column('property', sa.Column('mail_zip', sa.String(10), nullable=True))
    
    # Alternative mailing address fields (some sources use different naming)
    op.add_column('property', sa.Column('mailing_address', sa.String(200), nullable=True))
    op.add_column('property', sa.Column('mailing_city', sa.String(100), nullable=True))
    op.add_column('property', sa.Column('mailing_state', sa.String(2), nullable=True))
    op.add_column('property', sa.Column('mailing_zip', sa.String(10), nullable=True))
    
    # Metadata fields
    op.add_column('property', sa.Column('property_metadata', sa.JSON(), nullable=True))
    op.add_column('property', sa.Column('import_source', sa.String(50), nullable=True))
    op.add_column('property', sa.Column('external_id', sa.String(100), nullable=True))  # ID from external source
    
    # Audit fields
    op.add_column('property', sa.Column('created_at', sa.DateTime(), nullable=True, server_default=sa.func.now()))
    op.add_column('property', sa.Column('updated_at', sa.DateTime(), nullable=True, onupdate=sa.func.now()))
    
    # Phase 3: Create indexes for performance
    # Note: CONCURRENTLY cannot be used inside a transaction, so we use regular index creation
    # For production, these indexes can be created manually outside the migration with CONCURRENTLY
    op.create_index('ix_property_city', 'property', ['city'])
    op.create_index('ix_property_state', 'property', ['state'])
    op.create_index('ix_property_zip_code', 'property', ['zip_code'])
    op.create_index('ix_property_apn', 'property', ['apn'])
    op.create_index('ix_property_owner_occupied', 'property', ['owner_occupied'])
    op.create_index('ix_property_high_equity', 'property', ['high_equity'])
    op.create_index('ix_property_foreclosure', 'property', ['foreclosure'])
    op.create_index('ix_property_location', 'property', ['city', 'state', 'zip_code'])
    op.create_index('ix_property_value', 'property', ['market_value', 'equity_estimate'])
    
    # Create partial index for coordinates (PostgreSQL only)
    connection = op.get_bind()
    if connection.dialect.name == 'postgresql':
        op.create_index(
            'ix_property_coordinates', 'property', 
            ['longitude', 'latitude'],
            postgresql_where=sa.text('longitude IS NOT NULL AND latitude IS NOT NULL')
        )
    
    # Phase 4: Add unique constraint on APN (if not null)
    connection = op.get_bind()
    if connection.dialect.name == 'postgresql':
        # Create partial unique index for APN
        op.create_index(
            'uq_property_apn', 'property', ['apn'],
            unique=True,
            postgresql_where=sa.text('apn IS NOT NULL')
        )
    
    # Phase 5: Migrate existing contact_id relationships to PropertyContact table
    # This preserves existing relationships during the transition
    connection = op.get_bind()
    result = connection.execute(sa.text("""
        INSERT INTO property_contact (property_id, contact_id, relationship_type, is_primary, created_at)
        SELECT id, contact_id, 'owner', true, CURRENT_TIMESTAMP
        FROM property
        WHERE contact_id IS NOT NULL
        ON CONFLICT (property_id, contact_id) DO NOTHING
    """))
    
    # Log migration progress
    if result.rowcount > 0:
        print(f"Migrated {result.rowcount} existing property-contact relationships")
    
    # Phase 6: Make contact_id nullable for backward compatibility
    # This allows properties to be created without requiring a contact_id
    op.alter_column('property', 'contact_id', nullable=True)
    
    # Note: We're keeping the contact_id column for now to ensure backward compatibility
    # It can be removed in a future migration after all code is updated


def downgrade():
    """
    Rollback the PropertyRadar enhancement migration.
    This will remove all added fields and the association table.
    """
    
    # Restore contact_id NOT NULL constraint
    op.alter_column('property', 'contact_id', nullable=False)
    
    # Drop indexes first
    op.drop_index('uq_property_apn', 'property')
    op.drop_index('ix_property_coordinates', 'property')
    op.drop_index('ix_property_value', 'property')
    op.drop_index('ix_property_location', 'property')
    op.drop_index('ix_property_foreclosure', 'property')
    op.drop_index('ix_property_high_equity', 'property')
    op.drop_index('ix_property_owner_occupied', 'property')
    op.drop_index('ix_property_apn', 'property')
    op.drop_index('ix_property_zip_code', 'property')
    op.drop_index('ix_property_state', 'property')
    op.drop_index('ix_property_city', 'property')
    
    # Drop all added columns
    op.drop_column('property', 'updated_at')
    op.drop_column('property', 'created_at')
    op.drop_column('property', 'external_id')
    op.drop_column('property', 'import_source')
    op.drop_column('property', 'property_metadata')
    op.drop_column('property', 'mailing_zip')
    op.drop_column('property', 'mailing_state')
    op.drop_column('property', 'mailing_city')
    op.drop_column('property', 'mailing_address')
    op.drop_column('property', 'mail_zip')
    op.drop_column('property', 'mail_state')
    op.drop_column('property', 'mail_city')
    op.drop_column('property', 'mail_address')
    op.drop_column('property', 'owner_name')
    op.drop_column('property', 'high_equity')
    op.drop_column('property', 'foreclosure_status')
    op.drop_column('property', 'foreclosure')
    op.drop_column('property', 'listing_status')
    op.drop_column('property', 'listed_for_sale')
    op.drop_column('property', 'owner_occupied')
    op.drop_column('property', 'purchase_price')
    op.drop_column('property', 'purchase_date')
    op.drop_column('property', 'estimated_equity_percent')
    op.drop_column('property', 'estimated_equity')
    op.drop_column('property', 'estimated_value')
    op.drop_column('property', 'purchase_months_since')
    op.drop_column('property', 'last_sale_date')
    op.drop_column('property', 'last_sale_price')
    op.drop_column('property', 'equity_estimate')
    op.drop_column('property', 'market_value')
    op.drop_column('property', 'assessed_value')
    op.drop_column('property', 'bathrooms')
    op.drop_column('property', 'bedrooms')
    op.drop_column('property', 'square_feet')
    op.drop_column('property', 'year_built')
    op.drop_column('property', 'apn')
    op.drop_column('property', 'latitude')
    op.drop_column('property', 'longitude')
    op.drop_column('property', 'subdivision')
    op.drop_column('property', 'zip_code')
    op.drop_column('property', 'state')
    op.drop_column('property', 'city')
    
    # Drop PropertyContact indexes
    op.drop_index('ix_property_contact_relationship', 'property_contact')
    op.drop_index('ix_property_contact_contact_id', 'property_contact')
    op.drop_index('ix_property_contact_property_id', 'property_contact')
    
    # Drop PropertyContact table
    op.drop_table('property_contact')