# Service Dependency Audit - Process Documentation

## Audit Methodology

### Step 1: Service Discovery
**Command Used:**
```bash
find /Users/matt/Projects/attackacrack/openphone-sms/services -name "*.py" -type f | grep -v __pycache__ | sort
```

**Result:** Found 27 Python files in services directory

### Step 2: Dependency Analysis Process

For each service, I examined:

1. **Constructor (__init__)**: Check if dependencies are injected or created internally
2. **Imports**: Identify external libraries and inter-service dependencies
3. **Database Access**: Search for patterns:
   - `.query.`
   - `db.session`
   - Direct model imports from `crm_database`
4. **External API Calls**: Look for:
   - `requests` library usage
   - API client instantiation
   - Configuration/credential access

### Step 3: Audit Commands and Patterns

#### Check for dependency injection pattern:
```python
# GOOD - Dependency Injection
class ServiceA:
    def __init__(self, service_b: ServiceB):
        self.service_b = service_b

# BAD - Internal instantiation
class ServiceA:
    def __init__(self):
        self.service_b = ServiceB()
```

#### Check for database queries:
```bash
grep -n "\.query\." service_file.py
grep -n "db\.session" service_file.py
grep -n "from crm_database import" service_file.py
```

#### Check for external dependencies:
```bash
grep -n "import requests" service_file.py
grep -n "from api_integrations" service_file.py
grep -n "from flask_mail" service_file.py
```

## Detailed Findings by Service

### CampaignService Analysis
**File:** `services/campaign_service.py`

**Investigation Commands:**
```bash
# Check constructor
grep -A 10 "def __init__" services/campaign_service.py
# Check for database queries
grep "\.query\." services/campaign_service.py | wc -l  # Result: 15 occurrences
# Check imports
head -20 services/campaign_service.py
```

**Findings:**
```python
# Line 19-23: GOOD - Dependencies injected
def __init__(self, openphone_service: OpenPhoneService = None, 
             list_service: CampaignListService = None):
    self.openphone_service = openphone_service or OpenPhoneService()
    self.list_service = list_service or CampaignListService()

# Line 89: BAD - Direct database query
campaign = Campaign.query.get(campaign_id)

# Line 234: BAD - Complex query logic mixed with business logic
contacts = Contact.query.filter(Contact.phone.isnot(None))
```

### AppointmentService Analysis
**File:** `services/appointment_service.py`

**Investigation Commands:**
```bash
# Check imports
grep "from api_integrations" services/appointment_service.py
# Result: from api_integrations import create_google_calendar_event, delete_google_calendar_event

# Check constructor
grep -A 5 "def __init__" services/appointment_service.py
# Result: No __init__ found - using default constructor
```

**Findings:**
```python
# Line 3: BAD - Direct import of external functions
from api_integrations import create_google_calendar_event, delete_google_calendar_event

# Line 45: BAD - Direct call to external API
event_data = create_google_calendar_event(
    summary=f"Appointment with {contact.first_name} {contact.last_name}",
    ...
)
```

### OpenPhoneWebhookService Analysis
**File:** `services/openphone_webhook_service.py`

**Investigation Commands:**
```bash
# Check for service instantiation
grep "Service()" services/openphone_webhook_service.py
# Result: Line 156: sms_metrics_service = SMSMetricsService()

# Check constructor
grep -A 5 "def __init__" services/openphone_webhook_service.py
# Result: No constructor defined
```

**Findings:**
```python
# Line 156: BAD - Creating service internally
def _track_sms_metrics(self, activity_id: int, event_type: str):
    sms_metrics_service = SMSMetricsService()
    
# Should be:
def __init__(self, sms_metrics_service: SMSMetricsService):
    self.sms_metrics_service = sms_metrics_service
```

## Anti-Patterns Discovered

### 1. Services Creating Other Services
**Found in:**
- OpenPhoneWebhookService → creates SMSMetricsService (line 156)
- QuickBooksSyncService → creates QuickBooksService (line 28)

**Impact:** Makes testing impossible without mocking internal implementation

