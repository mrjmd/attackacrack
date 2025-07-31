#!/usr/bin/env python3
"""
OpenPhone Webhook Payload Examples and Validator

Based on OpenPhone webhook documentation:
https://support.openphone.com/hc/en-us/articles/4690754298903-How-to-use-webhooks

This file contains example payloads for all webhook event types to help with:
1. Testing webhook handlers
2. Validating payload structures
3. Ensuring we handle all fields correctly
"""

# Message Events
MESSAGE_RECEIVED_PAYLOAD = {
    "apiVersion": "v1",
    "createdAt": "2025-07-30T10:00:00.000Z",
    "data": {
        "object": {
            "id": "MSG123456789",
            "object": "message",
            "conversationId": "CONV123456",
            "createdAt": "2025-07-30T10:00:00.000Z",
            "direction": "incoming",
            "from": "+1234567890",
            "to": ["+0987654321"],
            "text": "Hello, this is a test message",
            "status": "received",
            "phoneNumberId": "PN123456",
            "userId": "USER123",
            "media": [  # THIS IS THE EXCITING PART!
                "https://media.openphone.com/attachment1.jpg",
                "https://media.openphone.com/attachment2.pdf"
            ],
            "deliveredAt": "2025-07-30T10:00:01.000Z"
        }
    },
    "id": "WEBHOOK123456",
    "type": "message.received"
}

# Note: message.sent webhook doesn't exist in OpenPhone API
# Only message.received and message.delivered are available

MESSAGE_DELIVERED_PAYLOAD = {
    "apiVersion": "v1",
    "createdAt": "2025-07-30T10:00:02.000Z",
    "data": {
        "object": {
            "id": "MSG123456790",
            "status": "delivered",
            "deliveredAt": "2025-07-30T10:00:02.000Z"
        }
    },
    "id": "WEBHOOK123458",
    "type": "message.delivered"
}

MESSAGE_FAILED_PAYLOAD = {
    "apiVersion": "v1",
    "createdAt": "2025-07-30T10:00:02.000Z",
    "data": {
        "object": {
            "id": "MSG123456791",
            "status": "failed",
            "failedAt": "2025-07-30T10:00:02.000Z",
            "errorCode": "30004",
            "errorMessage": "Message blocked"
        }
    },
    "id": "WEBHOOK123459",
    "type": "message.failed"
}

# Call Events
CALL_STARTED_PAYLOAD = {
    "apiVersion": "v1",
    "createdAt": "2025-07-30T10:00:00.000Z",
    "data": {
        "object": {
            "id": "CALL123456789",
            "object": "call",
            "createdAt": "2025-07-30T10:00:00.000Z",
            "direction": "incoming",
            "from": "+1234567890",
            "to": ["+0987654321"],
            "status": "started",
            "phoneNumberId": "PN123456",
            "userId": "USER123",
            "participants": ["+1234567890", "+0987654321"]
        }
    },
    "id": "WEBHOOK123460",
    "type": "call.started"
}

CALL_COMPLETED_PAYLOAD = {
    "apiVersion": "v1",
    "createdAt": "2025-07-30T10:05:00.000Z",
    "data": {
        "object": {
            "id": "CALL123456789",
            "object": "call",
            "status": "completed",
            "duration": 300,  # seconds
            "durationSeconds": 300,
            "answeredAt": "2025-07-30T10:00:05.000Z",
            "completedAt": "2025-07-30T10:05:00.000Z",
            "recordingUrl": "https://api.openphone.com/v1/call-recordings/CALL123456789",
            "voicemailUrl": None,
            "callerId": "+1234567890",
            "answeredBy": "USER123"
        }
    },
    "id": "WEBHOOK123461",
    "type": "call.completed"
}

CALL_MISSED_PAYLOAD = {
    "apiVersion": "v1",
    "createdAt": "2025-07-30T10:00:30.000Z",
    "data": {
        "object": {
            "id": "CALL123456790",
            "object": "call",
            "status": "no-answer",
            "missedAt": "2025-07-30T10:00:30.000Z"
        }
    },
    "id": "WEBHOOK123462",
    "type": "call.missed"
}

CALL_ANSWERED_PAYLOAD = {
    "apiVersion": "v1",
    "createdAt": "2025-07-30T10:00:05.000Z",
    "data": {
        "object": {
            "id": "CALL123456789",
            "answeredAt": "2025-07-30T10:00:05.000Z",
            "answeredBy": "USER123"
        }
    },
    "id": "WEBHOOK123463",
    "type": "call.answered"
}

CALL_FORWARDED_PAYLOAD = {
    "apiVersion": "v1",
    "createdAt": "2025-07-30T10:00:03.000Z",
    "data": {
        "object": {
            "id": "CALL123456791",
            "forwardedTo": "+1112223333",
            "forwardedAt": "2025-07-30T10:00:03.000Z"
        }
    },
    "id": "WEBHOOK123464",
    "type": "call.forwarded"
}

# Call Recording Events
CALL_RECORDING_COMPLETED_PAYLOAD = {
    "apiVersion": "v1",
    "createdAt": "2025-07-30T10:05:30.000Z",
    "data": {
        "object": {
            "id": "REC123456789",
            "callId": "CALL123456789",
            "url": "https://api.openphone.com/v1/call-recordings/CALL123456789",
            "duration": 300,
            "size": 2400000,  # bytes
            "createdAt": "2025-07-30T10:05:30.000Z"
        }
    },
    "id": "WEBHOOK123470",
    "type": "call.recording.completed"
}

