# SMS Campaign Technical Implementation Plan
**Date:** August 21, 2025  
**Based on:** SMS_CAMPAIGN_GAP_ANALYSIS.md  
**Architecture:** Enhanced Dependency Injection + Repository Pattern + Result Pattern  

## Executive Summary

This plan addresses the critical gaps identified in the SMS Campaign system analysis, structured in 4 phases with **MANDATORY Test-Driven Development** at every step. Each phase builds incrementally toward production readiness with built-in rollback capabilities.

### Critical Success Metrics
- **Phase 0**: Fix existing dependency injection issues (2-4 hours)
- **Phase 1**: Implement health check & reconciliation (20-25 hours)  
- **Phase 2**: Complete compliance & safety features (25-30 hours)
- **Phase 3**: Enhance campaign engine with advanced features (30-35 hours)
- **Total Estimated Time**: 77-94 hours across 3-4 weeks

## 🚨 MANDATORY: Test-Driven Development Enforcement

### TDD Workflow for ALL Features
```bash
# Phase 1: RED - Write failing tests FIRST
docker-compose exec web pytest tests/test_new_feature.py -xvs  # MUST FAIL

# Phase 2: GREEN - Minimal implementation to pass tests
# ... implement only enough to pass tests ...

# Phase 3: REFACTOR - Improve code while keeping tests green
docker-compose exec web pytest tests/  # ALL tests MUST stay green
```

### Coverage Requirements
- **Minimum**: 90% coverage for all new code
- **Target**: 95% coverage for critical paths
- **Health check & webhook services**: 100% coverage required

---

# PHASE 0: Critical Fixes (2-4 hours)
**BEFORE ANY new features - Fix existing issues**

## P0-01: Fix Campaign Task Dependency Injection ⚠️ URGENT

### User Story
As a system administrator, I need campaign processing tasks to work with proper dependency injection so that automated SMS campaigns can run reliably without service instantiation errors.

### Current Problem Analysis
```python
# tasks/campaign_tasks.py - Line 18 - BROKEN
campaign_service = CampaignService()  # NO DEPENDENCIES INJECTED
```

### Test Specifications (RED Phase)
```python
# tests/unit/tasks/test_campaign_tasks.py
class TestCampaignTasks:
    def test_process_campaign_queue_uses_dependency_injection(self, app):
        """Test that campaign tasks use proper DI from service registry"""
        with app.app_context():
            # Should not raise any missing dependency errors
            result = process_campaign_queue.apply()
            assert result.successful()
    
    def test_handle_opt_out_uses_injected_services(self, app):
        """Test opt-out handling uses injected dependencies"""
        with app.app_context():
            result = handle_incoming_message_opt_out.apply(
                args=['+11234567890', 'STOP']
            )
            assert result.successful()
```

### Implementation Steps (GREEN Phase)
1. **Fix `tasks/campaign_tasks.py`** - Replace direct instantiation with DI:
   ```python
   # OLD: campaign_service = CampaignService()
   # NEW: campaign_service = current_app.services.get('campaign')
   ```

2. **Ensure CampaignService is properly registered** in `app.py`

3. **Test with real Celery task execution**:
   ```bash
   docker-compose exec celery celery -A celery_worker.celery call tasks.campaign_tasks.process_campaign_queue
   ```

### Database Migrations Needed
None - this is a service layer fix.

### Risk Assessment
- **Risk**: Medium - Campaign automation currently broken
- **Rollback**: Simple - revert to previous task implementation
- **Test Coverage**: Focus on DI integration, mock repositories

**TODO Items:**
- [ ] `P0-01-A`: Write failing tests for campaign task DI (1h) - High priority
- [ ] `P0-01-B`: Fix CampaignService instantiation in tasks (0.5h) - High priority  
- [ ] `P0-01-C`: Verify Celery task execution works (0.5h) - Medium priority

---

## P0-02: Fix Celery Beat Configuration ⚠️ URGENT

### User Story
As a system administrator, I need scheduled tasks to run correctly so that campaign processing, appointment reminders, and daily reconciliation work automatically.

### Current Problem Analysis
```python
# celery_worker.py - Line 24 - BROKEN REFERENCE
'task': 'services.scheduler_service.run_daily_tasks',  # WRONG PATH
```

### Test Specifications (RED Phase)
```python
# tests/integration/test_celery_beat_integration.py
class TestCeleryBeatConfiguration:
    def test_scheduled_tasks_are_registered(self, celery_app):
        """Test that all beat schedule tasks are registered"""
        beat_schedule = celery_app.conf.beat_schedule
        assert 'run-daily-tasks' in beat_schedule
        
        task_name = beat_schedule['run-daily-tasks']['task']
        assert task_name in celery_app.tasks
        
    def test_daily_tasks_can_execute(self, app, celery_app):
        """Test that daily tasks can execute without errors"""
        with app.app_context():
            task = celery_app.tasks['services.scheduler_service.run_daily_tasks']
            result = task.apply()
            assert result.successful()
```

### Implementation Steps (GREEN Phase)
1. **Update `celery_worker.py` beat schedule**:
   ```python
   'task': 'services.scheduler_service.run_daily_tasks',  # Correct path
   ```

2. **Ensure task import is successful** in celery worker

3. **Test beat schedule execution**:
   ```bash
   docker-compose exec celery celery -A celery_worker.celery beat --loglevel=info
   ```

### Risk Assessment
- **Risk**: High - All scheduled tasks currently broken
- **Rollback**: Revert celery_worker.py changes
- **Impact**: Fixes appointment reminders, review requests, quote conversion

**TODO Items:**
- [ ] `P0-02-A`: Fix Celery beat task path reference (0.5h) - High priority
- [ ] `P0-02-B`: Test beat schedule execution (0.5h) - High priority
- [ ] `P0-02-C`: Verify scheduler service DI works (0.5h) - Medium priority

---

## P0-03: Restore Webhook Processing ⚠️ CRITICAL

### User Story  
As an operator, I need webhook processing to work reliably so that incoming messages, call events, and delivery status updates are captured in the system without data loss.

### Current Problem Analysis
```python
# routes/api_routes.py - Webhook service fallback pattern
webhook_service = current_app.services.get('openphone_webhook') or \
    OpenPhoneWebhookServiceRefactored(/* fallback instantiation */)
```

