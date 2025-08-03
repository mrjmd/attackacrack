# tasks/sync_tasks.py

import sys
import os
from celery import shared_task
from datetime import datetime, timedelta
import logging
import json
from typing import Optional

# Add the project root to the Python path to import scripts
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    max_retries=3,
    soft_time_limit=7200,  # 2 hour soft limit for large imports
    time_limit=7500,  # 2 hour 5 min hard limit
    acks_late=True,  # Ensure task survives worker restart
)
def sync_openphone_messages(self, days_back=30, force_large_scale=False):
    """
    Unified Celery task to sync OpenPhone messages
    Automatically chooses between enhanced and large-scale importers based on scope
    
    Args:
        days_back: Number of days to sync back from today
        force_large_scale: Force use of large scale importer
    """
    logger.info(f"Starting OpenPhone sync for last {days_back} days")
    
    try:
        # Calculate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)
        
        # Determine if we should use large scale importer
        # Use large scale for: initial imports (>30 days), forced, or if we detect many conversations
        use_large_scale = force_large_scale or days_back > 30
        
        if use_large_scale:
            logger.info("Using large scale importer with progress tracking")
            return _run_large_scale_sync(self, start_date, end_date)
        else:
            logger.info("Using standard enhanced importer")
            return _run_standard_sync(self, start_date, end_date, days_back)
            
    except Exception as e:
        logger.error(f"OpenPhone sync failed: {str(e)}", exc_info=True)
        self.update_state(
            state='FAILURE',
            meta={
                'exc_type': type(e).__name__,
                'exc_message': str(e),
                'status': 'Sync failed',
                'error_details': str(e)
            }
        )
        raise


def _run_standard_sync(self, start_date, end_date, days_back):
    """Run standard enhanced import for smaller syncs"""
    sync_start_time = datetime.now()
    
    # Initial progress
    self.update_state(state='PROGRESS', meta={
        'current': 0,
        'total': 100,
        'percent': 0,
        'status': f'Initializing sync from {start_date.date()} to {end_date.date()}',
        'start_time': sync_start_time.isoformat(),
        'stats': {
            'conversations': 0,
            'messages': 0,
            'calls': 0,
            'media': 0,
            'recordings': 0,
            'errors': 0,
        }
    })
    
    from scripts.data_management.imports.date_filtered_import import DateFilteredImporter
    
    # Create importer instance with date filtering
    importer = DateFilteredImporter(days_back=days_back)
    
    # Store reference to celery task for progress updates
    importer._celery_task = self
    importer._sync_start_time = sync_start_time
    importer._start_date = start_date
    importer._end_date = end_date
    
    # Wrap the importer's _process_conversations method to add progress tracking
    original_process_conversations = importer._process_conversations
    
    def process_conversations_with_progress(conversations):
        total_conversations = len(conversations)
        logger.info(f"Total conversations to process: {total_conversations}")
        
        # Update with discovered total
        self.update_state(state='PROGRESS', meta={
            'current': 0,
            'total': total_conversations,
            'percent': 0,
            'status': f'Processing {total_conversations} conversations...',
            'start_time': sync_start_time.isoformat(),
            'stats': importer.stats
        })
        
        # Call original method to process all conversations
        original_process_conversations(conversations)
        
    # Also wrap individual conversation processing for progress updates
    from crm_database import Conversation
    original_import_activities = importer._import_conversation_activities
    conversations_processed = 0
    
    def import_activities_with_progress(conversation: Conversation, participants: list):
        nonlocal conversations_processed
        
        # Call original method
        original_import_activities(conversation, participants)
        
        # Update progress
        conversations_processed += 1
        if hasattr(importer, '_total_conversations'):
            total = importer._total_conversations
        else:
            total = conversations_processed + 50  # Estimate
            
        # Update every 5 conversations
        if conversations_processed % 5 == 0 or conversations_processed == total:
            percent = int((conversations_processed / total) * 100) if total > 0 else 0
            
            self.update_state(state='PROGRESS', meta={
                'current': conversations_processed,
                'total': total,
                'percent': percent,
                'status': f'Processing conversation {conversations_processed}/{total}',
                'stats': {
                    'conversations': importer.stats.get('conversations_processed', conversations_processed),
                    'messages': importer.stats.get('messages_imported', 0),
                    'calls': importer.stats.get('calls_imported', 0),
                    'media': importer.stats.get('media_downloaded', 0),
                    'recordings': importer.stats.get('recordings_downloaded', 0),
                    'errors': len(importer.stats.get('errors', [])),
                },
                'start_time': sync_start_time.isoformat(),
                'date_range': {
                    'start': start_date.isoformat(),
                    'end': end_date.isoformat()
                }
            })
    
    # Store the original fetch method before replacing
    original_fetch_all = importer._fetch_all_conversations
    
    # Set total conversations when we fetch them
    def fetch_with_total():
        conversations = original_fetch_all()
        importer._total_conversations = len(conversations)
        return conversations
    
    # Replace the methods
    importer._process_conversations = process_conversations_with_progress
    importer._import_conversation_activities = import_activities_with_progress
    importer._fetch_all_conversations = fetch_with_total
    
    try:
        # Run the sync
        importer.run_comprehensive_import()
        
        # Final stats
        final_stats = importer.stats
        
        # Update final state
        self.update_state(state='SUCCESS', meta={
            'status': 'Sync completed successfully',
            'message': f'Successfully synced OpenPhone data for last {days_back} days',
            'stats': final_stats,
            'date_range': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat()
            },
            'start_time': sync_start_time.isoformat(),
            'end_time': datetime.now().isoformat()
        })
        
        return {
            'status': 'success',
            'message': f'Successfully synced OpenPhone data for last {days_back} days',
            'stats': final_stats,
            'date_range': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat()
            }
        }
    except Exception as e:
        raise


