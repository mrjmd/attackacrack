"""
Campaign Scheduling Service - Phase 3C
Handles campaign scheduling, recurring campaigns, and timezone-aware execution
"""

import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, TYPE_CHECKING
from zoneinfo import ZoneInfo

from repositories.campaign_repository import CampaignRepository
from repositories.activity_repository import ActivityRepository
from services.common.result import Result
from utils.datetime_utils import utc_now

if TYPE_CHECKING:
    from crm_database import Campaign, Activity

logger = logging.getLogger(__name__)


class CampaignSchedulingService:
    """Service for managing campaign scheduling and recurring campaigns"""
    
    def __init__(self, campaign_repository: CampaignRepository, activity_repository: ActivityRepository):
        """Initialize with repository dependencies"""
        self.campaign_repository = campaign_repository
        self.activity_repository = activity_repository
        
    def schedule_campaign(self, campaign_id: int, scheduled_at: datetime, timezone: str = "UTC") -> Result:
        """
        Schedule a campaign for future execution
        
        Args:
            campaign_id: ID of campaign to schedule
            scheduled_at: When to run the campaign (can be timezone-aware or naive)
            timezone: Timezone for scheduling (default UTC)
            
        Returns:
            Result with scheduled campaign or error
        """
        try:
            # Validate timezone first
            try:
                tz = ZoneInfo(timezone)
            except Exception:
                return Result.failure(f"Invalid timezone: {timezone}")
            
            # Get campaign
            campaign = self.campaign_repository.get_by_id(campaign_id)
            if not campaign:
                return Result.failure(f"Campaign {campaign_id} not found")
                
            # Validate campaign can be scheduled
            if campaign.status not in ['draft', 'scheduled']:
                return Result.failure(f"Cannot schedule campaign in status {campaign.status}")
                
            # Convert to UTC if needed
            if scheduled_at.tzinfo is None:
                # Naive datetime - treat as being in the specified timezone
                scheduled_at = scheduled_at.replace(tzinfo=tz)
                
            # Convert to naive UTC datetime for database storage
            utc_scheduled = scheduled_at.astimezone(ZoneInfo("UTC")).replace(tzinfo=None) if scheduled_at.tzinfo else scheduled_at
            
            # Validate not in the past
            current_time = utc_now().replace(tzinfo=None)
            if utc_scheduled < current_time:
                return Result.failure("Cannot schedule campaign in the past")
                
            # Update campaign - store naive UTC datetime
            campaign.status = "scheduled"
            campaign.scheduled_at = utc_scheduled
            campaign.timezone = timezone
            campaign.next_run_at = utc_scheduled  # For recurring campaigns
            
            # Commit changes
            self.campaign_repository.commit()
            
            # TODO: Log activity when Activity model fields are finalized
            
            return Result.success(campaign)
            
        except Exception as e:
            logger.error(f"Error scheduling campaign {campaign_id}: {e}")
            return Result.failure(str(e))
            
    def create_recurring_campaign(self, campaign_id: int, start_at: datetime, 
                                recurrence_pattern: Dict[str, Any], timezone: str = "UTC") -> Result:
        """
        Create a recurring campaign with the specified pattern
        
        Args:
            campaign_id: ID of campaign to make recurring
            start_at: When to first run the campaign
            recurrence_pattern: Dict with recurrence configuration
            timezone: Timezone for scheduling
            
        Returns:
            Result with recurring campaign or error
        """
        try:
            # Get campaign
            campaign = self.campaign_repository.get_by_id(campaign_id)
            if not campaign:
                return Result.failure(f"Campaign {campaign_id} not found")
                
            # Validate campaign can be scheduled
            if campaign.status not in ['draft', 'scheduled']:
                return Result.failure(f"Cannot schedule campaign in status {campaign.status}")
                
            # For recurring campaigns, preserve timezone-aware datetimes
            # Convert to timezone-aware UTC if needed
            if start_at.tzinfo is None:
                tz = ZoneInfo(timezone)
                start_at = start_at.replace(tzinfo=tz)
            utc_start = start_at.astimezone(ZoneInfo("UTC"))
            
            # Validate not in the past
            current_time = utc_now()
            if utc_start < current_time:
                return Result.failure("Cannot schedule campaign in the past")
                
            # Validate end date for recurring campaigns
            if 'end_date' in recurrence_pattern:
                end_date_str = recurrence_pattern['end_date']
                try:
                    end_date = datetime.fromisoformat(end_date_str)
                    if end_date.tzinfo is None:
                        end_date = end_date.replace(tzinfo=ZoneInfo(timezone))
                    if end_date <= current_time:
                        return Result.failure("End date must be in the future")
                except (ValueError, TypeError):
                    return Result.failure("Invalid end date format")
                
            # Update campaign directly (not through schedule_campaign to preserve timezone-aware)
            campaign.status = "scheduled"
            campaign.scheduled_at = utc_start  # Keep timezone-aware for recurring
            campaign.timezone = timezone
            campaign.is_recurring = True
            campaign.recurrence_pattern = recurrence_pattern
            campaign.next_run_at = utc_start  # Initial next_run_at same as scheduled_at
                
            self.campaign_repository.commit()
            
            return Result.success(campaign)
            
        except Exception as e:
            logger.error(f"Error creating recurring campaign {campaign_id}: {e}")
            return Result.failure(str(e))
            
    def calculate_next_run(self, current_run: datetime, pattern: Dict[str, Any], 
                          timezone: str = "UTC") -> Optional[datetime]:
        """
        Calculate the next run time for a recurring campaign
        
        Args:
            current_run: Current/last run datetime
            pattern: Recurrence pattern configuration
            timezone: Campaign timezone
            
        Returns:
            Next run datetime in UTC or None if no more runs
        """
        try:
            # Ensure current_run is timezone-aware
            if current_run.tzinfo is None:
                current_run = current_run.replace(tzinfo=ZoneInfo("UTC"))
                
            # Check end date
            if 'end_date' in pattern:
                end_date = datetime.fromisoformat(pattern['end_date'])
                if end_date.tzinfo is None:
                    end_date = end_date.replace(tzinfo=ZoneInfo(timezone))
                if current_run >= end_date:
                    return None
                    
            # Calculate based on pattern type
            pattern_type = pattern.get('type', 'daily')
            interval = pattern.get('interval', 1)
            
            if pattern_type == 'daily':
                next_run = current_run + timedelta(days=interval)
                
            elif pattern_type == 'weekly':
                # For weekly, check specific days of week if provided
                days_of_week = pattern.get('days_of_week', [])
                if days_of_week:
                    # Find next matching day
                    next_run = current_run + timedelta(days=1)
                    while next_run.weekday() not in days_of_week:
                        next_run += timedelta(days=1)
                else:
                    # Simple weekly interval
                    next_run = current_run + timedelta(weeks=interval)
                    
            elif pattern_type == 'monthly':
                # Simple month addition (could be enhanced)
                # Add roughly 30 days * interval
                next_run = current_run + timedelta(days=30 * interval)
                
            else:
                logger.warning(f"Unknown recurrence pattern type: {pattern_type}")
                return None
                
            # Keep timezone-aware for consistency with tests
            return next_run.astimezone(ZoneInfo("UTC"))
            
        except Exception as e:
            logger.error(f"Error calculating next run: {e}")
            return None
            
    def duplicate_campaign(self, campaign_id: int, new_name: Optional[str] = None) -> Result:
        """
        Duplicate a campaign for reuse
        
        Args:
            campaign_id: ID of campaign to duplicate
            new_name: Optional name for the duplicate
            
        Returns:
            Result with duplicated campaign or error
        """
        try:
            # Get original campaign
            original = self.campaign_repository.get_by_id(campaign_id)
            if not original:
                return Result.failure(f"Campaign {campaign_id} not found")
                
            # Create duplicate data
            duplicate_data = {
                "name": new_name or f"{original.name} (Copy)",
                "status": "draft",
                "template_a": original.template_a,
                "template_b": original.template_b,
                "quiet_hours_start": original.quiet_hours_start,
                "quiet_hours_end": original.quiet_hours_end,
                "on_existing_contact": original.on_existing_contact,
                "campaign_type": original.campaign_type,
                "audience_type": original.audience_type,
                "daily_limit": original.daily_limit,
                "business_hours_only": original.business_hours_only,
                "ab_config": original.ab_config,
                "channel": original.channel,
                "list_id": original.list_id,
                "adapt_script_template": original.adapt_script_template,
                "days_between_contacts": original.days_between_contacts,
                "parent_campaign_id": original.id,
                "timezone": original.timezone
            }
            
            created_campaign = self.campaign_repository.create(**duplicate_data)
            self.campaign_repository.commit()
            
            return Result.success({"campaign_id": created_campaign.id, "campaign": created_campaign})
            
        except Exception as e:
            logger.error(f"Error duplicating campaign {campaign_id}: {e}")
            return Result.failure(str(e))
            
    def archive_campaign(self, campaign_id: int, reason: Optional[str] = None) -> Result:
        """
        Archive a campaign
        
        Args:
            campaign_id: ID of campaign to archive
            reason: Optional reason for archiving
            
        Returns:
            Result with success or error
        """
        try:
            campaign = self.campaign_repository.get_by_id(campaign_id)
            if not campaign:
                return Result.failure(f"Campaign {campaign_id} not found")
                
            campaign.archived = True
            campaign.archived_at = utc_now()
            
            # Log activity
            activity_data = {
                "type": "campaign_archived",
                "campaign_id": campaign_id,
                "notes": reason or f"Campaign '{campaign.name}' archived",
                "created_at": utc_now()
            }
            self.activity_repository.create(**activity_data)
            
            self.campaign_repository.commit()
            
            return Result.success(campaign)
            
        except Exception as e:
            logger.error(f"Error archiving campaign {campaign_id}: {e}")
            return Result.failure(str(e))
            
    def unarchive_campaign(self, campaign_id: int) -> Result:
        """
        Unarchive a campaign
        
        Args:
            campaign_id: ID of campaign to unarchive
            
        Returns:
            Result with success or error
        """
        try:
            campaign = self.campaign_repository.get_by_id(campaign_id)
            if not campaign:
                return Result.failure(f"Campaign {campaign_id} not found")
                
            campaign.archived = False
            campaign.archived_at = None
            
            self.campaign_repository.commit()
            
            return Result.success(campaign)
            
        except Exception as e:
            logger.error(f"Error unarchiving campaign {campaign_id}: {e}")
            return Result.failure(str(e))
            
    def get_scheduled_campaigns(self, include_archived: bool = False) -> List['Campaign']:
        """
        Get all scheduled campaigns
        
        Args:
            include_archived: Whether to include archived campaigns
            
        Returns:
            List of scheduled campaigns
        """
        try:
            campaigns = self.campaign_repository.find_scheduled_campaigns()
            
            if not include_archived:
                campaigns = [c for c in campaigns if not c.archived]
                
            return campaigns
            
        except Exception as e:
            logger.error(f"Error getting scheduled campaigns: {e}")
            return []
            
    def get_campaigns_ready_to_run(self, current_time: Optional[datetime] = None) -> List['Campaign']:
        """
        Get campaigns that are ready to execute
        
        Args:
            current_time: Time to check against (default: now)
            
        Returns:
            List of campaigns ready to run
        """
        try:
            if current_time is None:
                current_time = utc_now()
                
            return self.campaign_repository.find_scheduled_campaigns_ready_to_run(current_time)
            
        except Exception as e:
            logger.error(f"Error getting campaigns ready to run: {e}")
            return []
            
    def cancel_schedule(self, campaign_id: int) -> Result:
        """
        Cancel a scheduled campaign
        
        Args:
            campaign_id: ID of campaign to cancel
            
        Returns:
            Result with success or error
        """
        try:
            campaign = self.campaign_repository.get_by_id(campaign_id)
            if not campaign:
                return Result.failure(f"Campaign {campaign_id} not found")
                
            if campaign.status != "scheduled":
                return Result.failure(f"Campaign is not scheduled (status: {campaign.status})")
                
            # Reset to draft
            campaign.status = "draft"
            campaign.scheduled_at = None
            campaign.next_run_at = None
            campaign.is_recurring = False
            campaign.recurrence_pattern = None
            
            self.campaign_repository.commit()
            
            return Result.success(campaign)
            
        except Exception as e:
            logger.error(f"Error cancelling schedule for campaign {campaign_id}: {e}")
            return Result.failure(str(e))
            
    def update_schedule(self, campaign_id: int, scheduled_at: datetime, 
                       timezone: Optional[str] = None) -> Result:
        """
        Update the schedule for a campaign
        
        Args:
            campaign_id: ID of campaign to update
            scheduled_at: New scheduled time
            timezone: Optional new timezone
            
        Returns:
            Result with updated campaign or error
        """
        try:
            campaign = self.campaign_repository.get_by_id(campaign_id)
            if not campaign:
                return Result.failure(f"Campaign {campaign_id} not found")
                
            if campaign.status != "scheduled":
                return Result.failure(f"Campaign is not scheduled (status: {campaign.status})")
                
            # Use existing timezone if not provided
            if timezone is None:
                timezone = campaign.timezone or "UTC"
                
            # Reschedule
            return self.schedule_campaign(campaign_id, scheduled_at, timezone)
            
        except Exception as e:
            logger.error(f"Error updating schedule for campaign {campaign_id}: {e}")
            return Result.failure(str(e))
            
    def cancel_scheduled_campaign(self, campaign_id: int) -> Result:
        """Alias for cancel_schedule for backward compatibility"""
        return self.cancel_schedule(campaign_id)
    
    def get_campaign_schedule_info(self, campaign_id: int) -> Result:
        """
        Get schedule information for a campaign
        
        Args:
            campaign_id: ID of campaign
            
        Returns:
            Result with schedule info or error
        """
        try:
            campaign = self.campaign_repository.get_by_id(campaign_id)
            if not campaign:
                return Result.failure(f"Campaign {campaign_id} not found")
                
            info = {
                'campaign_id': campaign_id,
                'status': campaign.status,
                'scheduled_at': campaign.scheduled_at,
                'timezone': campaign.timezone,
                'is_recurring': campaign.is_recurring,
                'recurrence_pattern': campaign.recurrence_pattern,
                'next_run_at': campaign.next_run_at,
                'archived': campaign.archived,
                'is_scheduled': campaign.status == 'scheduled'
            }
            
            return Result.success(info)
            
        except Exception as e:
            logger.error(f"Error getting schedule info for campaign {campaign_id}: {e}")
            return Result.failure(str(e))
    
    def get_archived_campaigns(self, include_date_range: bool = False,
                              start_date: Optional[datetime] = None,
                              end_date: Optional[datetime] = None) -> List['Campaign']:
        """
        Get archived campaigns with optional date filtering
        
        Args:
            include_date_range: Whether to filter by date
            start_date: Start of date range
            end_date: End of date range
            
        Returns:
            List of archived campaigns
        """
        try:
            return self.campaign_repository.find_archived_campaigns(
                include_date_range, start_date, end_date
            )
        except Exception as e:
            logger.error(f"Error getting archived campaigns: {e}")
            return []
    
    def execute_campaign(self, campaign_id: int) -> Result:
        """
        Execute a scheduled campaign (called by background task)
        
        Args:
            campaign_id: ID of campaign to execute
            
        Returns:
            Result with execution status
        """
        try:
            campaign = self.campaign_repository.get_by_id(campaign_id)
            if not campaign:
                return Result.failure(f"Campaign {campaign_id} not found")
                
            # Update status to running
            campaign.status = "running"
            
            # If recurring, calculate next run
            if campaign.is_recurring and campaign.recurrence_pattern:
                current_scheduled = campaign.scheduled_at or utc_now()
                if hasattr(current_scheduled, 'tzinfo') and current_scheduled.tzinfo is None:
                    current_scheduled = current_scheduled.replace(tzinfo=ZoneInfo("UTC"))
                next_run = self.calculate_next_run(
                    current_scheduled,
                    campaign.recurrence_pattern,
                    campaign.timezone
                )
                if next_run:
                    campaign.next_run_at = next_run
                    # Don't change scheduled_at here - it will be updated after execution completes
                    # Status stays as "running" during execution
            else:
                # For non-recurring campaigns, clear the scheduled time
                campaign.scheduled_at = None
                    
            self.campaign_repository.commit()
            
            return Result.success({"campaign_id": campaign_id, "status": "executing"})
            
        except Exception as e:
            logger.error(f"Error executing campaign {campaign_id}: {e}")
            return Result.failure(str(e))
    
    def execute_scheduled_campaign(self, campaign_id: int) -> Result:
        """Alias for execute_campaign for backward compatibility"""
        return self.execute_campaign(campaign_id)
    
    def duplicate_campaign(self, campaign_id: int, new_name: str, 
                          scheduled_at: Optional[datetime] = None, 
                          timezone: str = "UTC") -> Result:
        """
        Duplicate a campaign with optional scheduling.
        
        Args:
            campaign_id: ID of campaign to duplicate
            new_name: Name for the duplicate
            scheduled_at: Optional scheduled time
            timezone: Timezone for scheduling
            
        Returns:
            Result with duplicate campaign data or error
        """
        if scheduled_at:
            return self.duplicate_campaign_with_schedule(campaign_id, new_name, scheduled_at, timezone)
        else:
            # Just duplicate without scheduling
            try:
                original = self.campaign_repository.get_by_id(campaign_id)
                if not original:
                    return Result.failure(f"Campaign {campaign_id} not found")
                
                duplicate_data = {
                    'name': new_name,
                    'campaign_type': original.campaign_type,
                    'template_a': original.template_a,
                    'template_b': original.template_b,
                    'daily_limit': original.daily_limit,
                    'business_hours_only': original.business_hours_only,
                    'audience_type': original.audience_type,
                    'channel': original.channel,
                    'parent_campaign_id': original.id,
                    'status': 'draft'
                }
                
                self.campaign_repository.create(duplicate_data)
                self.campaign_repository.commit()
                
                return Result.success(duplicate_data)
                
            except Exception as e:
                logger.error(f"Error duplicating campaign {campaign_id}: {e}")
                return Result.failure(str(e))
    
    def duplicate_campaign_with_schedule(self, campaign_id: int, new_name: str, 
                                        scheduled_at: datetime, timezone: str = "UTC") -> Result:
        """
        Duplicate a campaign and schedule it.
        
        Args:
            campaign_id: ID of campaign to duplicate
            new_name: Name for the duplicate
            scheduled_at: When to schedule the duplicate
            timezone: Timezone for scheduling
            
        Returns:
            Result with duplicate campaign ID or error
        """
        try:
            # Get original campaign
            original = self.campaign_repository.get_by_id(campaign_id)
            if not original:
                return Result.failure(f"Campaign {campaign_id} not found")
            
            # Create duplicate
            duplicate_data = {
                'name': new_name,
                'campaign_type': original.campaign_type,
                'template_a': original.template_a,
                'template_b': original.template_b,
                'daily_limit': original.daily_limit,
                'business_hours_only': original.business_hours_only,
                'audience_type': original.audience_type,
                'channel': original.channel,
                'parent_campaign_id': original.id,
                'status': 'scheduled',
                'scheduled_at': scheduled_at,
                'timezone': timezone
            }
            
            from crm_database import Campaign
            duplicate = Campaign(**duplicate_data)
            self.campaign_repository.create(duplicate)
            self.campaign_repository.commit()
            
            # Copy memberships if any
            if original.memberships:
                from crm_database import CampaignMembership
                for membership in original.memberships:
                    new_membership = CampaignMembership(
                        campaign_id=duplicate.id,
                        contact_id=membership.contact_id,
                        status='pending'
                    )
                    self.campaign_repository.session.add(new_membership)
                self.campaign_repository.commit()
            
            return Result.success({
                'campaign_id': duplicate.id,
                'name': duplicate.name,
                'scheduled_at': duplicate.scheduled_at,
                'parent_campaign_id': original.id
            })
            
        except Exception as e:
            logger.error(f"Error duplicating campaign {campaign_id}: {e}")
            return Result.failure(str(e))
    
    def bulk_schedule_campaigns(self, campaign_ids: List[int], 
                               scheduled_at: datetime, timezone: str = "UTC") -> Result:
        """
        Schedule multiple campaigns at once.
        
        Args:
            campaign_ids: List of campaign IDs
            scheduled_at: When to schedule them
            timezone: Timezone for scheduling
            
        Returns:
            Result with scheduling results
        """
        try:
            scheduled_count = 0
            failed_campaigns = []
            
            for campaign_id in campaign_ids:
                result = self.schedule_campaign(campaign_id, scheduled_at, timezone)
                if result.is_success():
                    scheduled_count += 1
                else:
                    failed_campaigns.append({
                        'campaign_id': campaign_id,
                        'error': result.error
                    })
            
            return Result.success({
                'campaigns_scheduled': scheduled_count,
                'failed_campaigns': failed_campaigns,
                'total_attempted': len(campaign_ids)
            })
            
        except Exception as e:
            logger.error(f"Error bulk scheduling campaigns: {e}")
            return Result.failure(str(e))
    
    def cleanup_failed_schedules(self) -> int:
        """
        Clean up failed campaign schedules.
        
        Returns:
            Number of schedules cleaned
        """
        try:
            # Find campaigns with status 'scheduled' but past their time
            current_time = utc_now()
            from crm_database import Campaign
            
            failed_campaigns = self.campaign_repository.session.query(Campaign).filter(
                Campaign.status == 'scheduled',
                Campaign.scheduled_at < current_time - timedelta(hours=24),
                Campaign.archived == False
            ).all()
            
            cleaned_count = 0
            for campaign in failed_campaigns:
                campaign.status = 'failed'
                campaign.scheduled_at = None
                cleaned_count += 1
                logger.info(f"Cleaned up failed schedule for campaign {campaign.id}")
            
            if cleaned_count > 0:
                self.campaign_repository.commit()
            
            return cleaned_count
            
        except Exception as e:
            logger.error(f"Error cleaning up failed schedules: {e}")
            return 0
    
    def update_overdue_schedules(self) -> int:
        """
        Update schedules that are overdue.
        
        Returns:
            Number of schedules updated
        """
        try:
            current_time = utc_now()
            from crm_database import Campaign
            
            # Find overdue scheduled campaigns
            overdue_campaigns = self.campaign_repository.session.query(Campaign).filter(
                Campaign.status == 'scheduled',
                Campaign.scheduled_at < current_time,
                Campaign.scheduled_at >= current_time - timedelta(hours=24),
                Campaign.archived == False
            ).all()
            
            updated_count = 0
            for campaign in overdue_campaigns:
                # Reschedule for next available slot
                new_time = current_time + timedelta(minutes=30)
                campaign.scheduled_at = new_time
                updated_count += 1
                logger.info(f"Updated overdue schedule for campaign {campaign.id} to {new_time}")
            
            if updated_count > 0:
                self.campaign_repository.commit()
            
            return updated_count
            
        except Exception as e:
            logger.error(f"Error updating overdue schedules: {e}")
            return 0
    
    def validate_recurring_patterns(self) -> int:
        """
        Validate and fix recurring patterns.
        
        Returns:
            Number of patterns fixed
        """
        try:
            from crm_database import Campaign
            
            # Find campaigns with recurring patterns
            recurring_campaigns = self.campaign_repository.session.query(Campaign).filter(
                Campaign.is_recurring == True,
                Campaign.recurrence_pattern != None
            ).all()
            
            fixed_count = 0
            for campaign in recurring_campaigns:
                pattern = campaign.recurrence_pattern
                if pattern:
                    # Validate pattern structure
                    if not isinstance(pattern, dict):
                        campaign.is_recurring = False
                        campaign.recurrence_pattern = None
                        fixed_count += 1
                        logger.warning(f"Fixed invalid pattern for campaign {campaign.id}")
                    elif 'type' not in pattern or 'interval' not in pattern:
                        campaign.is_recurring = False
                        campaign.recurrence_pattern = None
                        fixed_count += 1
                        logger.warning(f"Fixed incomplete pattern for campaign {campaign.id}")
                    elif pattern.get('type') not in ['daily', 'weekly', 'monthly']:
                        campaign.is_recurring = False
                        campaign.recurrence_pattern = None
                        fixed_count += 1
                        logger.warning(f"Fixed invalid pattern type for campaign {campaign.id}")
            
            if fixed_count > 0:
                self.campaign_repository.commit()
            
            return fixed_count
            
        except Exception as e:
            logger.error(f"Error validating recurring patterns: {e}")
            return 0
    
    def schedule_campaign_with_validation(self, campaign_data: Dict[str, Any]) -> Result:
        """
        Schedule a campaign with business rules validation.
        
        Args:
            campaign_data: Dict with campaign_id, scheduled_at, timezone, validate_business_hours
            
        Returns:
            Result with scheduling result and warnings
        """
        try:
            campaign_id = campaign_data['campaign_id']
            scheduled_at = datetime.fromisoformat(
                campaign_data['scheduled_at'].replace('Z', '+00:00')
            )
            timezone = campaign_data.get('timezone', 'UTC')
            validate_business_hours = campaign_data.get('validate_business_hours', False)
            
            warnings = []
            
            # Validate business hours if requested
            if validate_business_hours:
                from zoneinfo import ZoneInfo
                local_time = scheduled_at.astimezone(ZoneInfo(timezone))
                hour = local_time.hour
                weekday = local_time.weekday()
                
                # Check if outside business hours (9 AM - 6 PM, Mon-Fri)
                if hour < 9 or hour >= 18:
                    warnings.append("Outside business hours")
                if weekday >= 5:  # Saturday = 5, Sunday = 6
                    warnings.append("Scheduled for weekend")
            
            # Schedule the campaign
            result = self.schedule_campaign(campaign_id, scheduled_at, timezone)
            
            if result.is_success():
                return Result.success({
                    'campaign_id': campaign_id,
                    'scheduled': True,
                    'warnings': warnings
                })
            else:
                return Result.failure(result.error)
                
        except Exception as e:
            logger.error(f"Error scheduling campaign with validation: {e}")
            return Result.failure(str(e))
    
    def get_campaign_calendar(self, start_date: datetime, end_date: datetime, 
                             timezone: str = "UTC") -> Result:
        """
        Get campaigns scheduled within a date range for calendar view.
        
        Args:
            start_date: Start of date range
            end_date: End of date range
            timezone: Timezone for display
            
        Returns:
            Result with list of campaign calendar events
        """
        try:
            from crm_database import Campaign
            from zoneinfo import ZoneInfo
            
            # Ensure dates are timezone-aware
            if start_date.tzinfo is None:
                start_date = start_date.replace(tzinfo=ZoneInfo("UTC"))
            if end_date.tzinfo is None:
                end_date = end_date.replace(tzinfo=ZoneInfo("UTC"))
            
            # Query campaigns in date range
            campaigns = self.campaign_repository.session.query(Campaign).filter(
                Campaign.scheduled_at >= start_date,
                Campaign.scheduled_at <= end_date,
                Campaign.status.in_(['scheduled', 'running'])
            ).order_by(Campaign.scheduled_at).all()
            
            # Format for calendar display
            calendar_events = []
            for campaign in campaigns:
                # Convert to requested timezone
                local_time = campaign.scheduled_at
                if local_time and timezone != "UTC":
                    if local_time.tzinfo is None:
                        local_time = local_time.replace(tzinfo=ZoneInfo("UTC"))
                    local_time = local_time.astimezone(ZoneInfo(timezone))
                
                calendar_events.append({
                    'id': campaign.id,
                    'title': campaign.name,
                    'start': local_time.isoformat() if local_time else None,
                    'status': campaign.status,
                    'is_recurring': campaign.is_recurring,
                    'color': '#4CAF50' if campaign.status == 'scheduled' else '#2196F3'
                })
            
            return Result.success(calendar_events)
            
        except Exception as e:
            logger.error(f"Error getting campaign calendar: {e}")
            return Result.failure(str(e))