### Test Specifications (RED Phase)
```python
# tests/integration/test_webhook_processing.py
class TestWebhookProcessing:
    def test_webhook_service_properly_injected(self, client, app):
        """Test webhook service gets proper DI"""
        with app.app_context():
            webhook_service = current_app.services.get('openphone_webhook')
            assert webhook_service is not None
            assert hasattr(webhook_service, 'activity_repository')
            
    def test_message_webhook_processing_end_to_end(self, client, app):
        """Test complete webhook processing with real payload"""
        webhook_payload = {
            'type': 'message.received',
            'data': {
                'object': {
                    'id': 'msg_test123',
                    'direction': 'incoming',
                    'from': '+11234567890',
                    'to': '+19876543210',
                    'text': 'Hello world',
                    'conversationId': 'conv_test123',
                    'createdAt': '2025-08-21T10:00:00Z'
                }
            }
        }
        
        response = client.post('/api/webhooks/openphone', 
                             json=webhook_payload,
                             headers={'Content-Type': 'application/json'})
        
        assert response.status_code == 200
        # Verify activity was created
```

### Implementation Steps (GREEN Phase)
1. **Ensure `openphone_webhook` service is registered** in `app.py`
2. **Remove fallback instantiation** from routes  
3. **Test webhook endpoint with realistic payloads**

### Risk Assessment
- **Risk**: Critical - Message tracking broken
- **Rollback**: Restore fallback pattern temporarily
- **Impact**: All OpenPhone integrations affected

**TODO Items:**
- [ ] `P0-03-A`: Register webhook service in service registry (1h) - Critical priority
- [ ] `P0-03-B`: Remove fallback patterns from API routes (0.5h) - High priority
- [ ] `P0-03-C`: Test end-to-end webhook processing (1h) - High priority

---

# PHASE 1: Foundation & Reliability (20-25 hours)
**Build robust monitoring and data sync systems**

## P1-01: Webhook Health Check Service 🚀 NEW

### User Story
As a system administrator, I need automated webhook health monitoring so that I'm alerted within minutes if OpenPhone message delivery stops working, preventing customer communication failures.

### Business Value
- **Prevents data loss** from missed webhook events
- **Reduces customer support tickets** from missed messages  
- **Enables proactive system maintenance** before users notice issues

### Test Specifications (RED Phase)
```python
# tests/unit/services/test_webhook_health_service.py
class TestWebhookHealthService:
    def test_send_health_check_message_success(self, webhook_health_service, mock_openphone):
        """Test sending health check message"""
        mock_openphone.send_message.return_value = {'success': True, 'id': 'msg_123'}
        
        result = webhook_health_service.send_health_check_message()
        
        assert result.is_success
        assert result.data['message_id'] == 'msg_123'
        mock_openphone.send_message.assert_called_once()
    
    def test_wait_for_webhook_receipt_timeout(self, webhook_health_service):
        """Test timeout when webhook not received"""
        result = webhook_health_service.wait_for_webhook_receipt('msg_123', timeout_seconds=5)
        
        assert result.is_failure
        assert 'timeout' in result.error.lower()
    
    def test_perform_health_check_complete_cycle(self, webhook_health_service, mock_openphone, mock_email):
        """Test complete health check cycle"""
        # Setup successful webhook simulation
        webhook_health_service.simulate_webhook_receipt('msg_123')
        
        result = webhook_health_service.perform_health_check()
        
        assert result.is_success
        assert result.data['status'] == 'healthy'
```

### Implementation Steps (GREEN Phase)

#### 1. Create WebhookHealthService
```python
# services/webhook_health_service.py
class WebhookHealthService:
    def __init__(self, 
                 openphone_service,
                 email_service,
                 webhook_event_repository: WebhookEventRepository,
                 setting_repository: SettingRepository):
        self.openphone_service = openphone_service
        self.email_service = email_service
        self.webhook_event_repository = webhook_event_repository
        self.setting_repository = setting_repository
        
    def perform_health_check(self) -> Result[Dict[str, Any]]:
        """Perform complete health check cycle"""
        # 1. Send test message to dedicated health check number
        # 2. Wait up to 2 minutes for webhook receipt
        # 3. Verify webhook was processed correctly
        # 4. Return health status
        
    def send_health_check_message(self) -> Result[Dict[str, str]]:
        """Send test message for health verification"""
        
    def wait_for_webhook_receipt(self, message_id: str, timeout_seconds: int = 120) -> Result[Dict]:
        """Wait for webhook receipt with timeout"""
        
    def send_health_alert(self, failure_details: str) -> Result[Dict]:
        """Send email alert for health check failure"""
```

#### 2. Create Health Check Task
```python
# tasks/health_check_tasks.py
@celery.task(bind=True)
def webhook_health_check(self):
    """Celery task for automated webhook health monitoring"""
    try:
        with current_app.app_context():
            health_service = current_app.services.get('webhook_health')
            result = health_service.perform_health_check()
            
            if result.is_failure:
                logger.error(f"Webhook health check failed: {result.error}")
                # Health service handles alerting internally
            
            return result.data
            
    except Exception as e:
        logger.error(f"Health check task error: {e}")
        self.retry(countdown=300, max_retries=3)  # Retry in 5 minutes
```

#### 3. Add to Celery Beat Schedule
```python
# celery_worker.py - Add to beat_schedule
'webhook-health-check': {
    'task': 'tasks.health_check_tasks.webhook_health_check',
    'schedule': crontab(minute=0),  # Every hour
},
```

### Configuration Requirements
```python
# Add to app configuration
WEBHOOK_HEALTH_CHECK_FROM_NUMBER="+15551234567"  # Dedicated test number 1
WEBHOOK_HEALTH_CHECK_TO_NUMBER="+15557654321"    # Dedicated test number 2
HEALTH_CHECK_ALERT_EMAIL="admin@attackacrack.com"
```

### Database Migrations Needed
```python
# Add to settings table
INSERT INTO settings (key, value) VALUES 
('webhook_health_enabled', 'true'),
('webhook_health_check_interval_minutes', '60'),
('webhook_health_timeout_seconds', '120');
```

### Risk Assessment & Rollback Plan
- **Risk**: Low - Additive feature, no existing system changes
- **Rollback**: Remove from beat schedule, disable via setting
- **Testing**: Mock OpenPhone API responses, simulate webhook delays

