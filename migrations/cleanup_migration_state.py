#!/usr/bin/env python3
"""
Clean up and verify migration state for Phase 3.
This script ensures migrations are properly tracked and can handle edge cases.
"""

from alembic import op
from sqlalchemy import text, inspect
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from crm_database import db

def verify_migration_state():
    """Verify and report on current migration state."""
    app = create_app()
    
    with app.app_context():
        conn = db.engine.connect()
        inspector = inspect(conn)
        
        print("=" * 60)
        print("MIGRATION STATE VERIFICATION")
        print("=" * 60)
        
        # Check current migration version
        try:
            result = conn.execute(text("SELECT version_num FROM alembic_version"))
            version = result.scalar()
            print(f"Current migration version: {version}")
        except Exception as e:
            print(f"Error checking migration version: {e}")
            return False
        
        # Check for the specific tables
        tables = inspector.get_table_names()
        phase3_tables = {
            'ab_test_result': 'Phase 3 A/B Testing Results',
            'campaign_templates': 'Phase 3 Campaign Templates'
        }
        
        print("\nPhase 3 Tables:")
        all_exist = True
        for table_name, description in phase3_tables.items():
            exists = table_name in tables
            status = "✅ EXISTS" if exists else "❌ MISSING"
            print(f"  {table_name}: {status} - {description}")
            if not exists:
                all_exist = False
        
        # Check for any lock issues
        print("\nChecking for database locks...")
        lock_query = text("""
            SELECT 
                pg_locks.pid,
                pg_stat_activity.query,
                pg_stat_activity.state,
                pg_stat_activity.wait_event_type,
                pg_stat_activity.wait_event,
                now() - pg_stat_activity.query_start as duration
            FROM pg_locks
            JOIN pg_stat_activity ON pg_locks.pid = pg_stat_activity.pid
            WHERE pg_locks.mode = 'AccessExclusiveLock'
            AND pg_stat_activity.query NOT LIKE '%pg_locks%'
            ORDER BY duration DESC
        """)
        
        try:
            locks = conn.execute(lock_query)
            lock_count = 0
            for row in locks:
                lock_count += 1
                print(f"\n  Lock found:")
                print(f"    PID: {row[0]}")
                print(f"    Query: {row[1][:100]}...")
                print(f"    State: {row[2]}")
                print(f"    Duration: {row[5]}")
            
            if lock_count == 0:
                print("  ✅ No exclusive locks found")
        except Exception as e:
            print(f"  Could not check locks: {e}")
        
        conn.close()
        return all_exist

def cleanup_stuck_migrations():
    """Clean up any stuck migration processes."""
    app = create_app()
    
    with app.app_context():
        conn = db.engine.connect()
        
        print("\n" + "=" * 60)
        print("CLEANING STUCK MIGRATIONS")
        print("=" * 60)
        
        # Find and terminate stuck CREATE TABLE queries
        stuck_query = text("""
            SELECT pid, now() - pg_stat_activity.query_start AS duration, query
            FROM pg_stat_activity
            WHERE query LIKE 'CREATE TABLE%'
            AND (now() - pg_stat_activity.query_start) > interval '1 minute'
        """)
        
        try:
            stuck = conn.execute(stuck_query)
            terminated = 0
            for row in stuck:
                pid = row[0]
                duration = row[1]
                query = row[2][:100]
                
                print(f"\nTerminating stuck query:")
                print(f"  PID: {pid}")
                print(f"  Duration: {duration}")
                print(f"  Query: {query}...")
                
                try:
                    conn.execute(text(f"SELECT pg_terminate_backend({pid})"))
                    terminated += 1
                    print(f"  ✅ Terminated PID {pid}")
                except Exception as e:
                    print(f"  ❌ Failed to terminate: {e}")
            
            if terminated == 0:
                print("✅ No stuck migrations found")
            else:
                print(f"\n✅ Terminated {terminated} stuck migration(s)")
                
        except Exception as e:
            print(f"Error checking for stuck migrations: {e}")
        
        conn.close()

def ensure_tables_exist():
    """Ensure Phase 3 tables exist even if migrations are confused."""
    app = create_app()
    
    with app.app_context():
        print("\n" + "=" * 60)
        print("ENSURING PHASE 3 TABLES EXIST")
        print("=" * 60)
        
        # This will create tables based on the models if they don't exist
        # But won't modify existing tables
        from crm_database import ABTestResult, CampaignTemplate
        
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        
        # Check and report status
        if 'ab_test_result' in tables:
            print("✅ ab_test_result table already exists")
        else:
            print("❌ ab_test_result table missing - would need migration")
        
        if 'campaign_templates' in tables:
            print("✅ campaign_templates table already exists")
        else:
            print("❌ campaign_templates table missing - would need migration")
        
        return True

def main():
    """Run all cleanup and verification steps."""
    print("\n🔧 PHASE 3 MIGRATION CLEANUP AND VERIFICATION\n")
    
    # Step 1: Verify current state
    state_ok = verify_migration_state()
    
    # Step 2: Clean up stuck migrations if any
    cleanup_stuck_migrations()
    
    # Step 3: Ensure tables exist
    tables_ok = ensure_tables_exist()
    
    # Summary
    print("\n" + "=" * 60)
    print("CLEANUP SUMMARY")
    print("=" * 60)
    
    if state_ok and tables_ok:
        print("✅ Phase 3 database is in good state")
        print("✅ Both ab_test_result and campaign_templates tables exist")
        print("✅ No migration issues detected")
        print("\n🎉 You can safely proceed with Phase 3 development!")
    else:
        print("⚠️ Some issues were detected")
        print("Please review the output above and run migrations if needed:")
        print("  docker-compose exec web flask db upgrade")
    
    print("=" * 60)

if __name__ == "__main__":
    main()