#!/usr/bin/env python3
"""
Test OpenPhone Webhook Handler

This script tests our webhook handler with all event types to ensure:
1. We handle all payload structures correctly
2. Media attachments are processed
3. AI summaries and transcripts are stored
4. Database operations work as expected
"""


import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
from scripts.script_logger import get_logger

logger = get_logger(__name__)

import requests
import hmac
import hashlib
import json
import sys
from webhook_payload_examples import *
from app import create_app

class WebhookTester:
    def __init__(self):
        self.app = create_app()
        with self.app.app_context():
            self.webhook_url = "http://localhost:5000/api/webhooks/openphone"
            self.signing_key = self.app.config.get('OPENPHONE_WEBHOOK_SIGNING_KEY', '')
    
    def generate_signature(self, payload):
        """Generate OpenPhone webhook signature"""
        payload_bytes = json.dumps(payload, separators=(',', ':')).encode('utf-8')
        signature = hmac.new(
            key=self.signing_key.encode('utf-8'),
            msg=payload_bytes,
            digestmod=hashlib.sha256
        ).hexdigest()
        return signature
    
    def send_webhook(self, payload, event_name):
        """Send a test webhook to our handler"""
        logger.info(f"\n📤 Testing {event_name}...")
        
        headers = {
            'Content-Type': 'application/json',
            'x-openphone-signature-v1': self.generate_signature(payload)
        }
        
        try:
            response = requests.post(
                self.webhook_url,
                json=payload,
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f"✅ Success: {result}")
                
                # Check for specific features
                if event_name == "message.received":
                    media = get_media_from_message(payload)
                    if media:
                        logger.info(f"   📎 Processed {len(media)} media attachments")
                
                return True
            else:
                logger.info(f"❌ Failed: {response.status_code}")
                logger.info(f"   Response: {response.text}")
                return False
                
        except requests.exceptions.ConnectionError:
            logger.info(f"❌ Connection failed - is the server running?")
            return False
        except Exception as e:
            logger.info(f"❌ Error: {e}")
            return False
    
    def test_all_webhooks(self):
        """Test all webhook event types"""
        # Test only the actual webhook types available in OpenPhone API
        tests = [
            ("Message Received (with media!)", MESSAGE_RECEIVED_PAYLOAD),
            ("Message Delivered", MESSAGE_DELIVERED_PAYLOAD),
            ("Call Completed", CALL_COMPLETED_PAYLOAD),
            ("Call Recording Completed", CALL_RECORDING_COMPLETED_PAYLOAD),
            ("Call Summary Completed", CALL_SUMMARY_CREATED_PAYLOAD),
            ("Call Transcript Completed", CALL_TRANSCRIPT_CREATED_PAYLOAD)
        ]
        
        logger.info("🧪 OpenPhone Webhook Handler Test Suite")
        logger.info("=" * 50)
        
        passed = 0
        failed = 0
        
        for test_name, payload in tests:
            if self.send_webhook(payload, test_name):
                passed += 1
            else:
                failed += 1
        
        logger.info("\n" + "=" * 50)
        logger.info(f"📊 Results: {passed} passed, {failed} failed")
        
        if failed == 0:
            logger.info("🎉 All webhooks handled successfully!")
        else:
            logger.info("⚠️  Some webhooks failed - check the implementation")
    
    def test_media_handling(self):
        """Specifically test media attachment handling"""
        logger.info("\n🖼️  Testing Media Attachment Handling")
        logger.info("=" * 50)
        
        # Create a message with multiple media types
        media_payload = MESSAGE_RECEIVED_PAYLOAD.copy()
        media_payload['data']['object']['media'] = [
            "https://media.openphone.com/image1.jpg",
            "https://media.openphone.com/image2.png", 
            "https://media.openphone.com/document.pdf",
            "https://media.openphone.com/video.mp4"
        ]
        media_payload['data']['object']['text'] = "Check out these attachments!"
        media_payload['id'] = "WEBHOOK_MEDIA_TEST"
        
        if self.send_webhook(media_payload, "Message with Multiple Media"):
            logger.info("✅ Media handling test passed!")
            
            # Check database to verify media was stored
            with self.app.app_context():
                from crm_database import Activity
                activity = Activity.query.filter_by(
                    openphone_id=media_payload['data']['object']['id']
                ).first()
                
                if activity and activity.media_urls:
                    logger.info(f"   📎 Verified {len(activity.media_urls)} media URLs in database")
                    for url in activity.media_urls:
                        logger.info(f"      - {url}")
        else:
            logger.info("❌ Media handling test failed")
    
    def test_ai_content_handling(self):
        """Test AI summary and transcript handling"""
        logger.info("\n🤖 Testing AI Content Handling")
        logger.info("=" * 50)
        
        # First create a call
        self.send_webhook(CALL_COMPLETED_PAYLOAD, "Call Completed")
        
        # Then add AI summary
        if self.send_webhook(CALL_SUMMARY_CREATED_PAYLOAD, "Call Summary"):
            logger.info("✅ AI Summary handled correctly")
        
        # Then add transcript
        if self.send_webhook(CALL_TRANSCRIPT_CREATED_PAYLOAD, "Call Transcript"):
            logger.info("✅ AI Transcript handled correctly")
            
            # Verify AI content in database
            with self.app.app_context():
                from crm_database import Activity
                activity = Activity.query.filter_by(
                    openphone_id=CALL_COMPLETED_PAYLOAD['data']['object']['id']
                ).first()
                
                if activity:
                    if activity.ai_summary:
                        logger.info("   ✅ AI Summary stored in database")
                    if activity.ai_transcript:
                        logger.info("   ✅ AI Transcript stored in database")
                        logger.info(f"      - {len(activity.ai_transcript.get('dialogue', []))} dialogue segments")

def main():
    if len(sys.argv) > 1:
        command = sys.argv[1]
    else:
        command = "all"
    
    tester = WebhookTester()
    
    if command == "all":
        tester.test_all_webhooks()
    elif command == "media":
        tester.test_media_handling()
    elif command == "ai":
        tester.test_ai_content_handling()
    elif command == "full":
        tester.test_all_webhooks()
        tester.test_media_handling()
        tester.test_ai_content_handling()
    else:
        logger.info("Usage: python test_webhook_handler.py [all|media|ai|full]")
        sys.exit(1)

if __name__ == "__main__":
    main()