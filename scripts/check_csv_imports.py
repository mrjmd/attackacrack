#!/usr/bin/env python
"""Check CSV import records in database"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from crm_database import CSVImport, db

app = create_app()

with app.app_context():
    # Query for record ID 15 specifically
    import_15 = CSVImport.query.filter_by(id=15).first()
    if import_15:
        print(f"\nFound CSV Import ID 15:")
        print(f"  Filename: {import_15.filename}")
        print(f"  Total Rows: {import_15.total_rows}")
        print(f"  Successful: {import_15.successful_imports}")
        print(f"  Failed: {import_15.failed_imports}")
        print(f"  Imported At: {import_15.imported_at}")
    else:
        print("\nCSV Import ID 15 not found")
    
    # Show all CSV imports
    print("\nAll CSV Import Records:")
    print("-" * 80)
    imports = CSVImport.query.order_by(CSVImport.id).all()
    for imp in imports:
        print(f"ID: {imp.id:3} | File: {imp.filename[:40]:40} | Total: {str(imp.total_rows):6} | Success: {str(imp.successful_imports):6} | Failed: {str(imp.failed_imports):6}")
    
    if not imports:
        print("No CSV import records found.")
    
    # Check for any incomplete imports
    print("\nIncomplete CSV Imports (with NULL values):")
    print("-" * 80)
    incomplete = CSVImport.query.filter(
        db.or_(
            CSVImport.total_rows.is_(None),
            CSVImport.successful_imports.is_(None),
            CSVImport.failed_imports.is_(None)
        )
    ).all()
    
    for imp in incomplete:
        print(f"ID: {imp.id:3} | File: {imp.filename[:40]:40} | Total: {imp.total_rows} | Success: {imp.successful_imports} | Failed: {imp.failed_imports}")
    
    if not incomplete:
        print("No incomplete CSV import records found.")