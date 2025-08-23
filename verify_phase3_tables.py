#!/usr/bin/env python3
"""Comprehensive verification of Phase 3 database tables and services."""

from app import create_app
from crm_database import db, ABTestResult, CampaignTemplate
from sqlalchemy import inspect, text
import sys
from datetime import datetime

app = create_app()

def check_tables():
    """Verify tables exist and have correct structure."""
    with app.app_context():
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        
        print("=" * 60)
        print("PHASE 3 TABLE VERIFICATION")
        print("=" * 60)
        
        # Check required tables
        required_tables = {
            'ab_test_result': ABTestResult,
            'campaign_templates': CampaignTemplate
        }
        
        all_good = True
        for table_name, model_class in required_tables.items():
            if table_name in tables:
                print(f"✅ {table_name}: EXISTS")
                
                # Verify we can query the table
                try:
                    count = db.session.query(model_class).count()
                    print(f"   - Record count: {count}")
                except Exception as e:
                    print(f"   ❌ Error querying: {e}")
                    all_good = False
            else:
                print(f"❌ {table_name}: MISSING")
                all_good = False
        
        return all_good

def test_repository_access():
    """Test that repositories can be accessed through service registry."""
    with app.app_context():
        print("\n" + "=" * 60)
        print("REPOSITORY ACCESS TEST")
        print("=" * 60)
        
        from flask import current_app
        
        # Test AB Test Result Repository
        try:
            ab_repo = current_app.services.get('ab_test_result_repository')
            print(f"✅ ab_test_result_repository: {type(ab_repo).__name__}")
        except Exception as e:
            print(f"❌ ab_test_result_repository: {e}")
            return False
        
        # Test Campaign Template Repository
        try:
            template_repo = current_app.services.get('campaign_template_repository')
            print(f"✅ campaign_template_repository: {type(template_repo).__name__}")
        except Exception as e:
            print(f"❌ campaign_template_repository: {e}")
            return False
        
        return True

def test_services():
    """Test that services can be accessed and are properly initialized."""
    with app.app_context():
        print("\n" + "=" * 60)
        print("SERVICE INITIALIZATION TEST")
        print("=" * 60)
        
        from flask import current_app
        
        # Test AB Testing Service
        try:
            ab_service = current_app.services.get('ab_testing')
            print(f"✅ ab_testing service: {type(ab_service).__name__}")
        except Exception as e:
            print(f"❌ ab_testing service: {e}")
            return False
        
        # Test Campaign Template Service
        try:
            template_service = current_app.services.get('campaign_template')
            print(f"✅ campaign_template service: {type(template_service).__name__}")
        except Exception as e:
            print(f"❌ campaign_template service: {e}")
            return False
        
        return True

def test_crud_operations():
    """Test basic CRUD operations on the new tables."""
    with app.app_context():
        print("\n" + "=" * 60)
        print("CRUD OPERATIONS TEST")
        print("=" * 60)
        
        try:
            # Test creating a campaign template
            template = CampaignTemplate(
                name=f"Test Template {datetime.now().isoformat()}",
                content="Test content with {{name}} variable",
                description="Test template for verification",
                category="test",
                status="draft",
                version=1,
                created_at=datetime.utcnow()
            )
            db.session.add(template)
            db.session.commit()
            print(f"✅ Created CampaignTemplate with ID: {template.id}")
            
            # Clean up
            db.session.delete(template)
            db.session.commit()
            print("✅ Deleted test CampaignTemplate")
            
            return True
            
        except Exception as e:
            print(f"❌ CRUD operation failed: {e}")
            db.session.rollback()
            return False

def main():
    """Run all verification tests."""
    print("\n🔍 RUNNING PHASE 3 DATABASE VERIFICATION\n")
    
    results = []
    
    # Run all tests
    results.append(("Table Structure", check_tables()))
    results.append(("Repository Access", test_repository_access()))
    results.append(("Service Initialization", test_services()))
    results.append(("CRUD Operations", test_crud_operations()))
    
    # Summary
    print("\n" + "=" * 60)
    print("VERIFICATION SUMMARY")
    print("=" * 60)
    
    all_passed = True
    for test_name, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{test_name}: {status}")
        if not passed:
            all_passed = False
    
    print("\n" + "=" * 60)
    if all_passed:
        print("🎉 ALL PHASE 3 DATABASE COMPONENTS VERIFIED SUCCESSFULLY!")
        print("The ab_test_result and campaign_templates tables are ready for use.")
    else:
        print("⚠️ Some verification tests failed. Please review the output above.")
    print("=" * 60)
    
    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())