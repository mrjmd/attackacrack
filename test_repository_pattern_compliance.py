#!/usr/bin/env python3
"""
Test script to verify campaign_template_service complies with repository pattern
This ensures the service works without importing database models
"""

import sys
import importlib.util
import ast


def check_service_imports():
    """Check that the service doesn't import database models"""
    file_path = "services/campaign_template_service.py"
    
    with open(file_path, 'r') as f:
        content = f.read()
    
    tree = ast.parse(content)
    
    violations = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module and 'crm_database' in node.module:
                for alias in node.names:
                    violations.append(f"Import of {alias.name} from crm_database")
    
    return violations


def test_enum_imports():
    """Verify enums are imported from services.enums"""
    try:
        from services.enums import TemplateCategory, TemplateStatus
        print("✓ Enums successfully imported from services.enums")
        return True
    except ImportError as e:
        print(f"✗ Failed to import enums: {e}")
        return False


def test_service_imports():
    """Test that service can be imported without database model dependencies"""
    try:
        # This should work without importing CampaignTemplate model
        from services.campaign_template_service import (
            CampaignTemplateService,
            TemplateVariable,
            TemplateValidationError,
            TemplateNotFoundError,
            TemplateDuplicateError
        )
        print("✓ Service successfully imported without database models")
        return True
    except ImportError as e:
        print(f"✗ Failed to import service: {e}")
        return False


def test_service_methods_return_dicts():
    """Verify service methods return dictionaries, not model objects"""
    from services.campaign_template_service import CampaignTemplateService
    import inspect
    
    # Methods that should return dictionaries
    dict_return_methods = [
        'create_template',
        'get_template', 
        'list_templates',
        'search_templates',
        'get_templates_by_category',
        'update_template',
        'soft_delete_template',
        'approve_template',
        'activate_template',
        'archive_template',
        'track_usage',
        'get_template_versions',
        'revert_to_version',
        'clone_template'
    ]
    
    issues = []
    for method_name in dict_return_methods:
        method = getattr(CampaignTemplateService, method_name)
        sig = inspect.signature(method)
        return_annotation = sig.return_annotation
        
        # Check if return type is Dict or List[Dict]
        if return_annotation != inspect._empty:
            return_str = str(return_annotation)
            if 'Dict' in return_str or 'dict' in return_str or 'List' in return_str or 'bool' in return_str:
                print(f"✓ {method_name} returns {return_str}")
            elif 'CampaignTemplate' in return_str:
                issues.append(f"{method_name} still returns CampaignTemplate")
                print(f"✗ {method_name} returns {return_str}")
    
    return issues


def main():
    """Run all compliance checks"""
    print("=" * 60)
    print("Repository Pattern Compliance Check")
    print("=" * 60)
    
    # Check for database imports
    print("\n1. Checking for database model imports...")
    violations = check_service_imports()
    if violations:
        print("✗ Found database model imports:")
        for v in violations:
            print(f"  - {v}")
    else:
        print("✓ No database model imports found")
    
    # Test enum imports
    print("\n2. Testing enum imports...")
    enum_ok = test_enum_imports()
    
    # Test service imports
    print("\n3. Testing service imports...")
    service_ok = test_service_imports()
    
    # Test return types
    print("\n4. Checking method return types...")
    if service_ok:
        return_issues = test_service_methods_return_dicts()
        if return_issues:
            print("\n✗ Methods still returning model objects:")
            for issue in return_issues:
                print(f"  - {issue}")
    
    # Summary
    print("\n" + "=" * 60)
    if not violations and enum_ok and service_ok and not return_issues:
        print("✅ Service fully complies with repository pattern!")
        print("   - No database model imports")
        print("   - Enums imported from services layer")
        print("   - All methods return dictionaries/primitives")
        return 0
    else:
        print("❌ Service has compliance issues")
        return 1


if __name__ == "__main__":
    sys.exit(main())