**TODO Items:**
- [ ] `P1-01-A`: Write comprehensive test suite for WebhookHealthService (4h) - High priority
- [ ] `P1-01-B`: Implement WebhookHealthService with Result pattern (6h) - High priority
- [ ] `P1-01-C`: Create health check Celery task with retry logic (2h) - Medium priority
- [ ] `P1-01-D`: Add health check to Celery beat schedule (1h) - Medium priority
- [ ] `P1-01-E`: Configure dedicated test phone numbers (1h) - Low priority
- [ ] `P1-01-F`: Integration test with actual OpenPhone API (2h) - Medium priority

---

## P1-02: Daily Reconciliation Script 🚀 NEW

### User Story  
As a data administrator, I need automated daily reconciliation with OpenPhone so that no messages or calls are missed due to webhook failures, ensuring 100% data accuracy.

### Business Value
- **Prevents revenue loss** from missed leads
- **Ensures audit compliance** with complete communication records
- **Reduces manual data verification work**

### Test Specifications (RED Phase)
```python
# tests/unit/services/test_reconciliation_service.py
class TestReconciliationService:
    def test_get_last_sync_timestamp(self, reconciliation_service, mock_setting_repo):
        """Test retrieving last successful sync timestamp"""
        mock_setting_repo.find_one_by.return_value = Mock(value='2025-08-20T10:00:00Z')
        
        timestamp = reconciliation_service.get_last_sync_timestamp()
        
        assert timestamp == datetime(2025, 8, 20, 10, 0, 0, tzinfo=timezone.utc)
    
    def test_fetch_openphone_activities_since(self, reconciliation_service, mock_openphone):
        """Test fetching activities from OpenPhone API"""
        mock_openphone.get_conversations.return_value = [
            {'id': 'conv_123', 'messages': [{'id': 'msg_456'}]}
        ]
        
        activities = reconciliation_service.fetch_openphone_activities_since(
            datetime(2025, 8, 20, 10, 0, 0, tzinfo=timezone.utc)
        )
        
        assert len(activities) > 0
        assert activities[0]['id'] == 'msg_456'
    
    def test_identify_missing_activities(self, reconciliation_service, mock_activity_repo):
        """Test identifying activities missing from local database"""
        openphone_activities = [
            {'id': 'msg_existing', 'type': 'message'},
            {'id': 'msg_missing', 'type': 'message'}
        ]
        mock_activity_repo.find_by_openphone_id.side_effect = [
            Mock(),  # msg_existing found
            None     # msg_missing not found
        ]
        
        missing = reconciliation_service.identify_missing_activities(openphone_activities)
        
        assert len(missing) == 1
        assert missing[0]['id'] == 'msg_missing'
    
    def test_reconcile_missing_activities_success(self, reconciliation_service, mock_webhook_service):
        """Test successful reconciliation of missing activities"""
        missing_activities = [{'id': 'msg_123', 'type': 'message'}]
        mock_webhook_service.process_webhook.return_value = Result.success({})
        
        result = reconciliation_service.reconcile_missing_activities(missing_activities)
        
        assert result.is_success
        assert result.data['reconciled_count'] == 1
        assert result.data['failed_count'] == 0
```

### Implementation Steps (GREEN Phase)

#### 1. Create ReconciliationService
```python
# services/reconciliation_service.py
class ReconciliationService:
    def __init__(self,
                 openphone_service,
                 webhook_service,
                 activity_repository: ActivityRepository,
                 setting_repository: SettingRepository):
        self.openphone_service = openphone_service
        self.webhook_service = webhook_service
        self.activity_repository = activity_repository
        self.setting_repository = setting_repository
    
    def perform_daily_reconciliation(self) -> Result[Dict[str, Any]]:
        """Perform complete daily reconciliation process"""
        # 1. Get last successful sync timestamp
        # 2. Fetch all OpenPhone activities since then
        # 3. Identify missing activities in local database
        # 4. Process missing activities through webhook service
        # 5. Update last sync timestamp
        # 6. Return reconciliation statistics
        
    def fetch_openphone_activities_since(self, since: datetime) -> List[Dict]:
        """Fetch all OpenPhone activities since timestamp"""
        # Use OpenPhone API pagination to get all conversations and messages
        
    def identify_missing_activities(self, openphone_activities: List[Dict]) -> List[Dict]:
        """Compare OpenPhone data with local database to find gaps"""
        
    def reconcile_missing_activities(self, missing_activities: List[Dict]) -> Result[Dict]:
        """Process missing activities through webhook service"""
```

#### 2. Create Reconciliation Task
```python
# tasks/reconciliation_tasks.py
@celery.task(bind=True)
def daily_reconciliation(self):
    """Daily reconciliation task"""
    try:
        with current_app.app_context():
            reconciliation_service = current_app.services.get('reconciliation')
            result = reconciliation_service.perform_daily_reconciliation()
            
            if result.is_failure:
                logger.error(f"Daily reconciliation failed: {result.error}")
                # Send alert email for failures
                
            logger.info(f"Reconciliation complete: {result.data}")
            return result.data
            
    except Exception as e:
        logger.error(f"Reconciliation task error: {e}")
        self.retry(countdown=1800, max_retries=3)  # Retry in 30 minutes
```

#### 3. Add to Celery Beat Schedule
```python
# celery_worker.py
'daily-reconciliation': {
    'task': 'tasks.reconciliation_tasks.daily_reconciliation',
    'schedule': crontab(hour=2, minute=0),  # 2 AM daily
},
```

### Repository Changes Required
```python
# Add to ActivityRepository
class ActivityRepository(BaseRepository):
    def find_by_openphone_ids(self, openphone_ids: List[str]) -> List[Activity]:
        """Bulk lookup for existing activities by OpenPhone ID"""
        
    def bulk_create_from_openphone_data(self, activities_data: List[Dict]) -> Result[int]:
        """Bulk create activities from OpenPhone API data"""
```

### Database Migrations Needed
```python
# Add reconciliation tracking to settings table
INSERT INTO settings (key, value) VALUES 
('last_openphone_reconciliation', '2025-08-21T00:00:00Z'),
('reconciliation_enabled', 'true'),
('reconciliation_lookback_days', '7');
```

### Risk Assessment & Rollback Plan
- **Risk**: Medium - Large data operations, potential performance impact
- **Rollback**: Disable task in beat schedule, revert timestamp setting
- **Testing**: Mock OpenPhone API, test with limited date ranges first

