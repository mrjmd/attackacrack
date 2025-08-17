#!/usr/bin/env python3
"""
Verify OpenPhone Webhook Setup for Production
This script checks all prerequisites and configuration for webhook deployment
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from crm_database import db, WebhookEvent
from datetime import datetime, timedelta
import requests

def verify_webhook_setup():
    """Check all webhook configuration and readiness"""
    
    app = create_app()
    with app.app_context():
        print("=" * 60)
        print("OpenPhone Webhook Setup Verification")
        print("=" * 60)
        
        # 1. Check Environment Variables
        print("\n1️⃣  ENVIRONMENT VARIABLES CHECK:")
        env_vars = {
            'OPENPHONE_API_KEY': os.environ.get('OPENPHONE_API_KEY'),
            'OPENPHONE_WEBHOOK_SIGNING_KEY': os.environ.get('OPENPHONE_WEBHOOK_SIGNING_KEY'),
            'OPENPHONE_PHONE_NUMBER_ID': os.environ.get('OPENPHONE_PHONE_NUMBER_ID'),
            'WEBHOOK_BASE_URL': os.environ.get('WEBHOOK_BASE_URL', 'https://attackacrack-prod-5ce6f.ondigitalocean.app')
        }
        
        all_set = True
        for key, value in env_vars.items():
            if value:
                print(f"  ✅ {key}: {'*' * 8}{value[-4:] if len(value) > 4 else '****'}")
            else:
                print(f"  ❌ {key}: NOT SET")
                all_set = False
        
        if not all_set:
            print("\n⚠️  Missing environment variables! Set these in production.")
            return False
        
        # 2. Check Database Table
        print("\n2️⃣  DATABASE CHECK:")
        try:
            # Check if webhook_events table exists
            recent_count = WebhookEvent.query.count()
            print(f"  ✅ webhook_events table exists ({recent_count} total events)")
            
            # Check recent webhook activity
            recent = WebhookEvent.query.filter(
                WebhookEvent.created_at > datetime.utcnow() - timedelta(days=1)
            ).count()
            
            if recent > 0:
                print(f"  ✅ {recent} webhooks received in last 24 hours")
            else:
                print(f"  ⚠️  No webhooks received in last 24 hours")
            
            # Check processing status
            failed = WebhookEvent.query.filter_by(processed=False).filter(
                WebhookEvent.error_message.isnot(None)
            ).count()
            
            if failed > 0:
                print(f"  ⚠️  {failed} failed webhook events need attention")
            
        except Exception as e:
            print(f"  ❌ Database error: {e}")
            return False
        
        # 3. Check OpenPhone API Connection
        print("\n3️⃣  OPENPHONE API CHECK:")
        try:
            headers = {'Authorization': env_vars['OPENPHONE_API_KEY']}
            response = requests.get(
                'https://api.openphone.com/v1/phone-numbers',
                headers=headers,
                timeout=5
            )
            
            if response.status_code == 200:
                print(f"  ✅ OpenPhone API connection successful")
                data = response.json()
                phone_numbers = data.get('data', [])
                if phone_numbers:
                    print(f"  ✅ Found {len(phone_numbers)} phone number(s)")
            else:
                print(f"  ❌ OpenPhone API error: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"  ❌ Could not connect to OpenPhone API: {e}")
            return False
        
        # 4. List Current Webhooks
        print("\n4️⃣  CURRENT WEBHOOKS:")
        try:
            response = requests.get(
                'https://api.openphone.com/v1/webhooks',
                headers=headers,
                timeout=5
            )
            
            if response.status_code == 200:
                webhooks = response.json().get('data', [])
                if webhooks:
                    print(f"  ⚠️  Found {len(webhooks)} existing webhook(s):")
                    for webhook in webhooks:
                        print(f"    - {webhook.get('url')}")
                        print(f"      Events: {', '.join(webhook.get('events', []))}")
                    print("\n  💡 Run 'python scripts/dev_tools/webhooks/manage_webhooks.py delete' to clean up")
                else:
                    print(f"  ✅ No existing webhooks (ready to create)")
            else:
                print(f"  ❌ Could not list webhooks: {response.status_code}")
                
        except Exception as e:
            print(f"  ❌ Error listing webhooks: {e}")
        
        # 5. Production URL Check
        print("\n5️⃣  PRODUCTION URL CHECK:")
        webhook_url = env_vars['WEBHOOK_BASE_URL'] + '/api/webhooks/openphone'
        print(f"  📍 Webhook URL: {webhook_url}")
        
        try:
            # Try to reach the health endpoint
            health_url = env_vars['WEBHOOK_BASE_URL'] + '/health'
            response = requests.get(health_url, timeout=5)
            
            if response.status_code == 200:
                print(f"  ✅ Production server is reachable")
            else:
                print(f"  ⚠️  Production server returned: {response.status_code}")
                
        except Exception as e:
            print(f"  ❌ Could not reach production server: {e}")
        
        # Summary
        print("\n" + "=" * 60)
        print("📋 NEXT STEPS:")
        print("=" * 60)
        
        if not webhooks:
            print("1. ✅ No cleanup needed - ready to create webhooks")
        else:
            print("1. 🧹 Clean up existing webhooks:")
            print("   python scripts/dev_tools/webhooks/manage_webhooks.py delete")
        
        print("\n2. 🚀 Create production webhooks:")
        print("   python scripts/dev_tools/webhooks/manage_webhooks.py create")
        
        print("\n3. 🧪 Test webhook connectivity:")
        print("   python scripts/dev_tools/webhooks/manage_webhooks.py test")
        
        print("\n4. 📱 Send a test SMS to verify end-to-end flow")
        
        print("\n" + "=" * 60)
        
        return True

if __name__ == "__main__":
    verify_webhook_setup()