"""
OpenPhoneSyncService - Handles OpenPhone data synchronization operations
"""
import os
import uuid
import logging
from typing import Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from repositories.contact_repository import ContactRepository
from repositories.activity_repository import ActivityRepository


class OpenPhoneSyncService:
    """Service for managing OpenPhone data synchronization"""
    
    def __init__(self, contact_repository: ContactRepository = None, activity_repository: ActivityRepository = None):
        """Initialize the OpenPhoneSyncService with repository dependencies"""
        self.logger = logging.getLogger(__name__)
        self.contact_repository = contact_repository
        self.activity_repository = activity_repository
    
    def get_sync_statistics(self) -> Dict[str, Any]:
        """
        Get OpenPhone sync statistics
        
        Returns:
            Dictionary containing sync statistics
        """
        stats = {
            'total_contacts': self.contact_repository.count_with_phone(),
            'total_messages': self.activity_repository.count_by_type('sms'),
            'last_sync': None
        }
        
        # Get last sync time (most recent message)
        last_activity = self.activity_repository.find_latest_by_type('sms')
        
        if last_activity:
            stats['last_sync'] = last_activity.created_at
        
        return stats
    
    def determine_sync_days(self, sync_type: str, custom_days: Optional[int] = None) -> int:
        """
        Determine the number of days to sync based on sync type
        
        Args:
            sync_type: Type of sync (last_7, last_30, last_90, full, custom)
            custom_days: Number of days for custom sync
            
        Returns:
            Number of days to sync
        """
        sync_days_map = {
            'last_7': 7,
            'last_30': 30,
            'last_90': 90,
            'full': 3650,  # 10 years for full sync
        }
        
        if sync_type == 'custom' and custom_days:
            return custom_days
        
        return sync_days_map.get(sync_type, 30)  # Default to 30 days
    
    def queue_sync_task(self, days_back: int, track_bounces: bool = False) -> Tuple[bool, str, Optional[str]]:
        """
        Queue an OpenPhone sync task
        
        Args:
            days_back: Number of days to sync
            track_bounces: Whether to track bounces
            
        Returns:
            Tuple of (success, message, task_id)
        """
        try:
            self.logger.info(f"Attempting to queue sync task for {days_back} days")
            
            # Get Celery instance based on Redis configuration
            redis_url = os.environ.get('REDIS_URL', '')
            
            if redis_url.startswith('rediss://'):
                # Production SSL Redis configuration
                from celery_config import create_celery_app
                celery = create_celery_app('attackacrack')
                from tasks.sync_tasks import sync_openphone_messages
                
                # Use fire-and-forget mode to avoid timeout
                task_id = str(uuid.uuid4())
                sync_openphone_messages.apply_async(
                    args=[days_back],
                    kwargs={'track_bounces': track_bounces},
                    task_id=task_id,
                    ignore_result=True  # Don't wait for backend connection
                )
                
                self.logger.info(f"Task queued successfully with ID: {task_id}, bounce tracking: {track_bounces}")
                
                msg = f'OpenPhone sync started for last {days_back} days'
                if track_bounces:
                    msg += ' with bounce tracking enabled'
                msg += '. Check sync health for progress.'
                
                return True, msg, task_id
                
            else:
                # Local non-SSL Redis configuration
                from tasks.sync_tasks import sync_openphone_messages
                task = sync_openphone_messages.delay(days_back=days_back, track_bounces=track_bounces)
                
                self.logger.info(f"Task queued successfully with ID: {task.id}, bounce tracking: {track_bounces}")
                
                msg = f'OpenPhone sync started for last {days_back} days'
                if track_bounces:
                    msg += ' with bounce tracking enabled'
                msg += f'. Task ID: {task.id}'
                
                return True, msg, task.id
                
        except Exception as e:
            self.logger.error(f"Error queuing sync task: {str(e)}", exc_info=True)
            
            # Provide helpful error message based on environment
            if os.environ.get('FLASK_ENV') == 'production':
                error_msg = 'Background task queueing failed. Use manual import script via console for now.'
                command_hint = f'python scripts/data_management/imports/enhanced_openphone_import.py --days-back {days_back}'
                return False, error_msg, command_hint
            else:
                return False, f'Error starting sync: {str(e)}', None
    
    def get_sync_progress(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the progress of a sync task
        
        Args:
            task_id: The task ID to check
            
        Returns:
            Progress information or None if unavailable
        """
        try:
            from services.task_service import TaskService
            task_service = TaskService()
            return task_service.get_task_status(task_id)
        except Exception as e:
            self.logger.error(f"Error getting sync progress: {str(e)}")
            return None
    
    def get_recent_sync_activity(self, limit: int = 10) -> list:
        """
        Get recent sync activity
        
        Args:
            limit: Maximum number of activities to return
            
        Returns:
            List of recent sync activities
        """
        recent_activities = self.activity_repository.find_recent_by_type_with_contact('sms', limit=limit)
        
        return [
            {
                'id': activity.id,
                'contact_name': activity.contact.get_full_name() if activity.contact else 'Unknown',
                'direction': activity.direction,
                'created_at': activity.created_at,
                'body_preview': activity.body[:50] if activity.body else ''
            }
            for activity in recent_activities
        ]