**TODO Items:**
- [ ] `P1-02-A`: Design reconciliation service interface and tests (3h) - High priority
- [ ] `P1-02-B`: Implement OpenPhone API pagination for bulk data fetch (4h) - High priority
- [ ] `P1-02-C`: Create activity gap detection logic (3h) - Medium priority
- [ ] `P1-02-D`: Implement idempotent webhook processing for reconciliation (4h) - High priority
- [ ] `P1-02-E`: Add bulk operations to ActivityRepository (2h) - Medium priority
- [ ] `P1-02-F`: Create daily reconciliation Celery task (2h) - Medium priority
- [ ] `P1-02-G`: Performance test with large datasets (2h) - Low priority

---

## P1-03: Error Recovery and Retry Logic 🔧 ENHANCEMENT

### User Story
As a system reliability engineer, I need robust error recovery for failed webhook processing so that temporary outages don't result in permanent data loss.

### Test Specifications (RED Phase)
```python
# tests/unit/services/test_webhook_retry_service.py
class TestWebhookRetryService:
    def test_queue_failed_webhook_for_retry(self, retry_service, mock_webhook_repo):
        """Test queuing failed webhook for retry"""
        webhook_event = Mock(id=123, retry_count=0, payload={'type': 'message.received'})
        
        result = retry_service.queue_for_retry(webhook_event, 'Database connection failed')
        
        assert result.is_success
        mock_webhook_repo.update.assert_called_with(
            123, status='retry_queued', error_message='Database connection failed'
        )
    
    def test_process_retry_queue_with_exponential_backoff(self, retry_service):
        """Test retry processing with exponential backoff"""
        failed_webhooks = [
            Mock(id=1, retry_count=1, created_at=datetime.utcnow() - timedelta(minutes=10)),
            Mock(id=2, retry_count=3, created_at=datetime.utcnow() - timedelta(hours=2))
        ]
        
        result = retry_service.process_retry_queue(failed_webhooks)
        
        assert result.is_success
        # Should process webhook 1 (backoff period met) but skip webhook 2
```

### Implementation Steps (GREEN Phase)
1. **Add retry logic to WebhookEventRepository**
2. **Create WebhookRetryService** with exponential backoff
3. **Add retry processing task** to Celery beat schedule
4. **Update webhook processing** to use retry service on failure

**TODO Items:**
- [ ] `P1-03-A`: Implement webhook retry service with exponential backoff (3h) - Medium priority
- [ ] `P1-03-B`: Add retry status tracking to webhook events (1h) - Medium priority
- [ ] `P1-03-C`: Create retry processing Celery task (2h) - Low priority

---

# PHASE 2: Compliance & Safety (25-30 hours)
**Implement legal compliance and safety features**

## P2-01: Opt-out/STOP Processing Pipeline 🚀 NEW COMPLIANCE

### User Story
As a compliance officer, I need comprehensive STOP processing so that the company avoids TCPA violations and potential legal penalties from continued messaging to opted-out users.

### Business Value
- **Prevents legal penalties** (up to $1,500 per violation)
- **Maintains carrier relationships** (prevents number blocking)
- **Builds customer trust** through respect for preferences

### Test Specifications (RED Phase)
```python
# tests/unit/services/test_opt_out_service.py
class TestOptOutService:
    def test_detect_opt_out_keywords(self, opt_out_service):
        """Test detection of opt-out keywords in various formats"""
        test_cases = [
            ('STOP', True),
            ('Please stop texting me', True),
            ('UNSUBSCRIBE', True),
            ('opt out please', True),
            ('This is not a stop message', False),
            ('stop by the store', False)  # Context matters
        ]
        
        for message, expected in test_cases:
            result = opt_out_service.is_opt_out_message(message)
            assert result == expected, f"Failed for: {message}"
    
    def test_process_opt_out_creates_flag(self, opt_out_service, mock_contact_repo, mock_flag_repo):
        """Test that opt-out processing creates proper contact flag"""
        contact = Mock(id=123, phone='+11234567890')
        mock_contact_repo.find_by_phone.return_value = contact
        
        result = opt_out_service.process_opt_out('+11234567890', 'STOP')
        
        assert result.is_success
        mock_flag_repo.create_flag_for_contact.assert_called_with(
            contact_id=123,
            flag_type='opted_out',
            flag_reason='STOP received: STOP',
            applies_to='sms'
        )
    
    def test_send_opt_out_confirmation(self, opt_out_service, mock_openphone):
        """Test sending confirmation message"""
        result = opt_out_service.send_opt_out_confirmation('+11234567890')
        
        assert result.is_success
        mock_openphone.send_message.assert_called_once()
        args = mock_openphone.send_message.call_args[0]
        assert 'unsubscribed' in args[1].lower()
    
    def test_exclude_opted_out_contacts_from_campaigns(self, campaign_service, mock_flag_repo):
        """Test that opted-out contacts are excluded from campaigns"""
        mock_flag_repo.get_contact_ids_with_flag_type.return_value = [123, 456]
        
        contacts = campaign_service.get_eligible_contacts({'exclude_opted_out': True})
        
        # Should exclude contacts 123 and 456
        contact_ids = [c.id for c in contacts]
        assert 123 not in contact_ids
        assert 456 not in contact_ids
```

### Implementation Steps (GREEN Phase)

#### 1. Create OptOutService
```python
# services/opt_out_service.py
class OptOutService:
    # Comprehensive opt-out keyword detection
    OPT_OUT_KEYWORDS = [
        'stop', 'unsubscribe', 'opt out', 'opt-out', 'remove me', 
        'cancel', 'quit', 'end', 'leave me alone', 'no more',
        'take me off', 'delete', 'remove', 'block'
    ]
    
    def __init__(self,
                 contact_repository: ContactRepository,
                 contact_flag_repository: ContactFlagRepository,
                 campaign_repository: CampaignRepository,
                 openphone_service):
        self.contact_repository = contact_repository
        self.contact_flag_repository = contact_flag_repository
        self.campaign_repository = campaign_repository
        self.openphone_service = openphone_service
    
    def process_opt_out(self, phone: str, message: str) -> Result[Dict]:
        """Process opt-out request and create flag"""
        # 1. Find contact by phone number
        # 2. Create opted_out flag
        # 3. Remove from all active campaigns
        # 4. Send confirmation message
        # 5. Log opt-out event
        
    def is_opt_out_message(self, message: str) -> bool:
        """Detect opt-out intent with context awareness"""
        
    def send_opt_out_confirmation(self, phone: str) -> Result[Dict]:
        """Send confirmation message per compliance requirements"""
        
    def remove_from_active_campaigns(self, contact_id: int) -> Result[int]:
        """Remove contact from all active campaigns"""
```

