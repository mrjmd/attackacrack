# OpenPhone Webhook Integration Guide

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Supported Webhook Events](#supported-webhook-events)
   - [Message Events](#message-events)
   - [Call Events](#call-events)
   - [AI-Generated Content Events](#ai-generated-content-events)
4. [Implementation Details](#implementation-details)
   - [Security](#security)
   - [Database Schema](#database-schema)
   - [Key Features](#key-features)
5. [Webhook Management](#webhook-management)
6. [Testing](#testing)
7. [Troubleshooting](#troubleshooting)
8. [Production Deployment](#production-deployment)

## Overview

This document provides comprehensive information about the OpenPhone webhook integration. Based on actual API documentation and testing, OpenPhone provides **6 webhook event types** that enable real-time updates for messages, calls, and AI-generated content.

### Actual Available Webhook Types

1. **`message.received`** - Incoming message received
2. **`message.delivered`** - Outgoing message delivered  
3. **`call.completed`** - Call finished (any status)
4. **`call.recording.completed`** - Call recording is ready
5. **`call.summary.completed`** - AI call summary generated
6. **`call.transcript.completed`** - AI call transcript generated

## Architecture

### Current Implementation Files

- **`services/openphone_webhook_service.py`** (360 lines) ✅
  - Streamlined implementation matching current database schema
  - Supports media attachments
  - Clean, maintainable architecture
  
- **`routes/api_routes.py`**
  - Contains `/api/webhooks/openphone` endpoint
  - Uses `OpenPhoneWebhookService`
  - HMAC signature verification

- **`manage_webhooks.py`**
  - Webhook management utility
  - Can list, create, test, and delete webhooks

### Key Benefits

1. **Simpler Code** - Focused on actual available events
2. **Media Support** - Captures image/file attachments
3. **Better Testing** - Comprehensive test coverage
4. **Current Schema** - Matches actual database models
5. **Cleaner Separation** - Each webhook type has dedicated handler

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

#### 2. `message.delivered` (Outgoing Message Delivered)
Updates the delivery status of sent messages.

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
- ✅ Recording URL may be included if available immediately

#### 2. `call.recording.completed`
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

#### 1. `call.summary.completed`
```json
{
  "type": "call.summary.completed",
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

#### 2. `call.transcript.completed`
```json
{
  "type": "call.transcript.completed",
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

## Implementation Details

### Security

All webhooks are verified using HMAC-SHA256 signature:

```python
signature = hmac.new(
    key=OPENPHONE_WEBHOOK_SIGNING_KEY.encode('utf-8'),
    msg=request_body,
    digestmod=hashlib.sha256
).hexdigest()
```

The signature is passed in the `x-openphone-signature-v1` header.

### Database Schema

Webhooks update the following models:

#### Activity Model
- `openphone_id`: Unique ID from OpenPhone
- `activity_type`: 'message' or 'call'
- `direction`: 'incoming' or 'outgoing'
- `body`: Message text
- `media_urls`: JSON array of media attachment URLs
- `recording_url`: URL for call recordings
- `ai_summary`: AI-generated call summary
- `ai_transcript`: AI-generated call transcript
- `status`: Current status

#### WebhookEvent Model
- `event_id`: Webhook event ID
- `event_type`: Type of webhook
- `payload`: Complete webhook payload (JSON)
- `processed`: Boolean flag
- `error_message`: Any processing errors

### Key Features

1. **Media Attachment Support** 📎
   - Message webhooks capture the `media` array
   - Media URLs stored in `activity.media_urls`
   - UI displays media attachments

2. **Call Recording Handling** 🎙️
   - `call.completed` includes recording URL if available
   - `call.recording.completed` updates call when ready later
   - Handles async recording processing

3. **AI Content Integration** 🤖
   - Call summaries with key points and next steps
   - Full transcripts with speaker identification
   - Sentiment analysis

4. **Idempotency**
   - Webhooks are idempotent - same event can be processed multiple times safely
   
5. **Automatic Contact Creation**
   - Unknown phone numbers automatically create new contacts
   
6. **Conversation Grouping**
   - Messages/calls are grouped by contact into conversations

## Webhook Management

### List Current Webhooks
```bash
python manage_webhooks.py list
```

### Create All Webhooks
```bash
python manage_webhooks.py create
```

This creates a single webhook subscription with all 6 events:
```json
{
  "url": "https://your-domain.com/api/webhooks/openphone",
  "events": [
    "message.received",
    "message.delivered",
    "call.completed",
    "call.recording.completed",
    "call.summary.completed",
    "call.transcript.completed"
  ]
}
```

### Test Webhook Connectivity
```bash
python manage_webhooks.py test
```

### Delete All Webhooks
```bash
python manage_webhooks.py delete
```

## Testing

### Automated Test Suite

#### Test All Event Types
```bash
python test_webhook_handler.py all
```

#### Test Media Handling
```bash
python test_webhook_handler.py media
```

#### Test AI Content
```bash
python test_webhook_handler.py ai
```

#### Run Full Test Suite
```bash
python test_webhook_handler.py full
```

### Manual Testing with cURL

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

### Example Test Payloads

Test payloads are available in `webhook_payload_examples.py` for all event types.

## Troubleshooting

### Common Issues

1. **403 Forbidden**
   - Check webhook signing key is configured correctly
   - Verify `OPENPHONE_WEBHOOK_SIGNING_KEY` environment variable

2. **404 Not Found**
   - Ensure webhook endpoint URL is correct
   - Check `WEBHOOK_BASE_URL` environment variable

3. **500 Server Error**
   - Check logs for database or processing errors
   - Verify database schema matches expectations

### Debug Mode

Enable detailed logging:
```python
import logging
logging.getLogger('services.openphone_webhook_service').setLevel(logging.DEBUG)
```

### Monitoring

- Watch logs for webhook events
- Verify media attachments appear in UI
- Check AI summaries/transcripts populate correctly
- Monitor `webhook_events` table for processing status

## Production Deployment

### Step 1: Environment Configuration
```bash
# Set required environment variables
export OPENPHONE_WEBHOOK_SIGNING_KEY="your-signing-key"
export WEBHOOK_BASE_URL="https://your-domain.com"
export OPENPHONE_API_KEY="your-api-key"
```

### Step 2: Clean Up Old Code
```bash
# Remove deprecated webhook service
rm services/webhook_sync_service.py

# Test everything still works
python test_webhook_handler.py full
```

### Step 3: Deploy Webhooks
```bash
# Create webhook subscriptions
python manage_webhooks.py create

# Verify they're active
python manage_webhooks.py list
```

### Step 4: Monitor & Validate
- Watch application logs for incoming webhook events
- Verify media attachments appear in conversations
- Check that AI summaries and transcripts populate
- Monitor webhook processing success rate

### Important Notes

1. **Limited Event Types**: Only 6 webhook types are available (not the 15+ we initially thought)
2. **No Intermediate States**: No `.started`, `.answered`, or `.missed` events
3. **Completion Events Only**: All events use `.completed` suffix
4. **No Outgoing Message Events**: We don't get notified when messages are sent (only delivered)
5. **Media Discovery**: The `media` array in messages was not documented but is available!

### Risk Mitigation

- All webhooks are idempotent (safe to replay)
- Old events won't break the handler
- Extensive logging for debugging
- Test suite validates all scenarios
- Automatic error recovery and retry logic