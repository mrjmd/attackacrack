-- Manual index creation script for production with CONCURRENTLY
-- Run this outside of a transaction to create indexes without locking the table
-- Usage: docker-compose exec db psql -U myuser -d crm_db -f /migrations/create_concurrent_indexes.sql

-- These indexes support PropertyRadar import performance
-- They should be created after the main migration has completed

-- Drop existing indexes if they exist (won't lock table)
DROP INDEX CONCURRENTLY IF EXISTS ix_property_city;
DROP INDEX CONCURRENTLY IF EXISTS ix_property_state;
DROP INDEX CONCURRENTLY IF EXISTS ix_property_zip_code;
DROP INDEX CONCURRENTLY IF EXISTS ix_property_apn;
DROP INDEX CONCURRENTLY IF EXISTS ix_property_owner_occupied;
DROP INDEX CONCURRENTLY IF EXISTS ix_property_high_equity;
DROP INDEX CONCURRENTLY IF EXISTS ix_property_foreclosure;
DROP INDEX CONCURRENTLY IF EXISTS ix_property_location;
DROP INDEX CONCURRENTLY IF EXISTS ix_property_value;
DROP INDEX CONCURRENTLY IF EXISTS ix_property_coordinates;

-- Create indexes concurrently (doesn't lock table for reads/writes)
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_property_city ON property(city);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_property_state ON property(state);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_property_zip_code ON property(zip_code);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_property_apn ON property(apn);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_property_owner_occupied ON property(owner_occupied);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_property_high_equity ON property(high_equity);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_property_foreclosure ON property(foreclosure);

-- Composite indexes for common queries
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_property_location ON property(city, state, zip_code);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_property_value ON property(market_value, equity_estimate);

-- Partial index for coordinates (only index rows with coordinates)
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_property_coordinates 
ON property(longitude, latitude) 
WHERE longitude IS NOT NULL AND latitude IS NOT NULL;

-- Partial unique index for APN (enforces uniqueness only when APN is present)
CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS uq_property_apn 
ON property(apn) 
WHERE apn IS NOT NULL;

-- Performance indexes for PropertyContact association table
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_property_contact_property_id ON property_contact(property_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_property_contact_contact_id ON property_contact(contact_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_property_contact_relationship ON property_contact(relationship_type);

-- Analyze tables after index creation for better query planning
ANALYZE property;
ANALYZE property_contact;

-- Display index information
\di property*