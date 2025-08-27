# Scripts Directory

This directory contains administrative utilities and data management scripts for the Attack-a-Crack CRM.

## Core Utilities

### Essential Scripts (Main Directory)
- `commands.py` - Flask CLI commands for admin user creation and password management
- `fix_password_hashes.py` - Utility for fixing and verifying password hashes
- `normalize_existing_data.py` - Data normalization reconciliation for existing contacts and properties
- `lint_check.py` - Code linting and style checking utility
- `celery_utils.py` - Shared Celery utilities used by data management scripts
- `script_logger.py` - Logging utilities for script execution
- `setup_dev.sh` - Development environment setup script
- `extract_secrets_for_github.sh` - Extract and format secrets for GitHub Actions
- `fix_env_vars.sh` - Environment variable configuration helper

## Directory Structure

### data_management/
Scripts for importing, exporting, and managing data:

#### imports/
- `enhanced_openphone_import.py` - Primary import script for OpenPhone data
- `large_scale_import.py` - Production-scale import wrapper for large datasets
- `safe_dry_run_import.py` - Test imports without database modifications
- `import_manager.py` - Interactive menu for import operations
- `targeted_csv_enrichment.py` - Enrich existing contacts from CSV/JSON
- `test_enhanced_import.py` - Test suite for import functionality
- `run_large_import.sh` - Docker wrapper for large imports

#### media/
- `backfill_call_recordings.py` - Download historical call recordings
- `backfill_messages.py` - Import recent messages from OpenPhone
- `fix_existing_media_urls.py` - Correct media URL formats in database
- `fix_media_urls.py` - General media URL correction utility
- `generate_media_fix_sql.py` - Generate SQL for bulk media fixes

#### Other Data Scripts
- `csv_importer.py` - Import contacts from CSV files
- `property_radar_importer.py` - Import property data from PropertyRadar
- `format_csv.py` - Format and clean CSV files for import
- `seed_products.py` - Populate products/services database

### dev_tools/
Development and debugging utilities:

#### webhooks/
- `manage_webhooks.py` - Create, list, and delete OpenPhone webhooks
- `test_webhook_handler.py` - Test webhook handling with sample payloads
- `webhook_payload_examples.py` - Example webhook payloads for testing

#### Other Dev Tools
- `generate_token.py` - Generate Google OAuth tokens
- `reset_database.py` - Drop and recreate database tables
- `remove_secrets.sh` - Remove secrets from git history

## Usage Examples

### Data Import & Normalization
```bash
# Run interactive import manager
python scripts/data_management/imports/import_manager.py

# Import contacts from CSV
python scripts/data_management/csv_importer.py

# Large-scale production import
./scripts/data_management/imports/run_large_import.sh

# Normalize existing data (dry run first to preview changes)
flask normalize-existing-data --dry-run
flask normalize-existing-data --properties-only
flask normalize-existing-data --contacts-only --batch-size 50
```

### Development Tools
```bash
# Reset database
python scripts/dev_tools/reset_database.py

# Manage webhooks
python scripts/dev_tools/webhooks/manage_webhooks.py --list
python scripts/dev_tools/webhooks/manage_webhooks.py --create

# Test webhook handling
python scripts/dev_tools/webhooks/test_webhook_handler.py
```

### Media Management
```bash
# Backfill call recordings
python scripts/data_management/media/backfill_call_recordings.py

# Fix media URLs
python scripts/data_management/media/fix_existing_media_urls.py
```

## Important Notes

- Most scripts require database access and appropriate environment variables
- Always run data modification scripts in a test environment first
- The `large_scale_import.py` is the recommended script for production imports
- Use dry run options when available to preview changes before execution
- The `normalize_existing_data.py` script is idempotent and safe to run multiple times
- Data normalization uses the same logic as PropertyRadar imports for consistency

## Removed Scripts

All one-off and archived scripts have been removed to reduce clutter and improve test coverage reports. These can be retrieved from git history if needed. Removed items include:
- Phase 2 warning reduction scripts
- One-off migration and fix scripts
- Deprecated import/export utilities
- Testing and debugging tools from earlier development phases
- The entire `archive/` directory with old scripts
- Empty `maintenance/` and `production_debugging/` directories