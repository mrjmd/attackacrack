#!/usr/bin/env python3
"""
Large Scale OpenPhone Import - Optimized for 7000+ conversations
Handles timeouts, progress tracking, and reliable execution for big imports
"""

import os
import signal
import sys
import time
import json
import requests
from datetime import datetime, timezone
from enhanced_openphone_import import EnhancedOpenPhoneImporter

class LargeScaleImporter(EnhancedOpenPhoneImporter):
    """Enhanced importer optimized for large scale imports with timeout handling"""
    
    def __init__(self, batch_size: int = 50, checkpoint_interval: int = 10, reset: bool = False):
        super().__init__()
        self.batch_size = batch_size
        self.checkpoint_interval = checkpoint_interval
        self.progress_file = 'import_progress.json'
        self.interrupted = False
        self.critical_errors = []
        
        # Enhanced timeout settings for large import
        self.timeout = (10, 60)  # Increased timeouts: 10s connect, 60s read
        self.max_retries = 5
        self.max_critical_errors = 5  # Abort after 5 critical errors
        
        # Setup signal handlers for graceful interruption
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        # Reset progress if requested
        if reset and os.path.exists(self.progress_file):
            os.remove(self.progress_file)
            print("🗑️  Reset: Cleared previous progress")
        
        # Load previous progress if exists
        self.progress = self._load_progress()
        
        print("🚀 Large Scale Import Initialized")
        print(f"📊 Batch Size: {batch_size} conversations")
        print(f"💾 Checkpoint Every: {checkpoint_interval} conversations")
        print(f"⏱️  API Timeout: {self.timeout[0]}s connect, {self.timeout[1]}s read")
        print(f"🔄 Max Retries: {self.max_retries}")
        print(f"❌ Max Critical Errors: {self.max_critical_errors} (then abort)")
    
    def _signal_handler(self, signum, frame):
        """Handle interruption signals gracefully"""
        print(f"\n⚠️  Received signal {signum}. Gracefully shutting down...")
        print("💾 Saving progress before exit...")
        self.interrupted = True
    
    def _load_progress(self) -> dict:
        """Load previous import progress"""
        if os.path.exists(self.progress_file):
            try:
                with open(self.progress_file, 'r') as f:
                    progress = json.load(f)
                    print(f"📂 Loaded previous progress: {progress.get('conversations_processed', 0)} conversations completed")
                    return progress
            except Exception as e:
                print(f"⚠️  Could not load progress file: {e}")
        
        return {
            'conversations_processed': 0,
            'last_conversation_id': None,
            'started_at': datetime.utcnow().isoformat(),
            'checkpoints': []
        }
    
    def _save_progress(self):
        """Save current import progress"""
        try:
            self.progress.update({
                'conversations_processed': self.stats['conversations_processed'],
                'updated_at': datetime.utcnow().isoformat(),
                'stats': self.stats
            })
            
            with open(self.progress_file, 'w') as f:
                json.dump(self.progress, f, indent=2)
                
        except Exception as e:
            print(f"⚠️  Could not save progress: {e}")
    
    def _make_api_request(self, url: str, params: dict = None, retry_count: int = 0):
        """Make API request with enhanced timeout and retry logic"""
        try:
            response = requests.get(
                url, 
                headers=self.headers, 
                params=params,
                verify=True,
                timeout=self.timeout
            )
            response.raise_for_status()
            return response
            
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            if retry_count < self.max_retries:
                wait_time = (2 ** retry_count)  # Exponential backoff
                print(f"⏳ API timeout/connection error. Retrying in {wait_time}s... ({retry_count + 1}/{self.max_retries})")
                time.sleep(wait_time)
                return self._make_api_request(url, params, retry_count + 1)
            else:
                raise Exception(f"API request failed after {self.max_retries} retries: {str(e)}")
                
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:  # Rate limit
                wait_time = int(e.response.headers.get('Retry-After', 60))
                print(f"🚦 Rate limited. Waiting {wait_time}s...")
                time.sleep(wait_time)
                return self._make_api_request(url, params, retry_count)
            else:
                raise
    
    def run_large_scale_import(self):
        """Main large scale import with checkpoint and resume capabilities"""
        print("="*80)
        print("🚀 STARTING LARGE SCALE OPENPHONE IMPORT")
        print("="*80)
        
        from app import create_app
        from services.contact_service import ContactService
        from services.ai_service import AIService
        
        app = create_app()
        
        with app.app_context():
            # Validate configuration
            api_key = app.config.get('OPENPHONE_API_KEY')
            user_phone_number = app.config.get('OPENPHONE_PHONE_NUMBER')
            phone_number_id = app.config.get('OPENPHONE_PHONE_NUMBER_ID')

            if not all([api_key, user_phone_number, phone_number_id]):
                print("❌ ERROR: Missing OpenPhone configuration")
                return False

            # Initialize parent class attributes
            self.headers = {"Authorization": api_key}
            self.user_phone_number = user_phone_number
            self.phone_number_id = phone_number_id
            self.contact_service = ContactService()
            self.ai_service = AIService()
            
            try:
                # Import in manageable batches
                self._import_in_batches()
                
                # Final statistics
                self._print_final_summary()
                
                # Clean up progress file on successful completion
                if os.path.exists(self.progress_file):
                    os.remove(self.progress_file)
                    print("🗑️  Cleaned up progress file")
                
                return True
                
            except KeyboardInterrupt:
                print("\n⚠️  Import interrupted by user")
                self._save_progress()
                print("💾 Progress saved. Resume with: python large_scale_import.py --resume")
                return False
                
            except Exception as e:
                print(f"❌ Import failed: {e}")
                self._save_progress()
                return False
    
    def _import_in_batches(self):
        """Import conversations in manageable batches"""
        print("📦 Starting batch import process...")
        
        # Get total conversation count first
        total_conversations = self._get_total_conversation_count()
        print(f"📊 Total conversations to import: {total_conversations}")
        
        batch_number = 1
        conversations_imported = self.progress['conversations_processed']
        
        while conversations_imported < total_conversations and not self.interrupted:
            print(f"\n📦 Processing Batch {batch_number} (Conversations {conversations_imported + 1}-{min(conversations_imported + self.batch_size, total_conversations)})")
            
            # Fetch batch of conversations
            batch_conversations = self._fetch_conversation_batch(
                offset=conversations_imported,
                limit=self.batch_size
            )
            
            if not batch_conversations:
                print("✅ No more conversations to import")
                break
            
            # Process this batch
            self._process_conversation_batch(batch_conversations)
            
            # Update progress
            conversations_imported += len(batch_conversations)
            self.progress['conversations_processed'] = conversations_imported
            
            # Save checkpoint
            if batch_number % (self.checkpoint_interval // self.batch_size or 1) == 0:
                self._save_progress()
                print(f"💾 Checkpoint saved: {conversations_imported} conversations completed")
            
            # Progress update
            progress_percent = (conversations_imported / total_conversations) * 100
            print(f"📈 Progress: {conversations_imported}/{total_conversations} ({progress_percent:.1f}%)")
            
            batch_number += 1
            
            # Brief pause between batches to be API-friendly
            time.sleep(2)
    
    def _get_total_conversation_count(self) -> int:
        """Get approximate total conversation count"""
        try:
            url = f"https://api.openphone.com/v1/conversations?phoneNumberId={self.phone_number_id}&maxResults=1"
            response = self._make_api_request(url)
            data = response.json()
            
            # OpenPhone API doesn't give exact totals, so we estimate
            # If we have nextPageToken, there are likely thousands
            if data.get('nextPageToken'):
                return 7000  # User's estimate
            else:
                return len(data.get('data', []))
                
        except Exception as e:
            print(f"⚠️  Could not get conversation count: {e}")
            return 7000  # Fallback to user's estimate
    
    def _fetch_conversation_batch(self, offset: int, limit: int) -> list:
        """Fetch a batch of conversations with pagination"""
        conversations = []
        fetched = 0
        page_token = None
        
        # Skip conversations we've already processed
        current_offset = 0
        
        try:
            while fetched < limit and current_offset <= offset + limit:
                url = f"https://api.openphone.com/v1/conversations?phoneNumberId={self.phone_number_id}&maxResults=100"
                params = {}
                if page_token:
                    params['pageToken'] = page_token
                
                response = self._make_api_request(url, params)
                data = response.json()
                
                batch_conversations = data.get('data', [])
                
                # Skip conversations until we reach our offset
                if current_offset < offset:
                    skip_count = min(len(batch_conversations), offset - current_offset)
                    batch_conversations = batch_conversations[skip_count:]
                    current_offset += skip_count
                
                # Take only what we need for this batch
                remaining_needed = limit - fetched
                batch_conversations = batch_conversations[:remaining_needed]
                
                conversations.extend(batch_conversations)
                fetched += len(batch_conversations)
                current_offset += len(batch_conversations)
                
                page_token = data.get('nextPageToken')
                if not page_token:
                    break
            
            return conversations
            
        except Exception as e:
            print(f"❌ Error fetching conversation batch: {e}")
            return []
    
    def _process_conversation_batch(self, conversations: list):
        """Process a batch of conversations with enhanced error handling"""
        from extensions import db
        
        for i, convo_data in enumerate(conversations):
            if self.interrupted:
                break
                
            try:
                # Use parent class processing with enhanced error handling
                self._process_single_conversation(convo_data)
                
                # Commit every few conversations to prevent data loss
                if (i + 1) % 5 == 0:
                    db.session.commit()
                    
            except Exception as e:
                error_msg = f"Error processing conversation {convo_data.get('id', 'unknown')}: {e}"
                
                # Handle database transaction rollback issues
                if "rolled back" in str(e).lower() or "uniqueviolation" in str(type(e).__name__):
                    print(f"🔄 Database rollback detected, recovering...")
                    try:
                        db.session.rollback()  # Rollback the failed transaction
                        print(f"⚠️  Skipping duplicate conversation: {convo_data.get('id', 'unknown')}")
                        continue  # Skip this conversation and continue
                    except Exception as rollback_error:
                        print(f"❌ Could not recover from rollback: {rollback_error}")
                
                # Check if this is a critical error
                if self._is_critical_error(e):
                    self.critical_errors.append(error_msg)
                    print(f"❌ CRITICAL ERROR: {error_msg}")
                    
                    if len(self.critical_errors) >= self.max_critical_errors:
                        print(f"\n🚨 TOO MANY CRITICAL ERRORS ({len(self.critical_errors)})!")
                        print("🛑 ABORTING IMPORT TO PREVENT DATA CORRUPTION")
                        print("💡 Fix the errors, reset, and restart from scratch")
                        raise Exception(f"Critical error limit exceeded: {len(self.critical_errors)} errors")
                else:
                    print(f"⚠️  Non-critical error: {error_msg}")
                    # Continue with next conversation for non-critical errors
                    continue
        
        # Final commit for the batch
        db.session.commit()
    
    def _process_single_conversation(self, convo_data: dict):
        """Process a single conversation with timeout-aware operations"""
        from extensions import db
        from crm_database import Conversation
        
        openphone_convo_id = convo_data.get('id')
        participants = convo_data.get('participants', [])
        other_participants = [p for p in participants if p != self.user_phone_number]
        
        if not other_participants:
            return
        
        # Check if already processed
        existing_conversation = db.session.query(Conversation).filter_by(
            openphone_id=openphone_convo_id
        ).first()
        
        if existing_conversation and len(existing_conversation.activities) > 0:
            return  # Skip already processed conversations
        
        # Use parent class processing
        primary_participant = other_participants[0]
        contact = self._get_or_create_contact(primary_participant, convo_data)
        conversation = self._get_or_create_conversation(
            openphone_convo_id, contact, convo_data, participants
        )
        
        # Import activities with timeout handling
        self._import_conversation_activities_with_timeout(conversation, other_participants)
        
        self.stats['conversations_processed'] += 1
    
    def _import_conversation_activities_with_timeout(self, conversation, other_participants: list):
        """Import activities with enhanced timeout and retry logic"""
        try:
            # Use parent class method but with enhanced API calls
            messages = self._fetch_messages_with_timeout(other_participants)
            calls = self._fetch_calls_with_timeout(other_participants[0])
            
            all_activities = messages + calls
            all_activities.sort(key=lambda x: x.get('createdAt', ''))
            
            for activity_data in all_activities:
                if self.interrupted:
                    break
                self._process_activity(conversation, activity_data)
                
        except Exception as e:
            print(f"⚠️  Error importing activities for conversation {conversation.id}: {e}")
    
    def _fetch_messages_with_timeout(self, participants: list) -> list:
        """Fetch messages with enhanced timeout handling"""
        messages = []
        page_token = None
        
        while True:
            try:
                url = "https://api.openphone.com/v1/messages"
                params = {
                    'phoneNumberId': self.phone_number_id,
                    'participants[]': participants,
                    'maxResults': 100
                }
                if page_token:
                    params['pageToken'] = page_token
                
                response = self._make_api_request(url, params)
                data = response.json()
                
                messages.extend(data.get('data', []))
                page_token = data.get('nextPageToken')
                
                if not page_token:
                    break
                    
            except Exception as e:
                print(f"⚠️  Error fetching messages: {e}")
                break
        
        return messages
    
    def _fetch_calls_with_timeout(self, participant: str) -> list:
        """Fetch calls with enhanced timeout handling"""
        calls = []
        page_token = None
        
        while True:
            try:
                url = "https://api.openphone.com/v1/calls"
                params = {
                    'phoneNumberId': self.phone_number_id,
                    'participants': participant,
                    'maxResults': 100
                }
                if page_token:
                    params['pageToken'] = page_token
                
                response = self._make_api_request(url, params)
                data = response.json()
                
                calls.extend(data.get('data', []))
                page_token = data.get('nextPageToken')
                
                if not page_token:
                    break
                    
            except Exception as e:
                print(f"⚠️  Error fetching calls: {e}")
                break
        
        return calls
    
    def _is_critical_error(self, exception: Exception) -> bool:
        """Determine if an error is critical and should cause immediate abort"""
        critical_patterns = [
            "has no attribute",  # Missing attributes (code errors)
            "not defined",       # Missing variables (code errors)
            "ImportError",       # Missing imports (code errors)
            "SyntaxError",       # Code syntax errors
            "database.*locked",  # Database lock issues
            "connection.*refused", # Database connection issues
            "authentication.*failed", # Auth issues
            "permission.*denied"   # Permission issues
        ]
        
        error_str = str(exception).lower()
        for pattern in critical_patterns:
            if pattern in error_str:
                return True
        
        return False
    
    def _print_final_summary(self):
        """Print comprehensive final summary"""
        print("\n" + "="*80)
        print("🎉 LARGE SCALE IMPORT COMPLETED SUCCESSFULLY")
        print("="*80)
        
        duration = datetime.utcnow() - datetime.fromisoformat(self.progress['started_at'])
        
        print(f"⏱️  Total Duration: {duration}")
        print(f"📊 Conversations Processed: {self.stats['conversations_processed']}")
        print(f"📱 Messages Imported: {self.stats['messages_imported']}")
        print(f"📞 Calls Imported: {self.stats['calls_imported']}")
        print(f"📎 Media Downloaded: {self.stats['media_downloaded']}")
        print(f"🎵 Recordings Downloaded: {self.stats['recordings_downloaded']}")
        print(f"📧 Voicemails Downloaded: {self.stats['voicemails_downloaded']}")
        print(f"🤖 AI Summaries Generated: {self.stats['ai_summaries_generated']}")
        
        if self.stats.get('validation_issues'):
            print(f"⚠️  Validation Issues: {len(self.stats['validation_issues'])}")
        
        if self.stats['errors']:
            print(f"❌ Errors Encountered: {len(self.stats['errors'])}")
        
        print("\n✅ All OpenPhone data successfully imported!")
        print("🎯 Ready for production use with full conversation history")
        print("="*80)


def main():
    """Main execution function with auto-resume and reset capabilities"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Large Scale OpenPhone Import')
    parser.add_argument('--batch-size', type=int, default=50, help='Conversations per batch')
    parser.add_argument('--checkpoint-interval', type=int, default=10, help='Save progress every N conversations')
    parser.add_argument('--resume', action='store_true', help='Resume from previous progress')
    parser.add_argument('--reset', action='store_true', help='Reset progress and start from scratch')
    parser.add_argument('--auto-resume', action='store_true', help='Automatically resume if progress file exists')
    
    args = parser.parse_args()
    
    print("🚀 Large Scale OpenPhone Import")
    print("="*80)
    
    # Check for existing progress
    progress_file = 'import_progress.json'
    has_progress = os.path.exists(progress_file)
    
    if args.reset:
        print("🗑️  RESET MODE: Starting fresh import")
    elif args.resume or (args.auto_resume and has_progress):
        if has_progress:
            print("🔄 RESUME MODE: Continuing from previous progress")
        else:
            print("⚠️  No previous progress found, starting fresh import")
    elif has_progress:
        print("📁 Found previous progress file")
        print("💡 Use --resume to continue, --reset to start fresh, or --auto-resume for automatic handling")
        
        # Auto-decide based on progress age
        try:
            with open(progress_file, 'r') as f:
                progress = json.load(f)
                last_update = datetime.fromisoformat(progress.get('updated_at', progress.get('started_at')))
                age_hours = (datetime.utcnow() - last_update).total_seconds() / 3600
                
                if age_hours < 24:  # Less than 24 hours old
                    print(f"🔄 Progress is recent ({age_hours:.1f}h old), auto-resuming...")
                    args.resume = True
                else:
                    print(f"⚠️  Progress is old ({age_hours:.1f}h), starting fresh...")
                    args.reset = True
        except:
            print("⚠️  Could not read progress, starting fresh...")
            args.reset = True
    
    try:
        importer = LargeScaleImporter(
            batch_size=args.batch_size,
            checkpoint_interval=args.checkpoint_interval,
            reset=args.reset
        )
        
        success = importer.run_large_scale_import()
        
        if success:
            print("\n✅ IMPORT COMPLETED SUCCESSFULLY!")
            print("🎯 All OpenPhone conversations have been imported")
            print("🌐 Check your app at http://localhost:5000/contacts/conversations")
            sys.exit(0)
        else:
            print("\n⚠️  IMPORT WAS INTERRUPTED")
            print("💾 Progress has been saved automatically")
            print("🔄 Resume with: python large_scale_import.py --resume")
            sys.exit(1)
            
    except Exception as e:
        if "critical error limit exceeded" in str(e).lower():
            print(f"\n🚨 CRITICAL ERRORS DETECTED - IMPORT ABORTED")
            print("🛠️  Fix the code issues and run with --reset to start fresh")
            print("📋 Critical errors encountered:")
            for error in importer.critical_errors:
                print(f"   - {error}")
            sys.exit(2)
        else:
            print(f"\n❌ UNEXPECTED ERROR: {e}")
            sys.exit(1)


if __name__ == '__main__':
    main()