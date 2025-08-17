# Service Dependency Audit

## Audit Date: August 17, 2025

This document audits all services in the `/services` directory to identify:
1. External dependencies (APIs, libraries)
2. Inter-service dependencies
3. Direct database access
4. Dependency injection readiness

## Service Analysis

### 1. AIService (`ai_service.py`)
**Current Dependencies:**
- External: Google Gemini API (`genai` library)
- Database: Direct - Activity model queries
- Other Services: None
- DI Status: ❌ Not using DI

**Required Changes:**
- [ ] Accept API key via constructor
- [ ] Create repository for Activity queries

---

### 2. AppointmentService (`appointment_service.py`)
**Current Dependencies:**
- External: Direct imports from `api_integrations.py`
  - `create_google_calendar_event`
  - `delete_google_calendar_event`
- Database: Direct - Appointment model queries
- Other Services: None
- DI Status: ❌ Not using DI

**Required Changes:**
- [ ] Create GoogleCalendarService
- [ ] Accept GoogleCalendarService via constructor
- [ ] Create AppointmentRepository

---

### 3. AuthService (`auth_service.py`)
**Current Dependencies:**
- External: Flask-Mail, Flask-Bcrypt
- Database: Direct - User, InviteToken queries
- Other Services: None
- DI Status: ❌ Not using DI (static methods)

**Required Changes:**
- [ ] Convert from static methods to instance methods
- [ ] Accept mail service via constructor
- [ ] Create UserRepository

---

### 4. CampaignListService (`campaign_list_service.py`)
**Current Dependencies:**
- External: None
- Database: Direct - CampaignList, CampaignListMember queries
- Other Services: None
- DI Status: ❌ Not using DI

**Required Changes:**
- [ ] Create CampaignListRepository

---

### 5. CampaignService (`campaign_service.py`)
**Current Dependencies:**
- External: None
- Database: Direct - Campaign, CampaignMembership, Contact, ContactFlag queries
- Other Services: 
  - OpenPhoneService (injected via constructor) ✅
  - CampaignListService (injected via constructor) ✅
- DI Status: ⚠️ Partial DI (services injected, but DB access is direct)

**Required Changes:**
- [ ] Create CampaignRepository
- [ ] Create ContactRepository (shared with ContactService)

---

### 6. ContactService (`contact_service.py`)
**Current Dependencies:**
- External: None
- Database: Direct - Contact, ContactFlag, Property, Job queries
- Other Services: None
- DI Status: ❌ Not using DI

**Required Changes:**
- [ ] Create ContactRepository
- [ ] Create PropertyRepository

---

### 7. ConversationService (`conversation_service.py`)
**Current Dependencies:**
- External: None
- Database: Direct - Conversation, Activity queries
- Other Services: None
- DI Status: ❌ Not using DI

**Required Changes:**
- [ ] Create ConversationRepository
- [ ] Create ActivityRepository

---

### 8. CSVImportService (`csv_import_service.py`)
**Current Dependencies:**
- External: CSV, pandas-like operations
- Database: Direct - Contact, CSVImport, CampaignList queries
- Other Services:
  - ContactService (injected via constructor) ✅
- DI Status: ⚠️ Partial DI

**Required Changes:**
- [ ] Use ContactRepository instead of direct queries
- [ ] Create CSVImportRepository

---

### 9. DashboardService (`dashboard_service.py`)
**Current Dependencies:**
- External: None
- Database: Direct - Contact, Activity, Campaign, Conversation queries
- Other Services: None
- DI Status: ❌ Not using DI

**Required Changes:**
- [ ] Accept repositories via constructor
- [ ] Heavy refactoring needed - too many direct queries

---

### 10. DiagnosticsService (`diagnostics_service.py`)
**Current Dependencies:**
- External: Redis (direct connection test)
- Database: Direct - SQLAlchemy connection test
- Other Services: None
- DI Status: ❌ Not using DI

**Required Changes:**
- [ ] Accept Redis client via constructor
- [ ] Accept DB connection via constructor

