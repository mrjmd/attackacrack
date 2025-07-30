# OpenPhone Webhook Integration Documentation

## Overview

This document describes the webhook integration with OpenPhone, including all supported event types, payload structures, and implementation details.

## Supported Webhook Events

### Message Events

#### 1. `message.received` (Incoming Message)
```json
{
  "type": "message.received",
  "data": {
    "object": {
      "id": "MSG123456789",
      "conversationId": "CONV123456",
      "direction": "incoming",
      "from": "+1234567890",
      "to": ["+0987654321"],
      "text": "Message content",
      "media": [
        "https://media.openphone.com/attachment1.jpg",
        "https://media.openphone.com/attachment2.pdf"
      ],
      "status": "received",
      "createdAt": "2025-07-30T10:00:00.000Z"
    }
  }
}
```
**Key Features:**
- ✅ `media` array contains URLs for attachments (images, PDFs, etc.)
- ✅ Automatically creates/updates contact and conversation
- ✅ Stores media URLs in database for display

#### 2. `message.sent` (Outgoing Message)
Similar to received, but `direction: "outgoing"`

#### 3. `message.delivered`
Updates message status to "delivered"

#### 4. `message.failed`
Updates message status to "failed" with error details

### Call Events

#### 1. `call.completed`
```json
{
  "type": "call.completed",
  "data": {
    "object": {
      "id": "CALL123456789",
      "status": "completed",
      "duration": 300,
      "participants": ["+1234567890", "+0987654321"],
      "recordingUrl": "https://api.openphone.com/v1/call-recordings/CALL123456789",
      "answeredAt": "2025-07-30T10:00:05.000Z",
      "completedAt": "2025-07-30T10:05:00.000Z"
    }
  }
}
```
**Key Features:**
- ✅ Stores call duration and recording URL
- ✅ Links to existing conversation or creates new one
- ✅ Recording URL can be fetched separately via API

#### 2. `call.started`, `call.missed`, `call.answered`, `call.forwarded`
Various call state updates

#### 3. `call.recording.completed`
```json
{
  "type": "call.recording.completed",
  "data": {
    "object": {
      "id": "REC123456789",
      "callId": "CALL123456789",
      "url": "https://api.openphone.com/v1/call-recordings/CALL123456789",
      "duration": 300,
      "size": 2400000
    }
  }
}
```
**Key Features:**
- ✅ Fired when call recording is ready (separate from call.completed)
- ✅ Updates existing call activity with recording URL
- ✅ Includes recording duration and file size

### AI-Generated Content Events

#### 1. `call_summary.created`
```json
{
  "type": "call_summary.created",
  "data": {
    "object": {
      "callId": "CALL123456789",
      "summary": "Customer inquired about pricing...",
      "keyPoints": ["Point 1", "Point 2"],
      "nextSteps": ["Action 1", "Action 2"],
      "sentiment": "positive"
    }
  }
}
```
**Key Features:**
- ✅ AI-generated summary attached to existing call
- ✅ Includes key points and recommended next steps
- ✅ Sentiment analysis

#### 2. `call_transcript.created`
```json
{
  "type": "call_transcript.created",
  "data": {
    "object": {
      "callId": "CALL123456789",
      "transcript": {
        "dialogue": [
          {
            "speaker": "Agent",
            "text": "Hello, how can I help?",
            "timestamp": "00:00:02"
          }
        ],
        "confidence": 0.95
      }
    }
  }
}
```
**Key Features:**
- ✅ Full call transcript with speaker identification
- ✅ Timestamps for each dialogue segment
- ✅ Confidence score

## Webhook Security

All webhooks are verified using HMAC-SHA256 signature:
```python
signature = hmac.new(
    key=OPENPHONE_WEBHOOK_SIGNING_KEY.encode('utf-8'),
    msg=request_body,
    digestmod=hashlib.sha256
).hexdigest()
```

The signature is passed in the `x-openphone-signature-v1` header.

## Testing Webhooks

### 1. List Current Webhooks
```bash
python manage_webhooks.py list
```

### 2. Create All Webhooks
```bash
python manage_webhooks.py create
```

### 3. Test Webhook Handler
```bash
# Test all event types
python test_webhook_handler.py all

# Test media handling specifically
python test_webhook_handler.py media

# Test AI content handling
python test_webhook_handler.py ai

# Run all tests
python test_webhook_handler.py full
```

### 4. Manual Testing with cURL
```bash
# Generate signature (requires signing key)
PAYLOAD='{"type":"message.received","data":{"object":{"id":"TEST123"}}}'
SIGNATURE=$(echo -n "$PAYLOAD" | openssl dgst -sha256 -hmac "$SIGNING_KEY" | cut -d' ' -f2)

# Send webhook
curl -X POST http://localhost:5000/api/webhooks/openphone \
  -H "Content-Type: application/json" \
  -H "x-openphone-signature-v1: $SIGNATURE" \
  -d "$PAYLOAD"
```

## Database Schema

Webhooks update the following models:

### Activity
- `openphone_id`: Unique ID from OpenPhone
- `activity_type`: 'message' or 'call'
- `direction`: 'incoming' or 'outgoing'
- `body`: Message text
- `media_urls`: JSON array of media attachment URLs
- `recording_url`: URL for call recordings
- `ai_summary`: AI-generated call summary
- `ai_transcript`: AI-generated call transcript
- `status`: Current status

### WebhookEvent
- `event_id`: Webhook event ID
- `event_type`: Type of webhook
- `payload`: Complete webhook payload (JSON)
- `processed`: Boolean flag
- `error_message`: Any processing errors

## Implementation Notes

1. **Idempotency**: Webhooks are idempotent - same event can be processed multiple times safely
2. **Media Storage**: Media URLs are stored but files are not downloaded automatically
3. **Contact Creation**: Unknown phone numbers automatically create new contacts
4. **Conversation Grouping**: Messages/calls are grouped by contact into conversations
5. **Real-time Updates**: Webhook events update the UI in real-time

## Troubleshooting

### Common Issues

1. **403 Forbidden**: Check webhook signing key is configured correctly
2. **404 Not Found**: Ensure webhook endpoint URL is correct
3. **500 Server Error**: Check logs for database or processing errors

### Debug Mode
Enable detailed logging:
```python
import logging
logging.getLogger('services.openphone_webhook_service').setLevel(logging.DEBUG)
```

## Future Enhancements

1. **Media Download Queue**: Automatically download and store media files locally
2. **Webhook Retry Logic**: Handle temporary failures with exponential backoff
3. **Event Streaming**: Push webhook events to frontend via WebSockets
4. **Analytics**: Track webhook processing metrics and success rates