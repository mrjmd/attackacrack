#!/usr/bin/env python3
"""
Local linting and code quality checks
Run this before pushing to catch CI issues early
"""

import subprocess
import sys
import os

def run_command(command, description):
    """Run a command and report results"""
    print(f"\n{'='*60}")
    print(f"Running: {description}")
    print(f"Command: {command}")
    print('='*60)
    
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)
    
    if result.returncode != 0:
        print(f"❌ FAILED: {description}")
        return False
    else:
        print(f"✅ PASSED: {description}")
        return True

def main():
    """Run all lint checks"""
    # Change to project root
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.chdir(project_root)
    
    all_passed = True
    
    # Check for Python syntax errors and undefined names
    if not run_command(
        "flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics "
        "--exclude=.git,__pycache__,docs,old_env,venv,env,.venv,migrations,node_modules",
        "Syntax errors and undefined names check"
    ):
        all_passed = False
    
    # Run full flake8 (warnings only)
    run_command(
        "flake8 . --count --exit-zero --max-complexity=10 --max-line-length=120 --statistics "
        "--exclude=.git,__pycache__,docs,old_env,venv,env,.venv,migrations,node_modules",
        "Full flake8 check (warnings)"
    )
    
    # Security scan with bandit
    if not run_command(
        "bandit -r . -f json -o bandit-report.json "
        "--skip B101 "
        "-x '.git,__pycache__,docs,old_env,venv,env,migrations,tests' || true",
        "Security scan with bandit"
    ):
        print("Note: Check bandit-report.json for security issues")
    
    # Check if requirements are installed
    print("\n" + "="*60)
    print("Checking Python dependencies...")
    print("="*60)
    
    missing_deps = []
    for dep in ['flake8', 'bandit', 'pytest', 'pytest-cov']:
        result = subprocess.run(f"pip show {dep}", shell=True, capture_output=True)
        if result.returncode != 0:
            missing_deps.append(dep)
    
    if missing_deps:
        print(f"⚠️  Missing dependencies: {', '.join(missing_deps)}")
        print(f"Install with: pip install {' '.join(missing_deps)}")
    else:
        print("✅ All linting dependencies installed")
    
    # Summary
    print("\n" + "="*60)
    if all_passed:
        print("✅ All checks passed! Safe to push to GitHub.")
    else:
        print("❌ Some checks failed. Fix issues before pushing.")
        sys.exit(1)
    print("="*60)

if __name__ == "__main__":
    main()