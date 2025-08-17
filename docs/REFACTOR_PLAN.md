# Refactoring Plan - Week of August 18, 2025

## Executive Summary
Focus on three high-impact areas that directly support campaign launch:
1. Move business logic to service layer (maintainability)
2. Fix critical UI/UX issues (usability)
3. Clean up obsolete code (reduce confusion)

## Phase 1: Service Layer Refactoring (2-3 days)
**Goal**: Move ALL business logic from routes to services

### Priority Routes to Refactor:

#### ✅ COMPLETED:
1. **routes/main_routes.py** - Dashboard refactored to DashboardService
2. **routes/campaigns.py** - Campaign logic moved to CampaignService

#### 🔧 HIGH PRIORITY (Heavy business logic):
1. **routes/todo_routes.py** - Most DB operations in routes
   - [ ] Create `TodoService` with all CRUD operations
   - [ ] Move dashboard todo logic with priority sorting
   - [ ] Standardize API responses

2. **routes/api_routes.py** - Complex diagnostic logic
   - [ ] Create `DiagnosticsService` for health checks
   - [ ] Create `TaskService` for Celery task management
   - [ ] Move message fetching logic to MessageService

3. **routes/settings_routes.py** - Sync orchestration logic
   - [ ] Create `SyncService` for sync health monitoring
   - [ ] Move Celery task queuing logic to service
   - [ ] Expand QuickBooksSyncService for manual sync

#### 📝 MEDIUM PRIORITY (Moderate refactoring needed):
4. **routes/contact_routes.py** - Mixed logic
   - [ ] Move search/filter logic to ContactService
   - [ ] Move bulk operations to service
   - [ ] Move export logic to service

5. **routes/property_routes.py** - Search/pagination
   - [ ] Expand PropertyService with search methods
   - [ ] Move pagination logic to service

#### ✅ LOW PRIORITY (Already well-structured):
6. **routes/auth.py** & **routes/auth_routes.py** - Minor updates
   - [ ] Expand AuthService with profile management
   - [ ] Add QuickBooks disconnect to service

#### ✅ NO REFACTORING NEEDED:
- **routes/job_routes.py** - Excellent service usage
- **routes/appointment_routes.py** - Properly using services
- **routes/invoice_routes.py** - Good service delegation
- **routes/quote_routes.py** - Minor DB query, mostly good
- **routes/growth_routes.py** - Placeholder routes only

### New Services to Create:

1. **TodoService** (`services/todo_service.py`)
   - `get_user_todos(user_id, include_completed=True)`
   - `get_dashboard_todos(user_id, limit=5)`
   - `create_todo(user_id, todo_data)`
   - `update_todo(todo_id, user_id, updates)`
   - `toggle_todo_completion(todo_id, user_id)`
   - `delete_todo(todo_id, user_id)`

2. **DiagnosticsService** (`services/diagnostics_service.py`)
   - `get_health_status()`
   - `get_redis_diagnostics()`
   - `test_database_connection()`
   - `get_system_metrics()`

3. **SyncService** (`services/sync_service.py`)
   - `get_sync_health_status()`
   - `get_openphone_sync_stats()`
   - `queue_openphone_sync(sync_type, options)`
   - `monitor_active_tasks()`

4. **TaskService** (`services/task_service.py`)
   - `get_task_status(task_id)`
   - `queue_task(task_name, args, kwargs)`
   - `cancel_task(task_id)`
   - `get_active_tasks()`

### Refactoring Pattern:
```python
# BAD (current) - logic in route
@route('/endpoint')
def endpoint():
    data = request.json
    # 50 lines of business logic here
    db.session.commit()
    return jsonify(result)

# GOOD (target) - logic in service
@route('/endpoint')
def endpoint():
    data = request.json
    try:
        result = service.process(data)
        return jsonify(result)
    except ValidationError as e:
        return jsonify({'error': str(e)}), 400
```

## Phase 2: Critical UI/UX Fixes (2-3 days)
**Goal**: Fix the most frustrating user experience issues

### High Priority Fixes:
1. **Loading States & Feedback**
   - [ ] Add loading spinner component
   - [ ] Add success/error toast notifications
   - [ ] Show progress for long operations (imports, campaigns)

2. **Contacts Page Overhaul**
   - [ ] Fix broken filters
   - [ ] Add proper pagination controls
   - [ ] Add bulk actions (select all, bulk delete/tag)
   - [ ] Fix search functionality