#### 2. Update Webhook Service Integration
```python
# Update openphone_webhook_service_refactored.py
def _handle_message_webhook(self, webhook_data: Dict) -> Result[Dict]:
    # Add opt-out processing for incoming messages
    if direction == 'incoming':
        opt_out_service = current_app.services.get('opt_out')
        opt_out_result = opt_out_service.process_opt_out(from_number, body)
        if opt_out_result.is_success and opt_out_result.data.get('opted_out'):
            # Log opt-out processing
            logger.info(f"Processed opt-out from {from_number}")
```

#### 3. Create Opt-Out Webhook Integration Task
```python
# tasks/opt_out_tasks.py
@celery.task
def process_opt_out_message(phone: str, message: str):
    """Process potential opt-out message asynchronously"""
    with current_app.app_context():
        opt_out_service = current_app.services.get('opt_out')
        return opt_out_service.process_opt_out(phone, message).data
```

### Database Migrations Needed
```python
# Migration: Add opt-out tracking
class OptOutTracking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    phone = db.Column(db.String(20), nullable=False, index=True)
    opted_out_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    original_message = db.Column(db.Text)
    confirmation_sent = db.Column(db.Boolean, default=False)
```

### Risk Assessment & Rollback Plan
- **Risk**: Critical - Legal compliance required
- **Rollback**: Not recommended - compliance feature
- **Testing**: Test with real carrier keywords, verify instant processing

**TODO Items:**
- [ ] `P2-01-A`: Create comprehensive opt-out keyword detection tests (3h) - Critical priority
- [ ] `P2-01-B`: Implement OptOutService with Result pattern (4h) - Critical priority
- [ ] `P2-01-C`: Integrate opt-out processing into webhook service (2h) - High priority
- [ ] `P2-01-D`: Create opt-out confirmation message templates (1h) - Medium priority
- [ ] `P2-01-E`: Add opt-out exclusion to campaign filtering (2h) - High priority
- [ ] `P2-01-F`: Create opt-out tracking database schema (1h) - Medium priority
- [ ] `P2-01-G`: Test with real carrier opt-out requirements (2h) - High priority

---

## P2-02: Phone Number Validation Integration 🚀 NEW COMPLIANCE

### User Story
As a campaign manager, I need phone number validation during import so that I only send messages to valid mobile numbers, reducing bounce rates and preventing carrier penalties.

### Business Value
- **Reduces bounce rates** from 10% to <2%
- **Prevents carrier blocking** of business numbers
- **Improves delivery rates** and campaign effectiveness
- **Saves money** on invalid number sends

### Test Specifications (RED Phase)
```python
# tests/unit/services/test_phone_validation_service.py
class TestPhoneValidationService:
    def test_validate_single_number_valid_mobile(self, validation_service, mock_numverify):
        """Test validation of valid mobile number"""
        mock_numverify.return_value = {
            'valid': True,
            'line_type': 'mobile',
            'carrier': 'Verizon',
            'location': 'Boston, MA'
        }
        
        result = validation_service.validate_phone_number('+11234567890')
        
        assert result.is_success
        assert result.data['valid'] is True
        assert result.data['line_type'] == 'mobile'
    
    def test_validate_batch_numbers(self, validation_service):
        """Test batch validation of multiple numbers"""
        phone_numbers = ['+11234567890', '+19876543210', '+15555555555']
        
        result = validation_service.validate_batch(phone_numbers)
        
        assert result.is_success
        assert len(result.data['results']) == 3
        assert 'valid_mobile_count' in result.data['summary']
    
    def test_validation_rate_limiting(self, validation_service):
        """Test that rate limiting is respected"""
        # NumVerify allows 1000 requests/month on free tier
        result = validation_service.check_rate_limit()
        
        assert result.is_success
        assert 'requests_remaining' in result.data
    
    def test_cache_validation_results(self, validation_service, mock_cache):
        """Test that validation results are cached"""
        validation_service.validate_phone_number('+11234567890')
        validation_service.validate_phone_number('+11234567890')  # Second call
        
        # Should only make one external API call
        assert mock_numverify.call_count == 1
```

### Implementation Steps (GREEN Phase)

#### 1. Create PhoneValidationService
```python
# services/phone_validation_service.py
class PhoneValidationService:
    def __init__(self, 
                 contact_repository: ContactRepository,
                 setting_repository: SettingRepository):
        self.contact_repository = contact_repository
        self.setting_repository = setting_repository
        self.api_key = os.environ.get('NUMVERIFY_API_KEY')
        self.cache = {}  # Simple in-memory cache
    
    def validate_phone_number(self, phone: str) -> Result[Dict]:
        """Validate single phone number via NumVerify API"""
        # 1. Check cache first
        # 2. Make NumVerify API call
        # 3. Parse response and determine validity
        # 4. Cache result
        # 5. Return standardized format
        
    def validate_batch(self, phone_numbers: List[str]) -> Result[Dict]:
        """Validate batch of phone numbers with rate limiting"""
        # 1. Check rate limits
        # 2. Process in chunks to respect API limits
        # 3. Return summary statistics
        
    def is_mobile_number(self, validation_result: Dict) -> bool:
        """Determine if number is mobile based on validation result"""
        mobile_types = ['mobile', 'cell', 'wireless']
        return validation_result.get('line_type', '').lower() in mobile_types
```

#### 2. Integrate with CSV Import Service
```python
# Update csv_import_service.py
def process_csv_with_validation(self, file_path: str, validate_phones: bool = True) -> Result[Dict]:
    """Process CSV import with optional phone validation"""
    if validate_phones:
        validation_service = current_app.services.get('phone_validation')
        # Validate phone numbers before creating contacts
        validation_results = validation_service.validate_batch(phone_numbers)
        # Filter out invalid numbers or landlines
```

#### 3. Create Validation Background Task
```python
# tasks/phone_validation_tasks.py
@celery.task
def validate_contact_phone_numbers(contact_ids: List[int]):
    """Background task to validate existing contact phone numbers"""
    with current_app.app_context():
        validation_service = current_app.services.get('phone_validation')
        contact_repository = current_app.services.get('contact_repository')
        
        for contact_id in contact_ids:
            contact = contact_repository.get_by_id(contact_id)
            if contact and contact.phone:
                result = validation_service.validate_phone_number(contact.phone)
                # Update contact with validation status
```

