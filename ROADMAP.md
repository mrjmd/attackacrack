# Attack-a-Crack CRM: Development Roadmap

**Version:** 2.3  
**Last Updated:** July 28, 2025

## Executive Summary

The Attack-a-Crack CRM is a comprehensive platform designed to manage every aspect of the business from lead generation to final payment. This roadmap outlines a phased development approach that prioritizes stability and foundational work before building advanced features.

## Current System Status

### ✅ Completed
- **Production-Ready Architecture:** Fully containerized with Docker/Docker Compose, Gunicorn, PostgreSQL
- **Background Task Processing:** Migrated from APScheduler to production-grade Celery/Redis stack
- **Secure Webhooks:** OpenPhone webhook endpoint with signature verification
- **Real-time Updates:** Live polling for new text messages on dashboard
- **Centralized Database:** SQLAlchemy models with comprehensive relationships

### ⚠️ Critical Alert
- **Empty Production Database:** Historical data import from OpenPhone must be rebuilt from scratch

## Development Philosophy: Stability First, Features Immediately After

This roadmap is organized into distinct phases where each phase is a prerequisite for the next. This approach minimizes technical debt and prevents regressions by front-loading foundational work.

---

## Phase 1: Data Foundation & Enrichment (IMMEDIATE PRIORITY)

**Goal:** Re-establish the database as the absolute "single source of truth" with a schema that captures every available data point and supports future feature requirements.

### Task 1.1: Enhance Database Models for Rich Communication & Marketing

**Priority:** CRITICAL  
**Estimated Effort:** 2-3 days

#### Design Philosophy: Unified Activity Model

The system uses a single `Activity` model to store all communication types (messages, calls, voicemails) along with their AI-generated enhancements (summaries, transcripts). This design enables:
- Simplified queries for the unified conversation view
- Consistent handling of all communication types
- Easy addition of new activity types
- Reduced database complexity

#### New/Enhanced Models

**User Model (New)**
```python
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    openphone_user_id = db.Column(db.String(100), unique=True)
    first_name = db.Column(db.String(50))
    last_name = db.Column(db.String(50))
    email = db.Column(db.String(120))
```

**PhoneNumber Model (New)**
```python
class PhoneNumber(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    openphone_id = db.Column(db.String(100), unique=True)
    phone_number = db.Column(db.String(20), unique=True)
    name = db.Column(db.String(100), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
```

**Activity Model (Expanded)**
```python
class Activity(db.Model):
    # Core fields
    id = db.Column(db.Integer, primary_key=True)
    openphone_id = db.Column(db.String(100), unique=True)
    conversation_id = db.Column(db.Integer, db.ForeignKey('conversation.id'))
    contact_id = db.Column(db.Integer, db.ForeignKey('contact.id'), nullable=True)
    
    # Activity details
    activity_type = db.Column(db.String(20))  # 'call', 'message', 'voicemail'
    direction = db.Column(db.String(10))  # 'incoming', 'outgoing'
    status = db.Column(db.String(50))  # 'answered', 'missed', 'delivered', 'completed', etc.
    
    # Participants
    from_number = db.Column(db.String(20), nullable=True)
    to_numbers = db.Column(db.JSON, nullable=True)  # Array for multiple recipients
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    phone_number_id = db.Column(db.String(100), nullable=True)  # OpenPhone number used
    
    # Message content
    body = db.Column(db.Text, nullable=True)
    media_urls = db.Column(db.JSON, nullable=True)  # Array of media attachment URLs
    
    # Call-specific fields
    duration_seconds = db.Column(db.Integer, nullable=True)
    recording_url = db.Column(db.String(500), nullable=True)
    voicemail_url = db.Column(db.String(500), nullable=True)
    answered_at = db.Column(db.DateTime, nullable=True)
    answered_by = db.Column(db.String(100), nullable=True)  # User ID
    completed_at = db.Column(db.DateTime, nullable=True)
    initiated_by = db.Column(db.String(100), nullable=True)  # User ID
    forwarded_from = db.Column(db.String(100), nullable=True)
    forwarded_to = db.Column(db.String(100), nullable=True)
    
    # AI-generated content (stored in same model for unified view)
    ai_summary = db.Column(db.Text, nullable=True)  # Call summary
    ai_next_steps = db.Column(db.Text, nullable=True)  # Recommended actions
    ai_transcript = db.Column(db.JSON, nullable=True)  # Call transcript dialogue
    ai_content_status = db.Column(db.String(50), nullable=True)  # 'pending', 'completed', 'failed'
    
    # Timestamps
    created_at = db.Column(db.DateTime)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
```

