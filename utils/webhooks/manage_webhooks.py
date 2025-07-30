#!/usr/bin/env python3
"""
OpenPhone Webhook Management Script

This script helps manage OpenPhone webhooks:
- List current webhooks
- Create new webhooks for all event types
- Test webhook connectivity
- Delete webhooks

Usage:
  python manage_webhooks.py list
  python manage_webhooks.py create
  python manage_webhooks.py test
  python manage_webhooks.py delete
"""

import requests
import json
import sys
from app import create_app

class WebhookManager:
    def __init__(self):
        app = create_app()
        with app.app_context():
            self.api_key = app.config.get('OPENPHONE_API_KEY')
            self.phone_number_id = app.config.get('OPENPHONE_PHONE_NUMBER_ID')
            self.webhook_url = app.config.get('WEBHOOK_BASE_URL', 'https://your-domain.com') + '/api/webhooks/openphone'
            
        if not self.api_key:
            raise ValueError("OPENPHONE_API_KEY not configured")
        
        self.headers = {
            'Authorization': self.api_key,
            'Content-Type': 'application/json'
        }
    
    def list_webhooks(self):
        """List all current webhooks"""
        print("🔍 Listing current OpenPhone webhooks...")
        
        url = "https://api.openphone.com/v1/webhooks"
        response = requests.get(url, headers=self.headers)
        
        if response.status_code == 200:
            webhooks = response.json().get('data', [])
            print(f"Found {len(webhooks)} webhooks:")
            
            for webhook in webhooks:
                print(f"  📡 {webhook.get('id')}")
                print(f"     URL: {webhook.get('url')}")
                print(f"     Events: {webhook.get('events', [])}")
                print(f"     Phone Number ID: {webhook.get('phoneNumberId')}")
                print(f"     Created: {webhook.get('createdAt')}")
                print()
        else:
            print(f"❌ Error listing webhooks: {response.status_code} - {response.text}")
    
    def create_webhooks(self):
        """Create webhooks for all event types"""
        print("🚀 Creating OpenPhone webhooks for all event types...")
        
        # Webhook events available in OpenPhone API (as of documentation)
        webhook_configs = [
            {
                'name': 'All OpenPhone Webhooks',
                'events': [
                    'message.received',
                    'message.delivered',
                    'call.completed',
                    'call.recording.completed',
                    'call.summary.completed',
                    'call.transcript.completed'
                ]
            }
        ]
        
        created_count = 0
        
        for config in webhook_configs:
            print(f"Creating {config['name']}...")
            
            webhook_data = {
                'url': self.webhook_url,
                'events': config['events'],
                'phoneNumberId': self.phone_number_id
            }
            
            url = "https://api.openphone.com/v1/webhooks"
            response = requests.post(url, headers=self.headers, json=webhook_data)
            
            if response.status_code == 201:
                webhook = response.json()
                print(f"  ✅ Created webhook: {webhook.get('id')}")
                print(f"     Events: {', '.join(config['events'])}")
                created_count += 1
            else:
                print(f"  ❌ Failed to create {config['name']}: {response.status_code}")
                print(f"     Error: {response.text}")
        
        print(f"\\n🎉 Created {created_count}/{len(webhook_configs)} webhooks")
    
    def test_webhook_connectivity(self):
        """Test if our webhook endpoint is accessible"""
        print("🧪 Testing webhook endpoint connectivity...")
        
        # Test basic connectivity (should get 403 due to missing signature)
        test_payload = {'type': 'test', 'data': {}}
        
        try:
            response = requests.post(
                self.webhook_url,
                json=test_payload,
                timeout=10
            )
            
            if response.status_code == 403:
                print("✅ Webhook endpoint is accessible (403 expected - missing signature)")
                print(f"   URL: {self.webhook_url}")
            else:
                print(f"⚠️  Unexpected response: {response.status_code}")
                print(f"   Response: {response.text}")
                
        except requests.RequestException as e:
            print(f"❌ Cannot reach webhook endpoint: {e}")
            print(f"   URL: {self.webhook_url}")
            print("   Make sure your application is running and accessible")
    
    def delete_all_webhooks(self):
        """Delete all webhooks (use with caution!)"""
        print("🗑️  Deleting all OpenPhone webhooks...")
        
        # First list webhooks
        url = "https://api.openphone.com/v1/webhooks"
        response = requests.get(url, headers=self.headers)
        
        if response.status_code != 200:
            print(f"❌ Error listing webhooks: {response.status_code}")
            return
        
        webhooks = response.json().get('data', [])
        
        if not webhooks:
            print("No webhooks to delete")
            return
        
        deleted_count = 0
        
        for webhook in webhooks:
            webhook_id = webhook.get('id')
            delete_url = f"https://api.openphone.com/v1/webhooks/{webhook_id}"
            
            delete_response = requests.delete(delete_url, headers=self.headers)
            
            if delete_response.status_code == 204:
                print(f"  ✅ Deleted webhook: {webhook_id}")
                deleted_count += 1
            else:
                print(f"  ❌ Failed to delete {webhook_id}: {delete_response.status_code}")
        
        print(f"\\n🗑️  Deleted {deleted_count}/{len(webhooks)} webhooks")

def main():
    if len(sys.argv) != 2:
        print("Usage: python manage_webhooks.py [list|create|test|delete]")
        sys.exit(1)
    
    command = sys.argv[1].lower()
    
    try:
        manager = WebhookManager()
        
        if command == 'list':
            manager.list_webhooks()
        elif command == 'create':
            manager.create_webhooks()
        elif command == 'test':
            manager.test_webhook_connectivity()
        elif command == 'delete':
            confirm = input("⚠️  Are you sure you want to delete ALL webhooks? (yes/no): ")
            if confirm.lower() == 'yes':
                manager.delete_all_webhooks()
            else:
                print("Cancelled")
        else:
            print(f"Unknown command: {command}")
            print("Available commands: list, create, test, delete")
            sys.exit(1)
            
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()