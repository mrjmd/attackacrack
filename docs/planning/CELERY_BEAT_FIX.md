# Celery Beat Scheduler Fix

## Current Issues

### 1. Missing Campaign Processing Schedule
**Problem:** The `process_campaign_queue` task is never scheduled to run automatically.

**Current State (celery_worker.py):**
```python
celery.conf.beat_schedule = {
    'run-daily-tasks': {
        'task': 'services.scheduler_service.run_daily_tasks',
        'schedule': 3600.0 * 24,  # Only runs once per day
    },
}
```

**Required Fix:**
```python
from celery.schedules import crontab

celery.conf.beat_schedule = {
    # Process campaign queue every minute
    'process-campaign-queue': {
        'task': 'tasks.campaign_tasks.process_campaign_queue',
        'schedule': 60.0,  # Every 60 seconds
    },
    # Keep existing daily tasks
    'run-daily-tasks': {
        'task': 'services.scheduler_service.run_daily_tasks',
        'schedule': crontab(hour=8, minute=0),  # Daily at 8 AM
    },
    # Add webhook health check (Phase 1)
    'webhook-health-check': {
        'task': 'tasks.sync_tasks.check_webhook_health',
        'schedule': 3600.0,  # Every hour
    },
    # Add daily reconciliation (Phase 1)
    'openphone-reconciliation': {
        'task': 'tasks.sync_tasks.reconcile_openphone_data',
        'schedule': crontab(hour=2, minute=0),  # Daily at 2 AM
    },
}
```

### 2. Dependency Injection Failure in Tasks

**Problem:** Campaign tasks instantiate services without dependencies.

**Current State (tasks/campaign_tasks.py):**
```python
@celery.task(bind=True)
def process_campaign_queue(self):
    try:
        campaign_service = CampaignService()  # ❌ No dependencies!
        stats = campaign_service.process_campaign_queue()
```

**Required Fix:**
```python
@celery.task(bind=True)
def process_campaign_queue(self):
    from flask import current_app
    
    try:
        # Get service with all dependencies from registry
        campaign_service = current_app.services.get('campaign')
        if not campaign_service:
            raise ValueError("Campaign service not available in registry")
            
        stats = campaign_service.process_campaign_queue()
```

### 3. Flask App Context Issues

**Problem:** Tasks need Flask app context to access service registry.

**Current State:** Context is provided by ContextTask but service registry might not be initialized.

**Required Fix (celery_worker.py):**
```python
class ContextTask(celery.Task):
    def __call__(self, *args, **kwargs):
        with flask_app.app_context():
            # Ensure service registry is initialized
            if not hasattr(flask_app, 'services'):
                from services import initialize_services
                flask_app.services = initialize_services(flask_app)
            return self.run(*args, **kwargs)
```

## Implementation Steps

### Step 1: Fix Celery Beat Schedule (15 minutes)
1. Add the campaign queue processing schedule
2. Add placeholder schedules for future health check and reconciliation tasks
3. Use crontab for specific times instead of intervals

### Step 2: Fix Campaign Task DI (30 minutes)
1. Update `process_campaign_queue` to use service registry
2. Update `handle_incoming_message_opt_out` to use service registry
3. Add error handling for missing services

### Step 3: Test Configuration (30 minutes)
1. Start Celery Beat: `celery -A celery_worker beat --loglevel=info`
2. Start Celery Worker: `celery -A celery_worker worker --loglevel=info`
3. Verify scheduled tasks appear in logs
4. Test campaign processing manually

### Step 4: Add Missing Tasks (2 hours)
Create placeholder tasks that will be implemented in Phase 1:
- `check_webhook_health` 
- `reconcile_openphone_data`
- `cleanup_old_campaigns`
- `generate_campaign_reports`

## Testing Commands

```bash
# Test Celery Beat configuration
docker-compose exec web celery -A celery_worker beat --loglevel=debug

# Test worker receives scheduled tasks
docker-compose exec web celery -A celery_worker worker --loglevel=info

# Manually trigger campaign processing
docker-compose exec web python -c "
from tasks.campaign_tasks import process_campaign_queue
result = process_campaign_queue.delay()
print(f'Task ID: {result.id}')
"

# Monitor task execution
docker-compose exec web celery -A celery_worker events

# Inspect scheduled tasks
docker-compose exec web celery -A celery_worker inspect scheduled
```

## Verification Checklist

- [ ] Celery Beat starts without errors
- [ ] Campaign queue task appears in schedule
- [ ] Task runs every 60 seconds
- [ ] Campaign service properly initialized in task
- [ ] Test message sends successfully
- [ ] No dependency injection errors
- [ ] Logs show proper task execution

## Common Issues & Solutions

### Issue: "Campaign service not available in registry"
**Solution:** Ensure service registry is initialized in ContextTask

### Issue: "No registered tasks"
**Solution:** Check task imports in celery_worker.py

### Issue: "Connection refused" to Redis
**Solution:** Verify Redis is running and CELERY_BROKER_URL is correct

### Issue: Tasks not executing on schedule
**Solution:** Ensure both beat and worker are running

## Production Considerations

1. **Separate Beat Process:** Run Celery Beat as a separate process/container
2. **Single Beat Instance:** Only ONE beat process should run (use Redis lock)
3. **Monitoring:** Add health checks for beat process
4. **Persistence:** Use celerybeat-schedule.db for schedule persistence
5. **Timezone:** Ensure UTC is used consistently

---

*Estimated Time to Fix: 1.5-2 hours*  
*Priority: CRITICAL - Blocks all campaign automation*