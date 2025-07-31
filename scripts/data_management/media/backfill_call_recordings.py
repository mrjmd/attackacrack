#!/usr/bin/env python3
"""
Backfill Call Recordings Script

This script fetches call recordings from OpenPhone API using the correct endpoint
(/v1/call-recordings/{callId}) and updates our database with recording URLs.

Run this after discovering the correct OpenPhone recordings API endpoint.
"""

import os
import requests
import logging
from datetime import datetime
from typing import Dict, List, Tuple

from app import create_app
from extensions import db
from crm_database import Activity

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CallRecordingsBackfill:
    """Backfill call recordings from OpenPhone API"""
    
    def __init__(self, batch_size: int = 50, delay_seconds: float = 0.1):
        self.batch_size = batch_size
        self.delay_seconds = delay_seconds
        self.stats = {
            'calls_processed': 0,
            'recordings_found': 0,
            'recordings_saved': 0,
            'api_errors': 0,
            'database_errors': 0
        }
        
    def run_backfill(self):
        """Main backfill method"""
        logger.info("--- Starting Call Recordings Backfill ---")
        
        app = create_app()
        
        with app.app_context():
            # Validate configuration
            api_key = app.config.get('OPENPHONE_API_KEY')
            if not api_key:
                logger.error("ERROR: Missing OPENPHONE_API_KEY. Aborting.")
                return
                
            self.headers = {"Authorization": api_key}
            
            # Get all calls that don't have recordings yet
            calls_to_process = self._get_calls_without_recordings()
            logger.info(f"Found {len(calls_to_process)} calls to process")
            
            if not calls_to_process:
                logger.info("No calls need recording backfill. Exiting.")
                return
                
            # Process calls in batches
            self._process_calls_in_batches(calls_to_process)
            
            # Print final statistics
            self._print_summary()
            
    def _get_calls_without_recordings(self) -> List[Activity]:
        """Get all call activities that don't have recording URLs"""
        return Activity.query.filter(
            Activity.activity_type == 'call',
            Activity.openphone_id.isnot(None),
            Activity.recording_url.is_(None)
        ).order_by(Activity.created_at.desc()).all()
        
    def _process_calls_in_batches(self, calls: List[Activity]):
        """Process calls in batches to avoid overwhelming the API"""
        import time
        
        total_calls = len(calls)
        
        for i in range(0, total_calls, self.batch_size):
            batch = calls[i:i + self.batch_size]
            batch_num = (i // self.batch_size) + 1
            total_batches = (total_calls + self.batch_size - 1) // self.batch_size
            
            logger.info(f"Processing batch {batch_num}/{total_batches} ({len(batch)} calls)")
            
            batch_recordings = 0
            
            for call in batch:
                try:
                    recording_data = self._fetch_call_recording(call.openphone_id)
                    self.stats['calls_processed'] += 1
                    
                    if recording_data:
                        self._save_recording_to_call(call, recording_data)
                        batch_recordings += 1
                        self.stats['recordings_found'] += 1
                        
                    # Small delay to be respectful to API
                    time.sleep(self.delay_seconds)
                    
                except Exception as e:
                    logger.error(f"Error processing call {call.id} ({call.openphone_id}): {e}")
                    self.stats['api_errors'] += 1
                    
            # Commit batch changes
            try:
                db.session.commit()
                self.stats['recordings_saved'] += batch_recordings
                logger.info(f"Batch {batch_num} complete: {batch_recordings} recordings found")
            except Exception as e:
                logger.error(f"Database error in batch {batch_num}: {e}")
                db.session.rollback()
                self.stats['database_errors'] += 1
                
    def _fetch_call_recording(self, call_id: str) -> Dict:
        """Fetch recording data for a specific call ID"""
        url = f"https://api.openphone.com/v1/call-recordings/{call_id}"
        
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                recordings = data.get('data', [])
                
                if recordings:
                    # Return the first (usually only) recording
                    recording = recordings[0]
                    logger.debug(f"Found recording for {call_id}: {recording.get('id')}")
                    return recording
                    
            elif response.status_code == 404:
                # No recording available - normal case
                logger.debug(f"No recording for call {call_id}")
                return None
                
            else:
                logger.warning(f"API error for call {call_id}: {response.status_code} - {response.text}")
                return None
                
        except requests.RequestException as e:
            logger.error(f"Network error fetching recording for {call_id}: {e}")
            return None
            
    def _save_recording_to_call(self, call: Activity, recording_data: Dict):
        """Save recording data to call activity"""
        try:
            # Update the call with recording information
            call.recording_url = recording_data.get('url')
            
            # Optionally store additional recording metadata
            if hasattr(call, 'recording_id'):
                call.recording_id = recording_data.get('id')
            if hasattr(call, 'recording_duration'):
                call.recording_duration = recording_data.get('duration')
                
            logger.debug(f"Updated call {call.id} with recording {recording_data.get('id')}")
            
        except Exception as e:
            logger.error(f"Error saving recording to call {call.id}: {e}")
            raise
            
    def _print_summary(self):
        """Print final backfill statistics"""
        logger.info("--- Call Recordings Backfill Complete ---")
        logger.info(f"Calls Processed: {self.stats['calls_processed']}")
        logger.info(f"Recordings Found: {self.stats['recordings_found']}")
        logger.info(f"Recordings Saved: {self.stats['recordings_saved']}")
        logger.info(f"API Errors: {self.stats['api_errors']}")
        logger.info(f"Database Errors: {self.stats['database_errors']}")
        
        if self.stats['recordings_found'] > 0:
            success_rate = (self.stats['recordings_found'] / self.stats['calls_processed']) * 100
            logger.info(f"Recording Success Rate: {success_rate:.1f}%")
            
        # Show final database state
        total_calls = Activity.query.filter(Activity.activity_type == 'call').count()
        calls_with_recordings = Activity.query.filter(
            Activity.activity_type == 'call',
            Activity.recording_url.isnot(None)
        ).count()
        
        logger.info(f"Database State: {calls_with_recordings}/{total_calls} calls have recordings")

if __name__ == "__main__":
    backfill = CallRecordingsBackfill(batch_size=20, delay_seconds=0.2)
    backfill.run_backfill()