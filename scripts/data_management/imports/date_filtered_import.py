#!/usr/bin/env python3
"""
Date-Filtered OpenPhone Import
Imports only conversations and activities within a specified date range
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional
import logging
import requests

from scripts.data_management.imports.enhanced_openphone_import import EnhancedOpenPhoneImporter

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DateFilteredImporter(EnhancedOpenPhoneImporter):
    """Enhanced importer that filters by date range"""
    
    def __init__(self, days_back: int = 30, dry_run_limit: Optional[int] = None):
        super().__init__(dry_run_limit=dry_run_limit)
        self.days_back = days_back
        self.cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_back)
        logger.info(f"📅 Date filter initialized: importing data from {self.cutoff_date.date()} onwards")
    
    def _fetch_all_conversations(self) -> List[Dict]:
        """Override to fetch conversations updated after cutoff date using API filtering"""
        logger.info(f"--- Fetching conversations updated in last {self.days_back} days ---")
        
        all_conversations = []
        page_token = None
        
        # Format cutoff date for API - OpenPhone expects ISO format
        cutoff_iso = self.cutoff_date.isoformat().replace('+00:00', 'Z')
        
        try:
            while True:
                url = f"https://api.openphone.com/v1/conversations?phoneNumberId={self.phone_number_id}"
                params = {
                    'maxResults': 100,
                    'updatedAfter': cutoff_iso  # Use API filtering!
                }
                if page_token:
                    params['pageToken'] = page_token
                
                response = requests.get(url, headers=self.headers, params=params, verify=True)
                response.raise_for_status()
                data = response.json()
                
                batch_conversations = data.get('data', [])
                all_conversations.extend(batch_conversations)
                
                logger.info(f"Fetched batch: {len(batch_conversations)} conversations, "
                          f"total: {len(all_conversations)}")
                
                page_token = data.get('nextPageToken')
                if not page_token:
                    break
            
            logger.info(f"✅ Found {len(all_conversations)} conversations updated since {self.cutoff_date.date()}")
            return all_conversations
            
        except Exception as e:
            logger.error(f"Error fetching conversations: {e}")
            self.stats['errors'].append(f"Conversations fetch: {str(e)}")
            return []
    
    
    def _fetch_messages_for_conversation(self, participants: List[str]) -> List[Dict]:
        """Override to only fetch messages within date range"""
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
                
                # Filter messages by date
                recent_messages = []
                for msg in batch_messages:
                    created_at_str = msg.get('createdAt', '')
                    if created_at_str:
                        try:
                            created_at = datetime.fromisoformat(created_at_str.replace('Z', '')).replace(tzinfo=timezone.utc)
                            if created_at >= self.cutoff_date:
                                recent_messages.append(msg)
                            elif created_at < self.cutoff_date:
                                # Messages are returned in reverse chronological order
                                # Once we hit an old message, all remaining will be older
                                logger.debug(f"Reached messages older than {self.days_back} days, stopping pagination")
                                return messages + recent_messages
                        except:
                            recent_messages.append(msg)  # Include if we can't parse date
                
                messages.extend(recent_messages)
                page_token = data.get('nextPageToken')
                
                if not page_token:
                    break
                    
        except Exception as e:
            logger.error(f"Error fetching messages: {e}")
            self.stats['errors'].append(f"Messages fetch: {str(e)}")
        
        return messages
    
    def _fetch_calls_for_participant(self, participant: str) -> List[Dict]:
        """Override to only fetch calls within date range"""
        calls = []
        page_token = None
        
        try:
            while True:
                url = "https://api.openphone.com/v1/calls"
                params = {
                    'phoneNumberId': self.phone_number_id,
                    'participants': participant,
                    'maxResults': 100
                }
                if page_token:
                    params['pageToken'] = page_token
                
                response = requests.get(url, headers=self.headers, params=params, verify=True)
                response.raise_for_status()
                data = response.json()
                
                batch_calls = data.get('data', [])
                
                # Filter calls by date
                recent_calls = []
                for call in batch_calls:
                    created_at_str = call.get('createdAt', '')
                    if created_at_str:
                        try:
                            created_at = datetime.fromisoformat(created_at_str.replace('Z', '')).replace(tzinfo=timezone.utc)
                            if created_at >= self.cutoff_date:
                                recent_calls.append(call)
                            elif created_at < self.cutoff_date:
                                # Calls are returned in reverse chronological order
                                logger.debug(f"Reached calls older than {self.days_back} days, stopping pagination")
                                return calls + recent_calls
                        except:
                            recent_calls.append(call)
                
                calls.extend(recent_calls)
                page_token = data.get('nextPageToken')
                
                if not page_token:
                    break
                    
        except Exception as e:
            logger.error(f"Error fetching calls: {e}")
            self.stats['errors'].append(f"Calls fetch: {str(e)}")
        
        return calls
    
    def _print_import_summary(self):
        """Override to show date range in summary"""
        print("\n" + "="*80)
        print(f"🎉 IMPORT COMPLETED - Last {self.days_back} days")
        print("="*80)
        print(f"📅 Date Range: {self.cutoff_date.date()} to {datetime.now().date()}")
        print(f"📊 Conversations Processed: {self.stats['conversations_processed']}")
        print(f"📱 Messages Imported: {self.stats['messages_imported']}")
        print(f"📞 Calls Imported: {self.stats['calls_imported']}")
        print(f"📎 Media Downloaded: {self.stats['media_downloaded']}")
        print(f"🎵 Recordings Downloaded: {self.stats['recordings_downloaded']}")
        print(f"📧 Voicemails Downloaded: {self.stats['voicemails_downloaded']}")
        print(f"🤖 AI Summaries Generated: {self.stats['ai_summaries_generated']}")
        
        if self.stats['validation_issues']:
            print(f"\n⚠️  VALIDATION ISSUES: {len(self.stats['validation_issues'])}")
            for issue in self.stats['validation_issues'][:5]:
                print(f"  - {issue}")
            if len(self.stats['validation_issues']) > 5:
                print(f"  ... and {len(self.stats['validation_issues']) - 5} more")
        
        if self.stats['errors']:
            print(f"\n❌ ERRORS: {len(self.stats['errors'])}")
            for error in self.stats['errors'][:10]:
                print(f"  - {error}")
            if len(self.stats['errors']) > 10:
                print(f"  ... and {len(self.stats['errors']) - 10} more errors")
        
        print("="*80)


def run_date_filtered_import(days_back: int = 30):
    """Run import filtered by date range"""
    logger.info(f"🚀 Starting date-filtered import for last {days_back} days")
    importer = DateFilteredImporter(days_back=days_back)
    importer.run_comprehensive_import()
    return importer.stats


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Date-filtered OpenPhone import')
    parser.add_argument('--days', type=int, default=30, help='Number of days to import (default: 30)')
    args = parser.parse_args()
    
    run_date_filtered_import(args.days)