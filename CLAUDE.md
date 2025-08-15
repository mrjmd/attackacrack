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
- Production-ready Docker architecture
- Enhanced database models for all OpenPhone data types
- Large scale import system (7000+ conversations)
- Contact enrichment from multiple CSV sources
- Webhook handling with signature verification
- Background task processing with Celery
- User authentication and authorization system
- SMS campaign system with A/B testing

### 🚧 In Progress
- QuickBooks Online integration (OAuth, customer sync, products/services)
- Email integration via SmartLead API
- Advanced financial dashboards and reporting
- DigitalOcean deployment configuration refinement

### 📋 Priority Roadmap
1. **CRITICAL - IMMEDIATE**: Production Environment & CI/CD Pipeline
   - Harden DigitalOcean App Platform configuration
   - Ensure web service, Celery workers, PostgreSQL, and Redis/Valkey work together
   - Configure GitHub Actions for automated testing and deployment
   - Set up monitoring, health checks, and error alerting (Sentry)
   - Verify all environment variables and secrets management

2. **HIGH PRIORITY**: OpenPhone Large Scale Import on Production
   - Ensure large_scale_import.py runs successfully in production environment
   - Implement real-time progress feedback and monitoring
   - Configure Celery workers with appropriate resources for 7000+ conversations
   - Set up proper logging and error recovery mechanisms
   - Test resume capability and checkpoint system

3. **NEXT**: Core Business Features
   - Contact CSV enrichment (79% contacts need data)
   - Text Campaign System enhancements
   - UI/UX improvements and polish

4. **FUTURE**: Integrations & Advanced Features
   - QuickBooks bidirectional sync
   - Financial dashboard and reporting
   - SmartLead email integration (Q2 2025)
   - Multi-channel campaigns

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

### Code Style
- Use Flask blueprints for routes
- Business logic in service modules
- No comments unless requested
- Follow existing patterns in codebase
- Use SQLAlchemy for all database operations

### Testing Requirements
- All new features require tests
- Aim for >90% code coverage
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
- Main config: `.do/app.yaml`
- Services: web (Flask), worker (Celery)
- Database: PostgreSQL 13
- Region: nyc3

### GitHub Actions CI/CD
- Automated testing on push to main
- Docker image build and push to registry
- Manual deployment trigger available

### Production Commands
```bash
# Deploy via GitHub Actions
# Push to main branch triggers CI/CD

# Manual deployment
doctl apps create --spec .do/app.yaml

# Update app spec
doctl apps update <app-id> --spec .do/app.yaml
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
- `services/contact_service.py` - Contact management
- `services/campaign_service.py` - Campaign operations
- `services/ai_service.py` - Gemini AI integration

### Routes (Controllers)
- `routes/dashboard_routes.py` - Main dashboard
- `routes/contact_routes.py` - Contact CRUD
- `routes/conversation_routes.py` - Messaging interface
- `routes/campaign_routes.py` - Campaign management
- `routes/api_routes.py` - API endpoints and webhooks

### Import Scripts
- `large_scale_import.py` - Production data import
- `scripts/data_management/imports/enhanced_openphone_import.py` - Core import logic
- `scripts/data_management/csv_importer.py` - CSV contact import

## Notes for Future Development

1. **Contact Enrichment Priority**: 79% of contacts missing critical data - CSV import is urgent
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

*This document should be updated as the project evolves. Last updated: January 2025*