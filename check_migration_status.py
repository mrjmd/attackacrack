#!/usr/bin/env python3
"""Check database tables and migration status."""

from app import create_app
from crm_database import db
from sqlalchemy import inspect, text
import sys

app = create_app()

with app.app_context():
    inspector = inspect(db.engine)
    tables = inspector.get_table_names()
    
    print("=" * 60)
    print("DATABASE TABLE CHECK")
    print("=" * 60)
    
    # Check for our problematic tables
    check_tables = ['ab_test_result', 'ab_test_results', 'campaign_templates']
    for table in check_tables:
        exists = table in tables
        print(f"{table}: {'EXISTS' if exists else 'MISSING'}")
    
    print("\n" + "=" * 60)
    print("MIGRATION STATUS")
    print("=" * 60)
    
    # Check current migration version
    try:
        result = db.session.execute(text("SELECT version_num FROM alembic_version"))
        version = result.scalar()
        print(f"Current migration: {version}")
    except Exception as e:
        print(f"Error checking migration: {e}")
    
    print("\n" + "=" * 60)
    print("ALL TABLES IN DATABASE")
    print("=" * 60)
    for table in sorted(tables):
        print(f"  - {table}")
    
    # Check for stuck queries
    print("\n" + "=" * 60)
    print("CHECKING FOR STUCK QUERIES")
    print("=" * 60)
    
    try:
        stuck_queries = db.session.execute(text("""
            SELECT pid, now() - pg_stat_activity.query_start AS duration, 
                   state, query
            FROM pg_stat_activity
            WHERE (now() - pg_stat_activity.query_start) > interval '30 seconds'
            AND state != 'idle'
            ORDER BY duration DESC
        """))
        
        stuck_count = 0
        for row in stuck_queries:
            stuck_count += 1
            print(f"\nPID: {row[0]}")
            print(f"Duration: {row[1]}")
            print(f"State: {row[2]}")
            print(f"Query: {row[3][:200]}...")
        
        if stuck_count == 0:
            print("No stuck queries found")
    except Exception as e:
        print(f"Error checking stuck queries: {e}")