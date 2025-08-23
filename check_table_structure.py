#!/usr/bin/env python3
"""Check table structure for ab_test_result and campaign_templates."""

from app import create_app
from crm_database import db
from sqlalchemy import inspect, text

app = create_app()

with app.app_context():
    inspector = inspect(db.engine)
    
    for table_name in ['ab_test_result', 'campaign_templates']:
        print("=" * 60)
        print(f"TABLE: {table_name}")
        print("=" * 60)
        
        try:
            # Get columns
            columns = inspector.get_columns(table_name)
            print("\nCOLUMNS:")
            for col in columns:
                nullable = "NULL" if col['nullable'] else "NOT NULL"
                print(f"  - {col['name']}: {col['type']} {nullable}")
            
            # Get indexes
            indexes = inspector.get_indexes(table_name)
            print("\nINDEXES:")
            for idx in indexes:
                unique = "UNIQUE" if idx['unique'] else ""
                print(f"  - {idx['name']}: {idx['column_names']} {unique}")
            
            # Get foreign keys
            fks = inspector.get_foreign_keys(table_name)
            print("\nFOREIGN KEYS:")
            for fk in fks:
                print(f"  - {fk['name']}: {fk['constrained_columns']} -> {fk['referred_table']}.{fk['referred_columns']}")
            
            # Get unique constraints
            uniques = inspector.get_unique_constraints(table_name)
            print("\nUNIQUE CONSTRAINTS:")
            for unique in uniques:
                print(f"  - {unique['name']}: {unique['column_names']}")
                
        except Exception as e:
            print(f"Error inspecting table: {e}")
        
        print()