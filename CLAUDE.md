# CLAUDE.md - Attack-a-Crack CRM Development Guide

## Project Overview

Attack-a-Crack CRM is a comprehensive Flask-based CRM system integrated with OpenPhone for SMS/communication management. It features automated workflows, AI-powered insights, multi-source contact enrichment, and is designed to manage every aspect of the business from lead generation to final payment.

**Tech Stack:**
- Backend: Flask + SQLAlchemy + PostgreSQL
- Background Tasks: Celery + Redis/Valkey
- SMS/Calls: OpenPhone API + Webhooks
- AI: Google Gemini API
- Deployment: DigitalOcean App Platform (Docker containers)
- Testing: pytest
- Version Control: GitHub with Actions CI/CD

## Project Structure

```
├── app.py                  # Flask application entry point
├── config.py              # Application configuration
├── crm_database.py        # SQLAlchemy database models
├── routes/                # Flask route handlers (blueprints)
├── services/              # Business logic layer
├── templates/             # Jinja2 HTML templates
├── tests/                 # Test suite
├── tasks/                 # Celery background tasks
├── migrations/            # Alembic database migrations
├── scripts/               # Administrative and data management scripts
├── docs/                  # Project documentation
└── .do/                   # DigitalOcean deployment configs
```

## Key Development Commands

### Testing
```bash
# Run all tests with coverage
docker-compose exec web pytest --cov --cov-report=term-missing --ignore=migrations/ --ignore=venv/

# Run specific test file
docker-compose exec web pytest tests/test_contact_service.py -xvs

# Run critical coverage tests
docker-compose exec web pytest tests/test_critical_coverage.py -v
```

### Database Management
```bash
# Run migrations
docker-compose exec web flask db upgrade

# Create new migration
docker-compose exec web flask db migrate -m "description"

# Check database stats
docker-compose exec web python -c "
from app import create_app
from crm_database import Contact, Conversation, Activity
app = create_app()
with app.app_context():
    print(f'Contacts: {Contact.query.count()}')
    print(f'Conversations: {Conversation.query.count()}')
    print(f'Activities: {Activity.query.count()}')
"
```

### Data Import
```bash
# Run large scale import (production)
docker-compose exec web python large_scale_import.py

# Run with resume capability
docker-compose exec web python large_scale_import.py --resume

# Run interactive import manager
docker-compose exec web python scripts/data_management/imports/import_manager.py
```

### Background Tasks
```bash
# Check Celery worker status
docker-compose exec celery celery -A celery_worker.celery inspect active

# Restart Celery workers
docker-compose restart celery celery-beat
```

## Current Project Status

### ✅ Completed Features
- **Production-ready deployment on DigitalOcean App Platform** ✨
- **Large scale OpenPhone import (7000+ conversations successfully imported!)** 🎉
- **Environment variables properly managed and preserved during deployments**
- **Universal CSV import system with smart format detection (10+ formats!)** 📊
- **SMS bounce tracking integrated with OpenPhone webhooks** 📈
- Enhanced database models for all OpenPhone data types
- Contact enrichment from multiple CSV sources with automatic merging
- Webhook handling with signature verification
- Background task processing with Celery + Valkey (Redis)
- User authentication and authorization system
- SMS campaign system with A/B testing
- Flask-Session with Redis backend for multi-worker support
- GitHub Actions CI/CD pipeline with proper env var preservation
- Valkey attached as managed database resource

### 🚧 In Progress - Week of August 18, 2025
**TOP PRIORITY: Launch production text campaign by end of week**

1. **Service Layer Refactoring** ✅ COMPLETE - All major routes refactored!
   - ✅ Dashboard refactored to DashboardService
   - ✅ Campaigns refactored to CampaignService  
   - ✅ Todo routes already using TodoService
   - ✅ Created DiagnosticsService & TaskService for routes/api_routes.py
   - ✅ Created OpenPhoneSyncService & SyncHealthService for routes/settings_routes.py
   - 🔧 Expand ContactService with search/pagination/bulk operations (remaining enhancement)
   
