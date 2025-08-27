"""
Debug test to see exactly what the route returns when the bug occurs
"""

import pytest
import io
from app import create_app
from crm_database import CampaignList, CSVImport, Contact, CampaignListMember
from extensions import db


def test_debug_route_response():
    """
    Debug what the CSV import route actually returns when the bug occurs
    """
    app = create_app()
    
    with app.test_client() as client:
        with app.app_context():
            # Clear data
            db.session.query(CampaignListMember).delete()
            db.session.query(CampaignList).delete()
            db.session.query(Contact).delete()
            db.session.query(CSVImport).delete()
            db.session.commit()
            
            # Create a large CSV that triggers async or causes issues
            csv_content = "first_name,last_name,phone,email\n"
            
            # Create enough existing contacts to trigger "updates" 
            for i in range(1729):
                phone = f"+1555000{i:04d}"
                existing_contact = Contact(
                    first_name=f"Existing{i}",
                    last_name="User",
                    phone=phone,
                    email=f"existing{i}@example.com"
                )
                db.session.add(existing_contact)
                csv_content += f"Updated{i},User,{phone},updated{i}@example.com\n"
            
            # Add new contacts 
            for i in range(59):
                phone = f"+1555999{i:03d}"
                csv_content += f"New{i},User,{phone},new{i}@example.com\n"
                
            db.session.commit()
            
            print(f"Setup: {Contact.query.count()} existing contacts")
            print(f"CSV size: {len(csv_content)} bytes")
            
            # Submit the CSV import
            response = client.post('/campaigns/import-csv', data={
                'csv_file': (io.BytesIO(csv_content.encode()), 'Debug-Test.csv'),
                'list_name': 'Debug-Test-List',
                'enrichment_mode': 'enrich_missing'
            }, content_type='multipart/form-data')
            
            print(f"Response status: {response.status_code}")
            print(f"Response headers: {dict(response.headers)}")
            
            # Check response content
            response_text = response.get_data(as_text=True)
            print(f"Response content type: {response.content_type}")
            print(f"Response length: {len(response_text)}")
            
            # If it's HTML, show key parts
            if 'html' in response.content_type.lower():
                if 'View List' in response_text:
                    print("FOUND: 'View List' button in HTML response")
                    # Find the list_id in the HTML
                    import re
                    list_id_matches = re.findall(r'list[_-]?id["\']?\s*[:=]\s*["\']?(\d+)', response_text, re.IGNORECASE)
                    if list_id_matches:
                        print(f"Found list_id references in HTML: {list_id_matches}")
                    else:
                        print("NO list_id found in HTML despite 'View List' button")
                        
                if 'import' in response_text.lower() and 'progress' in response_text.lower():
                    print("Response appears to be an import progress page")
                    
                # Look for task_id 
                task_id_matches = re.findall(r'task[_-]?id["\']?\s*[:=]\s*["\']?([a-f0-9-]+)', response_text, re.IGNORECASE)
                if task_id_matches:
                    print(f"Found task_id references in HTML: {task_id_matches}")
                    
                # Show key parts of HTML
                if len(response_text) > 500:
                    print("HTML response preview:")
                    print(response_text[:500])
                    print("...")
                    print(response_text[-200:])
                else:
                    print("Full HTML response:")
                    print(response_text)
                    
            else:
                # JSON or other response
                print(f"Non-HTML response: {response_text}")
            
            # Check database state
            final_lists = db.session.query(CampaignList).count()
            print(f"Campaign lists after import: {final_lists}")
            
            # Check CSV imports
            csv_imports = db.session.query(CSVImport).all()
            print(f"CSV imports after import: {len(csv_imports)}")
            for imp in csv_imports:
                print(f"  Import {imp.id}: {imp.filename}, metadata: {imp.import_metadata}")
                
            # This test is just for debugging - we expect the bug
            assert response.status_code in [200, 302], "Response should be OK or redirect"


if __name__ == '__main__':
    test_debug_route_response()