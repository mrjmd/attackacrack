#!/usr/bin/env python3
"""
OpenPhone Import Manager
Safe management of large-scale OpenPhone data imports with resume capability
"""


import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
from scripts.script_logger import get_logger

logger = get_logger(__name__)

import sys
import os
from datetime import datetime
from safe_dry_run_import import run_safe_dry_run
from enhanced_openphone_import import run_enhanced_import

def print_banner():
    logger.info("="*80)
    logger.info("OPENPHONE IMPORT MANAGER")
    logger.info("Safe management of large-scale data imports")
    logger.info("="*80)

def print_menu():
    logger.info("\nAvailable Actions:")
    logger.info("1. 🧪 Safe Dry Run (10 conversations) - NO DATABASE CHANGES")
    logger.info("2. 🧪 Extended Dry Run (100 conversations) - NO DATABASE CHANGES") 
    logger.info("3. 📊 Import Small Batch (100 conversations) - WRITES TO DATABASE")
    logger.info("4. 📊 Import Medium Batch (500 conversations) - WRITES TO DATABASE")
    logger.info("5. 🚀 Full Import (~7000 conversations) - WRITES TO DATABASE")
    logger.info("6. 🔄 Resume Import from specific conversation ID")
    logger.info("7. 📈 Check current database status")
    logger.info("8. ❌ Exit")

def check_database_status():
    """Check current state of database"""
    logger.info("\n--- Checking Database Status ---")
    
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
            
            logger.info(f"📊 Current Database State:")
            logger.info(f"  Contacts: {contacts_count}")
            logger.info(f"  Conversations: {conversations_count}")
            logger.info(f"  Activities: {activities_count}")
            logger.info(f"  Media Attachments: {media_count}")
            
            if conversations_count > 0:
                # Show most recent conversation
                recent_conv = db.session.query(Conversation).order_by(
                    Conversation.last_activity_at.desc()
                ).first()
                
                if recent_conv:
                    contact_name = f"{recent_conv.contact.first_name} {recent_conv.contact.last_name}"
                    logger.info(f"  Most Recent: {contact_name} at {recent_conv.last_activity_at}")
                    logger.info(f"  OpenPhone ID: {recent_conv.openphone_id}")
            
            return True
            
    except Exception as e:
        logger.info(f"❌ Error checking database: {e}")
        return False

def confirm_action(action_description: str) -> bool:
    """Get user confirmation for potentially destructive actions"""
    logger.info(f"\n⚠️  About to: {action_description}")
    response = input("Are you sure? Type 'yes' to continue: ").strip().lower()
    return response == 'yes'

def main():
    print_banner()
    
    while True:
        print_menu()
        
        try:
            choice = input("\nSelect an action (1-8): ").strip()
            
            if choice == '1':  # Safe dry run (10)
                logger.info("\n🧪 Running Safe Dry Run (10 conversations)...")
                success = run_safe_dry_run(conversation_limit=10)
                if success:
                    logger.info("✅ Dry run completed successfully!")
                else:
                    logger.info("❌ Dry run found issues!")
                
            elif choice == '2':  # Extended dry run (100)
                logger.info("\n🧪 Running Extended Dry Run (100 conversations)...")
                success = run_safe_dry_run(conversation_limit=100)
                if success:
                    logger.info("✅ Extended dry run completed successfully!")
                else:
                    logger.info("❌ Extended dry run found issues!")
                    
            elif choice == '3':  # Small batch import (100)
                if confirm_action("Import 100 conversations to DATABASE"):
                    logger.info("\n📊 Starting Small Batch Import (100 conversations)...")
                    logger.info("⏰ Estimated time: 5-10 minutes")
                    run_enhanced_import(dry_run_limit=100)
                    logger.info("✅ Small batch import completed!")
                    
            elif choice == '4':  # Medium batch import (500)
                if confirm_action("Import 500 conversations to DATABASE"):
                    logger.info("\n📊 Starting Medium Batch Import (500 conversations)...")
                    logger.info("⏰ Estimated time: 20-40 minutes")
                    run_enhanced_import(dry_run_limit=500)
                    logger.info("✅ Medium batch import completed!")
                    
            elif choice == '5':  # Full import
                if confirm_action("Import ALL ~7000 conversations to DATABASE"):
                    logger.info("\n🚀 Starting Full Import (~7000 conversations)...")
                    logger.info("⏰ Estimated time: 2-4 hours")
                    logger.info("💡 This will run with periodic checkpoints every 10 conversations")
                    run_enhanced_import()
                    logger.info("✅ Full import completed!")
                    
            elif choice == '6':  # Resume import
                conversation_id = input("Enter conversation ID to resume from: ").strip()
                if conversation_id:
                    if confirm_action(f"Resume import from conversation {conversation_id}"):
                        logger.info(f"\n🔄 Resuming import from conversation {conversation_id}...")
                        run_enhanced_import(start_from_conversation=conversation_id)
                        logger.info("✅ Resume import completed!")
                else:
                    logger.info("❌ Invalid conversation ID")
                    
            elif choice == '7':  # Check database status
                check_database_status()
                
            elif choice == '8':  # Exit
                logger.info("\n👋 Goodbye!")
                break
                
            else:
                logger.info("❌ Invalid choice. Please select 1-8.")
                
        except KeyboardInterrupt:
            logger.info("\n\n⚠️  Import interrupted by user")
            logger.info("💡 If import was in progress, you can resume using option 6")
            break
        except Exception as e:
            logger.info(f"\n❌ Error: {e}")
            logger.info("Please try again or check your configuration.")

def show_usage():
    """Show command line usage"""
    logger.info("OpenPhone Import Manager")
    logger.info("\nUsage:")
    logger.info("  python import_manager.py                 # Interactive mode")
    logger.info("  python import_manager.py dry-run         # Quick dry run")
    logger.info("  python import_manager.py dry-run-100     # Extended dry run") 
    logger.info("  python import_manager.py import-100      # Import 100 conversations")
    logger.info("  python import_manager.py status          # Check database status")

if __name__ == '__main__':
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        
        if command == 'dry-run':
            logger.info("🧪 Running Safe Dry Run (10 conversations)...")
            success = run_safe_dry_run(conversation_limit=10)
            sys.exit(0 if success else 1)
            
        elif command == 'dry-run-100':
            logger.info("🧪 Running Extended Dry Run (100 conversations)...")
            success = run_safe_dry_run(conversation_limit=100)
            sys.exit(0 if success else 1)
            
        elif command == 'import-100':
            logger.info("📊 Starting Small Batch Import (100 conversations)...")
            run_enhanced_import(dry_run_limit=100)
            sys.exit(0)
            
        elif command == 'status':
            success = check_database_status()
            sys.exit(0 if success else 1)
            
        elif command in ['help', '--help', '-h']:
            show_usage()
            sys.exit(0)
            
        else:
            logger.info(f"❌ Unknown command: {command}")
            show_usage()
            sys.exit(1)
    else:
        main()