### Configuration Requirements
```python
# Environment variables
NUMVERIFY_API_KEY=your_api_key_here
PHONE_VALIDATION_ENABLED=true
PHONE_VALIDATION_CACHE_TTL=3600  # 1 hour
```

### Database Migrations Needed
```python
# Add validation fields to contacts table
ALTER TABLE contacts ADD COLUMN phone_validated BOOLEAN DEFAULT FALSE;
ALTER TABLE contacts ADD COLUMN phone_validation_result JSONB;
ALTER TABLE contacts ADD COLUMN phone_line_type VARCHAR(20);
```

### Risk Assessment & Rollback Plan
- **Risk**: Medium - External API dependency
- **Rollback**: Disable validation flag, continue imports without validation
- **Cost Impact**: NumVerify free tier: 1000 validations/month

**TODO Items:**
- [ ] `P2-02-A`: Research and sign up for NumVerify API account (1h) - High priority
- [ ] `P2-02-B`: Create phone validation service tests (3h) - High priority
- [ ] `P2-02-C`: Implement NumVerify API integration (4h) - High priority
- [ ] `P2-02-D`: Add validation option to CSV import process (3h) - Medium priority
- [ ] `P2-02-E`: Create phone validation database schema (1h) - Medium priority
- [ ] `P2-02-F`: Implement validation result caching (2h) - Low priority
- [ ] `P2-02-G`: Add validation rate limiting and error handling (2h) - Medium priority

---

## P2-03: Consent Tracking System 🚀 NEW COMPLIANCE

### User Story
As a compliance manager, I need to track consent for all SMS communications so that we can demonstrate compliance with TCPA regulations during audits.

### Test Specifications (RED Phase)
```python
# tests/unit/services/test_consent_service.py
class TestConsentService:
    def test_record_explicit_consent(self, consent_service, mock_consent_repo):
        """Test recording explicit consent with timestamp"""
        result = consent_service.record_consent(
            phone='+11234567890',
            consent_type='explicit',
            source='website_signup',
            details={'form_id': 'contact_us_123'}
        )
        
        assert result.is_success
        mock_consent_repo.create.assert_called_with(
            phone='+11234567890',
            consent_type='explicit',
            source='website_signup',
            granted_at=ANY,
            details={'form_id': 'contact_us_123'}
        )
    
    def test_check_consent_status(self, consent_service, mock_consent_repo):
        """Test checking current consent status for phone number"""
        mock_consent_repo.get_latest_consent.return_value = Mock(
            consent_type='explicit',
            status='active'
        )
        
        result = consent_service.check_consent_status('+11234567890')
        
        assert result.is_success
        assert result.data['consent_type'] == 'explicit'
        assert result.data['status'] == 'active'
```

### Implementation Steps (GREEN Phase)
1. **Create consent tracking database schema**
2. **Implement ConsentService** with audit trail
3. **Integrate consent checking** into campaign filtering
4. **Add consent recording** to contact creation process

**TODO Items:**
- [ ] `P2-03-A`: Design consent tracking schema (2h) - Medium priority
- [ ] `P2-03-B`: Implement ConsentService (4h) - Medium priority
- [ ] `P2-03-C`: Integrate consent checks into campaigns (3h) - High priority

---

## P2-04: Do Not Call (DNC) List Management 🚀 NEW COMPLIANCE

### User Story
As a compliance officer, I need DNC list integration so that we never send marketing messages to numbers on federal or state do-not-call lists.

### Test Specifications (RED Phase)
```python
# tests/unit/services/test_dnc_service.py
class TestDNCService:
    def test_check_federal_dnc_list(self, dnc_service, mock_dnc_api):
        """Test checking number against federal DNC list"""
        mock_dnc_api.check_number.return_value = {'on_list': True, 'list': 'federal'}
        
        result = dnc_service.check_dnc_status('+11234567890')
        
        assert result.is_success
        assert result.data['on_dnc_list'] is True
        assert result.data['list_type'] == 'federal'
```

### Implementation Steps (GREEN Phase)
1. **Integrate with DNC API** (e.g., ScrubLists API)
2. **Create DNC checking service**
3. **Add DNC filtering** to campaign eligibility
4. **Implement DNC flag creation** for blocked numbers

**TODO Items:**
- [ ] `P2-04-A`: Research DNC API providers (2h) - Low priority
- [ ] `P2-04-B`: Implement DNC checking service (4h) - Low priority
- [ ] `P2-04-C`: Add DNC filtering to campaigns (2h) - Low priority

---

# PHASE 3: Campaign Engine Enhancement (30-35 hours)
**Advanced campaign features and analytics**

## P3-01: Fix Stateful Campaign Tracking 🔧 CRITICAL

### User Story
As a campaign manager, I need accurate campaign member status tracking so that I can see real delivery rates, response rates, and avoid sending duplicate messages to the same contact.

### Current Problem Analysis
```python
# services/campaign_service_refactored.py - Lines 888-897
# Campaign member status updates are inconsistent
# No activity linkage for tracking actual delivery
```

### Test Specifications (RED Phase)
```python
# tests/unit/services/test_campaign_tracking.py
class TestCampaignTracking:
    def test_campaign_member_status_progression(self, campaign_service, mock_repos):
        """Test status progression: pending -> sent -> delivered -> responded"""
        campaign_id = 123
        contact_id = 456
        
        # Initial status should be pending
        member = campaign_service.get_campaign_member(campaign_id, contact_id)
        assert member.status == 'pending'
        
        # After sending
        campaign_service.update_member_status(campaign_id, contact_id, 'sent')
        member = campaign_service.get_campaign_member(campaign_id, contact_id)
        assert member.status == 'sent'
        assert member.sent_at is not None
        
        # After delivery webhook
        campaign_service.update_member_status(campaign_id, contact_id, 'delivered')
        member = campaign_service.get_campaign_member(campaign_id, contact_id)
        assert member.status == 'delivered'
        assert member.delivered_at is not None
    
    def test_activity_linkage_for_tracking(self, campaign_service):
        """Test that campaign members are linked to activities"""
        result = campaign_service.send_campaign_message(
            campaign_id=123, contact_id=456, message='Test'
        )
        
        assert result.is_success
        member = campaign_service.get_campaign_member(123, 456)
        assert member.activity_id is not None  # Linked to sent message activity
    
    def test_response_detection_and_linking(self, campaign_service):
        """Test response detection from incoming messages"""
        # Simulate incoming message webhook for campaign member
        result = campaign_service.link_response_to_campaign(
            phone='+11234567890',
            incoming_activity_id=789
        )
        
        assert result.is_success
        # Should find recent campaign send and link response
```