**Conversation Model (Enhanced)**
```python
class Conversation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    openphone_id = db.Column(db.String(100), unique=True, nullable=True)
    contact_id = db.Column(db.Integer, db.ForeignKey('contact.id'), nullable=False)
    
    # Conversation details
    name = db.Column(db.String(200), nullable=True)  # Display name
    participants = db.Column(db.String(500), nullable=True)  # Comma-separated phone numbers
    phone_number_id = db.Column(db.String(100), nullable=True)  # Associated OpenPhone number
    
    # Activity tracking
    last_activity_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_activity_type = db.Column(db.String(20), nullable=True)  # 'message' or 'call'
    last_activity_id = db.Column(db.String(100), nullable=True)  # OpenPhone activity ID
    
    activities = db.relationship('Activity', backref='conversation', lazy=True, cascade="all, delete-orphan")
```

**WebhookEvent Model (New - for reliability)**
```python
class WebhookEvent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.String(100), unique=True)  # OpenPhone event ID
    event_type = db.Column(db.String(50))  # 'message.new', 'call.completed', etc.
    api_version = db.Column(db.String(10))  # 'v1', 'v2', 'v4'
    payload = db.Column(db.JSON)  # Full webhook payload for reprocessing
    processed = db.Column(db.Boolean, default=False)
    processed_at = db.Column(db.DateTime, nullable=True)
    error_message = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
```

**Campaign Model (Enhanced)**
```python
class Campaign(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default='draft')  # 'draft', 'running', 'paused', 'complete'
    template_a = db.Column(db.Text)  # A/B test variant A
    template_b = db.Column(db.Text, nullable=True)  # A/B test variant B
    quiet_hours_start = db.Column(db.Time, default=time(20, 0))  # 8 PM
    quiet_hours_end = db.Column(db.Time, default=time(9, 0))  # 9 AM
    on_existing_contact = db.Column(db.String(50), default='ignore')  # 'ignore', 'flag_for_review', 'adapt_script'
```

**CampaignMembership Model (Enhanced)**
```python
class CampaignMembership(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    contact_id = db.Column(db.Integer, db.ForeignKey('contact.id'))
    campaign_id = db.Column(db.Integer, db.ForeignKey('campaign.id'))
    status = db.Column(db.String(50), default='pending')  # 'pending', 'sent', 'failed', 'replied_positive', 'replied_negative', 'suppressed'
    variant_sent = db.Column(db.String(1), nullable=True)  # 'A' or 'B'
    sent_at = db.Column(db.DateTime, nullable=True)
    reply_activity_id = db.Column(db.Integer, db.ForeignKey('activity.id'), nullable=True)
```

### Task 1.2: Implement Robust Historical Data Import

**Priority:** CRITICAL  
**Estimated Effort:** 3-4 days

#### Implementation Details

**Data Sources from OpenPhone API:**
1. **Phone Numbers** (`/v1/phone-numbers`)
   - Fetch all active phone numbers
   - Store OpenPhone IDs for relationship mapping

2. **Conversations** (`/v1/conversations`)
   - Paginated fetch with `pageToken`
   - Extract participants, last activity info
   - Link to contacts by phone number matching

3. **Messages** (`/v1/messages`)
   - Fetch all historical messages
   - Handle multiple recipients (group messages)
   - Download and store media URLs
   - Map to conversations and contacts

4. **Calls** (`/v1/calls`)
   - Import complete call history
   - Capture all metadata (duration, participants, forwarding)
   - Store recording URLs

5. **Call Enhancements** (Business plan only)
   - Call Summaries (`/v1/call-summaries/{callId}`)
   - Call Transcripts (`/v1/call-transcripts/{callId}`)
   - Store in Activity model's AI fields

6. **Users** (from webhook events or API if available)
   - Extract user IDs from call/message data
   - Build user profiles from available data