2. **Contacts Page Overhaul** - Foundation for campaigns
   - Fix broken filters
   - Implement proper pagination
   - Complete UX improvement pass
   
3. **Campaign System Production Ready**
   - Vet list generation and templating
   - Test campaign workflow end-to-end
   - Launch first automated SMS campaign via OpenPhone API
   
4. **OpenPhone Webhooks** ✅ COMPLETE - Working in production!
   - Test response tracking

### 📋 Priority Roadmap
1. **THIS WEEK - Campaign Launch Prerequisites**
   - Fix dashboard activity sorting (sort by recent activity, not import time)
   - Overhaul contacts page (filters, pagination, intuitive UX)
   - Ensure OpenPhone webhooks working in production
   - Vet campaign list generation and templating
   - Send first automated text messages

2. **NEXT WEEK - Campaign Operations**
   - Monitor first campaign performance
   - Implement response tracking and analytics
   - Build automated follow-up sequences
   - A/B testing refinements
   - Daily limit compliance (125 texts/day for cold outreach)

3. **HIGH PRIORITY - Contact Enrichment** ✅ Ready to Use!
   - **Universal CSV import with smart detection at:**
     - `/campaigns/import-csv` - For campaign list creation
     - `/settings/imports` → CSV & PropertyRadar imports
   - Automatically detects 10+ CSV formats (OpenPhone, Realtor, PropertyRadar, etc.)
   - Phone number normalization to +1XXXXXXXXXX format
   - Smart enrichment: Only fills missing data, preserves existing
   - See `/docs/CSV_IMPORT_FIELD_MAPPING.md` for complete documentation

4. **UPCOMING - QuickBooks Integration**
   - Complete OAuth authentication flow
   - Customer sync and enrichment
   - Products/services import
   - Quote/invoice bidirectional sync
   - Payment tracking and reconciliation

5. **FUTURE - Advanced Features**
   - Financial dashboards and reporting
   - SmartLead email integration (Q2 2025)
   - Multi-channel campaigns (SMS + Email)
   - AI-powered response suggestions
   - Customer portal for self-service

## Core Database Models

### Contact
- Primary entity for customer/lead management
- Enriched from multiple sources (OpenPhone, CSV, QuickBooks)
- Fields: phone, email, name, company, addresses, tags, financial data
- Relationships: properties, conversations, activities, campaigns

### Activity
- Unified model for all communications (messages, calls, voicemails)
- Stores media URLs, recording URLs, AI summaries/transcripts
- Linked to conversations and contacts

### Conversation
- Groups activities by contact
- Tracks last activity and participant information

### Campaign & CampaignMembership
- SMS campaign management with A/B testing
- Compliance tracking (opt-outs, daily limits)
- Response sentiment analysis

### WebhookEvent
- Stores all OpenPhone webhook payloads
- Ensures idempotent processing
- Error tracking and retry capability

## External Integrations

### OpenPhone API
- **Base URL**: https://api.openphone.com/v1
- **Authentication**: API key in Authorization header
- **Key Endpoints**:
  - /conversations - Get conversation threads
  - /messages - Get/send SMS messages
  - /calls - Get call history
  - /call-recordings/{callId} - Get call recordings
- **Webhooks**: message.received, message.delivered, call.completed, call.recording.completed, call.summary.completed, call.transcript.completed
- **Limitations**: No media in messages API (but available in webhooks), no voicemail API

### QuickBooks Online (In Development)
- OAuth 2.0 authentication flow
- Customer sync and enrichment
- Products/services import
- Quote/invoice bidirectional sync

### Google APIs
- Gemini AI for conversation analysis
- Calendar integration for appointments
- OAuth for authentication

## Development Guidelines

### CRITICAL: Test-Driven Development (TDD) is MANDATORY
Starting immediately, all new features and refactoring MUST follow TDD:
1. **Write the test FIRST** - it should fail initially (Red)
2. **Write minimal code** to make the test pass (Green)  
3. **Refactor** to improve code quality while keeping tests green (Refactor)
4. **No code without tests** - if there's no test, the code doesn't get merged

