# Archived Scripts

This directory contains scripts that are no longer actively used but are kept for historical reference.

## Archived Scripts

### One-time Maintenance Scripts
- `cleanup_empty_conversations.py` - One-time cleanup of empty conversation records
- `fix_conversation_timestamps.py` - One-time fix for conversation timestamp issues
- `diagnose_redis.py` - Diagnostic script for Redis connection issues
- `sync_progress_monitor.py` - Old sync progress monitoring script

### Production Debugging Scripts
- `test_real_session.py` - Session debugging for production issues
- `test_auth.py` - Authentication testing script
- `test_redis_connection.py` - Redis connection testing
- `test_session_debug.py` - Session debugging utilities
- `test_session_config.py` - Session configuration testing

### Superseded Import Scripts
- `safe_dry_run_import.py` - Old dry-run import script (replaced by import_manager.py)
- `test_enhanced_import.py` - Test script for enhanced imports
- `date_filtered_import.py` - Date-filtered import (functionality merged into main import)

## Note
These scripts are archived because they:
- Were created for one-time data fixes
- Have been superseded by newer implementations
- Were temporary debugging utilities
- Are no longer compatible with the current codebase

If you need similar functionality, check the active scripts in the parent directories or create new scripts based on current patterns.