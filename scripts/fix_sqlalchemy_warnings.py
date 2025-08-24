#!/usr/bin/env python3
"""
Automated script to replace deprecated SQLAlchemy Query.get() with Session.get().

Part of Phase 2 Test Cleanup - eliminates ~35 Query.get() deprecation warnings.

Usage:
    python scripts/fix_sqlalchemy_warnings.py [--dry-run] [--verbose]
    
Options:
    --dry-run: Show what would be changed without modifying files
    --verbose: Show detailed output for each file processed
"""

import os
import re
import sys
import argparse
from pathlib import Path
from typing import List, Tuple, Dict


class SQLAlchemyReplacer:
    """Handles replacement of Query.get() with Session.get() pattern."""
    
    def __init__(self, dry_run: bool = False, verbose: bool = False):
        self.dry_run = dry_run
        self.verbose = verbose
        self.changes_made = 0
        self.files_changed = 0
        self.errors = []
        
        # Patterns to match and replace
        self.patterns = [
            # Pattern 1: Model.query.get(id) -> db.session.get(Model, id)
            (
                r'(\w+)\.query\.get\(([^)]+)\)',
                r'db.session.get(\1, \2)'
            ),
            # Pattern 2: self.session.query(Model).get(id) -> self.session.get(Model, id)
            (
                r'self\.session\.query\((\w+)\)\.get\(([^)]+)\)',
                r'self.session.get(\1, \2)'
            ),
            # Pattern 3: db.session.query(Model).get(id) -> db.session.get(Model, id)
            (
                r'db\.session\.query\((\w+)\)\.get\(([^)]+)\)',
                r'db.session.get(\1, \2)'
            ),
            # Pattern 4: session.query(Model).get(id) -> session.get(Model, id)
            (
                r'(\w+)\.query\((\w+)\)\.get\(([^)]+)\)',
                r'\1.get(\2, \3)'
            ),
        ]
        
        # Files to exclude from processing
        self.exclude_patterns = [
            'scripts/fix_sqlalchemy_warnings.py',  # Don't modify this script
            'scripts/fix_datetime_warnings.py',  # Don't modify other fix scripts
            '__pycache__',
            '.git',
            '.pytest_cache',
            'venv',
            'env',
            '*.pyc',
            '*.md',  # Skip markdown files
            '*.txt',  # Skip text files
            '.claude',  # Skip Claude agent files
        ]
        
    def should_process_file(self, filepath: Path) -> bool:
        """Check if a file should be processed."""
        filepath_str = str(filepath)
        
        # Check exclusion patterns
        for pattern in self.exclude_patterns:
            if pattern in filepath_str:
                return False
                
        # Only process Python files
        if not filepath.suffix == '.py':
            return False
            
        # Skip test files that are disabled
        if filepath.name.endswith('.disabled') or filepath.name.endswith('.skip'):
            return False
            
        return True
        
    def process_file(self, filepath: Path) -> int:
        """Process a single file and return number of replacements made."""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                original_content = f.read()
                
            content = original_content
            replacements = 0
            
            # Apply replacements
            for pattern, replacement in self.patterns:
                matches = re.findall(pattern, content)
                if matches:
                    content, count = re.subn(pattern, replacement, content)
                    replacements += count
                    
            # Special handling for more complex patterns
            content, additional_replacements = self.handle_complex_patterns(content)
            replacements += additional_replacements
            
            # Write changes if not dry run and there were changes
            if replacements > 0:
                if not self.dry_run:
                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.write(content)
                        
                if self.verbose:
                    print(f"  {filepath}: {replacements} replacements")
                    
                return replacements
                
        except Exception as e:
            self.errors.append((filepath, str(e)))
            if self.verbose:
                print(f"  ERROR in {filepath}: {e}")
                
        return 0
        
    def handle_complex_patterns(self, content: str) -> Tuple[str, int]:
        """Handle more complex SQLAlchemy patterns that need special treatment."""
        replacements = 0
        
        # Pattern for repository methods using query.get()
        # Example: return self.query(Contact).get(contact_id)
        # Should become: return self.session.get(Contact, contact_id)
        pattern = r'self\.query\((\w+)\)\.get\(([^)]+)\)'
        matches = re.findall(pattern, content)
        if matches:
            content = re.sub(pattern, r'self.session.get(\1, \2)', content)
            replacements += len(matches)
            
        # Pattern for test fixtures using query.get()
        # Example: contact = Contact.query.get(1)
        # Should become: contact = db.session.get(Contact, 1)
        lines = content.split('\n')
        new_lines = []
        for line in lines:
            # Check if line contains Model.query.get pattern
            if '.query.get(' in line and 'db.session.get(' not in line:
                # Extract the model name
                match = re.search(r'(\w+)\.query\.get\(', line)
                if match:
                    model_name = match.group(1)
                    # Check if we need to ensure db import
                    if 'from app import db' not in content and 'import db' not in content:
                        # This file might need db import, but we'll handle it conservatively
                        pass
                        
            new_lines.append(line)
            
        content = '\n'.join(new_lines)
        
        return content, replacements
        
    def process_directory(self, directory: Path) -> Dict[str, int]:
        """Process all Python files in a directory recursively."""
        stats = {
            'files_processed': 0,
            'files_changed': 0,
            'total_replacements': 0,
            'errors': 0
        }
        
        # Find all Python files
        python_files = []
        for root, dirs, files in os.walk(directory):
            # Skip excluded directories
            dirs[:] = [d for d in dirs if not any(exc in d for exc in self.exclude_patterns)]
            
            for file in files:
                filepath = Path(root) / file
                if self.should_process_file(filepath):
                    python_files.append(filepath)
                    
        print(f"Found {len(python_files)} Python files to process")
        
        # Process each file
        for filepath in python_files:
            stats['files_processed'] += 1
            replacements = self.process_file(filepath)
            
            if replacements > 0:
                stats['files_changed'] += 1
                stats['total_replacements'] += replacements
                
        stats['errors'] = len(self.errors)
        
        return stats
        
    def print_summary(self, stats: Dict[str, int]):
        """Print a summary of changes made."""
        print("\n" + "="*60)
        print("SQLALCHEMY QUERY.GET() REPLACEMENT SUMMARY")
        print("="*60)
        
        if self.dry_run:
            print("DRY RUN MODE - No files were actually modified")
            
        print(f"Files processed: {stats['files_processed']}")
        print(f"Files changed: {stats['files_changed']}")
        print(f"Total replacements: {stats['total_replacements']}")
        
        if stats['errors'] > 0:
            print(f"\nErrors encountered: {stats['errors']}")
            for filepath, error in self.errors[:10]:  # Show first 10 errors
                print(f"  - {filepath}: {error}")
                
        print("\nExpected warning reduction: ~35 Query.get() warnings")
        print("="*60)


def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(
        description='Replace deprecated SQLAlchemy Query.get() with Session.get()'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be changed without modifying files'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Show detailed output for each file processed'
    )
    parser.add_argument(
        '--directory',
        type=str,
        default='.',
        help='Directory to process (default: current directory)'
    )
    
    args = parser.parse_args()
    
    # Get project root
    project_root = Path(args.directory).resolve()
    
    print(f"Processing directory: {project_root}")
    print(f"Mode: {'DRY RUN' if args.dry_run else 'LIVE'}")
    print(f"Verbose: {args.verbose}")
    print("-" * 60)
    
    # Create replacer and process files
    replacer = SQLAlchemyReplacer(dry_run=args.dry_run, verbose=args.verbose)
    stats = replacer.process_directory(project_root)
    
    # Print summary
    replacer.print_summary(stats)
    
    # Return exit code based on errors
    return 1 if stats['errors'] > 0 else 0


if __name__ == '__main__':
    sys.exit(main())