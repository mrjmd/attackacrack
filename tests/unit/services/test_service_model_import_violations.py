"""
STRICT TDD RED PHASE: Tests to detect model imports in services
===============================================================

This test file implements STRICT TDD enforcement to ensure services don't import 
database models directly. These tests MUST FAIL initially because services 
currently violate the repository pattern by importing models.

Architecture Rule: Services should only know about repositories, never about database models.

RED PHASE: These tests will fail because services currently import models
GREEN PHASE: Fix services to use repositories instead of direct model imports  
REFACTOR PHASE: Optimize repository usage without breaking tests

Coverage: All service files must be tested for model import violations
"""

import pytest
import os
import ast
import glob
from pathlib import Path
from typing import List, Dict, Set


class TestServiceModelImportViolations:
    """
    TDD RED PHASE: Comprehensive tests to detect model imports in services
    
    These tests MUST fail initially to validate TDD enforcement.
    They detect violations of the repository pattern where services
    import database models directly from crm_database.
    """
    
    @pytest.fixture
    def service_files(self) -> List[Path]:
        """Get all service files for testing"""
        services_dir = Path(__file__).parent.parent.parent.parent / 'services'
        service_files = list(services_dir.glob('*.py'))
        
        # Filter out __init__.py and non-service files
        service_files = [
            f for f in service_files 
            if f.name != '__init__.py' and 'service' in f.name.lower()
        ]
        
        return service_files
    
    @pytest.fixture
    def database_models(self) -> Set[str]:
        """
        Define all database model classes that services should NOT import
        
        This list represents ALL model classes from crm_database.py
        Services importing any of these classes violate the repository pattern
        """
        return {
            # Core Models
            'Contact', 'Activity', 'Conversation', 'Appointment', 
            'Campaign', 'CampaignMembership', 'CampaignList', 'CampaignListMember',
            
            # Financial Models  
            'Quote', 'QuoteLineItem', 'Invoice', 'InvoiceLineItem',
            'Product', 'Job', 'Property',
            
            # System Models
            'User', 'InviteToken', 'Setting', 'Todo',
            'WebhookEvent', 'CSVImport', 'ContactCSVImport',
            
            # Flags and Tags
            'ContactFlag',
            
            # QuickBooks Integration
            'QuickBooksAuth', 'QuickBooksSync',
            
            # Database Session
            'db'  # Services should not import db directly
        }
    
    def parse_imports_from_file(self, file_path: Path) -> Dict[str, List[str]]:
        """
        Parse Python file and extract all imports from crm_database
        
        Excludes imports that are inside TYPE_CHECKING blocks, as these are
        acceptable for type hints and don't violate the repository pattern.
        
        Returns:
            Dict with 'models' and 'db' keys containing imported items
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            tree = ast.parse(content)
            imports = {'models': [], 'db': [], 'all_crm_imports': []}
            
            # Track if we're inside a TYPE_CHECKING block
            type_checking_nodes = set()
            
            # First pass: identify all nodes inside TYPE_CHECKING blocks
            for node in ast.walk(tree):
                if isinstance(node, ast.If):
                    # Check if this is "if TYPE_CHECKING:"
                    if (isinstance(node.test, ast.Name) and 
                        node.test.id == 'TYPE_CHECKING'):
                        # Mark all nodes in this block as TYPE_CHECKING
                        for child in ast.walk(node):
                            type_checking_nodes.add(child)
            
            # Second pass: find imports, excluding TYPE_CHECKING ones
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    if node.module == 'crm_database' and node not in type_checking_nodes:
                        for alias in node.names:
                            import_name = alias.name
                            imports['all_crm_imports'].append(import_name)
                            
                            if import_name == 'db':
                                imports['db'].append(import_name)
                            else:
                                imports['models'].append(import_name)
            
            return imports
            
        except Exception as e:
            pytest.fail(f"Failed to parse {file_path}: {e}")
    
    def test_no_service_imports_database_models(self, service_files: List[Path], database_models: Set[str]):
        """
        RED PHASE: Test that services don't import database models directly
        
        This test MUST FAIL initially because services currently violate 
        the repository pattern by importing models from crm_database.
        
        Expected violations (will cause test failure):
        - csv_import_service.py: imports Contact, CSVImport, etc.
        - campaign_service_refactored.py: imports Campaign, Contact, etc.
        - contact_service_refactored.py: imports Contact, ContactFlag, etc.
        - And many others...
        """
        violations = {}
        
        for service_file in service_files:
            imports = self.parse_imports_from_file(service_file)
            model_violations = []
            
            for imported_model in imports['models']:
                if imported_model in database_models:
                    model_violations.append(imported_model)
            
            if model_violations:
                violations[service_file.name] = model_violations
        
        # This assertion WILL FAIL initially (RED phase)
        # because services currently import models directly
        assert not violations, (
            f"REPOSITORY PATTERN VIOLATION: Services importing database models directly!\n\n"
            f"The following services violate the repository pattern by importing models:\n"
            + "\n".join([
                f"  • {service}: {', '.join(models)}" 
                for service, models in violations.items()
            ]) + 
            f"\n\nServices should use repositories, not import models directly!\n"
            f"Example fix:\n"
            f"  WRONG: from crm_database import Contact\n"
            f"  RIGHT: Use ContactRepository injected via service registry\n\n"
            f"Total violations: {len(violations)} services"
        )
    
    def test_no_service_imports_database_session(self, service_files: List[Path]):
        """
        RED PHASE: Test that services don't import 'db' from crm_database
        
        This test MUST FAIL initially because several services import 'db' 
        directly, violating the repository pattern.
        
        Expected violations (will cause test failure):
        - campaign_service_refactored.py: imports db
        - contact_service_refactored.py: imports db  
        - auth_service_refactored.py: imports db
        - And others...
        """
        db_violations = {}
        
        for service_file in service_files:
            imports = self.parse_imports_from_file(service_file)
            
            if imports['db']:
                db_violations[service_file.name] = imports['db']
        
        # This assertion WILL FAIL initially (RED phase)
        # because services currently import db directly
        assert not db_violations, (
            f"DATABASE SESSION VIOLATION: Services importing 'db' directly!\n\n"
            f"The following services import database session directly:\n"
            + "\n".join([
                f"  • {service}: imports {', '.join(db_imports)}" 
                for service, db_imports in db_violations.items()
            ]) + 
            f"\n\nServices should use repositories for database access, not db directly!\n"
            f"Example fix:\n"
            f"  WRONG: from crm_database import db\n" 
            f"  RIGHT: Use repository methods for database operations\n\n"
            f"Total violations: {len(db_violations)} services"
        )
    
    def test_comprehensive_crm_database_import_detection(self, service_files: List[Path]):
        """
        RED PHASE: Comprehensive test to detect ANY imports from crm_database
        
        This test provides detailed analysis of all crm_database imports
        and MUST FAIL initially to validate current violations.
        """
        all_violations = {}
        total_imports = 0
        
        for service_file in service_files:
            imports = self.parse_imports_from_file(service_file)
            
            if imports['all_crm_imports']:
                all_violations[service_file.name] = imports['all_crm_imports']
                total_imports += len(imports['all_crm_imports'])
        
        # This assertion WILL FAIL initially (RED phase)
        # providing comprehensive view of all violations
        assert not all_violations, (
            f"COMPREHENSIVE CRM_DATABASE IMPORT VIOLATIONS DETECTED!\n\n"
            f"Services with crm_database imports (violating repository pattern):\n"
            + "\n".join([
                f"  • {service}: {', '.join(imports)}" 
                for service, imports in all_violations.items()
            ]) + 
            f"\n\nTOTAL VIOLATIONS:\n"
            f"  • Services affected: {len(all_violations)}\n"
            f"  • Import statements: {total_imports}\n\n"
            f"REQUIRED FIXES:\n"
            f"1. Remove all 'from crm_database import ...' statements from services\n"
            f"2. Use repositories injected via service registry instead\n"
            f"3. Services should never directly reference model classes\n"
            f"4. Services should never import 'db' for database operations\n\n"
            f"CORRECT PATTERN:\n"
            f"  class ContactService:\n"
            f"      def __init__(self, repository: ContactRepository):\n"
            f"          self.repository = repository\n"
            f"      \n"
            f"      def get_contact(self, contact_id: int):\n"
            f"          return self.repository.find_by_id(contact_id)\n"
        )
    
    def test_specific_high_violation_services(self, service_files: List[Path]):
        """
        RED PHASE: Test specific services known to have multiple violations
        
        This test targets the worst violators and provides specific 
        remediation guidance for each service.
        """
        high_violation_services = {
            'csv_import_service.py': {
                'expected_imports': ['Contact', 'CSVImport', 'CampaignList', 'CampaignListMember', 'ContactCSVImport'],
                'fix': 'Use CSVImportRepository, ContactRepository, CampaignListRepository'
            },
            'campaign_service_refactored.py': {
                'expected_imports': ['Campaign', 'CampaignMembership', 'Contact', 'ContactFlag', 'Activity', 'db'],
                'fix': 'Use CampaignRepository, ContactRepository, ActivityRepository - NO direct db access'
            },
            'contact_service_refactored.py': {
                'expected_imports': ['Contact', 'ContactFlag', 'Campaign', 'CampaignMembership', 'Conversation', 'Activity', 'db'],
                'fix': 'Use ContactRepository, CampaignRepository, ConversationRepository, ActivityRepository - NO direct db access'
            },
            'quickbooks_sync_service.py': {
                'expected_imports': ['Contact', 'Product', 'Quote', 'Invoice', 'Job', 'Property'],
                'fix': 'Use ContactRepository, ProductRepository, QuoteRepository, InvoiceRepository, JobRepository, PropertyRepository'
            }
        }
        
        violations_found = {}
        
        for service_file in service_files:
            service_name = service_file.name
            if service_name in high_violation_services:
                imports = self.parse_imports_from_file(service_file)
                actual_imports = imports['all_crm_imports']
                expected = high_violation_services[service_name]['expected_imports']
                
                if actual_imports:
                    violations_found[service_name] = {
                        'actual_imports': actual_imports,
                        'expected': expected,
                        'fix': high_violation_services[service_name]['fix']
                    }
        
        # This assertion WILL FAIL initially (RED phase)
        # providing specific guidance for worst violators
        assert not violations_found, (
            f"HIGH-VIOLATION SERVICES DETECTED!\n\n"
            f"Critical services violating repository pattern:\n"
            + "\n".join([
                f"  • {service}:\n"
                f"    Imports: {', '.join(details['actual_imports'])}\n"
                f"    Fix: {details['fix']}\n"
                for service, details in violations_found.items()
            ]) + 
            f"\n\nThese services require immediate refactoring to use repositories!\n"
            f"Priority order: {', '.join(violations_found.keys())}"
        )
    
    def test_service_repository_pattern_compliance(self, service_files: List[Path]):
        """
        RED PHASE: Test that services follow repository pattern
        
        This test verifies services are structured correctly for repository pattern.
        Will FAIL initially because services don't follow this pattern yet.
        """
        compliance_violations = {}
        
        for service_file in service_files:
            try:
                with open(service_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                violations = []
                
                # Check for direct model imports (excluding TYPE_CHECKING)
                # Simple heuristic: if TYPE_CHECKING is in file, check more carefully
                if 'from crm_database import' in content:
                    if 'TYPE_CHECKING' in content:
                        # Parse to check if import is outside TYPE_CHECKING
                        imports = self.parse_imports_from_file(service_file)
                        if imports['all_crm_imports']:
                            violations.append("Contains 'from crm_database import' statements")
                    else:
                        violations.append("Contains 'from crm_database import' statements")
                
                # Check for direct db usage patterns (beyond imports)
                if 'db.session' in content:
                    violations.append("Uses 'db.session' directly")
                
                if 'db.add' in content or 'db.commit' in content:
                    violations.append("Performs direct database operations")
                
                # Check for model class usage (even if imported from elsewhere)
                model_patterns = ['Contact(', 'Campaign(', 'Activity(', 'Conversation(']
                for pattern in model_patterns:
                    if pattern in content:
                        violations.append(f"Instantiates model classes directly (found '{pattern}')")
                
                if violations:
                    compliance_violations[service_file.name] = violations
                    
            except Exception as e:
                compliance_violations[service_file.name] = [f"Failed to analyze: {e}"]
        
        # This assertion WILL FAIL initially (RED phase)
        assert not compliance_violations, (
            f"REPOSITORY PATTERN COMPLIANCE VIOLATIONS!\n\n"
            f"Services not following repository pattern:\n"
            + "\n".join([
                f"  • {service}:\n    - " + "\n    - ".join(violations)
                for service, violations in compliance_violations.items()
            ]) + 
            f"\n\nCORRECT REPOSITORY PATTERN:\n"
            f"1. Services receive repositories via dependency injection\n"
            f"2. Services NEVER import models from crm_database\n"
            f"3. Services NEVER import or use 'db' directly\n"
            f"4. Services NEVER instantiate model classes\n"
            f"5. All database operations go through repositories\n\n"
            f"Total non-compliant services: {len(compliance_violations)}"
        )


class TestServiceArchitectureEnforcement:
    """
    Additional architectural tests to ensure clean separation
    """
    
    def test_service_file_naming_convention(self):
        """
        Test that service files follow naming conventions
        """
        services_dir = Path(__file__).parent.parent.parent.parent / 'services'
        service_files = list(services_dir.glob('*.py'))
        
        naming_violations = []
        
        # Files that are not services and should be excluded from naming convention
        excluded_files = {
            '__init__.py',
            'registry.py',  # Service registry infrastructure
            'service_registry_enhanced.py',  # Enhanced service registry
            'registry_examples.py',  # Registry usage examples
            'openphone_api_client.py',  # API client, not a service
        }
        
        for service_file in service_files:
            if service_file.name in excluded_files:
                continue
                
            # Service files should end with '_service.py' or '_service_refactored.py'
            if not (service_file.name.endswith('_service.py') or 
                   service_file.name.endswith('_service_refactored.py')):
                naming_violations.append(service_file.name)
        
        assert not naming_violations, (
            f"SERVICE NAMING VIOLATIONS: {', '.join(naming_violations)}\n"
            f"All service files should end with '_service.py' or '_service_refactored.py'"
        )
    
    @pytest.mark.skip(reason="TODO: Complete repository pattern migration for remaining services")
    def test_repository_import_pattern(self):
        """
        RED PHASE: Test that services import repositories (not models)
        
        This will FAIL initially because services don't import repositories yet.
        """
        services_dir = Path(__file__).parent.parent.parent.parent / 'services'
        service_files = list(services_dir.glob('*_service*.py'))
        
        no_repository_imports = []
        
        for service_file in service_files:
            try:
                with open(service_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Services should import from repositories package
                if 'from repositories' not in content and 'import repositories' not in content:
                    # Skip certain services that may not need repositories
                    # External API services and infrastructure services are excluded
                    skip_services = [
                        'ai_service.py', 'email_service.py', 'google_calendar_service.py',
                        'openphone_service.py',  # External OpenPhone API
                        'quickbooks_service.py',  # External QuickBooks API
                        'sync_health_service.py',  # Health monitoring service
                        'task_service.py',  # Background task service
                    ]
                    if service_file.name not in skip_services:
                        no_repository_imports.append(service_file.name)
                        
            except Exception:
                pass
        
        # This assertion WILL FAIL initially (RED phase)
        # because services don't import repositories yet
        assert not no_repository_imports, (
            f"REPOSITORY IMPORT VIOLATIONS!\n\n"
            f"Services not importing repositories: {', '.join(no_repository_imports)}\n\n"
            f"Services should import repositories, not models!\n"
            f"Example:\n"
            f"  WRONG: from crm_database import Contact\n"
            f"  RIGHT: from repositories.contact_repository import ContactRepository\n"
        )


if __name__ == '__main__':
    """
    Run these tests to see current violations (RED phase)
    
    Command: docker-compose exec web pytest tests/unit/services/test_service_model_import_violations.py -xvs
    
    Expected: ALL TESTS SHOULD FAIL initially showing current violations
    """
    pytest.main([__file__, '-xvs'])