#!/usr/bin/env python3
"""
Cleanup empty conversations
This script identifies and optionally removes conversations that have no activities
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from crm_database import db, Conversation, Activity
from sqlalchemy import func

def cleanup_empty_conversations(delete=False):
    """Find and optionally delete conversations with no activities"""
    
    app = create_app()
    with app.app_context():
        # Find conversations with no activities using a left join
        empty_conversations = db.session.query(Conversation).outerjoin(
            Activity, Activity.conversation_id == Conversation.id
        ).group_by(Conversation.id).having(
            func.count(Activity.id) == 0
        ).all()
        
        print(f"Found {len(empty_conversations)} conversations with no activities:")
        
        for conv in empty_conversations:
            contact_name = "Unknown"
            if conv.contact:
                contact_name = conv.contact.first_name or conv.contact.phone or "No name"
            
            print(f"  - Conversation {conv.id}: {contact_name}")
            print(f"    OpenPhone ID: {conv.openphone_id}")
            print(f"    Last Activity At: {conv.last_activity_at}")
            print(f"    Participants: {conv.participants}")
        
        if delete and empty_conversations:
            response = input(f"\n⚠️  Delete these {len(empty_conversations)} empty conversations? (yes/no): ")
            if response.lower() == 'yes':
                for conv in empty_conversations:
                    db.session.delete(conv)
                db.session.commit()
                print(f"✅ Deleted {len(empty_conversations)} empty conversations")
            else:
                print("❌ Deletion cancelled")
        elif empty_conversations:
            print("\n💡 To delete these conversations, run with --delete flag")
            print("   python scripts/cleanup_empty_conversations.py --delete")

if __name__ == "__main__":
    delete_flag = '--delete' in sys.argv
    cleanup_empty_conversations(delete=delete_flag)