# Call Summary Events (AI-generated)
CALL_SUMMARY_CREATED_PAYLOAD = {
    "apiVersion": "v1",
    "createdAt": "2025-07-30T10:06:00.000Z",
    "data": {
        "object": {
            "id": "SUMMARY123456",
            "callId": "CALL123456789",
            "summary": "Customer called to inquire about pricing for residential window cleaning. Discussed standard packages and scheduled estimate for next Tuesday at 2 PM.",
            "keyPoints": [
                "Customer interested in bi-monthly service",
                "Has 20 windows, 2-story home",
                "Requested eco-friendly cleaning products"
            ],
            "nextSteps": [
                "Send pricing sheet via email",
                "Schedule on-site estimate for Tuesday 2 PM",
                "Prepare quote for bi-monthly service"
            ],
            "sentiment": "positive",
            "createdAt": "2025-07-30T10:06:00.000Z"
        }
    },
    "id": "WEBHOOK123465",
    "type": "call.summary.completed"
}

CALL_SUMMARY_UPDATED_PAYLOAD = {
    "apiVersion": "v1",
    "createdAt": "2025-07-30T10:07:00.000Z",
    "data": {
        "object": {
            "id": "SUMMARY123456",
            "callId": "CALL123456789",
            "summary": "Customer called to inquire about pricing for residential window cleaning. Discussed standard packages and scheduled estimate for next Tuesday at 2 PM. Customer mentioned they have pets.",
            "updatedAt": "2025-07-30T10:07:00.000Z"
        }
    },
    "id": "WEBHOOK123466",
    "type": "call_summary.updated"
}

# Call Transcript Events (AI-generated)
CALL_TRANSCRIPT_CREATED_PAYLOAD = {
    "apiVersion": "v1",
    "createdAt": "2025-07-30T10:06:30.000Z",
    "data": {
        "object": {
            "id": "TRANSCRIPT123456",
            "callId": "CALL123456789",
            "transcript": {
                "dialogue": [
                    {
                        "speaker": "Agent",
                        "text": "Good morning! Thanks for calling Bob's Window Cleaning. How can I help you today?",
                        "timestamp": "00:00:02"
                    },
                    {
                        "speaker": "Customer",
                        "text": "Hi, I'm looking to get a quote for window cleaning at my home.",
                        "timestamp": "00:00:08"
                    },
                    {
                        "speaker": "Agent",
                        "text": "I'd be happy to help with that. Can you tell me how many windows you have?",
                        "timestamp": "00:00:14"
                    },
                    {
                        "speaker": "Customer",
                        "text": "We have about 20 windows, it's a two-story house.",
                        "timestamp": "00:00:20"
                    }
                ],
                "confidence": 0.95,
                "language": "en-US"
            },
            "createdAt": "2025-07-30T10:06:30.000Z"
        }
    },
    "id": "WEBHOOK123467",
    "type": "call.transcript.completed"
}

CALL_TRANSCRIPT_UPDATED_PAYLOAD = {
    "apiVersion": "v1",
    "createdAt": "2025-07-30T10:08:00.000Z",
    "data": {
        "object": {
            "id": "TRANSCRIPT123456",
            "callId": "CALL123456789",
            "transcript": {
                "dialogue": [
                    # Updated with corrections
                ],
                "confidence": 0.98,
                "updatedAt": "2025-07-30T10:08:00.000Z"
            }
        }
    },
    "id": "WEBHOOK123468",
    "type": "call_transcript.updated"
}

# Validation Token Event
TOKEN_VALIDATED_PAYLOAD = {
    "apiVersion": "v1",
    "createdAt": "2025-07-30T10:00:00.000Z",
    "data": {
        "message": "Webhook endpoint validated successfully"
    },
    "id": "WEBHOOK123469",
    "type": "token.validated"
}

# All event types for reference (from OpenPhone API docs)
ALL_EVENT_TYPES = [
    "message.received",
    "message.delivered",
    "call.completed",
    "call.recording.completed",
    "call.summary.completed",
    "call.transcript.completed"
]

# Payload validation functions
def validate_webhook_payload(payload):
    """Validate a webhook payload has required fields"""
    required_fields = ['id', 'type', 'apiVersion', 'data']
    
    for field in required_fields:
        if field not in payload:
            return False, f"Missing required field: {field}"
    
    if payload['type'] not in ALL_EVENT_TYPES:
        return False, f"Unknown event type: {payload['type']}"
    
    return True, "Valid payload"

def get_media_from_message(payload):
    """Extract media URLs from a message payload"""
    try:
        return payload.get('data', {}).get('object', {}).get('media', [])
    except:
        return []

def test_all_payloads():
    """Test that all example payloads are valid"""
    # Only test the actual webhook types available in OpenPhone API
    payloads = {
        'message.received': MESSAGE_RECEIVED_PAYLOAD,
        'message.delivered': MESSAGE_DELIVERED_PAYLOAD,
        'call.completed': CALL_COMPLETED_PAYLOAD,
        'call.recording.completed': CALL_RECORDING_COMPLETED_PAYLOAD,
        'call.summary.completed': CALL_SUMMARY_CREATED_PAYLOAD,
        'call.transcript.completed': CALL_TRANSCRIPT_CREATED_PAYLOAD
    }
    
    print("Testing all webhook payload examples...")
    for event_type, payload in payloads.items():
        valid, message = validate_webhook_payload(payload)
        if valid:
            print(f"✅ {event_type}: Valid")
            # Check for media in message events
            if event_type.startswith('message.'):
                media = get_media_from_message(payload)
                if media:
                    print(f"   📎 Contains {len(media)} media attachments")
        else:
            print(f"❌ {event_type}: {message}")
    
    print("\nAll payloads tested!")

if __name__ == "__main__":
    test_all_payloads()