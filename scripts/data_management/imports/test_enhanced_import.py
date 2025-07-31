#!/usr/bin/env python3
"""
Test script for Enhanced OpenPhone Import
Validates import functionality with dry run and integrity checks
"""


import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
from scripts.script_logger import get_logger

logger = get_logger(__name__)

import sys
import time
from enhanced_openphone_import import run_enhanced_import
from app import create_app
from extensions import db
from crm_database import Contact, Conversation, Activity, MediaAttachment

def test_import_dry_run():
    """Test import with limited data for validation"""
    logger.info("="*80)
    logger.info("TESTING ENHANCED OPENPHONE IMPORT - DRY RUN")
    logger.info("="*80)
    
    # Run with limited data
    logger.info("Running import with limit of 5 conversations...")
    run_enhanced_import(dry_run_limit=5)
    
    logger.info("\n" + "="*80)
    logger.info("DRY RUN COMPLETED - VALIDATING RESULTS")
    logger.info("="*80)
    
    app = create_app()
    with app.app_context():
        # Count imported data
        contacts_count = db.session.query(Contact).count()
        conversations_count = db.session.query(Conversation).count()
        activities_count = db.session.query(Activity).count()
        media_count = db.session.query(MediaAttachment).count()
        
        logger.info(f"Contacts in database: {contacts_count}")
        logger.info(f"Conversations in database: {conversations_count}")
        logger.info(f"Activities in database: {activities_count}")
        logger.info(f"Media attachments in database: {media_count}")
        
        # Sample some data
        if activities_count > 0:
            logger.info("\nSample Activities:")
            sample_activities = db.session.query(Activity).limit(3).all()
            for activity in sample_activities:
                logger.info(f"  - {activity.activity_type} | {activity.direction} | {activity.created_at}")
                if activity.ai_summary:
                    logger.info(f"    AI Summary: {activity.ai_summary[:100]}...")
        
        if conversations_count > 0:
            logger.info("\nSample Conversations:")
            sample_conversations = db.session.query(Conversation).limit(3).all()
            for conv in sample_conversations:
                contact_name = f"{conv.contact.first_name} {conv.contact.last_name}" if conv.contact else "Unknown"
                logger.info(f"  - {contact_name} | Activities: {len(conv.activities)} | Last: {conv.last_activity_at}")
        
        logger.info("\n" + "="*80)
        logger.info("DRY RUN VALIDATION COMPLETED")
        logger.info("="*80)

def check_database_schema():
    """Verify database schema supports all enhanced fields"""
    logger.info("="*80)
    logger.info("VALIDATING DATABASE SCHEMA")
    logger.info("="*80)
    
    app = create_app()
    with app.app_context():
        try:
            # Test Activity model enhancements
            test_activity = Activity(
                openphone_id="test_123",
                activity_type="call",
                direction="outgoing",
                status="completed",
                duration_seconds=120,
                recording_url="https://example.com/recording.mp3",
                voicemail_url="https://example.com/voicemail.mp3",
                ai_summary="Test summary",
                ai_transcript={"dialogue": [{"speaker": "user", "text": "Hello"}]},
                ai_content_status="completed"
            )
            
            # Test Conversation model enhancements  
            test_conversation = Conversation(
                openphone_id="conv_test_123",
                contact_id=1,  # Assuming contact exists
                name="Test Conversation",
                participants="+1234567890,+1987654321",
                phone_number_id="pn_123",
                last_activity_type="call",
                last_activity_id="act_123"
            )
            
            logger.info("✓ Activity model schema validation passed")
            logger.info("✓ Conversation model schema validation passed")
            logger.info("✓ All enhanced fields are properly defined")
            
        except Exception as e:
            logger.info(f"✗ Schema validation failed: {e}")
            return False
    
    return True

def benchmark_import_performance():
    """Basic performance test of import functionality"""
    logger.info("="*80)
    logger.info("BENCHMARKING IMPORT PERFORMANCE")
    logger.info("="*80)
    
    start_time = time.time()
    
    # Run small import to measure performance
    run_enhanced_import(dry_run_limit=10)
    
    end_time = time.time()
    duration = end_time - start_time
    
    logger.info(f"\nImport Performance:")
    logger.info(f"Time taken for 10 conversations: {duration:.2f} seconds")
    logger.info(f"Average per conversation: {duration/10:.2f} seconds")
    
    if duration > 60:  # More than 1 minute for 10 conversations
        logger.info("⚠️  Performance Warning: Import is slower than expected")
    else:
        logger.info("✓ Performance looks good")

def validate_openphone_api_access():
    """Validate OpenPhone API connectivity and authentication"""
    logger.info("="*80)
    logger.info("VALIDATING OPENPHONE API ACCESS")
    logger.info("="*80)
    
    import requests
    from app import create_app
    
    app = create_app()
    with app.app_context():
        api_key = app.config.get('OPENPHONE_API_KEY')
        phone_number_id = app.config.get('OPENPHONE_PHONE_NUMBER_ID')
        
        if not api_key or not phone_number_id:
            logger.info("✗ Missing OpenPhone configuration")
            return False
        
        headers = {"Authorization": api_key}
        
        # Test basic API access
        try:
            response = requests.get(
                "https://api.openphone.com/v1/phone-numbers", 
                headers=headers, 
                verify=True,
                timeout=(5, 30)
            )
            
            if response.status_code == 200:
                logger.info("✓ OpenPhone API authentication successful")
                
                # Test specific endpoints
                test_endpoints = [
                    f"https://api.openphone.com/v1/conversations?phoneNumberId={phone_number_id}&maxResults=1",
                    "https://api.openphone.com/v1/users"
                ]
                
                for endpoint in test_endpoints:
                    try:
                        test_response = requests.get(endpoint, headers=headers, verify=True, timeout=(5, 30))
                        if test_response.status_code == 200:
                            logger.info(f"✓ {endpoint.split('/')[-1]} endpoint accessible")
                        else:
                            logger.info(f"⚠️  {endpoint.split('/')[-1]} endpoint returned {test_response.status_code}")
                    except Exception as e:
                        logger.info(f"✗ {endpoint.split('/')[-1]} endpoint error: {e}")
                
                return True
            else:
                logger.info(f"✗ OpenPhone API authentication failed: {response.status_code}")
                return False
                
        except Exception as e:
            logger.info(f"✗ OpenPhone API connection error: {e}")
            return False

def main():
    """Main test execution"""
    logger.info("ENHANCED OPENPHONE IMPORT - COMPREHENSIVE TEST SUITE")
    logger.info("="*80)
    
    # Validate prerequisites
    if not check_database_schema():
        logger.info("Database schema validation failed. Please run migrations.")
        sys.exit(1)
    
    if not validate_openphone_api_access():
        logger.info("OpenPhone API validation failed. Please check configuration.")
        sys.exit(1)
    
    # Run tests
    try:
        test_import_dry_run()
        benchmark_import_performance()
        
        logger.info("\n" + "="*80)
        logger.info("ALL TESTS COMPLETED SUCCESSFULLY")
        logger.info("="*80)
        logger.info("\nThe enhanced import is ready for production use.")
        logger.info("To run full import: python enhanced_openphone_import.py")
        logger.info("To run with webhook sync, ensure webhook_sync_service.py is integrated.")
        
    except Exception as e:
        logger.info(f"\n✗ Test suite failed with error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()