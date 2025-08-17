#!/usr/bin/env python3
"""
Fix conversation last_activity_at timestamps
This script updates conversations to use their actual last activity time
instead of the import/creation time
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from crm_database import db, Conversation, Activity
from datetime import datetime
from sqlalchemy import func

def fix_conversation_timestamps():
    """Update all conversation last_activity_at to match their actual last activity"""
    
    app = create_app()
    with app.app_context():
        # Get all conversations
        conversations = Conversation.query.all()
        
        fixed_count = 0
        no_activity_count = 0
        already_correct = 0
        
        print(f"Checking {len(conversations)} conversations...")
        
        for conv in conversations:
            # Get the actual most recent activity
            last_activity = db.session.query(Activity).filter(
                Activity.conversation_id == conv.id
            ).order_by(Activity.created_at.desc()).first()
            
            if last_activity:
                # Check if the timestamps match (within 1 second tolerance)
                if conv.last_activity_at:
                    time_diff = abs((conv.last_activity_at - last_activity.created_at).total_seconds())
                    if time_diff > 1:  # More than 1 second difference
                        print(f"Fixing conversation {conv.id}: {conv.last_activity_at} -> {last_activity.created_at}")
                        conv.last_activity_at = last_activity.created_at
                        fixed_count += 1
                    else:
                        already_correct += 1
                else:
                    # No last_activity_at set
                    print(f"Setting conversation {conv.id} last_activity_at to {last_activity.created_at}")
                    conv.last_activity_at = last_activity.created_at
                    fixed_count += 1
            else:
                # No activities found
                if conv.last_activity_at:
                    print(f"Conversation {conv.id} has no activities but last_activity_at is set to {conv.last_activity_at}")
                    # You might want to set this to None or leave it
                    # For now, we'll leave it as is
                no_activity_count += 1
        
        # Commit all changes
        if fixed_count > 0:
            db.session.commit()
            print(f"\n✅ Fixed {fixed_count} conversations")
        
        print(f"📊 Summary:")
        print(f"  - Fixed: {fixed_count}")
        print(f"  - Already correct: {already_correct}")
        print(f"  - No activities: {no_activity_count}")
        print(f"  - Total: {len(conversations)}")

if __name__ == "__main__":
    fix_conversation_timestamps()