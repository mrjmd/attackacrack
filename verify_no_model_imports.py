#!/usr/bin/env python
"""
Quick script to verify no services are importing from crm_database
"""

import os
import ast
from pathlib import Path

def check_service_files():
    """Check all service files for crm_database imports"""
    services_dir = Path(__file__).parent / 'services'
    service_files = list(services_dir.glob('*_service*.py'))
    
    # Filter out non-service files
    service_files = [
        f for f in service_files 
        if f.name != '__init__.py' and 'service' in f.name.lower()
    ]
    
    violations = {}
    
    for service_file in service_files:
        try:
            with open(service_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            tree = ast.parse(content)
            imports = []
            
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    if node.module == 'crm_database':
                        for alias in node.names:
                            imports.append(alias.name)
            
            if imports:
                violations[service_file.name] = imports
                
        except Exception as e:
            print(f"Error parsing {service_file.name}: {e}")
    
    return violations

def main():
    print("Checking services for crm_database imports...")
    violations = check_service_files()
    
    if violations:
        print("\n❌ VIOLATIONS FOUND:")
        for service, imports in violations.items():
            print(f"  • {service}: {', '.join(imports)}")
        print(f"\nTotal violations: {len(violations)} services")
        return 1
    else:
        print("\n✅ SUCCESS: No services importing from crm_database!")
        print("All services follow the repository pattern correctly.")
        return 0

if __name__ == '__main__':
    exit(main())