3. **Dashboard Activity Feed**
   - [ ] ✅ Already fixed sorting
   - [ ] Add activity type icons
   - [ ] Make clickable to view full conversation
   - [ ] Add time grouping (Today, Yesterday, This Week)

4. **Campaign Creation Flow**
   - [ ] Add preview before sending
   - [ ] Show estimated send time
   - [ ] Add validation warnings (e.g., "125 texts/day limit")
   - [ ] Clear success/failure feedback

### UI Components to Create:
```html
<!-- Loading Spinner -->
<div class="loading-spinner">
    <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
</div>

<!-- Toast Notification -->
<div class="toast success|error|warning">
    <span class="message">Operation successful!</span>
</div>

<!-- Pagination -->
<div class="pagination">
    <button>Previous</button>
    <span>Page 1 of 10</span>
    <button>Next</button>
</div>
```

## Phase 3: Technical Debt Cleanup (1 day)
**Goal**: Remove confusion and obsolete code

### Scripts to Archive/Delete:
```
scripts/archive/  # Create this directory
├── data_management/
│   ├── imports/
│   │   ├── date_filtered_import.py  # Superseded by large_scale_import
│   │   ├── enhanced_openphone_import.py  # Keep - used by large_scale
│   │   ├── safe_dry_run_import.py  # Archive - testing only
│   │   └── test_enhanced_import.py  # Archive - testing only
│   └── old_csv_importer.py  # If exists - replaced by csv_import_service
├── fix_env_vars.sh  # Dangerous - archive now that env is stable
└── dev_tools/
    └── obsolete/  # Move old development scripts here
```

### Code to Remove:
1. **Hardcoded Values**:
   - [ ] appointment_service.py - "Mike Harrington" email
   - [ ] Any hardcoded phone numbers or IDs
   - [ ] Move to config or database

2. **Print Statements**:
   - [ ] Global search for `print(` and replace with logger
   - [ ] Ensure all logging uses structured format

3. **Disabled Tests**:
   - [ ] Delete (don't fix) disabled test files for now
   - [ ] Document what they were testing for future reference

### Database Cleanup:
```python
# Script to clean up orphaned data
- [ ] Remove conversations without activities
- [ ] Remove activities without valid conversations
- [ ] Clean up test data from development
```

## Phase 4: Configuration & Error Handling (1 day)
**Goal**: Standardize patterns across the codebase

### Error Handling Strategy:
```python
# services/base_service.py
class ServiceError(Exception):
    """Base exception for service layer"""
    pass

class ValidationError(ServiceError):
    """Invalid input data"""
    pass

class NotFoundError(ServiceError):
    """Resource not found"""
    pass

class ExternalAPIError(ServiceError):
    """External API call failed"""
    pass

# In services:
def process(data):
    if not data.get('required_field'):
        raise ValidationError("Missing required field")
    
    try:
        result = external_api.call()
    except Exception as e:
        raise ExternalAPIError(f"API call failed: {e}")
    
    return result

# In routes:
@route('/endpoint')
def endpoint():
    try:
        result = service.process(request.json)
        return jsonify(result)
    except ValidationError as e:
        return jsonify({'error': str(e)}), 400
    except NotFoundError as e:
        return jsonify({'error': str(e)}), 404
    except ServiceError as e:
        logger.error(f"Service error: {e}")
        return jsonify({'error': 'Internal error'}), 500
```

### Configuration Improvements:
```python
# config.py additions
class Config:
    # Move hardcoded values here
    DEFAULT_APPOINTMENT_DURATION = 60  # minutes
    DEFAULT_APPOINTMENT_EMAIL = os.environ.get('DEFAULT_EMAIL', 'admin@attackacrack.com')
    SMS_DAILY_LIMIT = 125
    PAGINATION_DEFAULT = 50
    PAGINATION_MAX = 200
```

## Success Metrics
- [ ] All routes under 50 lines (business logic in services)
- [ ] No print() statements in codebase
- [ ] All user actions have loading/success/error feedback
- [ ] Contacts page is fast and intuitive
- [ ] No hardcoded values in business logic
- [ ] Clear separation: routes → services → models

## What We're NOT Doing (Yet)
- Comprehensive test coverage (after campaign launch)
- CI/CD pipeline changes (keeping auto-deploy for now)
- Major architectural changes (no need)
- Database schema changes (stable enough)
- Authentication system changes (working fine)

## Timeline
- **Monday-Tuesday**: Service layer refactoring
- **Wednesday-Thursday**: UI/UX improvements
- **Friday**: Technical debt cleanup & testing

This positions us to launch campaigns next week with a cleaner, more maintainable codebase.