**Import Strategy:**
```python
# Pseudocode for import process
def import_openphone_data():
    # 1. Import phone numbers first (needed for relationships)
    import_phone_numbers()
    
    # 2. Import conversations (creates conversation records)
    import_conversations()
    
    # 3. Import messages and calls (creates activity records)
    import_messages()  # Uses pagination
    import_calls()     # Uses pagination
    
    # 4. Enhance calls with AI content (if available)
    enhance_calls_with_ai()
    
    # 5. Link activities to contacts
    match_activities_to_contacts()
    
    # 6. Update conversation last_activity fields
    update_conversation_metadata()
```

**Error Handling & Resume Capability:**
- Track import progress in database
- Store last successful page token
- Implement retry logic with exponential backoff
- Log all API errors for review
- Support resuming interrupted imports

**Technical Considerations:**
- **Authentication**: Use API key in `Authorization` header (not Bearer token)
- **Rate Limiting**: Respect OpenPhone's rate limits with throttling
- **Webhook Versions**: Handle different API versions (v1, v2, v4) in webhook events
- **Data Integrity**: Store webhook event IDs to prevent duplicate processing
- **Media Storage**: Decide whether to store media URLs only or download files locally

---

## Phase 2: Core Workflow & Growth Engine (IMMEDIATE BUSINESS VALUE)

**Goal:** Build primary features for daily operations and growth, leveraging the rich, reliable dataset.

### Task 2.1: Unified Conversation View

**Priority:** HIGH  
**Estimated Effort:** 4-5 days

#### Features
- **Complete Timeline:** Chronological view of every interaction (calls, messages, emails)
- **Visual Distinction:** Different icons and colors based on activity type and status
- **Media Handling:** Clickable thumbnails for MMS attachments with full-size view
- **Call Integration:** Embedded audio players for recordings, expandable transcripts
- **Email Integration:** Seamless email threads woven into timeline

#### Technical Implementation
1. Redesign `contact_detail.html` template
2. Fetch all Activity records sorted chronologically
3. Implement media viewer component
4. Add audio player for call recordings
5. Integrate Gmail API for email display

### Task 2.2: Marketing Campaign Engine (MVP)

**Priority:** HIGH  
**Estimated Effort:** 6-7 days

#### Features
- **Campaign Builder:** Create SMS campaigns with A/B testing
- **Smart Scheduling:** Respect quiet hours and throttling limits
- **Contact Rules:** Handle existing contacts per campaign settings
- **Real-time Analytics:** Campaign performance dashboard
- **Reply Classification:** AI-powered positive/negative reply detection

#### Technical Implementation
1. Create `marketing_routes.py` blueprint
2. Build campaign management UI
3. Implement `execute_sms_campaign` Celery task
4. Create `send_throttled_sms` task with rate limiting
5. Add webhook handler for reply classification
6. Build analytics dashboard

---

## Phase 3: Business Intelligence & Financial Integration

**Goal:** Provide real-time business overview and replace other financial software.

### Task 3.1: Enhanced Quote & Invoice Lifecycle

**Estimated Effort:** 5-6 days

#### Automated Workflow Triggers
1. **Quote Created in CRM** → Push to QuickBooks
2. **Quote Sent from QuickBooks** → Trigger SMS follow-up
3. **Quote Approved** → Trigger scheduling algorithm
4. **Morning of Job** → Auto-convert Quote to Invoice
5. **Invoice Paid** → Update CRM status via webhook

### Task 3.2: Financial Dashboard & Profitability Engine

**Estimated Effort:** 4-5 days

#### Features
- Key metrics dashboard with callback tracking
- Revenue charts and trend analysis
- Monthly PDF report generation
- Bank statement import with AI categorization
- Profitability analysis and spending suggestions

---

## Phase 4: Advanced AI & Communication Excellence

**Goal:** Leverage cutting-edge AI for operational efficiency and ensure 100% reliable communication history.

### Task 4.1: Resilient Data Sync System

**Estimated Effort:** 3-4 days

#### Features
- **Real-time Webhooks:** Instant updates for critical events
- **Nightly Reconciliation:** Ensure data integrity
- **System Health Monitoring:** UI status indicator for data sync health
- **Automatic Recovery:** Handle missed events gracefully

### Task 4.2: AI-Powered Email Triage

**Estimated Effort:** 4-5 days

#### Features
- **Automatic Classification:** Customer inquiry, vendor, bill, calendar, marketing/spam
- **Smart Actions:** Auto-archive, label, or flag for attention
- **Background Processing:** Celery task checks Gmail every few minutes
- **Integration:** Results visible in Unified Inbox

