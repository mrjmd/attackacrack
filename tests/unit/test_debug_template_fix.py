"""
Debug test to check if the template is receiving list_id properly
"""

import pytest
import io
from app import create_app  
from crm_database import CampaignList, CSVImport, Contact
from extensions import db


def test_debug_template_list_id():
    """
    Debug if the template is receiving the list_id parameter
    """
    app = create_app()
    
    with app.test_client() as client:
        with app.app_context():
            # Clear data
            db.session.query(CampaignList).delete()
            db.session.query(Contact).delete()
            db.session.query(CSVImport).delete()
            db.session.commit()
            
            # Create large CSV that triggers async 
            csv_content = "first_name,last_name,phone,email\n"
            
            # Create existing contacts to trigger async behavior
            for i in range(500):  # Enough to trigger async
                phone = f"+1555000{i:04d}"
                existing_contact = Contact(
                    first_name=f"Existing{i}",
                    last_name="User",
                    phone=phone,
                    email=f"existing{i}@example.com"
                )
                db.session.add(existing_contact)
                csv_content += f"Updated{i},User,{phone},updated{i}@example.com\n"
                
            # Add some new contacts
            for i in range(50):
                phone = f"+1555999{i:03d}"
                csv_content += f"New{i},User,{phone},new{i}@example.com\n"
                
            db.session.commit()
            
            print(f"Setup: {Contact.query.count()} existing contacts")
            print(f"CSV size: {len(csv_content)} bytes")
            
            # Submit the CSV import
            response = client.post('/campaigns/import-csv', data={
                'csv_file': (io.BytesIO(csv_content.encode()), 'Template-Debug.csv'),
                'list_name': 'Template-Debug-List',
                'enrichment_mode': 'enrich_missing'
            }, content_type='multipart/form-data')
            
            print(f"Response status: {response.status_code}")
            
            # Check if list was created
            list_count = db.session.query(CampaignList).count()
            print(f"Lists created: {list_count}")
            
            if list_count > 0:
                created_list = db.session.query(CampaignList).first()
                print(f"Created list: ID={created_list.id}, Name='{created_list.name}'")
                
                # Check HTML for the specific list_id
                response_text = response.get_data(as_text=True)
                
                # Look for the list_id in the href
                list_url = f'/campaigns/lists/{created_list.id}'
                if list_url in response_text:
                    print(f"SUCCESS: Found list URL {list_url} in HTML")
                else:
                    print(f"BUG: List URL {list_url} NOT found in HTML")
                    
                    # Look for any reference to the list_id
                    if str(created_list.id) in response_text:
                        print(f"List ID {created_list.id} is somewhere in HTML")
                    else:
                        print(f"List ID {created_list.id} is NOT anywhere in HTML")
                    
                    # Check if "View List" button exists but has no href
                    if 'View List' in response_text:
                        import re
                        view_list_pattern = r'<a[^>]+id="view-list-btn"[^>]*href="([^"]*)"'
                        matches = re.findall(view_list_pattern, response_text)
                        if matches:
                            print(f"View List button href: {matches[0]}")
                        else:
                            print("View List button found but no href captured")
                            
                            # Look for the whole button tag
                            button_pattern = r'<a[^>]+View List[^<]*</a>'
                            button_matches = re.findall(button_pattern, response_text, re.DOTALL)
                            if button_matches:
                                print(f"View List button HTML: {button_matches[0]}")
                                
                # Also check what variables were passed to the template
                # This would require accessing Flask's template context, which is complex
                # For now, let's check if the progress page gets the right parameters
                
                if response.status_code == 200:
                    # It's a progress page - check for template variables
                    if 'Import Progress' in response_text:
                        print("Confirmed: This is the import progress page")
                        
                        # Check what data is available in JavaScript
                        import re
                        # Look for task_id in JavaScript
                        task_pattern = r'taskId\s*=\s*["\']([^"\']+)["\']'
                        task_matches = re.findall(task_pattern, response_text)
                        if task_matches:
                            print(f"Found task_id in JS: {task_matches[0]}")
                            
                        # Look for any list references
                        list_pattern = r'list[_-]?(?:id|Id)\s*[:=]\s*["\']?(\d+)'
                        list_matches = re.findall(list_pattern, response_text, re.IGNORECASE)
                        if list_matches:
                            print(f"Found list references: {list_matches}")
                        else:
                            print("No list references found in HTML/JS")
            else:
                print("BUG: No lists were created - async fix didn't work")


if __name__ == '__main__':
    test_debug_template_list_id()