### 2. Static Methods Instead of Instance Methods
**Found in:**
- AuthService (all methods are @staticmethod)
- InvoiceService (create_invoice_from_quote is static)

**Impact:** Cannot inject dependencies, forces tight coupling

### 3. Direct Database Access
**Statistics:**
```bash
# Count total direct queries across all services
for file in services/*.py; do
    count=$(grep -c "\.query\." "$file" 2>/dev/null || echo 0)
    if [ $count -gt 0 ]; then
        echo "$file: $count queries"
    fi
done

# Results:
services/campaign_service.py: 15 queries
services/contact_service.py: 12 queries
services/dashboard_service.py: 18 queries
services/conversation_service.py: 8 queries
# ... (21 services total with direct queries)
```

### 4. Configuration Access Pattern Issues
**Found in:**
```python
# BAD - Direct config access
class OpenPhoneService:
    def __init__(self):
        self.api_key = current_app.config.get('OPENPHONE_API_KEY')

# GOOD - Config injected
class OpenPhoneService:
    def __init__(self, api_key: str):
        self.api_key = api_key
```

## Dependency Chain Analysis

### Method: Trace Dependencies
For each service, I traced its dependencies to understand initialization order:

```python
# Dependency tree construction
CampaignService
├── OpenPhoneService (Level 0 - no dependencies)
├── CampaignListService (Level 0 - no dependencies)
└── Database queries (to be replaced with repositories)

CSVImportService
├── ContactService (Level 0 currently, will be Level 1 after repository)
└── Database queries (to be replaced with repositories)

DashboardService (Most complex)
├── Contact queries → ContactRepository
├── Activity queries → ActivityRepository
├── Campaign queries → CampaignRepository
├── Conversation queries → ConversationRepository
└── (No service dependencies currently)
```

## Quantitative Analysis

### Metrics Collected:
```python
# Script to analyze service dependencies
import os
import re

stats = {
    'total_services': 0,
    'using_di': 0,
    'using_partial_di': 0,
    'no_di': 0,
    'with_db_queries': 0,
    'with_external_apis': 0,
    'with_static_methods': 0
}

for service_file in os.listdir('services'):
    if service_file.endswith('.py'):
        stats['total_services'] += 1
        
        with open(f'services/{service_file}', 'r') as f:
            content = f.read()
            
            # Check for DI pattern
            if 'def __init__(self' in content and 'Service' in content:
                if '= None' in content:  # Partial DI with defaults
                    stats['using_partial_di'] += 1
                else:
                    stats['using_di'] += 1
            else:
                stats['no_di'] += 1
            
            # Check for DB queries
            if '.query.' in content or 'db.session' in content:
                stats['with_db_queries'] += 1
            
            # Check for external APIs
            if 'requests' in content or 'api_integrations' in content:
                stats['with_external_apis'] += 1
            
            # Check for static methods
            if '@staticmethod' in content:
                stats['with_static_methods'] += 1

print(stats)
```

**Results:**
- Total Services: 25
- Using Full DI: 0 (0%)
- Using Partial DI: 3 (12%)
- No DI: 22 (88%)
- With DB Queries: 21 (84%)
- With External APIs: 7 (28%)
- With Static Methods: 3 (12%)

## Key Insights

1. **Critical Finding**: Zero services currently use proper dependency injection
2. **Database Coupling**: 84% of services directly query the database
3. **Testing Impact**: Current architecture makes unit testing nearly impossible
4. **Refactoring Priority**: ContactRepository needed by 5+ services

## Next Steps Documentation

Based on the audit, the refactoring order should be:

1. **Create Core Repositories** (biggest impact)
   - ContactRepository - used by 5+ services
   - ActivityRepository - used by 4+ services
   
2. **Extract External Services** (isolation of concerns)
   - GoogleCalendarService - for AppointmentService
   - MailService - for AuthService
   
3. **Fix Anti-patterns** (improve testability)
   - Convert static methods to instance methods
   - Stop services from creating other services

---

*Process documented: August 17, 2025*
*Auditor: Claude Code Assistant*