# tasks/sync_tasks_production.py

import sys
import os
from celery import shared_task
from datetime import datetime, timedelta
import logging

# Add the project root to the Python path to import scripts
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    max_retries=3,
    soft_time_limit=7200,  # 2 hour soft limit
    time_limit=7500,  # 2 hour 5 min hard limit
    acks_late=True,  # Ensure task survives worker restart
)
def sync_openphone_messages_production(self, days_back=30, use_large_scale=True):
    """
    Production-ready Celery task to sync OpenPhone messages
    
    Args:
        days_back: Number of days to sync back from today
        use_large_scale: Use the large scale importer for big imports
    """
    logger.info(f"Starting production OpenPhone sync for last {days_back} days")
    
    try:
        # Calculate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)
        
        # Update task state
        self.update_state(state='PROGRESS', meta={
            'current': 0,
            'total': 100,
            'status': f'Initializing sync from {start_date.date()} to {end_date.date()}'
        })
        
        if use_large_scale:
            # Use the large scale importer for production
            from scripts.data_management.imports.large_scale_import import LargeScaleImporter
            
            # Initialize with production settings
            importer = LargeScaleImporter(
                batch_size=50,  # Process 50 conversations at a time
                checkpoint_interval=10,  # Save progress every 10 conversations
                reset=False  # Don't reset, allow resume
            )
            
            # Hook into progress updates
            original_save_progress = importer._save_progress
            
            def save_progress_with_celery_update():
                # Call original save
                original_save_progress()
                
                # Update Celery task state
                if importer.stats['conversations_processed'] > 0:
                    progress_pct = min(99, importer.stats['conversations_processed'] / 70)  # Assume ~7000 conversations
                    self.update_state(state='PROGRESS', meta={
                        'current': importer.stats['conversations_processed'],
                        'total': 7000,  # Estimate
                        'status': f"Processed {importer.stats['conversations_processed']} conversations",
                        'stats': importer.stats
                    })
            
            importer._save_progress = save_progress_with_celery_update
            
            # Run the import
            importer.run_comprehensive_import()
            
            return {
                'status': 'success',
                'message': f'Successfully synced OpenPhone data',
                'stats': importer.stats,
                'date_range': {
                    'start': start_date.isoformat(),
                    'end': end_date.isoformat()
                }
            }
            
        else:
            # Use standard importer for smaller syncs
            from scripts.data_management.imports.enhanced_openphone_import import run_enhanced_import
            run_enhanced_import()
            
            return {
                'status': 'success',
                'message': f'Successfully synced OpenPhone data for last {days_back} days',
                'date_range': {
                    'start': start_date.isoformat(),
                    'end': end_date.isoformat()
                }
            }
            
    except Exception as e:
        logger.error(f"OpenPhone sync failed: {str(e)}", exc_info=True)
        # Update task state to failure
        self.update_state(
            state='FAILURE',
            meta={
                'exc_type': type(e).__name__,
                'exc_message': str(e),
                'status': 'Sync failed'
            }
        )
        raise


@shared_task
def sync_openphone_daily_production():
    """Daily sync task - syncs last 2 days to ensure no gaps"""
    logger.info("Running daily OpenPhone sync")
    return sync_openphone_messages_production.apply_async(
        kwargs={'days_back': 2, 'use_large_scale': False}
    )