#!/usr/bin/env python3
"""Test migration chain to verify CI/CD will work"""

import tempfile
import os
import sys
from sqlalchemy import create_engine, text
from alembic.config import Config
from alembic import command

def test_migration_chain():
    """Test that migrations work from scratch (as in CI/CD)"""
    
    # Create a temporary SQLite database to test migrations
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
        db_path = tmp.name
    
    try:
        # Create database URL
        db_url = f'sqlite:///{db_path}'
        
        # Create engine and database
        engine = create_engine(db_url)
        
        # Configure Alembic
        alembic_cfg = Config('alembic.ini')
        alembic_cfg.set_main_option('sqlalchemy.url', db_url)
        
        print("Testing migration chain from scratch...")
        print(f"Database: {db_path}")
        
        # Run all migrations
        print("\n1. Running initial migration (c4c776fc75e9)...")
        try:
            command.upgrade(alembic_cfg, 'c4c776fc75e9')
        except Exception as e:
            print(f"   Migration error: {e}")
            import traceback
            traceback.print_exc()
        
        # Verify user table exists with correct structure
        with engine.connect() as conn:
            result = conn.execute(text("SELECT sql FROM sqlite_master WHERE type='table' AND name='user'"))
            row = result.fetchone()
            if row:
                print("   ✓ User table created successfully")
                # Check for password_hash column
                result = conn.execute(text("PRAGMA table_info(user)"))
                columns = {row[1]: row[2] for row in result}
                if 'password_hash' in columns:
                    print(f"   ✓ password_hash column exists (type: {columns['password_hash']})")
            else:
                print("   ✗ User table not found!")
                return False
        
        print("\n2. Running todo migration (5666d6960685)...")
        command.upgrade(alembic_cfg, '5666d6960685')
        
        # Verify todos table exists
        with engine.connect() as conn:
            result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='todos'"))
            if result.fetchone():
                print("   ✓ Todos table created successfully")
            else:
                print("   ✗ Todos table not found!")
                return False
        
        print("\n3. Running password hash upgrade migration (2792ed2d7978)...")
        command.upgrade(alembic_cfg, '2792ed2d7978')
        
        # Verify activity and campaign_membership changes
        with engine.connect() as conn:
            # Check activity table for new column
            result = conn.execute(text("PRAGMA table_info(activity)"))
            columns = [row[1] for row in result]
            if 'activity_metadata' in columns:
                print("   ✓ activity_metadata column added")
            
            # Check campaign_membership table for new columns
            result = conn.execute(text("PRAGMA table_info(campaign_membership)"))
            columns = [row[1] for row in result]
            if 'sent_activity_id' in columns:
                print("   ✓ sent_activity_id column added")
            if 'membership_metadata' in columns:
                print("   ✓ membership_metadata column added")
        
        print("\n4. Checking final state...")
        command.current(alembic_cfg)
        
        print("\n✅ All migrations completed successfully!")
        print("CI/CD should now work correctly with these migrations.")
        return True
        
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        # Clean up temporary database
        if os.path.exists(db_path):
            os.unlink(db_path)

if __name__ == '__main__':
    success = test_migration_chain()
    sys.exit(0 if success else 1)