See `/docs/ARCHITECTURE.md` for detailed testing strategy and patterns.

### CRITICAL: Research vs Implementation
- **RESEARCH TASKS**: When asked to research, investigate, or explore options - ONLY provide findings and recommendations. DO NOT implement without explicit approval.
- **NEVER** start implementation that involves costs (API subscriptions, paid services) without explicit user approval
- **ALWAYS** document findings comprehensively and let the user make implementation decisions
- Research deliverables should include: findings, options, costs, recommendations, and wait for user direction

### Architecture Principles
- **Dependency Injection**: Services receive dependencies via constructor, never create them
- **Service Registry Pattern**: All services managed centrally in app.py
- **Separation of Concerns**: Routes handle HTTP, services handle business logic, models handle data
- **No Direct DB Queries in Routes**: All database access through service methods
- **No External API Calls Outside Services**: API calls isolated in dedicated service classes

### Code Style
- Use Flask blueprints for routes
- Business logic in service modules  
- No comments unless requested
- Follow existing patterns in codebase
- Use SQLAlchemy for all database operations
- Type hints for all function parameters and returns

### Testing Requirements
- **TDD is mandatory** - write tests before implementation
- **Test Pyramid**: 70% unit tests, 25% integration tests, 5% E2E tests
- **Coverage Target**: >90% for all new code
- **Unit Tests**: Mock all dependencies, test business logic only
- **Integration Tests**: Use real test database, mock only external APIs
- **Test Isolation**: Each test must be independent, no shared state
- Use pytest fixtures for test data
- Test both success and error cases

### Security Best Practices
- Never commit secrets (use environment variables)
- Validate all user input
- Use HMAC signature verification for webhooks
- Implement proper authentication on all routes
- Encrypt sensitive data in database

### Git Workflow
```bash
# When committing changes
git status  # Check untracked files
git diff    # Review changes
git add .   # Stage changes
git commit -m "Description

🤖 Generated with Claude Code

Co-Authored-By: Claude <noreply@anthropic.com>"
```

## Environment Variables

Critical environment variables (must be set):
```bash
# Database
DATABASE_URL=postgresql://user:pass@db:5432/dbname

# OpenPhone
OPENPHONE_API_KEY=your_api_key
OPENPHONE_PHONE_NUMBER=your_phone
OPENPHONE_PHONE_NUMBER_ID=your_id
OPENPHONE_WEBHOOK_SIGNING_KEY=your_signing_key

# Redis/Celery
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/0

# Security
SECRET_KEY=your_secret_key
ENCRYPTION_KEY=your_encryption_key

# AI Services
GEMINI_API_KEY=your_gemini_key

# Optional Integrations
QUICKBOOKS_CLIENT_ID=your_qb_id
QUICKBOOKS_CLIENT_SECRET=your_qb_secret
SMARTLEAD_API_KEY=your_smartlead_key
```

## Deployment (DigitalOcean)

### Configuration
- Main config: `.do/app.yaml` (template only - no secrets)
- Services: web (Flask), worker (Celery)
- Database: PostgreSQL 13
- Valkey (Redis): Managed instance for sessions and Celery
- Region: nyc3

### GitHub Actions CI/CD
- **AUTOMATIC DEPLOYMENT**: Pushing to main automatically triggers deployment
- **DO NOT MANUALLY DEPLOY**: The CI/CD pipeline handles everything
- **IMPORTANT**: Never run manual deployments after git push
- Environment variables are now stored as encrypted values in app.yaml
- The deployment workflow simply updates the app with the spec

### Environment Variables Management  
**SOLVED**: Environment variables are now stored as ENCRYPTED values in app.yaml
- Encrypted values (EV[1:...]) are SAFE to commit to Git
- DigitalOcean automatically encrypts sensitive values when set
- These encrypted values are app-specific and cannot be used elsewhere
- To update values: Set them once, export spec, commit encrypted values
- Emergency restoration script available: `scripts/fix_env_vars.sh`

