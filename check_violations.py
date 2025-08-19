#!/usr/bin/env python3
"""
Simple script to check for architectural violations in services
"""

import os
import re
from pathlib import Path

def check_service_violations():
    """Check all service files for crm_database imports"""
    services_dir = Path('services')
    if not services_dir.exists():
        print("Services directory not found")
        return False
    
    violations = []
    service_files = list(services_dir.glob('*_service*.py'))
    service_files.extend(services_dir.glob('*service.py'))
    
    # Remove duplicates
    service_files = list(set(service_files))
    
    for service_file in service_files:
        if service_file.name == '__init__.py':
            continue
            
        try:
            with open(service_file, 'r') as f:
                content = f.read()
            
            # Check for direct imports from crm_database
            if 'from crm_database import' in content:
                violations.append(f"{service_file.name}: contains 'from crm_database import'")
            
            # Check for TYPE_CHECKING imports of models (not repositories)
            type_checking_pattern = r'if TYPE_CHECKING:.*?from crm_database import'
            if re.search(type_checking_pattern, content, re.DOTALL):
                violations.append(f"{service_file.name}: TYPE_CHECKING import from crm_database")
            
            # Check for direct db usage
            if 'from crm_database import db' in content:
                violations.append(f"{service_file.name}: imports db directly")
                
        except Exception as e:
            print(f"Error reading {service_file}: {e}")
    
    if violations:
        print("ARCHITECTURAL VIOLATIONS FOUND:")
        for violation in violations:
            print(f"  - {violation}")
        return False
    else:
        print("✅ NO ARCHITECTURAL VIOLATIONS FOUND")
        print(f"Checked {len(service_files)} service files")
        return True

if __name__ == '__main__':
    success = check_service_violations()
    exit(0 if success else 1)
