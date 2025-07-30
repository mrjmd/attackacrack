# Attack-a-Crack CRM

A comprehensive Flask-based CRM system integrated with OpenPhone for SMS/communication management, featuring automated workflows, AI-powered insights, and multi-source contact enrichment.

## Quick Start

### Prerequisites
- Docker and Docker Compose
- `.env` file configured (see `.env.example`)

### Development Setup
```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Access the application
open http://localhost:5000
```

## Development Commands

All commands should be run in the Docker container unless otherwise noted.

### Container Access
```bash
# Access web application container
docker-compose exec web bash

# Access database container
docker-compose exec db psql -U your_db_user -d your_db_name

# Access Redis container
docker-compose exec redis redis-cli
```

### Database Management
```bash
# Run database migrations
docker-compose exec web flask db upgrade

# Create new migration
docker-compose exec web flask db migrate -m "migration message"

# Reset database (WARNING: destroys all data)
docker-compose exec web flask db downgrade
docker-compose exec web flask db upgrade
```

### Testing
```bash
# Run all tests
docker-compose exec web pytest

# Run tests with verbose output
docker-compose exec web pytest -v

# Run specific test file
docker-compose exec web pytest tests/test_contact_service.py

# Run tests matching pattern
docker-compose exec web pytest -k "test_contact"

# Run tests with coverage report
docker-compose exec web pytest --cov

# Generate HTML coverage report
docker-compose exec web pytest --cov --cov-report=html
docker-compose exec web python -m http.server 8000 --directory htmlcov

# Run tests with coverage and exclude certain files
docker-compose exec web pytest --cov --cov-omit="*/migrations/*,*/venv/*,*/tests/*"

# Run tests for specific module with coverage
docker-compose exec web pytest tests/test_openphone_service.py --cov=services.openphone_service
```

### Data Import & Management
```bash
# Run OpenPhone historical data import
docker-compose exec web python enhanced_openphone_import.py

# Run large scale import (7000+ conversations)
docker-compose exec web python large_scale_import.py

# Resume interrupted import
docker-compose exec web python large_scale_import.py --resume

# Reset and start fresh import
docker-compose exec web python large_scale_import.py --reset

# Check import progress
docker-compose exec web python -c "
import json
with open('import_progress.json', 'r') as f:
    progress = json.load(f)
    print(f'Progress: {progress[\"conversations_processed\"]} conversations')
"

# Run CSV contact enrichment
docker-compose exec web python csv_contact_enrichment.py

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

### Background Tasks & Monitoring
```bash
# Check Celery worker status
docker-compose exec celery celery -A celery_worker.celery inspect active

# Check Celery scheduled tasks
docker-compose exec celery-beat celery -A celery_worker.celery inspect scheduled

# Monitor Celery workers
docker-compose exec celery celery -A celery_worker.celery events

# Restart Celery workers
docker-compose restart celery celery-beat

# Check Redis status
docker-compose exec redis redis-cli ping

# Monitor Redis
docker-compose exec redis redis-cli monitor
```

### Development Tools
```bash
# Python shell with application context
docker-compose exec web python -c "
from app import create_app
app = create_app()
with app.app_context():
    # Your code here
    pass
"

# Interactive Python shell
docker-compose exec web python

# Check application logs
docker-compose logs -f web

# Check specific service logs
docker-compose logs -f celery
docker-compose logs -f db
docker-compose logs -f redis

# Run linting
docker-compose exec web flake8 .

# Run code formatting
docker-compose exec web black .

# Check for security issues
docker-compose exec web bandit -r . -x tests/
```

### Service Management
```bash
# Stop all services
docker-compose down

# Stop and remove volumes (WARNING: destroys database)
docker-compose down -v

# Rebuild containers
docker-compose build

# Rebuild and start
docker-compose up --build

# Scale Celery workers
docker-compose up --scale celery=3

# View resource usage
docker-compose ps
docker stats
```

### Debugging & Troubleshooting
```bash
# Check container health
docker-compose ps

# Inspect container configuration
docker inspect openphone-sms_web_1

# Check disk space usage
docker system df

# Clean up unused Docker resources
docker system prune

# View database connections
docker-compose exec db psql -U your_db_user -d your_db_name -c "SELECT * FROM pg_stat_activity;"

# Check webhook events
docker-compose exec web python -c "
from app import create_app
from crm_database import WebhookEvent
app = create_app()
with app.app_context():
    recent = WebhookEvent.query.order_by(WebhookEvent.created_at.desc()).limit(10).all()
    for event in recent:
        print(f'{event.created_at}: {event.event_type} - {event.processed}')
"
```

### QuickBooks Integration
```bash
# Test QuickBooks connection
docker-compose exec web python -c "
from services.quickbooks_service import QuickBooksService
qb = QuickBooksService()
print('QB Connection Status:', qb.test_connection())
"

# Sync customers from QuickBooks
docker-compose exec web python -c "
from services.quickbooks_sync_service import QuickBooksSyncService
sync = QuickBooksSyncService()
result = sync.sync_customers()
print(f'Synced {result[\"synced_count\"]} customers')
"

# Import products/services from QuickBooks
docker-compose exec web python -c "
from services.quickbooks_sync_service import QuickBooksSyncService
sync = QuickBooksSyncService()
result = sync.sync_products()
print(f'Imported {result[\"imported_count\"]} products/services')
"

