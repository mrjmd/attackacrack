"""
TaskService - Handles Celery task status and management
"""
import os
from typing import Dict, Any, Optional
from celery.result import AsyncResult


class TaskService:
    """Service for managing and monitoring Celery tasks"""
    
    def __init__(self):
        """Initialize the TaskService with appropriate Celery configuration"""
        self.celery = self._get_celery_instance()
    
    def _get_celery_instance(self):
        """
        Get the appropriate Celery instance based on Redis configuration
        
        Returns:
            Celery application instance
        """
        redis_url = os.environ.get('REDIS_URL', '')
        
        if redis_url.startswith('rediss://'):
            # For production SSL Redis, use configured Celery app
            from celery_config import create_celery_app
            return create_celery_app('attackacrack')
        else:
            # For local non-SSL Redis, use the regular approach
            from celery_worker import celery
            return celery
    
    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """
        Get the status and details of a Celery task
        
        Args:
            task_id: The ID of the Celery task
            
        Returns:
            Dictionary containing task status information
            
        Raises:
            Exception: If task status cannot be retrieved
        """
        try:
            result = AsyncResult(task_id, app=self.celery)
            
            response = {
                'task_id': task_id,
                'state': result.state,
                'ready': result.ready()
            }
            
            if result.state == 'PENDING':
                # Task hasn't started yet
                response['meta'] = {'status': 'Task is waiting to be processed...'}
            elif result.state == 'PROGRESS':
                # Task is running with progress updates
                response['meta'] = result.info
            elif result.state == 'SUCCESS':
                # Task completed successfully
                response['result'] = result.result
                response['meta'] = result.info if hasattr(result, 'info') else None
            elif result.state == 'FAILURE':
                # Task failed
                response['error'] = str(result.info)
                response['meta'] = self._format_failure_meta(result.info)
            else:
                # Some other state
                response['meta'] = result.info
            
            return response
            
        except Exception as e:
            raise Exception(f"Could not fetch task status: {str(e)}")
    
    def _format_failure_meta(self, error_info) -> Dict[str, str]:
        """
        Format failure metadata for consistent error reporting
        
        Args:
            error_info: Error information from Celery result
            
        Returns:
            Formatted error metadata dictionary
        """
        if isinstance(error_info, dict):
            return {
                'exc_type': error_info.get('exc_type', 'Unknown'),
                'exc_message': error_info.get('exc_message', str(error_info)),
                'status': 'Task failed'
            }
        else:
            return {
                'exc_type': 'Unknown',
                'exc_message': str(error_info),
                'status': 'Task failed'
            }
    
    def cancel_task(self, task_id: str) -> bool:
        """
        Cancel a running or pending task
        
        Args:
            task_id: The ID of the task to cancel
            
        Returns:
            True if task was successfully cancelled, False otherwise
        """
        try:
            result = AsyncResult(task_id, app=self.celery)
            result.revoke(terminate=True)
            return True
        except Exception:
            return False
    
    def get_active_tasks(self) -> Optional[Dict[str, Any]]:
        """
        Get all active tasks across all workers
        
        Returns:
            Dictionary of active tasks by worker, or None if unavailable
        """
        try:
            inspect = self.celery.control.inspect()
            return inspect.active()
        except Exception:
            return None
    
    def get_scheduled_tasks(self) -> Optional[Dict[str, Any]]:
        """
        Get all scheduled tasks
        
        Returns:
            Dictionary of scheduled tasks by worker, or None if unavailable
        """
        try:
            inspect = self.celery.control.inspect()
            return inspect.scheduled()
        except Exception:
            return None
    
    def get_task_queue_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the task queue
        
        Returns:
            Dictionary containing queue statistics
        """
        stats = {
            'active_tasks': None,
            'scheduled_tasks': None,
            'workers_available': False
        }
        
        try:
            inspect = self.celery.control.inspect()
            active = inspect.active()
            scheduled = inspect.scheduled()
            
            if active is not None:
                stats['workers_available'] = True
                stats['active_tasks'] = sum(len(tasks) for tasks in active.values())
            
            if scheduled is not None:
                stats['scheduled_tasks'] = sum(len(tasks) for tasks in scheduled.values())
            
        except Exception:
            pass
        
        return stats