### Implementation Steps (GREEN Phase)

#### 1. Add Activity Linkage to Campaign Members
```python
# Migration: Add activity tracking to campaign members
ALTER TABLE campaign_members ADD COLUMN sent_activity_id INTEGER;
ALTER TABLE campaign_members ADD COLUMN reply_activity_id INTEGER;
ALTER TABLE campaign_members ADD COLUMN sent_at TIMESTAMP;
ALTER TABLE campaign_members ADD COLUMN delivered_at TIMESTAMP;
ALTER TABLE campaign_members ADD COLUMN responded_at TIMESTAMP;

# Add foreign key constraints
ALTER TABLE campaign_members ADD CONSTRAINT fk_sent_activity 
    FOREIGN KEY (sent_activity_id) REFERENCES activities(id);
ALTER TABLE campaign_members ADD CONSTRAINT fk_reply_activity 
    FOREIGN KEY (reply_activity_id) REFERENCES activities(id);
```

#### 2. Update CampaignService for Stateful Tracking
```python
# services/campaign_service_refactored.py
def send_campaign_message(self, campaign_id: int, contact_id: int, message: str) -> Result[Dict]:
    """Send message and create proper state tracking"""
    # 1. Send message via OpenPhone
    # 2. Create activity record for sent message
    # 3. Update campaign member with sent_activity_id and sent_at
    # 4. Return success with activity reference
    
def link_response_to_campaign(self, phone: str, incoming_activity_id: int) -> Result[Dict]:
    """Link incoming message response to recent campaign send"""
    # 1. Find contact by phone
    # 2. Find recent campaign sends to this contact (last 7 days)
    # 3. Link response to most recent campaign member
    # 4. Update member status to 'responded' with timestamp
```

#### 3. Update Webhook Service for Status Updates
```python
# services/openphone_webhook_service_refactored.py
def _handle_message_webhook(self, webhook_data: Dict) -> Result[Dict]:
    # For incoming messages, check if it's a response to campaign
    if direction == 'incoming':
        campaign_service = current_app.services.get('campaign')
        campaign_service.link_response_to_campaign(from_number, activity.id)
    
    # For outgoing message status updates (delivered, failed)
    elif direction == 'outgoing' and status in ['delivered', 'failed', 'read']:
        campaign_service = current_app.services.get('campaign')
        campaign_service.update_member_status_from_activity(openphone_id, status)
```

### Risk Assessment & Rollback Plan
- **Risk**: Medium - Database schema changes required
- **Rollback**: Revert migration, restore old status tracking
- **Testing**: Focus on webhook integration, status progression

**TODO Items:**
- [ ] `P3-01-A`: Create campaign member status progression tests (4h) - Critical priority
- [ ] `P3-01-B`: Add activity linkage database schema (1h) - High priority
- [ ] `P3-01-C`: Implement stateful campaign tracking (6h) - Critical priority
- [ ] `P3-01-D`: Update webhook service for status updates (3h) - High priority
- [ ] `P3-01-E`: Add response detection and linking (4h) - Medium priority
- [ ] `P3-01-F`: Update analytics to use accurate status tracking (2h) - Medium priority

---

## P3-02: Throttled Sending Implementation 🔧 ENHANCEMENT

### User Story
As a campaign manager, I need throttled message sending so that I can respect OpenPhone's 125 messages/day limit and avoid carrier penalties for bulk sending.

### Test Specifications (RED Phase)
```python
# tests/unit/services/test_campaign_throttling.py
class TestCampaignThrottling:
    def test_daily_limit_enforcement(self, campaign_service, mock_campaign_repo):
        """Test that daily limit is enforced"""
        mock_campaign_repo.get_today_send_count.return_value = 124
        
        can_send, remaining = campaign_service.can_send_today(campaign_id=123)
        
        assert can_send is True
        assert remaining == 1
    
    def test_business_hours_restriction(self, campaign_service):
        """Test business hours restriction"""
        # Mock current time to be outside business hours
        with patch('datetime.datetime') as mock_dt:
            mock_dt.now.return_value = datetime(2025, 8, 21, 22, 0, 0)  # 10 PM
            
            is_business_hours = campaign_service.is_business_hours()
            
            assert is_business_hours is False
    
    def test_throttled_queue_processing(self, campaign_service):
        """Test that queue processing respects throttling rules"""
        result = campaign_service.process_campaign_queue()
        
        assert result.is_success
        # Should not send more than daily limit
        assert result.data['messages_sent'] <= 125
```

### Implementation Steps (GREEN Phase)
1. **Enhance daily limit tracking** with accurate counting
2. **Implement business hours checking** with timezone support
3. **Add rate limiting** to campaign queue processing
4. **Create throttling dashboard** for monitoring

**TODO Items:**
- [ ] `P3-02-A`: Implement accurate daily send counting (2h) - Medium priority
- [ ] `P3-02-B`: Add timezone-aware business hours checking (2h) - Low priority
- [ ] `P3-02-C`: Create throttling monitoring dashboard (3h) - Low priority

---

## P3-03: Complete A/B Testing Analytics 🔧 ENHANCEMENT

### User Story
As a marketing manager, I need statistical A/B testing results so that I can make data-driven decisions about message effectiveness and optimize campaign performance.

### Test Specifications (RED Phase)
```python
# tests/unit/services/test_ab_testing.py
class TestABTesting:
    def test_statistical_significance_calculation(self, campaign_service):
        """Test chi-square test for A/B significance"""
        # Mock A/B test results: A (10% response), B (15% response)
        mock_results = {
            'A': {'sent': 1000, 'responded': 100, 'response_rate': 0.10},
            'B': {'sent': 1000, 'responded': 150, 'response_rate': 0.15}
        }
        
        analysis = campaign_service.analyze_ab_test(campaign_id=123)
        
        assert analysis['status'] == 'complete'
        assert analysis['winner'] == 'B'
        assert analysis['confidence'] >= 95.0
    
    def test_minimum_sample_size_enforcement(self, campaign_service):
        """Test that minimum sample size is enforced"""
        mock_results = {
            'A': {'sent': 50, 'responded': 5},
            'B': {'sent': 50, 'responded': 8}
        }
        
        analysis = campaign_service.analyze_ab_test(campaign_id=123)
        
        assert analysis['status'] == 'insufficient_data'
        assert 'minimum' in analysis['message'].lower()
```

