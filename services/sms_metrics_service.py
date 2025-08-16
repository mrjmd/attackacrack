"""
SMS Metrics and Bounce Tracking Service
Tracks delivery rates, bounce rates, and message performance
"""
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from sqlalchemy import func, and_, or_
from crm_database import db, Activity, Campaign, CampaignMembership, Contact
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
    
    def __init__(self):
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
            activity = Activity.query.get(activity_id)
            if not activity:
                return {'error': 'Activity not found'}
            
            # Update activity status
            activity.status = status
            activity.updated_at = datetime.utcnow()
            
            # Store bounce details if failed
            if status in self.STATUS_CATEGORIES['bounced']:
                bounce_type = self._classify_bounce(status_details)
                activity.metadata = activity.metadata or {}
                activity.metadata.update({
                    'bounce_type': bounce_type,
                    'bounce_details': status_details,
                    'bounced_at': datetime.utcnow().isoformat()
                })
                
                # Mark contact as having bounce issues
                if activity.contact_id:
                    self._update_contact_bounce_status(activity.contact_id, bounce_type)
            
            db.session.commit()
            
            return {
                'status': 'tracked',
                'activity_id': activity_id,
                'message_status': status,
                'bounce_type': bounce_type if status in self.STATUS_CATEGORIES['bounced'] else None
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
        """Update contact record with bounce information"""
        contact = Contact.query.get(contact_id)
        if contact:
            contact.metadata = contact.metadata or {}
            bounce_info = contact.metadata.get('bounce_info', {})
            
            # Track bounce counts by type
            bounce_counts = bounce_info.get('counts', {})
            bounce_counts[bounce_type] = bounce_counts.get(bounce_type, 0) + 1
            
            # Update bounce info
            bounce_info.update({
                'last_bounce': datetime.utcnow().isoformat(),
                'last_bounce_type': bounce_type,
                'counts': bounce_counts,
                'total_bounces': sum(bounce_counts.values())
            })
            
            contact.metadata['bounce_info'] = bounce_info
            
            # Mark as invalid if too many hard bounces
            if bounce_counts.get('hard', 0) >= 2:
                contact.metadata['sms_invalid'] = True
                contact.metadata['sms_invalid_reason'] = 'Multiple hard bounces'
    
    def get_campaign_metrics(self, campaign_id: int) -> Dict:
        """
        Get comprehensive metrics for a campaign
        
        Returns:
            Dict with sent, delivered, bounced, bounce_rate, etc.
        """
        try:
            # Get all campaign memberships
            memberships = CampaignMembership.query.filter_by(
                campaign_id=campaign_id
            ).all()
            
            metrics = {
                'total_contacts': len(memberships),
                'sent': 0,
                'delivered': 0,
                'bounced': 0,
                'pending': 0,
                'replied': 0,
                'opted_out': 0,
                'bounce_rate': 0.0,
                'delivery_rate': 0.0,
                'response_rate': 0.0,
                'bounce_breakdown': {
                    'hard': 0,
                    'soft': 0,
                    'carrier_rejection': 0,
                    'capability': 0,
                    'unknown': 0
                }
            }
            
            for membership in memberships:
                status = membership.status
                
                if status == 'sent':
                    metrics['sent'] += 1
                    
                    # Check actual delivery status from activity
                    if membership.sent_activity_id:
                        activity = Activity.query.get(membership.sent_activity_id)
                        if activity:
                            if activity.status in self.STATUS_CATEGORIES['delivered']:
                                metrics['delivered'] += 1
                            elif activity.status in self.STATUS_CATEGORIES['bounced']:
                                metrics['bounced'] += 1
                                # Track bounce type
                                bounce_type = (activity.metadata or {}).get('bounce_type', 'unknown')
                                metrics['bounce_breakdown'][bounce_type] += 1
                            elif activity.status in self.STATUS_CATEGORIES['pending']:
                                metrics['pending'] += 1
                
                elif status == 'failed':
                    metrics['bounced'] += 1
                elif status in ['replied_positive', 'replied_negative', 'replied_neutral']:
                    metrics['replied'] += 1
                    metrics['delivered'] += 1  # If they replied, it was delivered
                elif status == 'opted_out':
                    metrics['opted_out'] += 1
            
            # Calculate rates
            if metrics['sent'] > 0:
                metrics['bounce_rate'] = (metrics['bounced'] / metrics['sent']) * 100
                metrics['delivery_rate'] = (metrics['delivered'] / metrics['sent']) * 100
                metrics['response_rate'] = (metrics['replied'] / metrics['sent']) * 100
            
            # Add status indicator
            if metrics['bounce_rate'] > self.bounce_threshold_critical:
                metrics['status'] = 'critical'
                metrics['status_message'] = f"Critical: Bounce rate {metrics['bounce_rate']:.1f}% exceeds {self.bounce_threshold_critical}% threshold"
            elif metrics['bounce_rate'] > self.bounce_threshold_warning:
                metrics['status'] = 'warning'
                metrics['status_message'] = f"Warning: Bounce rate {metrics['bounce_rate']:.1f}% exceeds {self.bounce_threshold_warning}% threshold"
            else:
                metrics['status'] = 'healthy'
                metrics['status_message'] = f"Healthy: Bounce rate {metrics['bounce_rate']:.1f}% within acceptable limits"
            
            return metrics
            
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
            since_date = datetime.utcnow() - timedelta(days=days)
            
            # Query all message activities in timeframe
            messages = Activity.query.filter(
                and_(
                    Activity.activity_type == 'message',
                    Activity.direction == 'outgoing',
                    Activity.created_at >= since_date
                )
            ).all()
            
            metrics = {
                'period_days': days,
                'total_sent': len(messages),
                'delivered': 0,
                'bounced': 0,
                'pending': 0,
                'bounce_rate': 0.0,
                'delivery_rate': 0.0,
                'daily_average': 0.0,
                'bounce_trends': [],
                'top_bounce_reasons': {}
            }
            
            bounce_reasons = {}
            daily_stats = {}
            
            for message in messages:
                # Track daily stats
                date_key = message.created_at.date()
                if date_key not in daily_stats:
                    daily_stats[date_key] = {'sent': 0, 'bounced': 0}
                daily_stats[date_key]['sent'] += 1
                
                # Count by status
                if message.status in self.STATUS_CATEGORIES['delivered']:
                    metrics['delivered'] += 1
                elif message.status in self.STATUS_CATEGORIES['bounced']:
                    metrics['bounced'] += 1
                    daily_stats[date_key]['bounced'] += 1
                    
                    # Track bounce reasons
                    bounce_type = (message.metadata or {}).get('bounce_type', 'unknown')
                    bounce_reasons[bounce_type] = bounce_reasons.get(bounce_type, 0) + 1
                elif message.status in self.STATUS_CATEGORIES['pending']:
                    metrics['pending'] += 1
            
            # Calculate rates
            if metrics['total_sent'] > 0:
                metrics['bounce_rate'] = (metrics['bounced'] / metrics['total_sent']) * 100
                metrics['delivery_rate'] = (metrics['delivered'] / metrics['total_sent']) * 100
                metrics['daily_average'] = metrics['total_sent'] / days
            
            # Generate daily bounce trend
            for date in sorted(daily_stats.keys()):
                stats = daily_stats[date]
                bounce_rate = (stats['bounced'] / stats['sent'] * 100) if stats['sent'] > 0 else 0
                metrics['bounce_trends'].append({
                    'date': date.isoformat(),
                    'sent': stats['sent'],
                    'bounced': stats['bounced'],
                    'bounce_rate': bounce_rate
                })
            
            # Top bounce reasons
            metrics['top_bounce_reasons'] = dict(
                sorted(bounce_reasons.items(), key=lambda x: x[1], reverse=True)[:5]
            )
            
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
            contact = Contact.query.get(contact_id)
            if not contact:
                return {'error': 'Contact not found'}
            
            # Get all SMS activities for this contact
            messages = Activity.query.filter(
                and_(
                    Activity.contact_id == contact_id,
                    Activity.activity_type == 'message'
                )
            ).order_by(Activity.created_at.desc()).all()
            
            metrics = {
                'contact_id': contact_id,
                'phone': contact.phone,
                'total_messages': len(messages),
                'sent': 0,
                'received': 0,
                'delivered': 0,
                'bounced': 0,
                'bounce_info': contact.metadata.get('bounce_info', {}) if contact.metadata else {},
                'sms_valid': not (contact.metadata or {}).get('sms_invalid', False),
                'recent_messages': []
            }
            
            for message in messages:
                if message.direction == 'outgoing':
                    metrics['sent'] += 1
                    if message.status in self.STATUS_CATEGORIES['delivered']:
                        metrics['delivered'] += 1
                    elif message.status in self.STATUS_CATEGORIES['bounced']:
                        metrics['bounced'] += 1
                else:
                    metrics['received'] += 1
                
                # Add to recent messages (limit to 10)
                if len(metrics['recent_messages']) < 10:
                    metrics['recent_messages'].append({
                        'id': message.id,
                        'direction': message.direction,
                        'status': message.status,
                        'body': message.body[:100] if message.body else None,
                        'created_at': message.created_at.isoformat() if message.created_at else None
                    })
            
            # Calculate reliability score
            if metrics['sent'] > 0:
                metrics['delivery_rate'] = (metrics['delivered'] / metrics['sent']) * 100
                metrics['reliability_score'] = min(100, metrics['delivery_rate'])
            else:
                metrics['reliability_score'] = 100  # No sends, assume good
            
            return metrics
            
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
            # Query contacts with bounce metadata
            contacts = Contact.query.filter(
                Contact.metadata.contains('bounce_info')
            ).all()
            
            problematic = []
            
            for contact in contacts:
                bounce_info = (contact.metadata or {}).get('bounce_info', {})
                total_bounces = bounce_info.get('total_bounces', 0)
                
                if total_bounces >= bounce_threshold:
                    problematic.append({
                        'contact_id': contact.id,
                        'phone': contact.phone,
                        'name': contact.name,
                        'total_bounces': total_bounces,
                        'bounce_types': bounce_info.get('counts', {}),
                        'last_bounce': bounce_info.get('last_bounce'),
                        'sms_invalid': (contact.metadata or {}).get('sms_invalid', False)
                    })
            
            # Sort by total bounces descending
            problematic.sort(key=lambda x: x['total_bounces'], reverse=True)
            
            return problematic
            
        except Exception as e:
            logger.error(f"Error identifying problematic numbers: {str(e)}")
            return []