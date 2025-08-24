#!/usr/bin/env python3
"""
Automated script to replace deprecated datetime.utcnow() with timezone-aware alternatives.

Part of Phase 2 Test Cleanup - eliminates ~399 deprecation warnings.

Usage:
    python scripts/fix_datetime_warnings.py [--dry-run] [--verbose]
    
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


class DatetimeReplacer:
    """Handles replacement of datetime.utcnow() with timezone-aware alternatives."""
    
    def __init__(self, dry_run: bool = False, verbose: bool = False):
        self.dry_run = dry_run
        self.verbose = verbose
        self.changes_made = 0
        self.files_changed = 0
        self.errors = []
        
        # Patterns to match and replace
        self.patterns = [
            # Pattern 1: datetime.utcnow() -> utc_now()
            (
                r'datetime\.utcnow\(\)',
                'utc_now()',
                'from utils.datetime_utils import utc_now'
            ),
            # Pattern 2: datetime.datetime.utcnow() -> utc_now()
            (
                r'datetime\.datetime\.utcnow\(\)',
                'utc_now()',
                'from utils.datetime_utils import utc_now'
            ),
            # Pattern 3: from datetime import datetime, utcnow usage
            (
                r'from datetime import ([^;]+?)utcnow',
                r'from datetime import \1',
                None  # No import needed, will be handled separately
            ),
        ]
        
        # Files to exclude from processing
        self.exclude_patterns = [
            'scripts/fix_datetime_warnings.py',  # Don't modify this script
            'utils/datetime_utils.py',  # Don't modify the utils module
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
        
    def add_import_if_needed(self, content: str, import_statement: str) -> str:
        """Add import statement if not already present."""
        if not import_statement:
            return content
            
        # Check if import already exists
        if import_statement in content:
            return content
            
        # Check if utc_now is already imported
        if 'from utils.datetime_utils import' in content and 'utc_now' in content:
            return content
            
        # Find the right place to add the import
        lines = content.split('\n')
        
        # Look for existing imports
        import_section_end = 0
        has_datetime_import = False
        datetime_import_line = -1
        
        for i, line in enumerate(lines):
            if line.startswith('import ') or line.startswith('from '):
                import_section_end = i + 1
                if 'from datetime import' in line or 'import datetime' in line:
                    has_datetime_import = True
                    datetime_import_line = i
            elif import_section_end > 0 and line and not line.startswith('#'):
                # End of import section
                break
                
        # Add import after datetime imports if they exist
        if has_datetime_import and datetime_import_line >= 0:
            lines.insert(datetime_import_line + 1, import_statement)
        elif import_section_end > 0:
            # Add at the end of import section
            lines.insert(import_section_end, import_statement)
        else:
            # Add after module docstring and comments
            insert_pos = 0
            in_docstring = False
            for i, line in enumerate(lines):
                if line.startswith('"""') or line.startswith("'''"):
                    in_docstring = not in_docstring
                elif not in_docstring and line and not line.startswith('#'):
                    insert_pos = i
                    break
            lines.insert(insert_pos, import_statement)
            lines.insert(insert_pos + 1, '')
            
        return '\n'.join(lines)
        
    def process_file(self, filepath: Path) -> int:
        """Process a single file and return number of replacements made."""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                original_content = f.read()
                
            content = original_content
            replacements = 0
            needs_import = False
            import_to_add = None
            
            # Apply replacements
            for pattern, replacement, import_stmt in self.patterns:
                matches = re.findall(pattern, content)
                if matches:
                    content = re.sub(pattern, replacement, content)
                    replacements += len(matches)
                    if import_stmt:
                        needs_import = True
                        import_to_add = import_stmt
                        
            # Add import if needed
            if needs_import and import_to_add:
                content = self.add_import_if_needed(content, import_to_add)
                
            # Clean up any double imports or unused imports
            content = self.cleanup_imports(content)
            
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
        
    def cleanup_imports(self, content: str) -> str:
        """Clean up duplicate or unnecessary imports."""
        lines = content.split('\n')
        seen_imports = set()
        cleaned_lines = []
        
        for line in lines:
            # Remove duplicate imports
            if line.startswith('from ') or line.startswith('import '):
                if line in seen_imports:
                    continue  # Skip duplicate
                seen_imports.add(line)
                
            # Remove empty datetime imports
            if line == 'from datetime import ':
                continue
                
            cleaned_lines.append(line)
            
        return '\n'.join(cleaned_lines)
        
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
        print("DATETIME REPLACEMENT SUMMARY")
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
                
        print("\nExpected warning reduction: ~399 datetime.utcnow() warnings")
        print("="*60)


def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(
        description='Replace deprecated datetime.utcnow() with timezone-aware alternatives'
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
    replacer = DatetimeReplacer(dry_run=args.dry_run, verbose=args.verbose)
    stats = replacer.process_directory(project_root)
    
    # Print summary
    replacer.print_summary(stats)
    
    # Return exit code based on errors
    return 1 if stats['errors'] > 0 else 0


if __name__ == '__main__':
    sys.exit(main())