### Task 4.3: AI Image Analysis for Quoting

**Estimated Effort:** 5-6 days

#### Features
- **Automatic Trigger:** Analysis on media message receipt
- **Rich Context Prompting:** Include property data and conversation history
- **Structured Output:** JSON with damage type, confidence, recommendations
- **Confidence-Based Workflow:** 
  - High: Send quote directly
  - Medium: Create draft for review
  - Low: Ask clarifying questions

---

## Phase 5: Advanced Operations & Scheduling

### Task 5.1: Intelligent Scheduling Algorithm

**Estimated Effort:** 7-8 days

#### Features
- **Multi-Technician Support:** Individual base locations and schedules
- **Smart Duration Estimation:** Based on job type and quote value
- **Geographic Clustering:** Minimize travel time week-by-week
- **Customer Self-Scheduling:** One-click scheduling links

### Task 5.2: Multi-Source Data Importers

**Estimated Effort:** 3-4 days

#### Features
- **Patchwork Strategy:** Define source of truth for different data types
- **Upsert Logic:** Enrich existing contacts without overwriting
- **Conflict Resolution:** Flag conflicts for manual review
- **Data Source Tracking:** Track where each piece of data originated

---

## Technical Excellence (Ongoing)

### Comprehensive Test Suite
- **Target:** >90% code coverage
- **Tools:** pytest, pytest-cov
- **CI/CD:** GitHub Actions for automated testing

### Application Security
- **Authentication:** Full user login system
- **Webhook Security:** Signature verification for all endpoints
- **Input Validation:** Systematic review of all forms and APIs

### Frontend Scalability (Future)
- **Framework Migration:** React or Vue for complex interfaces
- **Phased Approach:** Start with Marketing and Scheduling dashboards

---

## Implementation Priority Matrix

### Phase 1 (Immediate - Next 1-2 weeks)
1. ✅ **Database Schema Enhancement** (Task 1.1)
2. ✅ **Historical Data Import** (Task 1.2)

### Phase 2 (High Priority - Next 2-3 weeks)
3. **Unified Conversation View** (Task 2.1)
4. **Marketing Campaign Engine MVP** (Task 2.2)

### Phase 3 (Medium Priority - Next 4-6 weeks)
5. **Enhanced Quote/Invoice Lifecycle** (Task 3.1)
6. **Financial Dashboard** (Task 3.2)

### Phase 4 (Advanced Features - 2-3 months)
7. **Resilient Data Sync** (Task 4.1)
8. **AI Email Triage** (Task 4.2)
9. **AI Image Analysis** (Task 4.3)

### Phase 5 (Long-term - 3-6 months)
10. **Intelligent Scheduling** (Task 5.1)
11. **Multi-Source Importers** (Task 5.2)

---

## Success Metrics

### Phase 1
- [ ] All models created and migrated successfully
- [ ] Historical data import completed with 100% accuracy
- [ ] Database serves as single source of truth

### Phase 2
- [ ] Unified conversation view reduces context switching
- [ ] Marketing campaigns generate measurable ROI
- [ ] Campaign analytics provide actionable insights

### Phase 3
- [ ] Quote-to-invoice workflow fully automated
- [ ] Financial dashboard provides real-time business health
- [ ] Monthly reporting automated

### Phase 4
- [ ] Data sync reliability reaches 99.9%
- [ ] Email triage reduces manual email processing by 80%
- [ ] AI image analysis speeds up quoting process by 50%

---

## Risk Mitigation

### Technical Risks
- **Database Migration Failures:** Comprehensive backup and rollback procedures
- **API Rate Limits:** Implement exponential backoff and request queuing
- **Data Loss:** Multiple backup strategies and integrity checks

### Business Risks
- **Feature Complexity:** MVP approach with iterative improvements
- **User Adoption:** Extensive documentation and training materials
- **Performance Issues:** Load testing and monitoring implementation

---

## Notes for Developers

### Code Organization
- Each phase should be developed in feature branches
- Database migrations must be thoroughly tested
- All new features require corresponding tests
- API integrations need comprehensive error handling

### Documentation Requirements
- Update this roadmap as features are completed
- Maintain technical documentation for each major feature
- Create user guides for new functionality
- Document all API integrations and webhook handlers

---

*This roadmap is a living document and should be updated as development progresses and business requirements evolve.*