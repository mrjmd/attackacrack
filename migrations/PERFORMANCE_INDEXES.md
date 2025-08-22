# Performance Indexes Migration Summary

## Migration Details
- **Migration ID**: `10992629d68e`
- **Description**: Add performance indexes for webhook, campaign, and opt-out processing
- **Date Created**: August 21, 2025

## Indexes Created

### Webhook Processing Indexes
1. **ix_activity_openphone_id** (B-tree)
   - Table: `activity`
   - Column: `openphone_id`
   - Purpose: Prevent duplicate webhook processing by quickly checking if an activity already exists

2. **ix_webhook_event_processed** (B-tree)
   - Table: `webhook_event`
   - Columns: `processed`, `event_type`
   - Purpose: Efficiently find unprocessed webhook events by type

### Campaign Processing Indexes
3. **ix_campaign_membership_campaign_status** (B-tree)
   - Table: `campaign_membership`
   - Columns: `campaign_id`, `status`
   - Purpose: Quickly find campaign members by campaign and their status

4. **ix_contact_phone_hash** (Hash - PostgreSQL only)
   - Table: `contact`
   - Column: `phone`
   - Purpose: Ultra-fast exact match lookups for phone numbers
   - Note: Falls back to B-tree index for SQLite

5. **ix_activity_conversation_created** (B-tree)
   - Table: `activity`
   - Columns: `conversation_id`, `created_at DESC`
   - Purpose: Efficiently load conversation history in chronological order

### Opt-Out Checking Indexes
6. **ix_contact_flag_opted_out** (Partial B-tree - PostgreSQL only)
   - Table: `contact_flag`
   - Columns: `flag_type`, `contact_id`
   - Condition: `WHERE flag_type = 'opted_out'`
   - Purpose: Quickly check if a contact has opted out
   - Note: Falls back to regular composite index for SQLite

### Additional Performance Indexes
7. **ix_conversation_contact_id** (B-tree)
   - Table: `conversation`
   - Column: `contact_id`
   - Purpose: Quick contact history lookup

8. **ix_activity_type** (B-tree)
   - Table: `activity`
   - Column: `activity_type`
   - Purpose: Filter activities by type

9. **ix_campaign_membership_contact_id** (B-tree)
   - Table: `campaign_membership`
   - Column: `contact_id`
   - Purpose: Check if contact is in any campaign

10. **ix_webhook_event_event_type** (B-tree)
    - Table: `webhook_event`
    - Column: `event_type`
    - Purpose: Analytics and filtering by event type

## Performance Benefits

### Before Indexes
- Phone number lookups: O(n) full table scan
- Campaign member queries: O(n*m) nested loops
- Opt-out checks: Full scan of contact_flag table
- Conversation history: Sorting entire activity table

### After Indexes
- Phone number lookups: O(1) with hash index
- Campaign member queries: O(log n) with composite index
- Opt-out checks: O(log k) where k = opted_out records only
- Conversation history: Pre-sorted index scan

## Compatibility

### PostgreSQL Features
- Hash index for phone lookups (optimal for exact matches)
- Partial indexes for opt-out flags (smaller index size)
- CREATE INDEX IF NOT EXISTS support

### SQLite Fallbacks
- B-tree index instead of hash for phone lookups
- Regular composite index instead of partial for opt-out flags
- Manual IF NOT EXISTS handling

## Testing Results
- **All 1670 tests passing** after migration
- Migration successfully applied and rolled back
- Both PostgreSQL and SQLite compatibility verified

## Usage Examples

### Optimized Queries

```sql
-- Fast phone lookup (uses hash index)
SELECT * FROM contact WHERE phone = '+11234567890';

-- Efficient campaign member retrieval
SELECT * FROM campaign_membership 
WHERE campaign_id = 123 AND status = 'pending';

-- Quick opt-out check (partial index)
SELECT * FROM contact_flag 
WHERE flag_type = 'opted_out' AND contact_id = 456;

-- Conversation history (pre-sorted)
SELECT * FROM activity 
WHERE conversation_id = 789 
ORDER BY created_at DESC;
```

## Maintenance Notes

1. **Index Monitoring**: Use `pg_stat_user_indexes` to monitor index usage
2. **Bloat Management**: Run `REINDEX CONCURRENTLY` periodically for heavily updated indexes
3. **Statistics**: Keep statistics updated with `ANALYZE` after bulk operations
4. **Hash Index Limitation**: Hash indexes don't support range queries or sorting

## Rollback Instructions

If needed, the migration can be safely rolled back:

```bash
docker-compose exec web flask db downgrade 2792ed2d7978
```

This will drop all created indexes without affecting data.