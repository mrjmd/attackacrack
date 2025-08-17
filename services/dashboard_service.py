"""
Dashboard Service
Handles all business logic for dashboard statistics and activity feeds
"""

from datetime import datetime, timedelta
from typing import Dict, List, Any
from sqlalchemy import func
from sqlalchemy.orm import selectinload, joinedload
from sqlalchemy import exists

from crm_database import (
    db, Contact, Campaign, CampaignMembership, 
    Activity, Conversation
)
from services.sms_metrics_service import SMSMetricsService


class DashboardService:
    """Service for dashboard data and statistics"""
    
    def __init__(self):
        self.metrics_service = SMSMetricsService()
    
    def get_dashboard_stats(self) -> Dict[str, Any]:
        """
        Get all dashboard statistics
        Returns dict with all stats for dashboard cards
        """
        stats = {}
        
        # Basic counts
        stats['contact_count'] = self._get_total_contacts()
        stats['contacts_added_this_week'] = self._get_contacts_added_this_week()
        stats['active_campaigns'] = self._get_active_campaigns()
        
        # Campaign metrics
        stats['campaign_response_rate'] = self._calculate_avg_campaign_response_rate()
        
        # Revenue (placeholder for now)
        stats['monthly_revenue'] = 12500  # TODO: Implement actual revenue tracking
        stats['revenue_growth'] = 8.5  # TODO: Calculate actual growth
        
        # Messaging metrics
        stats['messages_today'] = self._get_messages_sent_today()
        stats['overall_response_rate'] = self._calculate_overall_response_rate()
        
        # SMS bounce metrics (30 day)
        sms_metrics = self.metrics_service.get_global_metrics(days=30)
        stats['bounce_rate'] = sms_metrics.get('bounce_rate', 0)
        stats['delivery_rate'] = sms_metrics.get('delivery_rate', 0)
        stats['total_messages_30d'] = sms_metrics.get('total_sent', 0)
        stats['bounced_messages_30d'] = sms_metrics.get('bounced', 0)
        
        return stats
    
    def get_activity_timeline(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Get recent activity for the dashboard timeline
        Returns list of formatted activity items
        """
        # Get conversations with recent activity
        conversations = self._get_recent_conversations(limit)
        
        timeline_items = []
        for conv in conversations:
            # Get the most recent activity from pre-loaded activities
            last_activity = max(conv.activities, key=lambda act: act.created_at) if conv.activities else None
            if last_activity:
                item = self._format_activity_item(conv, last_activity)
                timeline_items.append(item)
        
        # Sort by most recent activity timestamp descending
        timeline_items.sort(key=lambda x: x['activity_timestamp'], reverse=True)
        
        return timeline_items
    
    def get_recent_campaigns(self, limit: int = 3) -> List[Campaign]:
        """Get recently created campaigns"""
        return Campaign.query.order_by(Campaign.created_at.desc()).limit(limit).all()
    
    def get_message_volume_data(self, days: int = 7) -> List[Dict[str, Any]]:
        """Get message volume data for the last N days"""
        message_volume_data = []
        for i in range(days):
            day = datetime.utcnow().date() - timedelta(days=days-1-i)
            count = Activity.query.filter(
                Activity.activity_type == 'message',
                func.date(Activity.created_at) == day
            ).count()
            message_volume_data.append({'date': day, 'count': count})
        return message_volume_data
    
    def get_campaign_queue_size(self) -> int:
        """Get number of pending campaign messages"""
        return CampaignMembership.query.filter_by(status='pending').count()
    
    def get_data_quality_score(self) -> int:
        """Calculate data quality score (percentage of contacts with complete info)"""
        from crm_database import Contact
        total_contacts = Contact.query.count()
        if total_contacts == 0:
            return 0
            
        contacts_with_names = Contact.query.filter(~Contact.first_name.like('%+1%')).count()
        contacts_with_emails = Contact.query.filter(
            Contact.email.isnot(None), 
            Contact.email != ''
        ).count()
        
        return round(((contacts_with_names + contacts_with_emails) / (total_contacts * 2)) * 100)
    
    # Private helper methods
    
    def _get_total_contacts(self) -> int:
        """Get total number of contacts"""
        return Contact.query.count()
    
    def _get_contacts_added_this_week(self) -> int:
        """Get number of contacts added in the last 7 days"""
        week_ago = datetime.utcnow() - timedelta(days=7)
        # Using Activity records as proxy since Contact doesn't have created_at
        return Activity.query.filter(
            Activity.created_at >= week_ago,
            Activity.contact_id.isnot(None)
        ).distinct(Activity.contact_id).count()
    
    def _get_active_campaigns(self) -> int:
        """Get number of active campaigns"""
        return Campaign.query.filter_by(status='running').count()
    
    def _calculate_avg_campaign_response_rate(self) -> float:
        """Calculate average response rate across all campaigns"""
        # Use eager loading to get campaigns with their memberships
        all_campaigns = Campaign.query.options(
            selectinload(Campaign.memberships)
        ).all()
        
        response_rates = []
        try:
            for campaign in all_campaigns:
                # Calculate response rate using pre-loaded memberships
                sent_count = sum(1 for m in campaign.memberships 
                                if m.status in ['sent', 'replied_positive', 'replied_negative'])
                if sent_count > 0:
                    replied_count = sum(1 for m in campaign.memberships 
                                      if m.status in ['replied_positive', 'replied_negative'])
                    response_rate = (replied_count / sent_count) * 100
                    response_rates.append(response_rate)
        except Exception as e:
            # Log error but don't crash dashboard
            pass
        
        return round(sum(response_rates) / len(response_rates), 1) if response_rates else 0
    
    def _get_messages_sent_today(self) -> int:
        """Get count of messages sent today"""
        today = datetime.utcnow().date()
        return Activity.query.filter(
            Activity.activity_type == 'message',
            Activity.direction == 'outgoing',
            func.date(Activity.created_at) == today
        ).count()
    
    def _calculate_overall_response_rate(self) -> float:
        """Calculate overall response rate (incoming vs outgoing messages)"""
        total_outgoing = Activity.query.filter(
            Activity.activity_type == 'message',
            Activity.direction == 'outgoing'
        ).count()
        
        total_incoming = Activity.query.filter(
            Activity.activity_type == 'message',
            Activity.direction == 'incoming'
        ).count()
        
        if total_outgoing > 0:
            return round((total_incoming / total_outgoing * 100), 1)
        return 0
    
    def _get_recent_conversations(self, limit: int) -> List[Conversation]:
        """Get recent conversations with activities"""
        return Conversation.query.options(
            joinedload(Conversation.contact),
            selectinload(Conversation.activities)
        ).filter(
            Conversation.last_activity_at.isnot(None),
            exists().where(Activity.conversation_id == Conversation.id)
        ).order_by(Conversation.last_activity_at.desc()).limit(limit).all()
    
    def _format_activity_item(self, conversation: Conversation, activity: Activity) -> Dict[str, Any]:
        """Format an activity for the timeline"""
        # Determine content based on activity type
        if activity.activity_type == 'call':
            if activity.direction == 'incoming':
                content = "📞 Incoming call"
            else:
                content = "📞 Outgoing call"
            if activity.duration_seconds:
                duration_min = activity.duration_seconds // 60
                content += f" ({duration_min}m)"
        elif activity.activity_type == 'voicemail':
            content = "🎤 Voicemail received"
        else:
            # Message type
            content = activity.body or "📱 Message (no content)"
        
        return {
            'contact_id': conversation.contact.id,
            'contact_name': conversation.contact.first_name or conversation.contact.phone,
            'contact_number': conversation.contact.phone,
            'latest_message_body': content,
            'timestamp': activity.created_at.strftime('%H:%M') if activity.created_at else 'Just now',
            'activity_timestamp': activity.created_at,
            'activity_type': activity.activity_type
        }