# Utility Scripts

This directory contains various utility scripts for maintenance and data management tasks.

## Directory Structure

### imports/
Import and migration scripts for bringing data into the system:
- `enhanced_openphone_import.py` - Enhanced import script for OpenPhone data
- `full_openphone_import.py` - Full OpenPhone data import
- `large_scale_import.py` - Script for handling large-scale data imports
- `safe_dry_run_import.py` - Safe dry-run testing for imports
- `import_manager.py` - General import management utilities
- `targeted_csv_enrichment.py` - CSV data enrichment utilities
- `test_enhanced_import.py` - Tests for enhanced import
- `run_large_import.sh` - Shell script for running large imports

### webhooks/
Webhook management and testing utilities:
- `manage_webhooks.py` - Webhook configuration management
- `test_webhook_handler.py` - Webhook handler testing
- `webhook_payload_examples.py` - Example webhook payloads for testing

### media/
Media and attachment handling utilities:
- `backfill_call_recordings.py` - Backfill historical call recordings
- `backfill_messages.py` - Backfill historical messages
- `fix_existing_media_urls.py` - Fix media URL formats in database
- `fix_media_urls.py` - Media URL correction utility
- `generate_media_fix_sql.py` - Generate SQL for media fixes

## Usage

These scripts are typically run manually for maintenance tasks. Most require database access and should be run with appropriate environment variables set.

Example:
```bash
python utils/media/backfill_messages.py
```