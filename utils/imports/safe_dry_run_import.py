#!/usr/bin/env python3
"""
Safe Dry Run OpenPhone Import
Tests import logic WITHOUT writing to database
Validates API access, data structure, and processing logic
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
from crm_database import Contact, Conversation, Activity, MediaAttachment
from services.contact_service import ContactService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SafeDryRunImporter:
    """
    Safe dry run importer - validates everything WITHOUT database writes
    Perfect for testing with production data before committing to full import
    """
    
    def __init__(self, conversation_limit: int = 10):
        self.conversation_limit = conversation_limit
        self.simulated_stats = {
            'conversations_analyzed': 0,
            'messages_found': 0,
            'calls_found': 0,
            'media_found': 0,
            'recordings_found': 0,
            'voicemails_found': 0,
            'contacts_would_create': 0,
            'api_calls_made': 0,
            'ai_summaries_available': 0,
            'ai_transcripts_available': 0,
            'errors': [],
            'warnings': []
        }
        
        # Track what we would create (simulation only)
        self.simulated_contacts = {}
        self.simulated_conversations = {}
        self.simulated_activities = []
        
    def run_safe_dry_run(self):
        """
        Main dry run - analyzes data structure without any database modifications
        """
        logger.info("="*80)
        logger.info("SAFE DRY RUN - NO DATABASE MODIFICATIONS")
        logger.info(f"Analyzing {self.conversation_limit} conversations")
        logger.info("="*80)
        
        app = create_app()
        
        with app.app_context():
            # Validate configuration
            api_key = app.config.get('OPENPHONE_API_KEY')
            user_phone_number = app.config.get('OPENPHONE_PHONE_NUMBER')
            phone_number_id = app.config.get('OPENPHONE_PHONE_NUMBER_ID')

            if not all([api_key, user_phone_number, phone_number_id]):
                logger.error("ERROR: Missing OpenPhone configuration")
                return False

            self.headers = {"Authorization": api_key}
            self.user_phone_number = user_phone_number
            self.phone_number_id = phone_number_id
            
            # Test API connectivity first
            if not self._test_api_connectivity():
                logger.error("API connectivity test failed")
                return False
            
            # Analyze conversations without importing
            conversations = self._fetch_conversations_for_analysis()
            self._analyze_conversations(conversations)
            self._test_ai_apis()
            
            # Print comprehensive analysis
            self._print_dry_run_analysis()
            
            return len(self.simulated_stats['errors']) == 0

    def _test_api_connectivity(self) -> bool:
        """Test all API endpoints we'll use in the real import"""
        logger.info("--- Testing API Connectivity ---")
        
        test_endpoints = [
            ("Phone Numbers", "https://api.openphone.com/v1/phone-numbers"),
            ("Conversations", f"https://api.openphone.com/v1/conversations?phoneNumberId={self.phone_number_id}&maxResults=1"),
        ]
        
        # Test Users API separately as it may not be available on all plans
        optional_endpoints = [
            ("Users", "https://api.openphone.com/v1/users"),
        ]
        
        for name, url in test_endpoints:
            try:
                response = requests.get(url, headers=self.headers, verify=True, timeout=(5, 30))
                self.simulated_stats['api_calls_made'] += 1
                
                if response.status_code == 200:
                    logger.info(f"✓ {name} API accessible")
                else:
                    logger.error(f"✗ {name} API returned {response.status_code}")
                    self.simulated_stats['errors'].append(f"{name} API: HTTP {response.status_code}")
                    return False
                    
            except Exception as e:
                logger.error(f"✗ {name} API connection failed: {e}")
                self.simulated_stats['errors'].append(f"{name} API: {str(e)}")
                return False
        
        # Test optional endpoints (don't fail if they're not available)
        for name, url in optional_endpoints:
            try:
                response = requests.get(url, headers=self.headers, verify=True, timeout=(5, 30))
                self.simulated_stats['api_calls_made'] += 1
                
                if response.status_code == 200:
                    logger.info(f"✓ {name} API accessible")
                else:
                    logger.info(f"ℹ️  {name} API returned {response.status_code} (may not be available on your plan)")
                    self.simulated_stats['warnings'].append(f"{name} API not available (HTTP {response.status_code})")
                    
            except Exception as e:
                logger.info(f"ℹ️  {name} API connection failed: {e} (may not be available on your plan)")
                self.simulated_stats['warnings'].append(f"{name} API not available: {str(e)}")
        
        return True

    def _fetch_conversations_for_analysis(self) -> List[Dict]:
        """Fetch limited conversations for analysis"""
        logger.info(f"--- Fetching {self.conversation_limit} Conversations for Analysis ---")
        
        try:
            url = f"https://api.openphone.com/v1/conversations?phoneNumberId={self.phone_number_id}"
            params = {'maxResults': self.conversation_limit}
            
            response = requests.get(url, headers=self.headers, params=params, verify=True)
            response.raise_for_status()
            self.simulated_stats['api_calls_made'] += 1
            
            conversations = response.json().get('data', [])
            logger.info(f"Successfully fetched {len(conversations)} conversations")
            
            return conversations
            
        except Exception as e:
            logger.error(f"Error fetching conversations: {e}")
            self.simulated_stats['errors'].append(f"Conversation fetch: {str(e)}")
            return []

    def _analyze_conversations(self, conversations: List[Dict]):
        """Analyze conversation structure without creating database records"""
        logger.info("--- Analyzing Conversation Structure ---")
        
        for i, convo_data in enumerate(conversations):
            try:
                openphone_convo_id = convo_data.get('id')
                participants = convo_data.get('participants', [])
                other_participants = [p for p in participants if p != self.user_phone_number]
                
                if not other_participants:
                    self.simulated_stats['warnings'].append(f"Conversation {i+1}: No external participants")
                    continue

                primary_participant = other_participants[0]
                logger.info(f"Analyzing conversation {i+1}/{len(conversations)} with {primary_participant}")
                
                # Simulate contact creation
                self._simulate_contact_creation(primary_participant, convo_data)
                
                # Simulate conversation creation  
                self._simulate_conversation_creation(openphone_convo_id, convo_data, participants)
                
                # Analyze activities for this conversation
                self._analyze_conversation_activities(primary_participant, other_participants)
                
                self.simulated_stats['conversations_analyzed'] += 1
                
            except Exception as e:
                logger.error(f"Error analyzing conversation {i+1}: {e}")
                self.simulated_stats['errors'].append(f"Conversation {i+1}: {str(e)}")

    def _simulate_contact_creation(self, phone_number: str, convo_data: Dict):
        """Simulate contact creation logic"""
        if phone_number not in self.simulated_contacts:
            contact_name = convo_data.get('name') or phone_number
            
            # Parse name 
            if ' ' in contact_name and not contact_name.startswith('+'):
                name_parts = contact_name.split(' ', 1)
                first_name = name_parts[0]
                last_name = name_parts[1]
            else:
                first_name = contact_name
                last_name = "(from OpenPhone)"
            
            self.simulated_contacts[phone_number] = {
                'first_name': first_name,
                'last_name': last_name,
                'phone': phone_number
            }
            
            self.simulated_stats['contacts_would_create'] += 1
            logger.info(f"  Would create contact: {first_name} {last_name}")

    def _simulate_conversation_creation(self, openphone_id: str, convo_data: Dict, participants: List[str]):
        """Simulate conversation creation"""
        if openphone_id not in self.simulated_conversations:
            self.simulated_conversations[openphone_id] = {
                'openphone_id': openphone_id,
                'name': convo_data.get('name'),
                'participants': participants,
                'last_activity_type': convo_data.get('lastActivityType'),
                'last_activity_id': convo_data.get('lastActivityId')
            }

    def _analyze_conversation_activities(self, primary_participant: str, other_participants: List[str]):
        """Analyze messages and calls for a conversation"""
        # Analyze messages
        messages = self._fetch_messages_for_analysis(other_participants)
        self.simulated_stats['messages_found'] += len(messages)
        
        # Analyze message media
        for message in messages:
            media_urls = message.get('media', [])
            self.simulated_stats['media_found'] += len(media_urls)
            
            if media_urls:
                logger.info(f"  Message has {len(media_urls)} media attachments")
        
        # Analyze calls
        calls = self._fetch_calls_for_analysis(primary_participant)
        self.simulated_stats['calls_found'] += len(calls)
        
        # Analyze call recordings and voicemails
        for call in calls:
            if call.get('recordingUrl'):
                self.simulated_stats['recordings_found'] += 1
            if call.get('voicemailUrl'):
                self.simulated_stats['voicemails_found'] += 1
            
            # Log call details
            duration = call.get('duration', 0)
            status = call.get('callStatus')
            logger.info(f"  Call: {status}, {duration}s, Recording: {'Yes' if call.get('recordingUrl') else 'No'}")

    def _fetch_messages_for_analysis(self, participants: List[str]) -> List[Dict]:
        """Fetch messages for analysis without processing"""
        try:
            url = "https://api.openphone.com/v1/messages"
            params = {
                'phoneNumberId': self.phone_number_id,
                'participants[]': participants,
                'maxResults': 50  # Limited for analysis
            }
            
            response = requests.get(url, headers=self.headers, params=params, verify=True)
            response.raise_for_status()
            self.simulated_stats['api_calls_made'] += 1
            
            return response.json().get('data', [])
            
        except Exception as e:
            logger.error(f"Error fetching messages for analysis: {e}")
            return []

    def _fetch_calls_for_analysis(self, participant: str) -> List[Dict]:
        """Fetch calls for analysis without processing"""
        try:
            url = "https://api.openphone.com/v1/calls"
            params = {
                'phoneNumberId': self.phone_number_id,
                'participants': participant,  # Single participant, not array
                'maxResults': 20  # Limited for analysis
            }
            
            response = requests.get(url, headers=self.headers, params=params, verify=True)
            response.raise_for_status()
            self.simulated_stats['api_calls_made'] += 1
            
            return response.json().get('data', [])
            
        except Exception as e:
            logger.error(f"Error fetching calls for analysis: {e}")
            return []

    def _test_ai_apis(self):
        """Test OpenPhone AI APIs availability"""
        logger.info("--- Testing OpenPhone AI APIs ---")
        
        # Use existing conversation data to find participants and test calls
        try:
            # Get a conversation to find a valid participant
            conv_url = f"https://api.openphone.com/v1/conversations?phoneNumberId={self.phone_number_id}&maxResults=3"
            conv_response = requests.get(conv_url, headers=self.headers, verify=True, timeout=(5, 30))
            
            if conv_response.status_code == 200:
                conversations = conv_response.json().get('data', [])
                
                for conv in conversations:
                    participants = conv.get('participants', [])
                    other_participants = [p for p in participants if p != self.user_phone_number]
                    
                    if other_participants:
                        participant = other_participants[0]
                        
                        # Fetch calls for this participant
                        calls_url = "https://api.openphone.com/v1/calls"
                        calls_params = {
                            'phoneNumberId': self.phone_number_id,
                            'participants': participant,
                            'maxResults': 3
                        }
                        
                        calls_response = requests.get(calls_url, headers=self.headers, params=calls_params, verify=True)
                        
                        if calls_response.status_code == 200:
                            calls = calls_response.json().get('data', [])
                            
                            for call in calls[:2]:  # Test first 2 calls
                                call_id = call.get('id')
                                
                                # Test call summary API
                                summary_url = f"https://api.openphone.com/v1/call-summaries/{call_id}"
                                summary_response = requests.get(summary_url, headers=self.headers, verify=True, timeout=(5, 30))
                                
                                if summary_response.status_code == 200:
                                    self.simulated_stats['ai_summaries_available'] += 1
                                    logger.info(f"  ✓ AI Summary available for call {call_id}")
                                elif summary_response.status_code == 404:
                                    logger.info(f"  - AI Summary not available for call {call_id}")
                                else:
                                    logger.warning(f"  ? AI Summary API returned {summary_response.status_code} for call {call_id}")
                                
                                # Test call transcript API
                                transcript_url = f"https://api.openphone.com/v1/call-transcripts/{call_id}"
                                transcript_response = requests.get(transcript_url, headers=self.headers, verify=True, timeout=(5, 30))
                                
                                if transcript_response.status_code == 200:
                                    self.simulated_stats['ai_transcripts_available'] += 1
                                    logger.info(f"  ✓ AI Transcript available for call {call_id}")
                                elif transcript_response.status_code == 404:
                                    logger.info(f"  - AI Transcript not available for call {call_id}")
                                else:
                                    logger.warning(f"  ? AI Transcript API returned {transcript_response.status_code} for call {call_id}")
                        
                        break  # Test with first valid participant only
            
        except Exception as e:
            logger.error(f"Error testing AI APIs: {e}")
            self.simulated_stats['errors'].append(f"AI API test: {str(e)}")

    def _print_dry_run_analysis(self):
        """Print comprehensive dry run analysis"""
        print("\n" + "="*80)
        print("SAFE DRY RUN ANALYSIS COMPLETE")
        print("="*80)
        print("📊 DATA ANALYSIS RESULTS:")
        print(f"  Conversations Analyzed: {self.simulated_stats['conversations_analyzed']}")
        print(f"  Messages Found: {self.simulated_stats['messages_found']}")
        print(f"  Calls Found: {self.simulated_stats['calls_found']}")
        print(f"  Media Attachments Found: {self.simulated_stats['media_found']}")
        print(f"  Call Recordings Found: {self.simulated_stats['recordings_found']}")
        print(f"  Voicemails Found: {self.simulated_stats['voicemails_found']}")
        print(f"  Contacts Would Create: {self.simulated_stats['contacts_would_create']}")
        
        print("\n🤖 AI CONTENT AVAILABILITY:")
        print(f"  AI Summaries Available: {self.simulated_stats['ai_summaries_available']}")
        print(f"  AI Transcripts Available: {self.simulated_stats['ai_transcripts_available']}")
        
        print(f"\n📡 API PERFORMANCE:")
        print(f"  Total API Calls Made: {self.simulated_stats['api_calls_made']}")
        
        if self.simulated_stats['warnings']:
            print(f"\n⚠️  WARNINGS ({len(self.simulated_stats['warnings'])}):")
            for warning in self.simulated_stats['warnings'][:5]:
                print(f"  - {warning}")
            if len(self.simulated_stats['warnings']) > 5:
                print(f"  ... and {len(self.simulated_stats['warnings']) - 5} more")
                
        if self.simulated_stats['errors']:
            print(f"\n❌ ERRORS ({len(self.simulated_stats['errors'])}):")
            for error in self.simulated_stats['errors']:
                print(f"  - {error}")
        else:
            print(f"\n✅ NO ERRORS DETECTED")
        
        print("\n" + "="*80)
        
        if not self.simulated_stats['errors']:
            print("🎉 DRY RUN SUCCESSFUL - READY FOR ACTUAL IMPORT")
            print("\nTo proceed with real import:")
            print("  python enhanced_openphone_import.py 100  # Import 100 conversations")
            print("  python enhanced_openphone_import.py      # Full import (all ~7000)")
        else:
            print("❌ ISSUES DETECTED - PLEASE RESOLVE BEFORE IMPORTING")
        
        print("="*80)


def run_safe_dry_run(conversation_limit: int = 10):
    """
    Run the safe dry run with specified conversation limit
    
    Args:
        conversation_limit: Number of conversations to analyze (default: 10)
    """
    importer = SafeDryRunImporter(conversation_limit=conversation_limit)
    return importer.run_safe_dry_run()


if __name__ == '__main__':
    import sys
    
    # Parse conversation limit from command line
    conversation_limit = 10
    if len(sys.argv) > 1:
        try:
            conversation_limit = int(sys.argv[1])
        except ValueError:
            print("Invalid conversation limit. Using default of 10.")
    
    print(f"Running safe dry run with {conversation_limit} conversations...")
    success = run_safe_dry_run(conversation_limit)
    
    if success:
        print("\n✅ Safe dry run completed successfully!")
        sys.exit(0)
    else:
        print("\n❌ Safe dry run found issues!")
        sys.exit(1)