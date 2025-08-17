"""
SyncHealthService - Monitors health and status of all sync operations
"""
import os
import logging
from typing import Dict, Any, Optional, List
from celery.result import AsyncResult


class SyncHealthService:
    """Service for monitoring sync health across all integrations"""
    
    def __init__(self):
        """Initialize the SyncHealthService"""
        self.logger = logging.getLogger(__name__)
        self.celery = self._get_celery_instance()
    
    def _get_celery_instance(self):
        """
        Get the appropriate Celery instance based on Redis configuration
        
        Returns:
            Celery application instance or None if not available
        """
        try:
            redis_url = os.environ.get('REDIS_URL', '')
            
            if redis_url.startswith('rediss://'):
                # For production SSL Redis
                from celery_config import create_celery_app
                return create_celery_app('attackacrack')
            else:
                # For local non-SSL Redis
                from celery_worker import celery
                return celery
        except Exception as e:
            self.logger.warning(f"Celery not available: {e}")
            return None
    
    def get_sync_health_status(self) -> Dict[str, Any]:
        """
        Get comprehensive sync health status
        
        Returns:
            Dictionary containing sync health information
        """
        health_data = {
            'celery_available': False,
            'active_tasks': None,
            'scheduled_tasks': None,
            'recent_tasks': [],
            'workers': {},
            'queue_stats': {}
        }
        
        if not self.celery:
            return health_data
        
        try:
            # Get Celery inspection data
            inspect = self.celery.control.inspect()
            
            # Get active tasks
            active_tasks = inspect.active()
            if active_tasks:
                health_data['celery_available'] = True
                health_data['active_tasks'] = active_tasks
                health_data['queue_stats']['active_count'] = sum(
                    len(tasks) for tasks in active_tasks.values()
                )
            
            # Get scheduled tasks
            scheduled_tasks = inspect.scheduled()
            if scheduled_tasks:
                health_data['scheduled_tasks'] = scheduled_tasks
                health_data['queue_stats']['scheduled_count'] = sum(
                    len(tasks) for tasks in scheduled_tasks.values()
                )
            
            # Get worker stats
            stats = inspect.stats()
            if stats:
                health_data['workers'] = self._format_worker_stats(stats)
            
            # Get recent task history (if available)
            health_data['recent_tasks'] = self._get_recent_task_history()
            
        except Exception as e:
            self.logger.error(f"Error getting sync health: {str(e)}")
            health_data['error'] = str(e)
        
        return health_data
    
    def _format_worker_stats(self, stats: Dict) -> Dict[str, Any]:
        """
        Format worker statistics for display
        
        Args:
            stats: Raw worker statistics from Celery
            
        Returns:
            Formatted worker statistics
        """
        formatted_stats = {}
        
        for worker_name, worker_stats in stats.items():
            formatted_stats[worker_name] = {
                'status': 'online',
                'pool': worker_stats.get('pool', {}).get('implementation', 'unknown'),
                'concurrency': worker_stats.get('pool', {}).get('max-concurrency', 0),
                'tasks_total': worker_stats.get('total', {}),
                'rusage': {
                    'user_time': worker_stats.get('rusage', {}).get('utime', 0),
                    'system_time': worker_stats.get('rusage', {}).get('stime', 0),
                }
            }
        
        return formatted_stats
    
    def _get_recent_task_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get recent task execution history
        
        Args:
            limit: Maximum number of recent tasks to return
            
        Returns:
            List of recent task information
        """
        # This would typically query a task result backend or database
        # For now, return empty list as this requires additional infrastructure
        return []
    
    def get_integration_status(self) -> Dict[str, Dict[str, Any]]:
        """
        Get status of all integration syncs
        
        Returns:
            Dictionary with status for each integration
        """
        integrations = {}
        
        # OpenPhone integration status
        try:
            from services.openphone_sync_service import OpenPhoneSyncService
            openphone_service = OpenPhoneSyncService()
            integrations['openphone'] = openphone_service.get_sync_statistics()
            integrations['openphone']['status'] = 'active'
        except Exception as e:
            integrations['openphone'] = {
                'status': 'error',
                'error': str(e)
            }
        
        # QuickBooks integration status
        try:
            from services.quickbooks_service import QuickBooksService
            qb_service = QuickBooksService()
            integrations['quickbooks'] = {
                'status': 'active' if qb_service.is_authenticated() else 'not_configured',
                'authenticated': qb_service.is_authenticated()
            }
        except Exception as e:
            integrations['quickbooks'] = {
                'status': 'error',
                'error': str(e)
            }
        
        return integrations
    
    def check_sync_errors(self) -> List[Dict[str, Any]]:
        """
        Check for any sync errors across all integrations
        
        Returns:
            List of error dictionaries
        """
        errors = []
        
        # Check for failed Celery tasks
        if self.celery:
            try:
                inspect = self.celery.control.inspect()
                reserved = inspect.reserved()
                
                # Check for tasks that might be stuck
                if reserved:
                    for worker, tasks in reserved.items():
                        for task in tasks:
                            if 'sync' in task.get('name', '').lower():
                                errors.append({
                                    'type': 'stuck_task',
                                    'worker': worker,
                                    'task': task.get('name'),
                                    'id': task.get('id')
                                })
            except Exception as e:
                errors.append({
                    'type': 'inspection_error',
                    'message': str(e)
                })
        
        return errors
    
    def get_sync_recommendations(self) -> List[str]:
        """
        Get recommendations for improving sync health
        
        Returns:
            List of recommendation strings
        """
        recommendations = []
        health_status = self.get_sync_health_status()
        
        if not health_status['celery_available']:
            recommendations.append("Celery workers are not available. Check Redis connection and worker processes.")
        
        if health_status.get('queue_stats', {}).get('active_count', 0) > 10:
            recommendations.append("High number of active tasks. Consider scaling workers.")
        
        if health_status.get('queue_stats', {}).get('scheduled_count', 0) > 50:
            recommendations.append("Large number of scheduled tasks. Monitor for potential backlog.")
        
        # Check integration-specific recommendations
        integrations = self.get_integration_status()
        
        if integrations.get('openphone', {}).get('last_sync'):
            from datetime import datetime, timedelta
            last_sync = integrations['openphone']['last_sync']
            if isinstance(last_sync, datetime) and last_sync < datetime.now() - timedelta(days=1):
                recommendations.append("OpenPhone hasn't synced in over 24 hours. Consider running a manual sync.")
        
        if not integrations.get('quickbooks', {}).get('authenticated'):
            recommendations.append("QuickBooks is not authenticated. Complete OAuth setup for financial sync.")
        
        return recommendations