---

### 11. InvoiceService (`invoice_service.py`)
**Current Dependencies:**
- External: None
- Database: Direct - Invoice, Quote queries
- Other Services: None (static methods)
- DI Status: ❌ Not using DI

**Required Changes:**
- [ ] Convert from static methods to instance methods
- [ ] Create InvoiceRepository
- [ ] Accept QuoteService via constructor

---

### 12. JobService (`job_service.py`)
**Current Dependencies:**
- External: None
- Database: Direct - Job queries
- Other Services: None
- DI Status: ❌ Not using DI

**Required Changes:**
- [ ] Create JobRepository

---

### 13. MessageService (`message_service.py`)
**Current Dependencies:**
- External: None
- Database: Direct - Activity, Conversation queries
- Other Services: None
- DI Status: ❌ Not using DI

**Required Changes:**
- [ ] Create/use ActivityRepository
- [ ] Create/use ConversationRepository

---

### 14. OpenPhoneService (`openphone_service.py`)
**Current Dependencies:**
- External: OpenPhone API (requests library)
- Database: None ✅
- Other Services: None
- DI Status: ⚠️ API key from config, not injected

**Required Changes:**
- [ ] Accept API configuration via constructor

---

### 15. OpenPhoneSyncService (`openphone_sync_service.py`)
**Current Dependencies:**
- External: Celery tasks
- Database: Direct - Contact, Activity queries
- Other Services: Tasks (imported directly)
- DI Status: ❌ Not using DI

**Required Changes:**
- [ ] Accept task queue via constructor
- [ ] Use repositories for DB access

---

### 16. OpenPhoneWebhookService (`openphone_webhook_service.py`)
**Current Dependencies:**
- External: None
- Database: Direct - WebhookEvent, Activity, Contact queries
- Other Services: 
  - SMSMetricsService (instantiated internally) ❌
- DI Status: ❌ Not using DI

**Required Changes:**
- [ ] Accept SMSMetricsService via constructor
- [ ] Create WebhookEventRepository

---

### 17. PropertyService (`property_service.py`)
**Current Dependencies:**
- External: None
- Database: Direct - Property queries
- Other Services: None
- DI Status: ❌ Not using DI

**Required Changes:**
- [ ] Create PropertyRepository

---

### 18. QuickBooksService (`quickbooks_service.py`)
**Current Dependencies:**
- External: QuickBooks API, OAuth2
- Database: Direct - QuickBooksAuth queries
- Other Services: None
- DI Status: ❌ Not using DI

**Required Changes:**
- [ ] Accept OAuth client via constructor
- [ ] Create QuickBooksAuthRepository

---

### 19. QuickBooksSyncService (`quickbooks_sync_service.py`)
**Current Dependencies:**
- External: None
- Database: Direct - Contact, QuickBooksCustomer queries
- Other Services:
  - QuickBooksService (instantiated internally) ❌
- DI Status: ❌ Not using DI

**Required Changes:**
- [ ] Accept QuickBooksService via constructor
- [ ] Use repositories for DB access

---

### 20. QuoteService (`quote_service.py`)
**Current Dependencies:**
- External: None
- Database: Direct - Quote, QuoteLineItem queries
- Other Services: None
- DI Status: ❌ Not using DI

**Required Changes:**
- [ ] Create QuoteRepository

---

### 21. SchedulerService (`scheduler_service.py`)
**Current Dependencies:**
- External: APScheduler
- Database: Direct - Campaign queries
- Other Services: Celery tasks (direct import)
- DI Status: ❌ Not using DI

**Required Changes:**
- [ ] Accept scheduler instance via constructor
- [ ] Accept task queue via constructor

---

### 22. SMSMetricsService (`sms_metrics_service.py`)
**Current Dependencies:**
- External: None
- Database: Direct - Activity, CampaignMembership queries
- Other Services: None
- DI Status: ❌ Not using DI

**Required Changes:**
- [ ] Use ActivityRepository
- [ ] Use CampaignRepository

