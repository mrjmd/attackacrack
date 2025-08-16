# Production Sync Recommendations for 7000+ Conversations

## Before Running Full Production Import

### 1. **Test with Smaller Batches First**
```bash
# Test with 10 conversations
docker compose exec celery python -c "from scripts.data_management.imports.enhanced_openphone_import import run_enhanced_import; run_enhanced_import(dry_run_limit=10)"

# Test with 100 conversations
docker compose exec celery python -c "from scripts.data_management.imports.enhanced_openphone_import import run_enhanced_import; run_enhanced_import(dry_run_limit=100)"
```

### 2. **Use the Large Scale Importer for Production**
The `large_scale_import.py` script is specifically designed for production use with:
- Checkpoint/resume capability
- Better timeout handling
- Progress tracking
- Graceful interruption support

### 3. **Monitor During Import**

#### Check Celery Task Progress:
```bash
# Monitor active tasks
docker compose exec web python -c "
from celery_worker import celery
inspect = celery.control.inspect()
active = inspect.active()
for worker, tasks in (active or {}).items():
    for task in tasks:
        print(f'{task[\"name\"]}: {task[\"id\"]}')
"
```

#### Check Database Growth:
```bash
# Monitor database size
docker compose exec db psql -U crm_user -d crm_db -c "
SELECT 
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables 
WHERE schemaname = 'public' 
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;"
```

#### Monitor Logs:
```bash
# Watch Celery logs
docker compose logs -f celery

# In another terminal, watch database logs
docker compose logs -f db
```

### 4. **Production Deployment Recommendations**

1. **Increase Celery Worker Resources**
   - Update `.do/app.yaml` to allocate more memory/CPU to the worker
   ```yaml
   workers:
     - name: celery
       size: professional-xs  # or larger
   ```

2. **Set Celery Task Timeouts**
   - Use the production task with timeouts (sync_tasks_production.py)
   - Soft limit: 2 hours, Hard limit: 2 hours 5 minutes

3. **Enable Redis Persistence** 
   - Ensure Redis/Valkey has persistence enabled for task recovery

4. **Database Connection Pooling**
   - Monitor connection count during import
   - May need to increase max_connections in PostgreSQL

5. **API Rate Limiting**
   - OpenPhone may have rate limits
   - The large_scale_import has retry logic with exponential backoff

### 5. **Step-by-Step Production Import**

1. **Backup Database First**
   ```bash
   # Create a backup before import
   doctl databases backups create <your-db-id>
   ```

2. **Start Small**
   - Run a 100-conversation test in production
   - Monitor for any issues
   - Check memory usage and performance

3. **Run Full Import During Low Usage**
   - Schedule for overnight or weekend
   - Expect 2-4 hours for 7000+ conversations
   - Monitor throughout

4. **Use Resume Capability**
   - If import fails, the large_scale_import can resume
   - Check `import_progress.json` for status

### 6. **Emergency Stop**
If you need to stop the import:
```bash
# Gracefully stop Celery worker
docker compose exec celery celery -A celery_worker control shutdown

# Or revoke specific task
docker compose exec web python -c "
from celery_worker import celery
celery.control.revoke('<task-id>', terminate=True)
"
```

## Summary

**For production with 7000+ conversations:**
1. ✅ Use `large_scale_import.py` instead of basic importer
2. ✅ Test with small batches first (10, 100, 500)
3. ✅ Monitor actively during import
4. ✅ Run during low-usage periods
5. ✅ Have a rollback plan ready

The system CAN handle 7000+ conversations, but proper monitoring and the production-ready importer are essential for success.