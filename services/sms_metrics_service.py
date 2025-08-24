"""
SMS Metrics and Bounce Tracking Service
Tracks delivery rates, bounce rates, and message performance
"""
from datetime import datetime, timedelta
from utils.datetime_utils import utc_now
from typing import Dict, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)

class SMSMetricsService:
    """Service for tracking SMS delivery metrics and bounce rates"""
    
    # Message status categories
    STATUS_CATEGORIES = {
        'delivered': ['delivered', 'sent', 'received'],
        'bounced': ['failed', 'undelivered', 'rejected', 'blocked'],
        'pending': ['queued', 'sending', 'pending'],
        'error': ['error', 'invalid', 'expired']
    }
    
    # Bounce type classifications
    BOUNCE_TYPES = {
        'hard': ['invalid_number', 'disconnected', 'does_not_exist', 'blacklisted'],
        'soft': ['temporary_failure', 'carrier_issue', 'network_error', 'timeout'],
        'carrier_rejection': ['spam_detected', 'content_violation', 'blocked', 'filtered'],
        'capability': ['landline', 'voip_unsupported', 'not_sms_capable']
    }
    
    def __init__(self, activity_repository, contact_repository, campaign_repository):
        """Initialize SMS Metrics Service with repository dependencies"""
        self.activity_repository = activity_repository
        self.contact_repository = contact_repository
        self.campaign_repository = campaign_repository
        
        self.bounce_threshold_warning = 3.0  # 3% triggers warning
        self.bounce_threshold_critical = 5.0  # 5% triggers critical alert
    
    def track_message_status(self, activity_id: int, status: str, 
                            status_details: Optional[str] = None) -> Dict:
        """
        Track the status of a sent message
        
        Args:
            activity_id: ID of the Activity record
            status: Message status (delivered, failed, etc.)
            status_details: Additional details about the status
        
        Returns:
            Dict with tracking results
        """
        try:
            activity = self.activity_repository.get_by_id(activity_id)
            if not activity:
                return {'error': 'Activity not found'}
            
            # Store bounce details if failed
            bounce_type = None
            if status in self.STATUS_CATEGORIES['bounced']:
                bounce_type = self._classify_bounce(status_details)
                bounce_metadata = {
                    'bounce_type': bounce_type,
                    'bounce_details': status_details,
                    'bounced_at': utc_now().isoformat()
                }
                
                # Update activity status and metadata via repository
                self.activity_repository.update_activity_status_with_metadata(
                    activity_id=activity_id,
                    status=status,
                    metadata=bounce_metadata
                )
                
                # Mark contact as having bounce issues
                if activity.contact_id:
                    self._update_contact_bounce_status(activity.contact_id, bounce_type)
            else:
                # Just update status without metadata
                self.activity_repository.update_activity_status_with_metadata(
                    activity_id=activity_id,
                    status=status,
                    metadata={}
                )
            
            return {
                'status': 'tracked',
                'activity_id': activity_id,
                'message_status': status,
                'bounce_type': bounce_type
            }
            
        except Exception as e:
            logger.error(f"Error tracking message status: {str(e)}")
            return {'error': str(e)}
    
    def _classify_bounce(self, status_details: Optional[str]) -> str:
        """Classify bounce type based on status details"""
        if not status_details:
            return 'unknown'
        
        status_lower = status_details.lower()
        
        for bounce_type, keywords in self.BOUNCE_TYPES.items():
            for keyword in keywords:
                if keyword in status_lower:
                    return bounce_type
        
        return 'unknown'
    
    def _update_contact_bounce_status(self, contact_id: int, bounce_type: str):
        """Update contact record with bounce information using repository"""
        bounce_info = {
            'bounce_type': bounce_type,
            'bounce_details': f'Bounce type: {bounce_type}',
            'bounced_at': utc_now().isoformat()
        }
        
        self.contact_repository.update_contact_bounce_status(
            contact_id=contact_id,
            bounce_info=bounce_info
        )
            
            # The repository method handles marking contacts as invalid
    
    def get_campaign_metrics(self, campaign_id: int) -> Dict:
        """
        Get comprehensive metrics for a campaign
        
        Returns:
            Dict with sent, delivered, bounced, bounce_rate, etc.
        """
        try:
            # Use campaign repository to get comprehensive metrics
            return self.campaign_repository.get_campaign_metrics_with_bounce_analysis(campaign_id)
            
        except Exception as e:
            logger.error(f"Error getting campaign metrics: {str(e)}")
            return {'error': str(e)}
    
    def get_global_metrics(self, days: int = 30) -> Dict:
        """
        Get global SMS metrics across all campaigns
        
        Args:
            days: Number of days to look back
        
        Returns:
            Dict with overall metrics
        """
        try:
            # Use activity repository to get daily stats
            daily_stats = self.activity_repository.get_daily_message_stats(days=days)
            
            # Calculate global metrics from daily stats
            total_sent = sum(day['sent'] for day in daily_stats)
            total_bounced = sum(day['bounced'] for day in daily_stats)
            
            metrics = {
                'period_days': days,
                'total_sent': total_sent,
                'delivered': total_sent - total_bounced,  # Approximation
                'bounced': total_bounced,
                'pending': 0,  # Not tracked in daily stats
                'bounce_rate': (total_bounced / total_sent * 100) if total_sent > 0 else 0.0,
                'delivery_rate': ((total_sent - total_bounced) / total_sent * 100) if total_sent > 0 else 0.0,
                'daily_average': total_sent / days if days > 0 else 0.0,
                'bounce_trends': daily_stats,
                'top_bounce_reasons': {}  # Could be enhanced with repository method
            }
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error getting global metrics: {str(e)}")
            return {'error': str(e)}
    
    def get_contact_sms_history(self, contact_id: int) -> Dict:
        """
        Get SMS history and metrics for a specific contact
        
        Returns:
            Dict with contact's SMS history and bounce information
        """
        try:
            # Use repositories to get contact and message data
            contact = self.contact_repository.get_by_id(contact_id)
            if not contact:
                return {'error': 'Contact not found'}
            
            # Get message summary from activity repository
            message_summary = self.activity_repository.get_contact_message_summary(contact_id)
            
            # Combine data from contact and message summary
            bounce_info = contact.contact_metadata.get('bounce_info', {}) if contact.contact_metadata else {}
            sms_valid = not (contact.contact_metadata or {}).get('sms_invalid', False)
            
            return {
                'contact_id': contact_id,
                'phone': contact.phone,
                'total_messages': message_summary['total_messages'],
                'sent_count': message_summary['sent_count'],
                'received_count': message_summary['received_count'],
                'delivered_count': message_summary['delivered_count'],
                'bounced_count': message_summary['bounced_count'],
                'bounce_info': bounce_info,
                'sms_valid': sms_valid,
                'recent_messages': message_summary['recent_messages'],
                'delivery_rate': (message_summary['delivered_count'] / message_summary['sent_count'] * 100) if message_summary['sent_count'] > 0 else 100,
                'reliability_score': self.contact_repository.get_contact_reliability_score(contact_id)
            }
            
        except Exception as e:
            logger.error(f"Error getting contact SMS history: {str(e)}")
            return {'error': str(e)}
    
    def identify_problematic_numbers(self, bounce_threshold: int = 2) -> List[Dict]:
        """
        Identify phone numbers with high bounce rates
        
        Args:
            bounce_threshold: Number of bounces to consider problematic
        
        Returns:
            List of problematic contacts with bounce details
        """
        try:
            # Use contact repository to find problematic numbers
            return self.contact_repository.find_problematic_numbers(bounce_threshold=bounce_threshold)
            
        except Exception as e:
            logger.error(f"Error identifying problematic numbers: {str(e)}")
            return []