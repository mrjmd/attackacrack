#!/usr/bin/env python3
"""
Enhanced OpenPhone Import Service
Comprehensive data import including all new database models:
- Media attachments (images, documents)
- Call recordings and voicemails 
- AI summaries and transcripts
- Complete conversation history with all participants
"""

import os
import requests
import json
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
from urllib3.exceptions import InsecureRequestWarning
from collections import Counter

# Suppress the InsecureRequestWarning from urllib3
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

# Import what we need from the main application
from app import create_app
from extensions import db
from crm_database import (
    Contact, Conversation, Activity, MediaAttachment, User, PhoneNumber, WebhookEvent
)
from services.contact_service import ContactService
from services.ai_service import AIService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- CONFIGURATION ---
MEDIA_UPLOAD_FOLDER = 'uploads/media'
RECORDINGS_FOLDER = 'uploads/recordings'
VOICEMAILS_FOLDER = 'uploads/voicemails'

class EnhancedOpenPhoneImporter:
    """Enhanced OpenPhone data importer with comprehensive data coverage"""
    
    def __init__(self, dry_run_limit: Optional[int] = None, start_from_conversation: Optional[str] = None):
        self.dry_run_limit = dry_run_limit
        self.start_from_conversation = start_from_conversation  # Resume from specific conversation ID
        self.stats = {
            'conversations_processed': 0,
            'messages_imported': 0,
            'calls_imported': 0,
            'media_downloaded': 0,
            'recordings_downloaded': 0,
            'voicemails_downloaded': 0,
            'ai_summaries_generated': 0,
            'validation_issues': [],
            'errors': []
        }
        
        # Create upload directories
        for folder in [MEDIA_UPLOAD_FOLDER, RECORDINGS_FOLDER, VOICEMAILS_FOLDER]:
            os.makedirs(folder, exist_ok=True)
            logger.info(f"Created/verified directory: {os.path.abspath(folder)}")
    
    def run_comprehensive_import(self):
        """
        Main import method - performs comprehensive OpenPhone data import
        """
        logger.info("--- Starting Enhanced OpenPhone Import ---")
        
        app = create_app()
        
        with app.app_context():
            # Validate configuration
            api_key = app.config.get('OPENPHONE_API_KEY')
            user_phone_number = app.config.get('OPENPHONE_PHONE_NUMBER')
            phone_number_id = app.config.get('OPENPHONE_PHONE_NUMBER_ID')

            if not all([api_key, user_phone_number, phone_number_id]):
                logger.error("ERROR: Missing OpenPhone configuration. Aborting.")
                return

            self.headers = {"Authorization": api_key}
            self.user_phone_number = user_phone_number
            self.phone_number_id = phone_number_id
            self.contact_service = ContactService()
            self.ai_service = AIService()
            
            # Import sequence
            self._import_phone_numbers()
            conversations = self._fetch_all_conversations()
            self._process_conversations(conversations)
            self._generate_ai_content_batch()
            self._validate_import_integrity()
            
            # Print final statistics
            self._print_import_summary()

    def _import_phone_numbers(self):
        """Import OpenPhone phone numbers for reference"""
        logger.info("--- Step 1: Importing Phone Numbers ---")
        
        try:
            # Import phone numbers  
            numbers_url = "https://api.openphone.com/v1/phone-numbers"
            response = requests.get(numbers_url, headers=self.headers, verify=True, timeout=(5, 30))
            if response.status_code == 200:
                numbers_data = response.json().get('data', [])
                for number_data in numbers_data:
                    existing_number = db.session.query(PhoneNumber).filter_by(
                        openphone_id=number_data.get('id')
                    ).first()
                    
                    if not existing_number:
                        new_number = PhoneNumber(
                            openphone_id=number_data.get('id'),
                            phone_number=number_data.get('phoneNumber'),
                            name=number_data.get('name'),
                            is_active=number_data.get('isActive', True)
                        )
                        db.session.add(new_number)
                        logger.info(f"Added phone number: {number_data.get('phoneNumber')}")
            
            db.session.commit()
            logger.info("Phone numbers imported successfully")
            
        except Exception as e:
            logger.error(f"Error importing phone numbers: {e}")
            self.stats['errors'].append(f"Phone numbers import: {str(e)}")

    def _fetch_all_conversations(self) -> List[Dict]:
        """Fetch all conversations with pagination support"""
        logger.info("--- Step 2: Fetching All Conversations ---")
        
        all_conversations = []
        page_token = None
        
        try:
            if self.dry_run_limit:
                logger.info(f"DRY RUN: Fetching only {self.dry_run_limit} conversations")
                url = f"https://api.openphone.com/v1/conversations?phoneNumberId={self.phone_number_id}"
                params = {'maxResults': self.dry_run_limit}
                response = requests.get(url, headers=self.headers, params=params, verify=True)
                response.raise_for_status()
                all_conversations = response.json().get('data', [])
            else:
                logger.info("FULL IMPORT: Fetching all conversations in pages")
                while True:
                    url = f"https://api.openphone.com/v1/conversations?phoneNumberId={self.phone_number_id}"
                    params = {'maxResults': 100}
                    if page_token:
                        params['pageToken'] = page_token
                        
                    response = requests.get(url, headers=self.headers, params=params, verify=True)
                    response.raise_for_status()
                    data = response.json()
                    
                    batch_conversations = data.get('data', [])
                    all_conversations.extend(batch_conversations)
                    
                    page_token = data.get('nextPageToken')
                    logger.info(f"Fetched {len(batch_conversations)} conversations, total: {len(all_conversations)}")
                    
                    if not page_token:
                        break
            
            logger.info(f"Found {len(all_conversations)} conversations to process")
            return all_conversations
            
        except Exception as e:
            logger.error(f"Error fetching conversations: {e}")
            self.stats['errors'].append(f"Conversations fetch: {str(e)}")
            return []

    def _process_conversations(self, conversations: List[Dict]):
        """Process each conversation and import all associated activities"""
        logger.info("--- Step 3: Processing Conversations and Activities ---")
        
        # Filter conversations if resuming from a specific point
        if self.start_from_conversation:
            found_start = False
            filtered_conversations = []
            for convo in conversations:
                if convo.get('id') == self.start_from_conversation:
                    found_start = True
                if found_start:
                    filtered_conversations.append(convo)
            conversations = filtered_conversations
            logger.info(f"Resuming from conversation {self.start_from_conversation}, processing {len(conversations)} conversations")
        
        for i, convo_data in enumerate(conversations):
            try:
                openphone_convo_id = convo_data.get('id')
                participants = convo_data.get('participants', [])
                other_participants = [p for p in participants if p != self.user_phone_number]
                
                if not other_participants:
                    continue

                # Check if conversation already fully processed
                existing_conversation = db.session.query(Conversation).filter_by(
                    openphone_id=openphone_convo_id
                ).first()
                
                if existing_conversation and len(existing_conversation.activities) > 0:
                    logger.info(f"Conversation {i+1}/{len(conversations)} already processed, skipping")
                    continue

                primary_participant = other_participants[0]
                logger.info(f"Processing conversation {i+1}/{len(conversations)} ({openphone_convo_id}) with {primary_participant}")
                
                # Get or create contact
                contact = self._get_or_create_contact(primary_participant, convo_data)
                
                # Get or create conversation record
                conversation = self._get_or_create_conversation(
                    openphone_convo_id, contact, convo_data, participants
                )
                
                # Import all activities for this conversation
                self._import_conversation_activities(conversation, other_participants)
                
                self.stats['conversations_processed'] += 1
                
                # Commit every 10 conversations to prevent loss on failure
                if (i + 1) % 10 == 0:
                    db.session.commit()
                    logger.info(f"Progress checkpoint: {i+1}/{len(conversations)} conversations processed")
                
            except Exception as e:
                logger.error(f"Error processing conversation {i+1} ({openphone_convo_id}): {e}")
                self.stats['errors'].append(f"Conversation {openphone_convo_id}: {str(e)}")
                # Continue with next conversation on error
                continue
        
        db.session.commit()
        logger.info("All conversations processed and committed")

    def _get_or_create_contact(self, phone_number: str, convo_data: Dict) -> Contact:
        """Get existing contact or create new one"""
        contact = self.contact_service.get_contact_by_phone(phone_number)
        if not contact:
            contact_name = convo_data.get('name') or phone_number
            # Split name if it contains space, otherwise use as first name
            if ' ' in contact_name and not contact_name.startswith('+'):
                name_parts = contact_name.split(' ', 1)
                first_name = name_parts[0]
                last_name = name_parts[1]
            else:
                first_name = contact_name
                last_name = "(from OpenPhone)"
                
            contact = self.contact_service.add_contact(
                first_name=first_name, 
                last_name=last_name, 
                phone=phone_number
            )
            logger.info(f"Created new contact: {first_name} {last_name}")
        
        return contact

    def _get_or_create_conversation(self, openphone_id: str, contact: Contact, 
                                  convo_data: Dict, participants: List[str]) -> Conversation:
        """Get existing conversation or create new one"""
        conversation = db.session.query(Conversation).filter_by(
            openphone_id=openphone_id
        ).first()
        
        if not conversation:
            conversation = Conversation(
                openphone_id=openphone_id,
                contact_id=contact.id,
                name=convo_data.get('name'),
                participants=','.join(participants),
                phone_number_id=self.phone_number_id,
                last_activity_type=convo_data.get('lastActivityType'),
                last_activity_id=convo_data.get('lastActivityId')
            )
            db.session.add(conversation)
            db.session.flush()  # Get the ID
            logger.info(f"Created conversation record for {contact.first_name}")
        
        return conversation

    def _import_conversation_activities(self, conversation: Conversation, other_participants: List[str]):
        """Import all messages and calls for a conversation"""
        all_activities = []
        
        # Fetch messages
        messages = self._fetch_messages_for_conversation(other_participants)
        all_activities.extend(messages)
        
        # Fetch calls  
        calls = self._fetch_calls_for_conversation(other_participants[0])  # Primary participant for calls
        all_activities.extend(calls)
        
        # Sort by creation time
        all_activities.sort(key=lambda x: x.get('createdAt', ''))
        
        logger.info(f"Found {len(all_activities)} activities ({len(messages)} messages, {len(calls)} calls)")
        
        # Process each activity
        for activity_data in all_activities:
            self._process_activity(conversation, activity_data)
        
        # Update conversation last activity timestamp
        if all_activities:
            last_activity = all_activities[-1]
            last_timestamp = datetime.fromisoformat(
                last_activity.get('createdAt', '').replace('Z', '')
            ).replace(tzinfo=timezone.utc)
            conversation.last_activity_at = last_timestamp

    def _fetch_messages_for_conversation(self, participants: List[str]) -> List[Dict]:
        """Fetch all messages for conversation participants"""
        messages = []
        page_token = None
        
        try:
            while True:
                url = "https://api.openphone.com/v1/messages"
                params = {
                    'phoneNumberId': self.phone_number_id,
                    'participants[]': participants,
                    'maxResults': 100
                }
                if page_token:
                    params['pageToken'] = page_token
                
                response = requests.get(url, headers=self.headers, params=params, verify=True)
                response.raise_for_status()
                data = response.json()
                
                batch_messages = data.get('data', [])
                messages.extend(batch_messages)
                
                page_token = data.get('nextPageToken')
                if not page_token:
                    break
                    
        except Exception as e:
            logger.error(f"Error fetching messages: {e}")
            self.stats['errors'].append(f"Messages fetch: {str(e)}")
        
        return messages

    def _fetch_calls_for_conversation(self, participant: str) -> List[Dict]:
        """Fetch all calls for a conversation participant"""
        calls = []
        page_token = None
        
        try:
            while True:
                url = "https://api.openphone.com/v1/calls"
                params = {
                    'phoneNumberId': self.phone_number_id,
                    'participants': participant,  # Single participant, not array
                    'maxResults': 100
                }
                if page_token:
                    params['pageToken'] = page_token
                
                response = requests.get(url, headers=self.headers, params=params, verify=True)
                response.raise_for_status()
                data = response.json()
                
                batch_calls = data.get('data', [])
                calls.extend(batch_calls)
                
                page_token = data.get('nextPageToken')
                if not page_token:
                    break
                    
        except Exception as e:
            logger.error(f"Error fetching calls: {e}")
            self.stats['errors'].append(f"Calls fetch: {str(e)}")
        
        return calls

    def _process_activity(self, conversation: Conversation, activity_data: Dict):
        """Process individual activity (message or call) with all enhancements"""
        activity_id = activity_data.get('id')
        
        # Skip if already imported
        existing_activity = db.session.query(Activity).filter_by(
            openphone_id=activity_id
        ).first()
        
        if existing_activity:
            return
        
        try:
            # Parse timestamp
            created_at = datetime.fromisoformat(
                activity_data.get('createdAt', '').replace('Z', '')
            ).replace(tzinfo=timezone.utc)
            
            # Determine activity type
            activity_type = activity_data.get('type', 'message')
            if 'callStatus' in activity_data or 'duration' in activity_data:
                activity_type = 'call'
            
            # Create enhanced activity record
            new_activity = Activity(
                conversation_id=conversation.id,
                contact_id=conversation.contact_id,
                openphone_id=activity_id,
                activity_type=activity_type,
                direction=activity_data.get('direction'),
                status=activity_data.get('status') or activity_data.get('callStatus'),
                
                # Participants
                from_number=activity_data.get('from'),
                to_numbers=activity_data.get('to', []),
                phone_number_id=activity_data.get('phoneNumberId'),
                
                # Content
                body=activity_data.get('text') or activity_data.get('body'),
                media_urls=activity_data.get('media', []),
                
                # Call-specific fields
                duration_seconds=activity_data.get('duration'),
                recording_url=activity_data.get('recordingUrl'),
                voicemail_url=activity_data.get('voicemailUrl'),
                answered_at=self._parse_datetime(activity_data.get('answeredAt')),
                answered_by=activity_data.get('answeredBy'),
                completed_at=self._parse_datetime(activity_data.get('completedAt')),
                initiated_by=activity_data.get('initiatedBy'),
                forwarded_from=activity_data.get('forwardedFrom'),
                forwarded_to=activity_data.get('forwardedTo'),
                
                # Timestamps
                created_at=created_at,
                updated_at=datetime.utcnow()
            )
            
            db.session.add(new_activity)
            db.session.flush()  # Get the ID for media attachments
            
            # Process media attachments
            self._download_media_attachments(new_activity, activity_data.get('media', []))
            
            # Download call recordings and voicemails
            if activity_type == 'call':
                self._download_call_recordings(new_activity, activity_data)
                self.stats['calls_imported'] += 1
            else:
                self.stats['messages_imported'] += 1
                
        except Exception as e:
            logger.error(f"Error processing activity {activity_id}: {e}")
            self.stats['errors'].append(f"Activity {activity_id}: {str(e)}")

    def _download_media_attachments(self, activity: Activity, media_urls: List[str]):
        """Download and store media attachments"""
        for media_url in media_urls:
            try:
                response = requests.get(media_url, verify=True, timeout=(5, 30))
                if response.status_code == 200:
                    # Generate filename from URL
                    filename = media_url.split('/')[-1].split('?')[0]
                    if not filename or '.' not in filename:
                        # Generate filename based on content type
                        content_type = response.headers.get('Content-Type', '')
                        extension = self._get_extension_from_content_type(content_type)
                        filename = f"media_{activity.id}_{len(activity.media_attachments)}{extension}"
                    
                    local_path = os.path.join(MEDIA_UPLOAD_FOLDER, filename)
                    
                    # Write file
                    with open(local_path, 'wb') as f:
                        f.write(response.content)
                    
                    # Create database record
                    media_attachment = MediaAttachment(
                        activity_id=activity.id,
                        source_url=media_url,
                        local_path=local_path,
                        content_type=response.headers.get('Content-Type')
                    )
                    db.session.add(media_attachment)
                    
                    self.stats['media_downloaded'] += 1
                    logger.info(f"Downloaded media: {filename}")
                    
            except Exception as e:
                logger.error(f"Error downloading media {media_url}: {e}")
                self.stats['errors'].append(f"Media download {media_url}: {str(e)}")

    def _fetch_call_recording_url(self, call_id: str) -> Optional[str]:
        """Fetch recording URL for a call using correct OpenPhone API endpoint"""
        try:
            url = f"https://api.openphone.com/v1/call-recordings/{call_id}"
            response = requests.get(url, headers=self.headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                recordings = data.get('data', [])
                if recordings:
                    recording = recordings[0]  # Usually just one recording per call
                    recording_url = recording.get('url')
                    logger.info(f"Found recording for call {call_id}: {recording.get('id')}")
                    return recording_url
            elif response.status_code == 404:
                # No recording available - normal case
                logger.debug(f"No recording available for call {call_id}")
                return None
            else:
                logger.warning(f"API error fetching recording for {call_id}: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"Error fetching recording for call {call_id}: {e}")
            return None

    def _download_call_recordings(self, activity: Activity, call_data: Dict):
        """Download call recordings and voicemails"""
        # Fetch recording using correct OpenPhone API endpoint
        call_id = call_data.get('id')
        if call_id:
            recording_url = self._fetch_call_recording_url(call_id)
            if recording_url:
                try:
                response = requests.get(recording_url, verify=True, timeout=(5, 30))
                if response.status_code == 200:
                    filename = f"recording_{activity.id}_{call_data.get('id', 'unknown')}.mp3"
                    local_path = os.path.join(RECORDINGS_FOLDER, filename)
                    
                    with open(local_path, 'wb') as f:
                        f.write(response.content)
                    
                    # Update activity with local recording path
                    activity.recording_url = local_path
                    
                    self.stats['recordings_downloaded'] += 1
                    logger.info(f"Downloaded recording: {filename}")
                    
            except Exception as e:
                logger.error(f"Error downloading recording: {e}")
                self.stats['errors'].append(f"Recording download: {str(e)}")
        
        # Download voicemail
        voicemail_url = call_data.get('voicemailUrl')
        if voicemail_url:
            try:
                response = requests.get(voicemail_url, verify=True, timeout=(5, 30))
                if response.status_code == 200:
                    filename = f"voicemail_{activity.id}_{call_data.get('id', 'unknown')}.mp3"
                    local_path = os.path.join(VOICEMAILS_FOLDER, filename)
                    
                    with open(local_path, 'wb') as f:
                        f.write(response.content)
                    
                    # Update activity with local voicemail path
                    activity.voicemail_url = local_path
                    
                    self.stats['voicemails_downloaded'] += 1
                    logger.info(f"Downloaded voicemail: {filename}")
                    
            except Exception as e:
                logger.error(f"Error downloading voicemail: {e}")
                self.stats['errors'].append(f"Voicemail download: {str(e)}")

    def _generate_ai_content_batch(self):
        """Generate AI summaries and transcripts for imported calls using OpenPhone APIs first, then fallback to local AI"""
        logger.info("--- Step 4: Fetching OpenPhone AI Content and Generating Local AI ---")
        
        try:
            # Find calls without AI content
            calls_needing_ai = db.session.query(Activity).filter(
                Activity.activity_type == 'call',
                Activity.ai_summary.is_(None),
                Activity.ai_content_status.is_(None)
            ).limit(50).all()  # Process in batches
            
            logger.info(f"Found {len(calls_needing_ai)} calls needing AI processing")
            
            for call_activity in calls_needing_ai:
                try:
                    # Mark as processing
                    call_activity.ai_content_status = 'pending'
                    db.session.commit()
                    
                    # First, try to get OpenPhone's AI summaries and transcripts
                    openphone_ai_success = self._fetch_openphone_ai_content(call_activity)
                    
                    # If OpenPhone AI content not available, generate our own
                    if not openphone_ai_success and call_activity.duration_seconds and call_activity.duration_seconds > 0:
                        summary_prompt = self._build_call_summary_prompt(call_activity)
                        ai_summary = self.ai_service.generate_content(summary_prompt)
                        
                        if ai_summary:
                            call_activity.ai_summary = ai_summary
                            call_activity.ai_content_status = 'completed'
                            self.stats['ai_summaries_generated'] += 1
                            logger.info(f"Generated local AI summary for call {call_activity.id}")
                        else:
                            call_activity.ai_content_status = 'failed'
                    elif not openphone_ai_success:
                        call_activity.ai_content_status = 'skipped'
                    
                    db.session.commit()
                    
                except Exception as e:
                    logger.error(f"Error generating AI content for call {call_activity.id}: {e}")
                    call_activity.ai_content_status = 'failed'
                    db.session.commit()
                    self.stats['errors'].append(f"AI generation call {call_activity.id}: {str(e)}")
            
        except Exception as e:
            logger.error(f"Error in batch AI generation: {e}")
            self.stats['errors'].append(f"AI batch generation: {str(e)}")

    def _fetch_openphone_ai_content(self, call_activity: Activity) -> bool:
        """
        Fetch OpenPhone's native AI summaries and transcripts for a call
        Returns True if successful, False otherwise
        """
        if not call_activity.openphone_id:
            return False
            
        success = False
        
        try:
            # Fetch call summary from OpenPhone
            summary_url = f"https://api.openphone.com/v1/call-summaries/{call_activity.openphone_id}"
            summary_response = requests.get(summary_url, headers=self.headers, verify=True, timeout=(5, 30))
            
            if summary_response.status_code == 200:
                summary_data = summary_response.json().get('data', {})
                if summary_data:
                    # Store OpenPhone's AI summary
                    highlights = summary_data.get('highlights', [])
                    next_steps = summary_data.get('nextSteps', [])
                    
                    summary_text = ""
                    if highlights:
                        summary_text += "Call Highlights:\n" + "\n".join(f"• {h}" for h in highlights)
                    if next_steps:
                        if summary_text:
                            summary_text += "\n\n"
                        summary_text += "Next Steps:\n" + "\n".join(f"• {s}" for s in next_steps)
                    
                    if summary_text:
                        call_activity.ai_summary = summary_text
                        call_activity.ai_next_steps = "\n".join(next_steps) if next_steps else None
                        success = True
                        logger.info(f"Fetched OpenPhone AI summary for call {call_activity.id}")
            
            # Fetch call transcript from OpenPhone
            transcript_url = f"https://api.openphone.com/v1/call-transcripts/{call_activity.openphone_id}"
            transcript_response = requests.get(transcript_url, headers=self.headers, verify=True, timeout=(5, 30))
            
            if transcript_response.status_code == 200:
                transcript_data = transcript_response.json().get('data', {})
                if transcript_data:
                    # Store structured transcript data
                    dialogue = transcript_data.get('dialogue', [])
                    if dialogue:
                        call_activity.ai_transcript = {
                            'dialogue': dialogue,
                            'confidence': transcript_data.get('confidence'),
                            'language': transcript_data.get('language', 'en'),
                            'imported_from': 'openphone_api'
                        }
                        success = True
                        logger.info(f"Fetched OpenPhone transcript for call {call_activity.id}")
            
            if success:
                call_activity.ai_content_status = 'completed'
                self.stats['ai_summaries_generated'] += 1
            
        except requests.exceptions.RequestException as e:
            if hasattr(e, 'response') and e.response.status_code == 404:
                # AI content not available for this call (normal for non-Business plans or recent calls)
                logger.debug(f"OpenPhone AI content not available for call {call_activity.id}")
            else:
                logger.error(f"Error fetching OpenPhone AI content for call {call_activity.id}: {e}")
                self.stats['errors'].append(f"OpenPhone AI fetch call {call_activity.id}: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error fetching OpenPhone AI content: {e}")
            self.stats['errors'].append(f"OpenPhone AI unexpected error: {str(e)}")
        
        return success

    def _build_call_summary_prompt(self, call_activity: Activity) -> str:
        """Build prompt for AI call summary generation"""
        contact_name = "Unknown"
        if call_activity.conversation and call_activity.conversation.contact:
            contact = call_activity.conversation.contact
            contact_name = f"{contact.first_name} {contact.last_name}"
        
        duration_mins = call_activity.duration_seconds // 60 if call_activity.duration_seconds else 0
        
        prompt = f"""
        Please generate a brief professional summary for this phone call:
        
        Contact: {contact_name}
        Direction: {call_activity.direction}
        Duration: {duration_mins} minutes
        Status: {call_activity.status}
        Date: {call_activity.created_at.strftime('%Y-%m-%d %H:%M') if call_activity.created_at else 'Unknown'}
        
        Based on this being a foundation repair business call, please provide:
        1. A brief summary of the likely call purpose
        2. Suggested next steps
        3. Any follow-up actions needed
        
        Keep the summary concise and professional.
        """
        
        return prompt

    def _validate_import_integrity(self):
        """Validate imported data integrity and identify potential issues"""
        logger.info("--- Step 5: Validating Import Integrity ---")
        
        validation_issues = []
        
        try:
            # Check for duplicate activities
            duplicate_activities = db.session.query(Activity.openphone_id).group_by(
                Activity.openphone_id
            ).having(db.func.count(Activity.openphone_id) > 1).all()
            
            if duplicate_activities:
                validation_issues.append(f"Found {len(duplicate_activities)} duplicate activities")
                logger.warning(f"Duplicate activities found: {len(duplicate_activities)}")
            
            # Check for orphaned activities (activities without conversations)
            orphaned_activities = db.session.query(Activity).filter(
                Activity.conversation_id.is_(None)
            ).count()
            
            if orphaned_activities > 0:
                validation_issues.append(f"Found {orphaned_activities} orphaned activities")
                logger.warning(f"Orphaned activities found: {orphaned_activities}")
            
            # Check for contacts without phone numbers
            contacts_without_phone = db.session.query(Contact).filter(
                Contact.phone.is_(None) | (Contact.phone == '')
            ).count()
            
            if contacts_without_phone > 0:
                validation_issues.append(f"Found {contacts_without_phone} contacts without phone numbers")
                logger.warning(f"Contacts without phone numbers: {contacts_without_phone}")
            
            # Check for failed media downloads
            failed_media = db.session.query(MediaAttachment).filter(
                MediaAttachment.local_path.is_(None)
            ).count()
            
            if failed_media > 0:
                validation_issues.append(f"Found {failed_media} media attachments without local files")
                logger.warning(f"Failed media downloads: {failed_media}")
            
            # Check for calls without duration
            calls_without_duration = db.session.query(Activity).filter(
                Activity.activity_type == 'call',
                Activity.duration_seconds.is_(None)
            ).count()
            
            if calls_without_duration > 0:
                validation_issues.append(f"Found {calls_without_duration} calls without duration data")
                logger.info(f"Calls without duration (normal for missed calls): {calls_without_duration}")
            
            self.stats['validation_issues'] = validation_issues
            
            if validation_issues:
                logger.info(f"Validation completed with {len(validation_issues)} issues identified")
            else:
                logger.info("Validation completed - no integrity issues found")
                
        except Exception as e:
            logger.error(f"Error during validation: {e}")
            self.stats['errors'].append(f"Validation error: {str(e)}")

    def _parse_datetime(self, datetime_str: Optional[str]) -> Optional[datetime]:
        """Parse OpenPhone datetime string to Python datetime"""
        if not datetime_str:
            return None
        try:
            return datetime.fromisoformat(datetime_str.replace('Z', '')).replace(tzinfo=timezone.utc)
        except Exception:
            return None

    def _get_extension_from_content_type(self, content_type: str) -> str:
        """Get file extension from content type"""
        extensions = {
            'image/jpeg': '.jpg',
            'image/png': '.png',
            'image/gif': '.gif',
            'application/pdf': '.pdf',
            'audio/mpeg': '.mp3',
            'audio/wav': '.wav',
            'video/mp4': '.mp4',
            'text/plain': '.txt'
        }
        return extensions.get(content_type, '.bin')

    def _print_import_summary(self):
        """Print comprehensive import statistics"""
        print("\n" + "="*80)
        print("ENHANCED OPENPHONE IMPORT COMPLETED")
        print("="*80)
        print(f"Conversations Processed: {self.stats['conversations_processed']}")
        print(f"Messages Imported: {self.stats['messages_imported']}")  
        print(f"Calls Imported: {self.stats['calls_imported']}")
        print(f"Media Files Downloaded: {self.stats['media_downloaded']}")
        print(f"Recordings Downloaded: {self.stats['recordings_downloaded']}")
        print(f"Voicemails Downloaded: {self.stats['voicemails_downloaded']}")
        print(f"AI Summaries Generated: {self.stats['ai_summaries_generated']}")
        print(f"Validation Issues: {len(self.stats.get('validation_issues', []))}")
        print(f"Errors Encountered: {len(self.stats['errors'])}")
        
        if self.stats.get('validation_issues'):
            print("\nVALIDATION ISSUES:")
            for issue in self.stats['validation_issues']:
                print(f"  - {issue}")
        
        if self.stats['errors']:
            print("\nERRORS:")
            for error in self.stats['errors'][:10]:  # Show first 10 errors
                print(f"  - {error}")
            if len(self.stats['errors']) > 10:
                print(f"  ... and {len(self.stats['errors']) - 10} more errors")
        
        print("="*80)


def run_enhanced_import(dry_run_limit: Optional[int] = None, start_from_conversation: Optional[str] = None):
    """
    Main entry point for enhanced OpenPhone import
    
    Args:
        dry_run_limit: If provided, limits import to N conversations for testing
        start_from_conversation: If provided, resumes import from specific conversation ID
    """
    importer = EnhancedOpenPhoneImporter(
        dry_run_limit=dry_run_limit,
        start_from_conversation=start_from_conversation
    )
    importer.run_comprehensive_import()


if __name__ == '__main__':
    import sys
    
    # Check for dry run argument
    dry_run_limit = None
    if len(sys.argv) > 1:
        try:
            dry_run_limit = int(sys.argv[1])
            print(f"Running in DRY RUN mode with limit: {dry_run_limit}")
        except ValueError:
            print("Invalid dry run limit. Using full import.")
    
    run_enhanced_import(dry_run_limit)