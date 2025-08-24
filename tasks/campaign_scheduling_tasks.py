"""
Campaign Scheduling Celery Tasks - Phase 3C
Background tasks for automated campaign scheduling and execution
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

from celery import Task
from celery_worker import celery
from app import create_app
from utils.datetime_utils import utc_now

logger = logging.getLogger(__name__)


@celery.task(name='check_scheduled_campaigns')
def check_scheduled_campaigns() -> Dict[str, Any]:
    """
    Check for campaigns ready to execute (runs every minute).
    
    Returns:
        Dict with success status and campaign counts
    """
    try:
        app = create_app()
        with app.app_context():
            scheduling_service = app.services.get('campaign_scheduling')
            
            if not scheduling_service:
                logger.error("Campaign scheduling service not found")
                return {
                    'success': False,
                    'error': 'Service not found',
                    'campaigns_found': 0,
                    'campaigns_queued': 0
                }
            
            # Get campaigns ready to run
            ready_campaigns = scheduling_service.get_campaigns_ready_to_run()
            
            campaigns_queued = 0
            for campaign in ready_campaigns:
                # Queue execution task for each ready campaign
                execute_scheduled_campaign.delay(campaign.id)
                campaigns_queued += 1
                logger.info(f"Queued campaign {campaign.id} for execution")
            
            return {
                'success': True,
                'campaigns_found': len(ready_campaigns),
                'campaigns_queued': campaigns_queued,
                'timestamp': utc_now().isoformat()
            }
            
    except Exception as e:
        logger.error(f"Error checking scheduled campaigns: {e}")
        return {
            'success': False,
            'error': str(e),
            'campaigns_found': 0,
            'campaigns_queued': 0
        }


@celery.task(name='execute_scheduled_campaign', bind=True, max_retries=3)
def execute_scheduled_campaign(self, campaign_id: int) -> Dict[str, Any]:
    """
    Execute a scheduled campaign.
    
    Args:
        campaign_id: ID of campaign to execute
        
    Returns:
        Dict with execution status
    """
    try:
        app = create_app()
        with app.app_context():
            scheduling_service = app.services.get('campaign_scheduling')
            campaign_service = app.services.get('campaign')
            
            if not scheduling_service or not campaign_service:
                raise ValueError("Required services not found")
            
            # Update campaign status via scheduling service
            result = scheduling_service.execute_scheduled_campaign(campaign_id)
            
            if not result.is_success:
                # For certain errors like "not found", don't retry - just return error
                if "not found" in result.error.lower():
                    return {
                        'success': False,
                        'campaign_id': campaign_id,
                        'error': result.error,
                        'timestamp': utc_now().isoformat()
                    }
                raise ValueError(result.error)
            
            # Process the campaign queue to send messages
            queue_result = campaign_service.process_campaign_queue()
            
            # Extract message counts
            messages_sent = queue_result.get('messages_sent', 0) if isinstance(queue_result, dict) else 0
            messages_failed = queue_result.get('messages_failed', 0) if isinstance(queue_result, dict) else 0
            
            logger.info(f"Successfully executed scheduled campaign {campaign_id}")
            
            # Build result with scheduling service data and message counts
            task_result = {
                'success': True,
                'campaign_id': campaign_id,
                'status': 'executing',
                'messages_sent': messages_sent,
                'messages_failed': messages_failed,
                'timestamp': utc_now().isoformat()
            }
            
            # Include any additional data from the scheduling service
            if isinstance(result.data, dict):
                for key, value in result.data.items():
                    if key not in task_result:  # Don't override existing keys
                        task_result[key] = value
                        
            return task_result
                
    except Exception as e:
        logger.error(f"Error executing scheduled campaign {campaign_id}: {e}")
        
        # Retry with exponential backoff
        retry_in = 60 * (2 ** self.request.retries)
        raise self.retry(exc=e, countdown=retry_in)


@celery.task(name='calculate_recurring_schedules')
def calculate_recurring_schedules() -> Dict[str, Any]:
    """
    Calculate next run times for recurring campaigns.
    
    Returns:
        Dict with update counts
    """
    try:
        app = create_app()
        with app.app_context():
            scheduling_service = app.services.get('campaign_scheduling')
            campaign_repository = app.services.get('campaign_repository')
            
            if not scheduling_service or not campaign_repository:
                raise ValueError("Required services not found")
            
            # Find recurring campaigns that need updating
            current_time = utc_now()
            recurring_campaigns = campaign_repository.find_recurring_campaigns_needing_update(current_time)
            
            updated_count = 0
            for campaign in recurring_campaigns:
                if campaign.recurrence_pattern:
                    next_run = scheduling_service.calculate_next_run(
                        campaign.scheduled_at or current_time,
                        campaign.recurrence_pattern,
                        campaign.timezone
                    )
                    
                    if next_run:
                        campaign_repository.update_next_run_at(campaign.id, next_run)
                        updated_count += 1
                        logger.info(f"Updated next run for campaign {campaign.id}: {next_run}")
                    else:
                        # No more runs, complete the campaign
                        campaign.status = 'complete'
                        campaign.is_recurring = False
                        logger.info(f"Completed recurring campaign {campaign.id}")
            
            campaign_repository.commit()
            
            return {
                'success': True,
                'campaigns_processed': len(recurring_campaigns),
                'campaigns_updated': updated_count,
                'timestamp': utc_now().isoformat()
            }
            
    except Exception as e:
        logger.error(f"Error calculating recurring schedules: {e}")
        return {
            'success': False,
            'error': str(e),
            'campaigns_processed': 0,
            'campaigns_updated': 0
        }


@celery.task(name='cleanup_expired_campaigns')
def cleanup_expired_campaigns() -> Dict[str, Any]:
    """
    Clean up expired recurring campaigns.
    
    Returns:
        Dict with cleanup counts
    """
    try:
        app = create_app()
        with app.app_context():
            campaign_repository = app.services.get('campaign_repository')
            
            if not campaign_repository:
                raise ValueError("Campaign repository not found")
            
            current_time = utc_now()
            cleaned_count = campaign_repository.cleanup_expired_recurring_campaigns(current_time)
            
            if cleaned_count > 0:
                campaign_repository.commit()
                logger.info(f"Cleaned up {cleaned_count} expired recurring campaigns")
            
            return {
                'success': True,
                'campaigns_cleaned': cleaned_count,
                'timestamp': current_time.isoformat()
            }
            
    except Exception as e:
        logger.error(f"Error cleaning up expired campaigns: {e}")
        return {
            'success': False,
            'error': str(e),
            'campaigns_cleaned': 0
        }


@celery.task(name='send_schedule_notifications')
def send_schedule_notifications() -> Dict[str, Any]:
    """
    Send notifications for upcoming scheduled campaigns.
    
    Returns:
        Dict with notification counts
    """
    try:
        app = create_app()
        with app.app_context():
            scheduling_service = app.services.get('campaign_scheduling')
            activity_repository = app.services.get('activity_repository')
            
            if not scheduling_service or not activity_repository:
                raise ValueError("Required services not found")
            
            # Get campaigns scheduled in the next hour
            current_time = utc_now()
            upcoming_time = current_time + timedelta(hours=1)
            
            scheduled_campaigns = scheduling_service.get_scheduled_campaigns()
            
            notifications_sent = 0
            for campaign in scheduled_campaigns:
                if campaign.scheduled_at and current_time <= campaign.scheduled_at <= upcoming_time:
                    # Create notification activity
                    from crm_database import Activity
                    
                    activity = Activity(
                        activity_type='notification',
                        direction='outgoing',
                        status='completed',
                        body=f"Campaign '{campaign.name}' scheduled to run at {campaign.scheduled_at}",
                        created_at=current_time
                    )
                    
                    activity_repository.create(activity)
                    notifications_sent += 1
                    logger.info(f"Sent notification for campaign {campaign.id}")
            
            if notifications_sent > 0:
                activity_repository.commit()
            
            return {
                'success': True,
                'notifications_sent': notifications_sent,
                'timestamp': current_time.isoformat()
            }
            
    except Exception as e:
        logger.error(f"Error sending schedule notifications: {e}")
        return {
            'success': False,
            'error': str(e),
            'notifications_sent': 0
        }


@celery.task(name='validate_scheduled_campaigns')
def validate_scheduled_campaigns() -> Dict[str, Any]:
    """
    Validate scheduled campaigns for issues before execution.
    
    Returns:
        Dict with validation results
    """
    try:
        app = create_app()
        with app.app_context():
            scheduling_service = app.services.get('campaign_scheduling')
            
            if not scheduling_service:
                raise ValueError("Campaign scheduling service not found")
            
            scheduled_campaigns = scheduling_service.get_scheduled_campaigns()
            
            issues_found = []
            for campaign in scheduled_campaigns:
                # Check for missing templates
                if not campaign.template_a:
                    issues_found.append({
                        'campaign_id': campaign.id,
                        'issue': 'Missing template'
                    })
                
                # Check for empty member list
                if not campaign.memberships:
                    issues_found.append({
                        'campaign_id': campaign.id,
                        'issue': 'No recipients'
                    })
                
                # Check for past scheduled time
                if campaign.scheduled_at and campaign.scheduled_at < utc_now():
                    issues_found.append({
                        'campaign_id': campaign.id,
                        'issue': 'Scheduled time in the past'
                    })
            
            return {
                'success': True,
                'campaigns_checked': len(scheduled_campaigns),
                'issues_found': len(issues_found),
                'issues': issues_found,
                'timestamp': utc_now().isoformat()
            }
            
    except Exception as e:
        logger.error(f"Error validating scheduled campaigns: {e}")
        return {
            'success': False,
            'error': str(e),
            'campaigns_checked': 0,
            'issues_found': 0
        }


@celery.task(name='archive_old_campaigns')
def archive_old_campaigns(days_old: int = 90) -> Dict[str, Any]:
    """
    Archive campaigns older than specified days.
    
    Args:
        days_old: Number of days before archiving
        
    Returns:
        Dict with archive counts
    """
    try:
        app = create_app()
        with app.app_context():
            campaign_repository = app.services.get('campaign_repository')
            
            if not campaign_repository:
                raise ValueError("Campaign repository not found")
            
            cutoff_date = utc_now() - timedelta(days=days_old)
            
            # Find old, completed campaigns
            old_campaigns = campaign_repository.session.query(Campaign).filter(
                Campaign.status == 'complete',
                Campaign.created_at < cutoff_date,
                Campaign.archived == False
            ).all()
            
            campaign_ids = [c.id for c in old_campaigns]
            
            if campaign_ids:
                archived_count = campaign_repository.bulk_archive_campaigns(campaign_ids)
                campaign_repository.commit()
                logger.info(f"Archived {archived_count} old campaigns")
            else:
                archived_count = 0
            
            return {
                'success': True,
                'campaigns_archived': archived_count,
                'cutoff_date': cutoff_date.isoformat(),
                'timestamp': utc_now().isoformat()
            }
            
    except Exception as e:
        logger.error(f"Error archiving old campaigns: {e}")
        return {
            'success': False,
            'error': str(e),
            'campaigns_archived': 0
        }


@celery.task(name='reschedule_failed_campaigns')
def reschedule_failed_campaigns() -> Dict[str, Any]:
    """
    Reschedule campaigns that failed to execute.
    
    Returns:
        Dict with reschedule counts
    """
    try:
        app = create_app()
        with app.app_context():
            scheduling_service = app.services.get('campaign_scheduling')
            campaign_repository = app.services.get('campaign_repository')
            
            if not scheduling_service or not campaign_repository:
                raise ValueError("Required services not found")
            
            # Find scheduled campaigns that are past their time but not running
            current_time = utc_now()
            stale_campaigns = campaign_repository.session.query(Campaign).filter(
                Campaign.status == 'scheduled',
                Campaign.scheduled_at < current_time - timedelta(minutes=30),
                Campaign.archived == False
            ).all()
            
            rescheduled_count = 0
            for campaign in stale_campaigns:
                # Reschedule for 5 minutes from now
                new_time = current_time + timedelta(minutes=5)
                result = scheduling_service.update_schedule(
                    campaign.id,
                    new_time,
                    campaign.timezone
                )
                
                if result.is_success:
                    rescheduled_count += 1
                    logger.info(f"Rescheduled campaign {campaign.id} to {new_time}")
            
            return {
                'success': True,
                'campaigns_found': len(stale_campaigns),
                'campaigns_rescheduled': rescheduled_count,
                'timestamp': current_time.isoformat()
            }
            
    except Exception as e:
        logger.error(f"Error rescheduling failed campaigns: {e}")
        return {
            'success': False,
            'error': str(e),
            'campaigns_found': 0,
            'campaigns_rescheduled': 0
        }


@celery.task(name='bulk_schedule_campaigns')
def bulk_schedule_campaigns(campaign_ids: List[int], scheduled_at: str, timezone: str = 'UTC') -> Dict[str, Any]:
    """
    Bulk schedule multiple campaigns at once.
    
    Args:
        campaign_ids: List of campaign IDs to schedule
        scheduled_at: ISO format datetime string
        timezone: Timezone for scheduling
        
    Returns:
        Dict with bulk scheduling results
    """
    try:
        app = create_app()
        with app.app_context():
            scheduling_service = app.services.get('campaign_scheduling')
            
            if not scheduling_service:
                raise ValueError("Campaign scheduling service not found")
            
            # Parse datetime
            scheduled_datetime = datetime.fromisoformat(scheduled_at.replace('Z', '+00:00'))
            
            # Call service method
            result = scheduling_service.bulk_schedule_campaigns(
                campaign_ids, scheduled_datetime, timezone
            )
            
            if result.is_success:
                data = result.data
                return {
                    'success': True,
                    'campaigns_scheduled': data['campaigns_scheduled'],
                    'failed_campaigns': data.get('failed_campaigns', []),
                    'timestamp': utc_now().isoformat()
                }
            else:
                raise ValueError(result.error)
                
    except Exception as e:
        logger.error(f"Error bulk scheduling campaigns: {e}")
        return {
            'success': False,
            'error': str(e),
            'campaigns_scheduled': 0,
            'failed_campaigns': campaign_ids
        }


@celery.task(name='periodic_schedule_maintenance')
def periodic_schedule_maintenance() -> Dict[str, Any]:
    """
    Perform periodic maintenance on campaign schedules.
    
    Returns:
        Dict with maintenance results
    """
    try:
        app = create_app()
        with app.app_context():
            scheduling_service = app.services.get('campaign_scheduling')
            
            if not scheduling_service:
                raise ValueError("Campaign scheduling service not found")
            
            # Perform maintenance operations
            failed_cleaned = scheduling_service.cleanup_failed_schedules()
            overdue_updated = scheduling_service.update_overdue_schedules()
            patterns_fixed = scheduling_service.validate_recurring_patterns()
            
            return {
                'success': True,
                'failed_schedules_cleaned': failed_cleaned,
                'overdue_schedules_updated': overdue_updated,
                'recurring_patterns_fixed': patterns_fixed,
                'timestamp': utc_now().isoformat()
            }
            
    except Exception as e:
        logger.error(f"Error performing schedule maintenance: {e}")
        return {
            'success': False,
            'error': str(e),
            'failed_schedules_cleaned': 0,
            'overdue_schedules_updated': 0,
            'recurring_patterns_fixed': 0
        }


@celery.task(name='schedule_campaign_with_validation')
def schedule_campaign_with_validation(campaign_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Schedule a campaign with business rules validation.
    
    Args:
        campaign_data: Dict containing campaign_id, scheduled_at, timezone, validate_business_hours
        
    Returns:
        Dict with scheduling result and warnings
    """
    try:
        app = create_app()
        with app.app_context():
            scheduling_service = app.services.get('campaign_scheduling')
            
            if not scheduling_service:
                raise ValueError("Campaign scheduling service not found")
            
            # Parse scheduled time
            scheduled_at = datetime.fromisoformat(
                campaign_data['scheduled_at'].replace('Z', '+00:00')
            )
            
            # Call service method with validation
            result = scheduling_service.schedule_campaign_with_validation(
                campaign_data
            )
            
            if result.is_success:
                data = result.data
                return {
                    'success': True,
                    'campaign_id': data['campaign_id'],
                    'scheduled': data['scheduled'],
                    'warnings': data.get('warnings', []),
                    'timestamp': utc_now().isoformat()
                }
            else:
                raise ValueError(result.error)
                
    except Exception as e:
        logger.error(f"Error scheduling campaign with validation: {e}")
        return {
            'success': False,
            'error': str(e),
            'campaign_id': campaign_data.get('campaign_id'),
            'scheduled': False,
            'warnings': []        }


# Import Campaign model for tasks
from crm_database import Campaign