---

### 23. SyncHealthService (`sync_health_service.py`)
**Current Dependencies:**
- External: Celery
- Database: None ✅
- Other Services: None
- DI Status: ⚠️ Celery from current_app

**Required Changes:**
- [ ] Accept Celery instance via constructor

---

### 24. TaskService (`task_service.py`)
**Current Dependencies:**
- External: Celery
- Database: None ✅
- Other Services: None
- DI Status: ⚠️ Celery from current_app

**Required Changes:**
- [ ] Accept Celery instance via constructor

---

### 25. TodoService (`todo_service.py`)
**Current Dependencies:**
- External: None
- Database: Direct - Todo queries
- Other Services: None
- DI Status: ❌ Not using DI

**Required Changes:**
- [ ] Create TodoRepository

---

## Summary Statistics

### Current State
- **Total Services:** 25
- **Using Full DI:** 0 (0%)
- **Using Partial DI:** 3 (12%)
- **No DI:** 22 (88%)
- **Direct DB Access:** 21 (84%)
- **External API Dependencies:** 7 (28%)

### Services Already Accepting Dependencies
1. CampaignService (accepts OpenPhoneService, CampaignListService)
2. CSVImportService (accepts ContactService)

### Services Creating Internal Dependencies (Anti-pattern)
1. OpenPhoneWebhookService → creates SMSMetricsService
2. QuickBooksSyncService → creates QuickBooksService

## Dependency Graph

### Level 0 (No Dependencies)
- OpenPhoneService
- AIService
- SchedulerService (after DI refactor)

### Level 1 (Simple Dependencies)
- MessageService → ActivityRepository, ConversationRepository
- ContactService → ContactRepository, PropertyRepository
- TodoService → TodoRepository
- PropertyService → PropertyRepository
- JobService → JobRepository
- DiagnosticsService → Redis, DB connection

### Level 2 (Service Dependencies)
- CampaignService → OpenPhoneService, CampaignListService, Repositories
- CSVImportService → ContactService, Repositories
- SMSMetricsService → ActivityRepository, CampaignRepository
- AppointmentService → GoogleCalendarService, AppointmentRepository
- QuoteService → QuoteRepository
- InvoiceService → QuoteService, InvoiceRepository

### Level 3 (Multiple Dependencies)
- DashboardService → Multiple services and repositories
- OpenPhoneWebhookService → SMSMetricsService, Repositories
- QuickBooksSyncService → QuickBooksService, Repositories
- OpenPhoneSyncService → TaskQueue, Repositories

### Level 4 (Complex Dependencies)
- AuthService → MailService, UserRepository, Bcrypt

## Priority Refactoring Order

### Phase 1: Create Core Repositories (Week 1, Monday-Tuesday)
1. ContactRepository (used by 5+ services)
2. ActivityRepository (used by 4+ services)
3. CampaignRepository (used by 3+ services)
4. ConversationRepository (used by 3+ services)

### Phase 2: Extract External Services (Week 1, Tuesday-Wednesday)
1. GoogleCalendarService (from api_integrations.py)
2. MailService (wrap Flask-Mail)
3. CeleryTaskQueue (wrap Celery)

### Phase 3: Refactor High-Value Services (Week 1, Wednesday-Thursday)
1. ContactService (core to everything)
2. CampaignService (already partial DI)
3. CSVImportService (critical feature)

### Phase 4: Fix Anti-patterns (Week 1, Friday)
1. OpenPhoneWebhookService (stop creating SMSMetricsService)
2. QuickBooksSyncService (stop creating QuickBooksService)
3. Convert static methods to instance methods (AuthService, InvoiceService)

## Next Steps

1. ✅ Complete this audit (W1-01)
2. Create GoogleCalendarService (W1-02)
3. Create EmailService abstraction (W1-03)
4. Begin repository pattern implementation
5. Update ServiceRegistry with lazy loading

---

*Audit completed: August 17, 2025*
*Next review: After Week 1 completion*