### Production Commands
```bash
# Deploy via GitHub Actions (preserves env vars)
# Push to main branch triggers CI/CD

# Manual deployment (use with caution)
doctl apps spec get <app-id> > temp-spec.yaml
# Edit temp-spec.yaml as needed
doctl apps update <app-id> --spec temp-spec.yaml

# Check deployment status
doctl apps list-deployments <app-id>

# View logs
doctl apps logs <app-id> <component-name> --tail=100
```

## Troubleshooting

### Common Issues

1. **Import Failures**
   - Check OpenPhone API key
   - Verify rate limits not exceeded
   - Use resume capability: `python large_scale_import.py --resume`

2. **Webhook Issues**
   - Verify signing key matches
   - Check webhook URL configuration
   - Review webhook_events table for errors

3. **Celery Task Failures**
   - Check Redis connection
   - Monitor worker logs: `docker-compose logs -f celery`
   - Restart workers if needed

4. **Database Connection Issues**
   - Verify DATABASE_URL format
   - Check connection pool settings
   - Monitor active connections

### Debug Mode
```python
# Enable detailed logging
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Performance Optimization

### Database
- Use eager loading to prevent N+1 queries
- Implement server-side pagination (100 records default)
- Add indexes for frequently queried fields
- Use database connection pooling

### Celery
- Limit concurrency based on instance size
- Use task timeouts to prevent hanging
- Implement retry logic with exponential backoff

### API Rate Limiting
- OpenPhone: Respect rate limits with throttling
- Implement request queuing for bulk operations
- Use batch operations where available

## UI/UX Standards

### Dark Theme Design
- Background: `bg-gray-900` (sidebar), `bg-gray-800` (main)
- Text: `text-white` (primary), `text-gray-400` (secondary)
- Buttons: `bg-blue-600 hover:bg-blue-700`
- Success/Error: `text-green-400` / `text-red-500`

### Component Patterns
- Use Tailwind CSS utility classes
- Maintain consistent spacing (p-8 for pages, p-6 for cards)
- All forms need proper validation and feedback
- Loading states for async operations

## Key Files Reference

### Core Application
- `app.py:create_app()` - Application factory
- `config.py` - Configuration management
- `crm_database.py` - All database models
- `celery_worker.py` - Background task configuration

### Services (Business Logic)
- `services/openphone_service.py` - OpenPhone API client
- `services/openphone_webhook_service.py` - Webhook processing
- `services/openphone_sync_service.py` - OpenPhone sync operations and task management
- `services/contact_service.py` - Contact management
- `services/campaign_service.py` - Campaign operations
- `services/dashboard_service.py` - Dashboard statistics and metrics
- `services/todo_service.py` - Todo task management
- `services/diagnostics_service.py` - System health checks and diagnostics
- `services/task_service.py` - Celery task status and management
- `services/sync_health_service.py` - Sync health monitoring across integrations
- `services/ai_service.py` - Gemini AI integration
- `services/csv_import_service.py` - Universal CSV import with smart detection
- `services/sms_metrics_service.py` - SMS bounce tracking and analytics

### Routes (Controllers)
- `routes/dashboard_routes.py` - Main dashboard (uses DashboardService)
- `routes/contact_routes.py` - Contact CRUD
- `routes/conversation_routes.py` - Messaging interface
- `routes/campaign_routes.py` - Campaign management (uses CampaignService)
- `routes/api_routes.py` - API endpoints and webhooks (uses DiagnosticsService, TaskService)
- `routes/settings_routes.py` - Settings and sync management (uses OpenPhoneSyncService, SyncHealthService)
- `routes/todo_routes.py` - Todo management (uses TodoService)

### Import Scripts
- `large_scale_import.py` - Production data import
- `scripts/data_management/imports/enhanced_openphone_import.py` - Core import logic
- `scripts/data_management/universal_csv_enrichment.py` - Universal CSV enrichment
- `scripts/data_management/csv_importer.py` - Legacy CSV contact import

### Supported CSV Formats (Auto-Detected)
The system automatically detects and imports from these CSV formats:
- **OpenPhone** - Contact exports with phone, name, email, address
- **Realtor.com** - Agent listings with contact info
- **Sotheby's International Realty** - Agent directory exports
- **Vicente Realty** - Agent contact lists
- **Exit Realty (Cape & Premier)** - Agent rosters
- **Jack Conway & Company** - Agent directories
- **Lamacchia Realty** - Contact exports
- **William Raveis** - Agent listings
- **PropertyRadar** - Property and owner data with dual contacts
- **Standard formats** - Any CSV with recognizable phone/name/email columns

## Recent Victories 🎉

### January 2025 - Complete Service Layer Refactoring
- **Completed FULL service layer refactoring** for all major routes!
- **Created 7 new service classes**:
  - DashboardService - Dashboard business logic
  - TodoService - Todo management
  - DiagnosticsService - System health checks
  - TaskService - Celery task management
  - OpenPhoneSyncService - OpenPhone sync operations
  - SyncHealthService - Sync health monitoring
  - Enhanced CampaignService - Campaign management
- **Refactored all primary routes** to use service layer pattern:
  - api_routes.py (-175 lines of business logic)
  - settings_routes.py (-110 lines of business logic)
  - dashboard_routes.py (previously completed)
  - campaign_routes.py (previously completed)
  - todo_routes.py (already using TodoService)
- **Removed 285+ lines of business logic** from route handlers
- **Improved code organization** with proper separation of concerns
- **All tests passing** with no breaking changes

### January 2025 - Universal CSV Import & SMS Tracking
- **Implemented universal CSV import** with automatic format detection for 10+ formats
- **Added SMS bounce tracking** using OpenPhone webhook data (FREE, no external APIs)
- **Fixed duplicate key constraints** in production CSV imports
- **Enhanced Settings import pages** with smart column detection and enrichment
- **Achieved 100% contact enrichment** capability without creating duplicates

### January 2025 - Production Deployment Success
- **Successfully imported 7000+ OpenPhone conversations** to production database
- **Fixed persistent environment variable issues** that were clearing on every deployment
- **Resolved Flask-Session multi-worker authentication** problems (1-in-4 success rate → 100%)
- **Established stable CI/CD pipeline** with proper secret management
- **Celery + Valkey integration** working flawlessly for background tasks

### Key Lessons Learned
1. **Environment Variables**: DigitalOcean's `doctl apps update --spec` replaces the entire spec. Solution: Fetch current spec first, modify, then deploy.
2. **Session Management**: Flask's default in-memory sessions don't work with multiple gunicorn workers. Solution: Flask-Session with Redis backend.
3. **Secret Management**: Never store secrets in app.yaml. Use DigitalOcean's environment variable management at the app level.
4. **Background Tasks**: Celery requires careful configuration with SSL for managed Redis/Valkey services.

## Notes for Future Development

1. **Contact Enrichment**: ✅ COMPLETE - Universal CSV import now available in production
2. **Media Handling**: OpenPhone API doesn't provide media URLs in messages endpoint, but webhooks do
3. **Campaign Limits**: 125 texts/day for cold outreach per phone number
4. **A/B Testing**: Requires minimum 100 contacts per variant for statistical significance
5. **QuickBooks Integration**: OAuth tokens need encryption and refresh handling
6. **Email Integration**: SmartLead API planned for Q2 2025
7. **Performance**: Database currently handles 7000+ conversations well
8. **Security**: All routes except webhooks require authentication

## Support Resources

- OpenPhone API Docs: https://www.openphone.com/docs/
- DigitalOcean App Platform: https://docs.digitalocean.com/products/app-platform/
- QuickBooks API: https://developer.intuit.com/app/developer/qbo/docs/
- Project Repository: (GitHub URL)
- Issue Tracking: GitHub Issues

---

*This document should be updated as the project evolves. Last updated: January 17, 2025*