def _run_large_scale_sync(self, start_date, end_date):
    """Run large scale import with progress tracking"""
    from scripts.data_management.imports.large_scale_import import LargeScaleImporter
    from extensions import db
    
    # Initialize importer with production settings
    importer = LargeScaleImporter(
        batch_size=50,
        checkpoint_interval=10,
        reset=False  # Allow resume from previous attempts
    )
    
    # Track start time
    sync_start_time = datetime.now()
    
    # Create progress tracking callback
    def update_celery_progress():
        """Update Celery task state with current progress"""
        stats = importer.stats
        # Check both places where count might be stored
        processed = stats.get('conversations_processed', 0)
        if hasattr(importer, 'progress') and isinstance(importer.progress, dict):
            # Large scale importer stores it here
            processed = max(processed, importer.progress.get('conversations_processed', 0))
        
        # Calculate estimated total (we'll update this as we learn more)
        estimated_total = importer._estimated_total if hasattr(importer, '_estimated_total') else 7000
        
        # Calculate progress percentage
        progress_pct = min(99, (processed / estimated_total * 100)) if estimated_total > 0 else 0
        
        # Calculate time estimates
        elapsed_time = (datetime.now() - sync_start_time).total_seconds()
        rate = processed / elapsed_time if elapsed_time > 0 else 0
        eta_seconds = (estimated_total - processed) / rate if rate > 0 else None
        
        # Update Celery state
        self.update_state(state='PROGRESS', meta={
            'current': processed,
            'total': estimated_total,
            'percent': round(progress_pct, 1),
            'status': f'Processing conversations... ({processed}/{estimated_total})',
            'stats': {
                'conversations': processed,
                'messages': stats.get('messages_imported', 0),
                'calls': stats.get('calls_imported', 0),
                'media': stats.get('media_downloaded', 0),
                'recordings': stats.get('recordings_downloaded', 0),
                'errors': len(stats.get('errors', [])),
            },
            'rate': f'{rate:.1f} conversations/sec' if rate > 0 else 'calculating...',
            'eta_seconds': eta_seconds,
            'start_time': sync_start_time.isoformat(),
            'date_range': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat()
            }
        })
    
    # Hook into the importer's progress saving
    original_save_progress = importer._save_progress
    original_process_conversations = importer._process_conversations
    
    def save_progress_with_celery():
        original_save_progress()
        update_celery_progress()
    
    # Update total estimate when we fetch conversations
    def process_conversations_with_total(conversations):
        importer._estimated_total = len(conversations)
        logger.info(f"Total conversations to process: {len(conversations)}")
        update_celery_progress()
        return original_process_conversations(conversations)
    
    # Also hook into batch processing to update totals dynamically
    original_process_batch = importer._process_conversation_batch if hasattr(importer, '_process_conversation_batch') else None
    
    def process_batch_with_update(batch_conversations):
        # Update our estimate based on progress
        current = importer.stats.get('conversations_processed', 0)
        if current > 0 and hasattr(importer, '_batch_number'):
            # Extrapolate total based on current progress
            estimated_total = int(current * 1.1)  # Add 10% buffer
            if estimated_total > importer._estimated_total:
                importer._estimated_total = estimated_total
                logger.info(f"Updated total estimate to: {estimated_total}")
        
        # Call original method
        if original_process_batch:
            result = original_process_batch(batch_conversations)
        else:
            # Fallback to parent class method
            from extensions import db
            for i, convo_data in enumerate(batch_conversations):
                try:
                    # Process conversation...
                    pass
                except Exception as e:
                    logger.error(f"Error processing conversation: {e}")
        
        # Update progress after batch
        update_celery_progress()
        return result if original_process_batch else None
    
    # Apply our hooks
    importer._save_progress = save_progress_with_celery
    importer._process_conversations = process_conversations_with_total
    if hasattr(importer, '_process_conversation_batch'):
        importer._process_conversation_batch = process_batch_with_update
    
    # Run the import
    logger.info("Starting large scale import with progress tracking")
    success = importer.run_comprehensive_import()
    
    # Final update
    final_stats = importer.stats
    end_time = datetime.now()
    total_time = (end_time - sync_start_time).total_seconds()
    
    if success:
        self.update_state(state='SUCCESS', meta={
            'status': 'Large scale sync completed successfully',
            'stats': final_stats,
            'total_time_seconds': total_time,
            'total_time_formatted': f'{int(total_time // 3600)}h {int((total_time % 3600) // 60)}m',
            'date_range': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat()
            },
            'start_time': sync_start_time.isoformat(),
            'end_time': end_time.isoformat()
        })
        
        return {
            'status': 'success',
            'message': 'Successfully completed large scale OpenPhone sync',
            'stats': final_stats,
            'total_time': f'{int(total_time // 3600)}h {int((total_time % 3600) // 60)}m'
        }
    else:
        raise Exception("Large scale import failed - check logs for details")


@shared_task
def sync_openphone_daily():
    """Daily sync task - syncs last 2 days to ensure no gaps"""
    logger.info("Running daily OpenPhone sync")
    return sync_openphone_messages.apply_async(kwargs={'days_back': 2})