### Implementation Steps (GREEN Phase)
1. **Fix statistical testing** with proper chi-square implementation
2. **Add confidence interval calculations**
3. **Implement sample size recommendations**
4. **Create A/B test dashboard** with visual analytics

**TODO Items:**
- [ ] `P3-03-A`: Fix A/B testing statistical calculations (4h) - Medium priority
- [ ] `P3-03-B`: Add confidence intervals and effect size (3h) - Low priority
- [ ] `P3-03-C`: Create A/B testing dashboard (4h) - Low priority

---

## P3-04: Advanced Campaign Templates 🚀 NEW

### User Story
As a campaign creator, I need advanced template features like conditional content and dynamic personalization so that I can create more engaging and relevant messages.

### Test Specifications (RED Phase)
```python
# tests/unit/services/test_campaign_templates.py
class TestCampaignTemplates:
    def test_conditional_personalization(self, template_service):
        """Test conditional content based on contact data"""
        template = "Hi {first_name|there}! {if company}We see you work at {company}.{endif}"
        contact = Mock(first_name='John', company='Acme Corp')
        
        result = template_service.render_template(template, contact)
        
        assert result == "Hi John! We see you work at Acme Corp."
    
    def test_fallback_personalization(self, template_service):
        """Test fallback values for missing contact data"""
        template = "Hi {first_name|valued customer}!"
        contact = Mock(first_name=None)
        
        result = template_service.render_template(template, contact)
        
        assert result == "Hi valued customer!"
```

### Implementation Steps (GREEN Phase)
1. **Create advanced template engine** with conditional logic
2. **Add template validation** and preview features
3. **Implement template library** with saved templates
4. **Add template analytics** for performance tracking

**TODO Items:**
- [ ] `P3-04-A`: Design advanced template syntax (3h) - Low priority
- [ ] `P3-04-B`: Implement template engine with conditionals (5h) - Low priority
- [ ] `P3-04-C`: Create template validation and preview (3h) - Low priority

---

# Implementation Timeline & Resource Allocation

## Sprint Planning (4 Sprints x 1 Week Each)

### Sprint 1: Foundation Fixes (Week 1)
**Focus**: Fix critical existing issues
- **Phase 0 Complete**: All dependency injection fixes
- **P1-01 Complete**: Webhook health check service
- **Estimated Effort**: 20-25 hours

### Sprint 2: Data Reliability (Week 2)
**Focus**: Ensure data accuracy and sync
- **P1-02 Complete**: Daily reconciliation system
- **P1-03 Complete**: Error recovery and retry logic
- **Estimated Effort**: 20-25 hours

### Sprint 3: Compliance & Safety (Week 3)
**Focus**: Legal compliance features
- **P2-01 Complete**: Opt-out/STOP processing
- **P2-02 Complete**: Phone number validation
- **P2-03 Partial**: Consent tracking (basic implementation)
- **Estimated Effort**: 25-30 hours

### Sprint 4: Campaign Enhancement (Week 4)
**Focus**: Advanced campaign features
- **P3-01 Complete**: Fix stateful tracking
- **P3-02 Complete**: Throttled sending
- **P3-03 Partial**: A/B testing improvements
- **Estimated Effort**: 20-25 hours

## Risk Mitigation & Rollback Strategy

### High-Risk Changes
1. **Database Schema Changes** (P3-01)
   - **Mitigation**: Test migrations in staging first
   - **Rollback**: Create down migrations for all schema changes

2. **External API Dependencies** (P2-02, P2-04)
   - **Mitigation**: Implement circuit breakers and fallback modes
   - **Rollback**: Feature flags to disable validation

3. **Celery Task Changes** (P0-01, P0-02)
   - **Mitigation**: Deploy during low-traffic hours
   - **Rollback**: Revert celery_worker.py to previous version

### Testing Strategy
1. **Unit Tests**: 95%+ coverage for all new services
2. **Integration Tests**: End-to-end workflow testing
3. **Load Testing**: Campaign queue processing under load
4. **Compliance Testing**: Opt-out processing with real keywords

## Success Metrics & KPIs

### Phase 0 Success Criteria
- [ ] All Celery tasks execute without dependency injection errors
- [ ] Beat schedule runs successfully every hour
- [ ] Webhook processing has 100% uptime for 48 hours

### Phase 1 Success Criteria
- [ ] Health check detects webhook failures within 5 minutes
- [ ] Reconciliation script runs daily without errors
- [ ] Data sync accuracy improves to 99.5%+

### Phase 2 Success Criteria
- [ ] Opt-out processing handles 100% of STOP keywords
- [ ] Phone validation reduces bounce rate to <2%
- [ ] Full TCPA compliance audit readiness

### Phase 3 Success Criteria
- [ ] Campaign tracking accuracy reaches 95%+
- [ ] Throttling prevents OpenPhone API rate limiting
- [ ] A/B testing provides statistically valid results

## Deployment & Monitoring Plan

### Deployment Phases
1. **Staging Deployment**: All features tested in staging environment
2. **Canary Release**: Gradual rollout with monitoring
3. **Full Production**: Complete feature activation

### Monitoring & Alerting
1. **Health Check Monitoring**: PagerDuty integration for webhook failures
2. **Campaign Performance**: Real-time dashboards for send rates and errors
3. **Compliance Monitoring**: Alerts for opt-out processing failures

### Documentation Requirements
1. **API Documentation**: Update for all new endpoints
2. **Compliance Documentation**: TCPA compliance procedures
3. **Runbook Documentation**: Troubleshooting guides for operators

---

## Conclusion

This technical plan addresses all critical gaps identified in the SMS Campaign system while maintaining strict adherence to Test-Driven Development principles. The phased approach ensures reliable progress with built-in rollback capabilities.

**Key Success Factors:**
1. **TDD Enforcement**: Every feature implemented with tests first
2. **Repository Pattern**: Consistent data access abstraction
3. **Result Pattern**: Standardized error handling
4. **Dependency Injection**: Clean service boundaries
5. **Incremental Deployment**: Risk mitigation through phased rollout

**Immediate Next Steps:**
1. Review and approve this implementation plan
2. Begin Phase 0 fixes with dependency injection issues
3. Set up monitoring and testing infrastructure
4. Execute Sprint 1 with daily standups and progress tracking

*Total Estimated Effort: 77-94 hours across 4 weeks*
*Expected Completion: September 18, 2025*