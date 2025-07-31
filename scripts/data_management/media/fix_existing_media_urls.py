#!/usr/bin/env python3
"""
Fix media_urls format in existing activities.
Since we can't determine the media type from the URL alone,
we'll need to make HEAD requests to check the Content-Type.
"""

import os
import sys
import requests
from datetime import datetime

# Add the app directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from crm_database import db, Activity
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

def get_media_type(url):
    """Get the media type by making a HEAD request to the URL"""
    try:
        response = requests.head(url, timeout=5, allow_redirects=True)
        content_type = response.headers.get('Content-Type', '')
        return content_type
    except Exception as e:
        print(f"Error checking {url}: {e}")
        # Fallback: assume it's an image if it's from Google Storage
        if 'storage.googleapis.com' in url:
            return 'image/jpeg'
        return 'application/octet-stream'

def fix_media_urls():
    """Convert media_urls from string array to dict array with type info"""
    # Import here to avoid circular imports
    from config import Config
    
    # Get database URL from config
    database_url = Config.SQLALCHEMY_DATABASE_URI
    if not database_url:
        print("No database URL configured")
        return
    
    # Create engine and session
    engine = create_engine(database_url)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        # Find all activities with media_urls
        activities = session.query(Activity).filter(
            Activity.media_urls.isnot(None),
            Activity.media_urls != '[]'
        ).all()
        
        print(f"Found {len(activities)} activities with media attachments")
        
        fixed_count = 0
        for activity in activities:
            if activity.media_urls and isinstance(activity.media_urls, list):
                needs_fix = False
                fixed_urls = []
                
                for item in activity.media_urls:
                    if isinstance(item, str):
                        # This is an old-format URL, needs fixing
                        needs_fix = True
                        media_type = get_media_type(item)
                        fixed_urls.append({
                            'url': item,
                            'type': media_type
                        })
                        print(f"  - {item} -> {media_type}")
                    elif isinstance(item, dict):
                        # Already in new format
                        fixed_urls.append(item)
                
                if needs_fix:
                    activity.media_urls = fixed_urls
                    fixed_count += 1
                    print(f"Fixed activity {activity.id}: {len(fixed_urls)} media items")
        
        if fixed_count > 0:
            session.commit()
            print(f"\nSuccessfully fixed {fixed_count} activities")
        else:
            print("No activities needed fixing")
            
    except Exception as e:
        print(f"Error: {e}")
        session.rollback()
    finally:
        session.close()

if __name__ == "__main__":
    fix_media_urls()