# Scripts Directory

This directory contains administrative and one-off scripts for maintenance and data management tasks.

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

### maintenance/
(Currently empty - for future maintenance scripts)

## Usage Examples

### Data Import
```bash
# Run interactive import manager
python scripts/data_management/imports/import_manager.py

# Import contacts from CSV
python scripts/data_management/csv_importer.py

# Large-scale production import
./scripts/data_management/imports/run_large_import.sh
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