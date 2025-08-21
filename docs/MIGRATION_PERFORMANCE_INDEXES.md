# Performance Indexes Migration - August 21, 2025

## Overview
Created and applied Alembic migration `348a94c904eb` to add critical performance indexes for webhook and campaign processing.

## Migration File
- **Location**: `/migrations/versions/348a94c904eb_add_critical_performance_indexes_for_.py`
- **Revision ID**: `348a94c904eb`
- **Parent Revision**: `2792ed2d7978`

## Indexes Created

### Critical Webhook Processing Indexes
1. **idx_activity_openphone_id** - Find activities by OpenPhone ID for webhook matching
   - PostgreSQL: Partial index with `WHERE openphone_id IS NOT NULL`
   - SQLite: Regular B-tree index

2. **idx_webhook_event_processed** - Track unprocessed webhook events
   - Composite index on `(processed, created_at)`

3. **idx_webhook_event_id** - Fast lookup by event_id to prevent duplicates

### Campaign Processing Indexes
4. **idx_campaign_membership_status** - Find campaign members by status
   - Composite index on `(campaign_id, status)`

5. **idx_campaign_membership_sent** - Track recent campaign sends
   - Composite index on `(sent_at, status)`

### Contact Lookup Indexes
6. **idx_contact_phone_hash** - Ultra-fast phone number lookups
   - PostgreSQL: Hash index for O(1) exact match lookups
   - SQLite: Regular B-tree index

7. **idx_contact_first_name** - Name search optimization
8. **idx_contact_last_name** - Name search optimization
9. **idx_contact_email** - Email lookup optimization

### Opt-Out Management
10. **idx_contact_flag_type_phone** - Quick opt-out verification
    - PostgreSQL: Partial index with `WHERE flag_type = 'opted_out'`
    - SQLite: Composite index on `(flag_type, contact_id)`

### Activity Tracking Indexes
11. **idx_activity_conversation_created** - Find activities in conversations
    - Composite index on `(conversation_id, created_at)`

12. **idx_activity_type_created** - Filter activities by type
    - Composite index on `(activity_type, created_at)`

13. **idx_activity_user** - Filter activities by user
    - Composite index on `(user_id, created_at)`

14. **idx_activity_contact** - Get contact activity history
    - Composite index on `(contact_id, created_at)`

### Conversation Indexes
15. **idx_conversation_phone_number_id** - Lookup by phone number
16. **idx_conversation_contact** - Lookup by contact

### Business Object Indexes
17. **idx_appointment_date** - Find appointments by date
    - Composite index on `(date, time)`

18. **idx_invoice_status_due** - Track invoice status
    - Composite index on `(status, due_date)`

## Database Compatibility
The migration handles both PostgreSQL and SQLite:
- **PostgreSQL**: Uses advanced features like hash indexes and partial indexes
- **SQLite**: Falls back to regular B-tree indexes where needed

## Performance Impact
These indexes will significantly improve:
- Webhook processing speed (matching OpenPhone events to activities)
- Campaign member lookups and status tracking
- Contact searches by phone, email, or name
- Opt-out verification during campaign sends
- Activity history retrieval
- Dashboard and reporting queries

## Testing
- Migration successfully applied to development database
- Downgrade tested and confirmed working
- All indexes verified as created in PostgreSQL

## Commands Used
```bash
# Create migration
docker-compose exec web flask db revision -m "Add critical performance indexes for webhook and campaign processing"

# Apply migration
docker-compose exec web flask db upgrade

# Test downgrade
docker-compose exec web flask db downgrade

# Re-apply after testing
docker-compose exec web flask db upgrade
```

## Next Steps
1. Monitor query performance with `EXPLAIN ANALYZE` to verify index usage
2. Consider adding additional indexes based on slow query logs
3. Set up regular `VACUUM ANALYZE` for PostgreSQL to maintain index statistics
4. Consider partitioning large tables (activity, campaign_membership) in the future