# Check QuickBooks sync status
docker-compose exec web python -c "
from app import create_app
from crm_database import Contact, Product, QuickBooksSync
app = create_app()
with app.app_context():
    qb_customers = Contact.query.filter(Contact.quickbooks_customer_id.isnot(None)).count()
    qb_products = Product.query.filter(Product.quickbooks_item_id.isnot(None)).count()
    sync_errors = QuickBooksSync.query.filter_by(sync_status='error').count()
    print(f'QB Customers: {qb_customers}')
    print(f'QB Products: {qb_products}')
    print(f'Sync Errors: {sync_errors}')
"
```

## Architecture Overview

### Core Components

1. **Flask Application (`app.py`)**: Main application factory using blueprints for modular routing
   - Uses Flask-Migrate for database migrations
   - Configured with ProxyFix for proper header handling in production

2. **Database Models (`crm_database.py`)**: SQLAlchemy models representing business entities
   - Contact: Customer information with relationships to properties and conversations
   - Property: Physical locations associated with contacts
   - Job: Work orders for properties with quotes and invoices
   - Conversation/Activity: OpenPhone message threads and communication history
   - Appointment: Scheduled meetings integrated with Google Calendar
   - Quote/Invoice: Financial documents tied to jobs

3. **Service Layer (`services/`)**: Business logic separated from routes
   - Each major entity has its own service module (contact_service.py, job_service.py, etc.)
   - `openphone_service.py`: Handles OpenPhone API integration
   - `ai_service.py`: Integrates with Google's Gemini API
   - `scheduler_service.py`: Manages scheduled tasks via Celery

4. **API Integration (`api_integrations.py`)**: External service integrations
   - OpenPhone webhook handling for incoming messages
   - Google Calendar API integration
   - Email sending capabilities

5. **Background Processing**: 
   - Celery workers (`celery_worker.py`) for async tasks
   - Redis as message broker
   - Celery Beat for scheduled tasks

### Key Patterns

- **Blueprint-based routing**: Each major feature has its own blueprint in `routes/`
- **Service pattern**: Business logic isolated in service modules
- **Docker-based deployment**: Multi-container setup with web app, database, Redis, Celery workers
- **Environment-based configuration**: Settings loaded from `.env` file via `config.py`

### External Dependencies

- **OpenPhone API**: SMS/call management (requires API key and webhook configuration)
- **Google APIs**: Calendar integration and Gemini AI (requires OAuth setup)
- **QuickBooks Online API**: Financial data, customers, products/services (requires OAuth 2.0 app)
- **PostgreSQL**: Primary data storage
- **Redis**: Message queue and caching
- **Ngrok**: Local webhook testing in development

### Testing Approach

Tests are located in `tests/` directory with pytest configuration in `pytest.ini`. Test files follow the pattern `test_*.py` and include unit tests for services, routes, and integrations.

## Project Status

### ✅ Completed Features
- Production-ready Docker architecture
- Enhanced database models for all OpenPhone data types
- Large scale import system (7000+ conversations)
- Contact enrichment from multiple CSV sources
- Webhook handling with signature verification
- Background task processing with Celery

### 🚧 In Progress
- OpenPhone historical data import (85%+ complete)
- Contact data enrichment from CSV sources

### 📋 Upcoming Priorities
- **QuickBooks Integration** (In Progress) - See [QUICKBOOKS_INTEGRATION_PLAN.md](QUICKBOOKS_INTEGRATION_PLAN.md)
  - OAuth 2.0 authentication with QuickBooks Online
  - Customer data sync and contact enrichment  
  - Real products/services import from QB items
  - Bidirectional quote/invoice workflows
  - Financial analytics and customer segmentation
- Enhanced conversation detail view with AI showcase
- Real-time performance charts and analytics
- Advanced campaign features with multi-channel support

## Environment Variables

Key environment variables (see `.env.example`):

```bash
# Database
DB_USER=your_db_user
DB_PASSWORD=your_db_password
DB_NAME=your_db_name
DATABASE_URL=postgresql://user:pass@db:5432/dbname

# OpenPhone
OPENPHONE_API_KEY=your_api_key
OPENPHONE_PHONE_NUMBER=your_phone_number
OPENPHONE_PHONE_NUMBER_ID=your_phone_number_id

# Redis
REDIS_URL=redis://redis:6379/0

# Google APIs
GOOGLE_CALENDAR_CREDENTIALS_FILE=path/to/credentials.json
GOOGLE_AI_API_KEY=your_gemini_api_key

# QuickBooks Online
QUICKBOOKS_CLIENT_ID=your_qb_app_client_id
QUICKBOOKS_CLIENT_SECRET=your_qb_app_client_secret
QUICKBOOKS_REDIRECT_URI=http://localhost:5000/auth/quickbooks/callback
QUICKBOOKS_SANDBOX=True

# Ngrok (for development)
NGROK_AUTHTOKEN=your_ngrok_token
```

## Contributing

1. Create feature branch from `main`
2. Run tests: `docker-compose exec web pytest`
3. Run linting: `docker-compose exec web flake8 .`
4. Update documentation as needed
5. Submit pull request

## Support

For issues or questions:
1. Check container logs: `docker-compose logs -f web`
2. Review application status in dashboard
3. Check import progress files
4. Verify webhook connectivity

---

*This README is maintained alongside the [ROADMAP.md](ROADMAP.md) which contains detailed development plans and priorities.*