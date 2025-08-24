#!/usr/bin/env python3
"""
Script to check the reduction in test warnings after applying fixes.

Part of Phase 2 Test Cleanup - verifies warning reduction.
"""

import subprocess
import sys
import re
from pathlib import Path


def count_warnings(test_path: str = "tests/") -> dict:
    """Run tests and count warnings by type."""
    
    print(f"Running tests in {test_path}...")
    
    # Run pytest with warnings captured
    result = subprocess.run(
        [sys.executable, "-m", "pytest", test_path, "-q", "--tb=no", "-W", "default"],
        capture_output=True,
        text=True,
        timeout=300
    )
    
    # Parse output for warnings
    output = result.stderr + result.stdout
    
    # Count different types of warnings
    warning_counts = {
        'datetime.utcnow': len(re.findall(r'datetime\.utcnow.*deprecated', output, re.IGNORECASE)),
        'Query.get': len(re.findall(r'Query\.get.*deprecated', output, re.IGNORECASE)),
        'Flask-Session': len(re.findall(r'(SESSION_USE_SIGNER|FileSystemSessionInterface).*deprecated', output, re.IGNORECASE)),
        'total_warnings': len(re.findall(r'DeprecationWarning|PendingDeprecationWarning', output)),
        'passed_tests': len(re.findall(r'(\d+) passed', output)),
        'failed_tests': len(re.findall(r'(\d+) failed', output)),
    }
    
    # Extract test counts
    match = re.search(r'(\d+) passed', output)
    if match:
        warning_counts['passed_tests'] = int(match.group(1))
    
    match = re.search(r'(\d+) failed', output)
    if match:
        warning_counts['failed_tests'] = int(match.group(1))
    else:
        warning_counts['failed_tests'] = 0
        
    # Check for warnings summary
    if 'warnings summary' in output:
        # Extract warning count from summary
        match = re.search(r'(\d+) warning', output)
        if match:
            warning_counts['summary_warnings'] = int(match.group(1))
    
    return warning_counts


def main():
    """Main entry point."""
    print("="*60)
    print("WARNING REDUCTION CHECK")
    print("="*60)
    
    # Check warnings in different test directories
    test_dirs = [
        "tests/unit/repositories",
        "tests/unit/services",
        "tests/integration",
    ]
    
    total_counts = {
        'datetime.utcnow': 0,
        'Query.get': 0,
        'Flask-Session': 0,
        'total_warnings': 0,
        'passed_tests': 0,
        'failed_tests': 0
    }
    
    for test_dir in test_dirs:
        if Path(test_dir).exists():
            print(f"\nChecking {test_dir}...")
            counts = count_warnings(test_dir)
            
            print(f"  Passed tests: {counts.get('passed_tests', 0)}")
            print(f"  Failed tests: {counts.get('failed_tests', 0)}")
            print(f"  datetime.utcnow warnings: {counts['datetime.utcnow']}")
            print(f"  Query.get warnings: {counts['Query.get']}")
            print(f"  Flask-Session warnings: {counts['Flask-Session']}")
            
            # Add to totals
            for key in total_counts:
                total_counts[key] += counts.get(key, 0)
    
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    print(f"Total passed tests: {total_counts['passed_tests']}")
    print(f"Total failed tests: {total_counts['failed_tests']}")
    print(f"\nWarning counts:")
    print(f"  datetime.utcnow: {total_counts['datetime.utcnow']} (target: 0, was ~399)")
    print(f"  Query.get: {total_counts['Query.get']} (target: 0, was ~35)")
    print(f"  Flask-Session: {total_counts['Flask-Session']} (target: 0, was ~2)")
    
    print("\n" + "="*60)
    print("EXPECTED REDUCTION")
    print("="*60)
    print(f"datetime.utcnow warnings eliminated: ~{399 - total_counts['datetime.utcnow']}")
    print(f"Query.get warnings eliminated: ~{35 - total_counts['Query.get']}")
    print(f"Flask-Session warnings eliminated: ~{2 - total_counts['Flask-Session']}")
    
    estimated_total_reduction = (399 - total_counts['datetime.utcnow']) + \
                                (35 - total_counts['Query.get']) + \
                                (2 - total_counts['Flask-Session'])
    
    print(f"\nTotal warnings eliminated: ~{estimated_total_reduction} of 436")
    print(f"Reduction percentage: {(estimated_total_reduction / 436) * 100:.1f}%")
    
    print("="*60)
    
    return 0


if __name__ == '__main__':
    sys.exit(main())