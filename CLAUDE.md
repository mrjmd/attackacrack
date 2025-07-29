# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Flask-based CRM system integrated with OpenPhone for SMS/communication management. The application uses PostgreSQL for data storage, Redis for caching/message queuing, and Celery for asynchronous task processing.

## Development Commands

### Running Tests
```bash
pytest                    # Run all tests
pytest -v                # Run tests with verbose output
pytest tests/test_file.py # Run specific test file
pytest -k "test_name"    # Run tests matching pattern
pytest --cov            # Run tests with coverage
```

### Local Development
```bash
# Install dependencies
pip install -r requirements.txt

# Run Flask development server (with SSL)
python app.py

# Run database migrations
flask db upgrade
flask db migrate -m "migration message"

# Docker development
docker-compose up        # Start all services
docker-compose down      # Stop all services
docker-compose logs -f   # View logs
docker-compose exec web bash # Access web container
```

### Background Tasks
```bash
# Run Celery worker locally
celery -A celery_worker.celery worker --loglevel=info

# Run Celery beat scheduler locally
celery -A celery_worker.celery beat --loglevel=info
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
- **PostgreSQL**: Primary data storage
- **Redis**: Message queue and caching
- **Ngrok**: Local webhook testing in development

### Testing Approach

Tests are located in `tests/` directory with pytest configuration in `pytest.ini`. Test files follow the pattern `test_*.py` and include unit tests for services, routes, and integrations.