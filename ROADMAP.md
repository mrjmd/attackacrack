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

**Activity Model (Expanded)**
```python
class Activity(db.Model):
    # Existing fields
    id = db.Column(db.Integer, primary_key=True)
    contact_id = db.Column(db.Integer, db.ForeignKey('contact.id'))
    conversation_id = db.Column(db.String(100))  # OpenPhone conversation ID
    openphone_id = db.Column(db.String(100), unique=True)
    
    # Enhanced fields
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    activity_type = db.Column(db.String(20))  # 'call', 'message'
    direction = db.Column(db.String(10))  # 'inbound', 'outbound'
    status = db.Column(db.String(50))  # 'answered', 'missed', 'delivered', etc.
    body = db.Column(db.Text)
    duration_seconds = db.Column(db.Integer, nullable=True)
    recording_url = db.Column(db.String(500), nullable=True)
    voicemail_url = db.Column(db.String(500), nullable=True)
    transcript = db.Column(db.Text, nullable=True)
    media_urls = db.Column(db.JSON, nullable=True)  # List of MMS attachment URLs
    created_at = db.Column(db.DateTime)
    ai_summary = db.Column(db.Text, nullable=True)  # For future AI content
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

- Create comprehensive import script that populates all new models
- Fetch and store User data from OpenPhone API
- Import all historical conversations, messages, and calls
- Handle media attachments and store URLs
- Implement error handling and resume capability

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