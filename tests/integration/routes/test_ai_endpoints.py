#!/usr/bin/env python3
"""
Test OpenPhone AI endpoints to verify availability
"""

import requests
import json
import logging
from app import create_app

# Configure logging for tests
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

def test_ai_endpoints():
    """Test OpenPhone AI endpoints with actual call data"""
    
    app = create_app()
    with app.app_context():
        api_key = app.config.get('OPENPHONE_API_KEY')
        phone_number_id = app.config.get('OPENPHONE_PHONE_NUMBER_ID')
        user_phone = app.config.get('OPENPHONE_PHONE_NUMBER')
        headers = {'Authorization': api_key}
        
        logger.info('=== TESTING OPENPHONE AI ENDPOINTS ===')
        
        # Get conversations to find participants
        logger.info('\n1. Fetching conversations to find participants...')
        conv_response = requests.get(
            f'https://api.openphone.com/v1/conversations?phoneNumberId={phone_number_id}&maxResults=5', 
            headers=headers, 
            verify=True
        )
        
        if conv_response.status_code != 200:
            logger.error(f'❌ Failed to fetch conversations: HTTP {conv_response.status_code}')
            return
        
        conversations = conv_response.json().get('data', [])
        logger.info(f'Found {len(conversations)} conversations')
        
        # Find participants and test calls
        for conv in conversations[:3]:
            participants = conv.get('participants', [])
            other_participants = [p for p in participants if p != user_phone]
            
            if not other_participants:
                continue
                
            participant = other_participants[0]
            logger.info(f'\n2. Testing calls with participant: {participant}')
            
            # Fetch calls for this participant (API requires single participant)
            call_response = requests.get(
                'https://api.openphone.com/v1/calls',
                headers=headers,
                params={
                    'phoneNumberId': phone_number_id,
                    'participants': participant,  # Single participant
                    'maxResults': 3
                },
                verify=True
            )
            
            logger.info(f'   Calls API: HTTP {call_response.status_code}')
            
            if call_response.status_code == 200:
                calls_data = call_response.json().get('data', [])
                logger.info(f'   Found {len(calls_data)} calls')
                
                # Test AI endpoints with first call
                if calls_data:
                    call = calls_data[0]
                    call_id = call.get('id')
                    duration = call.get('duration', 0)
                    status = call.get('status') or call.get('callStatus')
                    
                    logger.info(f'\n   Testing AI with call: {call_id}')
                    logger.info(f'   Duration: {duration}s, Status: {status}')
                    
                    # Test AI Summary
                    summary_url = f'https://api.openphone.com/v1/call-summaries/{call_id}'
                    summary_response = requests.get(summary_url, headers=headers, verify=True, timeout=(10, 30))
                    
                    logger.info(f'   AI Summary: HTTP {summary_response.status_code}')
                    if summary_response.status_code == 200:
                        logger.info('   ✅ AI Summary AVAILABLE!')
                        summary_data = summary_response.json()
                        if 'data' in summary_data:
                            data = summary_data['data']
                            highlights = data.get('highlights', [])
                            next_steps = data.get('nextSteps', [])
                            logger.info(f'      Highlights: {len(highlights)}, Next Steps: {len(next_steps)}')
                    elif summary_response.status_code == 404:
                        logger.info('   ❌ AI Summary not available for this call')
                    elif summary_response.status_code == 402:
                        logger.info('   💰 AI Summary requires Business plan')
                    else:
                        logger.info(f'   ⚠️  Unexpected: {summary_response.text[:100]}')
                    
                    # Test AI Transcript
                    transcript_url = f'https://api.openphone.com/v1/call-transcripts/{call_id}'
                    transcript_response = requests.get(transcript_url, headers=headers, verify=True, timeout=(10, 30))
                    
                    logger.info(f'   AI Transcript: HTTP {transcript_response.status_code}')
                    if transcript_response.status_code == 200:
                        logger.info('   ✅ AI Transcript AVAILABLE!')
                        transcript_data = transcript_response.json()
                        if 'data' in transcript_data:
                            data = transcript_data['data']
                            dialogue = data.get('dialogue', [])
                            logger.info(f'      Dialogue segments: {len(dialogue)}')
                    elif transcript_response.status_code == 404:
                        logger.info('   ❌ AI Transcript not available for this call')
                    elif transcript_response.status_code == 402:
                        logger.info('   💰 AI Transcript requires Business plan')
                    else:
                        logger.info(f'   ⚠️  Unexpected: {transcript_response.text[:100]}')
                    
                    return  # Exit after testing one call
                    
            elif call_response.status_code == 400:
                logger.info(f'   Bad request: {call_response.text[:150]}')
            else:
                logger.info(f'   Error: {call_response.text[:100]}')

if __name__ == '__main__':
    test_ai_endpoints()