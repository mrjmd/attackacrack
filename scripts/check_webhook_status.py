#!/usr/bin/env python3
"""
Check webhook status in production
Shows recent webhook events and their processing status
"""

import sys
import os
from utils.datetime_utils import utc_now
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from crm_database import db, WebhookEvent, Activity, Conversation
from datetime import datetime, timedelta
from sqlalchemy import desc

def check_webhook_status():
    """Check recent webhook activity and processing status"""
    
    app = create_app()
    with app.app_context():
        print("=" * 60)
        print("OpenPhone Webhook Status Check")
        print("=" * 60)
        
        # 1. Check recent webhook events
        print("\n📨 RECENT WEBHOOK EVENTS (Last 10):")
        recent_events = WebhookEvent.query.order_by(
            desc(WebhookEvent.created_at)
        ).limit(10).all()
        
        if recent_events:
            for event in recent_events:
                status = "✅ Processed" if event.processed else "❌ Failed"
                print(f"\n  {event.created_at.strftime('%Y-%m-%d %H:%M:%S')} - {event.event_type}")
                print(f"  Status: {status}")
                print(f"  Event ID: {event.event_id}")
                if event.error_message:
                    print(f"  Error: {event.error_message}")
        else:
            print("  No webhook events found")
        
        # 2. Check webhooks in last hour
        print("\n⏰ WEBHOOKS IN LAST HOUR:")
        one_hour_ago = utc_now() - timedelta(hours=1)
        recent_count = WebhookEvent.query.filter(
            WebhookEvent.created_at > one_hour_ago
        ).count()
        print(f"  {recent_count} webhook(s) received")
        
        # 3. Check processing statistics
        print("\n📊 PROCESSING STATISTICS:")
        total = WebhookEvent.query.count()
        processed = WebhookEvent.query.filter_by(processed=True).count()
        failed = WebhookEvent.query.filter(
            WebhookEvent.processed == False,
            WebhookEvent.error_message.isnot(None)
        ).count()
        
        print(f"  Total Events: {total}")
        print(f"  Successfully Processed: {processed}")
        print(f"  Failed: {failed}")
        if total > 0:
            success_rate = (processed / total) * 100
            print(f"  Success Rate: {success_rate:.1f}%")
        
        # 4. Check recent activities created from webhooks
        print("\n📱 RECENT ACTIVITIES (Last 5):")
        recent_activities = Activity.query.order_by(
            desc(Activity.created_at)
        ).limit(5).all()
        
        if recent_activities:
            for activity in recent_activities:
                direction = "→" if activity.direction == "outgoing" else "←"
                print(f"\n  {activity.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"  {direction} {activity.activity_type}: {activity.body[:50] if activity.body else 'No content'}")
                if activity.from_number:
                    print(f"  From: {activity.from_number}")
        else:
            print("  No recent activities")
        
        # 5. Check if webhooks are currently working
        print("\n🔍 WEBHOOK HEALTH:")
        latest_webhook = WebhookEvent.query.order_by(
            desc(WebhookEvent.created_at)
        ).first()
        
        if latest_webhook:
            time_since = utc_now() - latest_webhook.created_at
            hours = time_since.total_seconds() / 3600
            
            if hours < 1:
                print(f"  ✅ Webhooks active (last received {int(time_since.total_seconds() / 60)} minutes ago)")
            elif hours < 24:
                print(f"  ⚠️  Last webhook {hours:.1f} hours ago")
            else:
                days = hours / 24
                print(f"  ❌ No webhooks in {days:.1f} days - check configuration")
        else:
            print("  ❌ No webhooks have been received yet")
        
        print("\n" + "=" * 60)

if __name__ == "__main__":
    check_webhook_status()