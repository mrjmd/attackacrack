"""
Dashboard Service
Handles all business logic for dashboard statistics and activity feeds
Refactored to use Repository Pattern
"""

from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from flask import current_app

from services.sms_metrics_service import SMSMetricsService


class DashboardService:
    """Service for dashboard data and statistics using Repository Pattern"""
    
    def __init__(self, contact_repository=None, campaign_repository=None, 
                 activity_repository=None, conversation_repository=None):
        self.metrics_service = SMSMetricsService()
        
        # Repository dependencies (injected or retrieved from service registry)
        self.contact_repository = contact_repository
        self.campaign_repository = campaign_repository
        self.activity_repository = activity_repository
        self.conversation_repository = conversation_repository
    
    def _get_contact_repository(self):
        """Get contact repository (lazy load from service registry if not injected)"""
        if self.contact_repository is None:
            self.contact_repository = current_app.services.get('contact_repository')
        return self.contact_repository
        
    def _get_campaign_repository(self):
        """Get campaign repository (lazy load from service registry if not injected)"""
        if self.campaign_repository is None:
            self.campaign_repository = current_app.services.get('campaign_repository')
        return self.campaign_repository
        
    def _get_activity_repository(self):
        """Get activity repository (lazy load from service registry if not injected)"""
        if self.activity_repository is None:
            self.activity_repository = current_app.services.get('activity_repository')
        return self.activity_repository
        
    def _get_conversation_repository(self):
        """Get conversation repository (lazy load from service registry if not injected)"""
        if self.conversation_repository is None:
            self.conversation_repository = current_app.services.get('conversation_repository')
        return self.conversation_repository
    
    def get_dashboard_stats(self) -> Dict[str, Any]:
        """
        Get all dashboard statistics using repositories
        Returns dict with all stats for dashboard cards
        """
        stats = {}
        
        # Get repositories
        contact_repo = self._get_contact_repository()
        campaign_repo = self._get_campaign_repository()
        activity_repo = self._get_activity_repository()
        
        # Basic counts using repository methods
        stats['contact_count'] = contact_repo.get_total_contacts_count()
        stats['contacts_added_this_week'] = contact_repo.get_contacts_added_this_week_count()
        stats['active_campaigns'] = campaign_repo.get_active_campaigns_count()
        
        # Campaign metrics using repository methods
        stats['campaign_response_rate'] = campaign_repo.calculate_average_campaign_response_rate()
        
        # Revenue (placeholder for now)
        stats['monthly_revenue'] = 12500  # TODO: Implement actual revenue tracking
        stats['revenue_growth'] = 8.5  # TODO: Calculate actual growth
        
        # Messaging metrics using repository methods
        stats['messages_today'] = activity_repo.get_messages_sent_today_count()
        stats['overall_response_rate'] = activity_repo.calculate_overall_response_rate()
        
        # SMS bounce metrics (30 day)
        sms_metrics = self.metrics_service.get_global_metrics(days=30)
        stats['bounce_rate'] = sms_metrics.get('bounce_rate', 0)
        stats['delivery_rate'] = sms_metrics.get('delivery_rate', 0)
        stats['total_messages_30d'] = sms_metrics.get('total_sent', 0)
        stats['bounced_messages_30d'] = sms_metrics.get('bounced', 0)
        
        return stats
    
    def get_activity_timeline(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Get recent activity for the dashboard timeline using repository
        Returns list of formatted activity items
        """
        # Get conversations with recent activity using repository
        conversation_repo = self._get_conversation_repository()
        conversations = conversation_repo.get_recent_conversations_with_activities(limit=limit)
        
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
    
    def get_recent_campaigns(self, limit: int = 3):
        """Get recently created campaigns using repository"""
        campaign_repo = self._get_campaign_repository()
        return campaign_repo.get_recent_campaigns_with_limit(limit=limit)
    
    def get_message_volume_data(self, days: int = 7) -> List[Dict[str, Any]]:
        """Get message volume data for the last N days using repository"""
        activity_repo = self._get_activity_repository()
        return activity_repo.get_message_volume_data(days=days)
    
    def get_campaign_queue_size(self) -> int:
        """Get number of pending campaign messages using repository"""
        campaign_repo = self._get_campaign_repository()
        return campaign_repo.get_pending_campaign_queue_size()
    
    def get_data_quality_score(self) -> int:
        """Calculate data quality score using repository"""
        contact_repo = self._get_contact_repository()
        quality_stats = contact_repo.get_data_quality_stats()
        return quality_stats['data_quality_score']
    
    # Private helper methods
    # All database queries now use repository pattern
    
    def _format_activity_item(self, conversation, activity) -> Dict[str, Any]:
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