#!/usr/bin/env python3
"""
Script to fix Flask-Session configuration warnings.

Part of Phase 2 Test Cleanup - eliminates Flask-Session deprecation warnings.

Usage:
    python scripts/fix_flask_session_warnings.py [--dry-run]
    
Options:
    --dry-run: Show what would be changed without modifying files
"""

import sys
import argparse
from pathlib import Path


def fix_config_file(config_path: Path, dry_run: bool = False) -> bool:
    """
    Fix Flask-Session configuration in config.py.
    
    Removes deprecated settings and updates to new format.
    """
    if not config_path.exists():
        print(f"Config file not found: {config_path}")
        return False
        
    with open(config_path, 'r') as f:
        lines = f.readlines()
        
    new_lines = []
    changes_made = False
    
    for line in lines:
        # Remove deprecated SESSION_USE_SIGNER
        if 'SESSION_USE_SIGNER' in line:
            print(f"  Removing deprecated: {line.strip()}")
            changes_made = True
            continue
            
        # Update SESSION_TYPE if using filesystem
        if "SESSION_TYPE = 'filesystem'" in line or 'SESSION_TYPE = "filesystem"' in line:
            # Comment out the old line and add new configuration
            new_lines.append(f"# {line}")
            new_lines.append("    # Updated to use CacheLib backend directly (Flask-Session 0.5+)\n")
            new_lines.append("    SESSION_TYPE = 'cachelib'\n")
            new_lines.append("    SESSION_CACHELIB = FileSystemCache(cache_dir='flask_session', threshold=500)\n")
            print(f"  Updated SESSION_TYPE from 'filesystem' to 'cachelib'")
            changes_made = True
        else:
            new_lines.append(line)
            
    # Check if we need to add imports
    content = ''.join(new_lines)
    if 'SESSION_CACHELIB' in content and 'from cachelib' not in content:
        # Find import section
        import_added = False
        final_lines = []
        for line in new_lines:
            final_lines.append(line)
            if not import_added and ('import os' in line or 'from' in line and 'import' in line):
                final_lines.append("from cachelib import FileSystemCache\n")
                import_added = True
                print("  Added import: from cachelib import FileSystemCache")
                
        new_lines = final_lines
        
    if changes_made and not dry_run:
        with open(config_path, 'w') as f:
            f.writelines(new_lines)
        print(f"Updated {config_path}")
        
    return changes_made


def fix_app_file(app_path: Path, dry_run: bool = False) -> bool:
    """
    Fix Flask-Session initialization in app.py if needed.
    """
    if not app_path.exists():
        print(f"App file not found: {app_path}")
        return False
        
    with open(app_path, 'r') as f:
        content = f.read()
        
    original_content = content
    changes_made = False
    
    # Check for Flask-Session initialization
    if 'Session(app)' in content:
        # Make sure it's properly configured
        if 'from flask_session import Session' not in content:
            # Add import if missing
            lines = content.split('\n')
            for i, line in enumerate(lines):
                if 'from flask' in line:
                    lines.insert(i + 1, 'from flask_session import Session')
                    changes_made = True
                    print("  Added Flask-Session import")
                    break
            content = '\n'.join(lines)
            
    if changes_made and not dry_run:
        with open(app_path, 'w') as f:
            f.write(content)
        print(f"Updated {app_path}")
        
    return changes_made


def fix_requirements(req_path: Path, dry_run: bool = False) -> bool:
    """
    Ensure requirements.txt has the correct Flask-Session version.
    """
    if not req_path.exists():
        print(f"Requirements file not found: {req_path}")
        return False
        
    with open(req_path, 'r') as f:
        lines = f.readlines()
        
    new_lines = []
    changes_made = False
    has_cachelib = False
    
    for line in lines:
        if 'Flask-Session' in line:
            # Ensure we're using a recent version
            if not '>=0.5' in line and not '>=0.6' in line:
                new_lines.append('Flask-Session>=0.5.0\n')
                print(f"  Updated Flask-Session version requirement")
                changes_made = True
            else:
                new_lines.append(line)
        elif 'cachelib' in line.lower():
            has_cachelib = True
            new_lines.append(line)
        else:
            new_lines.append(line)
            
    # Add cachelib if missing and we're using Flask-Session
    if not has_cachelib and any('Flask-Session' in line for line in new_lines):
        new_lines.append('cachelib>=0.9.0\n')
        print("  Added cachelib dependency")
        changes_made = True
        
    if changes_made and not dry_run:
        with open(req_path, 'w') as f:
            f.writelines(new_lines)
        print(f"Updated {req_path}")
        
    return changes_made


def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(
        description='Fix Flask-Session configuration warnings'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be changed without modifying files'
    )
    
    args = parser.parse_args()
    
    # Get project root
    project_root = Path('.').resolve()
    
    print(f"Fixing Flask-Session warnings in: {project_root}")
    print(f"Mode: {'DRY RUN' if args.dry_run else 'LIVE'}")
    print("-" * 60)
    
    # Fix configuration files
    config_changed = fix_config_file(project_root / 'config.py', args.dry_run)
    app_changed = fix_app_file(project_root / 'app.py', args.dry_run)
    req_changed = fix_requirements(project_root / 'requirements.txt', args.dry_run)
    
    print("\n" + "="*60)
    print("FLASK-SESSION FIX SUMMARY")
    print("="*60)
    
    if args.dry_run:
        print("DRY RUN MODE - No files were actually modified")
        
    changes = sum([config_changed, app_changed, req_changed])
    print(f"Files updated: {changes}")
    
    if changes > 0:
        print("\nChanges made to eliminate Flask-Session warnings:")
        print("  - Removed deprecated SESSION_USE_SIGNER")
        print("  - Updated SESSION_TYPE to use CacheLib backend")
        print("  - Ensured proper Flask-Session version in requirements")
        
    print("="*60)
    
    return 0


if __name__ == '__main__':
    sys.exit(main())