#!/usr/bin/env python3
"""
Fix media_urls format in existing activities.
Converts from [{'url': '...', 'type': '...'}] to ['...']
"""

from crm_database import db, Activity
from app import create_app
import json

def fix_media_urls():
    """Convert media_urls from dict format to string array format"""
    app = create_app()
    
    with app.app_context():
        # Find all activities with media_urls
        activities = Activity.query.filter(Activity.media_urls.isnot(None)).all()
        
        fixed_count = 0
        for activity in activities:
            if activity.media_urls and isinstance(activity.media_urls, list):
                # Check if any item is a dict
                needs_fix = any(isinstance(item, dict) for item in activity.media_urls)
                
                if needs_fix:
                    # Extract URLs from dict objects
                    fixed_urls = []
                    for item in activity.media_urls:
                        if isinstance(item, dict) and 'url' in item:
                            fixed_urls.append(item['url'])
                        elif isinstance(item, str):
                            fixed_urls.append(item)
                    
                    activity.media_urls = fixed_urls
                    fixed_count += 1
                    print(f"Fixed activity {activity.id}: {len(fixed_urls)} media URLs")
        
        if fixed_count > 0:
            db.session.commit()
            print(f"\nFixed {fixed_count} activities with media attachments")
        else:
            print("No activities needed fixing")

if __name__ == "__main__":
    fix_media_urls()