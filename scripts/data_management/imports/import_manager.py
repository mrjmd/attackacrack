#!/usr/bin/env python3
"""
OpenPhone Import Manager
Safe management of large-scale OpenPhone data imports with resume capability
"""

import sys
import os
from datetime import datetime
from safe_dry_run_import import run_safe_dry_run
from enhanced_openphone_import import run_enhanced_import

def print_banner():
    print("="*80)
    print("OPENPHONE IMPORT MANAGER")
    print("Safe management of large-scale data imports")
    print("="*80)

def print_menu():
    print("\nAvailable Actions:")
    print("1. 🧪 Safe Dry Run (10 conversations) - NO DATABASE CHANGES")
    print("2. 🧪 Extended Dry Run (100 conversations) - NO DATABASE CHANGES") 
    print("3. 📊 Import Small Batch (100 conversations) - WRITES TO DATABASE")
    print("4. 📊 Import Medium Batch (500 conversations) - WRITES TO DATABASE")
    print("5. 🚀 Full Import (~7000 conversations) - WRITES TO DATABASE")
    print("6. 🔄 Resume Import from specific conversation ID")
    print("7. 📈 Check current database status")
    print("8. ❌ Exit")

def check_database_status():
    """Check current state of database"""
    print("\n--- Checking Database Status ---")
    
    try:
        from app import create_app
        from extensions import db
        from crm_database import Contact, Conversation, Activity, MediaAttachment
        
        app = create_app()
        with app.app_context():
            contacts_count = db.session.query(Contact).count()
            conversations_count = db.session.query(Conversation).count()
            activities_count = db.session.query(Activity).count()
            media_count = db.session.query(MediaAttachment).count()
            
            print(f"📊 Current Database State:")
            print(f"  Contacts: {contacts_count}")
            print(f"  Conversations: {conversations_count}")
            print(f"  Activities: {activities_count}")
            print(f"  Media Attachments: {media_count}")
            
            if conversations_count > 0:
                # Show most recent conversation
                recent_conv = db.session.query(Conversation).order_by(
                    Conversation.last_activity_at.desc()
                ).first()
                
                if recent_conv:
                    contact_name = f"{recent_conv.contact.first_name} {recent_conv.contact.last_name}"
                    print(f"  Most Recent: {contact_name} at {recent_conv.last_activity_at}")
                    print(f"  OpenPhone ID: {recent_conv.openphone_id}")
            
            return True
            
    except Exception as e:
        print(f"❌ Error checking database: {e}")
        return False

def confirm_action(action_description: str) -> bool:
    """Get user confirmation for potentially destructive actions"""
    print(f"\n⚠️  About to: {action_description}")
    response = input("Are you sure? Type 'yes' to continue: ").strip().lower()
    return response == 'yes'

def main():
    print_banner()
    
    while True:
        print_menu()
        
        try:
            choice = input("\nSelect an action (1-8): ").strip()
            
            if choice == '1':  # Safe dry run (10)
                print("\n🧪 Running Safe Dry Run (10 conversations)...")
                success = run_safe_dry_run(conversation_limit=10)
                if success:
                    print("✅ Dry run completed successfully!")
                else:
                    print("❌ Dry run found issues!")
                
            elif choice == '2':  # Extended dry run (100)
                print("\n🧪 Running Extended Dry Run (100 conversations)...")
                success = run_safe_dry_run(conversation_limit=100)
                if success:
                    print("✅ Extended dry run completed successfully!")
                else:
                    print("❌ Extended dry run found issues!")
                    
            elif choice == '3':  # Small batch import (100)
                if confirm_action("Import 100 conversations to DATABASE"):
                    print("\n📊 Starting Small Batch Import (100 conversations)...")
                    print("⏰ Estimated time: 5-10 minutes")
                    run_enhanced_import(dry_run_limit=100)
                    print("✅ Small batch import completed!")
                    
            elif choice == '4':  # Medium batch import (500)
                if confirm_action("Import 500 conversations to DATABASE"):
                    print("\n📊 Starting Medium Batch Import (500 conversations)...")
                    print("⏰ Estimated time: 20-40 minutes")
                    run_enhanced_import(dry_run_limit=500)
                    print("✅ Medium batch import completed!")
                    
            elif choice == '5':  # Full import
                if confirm_action("Import ALL ~7000 conversations to DATABASE"):
                    print("\n🚀 Starting Full Import (~7000 conversations)...")
                    print("⏰ Estimated time: 2-4 hours")
                    print("💡 This will run with periodic checkpoints every 10 conversations")
                    run_enhanced_import()
                    print("✅ Full import completed!")
                    
            elif choice == '6':  # Resume import
                conversation_id = input("Enter conversation ID to resume from: ").strip()
                if conversation_id:
                    if confirm_action(f"Resume import from conversation {conversation_id}"):
                        print(f"\n🔄 Resuming import from conversation {conversation_id}...")
                        run_enhanced_import(start_from_conversation=conversation_id)
                        print("✅ Resume import completed!")
                else:
                    print("❌ Invalid conversation ID")
                    
            elif choice == '7':  # Check database status
                check_database_status()
                
            elif choice == '8':  # Exit
                print("\n👋 Goodbye!")
                break
                
            else:
                print("❌ Invalid choice. Please select 1-8.")
                
        except KeyboardInterrupt:
            print("\n\n⚠️  Import interrupted by user")
            print("💡 If import was in progress, you can resume using option 6")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}")
            print("Please try again or check your configuration.")

def show_usage():
    """Show command line usage"""
    print("OpenPhone Import Manager")
    print("\nUsage:")
    print("  python import_manager.py                 # Interactive mode")
    print("  python import_manager.py dry-run         # Quick dry run")
    print("  python import_manager.py dry-run-100     # Extended dry run") 
    print("  python import_manager.py import-100      # Import 100 conversations")
    print("  python import_manager.py status          # Check database status")

if __name__ == '__main__':
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        
        if command == 'dry-run':
            print("🧪 Running Safe Dry Run (10 conversations)...")
            success = run_safe_dry_run(conversation_limit=10)
            sys.exit(0 if success else 1)
            
        elif command == 'dry-run-100':
            print("🧪 Running Extended Dry Run (100 conversations)...")
            success = run_safe_dry_run(conversation_limit=100)
            sys.exit(0 if success else 1)
            
        elif command == 'import-100':
            print("📊 Starting Small Batch Import (100 conversations)...")
            run_enhanced_import(dry_run_limit=100)
            sys.exit(0)
            
        elif command == 'status':
            success = check_database_status()
            sys.exit(0 if success else 1)
            
        elif command in ['help', '--help', '-h']:
            show_usage()
            sys.exit(0)
            
        else:
            print(f"❌ Unknown command: {command}")
            show_usage()
            sys.exit(1)
    else:
        main()